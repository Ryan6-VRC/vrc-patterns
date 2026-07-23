# contact-tracker — latching proximity tracker (Module)

The building block for anything that interacts with **another player's body**. VRChat won't let you constrain to another avatar's transform, so a contact receiver is the only channel to a point on someone else — and this turns that channel into a usable tracked position. Aim it at any contact tag (the shipped prefabs track a hand and a head); latch a prop, a follower, or a marker to it. It tracks with **zero synced position**: 6 coincident Proximity receivers acquire the target, an animated `allowOthers`-shut latches onto it, and a crawler-servo position constraint chases the latched sender. Every client re-derives the cage locally, so the tracked position never crosses the wire — and therefore **never late-syncs**: a late joiner sees the cage at home until it re-acquires. `Container` is the consumer surface — constrain your payload to it and replace `Marker`.

**Provenance:** generalized from a private production avatar's contact tracker (itself a VRCFury conversion of VRLabs Contact-Tracker, MIT). Vestigial Size motion-time bindings and orphaned transitions not ported.

Two prefabs, one controller:

- `ContactTracker.prefab` — sphere probes, tag `Hand` (the generic point tracker).
- `ContactTracker_Head.prefab` — variant: capsule probes (`height 8` → 1.2 m tall at acquisition scale), tag `Head`. Generous height absorbs per-avatar auto head-contact placement variance.

## Interface

- **Params:** `ContactTracker/Enable` (bool, in) — synced, unsaved; off is the reset (recalls the cage to `HomeAnchor/Offset`). `HomeAnchor` is an MA BoneProxy (Hips, AsChildAtRoot) so home follows the wearer instead of loading at the avatar-root origin — the floor; retarget the proxy or adjust `Offset` (ships 0.1 up, 0.35 forward of the hips) to move home. Anchoring by BoneProxy is safe here **only because** no clip path runs through `HomeAnchor` — it is referenced purely as a constraint source, which survives the build-time reparent. The six `ContactTracker/{X,Y,Z}±` floats are sensing — never synced, never menu-exposed.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController merges `built/ContactTracker_Fx_Parameters.asset` (`prms`); `ContactTracker/Enable` rides `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** Modular Avatar (the `HomeAnchor` proxy); **compose `anti-cull` alongside** (its README §When a module needs this) — the re-derivation below runs only while a remote client evaluates the wearer's animator, which is why VRLabs ships the same mechanism inside its tracker prefabs. Receivers are `localOnly: 0` **by necessity** — remote clients run the tracker to re-derive the cage; flipping them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in the scale constraint makes the tracking cage absolute-meters (avatar-scale-immune). Do not instantiate or delete it.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Measured behavior |
|---|---|---|
| Acquisition scale | 0.15 (TrackingPoints localScale) | sphere: latch ≤0.12 m radial, miss ≥0.30. capsule: latch ≤0.55 axial / ≤0.12 radial, miss ≥0.75 / ≥0.30 |
| Tracking scale | ×3 absolute (VRCScaleConstraint ScaleOffset) | proximity falloff = receiver radius × 3 = 3 m for both shapes (radius alone sets the falloff length — height just extends the capsule axis, not the falloff; see `runtime.md` §Contacts); steady-state probe reading ≈ 0.517 |
| Probe spread | ±0.5 local (tracking clip) | ±1.5 m world in tracking; sets the step-response limit below |
| Settle dwell | 1.0 s park-brake hold (tracking clip) | brake=1 damps the acquisition transient (smooth traverse, no leapfrog); releases as a snap at 1.0 s. Length is network-feel-tunable — **in-game wear-test owns it**; the emulator cannot discriminate values |
| Loss / acquire thresholds | all six <0.00001 / >0 | loss → freeze in place (fail-visible), filters reopen, cage recollapses |

## Verifying the install

With Enable off the cage must sit at `HomeAnchor/Offset`, on the wearer; finding it at the avatar-root origin means the BoneProxy never resolved. Enable on, then put a scripted `Hand` sender (`docs/verify.md`) in the cage: all six floats leave zero together and `allowOthers` shuts on every probe. A partial latch means the acquisition scale no longer suits this avatar's contact placement.

Two clients in-game, not the emulator: remote-side receiver firing (clones never simulate contacts), chase feel under real IK, and whether the settle dwell is right.

## Traps

- **Step-response envelope.** The crawler's target is the proximity-weighted centroid of the probe positions, so it converges only on targets moving continuously (or jumping ≲ the 1.5 m world probe offset — a 1.0 m hop converges, 2.5 m diverges). On loss the constraint's sum-normalized weights can kick the cage one probe-offset (≈4.5 m) in a stale direction before the freeze lands — benign for a receding hand (the stale direction points at the hand), visible with teleporting targets. Cycle Enable to recall a stranded cage.
- **A fully-broken latched contact cannot re-latch** (filters are checked at acquisition only), so a probe whose sender left its range mid-track drops out of the servo permanently until the next Searching pass.
- **Editing the rig:** a VRC constraint with `GlobalWeight 0` drives its transform to its captured `*AtRest` pose — it is not a no-op (only zero *source-weight sum* writes nothing). Setting `Locked` by script does not capture rest poses; set `*AtRest` fields explicitly.
