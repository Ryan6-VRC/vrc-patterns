# smooth-frametime — frametime-aware, clean-settling float smoothing (Pattern, study)

Three float-smoothing constructions — the exponential smoother in two α-flavours (`clamp01`, `remap`) and a constant-velocity-feel **hybrid** that still lands — over one owned frametime rig. Authored as two cosmetic always-on WD-ON Direct-tree layers: `Smooth/FrameTime` (the shared front-end — the rig plus `RateStep` and both α pairs) and `Smooth/Smoothers` (the three constructions, reading the front-end's AAPs). A convex blend `S = (1−α)·S + α·Target` with `α∈[0,1]` cannot overshoot and both weights are `≥0` by construction, so the one hard `directWeight ≥ 0` constraint (see `blendtree-math`) is satisfied for free.

**The front-end→smoother split is author-time legibility, not runtime structure.** Collapsing the two into a single Direct tree is mechanical — nest the children — and costs no timing, because layer order never bought same-frame data flow in the first place (`docs/gimmicks.md` "Layer order buys no same-frame data flow"). Fold it if you are counting layers. This is Pattern tier: a consumer lifts the YAML and recompiles it with their own params/GUIDs; `built/` is committed only so the graphs are readable without a compile. Generalized from standard VRChat DBT-math smoother constructions (vrc.school Advanced Blend Trees); no real-avatar naming.

## Interface

- **Params (in, float, NOT synced/saved — a consumer decides):** `Target` (the value to chase), `rateLocal` / `rateRemote` (the exponential-rate λ pair, selected by `IsLocal`; `α ≈ 1 − e^(−rate·dt)`; **equal by default — see §λ by IsLocal**), `maxSpeed` (hybrid constant-velocity cap, units/s), `crossover` (hybrid far→near handoff distance — a *live* param: `CrossDiff = crossover − |Δ|`), `IsLocal` (VRC built-in, float-declared for blend-param use), and `One` (a constant helper, never driven — leave at default). **Inputs assumed in `[0,1]`** (the reused clamp/ReLU 1D shapes saturate at 1).
- **Outputs (all AAPs, `aap: true`):** `SmoothedExpClamp`, `SmoothedExpRemap`, `SmoothedHybrid`, plus the owned rig (`Time`/`LastTime`/`FrameTime`) and the intermediates (`RateSelected`, `RateStep`, the `Alpha*`/`OneMinusAlpha*` pairs, `Delta`/`AbsDelta`/`CrossDiff`/`W`/`OneMinusW`/`SignDelta`).
- **Seam:** none shipped (Pattern tier, lifted as YAML). Every clip writes an animator parameter, not a scene binding, so there is nothing to repath. `basis` ↔ MA `pathMode` per `_template`.
- **Dependencies / required assets:** none. Owns its frametime rig rather than borrowing VRCFury's `FrameTimeService` (that service's update-ordering contract is undocumented — fragile for a lifted library entry).

## λ by IsLocal

The rate the smoothers consume is `RateSelected = IsLocal·rateLocal + (1−IsLocal)·rateRemote` — a 1D-on-IsLocal selection stage. Both constants live in param **defaults**, so tuning is an install-time edit, no tree surgery.

**The guard — don't split reflexively.** A local/remote λ split is warranted only when the two clients see *genuinely different input*: mostly OSC-driven params, where the wearer's client gets the immediate high-resolution update while remotes receive it capped to ~10 Hz at reduced resolution (bool-encoded or 8-bit-float synced params) — heavier remote smoothing masks that jitter. Absent that input asymmetry one λ is correct, which is why the shipped defaults are **equal**: the split exists as two editable numbers, not as shipped behavior.

## Behavior

The rig reads `dt` exactly (`FrameTime = 0.016667` at `dt = 1/60`). Every blend param / directWeight is read at frame start, so the feed-forward pipeline (`Time`→`FrameTime`→`RateStep`→`Alpha*`→`Smoothed*`) takes a few frames to fill after an input change. To re-measure after an edit, host the built controller on a bare `Animator` and tick `Animator.Update(dt)` in edit mode — `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe.

**`remap` is frametime-independent; `clamp01` is not.** `remap`'s steady-state decay ratio over a matched elapsed window holds constant across framerates; `clamp01`'s does not, because it linearizes `1−e^(−x)` and so converges faster the larger the per-frame step (i.e. the lower the fps). `remap` trades tree nodes for this precision — its independence holds only as far as its 1D keys sample the operating `RateStep` band densely, so keep them dense where you drive it. `clamp01` is the cheaper, honestly framerate-dependent flavour when exact independence isn't needed.

**The hybrid reaches and holds a static target exactly** (the near-term collapses to the same-frame exponential once the crossover weight `w→1`). Driving the target down to zero, the descent dips one far-step (`maxSpeed·FrameTime`) below zero at the crossing before the exponential home recovers. That transient is harmless for inputs kept in `[0,1]`, but a consumer chasing a hard-zero target should know it exists — the AAP itself carries the one-frame negative, and reading it back as a `directWeight` next frame gets it clamped to 0 by Unity.
