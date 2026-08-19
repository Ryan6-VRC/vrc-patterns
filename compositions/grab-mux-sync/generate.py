#!/usr/bin/env python3
"""This composition's own `object-sync` build: the shipped entry's generator,
run over a 4-object y CONFIG, emitting beside this file instead of into the
entry.

    python compositions/grab-mux-sync/generate.py           # writes the document
    python compositions/grab-mux-sync/generate.py --check   # asserts, writes nothing

Output: `object-sync/controller.yaml` beside this file. Compile it with
`CompileController` into `built/` beside it; the composition's VRCFury
`FullController` points at that build, never at `../../object-sync/built/`.

WHY THE BUILD LIVES HERE AND NOT IN THE ENTRY
---------------------------------------------
`check()`'s `[committed vs disk]` block pins a `controller.yaml` on disk for
every label `committed_configs()` returns, so a 4-object preset would force a
fourth build, prefab and README claim into the public entry for a single
consumer. The composition drives the entry's generator from outside instead:
`object-sync/generate.py` is imported unmodified and the entry stays
byte-identical. `CONVENTIONS.md` §compositions/ is the rule this implements.

THE CONFIG
----------
Four `rotation: "y"` objects on the entry's default wire (2 number + 8 bool
slots) and a flat slice ring — the grab-mux regime deliberately spends nothing
on refresh rate, because the wire only ever carries rests: while a prop moves it
rides the natively-synced physbone grab on every client, and the words matter
only after release, where the composition's release timer (T_swap, README) is
derived from this build's full ring + wire loop rather than from a fast wire.
Flat slices for the same reason: no object is hot on the wire, ever — the
grabbed one is off-wire by construction. No post-generation deviation: `Enable`
keeps the entry's default-off, driven by the entry's own menu Toggle.
"""

import glob
import importlib.util
import os
import re as _re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")
OUT_FX = os.path.join(HERE, "controller.yaml")

OBJECTS = [{"name": "Prop0", "rotation": "y"},
           {"name": "Prop1", "rotation": "y"},
           {"name": "Prop2", "rotation": "y"},
           {"name": "Prop3", "rotation": "y"}]

# The remote release→swap delay, seconds. Derived, not guessed (operator-ruled):
# full measure ring (4 slices x 46 frames ≈ 3.07 s, the carried build's own
# header line) + full wire loop (16 batches ≈ 1.87 s at the measured ~0.117 s
# tick) + fine-stage re-lock after the carry-time speed-ceiling escape
# (fineEscapeFrames 30 + settle ≈ 0.7 s) + ~0.85 s buffer. Invisible in the
# normal case — the remote shows its own held drop point, centimetres-to-
# decimetres from the swap target, and the damper glides the residual.
T_SWAP = 6.5

# Damper mux weight against self-weight 1 — τ = 1/ln(1 + 0.1) ≈ 10.5 frames.
# Empirical and wear-test-owned. The damper's ONE job is hiding the snap from
# the IK-drop hold onto the synced rest (operator-ruled 2026-08-18): ONLY
# RestShown carries it — engaged by the Bridge→RestShown weight change on the
# witnessed path, where it also smooths per-wire-cycle word steps thereafter.
# Every other state rides rigid (1:0): Local/Carried/Bridge so a grab and its
# hold have nothing to fight, Home so a body-riding prop never jiggles, and
# the HIDDEN rest states (RestHidden/RestWait) deliberately — a cold joiner's
# damper snaps onto the synced spot while the container is off, so the first
# shown frame is already in place and nothing ever flies in from the origin
# (operator-ruled 2026-08-18; the settle dwell now guards decode stability,
# not damper convergence).
W_DAMP = 0.1
# The visibility settle dwell on the cold sync path. Two live jobs, neither of
# them damper convergence (the hidden rest states ride rigid and snap): it lets
# the decode land a coherent word application after `Acquired` certifies, and it
# absorbs the raw-vs-Floatify one-frame skew this composition accepts by reading
# `Ch/Acquired` raw (the entry's README §Who drives the prop owns that skew).
# Tuning it toward zero reopens the cold-join stale-word window, not a damper
# artifact.
T_SETTLE = 0.5
# The release clip's sample-and-hold pulse, verbatim from grab-prop: freeze at
# t=0 (constraint off), re-sample the settled tip over [0.25, 0.5) — low-FPS
# sample-delivery insurance, not settle time.
T_RELEASE = 0.5


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(
            f"REFUSE: the object-sync generator is not at {ENTRY} — this build "
            "is the entry's generator run over a different CONFIG and cannot "
            "emit a document without it.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def config(mod):
    cfg = dict(mod.CONFIG)
    cfg["objects"] = [dict(ob) for ob in OBJECTS]
    return cfg


def global_params(cfg):
    """The composition prefab's `globalParams` for the carried FullController —
    and for the composition's own FX FullController, which must carry the SAME
    list so the two controllers' shared names stay bare together.

    A scoped match grammar, not an enumeration (`../../../docs/gimmicks.md`
    §Packaging): `ObjectSync/*` keeps `Enable` and `Ch/Acquired` bare — the
    entry's published pair, which the composition's placement and visibility
    layers read by name — and survives an entry-side rename where an enumerated
    name would be dropped in silence. The exclusions withhold carried state from
    host capture: the wire slots cross the network (a captured one takes the
    host's `saved` across loads) and `Ch/Cycle` accumulates. Everything the
    composition itself mints — the four `Grab<N>`/`Grab<N>_IsGrabbed` pairs and
    the four `Placed<N>` bits — deliberately matches NOTHING here: both halves
    of each physbone pair take the instance prefix together (the base-field
    rewrite asymmetry, `gimmicks.md` §Packaging), and a prefixed synced param
    syncs by table index exactly as well as a bare one.

    `!{ch}/Wire/Idx*` is the one entry the demo's list does NOT carry: the
    demo exposes the index bools because its tablet's Counter readout walks
    them, and this composition has no consumer — they are the same
    host-capturable carried-state class as the word slots, so they take the
    instance prefix here (bake-confirmed 2026-08-18: bare without this entry,
    prefixed with it, sync cost identical either way)."""
    p, ch = cfg["prefix"], cfg["channel"]
    return [f"{p}/*", f"!{ch}/Cycle", f"!{ch}/Wire/Idx*",
            f"!{ch}/Wire/Num*", f"!{ch}/Wire/Bool*"]


def composition_document(cfg):
    """The composition's own FX — the per-prop grab-mux machinery, emitted
    rather than hand-repeated because the four props differ only in their path
    prefix and parameter index. Two layers per prop:

    RIG LAYER (`Rig<N>`) — the grab-prop replay, identical on every client, no
    IsLocal anywhere: chords the grab rig (GrabPosition root home/drop swap,
    SourcePosition sample-and-hold, GrabBone GO) and the measurement input
    (`Sync{Obj}_Target` weights: HomeAnchor/Offset vs Carry). `Released` is the
    only timed state and the only driver site that stamps `Placed<N>` (wearer,
    localOnly — the value syncs). `Disabled` is off-is-reset: grab branch dead,
    per-client `_IsGrabbed` clear (localOnly false — sensing is per-client),
    wearer `Placed` clear.

    PLACEMENT LAYER (`Place<N>`) — the display mux + damper + visibility, split
    by IsLocal as states (a tree reads 0 from IsLocal forever). Every state is
    predicate-entered from current values; `Bridge` is the SOLE edge-entered
    state (only from a witnessed `Carried`), with exits on every predicate so
    no reset can wedge it. The visibility latch is machine position itself:
    once `RestShown` engages, `Acquired` falling drops nothing — mirroring the
    entry's own Follow latch — and the witnessed release path enters `RestShown`
    directly, skipping the cold path's hide+settle dwell (a prop that was
    visibly carried must not blink while parking).

    All state motions are single chord clips writing the FULL per-prop binding
    set (WD ON: an unbound property would revert to the scene default), and no
    clip binds `Placed<N>` or `Grab<N>_IsGrabbed` — drivers own those, per the
    driver/clip ownership split."""
    o = []
    w = o.append
    w("# GENERATED by compositions/grab-mux-sync/generate.py — edit there, "
      "never here.")
    w("# Four grabbable props on one 4-object y object-sync: grab is the motion")
    w("# transport (natively synced, zero wire), the words carry rests only, and")
    w(f"# remotes swap to the reconstruction T_SWAP={T_SWAP}s after a witnessed")
    w("# release (see generate.py for the derivation). Paths are mount-root —")
    w("# the composition prefab root.")
    w("schema: 1")
    w("controller: GrabMux_Fx")
    w("basis: mount-root")
    w("role: fx")
    w("")
    w("defaults:")
    w("  writeDefaults: on")
    w("  transition: { duration: 0, exitTime: none, interruption: none }")
    w("")
    w("parameters:")
    w("  IsLocal: bool")
    w("  # The entry's published pair, read bare (both FullControllers carry the")
    w("  # same scoped globalParams). scratch: the entry's params asset owns")
    w("  # their declarations; ours would duplicate them. FLOAT, matching the")
    w("  # entry's animator type exactly: VRCFury's merge keeps the FIRST")
    w("  # declaration of a shared name and drops the second's type with no")
    w("  # warning (VFController._NewParam), so a bool here would survive or")
    w("  # die by FullController merge order — conditions below read the pair")
    w("  # with float compares for the same reason.")
    w("  ObjectSync/Enable: { type: float, scratch: true }")
    w("  ObjectSync/Ch/Acquired: { type: float, scratch: true }")
    for i, ob in enumerate(cfg["objects"]):
        w(f"  Grab{i}_IsGrabbed: bool        "
          f"# minted by {ob['name']}'s grab physbone (parameter: Grab{i})")
        w(f"  Placed{i}: {{ type: bool, vrc: {{ synced: true, saved: false }} }}"
          f"  # world-placed vs home; wearer-stamped, cleared by Enable-off")
    w("")
    w("layers:")
    for i, ob in enumerate(cfg["objects"]):
        obj = ob["name"]
        w(f"  # ---- {obj}: grab-prop replay (all clients) "
          "-------------------------------")
        w(f"  - name: Rig{i}")
        w("    states:")
        for st, chord in [("Home", f"rig{i}_home"), ("Grabbed", f"rig{i}_grab"),
                          ("Placed", f"rig{i}_placed")]:
            w(f"      {st}:")
            w(f"        motion: {{ clip: {chord} }}")
            if st == "Home":
                w("        transitions:")
                w(f"          - {{ to: Grabbed, when: [ Grab{i}_IsGrabbed is true ] }}")
                w(f"          - {{ to: Placed, when: [ Placed{i} is true ] }}")
            elif st == "Grabbed":
                w("        transitions:")
                w(f"          - {{ to: Released, when: [ Grab{i}_IsGrabbed is false ] }}")
            else:
                w("        transitions:")
                w(f"          - {{ to: Grabbed, when: [ Grab{i}_IsGrabbed is true ] }}")
                w(f"          - {{ to: Home, when: [ Placed{i} is false ] }}")
        w("      Released:")
        w(f"        motion: {{ clip: rig{i}_released }}")
        w("        behaviours:")
        w(f"          - driver: {{ localOnly: true, set: {{ Placed{i}: 1 }} }}")
        w("        transitions:")
        w(f"          - {{ to: Grabbed, when: [ Grab{i}_IsGrabbed is true ] }}")
        w("          - { to: Placed, when: [], exitTime: 1.0 }")
        w("      Disabled:")
        w(f"        motion: {{ clip: rig{i}_off }}")
        w("        behaviours:")
        w(f"          - driver: {{ localOnly: false, set: {{ Grab{i}_IsGrabbed: 0 }} }}")
        w(f"          - driver: {{ localOnly: true, set: {{ Placed{i}: 0 }} }}")
        w("        transitions:")
        w("          - { to: Home, when: [ ObjectSync/Enable greater 0.5 ] }")
        w("    any:")
        w("      - { to: Disabled, when: [ ObjectSync/Enable less 0.5 ], "
          "canTransitionToSelf: false }")
        w("    entry:")
        w(f"      - {{ to: Grabbed, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"      - {{ to: Placed, when: [ Placed{i} is true ] }}")
        w("    default: Home")
        # Layout follows the private doll rig's grammar (read off its
        # controller, 2026-08-18): default state under entry on the center
        # column, the grab family in the LEFT lane with release below the
        # grab, placement converging back to center, AnyState-entered parks
        # outboard right. The Place layer below shares the same columns.
        w("    layout:")
        w("      nodes: { Home: [30, 180], Grabbed: [-210, 180], "
          "Released: [-210, 260], Placed: [30, 260], Disabled: [270, 60] }")
        w("      entry: [50, 120]")
        w("      any: [50, 40]")
        w("      exit: [50, 80]")
        w(f"  # ---- {obj}: display mux + damper + visibility "
          "-------------------------")
        w(f"  - name: Place{i}")
        w("    states:")
        w("      Local:")
        w(f"        motion: {{ clip: pl{i}_local }}")
        w("      Carried:")
        w(f"        motion: {{ clip: pl{i}_carried }}")
        w("        transitions:")
        w(f"          - {{ to: Bridge, when: [ Grab{i}_IsGrabbed is false ] }}")
        w("      Bridge:")
        w(f"        motion: {{ clip: pl{i}_bridge }}")
        w("        transitions:")
        w(f"          - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: RestShown, when: [ Placed{i} is true ], "
          "exitTime: 1.0 }")
        w(f"          - {{ to: Home, when: [ Placed{i} is false ], "
          "exitTime: 1.0 }")
        w("      RestHidden:")
        w(f"        motion: {{ clip: pl{i}_rest_hidden }}")
        w("        transitions:")
        w(f"          - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: Home, when: [ Placed{i} is false ] }}")
        w("          - { to: RestWait, when: [ ObjectSync/Ch/Acquired greater 0.5 ] }")
        w("      RestWait:")
        w(f"        motion: {{ clip: pl{i}_rest_wait }}")
        w("        transitions:")
        w(f"          - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: Home, when: [ Placed{i} is false ] }}")
        w("          - { to: RestShown, when: [], exitTime: 1.0 }")
        w("      RestShown:")
        w(f"        motion: {{ clip: pl{i}_rest_shown }}")
        w("        transitions:")
        w(f"          - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: Home, when: [ Placed{i} is false ] }}")
        w("      Home:")
        w(f"        motion: {{ clip: pl{i}_home }}")
        w("        transitions:")
        w(f"          - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: RestHidden, when: [ Placed{i} is true ] }}")
        w("      Disabled:")
        w(f"        motion: {{ clip: pl{i}_off }}")
        w("        transitions:")
        w("          - { to: Local, when: [ ObjectSync/Enable greater 0.5, "
          "IsLocal is true ] }")
        w(f"          - {{ to: Carried, when: [ ObjectSync/Enable greater 0.5, "
          f"Grab{i}_IsGrabbed is true ] }}")
        w(f"          - {{ to: RestHidden, when: [ ObjectSync/Enable greater 0.5, "
          f"Placed{i} is true ] }}")
        w("          - { to: Home, when: [ ObjectSync/Enable greater 0.5 ] }")
        w("    any:")
        w("      - { to: Disabled, when: [ ObjectSync/Enable less 0.5 ], "
          "canTransitionToSelf: false }")
        w("    entry:")
        w("      - { to: Local, when: [ IsLocal is true ] }")
        w(f"      - {{ to: Carried, when: [ Grab{i}_IsGrabbed is true ] }}")
        w(f"      - {{ to: RestHidden, when: [ Placed{i} is true ] }}")
        w("    default: Home")
        # Same column semantics as Rig<N>: grab family left (Carried over
        # Bridge, mirroring Grabbed over Released), the cold sync path as the
        # mirrored RIGHT arm (RestHidden over RestWait), both arms converging
        # on RestShown at center-bottom; Local and Disabled are the two
        # entry/AnyState parks, outboard at the top.
        w("    layout:")
        w("      nodes: { Local: [-210, 60], Carried: [-210, 180], "
          "Bridge: [-210, 260], RestShown: [30, 260], RestHidden: [270, 180], "
          "RestWait: [270, 260], Home: [30, 180], Disabled: [270, 60] }")
        w("      entry: [50, 120]")
        w("      any: [50, 40]")
        w("      exit: [50, 80]")
    w("")
    w("clips:")
    for i, ob in enumerate(cfg["objects"]):
        obj = ob["name"]
        p = f"Prop{i}"
        st = f"ObjectSync4/Sync{obj}_Target/VRCParentConstraint.Sources"
        gp = f"{p}/GrabRig/GrabPosition/VRCPositionConstraint.Sources"
        sp = f"{p}/GrabRig/SourcePosition/VRCPositionConstraint.IsActive"
        gb = f"{p}/GrabRig/GrabPosition/GrabBone/GameObject.m_IsActive"
        mx = f"{p}/Mux/VRCParentConstraint.Sources"
        dm = f"{p}/Damped/VRCParentConstraint.Sources"
        ct = f"{p}/Damped/Container/GameObject.m_IsActive"

        dme = f"{p}/Damped/VRCParentConstraint.m_Enabled"

        # THE HOLD IS THE DISPLAY LEAF'S m_Enabled FREEZE FOR THE RELEASE
        # WINDOW — grab-prop's Container freeze, instanced on Damped. Frame-
        # measured (2026-08-18, test-output/g5-grabphase): in the release frame
        # the tip snaps to its rest and the sample cell follows it even with
        # IsActive already 0 — the poison propagates down every LIVE constraint
        # the same frame, and a mid-chain m_Enabled freeze (tried on Carry)
        # just freezes the poisoned value: whether a node chases or holds in
        # that frame is where the constraint CYCLE's stale edge falls, and the
        # one node measured holding the last good value is Damped, one frame
        # stale by that ordering. So Damped freezes for exactly the released
        # clip (protecting every client's view, the wearer's included), the
        # root re-anchors onto that frozen drop, the tip settles there, and
        # the SourcePosition pulse re-samples it clean — HEALING Carry and the
        # measurement within the clip, which is why Carry stays live and
        # Placed re-enables Damped onto an already-agreeing chain. The ~0.3 s
        # poisoned measurement window disappears under T_SWAP's full-ring wait.
        def rig(name, home_w, carry_w, root_home, root_drop, sample, bone):
            w(f"  {name}:")
            w("    set:")
            w(f"      {st}.source0.Weight: {home_w}")
            w(f"      {st}.source1.Weight: {carry_w}")
            w(f"      {gp}.source0.Weight: {root_home}")
            w(f"      {gp}.source1.Weight: {root_drop}")
            w(f"      {sp}: {sample}")
            w(f"      {gb}: {bone}")
            w(f"      {dme}: 1")

        rig(f"rig{i}_home", 1, 0, 1, 0, 1, 1)
        rig(f"rig{i}_grab", 0, 1, 1, 0, 1, 1)
        rig(f"rig{i}_placed", 0, 1, 0, 1, 0, 1)
        rig(f"rig{i}_off", 1, 0, 1, 0, 1, 0)
        # The release clip: Damped freezes for the whole clip (the hold), the
        # root re-anchors onto the frozen drop via the [0,1] swap, and the
        # SourcePosition pulse re-samples the settled tip over [0.25, 0.5) —
        # the heal, and the re-grab pickup, in one mechanism.
        w(f"  rig{i}_released:")
        w(f"    seconds: {T_RELEASE}")
        w("    set:")
        w(f"      {st}.source0.Weight: 0")
        w(f"      {st}.source1.Weight: 1")
        w(f"      {gp}.source0.Weight: 0")
        w(f"      {gp}.source1.Weight: 1")
        w(f"      {gb}: 1")
        w(f"      {dme}: 0")
        w("    curves:")
        w(f"      {sp}: {{ tangents: stepped, "
          "keys: [ [0, 0], [0.25, 1], [0.5, 0] ] }")

        # The damper pair is explicit — RIGID = (1, 0), DAMPED = (W_DAMP, 1) —
        # because deriving self-weight from the mux weight made W_DAMP = 1
        # silently emit rigid everywhere while every doc still claimed a damper.
        RIGID, DAMPED = (1, 0), (W_DAMP, 1)

        def place(name, sync_w, carry_w, home_w, damp, vis, seconds=None):
            w(f"  {name}:")
            if seconds is not None:
                w(f"    seconds: {seconds}")
            w("    set:")
            w(f"      {mx}.source0.Weight: {sync_w}")
            w(f"      {mx}.source1.Weight: {carry_w}")
            w(f"      {mx}.source2.Weight: {home_w}")
            w(f"      {dm}.source0.Weight: {damp[0]}")
            w(f"      {dm}.source1.Weight: {damp[1]}")
            w(f"      {ct}: {vis}")

        place(f"pl{i}_local", 1, 0, 0, RIGID, 1)
        place(f"pl{i}_carried", 0, 1, 0, RIGID, 1)
        place(f"pl{i}_bridge", 0, 1, 0, RIGID, 1, seconds=T_SWAP)
        place(f"pl{i}_rest_hidden", 1, 0, 0, RIGID, 0)
        place(f"pl{i}_rest_wait", 1, 0, 0, RIGID, 0, seconds=T_SETTLE)
        place(f"pl{i}_rest_shown", 1, 0, 0, DAMPED, 1)
        place(f"pl{i}_home", 0, 0, 1, RIGID, 1)
        place(f"pl{i}_off", 0, 0, 1, RIGID, 0)
    return "\n".join(o) + "\n"


def main():
    mod = entry_module()
    cfg = config(mod)
    text, f = mod.document(cfg)
    facts = f["facts"]

    if facts["batchCount"] != 16 or facts["wireBits"] != 29:
        raise SystemExit(
            f"REFUSE: this build emits {facts['batchCount']} batches / "
            f"{facts['wireBits']} wire bits, but the settled configuration is "
            "16 / 29 (THE CONFIG above) — and the composition's T_swap timer is "
            "derived from those numbers, so a shape change here re-derives "
            "T_swap in the composition controller before it is accepted.")

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        assert_(mod.document(cfg)[0] == text, "regeneration is byte-identical")
        assert_(f"  {cfg['prefix']}/Enable: {{ type: float, default: 0, " in text,
                "Enable keeps the entry's default-off (no deviation)")
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8", newline="") as fh:
                assert_(fh.read().replace("\r\n", "\n") == text,
                        "carried controller.yaml on disk matches this config")
        else:
            assert_(False, f"carried controller.yaml is missing ({OUT})")
        fx = composition_document(cfg)
        assert_(composition_document(config(mod)) == fx,
                "FX regeneration from a fresh config is byte-identical")
        if os.path.exists(OUT_FX):
            with open(OUT_FX, encoding="utf-8", newline="") as fh:
                assert_(fh.read().replace("\r\n", "\n") == fx,
                        "FX controller.yaml on disk matches this generator")
        else:
            assert_(False, f"FX controller.yaml is missing ({OUT_FX})")
        # The FX reads the entry's pair by their BARE names AND at the entry's
        # exact animator type: VRCFury's merge keeps the first declaration of a
        # shared name and silently drops the second's type, so a type drift
        # between the two documents becomes a merge-order lottery. Pin the
        # entry's full declarations, not just the names.
        for decl in (
            f"  {cfg['prefix']}/Enable: {{ type: float, default: 0, "
            "vrc: { type: bool, synced: true, saved: false } }",
            f"  {cfg['channel']}/Acquired: {{ type: float, default: 0, "
            "vrc: { type: bool, synced: false, saved: false } }",
        ):
            assert_(decl in text,
                    f"entry document still declares `{decl.strip()}` — the FX "
                    "declares the same name as float and reads it with float "
                    "compares; a drift here re-opens the merge-order type "
                    "collision")
        assert_(": { type: float, scratch: true }" in fx
                and "ObjectSync/Enable: { type: bool" not in fx,
                "FX declares the shared pair as float scratch")
        # T_SWAP must cover what a remote actually waits for: full measure ring
        # (from the emitted header) + full wire loop (facts) + fine re-lock +
        # a real buffer. A CONFIG or word-channel tick change that stretches
        # either term past the hard-coded delay fails here instead of shipping
        # a remote that swaps onto a stale word.
        ring_m = _re.search(r"# Local measure cycle: (\d+) slices x (\d+) "
                            r"frames", text)
        assert_(ring_m is not None, "emitted document carries the ring header")
        if ring_m:
            ring = int(ring_m.group(1)) * int(ring_m.group(2)) / 60.0
            need = ring + facts["cycleSeconds"] + 0.7 + 0.5
            assert_(T_SWAP >= need,
                    f"T_SWAP {T_SWAP}s covers ring {ring:.2f} + wire "
                    f"{facts['cycleSeconds']:.2f} + relock 0.7 + buffer 0.5 "
                    f"= {need:.2f}s")
        want_gp = global_params(cfg)
        print("  globalParams for the composition prefab (BOTH FullControllers):")
        for n in want_gp:
            print(f"    {n}")
        # A stale `!` exclusion silently WIDENS the list (zero matches = the
        # wire slots handed to the first host that declares them), the opposite
        # failure to a stale enumeration — same assert as the demo's.
        for entry in [e for e in want_gp if e.startswith("!")]:
            stem = entry[1:].rstrip("*")
            assert_(stem in text,
                    f"exclusion `{entry}` still names a declared param "
                    f"(stem `{stem}` appears in the emitted document)")
        # The prefab is the hand-edited half — a wrong globalParams entry lands
        # silently (VRCFury exposes nothing and says nothing) and no compile or
        # gate reads the field, so pin both FullController blocks here (the
        # demo's generator carries the same assert for the same reason).
        pf_path = os.path.join(HERE, "GrabMuxSync.prefab")
        if os.path.exists(pf_path):
            body = open(pf_path, encoding="utf-8").read()
            blocks, cur, inside = [], [], False
            for ln in body.splitlines():
                if ln.strip() == "globalParams:":
                    inside, cur = True, []
                elif inside:
                    if ln.lstrip().startswith("- "):
                        # Unity writes each `!` entry single-quoted (YAML tag
                        # indicator) — strip the quotes, keep the `!`.
                        cur.append(ln.split("- ", 1)[1].strip().strip("'\""))
                    else:
                        blocks.append(cur)
                        inside = False
            if inside:
                blocks.append(cur)
            entry_blocks = [b for b in blocks
                            if any(e.lstrip("!").startswith(f"{cfg['prefix']}/")
                                   for e in b)]
            assert_(len(entry_blocks) == 2
                    and all(b == want_gp for b in entry_blocks),
                    f"both FullController globalParams blocks are exactly the "
                    f"{len(want_gp)} entries above, in order "
                    f"({[b for b in entry_blocks if b != want_gp][:1]})")
            # Both world pins (composition root + the carried rig's own) source
            # never-instantiated World.prefab assets; a broken reference there
            # resolves to null and the rig silently rides the avatar instead of
            # the world, reading correct at the origin — same assert, same
            # resolve-by-GUID method as the demo's.
            world = {}
            for meta in glob.glob(os.path.join(REPO, "*", "assets",
                                               "World.prefab.meta")):
                asset = meta[:-len(".meta")]
                with open(meta, encoding="utf-8") as mfh:
                    g = _re.search(r"^guid: ([0-9a-f]{32})$", mfh.read(), _re.M)
                if g and os.path.exists(asset):
                    with open(asset, encoding="utf-8") as afh:
                        world[g.group(1)] = set(
                            _re.findall(r"^--- !u!4 &(-?\d+)$", afh.read(),
                                        _re.M))
            refs = _re.findall(
                r"SourceTransform: \{fileID: (-?\d+), guid: ([0-9a-f]{32})",
                body)
            dangling = [r for r in refs
                        if r[1] not in world or r[0] not in world[r[1]]]
            # Exactly 4: parent + scale on the composition root, parent + scale
            # on the carried Rig. A deleted pin removes its refs and the rest
            # would still satisfy a bare "all resolve" — count it.
            assert_(len(refs) == 4 and not dangling,
                    f"exactly 4 cross-asset pin sources (root pair + Rig "
                    f"pair), all resolving to a composed entry's World.prefab "
                    f"— found {len(refs)}, dangling {sorted(set(dangling))}")
            # The consumer seam the entry deliberately ships empty: each
            # Sync{Obj}_Target must carry OUR two sources (Offset, Carry), or
            # every Sync-mediated path collapses to the world origin with the
            # state machines reading healthy — shipped exactly once before this
            # assert existed. The entry cannot hold this (its prefab is not
            # ours); this one is.
            # Consumer constraint sources by IDENTITY AND ORDER, not count —
            # the clips address sources by index, so a transposed pair reads
            # (2,2)-healthy while every chord measures the wrong node; the
            # origin defect this pass was written for shipped exactly that
            # shaped. Resolves each SourceTransform to its GameObject name via
            # the same document maps throughout; a stripped or nameless doc is
            # skipped, never crashed on, so a parse surprise reports FAIL
            # instead of a traceback.
            docs = {}
            for block in body.split("--- !u!"):
                m = _re.match(r"\d+ &(-?\d+)", block)
                if m:
                    docs[m.group(1)] = block
            go_of, name_of = {}, {}
            for fid, block in docs.items():
                if _re.search(r"^GameObject:", block, _re.M):
                    nm = _re.search(r"^  m_Name: (.*)$", block, _re.M)
                    if nm:
                        name_of[fid] = nm.group(1)
            for fid, block in docs.items():
                g = _re.search(r"m_GameObject: \{fileID: (-?\d+)\}", block)
                if g:
                    go_of[fid] = g.group(1)

            def source_names(block):
                n = _re.search(r"totalLength: (\d+)", block)
                if not n:
                    return None
                hits = list(_re.finditer(
                    r"SourceTransform: \{fileID: (-?\d+)"
                    r"(?:, guid: [0-9a-f]{32})?", block))[:int(n.group(1))]
                return [name_of.get(go_of.get(sm.group(1), ""),
                                    f"?{sm.group(1)}") for sm in hits]

            want_by_name = {}
            for i, ob in enumerate(cfg["objects"]):
                want_by_name[f"Sync{ob['name']}_Target"] = ["Offset", "Carry"]
            found, mux_syncs, bad = {}, [], {}
            for fid, block in docs.items():
                if not _re.search(r"^MonoBehaviour:", block, _re.M) \
                        or "totalLength" not in block:
                    continue
                nm = name_of.get(go_of.get(fid, ""), "")
                names = source_names(block)
                if names is None:
                    continue
                if nm in want_by_name:
                    found[nm] = names
                    if names != want_by_name[nm]:
                        bad[nm] = names
                elif nm == "Mux":
                    found[f"Mux#{fid}"] = names
                    if (len(names) != 3 or names[1:] != ["Carry", "Offset"]
                            or not names[0].startswith("Sync")):
                        bad[f"Mux#{fid}"] = names
                    else:
                        mux_syncs.append(names[0])
                elif nm == "Damped":
                    found[f"Damped#{fid}"] = names
                    if names != ["Mux", "Damped"]:
                        bad[f"Damped#{fid}"] = names
            n_obj = len(cfg["objects"])
            want_syncs = sorted(f"Sync{ob['name']}" for ob in cfg["objects"])
            counts = (len([k for k in found if k in want_by_name]),
                      len([k for k in found if k.startswith("Mux#")]),
                      len([k for k in found if k.startswith("Damped#")]))
            assert_(counts == (n_obj, n_obj, n_obj) and not bad
                    and sorted(mux_syncs) == want_syncs,
                    f"consumer sources by name+order: {n_obj}x Sync_Target "
                    f"[Offset, Carry], {n_obj}x Mux [Sync<obj>, Carry, Offset] "
                    f"(each object once), {n_obj}x Damped [Mux, self] — found "
                    f"{counts}, bad: {bad}, mux targets: {sorted(mux_syncs)}")
        else:
            assert_(False, f"GrabMuxSync.prefab is missing ({pf_path})")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload "
              f"/ {facts['batchCount']} batches / ~{facts['cycleSeconds']:.3f}s "
              f"refresh; surface pairs: "
              + ", ".join(f"Sync{ob['name']}" for ob in cfg["objects"]))
        sys.exit(0 if ok else 1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(f['layers'])} layers, "
          f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
          f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
          f"~{facts['cycleSeconds']:.3f}s refresh @60fps")
    fx = composition_document(cfg)
    with open(OUT_FX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fx)
    n = len(cfg["objects"])
    print(f"wrote {os.path.relpath(OUT_FX, HERE)}: {2 * n} layers "
          f"({n} props x rig+placement), T_SWAP {T_SWAP}s, damper {W_DAMP}:1")


if __name__ == "__main__":
    main()
