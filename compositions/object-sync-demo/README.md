# object-sync-demo — a world-synced prop with a live readout of its own wire (Composition)

A droppable rig that carries a prop at absolute world position and rotation for every client in the instance, with a hand-held tablet reading the sync out as it happens — the coarse and fine words, the batch index, and whether the pose this client is showing is trustworthy. Drop it on any humanoid avatar; it links to the hands by bone and touches nothing else. Widened to **52 synced bits** for a 3-batch, ~0.350 s full refresh, which is what makes the tablet's Index read as a counter rather than a blur.

## What it composes

| entry | built against | what it contributes |
|---|---|---|
| `object-sync` | `5a13330` | absolute world position + rotation over an animator channel |
| `word-channel` | `3657e95` | the wire underneath it (reached through `object-sync`) |
| `anti-cull` | `cecaecc` | keeps a view-culled wearer's decode running |
| `debug-shaders` | `2bd92bd` | the tablet and the world-coordinate cube |

**The stamp is those four commits.** A composition depends on N entries and rots when any of them changes shape, so the commits are what make "this stopped loading" bisectable rather than archaeological. Re-stamp when you rebuild against newer entries.

## Install

Drop `ObjectSyncDemo.prefab` under your avatar root. Nothing else — `HandR_Anchor` and `HandL_Anchor` are VRCFury `ArmatureLink`s targeting the humanoid **RightHand** and **LeftHand** bones, so they resolve on any humanoid rig without naming a bone or pointing at an object. The rig is world-pinned by construction, so at edit time the anchors line up with the hand bones only while the avatar sits at the origin; off-origin it visually detaches from the body. That is correct, not breakage.

## The arrangement, which is the point

    ObjectSyncDemo        VRCParentConstraint + VRCScaleConstraint -> World   [VF FullController = Demo_Fx]
    |- Display_Source     src0 = ObjectSync/Sync, src1 = ObjectSync/Rig/Prop/Display
    |- Prop_Damped        src0 = Display_Source, src1 = self
    |  `- Cube            the carried prop (+ DepthLight)   [VF Toggle = Wireframe]
    |- HandR_Anchor       [VF ArmatureLink -> RightHand]  `- HandOffset, RayOrigin/RayHit/RayLift
    |- HandL_Anchor       [VF ArmatureLink -> LeftHand]   `- Panel
    |- ObjectSync         the entry: Rig / Sync_Target / Sync
    `- AntiCull

This is `object-sync`'s `pin -> mux -> damper -> content` idiom (its README §Composing against Sync owns the law): `ObjectSyncDemo` is the world pin, `Display_Source` the multiplexer with `Sync` as one source, `Prop_Damped` the damper, `Cube` the content. The damper sits under a pinned parent because a damper whose parent moves is dragged by its parent's motion.

**The tuned numbers, and why they are what they are.** `Prop_Damped` runs `1 : 0` on the wearer and `0.05 : 1` on a remote — undamped locally so a grab has nothing to fight, damped remotely because that is the only side with a stepping reconstruction to smooth. Rotation is left undamped: position wants lag where rotation reads as sluggishness. `Panel` and `HandOffset` carry hand-placement offsets set by eye against a real head-height view; they are taste, they are why this composition exists as a prefab rather than a description, and there is no derivation to recover them from.

## Its own object-sync build

`object-sync/` beside this file is this composition's own build of the entry, at `numberSlots` 4 / `boolSlots` 18 against the shipped 147-bit word table — **52 wire bits, 3 batches, ~0.350 s**, against the entry's shipped 28-bit/6-batch default. `generate.py` drives `../../object-sync/generate.py` unmodified and deviates after, so the entry stays byte-identical; `CONVENTIONS.md` §compositions/ owns why the build lives here instead of as a fourth preset in the entry. Retune in `generate.py`, never in the emitted `controller.yaml`.

One post-generation deviation, applied in `demo_document()` which owns the reason: `Enable` defaults **true**, because a demo whose subject is off until you find the menu demonstrates nothing.

## Verifying it

`object-sync`'s own §Verifying the install is the procedure and this composition adds nothing to it, with one shortcut it makes available: the tablet is a readout of the same words the decode uses, so `_E2..E7` mirroring the coarse and fine words, `_E8` climbing as the batch index, and `_E9` tracking `ObjectSync/Sync_Valid` is a whole-wire check you can read off the avatar's own hand instead of from a param window.

Measured on this arrangement against a spawned remote clone: reconstruction converges **1.74 mm / 0.00°** with `Sync_Valid` true on the clone, and Freeze drifts 0.06 mm under a 2 m shove.

## Provenance

`object-sync` descends from VRLabs' **Custom-Object-Sync** (MIT, © VRLabs); the wire descends from **VRCFury**'s Parameter Compressor. The tablet and cube shaders are **Lereldarion**'s, with **d4rkpl4y3r**'s `unity_CameraInvProjection` patch for BIRP VR depth and the wireframe idea from **Neitri**; the glyph atlas rasterizes **Geist Mono** (SIL OFL 1.1). The three-tier arrangement was arrived at independently by a private doll rig and by this demo, which is what makes it an idiom rather than one author's habit.
