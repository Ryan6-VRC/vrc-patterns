# grab-prop — sample-and-hold world-drop (Module)

Grab a prop off your avatar, carry it live, drop it anywhere in the world, re-grab it in place. The drop costs **zero synced params**: every client replays the same release choreography off the natively-synced physbone grab, freezing the prop where it was dropped. Module total: **1 synced bit** (`GrabProp/Enable`).

**Provenance:** generalized from a private production avatar's grab-prop (VRLabs World-Constraint ancestry).

## Ground truth

- Parameters, states, clips and the whole release choreography are `controller.yaml`. Its header is the design record: it names each constraint cell, what disabling one means, and why the released pulse is a stepped curve. The published set is the prefab's `globalParams` — `GrabProp/Enable` alone, driven by the VRCFury Toggle on the root.
- `GrabProp/Enable` is **off-is-reset**: toggling it off and on recalls a dropped prop to the home anchor.
- `GrabBone_IsGrabbed` is minted by the grab physbone and never synced — the native grab sync regenerates it per client, which is what makes the drop cost nothing.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0`), so every clip binding resolves **prop-root relative** (`basis: mount-root`). The FullController merges `built/GrabProp_Fx_Parameters.asset`.
- Everything else about the rig — constraint sources, physbone forces, rest offsets — is in `GrabProp.prefab`. See **Rig** for what each node is for.
- **Dependencies:** none beyond the VRC SDK + VRCFury to build; **compose `anti-cull` alongside** (its README §When a module needs this) — a dropped prop holds state through replayed choreography while the wearer may be off-screen. Drop the prefab anywhere under the avatar.
- **Required assets:** none. `Payload` is a placeholder sphere on Unity's built-in default material; swap it for your prop mesh, keep it under `Container`.

## Before you compose it

**`HomeAnchor` rides the wearer** — an MA BoneProxy with the recall target as its `Offset` child, while the module root stays world-frozen so drops hold their world spot. Delete the BoneProxy for a fixed world-spot home instead. Keep the module's animated cells (`Container`/`SourcePosition`/`GrabPosition`) out of any re-parented subtree — a VRCF clip binding through an MA-moved node is dropped at build, and the warning that follows names the clip rather than the anchor (`nondestructive.md` has the measured build order).

**The freeze's placement is the design, not a convenience.** In the release frame the tip snaps to its rest and `SourcePosition` follows it before any same-frame `IsActive`/`m_Enabled` write can protect it, so the sample cell is briefly wrong on every release and anything reading it live inherits that — a rebuilt hold on `SourcePosition` itself, or on a mid-chain node the release frame updates, captures the home pose while reading exactly like this rig to every static check (frame-measured). `Container` survives because it reads the sample across the constraint cycle's stale edge — one frame behind, still holding the drop — and the pulse then re-samples the settled tip, healing the cell after the freeze has already saved the payload.

**Replicate the clip table, not this prose.** The rig holds still at both edges by constraint-freeze, and each freeze lives only as a clip value: `grabbed` freezes the **root** (`GrabPosition.IsActive` 0 — with it live, a re-grab from a drop swaps the root drop→home a frame before the grab owns the tip, and everything downstream reads the home anchor for one frame), and `dropped` never re-enables the **Container** constraint (the frozen transform IS the hold — re-riding a live chain after the drop re-opens whatever feedback path the consumer's display hangs off it). A composition that re-derives its chords from this section instead of diffing them binding-for-binding against `controller.yaml`'s clips has shipped both defects (frame-measured).

**Late join:** a dropped prop carries no synced position, so a late joiner parks in `Waiting` with the prop hidden until it witnesses a grab — the grab physbone lives outside the hidden branch, so a grab always re-establishes it. The wearer's own view never hides (IsLocal skips the park).

**Cross-client fidelity:** the world-frozen frame is locked per-client at load-in (`runtime.md` §Constraints) — clients agree on the drop point only because they replay the same clips off the synced grab, not because the frame itself is shared. Expect per-client drift on the order of the IK-delayed hand; exact placement needs a real position sync on top, out of scope here.

## Measured

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Knob |
|---|---|---|
| Released pulse phases | the `released` clip's phase keys — freeze at t=0, then the re-sample key, then hold to the clip end | the sample must land after the physbone tip has settled but before a re-grab is plausible; the clip length is the pulse |
| Remote settle dwell | the `timer` clip's length | retune in-game against real network settle time — the emulator can't validate it |

**Copy site — `drop-on-player`** clones this grab/release rig and carries its own copy of these rows and the `Rig` section, so a retune here lands half the homes. That entry's constants table marks which rows it takes from here.

## Verifying the install

Enable on: the prop rests at `HomeAnchor/Offset` on the wearer's hips. Finding it at the avatar-root origin means the BoneProxy never resolved; finding the module frame drifting with the avatar instead of holding its world spot means `FreezeToWorld`'s `ApplyDuringUpload` did not fire. Grab and release it — the prop must freeze where dropped and a re-grab must pick up in place rather than teleporting, which is the sample cell landing.

Two clients in-game, not the emulator: the remote settle dwell, and how far the per-client drift above actually opens up under real network conditions.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. `Locked` is on for every constraint and the clips swap source weights.

    GrabProp                          root — VRCFury FullController + Toggle
    ├─ Container                      VRCPositionConstraint follows SourcePosition; holds Payload
    │  └─ Payload                     sphere, built-in default material — swap for your mesh, keep
    │                                 it under Container
    ├─ SourcePosition                 VRCPositionConstraint follows DropPosition — the
    │                                 sample-and-hold cell
    ├─ HomeAnchor                     MA BoneProxy → Hips (AsChildAtRoot)
    │  └─ Offset                      the recall target — drag to taste (see above)
    ├─ GrabPosition                   VRCPositionConstraint over [HomeAnchor/Offset, Container] —
    │  │                              the bone chain's rest home
    │  └─ GrabBone                    VRCPhysBone (parameter GrabBone → mints GrabBone_IsGrabbed)
    │     └─ GrabBone_End
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation
    │           │                     frame
    │           └─ DropPosition       measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint driving the root; inactive in the editor,
    │                                 VRCFury ApplyDuringUpload turns it on at load-in
    └─ EditorOnly                     VRCPositionConstraint drives DropPosition from GrabPosition —
                                      edit-time alignment only; ApplyDuringUpload turns it off

**Physbone (`GrabBone`)** — tuned for grab-drag with no idle sway, and the shape of that tuning is what to preserve if you rebuild it: a pull with light stiffness and no spring or gravity, `immobileType AllMotion` at full immobile so a grab moves it and nothing else does, `allowGrabbing` on with `allowPosing` off (persistence is the constraint hold, never a pose), collision off, and `ignoreTransforms: [DropPosition]` so the tip-measure cell is not dragged by its own bone. The values are in `GrabProp.prefab`.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
