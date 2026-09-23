#!/usr/bin/env python3
"""contact-radar generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ in a mounting Editor —
the controller.yaml committed here is generated output and the repo gate holds
built/ to it, so hand-editing it desynchronises the document from both this
generator and the compiled controller. `--check` asserts the hand-maintained
prefab surface no compile or gate reads (README §Changing it).

What it builds: K per-sender "slots", one FX layer each. A slot is three
coincident face-proximity box receivers (X+, Y+, Z+ — four under `fourBox`,
below) plus a fourth coincident box, `Hit`, a Constant receiver riding the same
`allowOthers` flag and carrying no readout. The flag is
the latch: a sender whose overlap with a receiver began while the flag was shut
stays invisible to that receiver for the whole overlap, however the flag moves
later, and only a full exit and re-entry admits it (emulator-measured, README
§How it works). Exactly one slot is Open (flag up) at a time; the others are
Armed (flag shut) so hands already inside are blind to them. `Hit` reads 1 from
the collision step the slot admits a sender — a step before any Proximity value
exists, and 1 until the last sender it admitted leaves. The `Dedup` layer copies
it into `HitPrev` every frame, so `Hit > 0.5, HitPrev < 0.5` is the rising edge
and is exactly one animator frame wide at every frame rate: the Open slot
Latches on its OWN edge (flag shut, boxes expanded to the hold cube) and the
next Armed slot in ring order Opens in the same animator evaluation, reading the
latcher's stale Open and the same fresh edge, so the two land in one collision
step and the admission windows tile. The readings rung (every axis above zero)
stays as the fallback for an admission the Hit box missed and for a slot
standing on a stale Hit level (below); when neither fires, the self-open rung
recovers within one stepSeconds, the common path's floor and not a corner case.
The slots sit tilted, the cube's diagonal vertical, so a standing player's
stacked senders meet a face at staggered depths instead of one vertical plane
in one step (README §How it works); the readout lives in that frame and the
sphere is invariant under it. The latched
slot then reconstructs its hand's position exactly (box-tracker's readout,
three boxes and a configured sender radius — four boxes and a measured one
under `fourBox`) and computes r² = x²+y²+z² in a
piecewise-linear lookup; the burst fires when r² crosses the burst radius. The
zone is a sphere and nothing else: it is the one shape that is invariant under the
cube's tilt, so the readout frame never has to be undone in the tree.

A slot keeps its hand until the hand leaves the hold cube, and re-bursts each
time the hand crosses back inside the burst radius after retreating past the
re-arm radius. A released slot Recycles: its boxes collapse to near zero for
`stepSeconds` and restore with the flag shut, a fresh overlap episode that
rejects every hand still inside (measured), then it queues as Armed.

Dedup, and why a slot can admit a hand another slot already holds: the hold cube
is larger than the acquisition cube, so a tracked hand that retreats into the
band between the two faces and comes back is a fresh overlap for whichever slot
is Open, and a fast entry that jitters across a face can be admitted two or three
times over. Nothing in a per-slot latch can refuse that by itself. So the `Dedup`
layer also publishes `D/<j>_<k>/<ax>`, the difference of two slots' raw readings
on each axis, and a slot in `TrackOut` — the state reached only from `Latch`, so
only on a fresh admission — releases itself when every axis of that difference
is inside `dedupEpsilon` of zero against a slot already holding a sender. Two
coincident congruent boxes read one sender identically, so the difference is a
true zero rather than a small one (measured bit-identical in the shipping
client, near the origin and a kilometre from it). A slot that has settled —
reached the sphere, or the re-arm band after it — always wins, whatever its
index; between two fresh slots still in the shell the lower index wins, and
neither can release the other. `TrackBand` is `TrackOut` without those rungs: a
hand that re-arms in the band re-enters there, so the coincidence test never
re-runs for the life of a track, where two genuinely distinct senders could
drift within `dedupEpsilon` of each other and collapse to one slot. It writes
`Settled` like the two inside states do, because a fresh lower-index slot
yields only to a settled holder: a band holder that read as fresh would be
admitted a second time by a lower slot and both would burst on re-entry.

A stale `Hit` level, should one ever occur: a `Hit` box reading 1 with nothing
in its collision set. The candidate is a receiver the client stows and restores
around a hide — a stowed receiver writes 0 and on re-enable writes back the
value it held at stow, with nothing collected. This rig gives that no opening
of its own: nothing here stows a receiver, the flag being `allowOthers` and the
size a scale collapse, and the emulator's Enable cycle measured no such state.
Where one does stand, the cost is one step and never a hand: a genuine
admission raises no edge, so the slot latches on the readings rung a step later,
hands the ring on a step later, and the sweep's freeze rung below does not fire
for that one handoff, which keeps the old two-frame band. It clears the first
time that box sees a sender leave. Degradation to the pre-edge timing, not a
loss, and it is why the readings rung stays. Release never reads `Hit`, so a
stale level cannot recycle a slot either.

`fourBox` restores box-tracker's fourth receiver, `X-`, coincident with the
other three and rotated so its +Z face is the cage's -X face. The opposed pair
measures the sender's own radius rather than taking it from CONFIG: r =
h(X+ + X- - 1) and x = h(X+ - X-), from which y = 2h·Y+ - h·X+ - h·X- and z
likewise — every constant cancels, so the readout carries no bias term and the
burst origin is exact for a sender of any radius. The measurement is exported
per slot as `<prefix>/Slot<k>/R` for a consumer that needs it. R, x, y, z and
Output's localPosition are all metres in the `Cage/Size` frame, so a consumer
wanting world metres multiplies by that node's scale (it ships at 1). `senderRadius` then buys nothing in the readout and stays only as the
reachability lints' assumed maximum sender radius. The rig the flag wants is
one the shipped prefab does not carry, so `--check` holds a fourBox consumer's
prefab to the fourth receiver.

Rules the emitted document keeps, each bought by a measurement or a doc line:
- Every step-spanning dwell is authored in seconds >= 2/60: at 60 fps and below
  every frame carries a collision step, but above it a step lands only every
  second or third frame, and a collapse or stow shorter than the longest gap
  between two steps can pass with none sampling it (docs/runtime.md §Contacts).
  `latchSeconds` is the one dwell sized larger, because it waits for readings
  that land a whole client step after the admission edge.
- Every slot state writes every flag (Open, Armed, Front, Held, Settled, Shut), the
  burst toggle and the
  payload toggle, zeros included: an AAP holds its last clip-written value and a scene binding holds
  whatever last wrote it (docs/runtime.md §Animator evaluation). One function,
  `cfg()`, is where that rule is enforced — every slot clip goes through it.
- The burst states carry the readout tree: the payload wrapper enables where Output
  sits on that frame — the buffer particle inside it is born there — and only a tree
  state keeps writing that position. One toggle serves both consumers: a buffer
  particle reads its enable edge, a mesh reads its level.
- `Cage/Size` is the consumer's static size knob (README §Knobs): scaling it scales
  the cubes, the readout, the sphere and every band together, so every lint below
  holds at any scale; only the sender-radius bias term scales when it should not —
  and under `fourBox` there is no such term, so the origin is exact at any scale.
- Latch parks x, y, z at (h, -h, -h) so the first r² computed in TrackOut is
  3h², far outside the sphere, and holds until its own readings arrive (its Hit
  edge fires a step before them) or `latchSeconds` passes with none, in which
  case it recycles: the guard is the state sequence, no settle AAP. The readings
  rung is listed before the exit-time rung, and that ordering — not the duration
  — is what survives a hitch frame longer than the whole wait.
- Timed dwells are plain clips, never a curve inside a Direct tree (the tree's
  duration is data — docs/animator-schema.md §motions).
- Recycle's collapse/restore takes stepped tangents; a bare curve eases.
- The parameter driver lives only in Disabled (off-state hygiene, localOnly false:
  every client zeroes its own receiver floats).
- An admission can land on some of a slot's coincident boxes and not the
  others when the overlap begins on the very frame the slot opens (measured), and
  a slot holding a partial reading can never satisfy the all-box Latch — so
  Open steps aside to Partial on any single reading and Recycles a step later if
  the rest never arrive. An Open slot that stalls blocks every admission on
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
- Two hands within one frame of front travel at the same Chebyshev radius
  co-latch, the same window as a normal admission; `sweepSeconds` and the frame
  time are the two knobs on that resolution.
- `CR/Silent` decides what a hand the front finds inside the sphere does: loud
  (from Disabled — the toggle) bursts as usual; silent (from Boot — a fresh
  animator — and from Paused — a distance-hide resume) lands in TrackInSilent
  (payload on, the buffer particle's GameObject off: marker, no puff). The
  Sweep layer's Idle state clears Silent when the front reaches the face, so a
  hand that crosses in after the sweep bursts loud. Exhaustion clears it too:
  when every slot holds and nothing rides the frozen front, the layer steps to
  Exhausted, Wait with Silent written 0, because a slot freed minutes later
  would otherwise resume the front silently and a hand it then found would
  never puff. Its Silent 0 becomes readable only the frame after the last
  resident's own silent-or-loud choice, so that resident stays silent. The cost is that a resident the frozen front had not reached
  bursts loud when a freed slot finally reaches it.
- Boot is the default state and is entered only by a fresh animator (load,
  manual hide/show, mirror clones); Disabled is entered only by the toggle.
- Paused is entered from every state on `IsAnimatorEnabled` false, VRChat's
  one-frame pre-halt signal for a distance-hide (docs/runtime.md §Parameters
  carries the citation; view cull gives no signal, so the README asks the
  installer for renderer bounds that cover the working volume). Its clip collapses the boxes; on resume the rig passes through
  Paused, Armed (collapsed) and SweepShut at front 0 before anything grows, so
  whatever the receivers did during the pause is discarded and the present
  hands are re-acquired from scratch, silently.
- The five sweep AAPs have exactly one writer, the `Sweep` layer, whose every
  state writes all five: a WD-ON state reverts any AAP it does not write to its
  default (measured on this rig — a 1D-tree Armed state dropped `Sweeping` to 0
  within a frame), so a value that must persist across a state is written back
  to itself through a direct child weighted by its own value. Slot layers read
  them and report `Slot<k>/Front` (1 in their Sweep state) for the layer to
  ramp on.
- The handoff leaves no blind band, and that takes both halves. `Ramp -> Wait`
  fires on the sweeping slot's own Hit edge, so the front freezes on the frame
  the slot latches rather than a frame after its Front flag drops; and the
  successor's shut cube scales off `SweepPrev`, last frame's front, so it
  appears at exactly the size that just admitted instead of at a front that has
  already moved on. A sender at that exact size was admitted by the predecessor
  and is re-rejected by the coincident shut cube, which is the Recycle idiom.
  The freeze needs the edge, so a handoff whose Hit box was missed, or whose
  slot stood on a stale level, still costs the old two frames of band.
  Idle parks SweepPrev at acqHalf, so it is gated on every slot's Shut flag and
  listed after the freeze rungs: ending the sweep on the last handoff's own
  frame would resize the successor's shut cube out from under it. Wait holds
  SweepPrev off itself, never off Sweep: on Wait's first frame Sweep already
  reads the frozen front, one frame past the size that admitted, and copying it
  in would grow the successor's shut cube by one frame of travel on its second
  shut frame, with the flag then rising at that size — a band one frame of
  travel wide, rejected stickily, at every handoff.
- The `Ramp` state is a Direct tree whose duration is data: the ramp clip
  carries the timing and every other child is one frame long, which stretches
  the ramp by at most the sum of those children's weights over 60·sweepSeconds.

The boundary: `Cage/Size/Boundary` holds one unit mesh, `Sphere` (radius 1),
written by `--mesh` into assets/. The Sweep layer — the one layer with exactly
one state live at all times — writes its scale (R,R,R) and MeshRenderer enable
in every state, so the drawn surface is the configured burst surface by
construction, only while the toggle is on. `Boundary` ships inactive:
activating it is the consumer's opt-in, and its material the swap point.

Fragment mode: `document(overrides)` returns the document text and a facts
dict, the door a venue's owned copy regenerates through at its own CONFIG. A
key CONFIG does not carry is refused there, so a consumer still passing a key
this generator has since dropped fails at the door instead of being accepted
silently and built at the default.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "controller": "ContactRadar_Fx",
    "K": 4,                     # slots; each is one layer and four receivers (five under fourBox)
    "tags": ["HandR"],
    "acqHalf": 1.2,             # acquisition cube half-extent, m; at Cage/Size scale 1
    "holdHalf": 1.3,            # hold cube half-extent, m — h in the readout
    "burstRadius": 1.0,         # R_in, m
    "rearmRadius": 1.1,         # R_out, m
    "fourBox": False,           # add the X- receiver and measure r per sender instead of assuming it (needs a 4-box prefab)
    "senderRadius": 0.05,       # r, m — the hand sender's radius; a capsule reads as a constant bias.
                                #   Under fourBox the readout measures r instead, and this is only the lints' assumed maximum
    "stepSeconds": 0.035,       # every step-spanning dwell; >= 2 collision steps
    "latchSeconds": 0.10,       # Latch's bounded wait for the readings, which land one client step after the admission
    "dedupEpsilon": 0.004,      # the coincidence band on a [0, 1] reading: two slots this close on every axis are holding one sender.
                                #   Coincident receivers read one sender bit-identically in the client, so this is not sized
                                #   against readout noise; it covers a one-step skew between the two slots' readings on the
                                #   admission frame, and two real hands are still far outside its ball (the lint bounds it)
    "sweepSeconds": 2.0,        # the front's travel time from 0 to acqHalf at enable, load and resume; resolution = front travel per collision step
    "lookupSegments": 16,       # x² table resolution over [-h, h]
    "epsilon": 1e-5,            # the any-box loss floor
    "boxSize": 1.0,             # the receiver box `size` on every axis; the Boxes scale multiplies it
    "prefix": "CR",             # internal param namespace; never published
    "enable": "ContactRadar/Enable",
    "enableDefault": True,      # the enable parameter's default; False loads quiet (the prefab Toggle's default must agree)
}


# The acquisition cube is tilted so its body diagonal is world-vertical: every face sits at the same
# elevation (asin(1/sqrt3) = 35.26 deg) 120 deg apart in azimuth, so a standing player's stacked senders
# (head, mouth, hips, hands) meet a face at staggered depths instead of crossing one vertical plane in a
# single collision step. Unity's Quaternion.FromToRotation((1,1,1), up), (x, y, z, w). Each Slot<k> carries
# it and each Output its inverse; `check_rig` holds both, and every owned copy carries it by hand.
TILT = (-0.325058, 0.0, 0.325058, 0.888074)
TILT_INV = (0.325058, 0.0, -0.325058, 0.888074)


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def fmt(v):
    return format(float(v), ".9g")


def axes(c):
    """A slot's receiver axes. fourBox appends the opposed X- box the sender radius is measured from."""
    return ("X+", "Y+", "Z+", "X-") if c["fourBox"] else ("X+", "Y+", "Z+")


def receivers(c):
    """Every receiver a slot carries: the face-proximity axis boxes plus `Hit`, the coincident
    Constant box on the same allowOthers flag. `Hit` reads 1 from the step the slot admits a
    sender, a step before any Proximity value, and is the latch's edge source; it carries no
    face and no readout, so it is an axis to the flag, the stow and the Disabled driver and to
    nothing else."""
    return axes(c) + ("Hit",)


def lint(c):
    if not isinstance(c["fourBox"], bool):
        refuse("fourBox must be a bool — it selects the rig, not a box count")
    if c["fourBox"] and c["senderRadius"] <= 0:
        refuse("senderRadius must be > 0 under fourBox — the readout measures r per sender, but the reachability lints "
               "below still size the cube against an assumed maximum sender radius, and 0 claims the whole cube is usable")
    if c["K"] < 2:
        refuse("K must be >= 2 — one slot has nothing to hand off to")
    if c["holdHalf"] < c["acqHalf"]:
        refuse("holdHalf must be >= acqHalf — the latch expands, never shrinks")
    if c["burstRadius"] + c["senderRadius"] >= c["acqHalf"]:
        refuse("burstRadius + senderRadius must be < acqHalf — the burst must be reachable inside the cube")
    if c["rearmRadius"] <= c["burstRadius"]:
        refuse("rearmRadius must be > burstRadius")
    if c["rearmRadius"] + c["senderRadius"] >= c["acqHalf"]:
        refuse("rearmRadius + senderRadius must be < acqHalf — a re-arm must be reachable on axis")
    if c["stepSeconds"] < 2 / 60:
        refuse("stepSeconds must be >= 2/60 — every frame at 60 fps or below carries a collision step, but above 60 fps a step "
               "lands only every second or third frame and the longest gap between two is one step period plus one frame, just "
               "under 2/60 s; a dwell shorter than that gap can open and close with no step sampling it")
    if c["latchSeconds"] < 2 * c["stepSeconds"]:
        refuse("latchSeconds must be >= 2*stepSeconds — Latch waits for the readings, which land one client step after the "
               "admission, and below 60 fps a step is as long as the frame: up to 40 ms at a jittery 30 fps")
    if c["dedupEpsilon"] <= 0:
        refuse("dedupEpsilon must be > 0 — a float transition condition compares greater or less and never equal, so a "
               "zero-width band makes every dedup rung unfireable and two slots holding one sender both keep it")
    if 2 * c["holdHalf"] * c["dedupEpsilon"] >= c["senderRadius"]:
        refuse("2*holdHalf*dedupEpsilon must be < senderRadius — one unit of a face-proximity reading is 2*holdHalf metres, so "
               "that product is the dedup ball's radius in metres, and a ball as large as a sender releases two distinct "
               "senders' slots down to one")
    if c["sweepSeconds"] * 60 < 4.2:
        refuse("sweepSeconds is too short — the front (which runs 5% past the face) would cross more than a quarter of the cube per collision step")
    if 2 * c["holdHalf"] > 6:
        refuse("2*holdHalf exceeds the SDK's serialized box limit (6 m) — a sanity bound on the working volume")
    if c["lookupSegments"] < 4:
        refuse("lookupSegments must be >= 4")
    if "/" in c["prefix"] or not c["prefix"]:
        refuse("prefix must be a bare segment")
    if c["enable"].count("/") != 1:
        refuse("enable must be one prefixed name (Module/Enable) — the wildcard for a bare name matches nothing")


def zone_conds(c, me):
    """The inside predicate (one AND list) and the outside rungs (a list of AND lists — an OR)."""
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    inside = [f"{me}/r2 less {fmt(rin2)}"]
    outside = [[f"{me}/r2 greater {fmt(rout2)}"]]
    return inside, outside


BOUNDARY = "Cage/Size/Boundary"


def boundary_bindings(c, on):
    """The unit sphere's scale and renderer enable — the drawn surface is the configured burst surface."""
    R = c["burstRadius"]
    d = {}
    for ax in ("x", "y", "z"):
        d[f"{BOUNDARY}/Sphere/Transform.m_LocalScale.{ax}"] = fmt(R)
    d[f"{BOUNDARY}/Sphere/MeshRenderer.m_Enabled"] = 1 if on else 0
    return d


def slot_name(c, k):
    return f"{c['prefix']}/Slot{k}"


def boxes_path(k):
    return f"Cage/Size/Slot{k}/Boxes"


def out_path(k):
    return f"Cage/Size/Slot{k}/Output"


def emit_clip(o, name, sets, seconds=None, comment=None):
    body = ", ".join(f"{k2}: {v}" for k2, v in sets.items())
    sec = f"seconds: {fmt(seconds)}, " if seconds else ""
    o(f"  {name}: {{ {sec}set: {{ {body} }} }}" + (f"   # {comment}" if comment else ""))


def emit_layer(o, c, k, ks):
    P = c["prefix"]
    en = c["enable"]
    me = slot_name(c, k)
    eps = c["epsilon"]
    inside, outside = zone_conds(c, me)
    inside = ", ".join(inside)
    acq = c["acqHalf"]
    ax4 = axes(c)
    all_pos = ", ".join(f"{me}/{ax} greater 0" for ax in ax4)
    # The admission edge. `Hit` is this slot's own Constant box: 1 from the step it admits a sender, a step before
    # any Proximity value, and 1 until the last admitted sender leaves. The Dedup layer copies it into HitPrev every
    # frame, so this pair is the rising edge and is exactly one animator frame wide at any frame rate.
    edge = f"{me}/Hit greater 0.5, {me}/HitPrev less 0.5"
    de = fmt(c["dedupEpsilon"])
    nde = fmt(-c["dedupEpsilon"])
    paused = "          - { to: Paused, when: [ IsAnimatorEnabled is false ] }   # the pre-halt frame: park before the animator stops"
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"

    def rungs():
        o(paused)
        o(off)

    def release():
        """Release is the axis floor and nothing else: the slot lets its sender go when any box's reading falls
        away. There is deliberately NO rung on Hit, though Hit looks like the cleaner signal (it is recomputed
        from the receiver's remaining records on every exit, so it does hold at 1 through a merged pair's first
        departure). A partial admission the Hit box missed latches on the readings rung with Hit still 0 and has
        to keep tracking; a `Hit less 0.5` rung would recycle it on its very first tracking frame. Hit is the
        latch's edge source and never the release."""
        for ax in ax4:
            o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")

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
    o(f"          - driver: {{ localOnly: false, set: {{ {', '.join(f'{me}/{ax}: 0' for ax in receivers(c))} }} }}")
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
        ring = [f"{me}/Armed greater 0.5"] + [f"{slot_name(c, m)}/Armed less 0.5" for m in between]
        # The edge twin: slot i latches on its own Hit edge a step before its readings land, so the readings rung
        # below would never see it Open and reading at once. This twin reads i's Open one frame stale (still 1) and
        # the same fresh edge, so it hands off in the SAME evaluation; next frame i's Open reads 0 and it is dead.
        pconds = [f"{si}/Open greater 0.5", f"{si}/Hit greater 0.5", f"{si}/HitPrev less 0.5"] + ring
        # Mid-sweep the source must be the slot riding the front (Front 1): SweepShut also writes Open 1 and carries no
        # latch rung, so without this an edge during its shut step would advance the ring with nothing latched.
        o(f"          - {{ to: SweepShut, when: [ {', '.join(pconds + [f'{si}/Front greater 0.5', f'{P}/Sweeping greater 0.5'])} ] }}   # ring on the edge: slot {i} latched mid-sweep")
        o(f"          - {{ to: Open, when: [ {', '.join(pconds + [f'{P}/Sweeping less 0.5'])} ] }}   # ring on the edge: slot {i} latched")
        conds = [f"{si}/Open greater 0.5"] + [f"{si}/{ax} greater 0" for ax in ax4] + ring
        o(f"          - {{ to: SweepShut, when: [ {', '.join(conds + [f'{P}/Sweeping greater 0.5'])} ] }}   # ring on the readings: slot {i} fired mid-sweep, nothing Armed between")
        o(f"          - {{ to: Open, when: [ {', '.join(conds + [f'{P}/Sweeping less 0.5'])} ] }}   # ring on the readings: slot {i} fired, nothing Armed between")
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j < k]
    conds += [f"{me}/Armed greater 0.5"]
    o(f"          - {{ to: SweepShut, when: [ {', '.join(conds + [f'{P}/Sweeping greater 0.5'])} ], exitTime: 1.0 }}   # self-open into the sweep: nothing Open, no lower Armed; re-checked only on a crossing")
    o(f"          - {{ to: Open, when: [ {', '.join(conds + [f'{P}/Sweeping less 0.5'])} ], exitTime: 1.0 }}   # self-open: nothing Open, no lower Armed; re-checked only on a crossing, so it costs at most one stepSeconds with nothing Open — the common-path recovery when the ring's one-frame handoff finds no taker")
    o("      SweepShut:                   # the cube appears at the front SHUT for a step: everything inside it is re-rejected")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} sweep shut")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_sweepshut, directWeight: {P}/One }}")
    # SweepPrev, not Sweep: this cube must be the size the predecessor's flag-up cube last was when it could still
    # admit, which is one frame behind the live front by the time the admission is visible. Scaling off the live
    # front would leave a band the predecessor never reached and this shut cube already rejects — the blind band.
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/SweepPrev }}")
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
    o(f"          - {{ to: Latch, when: [ {edge} ] }}   # this slot's own admission edge, a step before its readings; the Sweep layer freezes the front on the same rung")
    o(f"          - {{ to: Latch, when: [ {all_pos} ] }}")
    for ax in ax4:
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    o(f"          - {{ to: Open, when: [ {P}/Sweep greater {fmt(acq)} ] }}   # the front reached the face: the sweep is over")
    o(f"          - {{ to: Open, when: [ {P}/Sweeping less 0.5 ] }}   # the Sweep layer went Idle on the frame this slot took the front (Idle parks Sweep exactly at the face)")
    o("      Open:                        # flag up at full size: only overlaps beginning now are admitted")
    o(f"        motion: {{ clip: slot{k}_open }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {edge} ] }}   # this slot's own admission edge: a step before the readings, one frame wide")
    o(f"          - {{ to: Latch, when: [ {all_pos} ] }}")
    for ax in ax4:
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
    o(f"          - {{ to: Latch, when: [ {edge} ] }}   # Partial writes Open 1, so it must latch on the edge the ring hands off on — near-dead, since the Hit box rises a step before any axis and Open would have taken it")
    o(f"          - {{ to: Latch, when: [ {all_pos} ] }}")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Latch:                       # flag shut + hold cube in one write; readout parked outside the zone; waits latchSeconds for the readings")
    o(f"        motion: {{ clip: slot{k}_latch }}")
    o("        transitions:")
    rungs()
    # The readings rung is listed FIRST deliberately, and the ordering — not latchSeconds — is what survives a
    # hitch: a frame longer than the whole wait makes both this rung and the exit-time rung eligible in the same
    # evaluation, and first-match takes this one. Do not reorder these two to "simplify" the ladder.
    o(f"          - {{ to: TrackOut, when: [ {all_pos} ] }}")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }   # an edge whose readings never came (an admission the axis boxes missed): release, as Partial does")
    o("      TrackOut:                    # readout live, payload off; outside the burst radius. Entered only from Latch, so the dedup rungs below run on a FRESH admission and never again")
    emit_tree(o, c, k, hold=f"slot{k}_hold")
    o("        transitions:")
    rungs()
    # Dedup: this slot has just latched, and another slot is already holding a sender at the same point. The
    # coincidence test is on the raw readings' difference (the D tree's AAPs), which is bit-exact for two
    # coincident congruent boxes reading one sender. A SETTLED holder (inside the sphere, or in the band after
    # it) always wins, whatever its index; between two fresh slots still in the shell the lower index wins, so
    # the two never release each other. Listed ahead of the release and zone rungs: the readings this test reads
    # land a frame before r² becomes real, and first-match order is what keeps a duplicate from bursting on its
    # way out.
    for j in ks:
        if j == k:
            continue
        sj = slot_name(c, j)
        lo, hi = min(j, k), max(j, k)
        dconds = []
        for ax in ax4:
            dconds.append(f"{P}/D/{lo}_{hi}/{ax} greater {nde}")
            dconds.append(f"{P}/D/{lo}_{hi}/{ax} less {de}")
        dconds.append(f"{sj}/Held greater 0.5")
        why = f"slot {j} holds this point"
        if j > k:
            dconds.append(f"{sj}/Settled greater 0.5")
            why = f"slot {j} holds this point and has settled (a higher index yields only to that)"
        o(f"          - {{ to: Recycle, when: [ {', '.join(dconds)} ] }}   # dedup: {why}")
    release()
    o(f"          - {{ to: TrackIn, when: [ {inside}, {P}/Silent less 0.5 ] }}")
    o(f"          - {{ to: TrackInSilent, when: [ {inside}, {P}/Silent greater 0.5 ] }}   # found inside by a silent sweep: marker, no puff")
    o("      TrackIn:                     # inside the burst radius; the payload is on (one burst per entry, a marker visible throughout)")
    emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
    o("        transitions:")
    rungs()
    release()
    for conds in outside:
        o(f"          - {{ to: TrackBand, when: [ {', '.join(conds)} ] }}")
    o("      TrackInSilent:               # inside the burst radius with the buffer particle held off: the marker rides, nothing puffs")
    emit_tree(o, c, k, hold=f"slot{k}_hold_burst_silent")
    o("        transitions:")
    rungs()
    release()
    for conds in outside:
        o(f"          - {{ to: TrackBand, when: [ {', '.join(conds)} ] }}")
    o("      TrackBand:                   # retreated past the re-arm radius, still held and settled: TrackOut's rungs without dedup, so a re-arm never re-runs the coincidence test")
    emit_tree(o, c, k, hold=f"slot{k}_hold_band")
    o("        transitions:")
    rungs()
    release()
    o(f"          - {{ to: TrackIn, when: [ {inside}, {P}/Silent less 0.5 ] }}")
    o(f"          - {{ to: TrackInSilent, when: [ {inside}, {P}/Silent greater 0.5 ] }}   # a silent sweep's endpoint survives a re-arm inside the band")
    o("      Recycle:                     # collapse a step, restore a step, flag shut: every hand inside is re-rejected")
    o(f"        motion: {{ clip: slot{k}_recycle }}")
    o("        transitions:")
    rungs()
    o("          - { to: Armed, when: [], exitTime: 1.0 }")
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], Armed: [30, 360], SweepShut: [-210, 360], Sweep: [-210, 450], Open: [30, 450], Partial: [270, 450], Latch: [30, 540], TrackOut: [-210, 630], TrackIn: [270, 630], TrackInSilent: [510, 630], TrackBand: [30, 630], Recycle: [30, 720] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_sweep_layer(o, c, ks):
    """The one writer of the five shared sweep AAPs. Every state writes all five — a WD-ON state
    reverts any AAP it does not write to its default (measured on this rig), so a value that
    must persist across a state is written back to itself through a direct child weighted by
    its own value. SweepPrev is the same idiom read one frame late on purpose: in Ramp a child
    weighted by Sweep writing 1 lands Sweep(F-1) in it, which is the size the last admitting
    flag-up cube had and therefore the size the next slot's shut cube must appear at. Wait holds
    it off itself (weight SweepPrev): Wait is entered on the admission frame, when Sweep already
    reads the frozen front one frame past that size, and a copy there would hand the successor a
    cube one frame of travel too large on its second shut frame."""
    P = c["prefix"]
    en = c["enable"]
    acq = c["acqHalf"]
    fronts_down = ", ".join(f"{slot_name(c, k)}/Front less 0.5" for k in ks)
    # The successor's shut cube reads SweepPrev, and Idle's clip writes SweepPrev = acqHalf. So Idle may not be
    # entered while any slot is still in SweepShut: on the last handoff of a sweep the front has already passed
    # the face, both this layer's Idle rung and the freeze rung are eligible, and an Idle that wins clobbers
    # SweepPrev to the full acquisition size under the cube that is reading it — the shut cube then appears at
    # the face and re-rejects everything inside it, including senders the sweep never reached. Slot<k>/Shut is
    # 1 only in slot<k>_sweepshut, so this holds the front parked until that step is over.
    shut_down = ", ".join(f"{slot_name(c, k)}/Shut less 0.5" for k in ks)
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
    o("    # Sweep (the front half-extent, m), SweepBase (where the current sweeper's ramp started) and SweepPrev (last frame's")
    o("    # front, which the next slot's shut cube rides). Slot layers read these")
    o("    # and never write them; each slot reports its own Front flag (1 in its Sweep state) for this layer to ramp on.")
    o("    # Its second job: every state writes the Boundary meshes' scale and renderer enable (one state is always live here).")
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
    # Exhaustion: every slot HOLDS (Held 1, written from TrackOut on), so nothing can ride the front. The last
    # resident's own silent-or-loud choice reads r², which its TrackOut tree computes from the readout AAPs one
    # frame after it writes them: the choice lands two frames after Held is visible. Silent must still read 1 on
    # that frame, so the clear takes two hops: Wait -> Exhausting (Wait's tree, Silent held) on every Held, then
    # Exhausting -> Exhausted on the choice's own frame, so its Silent 0 is readable only the frame after. Gating on
    # "nothing Armed, Front, Open or Shut" instead fires a frame earlier still and the last resident bursts loud
    # (measured). Silent > 0.5 because a loud sweep has nothing to clear. Ramp -> Wait on the fronts-down rung is
    # what brings an exhausted sweep here.
    all_held = ", ".join(f"{slot_name(c, k)}/Held greater 0.5" for k in ks)
    o("      Wait:                        # a sweep is pending or between slots: the front holds, SweepBase latches it, SweepPrev and Silent hold")
    hold_tree("Sweep wait", [("sw_sweeping", f"{P}/One"), ("sw_hold_sweep", f"{P}/Sweep"), ("sw_latch_base", f"{P}/Sweep"), ("sw_hold_prev", f"{P}/SweepPrev"), ("sw_hold_silent", f"{P}/Silent")])
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Idle, when: [ {P}/Sweep greater {fmt(acq)}, {shut_down} ] }}")
    for k in ks:
        o(f"          - {{ to: Ramp, when: [ {slot_name(c, k)}/Front greater 0.5 ] }}")
    o(f"          - {{ to: Exhausting, when: [ {P}/Silent greater 0.5, {all_held} ] }}   # every slot holds and nothing rides the frozen front: the silent sweep is over, whatever it never reached")
    o("      Exhausting:                  # Wait for one more frame: the last resident's inside choice reads Silent on this frame")
    hold_tree("Sweep exhausting", [("sw_sweeping", f"{P}/One"), ("sw_hold_sweep", f"{P}/Sweep"), ("sw_latch_base", f"{P}/Sweep"), ("sw_hold_prev", f"{P}/SweepPrev"), ("sw_hold_silent", f"{P}/Silent")])
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Exhausted, when: [ {all_held} ] }}")
    o(f"          - {{ to: Wait, when: [], exitTime: 1.0 }}   # a slot freed on this very frame: back to Wait, still silent")
    o("      Exhausted:                   # Wait with Silent cleared: a slot freed later resumes the front loud")
    hold_tree("Sweep exhausted", [("sw_exhausted", f"{P}/One"), ("sw_hold_sweep", f"{P}/Sweep"), ("sw_latch_base", f"{P}/Sweep"), ("sw_hold_prev", f"{P}/SweepPrev")])
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Idle, when: [ {P}/Sweep greater {fmt(acq)}, {shut_down} ] }}")
    for k in ks:
        o(f"          - {{ to: Ramp, when: [ {slot_name(c, k)}/Front greater 0.5 ] }}")
    o("      Ramp:                        # a slot's flag is up: the front grows from SweepBase at the configured speed")
    hold_tree("Sweep ramp", [("sw_ramp", f"{P}/One"), ("sw_hold_sweep", f"{P}/SweepBase"), ("sw_hold_base", f"{P}/SweepBase"), ("sw_hold_prev", f"{P}/Sweep"), ("sw_hold_silent", f"{P}/Silent")])
    o("        transitions:")
    o(paused)
    o(off)
    for k in ks:
        # The freeze: the sweeping slot's admission edge, read the frame it latches — a frame before its Front flag
        # drops. Ramp's clip is not sampled on the frame it leaves, so the front stops at the size that admitted,
        # and the successor's shut cube (× SweepPrev) appears at exactly that size. Without it the front advances
        # one more frame and leaves a band no cube ever offered.
        # Listed BEFORE the Idle rung, not after: on the sweep's last handoff the front has already read past the
        # face, so both rungs are eligible in the same evaluation and first-match decides. Idle would end the sweep
        # on the admission frame and park SweepPrev at acqHalf, so the successor's shut cube — already entered on
        # the same evaluation — would appear at the full acquisition size instead of at the size that just
        # admitted, re-rejecting everything the front had not yet reached. The freeze wins; Idle gets the frame
        # after, once Shut is down.
        o(f"          - {{ to: Wait, when: [ {slot_name(c, k)}/Front greater 0.5, {slot_name(c, k)}/Hit greater 0.5, {slot_name(c, k)}/HitPrev less 0.5 ] }}   # slot {k} latched: freeze the front on the admission frame")
    o(f"          - {{ to: Idle, when: [ {P}/Sweep greater {fmt(acq)}, {shut_down} ] }}   # the face: the sweep is over, once no successor's shut cube is still reading SweepPrev")
    o(f"          - {{ to: Wait, when: [ {fronts_down} ] }}   # the sweeper latched a frame ago (its edge was missed) or stalled: hold the front for the next slot's shut step")
    o("      Idle:                        # no sweep: Armed slots at full size, the front parked at the face, loud")
    o("        motion: { clip: sw_idle }")
    o("        transitions:")
    o(paused)
    o(off)
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], Wait: [30, 360], Ramp: [270, 360], Exhausting: [-210, 360], Exhausted: [-210, 450], Idle: [30, 450] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_sweep_clips(o, c):
    P = c["prefix"]
    T = c["sweepSeconds"]
    acq = c["acqHalf"]
    reach = acq * 1.05   # the ramp aims a little past the face so `Sweep greater acqHalf` fires before it ends

    def clip(name, sets, seconds=None, comment=None):
        emit_clip(o, name, sets, seconds, comment)

    def full(sweeping, silent, sweep, base, shown):
        # SweepPrev = Sweep in every plain-clip state: each of them parks the front, so last frame's front is this
        # frame's. Only the two tree states, where the front moves, need the one-frame lag a × Sweep child gives.
        d = {f"{P}/Sweeping": sweeping, f"{P}/Silent": silent, f"{P}/Sweep": fmt(sweep),
             f"{P}/SweepBase": fmt(base), f"{P}/SweepPrev": fmt(sweep)}
        d.update(boundary_bindings(c, shown))
        return d

    o("  # Sweep layer: constants, and the self-copies a hold needs (weight = the AAP's own value, the clip writes 1).")
    o("  # Every constant clip also writes the Boundary meshes: scale = the burst surface, renderer on only for the configured shape while enabled.")
    clip("sw_boot", full(1, 1, 0, 0, 0), None, "a fresh animator: silent, front at 0")
    clip("sw_off", full(1, 0, 0, 0, 0), None, "the toggle off: loud, front at 0")
    clip("sw_paused", full(1, 1, 0, 0, 0), None, "a distance-hide: silent, front at 0")
    clip("sw_idle", full(0, 0, acq, 0, 1), None, "no sweep: the front parked at the face")
    sweeping = {f"{P}/Sweeping": 1}
    sweeping.update(boundary_bindings(c, 1))
    clip("sw_sweeping", sweeping, None, "the constant part of Wait and Ramp")
    exhausted = dict(sweeping)
    exhausted[f"{P}/Silent"] = 0
    clip("sw_exhausted", exhausted, None, "the constant part of Exhausted: Sweeping 1, Silent 0")
    clip("sw_hold_sweep", {f"{P}/Sweep": 1}, None, "× Sweep (Wait: hold) or × SweepBase (Ramp: the ramp's origin)")
    clip("sw_hold_prev", {f"{P}/SweepPrev": 1}, None, "× Sweep (Ramp): SweepPrev ← last frame's Sweep (a Direct weight reads its parameter one frame late; SweepPrev's default 0 makes the fill term vanish, so the read is exact); × SweepPrev (Wait, Exhausted): hold")
    clip("sw_latch_base", {f"{P}/SweepBase": 1}, None, "× Sweep: SweepBase ← Sweep")
    clip("sw_hold_base", {f"{P}/SweepBase": 1}, None, "× SweepBase: hold")
    clip("sw_hold_silent", {f"{P}/Silent": 1}, None, "× Silent: hold")
    o(f"  sw_ramp:   # × One: Sweeping 1 and the front's own travel, 0 → {fmt(reach)} m over {fmt(T)} s, linear, added to SweepBase")
    o(f"    seconds: {fmt(T)}")
    ramp_set = ", ".join(f"{k2}: {v}" for k2, v in sweeping.items())
    o(f"    set: {{ {ramp_set} }}")
    o("    curves:")
    o(f"      {P}/Sweep: {{ tangents: linear, keys: [ [0, 0], [{fmt(T)}, {fmt(reach)}] ] }}")


def ax_tag(ax):
    """The clip-name suffix for a receiver axis, the readout clips' spelling: X+ -> xp, X- -> xn."""
    return ax.replace("+", "p").replace("-", "n").lower()


def emit_dedup_layer(o, c, ks):
    """The one always-live layer: last frame's Hit per slot, and the pairwise difference of the raw
    readings the TrackOut dedup rungs compare against dedupEpsilon."""
    o("  - name: Dedup")
    o("    # One state, one tree, no transitions, and deliberately no Paused and no Disabled. A park state would revert")
    o("    # HitPrev to its default 0 while a stowed receiver's restored Hit sat at 1, and the resume frame would then")
    o("    # manufacture exactly the false rising edge this layer exists to make impossible. It needs no park in any case:")
    o("    # a non-normalized Direct tree writes every binding it carries every frame, so nothing here can revert.")
    o("    # Two jobs. HitPrev: last frame's Hit per slot, which with Hit is the admission edge — one animator frame wide")
    o("    # at any frame rate. D/<j>_<k>/<ax> = Slot<k>/<ax> - Slot<j>/<ax> for every pair and every axis, built from the RAW [0, 1]")
    o("    # receiver floats rather than the signed readout AAPs because a negative Direct weight clamps to 0; the signs")
    o("    # live in the clips, where they are free. Every parameter here defaults to 0, so the below-weight-1 rest fill")
    o("    # contributes nothing and both reads are exact at any weight sum.")
    o("    states:")
    o("      Live:")
    o("        motion:")
    o("          tree: direct")
    o("          name: Dedup")
    o("          normalized: false")
    o("          children:")
    for k in ks:
        o(f"            - {{ clip: hitprev_{k}, directWeight: {slot_name(c, k)}/Hit }}")
    for k in ks:
        for ax in axes(c):
            o(f"            - {{ clip: d_slot{k}_{ax_tag(ax)}, directWeight: {slot_name(c, k)}/{ax} }}")
    o("    default: Live")
    o("    layout:")
    o("      nodes: { Live: [30, 180] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_dedup_clips(o, c, ks):
    P = c["prefix"]
    o("  # Dedup layer: one clip per slot writing HitPrev at weight = that slot's Hit, and one per (slot, axis) carrying")
    o("  # every pair that slot is in — +1 where it is the pair's higher index, −1 where it is the lower — at weight = that")
    o("  # slot's own reading on that axis. One clip per (slot, axis) rather than one per (pair, axis, sign): the weight is")
    o("  # the same for every term it carries, and per D binding the children carrying it are still exactly the pair's two")
    o("  # slots, so the difference is the same arithmetic in a quarter of the children on a tree that runs every frame.")
    for k in ks:
        emit_clip(o, f"hitprev_{k}", {f"{slot_name(c, k)}/HitPrev": 1}, None, f"× Slot{k}/Hit")
    for k in ks:
        for ax in axes(c):
            sets = {}
            for j in ks:
                if j == k:
                    continue
                lo, hi = min(j, k), max(j, k)
                sets[f"{P}/D/{lo}_{hi}/{ax}"] = 1 if k == hi else -1
            emit_clip(o, f"d_slot{k}_{ax_tag(ax)}", sets, None, f"× Slot{k}/{ax}")


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
    if c["fourBox"]:
        o(f"            - {{ clip: slot{k}_read_xn, directWeight: {me}/X- }}")
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

    def cfg(active, flag, scale, opn, armed, payload_on, buffer_on=1, front=0, held=0, settled=0, shut=0):
        d = {f"{B}/GameObject.m_IsActive": active}
        for ax in receivers(c):
            d[f"{B}/{ax}/VRCContactReceiver.allowOthers"] = flag
        if scale is not None:
            for ax in ("x", "y", "z"):
                d[f"{B}/Transform.m_LocalScale.{ax}"] = fmt(scale)
        d[f"{me}/Open"] = opn
        d[f"{me}/Armed"] = armed
        d[f"{me}/Front"] = front
        # Held: this slot is holding a sender (every post-latch state). Settled: and that sender has reached the
        # sphere, or the re-arm band after it — every held state but TrackOut, the fresh one. The dedup rungs read
        # another slot's pair, so every state must write both — a state that wrote neither would leave a stale 1
        # standing and make a newcomer yield to a slot that has already released.
        # Shut: 1 in slot<k>_sweepshut alone, the one step this slot's cube is being scaled off SweepPrev. The
        # Sweep layer's Idle rungs read it across every slot and hold off while any of them is up, because Idle
        # parks SweepPrev at acqHalf and would resize that cube out from under the step that is reading it.
        d[f"{me}/Held"] = held
        d[f"{me}/Settled"] = settled
        d[f"{me}/Shut"] = shut
        d[payload] = payload_on
        d[buffer] = buffer_on
        return d

    def clip(name, sets, seconds=None, comment=None):
        emit_clip(o, name, sets, seconds, comment)

    o(f"  # Slot {k} configurations — every one writes the box stow, the flag on every receiver (Hit included), the scale, the six protocol flags, the payload toggle and the buffer toggle.")
    clip(f"slot{k}_boot", cfg(0, 0, acq, 0, 0, 0), step, "stowed (a fresh animator)")
    clip(f"slot{k}_off", cfg(0, 0, acq, 0, 0, 0), step, "stowed; a stow shorter than a step comes back deaf")
    clip(f"slot{k}_paused", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed through the pause")
    clip(f"slot{k}_armed", cfg(1, 0, acq, 0, 1, 0), step, "Armed 1 at full size — the ring rule reads it one frame late")
    clip(f"slot{k}_armed_collapsed", cfg(1, 0, collapsed, 0, 1, 0), step, "Armed 1 collapsed: holds no rejections while a sweep runs")
    clip(f"slot{k}_sweepshut", cfg(1, 0, collapsed, 1, 0, 0, shut=1), step, "Open 1, Shut 1, flag shut, base scale: the front's own re-rejection step")
    clip(f"slot{k}_sweep_cfg", cfg(1, 1, collapsed, 1, 0, 0, front=1), None, "Open 1, Front 1, flag up, base scale: the growing cube's constant part")
    clip(f"slot{k}_front_scale", {f"{B}/Transform.m_LocalScale.{ax}": fmt(per_m) for ax in ("x", "y", "z")},
         None, "× Sweep: the cube at the front (the face once the sweep is over)")
    clip(f"slot{k}_open", cfg(1, 1, acq, 1, 0, 0), None, "Open 1 — the flag up at full size")
    clip(f"slot{k}_open_wait", cfg(1, 1, collapsed, 1, 0, 0), step, "Open 1 held a step at base scale: the partial-admission grace")
    latch = cfg(1, 0, hold, 0, 0, 0)
    # Parked at (h, −h, −h): x at +h is the sentinel a consumer reads as "not yet tracking"; r² reads 3h².
    latch.update({f"{me}/x": fmt(h), f"{me}/y": fmt(-h), f"{me}/z": fmt(-h)})
    if c["fourBox"]:
        # The one frame before the first measurement lands: R carries the configured assumption
        # rather than zero. Outside a track R is 0, like x, y and z — no state writes it there.
        latch[f"{me}/R"] = fmt(r)
    clip(f"slot{k}_latch", latch, c["latchSeconds"], "flag shut + hold cube in one write; readout parked at (h, −h, −h) so r² reads 3h²; the wait spans one client step of readings")
    clip(f"slot{k}_hold", cfg(1, 0, hold, 0, 0, 0, held=1), None, "tracking configuration, payload off, fresh (outside the sphere, never yet inside it)")
    clip(f"slot{k}_hold_band", cfg(1, 0, hold, 0, 0, 0, held=1, settled=1), None, "tracking configuration, payload off, settled (the re-arm band)")
    clip(f"slot{k}_hold_burst", cfg(1, 0, hold, 0, 0, 1, held=1, settled=1), None, "tracking configuration, payload on (inside the sphere)")
    clip(f"slot{k}_hold_burst_silent", cfg(1, 0, hold, 0, 0, 1, buffer_on=0, held=1, settled=1), None, "tracking configuration, payload on, buffer particle off (found inside by a silent sweep)")
    rec = cfg(1, 0, None, 0, 0, 0)
    body = ", ".join(f"{k2}: {v}" for k2, v in rec.items())
    o(f"  slot{k}_recycle:   # collapse for a step, restore for a step; stepped so nothing eases through the collapse")
    o(f"    seconds: {fmt(2 * step)}")
    o(f"    set: {{ {body} }}")
    o("    curves:")
    for ax in ("x", "y", "z"):
        o(f"      {B}/Transform.m_LocalScale.{ax}: {{ tangents: stepped, keys: [ [0, {fmt(collapsed)}], [{fmt(step)}, {fmt(acq)}], [{fmt(2 * step)}, {fmt(acq)}] ] }}")
    two_h = fmt(2 * h)
    if c["fourBox"]:
        o(f"  # Slot {k} readout, four boxes: the opposed X pair measures the sender's radius instead of assuming it —")
        o("  # r = h·X+ + h·X− − h and x = h·X+ − h·X− (box-tracker's derivation), so y = 2h·Y+ − h·X+ − h·X− and z likewise;")
        o("  # every constant cancels out of x, y and z, leaving pure per-reading coefficients and a bias clip carrying only r.")
        o("  # Summed under the non-normalized Direct root into the AAPs, R and Output's localPosition (metres, Size frame).")
        pos, neg = fmt(h), fmt(-h)
        clip(f"slot{k}_read_xp", {f"{me}/x": pos, f"{me}/y": neg, f"{me}/z": neg, f"{me}/R": pos,
                                  f"{O}/Transform.m_LocalPosition.x": pos,
                                  f"{O}/Transform.m_LocalPosition.y": neg,
                                  f"{O}/Transform.m_LocalPosition.z": neg})
        clip(f"slot{k}_read_xn", {f"{me}/x": neg, f"{me}/y": neg, f"{me}/z": neg, f"{me}/R": pos,
                                  f"{O}/Transform.m_LocalPosition.x": neg,
                                  f"{O}/Transform.m_LocalPosition.y": neg,
                                  f"{O}/Transform.m_LocalPosition.z": neg})
        clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{O}/Transform.m_LocalPosition.y": two_h})
        clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{O}/Transform.m_LocalPosition.z": two_h})
        clip(f"slot{k}_read_bias", {f"{me}/R": neg}, None, "the measured radius is the only term left with a constant")
    else:
        o(f"  # Slot {k} readout: c = 2h·V − h − r per axis (face proximity is linear from the +Z face; V is the box reading),")
        o("  # summed under the non-normalized Direct root into both the AAPs and Output's localPosition (metres, cage frame).")
        bias = fmt(-h - r)
        clip(f"slot{k}_read_xp", {f"{me}/x": two_h, f"{O}/Transform.m_LocalPosition.x": two_h})
        clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{O}/Transform.m_LocalPosition.y": two_h})
        clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{O}/Transform.m_LocalPosition.z": two_h})
        clip(f"slot{k}_read_bias", {f"{me}/x": bias, f"{me}/y": bias, f"{me}/z": bias,
                                    f"{O}/Transform.m_LocalPosition.x": bias,
                                    f"{O}/Transform.m_LocalPosition.y": bias,
                                    f"{O}/Transform.m_LocalPosition.z": bias})
    o(f"  # Slot {k} x² table: {N} segments over [−h, h]; each 1D tree blends the two nearest, a chord that overestimates by ≤ w²/4")
    if c["fourBox"]:
        o("  # inside the table. The measured readout spans exactly [−h, h], so nothing clamps.")
    else:
        o("  # inside the table. The readout spans [−h−r, h−r]: the bottom r metres clamp to the first threshold and read low, but any")
        o("  # x below −h already puts r² at h² or more, far outside the burst radius, so the inward bias holds where it matters.")
    for i in range(N + 1):
        t = -h + 2 * h * i / N
        clip(f"slot{k}_sq_{i}", {f"{me}/r2": fmt(t * t)})


def config(overrides):
    """CONFIG updated by `overrides`; a key CONFIG does not carry is refused, since `c.update` would
    accept it silently and a consumer passing a key this generator has dropped would build at the
    default without a word."""
    unknown = sorted(set(overrides or {}) - set(CONFIG))
    if unknown:
        refuse(f"unknown CONFIG key(s) {unknown} — this generator's CONFIG has no such knob (a dropped key, or a typo); "
               f"the keys are {sorted(CONFIG)}")
    c = dict(CONFIG)
    c.update(overrides or {})
    return c


def document(overrides=None):
    """The controller.yaml text for CONFIG updated by `overrides`, plus a facts dict."""
    c = config(overrides)
    lint(c)
    K = c["K"]
    ks = list(range(1, K + 1))
    P = c["prefix"]
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    L = []
    o = L.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o(f"# contact-radar: {K} per-sender slots, tags {c['tags']}, {len(axes(c))} face-proximity boxes each plus a coincident Constant box `Hit`.")
    o("# The acquisition cube is tilted (diagonal vertical) on the prefab; the readout is in that frame and the sphere is invariant.")
    o(f"# Burst at r² < {fmt(rin2)} (R_in {c['burstRadius']} m), re-arm at r² > {fmt(rout2)} (R_out {c['rearmRadius']} m).")
    rtxt = (f"sender radius measured per slot from the X- box ({c['senderRadius']} m is the lints' assumed maximum)"
            if c["fourBox"] else f"sender radius {c['senderRadius']} m")
    o(f"# Cube half-extents: acquisition {c['acqHalf']} m, hold {c['holdHalf']} m; {rtxt}; step dwell {c['stepSeconds']} s, latch wait {c['latchSeconds']} s.")
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
    o(f"  {c['enable']}: {{ type: bool, default: {'true' if c['enableDefault'] else 'false'}, vrc: {{ synced: true, saved: false }} }}  # the Toggle; off is the reset")
    o("  IsAnimatorEnabled: { type: bool, default: true }   # VRC built-in: false one frame before a distance-hide halts the animator")
    o(f"  {P}/One: {{ type: float, default: 1, scratch: true }}   # constant direct weight, never driven")
    o("  # The sweep (written only by the Sweep layer): Sweeping collapses every Armed slot, Silent picks the no-puff")
    o("  # endpoint, Sweep is the front half-extent (m), SweepBase the front the current sweeper's ramp started from,")
    o("  # SweepPrev last frame's Sweep — the size the next slot's shut cube appears at, so the handoff leaves no band.")
    o(f"  {P}/Sweeping: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/Silent: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/Sweep: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepBase: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepPrev: {{ type: float, aap: true, scratch: true }}")
    for k in ks:
        me = slot_name(c, k)
        o(f"  # Slot {k}: receiver floats (never a clip), the readout AAPs, and the six protocol flags.")
        for ax in receivers(c):
            note = ("   # the coincident Constant box: 1 from the collision step this slot admits a sender, a step before any"
                    " Proximity value, and 1 until the last admitted sender leaves") if ax == "Hit" else ""
            o(f"  {me}/{ax}: float{note}")
        for ax in ("x", "y", "z", "r2"):
            o(f"  {me}/{ax}: {{ type: float, aap: true, scratch: true }}")
        if c["fourBox"]:
            o(f"  {me}/R: {{ type: float, aap: true, scratch: true }}   # the measured sender radius, m — the export a consumer reads")
        o(f"  {me}/HitPrev: {{ type: float, aap: true, scratch: true }}   # last frame's Hit (the Dedup layer's); with Hit it is the admission edge")
        o(f"  {me}/Open: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Armed: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Front: {{ type: float, aap: true, scratch: true }}   # 1 while this slot's cube rides the front")
        o(f"  {me}/Held: {{ type: float, aap: true, scratch: true }}   # 1 while this slot holds a sender: every state past Latch")
        o(f"  {me}/Settled: {{ type: float, aap: true, scratch: true }}   # 1 once the sender it holds has reached the sphere (inside it, or in the re-arm band after): a fresh lower-index slot yields to a settled holder")
        o(f"  {me}/Shut: {{ type: float, aap: true, scratch: true }}   # 1 for the one step this slot's cube appears shut at SweepPrev; the Sweep layer holds Idle off while it is up")
    o("  # The Dedup layer's differences: D/<j>_<k>/<ax> = Slot<k>/<ax> - Slot<j>/<ax> on the raw readings, for every pair")
    o("  # j < k and every axis. Two coincident congruent boxes read one sender identically, so a pair holding the same")
    o("  # sender reads 0 on every axis and a freshly latched slot recognises the duplicate. Each defaults to 0, which is")
    o("  # what makes the tree's below-weight-1 rest fill vanish and the difference exact.")
    for j in ks:
        for k in ks:
            if j >= k:
                continue
            for ax in axes(c):
                o(f"  {P}/D/{j}_{k}/{ax}: {{ type: float, aap: true, scratch: true }}")
    o("")
    o("layers:")
    for k in ks:
        emit_layer(o, c, k, ks)
    emit_sweep_layer(o, c, ks)
    emit_dedup_layer(o, c, ks)
    o("")
    o("clips:")
    for k in ks:
        emit_clips(o, c, k)
    emit_sweep_clips(o, c)
    emit_dedup_clips(o, c, ks)
    facts = {"K": K, "fourBox": c["fourBox"],
             "receivers": (len(axes(c)) + 1) * K, "syncedBits": 1,
             "acqScale": 2 * c["acqHalf"] / c["boxSize"], "holdScale": 2 * c["holdHalf"] / c["boxSize"]}
    return "\n".join(L) + "\n", facts


def check_files(overrides, here, prefab):
    """The prefab surface no compile or gate reads: slot count, receiver tags and
    flags, the box size the coefficients assume, the enable on globalParams, and
    the two World.prefab pins on Cage. Under fourBox the fourth receiver is part
    of that surface — the shipped prefab is three-box, so a fourBox consumer's own
    prefab is what this holds. Reads the prefab YAML textually; a field it cannot
    find is a FAIL, never a pass."""
    c = config(overrides)
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
    ok = check_receivers(assert_, c, docs, prefab) and ok
    ok = check_rig(assert_, c, here, docs) and ok
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


def check_receivers(assert_, c, docs, label):
    """Every slot's receivers over a RESOLVED document list: the count, the tags and protocol
    flags, the box size the readout coefficients assume, the node scale their coincidence rests
    on, one parameter each, and the rotation putting each face-proximity box's +Z face on the
    axis its parameter names. `Hit` is partitioned out and held to its own list: it is a Constant
    box, so its receiverType and useFaceProximity differ and it carries no face to assert a
    rotation against."""
    ax4 = axes(c)
    addx = (" \u2014 fourBox wants a fourth receiver X- in every slot's Boxes, coincident with X+ Y+ Z+ and rotated"
            " so its +Z face is the cage's -X face; duplicate the X+ node, turn it 180 degrees about Y and"
            f" point its parameter at {c['prefix']}/Slot<k>/X-") if c["fourBox"] else ""
    ok = True
    # Only the pattern's own receivers, told by parameter: a copy may carry receivers of its own elsewhere.
    pre = re.escape(c["prefix"])
    slots = [d for d in docs if "collisionTags:" in d and "receiverType:" in d
             and re.search(rf"^  parameter: {pre}/Slot\d+/\S+$", d, re.M)]
    # A copy brought forward from before the shared OnEnter gate was removed still carries its receiver: one more
    # coincident receiver against the cluster bug, on a parameter nothing declares, so the build leaves it unprefixed.
    ok = assert_(not any(re.search(rf"^  parameter: {pre}/Enter$", d, re.M) for d in docs),
                 f"no receiver on {c['prefix']}/Enter: the shared OnEnter gate was removed; delete the Gate node from this copy") and ok
    # `Hit` is told apart by its parameter suffix before the axis loop below reaches it: it is Constant, not
    # face proximity, so three of that loop's asserts would name the wrong want and a fourth (the rotation)
    # would look up an axis that does not exist.
    hit = [d for d in slots if re.search(rf"^  parameter: {pre}/Slot\d+/Hit$", d, re.M)]
    recv = [d for d in slots if d not in hit]
    addhit = (f" — every slot also wants the coincident Constant box Hit in its Boxes: duplicate X+, then set"
              f" receiverType 0, useFaceProximity 0 and point its parameter at {c['prefix']}/Slot<k>/Hit")
    ok = assert_(len(slots) == (len(ax4) + 1) * c["K"],
                 f"{label}: {len(slots)} slot receivers == {len(ax4) + 1}K ({len(ax4)} face-proximity boxes plus Hit, per slot)"
                 + addx + addhit) and ok
    def coincident(d, param, what):
        """The two facts dedup rests on past the size and the node scale: the shape sits ON its transform
        (a nonzero offset moves one box off its siblings while every field still reads right), and the node
        hangs under `Boxes` of the very `Slot<k>` its parameter names (a box filed under the wrong slot, or
        under a node of its own beside Boxes, is animated by the wrong clip and moves independently). Dedup
        decides two slots hold one sender by their readings being bit-identical, which is only true while
        every slot's boxes are the same box in world space; both of these silently break that."""
        why = "dedup calls two slots one sender only because their boxes are identical in world space"
        good = assert_(re.search(r"^  position: \{x: 0, y: 0, z: 0\}$", d, re.M) is not None,
                       f"{what} {param}: shape offset is zero (the shape sits on its transform) — {why}")
        boxes, slot = transform_ancestry(docs, d)
        want = param.rsplit("/", 2)[1] if param and param.count("/") >= 2 else None
        return assert_(boxes == "Boxes" and want is not None and slot == want,
                       f"{what} {param}: hangs under {want}/Boxes (got {slot}/{boxes}) — {why}, and Boxes is the node that carries them together") and good

    params = []
    for d in recv:
        tags = re.findall(r"^  - (.+?)\s*$", d.split("collisionTags:")[1].split("allowSelf")[0], re.M)   # a tag may contain spaces (a vendor tag)
        ok = assert_(tags == c["tags"], f"receiver tags {tags} == {c['tags']}") and ok
        for fld, want in (("allowSelf", "0"), ("localOnly", "0"), ("useFaceProximity", "1"),
                          ("receiverType", "2"), ("shapeType", "2")):
            m = re.search(rf"^  {fld}: (\S+)$", d, re.M)
            ok = assert_(m is not None and m.group(1) == want, f"receiver {fld} == {want}") and ok
        m = re.search(r"^  size: \{x: (\S+), y: (\S+), z: (\S+)\}$", d, re.M)
        ok = assert_(m is not None and all(float(v) == c["boxSize"] for v in m.groups()),
                     f"receiver size == boxSize {c['boxSize']} on every axis") and ok
        m = re.search(r"^  parameter: (\S+)$", d, re.M)
        param = m.group(1) if m else None
        params.append(param)
        # The box's rotation is the one hand-maintained fact the readout coefficients rest on: the
        # +Z face must be the cage's named axis. Compared as a rotation, not as four numbers — q and
        # -q are the same rotation, and the Euler forms an inspector offers reach both signs.
        want = AXIS_ROTATION.get(param.rsplit("/", 1)[-1] if param else "")
        got = transform_rotation(docs, d)
        ok = assert_(want is not None and same_rotation(got, want), f"receiver {param}: box rotation {got} faces its axis") and ok
        ok = assert_(transform_scale(docs, d) == (1.0, 1.0, 1.0), f"receiver {param}: node scale is one (Boxes carries the size; a scaled node is silently non-coincident)") and ok
        ok = coincident(d, param, "receiver") and ok
    # `Hit`: the slot's own Constant box, coincident and congruent with the axis boxes and on the same animated
    # flag, so it is admitted and rejected with them and its rising edge IS the slot's admission. No rotation
    # assert — a cube is coincident under any rotation and Hit reads no face, so identity would guard nothing.
    # useFaceProximity is irrelevant to a Constant receiver and is held at 0 so the asset says so.
    for d in hit:
        tags = re.findall(r"^  - (.+?)\s*$", d.split("collisionTags:")[1].split("allowSelf")[0], re.M)
        ok = assert_(tags == c["tags"], f"Hit receiver tags {tags} == {c['tags']}") and ok
        for fld, want in (("allowSelf", "0"), ("localOnly", "0"), ("shapeType", "2"),
                          ("receiverType", "0"), ("useFaceProximity", "0"), ("minVelocity", "0")):
            m = re.search(rf"^  {fld}: (\S+)$", d, re.M)
            ok = assert_(m is not None and m.group(1) == want, f"Hit receiver {fld} == {want}") and ok
        m = re.search(r"^  size: \{x: (\S+), y: (\S+), z: (\S+)\}$", d, re.M)
        ok = assert_(m is not None and all(float(v) == c["boxSize"] for v in m.groups()),
                     f"Hit receiver size == boxSize {c['boxSize']} on every axis") and ok
        m = re.search(r"^  parameter: (\S+)$", d, re.M)
        param = m.group(1) if m else None
        params.append(param)
        ok = assert_(transform_scale(docs, d) == (1.0, 1.0, 1.0), f"receiver {param}: node scale is one (the dedup rule rests on this box being coincident with its siblings)") and ok
        ok = coincident(d, param, "Hit receiver") and ok
    expect = sorted(f"{c['prefix']}/Slot{k}/{ax}" for k in range(1, c["K"] + 1) for ax in receivers(c))
    ok = assert_(sorted(p or "" for p in params) == expect,
                 f"receiver parameters are exactly {c['prefix']}/Slot1..{c['K']}/{' '.join(receivers(c))}, one each" + addx + addhit) and ok
    return ok


def check_rig(assert_, c, here, docs, particles=True):
    """The hierarchy facts the clip paths and the size knob rest on: every Slot sits under
    `Cage/Size`, shipped at uniform scale 1 (the consumer's knob, README §Knobs), carrying the
    tilt with its `Output` counter-rotated (a consumer's world-aligned offsets hang there); each
    slot's `Burst` is inside the toggled `Payload` and its `Emit` is
    outside it, directly under `Output` — an `Emit` inside the wrapper would be disabled mid-burst
    and truncate it. `here` None (the consumer door) skips the Boundary asserts: the preview is the
    entry's opt-in and a copy may have dropped it."""
    ok = True
    gos, trs, rots, poss = {}, {}, {}, {}
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
            rq = re.search(r"m_LocalRotation: \{x: (\S+), y: (\S+), z: (\S+), w: (\S+)\}", d)
            rots[m.group(2)] = tuple(float(v) for v in rq.groups()) if rq else None
            pq = re.search(r"m_LocalPosition: \{x: (\S+), y: (\S+), z: (\S+)\}", d)
            poss[m.group(2)] = tuple(float(v) for v in pq.groups()) if pq else None

    def parent_name(tid):
        f = trs[tid][1]
        return gos.get(trs[f][0]) if f in trs else None

    size = [tid for tid, (go, _, _) in trs.items() if gos[go] == "Size"]
    ok = assert_(len(size) == 1 and parent_name(size[0]) == "Cage", "exactly one Size node, under Cage") and ok
    ok = assert_(len(size) == 1 and trs[size[0]][2] == (1.0, 1.0, 1.0), "Size ships at uniform scale 1") and ok
    # Only Size's own Slot<k> children: a consumer may name other nodes Slot<k> elsewhere (a spring rig per slot beside them).
    slots = [tid for tid, (go, _, _) in trs.items() if re.fullmatch(r"Slot\d+", gos[go]) and parent_name(tid) == "Size"]
    ok = assert_(len(slots) == c["K"], f"{len(slots)} Slot nodes directly under Size == K {c['K']}") and ok
    # Every slot is the SAME transform as every other: same tilt, no offset from Size, no scale of its own.
    # That is what makes two slots' coincident boxes read one sender bit-identically, which is the whole of
    # the dedup rule — a slot nudged a centimetre or scaled 1.001 still tracks, still bursts, and quietly
    # stops recognising the duplicate it was added to catch.
    ok = assert_(not [tid for tid, (go, _, _) in trs.items() if gos[go] == "Gate"],
                 "no Gate node: the shared OnEnter gate was removed; delete it from this copy") and ok
    for t in slots:
        ok = assert_(same_rotation(rots.get(t), TILT), f"{gos[trs[t][0]]} carries the tilt (got {rots.get(t)})") and ok
        ok = assert_(poss.get(t) == (0.0, 0.0, 0.0),
                     f"{gos[trs[t][0]]} sits at local position zero (got {poss.get(t)}) — dedup rests on every slot's boxes standing in the same place in world space") and ok
        ok = assert_(trs[t][2] == (1.0, 1.0, 1.0),
                     f"{gos[trs[t][0]]} carries local scale one (got {trs[t][2]}) — dedup rests on every slot's boxes being the same size, and Boxes is the only size lever") and ok
        outs = [o for o, (go, father, _) in trs.items() if father == t and gos[go] == "Output"]
        ok = assert_(len(outs) == 1 and same_rotation(rots.get(outs[0]), TILT_INV), f"{gos[trs[t][0]]}/Output carries the inverse tilt (got {[rots.get(o) for o in outs]})") and ok
    # Payload is the node the controller toggles; Burst and Emit are the shipped particle mechanism, which an owned
    # copy may replace (`particles` False skips them and asserts nothing else under Payload).
    places = (("Burst", "Payload"), ("Emit", "Output"), ("Payload", "Output")) if particles else (("Payload", "Output"),)
    for name, want in places:
        nodes = [tid for tid, (go, _, _) in trs.items() if gos[go] == name]
        ok = assert_(len(nodes) == c["K"] and all(parent_name(t) == want for t in nodes), f"{c['K']} {name} nodes, each under {want}") and ok
    # The boundary: one inactive Boundary under Size holding Sphere, a MeshFilter on the unit OBJ mesh
    # with its renderer enabled — the controller rewrites scale and enable live, so the saved enable is
    # what makes the edit-mode preview honest.
    if here is None:
        return ok   # the boundary is the entry's opt-in preview; a copy may have dropped it
    bnd = [tid for tid, (go, _, _) in trs.items() if gos[go] == "Boundary"]
    ok = assert_(len(bnd) == 1 and parent_name(bnd[0]) == "Size", "exactly one Boundary node, under Size") and ok
    if bnd:
        bgo = next(d for d in docs if d.startswith(f"1 &{trs[bnd[0]][0]}\n"))
        ok = assert_(re.search(r"^  m_IsActive: 0$", bgo, re.M) is not None, "Boundary ships inactive (the consumer's opt-in)") and ok
    for name, mesh in (("Sphere", "UnitSphere.obj"),):
        nodes = [tid for tid, (go, _, _) in trs.items() if gos[go] == name]
        ok = assert_(len(nodes) == 1 and parent_name(nodes[0]) == "Boundary", f"one {name} node, under Boundary") and ok
        if not nodes:
            continue
        go = trs[nodes[0]][0]
        if here is not None:
            mf = next((d for d in docs if d.startswith("33 &") and re.search(rf"^  m_GameObject: \{{fileID: {go}\}}$", d, re.M)), "")
            m = re.search(r"m_Mesh: \{fileID: -?\d+, guid: ([0-9a-f]{32}), type: 3\}", mf)
            ok = assert_(m is not None and m.group(1) == meta_guid(os.path.join(here, "assets", mesh)), f"{name}'s MeshFilter references assets/{mesh}") and ok
        mr = next((d for d in docs if d.startswith("23 &") and re.search(rf"^  m_GameObject: \{{fileID: {go}\}}$", d, re.M)), "")
        en = re.search(r"^  m_Enabled: (\d)$", mr, re.M)
        ok = assert_(en is not None and en.group(1) == "1", f"{name}'s MeshRenderer saved enabled — the edit-mode preview shows the burst surface") and ok
    return ok


# Receiver box rotation per axis: the box's local +Z must be the cage's named axis.
AXIS_ROTATION = {"X+": (0, 0.7071068, 0, 0.7071068), "Y+": (-0.7071068, 0, 0, 0.7071068), "Z+": (0, 0, 0, 1),
                 "X-": (0, -0.7071068, 0, 0.7071068)}


def same_rotation(got, want):
    """Two quaternions as rotations: q and -q are the same, and an inspector Euler reaches both signs."""
    return got is not None and abs(sum(a * b for a, b in zip(got, want))) > 1 - 1e-4


def transform_rotation(docs, component_doc):
    """The m_LocalRotation of the Transform owning the GameObject a component document belongs to."""
    go = re.search(r"^  m_GameObject: \{fileID: (\d+)\}$", component_doc, re.M)
    tr = next((t for t in docs if t.startswith("4 &") and go is not None
               and re.search(rf"^  m_GameObject: \{{fileID: {go.group(1)}\}}$", t, re.M)), None)
    rot = re.search(r"^  m_LocalRotation: \{x: (\S+), y: (\S+), z: (\S+), w: (\S+)\}$", tr or "", re.M)
    return tuple(float(v) for v in rot.groups()) if rot else None


def transform_ancestry(docs, component_doc, depth=2):
    """The names of the first `depth` ancestors of the GameObject a component document belongs to,
    nearest first — ("Boxes", "Slot<k>") for a slot receiver. None where the chain runs out."""
    go = re.search(r"^  m_GameObject: \{fileID: (\d+)\}$", component_doc, re.M)
    tr = next((t for t in docs if t.startswith("4 &") and go is not None
               and re.search(rf"^  m_GameObject: \{{fileID: {go.group(1)}\}}$", t, re.M)), None)
    names = []
    for _ in range(depth):
        f = re.search(r"^  m_Father: \{fileID: (\d+)\}$", tr or "", re.M)
        tr = next((t for t in docs if f is not None and t.startswith(f"4 &{f.group(1)}\n")), None)
        g = re.search(r"^  m_GameObject: \{fileID: (\d+)\}$", tr or "", re.M)
        go_doc = next((t for t in docs if g is not None and t.startswith(f"1 &{g.group(1)}\n")), None)
        m = re.search(r"^  m_Name: (.*)$", go_doc or "", re.M)
        names.append(m.group(1).strip() if m else None)
    return tuple(names)


def transform_scale(docs, component_doc):
    """The m_LocalScale of the Transform owning the GameObject a component document belongs to."""
    go = re.search(r"^  m_GameObject: \{fileID: (\d+)\}$", component_doc, re.M)
    tr = next((t for t in docs if t.startswith("4 &") and go is not None
               and re.search(rf"^  m_GameObject: \{{fileID: {go.group(1)}\}}$", t, re.M)), None)
    sc = re.search(r"^  m_LocalScale: \{x: (\S+), y: (\S+), z: (\S+)\}$", tr or "", re.M)
    return tuple(float(v) for v in sc.groups()) if sc else None


def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def check_seam(assert_, c, here, body):
    """The FullController's silent surface: globalParams exactly the enable, and its two
    objRefs pointing at THIS folder's built/ — a component built by copying a configured one
    keeps the donor's objRef and silently runs the donor's controller. Plus the Toggle holding
    the enable's other half: its defaultOn is the same bit as the document's enableDefault, and the two disagreeing is
    silent — the avatar comes up in the state neither side intended."""
    ok = True
    gp = re.search(r"globalParams:\n((?:\s+- .*\n)*)", body)
    got = [ln.strip()[2:] for ln in gp.group(1).splitlines()] if gp else None
    ok = assert_(got == [c["enable"]], f"globalParams == [{c['enable']}] (got {got})") and ok
    refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 2\}", body)
    want = [meta_guid(os.path.join(here, "built", c["controller"] + ".controller")),
            meta_guid(os.path.join(here, "built", c["controller"] + "_Parameters.asset"))]
    ok = assert_(refs == want, f"FullController objRefs == built/{c['controller']} controller + params GUIDs (got {refs})") and ok
    tog = [b for b in re.split(r"^    - rid: ", body, flags=re.M)[1:]
           if "class: Toggle" in b.split("data:", 1)[0]
           and re.search(r"^        useGlobalParam: 1$", b, re.M)
           and re.search(rf"^        globalParam: {re.escape(c['enable'])}$", b, re.M)]
    if assert_(len(tog) == 1, f"exactly one VRCFury Toggle drives {c['enable']} through useGlobalParam (got {len(tog)})"):
        for fld, want_v, why in (("defaultOn", 1 if c["enableDefault"] else 0, "the document's enableDefault"),
                                 ("saved", 0, "the controller's enable is saved: false, so a saved Toggle restores a bit nothing else keeps")):
            m = re.search(rf"^        {fld}: (\S+)$", tog[0], re.M)
            ok = assert_(m is not None and int(m.group(1)) == want_v, f"Toggle {fld} == {want_v} — {why}") and ok
    else:
        ok = False
    return ok


def check_prefab(overrides, prefab_path):
    """The consumer door: the receiver surface and the rig geometry (tilt, counter-rotated
    Output, Payload under Output) over any prefab at any CONFIG — an owned copy in a venue
    regenerates its document from this generator and nothing else ties its prefab to it. Not the
    entry-only asserts (the World pins, the built/ GUIDs, the Boundary mesh GUIDs, the Toggle), and
    nothing under Payload: what a copy hangs there (a box, a censor quad) is its own."""
    c = config(overrides)
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond
        return cond

    if not os.path.exists(prefab_path):
        print("  FAIL " + prefab_path + " is missing")
        return False
    docs = open(prefab_path, encoding="utf-8").read().split("--- !u!")
    ok = check_receivers(assert_, c, docs, os.path.basename(prefab_path)) and ok
    ok = check_rig(assert_, c, None, docs, particles=False) and ok
    print("OK" if ok else "FAILED")
    return ok


def write_meshes(assets):
    """The unit mesh the Boundary node holds, as OBJ text: a UV sphere of radius 1. The controller
    scales it to the burst surface."""
    import math

    def obj(path, verts, normals, faces, name):
        L = [f"# {name} — GENERATED by generate.py --mesh; unit size, scaled by the controller", f"o {name}"]
        L += [f"v {fmt(x)} {fmt(y)} {fmt(z)}" for x, y, z in verts]
        L += [f"vn {fmt(x)} {fmt(y)} {fmt(z)}" for x, y, z in normals]
        L += ["f " + " ".join(f"{i + 1}//{i + 1}" for i in f) for f in faces]
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(L) + "\n")

    seg, rings = 48, 24
    verts, faces = [], []
    for j in range(rings + 1):
        phi = math.pi * j / rings
        for i in range(seg + 1):
            th = 2 * math.pi * i / seg
            verts.append((math.sin(phi) * math.cos(th), math.cos(phi), math.sin(phi) * math.sin(th)))
    for j in range(rings):
        for i in range(seg):
            a, b = j * (seg + 1) + i, (j + 1) * (seg + 1) + i
            if j > 0:
                faces.append((a, a + 1, b))
            if j < rings - 1:
                faces.append((a + 1, b + 1, b))
    obj(os.path.join(assets, "UnitSphere.obj"), verts, verts, faces, "UnitSphere")


def main():
    if "--mesh" in sys.argv:
        write_meshes(os.path.join(HERE, "assets"))
        print("wrote assets/UnitSphere.obj")
        return
    if "--check" in sys.argv:
        sys.exit(0 if check_files({}, HERE, "ContactRadar.prefab") else 1)
    if "--check-prefab" in sys.argv:   # a consumer's owned copy at this CONFIG: the receiver and geometry asserts only
        i = sys.argv.index("--check-prefab") + 1
        if i >= len(sys.argv):
            refuse("--check-prefab needs a prefab path")
        sys.exit(0 if check_prefab({}, sys.argv[i]) else 1)
    text, facts = document({})
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    write_meshes(os.path.join(HERE, "assets"))   # idempotent, so regenerate-and-diff covers the OBJ too
    print(f"wrote controller.yaml and assets/UnitSphere.obj — K={facts['K']}, {facts['receivers']} receivers, {facts['syncedBits']} synced bit")


if __name__ == "__main__":
    main()
