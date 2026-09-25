#!/usr/bin/env python3
"""contact-radar generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ in a mounting Editor —
the controller.yaml committed here is generated output and the repo gate holds
built/ to it, so hand-editing it desynchronises the document from both this
generator and the compiled controller. `--check` asserts the hand-maintained
prefab surface no compile or gate reads (README §Changing it).

What it builds: K per-sender "slots", one FX layer each. A slot is three
coincident face-proximity box receivers (X+, Y+, Z+ — four under `fourBox`,
below) on one animated `allowOthers` flag. The flag is
the latch: a sender whose overlap with a receiver began while the flag was shut
stays invisible to that receiver for the whole overlap, however the flag moves
later, and only a full exit and re-entry admits it (docs/runtime.md
§Contacts). No slot ever sits open at full size. Exactly one slot rides the
front: a cube growing from the centre to the face over `sweepSeconds`, flag up,
so each hand inside is admitted alone as the front reaches its tilted Chebyshev
radius; every other free slot is Armed, collapsed, holding no rejection and
blind to nothing later. The admission shows as the readings: every axis box
reads above zero on the collision step after the front-size cube took the
hand, and that readings rung (`all_pos`, every axis `greater 0`) is the latch.
The riding slot Latches on its OWN readings (flag shut, boxes expanded to the
hold cube) and the next Armed slot in ring order takes the front in the same
animator evaluation, reading the latcher's stale Open and the same fresh
readings: it appears SHUT at last frame's front for a step (re-rejecting the
hand just taken and everything else inside), then rides on flag-up, so the
admission windows tile. When no neighbour fires, the self-open rung recovers
within one stepSeconds, the common path's floor and not a corner case. There
is no Constant `Hit` box: an earlier build carried one per slot as an edge one
collision step ahead of the readings, and it was removed to cut the rig's
contact-pair load in a crowd (README §Design notes carries the trade), so the
readings that were its fallback are the whole latch now, one step later.
The `Open` AAP means "this slot holds the front position" (shut at it, riding
it, or in Partial); the name predates the always-running front.
The slots sit tilted, the cube's diagonal vertical, so a standing player's
stacked senders meet a face at staggered depths instead of one vertical plane
in one step (README §How it works); the readout lives in that frame. The latched
slot then reconstructs its hand's position exactly (box-tracker's readout,
three boxes and a configured sender radius — four boxes and a measured one
under `fourBox`), computes r² = x²+y²+z² in a piecewise-linear lookup, and
undoes the tilt on the one axis the zone needs: yw = (x+y+z)/sqrt3 is the
hand's height above the cage centre (the tilt sends the slot's (1,1,1) diagonal
to world up), a linear term the read clips carry, and p2 = r² − yw² is the
in-plane radius², a fourth lookup subtracting yw's square. The zone is a
vertical cylinder about the cage centre with no height bound: the payload
fires when p2 crosses the burst radius, and a hand leaves the zone through the
cube's ends only by leaving the hold cube, which is the axis-floor release. The
cylinder's ends are therefore the tilted cube's corners: at the burst radius a
hand is inside the acquisition cube from every direction within a band of
half-height sqrt3·acqHalf − sqrt2·(R + r) about the centre (`band_half_height`,
which the lint holds above zero and the boundary draws), and past the band the
cube still reaches, direction-dependently. r² stays computed and exported, and
it is the settle rung's guard off the Latch park; the park writes yw as well,
so the first p2 the tree computes is never 3h² minus a stale square.

A slot keeps its hand until the hand leaves the hold cube, and re-bursts each
time the hand crosses back inside the burst radius after retreating past the
re-arm radius. With `farRadius` set (None by default), a settled hand whose
in-plane radius reads past it is let go as well: one rung in `TrackBand` alone,
the tracking state a hand reaches only settled, with live readings, so a hand standing between the far radius and the cube's reach
holds a slot only from its admission to `TrackBand`'s first frame, and the
front re-offers it every pass, the shape of a dedup re-admission. A collapsed
slot forms no contact pairs, which is what the knob buys in a crowd; a merge
whose per-axis maximum reads past the far radius releases the same way. A released slot Recycles: its boxes collapse for `stepSeconds`,
which ends every overlap it held (measured), then it goes straight back onto
the front when nothing else is Armed or holding the front and every lower-index
slot is Held, else it queues as Armed. The lower-index Held reads are the
tie-break: every flag is read one frame late, and two slots releasing on one
frame would each see the other as neither Open nor Armed and both ride; the
higher goes to Armed instead, where the self-open rule resolves it a step later.

Dedup, and why a slot can admit a hand another slot already holds: the front
re-offers every held hand inside its reach once per pass (below), a tracked hand
that retreats into the hold shell and comes back is a fresh overlap for the
riding slot, and a fast entry that jitters across the front can be admitted two
or three times over. Nothing in a per-slot latch can refuse any of that. So the `Dedup`
layer also publishes `D/<j>_<k>/<ax>`, the difference of two slots' raw readings
on each axis, and a slot in `TrackOut` — the state reached only from `Latch`, so
only on a fresh admission — releases itself when every axis of that difference
is inside `dedupEpsilon` of zero against a slot already holding a sender. Two
coincident congruent boxes read one sender identically, so the difference is a
true zero rather than a small one (measured bit-identical in the shipping
client, near the origin and a kilometre from it). A slot that has settled —
reached the zone, the re-arm band after it, or held outside it past the
fresh window below — always wins, whatever its
index; between two fresh slots still in the shell the lower index wins, and
neither can release the other. `TrackBand` and `TrackIn` carry the SETTLED
form of those rungs instead: the same tests inside SETTLED_EPSILON, a band only
bit-identical readings pass, so a hand that re-arms in the band or drifts near
another is never collapsed by the fresh band, while a merge that resolves onto
a held hand or splits into held hands releases within a few frames of doing
so (`dedup_rungs` in `emit_layer` has the two forms). `TrackBand` writes
`Settled` like the two inside states do, because a fresh lower-index slot
yields only to a settled holder: a band holder that read as fresh would be
admitted a second time by a lower slot and both would burst on re-entry.
`TrackOut` is also left for `TrackBand` once the readout is live (r² off the
Latch park, checked at each period of the tree, a few frames) with no rung
fired: the dedup rungs have had their say by then, and a hand held outside the
zone that stayed fresh would be re-taken from its holder by every lower-index
rider the front sends past it, hopping slots once a pass. The fresh-versus-fresh
index rule covers only the frames both admissions are fresh.

The front re-offers every held hand once per pass, so dedup is the common path,
not a corner: each pass the sweeper admits each held hand inside its reach,
Latches, reads the duplicate in `TrackOut` and Recycles with the payload never
on, then rides again from where the front froze. Two held hands the front
reaches on one collision step co-latch as a phantom, the per-axis maximum of
their readings, which no single-holder comparison matches. A Proximity receiver
reports its strongest sender, so every axis of that phantom is bit-identical to
one holder's reading of that axis: the phantom rungs in `TrackOut` release a
fresh reading composed axis-wise of held readings, one rung per assignment of
the axes to other slots that is not all one slot, each distinct holder Held and
a higher-index one Settled. A real hand fires one only by coinciding with a
different holder on every axis at once. A phantom with an unheld member (two
newcomers on one shell) matches nothing and stands until every member holds a
slot of its own or its reading lands on a held hand, re-composing at each
departure until then: the same-step merge trap, present tense (README §Traps).

The restart race: on the frame the front crosses the face the Sweep layer's
Restart rung and its freeze rungs can all be eligible, and nothing about an
admission is readable on the frame it happens, so a hand taken exactly at the
face can see Restart win before its readings exist. The admission survives
(Latch's hold scale overwrites the collapse a frame later), but the successor's
shut cube then rides SweepPrev 0 and the new pass re-offers the just-taken hand
while its holder is still fresh: one extra dedup cycle, and a lower-index rider
displaces the holder under the fresh-versus-fresh rule. At most once per pass,
and the hand stays tracked throughout. Release reads the axis floor and nothing
else.

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
  `latchSeconds` is Latch's dwell, the same rule for a different sample: the
  readings that latched were taken by the front-size cube, and TrackOut must
  not read them, so Latch waits until a collision step has sampled the hold
  cube; a cut on the expansion takes the release rung at once.
- Every slot state writes every flag (Open, Armed, Front, Held, Settled), the
  payload toggle and the buffer particle's force-on, zeros included: an AAP holds its last clip-written value and a scene binding holds
  whatever last wrote it (docs/runtime.md §Animator evaluation). One function,
  `cfg()`, is where that rule is enforced — every slot clip goes through it.
- The burst states carry the readout tree: the payload wrapper enables where Output
  sits on that frame — the buffer particle inside it is born there — and only a tree
  state keeps writing that position. One toggle serves both consumers: a buffer
  particle reads its enable edge, a mesh reads its level.
- `Cage/Size` is the consumer's static size knob (README §Knobs): scaling it scales
  the cubes, the readout, the cylinder and every band together, so every lint below
  holds at any scale; only the sender-radius bias term scales when it should not —
  and under `fourBox` there is no such term, so the origin is exact at any scale.
- Latch parks x, y, z at (h, -h, -h), and yw at that point's height, so the
  first r² computed in TrackOut is the tables' reading of that corner (about
  3h²; `park_r2` is the exact figure the settle guard compares against) and
  the first p2 about 8h²/3, both far outside the zone, and leaves for TrackOut
  once `latchSeconds` has passed with every axis still reading (the readings
  rung carries the exit time), on any axis at the floor at once (a cut on the
  expansion: Recycle now, never a slot left standing expanded), or when the
  dwell passes with neither, in which case it recycles: the guard is the state
  sequence, no settle AAP. The dwell exists because the readings that fired the
  latch were taken by the front-size cube, and above 60 fps the frame after the
  latch can carry no collision step: without it TrackOut's first evaluation
  applies the hold coefficients to front-size floats, decodes a point pushed
  outward by about holdHalf over the front, and for a hand deep inside the zone
  that point still reads inside R, so TrackIn fires on the duplicate before
  dedup can match it (measured at 144 fps: a burst per re-admission, and the
  holder itself released by the settled rung). One stepSeconds of Latch puts a
  hold-size sample under both slots before TrackOut compares them. The readings
  rung is listed before the fallback, and that ordering — not the duration — is
  what survives a hitch frame longer than the whole wait. No rung in TrackOut
  reads p2 outward all the same; the far rung lives in TrackBand.
- Timed dwells are plain clips, never a curve inside a Direct tree (the tree's
  duration is data — docs/animator-schema.md §motions).
- Recycle is one collapsed step, the same configuration Armed holds; it stays a
  state of its own because Armed's ring rungs carry no exit time and a collapse
  that can be left within a frame is not guaranteed to span a collision step
  above 60 fps.
- The parameter driver lives only in Disabled (off-state hygiene, localOnly false:
  every client zeroes its own receiver floats).
- An admission can land on some of a slot's coincident boxes and not the
  others when the overlap begins on the very frame the slot opens (measured), and
  a slot holding a partial reading can never satisfy the all-box Latch — so
  the riding slot steps aside to Partial on any single reading and Recycles a
  step later if the rest never arrive. A slot holding the front that stalls
  blocks every admission on the avatar; the recycled hand is merely invisible
  until the next pass reaches it.
- One rung fires per frame per layer; the ring rule's exclusivity rests on
  every rung also requiring the slot's OWN Armed flag, which is one frame stale:
  a slot that entered Armed this frame is skipped by its neighbours (they read
  its Armed as 0) and skips itself (it reads its own as 0), so two slots can
  never open on one firing.

The front, which always runs:
- Sticky rejection is why acquisition is a sweep and never a standing cube: a
  full-size shut cube rejects every hand already inside for the life of the
  overlap, and a full-size open cube takes everything that appears inside it on
  one step as one reading. So Armed slots sit COLLAPSED (they hold no
  rejections) and one slot rides: its cube grows from the front's last position
  (`CR/Sweep`, latched into `CR/SweepBase` while nothing rides) to acqHalf over
  `sweepSeconds`, flag up, so each hand is admitted alone as the front reaches
  it. On a latch the ring hands the next slot into SweepShut — the cube appears
  at last frame's front SHUT for a step, re-rejecting the just-latched hand and
  everything else inside (the Recycle idiom) — then Sweep continues from there.
  At the face the pass ends: `Restart` parks Sweep, SweepBase and SweepPrev at 0
  for `stepSeconds`, a plain clip so the hold spans a sampled collision step at
  any frame rate; the riding slot's cube collapses with it (front_scale × Sweep
  over the collapsed base scale), which ends every overlap it was rejecting,
  and the next pass grows from the centre with the flag still up.
- Exhaustion: with every slot Held nothing rides and Wait holds the front where
  it froze. A freed slot appears shut there, rides to the face, restarts, and
  reaches from 0 whatever the frozen front had stranded. No special case.
- Two hands within two collision steps of front travel at the same Chebyshev
  radius co-latch: the admission is read from the readings, which land a step
  after the front-size cube took the hand, so the window is the front's travel
  over that step and the one before it; `sweepSeconds` and the frame
  time are the two knobs on that resolution, and the phantom rungs above are
  what releases the result when both hands are already held.
- The cost of re-offering: each held hand inside the front's reach is admitted
  once per pass and released (readings, the dedup frame, a collapse, a shut
  step). With a spare Armed slot the ring hands the front on in the same
  evaluation and the front holds only for that successor's shut step; when the
  rider was the last free slot the whole cycle is on the front's path, so the
  effective period at K−1 held is `sweepSeconds` plus that per held hand. A
  held hand keeps tracking throughout, since its holder never moves.
- A hand the front finds with no slot holding it fires the payload exactly as a
  hand crossing in does, whether it is a newcomer, a resident at enable, or
  every resident after a fresh animator (load, a late joiner, a mirror clone) or
  a distance-hide resume. There is deliberately no quiet endpoint for the last
  two: a quiet endpoint costs a state copy per slot, a further sweep AAP and an exhaustion
  cap whose timing (the last resident's inside choice lands two frames after
  its Held) is the most fragile thing in the rig, and it buys only that an
  edge reader stays quiet for hands already inside. The consumer's tolerance
  for one payload edge per resident at each of those events is what this
  trades on; a level reader (a marker, a mosaic) sees no difference.
- Boot is the default state and is entered only by a fresh animator (load,
  manual hide/show, mirror clones); Disabled is entered only by the toggle.
- Paused is entered from every state on `IsAnimatorEnabled` false, VRChat's
  one-frame pre-halt signal for a distance-hide (docs/runtime.md §Parameters
  carries the citation; view cull gives no signal, so the README asks the
  installer for renderer bounds that cover the working volume). Its clip collapses the boxes; on resume the rig passes through
  Paused, Armed (collapsed) and SweepShut at front 0 before anything grows, so
  whatever the receivers did during the pause is discarded and the present
  hands are re-acquired from scratch.
- The three sweep AAPs have exactly one writer, the `Sweep` layer, whose every
  state writes all three: a WD-ON state reverts any AAP it does not write to its
  default (measured on this rig — a 1D-tree state dropped an AAP it did not
  write to 0 within a frame), so a value that must persist across a state is written back
  to itself through a direct child weighted by its own value. Slot layers read
  them and report `Slot<k>/Front` (1 in their Sweep state) for the layer to
  ramp on.
- The handoff leaves no blind band, and that takes both halves. `Ramp -> Wait`
  fires on the sweeping slot's own readings while its Front still reads 1, the
  frame it latches, so the front freezes at the size that admitted rather than
  a frame after its Front flag drops; and the successor's shut cube scales off
  `SweepPrev`, last frame's front, so it appears at exactly the size that just
  admitted instead of at a front that has already moved on. A sender at that
  exact size was admitted by the predecessor and is re-rejected by the
  coincident shut cube, which is the Recycle idiom.
  The restart rung is listed after the freeze rungs: on a pass's last handoff
  both are eligible in one evaluation, and a restart winning would park
  SweepPrev at 0 under the successor's shut cube on the frame it appears and
  re-run the pass with the just-taken hand's slot still in Latch. The freeze
  wins whenever both are eligible; a hand taken on the very frame the front
  crosses the face has no reading yet, and there Restart wins (the race above). A successor still in its shut step when a restart lands
  simply shrinks with it, which ends its overlaps, and regrows from 0. Wait holds
  SweepPrev off itself, never off Sweep: on Wait's first frame Sweep already
  reads the frozen front, one frame past the size that admitted, and copying it
  in would grow the successor's shut cube by one frame of travel on its second
  shut frame, with the flag then rising at that size — a band one frame of
  travel wide, rejected stickily, at every handoff.
- The `Ramp` state is a Direct tree whose duration is data: the ramp clip
  carries the timing and every other child is one frame long, which stretches
  the ramp by at most the sum of those children's weights over 60·sweepSeconds.

The boundary: `Cage/Size/Boundary` holds one unit mesh, `Cylinder` (an open
tube of radius 1, y in [-1, 1], its ends undrawn because the zone has none),
written by `--mesh` into assets/. The Sweep layer — the one layer with exactly
one state live at all times — writes its scale (R, band, R) and MeshRenderer
enable in every state, so the drawn surface is the burst radius over the band
inside which that radius is reached from every direction, by construction,
only while the toggle is on. `Boundary` ships inactive: activating it is the
consumer's opt-in, and its material the swap point.

Fragment mode: `document(overrides)` returns the document text and a facts
dict, the door a venue's owned copy regenerates through at its own CONFIG. A
key CONFIG does not carry is refused there, so a consumer still passing a key
this generator has since dropped fails at the door instead of being accepted
silently and built at the default.
"""

import itertools
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "controller": "ContactRadar_Fx",
    "K": 4,                     # slots; each is one layer and three receivers (four under fourBox)
    "tags": ["HandR"],
    "acqHalf": 1.2,             # acquisition cube half-extent, m; at Cage/Size scale 1
    "holdHalf": 1.3,            # hold cube half-extent, m — h in the readout
    "burstRadius": 1.0,         # R_in, m — the zone's horizontal radius (a vertical cylinder about the cage centre)
    "rearmRadius": 1.1,         # R_out, m
    "farRadius": None,          # m, or None: a settled hand whose in-plane radius reads past this is released (TrackBand only),
                                #   so heads standing between the zone and the cube's reach do not hold slots; None keeps every
                                #   held hand to the hold cube. Lint: above rearmRadius, below the hold cube's widest in-plane reach
    "fourBox": False,           # add the X- receiver and measure r per sender instead of assuming it (needs a 4-box prefab)
    "senderRadius": 0.05,       # r, m — the hand sender's radius; a capsule reads as a constant bias.
                                #   Under fourBox the readout measures r instead, and this is only the lints' assumed maximum
    "stepSeconds": 0.035,       # every step-spanning dwell; >= 2 collision steps
    "latchSeconds": 0.035,      # Latch's dwell before TrackOut: >= one collision step at any frame rate, so the first readings
                                #   TrackOut and dedup compare were taken at the hold cube (the frame after the latch carries no step
                                #   above 60 fps, and the hold coefficients over front-size readings decode a point inside the zone);
                                #   a cut on the expansion leaves Latch at once, and the same length is the terminal fallback
    "dedupEpsilon": 0.004,      # the coincidence band on a [0, 1] reading: two slots this close on every axis are holding one sender.
                                #   Coincident receivers read one sender bit-identically in the client, so this is not sized
                                #   against readout noise; it covers a one-step skew between the two slots' readings on the
                                #   admission frame, and two real hands are still far outside its ball (the lint bounds it)
    "sweepSeconds": 2.0,        # the front's travel time from the centre to the face, every pass: the period between two offers to a hand and
                                #   the resolution (front travel over the two collision steps an admission spans, the same-shell merge window) at once
    "lookupSegments": 16,       # x² table resolution over [-h, h]; the yw² table takes the same chord width over its wider span
    "epsilon": 1e-5,            # the any-box loss floor
    "boxSize": 1.0,             # the receiver box `size` on every axis; the Boxes scale multiplies it
    "prefix": "CR",             # internal param namespace; never published
    "enable": "ContactRadar/Enable",
    "enableDefault": True,      # the enable parameter's default; False means the first pass starts when the toggle turns on (the prefab Toggle's default must agree)
}


# The acquisition cube is tilted so its body diagonal is world-vertical: every face sits at the same
# elevation (asin(1/sqrt3) = 35.26 deg) 120 deg apart in azimuth, so a standing player's stacked senders
# (head, mouth, hips, hands) meet a face at staggered depths instead of crossing one vertical plane in a
# single collision step. Unity's Quaternion.FromToRotation((1,1,1), up), (x, y, z, w). Each Slot<k> carries
# it and each Output its inverse; `check_rig` holds both, and every owned copy carries it by hand.
# The settled dedup band on a [0, 1] reading. Not a knob: two settled slots reading one sender are bit-identical
# (measured in the shipping client), so the test needs no slack, and it runs on every frame of every hold rather than
# once per admission, so its false-match rate scales as this band to the power of the axis count. dedupEpsilon is the
# fresh band and covers a one-step admission skew this test never sees.
SETTLED_EPSILON = 0.0002

TILT = (-0.325058, 0.0, 0.325058, 0.888074)
TILT_INV = (0.325058, 0.0, -0.325058, 0.888074)
SQRT3 = 3 ** 0.5
# World height in the slot frame: the tilt sends the slot's (1, 1, 1) diagonal to world up, so a point's height
# above the cage centre is (x + y + z) / sqrt3 of its tilted-frame readout. yw undoes the tilt on the one axis the
# cylinder needs; the in-plane radius² is then r² − yw², and the readout frame is never undone for x and z.
YW_PER_AXIS = 1 / SQRT3


def band_half_height(c, radius):
    """The half-height, about the cage centre, of the band inside which a sender at horizontal `radius` is inside
    the acquisition cube from every direction. The tilted cube's horizontal cross-section is a hexagon at the
    centre height (inradius acqHalf·sqrt(3/2)) that shrinks toward each vertical corner at sqrt(1/2) per metre in
    the worst azimuth, so the band is sqrt3·(acqHalf − senderRadius) − sqrt2·radius: the cube shrunk by the sender's
    radius, a bound the overlap-based admission clears from every direction. Above and below the band the cube still
    reaches, but not from every direction: the zone's ends are the cube's corners, not caps."""
    return SQRT3 * (c["acqHalf"] - c["senderRadius"]) - 2 ** 0.5 * radius


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def fmt(v):
    return format(float(v), ".9g")


def axes(c):
    """A slot's receiver axes. fourBox appends the opposed X- box the sender radius is measured from."""
    return ("X+", "Y+", "Z+", "X-") if c["fourBox"] else ("X+", "Y+", "Z+")


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
    if c["rearmRadius"] <= c["burstRadius"]:
        refuse("rearmRadius must be > burstRadius")
    if band_half_height(c, c["rearmRadius"]) <= 0:
        refuse("sqrt3*acqHalf must exceed sqrt2*(rearmRadius + senderRadius) — the cylinder's re-arm radius must be inside the "
               "tilted acquisition cube from every direction at the centre height, or a hand can be in the zone on one side "
               "of you and unreachable on the other; the band this leaves is the zone's guaranteed height (band_half_height)")
    if c["stepSeconds"] < 2 / 60:
        refuse("stepSeconds must be >= 2/60 — every frame at 60 fps or below carries a collision step, but above 60 fps a step "
               "lands only every second or third frame and the longest gap between two is one step period plus one frame, just "
               "under 2/60 s; a dwell shorter than that gap can open and close with no step sampling it")
    if c["latchSeconds"] < c["stepSeconds"]:
        refuse("latchSeconds must be >= stepSeconds — Latch dwells so that a collision step samples the hold cube before TrackOut "
               "reads the readings, and stepSeconds is the shortest dwell one step is guaranteed to land in at any frame rate; "
               "a shorter Latch hands TrackOut the front-size readings that latched, which the hold coefficients decode inside the zone")
    if c["farRadius"] is not None:
        if c["farRadius"] <= c["rearmRadius"]:
            refuse("farRadius must be > rearmRadius — the far release is a settled hand's exit past the re-arm band; at or inside "
                   "the re-arm radius it would release a hand the zone still counts as present")
        if c["farRadius"] >= c["holdHalf"] * 2 ** 0.5:
            refuse("farRadius must be < holdHalf*sqrt2 — the hold cube's widest in-plane reach (its edge midpoints at the centre "
                   "height); past it no held hand can read that radius and the rung can never fire. Under three boxes the readout "
                   "saturates a sender radius short of the + faces, so the usable bound is a little inside this one")
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
    """The inside predicate (one AND list) and the outside rungs (a list of AND lists — an OR). The zone is a
    vertical cylinder: the compare is on p2, the in-plane radius², and nothing bounds the height, so a hand leaves
    the zone through the cube's ends by leaving the hold cube (the axis floor), never through a band."""
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    inside = [f"{me}/p2 less {fmt(rin2)}"]
    outside = [[f"{me}/p2 greater {fmt(rout2)}"]]
    return inside, outside


BOUNDARY = "Cage/Size/Boundary"


def boundary_bindings(c, on):
    """The unit tube's scale and renderer enable — the drawn surface is the burst radius, over the band inside
    which a hand at that radius is reached from every direction (the ends past it are the cube's corners)."""
    R = c["burstRadius"]
    H = band_half_height(c, R)
    d = {}
    for ax, v in (("x", R), ("y", H), ("z", R)):
        d[f"{BOUNDARY}/Cylinder/Transform.m_LocalScale.{ax}"] = fmt(v)
    d[f"{BOUNDARY}/Cylinder/MeshRenderer.m_Enabled"] = 1 if on else 0
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
    # The admission: every axis box reads above zero. The readings land on the collision step after the front-size
    # cube took the hand, and this one predicate is the latch, the ring handoff's trigger and the Sweep layer's freeze
    # (`emit_sweep_layer` uses it verbatim). `greater 0`, never `greater epsilon`: a reading in (0, epsilon] would then
    # latch here and hand off nowhere.
    all_pos = ", ".join(f"{me}/{ax} greater 0" for ax in ax4)
    de = fmt(c["dedupEpsilon"])
    nde = fmt(-c["dedupEpsilon"])
    paused = "          - { to: Paused, when: [ IsAnimatorEnabled is false ] }   # the pre-halt frame: park before the animator stops"
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"

    def rungs():
        o(paused)
        o(off)

    def release():
        """Release is the axis floor and nothing else: the slot lets its sender go when any box's reading falls
        away (a Proximity receiver reads 0 the step after its last sender leaves, or the step a contact is cut)."""
        for ax in ax4:
            o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")

    def dedup_rungs(settled):
        """The coincidence rungs, to Recycle. Fresh (TrackOut, entered only from Latch): this slot has just latched and
        another slot already holds a sender at the same point, tested inside dedupEpsilon, which covers the one-step skew
        the admission frame can carry. Settled (TrackIn, TrackBand): this slot has held for a while and now reads what
        another settled slot reads, tested inside SETTLED_EPSILON: a merge that resolved onto a hand another slot holds,
        or that decomposed into hands other slots hold. The test is on the raw readings' difference (the D tree's AAPs),
        bit-exact for two coincident congruent boxes reading one sender.
        Duplicate rung, one per other slot j: every axis inside the band, j Held. Fresh: a SETTLED j always wins, whatever
        its index, and between two fresh slots the lower index wins, so two never release each other. Settled: only
        against a lower-index settled j, so the higher index yields and a pair never both release; when the lower slot is
        a merge still holding an outranked second member, this releases the real single and the merge carries it until
        the next pass (README section Traps).
        Phantom rung, one per assignment of the axes to other slots that is not all one slot: a same-step merge of hands
        other slots hold reads, on every axis, exactly one holder's reading (a Proximity receiver reports its strongest
        sender). Each assigned axis is inside the band of its source AND strictly above every other source in the
        assignment: a merge is its members' per-axis maximum, so it clears each source on the axes it takes from another,
        while a duplicate of one source (difference zero everywhere) and a single sender that two merges each contain
        (below a merge on some axis) both fail. Without that clause the settled rung would release all three slots on one
        sender at once, and the fresh rung rejects a huddled hand's re-admission every pass. Every holder Held; Settled
        as for the duplicate rung."""
        e, ne = (fmt(SETTLED_EPSILON), fmt(-SETTLED_EPSILON)) if settled else (de, nde)

        def within(j, ax):
            lo, hi = min(j, k), max(j, k)
            return [f"{P}/D/{lo}_{hi}/{ax} greater {ne}", f"{P}/D/{lo}_{hi}/{ax} less {e}"]

        def above(s2, ax):
            # this slot's reading minus slot s2's is above the SETTLED band, on the fresh rung too: a same-step merge's
            # members sit within a step of front travel on the radius axis, inside the fresh band, so a fresh-band test here
            # would fail on nearly every phantom the rung exists for. Two members tied within this band on an axis leave
            # the phantom standing until dither or a departure breaks the tie. D/lo_hi is hi minus lo.
            lo, hi = min(s2, k), max(s2, k)
            se, nse = fmt(SETTLED_EPSILON), fmt(-SETTLED_EPSILON)
            return f"{P}/D/{lo}_{hi}/{ax} greater {se}" if k == hi else f"{P}/D/{lo}_{hi}/{ax} less {nse}"

        def holder(j):
            conds = [f"{slot_name(c, j)}/Held greater 0.5"]
            if settled or j > k:
                conds.append(f"{slot_name(c, j)}/Settled greater 0.5")
            return conds

        tag = "settled dedup" if settled else "dedup"
        for j in ks:
            if j == k or (settled and j > k):
                continue
            dconds = []
            for ax in ax4:
                dconds += within(j, ax)
            dconds += holder(j)
            why = (f"slot {j} (lower index, settled) holds this point" if settled else
                   f"slot {j} holds this point" + (" and has settled (a higher index yields only to that)" if j > k else ""))
            o(f"          - {{ to: Recycle, when: [ {', '.join(dconds)} ] }}   # {tag}: {why}")
        others = [j for j in ks if j != k]
        for assign in itertools.product(others, repeat=len(ax4)):
            srcs = sorted(set(assign))
            if len(srcs) == 1:
                continue
            dconds = []
            for ax, j in zip(ax4, assign):
                dconds += within(j, ax)
                dconds += [above(s2, ax) for s2 in srcs if s2 != j]
            for j in srcs:
                dconds += holder(j)
            o(f"          - {{ to: Recycle, when: [ {', '.join(dconds)} ] }}   # {tag} phantom: {'/'.join(f'{ax} of slot {j}' for ax, j in zip(ax4, assign))}")

    o(f"  - name: Slot{k}")
    o("    states:")
    o("      Boot:                        # a fresh animator: load, manual hide/show, a mirror clone")
    o(f"        motion: {{ clip: slot{k}_boot }}")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Disabled, when: [ {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ {en} is true ], exitTime: 1.0 }}")
    o("      Disabled:                    # Enable off — boxes stowed, flag shut, readings zeroed on every client")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: false, set: {{ {', '.join(f'{me}/{ax}: 0' for ax in ax4)} }} }}")
    o(f"        motion: {{ clip: slot{k}_off }}")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Armed, when: [ {en} is true ], exitTime: 1.0 }}   # quantized: an Enable cycle spans a step")
    o("      Paused:                      # boxes collapsed through the pause; resume re-acquires from scratch")
    o(f"        motion: {{ clip: slot{k}_paused }}")
    o("        transitions:")
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ IsAnimatorEnabled is true, {en} is true ] }}")
    o("      Armed:                       # flag shut and collapsed: holds no rejections; waits for the ring, or self-opens onto the front")
    o(f"        motion: {{ clip: slot{k}_armed }}")
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
        # The handoff reads slot i's Open one frame stale (still 1) and the same fresh readings that latch it, so it
        # fires in the SAME evaluation as i's Sweep -> Latch; next frame i's Open reads 0 and it is dead. Open and not
        # Front: Partial writes Open 1 with Front 0 and a full reading there (the rest of a partial admission arriving in
        # its grace step) latches and must hand off; a reading in SweepShut is impossible, its flag being shut and its
        # boxes collapsed in Armed, so Open admits no false source.
        conds = [f"{si}/Open greater 0.5"] + [f"{si}/{ax} greater 0" for ax in ax4] + ring
        o(f"          - {{ to: SweepShut, when: [ {', '.join(conds)} ] }}   # ring on the readings: slot {i} latched, nothing Armed between")
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j < k]
    conds += [f"{me}/Armed greater 0.5"]
    o(f"          - {{ to: SweepShut, when: [ {', '.join(conds)} ], exitTime: 1.0 }}   # self-open: nothing holding the front, no lower Armed; re-checked only on a crossing, so it costs at most one stepSeconds with nothing riding — the common-path recovery when the ring's one-frame handoff finds no taker")
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
    o(f"          - {{ to: Latch, when: [ {all_pos} ] }}   # this slot's own admission: the readings, a step after the front-size cube took the hand; the Sweep layer freezes the front on the same predicate")
    for ax in ax4:
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    # No exit at the face. The Sweep layer restarts the front there and this cube collapses with it (front_scale × Sweep
    # reads 0 over the collapsed base scale), which ends every overlap it was rejecting, and the next pass regrows it
    # from the centre with the flag still up.
    o("      Partial:                     # one box read a hand the others did not: a step's grace at the current front, else Recycle — a slot holding the front may never stall")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} partial")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_open_wait, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {all_pos} ] }}   # the rest of the reading arrived: Partial writes Open 1, so the ring hands off on this the same frame")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Latch:                       # flag shut + hold cube in one write; readout parked outside the zone; dwells one collision step so TrackOut reads the hold cube's readings")
    o(f"        motion: {{ clip: slot{k}_latch }}")
    o("        transitions:")
    rungs()
    # The readings rung carries the dwell's exit time: TrackOut reads hold-size readings only once a collision step has
    # sampled the expanded cube, and the frame after the latch may carry none above 60 fps (the docstring's Latch rule).
    # It is listed FIRST deliberately, and the ordering — not latchSeconds — is what survives a hitch: a frame longer
    # than the whole dwell makes this rung and the fallback eligible in the same evaluation, and first-match takes
    # this one. Do not reorder these to "simplify" the ladder.
    o(f"          - {{ to: TrackOut, when: [ {all_pos} ], exitTime: 1.0 }}")
    # A cut on the expansion: the hold-size step zeroes the readings (a crowd's shared pair budget does this to the
    # cube that just grew). Without this rung the slot would stand expanded and shut for latchSeconds doing nothing.
    for ax in ax4:
        o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}   # the readings fell on the expansion step: release now, as the tracking states do")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }   # neither rung read anything: the terminal fallback")
    o("      TrackOut:                    # readout live, payload off; outside the burst radius. Entered only from Latch, so the fresh dedup rungs below run on a fresh admission; the settled rungs in TrackIn and TrackBand re-run a tighter test for the life of the track")
    emit_tree(o, c, k, hold=f"slot{k}_hold")
    o("        transitions:")
    rungs()
    dedup_rungs(settled=False)
    release()
    o(f"          - {{ to: TrackIn, when: [ {inside} ] }}")
    # Fresh ends once the readout is live, not only by reaching the zone: the front re-offers every held hand each
    # pass, and a holder that stayed fresh would be re-taken by every lower-index rider under the fresh-versus-fresh
    # rule, hopping slots once a pass. The gate is r² off the Latch park (the tables' own reading of it), which lands a frame after D does, so
    # by the time this rung is eligible the dedup rungs above have read the second reading's D as well, and a hitch
    # frame on the first evaluation cannot settle a duplicate before dedup has had that frame. Checked at each
    # crossing of the tree's own period (a Direct tree's length is data: the weighted sum of its one-frame children,
    # the four square tables at weight one included, so about eight frames at 60 fps); listed last, so any
    # rung above that is eligible on the same frame wins. A hand grazing the park's corner of the hold cube reads the
    # park's r² and stays fresh there, which costs nothing but the re-take above.
    o(f"          - {{ to: TrackBand, when: [ {me}/r2 less {fmt(park_r2(c) - 1e-4)} ], exitTime: 1.0 }}   # readout live and still outside the zone: settle (r2 off the park, not p2: the zone's own predicate is above)")
    o("      TrackIn:                     # inside the burst radius in-plane (p2); the payload is on (one burst per entry, a marker visible throughout); settled dedup runs here. No height rung: a hand leaving through the cube's end takes the axis floor above")
    emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
    o("        transitions:")
    rungs()
    release()
    dedup_rungs(settled=True)
    for conds in outside:
        o(f"          - {{ to: TrackBand, when: [ {', '.join(conds)} ] }}")
    o("      TrackBand:                   # settled outside the zone, by retreating past the re-arm radius in-plane or by holding outside it past the fresh window: TrackOut's rungs with the settled dedup test in place of the fresh one" + ("; the far release lives here" if c["farRadius"] is not None else ""))
    emit_tree(o, c, k, hold=f"slot{k}_hold_band")
    o("        transitions:")
    rungs()
    release()
    dedup_rungs(settled=True)
    if c["farRadius"] is not None:
        # Here and nowhere else: TrackBand is reached with live readings (the fresh window off the Latch park, or the
        # re-arm crossing), where TrackOut's first evaluation can read hold coefficients over front-size floats above
        # 60 fps and would push a newcomer's p2 outward past any far radius for one frame. The far, dedup and release
        # rungs all go to Recycle and the far rung and TrackIn are exclusive, so the order among them is free.
        o(f"          - {{ to: Recycle, when: [ {me}/p2 greater {fmt(c['farRadius'] ** 2)} ] }}   # far release: settled past farRadius {c['farRadius']} m in-plane; the front re-offers it every pass")
    o(f"          - {{ to: TrackIn, when: [ {inside} ] }}")
    o("      Recycle:                     # collapsed for a step, flag shut: every overlap this slot held ends; then straight onto the front, or Armed")
    o(f"        motion: {{ clip: slot{k}_recycle }}")
    o("        transitions:")
    rungs()
    # The shortcut onto the front: with nothing holding it and nothing Armed, this is the slot that would self-open
    # after another step in Armed, so it goes to SweepShut directly and saves that step on every duplicate release. The
    # lower-index Held reads are the tie-break: every flag here is an AAP read one frame late, and two slots releasing
    # on one frame would each see the other as neither Open nor Armed (Recycle writes both 0) and both ride the front.
    # Requiring every lower slot to read Held sends the higher one to Armed, where the ordinary self-open rule (no
    # lower Armed) resolves it a step later. A lower slot in Latch reads Held 0 as well, which costs that one step and
    # nothing else.
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Held greater 0.5" for j in ks if j < k]
    o(f"          - {{ to: SweepShut, when: [ {', '.join(conds)} ], exitTime: 1.0 }}   # nothing holding the front, nothing Armed, every lower slot holding: straight onto the front")
    o("          - { to: Armed, when: [], exitTime: 1.0 }")
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], Armed: [30, 360], SweepShut: [-210, 360], Sweep: [-210, 450], Partial: [270, 450], Latch: [30, 540], TrackOut: [-210, 630], TrackIn: [270, 630], TrackBand: [30, 630], Recycle: [30, 720] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_sweep_layer(o, c, ks):
    """The one writer of the three shared sweep AAPs. Every state writes all three — a WD-ON state
    reverts any AAP it does not write to its default (measured on this rig), so a value that
    must persist across a state is written back to itself through a direct child weighted by
    its own value. SweepPrev is the same idiom read one frame late on purpose: in Ramp a child
    weighted by Sweep writing 1 lands Sweep(F-1) in it, which is the size the last admitting
    flag-up cube had and therefore the size the next slot's shut cube must appear at. Wait holds
    it off itself (weight SweepPrev): Wait is entered on the admission frame, when Sweep already
    reads the frozen front one frame past that size, and a copy there would hand the successor a
    cube one frame of travel too large on its second shut frame. Restart is the pass boundary: a
    plain clip of stepSeconds parking all three at 0, so the sweeper's cube is collapsed for a
    sampled collision step (every overlap it held ends) before the next pass grows from the centre."""
    P = c["prefix"]
    en = c["enable"]
    acq = c["acqHalf"]
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
    o("    # The expanding front, shared by every slot: Sweep (the front half-extent, m), SweepBase (where the current")
    o("    # sweeper's ramp started) and SweepPrev (last frame's front, which the next slot's shut cube rides). Slot layers")
    o("    # read these and never write them; each slot reports its own Front flag (1 in its Sweep state) for this layer to")
    o("    # ramp on. The front runs whenever a slot rides it and restarts from 0 at the face, so every hand inside the cube")
    o("    # is offered to exactly one flag-up cube once per pass.")
    o("    # Its second job: every state writes the Boundary meshes' scale and renderer enable (one state is always live here).")
    o("    states:")
    o("      Boot:                        # a fresh animator: the first pass runs from 0")
    o("        motion: { clip: sw_boot }")
    o("        transitions:")
    o(paused)
    o(off)
    o(f"          - {{ to: Wait, when: [ {en} is true ] }}")
    o("      Disabled:                    # the toggle is off: the next pass runs from 0")
    o("        motion: { clip: sw_off }")
    o("        transitions:")
    o(paused)
    o(f"          - {{ to: Wait, when: [ {en} is true ] }}")
    o("      Paused:                      # a distance-hide: the resume pass runs from 0")
    o("        motion: { clip: sw_paused }")
    o("        transitions:")
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Wait, when: [ IsAnimatorEnabled is true, {en} is true ] }}")
    o("      Wait:                        # nothing rides the front: it holds, SweepBase latches it, SweepPrev holds")
    hold_tree("Sweep wait", [("sw_shown", f"{P}/One"), ("sw_hold_sweep", f"{P}/Sweep"), ("sw_latch_base", f"{P}/Sweep"), ("sw_hold_prev", f"{P}/SweepPrev")])
    o("        transitions:")
    o(paused)
    o(off)
    for k in ks:
        o(f"          - {{ to: Ramp, when: [ {slot_name(c, k)}/Front greater 0.5 ] }}")
    o("      Ramp:                        # a slot's flag is up: the front grows from SweepBase at the configured speed")
    hold_tree("Sweep ramp", [("sw_ramp", f"{P}/One"), ("sw_hold_sweep", f"{P}/SweepBase"), ("sw_hold_base", f"{P}/SweepBase"), ("sw_hold_prev", f"{P}/Sweep")])
    o("        transitions:")
    o(paused)
    o(off)
    for k in ks:
        # The freeze: the sweeping slot's own readings (the slot layer's `all_pos`, verbatim) while its Front still reads
        # 1, which is the frame it latches — a frame before its Front flag drops. Ramp's clip is not sampled on the
        # frame it leaves, so the front stops at the size that admitted, and the successor's shut cube (× SweepPrev)
        # appears at exactly that size. Without it the front advances one more frame and leaves a band no cube ever
        # offered. `greater 0`, never the release floor: the slot layer latches on `greater 0`, and a predicate here
        # that read tighter would latch without freezing.
        # Listed BEFORE the restart rung, not after: on a pass's last handoff the front has already read past the
        # face, so both rungs are eligible in the same evaluation and first-match decides. A restart on the admission
        # frame would park SweepPrev at 0 under the successor's shut cube, entered on the same evaluation, and re-run
        # the pass with the just-admitted hand's slot still in Latch; the freeze wins whenever both are eligible. A hand
        # taken on the frame the front crosses the face has no reading yet, and there Restart wins (the docstring's
        # restart race): the admission survives and the just-taken hand is re-offered once.
        sk = slot_name(c, k)
        o(f"          - {{ to: Wait, when: [ {sk}/Front greater 0.5, {', '.join(f'{sk}/{ax} greater 0' for ax in axes(c))} ] }}   # slot {k} latched: freeze the front on the admission frame")
    o(f"          - {{ to: Restart, when: [ {P}/Sweep greater {fmt(acq)} ] }}   # the face: the pass is over, the next one runs from 0")
    o(f"          - {{ to: Wait, when: [ {fronts_down} ] }}   # nothing rides (a Partial stepped aside, or the pass's last handoff found no taker): hold the front for the next slot's shut step")
    o("      Restart:                     # the pass boundary: the front parked at 0 for a sampled step, so the sweeper's cube collapses and every overlap it held ends")
    o("        motion: { clip: sw_restart }")
    o("        transitions:")
    o(paused)
    o(off)
    o("          - { to: Wait, when: [], exitTime: 1.0 }")
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], Wait: [30, 360], Ramp: [270, 360], Restart: [30, 450] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_sweep_clips(o, c):
    P = c["prefix"]
    T = c["sweepSeconds"]
    acq = c["acqHalf"]
    step = c["stepSeconds"]
    reach = acq * 1.05   # the ramp aims a little past the face so `Sweep greater acqHalf` fires before it ends

    def clip(name, sets, seconds=None, comment=None):
        emit_clip(o, name, sets, seconds, comment)

    def full(sweep, base, shown):
        # SweepPrev = Sweep in every plain-clip state: each of them parks the front, so last frame's front is this
        # frame's. Only the two tree states, where the front moves, need the one-frame lag a × Sweep child gives.
        d = {f"{P}/Sweep": fmt(sweep), f"{P}/SweepBase": fmt(base), f"{P}/SweepPrev": fmt(sweep)}
        d.update(boundary_bindings(c, shown))
        return d

    o("  # Sweep layer: constants, and the self-copies a hold needs (weight = the AAP's own value, the clip writes 1).")
    o("  # Every constant clip also writes the Boundary meshes: scale = the burst surface, renderer on only while enabled.")
    clip("sw_boot", full(0, 0, 0), None, "a fresh animator: front at 0")
    clip("sw_off", full(0, 0, 0), None, "the toggle off: front at 0")
    clip("sw_paused", full(0, 0, 0), None, "a distance-hide: front at 0")
    clip("sw_restart", full(0, 0, 1), step, "the pass boundary: front, base and previous front at 0 for a sampled step")
    clip("sw_shown", boundary_bindings(c, 1), None, "the constant part of Wait and Ramp: the boundary drawn")
    clip("sw_hold_sweep", {f"{P}/Sweep": 1}, None, "× Sweep (Wait: hold) or × SweepBase (Ramp: the ramp's origin)")
    clip("sw_hold_prev", {f"{P}/SweepPrev": 1}, None, "× Sweep (Ramp): SweepPrev ← last frame's Sweep (a Direct weight reads its parameter one frame late; SweepPrev's default 0 makes the fill term vanish, so the read is exact); × SweepPrev (Wait): hold")
    clip("sw_latch_base", {f"{P}/SweepBase": 1}, None, "× Sweep: SweepBase ← Sweep")
    clip("sw_hold_base", {f"{P}/SweepBase": 1}, None, "× SweepBase: hold")
    o(f"  sw_ramp:   # × One: the front's own travel, 0 → {fmt(reach)} m over {fmt(T)} s, linear, added to SweepBase")
    o(f"    seconds: {fmt(T)}")
    ramp_set = ", ".join(f"{k2}: {v}" for k2, v in boundary_bindings(c, 1).items())
    o(f"    set: {{ {ramp_set} }}")
    o("    curves:")
    o(f"      {P}/Sweep: {{ tangents: linear, keys: [ [0, 0], [{fmt(T)}, {fmt(reach)}] ] }}")


def ax_tag(ax):
    """The clip-name suffix for a receiver axis, the readout clips' spelling: X+ -> xp, X- -> xn."""
    return ax.replace("+", "p").replace("-", "n").lower()


def emit_dedup_layer(o, c, ks):
    """The one always-live layer: the pairwise difference of the raw readings the dedup rungs compare
    against dedupEpsilon (fresh) and SETTLED_EPSILON (settled)."""
    o("  - name: Dedup")
    o("    # One state, one tree, no transitions, and deliberately no Paused and no Disabled: a non-normalized Direct tree")
    o("    # writes every binding it carries every frame, so nothing here can revert, and a park state would only add a")
    o("    # frame on which the differences read their defaults.")
    o("    # D/<j>_<k>/<ax> = Slot<k>/<ax> - Slot<j>/<ax> for every pair and every axis, built from the RAW [0, 1]")
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
    o("  # Dedup layer: one clip per (slot, axis) carrying")
    o("  # every pair that slot is in — +1 where it is the pair's higher index, −1 where it is the lower — at weight = that")
    o("  # slot's own reading on that axis. One clip per (slot, axis) rather than one per (pair, axis, sign): the weight is")
    o("  # the same for every term it carries, and per D binding the children carrying it are still exactly the pair's two")
    o("  # slots, so the difference is the same arithmetic in a quarter of the children on a tree that runs every frame.")
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
        for i, t in enumerate(sq_knots(c)):
            o(f"                - {{ clip: slot{k}_sq_{i}, threshold: {fmt(t)} }}")
    # The yw² table subtracts the height's square out of p2, leaving the in-plane radius²; same chord width as the
    # axis tables over yw's wider span, so its error bound is theirs.
    M = yw_segments(c)
    o("            - tree: 1d")
    o(f"              name: Slot{k} −yw²")
    o(f"              param: {me}/yw")
    o(f"              directWeight: {P}/One")
    o("              children:")
    for i, t in enumerate(yw_knots(c)):
        o(f"                - {{ clip: slot{k}_nsq_{i}, threshold: {fmt(t)} }}")


def yw_segments(c):
    """The yw² table's segment count: lookupSegments scaled by sqrt3, so a segment is as wide as an axis table's."""
    return int(round(c["lookupSegments"] * SQRT3))


def readout_span(c):
    """The range one axis readout can take, which the square tables span exactly. Three-box: c = 2h·V − h − r over
    V in [0, 1] is [−h−r, h−r]; a knot short of −h−r would clamp the bottom r metres and read the square low, which
    under the sphere sat far outside the zone and under the cylinder, once the height's square is subtracted, can read
    a hand near the bottom corners inside the burst radius from past the re-arm radius. fourBox measures r out of the
    readout and spans exactly [−h, h]. The Latch park at (h, −h, −h) then lies off the knots and past the top one, so
    the settle guard compares r² against the table's own value at the park (`park_r2`), not the analytic 3h²."""
    h, r = c["holdHalf"], c["senderRadius"]
    return (-h, h) if c["fourBox"] else (-h - r, h - r)


def table_square(knots, v):
    """What the emitted 1D table reads for a value: the chord between the two nearest knots, clamped at the ends."""
    if v <= knots[0]:
        return knots[0] ** 2
    if v >= knots[-1]:
        return knots[-1] ** 2
    for a, b in zip(knots, knots[1:]):
        if a <= v <= b:
            w = (v - a) / (b - a)
            return (1 - w) * a * a + w * b * b


def park_r2(c):
    """r² as the tables read the Latch park (h, −h, −h): the settle rung's guard, so it is exact by construction."""
    h = c["holdHalf"]
    return sum(table_square(sq_knots(c), v) for v in (h, -h, -h))


def sq_knots(c):
    lo, hi = readout_span(c)
    N = c["lookupSegments"]
    return [lo + (hi - lo) * i / N for i in range(N + 1)]


def yw_knots(c):
    """yw = (x + y + z)/sqrt3 spans sqrt3 times one axis's range."""
    lo, hi = readout_span(c)
    M = yw_segments(c)
    return [SQRT3 * (lo + (hi - lo) * i / M) for i in range(M + 1)]


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

    def cfg(active, flag, scale, opn, armed, payload_on, front=0, held=0, settled=0):
        d = {f"{B}/GameObject.m_IsActive": active}
        for ax in axes(c):
            d[f"{B}/{ax}/VRCContactReceiver.allowOthers"] = flag
        if scale is not None:
            for ax in ("x", "y", "z"):
                d[f"{B}/Transform.m_LocalScale.{ax}"] = fmt(scale)
        # Open: 1 while this slot holds the front position — SweepShut (shut), Sweep (flag up, Front 1 too) and
        # Partial. The name predates the always-running front, when it also meant a full-size cube; the self-open
        # rung and the ring rungs read it.
        d[f"{me}/Open"] = opn
        d[f"{me}/Armed"] = armed
        d[f"{me}/Front"] = front
        # Held: this slot is holding a sender (every post-latch state). Settled: and that sender has reached the
        # zone, or the re-arm band after it — every held state but TrackOut, the fresh one. The dedup rungs read
        # another slot's pair, so every state must write both — a state that wrote neither would leave a stale 1
        # standing and make a newcomer yield to a slot that has already released.
        d[f"{me}/Held"] = held
        d[f"{me}/Settled"] = settled
        d[payload] = payload_on
        # The buffer particle's GameObject is forced on in every state: nothing in the rig turns it off, and the
        # binding is kept so a copy whose Burst was saved inactive still fires on the payload edge.
        d[buffer] = 1
        return d

    def clip(name, sets, seconds=None, comment=None):
        emit_clip(o, name, sets, seconds, comment)

    o(f"  # Slot {k} configurations — every one writes the box stow, the flag on every receiver, the scale, the five protocol flags, the payload toggle and the buffer particle's force-on.")
    clip(f"slot{k}_boot", cfg(0, 0, acq, 0, 0, 0), step, "stowed (a fresh animator)")
    clip(f"slot{k}_off", cfg(0, 0, acq, 0, 0, 0), step, "stowed; a stow shorter than a step comes back deaf")
    clip(f"slot{k}_paused", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed through the pause")
    clip(f"slot{k}_armed", cfg(1, 0, collapsed, 0, 1, 0), step, "Armed 1, collapsed: holds no rejections; the ring rule reads Armed one frame late")
    clip(f"slot{k}_sweepshut", cfg(1, 0, collapsed, 1, 0, 0), step, "Open 1, flag shut, base scale: the front's own re-rejection step (the tree adds × SweepPrev)")
    clip(f"slot{k}_sweep_cfg", cfg(1, 1, collapsed, 1, 0, 0, front=1), None, "Open 1, Front 1, flag up, base scale: the growing cube's constant part")
    clip(f"slot{k}_front_scale", {f"{B}/Transform.m_LocalScale.{ax}": fmt(per_m) for ax in ("x", "y", "z")},
         None, "× Sweep: the cube at the front")
    clip(f"slot{k}_open_wait", cfg(1, 1, collapsed, 1, 0, 0), step, "Open 1 held a step at base scale: the partial-admission grace")
    latch = cfg(1, 0, hold, 0, 0, 0)
    # Parked at (h, −h, −h): x at +h is the sentinel a consumer reads as "not yet tracking"; r² reads the tables' value
    # there (park_r2, about 3h²). yw parks at the same point's height, −h/sqrt3, so the first p2 the tree computes is
    # about 8h²/3 and not r² minus a stale square left over from the last track, which could read inside the zone for
    # that one frame.
    latch.update({f"{me}/x": fmt(h), f"{me}/y": fmt(-h), f"{me}/z": fmt(-h), f"{me}/yw": fmt(-h * YW_PER_AXIS)})
    if c["fourBox"]:
        # The one frame before the first measurement lands: R carries the configured assumption
        # rather than zero. Outside a track R is 0, like x, y and z — no state writes it there.
        latch[f"{me}/R"] = fmt(r)
    clip(f"slot{k}_latch", latch, c["latchSeconds"], "flag shut + hold cube in one write; readout parked at (h, −h, −h) so r² reads 3h²; the dwell spans a collision step at the hold size, left early only by a cut")
    clip(f"slot{k}_hold", cfg(1, 0, hold, 0, 0, 0, held=1), None, "tracking configuration, payload off, fresh (outside the zone, never yet inside it)")
    clip(f"slot{k}_hold_band", cfg(1, 0, hold, 0, 0, 0, held=1, settled=1), None, "tracking configuration, payload off, settled (the re-arm band, or fresh no longer)")
    clip(f"slot{k}_hold_burst", cfg(1, 0, hold, 0, 0, 1, held=1, settled=1), None, "tracking configuration, payload on (inside the zone)")
    clip(f"slot{k}_recycle", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed for a step, flag shut: a fresh overlap episode for everything inside, the re-arm primitive")
    two_h = fmt(2 * h)
    if c["fourBox"]:
        o(f"  # Slot {k} readout, four boxes: the opposed X pair measures the sender's radius instead of assuming it —")
        o("  # r = h·X+ + h·X− − h and x = h·X+ − h·X− (box-tracker's derivation), so y = 2h·Y+ − h·X+ − h·X− and z likewise;")
        o("  # every constant cancels out of x, y and z, leaving pure per-reading coefficients and a bias clip carrying only r.")
        o("  # yw = (x + y + z)/sqrt3 = (−h·X+ − 3h·X− + 2h·Y+ + 2h·Z+)/sqrt3, the same sums over the tilted diagonal: no bias.")
        o("  # Summed under the non-normalized Direct root into the AAPs, R and Output's localPosition (metres, Size frame).")
        pos, neg = fmt(h), fmt(-h)
        yw = lambda v: fmt(v * YW_PER_AXIS)
        clip(f"slot{k}_read_xp", {f"{me}/x": pos, f"{me}/y": neg, f"{me}/z": neg, f"{me}/R": pos, f"{me}/yw": yw(-h),
                                  f"{O}/Transform.m_LocalPosition.x": pos,
                                  f"{O}/Transform.m_LocalPosition.y": neg,
                                  f"{O}/Transform.m_LocalPosition.z": neg})
        clip(f"slot{k}_read_xn", {f"{me}/x": neg, f"{me}/y": neg, f"{me}/z": neg, f"{me}/R": pos, f"{me}/yw": yw(-3 * h),
                                  f"{O}/Transform.m_LocalPosition.x": neg,
                                  f"{O}/Transform.m_LocalPosition.y": neg,
                                  f"{O}/Transform.m_LocalPosition.z": neg})
        clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{me}/yw": yw(2 * h), f"{O}/Transform.m_LocalPosition.y": two_h})
        clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{me}/yw": yw(2 * h), f"{O}/Transform.m_LocalPosition.z": two_h})
        clip(f"slot{k}_read_bias", {f"{me}/R": neg}, None, "the measured radius is the only term left with a constant")
    else:
        o(f"  # Slot {k} readout: c = 2h·V − h − r per axis (face proximity is linear from the +Z face; V is the box reading),")
        o("  # summed under the non-normalized Direct root into both the AAPs and Output's localPosition (metres, cage frame).")
        o("  # yw = (x + y + z)/sqrt3, the height above the cage centre: 2h/sqrt3 per reading and a bias of −3(h + r)/sqrt3.")
        bias = fmt(-h - r)
        yw = lambda v: fmt(v * YW_PER_AXIS)
        clip(f"slot{k}_read_xp", {f"{me}/x": two_h, f"{me}/yw": yw(2 * h), f"{O}/Transform.m_LocalPosition.x": two_h})
        clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{me}/yw": yw(2 * h), f"{O}/Transform.m_LocalPosition.y": two_h})
        clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{me}/yw": yw(2 * h), f"{O}/Transform.m_LocalPosition.z": two_h})
        clip(f"slot{k}_read_bias", {f"{me}/x": bias, f"{me}/y": bias, f"{me}/z": bias, f"{me}/yw": yw(-3 * (h + r)),
                                    f"{O}/Transform.m_LocalPosition.x": bias,
                                    f"{O}/Transform.m_LocalPosition.y": bias,
                                    f"{O}/Transform.m_LocalPosition.z": bias})
    lo, hi = readout_span(c)
    o(f"  # Slot {k} x² table: {N} segments over [{fmt(lo)}, {fmt(hi)}], the readout's whole range, so nothing clamps; each 1D tree blends")
    o("  # the two nearest knots, a chord that overestimates by ≤ w²/4. On three boxes a true coordinate past the + face, in")
    o("  # (h − r, h + r), reads h − r at the receiver itself: the square then reads low, and near the hold faces past the band")
    o("  # p2 can read a hand inside the burst radius from a little outside it (README §Traps).")
    o("  # Each square clip writes r2 (the distance² from the centre, exported) and p2 (the in-plane radius² the zone reads) alike;")
    o("  # the −yw² table below then takes the height's square back out of p2 alone. Its chord overestimates yw² and so reads")
    o("  # p2 low by up to the same w²/4, an outward bias of the zone that the axis tables' inward bias partly cancels.")
    for i, t in enumerate(sq_knots(c)):
        clip(f"slot{k}_sq_{i}", {f"{me}/r2": fmt(t * t), f"{me}/p2": fmt(t * t)})
    yk = yw_knots(c)
    o(f"  # Slot {k} −yw² table: {len(yk) - 1} segments over [{fmt(yk[0])}, {fmt(yk[-1])}], yw's whole range.")
    for i, t in enumerate(yk):
        clip(f"slot{k}_nsq_{i}", {f"{me}/p2": fmt(-t * t)})


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
    o(f"# contact-radar: {K} per-sender slots, tags {c['tags']}, {len(axes(c))} coincident face-proximity boxes each; the readings are the latch.")
    o("# The acquisition cube is tilted (diagonal vertical) on the prefab; the readout is in that frame, and yw = (x + y + z)/sqrt3")
    o("# undoes the tilt on the vertical axis alone. The zone is a vertical cylinder: p2 = x² + y² + z² − yw² is the in-plane radius².")
    far = f", far release at p2 > {fmt(c['farRadius'] ** 2)} ({c['farRadius']} m, TrackBand only)" if c["farRadius"] is not None else ""
    o(f"# Burst at p2 < {fmt(rin2)} (R_in {c['burstRadius']} m), re-arm at p2 > {fmt(rout2)} (R_out {c['rearmRadius']} m){far}; no height bound:")
    o(f"# a hand at the burst radius is inside the acquisition cube from every direction within ±{fmt(band_half_height(c, c['burstRadius']))} m")
    o("# of the centre height, and past that band the cube's corners are the zone's ends.")
    rtxt = (f"sender radius measured per slot from the X- box ({c['senderRadius']} m is the lints' assumed maximum)"
            if c["fourBox"] else f"sender radius {c['senderRadius']} m")
    o(f"# Cube half-extents: acquisition {c['acqHalf']} m, hold {c['holdHalf']} m; {rtxt}; step dwell {c['stepSeconds']} s, latch wait {c['latchSeconds']} s.")
    o(f"# One slot at a time rides an expanding front from the centre to the face over {c['sweepSeconds']} s, and the front restarts")
    o("# there, so every hand inside the cube is offered to exactly one flag-up cube per pass and admitted alone as the front")
    o("# reaches it; the Dedup layer releases a re-admitted hand another slot already holds.")
    o("# Per-client: every copy of the avatar senses on its own client (receivers localOnly 0);")
    o("# one synced bit (the enable) and nothing else crosses the wire. generate.py's docstring")
    o("# carries the mechanism; the README carries the traps.")
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
    o("  # The front (written only by the Sweep layer): Sweep is the front half-extent (m), SweepBase the front the current")
    o("  # sweeper's ramp started from, SweepPrev last frame's Sweep — the size the next slot's shut cube appears at, so the")
    o("  # handoff leaves no band.")
    o(f"  {P}/Sweep: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepBase: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepPrev: {{ type: float, aap: true, scratch: true }}")
    for k in ks:
        me = slot_name(c, k)
        o(f"  # Slot {k}: receiver floats (never a clip), the readout AAPs, and the five protocol flags.")
        for ax in axes(c):
            o(f"  {me}/{ax}: float")
        for ax in ("x", "y", "z", "r2"):
            o(f"  {me}/{ax}: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/yw: {{ type: float, aap: true, scratch: true }}   # the hand's height above the cage centre, m: (x + y + z)/sqrt3 undoes the tilt on that axis")
        o(f"  {me}/p2: {{ type: float, aap: true, scratch: true }}   # the in-plane radius², r2 − yw²: what the zone compares")
        if c["fourBox"]:
            o(f"  {me}/R: {{ type: float, aap: true, scratch: true }}   # the measured sender radius, m — the export a consumer reads")
        o(f"  {me}/Open: {{ type: float, aap: true, scratch: true }}   # 1 while this slot holds the front position: shut at SweepPrev, riding it flag-up, or in Partial")
        o(f"  {me}/Armed: {{ type: float, aap: true, scratch: true }}   # 1 while collapsed and waiting for the ring")
        o(f"  {me}/Front: {{ type: float, aap: true, scratch: true }}   # 1 while this slot's cube rides the front")
        o(f"  {me}/Held: {{ type: float, aap: true, scratch: true }}   # 1 while this slot holds a sender: every state past Latch")
        o(f"  {me}/Settled: {{ type: float, aap: true, scratch: true }}   # 1 once the sender it holds has reached the zone (inside it, or in the re-arm band after) or has been held outside it past the fresh window: a fresh lower-index slot yields to a settled holder")
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
    facts = {"K": K, "fourBox": c["fourBox"], "farRadius": c["farRadius"],
             "receivers": len(axes(c)) * K, "syncedBits": 1,
             "bandHalfHeight": band_half_height(c, c["burstRadius"]),
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
    axis its parameter names. A leftover `Hit` receiver (the Constant box earlier builds carried)
    is refused by name: nothing animates it any more, so it would stand at its saved flag and
    grow with every latch, costing exactly the contact pairs its removal bought."""
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
    # The Constant `Hit` box earlier builds carried per slot. Told apart by its parameter suffix before the axis loop
    # below reaches it, so the refusal names the node rather than three wrong-want asserts and a rotation lookup on an
    # axis that does not exist.
    hit = [d for d in slots if re.search(rf"^  parameter: {pre}/Slot\d+/Hit$", d, re.M)]
    ok = assert_(not hit,
                 f"no receiver on {c['prefix']}/Slot<k>/Hit (got {len(hit)}): the Constant Hit box was removed from the rig; delete the"
                 " Hit node under every slot's Boxes in this copy — nothing animates it, so it would stand at its saved flag and"
                 " grow with every latch, costing the contact pairs its removal bought") and ok
    recv = [d for d in slots if d not in hit]
    ok = assert_(len(recv) == len(ax4) * c["K"],
                 f"{label}: {len(recv)} slot receivers == {len(ax4)}K ({len(ax4)} face-proximity boxes per slot)" + addx) and ok
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
    expect = sorted(f"{c['prefix']}/Slot{k}/{ax}" for k in range(1, c["K"] + 1) for ax in ax4)
    ok = assert_(sorted(p or "" for p in params) == expect,
                 f"receiver parameters are exactly {c['prefix']}/Slot1..{c['K']}/{' '.join(ax4)}, one each" + addx) and ok
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
    # The boundary: one inactive Boundary under Size holding Cylinder, a MeshFilter on the unit open-tube OBJ mesh
    # with its renderer enabled — the controller rewrites scale and enable live, so the saved enable is
    # what makes the edit-mode preview honest.
    if here is None:
        return ok   # the boundary is the entry's opt-in preview; a copy may have dropped it
    bnd = [tid for tid, (go, _, _) in trs.items() if gos[go] == "Boundary"]
    ok = assert_(len(bnd) == 1 and parent_name(bnd[0]) == "Size", "exactly one Boundary node, under Size") and ok
    if bnd:
        bgo = next(d for d in docs if d.startswith(f"1 &{trs[bnd[0]][0]}\n"))
        ok = assert_(re.search(r"^  m_IsActive: 0$", bgo, re.M) is not None, "Boundary ships inactive (the consumer's opt-in)") and ok
    ok = assert_(not [tid for tid, (go, _, _) in trs.items() if gos[go] == "Sphere" and parent_name(tid) == "Boundary"],
                 "no Sphere node under Boundary: the zone is a cylinder and the sphere preview was removed") and ok
    for name, mesh in (("Cylinder", "UnitCylinder.obj"),):
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
    """The unit mesh the Boundary node holds, as OBJ text: an open tube of radius 1 spanning y in
    [-1, 1], its ends undrawn because the zone has none. The controller scales it to the burst radius
    and the guaranteed band."""
    import math

    def obj(path, verts, normals, faces, name):
        L = [f"# {name} — GENERATED by generate.py --mesh; unit size, scaled by the controller", f"o {name}"]
        L += [f"v {fmt(x)} {fmt(y)} {fmt(z)}" for x, y, z in verts]
        L += [f"vn {fmt(x)} {fmt(y)} {fmt(z)}" for x, y, z in normals]
        L += ["f " + " ".join(f"{i + 1}//{i + 1}" for i in f) for f in faces]
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(L) + "\n")

    seg = 48
    verts, normals, faces = [], [], []
    for y in (-1.0, 1.0):
        for i in range(seg + 1):
            th = 2 * math.pi * i / seg
            verts.append((math.cos(th), y, math.sin(th)))
            normals.append((math.cos(th), 0.0, math.sin(th)))
    for i in range(seg):
        a, b = i, seg + 1 + i
        faces.append((a, b, a + 1))
        faces.append((a + 1, b, b + 1))
    obj(os.path.join(assets, "UnitCylinder.obj"), verts, normals, faces, "UnitCylinder")


def main():
    if "--mesh" in sys.argv:
        write_meshes(os.path.join(HERE, "assets"))
        print("wrote assets/UnitCylinder.obj")
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
    print(f"wrote controller.yaml and assets/UnitCylinder.obj — K={facts['K']}, {facts['receivers']} receivers, {facts['syncedBits']} synced bit; "
          f"the burst radius is reached from every direction within ±{facts['bandHalfHeight']:.2f} m of the centre height")


if __name__ == "__main__":
    main()
