# grab-prop — sample-and-hold world-drop (Module tier)

Grab a prop off your avatar, carry it live, drop it anywhere in the world, re-grab it in place.
The drop costs **zero synced params**: every client replays the same release choreography off the
natively-synced physbone grab, freezing the prop where it was dropped (`gimmicks.md` §Constraint
patterns "Sample-and-hold drop"). Module total: **1 synced bit** (`GrabProp/Enable`).

**Provenance:** generalized from a Remy GestureTools GrabProp (VRLabs World-Constraint ancestry).
Abstracted away: the avatar-specific payload mesh and its feedback-glow controller, the MA BoneProxy
on the home anchor (now a plain GO — see Interface), a vestigial constraint source, and a dead
GameObject-active curve. Mechanism, constants, and hierarchy otherwise verbatim.

## Interface

- **Params:**
  - `GrabProp/Enable` (bool, in) — synced, **unsaved**. The menu front (VRCFury Toggle on the
    prefab root). Off-is-reset: toggling off/on recalls a dropped prop to the home anchor.
  - `GrabBone_IsGrabbed` (bool, sensing) — minted by the grab physbone (`parameter: GrabBone`),
    never synced/saved/menu-exposed; the native grab sync regenerates it per client.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0`), so
  every clip binding resolves **prop-root relative** (`basis: mount-root`). Pure VRCFury — no MA
  half. The FullController merges `built/GrabProp_Fx_Parameters.asset` (the built form of the
  YAML's `vrc:` block — the sync surface); `GrabProp/Enable` is exported via `globalParams` and
  the Toggle drives it.
- **Dependencies:** none beyond the VRC SDK + VRCFury to build; **compose `anti-cull` alongside**
  (its README §When a module needs this) — a dropped prop holds state through replayed choreography
  while the wearer may be off-screen, and a remote client that view-culls the wearer stops replaying
  it. Drop the prefab anywhere under the avatar.
- **Required assets:** none — `Payload` is a placeholder sphere on Unity's built-in default
  material; swap it for your prop mesh, keep it under `Container`.

## The one thing to know before using it

**`HomeAnchor` is deliberately not bone-anchored.** The module root is frozen to world at load-in
(`FreezeToWorld` constraint, enabled during upload), so out of the box the home is a fixed world
spot — the avatar's spawn point. For a follow-me home (prop returns to your hip/chest), anchor
`HomeAnchor` yourself: MA BoneProxy on it, or constrain it to a bone. It is referenced only as a
constraint source (an object reference — path-immune), so moving or re-parenting it is safe. If
you BoneProxy it, keep the module's animated cells (`Container`/`SourcePosition`/`GrabPosition`)
out of the re-parented subtree — a VRCF clip binding through an MA-moved node silently vanishes
at build (CONVENTIONS §Seam ordering has the measured mechanism).

## How it works

`GrabPosition` (the bone chain's rest home) multiplexes `[HomeAnchor, Container]`. The grab
physbone's tip is measured by `DropPosition`, a child of a world-rotation-frozen frame; the
`SourcePosition` cell samples it; `Container` (the payload mount) follows `SourcePosition`.

Release choreography (`Released`, 0.5 s): at t=0 the Container constraint **disables** — a disabled
constraint holds its transform, that is the freeze — and the bone chain re-anchors onto the frozen
prop; at t=0.25 `SourcePosition` re-samples the settled tip; at t=0.5 it holds. `Dropped` keeps the
constraint disabled (the frozen transform is the hold); the sample exists so a re-grab, which
re-enables it, picks up at the drop point instead of teleporting.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Released pulse phases | freeze 0 s / sample 0.25 s / hold 0.5 s | emulator sweep (this entry's build) |
| Remote settle dwell | 1.0 s (`timer` clip) | in-game batch (network timing) |
| Physbone constants | see Rig | emulator sweep (stiffness) |

**Late join:** a dropped prop carries no synced position, so a late joiner parks in `Waiting` with
the prop hidden (fail-visible — never shown at a wrong spot) until it witnesses a grab. The grab
physbone lives outside the hidden branch, so a grab always re-establishes it. The wearer's own view
never hides (IsLocal skips the park).

**Cross-client fidelity:** the world-frozen frame is per-client (locked at load-in, `runtime.md`
§Constraints) — clients agree on the drop point because they replay the same clips off the synced
grab, not because the frame is shared. Expect per-client drift on the order of the IK-delayed hand;
exact placement needs a real position sync on top (out of scope — Custom-Object-Sync territory).

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. The structure and the
feel-tuned physbone constants below are what a rebuild would otherwise need; `Locked` on every
constraint, source weights swapped by the clips.

    GrabProp                          root — VRCFury FullController + Toggle
    ├─ Container      (0, 0.8, 0.25)  VRCPositionConstraint follows SourcePosition; holds Payload
    │  └─ Payload                     sphere, built-in default material — swap for your mesh, keep under Container
    ├─ SourcePosition (0, 0.8, 0.25)  VRCPositionConstraint follows DropPosition (sample-and-hold cell)
    ├─ HomeAnchor     (0, 0.8, 0.25)  plain GO — the consumer anchors it (see above)
    ├─ GrabPosition   (0, 0.8, 0.25)  VRCPositionConstraint, sources [source0 HomeAnchor, source1 Container]
    │  └─ GrabBone                    VRCPhysBone (parameter GrabBone → mints GrabBone_IsGrabbed)
    │     └─ GrabBone_End (0, .02, 0)
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation frame
    │           └─ DropPosition (0, -.02, 0)  measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint drives root, FreezeToWorld; inactive in editor,
    │                                 ApplyDuringUpload TurnOn (freezes the module frame at load-in)
    └─ EditorOnly                     VRCPositionConstraint drives DropPosition from GrabPosition —
                                      edit-time alignment only; ApplyDuringUpload TurnOff (off at upload)

**Physbone (`GrabBone`)** — grab-drag with no idle sway; each value deliberate:
`pull 1`, `stiffness 0.2` (emulator-swept — 90% rule), `spring 0`, `gravity 0`; `immobileType
AllMotion` + `immobile 1` (a grab moves it, nothing else does); `radius 0.075`; `grabMovement 1`,
`maxStretch 100000`, `maxSquish 1`; `allowGrabbing` on, `allowPosing` off (persistence is the
constraint hold, never a pose), `allowCollision` off; `ignoreTransforms: [DropPosition]` (the
tip-measure cell must not be dragged by its own bone); `isAnimated 0`, `resetWhenDisabled 0`.

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID —
recompile is GUID-stable). The prefab is hand-maintained against the Rig section above.
