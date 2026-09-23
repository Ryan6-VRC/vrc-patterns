# contact-radar (Module)

A per-hand tracker: latches onto each other player's hand that enters a zone around you, one slot per hand, and exposes where that hand is so you can attach anything to it. Sensing runs on every client, so an attached prop sits on the hand where that client draws it. The shipped payload is a particle burst on entry; the production consumers of this entry attach props to the tracked hand.

## How it works

- Box contacts are selectively enabled and latched to track a series of matching senders as they enter and leave the zone. Each tracked hand holds one of K slots (K is how many hands can be tracked at once); only one slot accepts new senders at a time, and on acquisition it shuts its filter and the next slot opens in the same frame.
- One Constant-mode contact per slot halves the acquisition window, which is otherwise limited by a Proximity contact's two-step delay, and tells that slot that *it* took the hand, where a shared receiver could only report that something arrived somewhere.
- Three face-proximity boxes per slot reconstruct the sender's position. A blend tree sums the squares into r², and an animator transition compares r² against two radii, so the zone is a sphere with per-hand hysteresis.
- The cube is tilted so its body diagonal is vertical. A standing player's senders (head, hips, hands) then cross a face one at a time instead of all in one collision step, so each usually takes its own slot (§Traps). The sphere is the one zone shape that reads the same under the tilt.
- At enable, at load and after a distance-hide, one slot's cube grows outward from the centre so hands already inside are acquired one at a time.
- A dedup layer compares slots' raw readings and releases a slot that re-acquired a hand another slot already holds.
- Nothing is synced but the enable.

## Install guide

1. Know what a slot does. A hand keeps its slot as long as it stays near you (inside the larger tracking cube), so a prop hung on the slot follows the hand for as long as it is there; the shipped burst re-fires each time the hand pulls back a short distance and comes in again. For a doorbell, read the payload's rising edge and ignore its level (§Design notes, what a consumer reads).
2. Drop an instance of `ContactRadar.prefab` at the avatar root. `HomeAnchor` snaps to the Hips on its own; drag its `Offset` child to move where the zone sits. Edits belong on the instance or an owned copy, never on the package asset.
3. Set the body SkinnedMeshRenderer's Bounds (its `localBounds`) to reach twice `acqHalf` plus an arm's length in every direction from the hips; the tilted cube's corners reach nearly that far straight up and down. VRChat pauses a copy's animator while its observer is not looking at you, and this rig gets no signal for that, so a hand that entered while an observer looked away would burst late. An observer whose camera is inside any of your renderers' bounds never pauses you; with the bounds set, every toucher keeps your animator running. A far observer looking away is the accepted residual; compose `anti-cull` to close that too.
4. Scale `Cage/Size` if the zone should be larger or smaller. Uniform scale only, shipped at 1; it scales the zone, the readout and the hysteresis together.
5. Build. The expression menu gains a `Contact Radar` toggle, on by default.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- `ContactRadar/Enable` is the one parameter: synced, unsaved, on by default. Off stows the receivers and zeroes them on every client.
- Hang your prop under a slot's `Output`; it is the reconstructed hand position, in metres, one frame behind the hand, and stays world-aligned. Every slot needs its own copy. The parameters `CR/Slot<k>/x`, `y`, `z` carry the same readout for a controller, `r2` its squared distance, and `x` sits at `+holdHalf` while the slot has latched but has no reading yet.
- `Payload` under `Output` is the node the controller turns on while the hand is inside the sphere: put a mesh there and it shows while the hand is inside; a buffer particle there fires once on entry. `Marker` and `Burst` are the shipped examples of each.
- Replace `Marker` (a placeholder cube on the default material) with your mesh, or delete it.
- Restyle `Emit`, the visible burst, which ships on Unity's default particle sprite, or delete `Emit` and `Burst` together if you want no burst. Never disable `Emit` while keeping it; disabling it truncates a burst in flight.
- Activate `Boundary` to draw the sphere. Its `Sphere` ships on the default material, which is invisible from inside, so give it a `Cull Off` unlit (`overlay-shaders`). The controller scales it to the sphere's radius and shows it only while the toggle is on.
- To sense another sender than `HandR`, see §Changing it.

## Additional notes

- **One instance per avatar.** The menu front is a bare VRCFury `Toggle`, which exports an unprefixed name; two instances would collide on it.
- **Your own hands never fire it.** The wearer is excluded by design, so nothing happens when you test alone (§Verifying the install).
- **Do not rename anything under `Cage`.** The clip paths are the hierarchy names; a rename silently unbinds a slot.
- **Leave `assets/World.prefab` alone.** It is a never-instantiated asset that resolves as the world origin on every client, and two constraints on `Cage` source it. Do not instantiate it, delete it, or press Activate on those constraints: their offsets must stay zero.
- **The receivers count against your rank.** They cannot be local-only, since remote copies must sense for the tracking to reproduce, so all 4K of them count toward the SDK's contact-count statistic (`optimization.md`). At the shipped K that is past the Good gate on its own, and the 2K particle systems cap the avatar at Medium independently; raising K pushes both.
- **`Cage/Size` far from 1 shifts the readout.** Everything in the rig is metres in that node's frame except the sender-radius bias, so `Output` lands up to `senderRadius × (scale − 1)` off the hand per axis. Measured in av3emu at half and double size, that offset stays inside the puff's own spread; beyond that range, turn on `fourBox` to remove the term or retune CONFIG (§Knobs).
- **An optimizer that strips inactive objects** removes `Boundary` when you leave it off, which is intended. `Payload` is also inactive at rest with `Marker` and `Burst` inside it; a pass that strips inactive subtrees takes both.

## Performance stats

```c++
Contact Receivers:  4K       (16 at the shipped K of 4; 5K with fourBox; none local-only)
FX Animator Layers: K + 2    (one per slot, Sweep, Dedup)
Constraints:        3        (depth 1)
Particle Systems:   2K
Mesh Renderers:     K + 1    (K markers, one inactive boundary)
Material Slots:     2K + 1   (K markers, K bursts, one boundary)
Synced parameters:  1 bit
```

## Knobs

`Cage/Size` is the transform above. Everything else is `generate.py`'s CONFIG: edit, regenerate, recompile `built/` as a unit (§Changing it). Each row gives the direction and the relation; the value lives in the code (the shipped zone radius is `burstRadius` there), and a lint in `generate.py` refuses a value that breaks the relation.

Three regions come up throughout. The **re-arm band** is the ring between the burst radius and the re-arm radius. The **approach gap** is the space between the sphere and the face of the acquisition cube a hand must enter. The **hold shell** is the space between the acquisition cube's face and the larger hold cube's face, where a tracked hand may drift before it is released.

| Knob | What it does |
|---|---|
| `K` | Hands tracked at once. Each slot costs one FX layer and four receivers on every copy (five with `fourBox`), and the dedup rungs and parameters grow with K squared. Past a couple of dozen coincident receivers the rig measures its own configuration (`runtime.md` §Contacts). Lint: at least two, since one slot has nothing to hand off to. Changing K also means changing the prefab (§Changing it) |
| `burstRadius`, `rearmRadius` | The sphere, and the outer edge of the re-arm band. The band must exceed the client's readout noise at the world's working distance (`runtime.md` §Contacts) or a parked hand dithers a burst. Lints: the re-arm radius above the burst radius, and both reachable inside the cube on axis after the sender radius is added |
| `acqHalf`, `holdHalf` | The cube a hand must enter, and the larger cube it is tracked in. The approach gap on each axis is `acqHalf − burstRadius`, plus the sender's radius, since the overlap begins when the hand's surface reaches the face. It is the head start the latch gets before a fast hand is inside the sphere. The cube is tilted, so that distance depends on direction: a little further sideways, nearly twice as far straight up or down. `holdHalf − acqHalf` is the hold shell's depth. Both ship small, because a bigger cube fills K with hands that were never going to poke you. Lints: hold at least acquisition; the burst reachable; the box within the SDK's serialized limit |
| `senderRadius` | The constant bias of a capsule hand's nearest surface toward each face. Measure it on a real hand in-client, or let `fourBox` measure it per sender |
| `fourBox` | Measure the sender radius from an opposed pair of boxes instead of assuming it, so the burst origin is exact for any hand at any `Cage/Size`. Costs one receiver per slot and one more dedup axis, which is right: two senders of different radii can agree on three faces and differ on the fourth. Exported per slot as `CR/Slot<k>/R`. Needs an `X−` box the shipped prefab does not carry (§Changing it) |
| `stepSeconds` | Every timed wait that must span collision steps. Lint: above the longest gap between two steps (`runtime.md` §Contacts) |
| `latchSeconds` | How long a slot that has latched waits for its own readings before giving the slot back. Lint: at least twice `stepSeconds`, since the readings land a client step after the admission edge. Raising it holds a slot longer on every admission whose readings never come; lowering it drops real admissions on a jittery client |
| `dedupEpsilon` | How close two slots' raw readings must be on every axis before a just-latched slot decides it holds a hand another slot already holds (§Design notes). It is a tolerance on the reading, so the volume it describes scales with `holdHalf`. Lints: refuse zero, since a float transition never compares equal, and refuse a volume as large as a sender |
| `sweepSeconds` | How long the sweep at enable takes to grow from the centre to the cube face. Two hands the same distance out, as the tilted cube measures distance (the largest of the three axis distances), land on one slot if the front reaches both inside a frame; slower separates closer hands, faster looks snappier, and a low frame rate widens the window. Lint: no more than a quarter of the cube per collision step |
| `lookupSegments` | The x² table resolution. The chord error is one-sided and inward, so a coarse table shrinks the effective burst radius slightly |
| `enableDefault` | The enable's default in the document; False loads quiet, so the first sweep is the toggle's. The prefab `Toggle`'s default is the same bit from the other side and must agree; `--check` holds the pair |

**Provenance:** the three-box face-proximity readout is `box-tracker`'s (VRLabs Contact-Tracker ancestry), with the fourth box moved behind a flag and the sender radius supplied by config. The buffer-particle form is hfcRed/VRLabs Particle-Bufferer (MIT). The tilted cage is `absolute-grip-prop`'s, kept here for a different reason. The per-sender slot protocol, the expanding front and the dedup layer are this entry's own.

## Design notes

The state-by-state walk is `generate.py`'s module docstring, at the place an edit would break it, and `controller.yaml` carries every rung with a comment. This section states what the rig guarantees and why.

**What a consumer reads.** The readout writes `Output`'s localPosition and `CR/Slot<k>/x`, `y`, `z` in metres in the `Cage/Size` frame, and `r2` in metres squared; under `fourBox`, `CR/Slot<k>/R` is the measured sender radius. A slot that has latched but has no readings yet parks `x` at `+holdHalf`, which a consumer can read as "not yet tracking". `Payload` toggles on while the hand is inside the sphere and serves two consumers at once: a buffer particle inside it reads the enable edge (one puff per entry, however long the hand stays) and a mesh inside it reads the level.

The protocol rests on four contact-runtime facts in `runtime.md` §Contacts: a receiver aggregates its senders and the strongest wins; rejection at acquisition is sticky for the whole overlap; a host-scale collapse and restore is a fresh overlap episode with no deaf mode; a Constant receiver's value lands one collision step before a Proximity one. Two more are this entry's own, measured in av3emu and not yet in-client: a same-evaluation flag handoff between two receivers partitions the senders exactly, and a sender acquired in the one step before the flip is double-admitted; and a Constant receiver's value is written on admission and recomputed on departure, with nothing refreshing it between.

**Exactly one slot is open, and a hand goes to the slot that was open when it arrived.** Every other slot is armed with its allow flag shut, so a hand already inside is invisible to it for the whole overlap. Each slot's Constant box, `Hit`, rides the same flag as its readout boxes; its rising edge is the slot's own record that *this* slot took something, a step before any reading exists, where a shared receiver could only report that something somewhere arrived. The open slot latches on that edge and the next armed slot opens in the same evaluation, so the admission windows tile with no gap. When the edge is missed the slot latches on its readings a step later, and when nothing is open at all the lowest armed slot opens itself within one `stepSeconds`. Release reads the axis readings alone and never `Hit`: an admission the `Hit` box missed tracks with `Hit` still zero, and a release rung on `Hit` would recycle it on its first tracking frame. A released slot re-arms by collapsing its boxes for a step and restoring them shut, which rejects everything still inside.

**The cage is pinned to the world.** `Cage` is held at world rotation and world scale by the two `World.prefab` constraints and rides the Hips by position only. World rotation keeps the cube's corners from sweeping a parked hand out and back in when you turn; world scale keeps every radius in absolute metres under avatar scaling. A world-aligned cube's vertical face would admit a standing player's whole sender column in one collision step, and one slot would latch them all as a single phantom reading while every other slot rejected them; the tilt is what staggers their arrivals. The rotation is the `TILT` constant in `generate.py`; `--check` holds it here and `check_prefab` holds it on an owned copy.

**A sweep offers every radius of the cage to exactly one open cube.** Sticky rejection blinds the rig at enable, at load and after a distance-hide: armed slots at full size would reject every hand already inside. So one slot's cube grows outward from the centre over `sweepSeconds` while the armed slots sit collapsed, holding no rejections, and each hand is admitted alone as the front reaches it. At each handoff the successor appears shut at the size the front had on the admitting frame and holds that size for the whole shut step, so no radius is ever offered by no cube and a hand resting anywhere in the cage is acquired. From the toggle the sweep is loud, a burst per hand. From a fresh animator and from a distance-hide resume it is silent: a hand found inside the sphere gets the marker and no burst. Silent ends with the sweep, or with exhaustion: once every slot holds and nothing can ride the front, a slot freed later resumes it loud, so a resident the frozen front never reached bursts when it is finally admitted. A distance-hide announces itself one frame early (`runtime.md` §Parameters); every slot parks and collapses its boxes on that frame (the dedup layer alone never parks, so its edge memory survives a resume), so whatever the receivers did during the pause is discarded and the hands present at resume are re-acquired from scratch. The Sweep layer is the sole writer of its parameters and writes all of them in every state (`runtime.md` §Animator evaluation says why). It also draws the boundary, which is why a radius change needs no prefab edit.

**Dedup catches the second admission of a hand a slot already holds.** The hold shell exists so a tracked hand can drift, but a hand that retreats into it and returns is a fresh overlap for whichever slot is open, and a fast entry that jitters across a face can be admitted two or three times. No per-slot bookkeeping can refuse that. So an always-live layer publishes the per-axis difference of every pair of slots' raw readings, raw rather than the signed readout because a blend weight cannot be negative. A slot that has just latched releases itself when that difference is inside `dedupEpsilon` on every axis against a slot already holding a hand. A slot that has settled, inside the sphere or in the re-arm band after it, wins outright whatever its index; between two fresh slots still in the hold shell the lower index wins, and the rungs are asymmetric so neither can release the other. The comparison runs only on the frames after an admission, never for the life of a track, so two real hands that drift close later are not collapsed.

## Traps

- **Two hands within one collision step of each other share a slot.** The readout is then their per-axis maximum in the tilted frame, a corner that takes the farther hand's coordinate on an axis where both are positive and the nearer hand's where both are negative. So it can sit outside the sphere while a hand is inside, which delays or suppresses the burst, or inside it when neither hand is: one burst at a phantom point. The second hand is invisible until it leaves the cube and re-enters. When the first leaves, the point walks out with it, crosses the re-arm band, and the payload drops and re-fires once as the point snaps to the remaining hand; the slot itself is not released.
- **A crowd that appears inside the open cube on one frame goes to one slot.** A teleport or respawn into a group, or several avatars loading beside you at once, begins every overlap on the same step: the open slot latches them all as one reading, and the other slots, which opened after those overlaps began, see none of them until each leaves the cube and re-enters. A sweep runs only at enable, at load and after a distance-hide, so nothing re-examines them.
- **The tilt still merges column members close in height**, a hand beside a hip for instance, and a column approaching along a slice vertex of the tilted cube meets two faces at once and merges the pair straddling the vertex height. Measured in av3emu on a synthetic four-sender column: every member on its own slot at most azimuths, the two lowest merged at the vertex azimuths, and the one-step admission window recovered those at high frame rate.
- **The burst trails the hand by about four frames of its travel**: two collision steps before a Proximity value exists, one parameter hop, one transition read. A slow poke bursts a few centimetres inside the sphere, a swipe tens of centimetres. Widen `burstRadius` if fast hands matter.
- **Exhaustion.** With every slot latched, a new hand is rejected by every slot until it leaves the cube and re-enters, and a slot that frees later does not re-examine it. Exhaustion during a sweep leaves the sweep flag up and ends the silent endpoint; the next recycled slot resumes the front from where it stopped and finishes loud, so a resident the front had not reached bursts when it is finally admitted, and a hand that stopped inside the frozen front is never re-examined.
- **Dedup misses three cases.** Two hands admitted in the same step (one slot, one reading). A duplicate admitted alongside a second hand in the same step (the new slot reads the pair's maximum, the old slot one hand). Two real hands that sit within `dedupEpsilon` on every axis while one of them is newly admitted, which releases a real track. The epsilon covers the one collision step by which the two slots' readings can be skewed on the admission frame, not readout noise, which is common to coincident receivers; too small and a skewed duplicate survives, too large and two real hands collapse onto one slot. Setting `holdHalf` equal to `acqHalf` removes the hold shell that creates duplicates, at the cost of the drift allowance. A consumer reading per slot also sees a one-frame identity pop when a fresh lower-index slot displaces a fresh higher-index one; the burst is unaffected.
- **The boundary can hide a hand that still holds the payload**: the drawn surface is the burst surface, and the re-arm band lies outside it.
- **The readout coefficients and the hold cube are one unit.** `holdHalf` and `senderRadius` are baked into the readout clips; resize the boxes only through CONFIG, never on the prefab.

Deliberately not shipped: a cylinder zone (it needs the tilt undone in the tree, and a much larger cube); an `allowSelf` self-test variant (it changes what the pattern senses); one `Emit` shared across slots (a possible material-count saving, untested); and preemption, since evicting a tracked hand for a newcomer would cost a victim ladder per slot and still miss the hand it evicted.

## What is not proven here

In-client only: the burst landing on the toucher's hand as the toucher and a third observer each see it; the real capsule hand's `senderRadius`; readout dither at range, which sizes the re-arm band (size it from a two-client observation, not the emulator); and the coincident-receiver cluster with two wearers together, where the receivers of both copies stack in one spot and an avatar also carrying an owned copy stacks both counts.

Dedup rests on two coincident congruent boxes reading one sender bit-identically in the client, whichever was admitted first and however far the wearer stands from the world origin; the emulator's readings are bit-constant, so only a two-client observation can hold that. What no client observation has covered is the cluster case above, where a second wearer's coincident receivers share the spot.

## Changing it

- **Regenerate the build as a unit.** Run `python generate.py`, then recompile `built/` as a unit over the committed `.meta`s (`CONVENTIONS.md` §The gate has the procedure). `python generate.py --mesh` regenerates `assets/UnitSphere.obj`.
- **Run the check every time you touch the prefab.** `python generate.py --check` asserts the hand-maintained surface no compile or gate reads: receiver fields and tags, the tilt and its inverse, the node scales and positions dedup rests on, the seam, the World pins, the boundary. Nothing runs it for you and "gates green" never includes it.
- **Changing K.** Set CONFIG's `K`. Duplicate or delete `Slot<k>` subtrees directly under `Cage/Size`, with receiver parameters `CR/Slot<k>/…`, the tilt on the slot and its inverse on `Output`. The geometry must be exact: a slot nudged a centimetre or scaled by a hair still tracks and still bursts, and quietly stops recognising the duplicate dedup exists to catch, which is why `--check` asserts every slot's position, scale and box placement. Regenerate the build; `--check` counts slots against K.
- **Turning on `fourBox`.** Add an `X−` beside each slot's `X+ Y+ Z+`: duplicate the `X+` node, turn it 180° about Y so its +Z face is the cage's −X face, and point its parameter at `CR/Slot<k>/X-`. Then regenerate, since the readout coefficients change. `--check` names each slot that lacks the box.
- **Another sender.** Set CONFIG's `tags` and every receiver's collision tags; `--check` compares them.
- **An owned copy** carries the tilt, the slot geometry and the box fields by hand, under the same exactness rule as a new slot, and regenerates its document through `document(overrides)` at its own CONFIG; a key CONFIG does not carry is refused at that door, so a knob this generator drops fails a copy loudly. `check_prefab` in `generate.py` is the door a copy calls to hold the rig.

## Verifying the install

Your own hands are excluded by design, so nothing fires when you test alone. Drive a scripted `HandR` sender (`emulator.md` §Fake another player's contact) or use two clients. Run `--check` first (§Changing it); it catches the geometry and receiver faults, and nothing else below.

Enable on, walk. `Cage` rides the Hips, world-aligned, at world scale 1 whatever the avatar's scale; finding it at the module's mount point means the BoneProxy never resolved. A `Marker` sits upright while its `Boxes` sit tilted; a tilted marker or upright boxes means the tilt and its inverse have come apart, the failure mode of a hand-copied rig. A menu toggle that does nothing means the enable came out of the build prefixed: `globalParams` must be exactly `[ContactRadar/Enable]`. Two instances on one avatar show as one toggle driving both. Switch Enable off and on with the sender inside: every `Boxes` collapses, then the lowest slot's cube grows from the centre and the sender takes its slot and bursts as the front reaches it. With two senders inside, at each handoff the incoming slot's shut cube must be the size the outgoing cube had on its last admitting frame; larger means the front-freeze or the previous-front parameter is broken. A burst that fires with nothing visible means the `Burst` to `Emit` sub-emitter link was dropped by a re-edit; it is a non-child reference Unity's inspector will not author, and nothing checks it.

Two behaviours only these recipes exercise. Dedup: pull the sender out past the acquisition face but not past the hold face, then push it back in. Exactly one slot still holds it; a second slot admits it and releases itself within a frame or two, with no second burst. The distance-hide path: set the local runtime's `IsAnimatorEnabled` false, disable its Animator a few frames later, move the senders, then re-enable both. Every `Boxes` reads collapsed from the frame after the flag, and the resume re-acquires the senders now present, silently.

## Rig

    ContactRadar                 root — VRCFury FullController + VRCFury Toggle, two components
    ├─ HomeAnchor                MA BoneProxy → Hips (AsChildAtRoot); a constraint source only, no clip path runs through it
    │  └─ Offset                 drag to move the zone's home
    ├─ Cage                      position ← HomeAnchor/Offset; rotation and scale ← assets/World.prefab
    │  └─ Size                   the one inspector knob: uniform scale, ships at 1; nothing animates it
    │     ├─ Slot1               carries the tilt; one FX layer per slot; identical siblings Slot2 …
    │     │  ├─ Boxes            the size lever the controller animates: acquisition, hold, collapsed
    │     │  │  ├─ X+ Y+ Z+      coincident face-proximity box receivers, one per cage face, on the animated allow flag
    │     │  │  ├─ Hit           coincident Constant box on the same flag: the latch's edge source, nothing else;
    │     │  │  │                its node scale must be one, since dedup rests on it reading what its siblings read
    │     │  │  └─ X−            fourBox only: the fourth box, its face the cage's −X face
    │     │  └─ Output           the readout: localPosition in metres, slot frame; carries the inverse tilt
    │     │     ├─ Emit          the visible burst, Burst's Birth sub-emitter; outside Payload, never disabled
    │     │     └─ Payload       the one node the controller toggles: inactive at rest, on while inside the sphere
    │     │        ├─ Burst      buffer particle, no renderer; born where Output sits on the enable frame;
    │     │        │             its GameObject is held off during a silent acquisition
    │     │        └─ Marker     placeholder cube: swap this
    │     └─ Boundary            inactive: your opt-in to draw the zone
    │        └─ Sphere           unit sphere (assets/UnitSphere.obj), single-sided, no UVs; scaled and enabled by the controller
