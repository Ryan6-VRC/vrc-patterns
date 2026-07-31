# grab-prop — sample-and-hold world-drop (Module)

Grab a prop off your avatar, carry it live, drop it anywhere in the world, re-grab it in place. The drop costs **zero synced params**: every client replays the same release choreography off the natively-synced physbone grab, freezing the prop where it was dropped. Module total: **1 synced bit** (`GrabProp/Enable`).

**Provenance:** generalized from a private production avatar's grab-prop (VRLabs World-Constraint ancestry).

## Interface

- **Params:**
  - `GrabProp/Enable` (bool, in) — synced, **unsaved**. The menu front (VRCFury Toggle on the prefab root). Off-is-reset: toggling off/on recalls a dropped prop to the home anchor.
  - `GrabBone_IsGrabbed` (bool, sensing) — minted by the grab physbone (`parameter: GrabBone`), never synced/saved/menu-exposed; the native grab sync regenerates it per client.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0`), so every clip binding resolves **prop-root relative** (`basis: mount-root`). The FullController merges `built/GrabProp_Fx_Parameters.asset`; `GrabProp/Enable` is exported via `globalParams` and the Toggle drives it.
- **Dependencies:** none beyond the VRC SDK + VRCFury to build; **compose `anti-cull` alongside** (its README §When a module needs this) — a dropped prop holds state through replayed choreography while the wearer may be off-screen. Drop the prefab anywhere under the avatar.
- **Required assets:** none — `Payload` is a placeholder sphere on Unity's built-in default material; swap it for your prop mesh, keep it under `Container`.

## Before you compose it

**`HomeAnchor` rides the wearer** — an MA BoneProxy with the recall target as its `Offset` child (**Rig** has the shipped offset), while the module root stays world-frozen so drops hold their world spot. Delete the BoneProxy for a fixed world-spot home instead. Keep the module's animated cells (`Container`/`SourcePosition`/`GrabPosition`) out of any re-parented subtree — a VRCF clip binding through an MA-moved node silently vanishes at build (`nondestructive.md` has the measured build order).

## How it works

Release freezes the prop via constraint-disable — the `Container` constraint turns off, holding its last transform — plus a re-sample of the settled tip, so a re-grab, which re-enables the constraint, picks up at the drop point instead of teleporting.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Knob |
|---|---|---|
| Released pulse phases | the `released` clip's phase keys — freeze at t=0, then the re-sample key, then hold to the clip end | the sample must land after the physbone tip has settled but before a re-grab is plausible; the clip length is the pulse |
| Remote settle dwell | the `timer` clip's length | retune in-game against real network settle time — the emulator can't validate it |

**Copy site — `drop-on-player`** clones this grab/release rig and carries its own copy of these rows and the `Rig` section, so a retune here lands half the homes. That entry's constants table marks which rows it takes from here.

**Late join:** a dropped prop carries no synced position, so a late joiner parks in `Waiting` with the prop hidden until it witnesses a grab — the grab physbone lives outside the hidden branch, so a grab always re-establishes it. The wearer's own view never hides (IsLocal skips the park).

**Cross-client fidelity:** the world-frozen frame is locked per-client at load-in (`runtime.md` §Constraints) — clients agree on the drop point only because they replay the same clips off the synced grab, not because the frame itself is shared. Expect per-client drift on the order of the IK-delayed hand; exact placement needs a real position sync on top, out of scope here.

## Verifying the install

Enable on: the prop rests at `HomeAnchor/Offset` on the wearer's hips. Finding it at the avatar-root origin means the BoneProxy never resolved; finding the module frame drifting with the avatar instead of holding its world spot means `FreezeToWorld`'s `ApplyDuringUpload` did not fire. Grab and release it — the prop must freeze where dropped and a re-grab must pick up in place rather than teleporting, which is the sample cell landing.

Two clients in-game, not the emulator: the remote settle dwell, and how far the per-client drift above actually opens up under real network conditions.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. `Locked` on every constraint, source weights swapped by the clips.

    GrabProp                          root — VRCFury FullController + Toggle
    ├─ Container      (0, 0.8, 0.25)  VRCPositionConstraint follows SourcePosition; holds Payload
    │  └─ Payload                     sphere, built-in default material — swap for your mesh, keep under Container
    ├─ SourcePosition (0, 0.8, 0.25)  VRCPositionConstraint follows DropPosition (sample-and-hold cell)
    ├─ HomeAnchor                     MA BoneProxy → Hips (AsChildAtRoot)
    │  └─ Offset      (0, 0.1, 0.35)  the recall target — drag to taste (see above)
    ├─ GrabPosition   (0, 0.8, 0.25)  VRCPositionConstraint, sources [source0 HomeAnchor/Offset, source1 Container]
    │  └─ GrabBone                    VRCPhysBone (parameter GrabBone → mints GrabBone_IsGrabbed)
    │     └─ GrabBone_End (0, .02, 0)
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation frame
    │           └─ DropPosition (0, -.02, 0)  measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint drives root, FreezeToWorld; inactive in editor,
    │                                 ApplyDuringUpload TurnOn (freezes the module frame at load-in)
    └─ EditorOnly                     VRCPositionConstraint drives DropPosition from GrabPosition —
                                      edit-time alignment only; ApplyDuringUpload TurnOff (off at upload)

**Physbone (`GrabBone`)** — grab-drag with no idle sway; each value deliberate: `pull 1`, `stiffness 0.2`, `spring 0`, `gravity 0`; `immobileType AllMotion` + `immobile 1` (a grab moves it, nothing else does); `radius 0.075`; `grabMovement 1`, `maxStretch 100000`, `maxSquish 1`; `allowGrabbing` on, `allowPosing` off (persistence is the constraint hold, never a pose), `allowCollision` off; `ignoreTransforms: [DropPosition]` (the tip-measure cell must not be dragged by its own bone); `isAnimated 0`, `resetWhenDisabled 0`.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
