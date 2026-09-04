# smooth-frametime — frametime-aware, clean-settling float smoothing (Pattern, study)

Three float-smoothing constructions over one owned frametime rig: an exponential smoother in two α-flavours (`clamp01`, `remap`) and a constant-velocity-feel **hybrid** that still lands exactly on a static target. All are always-on cosmetic Direct-tree math, nothing synced or saved, so a consumer pays no synced bit. Pattern tier — lift the YAML and recompile with your own params/GUIDs; `built/` ships only so the graphs read in the animator window.

## Provenance

Generalized from standard VRChat DBT-math smoother constructions (vrc.school Advanced Blend Trees); the `IsLocal`-selected λ pair is a vendor outfit-smoother idiom (survey-verified; OSCmooth ships the same fork). No real-avatar naming.

## Ground truth

The three outputs `SmoothedExpClamp` / `SmoothedExpRemap` / `SmoothedHybrid` are AAPs; inputs are assumed in `[0,1]`; the λ pair and every other tunable lives in a param **default**, so tuning is an install-time edit with no tree surgery. A convex blend cannot overshoot and every weight is `≥0` by construction, so `blendtree-math`'s one hard `directWeight ≥ 0` constraint holds here for free. No seam and no dependencies: every clip writes an animator parameter, not a scene binding, so there is nothing to repath.

**The two-layer split (`Smooth/FrameTime` front-end, `Smooth/Smoothers`) is author-time legibility, not runtime structure.** Collapsing them into one Direct tree is mechanical — nest the children — and costs no timing, because layer order never bought same-frame data flow (`docs/gimmicks.md` "Layer order buys no same-frame data flow"). Fold it if you are counting layers. The rig is owned rather than borrowed from VRCFury's `FrameTimeService`, whose update-ordering contract is undocumented and fragile for a lifted entry.

## Traps

**Don't split λ reflexively.** `RateSelected` picks `rateLocal` or `rateRemote` by `IsLocal`, but both defaults ship **equal**. A split is warranted only when the two clients see genuinely different input — mostly OSC-driven params, where the wearer's client gets the immediate high-resolution update while remotes receive it capped to ~10 Hz at reduced resolution, so heavier remote smoothing masks that jitter. Absent that input asymmetry one λ is correct; the split exists as two editable defaults, not as shipped behavior.

## Behavior

**`remap` is frametime-independent; `clamp01` is not.** `remap`'s steady-state decay ratio over a matched elapsed window holds constant across framerates; `clamp01` linearizes `1−e^(−x)` and so converges faster the larger the per-frame step (the lower the fps). `remap`'s independence holds only as far as its 1D keys sample the operating `RateStep` band densely — keep them dense where you drive it. `clamp01` is the cheaper, honestly framerate-dependent flavour when exact independence isn't needed.

**The hybrid reaches and holds a static target exactly**, but driving the target down to zero dips one far-step (`maxSpeed·FrameTime`) below zero at the crossing before the exponential home recovers. That transient is harmless for inputs kept in `[0,1]`; a consumer chasing a hard-zero target should know the AAP itself carries the one-frame negative, and reading it back as a `directWeight` next frame gets it clamped to 0 by Unity.

**Re-measuring after an edit.** Every blend param is read at frame start, so the feed-forward pipeline takes a few frames to fill after an input change. Host the built controller on a bare `Animator` and tick `Animator.Update(dt)` in edit mode — `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe.
