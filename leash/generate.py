#!/usr/bin/env python3
"""leash generator: emits controller.yaml and rig.json from CONFIG below.

    python leash/generate.py            # writes controller.yaml and rig.json beside this file
    python leash/generate.py --check    # asserts Leash.prefab's hand-maintained surface against CONFIG

Edit CONFIG, rerun, then recompile built/ as a unit in a mounting Editor (CONVENTIONS.md §The gate).
Both outputs are pure functions of CONFIG. controller.yaml is the FX layer; rig.json is every number
the prefab is built to (node poses, constraint sources and weights, the proxy physbone, the rope's
Bezier weights, the sensing geometry). Nothing here writes Unity assets: the prefab is built from
rig.json in the Editor (README §Changing it), and `--check` holds it to CONFIG afterwards.

WHAT THE RIG IS
---------------
A leash whose far end is sensed for the OSC bridge (`vrc-bridge` mapping `osc_leash`). The consumer's
visible bones (a tail, or the demo's generated tube) are never simulated themselves: each carries a
two-source parent constraint, source 0 a proxy bone and source 1 a rope joint, weights animated.

  Holder    parent of the proxy chain; two sources, HipsAnchor (free, held) and StakeRoot (planted).
  Chain     the proxy: a copy of the consumer's chain (same local poses) under Holder, carrying the
            one grabbable, posable physbone `<prefix>/Chain`. Its tip is what the sensing reads.
  Stake     position-constrained to the proxy tip; FreezeToWorld captures it at a plant.
  StakeAim  aims at HipsAnchor; frozen with the stake, so it holds the leash line captured at the plant.
  StakeRoot a child of StakeAim placed so that Holder sitting there rests the proxy with its TIP ON THE
            STAKE and its body lying back along the captured line: a hand at the stake finds the tip,
            and a posed release from that grab re-plants where the hand let go.
  Rope      a cubic Bezier from HipsAnchor to Stake: two one-bone pendulum physbones supply the control
            points, each joint a four-source position constraint (Bernstein weights) smoothed by a
            spring-damping pair under a world-pinned frame, and aimed at the next joint.

THE MACHINE (one layer)
-----------------------
  Load      the default; writes Held and Planted 0 and leaves on the next evaluation, so neither clear
            rests on the first state after a load (docs/runtime.md §Parameters).
  Disabled  enable off: holder on the hips, visible on the proxy, nothing frozen, sensing stowed. The
            proxy physbone stays live, because for a tail consumer it IS the tail's physics.
  Free      holder on the hips, visible on the proxy.
  Held      the same clip; Held 1. Left on the release: a posed one plants, a plain one goes Free.
            _IsPosed is read as a level when _IsGrabbed falls, never as an edge.
  Plant     freeze the stake and its aim at entry; fade holder hips->StakeRoot and visible proxy->rope
            over CONFIG `plantFade` frames; one settled frame; then the proxy GameObject off for
            `cycleFrames` frames and on (resetWhenDisabled on), so the chain rests at StakeRoot with
            _IsPosed cleared. The cycle runs after the fade has landed, so it does not show. A grab
            during the fade exits to PHeld (the grab exit); a grab during the cycle frames misses.
  Planted   holder on StakeRoot, visible on the rope, frozen. Planted 1.
  PHeld     a pick-up: fade holder StakeRoot->hips and visible rope->proxy over `pickupFade` frames
            (longer than the plant's: the grabbed tip trails the moving root by about two frames of
            its travel), and unfreeze at the end. Held 1. Left like Held.
Every state keys every binding the layer owns (work under either Write Defaults mode).
Held is 1 in Held and PHeld; Planted is 1 in Plant and Planted; both 0 elsewhere.

CONFIG
------
  prefix        the published OSC prefix; the bridge's `LeashSettings.prefix` must match.
  tag           the private collision tag the sender and the four sensing boxes share.
  boxSize       the sensing boxes' edge, metres (the SDK editor caps a contact shape at 6).
  senderRadius  the sensing sender's sphere radius; the bridge's `sender_radius`.
  ratio         range multiplier: SenseProxy sits 1/ratio of the way from the collar carrier to the
                proxy tip, so the boxes read 1/ratio of the offset. The bridge's `ratio`.
  chain         the consumer's chain, root first: each bone's `visible` binding path (relative to the
                prefab root, or '/'-rooted from the avatar root), its local position and rotation
                (Unity Euler degrees) under its parent. Bone 0's parent is HipsAnchor.
  leafVisible   whether the last bone carries a visible constraint (the demo's tube is skinned to it;
                an unweighted `_end` leaf is left to ride its parent).
  physbone      the proxy physbone's fields. The leash-owned ones are fixed below (FIXED_PHYSBONE).
  plantFade, pickupFade, cycleFrames   frame counts at 60 fps.
  rope          pendulum and spring-damping settings for the rope.
  enableDefault the enable's default (synced, saved).
"""

import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME = 1 / 60

CONFIG = {
    "prefix": "Leash",
    "controller": "Leash_Fx",
    "tag": "LeashSense",
    "boxSize": 6.0,
    "senderRadius": 0.05,
    "ratio": 10,
    "chain": [
        {"visible": "HipsAnchor/V0", "pos": (0, 0, -0.08), "rot": (30, 180, 0)},
        {"visible": "HipsAnchor/V0/V1", "pos": (0, 0, 0.15)},
        {"visible": "HipsAnchor/V0/V1/V2", "pos": (0, 0, 0.15)},
        {"visible": "HipsAnchor/V0/V1/V2/V3", "pos": (0, 0, 0.15)},
        {"visible": "HipsAnchor/V0/V1/V2/V3/V4", "pos": (0, 0, 0.15)},
        {"visible": "HipsAnchor/V0/V1/V2/V3/V4/V5", "pos": (0, 0, 0.15)},
        {"visible": "HipsAnchor/V0/V1/V2/V3/V4/V5/V6", "pos": (0, 0, 0.15)},
    ],
    "leafVisible": True,
    # The demo consumer's own settings (a vendor tail's, gravity 0); immobile is the feel trade a consumer sets.
    "physbone": {"integrationType": "Advanced", "pull": 0.082, "spring": 0.718, "stiffness": 0.115,
                 "gravity": 0.0, "immobileType": "World", "immobile": 0.0, "radius": 0.03},
    "plantFade": 10,
    "pickupFade": 15,
    "cycleFrames": 3,
    "rope": {"pendulumLength": 0.3, "pull": 0.2, "spring": 0.3, "stiffness": 0.1, "gravity": 0.5,
             "radius": 0.02, "springWeights": {"M": [-1, 1.1, 4], "J": [0.05, 1]}},
    "enableDefault": True,
}

# What makes the proxy a leash, whatever the consumer's own settings are.
FIXED_PHYSBONE = {"maxStretch": 20, "grabMovement": 1, "allowGrabbing": "True", "allowPosing": "True",
                  "allowCollision": "False", "resetWhenDisabled": True, "isAnimated": False}
# Box shape rotations putting each face-proximity box's +Z face on the carrier's named axis.
AXES = (("Right", (0, 90, 0)), ("Up", (270, 0, 0)), ("Forward", (0, 0, 0)))


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


# ---- quaternion helpers (x, y, z, w), Unity conventions ----
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


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def rot(q, v):
    p = qmul(qmul(q, (v[0], v[1], v[2], 0.0)), qinv(q))
    return p[:3]


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a))
    return tuple(x / n for x in a)


def from_basis(r, u, f):
    """The quaternion whose columns are (r, u, f): it maps X->r, Y->u, Z->f."""
    m = ((r[0], u[0], f[0]), (r[1], u[1], f[1]), (r[2], u[2], f[2]))
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1) * 2
        return ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2
        return (s / 4, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2
        return ((m[0][1] + m[1][0]) / s, s / 4, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2
    return ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, s / 4, (m[1][0] - m[0][1]) / s)


def look(f, up=(0, 1, 0)):
    """Quaternion.LookRotation(f, up)."""
    f = norm(f)
    if abs(dot(f, norm(up))) > 0.999:
        up = (0, 0, 1)
    r = norm(cross(up, f))
    return from_basis(r, cross(f, r), f)


def fromto(a, b):
    """The minimal rotation taking direction a onto direction b (Quaternion.FromToRotation)."""
    a, b = norm(a), norm(b)
    c = dot(a, b)
    if c < -0.999999:
        ax = cross((1, 0, 0), a) if abs(a[0]) < 0.9 else cross((0, 1, 0), a)
        return qaxis(norm(ax), 180)
    x, y, z = cross(a, b)
    return tuple(v / math.sqrt(2 * (1 + c)) for v in (x, y, z, 1 + c))


def to_euler(q):
    """Unity eulerAngles (degrees) of q, for the prefab's Euler hint; the check compares quaternions."""
    x, y, z, w = q
    sx = 2 * (w * x - y * z)
    ex = math.degrees(math.asin(max(-1, min(1, sx))))
    ey = math.degrees(math.atan2(2 * (w * y + x * z), 1 - 2 * (x * x + y * y)))
    ez = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (x * x + z * z)))
    return tuple(round(v % 360, 4) for v in (ex, ey, ez))


def r6(v):
    return tuple(round(x, 6) for x in v)


# ---- the geometry ----
def validate(c):
    n = len(c["chain"])
    if n < 3:
        refuse("chain needs at least three transforms (two segments): the rope's Bezier and the plant need a line.")
    if not 0 < c["senderRadius"] < c["boxSize"] / 2:
        refuse("senderRadius must be positive and smaller than half the box.")
    if c["boxSize"] > 6:
        refuse("boxSize above 6: the SDK editor caps a contact shape at 6 units.")
    if not (isinstance(c["ratio"], (int, float)) and c["ratio"] >= 1):
        refuse("ratio must be 1 or more (1 senses the tip itself).")
    for k in ("plantFade", "pickupFade", "cycleFrames"):
        if not (isinstance(c[k], int) and c[k] >= 1):
            refuse(f"{k} is a whole number of frames, at least 1.")
    if c["plantFade"] < 6:
        refuse("plantFade under 6 frames: a root moved under a live grab trails the hand by one frame of its travel, "
               "so a faster fade throws the proxy.")
    if c["pickupFade"] < c["plantFade"]:
        refuse("pickupFade shorter than plantFade: the pick-up moves the root under a live grab, whose tip trails the root "
               "by about two frames of its travel, so it needs the longer fade.")
    if c["cycleFrames"] < 3:
        refuse("cycleFrames under 3: the proxy must stay off across at least one physbone step at any frame rate.")
    im = c["physbone"].get("immobileType")
    if im not in ("World", "AllMotion"):
        refuse("physbone.immobileType is World or AllMotion.")
    paths = [b["visible"] for b in c["chain"]]
    if len(set(paths)) != n:
        refuse("chain visible paths repeat.")


def geometry(c):
    """Poses in the Holder frame (= the chain's parent frame at rest): per bone position and rotation."""
    pos, rq = [], []
    p, q = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    for b in c["chain"]:
        p = add(p, rot(q, b["pos"]))
        q = qmul(q, euler(b.get("rot", (0, 0, 0))))
        pos.append(p)
        rq.append(q)
    tip, root = pos[-1], pos[0]
    chord = sub(tip, root)
    L = math.sqrt(dot(chord, chord))
    # StakeRoot's rotation under StakeAim maps the chord onto -Z (StakeAim's +Z points at the hips) and the
    # holder's up as near to +Y as the chord allows; its position then puts the rested tip on the stake.
    f = norm(chord)
    up = (0, 1, 0) if abs(f[1]) < 0.999 else (0, 0, 1)
    upo = norm(sub(up, tuple(x * dot(up, f) for x in f)))
    src = from_basis(cross(upo, f), upo, f)
    dst = from_basis(cross((0, 1, 0), (0, 0, -1)), (0, 1, 0), (0, 0, -1))
    rsr = qmul(dst, qinv(src))
    psr = tuple(-x for x in rot(rsr, tip))
    # Each visible bone's rotation offset against its rope joint, whose frame is +Z along the rope, +Y up. The
    # reference frame is bone 0's segment framed +Y up, carried bone to bone by the minimal rotation between
    # segments, so a rope lying straight keeps each bone's rest twist against its parent. A frame taken +Y up per
    # bone instead would roll wherever a segment hangs near vertical, twisting a hanging tail between bones.
    offs, F, dprev = [], None, None
    for i in range(len(pos)):
        d = sub(pos[i + 1], pos[i]) if i + 1 < len(pos) else sub(pos[i], pos[i - 1])
        F = look(d) if F is None else qmul(fromto(dprev, d), F)
        dprev = d
        offs.append(qmul(qinv(F), rq[i]))
    return {"pos": pos, "rot": rq, "L": L, "stakeRoot": (psr, rsr), "offsets": offs,
            "bone": [math.sqrt(dot(b["pos"], b["pos"])) for b in c["chain"][1:]]}


def proxy_names(c):
    return ["Chain"] + [f"P{i}" for i in range(1, len(c["chain"]))]


def proxy_paths(c):
    out, cur = [], "Holder"
    for nm in proxy_names(c):
        cur = f"{cur}/{nm}"
        out.append(cur)
    return out


def visible_bones(c):
    return c["chain"] if c["leafVisible"] else c["chain"][:-1]


def global_params(c):
    p = c["prefix"]
    return [f"{p}/Right", f"{p}/Up", f"{p}/Forward", f"{p}/Present", f"{p}/Held", f"{p}/Planted", f"{p}/Chain*"]


def rig(c):
    validate(c)
    g = geometry(c)
    n = len(c["chain"]) - 1   # segments
    names, paths = proxy_names(c), proxy_paths(c)
    joints = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        joints.append({"name": f"J{i}", "t": round(t, 6),
                       "bernstein": [round(u ** 3, 6), round(3 * u * u * t, 6), round(3 * u * t * t, 6), round(t ** 3, 6)]})
    vis = []
    for i, b in enumerate(visible_bones(c)):
        vis.append({"path": b["visible"], "proxy": paths[i], "joint": f"Rope/Frame/J{i}",
                    "ropeRotationOffset": r6(to_euler(g["offsets"][i])), "ropeRotationOffsetQ": r6(g["offsets"][i])})
    pb = dict(c["physbone"])
    pb.update(FIXED_PHYSBONE)
    pb["parameter"] = f"{c['prefix']}/Chain"
    p = c["prefix"]
    return {
        "_comment": "GENERATED by leash/generate.py from its CONFIG; never hand-edit. The numbers Leash.prefab is built to.",
        "prefix": p,
        "globalParams": global_params(c),
        "sensing": {"tag": c["tag"], "boxSize": c["boxSize"], "senderRadius": c["senderRadius"],
                    "proxyWeights": [round(1 - 1 / c["ratio"], 6), round(1 / c["ratio"], 6)],
                    "decode": f"{c['ratio']} * ({c['boxSize']} * reading - ({c['boxSize'] / 2} + {c['senderRadius']}))",
                    "boxes": [{"parameter": f"{p}/{a}", "rotation": list(e), "type": "Proximity", "faceProximity": True} for a, e in AXES]
                    + [{"parameter": f"{p}/Present", "rotation": [0, 0, 0], "type": "Constant", "faceProximity": False}]},
        "chain": [{"name": nm, "path": pa, "localPosition": r6(b["pos"]), "localRotation": r6(euler(b.get("rot", (0, 0, 0))))}
                  for nm, pa, b in zip(names, paths, c["chain"])],
        "tip": paths[-1],
        "chainLength": round(sum(g["bone"]), 6),
        "L": round(g["L"], 6),
        "stakeRoot": {"localPosition": r6(g["stakeRoot"][0]), "localRotation": r6(g["stakeRoot"][1]),
                      "localEuler": to_euler(g["stakeRoot"][1])},
        "physbone": pb,
        "visible": vis,
        "rope": dict(c["rope"], segments=n, joints=joints),
        "fades": {"plant": c["plantFade"], "pickup": c["pickupFade"], "cycle": c["cycleFrames"]},
    }


# ---- the controller ----
def t(n):
    return round(n * FRAME, 6)


def document(c):
    r = rig(c)
    p = c["prefix"]
    EN, HELD, PL, IG, IP = f"{p}/Enable", f"{p}/Held", f"{p}/Planted", f"{p}/Chain_IsGrabbed", f"{p}/Chain_IsPosed"
    HOLD = "Holder/VRCParentConstraint.Sources.source"
    FRZ, AFRZ = "Stake/VRCPositionConstraint.FreezeToWorld", "Stake/StakeAim/VRCAimConstraint.FreezeToWorld"
    PB = "Holder/Chain/GameObject.m_IsActive"
    SENSE = "Sense/GameObject.m_IsActive"
    VIS = [f"{v['path']}/VRCParentConstraint.Sources.source" for v in r["visible"]]

    def const(hips, proxy, frz, sense):
        s = {HOLD + "0.Weight": hips, HOLD + "1.Weight": 1 - hips, FRZ: frz, AFRZ: frz, PB: 1, SENSE: sense}
        for v in VIS:
            s[v + "0.Weight"] = proxy
            s[v + "1.Weight"] = 1 - proxy
        return s

    def lin(keys):
        return "{ tangents: linear, keys: [ " + ", ".join(f"[{a}, {b}]" for a, b in keys) + " ] }"

    def stp(keys):
        return "{ tangents: stepped, keys: [ " + ", ".join(f"[{a}, {b}]" for a, b in keys) + " ] }"

    F, G, C = c["plantFade"], c["pickupFade"], c["cycleFrames"]
    land = 1 + F
    off0 = land + 1.5          # one settled frame after both fades land, then the proxy off
    on = off0 + C
    PLEN = on + 1.5
    plant = {FRZ: stp([(0, 1), (t(PLEN), 1)]), AFRZ: stp([(0, 1), (t(PLEN), 1)]),
             HOLD + "0.Weight": lin([(0, 1), (t(1), 1), (t(land), 0), (t(PLEN), 0)]),
             HOLD + "1.Weight": lin([(0, 0), (t(1), 0), (t(land), 1), (t(PLEN), 1)]),
             PB: stp([(0, 1), (t(off0), 0), (t(on), 1), (t(PLEN), 1)]),
             SENSE: stp([(0, 1), (t(PLEN), 1)])}
    pheld = {FRZ: stp([(0, 1), (t(G - 0.5), 0), (t(G), 0)]), AFRZ: stp([(0, 1), (t(G - 0.5), 0), (t(G), 0)]),
             HOLD + "0.Weight": lin([(0, 0), (t(G), 1)]), HOLD + "1.Weight": lin([(0, 1), (t(G), 0)]),
             PB: stp([(0, 1), (t(G), 1)]), SENSE: stp([(0, 1), (t(G), 1)])}
    for v in VIS:
        plant[v + "0.Weight"] = lin([(0, 1), (t(1), 1), (t(land), 0), (t(PLEN), 0)])
        plant[v + "1.Weight"] = lin([(0, 0), (t(1), 0), (t(land), 1), (t(PLEN), 1)])
        pheld[v + "0.Weight"] = lin([(0, 0), (t(G), 1)])
        pheld[v + "1.Weight"] = lin([(0, 1), (t(G), 0)])

    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by leash/generate.py; edit its CONFIG and rerun, never hand-edit this file.")
    o("# The leash's one FX layer. generate.py's docstring is the state-by-state record; rig.json is the prefab's numbers.")
    o(f"# Published, bare (globalParams): {', '.join(r['globalParams'])}. {HELD} is 1 in Held and PHeld,")
    o(f"# {PL} is 1 in Plant and Planted, both latching. {EN} is the one intent (synced, saved) and takes the instance prefix.")
    o(f"# Fades: plant {F} frames, pick-up {G} frames, proxy cycle {C} frames. L (rest chord of the chain) {r['L']} m.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")
    o("parameters:")
    o(f"  {EN}: {{ type: bool, default: {'true' if c['enableDefault'] else 'false'}, vrc: {{ synced: true, saved: true }} }}")
    for a, _ in AXES:
        o(f"  {p}/{a}: {{ type: float, vrc: {{ synced: false, saved: false, osc: true }} }}   # face-proximity box, sensing")
    o(f"  {p}/Present: {{ type: bool, vrc: {{ synced: false, saved: false, osc: true }} }}   # Constant box, sensing")
    o(f"  {HELD}: {{ type: bool, vrc: {{ synced: false, saved: false, osc: true }} }}   # latching, driven here")
    o(f"  {PL}: {{ type: bool, vrc: {{ synced: false, saved: false, osc: true }} }}   # latching, driven here")
    o(f"  {IG}: {{ type: bool, vrc: {{ synced: false, saved: false }} }}   # the proxy physbone")
    o(f"  {IP}: {{ type: bool, vrc: {{ synced: false, saved: false }} }}   # the proxy physbone")
    o("")
    en_on, en_off = f"{EN} is true", f"{EN} is false"
    posed = f"{IG} is false, {IP} is true"
    plain = f"{IG} is false, {IP} is false"

    def state(name, clip, held, planted, trans):
        o(f"      {name}:")
        o(f"        motion: {{ clip: {clip} }}")
        o(f"        behaviours: [ {{ driver: {{ set: {{ {HELD}: {held}, {PL}: {planted} }} }} }} ]")
        o("        transitions:")
        for tr in trans:
            o(f"          - {tr}")

    o("layers:")
    o(f"  - name: {p}")
    o("    states:")
    o("      # The default: its clear is repeated by whichever state it hands to, one evaluation later.")
    state("Load", "disabled", 0, 0, [f"{{ to: Free, when: [ {en_on} ] }}", f"{{ to: Disabled, when: [ {en_off} ] }}"])
    state("Disabled", "disabled", 0, 0, [f"{{ to: Free, when: [ {en_on} ] }}"])
    state("Free", "free", 0, 0, [f"{{ to: Disabled, when: [ {en_off} ] }}", f"{{ to: Held, when: [ {IG} is true ] }}"])
    o("      # _IsPosed is a level read when _IsGrabbed falls: posed plants, plain goes home.")
    state("Held", "free", 1, 0, [f"{{ to: Disabled, when: [ {en_off} ] }}", f"{{ to: Plant, when: [ {posed} ] }}",
                                 f"{{ to: Free, when: [ {plain} ] }}"])
    o("      # Freeze at entry, fades, one settled frame, then the proxy cycle; the grab exit is listed before the hop.")
    state("Plant", "plant", 0, 1, [f"{{ to: PHeld, when: [ {IG} is true ] }}", "{ to: Planted, when: [], exitTime: 1.0 }"])
    state("Planted", "planted", 0, 1, [f"{{ to: Disabled, when: [ {en_off} ] }}", f"{{ to: PHeld, when: [ {IG} is true ] }}"])
    state("PHeld", "pheld", 1, 0, [f"{{ to: Disabled, when: [ {en_off} ] }}", f"{{ to: Plant, when: [ {posed} ] }}",
                                   f"{{ to: Free, when: [ {plain} ] }}"])
    o("    default: Load")
    o("    layout:")
    o("      nodes: { Load: [30, 180], Disabled: [-210, 260], Free: [30, 260], Held: [30, 340], Plant: [30, 420], "
      "Planted: [30, 500], PHeld: [270, 420] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o("clips:")

    def setclip(name, s):
        o(f"  {name}:")
        o("    set:")
        for k, v in s.items():
            o(f'      "{k}": {v}')

    def curveclip(name, length, cv):
        o(f"  {name}:")
        o(f"    length: {length}")
        o("    curves:")
        for k, v in cv.items():
            o(f'      "{k}": {v}')

    setclip("disabled", const(1, 1, 0, 0))
    setclip("free", const(1, 1, 0, 1))
    setclip("planted", const(0, 0, 1, 1))
    curveclip("plant", t(PLEN), plant)
    curveclip("pheld", t(G), pheld)
    o("")
    o("menu:")
    o(f"  - toggle: {p}")
    o(f"    param: {EN}")
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


class Prefab:
    def __init__(self, path):
        self.body, self.docs = parse_prefab(path)
        self.tr = {}          # transform id -> (go id, father id)
        self.name = {}        # go id -> name
        self.comps = {}       # go id -> [component doc]
        for i, (cls, d) in self.docs.items():
            if cls == 1:
                m = re.search(r"^  m_Name: (.*)$", d, re.M)
                self.name[i] = m.group(1).strip() if m else None
            elif cls == 4:
                self.tr[i] = (fid(d, "m_GameObject"), fid(d, "m_Father"))
            elif cls == 114:
                g = fid(d, "m_GameObject")
                self.comps.setdefault(g, []).append(d)
        # The mount: the FullController's GameObject. Paths are relative to it, which is the prefab root on the
        # entry and the rig's root on a consumer's avatar prefab (where the rig sits one level under the avatar).
        fc = next((fid(d, "m_GameObject") for cls, d in self.docs.values() if cls == 114 and re.search(r"^\s+globalParams:", d, re.M)), None)
        self.mount = next((i for i, (go, _) in self.tr.items() if fc is not None and go == fc), None)

    def path_of_tr(self, i):
        parts = []
        while i and i != "0" and i in self.tr:
            if i == self.mount:
                return "/".join(reversed(parts))
            go, fa = self.tr[i]
            parts.append(self.name.get(go))
            i = fa
        return "/".join(reversed(parts[:-1]))   # no mount on the walk: relative to the prefab root

    def by_path(self):
        return {self.path_of_tr(i): (i, go) for i, (go, _) in self.tr.items()}

    def transform(self, path):
        e = self.by_path().get(path)
        return self.docs[e[0]][1] if e else None

    def components(self, path, has):
        e = self.by_path().get(path)
        return [d for d in self.comps.get(e[1], [])] if e and has is None else \
            [d for d in (self.comps.get(e[1], []) if e else []) if re.search(has, d, re.M)]

    def source_paths(self, d):
        """The constraint's sources as (transform path or asset guid, weight, position offset, rotation offset
        as a quaternion), up to totalLength."""
        n = int(re.search(r"^    totalLength: (\d+)", d, re.M).group(1))
        out = []
        for k in range(n):
            blk = d.split(f"    source{k}:")[1] if f"    source{k}:" in d else ""
            m = re.search(r"SourceTransform: \{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}))?", blk)
            w = re.search(r"Weight: (\S+)", blk)
            po = re.search(r"ParentPositionOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            ro = re.search(r"ParentRotationOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            tgt = m.group(2) or self.path_of_tr(m.group(1)) if m else None
            out.append((tgt, float(w.group(1)) if w else None, tuple(float(x) for x in po.groups()) if po else None,
                        euler(tuple(float(x) for x in ro.groups())) if ro else None))
        return out


def tags_of(d):
    m = re.search(r"^  collisionTags:\n((?:  - .*\n)*)", d, re.M)
    return [ln[4:].strip() for ln in m.group(1).splitlines()] if m else None


def same_rotation(got, want):
    return got is not None and abs(sum(a * b for a, b in zip(got, want))) > 1 - 1e-5


def close(a, b, eps=1e-4):
    return a is not None and b is not None and all(abs(x - y) <= eps for x, y in zip(a, b))


ZERO3 = (0.0, 0.0, 0.0)
ZERO_Q = (0.0, 0.0, 0.0, 1.0)


def zero_offset(d):
    """A position or aim constraint's own PositionOffset / RotationOffset, named when nonzero."""
    return [f"{k} (got {vec(d, k)})" for k in ("PositionOffset", "RotationOffset")
            if vec(d, k) is not None and not close(vec(d, k), ZERO3)]


def source_faults(src, want):
    """Each (path, weight, position offset, rotation quaternion) in want against the parsed sources: the
    fields that differ, named, or [] when every source matches."""
    if [a for a, *_ in src] != [w[0] for w in want]:
        return [f"sources {[w[0] for w in want]} (got {[a for a, *_ in src]})"]
    out = []
    for (a, w, po, ro), (_, ww, wpo, wro) in zip(src, want):
        if w is None or abs(w - ww) > 1e-6:
            out.append(f"{a} weight {ww} (got {w})")
        if not close(po, wpo):
            out.append(f"{a} position offset {wpo} (got {po})")
        if not same_rotation(ro, wro):
            out.append(f"{a} rotation offset {wro} (got {ro})")
    return out


def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def check(c, prefab_path, entry=True):
    """Leash.prefab (or a consumer's prefab at the same CONFIG) against rig.json's numbers. Reads the YAML
    textually; a field it cannot find is a FAIL, never a pass."""
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
    s = r["sensing"]
    # The FullController seam: globalParams exactly the published surface, and its assets THIS entry's built/.
    gp = re.search(r"globalParams:\n((?:\s+- .*\n)*)", P.body)
    got = [ln.strip()[2:] for ln in gp.group(1).splitlines()] if gp else None
    A(got == r["globalParams"], f"globalParams == {r['globalParams']} (got {got}): the bridge reads these bare")
    if entry:
        refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 2\}", P.body)
        want = [meta_guid(os.path.join(HERE, "built", c["controller"] + x)) for x in (".controller", "_Menu.asset", "_Parameters.asset")]
        A(refs == want, f"FullController objRefs == built/{c['controller']} controller, menu, params (got {refs})")
    # Sensing: four boxes on Sense, one sender on SenseProxy, one private tag, the geometry the decode assumes.
    boxes = P.components("Sense", r"^  receiverType:")
    A(len(boxes) == 4, f"Sense carries 4 receivers (got {len(boxes)})")
    for want in s["boxes"]:
        d = next((b for b in boxes if re.search(rf"^  parameter: {re.escape(want['parameter'])}$", b, re.M)), None)
        if not A(d is not None, f"a Sense receiver writes {want['parameter']}"):
            continue
        tags = tags_of(d)
        A(tags == [s["tag"]], f"{want['parameter']}: tags == [{s['tag']}] (got {tags})")
        A(close(vec(d, "size"), (s["boxSize"],) * 3), f"{want['parameter']}: box size {s['boxSize']} on every axis")
        A(same_rotation(vec(d, "rotation"), euler(want["rotation"])), f"{want['parameter']}: box rotation puts its +Z face on its axis")
        for fld, v in (("shapeType", "2"), ("localOnly", "1"), ("allowSelf", "1"), ("allowOthers", "0"),
                       ("useFaceProximity", "1" if want["faceProximity"] else "0"),
                       ("receiverType", "2" if want["type"] == "Proximity" else "0")):
            m = re.search(rf"^  {fld}: (\S+)$", d, re.M)
            A(m is not None and m.group(1) == v, f"{want['parameter']}: {fld} == {v}")
        A(close(vec(d, "position"), (0, 0, 0)), f"{want['parameter']}: shape offset zero")
    snd = P.components("SenseProxy", r"^  collisionTags:")
    if A(len(snd) == 1, "SenseProxy carries one contact sender"):
        d = snd[0]
        tags = tags_of(d)
        A(tags == [s["tag"]], f"sender tags == [{s['tag']}] (got {tags})")
        m = re.search(r"^  radius: (\S+)$", d, re.M)
        A(m is not None and abs(float(m.group(1)) - s["senderRadius"]) < 1e-6, f"sender radius == {s['senderRadius']}")
        m = re.search(r"^  shapeType: (\S+)$", d, re.M)
        A(m is not None and m.group(1) == "0", "sender is a sphere")
        m = re.search(r"^  localOnly: (\S+)$", d, re.M)
        A(m is not None and m.group(1) == "1", "sender localOnly == 1")
        A(close(vec(d, "position"), (0, 0, 0)), "sender shape offset zero")
    pc = P.components("SenseProxy", r"^  Sources:")
    if A(len(pc) == 1, "SenseProxy carries one constraint"):
        want = [("Sense", s["proxyWeights"][0], ZERO3, ZERO_Q), (r["tip"], s["proxyWeights"][1], ZERO3, ZERO_Q)]
        bad = source_faults(P.source_paths(pc[0]), want) + zero_offset(pc[0])
        A(not bad, f"SenseProxy sources [Sense, tip] at {s['proxyWeights']}, zero offsets" + (f": {bad}" if bad else ""))
    # The proxy chain: its poses, and the physbone that makes it a leash.
    for b in r["chain"]:
        d = P.transform(b["path"])
        if A(d is not None, f"proxy {b['path']} exists"):
            A(close(vec(d, "m_LocalPosition"), b["localPosition"]), f"{b['path']}: local position {b['localPosition']}")
            A(same_rotation(vec(d, "m_LocalRotation"), b["localRotation"]), f"{b['path']}: local rotation")
    pbs = P.components(r["chain"][0]["path"], r"^  maxStretch:")
    if A(len(pbs) == 1, "the proxy root carries one physbone"):
        d = pbs[0]
        pb = r["physbone"]
        # Every field rig.json emits, as the serialized value: enums and booleans by their stored integer.
        enum = {"True": "1", "False": "0", True: "1", False: "0", "Simplified": "0", "Advanced": "1",
                "AllMotion": "0", "World": "1"}
        for fld, v in pb.items():
            m = re.search(rf"^  {fld}: (.*)$", d, re.M)
            got = m.group(1).strip() if m else None
            if fld == "parameter":
                good = got == v
            elif isinstance(v, bool) or isinstance(v, str):
                good = got == enum[v]
            else:
                good = got is not None and abs(float(got) - v) < 1e-6
            A(good, f"physbone {fld} == {v} (got {got})")
    # The plant geometry: StakeRoot rests the proxy tip on the stake.
    d = P.transform("Stake/StakeAim/StakeRoot")
    if A(d is not None, "Stake/StakeAim/StakeRoot exists"):
        A(close(vec(d, "m_LocalPosition"), r["stakeRoot"]["localPosition"]),
          f"StakeRoot local position {r['stakeRoot']['localPosition']} (L {r['L']} m back along the aim)")
        A(same_rotation(vec(d, "m_LocalRotation"), r["stakeRoot"]["localRotation"]), "StakeRoot faces the stake")
    # Rest weights are the Free clip's (the animator overwrites them in play); every offset is zero but a
    # visible bone's rope rotation offset.
    for path, want in (("Holder", [("HipsAnchor", 1, ZERO3, ZERO_Q), ("Stake/StakeAim/StakeRoot", 0, ZERO3, ZERO_Q)]),
                       ("Stake", [(r["tip"], 1, ZERO3, ZERO_Q)]), ("Stake/StakeAim", [("HipsAnchor", 1, ZERO3, ZERO_Q)])):
        cs = P.components(path, r"^  Sources:")
        if A(len(cs) == 1, f"{path} carries one constraint"):
            bad = source_faults(P.source_paths(cs[0]), want) + zero_offset(cs[0])
            A(not bad, f"{path} sources {[w[0] for w in want]} at weights {[w[1] for w in want]}, zero offsets"
              + (f": {bad}" if bad else ""))
    for v in r["visible"]:
        if v["path"].startswith("/"):
            continue   # a consumer's own bone lives outside this prefab: the consumer checks its constraint
        cs = P.components(v["path"], r"^  Sources:")
        if A(len(cs) == 1, f"visible {v['path']} carries one constraint"):
            want = [(v["proxy"], 1, ZERO3, ZERO_Q), (v["joint"], 0, ZERO3, tuple(v["ropeRotationOffsetQ"]))]
            bad = source_faults(P.source_paths(cs[0]), want)
            A(not bad, f"{v['path']} sources [{v['proxy']}, {v['joint']}] at weights [1, 0], rope rotation offset "
              f"{v['ropeRotationOffset']}" + (f": {bad}" if bad else ""))
    if entry:
        # The rope frame's world pin: zero source offset, sourced from THIS entry's World.prefab.
        cs = P.components("Rope/Frame", r"^  Sources:")
        wg = meta_guid(os.path.join(HERE, "assets", "World.prefab"))
        if A(len(cs) == 1, "Rope/Frame carries one constraint"):
            src = P.source_paths(cs[0])
            A(len(src) == 1 and src[0][0] == wg and close(src[0][2], (0, 0, 0)),
              "Rope/Frame is pinned to assets/World.prefab at zero source offset")
    print("OK" if ok else "FAILED")
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check(CONFIG, os.path.join(HERE, "Leash.prefab")) else 1)
    if "--check-prefab" in sys.argv:   # a consumer's prefab at this CONFIG: the entry-only asserts skipped
        i = sys.argv.index("--check-prefab") + 1
        if i >= len(sys.argv):
            refuse("--check-prefab needs a prefab path")
        sys.exit(0 if check(CONFIG, sys.argv[i], entry=False) else 1)
    text, r = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with open(os.path.join(HERE, "rig.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, indent=2)
        fh.write("\n")
    print(f"wrote controller.yaml ({CONFIG['controller']}) and rig.json: {len(r['chain'])} proxy transforms, "
          f"{len(r['visible'])} visible constraints, L {r['L']} m, StakeRoot {r['stakeRoot']['localPosition']} "
          f"{r['stakeRoot']['localEuler']}")


if __name__ == "__main__":
    main()
