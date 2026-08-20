# drag-bone — rotation from position history (Structural Module)

Gives heading to a prop that is positioned but never rotated — a dropped grab-prop, a contact-tracker cage. A force-free physbone tip trails the moving rig like a pull-cord; an aim constraint faces away from it, which is the direction of travel. Rotation synthesized purely from position history: **zero synced params, no controller, no menu** — every client re-derives it.

**Provenance:** generalized from a private production avatar's carryable-prop rotation rig.

Two prefabs, one mechanism:

- `DragBone_Yaw.prefab` — yaw only; the default. `Follower` never passes vertical motion, so yaw stays defined everywhere.
- `DragBone_Full.prefab` — all axes; the aim pitches too. Degenerate at the pole: yaw/roll there is arbitrary. Only for props that genuinely need pitch.

## Ground truth

- **Seam — two constraint-reference wiring points, both the consumer's to make.** **Input:** add your prop's container as the single source, weight 1 and zero offset, on `Follower`'s position constraint, which ships with an empty source list. **Output:** source your prop's rotation constraint at `Drag_Rotation` (a yaw-only consumer keeps its own X/Z axes unaffected). Both are object references rather than paths, so the prefab drops anywhere under the avatar. Nothing merges into any controller.
- Parameters: none.
- Everything else about the rig — every physbone force, every constraint axis mask, the trail offset — is in the two prefabs. See **Rig** for what each node is for.
- Dependencies: VRCFury, for the `FreezeToWorld` ApplyDuringUpload.

## Before you compose it

**The rig solves in a world-stable frame, and must stay in one.** The shipped root is world-frozen at load-in (`FreezeToWorld` parent constraint, enabled by ApplyDuringUpload), so the tip trails only when the *followed container* moves. Re-parent the rig under a bone, or defeat the freeze, and avatar locomotion drags the tip directly. With the freeze intact, the root's displacement while walking is transient only — judge the freeze by whether it settles back to zero once the avatar stops, not by a peak read mid-stride. Never mount the rig on the rotating prop itself, either: its aim output rotating its own solve frame is a feedback loop.

**grab-prop and contact-tracker are the intended pairings.** Source `Follower` at the container, and the payload's rotation constraint at `Drag_Rotation`.

**Mode switching and damping are the consumer's, not this rig's.** Multiplex `Drag_Rotation` against other rotation sources, and damp the raw aim — it snaps with the tip — with a self-sourced rotation constraint. Both are their own patterns; this entry ships the source, not the mux. **Face-the-wearer** is not a drag bone at all: a second yaw-only aim constraint targeting an MA BoneProxy anchor on the wearer, multiplexed the same way.

## Measured

Trail length is the only taste knob, and it lives at its authoring site: `DragBone_End`'s local −Z offset in each prefab, which you drag to retune. Lengthen for a calmer, laggier heading. `maxSquish` looks like a second knob and is not — it is a structural fence, see **Rig**. 90% rule: test before changing either.

## Verifying the install

Drag the followed container horizontally: the prop must swing to face the direction of travel and **hold that heading when the container stops**. Stopped means the *container* is at rest, not your hand — a physics-driven container (a hair or tail tip) keeps settling for seconds after you release, and the trailing yaw drifts along with it the whole time, so a sound rig reads as a hold failure unless you let the container come to rest first. A heading that decays back to rest means a nonzero `pull`/`stiffness` crept in; a prop that yaws while you walk with the container parked means the world-freeze is defeated (root riding a bone, or `FreezeToWorld` left inactive at build). The emulator shows all of this; what it cannot show is feel under real IK hand motion — trail-length taste is an in-game call.

## Rig

Identical trees; the two variants differ only in which axes `Follower` and `Drag_Rotation` affect.

    DragBone_Yaw                     root
    ├─ Follower                      VRCPositionConstraint, horizontal only (Full: all axes),
    │  │                             sources empty — the consumer adds their container here
    │  ├─ DragBone                   VRCPhysBone, every force zeroed, no grab/pose/collision
    │  │  └─ DragBone_End            the trailing tip — drag it to retune trail length
    │  └─ Drag_Rotation              VRCAimConstraint → DragBone_End, yaw-only (Full: all
    │                                axes) — the consumer output
    └─ FreezeToWorld                 VRCParentConstraint driving the root; inactive in the
                                     editor, ApplyDuringUpload turns it on at load-in

The physbone is a pure trailing particle: with every force at zero the tip holds its world position until the moving root drags it along at fixed bone length, so root→tip always points opposite the motion and the aim constraint faces along it. A stationary prop has a stationary tip — no return force means no oscillation and no rest-pose snap-back. Two degenerate cases follow from that, and each is fenced structurally rather than tuned:

- **Trail length → 0**, putting the aim target on the constraint origin, is fenced by `maxSquish 0`: the solver holds bone length exactly. `maxStretch` only ever lengthens the trail, so it is feel, not validity.
- **A vertical trail**, where yaw is undefined, is fenced by the yaw variant's planar follower: the bone root never moves vertically and nothing else can move the tip, at zero gravity, zero colliders and collision off. Keep `limitType None`.
