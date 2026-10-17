#!/usr/bin/env python3
"""control-panel controls generator: emits controls/controller.yaml (ControlPanelControls_Fx) from CONFIG.

    python control-panel/controls/generate.py            # writes controls/controller.yaml
    python control-panel/controls/generate.py --check    # asserts Panel.prefab's hand-built surface against CONFIG

The entry's own generate.py imports CONFIG, document(cfg) and rig(cfg) from here. Edit CONFIG, rerun, then
recompile controls/built/ as a unit in a mounting Editor (CONVENTIONS.md §The gate). Every output is a pure
function of CONFIG; nothing here writes Unity assets: `--check` holds the prefab to CONFIG afterwards.

WHAT THE CONTROLS ARE
---------------------
One self-contained subtree, `Panel.prefab`, lifted whole by a consumer: the model (assets/ControlPanel.fbx)
fully unpacked, so every bone is a named node a binding and `--check` can address, plus the components below
and nothing else. Unpacked, the prefab no longer follows the FBX: after a re-export that moves a bone, rebuild
it (`--check` pins each bone's rest pose, so a stale one fails there).

  Buttons     the FBX bone under Panel, root of ONE physbone (multiChildType Ignore) over the four button chains
              Btn1..Btn4 -> Btn<i>_End. Angle limit zero, squish on, stretch zero, collision on, grabbing off: a
              hand pushing a cap down compresses that chain. The solver squishes by moving Btn<i>_End along the
              bone, never by scaling the bone, so a cap skinned to Btn<i>_End travels rigidly. Each tip sits inside its
              cap's dome by the chain radius, so the radius engages at the cap's top and not above it.
  Btn<i>_End  each carries a local-only face-mode box receiver whose +Z face points up the press axis; it reads
              the sender's depth into the box, `rig()['receiver']`. It rides the End directly: nothing scales it.
  PressSender Unity-side, under the Panel bone: one local-only capsule sender along X lying at bottom-out depth,
              tag `tag`. The readout senses the panel's own parts, never the presser's hand, so it does not care
              which senders a stranger's avatar carries or when they joined.
  Slider      the posed stretch physbone, Slider -> Slider_End along the slot; `CP/Slider_Stretch` is the
              knob's fraction along the slot, 0 at slot 0's end and 1 at the far end. The knob skins to
              Slider_End, which the solver translates along the slot at unit scale.

THE LAYERS
----------
  Buttons     Idle -> the press ladder, Press1 > Press2 > Press3 > Press4, first match wins. A press entering
              above `press` depth goes to Arm<i>, which falls back to Idle if the reading drops under `press`
              before `arm` seconds: a hand passing sideways over a cap pushes it down too, and only a press holds the
              depth. Past the dwell it goes to Set<i> when the button reads off and Clear<i> when it reads on (a
              driver cannot invert), each stamping ControlPanel/Btn<i> wearer-only; then Hold until every receiver is
              below `release` depth, then Cooldown for `cooldown` seconds, then Idle. The cooldown is the floor
              between two toggles of one button, so it exceeds the wire's set/clear separation. Lifted from
              zone-touch's ladder, hold and cooldown dwell.
  Slot        N states, one per slot, each stamping its index into ControlPanel/Slot wearer-only; a state moves
              to its neighbour when CP/Slider_Stretch crosses the shared boundary by `hysteresis`. It runs live
              while the slider is held, so the lit segment follows the hand; nothing samples at release.
  Lamps       one state: a Direct tree weighted by CP/One, a 1D tree per button on ControlPanel/Btn<i> and one
              1D tree on ControlPanel/Slot whose child k raises Lamp_Seg<k> and lowers the rest.
  Offline     Online / Offline writing Lamp_Offline: offline on a remote copy until object-sync's word is
              trustworthy (not IsLocal, and ObjectSync/Enable or OS/Ready low). A state machine because a tree
              cannot read IsLocal without declaring it float.
Every state keys every binding its layer owns; Buttons and Slot own none, Lamps and Offline own the shapes.

CONFIG
------
  controller    the emitted controller's name.
  prefix        the published prefix (ControlPanel/Btn<i>, ControlPanel/Slot).
  internal      the internal prefix (required): no published wildcard may reach it.
  N             slider slots; feeds the segment lamps and the Slot layer together.
  mountPath     the Panel instance from the FullController's GameObject; every binding is prefixed with it.
  armature      the FBX armature node under the Panel instance (bones live under <armature>/Panel).
  mesh          the skinned mesh node under the Panel instance.
  buttons       button x positions in the panel frame (one per button), z, the Buttons root's height, the bones' head height and length,
                travel, and the chain radius (metres). maxSquish is travel over length.
  press, release   press depth fractions of travel: a press is accepted at or above `press`, held until every
                receiver is at or below `release`.
  boxSpan       the receiver box's depth along the press axis, a multiple of travel above 1, so a full press
                lies inside the box instead of on its top face (a face-mode box reads 0 past either face).
  senderRadius  the capsule sender's radius; its top surface sits at the tip's bottom-out height.
  arm           seconds a press must hold above `press` before it stamps [EMPIRICAL].
  cooldown      seconds between a release and the next accepted press.
  hysteresis    the Slot layer's margin past each slot boundary, in fractions of the slot's whole length.
  slider        the slot's x range, z, the Slider bone's root x, height, length (its maxStretch is the slot over it) and
                chain radius.
  tag           the sender/receiver collision tag (private).
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME = 1 / 60

CONFIG = {
    "controller": "ControlPanelControls_Fx",
    "prefix": "ControlPanel",
    "internal": "CP",
    "N": 5,
    "mountPath": "TwoHandProp/Body/Display/Panel",
    "armature": "Armature",
    "mesh": "ControlPanel",
    "buttons": {"x": (-0.09, -0.03, 0.03, 0.09), "z": 0.05, "rootY": 0.02, "head": 0.0, "boneLength": 0.02, "travel": 0.01, "radius": 0.01},
    "press": 0.8,
    "release": 0.5,
    "boxSpan": 1.1,
    "boxWidth": 0.02,
    "senderRadius": 0.004,
    "arm": 0.1,
    "cooldown": 0.5,
    "hysteresis": 0.02,
    "slider": {"x": (-0.1, 0.1), "z": -0.04, "rootX": -0.13, "y": 0.02, "boneLength": 0.03, "radius": 0.02},
    "tag": "ControlPanelPress",
}


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


def validate(c):
    n = c["N"]
    if not isinstance(n, int) or n < 2 or n > 255:
        refuse("N is a whole number of slots, 2..255: Slot is an 8-bit synced int.")
    for k in ("prefix", "internal"):
        if not c[k] or "/" in c[k]:
            refuse(f"{k} is one bare name segment, required.")
    if c["internal"].startswith(c["prefix"]):
        refuse("internal may not sit under prefix: the published wildcard would reach it.")
    b = c["buttons"]
    if not 1 <= len(b["x"]) <= 8:
        refuse("one to eight buttons.")
    if b["travel"] <= 0 or b["travel"] >= b["boneLength"]:
        refuse("travel is positive and shorter than the button bone: maxSquish is travel over bone length.")
    if b["radius"] <= 0:
        refuse("the button chain radius is positive: a radius of 0 neither collides nor grabs.")
    if not 0 < c["arm"] < c["cooldown"]:
        refuse("arm is positive and shorter than the cooldown.")
    if not 0 < c["release"] < c["press"] <= 1:
        refuse("0 < release < press <= 1: the hold band needs a gap.")
    if c["boxSpan"] <= 1 or c["press"] / c["boxSpan"] >= 1:
        refuse("boxSpan above 1: a full press must sit inside the box, not on its top face.")
    if c["senderRadius"] <= 0:
        refuse("senderRadius is positive.")
    if c["boxWidth"] / 2 >= min(abs(x1 - x0) for x0, x1 in zip(sorted(b["x"]), sorted(b["x"])[1:])) - c["boxWidth"] / 2:
        refuse("receiver boxes overlap their neighbours' across X.")
    if c["cooldown"] <= 0.2:
        refuse("cooldown at or under the wire's 0.2 s set/clear floor: two toggles could be a lost pair.")
    if not 0 < c["hysteresis"] < 0.5 / n:
        refuse("hysteresis is positive and under half a slot, or a slot has no stable band.")
    s = c["slider"]
    if s["x"][0] - s["rootX"] - s["boneLength"] > 1e-9 or s["x"][1] <= s["x"][0]:
        refuse("the Slider bone's rest tip is the slot's low end: rootX + boneLength == slider.x[0].")


def r6(v):
    return round(v, 6)


def rig(c):
    """Every number the Unity-side controls subtree is built to (contacts, physbones)."""
    validate(c)
    b, s = c["buttons"], c["slider"]
    span = b["travel"] * c["boxSpan"]
    tip = b["head"] + b["boneLength"]
    # Face mode reads (half + d + r) / size along the box's +Z, d the sender centre's offset from the box centre.
    # The box rides the cap tip, its centre `travel - span/2` below it: the reading is 0 with the cap at rest (the
    # sender's top surface on the box's bottom face) and depth / span as the cap goes down.
    centre = tip - (b["travel"] - span / 2)
    w = r6(c["boxWidth"])
    return {
        "receiver": {"shape": "Box", "useFaceProximity": True, "size": [w, w, r6(span)],
                     "position": [0, r6(centre - tip), 0], "rotation": [-90, 0, 0],
                     "localOnly": True, "allowSelf": True, "allowOthers": False, "tag": c["tag"],
                     "params": [f"{c['internal']}/Press{i + 1}" for i in range(len(b["x"]))]},
        "sender": {"shape": "Capsule", "radius": c["senderRadius"],
                   "height": r6(max(b["x"]) - min(b["x"]) + c["boxWidth"] + 2 * c["senderRadius"]),
                   "position": [r6((max(b["x"]) + min(b["x"])) / 2), r6(tip - b["travel"] - c["senderRadius"]), b["z"]],
                   "rotation": [0, 0, 90], "localOnly": True, "tag": c["tag"]},
        "thresholds": {"press": r6(c["press"] / c["boxSpan"]), "release": r6(c["release"] / c["boxSpan"])},
        "buttonsPhysBone": {"maxSquish": r6(b["travel"] / b["boneLength"]), "maxStretch": 0, "radius": b["radius"],
                            "parameter": f"{c['internal']}/Buttons"},
        "buttonTip": {"rest": r6(tip), "bottom": r6(tip - b["travel"])},
        "sliderPhysBone": {"maxStretch": r6((s["x"][1] - s["x"][0]) / s["boneLength"]), "maxSquish": 0, "radius": s["radius"],
                           "parameter": f"{c['internal']}/Slider"},
        # Rest poses in the Panel bone's frame (the panel frame): what the FBX must import as.
        "bones": dict([("Buttons", [0, b["rootY"], b["z"]])]
                      + [(f"Buttons/Btn{i + 1}", [x, b["head"], b["z"]]) for i, x in enumerate(b["x"])]
                      + [(f"Buttons/Btn{i + 1}/Btn{i + 1}_End", [x, r6(tip), b["z"]]) for i, x in enumerate(b["x"])]
                      + [("Slider", [s["rootX"], s["y"], s["z"]]), ("Slider/Slider_End", [s["x"][0], s["y"], s["z"]])]),
    }


def document(c):
    r = rig(c)
    P, I, N, M = c["prefix"], c["internal"], c["N"], c["mountPath"]
    nb = len(c["buttons"]["x"])
    BTN = [f"{P}/Btn{i + 1}" for i in range(nb)]
    PRESS = r["receiver"]["params"]
    SLOT, STRETCH, ONE = f"{P}/Slot", f"{I}/Slider_Stretch", f"{I}/One"
    press, release = r["thresholds"]["press"], r["thresholds"]["release"]
    shape = f"{M}/{c['mesh']}/SkinnedMeshRenderer.blendShape."
    LB = [f"{shape}Lamp_Btn{i + 1}" for i in range(nb)]
    LS = [f"{shape}Lamp_Seg{k}" for k in range(N)]
    LO = f"{shape}Lamp_Offline"
    h = c["hysteresis"]

    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by control-panel/controls/generate.py; edit its CONFIG and rerun, never hand-edit this file.")
    o("# The controls subtree's machine: button stamps, the slider quantizer, the lamps. The generator's docstring is the design record.")
    o(f"# Published (synced, unsaved, wearer-stamped): {', '.join(BTN)} (bool on the wire) and {SLOT} (int on the wire); both")
    o("# float in the animator, because the lamp trees read them as blend parameters.")
    o(f"# Press accepted at receiver reading {press}, held until every reading is under {release} (depth {c['press']} / {c['release']} of")
    o(f"# travel over a box {c['boxSpan']} travels deep). Arm {c['arm']} s, cooldown {c['cooldown']} s. Slot hysteresis {h} of the slider's length.")
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
    for p in BTN:
        o(f"  {p}: {{ type: float, default: 0, vrc: {{ type: bool, synced: true, saved: false }} }}")
    o(f"  {SLOT}: {{ type: float, default: 0, vrc: {{ type: int, synced: true, saved: false }} }}")
    for p in PRESS:
        o(f"  {p}: float   # sensing: a local-only receiver's press depth reading")
    o(f"  {STRETCH}: float   # sensing: the slider physbone ({I}/Slider)")
    o(f"  {ONE}: {{ type: float, default: 1, scratch: true }}   # the Direct tree's constant weight")
    o("  # Shared with the object-sync build through the one component; declarations match the entry's.")
    o("  ObjectSync/Enable: { type: float, default: 1, vrc: { type: bool, synced: true, saved: false } }")
    o("  OS/Ready: { type: float, default: 0, vrc: { type: bool, synced: false, saved: false } }")
    o("  IsLocal: bool   # VRC built-in")
    o("")
    o("layers:")
    # ---- Buttons ----
    o("  - name: Buttons")
    o("    states:")
    o("      # Remotes never leave Idle: the receivers are local-only, so their readings stay 0 there.")
    o("      Idle:")
    o("        motion: ~")
    o("        transitions:")
    for i in range(nb):
        o(f"          - {{ to: Arm{i + 1}, when: [ {PRESS[i]} greater {press} ] }}")
    o("      # The dwell: a cap pushed down by a hand passing sideways falls back before the clip ends. The stamp")
    o("      # rungs' condition is constant over the state (nothing writes Btn<i> here), so exit time is safe on them.")
    for i in range(nb):
        o(f"      Arm{i + 1}:")
        o("        motion: { clip: arm }")
        o("        transitions:")
        o(f"          - {{ to: Idle, when: [ {PRESS[i]} less {press} ] }}")
        o(f"          - {{ to: Set{i + 1}, when: [ {BTN[i]} less 0.5 ], exitTime: 1.0 }}")
        o(f"          - {{ to: Clear{i + 1}, when: [ {BTN[i]} greater 0.5 ], exitTime: 1.0 }}")
    for i in range(nb):
        for name, v in (("Set", 1), ("Clear", 0)):
            o(f"      {name}{i + 1}:")
            o("        motion: { clip: tick }")
            o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {BTN[i]}: {v} }} }} }} ]")
            o("        transitions:")
            o("          - { to: Hold, when: [], exitTime: 1.0 }")
    o("      Hold:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Cooldown, when: [ {', '.join(f'{p} less {release}' for p in PRESS)} ] }}")
    o("      # The floor between two toggles: no press rung leaves here.")
    o("      Cooldown:")
    o("        motion: { clip: cooldown }")
    o("        transitions:")
    o("          - { to: Idle, when: [], exitTime: 1.0 }")
    o("    default: Idle")
    o("    layout:")
    cols = [-330 + 240 * i for i in range(nb)]
    nodes = (["Idle: [30, 180]"] + [f"Arm{i + 1}: [{x}, 260]" for i, x in enumerate(cols)]
             + [f"Set{i + 1}: [{x}, 340]" for i, x in enumerate(cols)]
             + [f"Clear{i + 1}: [{x}, 420]" for i, x in enumerate(cols)] + ["Hold: [30, 520]", "Cooldown: [30, 600]"])
    o(f"      nodes: {{ {', '.join(nodes)} }}")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    # ---- Slot ----
    o("  # Boundary k/N between slot k-1 and slot k; a state leaves for a neighbour only past it by the hysteresis.")
    o("  - name: Slot")
    o("    states:")
    for k in range(N):
        o(f"      Slot{k}:")
        o("        motion: ~")
        o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {SLOT}: {k} }} }} }} ]")
        o("        transitions:")
        if k + 1 < N:
            o(f"          - {{ to: Slot{k + 1}, when: [ {STRETCH} greater {r6((k + 1) / N + h)} ] }}")
        if k > 0:
            o(f"          - {{ to: Slot{k - 1}, when: [ {STRETCH} less {r6(k / N - h)} ] }}")
    o("    default: Slot0")
    o("    layout:")
    o(f"      nodes: {{ {', '.join(f'Slot{k}: [{30 + 240 * k}, 180]' for k in range(N))} }}")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    # ---- Lamps ----
    o("  - name: Lamps")
    o("    states:")
    o("      Lamps:")
    o("        motion:")
    o("          tree: direct")
    o("          name: Lamps")
    o("          children:")
    for i in range(nb):
        o("            - tree: 1d")
        o(f"              name: Btn{i + 1}")
        o(f"              param: {BTN[i]}")
        o(f"              directWeight: {ONE}")
        o("              children:")
        o(f"                - {{ clip: btn{i + 1}_off, threshold: 0 }}")
        o(f"                - {{ clip: btn{i + 1}_on, threshold: 1 }}")
    o("            - tree: 1d")
    o("              name: Slot")
    o(f"              param: {SLOT}")
    o(f"              directWeight: {ONE}")
    o("              children:")
    for k in range(N):
        o(f"                - {{ clip: seg{k}, threshold: {k} }}")
    o("    default: Lamps")
    o("")
    # ---- Offline ----
    o("  # A remote shows the offline lamp until object-sync's word is trustworthy; the wearer never does.")
    o("  - name: Offline")
    o("    states:")
    o("      Offline:")
    o("        motion: { clip: offline }")
    o("        transitions:")
    o("          - { to: Online, when: [ IsLocal is true ] }")
    o("          - { to: Online, when: [ ObjectSync/Enable greater 0.5, OS/Ready greater 0.5 ] }")
    o("      Online:")
    o("        motion: { clip: online }")
    o("        transitions:")
    o("          - { to: Offline, when: [ IsLocal is false, ObjectSync/Enable less 0.5 ] }")
    o("          - { to: Offline, when: [ IsLocal is false, OS/Ready less 0.5 ] }")
    o("    default: Offline")
    o("    layout:")
    o("      nodes: { Offline: [30, 180], Online: [270, 180] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o("clips:")
    o(f"  tick: {{ seconds: {r6(FRAME)} }}")
    o(f"  arm: {{ seconds: {c['arm']} }}")
    o(f"  cooldown: {{ seconds: {c['cooldown']} }}")
    for i in range(nb):
        for name, v in (("off", 0), ("on", 100)):
            o(f'  btn{i + 1}_{name}: {{ set: {{ "{LB[i]}": {v} }} }}')
    for k in range(N):
        o(f"  seg{k}:")
        o("    set:")
        for j in range(N):
            o(f'      "{LS[j]}": {100 if j == k else 0}')
    o(f'  offline: {{ set: {{ "{LO}": 100 }} }}')
    o(f'  online: {{ set: {{ "{LO}": 0 }} }}')
    return "\n".join(L) + "\n"


# ---- --check: Panel.prefab's hand-built surface, which no compile or gate reads ----
# Serialized enum values (VRC SDK): MultiChildType Ignore 0; AdvancedBool False 0 / True 1; LimitType Angle 1;
# ImmobileType AllMotion 0; contact ShapeType Capsule 1 / Box 2; ReceiverType Proximity 2.
def docs_of(path):
    """fileID -> (class id, body, stripped)."""
    return {int(m.group(2)): (int(m.group(1)), m.group(4), bool(m.group(3))) for m in re.finditer(
        r"^--- !u!(\d+) &(-?\d+)( stripped)?\n(.*?)(?=^--- |\Z)", open(path, encoding="utf-8").read(), re.M | re.S)}


def fid(d, key):
    m = re.search(rf"^  {key}: \{{fileID: (-?\d+)", d, re.M)
    return int(m.group(1)) if m else None


def vec(d, key):
    m = re.search(rf"^  {key}: \{{x: (\S+), y: (\S+), z: (\S+)(?:, w: (\S+))?\}}", d, re.M)
    return tuple(float(v) for v in m.groups() if v is not None) if m else None


def field(d, key):
    m = re.search(rf"^  {key}: (.*)$", d, re.M)
    return m.group(1).strip() if m else None


def close(a, b, eps=1e-5):
    return a is not None and len(a) == len(b) and all(abs(x - y) <= eps for x, y in zip(a, b))


def quat(e):
    """Unity Euler degrees (applied Z, then X, then Y) -> (x, y, z, w)."""
    def axis(ax, deg):
        h = math.radians(deg) / 2
        v = [0.0, 0.0, 0.0]
        v[ax] = math.sin(h)
        return (v[0], v[1], v[2], math.cos(h))

    def mul(a, b):
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)
    return mul(mul(axis(1, e[1]), axis(0, e[0])), axis(2, e[2]))


def same_rot(got, want):
    return got is not None and abs(abs(sum(a * b for a, b in zip(got, want))) - 1) < 1e-5


def rotate(q, v):
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx)


def tags_of(d):
    m = re.search(r"^  collisionTags:\n((?:  - .+\n)+)", d, re.M)
    return [ln.split("- ", 1)[1].strip() for ln in m.group(1).splitlines()] if m else []


def check(c, prefab_path):
    """Panel.prefab against CONFIG. Reads the YAML textually; a field it cannot find is a FAIL, never a pass."""
    r = rig(c)
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    if not A(os.path.exists(prefab_path), f"{prefab_path} exists"):
        return False
    docs = docs_of(prefab_path)
    A(not any(st for _, _, st in docs.values()) and not any(cls == 1001 for cls, _, _ in docs.values()),
      "no prefab instance inside: the model is unpacked, so every bone is a named node")
    name = {i: field(d, "m_Name") for i, (cls, d, _) in docs.items() if cls == 1}
    tf = {i: d for i, (cls, d, _) in docs.items() if cls == 4}
    go_tf = {fid(d, "m_GameObject"): i for i, d in tf.items()}

    def path_of(t):
        parts = []
        while t in tf and fid(tf[t], "m_Father"):
            parts.append(name[fid(tf[t], "m_GameObject")])
            t = fid(tf[t], "m_Father")
        return "/".join(reversed(parts))

    tf_at = {path_of(t): t for t in tf}
    bone = f"{c['armature']}/Panel"
    # Bone rest poses in the Panel bone's frame (the panel frame); each step carries its parent's local rotation.
    for rel, want in r["bones"].items():
        if not A(f"{bone}/{rel}" in tf_at, f"bone {bone}/{rel} present"):
            continue
        pos, rot, acc = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), bone
        for seg in rel.split("/"):
            acc = f"{acc}/{seg}"
            d = tf[tf_at[acc]]
            lp, lr = vec(d, "m_LocalPosition"), vec(d, "m_LocalRotation")
            off = rotate(rot, lp)
            pos = tuple(p + q for p, q in zip(pos, off))
            x1, y1, z1, w1 = rot
            x2, y2, z2, w2 = lr
            rot = (w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                   w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2)
        A(close(pos, tuple(want), 1e-4), f"{bone}/{rel} rests at {want} in the panel frame (got {[round(v, 5) for v in pos]})")
    if f"{bone}/Slider" in tf_at:
        along = rotate(vec(tf[tf_at[f"{bone}/Slider"]], "m_LocalRotation"), (0, 1, 0))
        A(close(along, (1, 0, 0), 1e-4), f"Slider's local +Y points along the slot (+X) (got {[round(v, 4) for v in along]})")
    root_go = next((fid(d, "m_GameObject") for d in tf.values() if not fid(d, "m_Father")), None)
    A(name.get(root_go) == "Panel", f"root is Panel (got {name.get(root_go)})")
    A(c["mesh"] in tf_at, f"mesh node {c['mesh']} present (the lamp clips bind {c['mountPath']}/{c['mesh']})")

    comps = [d for cls, d, _ in docs.values() if cls == 114]
    host = lambda d: path_of(go_tf.get(fid(d, "m_GameObject")))
    pbs = [d for d in comps if re.search(r"^  multiChildType:", d, re.M)]
    recv = [d for d in comps if re.search(r"^  receiverType:", d, re.M)]
    send = [d for d in comps if re.search(r"^  collisionTags:", d, re.M) and not re.search(r"^  receiverType:", d, re.M)]
    nb = len(c["buttons"]["x"])
    A(len(comps) == 2 + nb + 1 and len(pbs) == 2 and len(recv) == nb and len(send) == 1,
      f"two physbones, {nb} receivers and one sender, nothing else (got {len(comps)} MonoBehaviours)")

    def physbone(at, want, extra):
        d = next((p for p in pbs if host(p) == at), None)
        if not A(d is not None, f"a physbone on {at}"):
            return
        A(fid(d, "rootTransform") == tf_at.get(at), f"{at}: rootTransform is {at}")
        flds = {"parameter": want["parameter"], "maxSquish": want["maxSquish"], "maxStretch": want["maxStretch"],
                "radius": want["radius"], "limitType": "1", "maxAngleX": 0, "pull": 1, "spring": 0, "stiffness": 0,
                "gravity": 0, "immobileType": "0", "immobile": 1, "isAnimated": "0", "resetWhenDisabled": "1",
                "ignoreTransforms": "[]", "colliders": "[]"}
        flds.update(extra)
        for k, v in flds.items():
            got = field(d, k)
            good = (got is not None and abs(float(got) - v) < 1e-5) if isinstance(v, (int, float)) else got == v
            A(good, f"{at}: {k} == {v} (got {got})")

    physbone(f"{bone}/Buttons", r["buttonsPhysBone"], {"multiChildType": "0", "allowCollision": "1", "allowGrabbing": "0", "allowPosing": "0"})
    physbone(f"{bone}/Slider", r["sliderPhysBone"], {"allowCollision": "0", "allowGrabbing": "1", "allowPosing": "1",
                                                     "stretchMotion": 0, "snapToHand": "0"})

    rv = r["receiver"]
    for i, prm in enumerate(rv["params"]):
        at = f"{bone}/Buttons/Btn{i + 1}/Btn{i + 1}_End"
        d = next((x for x in recv if host(x) == at), None)
        if not A(d is not None, f"a receiver on {at}"):
            continue
        A(field(d, "parameter") == prm, f"{at}: parameter {prm} (got {field(d, 'parameter')})")
        A(tags_of(d) == [rv["tag"]], f"{at}: tags == [{rv['tag']}] (got {tags_of(d)})")
        for k, v in (("shapeType", "2"), ("useFaceProximity", "1"), ("receiverType", "2"), ("localOnly", "1"),
                     ("allowSelf", "1"), ("allowOthers", "0")):
            A(field(d, k) == v, f"{at}: {k} == {v} (got {field(d, k)})")
        A(fid(d, "rootTransform") in (0, tf_at.get(at)), f"{at}: rides its own End")
        A(close(vec(d, "size"), tuple(rv["size"])), f"{at}: box size {rv['size']}")
        A(close(vec(d, "position"), tuple(rv["position"])), f"{at}: box offset {rv['position']}")
        A(same_rot(vec(d, "rotation"), quat(rv["rotation"])), f"{at}: box +Z face points up the press axis")
    sv = r["sender"]
    if A(len(send) == 1 and host(send[0]) == bone, f"one sender, on {bone}"):
        d = send[0]
        A(tags_of(d) == [sv["tag"]], f"sender tags == [{sv['tag']}] (got {tags_of(d)})")
        A(field(d, "shapeType") == "1" and field(d, "localOnly") == "1", "sender is a local-only capsule")
        A(fid(d, "rootTransform") in (0, tf_at.get(bone)), f"sender rides {bone}")
        for k in ("radius", "height"):
            A(field(d, k) is not None and abs(float(field(d, k)) - sv[k]) < 1e-6, f"sender {k} == {sv[k]}")
        A(close(vec(d, "position"), tuple(sv["position"])), f"sender at {sv['position']} (top surface on bottom-out)")
        A(same_rot(vec(d, "rotation"), quat(sv["rotation"])), "sender capsule lies along X")
    return ok


def main():
    if "--check" in sys.argv:
        return 0 if check(CONFIG, os.path.join(HERE, "Panel.prefab")) else 1
    text = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    r = rig(CONFIG)
    print(f"wrote controls/controller.yaml ({CONFIG['controller']}): N={CONFIG['N']}, press/release readings "
          f"{r['thresholds']['press']}/{r['thresholds']['release']}, receiver {r['receiver']['size']} at {r['receiver']['position']}, "
          f"sender {r['sender']['position']} h {r['sender']['height']}")


if __name__ == "__main__":
    sys.exit(main())
