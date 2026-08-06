#!/usr/bin/env python3
"""sync-probe generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ — controller.yaml is
generated output and never hand-edited. The probe measures the shipping client's
actual synced-parameter delivery schedule at a receiver, with no OSC monitoring
of a remote client: each wearer's REMOTE copy relays what it received onto
world-anchored contacts, and the observing client's own (local) receivers mirror
those into declared unsynced params its OSC surface serves. Two clients each
wearing one copy measure each other symmetrically.

Sender side (IsLocal), all synced params unsaved:
- Four rate-ladder rungs, each an 8-bit counter (synced Int) advancing on its
  own cadence via word-channel's Send/Extra idiom (exit-time dwell + one
  conditional-hop frame — the VRCFury guard against Unity's early exit-time
  quirk outrunning the sync tick). The 0.1s BARE rung alone omits the hop —
  a pure exit-time flip-flop, the experimental deviation that tests whether
  the guard matters in the shipping client. Counters wrap through an explicit
  Wrap state (a driver Add clips a synced Int at 255, so add-and-clip cannot
  wrap; the wrap publishes 0 and re-seeds the local float counter).
- Torn-snapshot pair: TornA + TornB written in ONE driver each tick with
  B = 255 - A, from two complementary local counters (one climbs, one
  descends; a convertRange inversion was measured off by one — 205 -> 49 —
  the float remap truncates on the Int copy), testing whether params changed
  in one tick really replicate as a coherent snapshot.
- FpsBand: a threshold ladder over the owned frametime rig (lifted from
  vrc-patterns/blendtree-math) driver-Sets a band index an OSC logger can
  read — the observing client's own frame clock rides its own avatar.

Receiver/relay side (remote copy of the OTHER player, running on the observing
client), relaying over contacts because OSC only ever serves the worn copy's
own tree:
- MirrorPump driver-copies the wire Ints to floats every frame (a blend tree
  reads an Int as 0).
- Relay layer: ONE Direct tree drives each relay sender's world position as
  pos.z = rest + value*step — ANALOG position encoding, one contact channel
  per byte, read by a face-mode box receiver (linear unlerp, float32-exact
  per object-sync's measured fine stage; 255 steps over 5.1 m is 22x coarser
  than what that stage reads exactly). Same-frame coherent by construction:
  a per-bit binary decode was rejected because every AAP hop costs one frame
  (docs/gimmicks.md), so an 8-stage bit cascade settles incoherently over
  ~15 frames — longer than the 6-frame delivery interval it must relay.
- Stride tallies: per rung, Delta = Cur - Prev (one Direct subtree), bucketed
  1/2/3/4+/big-jump by a transition ladder with the mod-256 wrap ranges as
  explicit OR rungs; a driver Adds the bucket tally (floats: unsynced, never
  clipped) and re-stages Prev. Valid only while delivery interval clears the
  ~5-frame classification pipeline — the 0.05s rung's tally is advisory, its
  truth is the live relay stream (README).
- Torn tally: Sum = TnA + TnB; a mismatch persisting >= tornPersistFrames
  counts once (a real torn tick persists ~a full tick; a render-frame
  boundary does not).
- Scan bus: a register cycler round-robins the tallies onto three analog
  lines (value = tally/10, select index, strobe) as the post-hoc cross-check
  on the live streams; the strobe flips as each register latches (a
  deliberate swap from the plan's parity bit — an XOR chain of tree stages
  costs more than the read-validity it buys), and a SweepMark sentinel
  register keeps the count even so the strobe has an edge at the sweep wrap.
- MirrorGate: a mirror clone runs clip layers from Entry at its own phase
  but executes no drivers (docs/runtime.md #Parameters), so ungated it
  would broadcast garbage on the live relay tags; a driver-set Alive bool
  (mirror-detect's race) holds the whole Rig inactive on mirror clones.
- Heartbeat: a two-state flip-flop of complementary GO-active clips (local
  time, zero network dependence) — exactly one of two Constant senders
  active at any instant. Classifies every anomaly: heartbeat clean +
  counters skipping = sync loss; both frozen valid = animator pause; both
  zero = relay collapse; erratic = contact trouble, discard the interval.
- Reset: one synced bool (menu TOGGLE on the wearer, held ~2s: a set->clear
  pair under ~0.2s is never seen remotely, docs/runtime.md); a localOnly:false
  driver clears tallies on every client and re-stages Prev from Cur so the
  first post-reset delivery does not count as a big-jump.

The rig (hand-maintained prefab, README §Rig): senders localOnly:false so
remote copies carry them; receivers localOnly:true, allowSelf:false,
allowOthers:true, so each client's receivers read only the other player's
relay and stay off everyone else's solve. All world-anchored via a
VRCParentConstraint onto a never-instantiated World.prefab source, park on
the SOURCE-space per-source offset (world-fixed on every client). Receiver
cells hold <= 8 receivers (the ~24-per-cell cross-player misread bug,
docs/runtime.md #Contacts) and the park stays within ~50 m of the world
origin (operator constraint: speculative world-bounds culling of contacts).

Driver-op ordering note: publish-then-increment rides two SEPARATE driver
behaviours (SMBs execute in list order — Unity contract); no driver op ever
reads a param the same driver wrote (RAW order within one driver is
unpinned here and deliberately never relied on).
"""

import os

CONFIG = {
    # Param prefix. The FullController's globalParams exposes the OSC surface
    # (wire counters, Rx mirrors, FpsBand, Reset); scratch takes VF prefixes.
    "channel": "SyncProbe",
    # The rate ladder. `guardHop` False = the bare rung (no +1-frame hop).
    # 0.15s was cut in planning: the decision boundary lies entirely between
    # 0.1 and 0.2 (docs/local/p12-plan.md).
    "rungs": [
        {"name": "R05",  "seconds": 0.05, "guardHop": True},
        {"name": "R10B", "seconds": 0.1,  "guardHop": False},
        {"name": "R10G", "seconds": 0.1,  "guardHop": True},
        {"name": "R20",  "seconds": 0.2,  "guardHop": True},
    ],
    "tornSeconds": 0.1,       # torn-pair write cadence (same as the shipped batch tick)
    "tornPersistFrames": 3,   # mismatch frames before a torn event counts
    "bigJump": 16,            # stride >= this buckets as big-jump (pause), not loss
    "scanDwellSeconds": 1.5,  # per-register dwell on the scan bus
    "heartbeatHalfSeconds": 0.5,  # half-period of the heartbeat flip-flop
    # Analog relay geometry — README §Rig carries the receiver-side halves.
    # pos.z = restOffset + value*step; 255*0.02 + 0.15 = 5.25 m, inside a
    # size-6 face receiver with >= 0.15 m guard at both ends (object-sync's
    # edge-guard rationale: 0 is then unambiguously "not acquired").
    "relayStep": 0.02,
    "relayRest": 0.15,
    "scanSelStep": 0.24,      # 22 registers: 0.15 + 21*0.24 = 5.19 m, inside the guard
    # FpsBand edges, seconds of frametime (ascending). Band k = between edge
    # k-1 and edge k; band 0 is below the first edge, band len(edges) above
    # the last. Chosen at common client rate plateaus: 85/66/52/37/27/17.5/
    # 12.5/9 fps.
    "fpsEdges": [0.011765, 0.015152, 0.019231, 0.027027,
                 0.037037, 0.057143, 0.08, 0.111111],
}

# Stride buckets: (label, positive (lo, hi), wrapped (lo, hi) or None).
# Wrapped ranges are the same strides seen across the 255->0 boundary:
# true stride s with Cur < Prev reads as Delta = s - 256.
BUCKETS = [
    ("S1",  (0.5, 1.5),   (-255.5, -254.5)),
    ("S2",  (1.5, 2.5),   (-254.5, -253.5)),
    ("S3",  (2.5, 3.5),   (-253.5, -252.5)),
    ("S4",  (3.5, 15.5),  (-252.5, -240.5)),
    ("Big", (15.5, 255.5), (-240.5, -0.5)),
]


def p(name):
    return f"{CONFIG['channel']}/{name}"


def emit():
    c = CONFIG
    ch = c["channel"]
    rungs = c["rungs"]
    step, rest = c["relayStep"], c["relayRest"]
    L = []
    o = L.append

    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o("# sync-probe: measures the shipping client's synced-param delivery schedule at a")
    o("# receiver. Sender half (IsLocal): a four-rung rate ladder of 8-bit counters")
    o("# (word-channel's Send/Extra cadence idiom; the R10B rung alone drops the +1-frame")
    o("# guard hop — the experimental deviation), a same-driver torn pair B = 255 - A, and")
    o("# an FpsBand ladder over an owned frametime rig. Receiver half (the remote copy on")
    o("# the observing client): wire Ints pumped to floats, relayed as ANALOG world")
    o("# positions (pos.z = rest + value*step — same-frame; a per-bit AAP cascade settles")
    o("# incoherently over ~15 frames, docs/gimmicks.md one-frame-per-hop), stride tallies")
    o("# bucketed 1/2/3/4+/big with mod-256 wrap rungs, a torn-persistence counter, a")
    o("# 21-register scan bus (value/select/strobe), a complementary GO-active heartbeat,")
    o("# and a Reset clear that re-stages Prev from Cur. generate.py's docstring carries")
    o("# the design; the README carries the rig, the calibration, and the declared limits.")
    o("")
    o("schema: 1")
    o(f"controller: {ch}_Fx")
    o("basis: mount-root          # every scene binding paths through the module's own Rig")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")

    # ---------------- parameters ----------------
    o("parameters:")
    o("  IsLocal: bool              # VRC built-in")
    o(f"  {p('True')}: {{ type: bool, default: true, scratch: true }}   # constant for +1-frame hops")
    o(f"  {p('One')}: {{ type: float, default: 1.0, scratch: true }}    # constant full-weight helper, never driven")
    o(f"  {p('Alive')}: {{ type: bool, scratch: true }}   # driver-set on every real copy; a mirror clone")
    o("                                                #   runs no drivers, so it stays false there (the")
    o("                                                #   mirror-detect race, vrc-patterns/mirror-detect)")
    o("  # Wire — the synced surface, 49 bits, all unsaved.")
    for r in rungs:
        guard = "guard hop" if r["guardHop"] else "BARE — no guard hop"
        o(f"  {p(r['name'])}: {{ type: int, vrc: {{ synced: true, saved: false }} }}   # {r['seconds']}s rung, {guard}")
    o(f"  {p('TornA')}: {{ type: int, vrc: {{ synced: true, saved: false }} }}   # torn pair: written same driver,")
    o(f"  {p('TornB')}: {{ type: int, vrc: {{ synced: true, saved: false }} }}   #   B = 255 - A always")
    o(f"  {p('Reset')}: {{ type: bool, vrc: {{ synced: true, saved: false }} }}  # menu button; clears tallies everywhere")
    o("  # OSC surface — declared unsynced (zero sync bits; OSC emission of undeclared")
    o("  # animator params is unreliable on the live client, docs/osc.md).")
    o(f"  {p('FpsBand')}: {{ type: int }}          # observing client's frame-rate band (README table)")
    for r in rungs:
        o(f"  {p('Rx/' + r['name'])}: float          # receiver mirror: other player's {r['name']} as delivered here")
    o(f"  {p('Rx/TornA')}: float")
    o(f"  {p('Rx/TornB')}: float")
    o(f"  {p('Rx/ScanVal')}: float")
    o(f"  {p('Rx/ScanSel')}: float")
    o(f"  {p('Rx/ScanStrobe')}: float")
    o(f"  {p('Rx/HbA')}: float")
    o(f"  {p('Rx/HbB')}: float")
    o(f"  {p('Rx/Prox')}: float          # proximity rider: cross-player analog fidelity + close-range distance")
    o("  # Sender scratch.")
    for r in rungs:
        o(f"  {p('Cnt/' + r['name'])}: {{ type: float, scratch: true }}")
    o(f"  {p('Cnt/Torn')}: {{ type: float, scratch: true }}")
    o(f"  {p('Cnt/TornB')}: {{ type: float, default: 255, scratch: true }}   # descending complement of Cnt/Torn")
    o("  # Frametime rig (lifted from vrc-patterns/blendtree-math).")
    o(f"  {p('Ft/Time')}: {{ type: float, aap: true, scratch: true }}")
    o(f"  {p('Ft/LastTime')}: {{ type: float, aap: true, scratch: true }}")
    o(f"  {p('Ft/FrameTime')}: {{ type: float, aap: true, scratch: true }}")
    o("  # Decode scratch (driver-pumped mirrors + AAP deltas).")
    for r in rungs:
        o(f"  {p('Dc/' + r['name'] + '/Cur')}: {{ type: float, scratch: true }}")
        o(f"  {p('Dc/' + r['name'] + '/Prev')}: {{ type: float, scratch: true }}")
        o(f"  {p('Dc/' + r['name'] + '/Delta')}: {{ type: float, aap: true, scratch: true }}")
    o(f"  {p('Dc/TnA')}: {{ type: float, scratch: true }}")
    o(f"  {p('Dc/TnB')}: {{ type: float, scratch: true }}")
    o(f"  {p('Dc/TornSum')}: {{ type: float, aap: true, scratch: true }}")
    o("  # Tallies (floats: a driver Add never clips an unsynced float).")
    for r in rungs:
        for b, _, _ in BUCKETS:
            o(f"  {p('Ty/' + r['name'] + '/' + b)}: {{ type: float, scratch: true }}")
    o(f"  {p('Ty/TornCount')}: {{ type: float, scratch: true }}")
    o("  # Scan bus scratch.")
    o(f"  {p('Sc/Val')}: {{ type: float, scratch: true }}")
    o(f"  {p('Sc/SelIdx')}: {{ type: float, scratch: true }}")
    o(f"  {p('Sc/Strobe')}: {{ type: float, scratch: true }}")
    o("")

    # ---------------- layers ----------------
    o("layers:")

    # --- rung senders ---
    for r in rungs:
        name, secs, hop = r["name"], r["seconds"], r["guardHop"]
        wire, cnt = p(name), p("Cnt/" + name)
        o(f"  # {name}: {secs}s cadence, {'Send/Extra guard hop' if hop else 'BARE exit-time flip-flop (no hop)'}.")
        o(f"  # Publish-then-increment as two driver behaviours (list-order execution);")
        o(f"  # Wrap publishes 0 by Set (a driver Add clips a synced Int at 255) and")
        o(f"  # re-seeds the counter at 1, so the wire walks ...254, 255, 0, 1...")
        o(f"  - name: {ch}/Rung/{name}")
        o("    states:")
        o("      Split:")
        o("        motion: ~")
        o("        transitions:")
        o("          - { to: Dead, when: [ IsLocal is false ] }")
        o(f"          - {{ to: {'Tick' if hop else 'TickA'}, when: [ IsLocal is true ] }}")
        o("      Dead:")
        o("        motion: ~")
        if hop:
            o("      Tick:")
            o("        motion: ~")
            o("        behaviours:")
            o(f"          - driver: {{ localOnly: true, copy: {{ {wire}: {cnt} }} }}")
            o(f"          - driver: {{ localOnly: true, add: {{ {cnt}: 1 }} }}")
            o("        transitions:")
            o(f"          - {{ to: Hop, when: [], exitTime: {secs} }}   # empty state: exitTime is literal seconds")
            o("      Hop:")
            o("        motion: ~")
            o("        transitions:")
            o(f"          - {{ to: Wrap, when: [ {cnt} greater 255.5 ] }}")
            o(f"          - {{ to: Tick, when: [ {p('True')} is true ] }}   # conditional hop = the guaranteed +1 frame")
            o("      Wrap:")
            o("        motion: ~")
            o("        behaviours:")
            o(f"          - driver: {{ localOnly: true, set: {{ {wire}: 0, {cnt}: 1 }} }}")
            o("        transitions:")
            o(f"          - {{ to: Hop, when: [], exitTime: {secs} }}   # the wrap IS a tick: 0 holds a full cadence")
            o("          # (a conditional hop straight back to Tick held 0 for one render frame,")
            o("          # under the ~0.1s tick, minting a phantom stride-2 every 256 ticks that")
            o("          # the bare rung does not have — exactly the guarded-vs-bare delta this")
            o("          # probe measures)")
            o("    default: Split")
            o("    layout:")
            o("      nodes:")
            o("        Split: [30, 180]")
            o("        Dead:  [270, 180]")
            o("        Tick:  [-210, 260]")
            o("        Hop:   [-450, 260]")
            o("        Wrap:  [-450, 350]")
        else:
            o("      # Pure exit-time chain — no conditional hop anywhere between ticks: the")
            o("      # wrap states are themselves ticks (they publish 0 by Set on schedule).")
            for a, b_ in (("A", "B"), ("B", "A")):
                o(f"      Tick{a}:")
                o("        motion: ~")
                o("        behaviours:")
                o(f"          - driver: {{ localOnly: true, copy: {{ {wire}: {cnt} }} }}")
                o(f"          - driver: {{ localOnly: true, add: {{ {cnt}: 1 }} }}")
                o("        transitions:")
                o(f"          - {{ to: Wrap{b_}, when: [ {cnt} greater 255.5 ], exitTime: {secs} }}")
                o(f"          - {{ to: Tick{b_}, when: [], exitTime: {secs} }}")
            for a, b_ in (("A", "B"), ("B", "A")):
                o(f"      Wrap{a}:")
                o("        motion: ~")
                o("        behaviours:")
                o(f"          - driver: {{ localOnly: true, set: {{ {wire}: 0, {cnt}: 1 }} }}")
                o("        transitions:")
                o(f"          - {{ to: Tick{b_}, when: [], exitTime: {secs} }}")
            o("    default: Split")
            o("    layout:")
            o("      nodes:")
            o("        Split: [30, 180]")
            o("        Dead:  [270, 180]")
            o("        TickA: [-210, 260]")
            o("        TickB: [-450, 260]")
            o("        WrapA: [-210, 350]")
            o("        WrapB: [-450, 350]")

    # --- torn writer ---
    ts = c["tornSeconds"]
    o(f"  # Torn pair: A and B = 255 - A written by ONE driver each {ts}s tick, from two")
    o("  # complementary counters (a convertRange inversion truncates on the Int copy —")
    o("  # measured 205 -> 49); both copies read their counters before the increment")
    o("  # behaviour runs, so the pair is exact and same-frame by construction.")
    o(f"  - name: {ch}/Torn")
    o("    states:")
    o("      Split:")
    o("        motion: ~")
    o("        transitions:")
    o("          - { to: Dead, when: [ IsLocal is false ] }")
    o("          - { to: Tick, when: [ IsLocal is true ] }")
    o("      Dead:")
    o("        motion: ~")
    o("      Tick:")
    o("        motion: ~")
    o("        behaviours:")
    o(f"          - driver:")
    o("              localOnly: true")
    o("              copy:")
    o(f"                {p('TornA')}: {p('Cnt/Torn')}")
    o(f"                {p('TornB')}: {p('Cnt/TornB')}")
    o(f"          - driver: {{ localOnly: true, add: {{ {p('Cnt/Torn')}: 1, {p('Cnt/TornB')}: -1 }} }}")
    o("        transitions:")
    o(f"          - {{ to: Hop, when: [], exitTime: {ts} }}")
    o("      Hop:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Wrap, when: [ {p('Cnt/Torn')} greater 255.5 ] }}")
    o(f"          - {{ to: Tick, when: [ {p('True')} is true ] }}")
    o("      Wrap:")
    o("        motion: ~")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {p('TornA')}: 0, {p('TornB')}: 255, {p('Cnt/Torn')}: 1, {p('Cnt/TornB')}: 254 }} }}")
    o("        transitions:")
    o(f"          - {{ to: Hop, when: [], exitTime: {ts} }}   # the wrap IS a tick — same dwell rule as the rungs")
    o("    default: Split")
    o("    layout:")
    o("      nodes:")
    o("        Split: [30, 180]")
    o("        Dead:  [270, 180]")
    o("        Tick:  [-210, 260]")
    o("        Hop:   [-450, 260]")
    o("        Wrap:  [-450, 350]")

    # --- frametime rig ---
    o("  # Frametime rig, lifted from vrc-patterns/blendtree-math (owned there; the")
    o("  # tangents: linear ramp makes Time equal elapsed seconds).")
    o(f"  - name: {ch}/FrameTime")
    o("    states:")
    o('      "FrameTime (WD ON)":')
    o("        motion:")
    o("          tree: direct")
    o("          name: FrameTime")
    o("          children:")
    o(f"            - {{ clip: ft_time_ramp, directWeight: {p('One')} }}")
    o("            - tree: direct")
    o('              name: "FrameTime = Time - LastTime"')
    o(f"              directWeight: {p('One')}")
    o("              children:")
    o(f"                - {{ clip: ft_pos, directWeight: {p('Ft/Time')} }}")
    o(f"                - {{ clip: ft_neg, directWeight: {p('Ft/LastTime')} }}")
    o(f"                - {{ clip: ft_stage, directWeight: {p('Ft/Time')} }}")
    o('    default: "FrameTime (WD ON)"')

    # --- fps band ladder ---
    edges = c["fpsEdges"]
    o("  # FpsBand: Watch's ladder routes on the FrameTime AAP (transitions read AAPs one")
    o("  # frame behind); each band state Sets the index and hops straight back. Repeated")
    o("  # Sets of an unchanged value cost nothing on the wire (OSC emission is change-only).")
    o(f"  - name: {ch}/FpsBand")
    o("    states:")
    o("      Split:")
    o("        motion: ~")
    o("        transitions:")
    o("          - { to: Dead, when: [ IsLocal is false ] }")
    o("          - { to: Watch, when: [ IsLocal is true ] }")
    o("      Dead:")
    o("        motion: ~")
    o("      Watch:")
    o("        motion: ~")
    o("        transitions:")
    ft = p("Ft/FrameTime")
    for k in range(len(edges) + 1):
        conds = []
        if k > 0:
            conds.append(f"{ft} greater {edges[k - 1]}")
        if k < len(edges):
            conds.append(f"{ft} less {edges[k]}")
        o(f"          - {{ to: Band{k}, when: [ {', '.join(conds)} ] }}")
    for k in range(len(edges) + 1):
        o(f"      Band{k}:")
        o("        motion: ~")
        o("        behaviours:")
        o(f"          - driver: {{ localOnly: true, set: {{ {p('FpsBand')}: {k} }} }}")
        o("        transitions:")
        o(f"          - {{ to: Watch, when: [ {p('True')} is true ] }}")
    o("    default: Split")

    # --- mirror pump ---
    o("  # MirrorPump: wire Ints -> scratch floats, every frame (a blend tree reads an Int")
    o("  # as 0 — CheckAnimator's non-float-blend-param rule). Runs on every copy; on the")
    o("  # wearer's own it harmlessly mirrors the values being sent.")
    o(f"  - name: {ch}/Pump")
    o("    states:")
    for a, b_ in (("A", "B"), ("B", "A")):
        o(f"      Pump{a}:")
        o("        motion: ~")
        o("        behaviours:")
        o("          - driver:")
        o("              copy:")
        for r in rungs:
            o(f"                {p('Dc/' + r['name'] + '/Cur')}: {p(r['name'])}")
        o(f"                {p('Dc/TnA')}: {p('TornA')}")
        o(f"                {p('Dc/TnB')}: {p('TornB')}")
        o("        transitions:")
        o(f"          - {{ to: Pump{b_}, when: [ {p('True')} is true ] }}")
    o("    default: PumpA")

    # --- relay tree ---
    o("  # Relay: ONE Direct tree drives every relay sender's position (pos.x = rest +")
    o("  # value*step, same-frame analog encoding), computes the per-rung Delta and the")
    o("  # torn Sum as AAPs, and drives the strobe sender's scale. relay_rest carries")
    o("  # every sender's full rest vector so each m_LocalPosition is written whole")
    o("  # (partial vector writes zero the unbound components — animator-schema.md).")
    o(f"  - name: {ch}/Relay")
    o("    states:")
    o('      "Relay (WD ON)":')
    o("        motion:")
    o("          tree: direct")
    o("          name: Relay")
    o("          children:")
    o(f"            - {{ clip: relay_rest, directWeight: {p('One')} }}")
    for r in rungs:
        o(f"            - {{ clip: relay_{r['name'].lower()}_step, directWeight: {p('Dc/' + r['name'] + '/Cur')} }}")
    o(f"            - {{ clip: relay_torna_step, directWeight: {p('Dc/TnA')} }}")
    o(f"            - {{ clip: relay_tornb_step, directWeight: {p('Dc/TnB')} }}")
    o(f"            - {{ clip: relay_scanval_step, directWeight: {p('Sc/Val')} }}")
    o(f"            - {{ clip: relay_scansel_step, directWeight: {p('Sc/SelIdx')} }}")
    o(f"            - {{ clip: relay_strobe_step, directWeight: {p('Sc/Strobe')} }}")
    for r in rungs:
        n = r["name"]
        o(f"            - tree: direct")
        o(f"              name: \"Delta {n} = Cur - Prev\"")
        o(f"              directWeight: {p('One')}")
        o("              children:")
        o(f"                - {{ clip: delta_{n.lower()}_pos, directWeight: {p('Dc/' + n + '/Cur')} }}")
        o(f"                - {{ clip: delta_{n.lower()}_neg, directWeight: {p('Dc/' + n + '/Prev')} }}")
    o(f"            - tree: direct")
    o("              name: \"TornSum = TnA + TnB\"")
    o(f"              directWeight: {p('One')}")
    o("              children:")
    o(f"                - {{ clip: tornsum_a, directWeight: {p('Dc/TnA')} }}")
    o(f"                - {{ clip: tornsum_b, directWeight: {p('Dc/TnB')} }}")
    o('    default: "Relay (WD ON)"')

    # --- stride tallies ---
    o("  # Stride tallies. Idle's ladder fires when Delta leaves (-0.5, 0.5); every bucket")
    o("  # has its positive range and its mod-256 wrap range as separate OR rungs. The")
    o("  # bucket driver Adds the tally and re-stages Prev; two Cool frames let the Delta")
    o("  # AAP settle against the new Prev before Idle re-arms — so classification is")
    o("  # valid only while the delivery interval clears ~5-6 frames (README: the 0.05s")
    o("  # rung's tally is advisory; its truth is the live relay stream).")
    for r in rungs:
        n = r["name"]
        d = p("Dc/" + n + "/Delta")
        o(f"  - name: {ch}/Tally/{n}")
        o("    states:")
        o("      Split:")
        o("        motion: ~")
        o("        transitions:")
        o("          - { to: Idle, when: [ IsLocal is false ] }")
        o("          - { to: Dead, when: [ IsLocal is true ] }")
        o("      Dead:")
        o("        motion: ~")
        o("      Idle:")
        o("        motion: ~")
        o("        transitions:")
        for b, pos, wrap in BUCKETS:
            o(f"          - {{ to: {b}, when: [ {d} greater {pos[0]}, {d} less {pos[1]} ] }}")
            if wrap:
                o(f"          - {{ to: {b}, when: [ {d} greater {wrap[0]}, {d} less {wrap[1]} ] }}")
        for b, _, _ in BUCKETS:
            o(f"      {b}:")
            o("        motion: ~")
            o("        behaviours:")
            o("          - driver:")
            o(f"              add: {{ {p('Ty/' + n + '/' + b)}: 1 }}")
            o(f"              copy: {{ {p('Dc/' + n + '/Prev')}: {p('Dc/' + n + '/Cur')} }}")
            o("        transitions:")
            o(f"          - {{ to: Cool1, when: [ {p('True')} is true ] }}")
        o("      Cool1:")
        o("        motion: ~")
        o("        transitions:")
        o(f"          - {{ to: Cool2, when: [ {p('True')} is true ] }}")
        o("      Cool2:")
        o("        motion: ~")
        o("        transitions:")
        o(f"          - {{ to: Idle, when: [ {p('True')} is true ] }}")
        o("    default: Split")

    # --- torn tally ---
    tp = c["tornPersistFrames"]
    sum_ok = [f"{p('Dc/TornSum')} greater 254.5", f"{p('Dc/TornSum')} less 255.5"]
    o(f"  # Torn tally: Sum != 255 persisting {tp} frames counts one torn event; Count")
    o("  # waits for the pair to re-agree so one event never counts twice.")
    o(f"  - name: {ch}/TornTally")
    o("    states:")
    o("      Split:")
    o("        motion: ~")
    o("        transitions:")
    o("          - { to: Idle, when: [ IsLocal is false ] }")
    o("          - { to: Dead, when: [ IsLocal is true ] }")
    o("      Dead:")
    o("        motion: ~")
    o("      Idle:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Susp1, when: [ {p('Dc/TornSum')} less 254.5 ] }}")
    o(f"          - {{ to: Susp1, when: [ {p('Dc/TornSum')} greater 255.5 ] }}")
    prev = "Susp1"
    for i in range(2, tp + 1):
        o(f"      {prev}:")
        o("        motion: ~")
        o("        transitions:")
        o(f"          - {{ to: Idle, when: [ {', '.join(sum_ok)} ] }}")
        o(f"          - {{ to: Susp{i}, when: [ {p('True')} is true ] }}")
        prev = f"Susp{i}"
    o(f"      {prev}:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Idle, when: [ {', '.join(sum_ok)} ] }}")
    o(f"          - {{ to: Count, when: [ {p('True')} is true ] }}")
    o("      Count:")
    o("        motion: ~")
    o("        behaviours:")
    o(f"          - driver: {{ add: {{ {p('Ty/TornCount')}: 1 }} }}")
    o("        transitions:")
    o(f"          - {{ to: Idle, when: [ {', '.join(sum_ok)} ] }}")
    o("    default: Split")

    # --- heartbeat ---
    hb = c["heartbeatHalfSeconds"]
    o(f"  # Heartbeat: {hb}s half-period flip-flop of complementary GO-active clips — pure")
    o("  # local time. Exactly one of HbA/HbB active at any instant on a healthy relay.")
    o(f"  - name: {ch}/Heartbeat")
    o("    states:")
    o("      HbA:")
    o("        motion: { clip: hb_a }")
    o("        transitions:")
    o("          - { to: HbB, when: [], exitTime: 1.0 }")
    o("      HbB:")
    o("        motion: { clip: hb_b }")
    o("        transitions:")
    o("          - { to: HbA, when: [], exitTime: 1.0 }")
    o("    default: HbA")

    # --- scan bus ---
    registers = []
    for r in rungs:
        for b, _, _ in BUCKETS:
            registers.append((f"{r['name']}/{b}", p(f"Ty/{r['name']}/{b}")))
    registers.append(("TornCount", p("Ty/TornCount")))
    registers.append(("SweepMark", None))  # sentinel: Sel 21, Val 128 — also keeps the
    #   register count EVEN, so the k%2 strobe has an edge at the sweep wrap
    dwell = c["scanDwellSeconds"]
    o(f"  # Scan bus: {len(registers)} registers round-robined at {dwell}s per register onto three")
    o("  # analog lines. Val carries tally/10 (convertRange 0..2550 -> 0..255): a raw")
    o("  # 0..255 copy saturated inside ONE 33s sweep on every rung faster than 0.2s")
    o("  # (R05's S1 fills 255 counts in 12.75s), unusable as the cross-check it exists")
    o("  # to be; at /10 the fastest register lasts ~128s, two clean sweeps. The strobe")
    o("  # flips as each register latches, so a logger reads Val/Sel only between edges;")
    o("  # the SweepMark sentinel (Sel 21, Val 128) makes the count even — 21 registers")
    o("  # left Reg20 and Reg0 both strobe-0, one edgeless interval per sweep.")
    o(f"  - name: {ch}/Scan")
    o("    states:")
    o("      Split:")
    o("        motion: ~")
    o("        transitions:")
    o("          - { to: Reg0, when: [ IsLocal is false ] }")
    o("          - { to: Dead, when: [ IsLocal is true ] }")
    o("      Dead:")
    o("        motion: ~")
    for k, (label, tally) in enumerate(registers):
        o(f"      Reg{k}:   # {label}")
        o("        motion: ~")
        o("        behaviours:")
        o("          - driver:")
        o("              set:")
        o(f"                {p('Sc/SelIdx')}: {k}")
        o(f"                {p('Sc/Strobe')}: {k % 2}")
        if tally is None:
            o(f"                {p('Sc/Val')}: 128")
        else:
            o("              copy:")
            o(f"                {p('Sc/Val')}: {{ source: {tally}, sourceMin: 0, sourceMax: 2550, destMin: 0, destMax: 255 }}")
        o("        transitions:")
        o(f"          - {{ to: Reg{(k + 1) % len(registers)}, when: [], exitTime: {dwell} }}")
    o("    default: Split")

    # --- mirror gate ---
    o("  # MirrorGate: a mirror clone runs the clip layers (the heartbeat included) from")
    o("  # Entry at its own phase but executes NO drivers, so its relay senders would")
    o("  # broadcast garbage on the live tags — both heartbeat lines high at once reads")
    o("  # as 'contact trouble, discard'. The gate holds the whole Rig inactive until a")
    o("  # driver proves this copy is real (mirror-detect's race); real copies pass in")
    o("  # ~2 frames, a mirror never does.")
    o(f"  - name: {ch}/MirrorGate")
    o("    states:")
    o("      Probe:")
    o("        motion: { clip: rig_off }")
    o("        behaviours:")
    o(f"          - driver: {{ set: {{ {p('Alive')}: 1 }} }}")
    o("        transitions:")
    o(f"          - {{ to: Live, when: [ {p('Alive')} is true ] }}")
    o("      Live:")
    o("        motion: { clip: rig_on }")
    o("    default: Probe")

    # --- reset ---
    o("  # Reset: the wearer's menu button clears tallies on EVERY client (localOnly")
    o("  # false) and re-stages Prev from Cur so the first post-reset delivery is not a")
    o("  # spurious big-jump.")
    o(f"  - name: {ch}/Reset")
    o("    states:")
    o("      Idle:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Clear, when: [ {p('Reset')} is true ] }}")
    o("      Clear:")
    o("        motion: ~")
    o("        behaviours:")
    o("          - driver:")
    o("              set:")
    for r in rungs:
        for b, _, _ in BUCKETS:
            o(f"                {p('Ty/' + r['name'] + '/' + b)}: 0")
    o(f"                {p('Ty/TornCount')}: 0")
    o("              copy:")
    for r in rungs:
        o(f"                {p('Dc/' + r['name'] + '/Prev')}: {p('Dc/' + r['name'] + '/Cur')}")
    o("        transitions:")
    o(f"          - {{ to: Idle, when: [ {p('Reset')} is false ] }}")
    o("    default: Idle")
    o("")

    # ---------------- clips ----------------
    o("clips:")
    o("  # Frametime rig. tangents: linear is REQUIRED — flat tangents stair-step Time.")
    o("  ft_time_ramp: { curves: { " + p("Ft/Time") + ": { tangents: linear, keys: [ [0, 0], [10000000, 10000000] ] } } }")
    o(f"  ft_pos:   {{ set: {{ {p('Ft/FrameTime')}: 1.0 }} }}")
    o(f"  ft_neg:   {{ set: {{ {p('Ft/FrameTime')}: -1.0 }} }}")
    o(f"  ft_stage: {{ set: {{ {p('Ft/LastTime')}: 1.0 }} }}")
    o("  # Delta / sum endpoints.")
    for r in rungs:
        n = r["name"].lower()
        o(f"  delta_{n}_pos: {{ set: {{ {p('Dc/' + r['name'] + '/Delta')}: 1.0 }} }}")
        o(f"  delta_{n}_neg: {{ set: {{ {p('Dc/' + r['name'] + '/Delta')}: -1.0 }} }}")
    o(f"  tornsum_a: {{ set: {{ {p('Dc/TornSum')}: 1.0 }} }}")
    o(f"  tornsum_b: {{ set: {{ {p('Dc/TornSum')}: 1.0 }} }}")
    o("  # Relay rest: every sender's full rest vector in ONE clip (weight One), so each")
    o("  # m_LocalPosition is written whole across the tree's union.")
    sender_paths = [("Rig/" + r["name"] + "/S", r["name"]) for r in rungs]
    rest_entries = []
    for r in rungs:
        rest_entries.append(f"Rig/{r['name']}/S")
    # Every animated sender sits under its own offset-carrying parent node and is
    # animated in z alone — the rest clip writes the full local vector, so a sender
    # authored at a lateral offset would otherwise be animated back to y=0, out of
    # its receiver's box (measured: ScanSel read 0 while ScanVal read exact).
    rest_entries += ["Rig/Torn/A/S", "Rig/Torn/B/S", "Rig/Scan/Val/S", "Rig/Scan/Sel/S"]
    o("  relay_rest:")
    o("    set:")
    for path in rest_entries:
        o(f"      \"{path}/Transform.m_LocalPosition.x\": 0")
        o(f"      \"{path}/Transform.m_LocalPosition.y\": 0")
        o(f"      \"{path}/Transform.m_LocalPosition.z\": {rest}")
    o("      # strobe: position-encoded like everything else (rest 0.5 = outside its")
    o("      # Constant box at z 2.5; +2.0 x Strobe puts it inside). A scale-0 sphere at")
    o("      # a box's centre was the first design and is unproven as a gate.")
    o("      \"Rig/Scan/Strobe/S/Transform.m_LocalPosition.x\": 0")
    o("      \"Rig/Scan/Strobe/S/Transform.m_LocalPosition.y\": 0")
    o("      \"Rig/Scan/Strobe/S/Transform.m_LocalPosition.z\": 0.5")
    o("  # Per-channel step endpoints: pos.z contribution = value * step.")
    for r in rungs:
        o(f"  relay_{r['name'].lower()}_step: {{ set: {{ \"Rig/{r['name']}/S/Transform.m_LocalPosition.z\": {step} }} }}")
    o(f"  relay_torna_step: {{ set: {{ \"Rig/Torn/A/S/Transform.m_LocalPosition.z\": {step} }} }}")
    o(f"  relay_tornb_step: {{ set: {{ \"Rig/Torn/B/S/Transform.m_LocalPosition.z\": {step} }} }}")
    o(f"  relay_scanval_step: {{ set: {{ \"Rig/Scan/Val/S/Transform.m_LocalPosition.z\": {step} }} }}")
    o(f"  relay_scansel_step: {{ set: {{ \"Rig/Scan/Sel/S/Transform.m_LocalPosition.z\": {c['scanSelStep']} }} }}")
    o("  relay_strobe_step: { set: { \"Rig/Scan/Strobe/S/Transform.m_LocalPosition.z\": 2.0 } }")
    o("  # Mirror gate endpoints.")
    o("  rig_off: { set: { \"Rig/GameObject.m_IsActive\": 0 } }")
    o("  rig_on:  { set: { \"Rig/GameObject.m_IsActive\": 1 } }")
    o("  # Heartbeat: complementary GO actives, half-period per clip.")
    o("  hb_a:")
    o(f"    seconds: {hb}")
    o("    set:")
    o("      \"Rig/Hb/SA/GameObject.m_IsActive\": 1")
    o("      \"Rig/Hb/SB/GameObject.m_IsActive\": 0")
    o("  hb_b:")
    o(f"    seconds: {hb}")
    o("    set:")
    o("      \"Rig/Hb/SA/GameObject.m_IsActive\": 0")
    o("      \"Rig/Hb/SB/GameObject.m_IsActive\": 1")
    o("")

    # ---------------- menu ----------------
    o("menu:")
    o("  # A toggle, not a button: the clear runs on the REMOTE copies, and a synced")
    o("  # set->clear pair needs ~0.2s of separation to be seen remotely at all")
    o("  # (docs/runtime.md #Parameters) — a button click is under it. Hold ~2s.")
    o("  - toggle: Reset")
    o(f"    param: {p('Reset')}")

    return "\n".join(L) + "\n", registers


def main():
    text, registers = emit()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controller.yaml")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    c = CONFIG
    synced = 8 * len(c["rungs"]) + 16 + 1
    layers = len(c["rungs"]) * 2 + 10
    print(f"wrote {out}: {synced} synced bits ({len(c['rungs'])} rungs + torn pair + reset), "
          f"{layers} layers, {len(registers)} scan registers, "
          f"relay span {c['relayRest']}..{c['relayRest'] + 255 * c['relayStep']:.2f} m")


if __name__ == "__main__":
    main()
