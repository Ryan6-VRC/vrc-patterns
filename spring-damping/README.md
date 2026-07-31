# spring-damping — secondary motion (bounce / lag) from self-referencing constraints (Structural Module)

Two kinds of physics-like secondary motion from VRChat constraints alone: **damping** — an object lagging behind its target — and **spring** — overshoot and bounce around it. Both are the same trick: a constraint that lists **its own transform** as a source alongside a `Target` and solves in world space, so each frame it blends a fraction of the way from its own last position toward the target — a feedback loop that low-passes the target's motion. Useful on its own, and a repeatable primitive larger constraint-driven systems build on.

## The three rigs

Weights are the tuned contract — the spring's shape and each damper's strength. All constraints solve in **world space** (`SolveInLocalSpace: 0`) and are `Locked`; the payload rides inside `Container`.

| Prefab | Component (on `Container`, unless noted) | Sources → weight |
|---|---|---|
| `PositionDamping` | `VRCPositionConstraint` | self `1`, `Position Target` `0.05` |
| `RotationDamping` | `VRCRotationConstraint` | self `1`, `Rotation Target` `0.025` (slower; rotation reads twitchier at equal weight) |
| `SpringConstraint` | two `VRCPositionConstraint`s | `Motion`: `Container` **`-1`**, `Spring Target` `1.1`, self `4`. `Container`: `Motion` `0.05`, self `1` |

**The spring's `-1` is load-bearing, not a typo.** `Motion` is pulled toward `Spring Target` (`1.1`), pushed *away* from the lagging `Container` (`-1` — the restoring force), and inertia-damped by its own last position (`4`); `Container` then damps toward `Motion` like a position damper. The negative source weight is what turns a low-pass into an oscillator — a cleanup pass that "fixes" it to a positive number silently deletes the bounce. Raise `Spring Target` (1→2) for a stiffer spring; raise `Motion`'s self weight for slower acceleration.

## Variations — parent constraint, per-axis

The self + `Target` source pattern is the mechanism, not the component; three edits adapt it without new tuning theory:

- **Combined position + rotation in one component.** Swap the constraint for a `VRCParentConstraint` with the same self + `Target` sources: it damps position *and* rotation together, one component instead of a `PositionDamping` + `RotationDamping` pair. The trade: position and rotation now share one weight instead of the two rigs' separate `0.05` / `0.025` split.
- **Damp only some axes.** Each constraint gates which axes it writes via `AffectsPosition{X,Y,Z}` / `AffectsRotation{X,Y,Z}`. Clear a flag and that axis leaves the feedback loop — it rigid-follows the parent, undamped.
- **Different strength per axis.** One constraint applies its source weights to *all* its enabled axes at once, so a per-axis strength split needs **one constraint per distinct value**: constraint A affecting only `X` (self `1` + `Target` `wX`), constraint B only `Y` (self `1` + `Target` `wY`), both on `Container` sharing the one `Target`. Stacking same-type constraints on one object is supported and costs one extra constraint (and one depth) per distinct-value axis. Mixing types (a `VRCPositionConstraint` for some axes + a `VRCParentConstraint` for others) is an equivalent alternative.

## Interface

- **Params:** none. No animator, nothing synced or saved — secondary motion is deterministic from transform motion, identical on every client without a synced bit.
- **Anchoring (the seam):** the rig ships **unanchored** — dropped in, `Container` and `Target` rest at the avatar-root origin (the wearer's feet). You place two things: the **rig** where the payload lives, and the **`Target`** at the pose the payload settles toward (see §Parent-transform dependency — this placement *is* the behavior). Anchor the `Target` with an MA `BoneProxy` (`nadena.dev.modular-avatar`, already a package dependency); the rig itself is parented normally.
- **Dependencies:** `com.vrchat.avatars` constraints (the `VRC*Constraint` components). No PhysBone, no contacts.
- **Required assets:** none — the `Cube` payload uses Unity's built-in cube + default material, a stand-in to make the motion visible. Replace it with your object (or constrain your object to `Container`).

## Parent-transform dependency

The effect is defined **entirely by two transforms and their frames** — get this wrong and the rig does nothing, or the wrong thing:

- **The `Target`'s frame is the rest pose.** `Container` chases the `Target`'s *world* position/rotation. Anchor the `Target` to the bone whose motion should drive the secondary motion: the head bone for a lagging hat, a hip bone for a swaying charm.
- **The rig's parent is the reference frame the payload lags *within*.** `Container` lags **world-space** motion, so parent the rig under the same moving bone as the `Target` and the two move together — **no relative motion, no effect.** The payload must be free to fall behind: parent the rig higher up (a stiffer parent, or the avatar root) than the `Target`'s bone.
- **Local-space breaks it.** Flipping `SolveInLocalSpace` to `1` makes the constraint chase the target in the parent's local frame, which cancels exactly the world drag the effect is built on. Leave it world.

## Framerate dependence

The fraction closed each frame is a **per-frame** constant, so these rigs are framerate-dependent — settle time is measured in frames, not seconds. If you need framerate-stable timing, drive the weight from `smooth-frametime`.

## Verifying the install

Enter play mode, anchor the `Target` to a moving bone, and move — the payload should trail and (spring) overshoot then settle. Two failure reads: the payload sitting at the **wearer's feet** means the rig or `Target` never got anchored (still at avatar-root origin); the payload **rigidly welded** to the bone with no lag means the rig and `Target` share a frame (no relative motion — reparent the rig higher) or a `Missing Script` on `Container` (the SDK's constraint components didn't resolve).

The av3emulator reproduces this faithfully — constraints are engine transforms, not avatar logic, so what you see in play mode is what uploads.

## Provenance

Generalized from VRLabs' MIT-licensed [`Spring-Constraint`](https://github.com/VRLabs/Spring-Constraint) and [`Damping-Constraints`](https://github.com/VRLabs/Damping-Constraints), whose rigs and tuned weights are reproduced as-is on VRChat constraints. No real-avatar naming — the payload is a placeholder cube.
