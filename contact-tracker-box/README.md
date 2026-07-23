# contact-tracker-box — 4-box face-proximity crawler (Module tier)

The low-contact-budget sibling of `contact-tracker`: **4 face-proximity box receivers** replace the
6-sphere cage, and an **exact absolute readout** replaces the crawler servo's convergence dynamics.
The ±X box pair gives the sender's x from the reading *difference* (sender radius cancels) and its
radius from the *sum*; the single Y+/Z+ boxes are radius-compensated with that measurement. The
reconstruction is linear in the four readings, so it lives in one non-normalized direct blend tree
writing `Output`'s localPosition. Range is **unlimited**: while tracking, a position constraint on
`TrackingPoints` sources `Output` — its own child, the documented-legal feedback loop
(`runtime.md` §Constraints) — against a self-source brake, so the cage crawls onto the measured
sender (~50 %/frame at the default gain `g = 0.5`) and the ±1.5 m working core travels with the
target indefinitely. `Container`
is the consumer surface — constrain your payload to it and replace `Marker`; it rigidly follows the
cage.

Same latch (`allowOthers` 1→0 shut at acquisition), same zero-position-sync model as
`contact-tracker`: every client re-derives the cage locally, nothing late-syncs. The trade against
the 6-sphere sibling is no longer range — it is **one target at a time, reconstructed exactly**,
for 4 contacts instead of 6.

While not tracking, all four receivers collapse to **one coincident cube** (each slab's GO at
localScale (0.5, 0.5, 1)) so every receiver latches the identical sender set — with the full slabs
open during acquisition, two hands half a meter apart could latch into *different* boxes and
garbage the readout. The cube also makes the editor gizmo honest: what you see while searching is
exactly the acquisition zone (plus sender radius). One frame after the latch samples, the slabs
expand to full tracking geometry (filters are checked at acquisition only).

**Provenance:** `contact-tracker`'s structure (three-state rig, park/self-hold/crawl constraint
trio) with box receivers replacing the spheres. The box readout is **exact** (worst-case error
0.0000 m over the working core, radius estimate too) where a 6-sphere one-shot centroid reaches
1.21 m worst case — and exactness makes a *constant* crawl gain sufficient, so no settle dwell.
Face proximity projects the sender center onto the +Z face *plane* (infinite laterally) and
unlerps linearly across the box depth — axis-separable by construction, radius purely additive
(`runtime.md` §Contacts).

One prefab, one controller: `ContactTrackerBox.prefab`.

## Interface

- **Params:** `ContactTrackerBox/Enable` (bool, in) — synced, unsaved; off is the reset **and the
  recall**: Reset parks the cage at `HomeAnchor/Offset` and rides the wearer.
  `HomeAnchor` is an MA BoneProxy (Hips, AsChildAtRoot); retarget the proxy or drag `Offset`
  (0.1 up / 0.35 forward) to move home. On latch the cage crawls freely — cycling Enable recalls a
  stranded cage home, same gesture as `contact-tracker`. The four `ContactTrackerBox/{X+,X-,Y+,Z+}`
  floats are sensing — never synced, never menu-exposed. `ContactTrackerBox/One` is a scratch
  constant (DBT carrier weight), excluded from the params asset.
- **Latch zone knob:** default **0.15 m per side**. Size/shape = `TrackingPoints` rest
  `localScale` **and** the scale constraint's `ScaleAtRest`, edited together (GlobalWeight 0
  drives to `ScaleAtRest`, so `localScale` alone is display-only) — zone side = 3 × scale.
  Per-axis values give a box-shaped zone (children are 90°-rotated; true-matrix). The receiver
  GOs' (0.5, 0.5, 1) is the cube-collapse invariant the clips own — not a knob. Tracking geometry
  is constraint-pinned absolute, so the zone knob never skews the readout.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind
  relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController
  merges `built/ContactTrackerBox_Fx_Parameters.asset` (`prms`); `ContactTrackerBox/Enable` rides
  `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** Modular Avatar (the `HomeAnchor` proxy); **compose `anti-cull` alongside**
  (its README §When a module needs this) — the re-derivation runs only while a remote client
  evaluates the wearer's animator, which is why VRLabs ships the same mechanism inside its tracker
  prefabs. Receivers are `localOnly: 0` **by necessity** — remote clients run the tracker to
  re-derive the cage; flipping them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in
  the scale constraint makes the tracking cage absolute-meters (avatar-scale-immune). Do not
  instantiate or delete it. The upload-only sourceless `FreezeToWorld` GO (VRCFury
  ApplyDuringUpload) pins the module frame to world — without it the cage composes with avatar
  root motion; leave it inactive in editor.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Measured behavior |
|---|---|---|
| Acquisition cube | TrackingPoints localScale + ScaleAtRest 0.05; receiver GOs (0.5, 0.5, 1) | one coincident **0.15 m cube** (half-extent 0.075 + sender radius): r=0.03 sender latches at +0.06, not at +0.12; identical latch sets; gizmo = zone. Shape fields are `[NotKeyable]` — host-GO scale is the only animatable knob |
| Latch-frame hold | cube at t=0 in the latch clip (scale curves reach 1 at t=1/60) | the latch samples the cube's occupants; slabs expand over the next frame |
| Tracking scale | ×1 absolute (VRCScaleConstraint ScaleOffset, World.prefab source) | boxes 6×6×3 m, faces ±1.5 m; working core \|x\|,\|y\|,\|z\| ≤ 1.5 m **around the cage**; all four read strictly >0 inside it (center latch reads 0.5 + r/3 per box — 0.5100 at r=0.03, exact) |
| Readout coefficients | 1.5 / 3 (readout_* clips) | derived from face position 1.5 m and depth 3 m — re-derive together if the box geometry changes. Scale-invariant (readings are geometry ratios) |
| Crawl gain | **static prefab value**, default **g = 0.5** (`VRCPositionConstraint` source0=Output=1 vs source1=self=1; g = w₀/(w₀+w₁)) | ~50 % of the cage→sender gap closed per frame. **Not animated by any clip** — WD-on holds the prefab value in every state, so retune live by scrubbing source0 in the inspector during play (no recompile). Self-weight is the brake (no dwell — the exact readout has no acquisition transient). First-order stable for g<1; framerate-dependent by design |
| Loss / acquire thresholds | any <0.00001 / all four >0 | ANY-loss (vs contact-tracker's ALL): one dead box breaks the reconstruction, so partial reads never hold Tracking |

## Verifying the install

With Enable off, walk: cage and `Container` must ride the wearer at `HomeAnchor/Offset` — finding
them at the avatar-root origin means the BoneProxy never resolved. Enable on, then put a scripted
`Hand` sender (`docs/verify.md`) inside the 0.15 m cube: the four floats leave zero together,
filters shut, the slabs expand, and `Output` sits on the sender exactly. Drag the sender away at
walking speed: the cage must follow (lag ≈ speed / (0.13 × fps)) with the latch held.

Two clients in-game, not the emulator: remote-side receiver firing, chase feel under real IK, and
the **capsule-sender bias** — real hand senders are capsules, which read a constant offset toward
the near surface (a few cm; constant, not jitter).

## Traps

- **`Output` leads the sender by ~gain × cage-gap while the cage is moving.** The DBT writes
  Output from readings sampled against the pre-crawl cage, then the constraint moves the cage the
  same frame. At latch (gap ≤ half-zone + radius) that is ≲2 cm decaying; during a steady walk it
  is ≈ one frame of sender travel (emulator-measured max 8 cm at ~15 fps editor; scales down with
  fps). Payloads read `Container` (the crawl-smoothed cage position) and never see it; scripting
  against `Output` should settle by time, not frames.
- **Loss while crawling is a freeze, not a recall.** ANY-loss drops to Searching: cage self-holds
  where it stands (fail-visible), filters reopen, cube recollapses at the stranded spot — a sender
  re-entering that cube relatches in place. Cycle Enable to recall. A teleporting target produces
  a clean loss with **no kick** (measured): the loss transition preempts the garbage-reading
  motion frame, unlike contact-tracker's always-on servo layer.
- **A fully-broken latched contact cannot re-latch** (filters check at acquisition only) — but
  under ANY-loss a single dead box exits Tracking immediately, so the degraded-partial-set state
  contact-tracker documents cannot persist here.
- **Contact shape fields don't animate.** `size`/`radius`/`position`/`rotation` and most plumbing
  are `[NotKeyable]` — the binder drops the curves silently, and script writes to shape fields
  need `UpdateShape()`. Resize contacts by host-GO transform scale, nothing else. For self-use,
  retag to a single hand (`HandR`) — the inflated slabs otherwise pick up both of the wearer's
  hands.
- **The readout coefficients and the box geometry are one unit.** The DBT clips encode face
  position/depth; resizing the tracking boxes without re-deriving `readout_*` silently skews the
  reconstruction. The zone knob (TrackingPoints rest scale) is safe — the readout is
  scale-invariant and the World.prefab constraint pins tracking geometry regardless. One caveat:
  a **non-uniform** zone skews the first latch frame's radius compensation (r estimated in
  X-axis units, applied on Y/Z) by ~r × (s_y/s_x − 1) for one frame; uniform zones are exact.
- **Editing the rig:** VRC constraint `Sources` is a **struct** — `Sources.Add()` on a retrieved
  copy silently serializes nothing; assign through `SerializedObject` and set `IsActive`
  explicitly. A constraint at `GlobalWeight 0` drives to its `*AtRest` pose — it is not a no-op.
