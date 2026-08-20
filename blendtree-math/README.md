# blendtree-math — the Direct-Blend-Tree math idiom catalog (Pattern, study)

The DBT-math primitives an agent reaches for when a gimmick needs arithmetic on animator floats without a scripted behaviour, organized into four **concern-layers** — `Math/Arithmetic`, `Math/MinMax`, `Math/Smoothing`, `Math/FrameTime` — each an always-on WD-ON Direct root tree whose named children are that concern's idioms.

**The four concern-layers are author-time legibility, not runtime structure.** Collapsing them into a single Direct tree is mechanical — nest the children — and costs no timing, because layer order never bought same-frame data flow in the first place (`docs/gimmicks.md` "Layer order buys no same-frame data flow"). Fold them if you are counting layers. This is Pattern tier: a consumer lifts the YAML and recompiles it in their own project with their own params/GUIDs; `built/` is committed only so the graphs are readable without a compile. Generalized from standard VRChat DBT-math constructions (vrc.school Advanced Blend Trees); no real-avatar naming.

## Ground truth

- Parameters, working ranges, and outputs: `controller.yaml` — every input and output is commented at its declaration site.
- **Seam:** Pattern tier — nothing shipped; lifted as YAML. Every clip writes an animator parameter, not a scene property, so there are no bindings to repath; a consumer imports the layers they want and renames the generic params to their own naming.
- **Dependencies / required assets:** only animator parameters and blend trees — no shader, mesh, or package dependency (contrast `color-adjust`, which depends on the target material's shader).

## The one hard constraint

A parameter used as a Direct blend tree's `directWeight` is clamped to `>=0` by Unity; every idiom below is shaped around that one fact. The full derivation — which outputs are safe to reuse as weights and which must round-trip through a 1D tree's unclamped blend parameter instead — is `controller.yaml`'s header comment ("THE ONE HARD CONSTRAINT").

## Coverage

| Concern-layer | Node | Idiom |
|---|---|---|
| `Math/Arithmetic` | `Add (Direct child)` → `SumDirect` | Direct-child (canonical, higher precision, positive-only) |
| | `Add (1D child)` → `Sum1D` | 1D-child (lower precision; its own `[0,1]` thresholds clamp a negative input to 0 — the Direct-child form has no thresholds at all, so there it is the raw `directWeight` Unity clamps, `controller.yaml:38-40`) |
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

`Max`/`Min` are derived, not primitive, so an input change takes ~3 frames to reach the recombined output; `controller.yaml`'s header ("SAME-FRAME vs SETTLE") derives why from the three sibling stages.

## Known limitation: the linear smoother limit-cycles (does not fully settle)

The linear smoother never settles — it oscillates by ±one step around its target forever, and near a zero target the dip lands negative and gets clamped as a `directWeight` (a live instance of the hard constraint above), distorting the low end. `controller.yaml`'s header ("LINEAR SMOOTHING LIMIT-CYCLES") has the full derivation. The exponential smoother has no such loop; prefer it when a value must truly settle.

## Behavior

Each idiom's output at `dt = 1/60`. Single-hop idioms are exact the frame their inputs change. To re-measure after an edit, host the built controller on a bare `Animator` and tick it in edit mode — `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe.

| Idiom | Input(s) | Output |
|---|---|---|
| divide (÷ 1+Input) | DivInput=3 | 0.2500 |
| remap ([−1,1]→[1,−1]) | RemapIn=−1.0 | 1.0000 |
| max (derived) | A=0.7, B=0.2 | 0.7000 (frame 3) |
