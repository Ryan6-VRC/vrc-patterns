# spring-damping — secondary motion (bounce / lag) from self-referencing constraints (Structural Module)

Two kinds of physics-like secondary motion from VRChat constraints alone: **damping** — an object lagging behind its target — and **spring** — overshoot and bounce around it. Both are the same trick: a constraint that lists **its own transform** as a source alongside a `Target` and solves in world space, so each frame it blends a fraction of the way from its own last position toward the target — a feedback loop that low-passes the target's motion; spring adds a second stage with a negative source weight so the loop rings instead of settling. Useful on its own to lend any object a natural sense of weight and momentum, and a repeatable primitive that larger constraint-driven systems build on.

This is a **structural** Module: the behavior lives in the constraint components, not an animator, so the entry ships prefabs and **no `controller.yaml`** — the gate's compile pass skips it, though its prefab-integrity pass still checks the prefabs import with no missing scripts (`CONVENTIONS.md` §The gate). Behavioural correctness rests on the install check below.

## The three rigs

Weights are the tuned contract — the spring's shape and each damper's strength. All constraints solve in **world space** (`SolveInLocalSpace: 0`) and are `Locked`; the payload rides inside `Container`.

| Prefab | Component (on `Container`, unless noted) | Sources → weight |
|---|---|---|
| `PositionDamping` | `VRCPositionConstraint` | self `1`, `Position Target` `0.05` → ~4.8% of the gap closed/frame |
| `RotationDamping` | `VRCRotationConstraint` | self `1`, `Rotation Target` `0.025` → ~2.4%/frame (slower, rotation reads twitchier) |
| `SpringConstraint` | two `VRCPositionConstraint`s | `Motion`: `Container` **`-1`**, `Spring Target` `1.1`, self `4`. `Container`: `Motion` `0.05`, self `1` |

**The spring's `-1` is load-bearing, not a typo.** `Motion` is pulled toward `Spring Target` (`1.1`), pushed *away* from the lagging `Container` (`-1` — the restoring force), and inertia-damped by its own last position (`4`); `Container` then damps toward `Motion` like a position damper. The negative source weight is what turns a low-pass into an oscillator — a cleanup pass that "fixes" it to a positive number silently deletes the bounce. Raise `Spring Target` (1→2) for a stiffer spring; raise `Motion`'s self weight for slower acceleration.

## Variations — parent constraint, per-axis

The self + `Target` source pattern is the mechanism, not the component; three edits adapt it without new tuning theory:

- **Combined position + rotation in one component.** Swap the constraint for a `VRCParentConstraint` with the same self + `Target` sources: it damps position *and* rotation together off one shared weight. One component instead of a `PositionDamping` + `RotationDamping` pair — the trade is that position and rotation now share a single strength (one weight) instead of the `0.05` / `0.025` split the two separate rigs carry.
- **Damp only some axes.** Each constraint gates which axes it writes via `AffectsPosition{X,Y,Z}` / `AffectsRotation{X,Y,Z}`. Clear a flag and that axis leaves the feedback loop — it rigid-follows the parent, undamped. A charm that should bob vertically but not sway: keep `AffectsPositionY`, clear `X`/`Z`.
- **Different strength per axis.** One constraint applies its source weights to *all* its enabled axes at once, so a per-axis strength split needs **one constraint per distinct value**: constraint A affecting only `X` (self `1` + `Target` `wX`), constraint B only `Y` (self `1` + `Target` `wY`), both on `Container` sharing the one `Target`. **Stacking same-type constraints on one object is supported** — VRC constraints are not `[DisallowMultipleComponent]`, and the SDK carries a dedicated `ReRegisterSameObjectConstraint` path; measured in play mode, an X-only and a Y-only `VRCPositionConstraint` on one `Container` each solve their own axis (Container reaches the target on both, the un-affected axis untouched). Cost is one extra constraint (and one depth) per distinct-value axis. Mixing types (a `VRCPositionConstraint` for some axes + a `VRCParentConstraint` for others) is an equivalent alternative, sometimes tidier to animate.

## Interface

- **Params:** none. No animator, nothing synced or saved — secondary motion is deterministic from transform motion, identical on every client without a synced bit.
- **Anchoring (the seam):** the rig ships **unanchored** — dropped in, `Container` and `Target` rest at the avatar-root origin (the wearer's feet). You place two things: the **rig** where the payload lives, and the **`Target`** at the pose the payload settles toward (see §Parent-transform dependency — this placement *is* the behavior). Anchor both to bones with an MA `BoneProxy` (`nadena.dev.modular-avatar`, already a package dependency) rather than leaving them loose. Only the `Target` is object-referenced (a constraint source), so only it is `BoneProxy`-eligible; the rig is parented normally.
- **Dependencies:** `com.vrchat.avatars` constraints (the `VRC*Constraint` components). No PhysBone, no contacts.
- **Required assets:** none — the `Cube` payload uses Unity's built-in cube + default material, a stand-in to make the motion visible. Replace it with your object (or constrain your object to `Container`).

## Parent-transform dependency

The effect is defined **entirely by two transforms and their frames** — get this wrong and the rig does nothing, or the wrong thing:

- **The `Target`'s frame is the rest pose.** `Container` chases the `Target`'s *world* position/ rotation. Anchor the `Target` to the bone whose motion should drive the secondary motion: the head bone for a lagging hat, a hip bone for a swaying charm. Move the `Target`, and you move what the payload springs toward.
- **The rig's parent is the reference frame the payload lags *within*.** Because the solve is world space and self-referencing, `Container` lags **world-space** motion — as its parent bone whips through the world, `Container` is dragged along, then the constraint pulls it back toward the (also-moving) `Target`, and the gap between them is the visible lag/bounce. Parent the rig under the same moving bone as the `Target` and the two move together — **no relative motion, no effect.** The payload must be free to fall behind: parent the rig higher up (a stiffer parent, or the avatar root) than the `Target`'s bone.
- **Local-space breaks it.** Flipping `SolveInLocalSpace` to `1` makes the constraint chase the target in the parent's local frame, which cancels exactly the world drag the effect is built on. Leave it world.

## Framerate dependence — why no frametime-independent version ships

The fraction closed each frame is a **per-frame** constant, so the settle is measured in frames, not seconds: at 90 fps the object catches up ~1.5× faster than at 60. A constraint weight is a fixed number with no access to `dt`, so a frametime-independent rig would need an animator to recompute the source weight from frametime each frame (`α = 1 − e^(−rate·dt)`, then weight `= α/(1−α)`) and drive it as an AAP — the construction `smooth-frametime` (remap-α) and `blendtree-math` (divide) already carry. That is real and feasible but out of scope here; these ship as the plain, framerate-dependent rigs the ancestors are, which is fine for cosmetic secondary motion where absolute settle time is not a contract. If you need framerate-stable timing, drive the weight from `smooth-frametime`.

## Verifying the install

Enter play mode, anchor the `Target` to a moving bone, and move — the payload should trail and (spring) overshoot then settle. Two failure reads: the payload sitting at the **wearer's feet** means the rig or `Target` never got anchored (still at avatar-root origin); the payload **rigidly welded** to the bone with no lag means the rig and `Target` share a frame (no relative motion — reparent the rig higher) or a `Missing Script` on `Container` (the SDK's constraint components didn't resolve).

The av3emulator reproduces this faithfully — constraints are engine transforms, not avatar logic, so what you see in play mode is what uploads.

## Provenance

Generalized from VRLabs' MIT-licensed [`Spring-Constraint`](https://github.com/VRLabs/Spring-Constraint) and [`Damping-Constraints`](https://github.com/VRLabs/Damping-Constraints) (position + rotation), whose rigs and tuned weights are reproduced as-is on VRChat constraints; the three are collected into one entry and the parent-transform dependency the ancestors leave to a video is made explicit here. No real-avatar naming — the payload is a placeholder cube.
