#!/usr/bin/env python3
"""world-pose generator: emits controller.yaml and rig.json from CONFIG below.

    python world-pose/generate.py            # writes controller.yaml and rig.json beside this file
    python world-pose/generate.py --check    # asserts WorldPose.prefab's hand-maintained surface against CONFIG

Edit CONFIG, rerun, then recompile built/ as a unit in a mounting Editor (CONVENTIONS.md §The gate) and
rebuild whatever rig.json moved in the prefab. Both outputs are pure functions of CONFIG. controller.yaml
declares the seven published floats and has no layers; rig.json is every number the prefab is built to,
the decode's constants included. Nothing here writes Unity assets.

WHAT THE RIG IS
---------------
An instrument: it publishes the avatar root's world position and heading, and the head's heading, as
seven unsynced floats an OSC reader decodes. Every contact is local-only, allowSelf only, on a private
tag per group, under a node held at world origin and world scale by two constraints on assets/World.prefab.

  Pos       three face-proximity boxes of edge `boxSize` at the world origin, their +Z faces turned onto
            world +X, +Y, +Z. Their sender, Pos/Sender, is position-constrained to the avatar root at
            weight g and to the pinned World node at 1 - g, so it sits at g x (root position).
  Yaw       two boxes of edge `yawBox` parked at (+PARK, 0, 0), reading world X and Z. Holder copies the
            avatar root's heading (Y only); its child Mark sits `yawArm` ahead on Holder's +Z, so the two
            readings carry sin and cos of the heading.
  HeadYaw   the same at (-PARK, 0, 0), Holder sourcing HeadAnchor: the head proxy, a node an MA BoneProxy
            moves under the humanoid Head keeping its authored world rotation, so it reads 0 with the head
            at rest over a root at heading 0 whatever the head bone's own rest frame is.

THE DECODE
----------
A face box reads (S/2 + r + d) / S for a sender of radius r whose centre sits d along the read axis from
the box centre (docs/runtime.md §Contacts: face mode is a linear unlerp from the +Z face). So
  position (metres)  = posA + posB * reading     posB = S / g,  posA = -(S/2 + r) / g
  sin, cos (heading) = yawA + yawB * reading     yawB = Sy / arm, yawA = -(Sy/2 + r) / arm
  heading (degrees)  = atan2(sin, cos)           Unity heading: clockwise seen from above, 0 = world +Z
A reading of exactly 0 is not sensing (no overlap, a stowed receiver): posA is not a position.

CONFIG
------
  prefix        the published names' prefix, the one knob a consumer renames: <prefix>/X, /Y, /Z, /YawX,
                /YawZ, /HeadYawX, /HeadYawZ. globalParams is <prefix>/*.
  controller    the emitted controller's name.
  tag           the stem of the three private collision tags: <tag>Pos, <tag>Yaw, <tag>HeadYaw.
  range         metres per axis about the world origin the position must read inside. It sets the gain
                g = (boxSize / 2) / (range * (1 + MARGIN)), so the decode and the resolution move with it.
  boxSize       the position boxes' edge, metres (the SDK editor caps a contact shape at 6).
  senderRadius  every sender's sphere radius.
  yawBox        the heading boxes' edge, metres.
  yawArm        the distance from a heading Holder to its Mark, metres.
"""

import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "prefix": "Pose",
    "controller": "WorldPose_Fx",
    "tag": "WorldPose",
    "range": 50.0,
    "boxSize": 6.0,
    "senderRadius": 0.05,
    "yawBox": 2.5,
    "yawArm": 1.0,
}

# Headroom past `range`, as a fraction of it: the position reads linearly out to about (1 + MARGIN) x range
# before a box saturates or reads 0, so a reading just outside the stated range is still a position.
MARGIN = 0.2
# The heading groups' distance from the world origin on X, clear of the position boxes.
PARK = 8.0
# Box shape rotations putting a face-proximity box's +Z face on the world axis named.
FACE = {"X": (0, 90, 0), "Y": (270, 0, 0), "Z": (0, 0, 0)}
HEAD_BONE = 10          # HumanBodyBones.Head
KEEP_ROTATION = 3       # BoneProxyAttachmentMode.AsChildKeepRotation


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qaxis(axis, deg):
    h = math.radians(deg) / 2
    s = math.sin(h)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h))


def euler(e):
    """Unity's Quaternion.Euler: Z, then X, then Y (q = qy * qx * qz)."""
    return qmul(qmul(qaxis((0, 1, 0), e[1]), qaxis((1, 0, 0), e[0])), qaxis((0, 0, 1), e[2]))


def r6(v):
    return round(v, 6) if isinstance(v, float) else [round(x, 6) for x in v]


def validate(c):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(/[A-Za-z0-9_]+)*", c["prefix"]):
        refuse("prefix must be a non-empty parameter path with no spaces or OSC metacharacters.")
    if c["boxSize"] > 6 or c["yawBox"] > 6:
        refuse("a box edge above 6: the SDK editor caps a contact shape at 6 units.")
    if not c["range"] > 0:
        refuse("range must be positive.")
    if not 0 < c["senderRadius"]:
        refuse("senderRadius must be positive.")
    g = gain(c)
    if g * c["range"] + c["senderRadius"] >= c["boxSize"] / 2:
        refuse("the sender's surface reaches the +Z face inside range: raise boxSize or lower senderRadius.")
    if not c["yawArm"] + c["senderRadius"] < c["yawBox"] / 2:
        refuse("yawArm + senderRadius must stay inside half yawBox, or a heading face saturates.")
    if not PARK - c["yawBox"] / 2 > c["boxSize"] / 2:
        refuse("the heading boxes would overlap the position boxes: lower yawBox or boxSize.")


def gain(c):
    return (c["boxSize"] / 2) / (c["range"] * (1 + MARGIN))


def names(c):
    p = c["prefix"]
    return {"X": f"{p}/X", "Y": f"{p}/Y", "Z": f"{p}/Z", "YawX": f"{p}/YawX", "YawZ": f"{p}/YawZ",
            "HeadYawX": f"{p}/HeadYawX", "HeadYawZ": f"{p}/HeadYawZ"}


def rig(c):
    validate(c)
    g = gain(c)
    S, Sy, r, arm = c["boxSize"], c["yawBox"], c["senderRadius"], c["yawArm"]
    n = names(c)
    t = c["tag"]
    pos_a, pos_b = -(S / 2 + r) / g, S / g
    yaw_a, yaw_b = -(Sy / 2 + r) / arm, Sy / arm

    def boxes(size, pairs, tag):
        return [{"parameter": n[k], "axis": ax, "rotation": list(FACE[ax]), "size": size, "tag": tag}
                for k, ax in pairs]

    return {
        "_comment": "GENERATED by world-pose/generate.py from its CONFIG; never hand-edit. The numbers WorldPose.prefab is built to.",
        "prefix": c["prefix"],
        "globalParams": [f"{c['prefix']}/*"],
        "parameters": list(n.values()),
        "gain": r6(g),
        "senderRadius": r,
        "groups": {
            "World/Pos": {"localPosition": [0, 0, 0], "tag": f"{t}Pos",
                          "receivers": boxes(S, (("X", "X"), ("Y", "Y"), ("Z", "Z")), f"{t}Pos"),
                          "sender": {"path": "World/Pos/Sender", "localPosition": [0, 0, 0],
                                     "position": {"sources": ["", "World"], "weights": [r6(g), r6(1 - g)]}}},
            "World/Yaw": {"localPosition": [PARK, 0, 0], "tag": f"{t}Yaw",
                          "receivers": boxes(Sy, (("YawX", "X"), ("YawZ", "Z")), f"{t}Yaw"),
                          "holder": {"path": "World/Yaw/Holder", "rotationY": ""},
                          "sender": {"path": "World/Yaw/Holder/Mark", "localPosition": [0, 0, arm]}},
            "World/HeadYaw": {"localPosition": [-PARK, 0, 0], "tag": f"{t}HeadYaw",
                              "receivers": boxes(Sy, (("HeadYawX", "X"), ("HeadYawZ", "Z")), f"{t}HeadYaw"),
                              "holder": {"path": "World/HeadYaw/Holder", "rotationY": "HeadAnchor"},
                              "sender": {"path": "World/HeadYaw/Holder/Mark", "localPosition": [0, 0, arm]}},
        },
        "headAnchor": {"path": "HeadAnchor", "boneReference": HEAD_BONE, "attachmentMode": KEEP_ROTATION,
                       "localRotation": [0, 0, 0, 1]},
        "decode": {
            "position": {"A": r6(pos_a), "B": r6(pos_b), "formula": f"metres = {r6(pos_a)} + {r6(pos_b)} * reading"},
            "heading": {"A": r6(yaw_a), "B": r6(yaw_b),
                        "formula": f"degrees = atan2({r6(yaw_a)} + {r6(yaw_b)} * readingX, {r6(yaw_a)} + {r6(yaw_b)} * readingZ)"},
            "notSensing": "a reading of exactly 0",
            "linearFrom": r6(pos_a), "linearTo": r6((S / 2 - r) / g),
            "metresPerContactMetre": r6(1 / g),
        },
    }


def document(c):
    r = rig(c)
    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by world-pose/generate.py; edit its CONFIG and rerun, never hand-edit this file.")
    o("# No layers: the receivers write these floats directly. The controller only declares them, beside the")
    o("# params asset, so the build carries each as an animator parameter as well as an expression parameter.")
    o(f"# Published, bare (globalParams): {', '.join(r['globalParams'])}. All momentary sensing outputs, none synced.")
    o(f"# Decode: position {r['decode']['position']['formula']}; heading {r['decode']['heading']['formula']}.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root")
    o("role: fx")
    o("")
    o("parameters:")
    for p in r["parameters"]:
        o(f"  {p}: {{ type: float, vrc: {{ synced: false, saved: false, osc: true }} }}   # face-proximity box, sensing")
    o("")
    o("layers: []")
    return "\n".join(L) + "\n", r


# ---- --check: the prefab surface no compile or gate reads ----
def parse_prefab(path):
    body = open(path, encoding="utf-8").read()
    docs = {}
    for d in body.split("--- !u!")[1:]:
        m = re.match(r"(\d+) &(-?\d+)", d)
        if m:
            docs[m.group(2)] = (int(m.group(1)), d)
    return body, docs


def fid(d, key):
    m = re.search(rf"^  {key}: \{{fileID: (-?\d+)", d, re.M)
    return m.group(1) if m else None


def vec(d, key):
    m = re.search(rf"^  {key}: \{{x: (\S+), y: (\S+), z: (\S+)(?:, w: (\S+))?\}}", d, re.M)
    return tuple(float(v) for v in m.groups() if v is not None) if m else None


def field(d, key):
    m = re.search(rf"^  {key}: (.*)$", d, re.M)
    return m.group(1).strip() if m else None


class Prefab:
    def __init__(self, path):
        self.body, self.docs = parse_prefab(path)
        self.tr, self.name, self.comps = {}, {}, {}
        for i, (cls, d) in self.docs.items():
            if cls == 1:
                self.name[i] = field(d, "m_Name")
            elif cls == 4:
                self.tr[i] = (fid(d, "m_GameObject"), fid(d, "m_Father"))
            elif cls == 114:
                self.comps.setdefault(fid(d, "m_GameObject"), []).append(d)
        fcs = [fid(d, "m_GameObject") for cls, d in self.docs.values() if cls == 114 and re.search(r"^\s+globalParams:", d, re.M)]
        if len(fcs) != 1:
            refuse(f"{path}: expected exactly one FullController (a component with globalParams), found {len(fcs)}")
        self.mount = next((i for i, (go, _) in self.tr.items() if go == fcs[0]), None)
        if self.mount is None:
            refuse(f"{path}: the FullController's GameObject has no Transform in this file")

    def path_of_tr(self, i):
        parts = []
        while i and i != "0" and i in self.tr:
            if i == self.mount:
                return "/".join(reversed(parts))
            go, fa = self.tr[i]
            parts.append(self.name.get(go))
            i = fa
        return None

    def entry(self, path):
        for i, (go, _) in self.tr.items():
            if self.path_of_tr(i) == path:
                return i, go
        return None

    def transform(self, path):
        e = self.entry(path)
        return self.docs[e[0]][1] if e else None

    def components(self, path, has):
        e = self.entry(path)
        return [d for d in (self.comps.get(e[1], []) if e else []) if re.search(has, d, re.M)]

    def sources(self, d):
        """(transform path or asset guid, weight, position offset, rotation offset) per source, up to totalLength."""
        n = int(re.search(r"^    totalLength: (\d+)", d, re.M).group(1))
        out = []
        for k in range(n):
            blk = d.split(f"    source{k}:")[1] if f"    source{k}:" in d else ""
            m = re.search(r"SourceTransform: \{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}))?", blk)
            w = re.search(r"Weight: (\S+)", blk)
            po = re.search(r"ParentPositionOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            ro = re.search(r"ParentRotationOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            tgt = (m.group(2) or self.path_of_tr(m.group(1))) if m else None
            out.append((tgt, float(w.group(1)) if w else None, tuple(float(x) for x in po.groups()) if po else None,
                        tuple(float(x) for x in ro.groups()) if ro else None))
        return out


def tags_of(d):
    m = re.search(r"^  collisionTags:\n((?:  - .*\n)*)", d, re.M)
    return [ln[4:].strip() for ln in m.group(1).splitlines()] if m else None


def same_rotation(got, want):
    return got is not None and abs(sum(a * b for a, b in zip(got, want))) > 1 - 1e-5


def close(a, b, eps=1e-4):
    return a is not None and b is not None and len(a) == len(b) and all(abs(x - y) <= eps for x, y in zip(a, b))


def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


ZERO3 = (0.0, 0.0, 0.0)


def check(c, prefab_path):
    """WorldPose.prefab against rig.json's numbers. Reads the YAML textually; a field it cannot find is a FAIL."""
    r = rig(c)
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    if not os.path.exists(prefab_path):
        print("  FAIL " + prefab_path + " is missing")
        return False
    P = Prefab(prefab_path)
    gp = re.search(r"globalParams:\n((?:\s+- .*\n)*)", P.body)
    got = [ln.strip()[2:] for ln in gp.group(1).splitlines()] if gp else None
    A(got == r["globalParams"], f"globalParams == {r['globalParams']} (got {got}): an OSC reader sees these names bare")
    refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 2\}", P.body)
    want = [meta_guid(os.path.join(HERE, "built", c["controller"] + x)) for x in (".controller", "_Parameters.asset")]
    A(refs == want, f"FullController objRefs == built/{c['controller']} controller then params (got {refs})")

    def zero_offsets(d, label):
        bad = [k for k in ("PositionOffset", "RotationOffset") if vec(d, k) is not None and not close(vec(d, k), ZERO3)]
        bad += [f"source {s[0]} offset" for s in P.sources(d) if not (close(s[2] or ZERO3, ZERO3) and close(s[3] or ZERO3, ZERO3))]
        A(not bad, f"{label}: every offset zero" + (f" (got {bad})" if bad else ""))

    # The world pin: both constraints on World, sourcing THIS entry's World.prefab at zero offset, enabled.
    wg = meta_guid(os.path.join(HERE, "assets", "World.prefab"))
    for kind in ("parent", "scale"):
        cs = [d for d in P.components("World", r"^  Sources:") if bool(re.search(r"^  ScaleAtRest:", d, re.M)) == (kind == "scale")]
        if A(len(cs) == 1, f"World carries one {kind} constraint"):
            d = cs[0]
            src = P.sources(d)
            A(len(src) == 1 and src[0][0] == wg and abs(src[0][1] - 1) < 1e-6, f"World {kind} pin sources assets/World.prefab at weight 1")
            zero_offsets(d, f"World {kind} pin")
            A(field(d, "m_Enabled") == "1" and field(d, "IsActive") == "1" and field(d, "Locked") == "1",
              f"World {kind} pin enabled, active, locked")
    # The head proxy.
    ha = r["headAnchor"]
    d = P.transform(ha["path"])
    if A(d is not None, f"{ha['path']} exists at the mount's top level"):
        A(same_rotation(vec(d, "m_LocalRotation"), ha["localRotation"]), f"{ha['path']}: local rotation identity (the head reads 0 at rest)")
    bp = P.components(ha["path"], r"^  boneReference:")
    if A(len(bp) == 1, f"{ha['path']} carries one MA BoneProxy"):
        A(field(bp[0], "boneReference") == str(ha["boneReference"]), f"BoneProxy boneReference == Head ({ha['boneReference']})")
        A(field(bp[0], "attachmentMode") == str(ha["attachmentMode"]), f"BoneProxy attachmentMode == AsChildKeepRotation ({ha['attachmentMode']})")
        A(not field(bp[0], "subPath"), "BoneProxy subPath empty")
    # The three groups: receivers, parks, senders, constraints.
    for gpath, gspec in r["groups"].items():
        d = P.transform(gpath)
        if A(d is not None, f"{gpath} exists"):
            A(close(vec(d, "m_LocalPosition"), gspec["localPosition"]), f"{gpath}: local position {gspec['localPosition']}")
            A(same_rotation(vec(d, "m_LocalRotation"), (0, 0, 0, 1)), f"{gpath}: unrotated")
        recvs = P.components(gpath, r"^  receiverType:")
        A(len(recvs) == len(gspec["receivers"]), f"{gpath} carries {len(gspec['receivers'])} receivers (got {len(recvs)})")
        for w in gspec["receivers"]:
            rd = next((x for x in recvs if field(x, "parameter") == w["parameter"]), None)
            if not A(rd is not None, f"a {gpath} receiver writes {w['parameter']}"):
                continue
            A(tags_of(rd) == [w["tag"]], f"{w['parameter']}: tags == [{w['tag']}] (got {tags_of(rd)})")
            A(close(vec(rd, "size"), (w["size"],) * 3), f"{w['parameter']}: box edge {w['size']}")
            A(same_rotation(vec(rd, "rotation"), euler(w["rotation"])), f"{w['parameter']}: +Z face on world {w['axis']}")
            A(close(vec(rd, "position"), ZERO3), f"{w['parameter']}: shape offset zero")
            for fld, v in (("shapeType", "2"), ("localOnly", "1"), ("allowSelf", "1"), ("allowOthers", "0"),
                           ("useFaceProximity", "1"), ("receiverType", "2"), ("contentTypes", "1")):
                A(field(rd, fld) == v, f"{w['parameter']}: {fld} == {v} (got {field(rd, fld)})")
        s = gspec["sender"]
        sd = P.transform(s["path"])
        if A(sd is not None, f"{s['path']} exists"):
            A(close(vec(sd, "m_LocalPosition"), s["localPosition"]), f"{s['path']}: local position {s['localPosition']}")
        snd = P.components(s["path"], r"^  collisionTags:")
        if A(len(snd) == 1, f"{s['path']} carries one contact sender"):
            x = snd[0]
            A(tags_of(x) == [gspec["tag"]], f"{s['path']}: tags == [{gspec['tag']}] (got {tags_of(x)})")
            A(field(x, "shapeType") == "0" and abs(float(field(x, "radius") or -1) - r["senderRadius"]) < 1e-6,
              f"{s['path']}: sphere of radius {r['senderRadius']}")
            A(field(x, "localOnly") == "1", f"{s['path']}: localOnly == 1")
            A(close(vec(x, "position"), ZERO3), f"{s['path']}: shape offset zero")
        if "position" in s:
            cs = P.components(s["path"], r"^  Sources:")
            if A(len(cs) == 1, f"{s['path']} carries one constraint"):
                src = P.sources(cs[0])
                sp, sw = s["position"]["sources"], s["position"]["weights"]
                A([x[0] for x in src] == sp and all(abs(a[1] - b) < 1e-6 for a, b in zip(src, sw)),
                  f"{s['path']} sources {sp} (the mount, the pinned World) at weights {sw}: the gain g"
                  + f" (got {[(x[0], x[1]) for x in src]})")
                zero_offsets(cs[0], s["path"])
        if "holder" in gspec:
            h = gspec["holder"]
            hd = P.transform(h["path"])
            if A(hd is not None, f"{h['path']} exists"):
                A(close(vec(hd, "m_LocalPosition"), ZERO3), f"{h['path']}: at its group's origin")
            cs = P.components(h["path"], r"^  Sources:")
            if A(len(cs) == 1, f"{h['path']} carries one constraint"):
                x = cs[0]
                src = P.sources(x)
                A([s0[0] for s0 in src] == [h["rotationY"]] and abs(src[0][1] - 1) < 1e-6,
                  f"{h['path']} rotation source [{h['rotationY'] or '(the mount)'}] at weight 1 (got {[s0[0] for s0 in src]})")
                A((field(x, "AffectsRotationX"), field(x, "AffectsRotationY"), field(x, "AffectsRotationZ")) == ("0", "1", "0"),
                  f"{h['path']}: Y axis only")
                A(close(vec(x, "RotationAtRest"), ZERO3), f"{h['path']}: rotation at rest zero")
                zero_offsets(x, h["path"])
    print("OK" if ok else "FAILED")
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check(CONFIG, os.path.join(HERE, "WorldPose.prefab")) else 1)
    text, r = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with open(os.path.join(HERE, "rig.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, indent=2)
        fh.write("\n")
    print(f"wrote controller.yaml ({CONFIG['controller']}) and rig.json: g {r['gain']}, "
          f"{r['decode']['position']['formula']}, {r['decode']['heading']['formula']}")


if __name__ == "__main__":
    main()
