# blendtree-math — the Direct-Blend-Tree math idiom catalog (Pattern, study)

The DBT-math primitives an agent reaches for when a gimmick needs arithmetic on animator floats without a scripted behaviour, organized into four **concern-layers** — `Math/Arithmetic`, `Math/MinMax`, `Math/Smoothing`, `Math/FrameTime` — each an always-on WD-ON Direct root tree whose named children are that concern's idioms.

**The four concern-layers are author-time legibility, not runtime structure.** Collapsing them into a single Direct tree is mechanical — nest the children — and costs no timing, because layer order never bought same-frame data flow in the first place (`docs/gimmicks.md` "Layer order buys no same-frame data flow"). Fold them if you are counting layers. This is Pattern tier: a consumer lifts the YAML and recompiles it in their own project with their own params/GUIDs; `built/` is committed only so the graphs are readable without a compile. Generalized from standard VRChat DBT-math constructions (vrc.school Advanced Blend Trees); no real-avatar naming.

## Interface

- **Params:** generic float inputs (not synced/saved — a consumer decides): `A`/`B` (shared inputs for add/subtract/multiply/min/max, working range `[0,1]`), `RemapIn` (`[-1,1]`), `ClampIn`, `DivInput` (`>=0`), `SmoothTarget` + `ExpKeep`/`ExpMix` (exponential smoothing), `LinTarget` (linear smoothing), and `One` (a constant helper, never driven — leave it at its default). Outputs (all AAPs, `aap: true`, not synced): `SumDirect`, `Sum1D`, `DiffOut`, `ProdOut`, `NegOut`, `ClampOut`, `DivOut`, `MaxOut`, `MinOut`, `SmoothedExp`, `SmoothedLin`, `Time`, `LastTime`, `FrameTime`, the composed min/max intermediates (`MaxDiff`/`MaxRelu`, `MinDiff`/`MinRelu`), the linear-smoothing intermediate (`LinDelta`), and one throwaway (`DivDummy`).
- **Seam:** none shipped (Pattern tier, lifted as YAML). Every clip writes an animator parameter, not a scene property, so there are no bindings to repath; a consumer imports the layers they want and renames the generic params to their own naming.
- **Dependencies / required assets:** none. Only animator parameters and blend trees — no shader, mesh, or package dependency (contrast `color-adjust`, which depends on the target material's shader).

## The one hard constraint

A parameter used as a Direct blend tree's `directWeight` is clamped to `>=0` by Unity — only a clip's authored curve *value* may carry a negative sign. Every idiom is shaped around that: `A`/`B` and the genuine clamp0 outputs (`MaxRelu`, `MinRelu`) are used directly as weights; a genuinely signed intermediate (`MaxDiff`, `MinDiff`, `LinDelta`) is instead read back through a 1D tree, whose blend *parameter* — unlike a Direct weight — is never clamped. (`SmoothedLin` looks `>=0` but isn't quite — see the linear-smoother limitation below.)

## Coverage

| Concern-layer | Node | Idiom |
|---|---|---|
| `Math/Arithmetic` | `Add (Direct child)` → `SumDirect` | Direct-child (canonical, higher precision, positive-only) |
| | `Add (1D child)` → `Sum1D` | 1D-child (lower precision; needed for signed inputs, since Direct-child thresholds clamp negatives) |
| | `Subtract` → `DiffOut` | Direct-child, sign baked into the clip constant |
| | `Multiply` → `ProdOut` | nested Direct trees (positive-only) |
| | `Divide` → `DivOut` | Normalize Blend Values + a weight-1 dummy child (divides by `1 + Input`, not `Input`) |
| | `Negate/Remap` → `NegOut` | 1D tree's own clamp-and-lerp math *is* the remap |
| | `Clamp` → `ClampOut` | 1D natural saturation to `[0,1]`; shape reused as min/max's `ReLU` stage |
| `Math/MinMax` | `Max` = `A−B` → `ReLU` → `b + ReLU(a−b)` → `MaxOut` | `max(a,b) = b + clamp0(a-b)` |
| | `Min` = `B−A` → `ReLU` → `b − ReLU(b−a)` → `MinOut` | `min(a,b) = b - clamp0(b-a)` |
| `Math/Smoothing` | `Exponential` → `SmoothedExp` | single Direct tree; settles cleanly, framerate-dependent by design |
| | `Linear` → `SmoothedLin` | fixed per-frame step, clamped delta — **limit-cycles by ±one step, see below** |
| `Math/FrameTime` | `Time Ramp` + `FrameTime = Time − LastTime` → `FrameTime` | `tangents: linear` ramp + `FrameTime = Time - LastTime` |

## The frametime rig is owned, not borrowed

This entry computes `FrameTime` itself instead of using VRCFury's `FrameTimeService`, which is lazy-initialized with no documented update-order contract — fragile for a library entry meant to be lifted into an arbitrary project. Neither smoother is wired to `FrameTime` here: to make either frame-rate independent, scale its per-frame step by `FrameTime` using the `Multiply` idiom before adding it in.

## min/max settle over ~3 frames

`Max`/`Min`'s three stages (`diff → ReLU → recombine`) are siblings in one tree, each reading the previous stage's AAP from last frame, so an input change settles at frame ~3 on the branch whose difference is positive; the other branch's `ReLU` is 0 from frame 1, so it is exact immediately.

## Known limitation: the linear smoother limit-cycles (does not fully settle)

The linear smoother ramps toward the target at a fixed step, then oscillates by ±one step around it forever — it never settles, because the clamped step acts on a one-frame-stale delta (`LinTarget − SmoothedLin`). Near a zero target the cycle dips `SmoothedLin` slightly negative; since this idiom uses `SmoothedLin` as a `directWeight`, Unity clamps that dip to 0, distorting the low end — a live instance of the hard constraint above. To carry a truly signed smoothed value, read it through a 1D tree instead of self-weighting. The exponential smoother has no such loop, because it feeds `SmoothedExp` and `SmoothTarget` directly as blend parameters with no computed intermediate; prefer it when a value must truly settle.

## Behavior

Each idiom's output at `dt = 1/60`. Single-hop idioms are exact the frame their inputs change. To re-measure after an edit, host the built controller on a bare `Animator` and tick it in edit mode — `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe.

| Idiom | Input(s) | Output |
|---|---|---|
| divide (÷ 1+Input) | DivInput=3 | 0.2500 |
| remap ([−1,1]→[1,−1]) | RemapIn=−1.0 | 1.0000 |
| max (derived) | A=0.7, B=0.2 | 0.7000 (frame 3) |
