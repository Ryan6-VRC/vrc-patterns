# drag-bone — rotation from position history (Structural Module)

Gives heading to a prop that is positioned but never rotated — a dropped grab-prop, a contact-tracker cage. A force-free physbone tip trails the moving rig like a pull-cord; an aim constraint faces away from it, which is the direction of travel. Rotation synthesized purely from position history: **zero synced params, no controller, no menu** — every client re-derives it.

**Provenance:** generalized from a private production avatar's carryable-prop rotation rig. Abstracted away: the consumer-side rotation-source multiplex and damping (see Combinations), and a face-the-wearer companion aim source. Mechanism and trail length otherwise verbatim.

Two prefabs, one mechanism:

- `DragBone_Yaw.prefab` — yaw only; the default. `Follower` never passes vertical motion (`AffectsPositionY` off), so the trail cannot verticalize and yaw stays defined everywhere.
- `DragBone_Full.prefab` — all axes; the aim pitches too. Degenerate at the pole: a trail crossing vertical pitches through smoothly (measured) but yaw/roll there is arbitrary. Only for props that genuinely need pitch.

## Interface

- **Params:** none.
- **Seam:** none — nothing merges into any controller. Two constraint-reference wiring points: **input** — add your prop's container as the single source (weight 1, zero offset) on `Follower`'s position constraint; **output** — source your prop's rotation constraint at `Drag_Rotation` (yaw-only consumers keep their own X/Z axes unaffected). Both are object references, path-immune; drop the prefab anywhere under the avatar.
- **Dependencies:** VRCFury (the `FreezeToWorld` ApplyDuringUpload).
- **Required assets:** none.

## Before you compose it

**The rig solves in a world-stable frame, and must stay in one.** The shipped root is world-frozen at load-in (`FreezeToWorld` parent constraint, enabled by ApplyDuringUpload — the grab-prop idiom), so the tip trails only when the *followed container* moves. Re-parent the rig under a bone, or defeat the freeze, and avatar locomotion drags the tip directly — the prop yaws to face the walk direction even while parked. Measured with the freeze intact: 1.5 m of avatar travel moved the module root 3 mm and left yaw tracking the container exactly.

## How it works

The physbone is a pure trailing particle: every force zeroed (`pull`/`spring`/`stiffness`/ `gravity` 0), so the tip holds its world position until the moving root drags it along at fixed bone length — root→tip always points opposite the motion, and the aim constraint (aim +Z, offset 180° yaw) faces along it. A stationary prop has a stationary tip, so the heading **holds** rather than decaying or wobbling: no return force means no oscillation and no rest-pose snap-back.

Degenerate cases, and what fences each:

- **Trail length → 0** (aim target on the constraint origin): fenced by `maxSquish 0` — the solver holds bone length exactly (measured invariant at 5 m/s). That one setting is the invariant; `maxStretch` only lengthens the trail (feel, not validity).
- **Trail goes vertical** (yaw undefined): fenced structurally by the yaw variant's planar follower — the bone root never moves vertically and nothing else (gravity 0, collision off) can move the tip. Physbone angle limits cannot replace this: a hinge (`limitRotation` zero) confines swing to the bone-local X axis, the one tested reorientation (0,0,90) tracked one heading then froze at its limit mid-turn while still allowing a vertical trail, and cone/polar limits are rest-axis-centered so they cannot exclude the poles — a 91° cone tested alongside the sandwich below clamped legitimate rear headings mid-turn. Keep `limitType None`. A **two-plane collider sandwich** *can* replace it where a planar follower won't fit (a rig that must ride a vertically-moving parent): two Plane `VRCPhysBoneCollider`s riding the bone root, facing each other at ±(radius + slack) around root height, with a nonzero bone radius. Measured (r 0.02, slack 0.005): tip vertical deviation ≤9 mm and zero yaw disturbance under 1 m of vertical root drive, horizontal tracking unchanged. Two colliders is the collider-fence **minimum**: a plane is one-sided, and nothing can press the tip onto a single pane from the far side — physbone gravity expresses only through `pull` (measured inert at pull 0), and nonzero pull + gravity collapses the trail's horizontal component against the pane exactly when the prop rests, undefining yaw. The shipped prefab keeps the follower — same fence, **zero colliders** (colliders cost avatar performance rank) — and never mount the rig on the rotating prop itself: its aim output rotating its own solve frame is a feedback loop.
- **Pure 180° reversal:** an exactly-collinear reversal *pushes through* the tip instead of swinging it — heading reads backwards until any lateral motion breaks the symmetry, then recovers in a fast smooth swing (~3°/frame max, no snap). Real hand and locomotion paths always carry lateral motion; scripted perfectly-straight reversals are the only place this shows.

Empirical constants (90% rule — test before changing):

| Constant | Value | Measured behavior |
|---|---|---|
| Trail length | `DragBone_End`'s local −Z offset (see **Rig**) — drag it to retune | response distance: heading settles after ~one trail length of travel; curvature lag ≈ trail/turn-radius radians (at the shipped length, 13° on a 0.5 m-radius circle). Lengthen for calmer, laggier heading |
| `maxSquish` | 0 | the length invariant above — the one setting that reintroduces the zero-length degeneracy |
| Straight-line tracking | ≤3° error | steady-state, both variants |
| Stationary hold | exact | zero yaw drift/jump over multi-second holds |

## Combinations

- **grab-prop / contact-tracker** — the intended pairings: both position a container without rotating it. Source `Follower` at the container (grab-prop's `Container`, contact-tracker's `Container`), and the payload's rotation constraint at `Drag_Rotation`.
- **Mode switching and damping** are the consumer's, not this rig's: multiplex `Drag_Rotation` against other rotation sources with animated source weights, and damp the raw aim (it snaps with the tip) with a self-sourced rotation constraint — the ancestor runs self-weight 1 / drag-weight 0.2. Both are their own patterns; this entry ships the source, not the mux.
- **Face-the-wearer** (the return-flight companion): not a drag bone at all — a second yaw-only aim constraint targeting an MA BoneProxy anchor on the wearer, multiplexed the same way.

## Verifying the install

Drag the followed container horizontally: the prop must swing to face the direction of travel and **hold that heading when the container stops**. A heading that decays back to rest means a nonzero `pull`/`stiffness` crept in; a prop that yaws while you walk with the container parked means the world-freeze is defeated (root riding a bone, or `FreezeToWorld` left inactive at build). The emulator shows all of this; what it cannot show is feel under real IK hand motion — trail-length taste is an in-game call.

## Rig

Identical trees; the two variants differ only in which axes `Follower` and `Drag_Rotation` affect.

    DragBone_Yaw                     root
    ├─ Follower                      VRCPositionConstraint, X/Z only (Full: XYZ), sources empty —
    │  │                             the consumer adds their container here
    │  ├─ DragBone                   VRCPhysBone: pull 0, spring 0, stiffness 0, gravity 0,
    │  │  │                          immobile 0, limitType None, maxStretch 0, maxSquish 0,
    │  │  │                          no grab/pose/collision, resetWhenDisabled on
    │  │  └─ DragBone_End (0,0,−0.1) the trailing tip — drag to retune trail length
    │  └─ Drag_Rotation              VRCAimConstraint → DragBone_End; aim +Z, offset (0,180,0),
    │                                yaw-only (Full: all axes) — the consumer output
    └─ FreezeToWorld                 VRCParentConstraint drives root, FreezeToWorld; inactive in
                                     editor, ApplyDuringUpload TurnOn (world-locks the frame at load-in)
