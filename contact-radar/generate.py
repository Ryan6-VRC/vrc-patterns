#!/usr/bin/env python3
"""contact-radar generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ in a mounting Editor —
the controller.yaml committed here is generated output and the repo gate holds
built/ to it, so hand-editing it desynchronises the document from both this
generator and the compiled controller. `--check` asserts the hand-maintained
prefab surface no compile or gate reads (README §Verifying).

What it builds: K per-sender "slots", one FX layer each. A slot is three
coincident face-proximity box receivers (X+, Y+, Z+) whose `allowOthers` flag is
the latch: a sender whose overlap with a receiver began while the flag was shut
stays invisible to that receiver for the whole overlap, however the flag moves
later, and only a full exit and re-entry admits it (emulator-measured, README
§How it works). Exactly one slot is Open (flag up) at a time; the others are
Armed (flag shut) so hands already inside are blind to them. When the Open slot
reads a hand it Latches (flag shut, boxes expanded to the hold cube) and the
next Armed slot in ring order Opens in the same animator evaluation, so the
two land in one collision step and the admission windows tile. The latched
slot then reconstructs its hand's position exactly (box-tracker's readout,
three boxes and a configured sender radius) and computes r² = x²+y²+z² in a
piecewise-linear lookup; the burst fires when r² crosses the burst radius.

Two modes, one flag: `dwell` keeps the slot until the hand leaves the hold cube
and re-bursts each time it crosses back inside the burst radius after retreating
past the re-arm radius; `entry` releases the slot at the burst, so the hand has
to leave the acquisition cube and come back for another. A released slot
Recycles: its boxes collapse to near zero for `stepSeconds` and restore with the
flag shut, a fresh overlap episode that rejects every hand still inside
(measured), then it queues as Armed.

Rules the emitted document keeps, each bought by a measurement or a doc line:
- Every step-spanning dwell is authored in seconds >= 2/60: the collision scene
  steps at most 60 times a second and a collapse or stow shorter than a step is
  skipped silently (docs/runtime.md §Contacts).
- Every slot state writes every flag (Open, Armed), the burst toggle and the
  payload toggle, zeros included: an AAP holds its last clip-written value and a scene binding holds
  whatever last wrote it (docs/runtime.md §Animator evaluation).
- The burst states carry the readout tree: the payload wrapper enables where Output
  sits on that frame — the buffer particle inside it is born there — and only a tree
  state keeps writing that position. One toggle serves both consumers: a buffer
  particle reads its enable edge, a mesh reads its level.
- `Cage/Size` is the consumer's static size knob (README §Knobs): scaling it scales
  the cubes, the readout, the sphere and every band together, so every lint below
  holds at any scale; only the sender-radius bias term scales when it should not.
- Latch writes x, y, z to holdHalf so the first r² computed in TrackOut is
  3h², far outside the sphere; the guard is the state sequence, no settle AAP.
- Timed dwells are plain clips, never a curve inside a Direct tree (the tree's
  duration is data — docs/animator-schema.md §motions).
- Recycle's collapse/restore takes stepped tangents; a bare curve eases.
- The parameter driver lives only in Disabled (off-state hygiene, localOnly false:
  every client zeroes its own receiver floats).
- An admission can land on some of a slot's three coincident boxes and not the
  others when the overlap begins on the very frame the slot opens (measured), and
  a slot holding a partial reading can never satisfy the three-way Latch — so
  Open steps aside to Partial on any single reading and Recycles a step later if
  the other two never arrive. An Open slot that stalls blocks every admission on
  the avatar; the recycled hand is merely invisible until it re-enters.
- One rung fires per frame per layer; the ring rule's exclusivity rests on
  every rung also requiring the slot's OWN Armed flag, which is one frame stale:
  a slot that entered Armed this frame is skipped by its neighbours (they read
  its Armed as 0) and skips itself (it reads its own as 0), so two slots can
  never open on one firing.

What happens at enable, at load and around a pause — the expanding front:
- Sticky rejection is also what blinds the rig at enable: Armed slots at full
  size reject every hand already inside. So while `CR/Sweeping` is up, Armed
  slots sit COLLAPSED (they hold no rejections) and one slot sweeps: its cube
  grows from the last front position (`CR/Sweep`, latched into `CR/SweepBase`
  by the SweepShut step) to acqHalf over `sweepSeconds`, flag up, so each hand
  is admitted alone as the front reaches it. On a latch the ring opens the next
  slot into SweepShut — the cube appears at the current front SHUT for a step,
  re-rejecting the just-latched hand and everything else inside the front (the
  Recycle idiom) — then Sweep continues from there. The sweep ends when the
  front reads past acqHalf: that slot goes Open at full size, clears Sweeping,
  and every Armed slot restores shut with nothing unlatched left inside.
- Two hands within about two collision steps of front travel at the same
  Chebyshev radius co-latch, the same window as a normal admission; the sweep
  speed is that resolution.
- `CR/Silent` decides what a hand the front finds inside the sphere does: loud
  (from Disabled — the toggle) bursts as usual; silent (from Boot — a fresh
  animator — and from Paused — a distance-hide resume) lands in TrackInSilent
  in dwell mode (payload on, the buffer particle's GameObject off: marker, no
  puff) and releases without a burst in entry mode. Open at full size clears
  Silent, so a hand that crosses in after the sweep bursts loud.
- Boot is the default state and is entered only by a fresh animator (load,
  manual hide/show, mirror clones); Disabled is entered only by the toggle.
- Paused is entered from every state on `IsAnimatorEnabled` false, VRChat's
  one-frame pre-halt signal for a distance-hide (docs/runtime.md §Parameters
  carries the citation; view cull gives no signal and is the README's bounds
  requirement). Its clip collapses the boxes; on resume the rig passes through
  Paused, Armed (collapsed) and SweepShut at front 0 before anything grows, so
  whatever the receivers did during the pause is discarded and the present
  hands are re-acquired from scratch, silently.
- The four sweep AAPs have exactly one writer, the `Sweep` layer, whose every
  state writes all four: a WD-ON state reverts any AAP it does not write to its
  default (measured on this rig — a 1D-tree Armed state dropped `Sweeping` to 0
  within a frame), so a value that must persist across a state is written back
  to itself through a direct child weighted by its own value. Slot layers read
  the four and report `Slot<k>/Front` (1 in their Sweep state) for the layer to
  ramp on; the front advances only while a flag-up cube is riding it, so the
  next slot's shut step never sweeps a hand it would reject.
- The `Ramp` state is a Direct tree whose duration is data: the ramp clip
  carries the timing and the self-copies are one frame long, which stretches
  the ramp by at most (2·SweepBase + Silent)/(60·sweepSeconds).

Fragment mode: `document(overrides)` returns the document text and a facts
dict; `entry-mode/generate.py` is the second consumer.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "controller": "ContactRadar_Fx",
    "mode": "dwell",            # dwell | entry
    "K": 4,                     # slots; each is one layer and 3 receivers
    "tags": ["HandR"],
    "acqHalf": 1.2,             # acquisition cube half-extent, m (entry mode's re-arm surface); at Cage/Size scale 1
    "holdHalf": 1.3,            # hold cube half-extent, m — h in the readout
    "burstRadius": 1.0,         # R_in, m
    "rearmRadius": 1.1,         # R_out, m (dwell only)
    "senderRadius": 0.05,       # r, m — the hand sender's radius; a capsule reads as a constant bias
    "stepSeconds": 0.035,       # every step-spanning dwell; >= 2 collision steps
    "sweepSeconds": 1.0,        # the front's travel time from 0 to acqHalf at enable, load and resume
    "boundsHalf": 2.0,          # the renderer-bounds cube half-extent, m: an observer inside it never view-culls you
    "lookupSegments": 16,       # x² table resolution over [-h, h]
    "epsilon": 1e-5,            # the any-box loss floor
    "boxSize": 1.0,             # the receiver box `size` on every axis; the Boxes scale multiplies it
    "prefix": "CR",             # internal param namespace; never published
    "enable": "ContactRadar/Enable",
}


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def fmt(v):
    return format(float(v), ".9g")


def lint(c):
    if c["mode"] not in ("dwell", "entry"):
        refuse("mode must be dwell or entry")
    if c["K"] < 2:
        refuse("K must be >= 2 — one slot has nothing to hand off to")
    if c["holdHalf"] < c["acqHalf"]:
        refuse("holdHalf must be >= acqHalf — the latch expands, never shrinks")
    if c["burstRadius"] + c["senderRadius"] >= c["acqHalf"]:
        refuse("burstRadius + senderRadius must be < acqHalf — the burst must be reachable inside the cube")
    if c["mode"] == "dwell":
        if c["rearmRadius"] <= c["burstRadius"]:
            refuse("rearmRadius must be > burstRadius")
        if c["rearmRadius"] + c["senderRadius"] >= c["acqHalf"]:
            refuse("rearmRadius + senderRadius must be < acqHalf — a dwell re-arm must be reachable on axis")
    if c["stepSeconds"] < 2 / 60:
        refuse("stepSeconds must be >= 2/60 — a dwell shorter than two collision steps can be skipped")
    if c["sweepSeconds"] * 60 / c["acqHalf"] < 4:
        refuse("sweepSeconds is too short — the front would cross more than a quarter of the cube per collision step")
    if c["boundsHalf"] <= c["holdHalf"]:
        refuse("boundsHalf must exceed holdHalf — a toucher's head is outside the hold cube while the hand is inside")
    if 2 * c["holdHalf"] > 6:
        refuse("2*holdHalf exceeds the SDK's serialized box limit (6 m) — a sanity bound on the working volume")
    if c["lookupSegments"] < 4:
        refuse("lookupSegments must be >= 4")
    if "/" in c["prefix"] or not c["prefix"]:
        refuse("prefix must be a bare segment")
    if c["enable"].count("/") != 1:
        refuse("enable must be one prefixed name (Module/Enable) — the wildcard for a bare name matches nothing")


def slot_name(c, k):
    return f"{c['prefix']}/Slot{k}"


def boxes_path(k):
    return f"Cage/Size/Slot{k}/Boxes"


def out_path(k):
    return f"Cage/Size/Slot{k}/Output"


def emit_layer(o, c, k, ks):
    P = c["prefix"]
    en = c["enable"]
    mode = c["mode"]
    me = slot_name(c, k)
    eps = c["epsilon"]
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    acq = c["acqHalf"]
    paused = "          - { to: Paused, when: [ IsAnimatorEnabled is false ] }   # the pre-halt frame: park before the animator stops"
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"

    def rungs():
        o(paused)
        o(off)

    o(f"  - name: Slot{k}")
    o("    states:")
    o("      Boot:                        # a fresh animator: load, manual hide/show, a mirror clone — the Sweep layer makes its sweep silent")
    o(f"        motion: {{ clip: slot{k}_boot }}")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Disabled, when: [ {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ {en} is true ], exitTime: 1.0 }}")
    o("      Disabled:                    # Enable off — boxes stowed, flag shut, readings zeroed on every client")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: false, set: {{ {me}/X+: 0, {me}/Y+: 0, {me}/Z+: 0 }} }}")
    o(f"        motion: {{ clip: slot{k}_off }}")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Armed, when: [ {en} is true ], exitTime: 1.0 }}   # quantized: an Enable cycle spans a step")
    o("      Paused:                      # boxes collapsed through the pause; resume re-acquires from scratch")
    o(f"        motion: {{ clip: slot{k}_paused }}")
    o("        transitions:")
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ IsAnimatorEnabled is true, {en} is true ] }}")
    o("      Armed:                       # flag shut: every hand already inside stays invisible to this slot; collapsed while a sweep runs")
    o("        motion:")
    o("          tree: 1d")
    o(f"          name: Slot{k} armed")
    o(f"          param: {P}/Sweeping")
    o("          children:")
    o(f"            - {{ clip: slot{k}_armed, threshold: 0 }}")
    o(f"            - {{ clip: slot{k}_armed_collapsed, threshold: 1 }}")
    o("        transitions:")
    rungs()
    for i in ks:
        if i == k:
            continue
        between = []
        m = i % len(ks) + 1
        while m != k:
            between.append(m)
            m = m % len(ks) + 1
        si = slot_name(c, i)
        conds = [f"{si}/Open greater 0.5", f"{si}/X+ greater 0", f"{si}/Y+ greater 0", f"{si}/Z+ greater 0",
                 f"{me}/Armed greater 0.5"]
        conds += [f"{slot_name(c, m)}/Armed less 0.5" for m in between]
        o(f"          - {{ to: SweepShut, when: [ {', '.join(conds + [f'{P}/Sweeping greater 0.5'])} ] }}   # ring: slot {i} fired mid-sweep, nothing Armed between")
        o(f"          - {{ to: Open, when: [ {', '.join(conds + [f'{P}/Sweeping less 0.5'])} ] }}   # ring: slot {i} fired, nothing Armed between")
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j < k]
    conds += [f"{me}/Armed greater 0.5"]
    o(f"          - {{ to: SweepShut, when: [ {', '.join(conds + [f'{P}/Sweeping greater 0.5'])} ], exitTime: 1.0 }}   # self-open into the sweep: nothing Open, no lower Armed; re-checked only on a crossing")
    o(f"          - {{ to: Open, when: [ {', '.join(conds + [f'{P}/Sweeping less 0.5'])} ], exitTime: 1.0 }}   # self-open: nothing Open, no lower Armed; re-checked only on a crossing")
    o("      SweepShut:                   # the cube appears at the front SHUT for a step: everything inside it is re-rejected")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} sweep shut")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_sweepshut, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o("          - { to: Sweep, when: [], exitTime: 1.0 }")
    o("      Sweep:                       # flag up, the cube riding the Sweep layer's front: each hand is admitted alone as the front reaches it")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} sweep")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_sweep_cfg, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {me}/X+ greater 0, {me}/Y+ greater 0, {me}/Z+ greater 0 ] }}")
    for ax in ("X+", "Y+", "Z+"):
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    o(f"          - {{ to: Open, when: [ {P}/Sweep greater {fmt(acq)} ] }}   # the front reached the face: the sweep is over")
    o("      Open:                        # flag up at full size: only overlaps beginning now are admitted")
    o(f"        motion: {{ clip: slot{k}_open }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {me}/X+ greater 0, {me}/Y+ greater 0, {me}/Z+ greater 0 ] }}")
    for ax in ("X+", "Y+", "Z+"):
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    o("      Partial:                     # one box read a hand the others did not: a step's grace at the current front, else Recycle — an Open slot may never stall")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} partial")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_open_wait, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {me}/X+ greater 0, {me}/Y+ greater 0, {me}/Z+ greater 0 ] }}")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Latch:                       # flag shut + hold cube in one write; x,y,z parked at h so the first r² reads 3h²")
    o(f"        motion: {{ clip: slot{k}_latch }}")
    o("        transitions:")
    rungs()
    o("          - { to: TrackOut, when: [], exitTime: 1.0 }")
    o("      TrackOut:                    # readout live, payload off; outside the burst radius")
    emit_tree(o, c, k, hold=f"slot{k}_hold")
    o("        transitions:")
    rungs()
    for ax in ("X+", "Y+", "Z+"):
        o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")
    if mode == "dwell":
        o(f"          - {{ to: TrackIn, when: [ {me}/r2 less {fmt(rin2)}, {P}/Silent less 0.5 ] }}")
        o(f"          - {{ to: TrackInSilent, when: [ {me}/r2 less {fmt(rin2)}, {P}/Silent greater 0.5 ] }}   # found inside by a silent sweep: marker, no puff")
    else:
        o(f"          - {{ to: Burst, when: [ {me}/r2 less {fmt(rin2)}, {P}/Silent less 0.5 ] }}")
        o(f"          - {{ to: Recycle, when: [ {me}/r2 less {fmt(rin2)}, {P}/Silent greater 0.5 ] }}   # found inside by a silent sweep: release without a burst")
    if mode == "dwell":
        o("      TrackIn:                     # inside the burst radius; the payload is on (one burst per entry, a marker visible throughout)")
        emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
        o("        transitions:")
        rungs()
        for ax in ("X+", "Y+", "Z+"):
            o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")
        o(f"          - {{ to: TrackOut, when: [ {me}/r2 greater {fmt(rout2)} ] }}")
        o("      TrackInSilent:               # inside the burst radius with the buffer particle held off: the marker rides, nothing puffs")
        emit_tree(o, c, k, hold=f"slot{k}_hold_burst_silent")
        o("        transitions:")
        rungs()
        for ax in ("X+", "Y+", "Z+"):
            o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")
        o(f"          - {{ to: TrackOut, when: [ {me}/r2 greater {fmt(rout2)} ] }}")
    else:
        o("      Burst:                       # the payload on for the tree's own dwell, then release")
        emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
        o("        transitions:")
        rungs()
        o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Recycle:                     # collapse a step, restore a step, flag shut: every hand inside is re-rejected")
    o(f"        motion: {{ clip: slot{k}_recycle }}")
    o("        transitions:")
    rungs()
    o("          - { to: Armed, when: [], exitTime: 1.0 }")
    o("    default: Boot")
    o("    layout:")
    target = "TrackIn" if mode == "dwell" else "Burst"
    extra = ", TrackInSilent: [510, 540]" if mode == "dwell" else ""
    o(f"      nodes: {{ Boot: [30, 90], Disabled: [30, 180], Paused: [270, 180], Armed: [30, 270], SweepShut: [-210, 270], Sweep: [-210, 360], Open: [30, 360], Partial: [270, 360], Latch: [30, 450], TrackOut: [-210, 540], {target}: [270, 540]{extra}, Recycle: [30, 630] }}")
    o("      entry: [50, 30]")
    o("      any:   [300, 30]")
    o("      exit:  [180, 30]")


def emit_sweep_layer(o, c, ks):
    """The one writer of the four shared sweep AAPs. Every state writes all four — a WD-ON state
    reverts any AAP it does not write to its default (measured on this rig), so a value that
    must persist across a state is written back to itself through a direct child weighted by
    its own value."""
    P = c["prefix"]
    en = c["enable"]
    acq = c["acqHalf"]
    fronts_up = " , ".join(f"{slot_name(c, k)}/Front greater 0.5" for k in ks)
    fronts_down = ", ".join(f"{slot_name(c, k)}/Front less 0.5" for k in ks)
    paused = "          - { to: Paused, when: [ IsAnimatorEnabled is false ] }"
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"

    def hold_tree(name, children):
        o("        motion:")
        o("          tree: direct")
        o(f"          name: {name}")
        o("          normalized: false")
        o("          children:")
        for clip, w in children:
            o(f"            - {{ clip: {clip}, directWeight: {w} }}")

    o("  - name: Sweep")
    o("    # The expanding front, shared by every slot: Sweeping (collapse the Armed slots), Silent (the no-puff endpoint),")
    o("    # Sweep (the front half-extent, m) and SweepBase (where the current sweeper's ramp started). Slot layers read these")
    o("    # and never write them; each slot reports its own Front flag (1 in its Sweep state) for this layer to ramp on.")
    o("    states:")
    o("      Boot:                        # a fresh animator: the first sweep is silent")
    o("        motion: { clip: sw_boot }")
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Wait, when: [ {en} is true ] }}")
    o("      Disabled:                    # the toggle is off: the next sweep is loud")
    o("        motion: { clip: sw_off }")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Wait, when: [ {en} is true ] }}")
    o("      Paused:                      # a distance-hide: the resume sweep is silent")
    o("        motion: { clip: sw_paused }")
    o("        transitions:")
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Wait, when: [ IsAnimatorEnabled is true, {en} is true ] }}")
    o("      Wait:                        # a sweep is pending or between slots: the front holds, SweepBase latches it, Silent holds")
    hold_tree("Sweep wait", [("sw_sweeping", f"{P}/One"), ("sw_hold_sweep", f"{P}/Sweep"), ("sw_latch_base", f"{P}/Sweep"), ("sw_hold_silent", f"{P}/Silent")])
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Idle, when: [ {P}/Sweep greater {fmt(acq)} ] }}")
    for k in ks:
        o(f"          - {{ to: Ramp, when: [ {slot_name(c, k)}/Front greater 0.5 ] }}")
    o("      Ramp:                        # a slot's flag is up: the front grows from SweepBase at the configured speed")
    hold_tree("Sweep ramp", [("sw_ramp", f"{P}/One"), ("sw_hold_sweep", f"{P}/SweepBase"), ("sw_hold_base", f"{P}/SweepBase"), ("sw_hold_silent", f"{P}/Silent")])
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Idle, when: [ {P}/Sweep greater {fmt(acq)} ] }}   # the face: the sweep is over")
    o(f"          - {{ to: Wait, when: [ {fronts_down} ] }}   # the sweeper latched (or stalled): hold the front for the next slot's shut step")
    o("      Idle:                        # no sweep: Armed slots at full size, the front parked at the face, loud")
    o("        motion: { clip: sw_idle }")
    o("        transitions:")
    o(paused)
    o(off)
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 90], Disabled: [30, 180], Paused: [270, 180], Wait: [30, 270], Ramp: [270, 270], Idle: [30, 360] }")
    o("      entry: [50, 30]")
    o("      any:   [300, 30]")
    o("      exit:  [180, 30]")


def emit_sweep_clips(o, c):
    P = c["prefix"]
    T = c["sweepSeconds"]
    acq = c["acqHalf"]
    reach = acq * 1.05   # the ramp aims a little past the face so `Sweep greater acqHalf` fires before it ends

    def clip(name, sets, seconds=None, comment=None):
        body = ", ".join(f"{k2}: {v}" for k2, v in sets.items())
        sec = f"seconds: {fmt(seconds)}, " if seconds else ""
        o(f"  {name}: {{ {sec}set: {{ {body} }} }}" + (f"   # {comment}" if comment else ""))

    def full(sweeping, silent, sweep, base):
        return {f"{P}/Sweeping": sweeping, f"{P}/Silent": silent, f"{P}/Sweep": fmt(sweep), f"{P}/SweepBase": fmt(base)}

    o("  # Sweep layer: constants, and the self-copies a hold needs (weight = the AAP's own value, the clip writes 1).")
    clip("sw_boot", full(1, 1, 0, 0), None, "a fresh animator: silent, front at 0")
    clip("sw_off", full(1, 0, 0, 0), None, "the toggle off: loud, front at 0")
    clip("sw_paused", full(1, 1, 0, 0), None, "a distance-hide: silent, front at 0")
    clip("sw_idle", full(0, 0, acq, 0), None, "no sweep: the front parked at the face")
    clip("sw_sweeping", {f"{P}/Sweeping": 1}, None, "the constant part of Wait")
    clip("sw_hold_sweep", {f"{P}/Sweep": 1}, None, "× Sweep (Wait: hold) or × SweepBase (Ramp: the ramp's origin)")
    clip("sw_latch_base", {f"{P}/SweepBase": 1}, None, "× Sweep: SweepBase ← Sweep")
    clip("sw_hold_base", {f"{P}/SweepBase": 1}, None, "× SweepBase: hold")
    clip("sw_hold_silent", {f"{P}/Silent": 1}, None, "× Silent: hold")
    o(f"  sw_ramp:   # × One: Sweeping 1 and the front's own travel, 0 → {fmt(reach)} m over {fmt(T)} s, linear, added to SweepBase")
    o(f"    seconds: {fmt(T)}")
    o(f"    set: {{ {P}/Sweeping: 1 }}")
    o("    curves:")
    o(f"      {P}/Sweep: {{ tangents: linear, keys: [ [0, 0], [{fmt(T)}, {fmt(reach)}] ] }}")


def emit_tree(o, c, k, hold):
    P = c["prefix"]
    me = slot_name(c, k)
    h = c["holdHalf"]
    N = c["lookupSegments"]
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} readout")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: {hold}, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_read_bias, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_read_xp, directWeight: {me}/X+ }}")
    o(f"            - {{ clip: slot{k}_read_yp, directWeight: {me}/Y+ }}")
    o(f"            - {{ clip: slot{k}_read_zp, directWeight: {me}/Z+ }}")
    for ax in ("x", "y", "z"):
        o("            - tree: 1d")
        o(f"              name: Slot{k} {ax}²")
        o(f"              param: {me}/{ax}")
        o(f"              directWeight: {P}/One")
        o("              children:")
        for i in range(N + 1):
            t = -h + 2 * h * i / N
            o(f"                - {{ clip: slot{k}_sq_{i}, threshold: {fmt(t)} }}")


def emit_clips(o, c, k):
    me = slot_name(c, k)
    B = boxes_path(k)
    O = out_path(k)
    h = c["holdHalf"]
    r = c["senderRadius"]
    step = c["stepSeconds"]
    N = c["lookupSegments"]
    acq = 2 * c["acqHalf"] / c["boxSize"]
    hold = 2 * c["holdHalf"] / c["boxSize"]
    collapsed = 0.001
    per_m = 2 / c["boxSize"]          # box scale per metre of front half-extent
    payload = f"{O}/Payload/GameObject.m_IsActive"
    buffer = f"{O}/Payload/Burst/GameObject.m_IsActive"

    def cfg(active, flag, scale, opn, armed, payload_on, buffer_on=1, front=0):
        d = {f"{B}/GameObject.m_IsActive": active}
        for ax in ("X+", "Y+", "Z+"):
            d[f"{B}/{ax}/VRCContactReceiver.allowOthers"] = flag
        if scale is not None:
            for ax in ("x", "y", "z"):
                d[f"{B}/Transform.m_LocalScale.{ax}"] = fmt(scale)
        d[f"{me}/Open"] = opn
        d[f"{me}/Armed"] = armed
        d[f"{me}/Front"] = front
        d[payload] = payload_on
        d[buffer] = buffer_on
        return d

    def clip(name, sets, seconds=None, comment=None):
        body = ", ".join(f"{k2}: {v}" for k2, v in sets.items())
        sec = f"seconds: {fmt(seconds)}, " if seconds else ""
        o(f"  {name}: {{ {sec}set: {{ {body} }} }}" + (f"   # {comment}" if comment else ""))

    o(f"  # Slot {k} configurations — every one writes the box stow, the flag, the scale, the three protocol flags, the payload toggle and the buffer toggle.")
    clip(f"slot{k}_boot", cfg(0, 0, acq, 0, 0, 0), step, "stowed (a fresh animator)")
    clip(f"slot{k}_off", cfg(0, 0, acq, 0, 0, 0), step, "stowed; a stow shorter than a step comes back deaf")
    clip(f"slot{k}_paused", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed through the pause")
    clip(f"slot{k}_armed", cfg(1, 0, acq, 0, 1, 0), step, "Armed 1 at full size — the ring rule reads it one frame late")
    clip(f"slot{k}_armed_collapsed", cfg(1, 0, collapsed, 0, 1, 0), step, "Armed 1 collapsed: holds no rejections while a sweep runs")
    clip(f"slot{k}_sweepshut", cfg(1, 0, collapsed, 1, 0, 0), step, "Open 1, flag shut, base scale: the front's own re-rejection step")
    clip(f"slot{k}_sweep_cfg", cfg(1, 1, collapsed, 1, 0, 0, front=1), None, "Open 1, Front 1, flag up, base scale: the growing cube's constant part")
    clip(f"slot{k}_front_scale", {f"{B}/Transform.m_LocalScale.{ax}": fmt(per_m) for ax in ("x", "y", "z")},
         None, "× Sweep: the cube at the front (the face once the sweep is over)")
    clip(f"slot{k}_open", cfg(1, 1, acq, 1, 0, 0), None, "Open 1 — the flag up at full size")
    clip(f"slot{k}_open_wait", cfg(1, 1, collapsed, 1, 0, 0), step, "Open 1 held a step at base scale: the partial-admission grace")
    latch = cfg(1, 0, hold, 0, 0, 0)
    latch.update({f"{me}/x": fmt(h), f"{me}/y": fmt(h), f"{me}/z": fmt(h)})
    clip(f"slot{k}_latch", latch, step, "flag shut + hold cube in one write; x,y,z parked at h (r² reads 3h²)")
    clip(f"slot{k}_hold", cfg(1, 0, hold, 0, 0, 0), None, "tracking configuration, payload off (outside the sphere)")
    clip(f"slot{k}_hold_burst", cfg(1, 0, hold, 0, 0, 1), None, "tracking configuration, payload on (inside the sphere)")
    if c["mode"] == "dwell":
        clip(f"slot{k}_hold_burst_silent", cfg(1, 0, hold, 0, 0, 1, buffer_on=0), None, "tracking configuration, payload on, buffer particle off (found inside by a silent sweep)")
    rec = cfg(1, 0, None, 0, 0, 0)
    body = ", ".join(f"{k2}: {v}" for k2, v in rec.items())
    o(f"  slot{k}_recycle:   # collapse for a step, restore for a step; stepped so nothing eases through the collapse")
    o(f"    seconds: {fmt(2 * step)}")
    o(f"    set: {{ {body} }}")
    o("    curves:")
    for ax in ("x", "y", "z"):
        o(f"      {B}/Transform.m_LocalScale.{ax}: {{ tangents: stepped, keys: [ [0, {fmt(collapsed)}], [{fmt(step)}, {fmt(acq)}], [{fmt(2 * step)}, {fmt(acq)}] ] }}")
    o(f"  # Slot {k} readout: c = 2h·V − h − r per axis (face proximity is linear from the +Z face; V is the box reading),")
    o("  # summed under the non-normalized Direct root into both the AAPs and Output's localPosition (metres, cage frame).")
    two_h = fmt(2 * h)
    bias = fmt(-h - r)
    clip(f"slot{k}_read_xp", {f"{me}/x": two_h, f"{O}/Transform.m_LocalPosition.x": two_h})
    clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{O}/Transform.m_LocalPosition.y": two_h})
    clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{O}/Transform.m_LocalPosition.z": two_h})
    clip(f"slot{k}_read_bias", {f"{me}/x": bias, f"{me}/y": bias, f"{me}/z": bias,
                                f"{O}/Transform.m_LocalPosition.x": bias,
                                f"{O}/Transform.m_LocalPosition.y": bias,
                                f"{O}/Transform.m_LocalPosition.z": bias})
    o(f"  # Slot {k} x² table: {N} segments over [−h, h]; each 1D tree blends the two nearest, a chord that overestimates by ≤ w²/4")
    o("  # inside the table. The readout spans [−h−r, h−r]: the bottom r metres clamp to the first threshold and read low, but any")
    o("  # x below −h already puts r² at h² or more, far outside the burst radius, so the inward bias holds where it matters.")
    for i in range(N + 1):
        t = -h + 2 * h * i / N
        clip(f"slot{k}_sq_{i}", {f"{me}/r2": fmt(t * t)})


def document(overrides=None):
    """The controller.yaml text for CONFIG updated by `overrides`, plus a facts dict."""
    c = dict(CONFIG)
    c.update(overrides or {})
    lint(c)
    K = c["K"]
    ks = list(range(1, K + 1))
    P = c["prefix"]
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    L = []
    o = L.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o(f"# contact-radar: {K} per-sender slots, mode {c['mode']}, tags {c['tags']}, 3 face-proximity boxes each.")
    if c["mode"] == "dwell":
        o(f"# Burst at r² < {fmt(rin2)} (R_in {c['burstRadius']} m), re-arm at r² > {fmt(rout2)} (R_out {c['rearmRadius']} m).")
    else:
        o(f"# Burst at r² < {fmt(rin2)} (R_in {c['burstRadius']} m); the slot releases at the burst and the")
        o(f"# acquisition cube face ({c['acqHalf']} m) is the re-arm surface.")
    o(f"# Cube half-extents: acquisition {c['acqHalf']} m, hold {c['holdHalf']} m; sender radius {c['senderRadius']} m; step dwell {c['stepSeconds']} s.")
    o(f"# At enable, load and distance-hide resume one slot at a time sweeps its cube out over {c['sweepSeconds']} s so hands")
    o("# already inside are admitted one by one (the expanding front); loud from the toggle, silent from a load or a resume.")
    o("# Per-client: every copy of the avatar senses on its own client (receivers localOnly 0);")
    o("# one synced bit (the enable) and nothing else crosses the wire. generate.py's docstring")
    o("# carries the mechanism; the README carries the traps and the measurements.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root          # paths bind against the module prefab root (VRCFury FullController seam)")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")
    o("parameters:")
    o(f"  {c['enable']}: {{ type: bool, default: true, vrc: {{ synced: true, saved: false }} }}  # the Toggle; off is the reset")
    o("  IsAnimatorEnabled: { type: bool, default: true }   # VRC built-in: false one frame before a distance-hide halts the animator")
    o(f"  {P}/One: {{ type: float, default: 1, scratch: true }}   # constant direct weight, never driven")
    o("  # The sweep (written only by the Sweep layer): Sweeping collapses every Armed slot, Silent picks the no-puff")
    o("  # endpoint, Sweep is the front half-extent (m), SweepBase the front the current sweeper's ramp started from.")
    o(f"  {P}/Sweeping: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/Silent: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/Sweep: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepBase: {{ type: float, aap: true, scratch: true }}")
    for k in ks:
        me = slot_name(c, k)
        o(f"  # Slot {k}: receiver floats (never a clip), the readout AAPs, and the three protocol flags.")
        for ax in ("X+", "Y+", "Z+"):
            o(f"  {me}/{ax}: float")
        for ax in ("x", "y", "z", "r2"):
            o(f"  {me}/{ax}: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Open: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Armed: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Front: {{ type: float, aap: true, scratch: true }}   # 1 while this slot's cube rides the front")
    o("")
    o("layers:")
    for k in ks:
        emit_layer(o, c, k, ks)
    emit_sweep_layer(o, c, ks)
    o("")
    o("clips:")
    for k in ks:
        emit_clips(o, c, k)
    emit_sweep_clips(o, c)
    facts = {"K": K, "mode": c["mode"], "receivers": 3 * K, "syncedBits": 1,
             "acqScale": 2 * c["acqHalf"] / c["boxSize"], "holdScale": 2 * c["holdHalf"] / c["boxSize"]}
    return "\n".join(L) + "\n", facts


def check_files(overrides, here, prefab):
    """The prefab surface no compile or gate reads: slot count, receiver tags and
    flags, the box size the coefficients assume, the enable on globalParams, and
    the two World.prefab pins on Cage. Reads the prefab YAML textually; a field
    it cannot find is a FAIL, never a pass."""
    c = dict(CONFIG)
    c.update(overrides or {})
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond
        return cond

    path = os.path.join(here, prefab)
    if not os.path.exists(path):
        print("  FAIL " + prefab + " is missing")
        return False
    body = open(path, encoding="utf-8").read()
    docs = body.split("--- !u!")
    names = re.findall(r"^  m_Name: (Slot\d+)$", body, re.M)
    assert_(len(names) == c["K"], f"{prefab}: {len(names)} Slot GameObjects == K {c['K']}")
    recv = [d for d in docs if "collisionTags:" in d and "receiverType:" in d]
    assert_(len(recv) == 3 * c["K"], f"{prefab}: {len(recv)} receivers == 3K")
    params = []
    for d in recv:
        tags = re.findall(r"^  - (\S+)$", d.split("collisionTags:")[1].split("allowSelf")[0], re.M)
        assert_(tags == c["tags"], f"receiver tags {tags} == {c['tags']}")
        for fld, want in (("allowSelf", "0"), ("localOnly", "0"), ("useFaceProximity", "1"),
                          ("receiverType", "2"), ("shapeType", "2")):
            m = re.search(rf"^  {fld}: (\S+)$", d, re.M)
            assert_(m is not None and m.group(1) == want, f"receiver {fld} == {want}")
        m = re.search(r"^  size: \{x: (\S+), y: (\S+), z: (\S+)\}$", d, re.M)
        assert_(m is not None and all(float(v) == c["boxSize"] for v in m.groups()),
                f"receiver size == boxSize {c['boxSize']} on every axis")
        m = re.search(r"^  parameter: (\S+)$", d, re.M)
        param = m.group(1) if m else None
        params.append(param)
        # The box's rotation is the one hand-maintained fact the readout coefficients rest on: the
        # +Z face must be the cage's +X / +Y / +Z face for the axis its parameter names.
        go = re.search(r"^  m_GameObject: \{fileID: (\d+)\}$", d, re.M)
        tr = next((t for t in docs if t.startswith("4 &") and go is not None
                   and re.search(rf"^  m_GameObject: \{{fileID: {go.group(1)}\}}$", t, re.M)), None)
        rot = re.search(r"^  m_LocalRotation: \{x: (\S+), y: (\S+), z: (\S+), w: (\S+)\}$", tr or "", re.M)
        want = AXIS_ROTATION.get(param.rsplit("/", 1)[-1] if param else "")
        got = tuple(float(v) for v in rot.groups()) if rot else None
        assert_(want is not None and got is not None and all(abs(a - b) < 1e-4 for a, b in zip(got, want)),
                f"receiver {param}: box rotation {got} faces its axis")
    ok = check_rig(assert_, c, docs) and ok
    expect = sorted(f"{c['prefix']}/Slot{k}/{ax}" for k in range(1, c["K"] + 1) for ax in ("X+", "Y+", "Z+"))
    assert_(sorted(p or "" for p in params) == expect, f"receiver parameters are exactly {c['prefix']}/Slot1..{c['K']}/X+ Y+ Z+, one each")
    ok = check_seam(assert_, c, here, body) and ok
    # The two world pins: exactly two constraint sources point at THIS entry's assets/World.prefab, at
    # zero offset — a nonzero per-source offset is multiplied by the avatar's scale factor in-client.
    # Unity's YAML writer wraps long lines, so the pin's `type: 3}` tail may sit on the next line.
    pins = re.findall(r"SourceTransform: \{fileID: \d+, guid: ([0-9a-f]{32}),\s*type: 3\}\n\s+Weight: \S+\n\s+ParentPositionOffset: \{x: (\S+), y: (\S+), z: (\S+)\}\n\s+ParentRotationOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", body)
    world_guid = meta_guid(os.path.join(here, "assets", "World.prefab"))
    assert_(len(pins) == 2 and all(p[0] == world_guid for p in pins),
            f"exactly two constraint sources point at assets/World.prefab (the rotation and scale pins on Cage): {len(pins)}")
    assert_(all(float(v) == 0 for p in pins for v in p[1:]), "both World pins carry zero source offsets")
    print("OK" if ok else "FAILED")
    return ok


def check_rig(assert_, c, docs):
    """The hierarchy facts the clip paths and the size knob rest on: every Slot sits under
    `Cage/Size`, shipped at uniform scale 1 (the consumer's knob, README §Knobs); each slot's
    `Burst` is inside the toggled `Payload` and its `Emit` is outside it, directly under `Output`
    — an `Emit` inside the wrapper would be disabled mid-burst and truncate it."""
    ok = True
    gos, trs = {}, {}
    for d in docs:
        m = re.match(r"(\d+) &(\d+)", d)
        if not m:
            continue
        if m.group(1) == "1":
            gos[m.group(2)] = re.search(r"^  m_Name: (.*)$", d, re.M).group(1)
        elif m.group(1) == "4":
            go = re.search(r"m_GameObject: \{fileID: (\d+)\}", d).group(1)
            father = re.search(r"m_Father: \{fileID: (\d+)\}", d).group(1)
            sc = re.search(r"m_LocalScale: \{x: (\S+), y: (\S+), z: (\S+)\}", d).groups()
            trs[m.group(2)] = (go, father, tuple(float(v) for v in sc))

    def parent_name(tid):
        f = trs[tid][1]
        return gos.get(trs[f][0]) if f in trs else None

    size = [tid for tid, (go, _, _) in trs.items() if gos[go] == "Size"]
    ok = assert_(len(size) == 1 and parent_name(size[0]) == "Cage", "exactly one Size node, under Cage") and ok
    ok = assert_(len(size) == 1 and trs[size[0]][2] == (1.0, 1.0, 1.0), "Size ships at uniform scale 1") and ok
    slots = [tid for tid, (go, _, _) in trs.items() if re.fullmatch(r"Slot\d+", gos[go])]
    ok = assert_(len(slots) == c["K"] and all(parent_name(t) == "Size" for t in slots), "every Slot is a child of Size") and ok
    for name, want in (("Burst", "Payload"), ("Emit", "Output"), ("Payload", "Output")):
        nodes = [tid for tid, (go, _, _) in trs.items() if gos[go] == name]
        ok = assert_(len(nodes) == c["K"] and all(parent_name(t) == want for t in nodes), f"{c['K']} {name} nodes, each under {want}") and ok
    # The view-cull requirement: one Bounds node under Size, a MeshRenderer, scaled to the boundsHalf cube.
    bounds = [tid for tid, (go, _, _) in trs.items() if gos[go] == "Bounds"]
    ok = assert_(len(bounds) == 1 and parent_name(bounds[0]) == "Size", "exactly one Bounds node, under Size") and ok
    want = tuple([2.0 * c["boundsHalf"]] * 3)
    ok = assert_(len(bounds) == 1 and trs[bounds[0]][2] == want, f"Bounds scale == 2*boundsHalf on every axis ({want})") and ok
    bgo = trs[bounds[0]][0] if bounds else None
    has = any(d.startswith("23 &") and re.search(r"m_GameObject: \{fileID: " + str(bgo) + r"\}", d) for d in docs) if bgo else False
    ok = assert_(has, "Bounds carries a MeshRenderer") and ok
    return ok


# Receiver box rotation per axis: the box's local +Z must be the cage's named axis.
AXIS_ROTATION = {"X+": (0, 0.7071068, 0, 0.7071068), "Y+": (-0.7071068, 0, 0, 0.7071068), "Z+": (0, 0, 0, 1)}


def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def check_seam(assert_, c, here, body):
    """The FullController's silent surface: globalParams exactly the enable, and its two
    objRefs pointing at THIS folder's built/ — a component built by copying a configured one
    keeps the donor's objRef and silently runs the donor's controller."""
    ok = True
    gp = re.search(r"globalParams:\n((?:\s+- .*\n)*)", body)
    got = [ln.strip()[2:] for ln in gp.group(1).splitlines()] if gp else None
    ok = assert_(got == [c["enable"]], f"globalParams == [{c['enable']}] (got {got})") and ok
    refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 2\}", body)
    want = [meta_guid(os.path.join(here, "built", c["controller"] + ".controller")),
            meta_guid(os.path.join(here, "built", c["controller"] + "_Parameters.asset"))]
    ok = assert_(refs == want, f"FullController objRefs == built/{c['controller']} controller + params GUIDs (got {refs})") and ok
    return ok


def check_variant(overrides, here, prefab, base_prefab, base_config=None):
    """A prefab VARIANT's file holds only its overrides, so the receiver surface is the base
    prefab's and is checked there; what the variant file itself states is its source, the
    slot removals taking the base K down to this K, and its own FullController seam."""
    c = dict(CONFIG)
    c.update(overrides or {})
    b = dict(CONFIG)
    b.update(base_config or {})
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond
        return cond

    path = os.path.join(here, prefab)
    if not os.path.exists(path):
        print("  FAIL " + prefab + " is missing")
        return False
    body = open(path, encoding="utf-8").read()
    src = re.search(r"m_SourcePrefab: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 3\}", body)
    assert_(src is not None and src.group(1) == meta_guid(base_prefab), f"{prefab} is a variant of {os.path.basename(base_prefab)}")
    removed = re.search(r"m_RemovedGameObjects:\n((?:\s+- \{.*\n)*)", body)
    base_body = open(base_prefab, encoding="utf-8").read()
    names = []
    for fid in re.findall(r"fileID: (\d+)", removed.group(1) if removed else ""):
        m = re.search(rf"^--- !u!1 &{fid}\nGameObject:\n(?:.*\n)*?  m_Name: (\S+)$", base_body, re.M)
        names.append(m.group(1) if m else f"<{fid}>")
    want = sorted([f"Slot{i}" for i in range(c["K"] + 1, b["K"] + 1)] + ["Marker"] * c["K"])
    assert_(sorted(names) == want, f"removed GameObjects {sorted(names)} == the slots above K plus each kept slot's Marker ({want})")
    rc = re.search(r"m_RemovedComponents:\n((?:\s+- \{.*\n)*)", body)
    assert_(rc is not None and len(rc.group(1).splitlines()) == 1, "exactly one removed component (the inherited FullController)")
    ok = check_seam(assert_, c, here, body) and ok
    print("OK" if ok else "FAILED")
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check_files({}, HERE, "ContactRadar.prefab") else 1)
    text, facts = document({})
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml — mode {facts['mode']}, K={facts['K']}, {facts['receivers']} receivers, {facts['syncedBits']} synced bit")


if __name__ == "__main__":
    main()
