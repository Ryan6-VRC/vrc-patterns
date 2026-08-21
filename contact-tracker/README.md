# contact-tracker — latching proximity tracker (Module)

The building block for anything that interacts with **another player's body** — VRChat won't let you constrain to another avatar's transform, so a contact receiver is the only channel to a point on someone else. It tracks with **zero synced position**: 6 coincident Proximity receivers acquire the target, an animated `allowOthers`-shut latches onto it, and a crawler-servo position constraint chases the latched sender, every client re-deriving the cage locally so the tracked position never crosses the wire and **never late-syncs** — a late joiner sees the cage at home until it re-acquires. `Container` is the consumer surface — constrain your payload to it and replace `Marker`. For a single tracked point `box-tracker` reconstructs an exact position instead of this servo; for a player's **head** use `drop-on-player`.

**Provenance:** generalized from a private production avatar's contact tracker (itself a VRCFury conversion of VRLabs Contact-Tracker, MIT).

## Ground truth

`controller.yaml` owns the Reset/Searching/Tracking machine, the crawler servo, and every tuned constant (values at their sites). `ContactTracker/Enable` (bool, synced, unsaved) rides `globalParams` with a VRCFury `Toggle` (`useGlobalParam`) as the menu front; off is the reset, recalling the cage to `HomeAnchor/Offset`. The six `ContactTracker/{X,Y,Z}±` floats are sensing — never synced, never menu-exposed.

- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root`, so clip paths bind relative to the prefab root and the internal hierarchy names are load-bearing.
- **`HomeAnchor` is an MA BoneProxy (Hips, `AsChildAtRoot`); anchoring by BoneProxy is safe here *only because* no clip path runs through `HomeAnchor`** — it is referenced purely as a constraint source, which survives the build-time reparent.
- **The upload-only sourceless `FreezeToWorld` GO** (VRCFury `ApplyDuringUpload`, inactive in editor) pins the module frame to world — without it the cage composes with avatar root motion (the twin `box-tracker` documents).
- **`assets/World.prefab`** is a never-instantiated scale reference; sourcing it in the scale constraint makes the cage absolute-meters (avatar-scale-immune). Do not instantiate or delete it.
- **Compose `anti-cull` alongside** (its README §Traps): the re-derivation runs only while a remote client evaluates the wearer's animator. Receivers are `localOnly: 0` **by necessity** — remote clients run the tracker to re-derive the cage, so flipping them local-only breaks remote copies silently. Depends on Modular Avatar.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Knob |
|---|---|---|
| Acquisition scale | `TrackingPoints` rest `localScale` + the scale constraint's `ScaleAtRest`, both (`GlobalWeight 0` drives to `ScaleAtRest`) | latch radius ∝ the scale |
| Tracking scale | ×3 absolute (VRCScaleConstraint `ScaleOffset`) | falloff = receiver radius × 3; radius alone sets it (`runtime.md` §Contacts) |
| Probe spread | ±0.5 local (tracking clip) | ±1.5 m world in tracking; sets the step-response limit below |
| Settle dwell | the `tracking` clip's `source6` (park-brake) hold length | network-feel-tunable — **in-game wear-test owns it**; the emulator cannot discriminate values |
| Loss / acquire thresholds | all six <0.00001 / >0 | loss → freeze in place (fail-visible), filters reopen, cage recollapses |

## Traps

- **Step-response envelope.** The crawler's target is the proximity-weighted centroid of the probe positions, so it converges only on targets moving continuously, or jumping less than roughly the 1.5 m world probe offset. On loss the constraint's sum-normalized weights kick the cage up to one probe-offset (1.5 m) in a stale direction before the freeze lands — benign for a receding hand, visible with teleporting targets. Cycle Enable to recall a stranded cage. Displacement off this rig is per rendered frame, not per second — pin `Application.targetFrameRate` before reading it (`verify.md`).
- **A fully-broken latched contact cannot re-latch** (filters are checked at acquisition only), so a probe whose sender left its range mid-track drops out of the servo permanently until the next Searching pass.
- **Editing the rig:** the `GlobalWeight 0` drive-to-rest and script-set-`Locked` capture-nothing traps live in `runtime.md` §Constraints — set `*AtRest` fields explicitly when rebuilding.

## Verifying the install

With Enable off the cage must sit at `HomeAnchor/Offset`, on the wearer; finding it at the avatar-root origin means the BoneProxy never resolved. Enable on, then put a scripted `Hand` sender (`docs/emulator.md`) in the cage: all six floats leave zero together and `allowOthers` shuts on every probe. A partial latch means the acquisition scale doesn't suit this avatar's contacts.

Two clients in-game, not the emulator: remote-side receiver firing, chase feel under real IK, and whether the settle dwell is right.
