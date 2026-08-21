#!/usr/bin/env python3
"""grab-sync — one grab-prop cell + one object-sync, architected for four.

    python compositions/grab-sync/generate.py           # writes both documents
    python compositions/grab-sync/generate.py --check   # asserts, writes nothing

Two emissions, one CONFIG:

  object-sync/controller.yaml   the CARRIED object-sync build — the entry's
                                generator run unmodified over PROPS-derived
                                objects. At one prop this is byte-identical to
                                the entry's committed `y/` document, and
                                `--check` pins that; at four props the same
                                CONFIG regenerates it with the slice ring, which
                                is what "scale by configuration" means.
  controller.yaml               the composition's own chords: the per-prop
                                merged placement layer, the engage latch, the
                                bridge timer and the remote weight crossfade.

WHY THE CHORDS ARE GENERATED AND NOT HAND-AUTHORED
--------------------------------------------------
Anything that would need re-derivation at N=4 — the bridge seconds, the
`Placed<N>` names, the per-prop paths — is computed from PROPS here, so growing
to four props is `PROPS = [...]` and a regenerate, never a re-derivation
(docs/local/g5-attempt2-spec.md §Scope owns the constraint).

THE CHORD LAW THIS FILE ENFORCES BY CONSTRUCTION
------------------------------------------------
IsLocal chords bind exactly the grab cell's own table (the LocalPose position
freeze, the SourcePosition sample pulse, the GrabPosition root freeze and its
mux weights) and NEVER a Container weight — the wearer rides LocalPose at the
authored 1:0 through WD-ON defaults, so no weight write can race the release
freeze (law 1). Remote chords bind the Container weights, and the only
transitions that move them are the bridge->placed crossfade and the carried
entry, both at least one animator frame from any physbone edge. `--check`
asserts both halves on the emitted document.

The grab cell's chord values are grab-prop's clip table with two renames and a
path prefix: vanilla `Container` (the enable-only display cell) maps to this
composition's `LocalPose`, vanilla's display GO maps to our `Container`, and
every path gains `<prop>/GrabRig/` or `<prop>/`. `--check` asserts the mapped
binding-superset against `../../grab-prop/controller.yaml` for the four
choreography clips (anchored/grabbed/released/dropped). The lifecycle clips
(disabled/timer/waiting) are deliberately NOT asserted: the composition
redesigns lifecycle around object-sync's Enable (off-is-reset, the visibility
latch), and pinning them would pin the design this composition replaces.

BRIDGE AND CROSSFADE
--------------------
bridge_seconds(facts) sums the named terms the spec argues (no freshness
observable exists, so the swap waits out the pipeline): the wearer's measure
period (33-frame walk + settleFrames), one full wire loop (batchCount x
batchSeconds), the fine re-lock bound (fineEscapeFrames), plus a flat buffer.
Exactness is not load-bearing — the swap glides (CROSSFADE_SECONDS, EMPIRICAL:
retune against wear-test item 5, longer hides more of the decode-vs-replay
disagreement at the cost of visible lag).
"""

import importlib.util
import os
import re as _re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
ENTRY = os.path.join(REPO, "object-sync", "generate.py")
GRABPROP_YAML = os.path.join(REPO, "grab-prop", "controller.yaml")
OUT_CARRIED = os.path.join(HERE, "object-sync", "controller.yaml")
OUT_OWN = os.path.join(HERE, "controller.yaml")

# The prop list — the ONE knob N=4 turns. Each entry is a name used for the
# composition's own nodes (`<name>/...`), its synced bit (`Placed<i>`), and its
# grab param (`Grab<i>`). The carried object-sync objects derive from it.
PROPS = ["Prop0"]

# Object-sync object names: at one prop the carried build keeps the entry's own
# committed `y/` shape verbatim (object "Prop", surface pair Sync/Sync_Target),
# so the carried document is byte-identical to the entry's and `--check` can pin
# it. At several props the objects take the prop names and the surface pairs
# gain them (Sync{Obj} — the spec's named N=4 hand-work).
def carried_objects():
    if len(PROPS) == 1:
        return [{"name": "Prop", "rotation": "y"}]
    return [{"name": p, "rotation": "y"} for p in PROPS]


CROSSFADE_SECONDS = 0.3   # EMPIRICAL — the remote placed-swap glide; wear-test item 5 owns retunes
BRIDGE_BUFFER_SECONDS = 0.5  # flat headroom over the derived pipeline terms
RELEASE_PULSE = [(0.0, 0), (0.25, 1), (0.5, 0)]  # grab-prop's released pulse, verbatim (90% rule)
REMOTE_DWELL_SECONDS = 1.0   # grab-prop's remote settle dwell, verbatim
ENGAGE_DELAY_SECONDS = 0.1   # >= one driver frame between Acquired and the latch (spec §Visibility)


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(f"REFUSE: object-sync generator not at {ENTRY}")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def carried_config(mod):
    cfg = dict(mod.CONFIG)
    cfg["objects"] = carried_objects()
    return cfg


def bridge_seconds(mod, cfg, facts):
    """Named terms, each argued in the spec; returns (seconds, term table)."""
    fps = 60.0
    measure = (33 + cfg["settleFrames"]) / fps
    wire = facts["batchCount"] * cfg["wire"]["batchSeconds"]
    relock = cfg["fineEscapeFrames"] / fps
    total = measure + wire + relock + BRIDGE_BUFFER_SECONDS
    terms = [("measure (33-frame walk + settleFrames)", measure),
             ("wire loop (batchCount x batchSeconds)", wire),
             ("fine re-lock bound (fineEscapeFrames)", relock),
             ("buffer", BRIDGE_BUFFER_SECONDS)]
    return round(total, 2), terms


# ------------------------------------------------------------ chord tables ----

def cell(p):
    """The grab-cell binding paths for one prop, vanilla names mapped."""
    return {
        "vis":    f"{p}/Container/GameObject.m_IsActive",
        "boneGO": f"{p}/GrabRig/GrabPosition/GrabBone/GameObject.m_IsActive",
        "lpEn":   f"{p}/LocalPose/VRCPositionConstraint.m_Enabled",
        "srcAct": f"{p}/GrabRig/SourcePosition/VRCPositionConstraint.IsActive",
        "gpAct":  f"{p}/GrabRig/GrabPosition/VRCPositionConstraint.IsActive",
        "gpW0":   f"{p}/GrabRig/GrabPosition/VRCPositionConstraint.Sources.source0.Weight",
        "gpW1":   f"{p}/GrabRig/GrabPosition/VRCPositionConstraint.Sources.source1.Weight",
    }


def weights(p):
    """The Container mux — REMOTE chords only (the chord law above)."""
    return {
        "cposW0": f"{p}/Container/VRCPositionConstraint.Sources.source0.Weight",
        "cposW1": f"{p}/Container/VRCPositionConstraint.Sources.source1.Weight",
        "crotW0": f"{p}/Container/VRCRotationConstraint.Sources.source0.Weight",
        "crotW1": f"{p}/Container/VRCRotationConstraint.Sources.source1.Weight",
    }


# vanilla grab-prop chord values (clip table, not prose): vis, boneGO, lpEn,
# srcAct, gpAct, gpW0, gpW1. `released` carries the srcAct pulse instead of a
# constant. The four choreography rows are asserted against grab-prop's yaml.
CHOREO = {
    "anchored": dict(vis=1, boneGO=1, lpEn=1, srcAct=1, gpAct=1, gpW0=1, gpW1=0),
    "grabbed":  dict(vis=1, boneGO=1, lpEn=1, srcAct=1, gpAct=0, gpW0=0, gpW1=1),
    "released": dict(vis=1, boneGO=1, lpEn=0,           gpAct=1, gpW0=0, gpW1=1),
    "dropped":  dict(vis=1, boneGO=1, lpEn=0, srcAct=0, gpAct=1, gpW0=0, gpW1=1),
}


def clip_lines(name, p, vals, pulse=False, seconds=None, remote=None, extra_comment=None):
    """One clip block. `remote` = (w0, w1) Container weights or None for an
    IsLocal chord (which must not bind them)."""
    c, w = cell(p), weights(p)
    L = [f"  {name}:"]
    if extra_comment:
        L[0] += f"   # {extra_comment}"
    if seconds is not None:
        L.append(f"    seconds: {seconds}")
    L.append("    set:")
    for k in ("vis", "boneGO", "lpEn", "srcAct", "gpAct", "gpW0", "gpW1"):
        if k == "srcAct" and pulse:
            continue
        if k in vals:
            L.append(f'      "{c[k]}": {vals[k]}')
    if remote is not None:
        w0, w1 = remote
        L.append(f'      "{w["cposW0"]}": {w0}')
        L.append(f'      "{w["cposW1"]}": {w1}')
        L.append(f'      "{w["crotW0"]}": {w0}')
        L.append(f'      "{w["crotW1"]}": {w1}')
    if pulse:
        keys = ", ".join(f"[{t}, {v}]" for t, v in RELEASE_PULSE)
        L.append("    curves:")
        L.append(f'      "{c["srcAct"]}": {{ tangents: stepped, keys: [ {keys} ] }}')
    return L


def own_document(mod, cfg, facts):
    bridge, terms = bridge_seconds(mod, cfg, facts)
    L = []
    L.append("# grab-sync composition chords — GENERATED by generate.py; edit the generator.")
    L.append("# The chord law (IsLocal chords never bind a Container weight; remote weight")
    L.append("# moves only at the bridge crossfade and the carried entry) is enforced by")
    L.append("# emission shape and asserted by --check. Grab-cell values are grab-prop's")
    L.append("# clip table mapped (vanilla Container -> LocalPose; --check pins the superset).")
    L.append("# Bridge timer, derived f(CONFIG) at 60 fps — exactness is not load-bearing, the swap glides:")
    for name, v in terms:
        L.append(f"#   {name}: {v:.3f}s")
    L.append(f"#   total: {bridge}s")
    L.append("")
    L.append("schema: 1")
    L.append("controller: GrabSync_Fx")
    L.append("basis: mount-root          # FullController on the GrabSync prefab root")
    L.append("role: fx")
    L.append("")
    L.append("defaults:")
    L.append("  writeDefaults: on")
    L.append("  transition: { duration: 0, exitTime: none, interruption: none }")
    L.append("")
    L.append("parameters:")
    L.append("  # The entry's published interface, read by name across the two FullControllers")
    L.append("  # (both list ObjectSync/* in globalParams). Declared float/scratch here: the")
    L.append("  # entry's params asset owns the VRC declaration, and float compares avoid a")
    L.append("  # merged-type mismatch on the If op (the entry declares Enable float).")
    L.append("  ObjectSync/Enable:      { type: float, scratch: true }")
    L.append("  ObjectSync/Ch/Acquired: { type: bool,  scratch: true }")
    L.append("  IsLocal:                bool     # VRC built-in (bool, matching the emulator's typing)")
    L.append("  GS/Engaged:             bool     # the visibility latch (spec §Visibility); driver-written")
    for i, p in enumerate(PROPS):
        L.append(f"  Grab{i}_IsGrabbed:       bool     # sensing — minted by {p}'s grab physbone (parameter: Grab{i}); never synced")
        L.append(f"  Placed{i}:               {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}")
    L.append("")
    L.append("layers:")

    # ---- engage latch -------------------------------------------------------
    L.append("  # The visibility latch: engages on Acquired DELAYED (the receiver certifies")
    L.append("  # one driver-frame ahead of the word copies the decode reads), releases only")
    L.append("  # on Enable-off — deliberately looser than the entry's consumer predicate, so")
    L.append("  # a cull resume holds the last-decoded pose instead of blinking the prop")
    L.append("  # (stated deviation; mirrors the entry's own Follow latch).")
    L.append("  - name: GS/Engage")
    L.append("    states:")
    L.append("      Disengaged:")
    L.append("        motion: ~")
    L.append("        behaviours: [ { driver: { set: { GS/Engaged: 0 } } } ]")
    L.append("        transitions:")
    L.append("          - { to: Delay, when: [ ObjectSync/Ch/Acquired is true, ObjectSync/Enable greater 0.5 ] }")
    L.append("      Delay:")
    L.append("        motion: { clip: engage_delay }")
    L.append("        transitions:")
    L.append("          - { to: Disengaged, when: [ ObjectSync/Enable less 0.5 ] }")
    L.append("          - { to: Engaged, when: [], exitTime: 1.0 }")
    L.append("      Engaged:")
    L.append("        motion: ~")
    L.append("        behaviours: [ { driver: { set: { GS/Engaged: 1 } } } ]")
    L.append("        transitions:")
    L.append("          - { to: Disengaged, when: [ ObjectSync/Enable less 0.5 ] }")
    L.append("    default: Disengaged")

    # ---- per-prop merged placement layer ------------------------------------
    for i, p in enumerate(PROPS):
        G, P = f"Grab{i}_IsGrabbed", f"Placed{i}"
        L.append(f"  # {p}: the merged level-predicated placement layer. Every state is entered")
        L.append("  # on LEVELS of current values (a late joiner reaches Placed with no edge);")
        L.append("  # the witnessed-release bridge is the sole edge-entered path and its miss")
        L.append("  # collapses to the level path after the timer.")
        L.append(f"  - name: GS/{p}")
        L.append("    states:")
        # local branch
        L.append("      LocalDisabled:   # off-is-reset: recall home, clear Placed (localOnly; value syncs)")
        L.append(f"        motion: {{ clip: {p}_local_disabled }}")
        L.append("        behaviours:")
        L.append(f"          - driver: {{ localOnly: true, set: {{ {P}: 0 }} }}")
        L.append(f"          - driver: {{ set: {{ {G}: 0 }} }}   # clears only because the bone GO is inactive in this chord")
        L.append("        transitions:")
        L.append("          - { to: LocalHome, when: [ ObjectSync/Enable greater 0.5 ] }")
        L.append("      LocalHome:")
        L.append(f"        motion: {{ clip: {p}_local_home }}")
        L.append("        behaviours:")
        L.append(f"          - driver: {{ localOnly: true, set: {{ {P}: 0 }} }}")
        L.append("        transitions:")
        L.append("          - { to: LocalDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: LocalGrabbed, when: [ {G} is true ] }}")
        L.append("      LocalGrabbed:")
        L.append(f"        motion: {{ clip: {p}_local_grabbed }}")
        L.append("        transitions:")
        L.append("          - { to: LocalDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: LocalReleased, when: [ {G} is false ] }}")
        L.append("      LocalReleased:   # the pulse; its length is the re-grab lockout (vanilla)")
        L.append(f"        motion: {{ clip: {p}_local_released }}")
        L.append("        behaviours:")
        L.append(f"          - driver: {{ localOnly: true, set: {{ {P}: 1 }} }}")
        L.append("        transitions:")
        L.append("          - { to: LocalPlaced, when: [], exitTime: 1.0 }")
        L.append("      LocalPlaced:")
        L.append(f"        motion: {{ clip: {p}_local_placed }}")
        L.append("        transitions:")
        L.append("          - { to: LocalDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: LocalGrabbed, when: [ {G} is true ] }}")
        # remote branch
        L.append("      RemoteWait:      # grab-prop's remote settle dwell, verbatim. The IsLocal escapes")
        L.append("                       # are LEVEL transitions, first in the ladder: entry rungs evaluate at")
        L.append("                       # playable frame 0, before the runtime has written IsLocal, so an")
        L.append("                       # entry-only IsLocal route strands the wearer in the remote branch")
        L.append("                       # (measured; vanilla grab-prop's Timer routes the same way).")
        L.append(f"        motion: {{ clip: {p}_remote_wait }}")
        L.append("        transitions:")
        L.append("          - { to: LocalDisabled, when: [ IsLocal is true, ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: LocalGrabbed, when: [ IsLocal is true, {G} is true ] }}")
        L.append(f"          - {{ to: LocalPlaced, when: [ IsLocal is true, {P} is true ] }}")
        L.append("          - { to: LocalHome, when: [ IsLocal is true ] }")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ], exitTime: 1.0 }}")
        L.append(f"          - {{ to: RemotePlaced, when: [ {P} is true, GS/Engaged is true ], exitTime: 1.0 }}")
        L.append("          - { to: RemoteHome, when: [ ObjectSync/Enable greater 0.5, GS/Engaged is true ], exitTime: 1.0 }")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ], exitTime: 1.0 }")
        L.append("          - { to: RemoteUncertified, when: [], exitTime: 1.0 }")
        L.append("      RemoteDisabled:  # Enable off: hidden, parked home, sensing cleared")
        L.append(f"        motion: {{ clip: {p}_remote_disabled }}")
        L.append("        behaviours:")
        L.append(f"          - driver: {{ set: {{ {G}: 0 }} }}")
        L.append("        transitions:")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ] }}")
        L.append("          - { to: RemoteHome, when: [ ObjectSync/Enable greater 0.5, GS/Engaged is true ] }")
        L.append("          - { to: RemoteUncertified, when: [ ObjectSync/Enable greater 0.5 ] }")
        L.append("      RemoteUncertified:  # Enable on but no certified table yet: hidden, parked")
        L.append(f"        motion: {{ clip: {p}_remote_hidden }}")
        L.append("        transitions:")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ] }}")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: RemotePlaced, when: [ {P} is true, GS/Engaged is true ] }}")
        L.append("          - { to: RemoteHome, when: [ GS/Engaged is true ] }")
        L.append("      RemoteHome:")
        L.append(f"        motion: {{ clip: {p}_remote_home }}")
        L.append("        transitions:")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ] }}")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: RemotePlaced, when: [ {P} is true ] }}")
        L.append("      RemoteGrabbed:   # the replicated grab replays the grab cell; display rides LocalPose")
        L.append(f"        motion: {{ clip: {p}_remote_grabbed }}")
        L.append("        transitions:")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: RemoteBridge, when: [ {G} is false ] }}")
        L.append("      RemoteBridge:    # witnessed release: replay the drop, wait out the pipeline,")
        L.append("                       # then CROSSFADE to the decoded truth (the transition duration)")
        L.append(f"        motion: {{ clip: {p}_remote_bridge }}")
        L.append("        transitions:")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ] }}")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: RemotePlaced, when: [ {P} is true, GS/Engaged is true ], exitTime: 1.0, duration: {CROSSFADE_SECONDS} }}")
        L.append("          - { to: RemoteHome, when: [ GS/Engaged is true ], exitTime: 1.0, duration: " + str(CROSSFADE_SECONDS) + " }")
        L.append("          - { to: RemoteUncertified, when: [], exitTime: 1.0 }")
        L.append("      RemotePlaced:    # display rides the reconstruction (level-entered: late join lands here)")
        L.append(f"        motion: {{ clip: {p}_remote_placed }}")
        L.append("        transitions:")
        L.append(f"          - {{ to: RemoteGrabbed, when: [ {G} is true ] }}   # the carried entry: word->drag swap, one frame")
        L.append("          - { to: RemoteDisabled, when: [ ObjectSync/Enable less 0.5 ] }")
        L.append(f"          - {{ to: RemoteHome, when: [ {P} is false ] }}")
        L.append("    entry:")
        L.append(f"      - {{ to: LocalDisabled, when: [ IsLocal is true, ObjectSync/Enable less 0.5 ] }}")
        L.append(f"      - {{ to: LocalGrabbed, when: [ IsLocal is true, {G} is true ] }}")
        L.append(f"      - {{ to: LocalPlaced, when: [ IsLocal is true, {P} is true ] }}")
        L.append("      - { to: LocalHome, when: [ IsLocal is true ] }")
        L.append("    default: RemoteWait")
        L.append("    layout:")
        L.append("      nodes:")
        L.append("        RemoteWait: [30, 180]")
        L.append("        LocalHome: [-450, 250]")
        L.append("        LocalDisabled: [-690, 250]")
        L.append("        LocalGrabbed: [-450, 340]")
        L.append("        LocalReleased: [-210, 340]")
        L.append("        LocalPlaced: [-210, 430]")
        L.append("        RemoteDisabled: [270, 250]")
        L.append("        RemoteUncertified: [510, 250]")
        L.append("        RemoteHome: [30, 320]")
        L.append("        RemoteGrabbed: [30, 410]")
        L.append("        RemoteBridge: [270, 410]")
        L.append("        RemotePlaced: [270, 500]")
        L.append("      entry: [50, 120]")
        L.append("      any:   [50, 40]")
        L.append("      exit:  [50, 80]")

    # ---- clips ----------------------------------------------------------------
    bridge_val, _ = bridge_seconds(mod, cfg, facts)
    L.append("")
    L.append("clips:")
    L.append(f"  engage_delay: {{ seconds: {ENGAGE_DELAY_SECONDS} }}")
    for i, p in enumerate(PROPS):
        # IsLocal chords: grab-prop's table mapped, NO Container weights (chord law).
        L.extend(clip_lines(f"{p}_local_home", p, CHOREO["anchored"], remote=None))
        L.extend(clip_lines(f"{p}_local_grabbed", p, CHOREO["grabbed"], remote=None))
        L.extend(clip_lines(f"{p}_local_released", p, CHOREO["released"], pulse=True, seconds=0.5, remote=None,
                            extra_comment="the pulse [EMPIRICAL: sample window [0.25,0.50)s — grab-prop's, verbatim]"))
        L.extend(clip_lines(f"{p}_local_placed", p, CHOREO["dropped"], remote=None))
        L.extend(clip_lines(f"{p}_local_disabled", p,
                            dict(vis=1, boneGO=0, lpEn=1, srcAct=1, gpAct=1, gpW0=1, gpW1=0), remote=None,
                            extra_comment="wearer stays visible (spec's visibility formula); bone dead, parked home"))
        # Remote chords: full set including Container weights.
        L.extend(clip_lines(f"{p}_remote_wait", p,
                            dict(vis=0, boneGO=1, lpEn=1, srcAct=1, gpAct=0, gpW0=1, gpW1=0),
                            seconds=REMOTE_DWELL_SECONDS, remote=(1, 0),
                            extra_comment="grab-prop's timer chord, hidden, weights parked on LocalPose"))
        L.extend(clip_lines(f"{p}_remote_disabled", p,
                            dict(vis=0, boneGO=0, lpEn=1, srcAct=1, gpAct=1, gpW0=1, gpW1=0), remote=(1, 0)))
        L.extend(clip_lines(f"{p}_remote_hidden", p,
                            dict(vis=0, boneGO=1, lpEn=1, srcAct=1, gpAct=1, gpW0=1, gpW1=0), remote=(1, 0)))
        L.extend(clip_lines(f"{p}_remote_home", p, dict(CHOREO["anchored"]), remote=(1, 0)))
        L.extend(clip_lines(f"{p}_remote_grabbed", p, dict(CHOREO["grabbed"]), remote=(1, 0)))
        L.extend(clip_lines(f"{p}_remote_bridge", p, dict(CHOREO["released"]), pulse=True,
                            seconds=bridge_val, remote=(1, 0),
                            extra_comment="released replay + dwell; length = the derived bridge (header)"))
        L.extend(clip_lines(f"{p}_remote_placed", p, dict(CHOREO["dropped"]), remote=(0, 1)))
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ checks ----

def parse_clips(yaml_text):
    """Minimal reader of a schema document's clips: block — name -> {binding: value},
    plus curves as name -> {binding: [(t,v)...]}. Enough for the superset assert."""
    clips, cur, curves_mode = {}, None, False
    in_clips = False
    for ln in yaml_text.splitlines():
        if ln.startswith("clips:"):
            in_clips = True
            continue
        if in_clips and ln and not ln.startswith((" ", "#", "\t")):
            in_clips = False
        if not in_clips or not ln.strip() or ln.strip().startswith("#"):
            continue
        m = _re.match(r"^  (\w+):", ln)
        if m:
            cur = m.group(1)
            clips[cur] = {"set": {}, "curves": {}}
            curves_mode = False
            inline = _re.search(r"\{ set: \{ (.+): ([^}]+) \} \}", ln)
            if inline:
                clips[cur]["set"][inline.group(1).strip().strip('"')] = inline.group(2).strip()
            continue
        if cur is None:
            continue
        if _re.match(r"^    curves:", ln):
            curves_mode = True
            continue
        if _re.match(r"^    set:", ln):
            curves_mode = False
            continue
        m = _re.match(r'^      "([^"]+)":\s*(.+)$', ln)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if curves_mode:
                keys = _re.findall(r"\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]", val)
                clips[cur]["curves"][key] = [(float(a), float(b)) for a, b in keys[1:] or keys]
                # note: first [t,v] pair list may include the tangents wrapper's keys only
                clips[cur]["curves"][key] = [(float(a), float(b)) for a, b in keys]
            else:
                clips[cur]["set"][key] = val
    return clips


def map_vanilla_binding(b, p):
    """grab-prop path -> composition path (the two renames + prefixes)."""
    if b.startswith("Container/GameObject."):
        return f"{p}/Container/GameObject." + b.split(".", 1)[1]
    if b.startswith("Container/"):
        return f"{p}/LocalPose/" + b.split("/", 1)[1]
    return f"{p}/GrabRig/" + b


VANILLA_TO_LOCAL = {"anchored": "local_home", "grabbed": "local_grabbed",
                    "released": "local_released", "dropped": "local_placed"}


def main():
    mod = entry_module()
    cfg = carried_config(mod)
    carried_text, f = mod.document(cfg)
    facts = f["facts"]
    own_text = own_document(mod, cfg, facts)

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        assert_(mod.document(cfg)[0] == carried_text, "carried document regenerates byte-identical")
        assert_(own_document(mod, cfg, facts) == own_text, "own document regenerates byte-identical")

        if len(PROPS) == 1:
            entry_y = open(os.path.join(REPO, "object-sync", "y", "controller.yaml"), encoding="utf-8").read()
            assert_(carried_text == entry_y,
                    "at one prop the carried build IS the entry's committed y/ document, byte-identical")

        # the mapped binding-superset: grab-prop's four choreography clips
        vanilla = parse_clips(open(GRABPROP_YAML, encoding="utf-8").read())
        ours = parse_clips(own_text)
        for i, p in enumerate(PROPS):
            for vclip, lsuffix in VANILLA_TO_LOCAL.items():
                oclip = f"{p}_{lsuffix}"
                missing = []
                for b, v in vanilla[vclip]["set"].items():
                    mb = map_vanilla_binding(b, p)
                    if ours.get(oclip, {}).get("set", {}).get(mb) != v:
                        missing.append(f"{b} -> {mb} (want {v}, have {ours.get(oclip, {}).get('set', {}).get(mb)})")
                for b, keys in vanilla[vclip]["curves"].items():
                    mb = map_vanilla_binding(b, p)
                    if ours.get(oclip, {}).get("curves", {}).get(mb) != keys:
                        missing.append(f"curve {b} -> {mb}")
                assert_(not missing, f"{oclip} is a binding-superset of grab-prop's `{vclip}` — missing: {missing}")

        # the chord law: no Container weight binding in any IsLocal chord
        for i, p in enumerate(PROPS):
            wkeys = set(weights(p).values())
            offenders = []
            for cname, c in ours.items():
                if not cname.startswith(f"{p}_local_"):
                    continue
                for b in list(c["set"]) + list(c["curves"]):
                    if b in wkeys:
                        offenders.append(f"{cname}: {b}")
            assert_(not offenders, f"no Container weight key in any {p} IsLocal chord — offenders: {offenders}")

        # every remote chord binds the full Container weight quartet (WD-independence
        # of the remote display path)
        for i, p in enumerate(PROPS):
            wkeys = set(weights(p).values())
            bad = []
            for cname, c in ours.items():
                if not cname.startswith(f"{p}_remote_"):
                    continue
                if not wkeys.issubset(set(c["set"])):
                    bad.append(cname)
            assert_(not bad, f"every {p} remote chord binds all four Container weights — missing in: {bad}")

        print(f"  bridge: {bridge_seconds(mod, cfg, facts)[0]}s; crossfade: {CROSSFADE_SECONDS}s; "
              f"wire {facts['wireBits']} bits / {facts['batchCount']} batches")
        print(f"  globalParams for BOTH FullControllers (the entry's own discipline): ['ObjectSync/*']")
        print("scope: emit determinism, the carried-document pin, the mapped chord superset and")
        print("  the chord law only — prefab wiring asserts land with the prefab (see --check-prefab");
        print("  section below when present); runtime behavior is the play session's, never this check's")
        sys.exit(0 if ok else 1)

    os.makedirs(os.path.dirname(OUT_CARRIED), exist_ok=True)
    with open(OUT_CARRIED, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(carried_text)
    with open(OUT_OWN, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(own_text)
    bridge_val, terms = bridge_seconds(mod, cfg, facts)
    print(f"wrote object-sync/controller.yaml: {len(f['layers'])} layers, wire {facts['wireBits']} bits, "
          f"{facts['batchCount']} batches, ~{facts['cycleSeconds']:.3f}s refresh")
    print(f"wrote controller.yaml: {len(PROPS)} prop(s), bridge {bridge_val}s "
          f"({' + '.join(f'{n}={v:.3f}' for n, v in terms)}), crossfade {CROSSFADE_SECONDS}s")
    print(f"synced-bit budget: wire {facts['wireBits']} + ObjectSync/Enable 1 + Placed x{len(PROPS)} "
          f"= {facts['wireBits'] + 1 + len(PROPS)} bits (read the compile line, never extend by delta)")


if __name__ == "__main__":
    main()
