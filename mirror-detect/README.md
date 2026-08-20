# mirror-detect — real local copy, mirror clone, or remote? (Pattern, study)

One FX layer, zero synced bits, no scene objects, and a three-valued output a consumer branches on to behave one way on your own body, another in the mirror, and a third on everyone else's screen. Build with it: a manual head chop that must never shrink your head in mirrors or photos (`head-proxy`), mirror-side scale compensation for a gimmick whose chopped parent exists only outside the mirror (`head-deform`), wearer-only control widgets that should not render on the mirror clone.

**Provenance:** the standard parameter-driver race (VRLabs lineage); extracted from this library's proxy-head rig, where it previously shipped embedded.

## Ground truth

- The three values, the driver race that produces them, and each parameter's sync / scratch / saved status: `controller.yaml`, whose header is the design record.
- **Consume it one of two ways** — lift the layer whole into your own controller YAML, or reference `built/MirrorDetect_Fx.controller` as an additional controller row in a VRCFury `FullController`. Pattern tier: nothing here merges itself, and no prefab publishes a name.
- The second form is what enables **variant-by-controller-omission**: a variant that omits the row parks `IsMirror` at its declared default, which selects that consumer branch permanently — defaults-as-configuration, no controller fork (`gimmicks.md` §Packaging).
- `MirrorDetection/*` is the namespace consumers read, deliberately not renamed to match this entry's folder. It is the published interface even though no artifact declares it as one, so a rename unbinds every consumer's conditions with nothing to warn on.

## Traps

- **Design consumer branches so only the driven −1 is special.** A remote never enters the local branch and nothing ever writes its copy, so it reads whatever default the merged declarations land on — and a consumer may deliberately re-declare `IsMirror` with default 1 so remotes take the mirror clone's branch (both lack a first-person chop; `head-deform` does exactly this). Make every plausible parked value (0 or 1) land on the remote-correct branch and no framework default-merge subtlety is load-bearing.

## Behavior

What each leg of the three-valued contract rests on, and how far a check reaches:

- **−1 (real local)** is provable in the emulator as a hard transition condition on a consumer — a state gated `IsMirror less 0` engaging at all is the proof (the proxy rig's fake chop uses exactly this). It lands within the first frames: Init → Fork → NotMirror is two buffer-clip hops.
- **parked (remote)** is the absence of a write, so the only observable is the consumer's branch, and the trap above is what makes that observation meaningful.
- **+1 (mirror clone)** rests on the client's clone semantics (copied parameters, no driver execution), and is an in-game check. The emulator's MirrorReflection clone does run its animator and so does take this branch, but `IsMirror` is a clip-written AAP and the emulator's AAP readback door attaches to the **local** runtime only — there is no channel that reads a clone's AAP, which is what makes this leg in-game rather than the clone being inert (`docs/emulator.md` owns the boundary).

Re-measure after an edit: emulator play mode, drive locally, read `IsMirror` at a pause after a few frames (−1), then on a second client or in-game confirm mirror-side behavior via a gated consumer rather than reading the param.
