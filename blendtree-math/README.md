# blendtree-math — the Direct-Blend-Tree math idiom catalog (Pattern, study)

The DBT-math primitives an agent reaches for when a gimmick needs arithmetic on animator floats without a scripted behaviour — add (two idioms), subtract, multiply, divide, negate/remap, clamp, the composed min/max, the smoothing family, and an owned frametime rig — organized into four **concern-layers** (`Math/Arithmetic`, `Math/MinMax`, `Math/Smoothing`, `Math/FrameTime`), each an always-on WD-ON Direct root tree whose named children are that concern's idioms. The four layers are author-time legibility, not runtime structure: collapsing them into one Direct tree is mechanical (nest the children) and costs no timing, because layer order never bought same-frame data flow (`docs/gimmicks.md` "Layer order buys no same-frame data flow"). Pattern tier — a consumer lifts the YAML, recompiles it with their own params/GUIDs, and `built/` is committed only so the graphs read without a compile.

**Provenance:** generalized from standard VRChat DBT-math constructions (vrc.school Advanced Blend Trees); no real-avatar naming.

## Ground truth

The four idiom families share one hard constraint: a parameter used *as* a Direct `directWeight` is clamped `>=0` by Unity, so signed intermediates are read back through a 1D tree whose blend parameter is never clamped; the ~3-frame min/max settle and the linear smoother's limit-cycle are both the one-frame AAP hop showing through. No seam ships (Pattern tier); every clip writes an animator parameter, not a scene property, so there are no bindings to repath — a consumer renames the generic params. No shader, mesh, or package dependency (contrast `color-adjust`).

## Traps

- **The frametime rig is owned, not borrowed.** This entry computes `FrameTime` itself instead of using VRCFury's `FrameTimeService`, which is lazy-initialized with no documented update-order contract — fragile for a library entry meant to be lifted into an arbitrary project. Neither smoother is wired to `FrameTime` here: to make either frame-rate independent, scale its per-frame step by `FrameTime` with the `Multiply` idiom before adding it in.

## Behavior

Each idiom's output at `dt = 1/60`; single-hop arithmetic idioms are exact the frame their inputs change, while the derived min/max settle over ~3 frames on the branch whose difference is positive. To re-measure after an edit, host the built controller on a bare `Animator` and tick it in edit mode — `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe. Baselines:

| Idiom | Input(s) | Output |
|---|---|---|
| divide (÷ 1+Input) | DivInput=3 | 0.2500 |
| remap ([−1,1]→[1,−1]) | RemapIn=−1.0 | 1.0000 |
| max (derived) | A=0.7, B=0.2 | 0.7000 (frame 3) |
