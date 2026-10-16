# two-hand-prop (Module)

A prop with two grab handles that you steer on purpose: one hand carries it with its rotation held still, and two hands turn it to lie along the line between them. The first handle grabbed keeps the prop on that hand and the second only turns it, so a second player can steer without pulling it out of your hand. Two prefabs: `TwoHandProp_Yaw` turns only about the vertical, `TwoHandProp_Full` tilts as well. Costs 2 synced bits.

## How it works

- Each handle is an invisible grab physbone. Grabs on a physbone are synced by VRChat itself, so every client sees them live at no parameter cost. The prop follows the hands through VRC constraints.
- The handle grabbed first is the **primary**. The prop sits on the primary hand, at that handle's place on the prop. The other handle, the **secondary**, only turns it.
- One hand: the prop follows the hand and does not turn.
- Both hands: the prop turns to lie along the line between the hands, keeping its up direction pointing up.
- When the primary lets go, the secondary becomes the primary. The hands are rarely exactly a handle-spacing apart, so the prop has to slide along its length onto the new hand. It eases there over a short timed wait (the **dwell**), then snaps the last of the way. This is the **handoff**.
- Let go of both and the prop stays where it is in the world. Grab either handle and it picks up in place.
- Your own client records which handle is primary in a synced bit, `TwoHandProp/PrimaryB`, and every other client follows it.
- Besides that bit and the on/off switch, `TwoHandProp/Enable`, nothing is synced. As in `grab-prop`, this library's one-handle prop, each client works out where a dropped prop rests from the grabs it saw, and a player who joins late sees the prop only once someone grabs it.

## Install guide

Needs the VRC SDK, VRCFury and Modular Avatar.

1. Pick a prefab. `TwoHandProp_Yaw.prefab` suits anything carried level: a bench, a stretcher, a banner pole carried flat. `TwoHandProp_Full.prefab` also tilts toward the line of your hands, for a staff, a rifle, a pointer. Neither can tell which way to face when your hands are straight above each other (§Traps).
2. Drop one instance anywhere under the avatar root. Edit the instance or an owned copy, never the package asset. `HomeAnchor` attaches itself to the Hips at build; drag its `Offset` child to place where the prop rests when not in use.
3. Swap the placeholder meshes under `Body/Display` for your own: `Payload` (the bar) and the two `Grip` spheres. Keep them under `Display`, the node that hides and shows the prop. The grips are only visual. Where the hands actually grab is the handle spacing, a multi-node edit (§Knobs) if your mesh is longer or shorter.
4. Add this library's `anti-cull` module to the avatar too; it keeps your animator running for every viewer. A dropped prop stays put only because each client replays the grabs it saw, and a viewer whose client pauses your animator while you are off-screen misses them (`anti-cull` README §Traps, "When a module needs this").
5. Enter play mode or upload. The expression menu gains a `TwoHandProp` toggle, off by default. §Verifying the install tells a working install from a broken one.

## How to use

- `TwoHandProp/Enable` is the one parameter you drive: synced, not saved. On shows the prop at its home; off hides it, and on again brings it home from wherever it was dropped.
- Grab one handle to carry. Grab the other to turn. Let go of the primary and the prop slides onto the other hand; let go of the secondary and you are back to carrying with one hand. Let go of both to leave it.
- A second player can take the free handle and steer while you carry. The prop stays on your hand and passes to them only when you let go.

## Additional notes

- **One instance per avatar.** The menu control is a bare VRCFury `Toggle`, which exports `TwoHandProp/Enable` without a per-instance prefix; two instances would share it.
- **Do not rename anything inside the prefab.** The animations address nodes by path; a rename silently stops a state from moving them.
- **In the editor the prop sits where it was authored, not at its home.** Both constraints on `Body`, the prop's node, ship switched off and the animator switches them on, so in play the prop moves to `HomeAnchor/Offset`. Move the home by dragging `Offset`, never `Body`.
- **Keep `HolderA` and `HolderB` directly under the prefab root.** The handle physbones' parameter names get their per-instance prefix only while they sit under the root's VRCFury FullController at build. A Modular Avatar component that moves a holder elsewhere leaves the grabs unread, and the prop never follows a hand (`nondestructive.md`, rule 1).

## Performance stats

```c++
PhysBone Components:  2
PhysBone Transforms:  4
Constraints:          9        (depth 6)
FX Animator Layers:   2        (the controller's one, and one the VRCFury Toggle adds)
Mesh Renderers:       3        (placeholders: Payload and the two Grip spheres; 3 of Excellent's 4)
Material Slots:       3        (placeholders, Unity's built-in default; 3 of Excellent's 4)
Synced parameters:    2 bits   (TwoHandProp/Enable, TwoHandProp/PrimaryB)
```

## Knobs

Each row gives the direction and the relation; the value lives in `controller.yaml` or on the prefab node named. Node names are in §Rig.

| Knob | What it does |
|---|---|
| Handoff weight (`handoffToA`/`handoffToB` clips: the new primary's source weight on `Body`'s position constraint, against `Body`'s own) | How fast the handoff slide closes, per frame. Higher snaps sooner; lower glides longer. A per-frame fraction, so the glide is shorter in seconds at a high frame rate (`spring-damping` README §Framerate dependence). Keep the two clips equal |
| Handoff dwell (the same clips' length) | How long the slide eases before the snap. Shorter leaves a larger snap at the end, and a low frame rate fits fewer easing frames into it |
| Remote settle dwell (`timer` clip's length) | As `grab-prop`: how long a remote copy waits for synced values to arrive before acting on them. Retune in-game only |
| Handle spacing (prefab node positions) | Where the two handles sit on the prop. Copy sites: `Body/RestA`, `Body/Display/GripA`, `Body/CarryA`, `Body/CarryA/OffA` (the negation of `CarryA`), `HolderA` (`Body`'s position plus `RestA`), each mirrored for B; `Body/AimNode` (at A's position, no mirror); `Payload`'s length; and the `PositionAtRest` of every constraint on those nodes. Wider spacing lengthens the handoff slide. Edit your copy of `TwoHandProp_Yaw`; `TwoHandProp_Full` is its variant and inherits the change |
| Home rest (`HomeAnchor/Offset`) | Where the prop rests on the avatar when not in use |

The handoff weight, the handoff dwell and the handle spacing are feel constants: the emulator shows what they do, and only a headset shows whether they feel right.

**Provenance:** the grab cell, the drop, the world-frozen frame, the late-join park and the boot dwell are `grab-prop`'s (VRLabs World-Constraint ancestry). The self-source damper on the handoff is `spring-damping`'s (VRLabs Damping-Constraints, MIT). The yaw and full prefab pair follows `drag-bone`. The two-handle arbitration is this entry's own.

## Design notes

`controller.yaml`'s header lists every constraint cell and its sources; its state comments carry each state's reason. This section states what the rig guarantees and why.

**A held handle's chain root is frozen.** Moving a held chain's root moves its grabbed tip by about a frame of root travel (`runtime.md` §PhysBones). The prop follows the tips, so that term feeds back: on a prototype of this rig in the emulator it rang through one hand and never settled through two. So each held handle's holder is frozen while it is held, as `grab-prop` freezes its chain's root while grabbed. The holder sits above the chain root, not on it: on the same prototype, a constraint on the root's own transform lost to the physbone solver, and the nodes reading the tip kept reading where it started.

**One hand freezes rotation rather than aiming.** With one hand on, the free tip rides the prop a frame behind it, so an aim at it chases the prop's own lag and turns the prop a little with every hand movement. The freeze is memoryless and costs nothing.

**The prop reads the hands one frame late, on purpose.** On the frame a handle is released, its tip springs back to its frozen holder before the animator has seen the release. Anything reading that tip on that frame reads the old grab spot. `CarryA`, `CarryB` and `AimNode` are children of `Body`, so `Body`'s constraints solve first and read them as the previous frame left them (`runtime.md` §Constraints, the target-hierarchy bullet). By the next frame the animator's new state already holds the prop. The cost is one frame of lag on the carry, as in `grab-prop`.

**The yaw prefab is a mask, not a separate aim.** `AimNode` aims along the hands with its up axis kept up, so the yaw prefab's Y-only mask on `Body`'s rotation constraint takes the heading to within a fraction of a degree below vertical (`runtime.md` §Constraints, the rotation-axis-mask bullet).

**The primary bit makes the two-hand states a function of synced values.** A remote whose own grab order disagrees with the wearer's, because two grabs landed within one sync tick or its animator was rebuilt mid-hold, routes to the wearer's primary once the bit arrives (`runtime.md` §Parameters and network sync, on culling). A release always outranks the bit, so a late bit can never anchor the prop to a hand that has let go.

## Traps

- **Never move `CarryA`, `CarryB` or `AimNode` out from under `Body`.** The one-frame-late read above depends on it. Moved out, a release frame reads the snapped tip: a drop springs back to where the grab began and a released secondary swings the heading.
- **Never add a source to any of the rig's constraints**, even at weight 0. An added source can reorder the release frame with every animation unchanged (`grab-prop` README §How it works). Repoint an existing source instead.
- **Heading is each client's own history.** Two hands set it and a recall home resets it. A remote copy whose animator was paused through a two-hand turn, or a late joiner who first sees a one-hand grab, shows the prop at a different heading until the next two-hand grab. A drop every client agrees on, late joiners included, is a composition with `object-sync`, the way `compositions/grab-sync` does it for `grab-prop`.
- **Hands stacked vertically leave the heading undefined**, in both prefabs. Near vertical it follows tiny sideways offsets; the yaw prefab removes pitch, not this.
- **A remote is expected to snap to the other hand once in a grab race.** If the second grab lands within a sync tick of the first, a remote that saw them the other way round anchors to the wrong hand until the bit arrives, then snaps across, with no handoff easing.
- **The handoff slide is as long as the hands are wider or narrower than the handles.** Two players holding far apart move it a long way; that is the price of never hanging the prop between them.
- **A secondary far away still steers.** Rotation follows the line to the secondary hand however far it is, so a second player at arm's length or beyond swings the prop around your hand.
- **Do not enable or Activate the `FreezeToWorld` node in the editor.** It ships inactive and VRCFury turns it on at build.

## What is not proven here

Everything below needs the shipping client:

- remote players taking the handles, and the two-player carry and steer;
- the primary-bit race between two near-simultaneous grabs, and the remote snap it allows;
- how the heading reads on a remote while two IK-delayed hands steer it;
- a late joiner's park and first grab, and a remote paused through a two-hand turn;
- the vertical-hands heading, which no run has driven;
- a mirror clone, which replays your parameters into its own animator without running its drivers, and has not been watched routing;
- the feel of the handoff weight and dwell, and of the handle spacing, in a headset.

## Changing it

- **After any edit to `controller.yaml`, regenerate `built/` as a unit** over the committed `.meta`s (`CONVENTIONS.md` §The gate has the procedure), then run `tools/gate.ps1`.
- **Edit prefab structure on `TwoHandProp_Yaw` (or your owned copy of it).** `TwoHandProp_Full` overrides only the X and Z axes of `Body`'s rotation constraint and inherits everything else.

## Verifying the install

Enable on: the prop rests at `HomeAnchor/Offset` on the hips. At the avatar root's origin instead, the BoneProxy never resolved. Drifting with the avatar instead of holding still in the world, `FreezeToWorld`'s `ApplyDuringUpload` did not fire. A menu toggle that does nothing means the enable came out of the build prefixed: `globalParams` must be exactly `[TwoHandProp/Enable]`.

Grab a handle and watch its `_IsGrabbed` parameter. It must rise; if it does not, the handle's physbone has left the FullController's reach (§Additional notes). If it rises and the prop stays put, a node was renamed or a clip's path no longer resolves.

Swing the second handle, then release it: the heading must hold exactly. A heading that jumps on release, or a drop that springs back to where the grab began, means the release frame is being read live: one of `CarryA`, `CarryB`, `AimNode` has left `Body`, or a source was added to a constraint (§Traps).

In the emulator, release timing is only trustworthy driven from `Update()` (`emulator.md` §Induce a physbone grab/pose).

## Rig

The prefab is the shipped artifact and ships no builder; edit it in place. Every constraint is `Locked`; the clips switch the source weights and `IsActive` of `Body`'s and the holders' constraints. `controller.yaml`'s header lists `Body`'s sources in slot order.

    TwoHandProp_Yaw                  root — VRCFury FullController + Toggle
    ├─ Body                          the prop: a position and a rotation constraint (Y only on the yaw prefab)
    │  ├─ Display                    hidden and shown by the clips — your meshes go here
    │  │  ├─ Payload                 placeholder bar: swap this
    │  │  ├─ GripA, GripB            placeholder handle spheres, visual only
    │  ├─ RestA, RestB               where each holder sits, one chain length below its grip
    │  ├─ CarryA                     position ← HandleA_End; under Body on purpose (§Traps)
    │  │  └─ OffA                    where Body sits when A is primary
    │  ├─ CarryB  └─ OffB            the same for B
    │  └─ AimNode                    position ← HandleA_End; aims +X at HandleB_End, up kept up; under Body on purpose
    ├─ HolderA                       parent ← Body/RestA; frozen while A is held
    │  └─ HandleA_Root               VRCPhysBone (parameter HandleA); hidden while the module is off
    │     └─ HandleA_End             the grabbed tip
    ├─ HolderB  └─ …                 the same for B
    ├─ HomeAnchor                    MA BoneProxy → Hips (AsChildAtRoot)
    │  └─ Offset                     the home rest
    └─ FreezeToWorld                 inactive in the editor; its constraint freezes the root in the world,
                                     switched on at build by a VRCFury ApplyDuringUpload

**Physbones (`HandleA_Root`, `HandleB_Root`)** are `grab-prop`'s grab bone with stiffness removed: a grab moves the tip and nothing else does, and a free chain rides its holder rigidly.
