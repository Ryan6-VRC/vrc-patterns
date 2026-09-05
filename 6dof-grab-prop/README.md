# 6dof-grab-prop — a prop anyone grabs, turns in their hand, and sets down (Module)

Grab the prop off the wearer, and it turns with your hand like a real object: roll your wrist and it rolls, tilt it and it tilts. Drop it and it stays where it was left, re-grabbable in place. Anyone in the instance can do this, the wearer included, and nobody needs to install anything. Position is the natively synced physbone grab, as in `grab-prop`; orientation is recovered on every client from the grabber's own built-in `Hand` palm sender, read by eight box receivers parked on the physbone tip and solved in blend trees. Module total: **1 synced bit** (`SixDofGrabProp/Enable`), 8 contact receivers, no FinalIK, no finger tags.

**Provenance:** the remote-grabbable-prop idea and its cage-on-the-tip acquisition are ThatFatKidsMom's Avatar-Prop (MIT), itself a derivative of VRLabs' Contact-Tracker; this entry replaces its three finger and palm trackers plus a FinalIK aim solver with one palm-capsule readout and two VRC aim constraints. The grab cell is `grab-prop`'s, the aim pair `object-sync`'s, the receiver conventions `box-tracker`'s.

## Interface

- **Params:** `SixDofGrabProp/Enable` (bool, in) — synced, **unsaved**; the menu front (VRCFury Toggle on the prefab root). Off is the reset: toggling off and on recalls a dropped prop home. Everything under `Palm/` is internal to the module and takes the instance prefix.
- **Seam:** one VRCFury `FullController` on the prefab root playing two controllers, the glue first, then the readout; `basis: mount-root`, so clip paths bind relative to the prefab root and the internal hierarchy names are load-bearing. `HomeAnchor` is an MA `BoneProxy` on Hips, referenced only as a constraint source. Both controllers and both params assets regenerate from `generate.py` (the YAML) and `CompileController` (the built assets); the Toggle is a VRCFury component on the prefab root, hand-maintained.
- **Dependencies:** VRC SDK, VRCFury and Modular Avatar to build. **Compose `anti-cull` alongside** (its README §When a module needs this): the drop is replayed choreography and the orientation is contact tracking, both of which stop on a culled remote.
- **Required assets:** `assets/World.prefab`, the never-instantiated scale reference the cage pins to; do not instantiate or delete it. `Payload` is a placeholder sphere; swap it, keep it under `Container/Rotor`.

## What it demonstrates

Recovering a **rotation** from another player's body with contacts, at 6 degrees of freedom, on a budget of eight receivers and no assumed hand pose. The position half is solved elsewhere in this library; the orientation half is what this entry exists for, and three things about it are not visible from the artifacts.

**The readout is the palm capsule's axis, not a fingertip.** Every avatar carries a `Hand` sender: a capsule lying across the palm, rigid with the wrist, that no finger gesture moves. Eight face-proximity boxes in four opposed tetrahedral pairs read the capsule's extent along each direction; the extents solve the capsule's half-length, its midpoint and the unsigned projections of its axis. The signs are the hard part: a line has a four-way sign ambiguity that a static readout cannot break, so the readout holds one **oriented** sign pattern as animator state and hops only to a Hamming-neighbour pattern whose residual beats the held one by a margin. That is what makes the frame *stable* rather than merely correct: a prop that jumped 8–89° whenever a projection crossed zero would be useless in a hand. All of it is blend-tree arithmetic with no sqrt and no divide (the tetrahedral directions sum to zero, so a pattern's consistency residual is a plain signed sum, and the square root in the half-length solve is a 1D lookup).

**Roll comes from the physbone tip, and the tip is a per-grab constant.** With `snapToHand` off, the grab pins the bone's endpoint at a fixed offset from the hand point, so the tip is a rigid point in the grabbing hand. The recovered frame aims along the palm axis and takes its up direction toward the tip: a `VRCAimConstraint` pair, an up helper aiming at the tip and a child aiming along the axis with `ObjectRotationUp` against it (`object-sync` §Rig owns why `ObjectUp` silently fails here). Roll is therefore as good as the tip's lever arm off the palm axis. The readout computes that lever once per grab and, below a threshold, selects a second aim constraint with world-up instead; roll about the palm axis is then not sensed, and a vertical palm in that mode flips it.

**Capture is relative, by disable-hold.** The prop never snaps to the hand: on grab it holds the pose it had, a `Held` node under the recovered frame is driven onto the prop's rotation, and once the readout settles `Held`'s constraint is disabled, so it keeps its local pose under the frame and rides it. The prop's `Rotor` then follows `Held`. Release disables `Rotor`'s constraint, which freezes the rotation the same way `grab-prop` freezes position. Every client captures on its own readout, so the offset each client holds differs by however far the hand turned during that client's acquisition; the fixed dwell before capture keeps that to the IK delay.

## How it works

The glue controller is `grab-prop`'s cell, clip table replicated binding for binding, plus four states around the latch. `Acquire` is entered on the grab: the cage sits at its acquisition scale with filters open, and the palm arriving inside all eight boxes is what advances to `Latched`, which shuts the filters on frame 0 (what is inside is what stays latched) and expands the hosts to working scale on frame 1. `Settling` waits a fixed dwell for the residual to fall and the half-length to read palm-plausible, then exits to `Held6` or `Held5` by the lever gate, or back to `Acquire` on a timeout, reopening the filters. That loop is the hand-identification mechanism, and it is a residual test, not an identity test: a second palm latched with the grabbing one usually keeps the residual high, the loop reopens, a broken latched contact cannot re-latch, and the readout converges on the palm that stays with the tip. A two-handed grab loops indefinitely and the prop carries position-only. Each box reads its nearest sender, so two palms whose union happens to read like one plausible capsule pass the settle gate and the prop captures a blend of the two; the half-length band is the only guard, and narrowing it toward the surveyed hands rejects more such unions at the cost of large hands.

Nothing in a grab cycle toggles a receiver GameObject, which is why no receiver stow is needed (Avatar-Prop stows its trackers because it deactivates them during the grab). The one state that does, `Disabled`, holds for a dwell, because a receiver switched off and on inside one frame with a sender inside is deaf for the session.

The working boxes are far larger than the palm on purpose. On a remote client the tip rides the synced grab point while the grabber's hand sender rides IK-smoothed bones about half a second behind, so during motion the palm trails the tip by that much travel and must still lie inside every box's linear range. Past that range any reading hits zero, the machine returns to `Acquire`, and re-acquires when the hand catches up; each re-capture takes the prop's frozen pose as the new offset.

The cage is tilted, cube diagonal to vertical, and the tilt is load-bearing. A palm axis lying in one of the cage's coordinate planes has a mirror line about that plane's diagonal that reads identically on every box, a two-line ambiguity no residual can break; with a world-aligned cage, turning a palm-down hand about the vertical, or pronating with the forearm along a world axis, sits in that plane for the whole motion and the prop follows the wrong line for seconds. With every cage axis at the same elevation and 120° apart in azimuth, no horizontal or vertical motion stays in a cage plane; a crossing is transient and the hysteresis rides it out.

Every clip in the glue layer writes the layer's whole binding set. On a scene binding a state writes only what its own clip writes, so a delta clip would inherit the previous state's values.

## Before you compose it

The bone length and the grab radius are one trade with the acquisition volume, stated here because it cannot be read off the prefab. The latch fires while the cage is small, so that core must reach from the tip to the far side of the grabbing palm and as little further as possible. With `snapToHand` off, a hand that closes near the root of a long bone pulls the endpoint along at nearly the bone's length, so every centimetre of bone or grab radius is a centimetre of acquisition core, and a bigger core latches bystanders' hands. The shipped bone is short and the grab radius small, which keeps the core tight and leaves the roll lever to wherever the fist happens to close; a long crossguard bone buys a guaranteed lever and is the opposite corner of the same trade. Lengthen the bone only together with the acquisition scale in `generate.py`, and expect more strays latched.

Two consequences of allowing self senders on a hip-parked home: the wearer's own resting hand often sits inside the acquisition core, so another player's grab may capture only after the wearer's hand moves away; drag `HomeAnchor/Offset` out of the idle hand path if that bites. And the wearer's own grab gets the full orientation path.

Keep `Container`, `Container/SourcePosition`, `Container/Rotor` and `GrabPosition` out of any re-parented subtree: a VRCFury clip binding through an MA-moved node is dropped at build (`nondestructive.md`). The `Cage` subtree must stay in the physbone's `ignoreTransforms`, or the solver enrols the whole readout rig as chain bones.

## Limits, stated

- Within roughly a kilometre of the world origin. The readout rides the client's float32 world-position error, white at 0.045 mm per box near the origin and a wandering bias of centimetres at 10 km, where nothing here works. That is the client's law, not a knob.
- A hand-edited hand collider that breaks the SDK's automatic `r = 0.5 s` proportion gives that grabber a constant axis bias.
- The readout's remaining error is the naive nearest-surface capsule model's slow pose-dependent bias, under a degree median and a few degrees at the tail, which a prop riding the frame shows as slight drift across the wrist's range, not shake.
- Three co-located wearers of this entry reach the receiver-cluster count that reads wrong values.
- The remote hand's readout noise is unmeasured: the client floor was measured on the wearer's own hand.
- Two palms in the core are rejected by residual, not identified: a union that reads like one plausible capsule captures a blend (§How it works).
- Not ported from Avatar-Prop, deliberately: its distance-too-far reset (`grab-prop`'s unlimited carry plus Enable-off recall covers it) and its left-hand grip mirror (relative capture takes the pose from the grab itself).

## Empirical constants (90 % rule)

Every value lives in `generate.py`; the table names the knob and the relation.

| Constant | Knob | Relation |
|---|---|---|
| Box geometry | `F`, `D` | face plane and depth at working scale; larger tolerates more remote hand lag, and the extents, lookup and every leaf clip follow from it |
| Acquisition scale | `ACQ_SCALE` | host scale between grabs; sized so the shipped bone and grab radius put the whole palm inside all eight boxes, measured on the synthesized palm |
| Sign margin | `MARGIN` | keep-previous hysteresis in residual metres; below it noise flips the held pattern, above it the pattern lags through degenerate regions |
| Lever threshold | `LEVER_T` | tip-to-axis distance below which roll falls back to world-up; roll error scales as tip-to-midpoint distance over lever |
| Settle gate | `RES_SETTLE`, `S_LO`, `S_HI` | residual and half-length band a capture requires; wider captures sooner and on worse geometry, and admits more two-palm unions |
| Square-root lookup | `LUT_LO`, `LUT_HI`, `LUT_N` | must cover the discriminant over the whole half-length band, or S reads wrong while the gate still passes; the generator refuses a lookup that does not |
| Dwells | `CAPTURE_DWELL`, `SETTLE_TIMEOUT`, `DISABLED_DWELL` | seconds before a capture may fire; seconds before the latch loop reopens; seconds a receiver stays off |
| Grab radius, bone length | prefab `GrabBone` `radius`, `GrabBone_End` position | the acquisition trade above; `--check` pins them to `GRAB_RADIUS` and `BONE_END` in `generate.py` |

## Verifying the install

Enable on: the prop rests at `HomeAnchor/Offset` on the wearer's hips; at the origin means the BoneProxy never resolved. Grab it and hold still: the prop should not snap, and within the capture dwell it starts turning with the hand; a prop that follows position but never turns means the readout never settled, which is a second palm in the core, a hand outside it, or `Cage` missing from the physbone's ignore list. Roll the wrist: the prop rolls with it when the grip is off the palm axis and holds a world-up roll when it is on it. Drop and re-grab as `grab-prop`.

`generate.py --check` asserts the prefab surface no compile reads: controller and params order in the FullController, `globalParams`, each receiver's name-to-parameter mapping, tags, filters, locality, content type and size, the cage tilt and its scale source, the exact sources and zero offsets of `Rotor`, `Held` and `Frame`, and the physbone's `snapToHand`, grab filter, radius, bone length and ignore list. `twin.py` is the per-frame reference the compiled readout is scored against, not a build input: `python twin.py truth <sweep>` checks the midpoint and lever against a recorded sweep's true centre and axis, and `compare` scores a Unity edit-tick dump against the twin's.

Two clients in-game, not the emulator: the rigid grab offset (the emulator's grab helper applies it unrotated), remote-side re-derivation against a real IK-delayed hand, the per-client capture offset, the remote hand's readout noise, and late join.

## Rig

The prefab is `grab-prop`'s with three additions; edit it in place, `Locked` on every constraint, source weights swapped by the clips.

    SixDofGrabProp                    root — VRCFury FullController [glue, readout] + Toggle
    ├─ Container                      grab-prop's position cell, untouched
    │  ├─ Rotor                       VRCRotationConstraint ← [HomeAnchor/Offset, Held]; disabled = the rotation freeze
    │  │  └─ Payload
    │  └─ SourcePosition
    ├─ HomeAnchor / Offset            MA BoneProxy → Hips; the home attitude is the Offset transform, never a baked offset
    ├─ GrabPosition ← [Offset, Container]
    │  └─ GrabBone                    VRCPhysBone: snapToHand 0, ignoreTransforms [DropPosition, Cage]
    │     └─ GrabBone_End
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld: the readout frame is world-attitude
    │           ├─ DropPosition
    │           └─ Cage               VRCScaleConstraint → assets/World.prefab; nothing else on this node
    │              ├─ T1p T1m … T4p T4m   8 box receivers, local +Z = ±d_j; host scale animated acquisition ↔ working
    │              └─ Mid             localPosition = the sensed midpoint (readout Math layer)
    │                 ├─ ProxyA       localPosition = the signed axis vector (readout Select layer)
    │                 ├─ UpAim        VRCAimConstraint +Y → Cage, WorldUp None
    │                 │  └─ Recon     VRCAimConstraint +Z → ProxyA, ObjectRotationUp against UpAim
    │                 ├─ ReconW       VRCAimConstraint +Z → ProxyA, world-up
    │                 └─ Frame        VRCRotationConstraint ← [Recon, ReconW], the roll mode
    │                    └─ Held      VRCRotationConstraint ← Rotor; disabled = the capture
    ├─ FreezeToWorld
    └─ EditorOnly

`Rotor` carries the rotation channel so `Container`'s constraint and `GrabPosition`'s sources stay exactly `grab-prop`'s measured graph. The freeze bit is alone on `FreezeRotation` and the scale pin alone on `Cage`; the collapse is animated on the eight hosts, uniformly, because tetrahedrally rotated boxes under non-uniform scale shear. Both rotation constraints are zeroed, never activated: the capture is correct only with identity offsets on `Rotor` and `Held`.
