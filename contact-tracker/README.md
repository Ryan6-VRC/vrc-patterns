# contact-tracker — latching proximity tracker (Module tier)

Tracks one point on another player with zero synced position: 6 coincident Proximity receivers
acquire, an animated `allowOthers` shut latches, and a crawler-servo position constraint chases
the latched sender. Every client re-derives the cage locally, so the tracked position never
crosses the wire — and therefore **never late-syncs**: a late joiner sees the cage at home until
it re-acquires. `Container` is the consumer surface — constrain your payload to it and replace
`Marker`.

**Provenance:** generalized from a Remy project's `ContactTracker_Fx` (itself a VRCFury conversion
of VRLabs Contact-Tracker, MIT). Vestigial Size motion-time bindings and orphaned transitions not ported.

Two prefabs, one controller:

- `ContactTracker.prefab` — sphere probes, tag `Hand` (the generic point tracker).
- `ContactTracker_Head.prefab` — variant: capsule probes (`height 8` → 1.2 m tall at acquisition
  scale), tag `Head`. Generous height absorbs per-avatar auto head-contact placement variance.

## Interface

- **Params:** `ContactTracker/Enable` (bool, in) — synced, unsaved; off is the reset (recalls the
  cage to `HomeAnchor`). The six `ContactTracker/{X,Y,Z}±` floats are sensing — never synced,
  never menu-exposed.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind
  relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController
  merges `built/ContactTracker_Fx_Parameters.asset` (`prms`); `ContactTracker/Enable` rides
  `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** none. Receivers are `localOnly: 0` **by necessity** — remote clients run the
  tracker to re-derive the cage; flipping them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in
  the scale constraint makes the tracking cage absolute-meters (avatar-scale-immune). Do not
  instantiate or delete it.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Measured behavior |
|---|---|---|
| Acquisition scale | 0.15 (TrackingPoints localScale) | sphere: latch ≤0.12 m radial, miss ≥0.30. capsule: latch ≤0.55 axial / ≤0.12 radial, miss ≥0.75 / ≥0.30 |
| Tracking scale | ×3 absolute (VRCScaleConstraint ScaleOffset) | proximity falloff = receiver radius × 3 = 3 m for both shapes (SDK source: capsule proximity = distance to the axis *segment* normalized by radius — height extends the axis, radius alone sets falloff); steady-state probe reading ≈ 0.517 |
| Probe spread | ±0.5 local (tracking clip) | ±1.5 m world in tracking; sets the step-response limit below |
| Settle dwell | 1.0 s park-brake hold (tracking clip) | brake=1 damps the acquisition transient (smooth traverse, no leapfrog); releases as a snap at 1.0 s. Length is network-feel-tunable — **in-game wear-test owns it**; the emulator cannot discriminate values |
| Loss / acquire thresholds | all six <0.00001 / >0 | loss → freeze in place (fail-visible), filters reopen, cage recollapses |

## Verified (emulator) and handed off (in-game)

Emulator-proven in batched sessions: full lifecycle Reset → Searching → latch → chase
(converges to 0.000 m on a continuously moving sender) → lock (a second in-range sender is
ignored) → loss-freeze → re-acquire → Enable-off recall. `ApplyDuringUpload` enables the
world-freeze root at build. Both variants' acquisition geometry bracketed as above.

Needs two clients in-game (emulator boundary, `docs/verify.md`): remote-side receiver firing
(the clone's rig, receivers, and replicated Enable were verified present; the emulator does not
simulate contacts on non-local clones), real-IK chase feel, and the dwell length.

## Traps

- **Step-response envelope.** The crawler's target is the proximity-weighted centroid of the
  probe positions, so it converges only on targets moving continuously (or jumping ≲ the 1.5 m
  world probe offset — a 1.0 m hop converges, 2.5 m diverges). On loss the constraint's
  sum-normalized weights can kick the cage one probe-offset (≈4.5 m) in a stale direction before
  the freeze lands — benign for a receding hand (the stale direction points at the hand),
  visible with teleporting targets. Cycle Enable to recall a stranded cage.
- **A fully-broken latched contact cannot re-latch** (filters are checked at acquisition only),
  so a probe whose sender left its range mid-track drops out of the servo permanently until the
  next Searching pass.
- **Editing the rig:** a VRC constraint with `GlobalWeight 0` drives its transform to its
  captured `*AtRest` pose — it is not a no-op (only zero *source-weight sum* writes nothing).
  Setting `Locked` by script does not capture rest poses; set `*AtRest` fields explicitly.
