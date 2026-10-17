#!/usr/bin/env python3
"""control-panel generator: the frame around the controls. Emits the glue's clip table, the entry's own
object-sync build and rig.json from CONFIG, and checks ControlPanel.prefab's hand-maintained surface.

    python control-panel/generate.py           # writes controller.yaml's clip table, object-sync/controller.yaml, rig.json
    python control-panel/generate.py --check   # asserts ControlPanel.prefab against CONFIG; writes nothing

Edit CONFIG, rerun, then recompile `built/` and `object-sync/built/` as units in a mounting Editor
(CONVENTIONS.md §The gate), with both the source and the outDir addressed as
`Packages/com.ryan6vrc.patterns/control-panel/...`. The controls subtree has its own generator
(`controls/generate.py`); this one imports its CONFIG for N, the slot count the mesh and the lamps share.

WHAT THE FRAME IS
-----------------
`two-hand-prop`'s full-rotation prop carries the panel; `object-sync`'s word carries where it was set down,
so a player who joins late sees it in place. The glue controller (`controller.yaml`) arbitrates the two:
`two-hand-prop`'s eleven-state cell lifted whole, plus `grab-sync`'s word states. Its header carries the
design decisions; the clip table below its BEGIN marker is emitted here.

The one new node is `Park`, a child of the pinned root: a position and a rotation constraint over
[TwoHandProp/HomeAnchor/Offset, ObjectSync/Sync, Park itself]. `two-hand-prop`'s `Body` already takes
`HomeAnchor/Offset` as source0 on both of its constraints; that slot is repointed at `Park`, so every cell
state that shows the prop at home now shows it at Park, and Park is home, the word, or a damped glide onto
the word, by its weights. No source is added to any `two-hand-prop` constraint (its README §Traps).

THE CLIP TABLE
--------------
Read live from ../two-hand-prop/controller.yaml at emit time: every cell binding, values unchanged, path
gaining the `TwoHandProp/` prefix. Each glue clip names the cell clip it transcribes (CLIPS below), adds
Park's six weights from PARK_SETS, and in the glue's own hidden states overrides the cell's `Display`
write (the one carve: `Display` is the cell's visibility node and the glue's too, because the panel model
rides under it). Nothing here freezes a cell value: a retune of two-hand-prop reaches the glue on the
next run.

HOW ControlPanel.prefab IS BUILT
--------------------------------
The prefab is the artifact; this is the recipe it was made by, and `--check` holds it to CONFIG.

  ControlPanel     root. VRCParentConstraint + VRCScaleConstraint -> ../object-sync/assets/World.prefab at
                   zero offsets, both m_Enabled 0, and a VRCFury ApplyDuringUpload playing
                   ../object-sync/assets/PinEnable.anim (re-enables both at build): grab-sync's root, copied.
                   One VRCFury FullController: controllers and prms [glue built/, controls/built/,
                   object-sync/built/] in that order; globalParams = global_params(). One bare VRCFury
                   Toggle `Control Panel` -> ControlPanel/Enable, defaultOn.
  TwoHandProp      nested ../two-hand-prop/TwoHandProp_Full.prefab. Removed: its FullController and
                   Toggle (the glue plays its chords), its FreezeToWorld node (the root pin owns the world
                   frame), Body/Display/Payload, GripA, GripB (the panel model carries its own grips).
                   Overridden: Body's position and rotation constraint source0 -> Park; the handle spacing
                   to CONFIG handleSpacing on every copy site two-hand-prop's README §Knobs lists (RestA/B,
                   CarryA/B, OffA/B, AimNode, HolderA/B and the PositionAtRest of the constraints on
                   CarryA/B, AimNode, HolderA/B). Added: Body/Display/Panel, the controls subtree's mount
                   (controls/Panel.prefab once it exists; a placeholder cube until then).
  Park             as above; Locked, zero offsets, rest weights HOME.
  ObjectSync       nested ../object-sync/ObjectSync.prefab (the entry root: one object, full rotation).
                   Removed: its root FullController, Toggle, ApplyDuringUpload and pin pair (the shared root
                   component, the root Toggle and the root pin replace them), and the Drop Toggle on
                   Sync_Target (its FreezeToWorld writer would fight the glue). Overridden: Rig/Prop parked at
                   rig_offset(rigSeed) and every contact retagged to tag_set(rigSeed); Sync_Target's
                   constraint gains source0 = TwoHandProp/Body at weight 1, static, so the wearer measures the
                   prop itself.
"""

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
OS_GEN = os.path.join(ROOT, "object-sync", "generate.py")
LEASH_GEN = os.path.join(ROOT, "leash-stake", "generate.py")
CONTROLS_GEN = os.path.join(HERE, "controls", "generate.py")
CELL_DOC = os.path.join(ROOT, "two-hand-prop", "controller.yaml")
GLUE_DOC = os.path.join(HERE, "controller.yaml")
SYNC_OUT = os.path.join(HERE, "object-sync", "controller.yaml")
RIG_OUT = os.path.join(HERE, "rig.json")
SYNC_MOUNT = "ObjectSync"
CELL = "TwoHandProp"

CONFIG = {
    "prefix": "ControlPanel",
    "controller": "ControlPanel_Fx",
    # ControlPanel/Enable's default: the panel spawns shown.
    "enableDefault": True,
    # This build's object-sync tags and park; differs from every other object-sync build on the avatar
    # (a consumer's game objects carry their own).
    "rigSeed": "control-panel/g1",
    # The glue's dwells, seconds. [EMPIRICAL] all three; runtime.md's 90% rule governs a change.
    #   bridge   a remote's wait after a release before it trusts the word: the word's release-to-committed
    #            latency (a measure walk plus one wire refresh) and margin.
    #   acquire  a late joiner's hidden flush onto the word before it shows.
    #   resumeGrab  the hidden wait while a grab taken out of the cull park populates the cell.
    # The cull park's own dwell is `bridge` (a resume cannot tell how long ago the release was).
    # bridge = two of this build's word refreshes (a pose that just missed a batch waits a whole extra
    # refresh) + Park's glide to within a few percent at syncDamp + margin for a loaded frame clock; it
    # re-derives whenever the object-sync build's batch count or syncDamp changes.
    "bridge": 2.4,
    # acquire: Park rigid on the word and Body on Park settle within a frame or two; the length covers a slow
    # client's few frames.
    "acquire": 0.15,
    "resumeGrab": 0.1,
    # Park's damped word weight against its self source of 1 in Synced and Bridge. [EMPIRICAL] A per-frame
    # keep of 1/(1+w): sized so a word step finishes gliding inside one word refresh, so steps never stack
    # into a trailing lag. Lower glides longer than a refresh; higher steps visibly. Frame-rate dependent
    # (spring-damping README §Framerate dependence).
    "syncDamp": 0.1,
    # Panel geometry, Unity frame of TwoHandProp/Body/Display, metres (contract's rig.json defaults).
    "handleSpacing": 0.4,
    "plate": {"x": [-0.17, 0.17], "z": [-0.11, 0.11], "top": 0.02, "bottom": -0.01},
    "grips": {"x": 0.2, "radius": 0.018, "z": [-0.07, 0.07]},
    "buttons": {"x": [-0.09, -0.03, 0.03, 0.09], "z": 0.05, "capDiameter": 0.03, "capTop": 0.03, "travel": 0.01,
                "boneLength": 0.03},
    "buttonLamps": {"z": 0.085, "diameter": 0.008, "parked": 0.019, "raised": 0.0205},
    "slider": {"x": [-0.1, 0.1], "z": -0.04, "boneLength": 0.03, "rootX": -0.13, "knob": [0.02, 0.025]},
    "segments": {"z": -0.075, "depth": 0.006, "widthFraction": 0.6},
    "offline": {"x": 0.14, "z": 0.085, "diameter": 0.01},
    "labelStrip": {"z": -0.1},
    "mesh": "ControlPanel",
    "material": "ControlPanel",
}

# N when controls/generate.py cannot be read (the contract's default).
DEFAULT_N = 5
BONES = {"root": "Panel", "buttonsRoot": "Buttons", "buttons": ["Btn1", "Btn2", "Btn3", "Btn4"],
         "buttonEnds": ["Btn1_End", "Btn2_End", "Btn3_End", "Btn4_End"], "slider": "Slider",
         "sliderEnd": "Slider_End", "knob": "Knob"}


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slots():
    """N from the controls subtree's CONFIG, so the mesh, the lamps and the quantizer agree."""
    if not os.path.exists(CONTROLS_GEN):
        print(f"note: {os.path.relpath(CONTROLS_GEN, HERE)} is absent; N falls back to {DEFAULT_N}")
        return DEFAULT_N
    return int(load(CONTROLS_GEN, "control_panel_controls").CONFIG["N"])


def sync_gen():
    if not os.path.exists(OS_GEN):
        refuse(f"{OS_GEN} is missing; this entry drives object-sync's generator unmodified.")
    return load(OS_GEN, "object_sync_generate")


def sync_config(c, og):
    cfg = dict(og.CONFIG)
    cfg["objects"] = [{"name": "Prop", "rotation": "full"}]
    cfg["mountPath"] = SYNC_MOUNT
    cfg["rigSeed"] = c["rigSeed"]
    return cfg


def global_params(c, og):
    """One wildcard per published prefix: this entry's, then object-sync's derived list."""
    return [f"{c['prefix']}/*"] + og.document(sync_config(c, og))[1]["facts"]["globalParams"]


def rig(c, n):
    """rig.json: the numbers the mesh is built to. The contract's schema, key for key."""
    b, bl, sg, of = c["buttons"], c["buttonLamps"], c["segments"], c["offline"]
    return {
        "_comment": "GENERATED by control-panel/generate.py; never hand-edit.",
        "frame": "Unity: X long axis, +Y face normal, +Z far edge; metres",
        "N": n,
        "plate": c["plate"],
        "grips": c["grips"],
        "handleSpacing": c["handleSpacing"],
        "buttons": b,
        "buttonLamps": dict(bl, shapes=[f"Lamp_{name}" for name in BONES["buttons"]]),
        "slider": c["slider"],
        "segments": dict(sg, shapes=[f"Lamp_Seg{k}" for k in range(n)]),
        "offline": dict(of, shape="Lamp_Offline"),
        "labelStrip": c["labelStrip"],
        "bones": BONES,
        "mesh": c["mesh"],
        "material": c["material"],
    }


# ======================================================================= the glue's clip table ===
BEGIN = "  # --- BEGIN GENERATED by generate.py: cell bindings from two-hand-prop, Park from PARK_SETS."
END = "  # --- END GENERATED"
DISPLAY = "Body/Display/GameObject.m_IsActive"
PARK_KEYS = [f"Park/{k}.Sources.source{i}.Weight" for k in ("VRCPositionConstraint", "VRCRotationConstraint")
             for i in range(3)]


def park_sets(c):
    """Park's weights over [home, word, self], one triple for both channels."""
    w = c["syncDamp"]
    return {"HOME": (1, 0, 0), "ACQUIRE": (0, 1, 0), "SYNC": (0, w, 1)}


# (glue clip, cell clip it transcribes, Park set, Display override or None, length key or None, note).
# A length key of None keeps the cell clip's own length.
CLIPS = (
    ("timer", "timer", "HOME", None, None, "cell `timer` + Park HOME  [EMPIRICAL: the remote settle dwell is the cell's]"),
    ("disabled", "disabled", "HOME", None, None, "cell `disabled` + Park HOME"),
    ("home", "home", "HOME", None, None, "cell `home` + Park HOME: Body rides Park, Park rides HomeAnchor/Offset"),
    ("heldA", "heldA", "HOME", None, None, "cell `heldA` + Park HOME"),
    ("heldB", "heldB", "HOME", None, None, "cell `heldB` + Park HOME"),
    ("bothA", "bothA", "HOME", None, None, "cell `bothA` + Park HOME"),
    ("bothB", "bothB", "HOME", None, None, "cell `bothB` + Park HOME"),
    ("handoffToA", "handoffToA", "HOME", None, None, "cell `handoffToA` + Park HOME  [EMPIRICAL: the cell's dwell and damper]"),
    ("handoffToB", "handoffToB", "HOME", None, None, "cell `handoffToB` + Park HOME  [EMPIRICAL: the cell's dwell and damper]"),
    ("dropped", "dropped", "HOME", None, None, "cell `dropped` + Park HOME: the wearer's hold"),
    ("waiting", "waiting", "HOME", None, None, "cell `waiting` + Park HOME: hidden, never shown at a guessed spot"),
    ("bridge", "dropped", "SYNC", None, "bridge", "cell `dropped` + Park SYNC: the remote holds its replayed drop while Park glides onto the word  [EMPIRICAL: dwell = clip length]"),
    ("synced", "home", "SYNC", 1, None, "cell `home` + Park SYNC: Body rides Park, Park damps onto the word"),
    ("acquire", "home", "ACQUIRE", 0, "acquire", "cell `home` + Park ACQUIRE, hidden: Park and Body flush onto the word  [EMPIRICAL: dwell = clip length]"),
    ("resume", "home", "ACQUIRE", 0, "bridge", "cell `home` + Park ACQUIRE, hidden: the cull park  [EMPIRICAL: dwell = clip length = bridge]"),
    ("resume_grabA", "heldA", "ACQUIRE", 0, "resumeGrab", "cell `heldA` + Park ACQUIRE, hidden while the cell populates  [EMPIRICAL: dwell = clip length]"),
    ("resume_grabB", "heldB", "ACQUIRE", 0, "resumeGrab", "cell `heldB` + Park ACQUIRE, hidden while the cell populates  [EMPIRICAL: dwell = clip length]"),
)


def _num(v):
    r = round(float(v), 6)
    return str(int(r)) if r == int(r) else str(r)


def parse_clips(path):
    """two-hand-prop's clip table: 2-space clip names, `seconds:`, `set:` rows. Values kept verbatim."""
    clips, cur, started = {}, None, False
    for line in open(path, encoding="utf-8"):
        if line.startswith("clips:"):
            started = True
            continue
        if not started:
            continue
        m = re.match(r"^  ([\w]+):", line)
        if m:
            cur = clips.setdefault(m.group(1), {"set": {}, "len": None})
            continue
        m = re.match(r"^    seconds: ([\d.]+)", line)
        if m and cur is not None:
            cur["len"] = m.group(1)
            continue
        if re.match(r"^    (curves|length):", line):
            refuse(f"{path}: the cell gained a `{line.strip()}` row; parse_clips models `seconds:` and `set:` only.")
        m = re.match(r'^      "([^"]+)": (\S+)', line)
        if m and cur is not None:
            cur["set"][m.group(1)] = m.group(2)
    return clips


def emit_clips(c):
    cell = parse_clips(CELL_DOC)
    sets = park_sets(c)
    out = []
    for name, src, pset, disp, lkey, note in CLIPS:
        if src not in cell:
            refuse(f"two-hand-prop/controller.yaml has no clip `{src}`; `{name}` transcribes it.")
        e = cell[src]
        if DISPLAY not in e["set"]:
            refuse(f"two-hand-prop clip `{src}` no longer writes {DISPLAY}; the glue's show/hide carve rides it.")
        length = c[lkey] if lkey else (float(e["len"]) if e["len"] else None)
        head = f"  {name}:"
        out.append(head + " " * max(1, 16 - len(head)) + "# " + note)
        if length is not None:
            out.append(f"    seconds: {round(float(length), 4)}")
        out.append("    set:")
        for k, v in e["set"].items():
            if k == DISPLAY and disp is not None:
                v = str(disp)
            out.append(f'      "{CELL}/{k}": {v}')
        for k, v in zip(PARK_KEYS, sets[pset] * 2):
            out.append(f'      "{k}": {_num(v)}')
    return out


def splice(path, body):
    """Replace the marked region of controller.yaml, every byte outside it untouched."""
    lines = open(path, encoding="utf-8").read().split("\n")
    bi = [i for i, l in enumerate(lines) if l == BEGIN]
    ei = [i for i, l in enumerate(lines) if l == END]
    if len(bi) != 1 or len(ei) != 1 or bi[0] >= ei[0]:
        refuse(f"{os.path.basename(path)} must carry exactly one BEGIN/END marker pair, in order "
               f"(found {len(bi)} begin, {len(ei)} end).")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines[:bi[0] + 1] + body + lines[ei[0]:]))
    return len(body)


# ================================================== --check: the prefab surface no compile or gate reads ===
def check(c):
    og = sync_gen()
    ls = load(LEASH_GEN, "leash_stake_generate")   # its textual Prefab reader, read-only
    path = os.path.join(HERE, "ControlPanel.prefab")
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    if not A(os.path.exists(path), "ControlPanel.prefab exists"):
        return False
    index = ls.index_of(os.path.join(ROOT, "object-sync"), os.path.join(ROOT, "two-hand-prop"), HERE)
    P = ls.Prefab(path, index)
    g = lambda rel: ls.meta_guid(os.path.join(HERE, rel)) if os.path.exists(os.path.join(HERE, rel) + ".meta") else None

    # The FullController: one component, [glue, controls, object-sync] in both lists, the derived globalParams.
    A(P.body.count("class: FullController") == 1, "exactly one FullController authored in the prefab")
    want_gp = global_params(c, og)
    gp = re.findall(r"globalParams:\n((?:\s+- .+\n)+)", P.fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"") for ln in b.splitlines()] for b in gp]
    A(got == [want_gp], f"globalParams == {want_gp} (got {got})")
    for kind, rels in (("controllers", (f"built/{c['controller']}.controller",
                                        "controls/built/ControlPanelControls_Fx.controller",
                                        "object-sync/built/ObjectSync_Fx.controller")),
                       ("prms", (f"built/{c['controller']}_Parameters.asset",
                                 "controls/built/ControlPanelControls_Fx_Parameters.asset",
                                 "object-sync/built/ObjectSync_Fx_Parameters.asset"))):
        block = P.fc.split(f"        {kind}:")[1] if f"        {kind}:" in P.fc else ""
        block = re.split(r"\n        [a-zA-Z]", block, maxsplit=1)[0]
        refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32})", block)
        want = [g(r) for r in rels]
        A(None not in want and refs == want, f"FullController {kind} == {list(rels)} in that order (got {refs}, want {want})")
    tog = re.findall(r"class: Toggle,.*?\n(.*?)(?=\n--- |\Z)", P.body, re.S)
    A(len(tog) == 1 and re.search(rf"globalParam: {c['prefix']}/Enable\n", tog[0])
      and re.search(r"useGlobalParam: 1\n", tog[0]) and re.search(r"defaultOn: 1\n", tog[0]),
      f"one bare Toggle drives {c['prefix']}/Enable, defaultOn")

    # The root pin: grab-sync's, disabled in the editor, zero offsets, re-enabled by ApplyDuringUpload.
    pins = P.components("", r"^  Sources:")
    A(len(pins) == 2 and all(ls.field(d, "m_Enabled") == "0" for d in pins), "the root carries the pin pair, both m_Enabled 0")
    world = ls.meta_guid(os.path.join(ROOT, "object-sync", "assets", "World.prefab"))
    for d in pins:
        src = P.sources(d)
        A([s[0] for s in src] == [world] and all(ls.close(s[2] or ls.ZERO3, ls.ZERO3) for s in src)
          and not ls.own_offsets(d), "root pin sources World.prefab at zero offset")
    adu = re.findall(r"class: ApplyDuringUpload.*?(?=\n--- |\Z)", P.body, re.S)
    pe = ls.meta_guid(os.path.join(ROOT, "object-sync", "assets", "PinEnable.anim"))
    A(len(adu) == 1 and pe in adu[0], "one ApplyDuringUpload, playing object-sync/assets/PinEnable.anim")

    # Park: three sources, zero offsets, Locked, rest weights HOME.
    home = park_sets(c)["HOME"]
    for has, label in ((r"^  PositionAtRest:(?![\s\S]*RotationAtRest)", "position"), (r"^  RotationAtRest:", "rotation")):
        cs = [d for d in P.components("Park", r"^  Sources:") if re.search(has, d, re.M)]
        if A(len(cs) == 1, f"Park carries one {label} constraint"):
            want = [(f"{CELL}/HomeAnchor/Offset", home[0], None, None), (f"{SYNC_MOUNT}/Sync", home[1], None, None),
                    ("Park", home[2], None, None)]
            bad = ls.source_faults(P.sources(cs[0]), want) + ls.own_offsets(cs[0])
            A(not bad and ls.field(cs[0], "Locked") == "1",
              f"Park {label} sources [HomeAnchor/Offset, Sync, self] at {list(home)}, zero offsets, Locked" + (f": {bad}" if bad else ""))

    # Every constraint authored here fills exactly its totalLength slots.
    for i, (cls, d) in P.docs.items():
        m = re.search(r"^    totalLength: (\d+)", d, re.M)
        if m:
            filled = len(re.findall(r"SourceTransform: \{fileID: [1-9-]", d))
            A(filled == int(m.group(1)), f"&{i}: totalLength {m.group(1)} == filled slots {filled}")

    check_cell(c, ls, P, A)
    check_sync(c, og, ls, P, A)
    print("OK" if ok else "FAILED")
    return ok


def nested(ls, P, rel):
    """The one PrefabInstance of ../<rel> in the prefab, its modifications, and name/kind resolvers."""
    guid = ls.meta_guid(os.path.join(ROOT, rel))
    insts = [i for i, (cls, d) in P.docs.items() if cls == 1001 and f"guid: {guid}" in d.split("m_SourcePrefab:")[-1]]
    if len(insts) != 1:
        return None
    inst = insts[0]

    def real(f, g):
        s = P.sub(g)
        return s.resolve(int(f)) if s else None

    def nm(f, g):
        hit = real(f, g)
        if hit is None:
            return None
        s, i = hit
        cls, d = s.docs[i]
        if cls != 1:
            s, i = s.resolve(ls.fid(d, "m_GameObject")) or (None, None)
        m = re.search(r"^  m_Name: (.*)$", s.docs[i][1], re.M) if s else None
        return m.group(1).strip() if m else None

    def body(f, g):
        hit = real(f, g)
        return hit[0].docs[hit[1]][1] if hit else ""

    return inst, P.docs[inst][1], P.instance_mods(inst), nm, body


def removed_of(sb, nm, body):
    out = []
    for f, g in re.findall(r"fileID: (-?\d+), guid: (\w+)", "".join(re.findall(r"m_RemovedComponents:\n((?:    - \{fileID: .+\n)*)", sb))):
        d = body(f, g)
        k = re.search(r"class: (\w+)", d)
        kind = k.group(1) if k else ("ParentConstraint" if "RotationAtRest" in d and "PositionAtRest" in d else
                                     "ScaleConstraint" if "ScaleAtRest" in d else "constraint" if "Sources:" in d else "?")
        out.append((nm(f, g), kind))
    gos = [nm(f, g) for f, g in re.findall(r"fileID: (-?\d+), guid: (\w+)",
                                           "".join(re.findall(r"m_RemovedGameObjects:\n((?:    - \{fileID: .+\n)*)", sb)))]
    return out, gos


def check_cell(c, ls, P, A):
    """The nested two-hand-prop: its removals, the Park repoint, the handle spacing."""
    got = nested(ls, P, "two-hand-prop/TwoHandProp_Full.prefab")
    if not A(got, "ControlPanel.prefab nests two-hand-prop/TwoHandProp_Full.prefab once"):
        return
    inst, sb, mods, nm, body = got
    A(next((v.strip() for f, g, pp, v, ref in mods if pp == "m_Name"), None) == CELL, f"the cell instance is named {CELL!r}")
    tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)\}", sb)
    A(tp and int(tp.group(1)) == P.mount, "the cell instance hangs directly under the root")
    comps, gos = removed_of(sb, nm, body)
    root_name = "TwoHandProp_Yaw"   # the variant's root resolves to its base's GameObject
    for what in ("FullController", "Toggle"):
        A(any(k == what for n, k in comps), f"the cell instance removes its root {what} (got {comps})")
    A(sorted(gos) == sorted(["FreezeToWorld", "Payload", "GripA", "GripB"]),
      f"the cell instance removes FreezeToWorld, Payload, GripA, GripB (got {gos})")

    # Body's two constraints: source0 repointed at Park, nothing added (totalLength unmodified).
    for has, label in (("PositionAtRest", "position"), ("RotationAtRest", "rotation")):
        rows = {pp: (v, int(ref)) for f, g, pp, v, ref in mods if nm(f, g) == "Body" and has in body(f, g)
                and "Sources" in body(f, g) and pp.startswith("Sources.")}
        ref = rows.get("Sources.source0.SourceTransform", ("", 0))[1]
        A(ref and P.path_of(ref) == "Park", f"Body {label} constraint source0 -> Park")
        A("Sources.totalLength" not in rows and not [p for p in rows if not p.startswith("Sources.source0.")],
          f"Body {label} constraint: only source0 overridden, no source added ({sorted(rows)})")

    # Handle spacing on every copy site (two-hand-prop README §Knobs), A at -X and B at +X.
    h = c["handleSpacing"] / 2
    sites = {"RestA": -h, "RestB": h, "CarryA": -h, "CarryB": h, "OffA": h, "OffB": -h, "AimNode": -h,
             "HolderA": -h, "HolderB": h}
    tf = {}
    for f, g, pp, v, ref in mods:
        n = nm(f, g)
        if n in sites and pp == "m_LocalPosition.x" and "m_Father" in body(f, g):
            tf[n] = float(v)
    bad = {n: tf.get(n) for n, x in sites.items() if tf.get(n) is None or abs(tf[n] - x) > 1e-6}
    A(not bad, f"handle spacing {c['handleSpacing']}: transform x on {sorted(sites)} (off: {bad})")
    rest = {}
    for f, g, pp, v, ref in mods:
        n = nm(f, g)
        if n in ("CarryA", "CarryB", "AimNode", "HolderA", "HolderB") and pp == "PositionAtRest.x":
            rest[n] = float(v)
    want_rest = {n: sites[n] for n in ("CarryA", "CarryB", "AimNode", "HolderA", "HolderB")}
    bad = {n: rest.get(n) for n, x in want_rest.items() if rest.get(n) is None or abs(rest[n] - x) > 1e-6}
    A(not bad, f"handle spacing: PositionAtRest.x on CarryA/B, AimNode, HolderA/B (off: {bad})")


def check_sync(c, og, ls, P, A):
    """The nested object-sync: named, under the root, its fronts and pin removed, re-parked and retagged to
    rigSeed, Sync_Target measuring TwoHandProp/Body."""
    got = nested(ls, P, "object-sync/ObjectSync.prefab")
    if not A(got, "ControlPanel.prefab nests object-sync/ObjectSync.prefab once"):
        return
    inst, sb, mods, nm, body = got
    A(next((v.strip() for f, g, pp, v, ref in mods if pp == "m_Name"), None) == SYNC_MOUNT,
      f"the sync instance is named {SYNC_MOUNT!r} (the emitted bindings' prefix)")
    tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)\}", sb)
    A(tp and int(tp.group(1)) == P.mount, "the sync instance hangs directly under the root, the component's GameObject")
    comps, gos = removed_of(sb, nm, body)
    for who, what in ((SYNC_MOUNT, "FullController"), (SYNC_MOUNT, "Toggle"), (SYNC_MOUNT, "ApplyDuringUpload"),
                      (SYNC_MOUNT, "ParentConstraint"), (SYNC_MOUNT, "ScaleConstraint"), ("Sync_Target", "Toggle")):
        A((who, what) in comps, f"the sync instance removes {who}'s {what}")
    A(not gos, f"the sync instance removes no GameObject (got {gos})")

    scfg = sync_config(c, og)
    want_park = tuple(float(v) for v in og.rig_offset(c["rigSeed"]))
    pm = {pp: v for f, g, pp, v, ref in mods if nm(f, g) == "Prop" and pp.startswith("m_LocalPosition.")}
    got_park = tuple(float(pm.get(f"m_LocalPosition.{a}", "nan")) for a in "xyz")
    A(got_park == want_park, f"Rig/Prop park == rig_offset({c['rigSeed']!r}) {want_park} (got {got_park})")
    carriers = og.tag_carriers(scfg, "Prop")
    for tg in og.tag_set(scfg, "Prop"):
        n = sb.count(f"value: {tg}\n")
        A(n == carriers[tg], f"tag {tg} on exactly its stage's components ({n} of {carriers[tg]})")
    for tg in og.tag_set(og.CONFIG, og.CONFIG["objects"][0]["name"]):
        A(f"value: {tg}\n" not in P.body, f"no override names the entry-default tag {tg}")
    tg = {pp: (v, int(ref)) for f, g, pp, v, ref in mods if nm(f, g) == "Sync_Target" and pp.startswith("Sources.")}
    A(tg.get("Sources.totalLength", ("",))[0] == "1", f"Sync_Target's constraint carries one source (got {tg.get('Sources.totalLength')})")
    ref = tg.get("Sources.source0.SourceTransform", ("", 0))[1]
    A(ref and P.path_of(ref) == f"{CELL}/Body", f"Sync_Target's source0 is {CELL}/Body")
    A(tg.get("Sources.source0.Weight", ("1",))[0] == "1", "Sync_Target's source0 weight 1")

    # Names the glue reads that object-sync owns must be names its build declares.
    glue = re.sub(r"#.*", "", open(GLUE_DOC, encoding="utf-8").read())
    roots = {og.CONFIG["prefix"].split("/")[0], og.CONFIG["internal"].split("/")[0], og.CONFIG["channel"].split("/")[0]}
    reached = sorted({n for n in re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", glue) if n.split("/")[0] in roots})
    declared = set(re.findall(r"^  ([^\s#:]+):", og.document(scfg)[0], re.M))
    A(reached and not [n for n in reached if n not in declared], f"every object-sync name the glue reads is declared by its build ({reached})")


def main():
    c = CONFIG
    if "--check" in sys.argv:
        sys.exit(0 if check(c) else 1)
    og = sync_gen()
    n = splice(GLUE_DOC, emit_clips(c))
    stext, f = og.document(sync_config(c, og))
    os.makedirs(os.path.dirname(SYNC_OUT), exist_ok=True)
    with open(SYNC_OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(stext)
    with open(RIG_OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rig(c, slots()), fh, indent=2)
        fh.write("\n")
    facts = f["facts"]
    print(f"wrote controller.yaml ({len(CLIPS)} clips, {n} lines), object-sync/controller.yaml "
          f"({facts['wireBits']} wire bits, ~{facts['cycleSeconds']:.3f}s refresh), rig.json; "
          f"globalParams {global_params(c, og)}")


if __name__ == "__main__":
    main()
