#!/usr/bin/env python3
"""control-panel generator: the frame around the controls. Emits the glue's clip table, the entry's own
object-sync build and rig.json from CONFIG, and checks ControlPanel.prefab's hand-maintained surface.

    python control-panel/generate.py           # writes controller.yaml's clip table, object-sync/controller.yaml, rig.json
    python control-panel/generate.py --check   # asserts ControlPanel.prefab against CONFIG; writes nothing

Edit CONFIG, rerun, then recompile `built/` and `object-sync/built/` as units in a mounting Editor
(CONVENTIONS.md §The gate), with both the source and the outDir addressed as
`Packages/com.ryan6vrc.patterns/control-panel/...`. The controls subtree has its own generator
(`controls/generate.py`); this one reads its `controls` rows, `face` and rig() (every cap, slider and knob
number, the bone and shape names, the bone rest poses) and keeps only the frame's own geometry: plate, grips,
lamp placement and size. rig.json is the mesh builder's whole input
(assets/ControlPanel_build.py); its `restPoses` are the positions `controls/generate.py --check` holds the
imported bones to.

WHAT THE FRAME IS
-----------------
`two-hand-prop`'s full-rotation prop carries the panel; `object-sync`'s word carries where it was set down,
so a player who joins late sees it in place. The glue controller (`controller.yaml`) arbitrates the two:
`two-hand-prop`'s eleven-state cell lifted whole, plus `grab-sync`'s word states. Its header carries the
design decisions; the clip table below its BEGIN marker is emitted here.

The one new node is `Park`, a child of the pinned root: a position and a rotation constraint over
[TwoHandProp/HomeAnchor/Offset, ObjectSync/Sync, Park itself, TwoHandProp/Body]. The Body slot lets Park copy a
remote's replayed drop during Bridge, so Synced glides from where the panel rested instead of snapping. `two-hand-prop`'s `Body` already takes
`HomeAnchor/Offset` as source0 on both of its constraints; that slot is repointed at `Park`, so every cell
state that shows the prop at home now shows it at Park, and Park is home, the word, or a damped glide onto
the word, by its weights. No source is added to any `two-hand-prop` constraint (its README §Traps); Park is
this entry's own node, so its Body slot is not bound by that rule.

THE CLIP TABLE
--------------
Read live from ../two-hand-prop/controller.yaml at emit time: every cell binding, values unchanged, path
gaining the `TwoHandProp/` prefix. Each glue clip names the cell clip it transcribes (CLIPS below), adds
Park's eight weights from PARK_SETS, and in the glue's own hidden states overrides the cell's `Display`
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
                   Overridden: Body's position and rotation constraint source0 -> Park; the handle places
                   on every copy site two-hand-prop's README §Knobs lists (the positions of RestA/B,
                   CarryA/B, OffA/B, AimNode, HolderA/B and HandleA/B_End, and the PositionAtRest of the
                   constraints on CarryA/B, AimNode, HolderA/B). Each handle's chain runs the mesh's grip:
                   in the panel frame HandleX_Root at (-+X, 0, grips.z[0]) and HandleX_End, the tip and so
                   the handle's place, at (-+X, 0, grips.z[1]), X = handleSpacing / 2 + grabOffset; in
                   Body's frame each is that point turned `tilt` about X. So RestX = the root, HolderX =
                   Body's position + RestX, CarryX = AimNode (A) = the tip, OffX = -tip, HandleX_End's
                   local position tip - root (HandleX_Root stays at its holder's origin). Added: a connected instance of controls/Panel.prefab
                   under Body/Display, named Panel, at the origin rotated CONFIG tilt about X (the lift unit; its bindings
                   resolve here).
  Park             as above, four sources; Locked, zero offsets, rest weights HOME. Its rotation constraint's
                   source0 is HomeLevel instead of HomeAnchor/Offset.
  HomeLevel        a child of the pinned root: one VRCRotationConstraint over TwoHandProp/HomeAnchor/Offset,
                   AffectsRotation Y only, Locked, zero offsets. The home rest's heading without its lean, so a
                   panel at home stays level when the wearer leans and a grab from home starts level
                   (runtime.md §Constraints, the rotation-axis-mask bullet; compositions/grab-sync's home mux).
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
import math
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
# The least margin by which each handle's grab capsule must reach past its visible grip's farthest surface, metres.
GRIP_COVER = 0.005
CELL = "TwoHandProp"

CONFIG = {
    "prefix": "ControlPanel",
    "controller": "ControlPanel_Fx",
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
    # The buttons are live only once every copy has settled onto the word, because each other player's copy
    # replays the drop through its own IK-delayed view of the hands and a press judged on the wearer's copy
    # before theirs settles lands on a different cap than the one they see.
    #   settle      a remote's inert dwell in Synced while Park glides its replayed drop onto the word; the
    #               glide keeps 1/(1+syncDamp) of the gap per frame, so 5 cm closes to 1 mm in about 41 frames,
    #               0.9 s at 45 fps. [EMPIRICAL]
    #   liveMargin  the wire's latency between the wearer's release and a remote seeing it. [EMPIRICAL]
    # The wearer's buttons go live `bridge + settle + liveMargin` after a drop (the Dropped dwell).
    "settle": 1.0,
    "liveMargin": 0.5,
    # The panel's mount under Body/Display: degrees about X, the handle axis. Negative tips the face toward -Z,
    # the holder's side when handle A is in the left hand. The two-hand carry keeps roll level with the world,
    # so this is the only tilt the panel has, carried, set down or at home.
    "tilt": -45,
    # Park's damped word weight against its self source of 1 in Synced and Bridge. [EMPIRICAL] A per-frame
    # keep of 1/(1+w): sized so a word step finishes gliding inside one word refresh, so steps never stack
    # into a trailing lag. Lower glides longer than a refresh; higher steps visibly. Frame-rate dependent
    # (spring-damping README §Framerate dependence).
    "syncDamp": 0.1,
    # Panel geometry, Unity frame of TwoHandProp/Body/Display, metres (contract's rig.json defaults).
    "handleSpacing": 0.4,
    # bottom -0.02: the chosen selector cap rests sunk `travel` by its lamp shape and a press sinks it `squish` more, and
    # its skirt reaches `travel` below the face (capTop - travel), so it bottoms at capTop - 3 travel - squish; the mesh
    # builder asserts it clears the underside.
    "plate": {"x": [-0.17, 0.17], "z": [-0.17, 0.17], "top": 0.02, "bottom": -0.02},
    "grips": {"x": 0.2, "radius": 0.018, "z": [-0.07, 0.07]},
    # How far each handle's grab chain sits outward along X from its grip's axis, at x = +-(handleSpacing / 2 +
    # grabOffset); the grip mesh stays put. A wider offset moves the grab volume off the controls between the
    # handles; --check holds that each capsule still covers its whole visible grip with GRIP_COVER to spare.
    "grabOffset": 0,
    # The rows (cap positions and joint, slider tracks, chains, knob rest, channel depth) are the controls CONFIG's;
    # rig() reads them from there. Only the mesh-only numbers are here. Every lamp parks `parked` under the face and
    # its shape raises it to `raised`.
    "lamps": {"parked": 0.019, "raised": 0.0205},
    # A dot beyond each button cap. rig() gives each selector segment the same dot at the same z offset from it.
    "buttonLamps": {"z": 0.145, "diameter": 0.014},
    # The knob's footprint, [along X, across Z].
    "knob": [0.02, 0.025],
    # A discrete slider's segment row, one lamp per slot: `dz` from the track, `depth` along Z, `widthFraction` of
    # one slot's pitch along X.
    "segments": {"dz": -0.03, "depth": 0.006, "widthFraction": 0.8},
    # A smooth slider's strip: always lit from atlas swatch `swatch` (the mesh builder refuses one without
    # emission). It has no shape and no geometry of its own here: rig() places it in `segments`' row geometry.
    "strip": {"swatch": "amber"},
    "mesh": "ControlPanel",
    "material": "ControlPanel",
}


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def controls():
    """The controls subtree's generator module: its CONFIG owns the rows, so the mesh, the lamps, the contacts
    and the controller agree. Refuses a layout its validate() refuses."""
    if not os.path.exists(CONTROLS_GEN):
        refuse(f"{CONTROLS_GEN} is missing; the rows are read from its CONFIG.")
    mod = load(CONTROLS_GEN, "control_panel_controls")
    mod.validate(mod.CONFIG)
    return mod


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


def rig(c, ctl):
    """rig.json: every number the mesh is built to. `ctl` is the controls generator module: the rows, names and
    rest poses come from its rig(), the mesh-only geometry from `c`."""
    cc = ctl.CONFIG
    if abs(c["plate"]["x"][1] - c["plate"]["x"][0] - cc["face"]) > 1e-9:
        refuse(f"plate.x spans {c['plate']['x'][1] - c['plate']['x'][0]} but the controls CONFIG's face is {cc['face']}; they are one width.")
    cr = ctl.rig(cc)
    nm, sh, cb = cr["names"], cr["shapes"], cc["caps"]
    btn, sel = ctl.rows(cc, "buttons")[0], ctl.rows(cc, "selector")[0]
    sliders = []
    for e in cr["sliders"]:
        s = {"name": e["name"], "kind": e["kind"], "x": e["x"], "z": e["z"], "y": e["y"], "bone": e["bone"],
             "end": e["end"], "knob": e["knob"], "boneLength": e["boneLength"], "rootX": e["rootX"],
             "tipRestX": e["tipRestX"], "knobY": e["knobY"], "channelDepth": e["channelDepth"], "knobSize": c["knob"]}
        seg = c["segments"]
        if e["kind"] == "slider":
            s["segments"] = {"z": round(e["z"] + seg["dz"], 6), "depth": seg["depth"],
                             "widthFraction": seg["widthFraction"], "shapes": sh[e["name"]]}
        else:
            # The strip takes a discrete slider's segment row: `dz` from its own track, `depth` as its width.
            s["strip"] = {"x": e["x"][0], "z": round(e["z"] + seg["dz"], 6), "width": seg["depth"],
                          "swatch": c["strip"]["swatch"]}
        sliders.append(s)
    return {
        "_comment": "GENERATED by control-panel/generate.py; never hand-edit.",
        "frame": "Unity panel frame: X long axis (handle A at -X), +Y face normal, +Z far edge; metres. Every position "
                 "below is in it; restPoses are the bones' heads, relative to the Panel bone.",
        "plate": c["plate"],
        "grips": c["grips"],
        "handleSpacing": c["handleSpacing"],
        "lamps": c["lamps"],
        "buttons": {"x": list(btn["x"]), "z": btn["z"], "capDiameter": cb["capDiameter"], "capTop": cb["capTop"],
                    "travel": cb["travel"], "squish": cb["squish"], "boneLength": cb["boneLength"],
                    "chainRadius": cb["radius"]},
        "buttonLamps": dict(c["buttonLamps"], shapes=sh["buttons"]),
        # The selector's segments share the buttons' joint; `segmentWidth` is each one's extent along X (its depth in Z
        # is the caps' capDiameter), and `sink` how far its lamp shape lowers the chosen segment. Its lamps are the
        # button row's dots, each the button dots' z offset (buttonLamps.z - buttons.z) from its segment.
        "selector": {"x": list(sel["x"]), "z": sel["z"], "segmentWidth": sel["segmentWidth"], "sink": cb["travel"],
                     "lamps": {"z": round(sel["z"] + c["buttonLamps"]["z"] - btn["z"], 6),
                               "diameter": c["buttonLamps"]["diameter"]}, "shapes": sh["selector"]},
        "sliders": sliders,
        "controlsRetract": {"shape": sh["retract"], "capDepth": cb["travel"], "channelDepth": cc["sliders"]["channelDepth"]},
        "bones": nm,
        "restPoses": cr["bones"],
        "mesh": c["mesh"],
        "material": c["material"],
    }


# ======================================================================= the glue's clip table ===
BEGIN = "  # --- BEGIN GENERATED by generate.py: cell bindings from two-hand-prop, Park from PARK_SETS."
END = "  # --- END GENERATED"
DISPLAY = "Body/Display/GameObject.m_IsActive"
PARK_KEYS = [f"Park/{k}.Sources.source{i}.Weight" for k in ("VRCPositionConstraint", "VRCRotationConstraint")
             for i in range(4)]


def park_sets(c):
    """Park's weights over [home, word, self, Body], one set for both channels."""
    w = c["syncDamp"]
    return {"HOME": (1, 0, 0, 0), "ACQUIRE": (0, 1, 0, 0), "SYNC": (0, w, 1, 0), "BRIDGE": (0, 0, 0, 1)}


# (glue clip, cell clip it transcribes, Park set, Display override or None, length key or None, live, note).
# A length key of None keeps the cell clip's own length; `live` is the clip's write of the controls' <internal>/Live.
CLIPS = (
    ("timer", "timer", "HOME", None, None, 0, "cell `timer` + Park HOME  [EMPIRICAL: the remote settle dwell is the cell's]"),
    ("disabled", "disabled", "HOME", None, None, 0, "cell `disabled` + Park HOME"),
    ("home", "home", "HOME", None, None, 0, "cell `home` + Park HOME: Body rides Park, Park rides HomeAnchor/Offset"),
    ("heldA", "heldA", "HOME", None, None, 0, "cell `heldA` + Park HOME"),
    ("heldB", "heldB", "HOME", None, None, 0, "cell `heldB` + Park HOME"),
    ("bothA", "bothA", "HOME", None, None, 0, "cell `bothA` + Park HOME"),
    ("bothB", "bothB", "HOME", None, None, 0, "cell `bothB` + Park HOME"),
    ("handoffToA", "handoffToA", "HOME", None, None, 0, "cell `handoffToA` + Park HOME  [EMPIRICAL: the cell's dwell and damper]"),
    ("handoffToB", "handoffToB", "HOME", None, None, 0, "cell `handoffToB` + Park HOME  [EMPIRICAL: the cell's dwell and damper]"),
    ("dropped", "dropped", "HOME", None, "live", 0, "cell `dropped` + Park HOME: the wearer's hold, buttons inert  [EMPIRICAL: dwell = clip length = live]"),
    ("placed", "dropped", "HOME", None, None, 1, "cell `dropped` + Park HOME: the wearer's hold, buttons live"),
    ("waiting", "waiting", "HOME", None, None, 0, "cell `waiting` + Park HOME: hidden, never shown at a guessed spot"),
    ("bridge", "dropped", "BRIDGE", None, "bridge", 0, "cell `dropped` + Park BRIDGE: the remote holds its replayed drop and Park copies it rigidly  [EMPIRICAL: dwell = clip length]"),
    ("synced", "home", "SYNC", 1, "settle", 0, "cell `home` + Park SYNC: Body rides Park, Park glides from the replayed drop onto the word, buttons inert  [EMPIRICAL: dwell = clip length = settle]"),
    ("syncedLive", "home", "SYNC", 1, None, 1, "cell `home` + Park SYNC, settled: buttons live"),
    ("acquire", "home", "ACQUIRE", 0, "acquire", 0, "cell `home` + Park ACQUIRE, hidden: Park and Body flush onto the word  [EMPIRICAL: dwell = clip length]"),
    ("resume", "home", "ACQUIRE", 0, "bridge", 0, "cell `home` + Park ACQUIRE, hidden: the cull park  [EMPIRICAL: dwell = clip length = bridge]"),
    ("resume_grabA", "heldA", "ACQUIRE", 0, "resumeGrab", 0, "cell `heldA` + Park ACQUIRE, hidden while the cell populates  [EMPIRICAL: dwell = clip length]"),
    ("resume_grabB", "heldB", "ACQUIRE", 0, "resumeGrab", 0, "cell `heldB` + Park ACQUIRE, hidden while the cell populates  [EMPIRICAL: dwell = clip length]"),
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


def live_param():
    return f"{controls().CONFIG['internal']}/Live"


def emit_clips(c):
    cell = parse_clips(CELL_DOC)
    sets = park_sets(c)
    lens = dict(c, live=c["bridge"] + c["settle"] + c["liveMargin"])
    live = live_param()
    out = []
    for name, src, pset, disp, lkey, lv, note in CLIPS:
        if src not in cell:
            refuse(f"two-hand-prop/controller.yaml has no clip `{src}`; `{name}` transcribes it.")
        e = cell[src]
        if DISPLAY not in e["set"]:
            refuse(f"two-hand-prop clip `{src}` no longer writes {DISPLAY}; the glue's show/hide carve rides it.")
        length = lens[lkey] if lkey else (float(e["len"]) if e["len"] else None)
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
        out.append(f'      "{live}": {lv}')
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
      and re.search(r"useGlobalParam: 1\n", tog[0]), f"one bare Toggle drives {c['prefix']}/Enable")
    # The Toggle's default must be the glue's declared default for the same parameter, or the menu and the animator disagree at spawn.
    decl = re.search(rf"^  {re.escape(c['prefix'])}/Enable:.*?default: (\S+?)[,\s]", open(GLUE_DOC, encoding="utf-8").read(), re.M)
    don = re.search(r"defaultOn: (\d)\n", tog[0]) if len(tog) == 1 else None
    A(decl and don and (float(decl.group(1)) > 0.5) == (don.group(1) == "1"),
      f"the Toggle's defaultOn ({don and don.group(1)}) matches the glue's declared {c['prefix']}/Enable default ({decl and decl.group(1)})")

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

    # Park: four sources, zero offsets, Locked, rest weights HOME. The glue's value-sets write one weight per
    # source slot, so every set must span exactly the prefab's slots: a set one short leaves a slot at its
    # last-written weight, one long writes a slot past totalLength that the client never solves.
    sets = park_sets(c)
    A(all(len(v) == 4 for v in sets.values()), f"every Park value-set spans Park's four sources ({sets})")
    home = sets["HOME"]
    for has, label, h0 in ((r"^  PositionAtRest:(?![\s\S]*RotationAtRest)", "position", f"{CELL}/HomeAnchor/Offset"),
                           (r"^  RotationAtRest:", "rotation", "HomeLevel")):
        cs = [d for d in P.components("Park", r"^  Sources:") if re.search(has, d, re.M)]
        if A(len(cs) == 1, f"Park carries one {label} constraint"):
            want = [(h0, home[0], None, None), (f"{SYNC_MOUNT}/Sync", home[1], None, None),
                    ("Park", home[2], None, None), (f"{CELL}/Body", home[3], None, None)]
            bad = ls.source_faults(P.sources(cs[0]), want) + ls.own_offsets(cs[0])
            A(not bad and ls.field(cs[0], "Locked") == "1",
              f"Park {label} sources [{h0.rsplit('/', 2)[-2] + '/' if '/' in h0 else ''}{h0.rsplit('/', 1)[-1]}, Sync, self, Body] at {list(home)}, zero offsets, Locked" + (f": {bad}" if bad else ""))

    # HomeLevel: the home rest's heading only, so a lean at the hips never tilts the panel at home, and a grab
    # from home (the one-hand carry freezes the attitude it starts from) never starts tilted.
    hl = P.components("HomeLevel", r"^  Sources:")
    if A(len(hl) == 1 and re.search(r"^  RotationAtRest:", hl[0], re.M), "HomeLevel carries one rotation constraint"):
        d = hl[0]
        bad = ls.source_faults(P.sources(d), [(f"{CELL}/HomeAnchor/Offset", 1, None, None)]) + ls.own_offsets(d)
        axes = [ls.field(d, f"AffectsRotation{a}") for a in "XYZ"]
        A(not bad and axes == ["0", "1", "0"] and ls.field(d, "Locked") == "1",
          f"HomeLevel: one source HomeAnchor/Offset at 1, Y only, zero offsets, Locked (axes {axes}{': ' + str(bad) if bad else ''})")

    # Every constraint authored here fills exactly its totalLength slots.
    for i, (cls, d) in P.docs.items():
        m = re.search(r"^    totalLength: (\d+)", d, re.M)
        if m:
            filled = len(re.findall(r"SourceTransform: \{fileID: [1-9-]", d))
            A(filled == int(m.group(1)), f"&{i}: totalLength {m.group(1)} == filled slots {filled}")

    check_cell(c, ls, P, A)
    check_panel(ls, P, A, c)
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
    """The nested two-hand-prop: its removals, the Park repoint, the handle places and their grip coverage."""
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

    # The handle places and chains on every copy site (two-hand-prop README §Knobs), A at -X and B at +X: each grab
    # chain runs its grip, root at grips.z[0] and tip, the handle's place, at grips.z[1], at panel y 0 and
    # x = +-(handleSpacing / 2 + grabOffset), rotated into Body's frame by the tilt about X. An axis the instance
    # does not override keeps the cell prefab's value, so each site is read as override-else-prefab.
    hx, gz, th = c["handleSpacing"] / 2 + c["grabOffset"], c["grips"]["z"], math.radians(c["tilt"])

    def body_of(x, z):
        return (x, -z * math.sin(th), z * math.cos(th))

    at = {}
    for f, g, pp, v, ref in mods:
        n, d = nm(f, g), body(f, g)
        for key, kind in (("m_LocalPosition", "tf"), ("PositionAtRest", "rest")):
            if pp.startswith(key + ".") and (kind == "rest" or "m_Father" in d):
                base = ls.vec(d, key)
                cur = at.setdefault((kind, n), list(base) if base else [float("nan")] * 3)
                cur["xyz".index(pp[-1])] = float(v)
    body_pos = tuple(at.get(("tf", "Body"), ls.vec(cell_doc("Body"), "m_LocalPosition")))
    sites = {}
    for k, sx in (("A", -1), ("B", 1)):
        end, root = body_of(sx * hx, gz[1]), body_of(sx * hx, gz[0])
        sites[f"Rest{k}"] = root
        sites[f"Carry{k}"] = end
        sites[f"Off{k}"] = tuple(-v for v in end)
        sites[f"Holder{k}"] = tuple(b + v for b, v in zip(body_pos, root))
        sites[f"Handle{k}_End"] = tuple(e - r for e, r in zip(end, root))
    sites["AimNode"] = sites["CarryA"]
    off = lambda kind, names: {n: at.get((kind, n)) for n in names
                               if not at.get((kind, n)) or any(not abs(a - w) <= 1e-6 for a, w in zip(at[(kind, n)], sites[n]))}
    bad = off("tf", sites)
    A(not bad, f"handle places (spacing {c['handleSpacing']}, grabOffset {c['grabOffset']}, chains along grips.z {gz}): "
               f"transform position on {sorted(sites)} (off: {bad})")
    bad = off("rest", ("CarryA", "CarryB", "AimNode", "HolderA", "HolderB"))
    A(not bad, f"handle places: PositionAtRest on CarryA/B, AimNode, HolderA/B (off: {bad})")
    # Each grab capsule covers its whole visible grip with GRIP_COVER to spare: the grip (a cylinder of grips.radius
    # about x = +-grips.x, spanning grips.z) lies within the capsule's radius of its axis, which spans the same z at
    # x = +-hx, and the capsule's ends reach a radius past the grip's.
    rad = {}
    for n in ("HandleA_Root", "HandleB_Root"):
        d = cell_doc(n, "allowGrabbing:")
        flat = d and re.search(r"^  radiusCurve:\n    serializedVersion: \d+\n    m_Curve: \[\]", d, re.M)
        r = [float(v) for f, g, pp, v, ref in mods if nm(f, g) == n and pp == "radius"]
        curved = any(nm(f, g) == n and pp.startswith("radiusCurve.") for f, g, pp, v, ref in mods)
        if flat and not curved:
            rad[n] = r[-1] if r else float(ls.field(d, "radius"))
    reach = abs(hx - c["grips"]["x"]) + c["grips"]["radius"]
    A(len(rad) == 2 and min(rad.values()) - reach >= GRIP_COVER - 1e-9,
      f"each handle's grab capsule (radius {rad}, axis x +-{hx:g}) covers its whole grip (axis x +-{c['grips']['x']}, "
      f"radius {c['grips']['radius']}): farthest grip surface {reach:.4f} m from the axis, wanted at least {GRIP_COVER} "
      "inside the radius (a radius curve counts as no radius)")


def cell_doc(name, has="m_LocalPosition:"):
    """The document on GameObject `name` in two-hand-prop's TwoHandProp_Yaw.prefab (TwoHandProp_Full's base) that
    carries `has`, or None: the value an axis the nested instance does not override keeps."""
    text = open(os.path.join(ROOT, "two-hand-prop", "TwoHandProp_Yaw.prefab"), encoding="utf-8").read()
    docs = re.findall(r"^--- !u!(\d+) &(-?\d+)\n(.*?)(?=^--- |\Z)", text, re.M | re.S)
    go = {i for cls, i, d in docs if cls == "1" and re.search(rf"^  m_Name: {re.escape(name)}$", d, re.M)}
    owner = lambda d: (re.search(r"^  m_GameObject: \{fileID: (-?\d+)\}", d, re.M) or [None, None])[1]
    return next((d for cls, i, d in docs if has in d and owner(d) in go), None)


def check_panel(ls, P, A, c):
    """The controls subtree: one connected instance of controls/Panel.prefab, named Panel, under
    TwoHandProp/Body/Display at the origin, rotated CONFIG tilt about X, where the controls controller's bindings resolve."""
    got = nested(ls, P, "control-panel/controls/Panel.prefab")
    if not A(got, "ControlPanel.prefab nests control-panel/controls/Panel.prefab once"):
        return
    inst, sb, mods, nm, body = got
    A(next((v.strip() for f, g, pp, v, ref in mods if pp == "m_Name"), None) == "Panel", "the controls instance is named 'Panel'")
    tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)\}", sb)
    A(tp and P.path_of(int(tp.group(1))) == f"{CELL}/Body/Display", f"the controls instance hangs under {CELL}/Body/Display")
    half = math.radians(c["tilt"]) / 2
    want = {"m_LocalPosition.x": 0, "m_LocalPosition.y": 0, "m_LocalPosition.z": 0, "m_LocalRotation.x": math.sin(half),
            "m_LocalRotation.y": 0, "m_LocalRotation.z": 0, "m_LocalRotation.w": math.cos(half), "m_LocalScale.x": 1,
            "m_LocalScale.y": 1, "m_LocalScale.z": 1}
    tfm = {pp: float(v) for f, g, pp, v, ref in mods if pp in want and nm(f, g) == "Panel" and "m_Father" in body(f, g)}
    unset = {"m_LocalRotation.w": 1}
    A(all(abs(tfm.get(pp, unset.get(pp, 0)) - v) < 1e-5 for pp, v in want.items() if pp.startswith(("m_LocalPosition", "m_LocalRotation"))),
      f"the controls instance's root sits at the origin, tilted {c['tilt']} degrees about X ({tfm})")
    other = sorted({pp for f, g, pp, v, ref in mods if pp not in want and pp != "m_Name" and not pp.startswith("m_LocalEulerAnglesHint")})
    removed = re.findall(r"m_Removed(?:Components|GameObjects): \[\]", sb)
    A(not other and len(removed) == 2, f"the controls instance carries no other override or removal ({other})")


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
        json.dump(rig(c, controls()), fh, indent=2)
        fh.write("\n")
    facts = f["facts"]
    print(f"wrote controller.yaml ({len(CLIPS)} clips, {n} lines), object-sync/controller.yaml "
          f"({facts['wireBits']} wire bits, ~{facts['cycleSeconds']:.3f}s refresh), rig.json; "
          f"globalParams {global_params(c, og)}")


if __name__ == "__main__":
    main()
