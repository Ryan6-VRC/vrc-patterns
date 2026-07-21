# contact-tracker-box — 4-box face-proximity tracker (Module tier)

The low-contact-budget sibling of `contact-tracker`: **4 face-proximity box receivers** replace the
6-sphere cage, and an **absolute readout** replaces the crawler servo. The ±X box pair gives the
sender's x from the reading *difference* (sender radius cancels) and its radius from the *sum*; the
single Y+/Z+ boxes are radius-compensated with that measurement. The reconstruction is linear in
the four readings, so it lives in one non-normalized direct blend tree writing `Output`'s
localPosition — exact in a single step, no convergence dynamics. `Container` is the consumer
surface — constrain your payload to it and replace `Marker`; it follows `Output` on a damped
chase (§Interface), so the one-frame exactness is `Output`'s, not the marker's.

Same tag (`Hand`), same latch (`allowOthers` 1→0 shut at acquisition), same zero-position-sync
model as `contact-tracker`: every client re-derives the cage locally, nothing late-syncs. **The
trade for exactness + budget is range**: the working volume is a fixed **±1.5 m core** around the
deployment point — while tracking it does not chase. Inside it, tracking is exact; outside it,
loss. The volume freezes to world when Enable turns on and rides the wearer while Enable is off,
so **cycling Enable is the re-deploy gesture** — the analogue of `contact-tracker`'s
cycle-Enable-to-recall.

While not tracking, all four receivers collapse to **one coincident 0.45 m cube** (each slab's
GO animated to a non-uniform scale) so every receiver latches the identical sender set — with the
full slabs open during acquisition, two hands half a meter apart could latch into *different*
boxes and garbage the readout. The cube also makes the editor gizmo honest: what you see while
searching is exactly the acquisition zone. One frame after the latch samples, the slabs expand to
full tracking geometry (post-latch shape doesn't affect which senders are held — filters are
checked at acquisition only).

**Provenance:** `contact-tracker`'s structure with box receivers replacing the spheres. That swap is
the reason this entry exists: 4-box reconstruction is **exact** (worst-case error 0.0000 m, radius
estimate too) where a 6-sphere one-shot centroid reaches 1.21 m worst case over the same grid.
Face proximity projects the sender center onto the +Z face *plane* (infinite laterally) and
unlerps linearly across the box depth — axis-separable by construction, radius purely additive
(`ContactManager` source; `runtime.md` §Contacts).

One prefab, one controller: `ContactTrackerBox.prefab`.

## Interface

- **Params:** `ContactTrackerBox/Enable` (bool, in) — synced, unsaved; off is the reset **and
  the recall**: Reset unfreezes the module root onto `HomeAnchor/DeployPoint` (rides the wearer),
  and the Reset→Searching edge refreezes it where the wearer stands. While not tracking,
  `Container` parks at `HomeAnchor/Offset` — `HomeAnchor` is an MA BoneProxy (Hips, AsChildAtRoot);
  retarget the proxy or drag `Offset` (0.1 up / 0.35 forward) / `DeployPoint` (0.6 down / 0.35
  forward of the hips — the volume core sits 1.0 m above it) to move park and deploy. The latch
  swaps `Container` onto a **damped chase** of the live readout (~13%/frame; the `latch` clip's
  Container source0 weight, feel-tunable 0.1–0.2 against the self-source's 1). The volume itself
  cannot be avatar-anchored while live (`TrackingPoints`' children are path-animated — anchor by
  constraint only), which is why deploy goes through the animated FreezeToWorld constraint. The
  four `ContactTrackerBox/{X+,X-,Y+,Z+}` floats are sensing — never synced, never menu-exposed.
  `ContactTrackerBox/One` is a scratch constant (DBT carrier weight), excluded from the params
  asset.
- **Seam:** VRCFury FullController on the prefab root; `basis: mount-root` — clip paths bind
  relative to the prefab root, so the internal hierarchy names are load-bearing. The FullController
  merges `built/ContactTrackerBox_Fx_Parameters.asset` (`prms`); `ContactTrackerBox/Enable` rides
  `globalParams`, and a VRCFury `Toggle` (`useGlobalParam`) is the menu front inside the module.
- **Dependencies:** none to build; **compose `anti-cull` alongside** (its README §When a module
  needs this) — the re-derivation below runs only while a remote client evaluates the wearer's
  animator, which is why VRLabs ships the same mechanism inside its tracker prefabs. Receivers are
  `localOnly: 0` **by necessity** — remote clients run the tracker to re-derive the cage; flipping
  them local-only breaks remote copies silently.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference; sourcing it in
  the scale constraint makes the deployed cage absolute-meters (avatar-scale-immune). Do not
  instantiate or delete it.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Measured behavior |
|---|---|---|
| Acquisition cube | receiver GOs at localScale (0.5, 0.5, 1) while not tracking; TrackingPoints localScale 0.15 | all four slabs become one coincident 3×3×3 local = **0.45 m cube** (half-extent 0.225 + sender radius): identical latch sets, gizmo = zone. Shape fields are `[NotKeyable]` — host-GO scale is the only animatable knob (honored per-frame, per-axis, true-matrix under the 90° rotations) |
| Latch-frame hold | cube at t=0 in the latch clip (scale curves reach 1 at t=1/60) | the latch samples on the cube's occupants; slabs expand over the next frame (contact-tracker's coincident-frame idiom) |
| Tracking scale | ×1 absolute (VRCScaleConstraint ScaleOffset, World.prefab source) | boxes 6×6×3 m, faces at ±1.5 m; working core \|x\|,\|y\|,\|z\| ≤ 1.5 m; all four read strictly >0 inside it |
| Readout coefficients | 1.5 / 3 (readout_* clips) | derived from face position 1.5 m and depth 3 m — re-derive together if the box geometry changes. The readout is uniform-scale-invariant (readings are geometry ratios), so exactness holds even at acquisition scale; the constraint pins *range* |
| Deploy/recall | FreezeToWorld animated on the Enable cycle; one source (DeployPoint, weight 1); RebakeOffsetsWhenUnfrozen 0 | a sourceless freeze never re-captures its pose (no knob refreshes it — native-side); with one source, every 0→1 edge re-freezes at the current pose |
| Marker damping | Container source0 (Output) 0.15 vs self source2 1.0, latch clip | normalized → ~13% of the gap closed per frame; framerate-dependent by design (spring-damping's documented trade); feel band 0.1–0.2 |
| Loss / acquire thresholds | any <0.00001 / all four >0 | ANY-loss (vs contact-tracker's ALL): one dead box breaks the reconstruction, so partial reads never hold Tracking |

## Verifying the install

With Enable off, walk: the (inactive-receiver) volume must ride the wearer at `DeployPoint` —
stuck at a fixed world spot means the freeze constraint's source is gone. Enable on, then put a
scripted `Hand` sender (`docs/verify.md`) in the 0.45 m acquisition cube: the four floats leave
zero together, filters shut, the slabs expand, and `Container` glides off `HomeAnchor/Offset`
onto the damped readout chase. Walking now must leave the volume where it froze; cycling Enable
must recall and re-freeze it at the wearer's new spot.

Two clients in-game, not the emulator: remote-side receiver firing, and the **capsule-sender
bias** — real hand and finger senders are capsules, which read a constant offset toward the near
surface bounded by the capsule's segment half-length projected per axis (a few cm for a real hand
collider). Constant, not jitter, so it reads as a small fixed tracking error rather than noise.

## Traps

- **Range is a hard box.** The volume freezes in world space when Enable turns on; a target (or
  wearer drift) beyond ±1.5 m of that point is loss, not degradation. There is no crawl — cycle
  Enable to re-deploy where you stand. If you need roaming range, use `contact-tracker`.
- **Contact shape fields don't animate.** `size`/`radius`/`position`/`rotation` and most of the
  plumbing are `[NotKeyable]` (`allowSelf`/`allowOthers`/`receiverType`/`minVelocity` do bind) —
  the binder drops the curves silently, and even script writes to shape fields need
  `UpdateShape()`. Resize contacts by animating the host GO's transform scale, nothing else.
  For self-use, retag to a single hand (`HandR`) — the inflated slabs otherwise pick up both of
  the wearer's hands.
- **The readout coefficients and the box geometry are one unit.** The DBT clips encode face
  position/depth; scaling or resizing the tracking boxes without re-deriving `readout_*` silently
  skews the reconstruction. The acquisition cube scales (`0.5, 0.5, 1`) are the safe knob — the
  readout is scale-invariant, and the World.prefab constraint pins the deployed geometry
  regardless.
- **Latch-frame transient.** Readings sampled in the 1–2 sim ticks around the deploy scale flip
  can momentarily mix scales; the Output settles within ~2 frames (60 Hz contact sim — settle by
  time, not frames, when scripting against it).
- **Known intermittent: tracking-scale wedge.** Rarely (1 of 3 emulator sessions once; not
  reproduced since), the tracking `VRCScaleConstraint` never inflates after a bake — GW animates
  to 1 but lossyScale stays 0.15 for the whole session. Tracking stays exact (the readout is
  scale-invariant) but range collapses to the acquisition cube. Signature: all four floats read
  ≈ 0.678 at a center latch instead of ≈ 0.527. Suspected native bake-init race (possibly the
  Container self-source cycle — unproven). Recovery untested; cycle Enable, else re-bake.
- **Editing the rig:** VRC constraint `Sources` is a **struct** — `Sources.Add()` on a retrieved
  copy silently serializes nothing; assign through `SerializedObject` (`Sources.source0.*`,
  `Sources.totalLength`) and set `IsActive` explicitly.
