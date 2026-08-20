# contact-tracker — latching proximity tracker (Module)

The building block for anything that interacts with **another player's body** — VRChat won't let you constrain to another avatar's transform, so a contact receiver is the only channel to a point on someone else. It tracks with **zero synced position**: 6 coincident Proximity receivers acquire the target, an animated `allowOthers`-shut latches onto it, and a crawler-servo position constraint chases the latched sender, every client re-deriving the cage locally so the tracked position never crosses the wire and **never late-syncs** — a late joiner sees the cage at home until it re-acquires. `Container` is the consumer surface — constrain your payload to it and replace `Marker`.

**Provenance:** generalized from a private production avatar's contact tracker (itself a VRCFury conversion of VRLabs Contact-Tracker, MIT).

One prefab, one controller: `ContactTracker.prefab` — sphere probes, tag `Hand`. For a player's **head**, use `drop-on-player` instead — its box-tracker cage carries a head-catch zone and payload.

## Ground truth

- Parameters and behavior: `controller.yaml`. The set published to the host avatar: the prefab's VRCFury `FullController` `globalParams`. Everything else about the rig, including the `HomeAnchor` BoneProxy wiring (Hips, AsChildAtRoot; retarget the proxy or adjust its `Offset` child to move home): `ContactTracker.prefab`.
- Anchoring `HomeAnchor` by BoneProxy is safe here **only because** no clip path runs through it — it is referenced purely as a constraint source, which survives the build-time reparent.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController merges `built/ContactTracker_Fx_Parameters.asset` (`prms`); `ContactTracker/Enable` rides `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** Modular Avatar (the `HomeAnchor` proxy); **compose `anti-cull` alongside** (its README §When a module needs this) — the re-derivation below runs only while a remote client evaluates the wearer's animator. Receivers are `localOnly: 0` **by necessity** — remote clients run the tracker to re-derive the cage; flipping them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in the scale constraint makes the tracking cage absolute-meters (avatar-scale-immune). Do not instantiate or delete it. The upload-only sourceless `FreezeToWorld` GO (VRCFury `ApplyDuringUpload`, targeting the module root) pins the module frame to world — without it the cage composes with avatar root motion; leave it inactive in editor (`box-tracker`'s README documents its twin).

## Empirical constants (90% rule — test before changing)

| Constant | Value | Knob |
|---|---|---|
| Acquisition scale | `TrackingPoints` rest `localScale` + the scale constraint's `ScaleAtRest`, both (GlobalWeight 0 drives to `ScaleAtRest`) | radial latch distance ∝ the scale — larger scale widens the latch radius |
| Tracking scale | ×3 absolute (VRCScaleConstraint ScaleOffset) | falloff length = receiver radius × 3; radius alone sets it (see `runtime.md` §Contacts) |
| Probe spread | ±0.5 local (tracking clip) | ±1.5 m world in tracking; sets the step-response limit below |
| Settle dwell | the `tracking` clip's `source6` (park-brake) hold-then-drop curve — its hold length | network-feel-tunable — **in-game wear-test owns it**; the emulator cannot discriminate values |
| Loss / acquire thresholds | all six <0.00001 / >0 | loss → freeze in place (fail-visible), filters reopen, cage recollapses |

## Verifying the install

With Enable off the cage must sit at `HomeAnchor/Offset`, on the wearer; finding it at the avatar-root origin means the BoneProxy never resolved. Enable on, then put a scripted `Hand` sender (`docs/emulator.md`) in the cage: all six floats leave zero together and `allowOthers` shuts on every probe. A partial latch means the acquisition scale doesn't suit this avatar's contact placement.

Two clients in-game, not the emulator: remote-side receiver firing, chase feel under real IK, and whether the settle dwell is right.

## Traps

- **Step-response envelope.** The crawler's target is the proximity-weighted centroid of the probe positions, so it converges only on targets moving continuously, or jumping less than roughly the 1.5 m world probe offset. On loss the constraint's sum-normalized weights kick the cage up to one probe-offset (1.5 m) in a stale direction before the freeze lands — benign for a receding hand, visible with teleporting targets. Cycle Enable to recall a stranded cage.
- **Displacement figures are per rendered frame, not per second.** Pin `Application.targetFrameRate` before reading displacement off this rig (`verify.md`).
- **A fully-broken latched contact cannot re-latch** (filters are checked at acquisition only), so a probe whose sender left its range mid-track drops out of the servo permanently until the next Searching pass.
- **Editing the rig:** the `GlobalWeight 0` drive-to-rest and script-set-`Locked` capture-nothing traps live in `runtime.md` §Constraints — set `*AtRest` fields explicitly when rebuilding.
