# absolute-grip-prop — a prop that lands in the same authored grip, in every hand, on every client (Module)

Grab the prop off the wearer and it snaps into your hand the way a real object would: the same grip every time, whichever hand takes it, and every client in the instance sees the same thing. Drop it and it stays where it was left, re-grabbable in place. Anyone can do this, the wearer included, and nobody installs anything. Position is the natively synced physbone grab with `snapToHand` on, so the tip is the client's own hand grab point; orientation is re-derived on every client from the grabber's built-in `Hand` palm sender plus a two-receiver `HandL`/`HandR` gate for which hand and a two-receiver `FingerIndex` cue for which way the palm axis points, then the prop rides an **authored** grip pose under that frame. Nothing is captured at grab time, so repeated pickups have nothing to accumulate. Module total: **1 synced bit** (`AbsoluteGrip/Enable`), 12 contact receivers, no FinalIK.

**Provenance:** the palm readout, the tilted cage, the position cell and most of the glue are `6dof-grab-prop`'s, reused wholesale (and through it `grab-prop`, `object-sync`, `box-tracker`); the hand gate on the tip, the snap-on grab and the per-hand grip pose are ThatFatKidsMom's Avatar-Prop (MIT), itself a derivative of VRLabs' Contact-Tracker. Avatar-Prop takes orientation from three finger trackers and a FinalIK solver and assumes a closed grip; this entry takes it from the palm capsule, pays one finger cue for the sign, and assumes no pose.

## Interface

- **Params:** `AbsoluteGrip/Enable` (bool, in) — synced, **unsaved**; the menu front (VRCFury Toggle on the prefab root). Off is the reset: toggling off and on recalls a dropped prop home. Everything under `Palm/` is internal to the module and takes the instance prefix; `globalParams` is the derived wildcard for the one published prefix, so an added internal name can never widen exposure.
- **Seam:** one VRCFury `FullController` on the prefab root playing two controllers, the glue first, then the readout; `basis: mount-root`, so clip paths bind relative to the prefab root and the internal hierarchy names are load-bearing. `HomeAnchor` is an MA `BoneProxy` on Hips, referenced only as a constraint source. Both controllers and both params assets regenerate from `generate.py` (the YAML) and `CompileController` (the built assets); the Toggle is a VRCFury component on the prefab root, hand-maintained.
- **Dependencies:** VRC SDK, VRCFury and Modular Avatar to build. **Compose `anti-cull` alongside** (its README §When a module needs this): the drop is replayed choreography and the orientation is contact tracking, both of which stop on a culled remote.
- **Required assets:** `assets/World.prefab`, the never-instantiated scale reference the cage pins to; do not instantiate or delete it. `Payload` is a placeholder sphere; swap it, keep it under `Container/Damped`.
- **The grip is yours to author.** `Frame/GripR` and `Frame/GripL` ship at identity: the prop's own +Z lies along the palm axis toward the thumb and its +Y points from the palm centre toward the tip, for a right hand. Rotate each node's local rotation to how the prop should sit in that hand; the two are authored independently, never one derived from the other, because the two hands' sensed frames are reflections, not rotations, of each other. `generate.py --check` pins both rotations to the generator's constants, so author them there and in the prefab together.

## What it demonstrates

An **absolute** grip from contacts: the prop's pose in the hand is a function of the grabber's current pose and an authored constant, with no dependence on what the prop was doing before the grab. `6dof-grab-prop` recovers the same frame but captures the prop's pose relative to it at each grab, and every client captures on its own readout at its own instant, so each pickup adds a per-client disagreement that nothing reconciles. Here the carry pose is `Frame · Grip`, so a drop-time disagreement is replaced at the next grab, never compounded. Three things make that possible and none is visible from the artifacts.

**The tip is the client's hand grab point, and that makes the roll lever structural.** With `snapToHand` on, the grab pins the bone endpoint to where the client puts a held object: seen in-game, well off the palm capsule's centre, about where a ball would rest in the hand, though its exact offset is unmeasured and every lever figure the entry was sized against is a constructed ball point on one base (the in-game checklist's first item reads the real one). So wherever the client puts that point off the palm axis, which is where it was seen, the tip sits a hand-sized lever off the axis on every grab and on every client, and the frame's up direction (palm midpoint toward the tip) is well conditioned. The shipped entry's world-up fallback had no job left and is gone; what replaced it is a refusal, and the refusal is also the only detector of a grab point that lands on the axis (§Limits). The readout publishes the squared distance from the tip to the palm midpoint, which with the tip's along-axis offset near zero on every surveyed base is the lever to within a few percent, and the settle branch refuses to engage below a floor rather than driving an aim constraint with a degenerate up. There is no partially-correct absolute grip, so there is no fallback.

**Handedness is a tag, never geometry.** The sensed features are a point and a directed line, and a point plus a vector has no chirality: the left-hand and right-hand configurations are related by a rotation no readout can separate. Only a tag can. Two proximity spheres on the tip carry `HandL` and `HandR`, and the glue reads their **difference**: the nearer palm reads higher at any distance, so the sign needs no absolute threshold and no scale (a foreign palm well outside the hand still reads a large fraction at this radius, so no threshold on one reading could be placed). What the glue still demands is a margin on the difference, which is a proximity floor: a palm has to be inside the sphere, and the sphere's radius is the headroom a remote's trailing palm gets. Two palms reading alike, or none, read as undecided, and undecided refuses; a palm decisively nearer the tip than the other is taken as the hand, and whether two palms both in the core then engage is the residual's call (§How it works). The bit is read once, at the engage, and latched as which carry state the machine is in: on a remote the grabber's palm trails the synced tip by the IK delay during motion, so a carry state that re-read the gate would drop the grip on every fast swing.

**The axis sign is one finger.** A point plus a symmetric capsule reads identically rotated 180° about the tip's perpendicular offset, so the palm readout yields the axis as a line and the eight-box machine holds an orientation only for continuity, not correctness. The index finger is on the thumb side of the palm whatever the curl (measured at rest across thirty hands, and through every shipped gesture on one base), and its along-axis coordinate is the one component a curl does not move. Two proximity spheres on the readout's two axis proxies, at the palm midpoint plus and minus the sensed axis, both tagged `FingerIndex`, and their **difference** is the sign: the geometry makes the sign of that differential exactly "which side of the midpoint plane the index's nearest point is on", independent of curl and of hand size, and a single receiver against a threshold cannot do it (a reading confounds side with distance). The readout writes the axis to both proxies, so the sign mux is two aim constraints under one rotation constraint and costs no arithmetic. The cue pair's filters are **never** shut: the pinky-side contact breaks during a curl on a third of the surveyed hands, and a latched contact that fully breaks cannot re-latch while filters are shut, which would leave a dead receiver reading an unconditionally correct sign.

## How it works

The glue controller is `grab-prop`'s cell, clip table replicated binding for binding, plus the latch, a confirm dwell and a receiver stow. `Acquire` is entered on the grab: the cage sits at its acquisition scale with filters open, and the palm arriving inside all eight boxes **and** a hand tag reading at the tip is what advances to `Latched`, which shuts the box and gate filters on frame 0 (what is inside is what stays latched) and expands the box hosts to working scale on frame 1. `Settling` holds the prop frozen for a fill sized in frames while the readout pipeline primes: the residual and half-length land a few frames after working scale, and the cue two stages later still, since the proxies must move and the contacts sample after the constraint solve. `Settled` then polls every frame for the residual to fall, the half-length to read palm-plausible, the lever proxy to clear its floor, and both differentials to be decisive, and branches into one of four `Confirm` states by hand and sign, or into `Reacquire` at the timeout.

`Reacquire` is a receiver stow, and it exists because a reopened filter does not re-acquire. Contact acquisition is an enter event: a latched palm that breaks out of a box while the filters are shut and comes back before they reopen is rejected on the way in, and once it sits inside there is no further entry for the reopened filter to admit, so the shipped entry's loop (timeout, reopen, poll) would hold that hand position-only for the rest of the grab. A slow receiver stow re-acquires a sender already in its volume (measured in-client), so every box loss between the latch and the carry, and the settle timeout, pass through `Reacquire`: all twelve receiver GameObjects off for the same dwell `Disabled` holds, then `Acquire` with the filters open. The carry states keep the shipped entry's direct loss path to `Acquire`, since a hand that leaves a working-scale box and returns inside the one frame the reopen takes is not a hand.

`Confirm` is the temporal guard, and it exists because the sign is irreversible for the hold. The held line runs a few degrees wrong for one to three frames at a fraction of a percent duty even inside a continuous hold, and the cue's own magnitude does not flag a wrong-line frame; deciding on one frame would latch a 180°-wrong grip until the next grab. So every engage condition is re-tested each frame for the dwell, any one failing returns to `Settled`, and the dwell's exit time is the decision. The four `Carry` states then ride the authored grip for the latched hand with `Frame` on the aim constraint for the latched sign; neither the gate nor the cue is read again until the next acquisition. A refusal is legible: the prop follows position and never turns.

That loop is the hand-identification mechanism, and it is a residual test with one identity added: a left plus a right palm reading alike at the tip are rejected by the gate outright, and any other pair, two same-handed palms or two at unequal distances, is rejected only as the shipped entry rejects them, by the residual and the half-length band. A union that reads like one plausible capsule from one hand still engages; the band is the guard, and narrowing it toward the surveyed hands rejects more unions at the cost of large hands.

Both states that toggle a receiver GameObject, `Disabled` and `Reacquire`, hold for a dwell that covers all twelve receivers, because a receiver switched off and on inside one frame with a sender inside is deaf for the session. A stowed receiver reads exactly zero; `Disabled`'s entry driver zeroes the twelve params as well so nothing stale gates the enable that follows.

The working boxes stay far larger than the palm, as shipped: on a remote the tip rides the synced grab point while the hand sender rides IK-smoothed bones about half a second behind. But the boxes are no longer the binding term. The gate and cue spheres are hand-sized, and it is those the engage reads; a remote grabber's palm swinging past their range during acquisition leaves the machine polling until the timeout reopens the latch. The cage tilt (cube diagonal to vertical) is load-bearing exactly as in `6dof-grab-prop`, and every clip in the glue layer writes the layer's whole binding set, `Frame` and `Rotor` weights included.

## Before you compose it

The acquisition trade `6dof-grab-prop` documents no longer exists. With `snapToHand` on, the tip goes to the hand grab point wherever the hand closed, so the bone length and the grab radius stop feeding the acquisition core: the core only has to reach from that point to the far side of the grabbing palm, a small per-avatar constant. The grab radius is therefore a free reach knob, and the acquisition scale covers the palm from the ball point; it ships at the shipped entry's value pending the in-game read of the real grab point's offset, and a tighter one rejects more bystanders.

Two consequences of allowing self senders on a hip-parked home: the wearer's own resting hand often sits inside the acquisition core, so another player's grab may engage only after the wearer's hand moves away; drag `HomeAnchor/Offset` out of the idle hand path if that bites. And the wearer's own grab gets the full orientation path, per hand.

Keep `Container`, `Container/SourcePosition`, `Container/Rotor` and `GrabPosition` out of any re-parented subtree: a VRCFury clip binding through an MA-moved node is dropped at build (`nondestructive.md`). The `Cage` subtree must stay in the physbone's `ignoreTransforms`, or the solver enrols the whole readout rig, gate and cue included, as chain bones.

## Limits, stated

- At release each client freezes the pose its own readout held at its own release frame, so clients disagree about the resting rotation by however far the grabber's wrist turned over the IK-delay window. That disagreement is per drop, does not accumulate, is erased by the next grab, and vanishes for a release from a still hand. No client can tell it is the grabber's (the prop's animator runs as the wearer's copy everywhere, and the grabber is in general a third player), so no dwell compensates.
- The roll channel depends on the client putting its grab point off the palm axis. That is client behaviour this entry neither controls nor measures; the lever floor is the only detector, and a grab point on the axis refuses rather than spins.
- The authored grip lands a few degrees differently in each grabber's hand: the palm capsule's axis is built from the avatar's rest pose and sits a dozen degrees off the anatomical width axis, differently per base. A constant per avatar, not drift.
- The sensed frame's chirality is the gate's: a missed or misread hand tag shows as a mirrored grip on that client alone.
- Two same-handed palms in the core are rejected by residual, not identified (§How it works).
- Two co-located wearers of this entry reach the receiver-cluster count that reads wrong values; the shipped entry needed three.
- On a remote during fast motion the binding terms are the gate and cue spheres, not the boxes: a broken engage drops to position-only and retries at the timeout cadence plus the stow dwell.
- A readout hop that reversed the held orientation mid-carry would leave a latched sign that is now wrong for the rest of the grab; measured at zero occurrences inside a continuous hold, and reasoned rather than measured in-client.
- Within roughly a kilometre of the world origin, the same float32 law as the shipped entry; a hand-edited hand collider breaking the SDK's automatic proportion gives that grabber a constant bias; the remote hand's readout noise is unmeasured.

## Empirical constants (90 % rule)

Every value lives in `generate.py`; the table names the knob and the relation.

| Constant | Knob | Relation |
|---|---|---|
| Box geometry, acquisition scale, sign margin, settle gate, square-root lookup, settle timeout, damping, grab radius, bone length | as `6dof-grab-prop` | unchanged, and its table owns them |
| Stow dwell | `DISABLED_DWELL` | seconds the receivers stay off in `Disabled` and `Reacquire`; must outlive one evaluation at the lowest frame rate, and every extra frame is re-acquisition delay after a broken latch |
| Gate radius | `GATE_R` | proximity radius of the two hand spheres on the tip; the read is the differential, so the radius is headroom for a remote's lagged palm, not a threshold |
| Gate margin | `GATE_M` | how decisive the hand differential must be; below it two palms or none refuse |
| Cue radius | `CUE_R` | proximity radius of the two index spheres at the axis proxies; the argmax of the worst-case differential over the measured hands, smaller goes blind on large hands and larger flattens the differential |
| Cue margin | `CUE_M` | how decisive the sign differential must be; sized against the readout's own axis error on the measured hands, never against the emulator, which reads it low |
| Lever floor | `MM_MIN` | squared tip-to-midpoint distance below which the settle branch refuses |
| Fill | `SETTLE_FILL` | time frozen after the latch, sized so that at the lowest frame rate you care about the fill plus the confirm dwell outlasts the readout pipeline, the cue's two extra stages included; a clip length is wall-clock, so a slower client fills fewer frames and the confirm dwell is what still stands between a half-primed pipeline and a carry |
| Confirm dwell | `CONFIRM_DWELL` | how long every engage condition must hold before hand and sign latch; must exceed the readout's transient wrong-line runs at the lowest frame rate you care about |
| Grip poses | `GRIP_R`, `GRIP_L` | the authored per-hand grip, mirrored in the prefab nodes of the same names |

## Verifying the install

Enable on: the prop rests at `HomeAnchor/Offset` on the wearer's hips; at the origin means the BoneProxy never resolved. Grab it with one hand and hold still: the prop snaps into the hand at the grab point, and within the confirm dwell it turns to the authored grip; a prop that follows position but never turns is a refusal, which is a second palm in the core, a hand outside the boxes, the index finger too far from the grip for the cue, a tip on the palm axis, or `Cage` missing from the physbone's ignore list. Roll the wrist: the prop rolls with it, always. Grab with the other hand: the other authored grip, not a mirror of the first. Drop and re-grab as `grab-prop`; repeated pickups land in the same grip.

`generate.py --check` asserts the prefab surface no compile reads: controller and params order in the FullController, the `globalParams` wildcard, each of the twelve receivers' name-to-parameter mapping, tags, shape, filters serialized open, locality, content type and size or radius, the gate and cue hosts, the cage tilt and its scale source, the exact sources and zero offsets of `Rotor` and `Frame`, the two aim constraints' targets and up mode, the grip nodes' rotations and absence of constraints, the absence of the shipped entry's capture and fallback nodes, and the physbone's snap, dynamics, grab filter, radius, bone length and ignore list. `twin.py` is the per-frame reference the compiled readout is scored against, not a build input; it evaluates the palm half of the readout only, since the recorded sweeps carry no finger.

The emulator cannot reproduce a snap-on grab (its grab helper applies the offset unrotated) or the client's finger capsule shape, and it has no contact noise. Two clients in-game, not the emulator: the real grab point's offset and the acquisition scale against it, the sign cue's margin against a real index at real curl and splay, the remote hand against the gate and cue spheres through the IK delay, the confirm dwell against contact noise, cross-client agreement of the grip over repeated pickups, and late join. The checklist below is that run.

## In-game checklist

Two clients: A grabs, B watches; the last item needs a third player. Each item says what passes; a refusal is a prop that follows position and never turns.

- [ ] **Snap-on grab point.** A grabs, once as the wearer and once as a visitor: the prop's origin sits in the hand where a held ball would rest, with no jump toward the palm surface on either client. Note how far off the palm axis the grab point sits; the acquisition scale and the lever floor were sized without that read.
- [ ] **Sign never 180° wrong.** A takes the prop at several wrist attitudes and holds still each time: on B's client the prop never presents rotated 180° about the palm axis, and any refusal engages within a couple of seconds of holding still. A wrong-sign carry, or a refusal that outlasts a still hand, fails.
- [ ] **Per-hand grip.** A grabs with the left, drops, grabs with the right: each hand lands its own authored grip, not a mirror of the other, as seen by A and by B.
- [ ] **Repeated pickup and drop.** Five or more cycles at varied attitudes: the held orientation A and B see agrees on every cycle with no disagreement growing cycle to cycle, and whatever resting disagreement a drop leaves is gone at the next grab.
- [ ] **Fast wrist before release.** A rotates fast and releases mid-motion: the frozen rest orientations on the two clients differ by no more than the wrist turned over the sync delay, and a still-hand drop afterwards leaves no disagreement at all.
- [ ] **Two-handed grab.** Both of A's hands on the tip: the prop refuses; releasing one hand engages within the settle timeout plus the stow dwell.
- [ ] **Roll at a real grip.** A rolls the wrist through a full turn: the prop rolls with it throughout, never spinning free or holding still.
- [ ] **Remote fast swing during acquisition.** A grabs and swings immediately: on B's client the prop is position-only through the swing and engages once the hand settles; a hold that stays position-only after the hand is still fails.
- [ ] **Cue margin against real fingers.** With finger tracking, A splays the index hard toward the middle finger while gripping: the prop engages or refuses, never engages with the wrong sign.
- [ ] **Wearer's idle hand.** The prop home on the hips with the wearer's hand resting beside it, and a visitor grabs: the grab engages once the wearer's hand moves away, and never engages the wearer's palm as the grip.
- [ ] **Late join.** B joins after A has dropped the prop in the world: B sees the prop hidden until A's next grab, then carried and dropped where A sees it.
- [ ] **Bystander's hand.** A third player's hand, index included, near the held or dropped prop: the sign, the hand and the pose never change on any client.

## Rig

The prefab is `6dof-grab-prop`'s with the capture and fallback removed and the gate, cue and grips added; edit it in place, `Locked` on every constraint, source weights swapped by the clips.

    AbsoluteGripProp                  root — VRCFury FullController [glue, readout] + Toggle
    ├─ Container                      grab-prop's position cell, untouched
    │  ├─ Rotor                       VRCRotationConstraint ← [HomeAnchor/Offset, GripR, GripL]; disabled = the rotation freeze
    │  ├─ Damped                      VRCRotationConstraint ← [self, Rotor]: the smoother; a sibling of Rotor, never its child
    │  │  └─ Payload
    │  └─ SourcePosition
    ├─ HomeAnchor / Offset            MA BoneProxy → Hips; the home attitude is the Offset transform, never a baked offset
    ├─ GrabPosition ← [Offset, Container]
    │  └─ GrabBone                    VRCPhysBone: snapToHand 1, ignoreTransforms [DropPosition, Cage]
    │     └─ GrabBone_End
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld: the readout frame is world-attitude
    │           ├─ DropPosition
    │           └─ Cage               VRCScaleConstraint → assets/World.prefab; nothing else on this node
    │              ├─ T1p T1m … T4p T4m   8 box receivers [Hand], local +Z = ±d_j; host scale animated acquisition ↔ working
    │              ├─ HandL, HandR    2 sphere receivers, one tag each: the gate, on the tip
    │              └─ Mid             localPosition = the sensed midpoint (readout Math layer)
    │                 ├─ ProxyA       localPosition = +axis (readout Select layer)
    │                 │  └─ CueP      sphere receiver [FingerIndex], zero local position
    │                 ├─ ProxyB       localPosition = −axis (the same clips, negated)
    │                 │  └─ CueN      sphere receiver [FingerIndex], zero local position
    │                 ├─ UpAim        VRCAimConstraint +Y → Cage, WorldUp None
    │                 │  ├─ Recon     VRCAimConstraint +Z → ProxyA, ObjectRotationUp against UpAim
    │                 │  └─ ReconN    VRCAimConstraint +Z → ProxyB, ObjectRotationUp against UpAim
    │                 └─ Frame        VRCRotationConstraint ← [Recon, ReconN], the sign mux
    │                    ├─ GripR     no constraint; the authored right-hand grip in its localRotation
    │                    └─ GripL     no constraint; the authored left-hand grip in its localRotation
    ├─ FreezeToWorld
    └─ EditorOnly

`Rotor` carries the rotation channel so `Container`'s constraint and `GrabPosition`'s sources stay exactly `grab-prop`'s measured graph. `ReconN` sits under `UpAim` beside `Recon` so both read the up helper in the same solve group. Every rotation constraint is zeroed, never activated, and the grip lives in the grip node's own local rotation and never in a source offset: with identity offsets the carry pose is exactly `Frame · Grip`, which is the whole claim.
