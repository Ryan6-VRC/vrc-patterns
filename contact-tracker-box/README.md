# contact-tracker-box — 4-box face-proximity tracker (Module tier)

The low-contact-budget sibling of `contact-tracker`: **4 face-proximity box receivers** replace the
6-sphere cage, and an **absolute readout** replaces the crawler servo. The ±X box pair gives the
sender's x from the reading *difference* (sender radius cancels) and its radius from the *sum*; the
single Y+/Z+ boxes are radius-compensated with that measurement. The reconstruction is linear in
the four readings, so it lives in one non-normalized direct blend tree writing `Output`'s
localPosition — exact in a single step, no convergence dynamics, no step-response envelope.
`Container` is the consumer surface — constrain your payload to it and replace `Marker`.

Same tag (`Hand`), same latch (`allowOthers` 1→0 shut at acquisition), same zero-position-sync
model as `contact-tracker`: every client re-derives the cage locally, nothing late-syncs. **The
trade for exactness + budget is range**: the working volume is a fixed **±1.5 m core** around the
world-frozen deployment point — the volume does not chase. Inside it, tracking is exact; outside
it, loss.

**Provenance:** `contact-tracker` (G5b) structure + the G5d box-contact probe. Probe (SDK 3.10.4,
397-point sweep, sender radii 0.05/0.10/0.20): 4-box reconstruction worst-case error **0.0000 m**
(radius estimate also exact); 6-sphere one-shot centroid worst case 1.21 m over the same grid.
Face proximity projects the sender center onto the +Z face *plane* (infinite laterally) and
unlerps linearly across the box depth — axis-separable by construction, radius purely additive
(`ContactManager` source; `runtime.md` §Contacts).

One prefab, one controller: `ContactTrackerBox.prefab`.

## Interface

- **Params:** `ContactTrackerBox/Enable` (bool, in) — synced, unsaved; off is the reset (recalls
  `Container` to the rig origin). The four `ContactTrackerBox/{X+,X-,Y+,Z+}` floats are sensing —
  never synced, never menu-exposed. `ContactTrackerBox/One` is a scratch constant (DBT carrier
  weight), excluded from the params asset.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind
  relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController
  merges `built/ContactTrackerBox_Fx_Parameters.asset` (`prms`); `ContactTrackerBox/Enable` rides
  `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** none. Receivers are `localOnly: 0` **by necessity** — remote clients run the
  tracker to re-derive the cage; flipping them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in
  the scale constraint makes the deployed cage absolute-meters (avatar-scale-immune). Do not
  instantiate or delete it.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Measured behavior |
|---|---|---|
| Acquisition scale | 0.15 (TrackingPoints localScale) | boxes 0.9×0.9×0.45 m, all-four core ≈ ±0.225 m: latch ≤0.20 m axial, miss ≥0.30 (edge = 0.225 + sender radius) |
| Tracking scale | ×1 absolute (VRCScaleConstraint ScaleOffset, World.prefab source) | boxes 6×6×3 m, faces at ±1.5 m; working core \|x\|,\|y\|,\|z\| ≤ 1.5 m; all four read strictly >0 inside it |
| Readout coefficients | 1.5 / 3 (readout_* clips) | derived from face position 1.5 m and depth 3 m — re-derive together if the box geometry changes. The readout is uniform-scale-invariant (readings are geometry ratios), so exactness holds even at acquisition scale; the constraint pins *range* |
| Loss / acquire thresholds | any <0.00001 / all four >0 | ANY-loss (vs contact-tracker's ALL): one dead box breaks the reconstruction, so partial reads never hold Tracking |

## Verified (emulator) and handed off (in-game)

Emulator-proven (Av3Emulator, VRCFury play build): full lifecycle Reset → Searching → latch
(filters shut) → **exact off-center track** (error 0.0000 m at (0.9, −0.7, 1.1) — not
self-parked) → a second in-range sender ignored → ANY-loss at the face boundary → filters
reopen/recollapse/recall → re-acquire → Enable-off recall (no latch while off, sender in core) →
Reset→Tracking resume edge → world-freeze (volume stays put under avatar motion, tracking stays
exact). Acquisition boundary bracketed as above.

Needs two clients in-game (emulator boundary, `docs/verify.md`): remote-side receiver firing, and
the **capsule-sender bias** — real hand/finger senders are capsules, which read a constant offset
toward the near surface, bounded by the capsule's segment half-length projected per axis (probe:
0.07–0.14 m with an oversized 0.3 m capsule; a few cm for a real hand collider). Constant, not
jitter.

## Traps

- **Range is a hard box.** The volume freezes in world space at deployment; a target (or wearer
  drift) beyond ±1.5 m of that point is loss, not degradation. There is no crawl. If you need
  roaming range, use `contact-tracker`.
- **The readout coefficients and the box geometry are one unit.** The DBT clips encode face
  position/depth; scaling or resizing the tracking boxes without re-deriving `readout_*` silently
  skews the reconstruction. The acquisition scale (`TrackingPoints` localScale) is the safe
  prefab-level knob — the readout is scale-invariant, and the World.prefab constraint pins the
  deployed geometry regardless.
- **Latch-frame transient.** Readings sampled in the 1–2 sim ticks around the deploy scale flip
  can momentarily mix scales; the Output settles within ~2 frames (60 Hz contact sim — settle by
  time, not frames, when scripting against it).
- **Editing the rig:** VRC constraint `Sources` is a **struct** — `Sources.Add()` on a retrieved
  copy silently serializes nothing; assign through `SerializedObject` (`Sources.source0.*`,
  `Sources.totalLength`) and set `IsActive` explicitly.
