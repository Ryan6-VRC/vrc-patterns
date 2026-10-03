#!/usr/bin/env python3
"""contact-radar generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ in a mounting Editor —
the controller.yaml committed here is generated output and the repo gate holds
built/ to it, so hand-editing it desynchronises the document from both this
generator and the compiled controller. `--check` asserts the hand-maintained
prefab surface no compile or gate reads (README §Changing it).

What it builds: K per-sender "slots", one FX layer each. A slot is three
coincident face-proximity box receivers (X+, Y+, Z+ — four under `fourBox`,
below) under one `Boxes` node, each on an animated `allowOthers` flag. The flag
is the latch: a sender whose overlap with a receiver began while the flag was
shut stays invisible to that receiver for the whole overlap, however the flag
moves later, and only a full exit and re-entry admits it (docs/runtime.md
§Contacts). No slot ever sits open at full size. Exactly one slot rides the
front: a cube growing from the centre to the acquisition face over
`sweepSeconds`, flag up, so each sender inside is admitted alone as the front
reaches its tilted Chebyshev radius; every other free slot is Armed, collapsed,
holding no rejection. The admission shows as the readings: every riding box
reads above zero on the collision step after the front-size cube took the
sender, and that readings rung (`ride_pos`, X+ Y+ Z+ `greater 0`) is the latch.
`ride_pos` never reads X-: under `fourBox` the fourth box rides collapsed with
its flag shut, so it admits nothing that would skew the first measurement, and
opens only at the placement (below). The next Armed slot in ring order takes
the front in the same animator evaluation, reading the latcher's stale Open and
the same fresh readings: it appears SHUT at last frame's front for a step
(re-rejecting the sender just taken and everything else inside), then rides on
flag-up, so the admission windows tile. When no neighbour fires, the self-open
rung recovers within one stepSeconds. The `Open` AAP means "this slot holds the
front position" (shut at it, riding it, or in Partial).
The slots sit tilted, the cube's diagonal vertical, so a standing player's
stacked senders meet a face at staggered depths instead of one vertical plane
in one step (README §How it works); every position below is in that frame.

The hold is a follower, not a cube. A latched slot shrinks its boxes to a small
cluster at the sender's decoded point and moves the cluster with the sender
every frame; the cluster's centre is owned by the animator as parameters and
written to `Boxes`' localPosition, since the animator cannot read a transform
it does not write. The rig's standing
contact-pair load is then one pair per receiver per sender inside the cluster,
not per sender inside a cage-sized hold cube. The placement, in three states:
- `Latch`, one evaluation: decodes the sender's point from the three riding
  readings at the front size that admitted it, per axis 2·F·V − F − r, with V
  the reading, r `senderRadius` and F the slot's own front-size register
  (`Slot<k>/F`, written in Sweep and Partial from `CR/Sweep` one frame late and
  read by Latch alone; a slot-local copy because Restart parks SweepPrev at 0 on the
  pass boundary and an admission on that frame would decode against zero).
  F·V is a product of two parameters, so the decode is a nested Direct tree: a
  child weighted by F holding a tree whose children are weighted by the
  readings. An axis whose reading is the clamp, exactly 1.0, adds 2·r: the
  admitting face reads 1.0 because the sender straddles it, the overlap having
  begun when the front reached the sender's near surface, so its centre sits
  about F + r out where the decode gives F − r (a 1D tree per riding axis on its
  raw reading, 0 at 0.999 and 2·r at 1.0). The point goes to `Boxes`' position,
  to every centre register and to Mem; the riding flags shut, the boxes shrink to `placeHalf`, X- opens flag
  up there (fourBox), the readout parks, Held 1. Latch leaves on its own `Held
  greater 0.5`, false on the entry evaluation and true on the next, so the
  decode samples front-size readings only: a tree state re-samples every frame,
  and once the shrunk cluster's readings land the same tree would decode them
  with front-size coefficients and throw the cluster off the sender.
- `LatchWait`, 2·stepSeconds plus its tree's register term: everything held. A freshly
  opened Proximity receiver reads exactly 0 on its first colliding step and its
  value on the second (docs/runtime.md §Contacts), which is X-'s case. A riding
  axis at the floor recycles at once (a cut on the shrink step, or a merge
  corner that holds nothing); every axis reading takes LatchGrow; the fallback
  recycles (X- never read: the sender's surface was not inside the placement
  cluster on its axis).
- `LatchGrow`, `latchSeconds` plus its tree's register term: every flag shut, the cluster grown to
  `followHalf`, so a step samples the grown cluster before TrackOut decodes it. The dwell spans two
  collision steps, not one: a remote clone's receiver values reach its animator about a frame later
  than the wearer's own, so a one-step dwell that holds on the wearer lets a clone's rider decode the
  placement cluster's readings with followHalf coefficients, miss dedupBand and fire the zone rung.
Why place small and grow after: a same-step merge of two senders latches to the
per-axis maximum of their readings, a corner on neither. A placeHalf cluster at
that corner keeps a sender only if it lies within placeHalf plus its radius of
the corner on every axis, so two senders farther apart than that both fall out,
the readings go to the floor and the slot recycles within a step. The sender
that does stay inside keeps its admission: an overlap that never breaks keeps
its episode through a scale and position change (the rig's own premise; README §Design notes).

The follower (TrackOut, TrackIn, TrackBand). Per slot the animator owns the
cluster centre `C/<x|y|z>`, the delayed copies `pairDelay` needs (`C1/…` at 2,
`C2/…` at 3, none at the default 1) and `Mem/…`, the last decoded point. Every one of them is stored
as (value + A)/S: a Direct weight clamps negative to zero, and a Direct tree's
length is Σ(weight × child length), so a register read as a weight must be
non-negative and small. A = B + 1 and S = 16 keep every register in (0, 0.5)
for any point within the bound B (below), so each one-frame copy child adds
under half a frame to its state's length; each dwell states the bound computed
from it. A clip writing a signed quantity from a register carries S per unit,
and the −A rides the state's weight-One configuration clip; a clip copying a
register writes 1; every register defaults to 0, so the below-one rest fill of
a Direct tree contributes nothing. Each frame, in a track state:
1. the offset of the sender from the cluster centre decodes from the readings
   with box-tracker's readout at h = followHalf (three boxes and senderRadius,
   or four and the measured radius under fourBox);
2. the decoded point is the pairing register plus that offset, written to x, y,
   z, `Output`'s localPosition, Mem, and through the square tables to yw, r2,
   p2;
3. the new centre is (1 − g)·C + g·(pairing register + offset), g =
   `followGain`, written to C and to `Boxes`' localPosition.
Every AAP read as a weight is one frame late, so a child weighted by C reads the
centre written one evaluation back, by C1 two, by C2 three. The reading that
lands on an evaluation was sampled against the centre written `pairDelay`
evaluations earlier, so the pairing register is C for pairDelay 1, C1 for 2, C2
for 3, and the chain carries only the copies the pairing reads. Why g below 1:
a true sampling delay one frame off `pairDelay` puts the centre's one-frame
travel into the decoded point as error and feeds it into the next centre; at
g 1 that error grows without bound, at 0.5 it decays. Latch seeds every chain
register with the decoded point and every hold state copies them, so the chain
never reads a previous episode.

The decoded point is absolute in the tilted frame and spans ±B, B = acqHalf +
followHalf (the acquisition cube grown by the cluster): the square tables span
±B, the yw table √3 times that, the Latch park is (B, −B, −B) so r2 and p2 read
outside every zone there (and x at +B is the "not yet tracking" sentinel), and
TrackOut's settle rung keeps its guard r2 off the park (`park_r2`). B is also
the bound rung: a decoded point past it on any axis recycles, since a follower
has no face to release at and would otherwise follow a departing sender
indefinitely. The zone is a vertical cylinder about the cage centre with no
height bound: yw = (x+y+z)/sqrt3 is the sender's height (the tilt sends the
slot's (1,1,1) diagonal to world up), p2 = r² − yw² the in-plane radius², and
the payload fires when p2 crosses the burst radius. At the burst radius a
sender is inside the acquisition cube from every direction within a band of
half-height sqrt3·(acqHalf − r) − sqrt2·R about the centre
(`band_half_height`; the lint holds it above zero at the re-arm radius, and the
boundary draws it at the burst radius).

Reacquire, the cut. In a crowd a held sender can drop out of a receiver cluster
for one collision step (docs/runtime.md §Contacts); every axis reads 0. Any
axis at the floor in TrackIn or TrackBand takes the reacquire, three states
written twice (`emit_reacquire`, once per payload bit, since the payload is a
discrete binding a Direct tree cannot blend from a remembered flag):
`ReCollapse*` collapses the boxes at the cage centre for `stepSeconds` (the
overlap that re-forms after a cut meets the shut flag and is rejected for its
whole length; a collapse spanning a sampled step ends it, and only away from the
sender: a collapsed box at the sender's own point stays inside its sphere, so the
rejected overlap never breaks) and resets the whole chain to Mem
(the centre lags the sender; Mem is where it last decoded); `ReOpen*` opens all
boxes flag up at placeHalf on Mem and waits `reacquireSeconds` for every axis
to read; `ReShut*` shuts the flags and grows to followHalf for `latchSeconds`
(each of the three dwells its configured base plus its tree's register term)
before Track resumes. A second cut inside ReShut recycles, so one reacquire per
cut. Readout x, y, z, yw, R, Output, Held, Settled and the payload hold
throughout; r2 and p2 read 0 there (their tables do not ride these trees: four
one-frame tables would add four frames to every dwell); the latch states park
them outside every zone. `Re` is 1 in the six
states. TrackOut's two zone rungs wait on every other slot's Re: a reacquiring
slot's Mem is frozen at the cut, and a rider that re-took a fast sender could
decode it past dedupBand from there and burst on the duplicate. Re stands at
most stepSeconds + reacquireSeconds + latchSeconds (plus the computed tree
terms) per cut, so the gate cannot strand a newcomer. TrackOut, entered only
from LatchGrow, recycles on a floor instead: a fresh slot that loses its sender
before settling is given back. Every axis reading above 0.9999 at once is the
sender's avatar hidden, swapped or reloaded (docs/runtime.md §Contacts); it is
the first rung in every track state, so the follower never decodes that row.

Dedup, on positions. The front re-offers every held sender inside its reach once
per pass, so a riding slot re-admits senders other slots hold as the common
path. The `Dedup` layer publishes `D/<j>_<k>/<x|y|z>` = Mem_k − Mem_j in metres
(the common A cancels; the Mem registers are non-negative, so they are the
weights), and a track state releases itself when every axis of that difference
is inside ±dedupBand against a slot j that is Held: fresh (TrackOut) against any
Settled j and any lower-index j; settled (TrackIn, TrackBand) against a
lower-index Settled j. A slot in a Re* state holds Mem, Held and Settled, so a
rider that re-takes its sender still matches it. The phantom rungs release a
same-step merge of senders other slots hold: the merge is their per-axis
maximum, so for every assignment of the three axes to other slots that is not
all one slot, each assigned axis inside the band of its source and strictly
above every other source in the assignment there, every source Held and Settled
as the duplicate rung requires. A real single sender two merges each contain
sits at or below one of them somewhere and is left alone. Under fourBox a
merge across the opposed X boxes decodes x at the midpoint of its two X faces
and inflates R: `R greater maxSenderRadius` (senderRadius + dedupBand) recycles
one separated by more than the band, and one separated by less has its midpoint
within the band of both sources. A merge with an unheld member stays until that
member leaves the cluster (README §Traps).

Settling and the far release: TrackOut is left for TrackBand once the readout
is live (r² off the Latch park, checked at each period of the tree) with no rung
fired, so a sender held outside the zone settles rather than staying fresh and
being re-taken by every lower-index rider. With `farRadius` set (None by
default), a settled sender whose in-plane radius reads past it is let go: one
rung in `TrackBand` alone. A released slot Recycles: its boxes collapse at the
cage centre for `stepSeconds`, which ends every overlap it held, then it goes
straight back onto the front when nothing else is Armed or holding the front
and every lower-index slot is Held, else it queues as Armed. The lower-index
Held reads are the tie-break: every flag is read one frame late, and two slots
releasing on one frame would each see the other as neither Open nor Armed and
both ride; the higher goes to Armed instead.

The restart race: on the frame the front crosses the face the Sweep layer's
Restart rung and its freeze rungs can all be eligible, and nothing about an
admission is readable on the frame it happens, so a sender taken exactly at the
face can see Restart win before its readings exist; the successor's shut cube
then rides SweepPrev 0 and the new pass re-offers the just-taken sender while
its holder is still fresh: one extra dedup cycle at most once per pass. A
sender standing within one step of front travel inside the acquisition face is
met on the very step the front crosses it, its readings land after Restart has
collapsed the cube, and the slot reads a partial admission and recycles, every
pass, so that sender is never held until it moves (README §Traps).

`fourBox` restores box-tracker's fourth receiver, `X-`, coincident with the
other three and rotated so its +Z face is the cage's -X face. The opposed pair
measures the sender's own radius rather than taking it from CONFIG: r =
h(X+ + X- - 1) and x = h(X+ - X-), from which y = 2h·Y+ - h·X+ - h·X- and z
likewise, so the follower's offset carries no radius term. The measurement is
exported per slot as `<prefix>/Slot<k>/R`. X- carries its own scale binding,
written in every state: collapsed while the others ride the front, coincident
with them everywhere else. `senderRadius` still sets the placement offset under
fourBox (the fourth box does not ride), so a consumer sets it to its senders'
typical radius. The shipped prefab is three-box, so `--check` holds a fourBox
consumer's prefab to the fourth receiver.

Rules the emitted document keeps, each bought by a measurement or a doc line:
- Every step-spanning dwell is authored in seconds >= 2/60: at 60 fps and below
  every frame carries a collision step, but above it a step lands only every
  second or third frame, and a collapse or stow shorter than the longest gap
  between two steps can pass with none sampling it (docs/runtime.md §Contacts).
- Every slot state writes every scene binding and flag its layer owns: the box
  stow, every receiver's flag, `Boxes`' scale and localPosition, `Output`'s
  localPosition, X-'s scale
  under fourBox, Open, Armed, Front, Held, Settled, Re, the payload toggle and
  the buffer particle's force-on, zeros included: an AAP holds its last
  clip-written value and a scene binding holds whatever last wrote it
  (docs/runtime.md §Animator evaluation). One function, `cfg()`, is where that
  rule is enforced — every slot configuration clip goes through it, except
  the two clone states, which write the payload toggle and the buffer force-on
  only: on a mirror clone every transform is the wearer's.
- Every binding a tree state writes is also in that state's weight-One clip, so
  each binding's weight sum is at least one and the tree's sum is exact (no
  rest fill; docs/animator-schema.md §motions); a register binding is exact
  without one because it defaults to 0.
- Every value that must persist through a tree state is written back to itself
  there through a child weighted by its own value (docs/runtime.md §Animator
  evaluation): the chain and Mem in every hold state, R in Re*, and F within
  Latch, its one reader, so a second Latch evaluation decodes at the same size.
- A dwell inside a tree state is an exit-time rung, and a Direct tree's length
  is data (Σ weight × child length): every such dwell (LatchWait, LatchGrow, the
  six Re* states, TrackOut's fresh window) is its configured base plus the tree's
  register and reading terms, never an exact elapsed wait, and its comment states
  the bound the generator computes from the weight maxima.
- Ladders list the readings rung before the fallback, and that ordering — not
  the duration — is what survives a hitch frame longer than the whole dwell.
- The burst states carry the readout tree: the payload wrapper enables where
  Output sits on that frame, and only a tree state keeps writing that position.
  One toggle serves both consumers: a buffer particle reads its enable edge, a
  mesh reads its level.
- `Cage/Size` is the consumer's static size knob (README §Knobs): scaling it
  scales the cubes, the clusters, the readout, the cylinder and every band
  together; only the sender-radius terms scale when they should not.
- Timed curves are plain clips, never a curve inside a Direct tree.
- Recycle is one collapsed step, the same configuration Armed holds; it stays a
  state of its own because Armed's ring rungs carry no exit time.
- The parameter driver lives only in Disabled (off-state hygiene, localOnly false:
  every client zeroes its own receiver floats).
- An admission can land on some of a slot's coincident boxes and not the
  others when the overlap begins on the very frame the slot opens, so
  the riding slot steps aside to Partial on any single riding reading and
  Recycles a step later if the rest never arrive. A slot holding the front that
  stalls blocks every admission on the avatar.
- One rung fires per frame per layer; the ring rule's exclusivity rests on
  every rung also requiring the slot's OWN Armed flag, which is one frame stale,
  so two slots can never open on one firing.

The front, which always runs:
- Sticky rejection is why acquisition is a sweep and never a standing cube: a
  full-size shut cube rejects every sender already inside for the life of the
  overlap, and a full-size open cube takes everything that appears inside it on
  one step as one reading. So Armed slots sit COLLAPSED (they hold no
  rejections) and one slot rides: its cube grows from the front's last position
  (`CR/Sweep`, latched into `CR/SweepBase` while nothing rides) to acqHalf over
  `sweepSeconds`, flag up. On a latch the ring hands the next slot into
  SweepShut — the cube appears at last frame's front SHUT for a step,
  re-rejecting the just-latched sender and everything else inside (the Recycle
  idiom) — then Sweep continues from there. At the face the pass ends:
  `Restart` parks Sweep, SweepBase and SweepPrev at 0 for `stepSeconds`, a plain
  clip so the hold spans a sampled collision step at any frame rate; the riding
  slot's cube collapses with it, which ends every overlap it was rejecting, and
  the next pass grows from the centre with the flag still up.
- Exhaustion: with every slot Held nothing rides and Wait holds the front where
  it froze. A freed slot appears shut there, rides to the face, restarts, and
  reaches from 0 whatever the frozen front had stranded. No special case.
- Two senders within two collision steps of front travel at the same Chebyshev
  radius co-latch: the admission is read from the readings, which land a step
  after the front-size cube took the sender; `sweepSeconds` and the frame time
  are the two knobs on that resolution, the placement above drops a merge of
  far-apart members, and the phantom rungs release one of held senders.
- The cost of re-offering: each held sender inside the front's reach is admitted
  once per pass and released. With a spare Armed slot the ring hands the front
  on in the same evaluation and the front holds only for that successor's shut
  step; when the rider was the last free slot the whole cycle is on the front's
  path. A held sender keeps tracking throughout, since its holder never moves.
- A sender the front finds with no slot holding it fires the payload exactly as
  one crossing in does, whether it is a newcomer, a resident at enable, or every
  resident after a fresh animator (load, a late joiner) or a distance-hide
  resume; a mirror clone runs no acquisition and re-fires nothing (below). There is deliberately no quiet endpoint for the last
  two: it costs a state copy per slot, a further sweep AAP and an exhaustion cap,
  and buys only that an edge reader stays quiet for senders already inside.
- Boot is the default state and is entered only by a fresh animator (load,
  manual hide/show, mirror clones); Disabled is entered only by the toggle.
- A mirror clone runs none of this. The client's mirror and camera clones take
  every transform from the wearer's copy, replay its parameter values, run no
  parameter drivers and traverse the state machine from Entry
  (docs/runtime.md §Parameters). A clone's slot that ran the rig would read
  the wearer's receiver floats as its own admissions and latch phantoms: its
  rider copy, one frame behind the wearer, decodes the wearer's Recycle row
  and fires the payload once per pass at the wearer's own body. The `Gate`
  layer is mirror-detect's driver race (`<prefix>/Gate`: 0 unresolved, 1 the
  wearer's own copy and every remote, 2 a mirror clone); Boot, Disabled and
  Paused wait on it and send a clone to `MirrorOff`/`MirrorOn`, two states
  that write only the payload toggle and the buffer force-on, switched by
  `Slot<k>/Shown`, a float an entry driver sets on the wearer's copy (1 on
  entering TrackIn, 0 on entering TrackBand, Recycle, Paused or Disabled;
  localOnly except Disabled's, which every client runs) and the clone replays.
  Positions in the mirror are the wearer's; only the enables are the clone's.
  The Sweep layer's clone states write the boundary's scale and renderer
  enable and nothing of the front. The race is run once per animator: Boot is
  re-entered only by a rebuild (docs/runtime.md §Parameters: manual hide/show
  rebuilds, a distance-hide resumes with prior state and never leaves Paused
  for Boot), and a rebuilt animator starts `DetectMirror`, a scratch bool in no
  asset, at false. A saved declaration is the one way it could persist, and the
  README refuses it.
- Paused is entered from every state on `IsAnimatorEnabled` false, VRChat's
  one-frame pre-halt signal for a distance-hide (docs/runtime.md §Parameters
  carries the citation; view cull gives no signal, so the README asks the
  installer for renderer bounds that cover the working volume). Its clip
  collapses the boxes; on resume the rig passes through Paused, Armed
  (collapsed) and SweepShut at front 0 before anything grows, so the present
  senders are re-acquired from scratch.
- The three sweep AAPs have exactly one writer, the `Sweep` layer, whose every
  state writes all three. Slot layers read them and report `Slot<k>/Front` (1
  in their Sweep state) for the layer to ramp on.
- The handoff leaves no blind band, and that takes both halves. `Ramp -> Wait`
  fires on the sweeping slot's own riding readings while its Front still reads
  1, the frame it latches, so the front freezes at the size that admitted; and
  the successor's shut cube scales off `SweepPrev`, last frame's front, so it
  appears at exactly the size that just admitted. The restart rung is listed
  after the freeze rungs: on a pass's last handoff both are eligible in one
  evaluation, and the freeze wins. Wait holds SweepPrev off itself, never off
  Sweep: on Wait's first frame Sweep already reads the frozen front, one frame
  past the size that admitted.
- The `Ramp` state is a Direct tree whose duration is data: the ramp clip
  carries the timing and every other child is one frame long, which stretches
  the ramp by at most the sum of those children's weights over 60·sweepSeconds.

The boundary: `Cage/Size/Boundary` holds one unit mesh, `Cylinder` (an open
tube of radius 1, y in [-1, 1], its ends undrawn because the zone has none),
written by `--mesh` into assets/. The Sweep layer — the one layer with exactly
one state live at all times — writes its scale (R, band, R) and MeshRenderer
enable in every state, so the drawn surface is the burst radius over the band,
only while the toggle is on. `Boundary` ships inactive: activating it is the
consumer's opt-in, and its material the swap point.

Fragment mode: `document(overrides)` returns the document text and a facts
dict, the door a venue's owned copy regenerates through at its own CONFIG. A
key CONFIG does not carry is refused there, so a consumer still passing a key
this generator has since dropped fails at the door instead of being accepted
silently and built at the default.
"""

import itertools
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "controller": "ContactRadar_Fx",
    "K": 4,                     # slots; each is one layer and three receivers (four under fourBox)
    "tags": ["HandR"],
    "acqHalf": 1.2,             # acquisition cube half-extent, m; at Cage/Size scale 1
    "burstRadius": 1.0,         # R_in, m — the zone's horizontal radius (a vertical cylinder about the cage centre)
    "rearmRadius": 1.1,         # R_out, m
    "farRadius": None,          # m, or None: a settled sender whose in-plane radius reads past this is released (TrackBand only).
                                #   None keeps every held sender to the bound B = acqHalf + followHalf. Lint: above rearmRadius, below B
    "followHalf": 0.5,          # m, the hold cluster's half-extent — h in the follower's readout. Lint: above placeHalf, below acqHalf
    "placeHalf": 0.15,          # m, the half-extent of the small cluster every latch and every reacquire opens at. Lint: above senderRadius,
                                #   and placeHalf + senderRadius above sqrt3·senderRadius, the three-box bias a sender of twice the radius carries
    "followGain": 0.5,          # per-frame fraction of the decoded offset the cluster centre moves by. Lint: in (0, 1]; below 1 keeps the
                                #   loop bounded when the true sampling delay is a frame off pairDelay
    "pairDelay": 1,             # evaluations between a centre write and the first evaluation whose reading was sampled against it: 1, 2 or 3
    "dedupBand": 0.05,          # m per axis within which two slots' decoded points are one sender
    "reacquireSeconds": 0.1,    # s the placement cluster stands flag up after a cut before the slot is given back. Lint: >= 2*stepSeconds
    "fourBox": False,           # add the X- receiver and measure r per sender instead of assuming it (needs a 4-box prefab)
    "senderRadius": 0.05,       # r, m — the senders' typical radius: the placement offset at every latch (both rigs) and the
                                #   three-box readout's bias. Under fourBox the follower measures r instead
    "stepSeconds": 0.035,       # every step-spanning dwell; >= 2 collision steps
    "latchSeconds": 0.07,       # LatchGrow's and ReShut's dwell, so a step samples the grown cluster before the follower decodes its readings
                                #   with followHalf coefficients: two collision steps, because a remote clone's receivers reach its animator a frame
                                #   later than the wearer's, so a dwell sized to one step on the wearer is one step short on every other client.
                                #   Lint: >= 2*stepSeconds
    "sweepSeconds": 2.0,        # the front's travel time from the centre to the face, every pass: the period between two offers to a sender and
                                #   the resolution (front travel over the two collision steps an admission spans, the same-shell merge window) at once
    "lookupSegments": 16,       # square-table resolution: segments per 2·TABLE_REF of the ±B span (table_segments); the yw² table takes the same chord width
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
TILT = (-0.325058, 0.0, 0.325058, 0.888074)
TILT_INV = (0.325058, 0.0, -0.325058, 0.888074)
SQRT3 = 3 ** 0.5
# World height in the slot frame: the tilt sends the slot's (1, 1, 1) diagonal to world up, so a point's height
# above the cage centre is (x + y + z) / sqrt3 of its tilted-frame readout. yw undoes the tilt on the one axis the
# cylinder needs; the in-plane radius² is then r² − yw², and the readout frame is never undone for x and z.
YW_PER_AXIS = 1 / SQRT3
# The register scale: every centre and memory register is stored as (value + A) / S. With A = B + 1 a register
# for a point within ±B lies in [1/S, (2B + 1)/S], below 0.5 while B < 3.5 (the lint), so a one-frame copy child adds
# under half a frame to its state's length and every weight stays positive.
S_REG = 16
# The chord-width reference of the square tables: lookupSegments segments span ±TABLE_REF, so the tables over ±B
# carry lookupSegments·B/TABLE_REF segments and the chord width does not move with B. 1.3 m is the half-extent the
# shipped tables spanned, so the default keeps their chord width, 2·1.3/16 m per segment.
TABLE_REF = 1.3
FRAME = 1 / 60                  # a set clip's floored length, the length of every one-frame child
POS = ("x", "y", "z")
RIDE_AXIS = {"X+": "x", "Y+": "y", "Z+": "z"}   # the riding box whose reading decodes each tilted axis at the latch


def bound(c):
    """B: the decoded point's reach on each tilted axis — the acquisition cube grown by the cluster. The bound rung
    releases past it; the tables, the park and the register offset derive from it."""
    return c["acqHalf"] + c["followHalf"]


def reg_offset(c):
    """A: the register offset, a metre past the bound, so a point a frame past B before the bound rung fires is still
    stored positive."""
    return bound(c) + 1


def reg_max(c):
    """The largest register value for a point within ±B: the weight bound each dwell's length is computed from."""
    return (bound(c) + reg_offset(c)) / S_REG


def max_sender_radius(c):
    """fourBox only: the measured R above which the opposed X boxes are reading two different senders. Derived, not a
    knob: senderRadius + dedupBand is the separation past which a composite's midpoint leaves the band of its sources."""
    return c["senderRadius"] + c["dedupBand"]


def chain(c):
    """The centre and its delayed copies, C → C1 → C2: only as deep as the pairing register reads. A child weighted by C
    reads the centre written one evaluation back, by C1 two, by C2 three; nothing reads a deeper copy, so none is
    emitted (pairDelay 1: no copy at all, pairDelay 2: C1 only)."""
    return ["C"] + [f"C{i}" for i in range(1, c["pairDelay"])]


def pairing(c):
    """The register the follower adds the decoded offset to: the centre the reading landing now was sampled against."""
    return chain(c)[-1]


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


def riding(c):
    """The receivers that ride the front: X- rides collapsed under fourBox, so every admission predicate reads these."""
    return ("X+", "Y+", "Z+")


def lint(c):
    if not isinstance(c["fourBox"], bool):
        refuse("fourBox must be a bool — it selects the rig, not a box count")
    if c["fourBox"] and c["senderRadius"] <= 0:
        refuse("senderRadius must be > 0 under fourBox — the follower measures r per sender, but the placement and the R "
               "bound (senderRadius + dedupBand) still take it as the senders' typical radius")
    if c["K"] < 2:
        refuse("K must be >= 2 — one slot has nothing to hand off to")
    if c["rearmRadius"] <= c["burstRadius"]:
        refuse("rearmRadius must be > burstRadius")
    if band_half_height(c, c["rearmRadius"]) <= 0:
        refuse("sqrt3*acqHalf must exceed sqrt2*(rearmRadius + senderRadius) — the cylinder's re-arm radius must be inside the "
               "tilted acquisition cube from every direction at the centre height, or a sender can be in the zone on one side "
               "of you and unreachable on the other; the band this leaves is the zone's guaranteed height (band_half_height)")
    if c["stepSeconds"] < 2 / 60:
        refuse("stepSeconds must be >= 2/60 — every frame at 60 fps or below carries a collision step, but above 60 fps a step "
               "lands only every second or third frame and the longest gap between two is one step period plus one frame, just "
               "under 2/60 s; a dwell shorter than that gap can open and close with no step sampling it")
    if c["latchSeconds"] < 2 * c["stepSeconds"]:
        refuse("latchSeconds must be >= 2*stepSeconds — LatchGrow and ReShut dwell so that a collision step samples the grown "
               "cluster before the follower reads it, stepSeconds is the shortest dwell one step is guaranteed to land in at any "
               "frame rate, and a remote clone's receivers reach its animator a frame later than the wearer's; a shorter dwell "
               "hands a clone's follower placement-size readings decoded with followHalf coefficients")
    if not c["followHalf"] > c["placeHalf"] > c["senderRadius"]:
        refuse("followHalf > placeHalf > senderRadius must hold — the placement cluster must contain a sender's surface at the "
               "decoded point (placeHalf above the radius), and the follow cluster grows from it (followHalf above placeHalf)")
    if c["followHalf"] >= c["acqHalf"]:
        refuse("followHalf must be < acqHalf — the hold cluster is a small box at the sender; one as large as the acquisition "
               "cube stands the cage-sized pair load the follower exists to remove")
    if c["placeHalf"] + c["senderRadius"] <= SQRT3 * c["senderRadius"]:
        refuse("placeHalf + senderRadius must exceed sqrt3*senderRadius — the latch decodes with the assumed radius, and a "
               "sender of twice it carries a bias of that radius on each tilted axis, sqrt3 times it in distance; a placement "
               "cluster that cannot reach that far loses every sender larger than the assumption")
    if c["placeHalf"] + c["senderRadius"] <= 2 * c["acqHalf"] * c["stepSeconds"] / c["sweepSeconds"] + c["senderRadius"]:
        refuse("placeHalf + senderRadius must exceed 2*acqHalf*stepSeconds/sweepSeconds + senderRadius — after the saturated-axis "
               "correction the latch's residual on that axis is up to two steps of front travel (F is the front one step after the "
               "admitting cube) plus the radius mismatch, and the placement cluster must still contain the sender's surface there")
    if c["reacquireSeconds"] < 2 * c["stepSeconds"]:
        refuse("reacquireSeconds must be >= 2*stepSeconds — a returning sender reads through the placement cluster only after "
               "the Proximity acquisition cost, two collision steps, and stepSeconds is the dwell one step is guaranteed to "
               "land in at any frame rate; a shorter wait can time out before any return reads")
    if isinstance(c["pairDelay"], bool) or c["pairDelay"] not in (1, 2, 3):
        refuse("pairDelay must be 1, 2 or 3 — the pairing register is C, C1 or C2; the round measures which")
    if not 0 < c["followGain"] <= 1:
        refuse("followGain must be in (0, 1] — 0 never moves the cluster, and above 1 the centre overshoots the sender every frame")
    if c["dedupBand"] <= 0:
        refuse("dedupBand must be > 0 — a float transition condition compares greater or less and never equal, so a "
               "zero-width band makes every dedup rung unfireable and two slots holding one sender both keep it")
    if c["farRadius"] is not None:
        if c["farRadius"] <= c["rearmRadius"]:
            refuse("farRadius must be > rearmRadius — the far release is a settled sender's exit past the re-arm band; at or inside "
                   "the re-arm radius it would release a sender the zone still counts as present")
        if c["farRadius"] >= bound(c):
            refuse("farRadius must be < acqHalf + followHalf — the bound rung releases every sender past that on any tilted axis, "
                   "so a far radius beyond it is never read")
    if reg_max(c) >= 0.5:
        refuse("acqHalf + followHalf must be < 3.5 — the registers are stored as (value + A)/16 and must stay below 0.5 so each "
               "copy child adds under half a frame to its state's length (the dwells are computed from that bound)")
    if c["sweepSeconds"] * 60 < 4.2:
        refuse("sweepSeconds is too short — the front (which runs 5% past the face) would cross more than a quarter of the cube per collision step")
    if 2 * c["acqHalf"] > 6:
        refuse("2*acqHalf exceeds the SDK's serialized box limit (6 m) — a sanity bound on the working volume")
    if c["lookupSegments"] < 4:
        refuse("lookupSegments must be >= 4")
    if "/" in c["prefix"] or not c["prefix"]:
        refuse("prefix must be a bare segment")
    if c["enable"].count("/") != 1:
        refuse("enable must be one prefixed name (Module/Enable) — the wildcard for a bare name matches nothing")


def zone_conds(c, me):
    """The inside predicate (one AND list) and the outside rungs (a list of AND lists — an OR). The zone is a
    vertical cylinder: the compare is on p2, the in-plane radius², and nothing bounds the height, so a sender leaves
    the zone through the cube's ends only by the bound rung or the axis floor, never through a band."""
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    inside = [f"{me}/p2 less {fmt(rin2)}"]
    outside = [[f"{me}/p2 greater {fmt(rout2)}"]]
    return inside, outside


BOUNDARY = "Cage/Size/Boundary"


def boundary_bindings(c, on):
    """The unit tube's scale and renderer enable — the drawn surface is the burst radius, over the band inside
    which a sender at that radius is reached from every direction (the ends past it are the cube's corners)."""
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


def xn_path(k):
    return f"Cage/Size/Slot{k}/Boxes/X-"


def out_path(k):
    return f"Cage/Size/Slot{k}/Output"


def emit_clip(o, name, sets, seconds=None, comment=None):
    body = ", ".join(f"{k2}: {v}" for k2, v in sets.items())
    sec = f"seconds: {fmt(seconds)}, " if seconds else ""
    o(f"  {name}: {{ {sec}set: {{ {body} }} }}" + (f"   # {comment}" if comment else ""))


def ax_tag(ax):
    """The clip-name suffix for a receiver axis, the readout clips' spelling: X+ -> xp, X- -> xn."""
    return ax.replace("+", "p").replace("-", "n").lower()


# ----- the slot's trees: one spec drives both the emitted children and the computed dwell bound -----

def leaf(clip, weight, wmax):
    return ("clip", clip, weight, wmax)


def subtree(name, weight, wmax, children):
    return ("tree", name, weight, wmax, children)


def tables(c, k):
    """The four 1D square tables at weight One: x², y², z² into r2 and p2, then −yw² into p2."""
    me = slot_name(c, k)
    P = c["prefix"]
    out = [("table", f"Slot{k} {a}²", f"{me}/{a}", f"{P}/One", [(f"slot{k}_sq_{i}", t) for i, t in enumerate(sq_knots(c))])
           for a in POS]
    out.append(("table", f"Slot{k} −yw²", f"{me}/yw", f"{P}/One", [(f"slot{k}_nsq_{i}", t) for i, t in enumerate(yw_knots(c))]))
    return out


def tree_seconds(children, lengths):
    """An upper bound on a Direct tree state's length, Σ(weight max × child length) (docs/animator-schema.md §motions),
    from each child's declared weight maximum. A nested child scales its subtree's bound by its own weight."""
    total = 0.0
    for ch in children:
        if ch[0] == "clip":
            total += ch[3] * lengths[ch[1]]
        elif ch[0] == "tree":
            total += ch[3] * tree_seconds(ch[4], lengths)
        else:
            total += FRAME   # a 1D table of one-frame clips at weight One
    return total


def emit_children(o, children, ind):
    pad = " " * ind
    for ch in children:
        if ch[0] == "clip":
            o(f"{pad}- {{ clip: {ch[1]}, directWeight: {ch[2]} }}")
        elif ch[0] == "tree":
            o(f"{pad}- tree: direct")
            o(f"{pad}  name: {ch[1]}")
            o(f"{pad}  normalized: false")
            o(f"{pad}  directWeight: {ch[2]}")
            o(f"{pad}  children:")
            emit_children(o, ch[4], ind + 4)
        else:
            _, name, param, weight, knots = ch[:5]
            if len(ch) > 5:
                o(f"{pad}# {ch[5]}")
            o(f"{pad}- tree: 1d")
            o(f"{pad}  name: {name}")
            o(f"{pad}  param: {param}")
            o(f"{pad}  directWeight: {weight}")
            o(f"{pad}  children:")
            for clip, t in knots:
                o(f"{pad}    - {{ clip: {clip}, threshold: {fmt(t)} }}")


def emit_motion(o, name, children):
    o("        motion:")
    o("          tree: direct")
    o(f"          name: {name}")
    o("          normalized: false")
    o("          children:")
    emit_children(o, children, 12)


def track_children(c, k, hold):
    """A track state's follower tree. `hold` is the state's configuration clip at weight One: its flags and payload,
    and the readout's constant terms (the read bias and every −A). Then one child per reading (the offset at h =
    followHalf) and one per chain register and axis, each carrying everything that register contributes: the centre's
    (1 − g) share, its copy into the next link, and on the pairing register the decoded point's base."""
    P = c["prefix"]
    me = slot_name(c, k)
    w = reg_max(c)
    ch = [leaf(hold, f"{P}/One", 1)]
    ch += [leaf(f"slot{k}_read_{ax_tag(ax)}", f"{me}/{ax}", 1) for ax in axes(c)]
    ch += [leaf(f"slot{k}_follow_{reg}_{a}", f"{me}/{reg}/{a}", w) for reg in chain(c) for a in POS]
    return ch + tables(c, k)


def keep_children(c, k, cfg_clip):
    """A hold state's tree (LatchWait, LatchGrow): the configuration at One, and every register copying itself, the
    centre also writing Boxes' position (S per unit; the −A rides the configuration clip)."""
    P = c["prefix"]
    me = slot_name(c, k)
    w = reg_max(c)
    return [leaf(cfg_clip, f"{P}/One", 1)] + [leaf(f"slot{k}_keep_{reg}_{a}", f"{me}/{reg}/{a}", w)
                                               for reg in chain(c) + ["Mem"] for a in POS]


def re_children(c, k, cfg_clip, at_mem=True):
    """A reacquire state's tree: the configuration at One, and per axis one child weighted by Mem that holds Mem,
    resets every chain register to it, holds the readout at it and, with `at_mem`, puts Boxes there (ReCollapse keeps
    Boxes at the cage centre); R holds itself under fourBox."""
    P = c["prefix"]
    me = slot_name(c, k)
    kind = "re_mem" if at_mem else "re_hold"
    ch = [leaf(cfg_clip, f"{P}/One", 1)] + [leaf(f"slot{k}_{kind}_{a}", f"{me}/Mem/{a}", reg_max(c)) for a in POS]
    if c["fourBox"]:
        ch.append(leaf(f"slot{k}_re_R", f"{me}/R", max_sender_radius(c)))
    return ch


def latch_children(c, k):
    """Latch's decode. The configuration at One carries the constant terms (−r on Boxes, (A − r)/S on every
    register); the product F·(2V − 1) is a child weighted by F holding a tree of the riding readings (× 2) and One
    (× −1). That tree's One child also writes F 1, F's self-copy, so a second Latch evaluation decodes at the same F."""
    P = c["prefix"]
    me = slot_name(c, k)
    inner = [leaf(f"slot{k}_place_neg", f"{P}/One", 1)] + [leaf(f"slot{k}_place_{ax_tag(ax)}", f"{me}/{ax}", 1) for ax in riding(c)]
    # The saturated-axis correction, one 1D tree per riding axis on its raw reading. The admitting face reads the clamp,
    # 1.0, because the sender straddles it: the overlap began when the front reached the sender's near surface, so its
    # centre sits about F + r out while 2F·V − F − r gives F − r. A reading of exactly 1.0 takes the full +2r, one at or
    # below 0.999 takes none, and the thin blend between is the face's last millimetre.
    sat = [("table", f"Slot{k} {RIDE_AXIS[ax]} saturated", f"{me}/{ax}", f"{P}/One",
            [(f"slot{k}_sat_{ax_tag(ax)}_0", 0.999), (f"slot{k}_sat_{ax_tag(ax)}_2r", 1.0)],
            f"{ax} at the clamp (1.0): the sender straddles that face, its centre about 2·senderRadius past the decode; add it")
           for ax in riding(c)]
    return [leaf(f"slot{k}_latch", f"{P}/One", 1),
            subtree(f"Slot{k} latch decode", f"{me}/F", c["acqHalf"] * 1.05, inner)] + sat


def emit_layer(o, c, k, ks, lengths):
    P = c["prefix"]
    en = c["enable"]
    me = slot_name(c, k)
    eps = c["epsilon"]
    inside, outside = zone_conds(c, me)
    inside = ", ".join(inside)
    ax4 = axes(c)
    B = bound(c)
    # The admission: every riding box reads above zero. The readings land on the collision step after the front-size
    # cube took the sender, and this one predicate is the latch, the ring handoff's trigger and the Sweep layer's freeze
    # (`emit_sweep_layer` uses it verbatim). `greater 0`, never `greater epsilon`: a reading in (0, epsilon] would then
    # latch here and hand off nowhere. Never X-: it rides collapsed under fourBox and would never read above zero.
    ride_pos = ", ".join(f"{me}/{ax} greater 0" for ax in riding(c))
    # Every box, X- included: the predicate once the placement has opened X- (LatchWait on), and the reacquire's.
    all_pos = ", ".join(f"{me}/{ax} greater 0" for ax in ax4)
    band = fmt(c["dedupBand"])
    nband = fmt(-c["dedupBand"])
    paused = "          - { to: Paused, when: [ IsAnimatorEnabled is false ] }   # the pre-halt frame: park before the animator stops"
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"

    def rungs():
        o(paused)
        o(off)

    def floor(to, axs, why):
        for ax in axs:
            o(f"          - {{ to: {to}, when: [ {me}/{ax} less {fmt(eps)} ] }}   # {why}")

    def dwell(children, rung):
        """An exit-time rung with the dwell it rides, as the generator bounds the tree's length."""
        return f"{rung}   # dwell: the tree's length, at most {fmt(round(tree_seconds(children, lengths), 4))} s (Σ weight max × child length)"

    def hide():
        # The hide row: every axis reads 1.0 on one step when the sender's avatar is hidden, swapped or reloaded
        # (docs/runtime.md §Contacts). First, so the follower never decodes it: decoded, it is an offset of h − r on
        # every axis under three boxes and R = h under four, and the cluster would jump off the sender.
        o(f"          - {{ to: Recycle, when: [ {', '.join(f'{me}/{ax} greater 0.9999' for ax in ax4)} ] }}   # the sender's avatar hidden, swapped or reloaded: every axis at 1.0")

    def r_bound():
        if c["fourBox"]:
            # A composite across the opposed X boxes (X+ reading one sender, X- another) decodes x at the midpoint of
            # the two X faces and inflates R by half their separation; past senderRadius + dedupBand it is two senders.
            o(f"          - {{ to: Recycle, when: [ {me}/R greater {fmt(max_sender_radius(c))} ] }}   # R past senderRadius + dedupBand: the opposed X boxes read two senders")

    def bound_rungs():
        # The bound: the decoded point past B = acqHalf + followHalf on any tilted axis. A follower has no face to
        # release at and would follow a departing sender indefinitely; B is the acquisition cube grown by the cluster.
        # The Latch park sits exactly on +B / −B, and the strict compare is what keeps it from firing there.
        for a in POS:
            o(f"          - {{ to: Recycle, when: [ {me}/{a} greater {fmt(B)} ] }}   # past the bound on {a}")
            o(f"          - {{ to: Recycle, when: [ {me}/{a} less {fmt(-B)} ] }}")

    def dedup_rungs(settled):
        """The position rungs, to Recycle, on D/<lo>_<hi>/<a> = Mem_hi − Mem_lo in metres (the Dedup layer).
        Duplicate rung, one per other slot j: every axis inside ±dedupBand, j Held. Fresh (TrackOut): a SETTLED j always
        wins, whatever its index, and between two fresh slots the lower index wins, so two never release each other.
        Settled (TrackIn, TrackBand): only against a lower-index settled j, so the higher index yields.
        Phantom rung, one per assignment of the three axes to other slots that is not all one slot: a same-step merge of
        senders other slots hold is their per-axis maximum, so each assigned axis is inside the band of its source AND
        strictly above every other source in the assignment there. Strictly means above zero, the smallest form: the merge
        clears each source by the members' separation on the axes it takes from another, while a duplicate of one source
        and a single sender that two merges each contain sit at or below a source somewhere and fail. Every source Held;
        Settled as for the duplicate rung."""
        def within(j, a):
            lo, hi = min(j, k), max(j, k)
            return [f"{P}/D/{lo}_{hi}/{a} greater {nband}", f"{P}/D/{lo}_{hi}/{a} less {band}"]

        def above(s2, a):
            lo, hi = min(s2, k), max(s2, k)
            return f"{P}/D/{lo}_{hi}/{a} greater 0" if k == hi else f"{P}/D/{lo}_{hi}/{a} less 0"

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
            for a in POS:
                dconds += within(j, a)
            dconds += holder(j)
            why = (f"slot {j} (lower index, settled) holds this point" if settled else
                   f"slot {j} holds this point" + (" and has settled (a higher index yields only to that)" if j > k else ""))
            o(f"          - {{ to: Recycle, when: [ {', '.join(dconds)} ] }}   # {tag}: {why}")
        others = [j for j in ks if j != k]
        for assign in itertools.product(others, repeat=len(POS)):
            srcs = sorted(set(assign))
            if len(srcs) == 1:
                continue
            dconds = []
            for a, j in zip(POS, assign):
                dconds += within(j, a)
                dconds += [above(s2, a) for s2 in srcs if s2 != j]
            for j in srcs:
                dconds += holder(j)
            o(f"          - {{ to: Recycle, when: [ {', '.join(dconds)} ] }}   # {tag} phantom: {'/'.join(f'{a} of slot {j}' for a, j in zip(POS, assign))}")

    o(f"  - name: Slot{k}")
    o("    states:")
    # The Gate layer's verdict: every park state waits on it, and a mirror clone goes to the two enable-only states.
    mirror = f"          - {{ to: MirrorOff, when: [ {P}/Gate greater 1.5 ] }}   # a mirror clone: no slot logic; the payload follows the wearer's Shown"
    run = f"{P}/Gate greater 0.5, {P}/Gate less 1.5"
    o("      Boot:                        # a fresh animator: load, manual hide/show, a mirror clone; leaves only on the Gate layer's verdict")
    o(f"        motion: {{ clip: slot{k}_boot }}")
    o("        transitions:")
    o(mirror)
    o(paused)
    o(f"          - {{ to: Disabled, when: [ {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ {en} is true, {run} ], exitTime: 1.0 }}")
    o("      Disabled:                    # Enable off — boxes stowed, flags shut, readings zeroed on every client")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: false, set: {{ {', '.join(f'{me}/{ax}: 0' for ax in ax4)}, {me}/Shown: 0 }} }}")
    o(f"        motion: {{ clip: slot{k}_off }}")
    o("        transitions:")
    o(mirror)
    o(paused)
    o(f"          - {{ to: Armed, when: [ {en} is true, {run} ], exitTime: 1.0 }}   # quantized: an Enable cycle spans a step")
    o("      Paused:                      # boxes collapsed through the pause; resume re-acquires from scratch")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {me}/Shown: 0 }} }}")
    o(f"        motion: {{ clip: slot{k}_paused }}")
    o("        transitions:")
    o(mirror)
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Armed, when: [ IsAnimatorEnabled is true, {en} is true, {run} ] }}")
    o("      MirrorOff:                   # a mirror clone, this slot's payload off. Every transform here is the wearer's; nothing else is written")
    o(f"        motion: {{ clip: slot{k}_mirror_off }}")
    o("        transitions:")
    o(f"          - {{ to: MirrorOn, when: [ {me}/Shown greater 0.5 ] }}")
    o("      MirrorOn:                    # a mirror clone, this slot's payload on: the burst fires on this edge, where the wearer's Output sits")
    o(f"        motion: {{ clip: slot{k}_mirror_on }}")
    o("        transitions:")
    o(f"          - {{ to: MirrorOff, when: [ {me}/Shown less 0.5 ] }}")
    o("      Armed:                       # flags shut and collapsed: holds no rejections; waits for the ring, or self-opens onto the front")
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
        # The handoff reads slot i's Open one frame stale (still 1) and the same fresh riding readings that latch it, so
        # it fires in the SAME evaluation as i's Sweep -> Latch; next frame i's Open reads 0 and it is dead. Open and not
        # Front: Partial writes Open 1 with Front 0 and a full reading there latches and must hand off.
        conds = [f"{si}/Open greater 0.5"] + [f"{si}/{ax} greater 0" for ax in riding(c)] + ring
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
    o("      Sweep:                       # flag up, the cube riding the Sweep layer's front: each sender is admitted alone as the front reaches it")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} sweep")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_sweep_cfg, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {ride_pos} ] }}   # this slot's own admission: the riding readings, a step after the front-size cube took the sender; the Sweep layer freezes the front on the same predicate")
    for ax in riding(c):
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    # No exit at the face. The Sweep layer restarts the front there and this cube collapses with it (front_scale × Sweep
    # reads 0 over the collapsed base scale), which ends every overlap it was rejecting, and the next pass regrows it
    # from the centre with the flag still up.
    o("      Partial:                     # one riding box read a sender the others did not: a step's grace at the current front, else Recycle — a slot holding the front may never stall")
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} partial")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: slot{k}_open_wait, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_front_scale, directWeight: {P}/Sweep }}")
    o("        transitions:")
    rungs()
    o(f"          - {{ to: Latch, when: [ {ride_pos} ] }}   # the rest of the reading arrived: Partial writes Open 1, so the ring hands off on this the same frame")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Latch:                       # one evaluation: decode the point at the admitting front size, place the boxes there at placeHalf with the riding flags shut"
      + (" and X- flag up" if c["fourBox"] else "") + ", seed every register, park the readout")
    emit_motion(o, f"Slot{k} latch", latch_children(c, k))
    o("        transitions:")
    rungs()
    # Held reads 0 on the entry evaluation (the riding state wrote it) and 1 on the next, at any frame rate, so the
    # decode runs on front-size readings only: the placement's write reaches the sim a step later. Nothing else leaves
    # Latch: a cut on this evaluation is LatchWait's floor rung one evaluation later.
    o(f"          - {{ to: LatchWait, when: [ {me}/Held greater 0.5 ] }}")
    lw = keep_children(c, k, f"slot{k}_latchwait")
    o("      LatchWait:                   # the placement held for two collision steps"
      + (": X-, freshly opened, reads exactly 0 on its first step and its value on the second" if c["fourBox"] else ": a riding axis the placement lost has fallen by then"))
    emit_motion(o, f"Slot{k} latch wait", lw)
    o("        transitions:")
    rungs()
    floor("Recycle", riding(c), "a riding axis fell: a cut on the shrink step, or a merge corner that holds nothing" + (" (never X-, which reads 0 on its first step)" if c["fourBox"] else ""))
    o(dwell(lw, f"          - {{ to: LatchGrow, when: [ {all_pos} ], exitTime: 1.0 }}"))
    o("          - { to: Recycle, when: [], exitTime: 1.0 }   # the terminal fallback" + ("; X- never read: the sender's surface was not inside the placement cluster on its axis" if c["fourBox"] else ", unreachable while every axis is above zero or at the floor"))
    lg = keep_children(c, k, f"slot{k}_latchgrow")
    o("      LatchGrow:                   # every flag shut, the cluster grown to followHalf: a collision step samples it before TrackOut decodes")
    emit_motion(o, f"Slot{k} latch grow", lg)
    o("        transitions:")
    rungs()
    floor("Recycle", ax4, "the readings fell on the grow step: release now")
    o(dwell(lg, f"          - {{ to: TrackOut, when: [ {all_pos} ], exitTime: 1.0 }}"))
    o("          - { to: Recycle, when: [], exitTime: 1.0 }   # the terminal fallback, as LatchWait's")
    # The reacquire gate: a reacquiring slot's Mem is frozen at the cut, and a rider that re-takes a fast sender a few
    # frames later can decode it past dedupBand from that point and miss the rung. So TrackOut's two zone rungs wait
    # while any other slot's Re reads 1; the dedup rungs, listed first, are re-tested every frame meanwhile, and once
    # the original slot tracks again with a live Mem the rider matches it and recycles with no payload edge.
    gate = "".join(f", {slot_name(c, j)}/Re less 0.5" for j in ks if j != k)
    to = track_children(c, k, f"slot{k}_hold")
    o("      TrackOut:                    # the follower live, payload off; outside the burst radius. Entered only from LatchGrow, so the fresh dedup rungs below run on a fresh admission; the settled rungs in TrackIn and TrackBand re-run a narrower test for the life of the track")
    emit_motion(o, f"Slot{k} follow", to)
    o("        transitions:")
    rungs()
    hide()
    floor("Recycle", ax4, "a fresh slot that loses its sender before settling is given back")
    r_bound()
    dedup_rungs(settled=False)
    o(f"          - {{ to: TrackIn, when: [ {inside}{gate} ] }}   # the reacquire gate: held while any other slot reacquires")
    bound_rungs()
    # Fresh ends once the readout is live, not only by reaching the zone: the front re-offers every held sender each
    # pass, and a holder that stayed fresh would be re-taken by every lower-index rider under the fresh-versus-fresh
    # rule, hopping slots once a pass. The gate is r² off the Latch park (the tables' own reading of it), which lands a
    # frame after D does, so the dedup rungs above have read the decode's D by the time this rung is eligible. Checked at
    # each crossing of the tree's own period; listed last, so any rung above that is eligible on the same frame wins.
    o(dwell(to, f"          - {{ to: TrackBand, when: [ {me}/r2 less {fmt(park_r2(c) - 1e-4)}{gate} ], exitTime: 1.0 }}") + "; the fresh window, reacquire-gated")
    ti = track_children(c, k, f"slot{k}_hold_burst")
    o("      TrackIn:                     # inside the burst radius in-plane (p2); the payload is on (one burst per entry, a marker visible throughout); settled dedup runs here; a floor takes the reacquire")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {me}/Shown: 1 }} }}   # the mirror clone's enable: replayed, never clip-bound")
    emit_motion(o, f"Slot{k} follow", ti)
    o("        transitions:")
    rungs()
    hide()
    floor("ReCollapseIn", ax4, "a cut, or the sender left the cluster: reacquire at Mem")
    r_bound()
    dedup_rungs(settled=True)
    for conds in outside:
        o(f"          - {{ to: TrackBand, when: [ {', '.join(conds)} ] }}")
    bound_rungs()
    tb = track_children(c, k, f"slot{k}_hold_band")
    o("      TrackBand:                   # settled outside the zone, by retreating past the re-arm radius in-plane or by holding outside it past the fresh window; a floor takes the reacquire" + ("; the far release lives here" if c["farRadius"] is not None else ""))
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {me}/Shown: 0 }} }}")
    emit_motion(o, f"Slot{k} follow", tb)
    o("        transitions:")
    rungs()
    hide()
    floor("ReCollapseBand", ax4, "a cut, or the sender left the cluster: reacquire at Mem")
    r_bound()
    dedup_rungs(settled=True)
    if c["farRadius"] is not None:
        # Here and nowhere else: TrackBand is reached with live readings (the fresh window off the Latch park, or the
        # re-arm crossing), so a newcomer's first decode decides nothing about the far radius.
        o(f"          - {{ to: Recycle, when: [ {me}/p2 greater {fmt(c['farRadius'] ** 2)} ] }}   # far release: settled past farRadius {c['farRadius']} m in-plane; the front re-offers it every pass")
    o(f"          - {{ to: TrackIn, when: [ {inside} ] }}")
    bound_rungs()
    for suffix, back in (("In", "TrackIn"), ("Band", "TrackBand")):
        emit_reacquire(o, c, k, suffix, back, rungs, floor, dwell, all_pos)
    o("      Recycle:                     # collapsed at the cage centre for a step, flags shut: every overlap this slot held ends; then straight onto the front, or Armed")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {me}/Shown: 0 }} }}")
    o(f"        motion: {{ clip: slot{k}_recycle }}")
    o("        transitions:")
    rungs()
    # The shortcut onto the front: with nothing holding it and nothing Armed, this is the slot that would self-open
    # after another step in Armed, so it goes to SweepShut directly and saves that step on every duplicate release. The
    # lower-index Held reads are the tie-break: every flag here is an AAP read one frame late, and two slots releasing
    # on one frame would each see the other as neither Open nor Armed (Recycle writes both 0) and both ride the front.
    # Requiring every lower slot to read Held sends the higher one to Armed, where the ordinary self-open rule (no
    # lower Armed) resolves it a step later.
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Held greater 0.5" for j in ks if j < k]
    o(f"          - {{ to: SweepShut, when: [ {', '.join(conds)} ], exitTime: 1.0 }}   # nothing holding the front, nothing Armed, every lower slot holding: straight onto the front")
    o("          - { to: Armed, when: [], exitTime: 1.0 }")
    o("    default: Boot")
    o("    layout:")
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], MirrorOff: [510, 180], MirrorOn: [510, 270], Armed: [30, 360], SweepShut: [-210, 360], Sweep: [-210, 450], Partial: [270, 450], "
      "Latch: [30, 450], LatchWait: [30, 540], LatchGrow: [30, 630], TrackOut: [-210, 720], TrackBand: [30, 720], TrackIn: [270, 720], Recycle: [30, 810], "
      "ReCollapseIn: [510, 720], ReOpenIn: [510, 630], ReShutIn: [510, 540], ReCollapseBand: [-450, 720], ReOpenBand: [-450, 630], ReShutBand: [-450, 540] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_reacquire(o, c, k, suffix, back, rungs, floor, dwell, all_pos):
    """The three reacquire states for one payload bit (In: on, Band: off), written once per bit because the payload is
    a discrete binding a Direct tree cannot blend from a remembered flag."""
    ax4 = axes(c)
    s = suffix.lower()
    col = re_children(c, k, f"slot{k}_recollapse_{s}", at_mem=False)
    o(f"      ReCollapse{suffix}:" + " " * (18 - len(suffix)) + "# a cut: boxes collapsed at the cage centre for a sampled step, flags shut, the chain reset to Mem, readout and payload held, Re 1")
    emit_motion(o, f"Slot{k} recollapse {s}", col)
    o("        transitions:")
    rungs()
    # The cut ended the sender's episode, and the overlap that re-forms on the next step meets the shut flag and is
    # rejected for its whole length (rejection is sticky); a collapse spanning a sampled step ends that rejected overlap.
    o(dwell(col, f"          - {{ to: ReOpen{suffix}, when: [], exitTime: 1.0 }}"))
    opn = re_children(c, k, f"slot{k}_reopen_{s}")
    o(f"      ReOpen{suffix}:" + " " * (22 - len(suffix)) + "# every box flag up at placeHalf on Mem: the returning sender is admitted through it, or the slot is given back")
    emit_motion(o, f"Slot{k} reopen {s}", opn)
    o("        transitions:")
    rungs()
    o(f"          - {{ to: ReShut{suffix}, when: [ {all_pos} ] }}   # the sender is back, admitted on every box")
    o(dwell(opn, "          - { to: Recycle, when: [], exitTime: 1.0 }") + "; the timeout: nothing came back")
    sh = re_children(c, k, f"slot{k}_reshut_{s}")
    o(f"      ReShut{suffix}:" + " " * (22 - len(suffix)) + "# flags shut, grown to followHalf: a step samples the grown cluster before the follower resumes")
    emit_motion(o, f"Slot{k} reshut {s}", sh)
    o("        transitions:")
    rungs()
    o(dwell(sh, f"          - {{ to: {back}, when: [ {all_pos} ], exitTime: 1.0 }}"))
    floor("Recycle", ax4, "a second cut inside the dwell: give the slot back, one reacquire per cut")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }   # the terminal fallback")


def emit_gate_layer(o, c):
    """mirror-detect's driver race (the standard VRLabs-lineage technique), lifted whole and given a third verdict: the
    wearer's own copy evaluates first, DetectMirror still false, and its Real state's localOnly driver sets it true; a
    mirror clone instantiates later with the wearer's values and runs no driver, so it forks to Mirror; a remote never
    takes the local branch. Gate carries the verdict as an AAP every park state waits on."""
    P = c["prefix"]
    o("  - name: Gate")
    o("    # Which copy of the avatar this animator is: 1 runs the rig (the wearer's own copy, every remote), 2 is a mirror")
    o("    # clone (docs/runtime.md §Parameters: a clone replays the wearer's parameter values, runs no driver and starts")
    o("    # from Entry). First in the layer order. A clone that read Gate 1 would run the rig on the wearer's receiver")
    o("    # floats and fire phantom bursts in the mirror; README §What is not proven names the one client fact this rests on.")
    o("    states:")
    o("      Init:")
    o("        motion: { clip: gate_wait }")
    o("        transitions:")
    o("          - { to: Fork,   when: [ IsLocal is true ] }")
    o("          - { to: Remote, when: [ IsLocal is false ] }")
    o("      Fork:")
    o("        motion: { clip: gate_wait }")
    o("        transitions:")
    o(f"          - {{ to: Real,   when: [ {P}/DetectMirror is false ] }}   # the wearer's own copy: it evaluates before its own driver fires")
    o(f"          - {{ to: Mirror, when: [ {P}/DetectMirror is true ] }}    # a mirror clone: it enters with the driver-set value")
    o("      Real:")
    o("        motion: { clip: gate_run }")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {P}/DetectMirror: 1 }} }}")
    o("      Mirror:")
    o("        motion: { clip: gate_mirror }")
    o("      Remote:")
    o("        motion: { clip: gate_run }")
    o("    default: Init")
    o("    layout:")
    o("      nodes: { Init: [30, 180], Fork: [-60, 260], Remote: [150, 260], Real: [-160, 340], Mirror: [50, 340] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_gate_clips(o, c):
    P = c["prefix"]
    o("  # Gate layer: the verdict, held by the state that reached it; Init and Fork leave Gate at its default 0.")
    o("  gate_wait: { seconds: 0.0167 }   # unresolved")
    emit_clip(o, "gate_run", {f"{P}/Gate": 1}, None, "the wearer's own copy and every remote: run the rig")
    emit_clip(o, "gate_mirror", {f"{P}/Gate": 2}, None, "a mirror clone: the enable-only states")


def emit_sweep_layer(o, c, ks):
    """The one writer of the three shared sweep AAPs. Every state writes all three — a WD-ON state
    reverts any AAP it does not write to its default (docs/runtime.md §Animator evaluation), so a value that
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
    o("    # ramp on. The front runs whenever a slot rides it and restarts from 0 at the face, so every sender inside the cube")
    o("    # is offered to exactly one flag-up cube once per pass.")
    o("    # Its second job: every state writes the Boundary meshes' scale and renderer enable (one state is always live here).")
    o("    states:")
    mirror = f"          - {{ to: MirrorOff, when: [ {P}/Gate greater 1.5 ] }}   # a mirror clone: the boundary's enable only; the front is the wearer's"
    run = f"{P}/Gate greater 0.5, {P}/Gate less 1.5"
    o("      Boot:                        # a fresh animator: the first pass runs from 0; leaves only on the Gate layer's verdict")
    o("        motion: { clip: sw_boot }")
    o("        transitions:")
    o(mirror)
    o(paused)
    o(off)
    o(f"          - {{ to: Wait, when: [ {en} is true, {run} ] }}")
    o("      Disabled:                    # the toggle is off: the next pass runs from 0")
    o("        motion: { clip: sw_off }")
    o("        transitions:")
    o(mirror)
    o(paused)
    o(f"          - {{ to: Wait, when: [ {en} is true, {run} ] }}")
    o("      Paused:                      # a distance-hide: the resume pass runs from 0")
    o("        motion: { clip: sw_paused }")
    o("        transitions:")
    o(mirror)
    o(f"          - {{ to: Disabled, when: [ IsAnimatorEnabled is true, {en} is false ] }}")
    o(f"          - {{ to: Wait, when: [ IsAnimatorEnabled is true, {en} is true, {run} ] }}")
    o("      MirrorOff:                   # a mirror clone, toggle off: the boundary hidden")
    o("        motion: { clip: sw_mirror_off }")
    o("        transitions:")
    o(f"          - {{ to: MirrorOn, when: [ {en} is true ] }}")
    o("      MirrorOn:                    # a mirror clone, toggle on: the boundary drawn at the wearer's scale")
    o("        motion: { clip: sw_mirror_on }")
    o("        transitions:")
    o(f"          - {{ to: MirrorOff, when: [ {en} is false ] }}")
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
        # The freeze: the sweeping slot's own riding readings (the slot layer's `ride_pos`, verbatim) while its Front
        # still reads 1, which is the frame it latches — a frame before its Front flag drops. Ramp's clip is not sampled
        # on the frame it leaves, so the front stops at the size that admitted, and the successor's shut cube (×
        # SweepPrev) appears at exactly that size. `greater 0`, never the release floor: the slot layer latches on
        # `greater 0`, and a predicate here that read tighter would latch without freezing.
        # Listed BEFORE the restart rung, not after: on a pass's last handoff the front has already read past the
        # face, so both rungs are eligible in the same evaluation and first-match decides; the freeze wins whenever both
        # are eligible. A sender taken on the frame the front crosses the face has no reading yet, and there Restart
        # wins (the docstring's restart race): the admission survives and the just-taken sender is re-offered once.
        sk = slot_name(c, k)
        o(f"          - {{ to: Wait, when: [ {sk}/Front greater 0.5, {', '.join(f'{sk}/{ax} greater 0' for ax in riding(c))} ] }}   # slot {k} latched: freeze the front on the admission frame")
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
    o("      nodes: { Boot: [30, 180], Disabled: [30, 270], Paused: [270, 270], MirrorOff: [510, 180], MirrorOn: [510, 270], Wait: [30, 360], Ramp: [270, 360], Restart: [30, 450] }")
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
    clip("sw_mirror_off", boundary_bindings(c, 0), None, "a mirror clone, toggle off: the boundary's enable (its scale, written too, is the wearer's on a clone)")
    clip("sw_mirror_on", boundary_bindings(c, 1), None, "a mirror clone, toggle on")
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


def emit_dedup_layer(o, c, ks):
    """The one always-live layer: the pairwise difference of the slots' last decoded points the dedup rungs compare
    against dedupBand."""
    o("  - name: Dedup")
    o("    # One state, one tree, no transitions, and deliberately no Paused and no Disabled: a non-normalized Direct tree")
    o("    # writes every binding it carries every frame, so nothing here can revert, and a park state would only add a")
    o("    # frame on which the differences read their defaults.")
    o("    # D/<j>_<k>/<a> = Mem_k − Mem_j in metres for every pair and every tilted axis. The weights are the Mem registers,")
    o("    # stored as (point + A)/S and so positive (a negative Direct weight clamps to 0); each clip writes ±S, and the")
    o("    # common A cancels in the difference. Every parameter here defaults to 0, so the below-weight-1 rest fill")
    o("    # contributes nothing and the difference is exact at any weight sum.")
    o("    states:")
    o("      Live:")
    o("        motion:")
    o("          tree: direct")
    o("          name: Dedup")
    o("          normalized: false")
    o("          children:")
    for k in ks:
        for a in POS:
            o(f"            - {{ clip: d_slot{k}_{a}, directWeight: {slot_name(c, k)}/Mem/{a} }}")
    o("    default: Live")
    o("    layout:")
    o("      nodes: { Live: [30, 180] }")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_dedup_clips(o, c, ks):
    P = c["prefix"]
    o("  # Dedup layer: one clip per (slot, axis) carrying every pair that slot is in — +S where it is the pair's higher")
    o("  # index, −S where it is the lower — at weight = that slot's Mem register on that axis.")
    for k in ks:
        for a in POS:
            sets = {}
            for j in ks:
                if j == k:
                    continue
                lo, hi = min(j, k), max(j, k)
                sets[f"{P}/D/{lo}_{hi}/{a}"] = S_REG if k == hi else -S_REG
            emit_clip(o, f"d_slot{k}_{a}", sets, None, f"× Slot{k}/Mem/{a}")


def table_segments(c):
    """The axis tables' segment count over ±B: lookupSegments per 2·TABLE_REF of span, so the chord width stays put
    as B moves."""
    return int(round(c["lookupSegments"] * bound(c) / TABLE_REF))


def yw_segments(c):
    """The yw² table's segment count: the axis tables' scaled by sqrt3, so a segment is as wide as theirs."""
    return int(round(table_segments(c) * SQRT3))


def readout_span(c):
    """The range one decoded axis can take, which the square tables span exactly: ±B, the bound rung's. The decoded
    point is absolute in the tilted frame, so a table clamped at the cluster's own extent would read every sender
    inside the zone. The Latch park at (B, −B, −B) sits on the end knots, so park_r2 is the exact 3B²."""
    B = bound(c)
    return (-B, B)


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
    """r² as the tables read the Latch park (B, −B, −B): the settle rung's guard, so it is exact by construction."""
    B = bound(c)
    return sum(table_square(sq_knots(c), v) for v in (B, -B, -B))


def sq_knots(c):
    lo, hi = readout_span(c)
    N = table_segments(c)
    return [lo + (hi - lo) * i / N for i in range(N + 1)]


def yw_knots(c):
    """yw = (x + y + z)/sqrt3 spans sqrt3 times one axis's range."""
    lo, hi = readout_span(c)
    M = yw_segments(c)
    return [SQRT3 * (lo + (hi - lo) * i / M) for i in range(M + 1)]


def build_clips(c, k):
    """Every clip of slot k, in emission order, as (name, (sets, seconds, comment)) rows, with section comments as
    (None, text) rows. Built before the layers are emitted so each dwell's bound can read the clip lengths."""
    me = slot_name(c, k)
    BX = boxes_path(k)
    O = out_path(k)
    h = c["followHalf"]
    r = c["senderRadius"]
    g = c["followGain"]
    S = S_REG
    A = reg_offset(c)
    B = bound(c)
    step = c["stepSeconds"]
    acq = 2 * c["acqHalf"] / c["boxSize"]
    follow = 2 * c["followHalf"] / c["boxSize"]
    place = 2 * c["placeHalf"] / c["boxSize"]
    collapsed = 0.001
    per_m = 2 / c["boxSize"]          # box scale per metre of front half-extent
    payload = f"{O}/Payload/GameObject.m_IsActive"
    buffer = f"{O}/Payload/Burst/GameObject.m_IsActive"
    four = c["fourBox"]
    rows = []

    def note(text):
        rows.append((None, text))

    def clip(name, sets, seconds=None, comment=None):
        rows.append((name, (sets, seconds, comment)))

    def cfg(active, flag, scale, opn, armed, payload_on, front=0, held=0, settled=0, re_=0, xn_flag=None, xn_scale=1, pos=(0, 0, 0)):
        d = {f"{BX}/GameObject.m_IsActive": active}
        for ax in axes(c):
            d[f"{BX}/{ax}/VRCContactReceiver.allowOthers"] = xn_flag if (ax == "X-" and xn_flag is not None) else flag
        for a in POS:
            d[f"{BX}/Transform.m_LocalScale.{a}"] = fmt(scale)
        # Boxes' localPosition is a binding every state writes: the follower and the reacquire move it, so a state that
        # omitted it would hold a stale centre under WD OFF and sweep the front about it. `pos` None leaves the write to
        # the caller (the tree states, whose constant term rides this clip).
        if pos is not None:
            for a, v in zip(POS, pos):
                d[f"{BX}/Transform.m_LocalPosition.{a}"] = fmt(v)
        # Output's localPosition likewise: the track and reacquire trees write it from the registers (their constants
        # replace these zeros), every other state parks it at the cage centre, so a free or latching slot's Output reads
        # the centre at WD OFF as well as ON.
        for a in POS:
            d[f"{O}/Transform.m_LocalPosition.{a}"] = 0
        if four:
            # X-'s own scale, relative to Boxes: collapsed while the other three ride the front (it would never read
            # above zero there), coincident with them everywhere else. Transform vectors animate as a unit.
            for a in POS:
                d[f"{xn_path(k)}/Transform.m_LocalScale.{a}"] = fmt(xn_scale)
        # Open: 1 while this slot holds the front position — SweepShut (shut), Sweep (flag up, Front 1 too) and
        # Partial. The self-open rung and the ring rungs read it.
        d[f"{me}/Open"] = opn
        d[f"{me}/Armed"] = armed
        d[f"{me}/Front"] = front
        # Held: this slot is holding a sender (Latch on). Settled: and that sender has reached the zone, the re-arm
        # band after it, or has been held past the fresh window. The dedup rungs read another slot's pair, so every
        # state must write both: a state that wrote neither would leave a stale 1 standing and make a newcomer yield
        # to a slot that has already released.
        d[f"{me}/Held"] = held
        d[f"{me}/Settled"] = settled
        # Re: 1 in the six reacquire states; every other slot's TrackOut holds its zone rungs on it.
        d[f"{me}/Re"] = re_
        d[payload] = payload_on
        # The buffer particle's GameObject is forced on in every state: nothing in the rig turns it off, and the
        # binding is kept so a copy whose Burst was saved inactive still fires on the payload edge.
        d[buffer] = 1
        return d

    # The follower's offset per reading at h = followHalf: (dx, dy, dz) and the R term; and the constant bias.
    if four:
        offs = {"X+": ((h, -h, -h), h), "X-": ((-h, -h, -h), h), "Y+": ((0, 2 * h, 0), 0), "Z+": ((0, 0, 2 * h), 0)}
        bias = (0.0, 0.0, 0.0)
    else:
        offs = {"X+": ((2 * h, 0, 0), 0), "Y+": ((0, 2 * h, 0), 0), "Z+": ((0, 0, 2 * h), 0)}
        bias = (-h - r,) * 3

    def point_terms(vec, base=1.0, centre=True):
        """The bindings a term of the decoded point drives, per unit of it on each axis: x y z and Output (metres),
        yw, Mem (1/S), and with `centre` the follower's share of the new centre, C (g/S) and Boxes (g)."""
        d = {}
        for a, v in zip(POS, vec):
            if v == 0:
                continue
            d[f"{me}/{a}"] = v * base
            d[f"{O}/Transform.m_LocalPosition.{a}"] = v * base
            d[f"{me}/Mem/{a}"] = v * base / S
            if centre:
                d[f"{me}/C/{a}"] = g * v * base / S
                d[f"{BX}/Transform.m_LocalPosition.{a}"] = g * v * base
        if sum(vec):
            d[f"{me}/yw"] = sum(vec) * base * YW_PER_AXIS
        return d

    def readout_const():
        """The follower's constant terms, carried by each track state's weight-One configuration: the read bias on the
        point (Mem's, C's share and Boxes' share of it), and the −A every signed write from a register owes."""
        d = {}
        for a, b in zip(POS, bias):
            d[f"{me}/{a}"] = fmt(b - A)
            d[f"{O}/Transform.m_LocalPosition.{a}"] = fmt(b - A)
            d[f"{me}/Mem/{a}"] = fmt(b / S)
            d[f"{me}/C/{a}"] = fmt(g * b / S)
            d[f"{BX}/Transform.m_LocalPosition.{a}"] = fmt(g * b - A)
        d[f"{me}/yw"] = fmt((sum(bias) - 3 * A) * YW_PER_AXIS)
        if four:
            d[f"{me}/R"] = fmt(-h)
        return d

    def held_const(readout):
        """A hold state's constant terms: −A on Boxes (its position is S·C − A), and with `readout` the −A on the held
        readout too (the reacquire states hold x, y, z, yw and Output at Mem)."""
        d = {f"{BX}/Transform.m_LocalPosition.{a}": fmt(-A) for a in POS}
        if readout:
            for a in POS:
                d[f"{me}/{a}"] = fmt(-A)
                d[f"{O}/Transform.m_LocalPosition.{a}"] = fmt(-A)
            d[f"{me}/yw"] = fmt(-3 * A * YW_PER_AXIS)
        return d

    def park():
        # Parked at (B, −B, −B): x at +B is the sentinel a consumer reads as "not yet tracking"; r² reads 3B², outside
        # every zone, and the settle guard compares against the tables' own value there (park_r2). yw parks at that
        # point's height, so the first p2 the tree computes is about 8B²/3 and not r² minus a stale square.
        d = {f"{me}/x": fmt(B), f"{me}/y": fmt(-B), f"{me}/z": fmt(-B), f"{me}/yw": fmt(-B * YW_PER_AXIS)}
        # r2 and p2 as the tables would read the park, so a consumer gating on p2 reads the latch outside every zone.
        d[f"{me}/r2"] = fmt(park_r2(c))
        d[f"{me}/p2"] = fmt(park_r2(c) - table_square(yw_knots(c), -B * YW_PER_AXIS))
        if four:
            # The frames before the first measurement lands: R carries the configured assumption rather than zero.
            d[f"{me}/R"] = fmt(r)
        return d

    def fmts(d):
        return {key: fmt(v) for key, v in d.items()}

    regs = chain(c) + ["Mem"]
    note(f"Slot {k} configurations — every one writes the box stow, the flag on every receiver, Boxes' scale and localPosition"
         + (", X-'s scale" if four else "") + ", the six protocol flags, the payload toggle and the buffer particle's force-on.")
    clip(f"slot{k}_boot", cfg(0, 0, acq, 0, 0, 0), step, "stowed (a fresh animator)")
    clip(f"slot{k}_off", cfg(0, 0, acq, 0, 0, 0), step, "stowed; a stow shorter than a step comes back deaf")
    clip(f"slot{k}_paused", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed through the pause")
    clip(f"slot{k}_mirror_off", {payload: 0, buffer: 1}, None, "a mirror clone, Shown 0: the payload off; every transform is the wearer's, the rest holds its rest value")
    clip(f"slot{k}_mirror_on", {payload: 1, buffer: 1}, None, "a mirror clone, Shown 1: the payload on, the burst fired on the edge")
    clip(f"slot{k}_armed", cfg(1, 0, collapsed, 0, 1, 0), step, "Armed 1, collapsed: holds no rejections; the ring rule reads Armed one frame late")
    clip(f"slot{k}_sweepshut", cfg(1, 0, collapsed, 1, 0, 0, xn_scale=collapsed), step, "Open 1, flags shut, base scale: the front's own re-rejection step (the tree adds × SweepPrev)")
    clip(f"slot{k}_sweep_cfg", cfg(1, 1, collapsed, 1, 0, 0, front=1, xn_flag=0, xn_scale=collapsed), None,
         "Open 1, Front 1, riding flags up" + (", X- shut and collapsed" if four else "") + ", base scale: the growing cube's constant part")
    # F, the slot's front-size register, rides this clip: × Sweep in Sweep and Partial it is last frame's front, the size
    # the admitting cube had, and Latch decodes against it. × SweepPrev in SweepShut it is written too, harmlessly: Latch
    # is never entered from SweepShut, and Sweep's first evaluation overwrites it.
    clip(f"slot{k}_front_scale", {**{f"{BX}/Transform.m_LocalScale.{a}": fmt(per_m) for a in POS}, f"{me}/F": 1},
         None, "× Sweep: the cube at the front, and F ← the front")
    clip(f"slot{k}_open_wait", cfg(1, 1, collapsed, 1, 0, 0, xn_flag=0, xn_scale=collapsed), step, "Open 1 held a step at base scale: the partial-admission grace")

    note(f"Slot {k} latch: the decode at the admitting front size, per axis 2·F·V − F − r (r = senderRadius), into Boxes' position")
    note("(metres) and every register ((point + A)/S). F·V is the nested tree: the place_* clips sit under a child weighted by F.")
    latch = cfg(1, 0, place, 0, 0, 0, held=1, xn_flag=1, pos=None)
    for a in POS:
        latch[f"{BX}/Transform.m_LocalPosition.{a}"] = fmt(-r)
        for reg in regs:
            latch[f"{me}/{reg}/{a}"] = fmt((A - r) / S)
    latch.update(park())
    clip(f"slot{k}_latch", latch, None, "placeHalf cluster, riding flags shut" + (", X- flag up" if four else "") + ", Held 1, readout parked at (B, −B, −B); the decode's constant terms")
    neg = {f"{me}/F": 1}
    for a in POS:
        neg[f"{BX}/Transform.m_LocalPosition.{a}"] = -1
        for reg in regs:
            neg[f"{me}/{reg}/{a}"] = fmt(-1 / S)
    clip(f"slot{k}_place_neg", neg, None, "× F × One: the −F term on every axis, and F ← F (its self-copy, so a second Latch evaluation decodes at the same size)")
    for ax in riding(c):
        a = RIDE_AXIS[ax]
        # 2 metres of position per metre of F per unit reading: the face reading is (F + d + r)/(2F) over a cube of
        # half-extent F. Not 2/boxSize: F is a half-extent in metres (front_scale's per_m converts it to box scale).
        clip(f"slot{k}_place_{ax_tag(ax)}", {f"{BX}/Transform.m_LocalPosition.{a}": 2, **{f"{me}/{reg}/{a}": fmt(2 / S) for reg in regs}},
             None, f"× F × {ax}: the decode's reading term on {a}")

    for ax in riding(c):
        a = RIDE_AXIS[ax]
        corr = 2 * r
        clip(f"slot{k}_sat_{ax_tag(ax)}_0", {f"{BX}/Transform.m_LocalPosition.{a}": 0, **{f"{me}/{reg}/{a}": 0 for reg in regs}},
             None, f"{ax} at or below 0.999: no correction on {a}")
        clip(f"slot{k}_sat_{ax_tag(ax)}_2r", {f"{BX}/Transform.m_LocalPosition.{a}": fmt(corr), **{f"{me}/{reg}/{a}": fmt(corr / S) for reg in regs}},
             None, f"{ax} at 1.0: +2·senderRadius on {a}, the sender's centre past the face it straddles")

    note(f"Slot {k} latch wait and grow: the placement held. Boxes sits at S·C − A, every register copies itself.")
    lw = cfg(1, 0, place, 0, 0, 0, held=1, xn_flag=1, pos=None)
    lw.update(held_const(False))
    lw.update(park())
    clip(f"slot{k}_latchwait", lw, 2 * step, "the placement as Latch wrote it, for two collision steps" + (": X- reads its value on the second" if four else ""))
    lg = cfg(1, 0, follow, 0, 0, 0, held=1, pos=None)
    lg.update(held_const(False))
    lg.update(park())
    clip(f"slot{k}_latchgrow", lg, c["latchSeconds"], "every flag shut, the followHalf cluster: a collision step samples it before TrackOut decodes")
    for reg in regs:
        for a in POS:
            d = {f"{me}/{reg}/{a}": 1}
            if reg == "C":
                d[f"{BX}/Transform.m_LocalPosition.{a}"] = S
            clip(f"slot{k}_keep_{reg}_{a}", d, None, f"× {reg}/{a}: hold" + (", Boxes there" if reg == "C" else ""))

    note(f"Slot {k} follower: the configurations carry the readout's constants (bias and −A); the reading children the offset at")
    note("h = followHalf; the register children the centre's (1 − g) share, the chain's copies and, on the pairing register, the")
    note(f"decoded point's base. Pairing register: {pairing(c)} (pairDelay {c['pairDelay']}); g = {fmt(g)}; A = {fmt(A)}, S = {S}.")
    for name, payload_on, settled, why in ((f"slot{k}_hold", 0, 0, "the follower, payload off, fresh (outside the zone, never yet inside it)"),
                                           (f"slot{k}_hold_band", 0, 1, "the follower, payload off, settled (the re-arm band, or fresh no longer)"),
                                           (f"slot{k}_hold_burst", 1, 1, "the follower, payload on (inside the zone)")):
        d = cfg(1, 0, follow, 0, 0, payload_on, held=1, settled=settled, pos=None)
        d.update(readout_const())
        clip(name, d, None, why)
    for ax in axes(c):
        vec, rterm = offs[ax]
        d = point_terms(vec)
        if rterm:
            d[f"{me}/R"] = rterm
        clip(f"slot{k}_read_{ax_tag(ax)}", fmts(d), None, f"× {ax}: the offset at h = followHalf")
    ch = chain(c)
    for i, reg in enumerate(ch):
        for j, a in enumerate(POS):
            d = {}
            if reg == "C":
                d[f"{me}/C/{a}"] = 1 - g
                d[f"{BX}/Transform.m_LocalPosition.{a}"] = (1 - g) * S
            if i + 1 < len(ch):
                d[f"{me}/{ch[i + 1]}/{a}"] = 1
            if reg == pairing(c):
                unit = [0, 0, 0]
                unit[j] = 1
                for key, v in point_terms(unit, base=S).items():
                    d[key] = d.get(key, 0) + v
            parts = (["the centre's (1 − g) share"] if reg == "C" else []) + ([f"{ch[i + 1]} ← {reg}"] if i + 1 < len(ch) else []) \
                + (["the decoded point's base"] if reg == pairing(c) else [])
            clip(f"slot{k}_follow_{reg}_{a}", fmts(d), None, f"× {reg}/{a}: " + ", ".join(parts))

    note(f"Slot {k} reacquire: the readout and every register at Mem, Boxes at Mem once reopened (the collapse sits at the centre).")
    for s, payload_on in (("in", 1), ("band", 0)):
        for state, scale, flag, secs, why in (("recollapse", collapsed, 0, step, "collapsed for a sampled step, flags shut: ends the episode the shut flag rejected"),
                                              ("reopen", place, 1, c["reacquireSeconds"], "every box flag up at placeHalf: its length is the timeout"),
                                              ("reshut", follow, 0, c["latchSeconds"], "flags shut, the followHalf cluster: a step samples it before the follower resumes")):
            # ReCollapse collapses at the cage centre, not at Mem: a collapsed box at the sender's own point is still inside
            # the sender's sphere, so the rejected overlap never breaks and ReOpen could never re-admit a still sender.
            # Recycle collapses at the centre for the same reason. ReOpen and ReShut put Boxes back at Mem.
            at_mem = state != "recollapse"
            d = cfg(1, flag, scale, 0, 0, payload_on, held=1, settled=1, re_=1, pos=None if at_mem else (0, 0, 0))
            hc = held_const(True)
            if not at_mem:
                hc = {key: v for key, v in hc.items() if not key.startswith(f"{BX}/")}
            d.update(hc)
            clip(f"slot{k}_{state}_{s}", d, secs, why + (", payload held on" if payload_on else ", payload held off"))
    for j, a in enumerate(POS):
        d = {f"{me}/{reg}/{a}": 1 for reg in regs}
        d[f"{BX}/Transform.m_LocalPosition.{a}"] = S
        unit = [0, 0, 0]
        unit[j] = 1
        for key, v in point_terms(unit, base=S, centre=False).items():
            if key != f"{me}/Mem/{a}":
                d[key] = v
        clip(f"slot{k}_re_mem_{a}", fmts(d), None, f"× Mem/{a}: Mem held, the chain reset to it, Boxes and the readout there")
        d = {key: v for key, v in d.items() if not key.startswith(f"{BX}/")}
        clip(f"slot{k}_re_hold_{a}", fmts(d), None, f"× Mem/{a}: Mem held, the chain reset to it, the readout there; Boxes stays at the centre")
    if four:
        clip(f"slot{k}_re_R", {f"{me}/R": 1}, None, "× R: the measured radius held")
    clip(f"slot{k}_recycle", cfg(1, 0, collapsed, 0, 0, 0), step, "collapsed at the cage centre for a step, flags shut: a fresh overlap episode for everything inside, the re-arm primitive")

    lo, hi = readout_span(c)
    N = table_segments(c)
    note(f"Slot {k} x² table: {N} segments over [{fmt(lo)}, {fmt(hi)}], ±B, the decoded point's whole range, so nothing inside the")
    note("bound clamps; each 1D tree blends the two nearest knots, a chord that overestimates by ≤ w²/4.")
    note("Each square clip writes r2 (the distance² from the centre, exported) and p2 (the in-plane radius² the zone reads) alike;")
    note("the −yw² table below then takes the height's square back out of p2 alone. Its chord overestimates yw² and so reads")
    note("p2 low by up to the same w²/4, an outward bias of the zone that the axis tables' inward bias partly cancels.")
    for i, t in enumerate(sq_knots(c)):
        clip(f"slot{k}_sq_{i}", {f"{me}/r2": fmt(t * t), f"{me}/p2": fmt(t * t)})
    yk = yw_knots(c)
    note(f"Slot {k} −yw² table: {len(yk) - 1} segments over [{fmt(yk[0])}, {fmt(yk[-1])}], yw's whole range.")
    for i, t in enumerate(yk):
        clip(f"slot{k}_nsq_{i}", {f"{me}/p2": fmt(-t * t)})
    return rows


def clip_lengths(rows):
    return {name: (spec[1] or FRAME) for name, spec in rows if name is not None}


def emit_clips(o, rows):
    for name, spec in rows:
        if name is None:
            o(f"  # {spec}")
        else:
            emit_clip(o, name, *spec)


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
    B = bound(c)
    rows = {k: build_clips(c, k) for k in ks}
    L = []
    o = L.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o(f"# contact-radar: {K} per-sender slots, tags {c['tags']}, {len(axes(c))} coincident face-proximity boxes each; the riding readings are the latch.")
    o("# The acquisition cube is tilted (diagonal vertical) on the prefab; the readout is in that frame, and yw = (x + y + z)/sqrt3")
    o("# undoes the tilt on the vertical axis alone. The zone is a vertical cylinder: p2 = x² + y² + z² − yw² is the in-plane radius².")
    far = f", far release at p2 > {fmt(c['farRadius'] ** 2)} ({c['farRadius']} m, TrackBand only)" if c["farRadius"] is not None else ""
    o(f"# Burst at p2 < {fmt(rin2)} (R_in {c['burstRadius']} m), re-arm at p2 > {fmt(rout2)} (R_out {c['rearmRadius']} m){far}; no height bound:")
    o(f"# a sender at the burst radius is inside the acquisition cube from every direction within ±{fmt(band_half_height(c, c['burstRadius']))} m")
    o("# of the centre height, and past that band the cube's corners are the zone's ends.")
    rtxt = (f"sender radius measured per slot from the X- box, {c['senderRadius']} m assumed at the placement"
            if c["fourBox"] else f"sender radius {c['senderRadius']} m")
    o(f"# Acquisition half-extent {c['acqHalf']} m; a latch places a {c['placeHalf']} m cluster at the decoded point and grows it to {c['followHalf']} m,")
    o(f"# which follows the sender at gain {c['followGain']}, paired {c['pairDelay']} evaluations back; bound ±{fmt(B)} m per tilted axis; {rtxt};")
    o(f"# step dwell {c['stepSeconds']} s, grow dwell {c['latchSeconds']} s, reacquire wait {c['reacquireSeconds']} s; dedup band {c['dedupBand']} m.")
    o(f"# One slot at a time rides an expanding front from the centre to the face over {c['sweepSeconds']} s, and the front restarts")
    o("# there, so every sender inside the cube is offered to exactly one flag-up cube per pass and admitted alone as the front")
    o("# reaches it; the Dedup layer releases a re-admitted sender another slot already holds.")
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
    o("  IsLocal: bool   # VRC built-in: true on the wearer's own copy and on its mirror clone, false on every remote")
    o(f"  {P}/DetectMirror: {{ type: bool, scratch: true }}   # mirror-detect's race residue: a localOnly driver sets it on the wearer's copy; a mirror clone enters with it already true. Never saved")
    o(f"  {P}/Gate: {{ type: float, aap: true, scratch: true }}   # the Gate layer's verdict: 0 unresolved, 1 this copy runs the rig (the wearer's own and every remote), 2 a mirror clone")
    o(f"  {P}/One: {{ type: float, default: 1, scratch: true }}   # constant direct weight, never driven")
    o("  # The front (written only by the Sweep layer): Sweep is the front half-extent (m), SweepBase the front the current")
    o("  # sweeper's ramp started from, SweepPrev last frame's Sweep — the size the next slot's shut cube appears at, so the")
    o("  # handoff leaves no band.")
    o(f"  {P}/Sweep: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepBase: {{ type: float, aap: true, scratch: true }}")
    o(f"  {P}/SweepPrev: {{ type: float, aap: true, scratch: true }}")
    for k in ks:
        me = slot_name(c, k)
        o(f"  # Slot {k}: receiver floats (never a clip), the readout AAPs, the six protocol flags, then the follower's registers,")
        o("  # each stored as (point + A)/S with default 0 (the rest fill a register weight leaves is then zero).")
        for ax in axes(c):
            o(f"  {me}/{ax}: float")
        o(f"  {me}/Shown: float   # driver-written, never a clip: 1 while this slot's payload is on. Unsynced and in the params asset, so a mirror clone replays the wearer's value")
        for ax in ("x", "y", "z", "r2"):
            o(f"  {me}/{ax}: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/yw: {{ type: float, aap: true, scratch: true }}   # the sender's height above the cage centre, m: (x + y + z)/sqrt3 undoes the tilt on that axis")
        o(f"  {me}/p2: {{ type: float, aap: true, scratch: true }}   # the in-plane radius², r2 − yw²: what the zone compares")
        if c["fourBox"]:
            o(f"  {me}/R: {{ type: float, aap: true, scratch: true }}   # the measured sender radius, m — the export a consumer reads")
        o(f"  {me}/Open: {{ type: float, aap: true, scratch: true }}   # 1 while this slot holds the front position: shut at SweepPrev, riding it flag-up, or in Partial")
        o(f"  {me}/Armed: {{ type: float, aap: true, scratch: true }}   # 1 while collapsed and waiting for the ring")
        o(f"  {me}/Front: {{ type: float, aap: true, scratch: true }}   # 1 while this slot's cube rides the front")
        o(f"  {me}/Held: {{ type: float, aap: true, scratch: true }}   # 1 while this slot holds a sender: Latch and every state after it")
        o(f"  {me}/Settled: {{ type: float, aap: true, scratch: true }}   # 1 once the sender it holds has reached the zone (inside it, or in the re-arm band after) or has been held outside it past the fresh window: a fresh lower-index slot yields to a settled holder")
        o(f"  {me}/Re: {{ type: float, aap: true, scratch: true }}   # 1 in the six reacquire states: another slot's fresh admission waits in TrackOut on it")
        o(f"  {me}/F: {{ type: float, aap: true, scratch: true }}   # the front size the admission was made at, m: written while riding, read by Latch alone")
        for reg in chain(c) + ["Mem"]:
            what = {"C": "the cluster centre", "C1": "the centre one evaluation older than C", "C2": "the centre two evaluations older than C",
                    "Mem": "the last decoded point"}[reg]
            for a in POS:
                o(f"  {me}/{reg}/{a}: {{ type: float, aap: true, scratch: true }}   # {what}, stored (value + A)/S")
    o("  # The Dedup layer's differences: D/<j>_<k>/<a> = Mem_k − Mem_j in metres, for every pair j < k and every tilted axis.")
    o("  # Each defaults to 0, which is what makes the tree's below-weight-1 rest fill vanish and the difference exact.")
    for j in ks:
        for k in ks:
            if j >= k:
                continue
            for a in POS:
                o(f"  {P}/D/{j}_{k}/{a}: {{ type: float, aap: true, scratch: true }}")
    o("")
    o("layers:")
    emit_gate_layer(o, c)
    for k in ks:
        emit_layer(o, c, k, ks, clip_lengths(rows[k]))
    emit_sweep_layer(o, c, ks)
    emit_dedup_layer(o, c, ks)
    o("")
    o("clips:")
    emit_gate_clips(o, c)
    for k in ks:
        emit_clips(o, rows[k])
    emit_sweep_clips(o, c)
    emit_dedup_clips(o, c, ks)
    facts = {"K": K, "fourBox": c["fourBox"], "farRadius": c["farRadius"],
             "receivers": len(axes(c)) * K, "syncedBits": 1, "layers": K + 3,
             "bandHalfHeight": band_half_height(c, c["burstRadius"]), "bound": B,
             "acqScale": 2 * c["acqHalf"] / c["boxSize"], "followScale": 2 * c["followHalf"] / c["boxSize"],
             "placeScale": 2 * c["placeHalf"] / c["boxSize"]}
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
        """The two facts the readout rests on past the size and the node scale: the shape sits ON its transform
        (a nonzero offset moves one box off its siblings while every field still reads right), and the node
        hangs under `Boxes` of the very `Slot<k>` its parameter names (a box filed under the wrong slot, or
        under a node of its own beside Boxes, is animated by the wrong clip and moves independently). The
        latch's decode and the follower's readout take a slot's boxes to be one coincident cluster at Boxes'
        position; both of these silently break that, and the decoded point dedup compares with it."""
        why = "the readout takes a slot's boxes to be one coincident cluster at Boxes' position"
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
    # Dedup compares points decoded in each slot's own frame, so a slot nudged or scaled off the others still
    # tracks, still bursts, and quietly stops recognising the duplicate it was added to catch.
    ok = assert_(not [tid for tid, (go, _, _) in trs.items() if gos[go] == "Gate"],
                 "no Gate node: the shared OnEnter gate was removed; delete it from this copy") and ok
    for t in slots:
        ok = assert_(same_rotation(rots.get(t), TILT), f"{gos[trs[t][0]]} carries the tilt (got {rots.get(t)})") and ok
        ok = assert_(poss.get(t) == (0.0, 0.0, 0.0),
                     f"{gos[trs[t][0]]} sits at local position zero (got {poss.get(t)}) — dedup compares points decoded in each slot's own frame, so every slot's frame must be the same") and ok
        ok = assert_(trs[t][2] == (1.0, 1.0, 1.0),
                     f"{gos[trs[t][0]]} carries local scale one (got {trs[t][2]}) — dedup compares points decoded in each slot's own frame, and Boxes is the only size lever") and ok
        # Boxes at the slot's origin: every state writes its position, so the saved one is only the edit-mode rest, but a
        # copy built by hand starts from it, and the readout's coefficients and the latch's placement take Boxes and Output
        # to share the slot's origin.
        bxs = [b for b, (go, father, _) in trs.items() if father == t and gos[go] == "Boxes"]
        ok = assert_(len(bxs) == 1 and poss.get(bxs[0]) == (0.0, 0.0, 0.0),
                     f"{gos[trs[t][0]]}/Boxes sits at local position zero (got {[poss.get(b) for b in bxs]}) — the readout's "
                     "coefficients and the latch's placement put a sender relative to the slot's origin, which Output shares") and ok
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
