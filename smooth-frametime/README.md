# smooth-frametime — frametime-aware, clean-settling float smoothing (Pattern, study)

Three float-smoothing constructions — the exponential smoother in two α-flavours (`clamp01`, `remap`)
and a constant-velocity-feel **hybrid** that still lands — over one owned frametime rig. Authored as two
cosmetic always-on WD-ON Direct-tree layers: `Smooth/FrameTime` (the shared front-end — the rig plus
`RateStep` and both α pairs) and `Smooth/Smoothers` (the three constructions, reading the front-end's
AAPs). Opening one tree in the Animator window reads one concern with named nodes and value-named clips.
A convex blend `S = (1−α)·S + α·Target` with `α∈[0,1]` cannot overshoot and both weights are `≥0` by
construction, so the one hard `directWeight ≥ 0` constraint (see `blendtree-math`) is satisfied for free.

**Layers are author-time legibility, not runtime structure** (`docs/gimmicks.md`, the bullet of that
name): both dominant FX optimizers flatten always-on Direct-tree layers into one tree on upload, and an
AAP is invisible to every reader until the next frame whether they share a tree or sit in different
layers. The front-end→smoother split is therefore a legibility choice, not a correctness requirement —
timing is identical to the same math in a single tree; the only differences are sub-`1e-5`
float-summation-order artifacts, far inside the `2e-3` bar. Every blend param / directWeight is
read at frame start, so a feed-forward chain of depth D fills over ~D frames after an input change (the
settle table's first ~3 zero rows). The exponential's `S`-reads-itself is the *intended* one-frame
recurrence, not a defect; the hybrid's near-term reads `SmoothedHybrid`/`Target` as blend params **inside**
the tree that writes `SmoothedHybrid` (materializing the near-next-state as a separate AAP would add a
second feedback frame and limit-cycle — the caveat `blendtree-math`'s linear smoother demonstrates). This
is Pattern tier: a consumer lifts the YAML and recompiles it with their own params/GUIDs; `built/` is
committed only so the graphs are readable without a compile. Generalized from standard VRChat DBT-math
smoother constructions (vrc.school Advanced Blend Trees); no real-avatar naming.

## Interface

- **Params (in, float, NOT synced/saved — a consumer decides):** `Target` (the value to chase),
  `rate` (exponential rate; `α ≈ 1 − e^(−rate·dt)`), `maxSpeed` (hybrid constant-velocity cap,
  units/s), `crossover` (hybrid far→near handoff distance — a *live* param: `CrossDiff = crossover −
  |Δ|`), and `One` (a constant helper, never driven — leave at default). **Inputs assumed in `[0,1]`**
  (the reused clamp/ReLU 1D shapes saturate at 1).
- **Outputs (all AAPs, `aap: true`):** `SmoothedExpClamp`, `SmoothedExpRemap`, `SmoothedHybrid`, plus
  the owned rig (`Time`/`LastTime`/`FrameTime`) and the intermediates (`RateStep`, the
  `Alpha*`/`OneMinusAlpha*` pairs, `Delta`/`AbsDelta`/`CrossDiff`/`W`/`OneMinusW`/`SignDelta`).
- **Seam:** none shipped (Pattern tier, lifted as YAML). Every clip writes an animator parameter, not a
  scene binding, so there is nothing to repath. `basis` ↔ MA `pathMode` per `_template`.
- **Dependencies / required assets:** none. Owns its frametime rig rather than borrowing VRCFury's
  `FrameTimeService` (that service's update-ordering contract is undocumented — fragile for a lifted
  library entry).

## Measured behavior

Proven by compiling the built controller to a fresh-GUID scratch copy, hosting it on a bare `Animator`,
and ticking `Animator.Update(dt)` in **edit mode** — no play mode (`docs/verify.md` → "Pure controller
math skips play mode entirely"). `SetFloat` inputs, `GetFloat` AAP outputs. Faithful because AAP writes
and blend-tree evaluation are stock Unity, identical to the FX playable. Tolerance `2e-3`. The rig reads
`dt` exactly (`FrameTime = 0.016667` at `dt = 1/60`).

### Settle table — `dt = 1/60`, `Target` stepped 0 → 1

| frame | `ExpClamp` | `ExpRemap` | `Hybrid` |
|---|---|---|---|
| f1–f3 | 0.000000 | 0.000000 | 0.000000 |
| f5  | 0.100000 | 0.095163 | 0.033333 |
| f10 | 0.468559 | 0.451190 | 0.200000 |
| f20 | 0.814698 | 0.798105 | 0.533333 |
| f40 | 0.977472 | 0.972677 | 1.000000 |
| f80 | 0.999667 | 0.999500 | 1.000000 |
| f150 | 1.000000 | 1.000000 | 1.000000 |

The first ~3 frames are 0 — the feed-forward pipeline (`Time`→`FrameTime`→`RateStep`→`Alpha*`→`Smoothed*`)
filling. The hybrid reaches `Target` fastest (constant `maxSpeed` step far from target, then exp home).

### No overshoot (exp)

Across the whole 0→1 ramp neither exp curve exceeds `Target=1`: **max `ExpClamp` = 1.000000**, **max
`ExpRemap` = 1.000000**. Convexity is a same-frame property, so it survives a lag spike — under a
jittered `dt` (§Robustness) the maxima stay `1.000000` / `1.000000`. No frame overshoots.

### Frametime-independence — warm residual ratio

**The metric is the warm (steady-state) residual ratio, not from-zero absolute values.** Ticking from 0
to a matched wall-clock elapsed conflates two things: the exponential's steady decay *and* the ~3-frame
feed-forward startup fill (the settle table's zero rows) — and that fill costs a fixed number of *frames*,
so its *wall-clock* cost scales with `dt` and shows up as a framerate-dependent offset that has nothing to
do with the smoother's steady behavior. It would make an honestly-independent construction look divergent.
The honest measure isolates the steady state: warm the pipeline, then measure how the residual
`(Target − S)` decays over a matched elapsed window. For a genuinely frametime-independent smoother the
ratio `(1−S @1.0 s)/(1−S @0.5 s)` equals `e^(−rate·0.5) = e^(−3) = 0.049787` at *any* framerate (the
per-frame factor `e^(−rate·dt)` composes to `e^(−rate·τ)`). `Target=1`, rate 6:

| dt | `remap` ratio | `clamp01` ratio |
|---|---|---|
| 1/60 | 0.049782 | 0.042391 |
| 1/30 | 0.049779 | 0.035186 |
| 1/12 | 0.049786 | 0.015625 |

**`remap` is frametime-independent** — spread **7e-6** across 60/30/12 fps — measurement-floor noise, far
inside tolerance. **`clamp01` is the first-order contrast** — spread **2.7e-2**, visibly framerate-*dependent*
(it linearizes `1−e^(−x)`, so it converges faster the larger the per-frame step, i.e. the lower the fps).

`remap`'s independence is exact to the 1D's sampling accuracy, and the shipped **12-key** set
(`0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1, 1.5, 2, 3, 4`) samples the convex `1−e^(−x)` / `e^(−x)` densely
where it bends hardest, so the per-frame decay factor matches the true exponential — exact at the test
framerates, which land on keys:

| dt | `RateStep` | `AlphaRemap` | true `1−e^(−rs)` | `OneMinusAlphaRemap` | true `e^(−rs)` |
|---|---|---|---|---|---|
| 1/60 | 0.1 | 0.095163 | 0.095163 | 0.904837 | 0.904837 |
| 1/30 | 0.2 | 0.181269 | 0.181269 | 0.818731 | 0.818731 |
| 1/12 | 0.5 | 0.393469 | 0.393469 | 0.606531 | 0.606531 |

The `Alpha`+`OneMinusAlpha` pair sums to 1 every frame (the convexity trap is handled) *and* tracks the
true exponential. `remap` trades tree nodes for precision — its frametime-independence is real but bounded
by 1D key density, so keys must be dense in the operating `RateStep` band. `clamp01` is the cheaper,
honestly-framerate-*dependent* flavour when exact independence isn't needed.

### Hybrid landing

Static `Target=1`, 400 frames: `SmoothedHybrid = 1.000000`, **residual 0.000000** — it reaches and holds
(the near-term is the same-frame exponential, so a stale `w→1` reduces to pure exp home). Driving
`Target 1 → 0` (`maxSpeed=2`, `crossover=0.1`):

`f1=0.900004  f10=0.456105  f20=0.122774  f30=0.000000  … f200=0.000000`

**Near-zero low-end quirk (expected):** the descent dips to a **min of −0.033333** before settling at
`0.000000` — exactly one far-step (`maxSpeed·FrameTime = 2/60 = 0.0333`) of overshoot past zero at the
crossing, then the exp home recovers. The AAP itself carries that one-frame negative; read back as a
`directWeight` next frame Unity clamps it to 0 (the low-end distortion `blendtree-math`'s linear smoother
documents). Harmless for inputs in `[0,1]`, but a consumer chasing a hard-zero target should know the
transient exists.

### Robustness

- **Jittered `dt`** (alternating `1/60` and a `1/8` spike, `Target=1`): exp never overshoots — max
  `ExpClamp` / `ExpRemap` = `1.000000` / `1.000000`, both settle to `1.000000`. Convexity is same-frame,
  so a hitch cannot push past target.
- **Hold-then-step** (`Target=0` held 30 f, then stepped to 1, `dt=1/60`): all three sit at `0.000000`
  during the hold, then track sanely and monotonically — `f5 [C=0.409510 R=0.393471 H=0.377234]`,
  `f20 [C=0.878423 R=0.864666 H=0.877233]`, `f40 [C=0.985219 R=0.981685 H=0.999782]`; post-step maxima
  `C=0.998203`, `R=0.997522` (no overshoot).
