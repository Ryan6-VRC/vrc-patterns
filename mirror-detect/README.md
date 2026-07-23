# mirror-detect — real local copy, mirror clone, or remote? (Pattern, study)

One FX layer, zero synced bits, no scene objects: `MirrorDetection/IsMirror` reads **−1** on the real local avatar, **+1** on the mirror clone, and **parks at its declared default** on every remote (0 as shipped). The race: the real local copy evaluates first — `DetectMirror` still false → `NotMirror` writes −1 and a `localOnly` driver flips `DetectMirror`; the mirror clone instantiates later **with copied parameter values and no driver execution** → forks straight to `Mirror`. Remotes never enter the local branch and nothing ever writes their copy.

Build with it: anything that must behave differently on your own body than in the mirror — a manual head chop that must never shrink your head in mirrors or photos (`head-proxy`), mirror-side scale compensation for a gimmick whose chopped parent exists only outside the mirror (`head-deform`), wearer-only control widgets that shouldn't render on the mirror clone.

**Provenance:** the standard parameter-driver race (VRLabs lineage); extracted from this library's proxy-head rig, where it previously shipped embedded.

## Interface

- **Params:** `MirrorDetection/IsMirror` (float AAP, out; −1/0/+1) — never synced, never menu-exposed; it stays listed in the params asset deliberately, as the output a consumer reads. `MirrorDetection/DetectMirror` (bool, scratch) — race residue, out of the params asset. **Never saved**: a persisted `true` routes the next session's real local copy to `Mirror` permanently. The `MirrorDetection/*` namespace is the name consumers read — it is deliberately not renamed to match this entry's folder.
- **Seam:** none shipped (Pattern tier). Consume either by lifting the layer whole into your controller YAML, or by referencing `built/MirrorDetect_Fx.controller` as an additional controller row in a VRCFury `FullController`. The second form is what enables **variant-by-controller-omission**: a variant that omits the row parks `IsMirror` at its declared default, which selects that consumer branch permanently — defaults-as-configuration, no controller fork (`gimmicks.md` §Packaging).
- **Dependencies:** none beyond the `IsLocal` builtin.
- **Required assets:** none.

## Behavior

The three-valued contract, and what each leg rests on:

- **−1 (real local):** provable in the emulator as a hard transition condition on a consumer — a state gated `IsMirror less 0` engaging at all is the proof (the proxy rig's fake chop uses exactly this). Lands within the first frames: Init → Fork → NotMirror is two buffer-clip hops.
- **parked (remote):** the remote copy parks in `Remote` off `IsLocal` alone and never writes the param — a remote reads whatever default the merged declarations land on, and a consumer may deliberately re-declare `IsMirror` with default 1 so remotes take the mirror clone's branch (both lack a first-person chop; `head-deform` does exactly this). Design consumer branches so **only the driven −1 is special** — every plausible parked value (0 or 1) then lands on the remote-correct branch, and no framework default-merge subtlety is load-bearing.
- **+1 (mirror clone):** rests on the client's clone semantics (copied parameters, no driver execution). The emulator's mirror clone is a transform-copy puppet, so this leg is an in-game check (`docs/verify.md` owns the boundary).

Re-measure after an edit: emulator play mode, drive locally, read `IsMirror` at a pause after a few frames (−1), then on a second client or in-game confirm mirror-side behavior via a gated consumer rather than reading the param.
