# object-sync-demo — a world-synced prop with a live readout of its own wire (Composition)

A droppable rig that carries a prop at absolute world position and rotation for every client in the instance: hold it in your hand, **point at a surface and place it there**, or freeze it where it stands. A hand-held tablet reads the sync out as it happens — the coarse and fine words, the batch index, and whether this client's receiver has a whole word table yet. Drop it on any humanoid avatar; it links to the hands by bone and touches nothing else. Widened to **50 synced bits** for a 3-batch, ~0.350 s full refresh, which is what makes the tablet's Index read as a counter rather than a blur.

Worth reading as a worked example of three things beyond world sync: a **hand-mounted `VRCRaycast`** with a surface-aligned result driving placement, a **`debug-shaders` numeric readout** driven live from animator clips, and a constraint **placement multiplexer** with a miss-tolerant hold state.

## What it composes

| entry | what it contributes |
|---|---|
| `object-sync` | absolute world position + rotation over an animator channel |
| `word-channel` | the wire underneath it (reached through `object-sync`) |
| `anti-cull` | keeps a view-culled wearer's decode running |
| `debug-shaders` | the hand tablet's numeric readout and the world-coordinate cube |

Its own contribution, belonging to no entry: the raycast placement mode, the three-mode placement multiplexer, and the clips that drive the tablet.

## Install

Drop `ObjectSyncDemo.prefab` under your avatar root. Nothing else — `HandR_Anchor` and `HandL_Anchor` are VRCFury `ArmatureLink`s targeting the humanoid **RightHand** and **LeftHand** bones, so they resolve on any humanoid rig without naming a bone or pointing at an object. The *link* resolves anywhere; the three hand-placement offsets under **The tuned numbers** are calibrated to one base and do not, which makes them the first thing to re-set when the prop lands wrong in the hand. It builds correctly from any scene position and at any avatar scale, and the rig rides the body while you author rather than snapping to the origin: the root's two pinning constraints ship **disabled** and a VRCFury `ApplyDuringUpload` re-enables them during the build, so the hand seams capture the poses authored on the avatar instead of the origin-parked ones an edit-time constraint solve would yank them to. All three of those — both constraints and the clip — are **inherited from `object-sync`'s entry prefab**, which this prefab is a variant of; they are not authored here and not yours to tune.

**Do not enable those two constraints** to make the editor view look world-pinned. An enabled pin at edit time is what makes a keep-offsets seam bake the wrong offsets, and a re-baked pin is the failure the swap exists to prevent — `../../../docs/gimmicks.md` §Constraint patterns owns the rule and the trap it replaces.

## The arrangement, which is the point

    ObjectSyncDemo         a PREFAB VARIANT of ../../object-sync/ObjectSync.prefab
                           inherited: the entry's World pin (two constraints, disabled in the editor,
                             re-enabled at upload by ApplyDuringUpload → PinEnable.anim) and its own
                             nodes Rig / Sync_Target / Sync
                           removed:  the entry's FullController and menu Toggle, and Sync_Target's Drop
                             toggle — this composition drives placement itself
                           added:    the demo's own 50-bit object-sync build, and a FullController for
                             everything below
    |- Rig Sync_Target Sync  the entry's, inherited
    |- Display_Source      src0 = Sync, src1 = Rig/Prop/Display
    |- Prop_Damped         src0 = Display_Source, src1 = self
    |  `- Cube             the carried prop (+ DepthLight)   [VF Toggle = Wireframe]
    |- HandR_Anchor        [VF ArmatureLink -> RightHand]
    |  |- HandOffset       where the prop sits in the Hand mode
    |  `- RayOrigin        VRCRaycast: +Z, 10 m, result oriented to the hit normal
    |     `- RayHit        the raycast's resultTransform
    |        `- RayLift    half the cube's 0.15 m extent up the normal, so it rests ON the surface
    |- HandL_Anchor        [VF ArmatureLink -> LeftHand]   `- Panel   the debug-shaders tablet
    `- AntiCull

This is `object-sync`'s `pin -> mux -> damper -> content` idiom (its README §Composing against Sync owns the law), with the pin supplied by the entry rather than built here: the variant root **is** the entry's pinned root, `Display_Source` is the multiplexer with `Sync` as one source, `Prop_Damped` the damper, `Cube` the content. Read it by role: `Rig` is the measurement tree, riding the root's pin; the `Display_Source → Prop_Damped → Cube` chain is the content the measurement drives. There is one pinned frame now, not a composition pin above an entry pin — the entry carries it, and every consumer gets it.

**`PinEnable.anim` is the entry's asset, not this composition's** — `../../object-sync/assets/PinEnable.anim`, inherited with the pin, and `../../object-sync/README.md` §Required assets is where its content is specified. It is reached here through inheritance and is not yours to edit; a curve dropped or retargeted there leaves every check green and surfaces only as a mislinked hand on someone else's avatar.

**The tuned numbers, and why they are what they are.** `Prop_Damped` runs `1 : 0` on the wearer and `0.05 : 1` on a remote — undamped locally so a grab has nothing to fight, damped remotely because that is the only side with a stepping reconstruction to smooth. Rotation is left undamped: position wants lag where rotation reads as sluggishness. `Panel`, `HandOffset` and `RayOrigin`'s rotation carry hand-placement offsets set by eye against a real head-height view, on **one** humanoid base; they are taste, they are why this composition exists as a prefab rather than a description, and there is no derivation to recover them from. That base is the calibration rather than a neutral default, so on a rig whose hand differs in size or bone orientation the prop reads as buried in the palm or floating off it and the ray aims somewhere the hand is not — re-set all three by eye, and do not read a bad landing as a seam bug. Anchor-to-bone distance is what tells those apart: the seam is doing its job whenever that distance equals the authored offset, however wrong the placement looks on screen.

## Placement modes, and the raycast

`Placement/Mode` selects what drives `Sync_Target`: **1 = Hand** (rides `HandOffset`), **2 = Raycast** (rides `RayLift`), **3 = Freeze** (parks and raises `FreezeToWorld`). 0 is the unstamped value and parks as Hand — a menu Toggle writes 0 on release, so the ladder self-heals rather than going dark.

**The raycast is worth lifting on its own.** `RayOrigin` carries a `VRCRaycast` firing +Z from the right hand over 10 m with `applyTransformScale`, and its `resultTransform` is `RayHit` with `applyRotation` on and `alignmentAxis` Y — so the hit transform arrives already **oriented to the surface normal**, and pointing at a wall or a ceiling places the prop flat against it rather than upright. `RayLift` then offsets half the prop's extent along that normal so it rests on the surface instead of half-buried. A raycast that only gave you a point would need all of that rebuilt in constraints.

**`Raycast` and `RayHold` are two states, and the miss gate took three tries.** Aim at open sky and `behaviorOnMiss: DoNothing` stops updating the result and drops `Ray_Hit` false, which is what `RayHold` transitions on. That alone is not a hold: the result transform is a child of the hand-mounted origin, so a frozen *local* result still rides the wearer around the world. Nor is a self-source at weight 1 — measured, a constraint damps its sources but does not resist its own parent, and the cube walked the full 1.5 m with the avatar. `FreezeToWorld` is what makes the hold true in world space (measured 0.000004 m over a 2 m walk). Re-acquiring drops it to 0 and raw tracking resumes.

Tracking is deliberately **raw** — no smoothing on the aim. Aliasing under a fast sweep is this rig's subject rather than its defect, and an exponential smoother changes the approach curve, never the sample rate, so it could not suppress it anyway.

**The trap, which costs an hour and has no symptom.** Keep `Placement/Ray_Hit` **off** `globalParams`. VRCFury decides on the suffixed animator param but rewrites the `VRCRaycast` component's **base** parameter, so exposing `Placement/Ray_Hit` leaves the component writing `VF117_Placement/Ray_Hit` while the controller reads the bare one — the miss gate goes dead with no warning and no error, and everything looks wired. Scoping the prefab's list to `ObjectSync/*` rather than widening it to `*` is what keeps this pair prefixed together; `../../../docs/gimmicks.md` §Packaging and interface owns the asymmetry and the sensing components it does *not* apply to.

`selective-animation` is the other raycast in this repo and the deeper reference on the component itself — per-observer targeting, layer masking, and why a miss reports differently per `MissBehavior`. It aims at *players*; this one aims at *world surfaces*, so the two do not share a trap list.

## The tablet, as a debug-shaders example

`Panel` is a `debug-shaders` numeric display driven entirely from animator clips: each row's value is a material property (`_E2_Value` … `_E9_Value`) written by a Direct blend tree, so the readout is live with no script and no update loop. `_E0`/`_E1` are the label-only header; `_E2..E7` show the full-resolution decoded cell index (0–4095, 2 m steps) and fine index (0–4095, ~0.78 mm steps) per axis — the assembled AAPs, not the truncated word bytes — `_E8` is the batch index, `_E9` is `OSCh/Acquired` — *this client's receiver has applied a complete word table*. (gate on `OS/Ready`). Read `_E9` on a **remote clone**: it is a receiver reading, so the wearer's own tablet sits at 0 there all session, correctly. Coarse ticks over in cell-sized steps and fine tracks continuously within the cell, so the two-stage measurement system is visible at a glance. It costs zero synced bits — every value it shows is already local.

## Its own object-sync build

`object-sync/` beside this file is this composition's own build of the entry, at `numberSlots` 4 / `boolSlots` 16 against the shipped 144-bit word table — **50 wire bits, 3 batches, ~0.350 s**, against the entry's shipped 28-bit/6-batch default. `generate.py` drives `../../object-sync/generate.py` unmodified at its own CONFIG, so the entry stays byte-identical; `CONVENTIONS.md` §compositions/ owns why the build lives here instead of as a fourth preset in the entry. The variant reaches it by **removing** the entry's inherited `FullController` — a VRCFury component takes no prefab-instance override, so remove-and-add is the only way to redirect one (`../../../docs/nondestructive.md`) — and this build then rides ONE root `FullController` together with `Demo_Fx`: the sealed-interface coupling (`../../object-sync/README.md` §Seam), which is also what lets the tablet read the sealed `OS/D/*` decode, `OS/Ready` and `OSCh/Acquired` at all. Retune in `generate.py`, never in the emitted `controller.yaml`.

One departure, `enableDefault: 1` in `demo_config()`: `Enable` defaults **true**, because a demo whose subject is off until you find the menu demonstrates nothing.

## Verifying it

`object-sync`'s own §Verifying the install is the procedure and this composition adds nothing to it, with one shortcut it makes available: the tablet reads the full-resolution decoded values the entry computes, so `_E2..E7` showing the assembled cell index and fine index per axis, `_E8` climbing as the batch index, and `_E9` reading `OSCh/Acquired` **on a clone** is a whole-wire check you can read off the hand instead of from a param window.

Measured on this arrangement against a spawned remote clone, with the clone's reconstruction engaged and its decode certified: reconstruction converges **1.74 mm / 0.00°**, and Freeze drifts 0.06 mm under a 2 m shove.

The hand seams capture independently of where the avatar sits and how it is scaled: built anchor-to-bone error is **≤ 1 µm** at the origin, at (3, 0, −2), and at avatar root scale 1.7 — against **3.61 m** and **0.72 m** for the latter two with the pins left enabled at edit time. Scale is the case position alone cannot expose, and the one the shipped reference never exercised.

## Provenance

`object-sync` descends from VRLabs' **Custom-Object-Sync** (MIT, © VRLabs); the wire descends from **VRCFury**'s Parameter Compressor. The tablet and cube shaders are **Lereldarion**'s, with **d4rkpl4y3r**'s `unity_CameraInvProjection` patch for BIRP VR depth and the wireframe idea from **Neitri**; the glyph atlas rasterizes **Geist Mono** (SIL OFL 1.1). The three-tier arrangement was arrived at independently by a private doll rig and by this demo, which is what makes it an idiom rather than one author's habit.
