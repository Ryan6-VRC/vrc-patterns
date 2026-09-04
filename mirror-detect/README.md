# mirror-detect — real local copy, mirror clone, or remote? (Pattern, study)

One FX layer, zero synced bits, no scene objects: a three-valued signal that tells the real local avatar from its mirror clone from every remote. Build it into anything that must behave differently on your own body than in the mirror — a head chop that must never shrink your head in mirrors or photos (`head-proxy`), mirror-side scale compensation for a gimmick whose chopped parent exists only outside the mirror (`head-deform`), wearer-only widgets that shouldn't render on the mirror clone.

**Provenance:** the standard parameter-driver race (VRLabs lineage); extracted from this library's proxy-head rig.

## Ground truth

`MirrorDetection/IsMirror` (float AAP) is the output a consumer reads — **−1** real local, **+1** mirror clone, **parked at its declared default** on remotes (0 as shipped); `MirrorDetection/DetectMirror` (bool) is race residue, scratch, out of the params asset. `IsMirror` stays listed in the params asset deliberately — it is the signal consumers read — and the `MirrorDetection/*` namespace is that consumer-facing name, deliberately not renamed to match this folder.

## Traps

- **Never save `DetectMirror`.** A persisted `true` routes the next session's real local copy to `Mirror` permanently.
- **Consume by lifting the layer whole, or by referencing `built/MirrorDetect_Fx.controller` as a controller row in a VRCFury `FullController`.** The second form enables **variant-by-controller-omission**: a variant that omits the row parks `IsMirror` at its declared default, which selects that consumer branch permanently — defaults-as-configuration, no controller fork (`gimmicks.md` §Packaging and interface).
- **Design consumer branches so only the driven −1 is special.** A remote never writes the param and reads whatever the merged declarations default to, so make every plausible parked value (0 or 1) land on the remote-correct branch — then no framework default-merge subtlety is load-bearing. A consumer may re-declare `IsMirror` with default 1 so remotes take the mirror clone's branch (both lack a first-person chop; `head-deform` does exactly this).

## Behavior

- **−1 (real local)** is provable in the emulator as a hard transition condition on a consumer: a state gated `IsMirror less 0` engaging at all is the proof (the proxy rig's fake chop uses exactly this). It lands within the first frames.
- **+1 (mirror clone)** is an in-game check, not an emulator one. The emulator's MirrorReflection clone does run its animator and take this branch, but `IsMirror` is a clip-written AAP and the emulator's AAP readback attaches to the **local** runtime only — no channel reads a clone's AAP (`docs/emulator.md` owns the boundary).

Re-measure after an edit: emulator play mode, drive locally, read `IsMirror` at a pause after a few frames (−1); then on a second client or in-game confirm mirror-side behavior via a gated consumer rather than reading the param.
