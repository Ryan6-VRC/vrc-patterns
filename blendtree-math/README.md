# blendtree-math — the Direct-Blend-Tree math idiom catalog (Pattern, study)

The DBT-math primitives an agent reaches for when a gimmick needs arithmetic on animator floats
without a scripted behaviour: add (two idioms), subtract, multiply, negate/remap, clamp, divide, the
composed min/max, and the exponential/linear smoothing and frametime family. The catalog is organized
into four **concern-layers** — `Math/Arithmetic`, `Math/MinMax`, `Math/Smoothing`, `Math/FrameTime` —
each an always-on WD-ON Direct root tree whose named children are that concern's idioms, so opening one
tree in the Animator window reads one concern with named nodes and value-named clips, no other graphs in
the view.

**Layers are author-time legibility, not runtime structure** (`docs/gimmicks.md`, the bullet of that
name): both dominant FX optimizers flatten always-on Direct-tree layers into one tree on upload, and an
AAP is invisible to every reader until the next frame whether they share a tree or sit in different
layers — so layer structure never affected the math and the flatten is behavior-preserving. min/max is
authored as one tree purely for readability (see the settle below). This is Pattern tier: a consumer lifts
the YAML and recompiles it in their own project with their own params/GUIDs; `built/` is committed only
so the graphs are readable without a compile. Generalized from standard VRChat DBT-math constructions
(vrc.school Advanced Blend Trees); no real-avatar naming.

## Interface

- **Params:** generic float inputs, drivable (not synced/saved here — a consumer decides that):
  `A`/`B` (shared inputs for add/subtract/multiply/min/max, working range `[0,1]`), `RemapIn`
  (`[-1,1]`), `ClampIn`, `DivInput` (`>=0`), `SmoothTarget` + `ExpKeep`/`ExpMix` (exponential smoothing),
  `LinTarget` (linear smoothing), and `One` (a constant helper, never driven — leave it at its default).
  Outputs are all AAPs (`aap: true`, written by a clip curve, not synced): the two add idioms write
  **distinct** outputs `SumDirect` (Direct-child) and `Sum1D` (1D-child), plus `DiffOut`, `ProdOut`,
  `NegOut`, `ClampOut`, `DivOut`, `MaxOut`, `MinOut`, `SmoothedExp`, `SmoothedLin`, `Time`, `LastTime`,
  `FrameTime`, the composed min/max intermediates (`MaxDiff`/`MaxRelu`, `MinDiff`/`MinRelu`), the
  linear-smoothing intermediate (`LinDelta`), and one throwaway (`DivDummy`).
- **Seam:** none shipped — this is Pattern tier, lifted as YAML. Every clip writes an animator parameter,
  not a scene property, so there are no bindings to repath; a consumer imports the layers they want and
  renames the generic params to their own naming.
- **Dependencies / required assets:** none. Only animator parameters and blend trees — no shader, mesh,
  or package dependency (contrast `color-adjust`, which depends on the target material's shader).

## The one hard constraint

A parameter used as a Direct blend tree's `directWeight` is clamped to `>=0` by Unity — only a clip's
authored curve *value* may carry a negative sign. Every idiom is shaped around that: `A`/`B` and the
genuine clamp0 outputs (`MaxRelu`, `MinRelu`) are used directly as weights; a genuinely signed
intermediate (`MaxDiff`, `MinDiff`, `LinDelta`) is instead read back through a 1D tree, whose blend
*parameter* — unlike a Direct weight — is never clamped. (`SmoothedLin` looks `>=0` but isn't quite — see
the linear-smoother limitation below, a live instance of why this rule exists.)

## Coverage

| Concern-layer | Node | Idiom |
|---|---|---|
| `Math/Arithmetic` | `Add (Direct child)` → `SumDirect` | Direct-child (canonical, higher precision, positive-only) |
| | `Add (1D child)` → `Sum1D` | 1D-child (lower precision; `[0,1]` thresholds clamp negatives, so signed inputs need signed thresholds like `Negate/Remap`'s) — **distinct output, runs live beside the Direct one for comparison** |
| | `Subtract` → `DiffOut` | Direct-child, sign baked into the clip constant |
| | `Multiply` → `ProdOut` | nested Direct trees (positive-only) |
| | `Divide` → `DivOut` | Normalize Blend Values + a weight-1 dummy child (divides by `1 + Input`, not `Input`) |
| | `Negate/Remap` → `NegOut` | 1D tree's own clamp-and-lerp math *is* the remap |
| | `Clamp` → `ClampOut` | 1D natural saturation to `[0,1]`; shape reused as min/max's `ReLU` stage |
| `Math/MinMax` | `Max` = `A−B` → `ReLU` → `b + ReLU(a−b)` → `MaxOut` | `max(a,b) = b + clamp0(a-b)` |
| | `Min` = `B−A` → `ReLU` → `b − ReLU(b−a)` → `MinOut` | `min(a,b) = b - clamp0(b-a)` |
| `Math/Smoothing` | `Exponential` → `SmoothedExp` | single Direct tree; mirrors the `smoother` fixture — settles cleanly, framerate-dependent by design |
| | `Linear` → `SmoothedLin` | fixed per-frame step, clamped delta — **limit-cycles by ±one step, see below** |
| `Math/FrameTime` | `Time Ramp` + `FrameTime = Time − LastTime` → `FrameTime` | `tangents: linear` ramp + `FrameTime = Time - LastTime` |

## The frametime rig is owned, not borrowed

VRCFury ships a `FrameTimeService` that can supply a frametime parameter for free. This entry does
**not** use it: that service is lazy-initialized and cached with no documented contract on when it
updates relative to a consumer's own layers, which makes depending on it fragile for a library entry
meant to be lifted into an arbitrary project. The `Time Ramp` clip and the `FrameTime = Time − LastTime`
calc are self-contained, so the rig works regardless of what else is in the FX controller. As siblings in
one tree the calc reads `Time` at frame start — a one-frame-old `dt` — which still equals the true `dt`
exactly at a steady frame rate. Borrowing VRCFury's service is a deliberate, non-default choice a
consumer can make for their own build.

Neither smoother is wired to `FrameTime` here (one concern per node): to make either frame-rate
independent, scale its per-frame step by `FrameTime` using the `Multiply` idiom before adding it in.

## min/max settle over ~3 frames

`Max`/`Min` are derived, not primitive, and their three stages (`diff → ReLU → recombine`) are siblings
in one tree, so each reads the previous stage's AAP at **frame start** — last frame's write. An input
change therefore propagates one stage per frame and the output settles at frame ~3, steady-state exact.
Measured (`A=0.7, B=0.2`, so `max=0.7`; the input change lands at frame 1):

```
frame     1      2      3
MaxDiff   0.50   0.50   0.50
MaxRelu   0.00   0.50   0.50
MaxOut    0.20   0.20   0.70   ← steady
```

This settle is intrinsic — one frame per AAP hop, independent of layer structure or optimization; the
upload-time flatten changes nothing about it (`docs/gimmicks.md`). It is invisible for the uses this math
serves — a value a few frames behind a slider reads as instant. (Only the branch whose difference is
positive settles; the
other branch's `ReLU` is 0 from frame 1, so its output is exact immediately — see the crossover rows.)

## Known limitation: the linear smoother limit-cycles (does not fully settle)

The linear smoother ramps cleanly toward the target at a fixed step, then **oscillates by ±one step
around it forever** — it never settles. This is inherent: the clamped step needs a *computed* delta
(`LinTarget − SmoothedLin`), and a blend tree can't both produce a value and consume it as a blend
parameter in the same frame, so the step always acts on a **one-frame-stale delta**. Near the target that
stale ±step keeps pushing a full step past it, then back. Measured with step `0.1`: `SmoothedLin` reaches
`1.0` at frame 11, then cycles `1.0 ↔ 1.1`.

Near a **zero** target the cycle dips `SmoothedLin` slightly negative. This idiom, for simplicity, uses
`SmoothedLin` as a `directWeight` (the carry and the delta's negative term), and Unity clamps a negative
weight to 0 — so the low end distorts. `SmoothedLin` is thus **not** a guaranteed-`>=0` weight: a value
that *looks* non-negative but a feedback loop nudges below zero, then a Direct weight silently clamps it —
a live instance of the hard constraint above. To carry a truly signed smoothed value, read it through a
1D tree (as the signed intermediates do) instead of self-weighting.

The **exponential smoother has no such loop** and settles cleanly, because it feeds `SmoothedExp` and
`SmoothTarget` *directly* as blend parameters — no computed intermediate, no delay. That pairing is the
study lesson. The cycle is intrinsic to the one-frame delay and can't be tuned away; three mitigations,
none free: a **smaller step** tightens the band and slows the ramp; a **`FrameTime`-scaled step**
normalizes it across framerates but still cycles; if you need a value that truly holds, **prefer the
exponential smoother**.

## Verified behavior

Measured by hosting the built controller on an `Animator` and ticking it deterministically at
`dt = 1/60` (frametime rows also at `1/30`); a bare `Animator` is faithful, since AAP writes and
blend-tree evaluation are standard Unity animator behavior identical to VRChat's FX playable. Single-hop
idioms are exact the frame their inputs change; the derived rows are steady-state after their settle.
Tolerance `2e-3`.

| Idiom | Input(s) | Expected | Measured | Result |
|---|---|---|---|---|
| add (Direct child → `SumDirect`) | A=0.7, B=0.2 | 0.9 | 0.9000 | PASS |
| add (1D child → `Sum1D`) | A=0.7, B=0.2 | 0.9 | 0.9000 | PASS |
| subtract | A=0.7, B=0.2 | 0.5 | 0.5000 | PASS |
| multiply | A=0.7, B=0.2 | 0.14 | 0.1400 | PASS |
| divide (÷ 1+Input) | DivInput=3 | 0.25 | 0.2500 | PASS |
| divide (÷ 1+Input) | DivInput=1 | 0.5 | 0.5000 | PASS |
| negate | RemapIn=0.5 | −0.5 | −0.5000 | PASS |
| remap ([−1,1]→[1,−1]) | RemapIn=−1.0 | 1.0 | 1.0000 | PASS |
| clamp (saturate high) | ClampIn=1.5 | 1.0 | 1.0000 | PASS |
| clamp (saturate low) | ClampIn=−0.5 | 0.0 | 0.0000 | PASS |
| clamp (in-range identity) | ClampIn=0.4 | 0.4 | 0.4000 | PASS |
| max (derived) | A=0.7, B=0.2 | 0.7 | 0.7000 (frame 3) | PASS |
| min (derived) | A=0.7, B=0.2 | 0.2 | 0.2000 | PASS |
| max (crossover) | A=0.2, B=0.7 | 0.7 | 0.7000 | PASS |
| min (crossover) | A=0.2, B=0.7 | 0.2 | 0.2000 (frame 3) | PASS |
| frametime rig | dt=1/60 | 0.016667 | 0.01667 | PASS |
| frametime rig | dt=1/30 | 0.033333 | 0.03333 | PASS |

The min/max crossover rows (A<B and A>B) confirm the composed idioms track the true extremum, not just
one input, and show that the settling branch is whichever difference is positive.

**Smoothers** (target 1.0, step/λ as authored; sampled by frame):

- **exponential** (`ExpKeep=0.9`) — tracks `1 − 0.9ⁿ` exactly and converges:
  `f1=0.100  f5=0.410  f10=0.651  f20=0.878  f40=0.985  f80=0.9998`.
- **linear** (step 0.1) — clean ramp then ±one-step limit cycle (the known limitation above):
  `f1=0.000  f5=0.400  f10=0.900  f11=1.000  f12=1.100  f14=1.000`.
