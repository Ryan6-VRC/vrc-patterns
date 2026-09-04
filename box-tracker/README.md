# box-tracker — 4-box face-proximity crawler (Module)

Make a payload follow one point on another player, one target at a time, reconstructed to an **exact absolute position**: 4 face-proximity box receivers replace `contact-tracker`'s 6-sphere cage, and an exact linear readout replaces its crawler-servo convergence. For a single tracked point (the usual want), this generally supersedes `contact-tracker`. The readings feed a non-normalized direct blend tree that writes `Output`'s localPosition, and a position constraint on `TrackingPoints` — sourcing `Output`, its own child, the documented-legal feedback loop (`runtime.md` §Constraints) — crawls the cage to follow it; same latch and zero-position-sync model as `contact-tracker`. `Container` is the consumer surface — constrain your payload to it and replace `Marker`.

**Provenance:** `contact-tracker`'s structure (three-state rig, park/self-hold/crawl constraint trio) with box receivers replacing the spheres. The readout is exact over the working core.

## Ground truth

A VRCFury `Toggle` (`useGlobalParam`) is the menu front; `Enable` off is the reset and the recall, parking the cage at `HomeAnchor/Offset` on the wearer.

- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root`, so clip paths bind relative to the prefab root and the internal hierarchy names are load-bearing. `built/BoxTracker_Fx_Parameters.asset` merges via `prms`.
- **Home:** `HomeAnchor` is an MA BoneProxy (Hips, `AsChildAtRoot`); retarget the proxy or drag its `Offset` child to move home.
- **`assets/World.prefab`** is a never-instantiated scale reference; sourcing it in the scale constraint makes the tracking cage absolute-meters (avatar-scale-immune). Do not instantiate or delete it.
- **The upload-only sourceless `FreezeToWorld` GO** (VRCFury `ApplyDuringUpload`) pins the module frame to world — without it the cage composes with avatar root motion; leave it inactive in editor.
- **Compose `anti-cull` alongside** (its README §Traps): the re-derivation runs only while a remote client evaluates the wearer's animator. Receivers are `localOnly: 0` **by necessity** — remote clients run the tracker to re-derive the cage, and flipping them local-only breaks remote copies silently. Depends on Modular Avatar.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Knob |
|---|---|---|
| Acquisition cube | `TrackingPoints` rest `localScale` + the scale constraint's `ScaleAtRest`, both (`GlobalWeight 0` drives to `ScaleAtRest`, so `localScale` alone is display-only); the receiver GOs collapse to one coincident cube while not tracking | host-GO scale widens the zone |
| Tracking scale | ×1 absolute (VRCScaleConstraint `ScaleOffset`, World.prefab source) | not a knob — defines the working core: the cage half-extent in absolute metres, fixed by the readout coefficients in `controller.yaml` |
| Crawl gain | prefab `TrackingPoints/VRCPositionConstraint` `source0` (Output) against `source1` (self), **and** the `latch` clip's `source0` curve — **two homes that must agree** | lower `source0` for a floatier follow, raise it toward a locked-on snap; retune in the clip, not the running scene — it owns `source0` during Tracking, so a WD-on frame overwrites the inspector |
| Loss / acquire thresholds | the proximity comparisons on the Tracking and Searching edges in `controller.yaml` — acquire on all four positive, lose on any one hitting an epsilon floor | ANY-loss (vs `contact-tracker`'s ALL): one dead box breaks the reconstruction, so partial reads never hold Tracking |

**Copy site — `drop-on-player`** embeds this tracker rig and carries its own copy of every row it does not re-tune, so a retune here lands half the homes. That entry's constants table marks which rows it takes from here.

## Traps

- **`Output` leads the sender while the cage is moving.** The DBT writes `Output` from readings sampled against the pre-crawl cage, then the constraint moves the cage the same frame. Payloads read `Container` (the crawl-smoothed cage position), never `Output`; scripting against `Output` should settle by time, not frames.
- **Loss while crawling is a freeze, not a recall.** ANY-loss drops to Searching: the cage self-holds where it stands (fail-visible), filters reopen, and the cube recollapses at the stranded spot — a sender re-entering that cube relatches in place, or cycle Enable to recall. A teleporting target produces a clean loss with no kick, unlike `contact-tracker`'s always-on servo layer. A fully-broken latched contact cannot re-latch (filters check at acquisition only).
- **The readout coefficients and the box geometry are one unit.** The DBT clips encode face position/depth; resizing the tracking boxes without re-deriving `readout_*` silently skews the reconstruction. The zone knob (`TrackingPoints` rest scale) is safe — the readout is scale-invariant — but keep zones uniform: a non-uniform zone skews the first latch frame's radius compensation for one frame.
- **Contact shape fields don't animate.** `size`/`radius`/`position`/`rotation` and most plumbing are `[NotKeyable]` — the binder drops the curves silently, and script writes to shape fields need `UpdateShape()`. Resize contacts by host-GO transform scale, nothing else. For self-use, retag to a single hand (`HandR`) — the inflated slabs otherwise pick up both of the wearer's hands.
- **Editing the rig:** the script-built-constraint traps (boxed `Sources` writes, default-false `IsActive`, `GlobalWeight 0` driving to rest) live in `runtime.md` §Constraints — write through `SerializedObject`.

## Verifying the install

With Enable off, walk: cage and `Container` must ride the wearer at `HomeAnchor/Offset` — finding them at the avatar-root origin means the BoneProxy never resolved. Enable on, then put a scripted `Hand` sender (`docs/emulator.md`) inside the acquisition cube: the four floats leave zero together, filters shut, the slabs expand, and `Output` sits on the sender exactly while the cage eases onto it. Drag the sender away at walking speed: the cage must follow, with the latch held.

Two clients in-game, not the emulator: remote-side receiver firing, chase feel under real IK, and the **capsule-sender bias** — real hand senders are capsules, which read a constant offset toward the near surface (a few cm; constant, not jitter).
