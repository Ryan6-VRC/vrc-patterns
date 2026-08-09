# object-sync-demo — a world-synced prop with a live readout of its own wire (Composition)

A droppable rig that carries a prop at absolute world position and rotation for every client in the instance: hold it in your hand, **point at a surface and place it there**, or freeze it where it stands. A hand-held tablet reads the sync out as it happens — the coarse and fine words, the batch index, and whether the pose this client is showing is trustworthy. Drop it on any humanoid avatar; it links to the hands by bone and touches nothing else. Widened to **52 synced bits** for a 3-batch, ~0.350 s full refresh, which is what makes the tablet's Index read as a counter rather than a blur.

Worth reading as a worked example of three things beyond world sync: a **hand-mounted `VRCRaycast`** with a surface-aligned result driving placement, a **`debug-shaders` numeric readout** driven live from animator clips, and a constraint **placement multiplexer** with a miss-tolerant hold state.

## What it composes

| entry | built against | what it contributes |
|---|---|---|
| `object-sync` | `5a13330` | absolute world position + rotation over an animator channel |
| `word-channel` | `3657e95` | the wire underneath it (reached through `object-sync`) |
| `anti-cull` | `cecaecc` | keeps a view-culled wearer's decode running |
| `debug-shaders` | `2bd92bd` | the hand tablet's numeric readout and the world-coordinate cube |

Its own contribution, belonging to no entry: the raycast placement mode, the three-mode placement multiplexer, and the clips that drive the tablet.

**The stamp is those four commits.** A composition depends on N entries and rots when any of them changes shape, so the commits are what make "this stopped loading" bisectable rather than archaeological. Re-stamp when you rebuild against newer entries.

## Install

Drop `ObjectSyncDemo.prefab` under your avatar root. Nothing else — `HandR_Anchor` and `HandL_Anchor` are VRCFury `ArmatureLink`s targeting the humanoid **RightHand** and **LeftHand** bones, so they resolve on any humanoid rig without naming a bone or pointing at an object. The rig is world-pinned by construction, so at edit time the anchors line up with the hand bones only while the avatar sits at the origin; off-origin it visually detaches from the body. That is correct, not breakage.

## The arrangement, which is the point

    ObjectSyncDemo         VRCParentConstraint + VRCScaleConstraint -> World   [VF FullController = Demo_Fx]
    |- Display_Source      src0 = ObjectSync/Sync, src1 = ObjectSync/Rig/Prop/Display
    |- Prop_Damped         src0 = Display_Source, src1 = self
    |  `- Cube             the carried prop (+ DepthLight)   [VF Toggle = Wireframe]
    |- HandR_Anchor        [VF ArmatureLink -> RightHand]
    |  |- HandOffset       where the prop sits in the Hand mode
    |  `- RayOrigin        VRCRaycast: +Z, 10 m, result oriented to the hit normal
    |     `- RayHit        the raycast's resultTransform
    |        `- RayLift    half the cube's 0.15 m extent up the normal, so it rests ON the surface
    |- HandL_Anchor        [VF ArmatureLink -> LeftHand]   `- Panel   the debug-shaders tablet
    |- ObjectSync          the entry: Rig / Sync_Target / Sync
    `- AntiCull

This is `object-sync`'s `pin -> mux -> damper -> content` idiom (its README §Composing against Sync owns the law): `ObjectSyncDemo` is the world pin, `Display_Source` the multiplexer with `Sync` as one source, `Prop_Damped` the damper, `Cube` the content. The damper sits under a pinned parent because a damper whose parent moves is dragged by its parent's motion.

**The tuned numbers, and why they are what they are.** `Prop_Damped` runs `1 : 0` on the wearer and `0.05 : 1` on a remote — undamped locally so a grab has nothing to fight, damped remotely because that is the only side with a stepping reconstruction to smooth. Rotation is left undamped: position wants lag where rotation reads as sluggishness. `Panel` and `HandOffset` carry hand-placement offsets set by eye against a real head-height view; they are taste, they are why this composition exists as a prefab rather than a description, and there is no derivation to recover them from.

## Placement modes, and the raycast

`Placement/Mode` selects what drives `Sync_Target`: **1 = Hand** (rides `HandOffset`), **2 = Raycast** (rides `RayLift`), **3 = Freeze** (parks and raises `FreezeToWorld`). 0 is the unstamped value and parks as Hand — a menu Toggle writes 0 on release, so the ladder self-heals rather than going dark.

**The raycast is worth lifting on its own.** `RayOrigin` carries a `VRCRaycast` firing +Z from the right hand over 10 m with `applyTransformScale`, and its `resultTransform` is `RayHit` with `applyRotation` on and `alignmentAxis` Y — so the hit transform arrives already **oriented to the surface normal**, and pointing at a wall or a ceiling places the prop flat against it rather than upright. `RayLift` then offsets half the prop's extent along that normal so it rests on the surface instead of half-buried. A raycast that only gave you a point would need all of that rebuilt in constraints.

**`Raycast` and `RayHold` are two states, and the miss gate took three tries.** Aim at open sky and `behaviorOnMiss: DoNothing` stops updating the result and drops `Ray_Hit` false, which is what `RayHold` transitions on. That alone is not a hold: the result transform is a child of the hand-mounted origin, so a frozen *local* result still rides the wearer around the world. Nor is a self-source at weight 1 — measured, a constraint damps its sources but does not resist its own parent, and the cube walked the full 1.5 m with the avatar. `FreezeToWorld` is what makes the hold true in world space (measured 0.000004 m over a 2 m walk). Re-acquiring drops it to 0 and raw tracking resumes.

Tracking is deliberately **raw** — no smoothing on the aim. Aliasing under a fast sweep is this rig's subject rather than its defect, and an exponential smoother changes the approach curve, never the sample rate, so it could not suppress it anyway.

**The trap, which costs an hour and has no symptom.** Keep `Placement/Ray_Hit` **off** `globalParams`. VRCFury rewrites the `VRCRaycast` component's own output parameter to a prefixed name (`VF117_Placement/Ray_Hit`) while a globally-exposed controller keeps reading the bare one — the miss gate goes dead with no warning and no error, and everything looks wired.

`selective-animation` is the other raycast in this repo and the deeper reference on the component itself — per-observer targeting, layer masking, and why a miss reports differently per `MissBehavior`. It aims at *players*; this one aims at *world surfaces*, so the two do not share a trap list.

## The tablet, as a debug-shaders example

`Panel` is a `debug-shaders` numeric display driven entirely from animator clips: each row's value is a material property (`_E2_Value` … `_E9_Value`) written by a Direct blend tree, so the readout is live with no script and no update loop. `_E0`/`_E1` are the label-only header; `_E2..E7` show the full-resolution decoded cell index (0–8191, 2 m steps) and fine index (0–4095, ~1.07 mm steps) per axis — the assembled AAPs, not the truncated word bytes — `_E8` is the batch index, `_E9` is `ObjectSync/Ch/Acquired` — *this client's receiver has applied a complete word table*. Read `_E9` on a **remote clone**: it is a receiver reading, so the wearer's own tablet sits at 0 there all session, correctly. Coarse ticks over in cell-sized steps and fine tracks continuously within the cell, so the two-stage measurement system is visible at a glance. It costs zero synced bits — every value it shows is already local.

## Its own object-sync build

`object-sync/` beside this file is this composition's own build of the entry, at `numberSlots` 4 / `boolSlots` 18 against the shipped 147-bit word table — **52 wire bits, 3 batches, ~0.350 s**, against the entry's shipped 28-bit/6-batch default. `generate.py` drives `../../object-sync/generate.py` unmodified and deviates after, so the entry stays byte-identical; `CONVENTIONS.md` §compositions/ owns why the build lives here instead of as a fourth preset in the entry. Retune in `generate.py`, never in the emitted `controller.yaml`.

One post-generation deviation, applied in `demo_document()` which owns the reason: `Enable` defaults **true**, because a demo whose subject is off until you find the menu demonstrates nothing.

## Verifying it

`object-sync`'s own §Verifying the install is the procedure and this composition adds nothing to it, with one shortcut it makes available: the tablet reads the full-resolution decoded values the entry computes, so `_E2..E7` showing the assembled cell index and fine index per axis, `_E8` climbing as the batch index, and `_E9` reading `ObjectSync/Ch/Acquired` **on a clone** is a whole-wire check you can read off the hand instead of from a param window. `_E9` on the wearer's own tablet is 0 whatever the wire is doing, so the shortcut is a clone-side one.

Measured on this arrangement against a spawned remote clone, with the clone's reconstruction engaged and its decode certified: reconstruction converges **1.74 mm / 0.00°**, and Freeze drifts 0.06 mm under a 2 m shove.

## Provenance

`object-sync` descends from VRLabs' **Custom-Object-Sync** (MIT, © VRLabs); the wire descends from **VRCFury**'s Parameter Compressor. The tablet and cube shaders are **Lereldarion**'s, with **d4rkpl4y3r**'s `unity_CameraInvProjection` patch for BIRP VR depth and the wireframe idea from **Neitri**; the glyph atlas rasterizes **Geist Mono** (SIL OFL 1.1). The three-tier arrangement was arrived at independently by a private doll rig and by this demo, which is what makes it an idiom rather than one author's habit.
