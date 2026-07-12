# blendtree-math — the Direct-Blend-Tree math idiom catalog (Pattern, study)

The DBT-math primitives an agent reaches for when a gimmick needs arithmetic on animator floats
without a scripted behaviour: add, subtract, multiply, negate/remap, clamp, divide, the composed
min/max, and the exponential/linear/frametime-independent smoothing family. Each primitive is isolated
in its own layer so a human (or agent) can open one state's blend tree in the Animator window and read
the idiom in isolation, without the others' graphs cluttering the view — a **study layout, not a shipping
one** (see the shipping note below).

**Study entry:** this entry commits `built/` so the blend-tree graphs — the nested Direct trees, the
composed min/max chains, and the 1D-vs-Direct contrast — are legible in the Animator window, where a
blend tree reads far more clearly than in YAML (CONVENTIONS permits this for a declared study/reference
entry). It is still Pattern tier: a consumer lifts the YAML and recompiles it in their own project with
their own params/GUIDs, rather than referencing the committed controller by GUID.

**Shipping: collapse the idioms you lift into one Direct Blend Tree layer — do not replicate the
per-layer catalog.** Unity's per-layer runtime cost is super-linear (`gimmicks.md` §Blend tree patterns),
and the optimizers (d4rk, VRCFury) merge blend-tree math into a single DBT regardless; the one-idiom-per-
layer split here exists only so each graph reads alone. Folded into one always-on WD-ON Direct tree, every
blend param / directWeight is read at frame start, so a computed intermediate feeds the next stage one
frame stale and a feed-forward chain of depth D settles ~D frames after an input change (`verify.md`) —
fine for the uses this math serves (a smoother's job is lag; a color a few frames behind a slider is
invisible). The study layers that chain *same-frame* (composed min/max, the frametime rig's `Time`→`FrameTime`
split) trade that exactness for the settle when collapsed; the exponential smoother's `S`-reads-itself
feedback is already the intended one-frame recurrence and collapses with no change.

**Provenance:** generalized from standard VRChat DBT-math constructions (vrc.school Advanced Blend
Trees); no real-avatar naming.

## Interface

- **Params:** generic float inputs, drivable (not synced/saved here — a consumer decides that):
  `A`/`B` (shared inputs for add/subtract/multiply/min/max, working range `[0,1]`), `RemapIn`
  (`[-1,1]`), `ClampIn`, `DivInput` (`>=0`), `SmoothTarget` + `ExpKeep`/`ExpMix` (exponential smoothing),
  `LinTarget` (linear smoothing), and `One` (a constant helper, never driven — leave it at its default).
  Outputs are all AAPs (`aap: true`, written by a clip curve, not synced): `SumOut`, `DiffOut`,
  `ProdOut`, `NegOut`, `ClampOut`, `DivOut`, `MaxOut`, `MinOut`, `SmoothedExp`, `SmoothedLin`, `Time`,
  `LastTime`, `FrameTime`, plus the composed min/max intermediates (`MaxDiff`/`MaxRelu`,
  `MinDiff`/`MinRelu`) and the linear-smoothing intermediate (`LinDelta`), and one throwaway
  (`DivDummy`).
- **Seam:** none shipped — this is Pattern tier, lifted as YAML. No scene bindings exist to repath (every
  clip here writes an animator parameter, not a scene property), so a consumer just imports the layers
  they want and renames the generic params to their own naming.
- **Dependencies:** none. This entry uses only animator parameters and blend trees — no shader, mesh, or
  package dependency (contrast `color-adjust`, which depends on the target material's shader).
- **Required assets:** none.

## The one hard constraint

A parameter used as a Direct blend tree's `directWeight` is clamped to `>=0` by Unity — only a clip's
authored curve *value* may carry a negative sign. Every idiom below is shaped around that: `A`/`B` and
the genuine clamp0 outputs (`MaxRelu`, `MinRelu`) are used directly as weights; a genuinely signed
intermediate (`MaxDiff`, `MinDiff`, `LinDelta`) is instead read back through a 1D tree, whose blend
*parameter* — unlike a Direct weight — is never clamped. (`SmoothedLin` looks `>=0` but isn't quite — see
the linear-smoother limitation below, a live instance of why this rule exists.)

## Coverage

| Primitive | Layer(s) | Idiom |
|---|---|---|
| add | `Add_Direct`, `Add_1D` | both shown, for comparison — Direct-child (canonical, higher precision, positive-only) vs. 1D-child (lower precision; as configured here its `[0,1]` thresholds clamp negatives, so signed inputs need signed thresholds like `NegateRemap`'s) |
| subtract | `Subtract` | Direct-child, sign baked into the clip constant |
| multiply | `Multiply` | nested Direct trees (positive-only) |
| negate/remap | `NegateRemap` | 1D tree's own clamp-and-lerp math *is* the remap |
| clamp | `Clamp` | 1D natural saturation to `[0,1]`; shape reused by min/max's ReLU stage |
| divide | `Divide` | Normalize Blend Values + a weight-1 dummy child (divides by `1 + Input`, not `Input`) |
| max (derived) | `MaxDiffCalc` → `MaxReluCalc` → `MaxOutCalc` | `max(a,b) = b + clamp0(a-b)` |
| min (derived) | `MinDiffCalc` → `MinReluCalc` → `MinOutCalc` | `min(a,b) = b - clamp0(b-a)` |
| exponential smoothing | `ExpSmooth` | single Direct tree; mirrors the `smoother` fixture — stable, framerate-dependent by design |
| linear smoothing | `LinSmooth` | single Direct tree; fixed per-frame step, clamped delta — **limit-cycles by ±one step, see below** |
| frametime rig | `TimeRamp` → `FrameTimeCalc` | `tangents: linear` ramp + `FrameTime = Time - LastTime` |

## The frametime rig is owned, not borrowed

VRCFury ships a `FrameTimeService` that can supply a frametime parameter for free. This entry does
**not** use it: that service is lazy-initialized and cached with no documented contract on when it
updates relative to a consumer's own layers, which makes depending on it fragile for a library entry
meant to be lifted into an arbitrary project. `TimeRamp` + `FrameTimeCalc` are self-contained — a Time
ramp this entry owns and a calc layer that reads it — so the rig works regardless of what else is in the
FX controller. Borrowing VRCFury's service instead is a deliberate, non-default choice a consumer can
make for their own build; it is not what this entry ships.

Neither smoothing idiom here is wired to `FrameTime` directly (kept legible — one concern per layer):
to make either frame-rate independent, scale its per-frame step by `FrameTime` using the `multiply`
idiom above before adding it in.

## Known limitation: the linear smoother limit-cycles (does not fully settle)

The linear smoother ramps cleanly toward the target at a fixed step, then **oscillates by ±one step
around it forever** — it never settles. This is inherent, not a bug in this construction: the clamped
step needs a *computed* delta (`LinTarget − SmoothedLin`), and a blend tree can't both produce a value
and consume it as a blend parameter in the same frame, so the step always acts on a **one-frame-stale
delta**. Near the target that stale ±step keeps pushing a full step past it, then back — a limit cycle
of amplitude one step. Measured: with step `0.1`, `SmoothedLin` reaches `1.0` at frame 11 then cycles
`1.0 ↔ 1.1`.

A second consequence, unmeasured by the up-ramp table but reachable by driving `LinTarget` toward 0:
near a zero target the cycle dips `SmoothedLin` slightly **negative**. This idiom, for simplicity, uses
`SmoothedLin` as a `directWeight` (the carry and the delta's negative term), and Unity clamps a negative
weight to 0 — so the low end of the cycle distorts. `SmoothedLin` is thus **not** a guaranteed-`>=0`
weight, and this is a concrete instance of the hard constraint above: a value that *looks* non-negative
but a feedback loop nudges below zero, then a Direct weight silently clamps it. To carry a truly signed
smoothed value, read it through a 1D tree (as the signed intermediates do) instead of self-weighting.

The **exponential smoother has no such loop** and settles cleanly, because it feeds `SmoothedExp` and
`SmoothTarget` *directly* as blend parameters — no computed intermediate, no delay. That is the study
lesson of pairing them here.

The cycle is intrinsic to the one-frame delay, not to this construction — it cannot be tuned away. Three
mitigations, none free: a **smaller step** tightens the band and slows the ramp; a **`FrameTime`-scaled
step** normalizes it across framerates but still cycles; if you need a value that truly holds, **prefer
the exponential smoother**. Keep this idiom in one Direct tree — splitting the delta and apply across
separate layers adds a frame of delay per split and widens the cycle.

## Verified behavior

Measured by hosting the built controller on an `Animator` and ticking it deterministically at
`dt = 1/60`; a bare `Animator` is faithful for this, since AAP writes and blend-tree evaluation are
standard Unity animator behavior identical to VRChat's FX playable. Tolerance `2e-3`.

| Idiom | Input(s) | Expected | Measured | Result |
|---|---|---|---|---|
| add | A=0.7, B=0.2 | 0.9 | 0.9 | PASS |
| subtract | A=0.7, B=0.2 | 0.5 | 0.5 | PASS |
| multiply | A=0.7, B=0.2 | 0.14 | 0.14 | PASS |
| max (derived) | A=0.7, B=0.2 | 0.7 | 0.7 | PASS |
| min (derived) | A=0.7, B=0.2 | 0.2 | 0.2 | PASS |
| max (crossover) | A=0.2, B=0.7 | 0.7 | 0.7 | PASS |
| min (crossover) | A=0.2, B=0.7 | 0.2 | 0.2 | PASS |
| add — Direct-child only | A=0.7, B=0.2 (Add_1D layer weight 0) | 0.9 | 0.9 | PASS |
| add — 1D-child only | A=0.7, B=0.2 (Add_Direct layer weight 0) | 0.9 | 0.9 | PASS |
| negate | RemapIn=0.5 | −0.5 | −0.5 | PASS |
| remap ([−1,1]→[1,−1]) | RemapIn=−1.0 | 1.0 | 1.0 | PASS |
| clamp (saturate high) | ClampIn=1.5 | 1.0 | 1.0 | PASS |
| clamp (saturate low) | ClampIn=−0.5 | 0.0 | 0.0 | PASS |
| clamp (in-range identity) | ClampIn=0.4 | 0.4 | 0.4 | PASS |
| divide (÷ 1+Input) | DivInput=3 | 0.25 | 0.25 | PASS |
| divide (÷ 1+Input) | DivInput=1 | 0.5 | 0.5 | PASS |
| frametime rig | dt=1/60 | 0.01667 | 0.016667 | PASS |
| frametime rig | dt=1/30 | 0.03333 | 0.033333 | PASS |

The `add` isolation rows drive each idiom alone (zeroing the other layer's weight), confirming
Direct-child and 1D-child both compute `A+B`. The min/max crossover rows (A<B and A>B) confirm the
composed idioms track the true extremum, not just one input.

**Smoothers** (target 1.0, step/λ as authored; sampled by frame):

- **exponential** (`ExpKeep=0.9`) — tracks `1 − 0.9ⁿ` exactly and converges:
  `f1=0.100  f5=0.410  f10=0.651  f20=0.878  f40=0.985  f80=0.9998`.
- **linear** (step 0.1) — clean ramp then ±one-step limit cycle (the known limitation above):
  `f1=0.000  f5=0.400  f10=0.900  f11=1.000  f12=1.100  f14=1.000  f20=1.000  f30=1.100`.
- **frametime rig** — `FrameTime` equals the tick `dt` exactly (0.01667 at dt=1/60, 0.03333 at
  dt=1/30), proving it measures real elapsed frame time, not ~0.
