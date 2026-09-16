# contact-radar — per-sender contact slots with an exact burst origin (Module)

A particle burst wherever another player's right hand enters a sphere around you: several hands at once, each burst on its own hand, no retrigger for a hand dithering at the edge, and everything sensed per client so the burst lands on the hand as each observer sees it. Nothing here syncs but the enable — every copy of the avatar runs its own sensing, which is the only way the burst can sit on the hand where that observer's client draws it. **One synced bit; 3K receivers per copy.**

Two modes, one generator flag, one rig. **Dwell** (the root prefab) holds a hand from cube entry to cube exit and re-bursts each time it comes back inside the burst radius after retreating past the re-arm radius — poke, pull back, poke again — with the payload on the whole time the hand is inside the sphere, so a mesh in it rides the hand. **Entry** (`entry-mode/`) releases the slot a few frames after the burst (the burst state's own dwell, set by its Direct tree's data-dependent length), so a hand has to leave the acquisition cube and come back for another; a hand that stays in fires once. Pick dwell for a reactive bubble, entry for a doorbell. Ships at a 1 m sphere with 0.10 m of hysteresis in both modes; `Cage/Size` rescales the whole thing in the inspector (§Knobs).

**Provenance:** `box-tracker`'s face-proximity readout (VRLabs Contact-Tracker ancestry) with the fourth box removed and the sender radius supplied by config; the buffer-particle form is hfcRed/VRLabs Particle-Bufferer (MIT); the per-sender slot protocol — arm shut, open one at a time, hand off in the same evaluation, re-arm by scale collapse — is this entry's own, resting on the emulator measurements in §How it works.

## Ground truth

- **Seam:** VRCFury `FullController` on the prefab root, FX, `basis: mount-root`; the hierarchy names are the clip paths, so a rename under `Cage` silently unbinds a slot. `HomeAnchor` is an MA `BoneProxy` to Hips, referenced only as a constraint source — no clip path runs through it. `globalParams` is exactly `[ContactRadar/Enable]`; every internal name sits under `CR/` and instance-prefixes at build. Depends on the VRC SDK, VRCFury and Modular Avatar.
- **The menu front is one VRCFury `Toggle` on `ContactRadar/Enable`, synced, unsaved, default on.** Off stows the receivers and zeroes their floats on every client; on re-arms every slot shut, so a hand already inside when you switch on is invisible until it leaves the cube and re-enters. **One instance per avatar** — the bare Toggle exports an unprefixed name, and two instances would collide on it.
- **Receivers are `localOnly: 0` and `allowSelf: 0` by necessity.** Remote copies must sense so the burst reproduces on every client; your own hand is excluded so a wearer's own gestures never fire it. Tag `HandR` is the config's; retag for another sender.
- **`Cage` is pinned to world rotation and world scale** by two constraints sourcing `assets/World.prefab`, a never-instantiated asset that resolves as world origin on every client, and rides the Hips by position only. World rotation keeps the cube's corners from sweeping a parked hand out and back in when you turn; world scale keeps every radius in absolute metres under avatar scaling. Do not instantiate or delete `World.prefab`, and never Activate either pin — their offsets must stay zero.
- **No anti-cull needed.** A client that has culled you cannot see the burst either, and every slot re-derives from current values on resume.

## Knobs

One knob is a transform; the rest live in `generate.py`'s CONFIG and the prefab — regenerate, recompile `built/` as a unit, and the README stays as it is.

| Knob | Direction |
|---|---|
| `Cage/Size` (transform scale, on your instance) | the whole sensor at once — cubes, readout, sphere, both bands — since every radius is metres in this node's frame, and it ships at uniform 1. Hold it uniform, between 0.5 and 2.0: the one term that does not scale is the sender-radius bias, so the burst origin lands `senderRadius × (scale − 1)` off the hand per axis, inward when smaller and outward when larger (emulator-measured at 0.5 and 2.0: 2.5 cm and 5 cm per axis, inside the 2 s puff's own spread). Past that range, or for an exact origin at any other size, retune CONFIG and regenerate instead |
| `K` | slots = simultaneous hands before a newcomer is missed until it re-enters the cube; each slot is one FX layer and three receivers on every copy, and the receiver cluster bug (`docs/runtime.md` §Contacts) is reached when two wearers stand together at high K. Other K: duplicate a `Slot<k>` subtree under `Cage` (receiver parameters `CR/Slot<k>/…`), set CONFIG, regenerate |
| `burstRadius`, `rearmRadius` | the sphere and the dwell band; the band must exceed the client's temporal noise on the readout at the world's working distance (`docs/runtime.md` §Contacts) or a parked hand dithers a burst. The band is the only re-arm dwell mode has; entry mode's is the cube face below |
| `acqHalf`, `holdHalf` | the acquisition cube a hand must enter and the larger hold cube it tracks in. The acquisition face sits `acqHalf − burstRadius − senderRadius` outside the sphere on axis, and that gap is two things at once: the head start the four-frame pipeline gets before a fast hand is inside the sphere (it only decides how far inside a swipe bursts), and in entry mode the re-arm surface — a hand must retract that far past the sphere to burst again, so it is entry's hysteresis. Both ship small, because `acqHalf` is also what admits a hand that was never going to poke you: a bigger acquisition cube fills K faster. `holdHalf − acqHalf` is the admission hysteresis, the drift a held hand gets before it releases |
| `senderRadius` | the constant bias of the hand sender's nearest surface toward each face; measure it on a real capsule hand in-client and retune here, or re-derive it per sender from a fourth `X−` box exactly as `box-tracker` does (the escape hatch this entry deliberately leaves out) |
| `stepSeconds` | every dwell that must span collision steps; never below two steps |
| `lookupSegments` | the x² table resolution; the chord error is one-sided and inward, so a coarse table shrinks the effective burst radius slightly |

## How it works

Receivers aggregate senders, strongest wins, so per-sender behaviour exists only through the latch: the allow flags are checked when an overlap begins and never again. Three facts measured in av3emu carry the whole protocol. **Rejection is sticky** — a sender whose overlap began while `allowOthers` was shut is absent from that receiver's collision set for as long as the overlap lasts, whatever the flag does later, on Proximity, Constant and OnEnter alike. **A scale collapse and restore is a fresh episode** for every sender present, with no deaf failure: too short for a step is a silent no-op, never a false zero (a GameObject bounce that short comes back deaf). **A same-evaluation flag handoff between two receivers partitions senders exactly**, and a sender acquired in the one step before the flip is double-admitted.

Each slot is one layer (`generate.py`'s docstring walks the states). What is not derivable from the document: the ring rule opens the next Armed slot in the same evaluation the Open slot latches, so the two land in one collision step and the admission windows tile; when nothing is Open, the lowest Armed slot opens itself on its clip's exit-time crossing, quantized so the flags it reads are fresh; a hand read by only some of a slot's three coincident boxes (it happens on the frame the slot opens) parks the slot in Partial for a step and then Recycles it, because an Open slot that stalls blocks every admission on the avatar. The burst is arithmetic, not a receiver: the tree sums `x = 2h·X+ − h − r` per axis into the AAPs and `Output`'s localPosition, three 1D lookups add x², y², z² into r², and the transition compares r² against the two radii — which is what makes the zone a sphere and the hysteresis per-sender.

The burst states toggle one node, `Payload`, on while the hand is inside the sphere, and it serves two consumers at once because they read it differently: `Burst` inside it is a renderer-less buffer particle born at `Output` on the frame the wrapper enables (the edge — one puff per entry, however long the hand stays), and a mesh inside it is visible for as long as the wrapper is on (the level — the dwell demo's `Marker` rides the hand until it retreats past the re-arm radius). `Emit`, the visible burst, is `Burst`'s Birth sub-emitter and sits outside the wrapper, directly under `Output`, never disabled — disabling it is what truncates a burst in flight — and its sub-emitter reference is a non-child link Unity's inspector will not author; if a re-edit drops it, the buffer fires and nothing visible emits.

## Traps

- **The co-latch window.** A Proximity reading costs two collision steps, so a second hand whose overlap began within about two steps of the first is admitted by the same slot and rejected by the next for its whole overlap. The readout is then a per-axis *maximum* over the two hands — a corner that is never nearer the centre than either hand on same-sign approaches (it delays or suppresses a burst) and can sit inside the sphere when neither hand does only when the hands approach on opposite signs of different axes: one burst at a phantom point, and the second hand invisible until it exits the cube and re-enters. Two right hands crossing the cube face within about 1/30 s. The unbuilt refinement is one shared OnEnter receiver over the cube, flag always open, whose pulse triggers the Open slot a step earlier.
- **The burst trails the hand by about four frames of travel.** The readout lands one frame behind the hand and the r² predicate three more (two collision steps for a Proximity value, one AAP hop, one transition read), so the burst fires inside the sphere by the hand's speed times four frames — a few centimetres for a slow poke, tens of centimetres for a swipe — and `Output` on the burst frame sits one frame of travel behind the hand. Widen `burstRadius` if fast hands matter.
- **A hand that stays inside holds its slot** (dwell): a friend standing with a hand in your cube occupies one of K until they move it out of the hold cube. Entry mode releases at the burst instead.
- **Exhaustion.** The Open slot fires with no Armed slot left: nothing opens, and a hand entering meanwhile is rejected by every slot until it leaves the cube and re-enters. In dwell mode that is K hands inside the cube; in entry mode it is K hands loitering in the shell between the sphere and the cube face. No preemption ships: evicting a tracked hand to serve a newcomer would cost a victim ladder per slot and still miss the hand it evicted.
- **Every step-spanning dwell is authored in seconds, never frames**, and every slot state writes every flag and the payload toggle, zeros included — a state that wrote only its own 1 would leave `Open` stuck and the ring rule firing forever. The generator enforces both; a hand edit of `controller.yaml` is how they break.
- **The readout coefficients and the hold cube are one unit.** `holdHalf` and `senderRadius` are baked into the readout clips; resize the boxes only through CONFIG.
- **3K coincident receivers on every copy.** Two wearers side by side approach the ~24-receiver cluster bug as K grows; K is the knob and off stows them.
- **Nothing here is faithful in-client until measured there:** the emulator's readings are bit-constant, the client's dither with distance from the world origin, and the client refreshes receivers in only a fraction of frames. The dwell band and the entry-mode cube margin are the remedies; size them from a two-client observation, not from the emulator.

Deliberately not shipped: the shared OnEnter refinement above, an `allowSelf` self-test variant (it changes what the pattern senses), one `Emit` shared across slots (a possible material-count optimization, untested), and preemption.

## Entry mode

`entry-mode/ContactRadarEntry.prefab` is a prefab **variant** of `ContactRadar.prefab` at its own CONFIG's lower K. It customises exactly three things, each stated here because a removal is unvalidated (`docs/nondestructive.md`): the inherited root `FullController` is removed and re-added pointing at `entry-mode/built/`; the slots above its K are removed as variant overrides; and each kept slot's `Marker` is removed, because here `Payload` is on only for the burst state's few frames and a mesh inside it would flash (keep one if a flash on poke is what you want). `generate.py --check` names every removal. Every other node is inherited, so a retune of the shared rig reaches it without a diff. Its `built/` carries its own GUIDs.

## Verifying the install

Enable on, walk: `Cage` rides the Hips, world-aligned, at world scale 1 whatever the avatar's scale — finding it at the avatar root means the BoneProxy never resolved. Put a scripted `HandR` sender (`docs/emulator.md` §Fake another player's contact) straight in along one cage axis: the first slot's three floats leave zero together, its flag shuts and its boxes expand on one frame while the next slot's flag opens on the same frame, `Output` sits on the sender, and `Payload` enables as the sender crosses the burst radius with `Emit` emitting. Pull the sender past the re-arm radius and back: a second burst (dwell) or none until it leaves the cube (entry). In dwell the `Marker` cube rides the sender while it is inside the sphere and vanishes as it retreats past the re-arm radius; the slot itself is held until the sender leaves the hold cube. Scale `Cage/Size` on the instance and every distance above scales with it. A second sender arriving while the first is inside gets its own slot and its own burst; a hand already inside when the module enables gets none until it re-enters.

What stays in-client only: the burst landing on the toucher's hand as the toucher and a third observer each see it, the real capsule hand's `senderRadius`, threshold dither at range, and the cluster bug with two wearers together.

## Rig

    ContactRadar                 root — VRCFury FullController + Toggle
    ├─ HomeAnchor                MA BoneProxy → Hips (AsChildAtRoot)
    │  └─ Offset                 drag to move the cage's home
    ├─ Cage                      VRCPositionConstraint ← HomeAnchor/Offset; VRCRotationConstraint and
    │                            VRCScaleConstraint ← assets/World.prefab (world rotation, world scale 1)
    │  └─ Size                   the consumer's size knob: uniform scale, ships at 1 (§Knobs); nothing animates it
    │     ├─ Slot1               identity; one FX layer per slot
    │     │  ├─ Boxes            the cube lever and the collapse lever — localScale is 2·acqHalf at rest, animated
    │     │  │  ├─ X+  Y+  Z+    coincident box receivers, face proximity, tags [HandR], allowSelf 0,
    │     │  │                   allowOthers animated, localOnly 0, each rotated so its +Z face is the cage's +X/+Y/+Z face
    │     │  └─ Output           the readout node: the tree writes its localPosition in metres, Size frame
    │     │     ├─ Emit          the visible burst, Burst's Birth sub-emitter, never disabled — swap its look here
    │     │     └─ Payload       the one node the controller toggles: inactive at rest, on while the hand is inside the sphere
    │     │        ├─ Burst      buffer particle, renderer deleted, active — born where Output sits on the frame Payload enables
    │     │        └─ Marker     placeholder cube, built-in default material — swap this; removed in the entry variant
    │     ├─ Slot2 …             identical subtrees
