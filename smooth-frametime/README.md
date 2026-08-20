# smooth-frametime — frametime-aware, clean-settling float smoothing (Pattern, study)

Three float-smoothing constructions over one owned frametime rig: the exponential smoother in two α-flavours (`clamp01`, `remap`) and a constant-velocity-feel **hybrid** that still lands exactly on a static target. Pattern tier — a consumer lifts `controller.yaml` and recompiles it against their own parameters and GUIDs; `built/` is committed only so the graphs read in the Animator window without a compile. Costs no synced bits: every parameter is a local float the consumer decides how to drive.

**Provenance:** generalized from standard VRChat DBT-math smoother constructions (vrc.school Advanced Blend Trees); the λ-by-`IsLocal` selection is a vendor outfit-smoother's idiom, survey-verified, and OSCmooth ships the same fork. No real-avatar naming.

## Ground truth

- Parameters, the two layers, and every tree: `controller.yaml`. It is hand-authored — this entry has no generator — and its header comment is the design record: the author-time-only front-end/smoother split (fold the two layers into one Direct tree if you are counting layers; layer order never bought same-frame data flow), the feed-forward settle, the `directWeight ≥ 0` constraint `blendtree-math` owns and how each construction satisfies it, and the same-frame convexity pairings.
- Both λ constants live in parameter **defaults**, so retuning them is an install-time edit rather than tree surgery.
- Seam: none. Pattern tier is lifted as YAML, and every clip writes an animator parameter rather than a scene binding, so there is nothing to repath.
- Dependencies: none. The frametime rig is owned rather than borrowed from VRCFury's `FrameTimeService`, whose update-ordering contract is undocumented — too fragile a dependency for an entry meant to be lifted into someone else's controller.

## Traps

- **Don't split λ reflexively.** A local/remote λ split is warranted only when the two clients see *genuinely different input*: mostly OSC-driven params, where the wearer's client gets the immediate high-resolution update while remotes receive it capped to ~10 Hz at reduced resolution (bool-encoded or 8-bit-float synced params), and heavier remote smoothing masks that jitter. Absent that input asymmetry one λ is correct, which is why the shipped defaults are **equal** — the split ships as two editable numbers, not as behavior.
- **The hybrid dips below zero on the way to a zero target.** Driving the target down to 0, the descent overshoots one far-step (`maxSpeed·FrameTime`) negative at the crossing before the exponential home recovers. Harmless for inputs kept in `[0,1]`, but the AAP itself carries that one-frame negative: a consumer reading it back as a `directWeight` next frame gets it clamped to 0 by Unity, which is the symptom if the value looks right on a graph and wrong downstream.
- **`remap`'s frametime independence is only as good as its key density.** It holds where the 1D keys sample the operating `RateStep` band densely, so keep them dense across the framerates you drive it at. `clamp01` is the cheaper, honestly framerate-dependent flavour: it linearizes `1 − e^(−x)` and so converges faster the larger the per-frame step, i.e. the lower the fps.

## Behavior

The rig reads `dt` exactly, and the feed-forward pipeline (`Time`→`FrameTime`→`RateStep`→`Alpha*`→`Smoothed*`) takes a few frames to fill after an input change — a smoother's job is lag, so that is intended, not settle error to chase. To re-measure any of it after an edit, host the built controller on a bare `Animator` and tick `Animator.Update(dt)` in edit mode; `docs/emulator.md` §"Pure controller math skips play mode entirely" owns the recipe, and it is how the framerate comparison between the two α-flavours is made — run a matched elapsed window at two `dt`s and compare the steady-state decay ratio.
