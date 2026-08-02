# object-sync — absolute world position + rotation for a droppable prop (Module)

A prop that can be set down anywhere in the world and is in the same place for everyone, including a player who joins after it was dropped: a two-stage contact measure quantizes its world transform on the wearer's client and `word-channel` replicates the bits, with no physbone, no Rigidbody, and no synced position of its own. The packaged novelty is the redundant fine stage — a second, bias-cancelling readout wide enough to absorb the coarse stage's error — which puts millimetre placement anywhere in a ±8192 m world inside **29 synced bits**, refreshed end to end in ~0.7 s.

The generator ships one built configuration (one object, full rotation). Two further configurations are generator paths — `y` (one object, heading only) and `y_double` (two objects, heading only, time-multiplexed onto one measure rig) — carried in `generate.py`'s `PRESETS`, not committed as builds.

## Provenance

VRLabs **Custom-Object-Sync** (MIT, © VRLabs) is the studied ancestor. Two of its idioms are re-derived here: the successive-approximation threshold walk that turns an analog reading into bits, and the setter tree that drives a constraint's `PositionOffset` from decoded values. Its receive side is rejected wholesale — a multi-frame decode walk is exactly what a culling pause interrupts, so every decode here is a blend tree holding no state between frames — and so is its physics world-pin and its six rotation physbones. The transport is `vrc-patterns/word-channel`, whose protocol descends from VRCFury's Parameter Compressor. Nothing is ported from either; both are credited as ancestors.

## Interface

- **Params in**: none. The module measures a transform, not a parameter — point `Rig/Prop/Coarse/Sender` and `Rig/Prop/Fine/Sender` at whatever your gimmick uses as the prop's authority transform (a grab bone, a drop anchor) and it syncs that.
- **Params out** (every client): `Prop/PX/{C,F}` + `Prop/PX/{C0..C4,F0..F3}` and the same per axis, `Prop/R{A,B}/{X,Y,Z}` + four bools each — the word table, driven by the receiver on remotes and by the encode layers on the wearer. `ObjectSync/Ch/Cycle` is word-channel's remote freshness counter. Everything else is `scratch:`.
- **Wire** (the only synced params, all unsaved): 4 index bools + 2 8-bit int slots + 9 bool slots = **29 bits**, 6 batches, ~0.70 s full refresh at 60 fps.
- **Seam**: VRCFury `FullController` on the prefab root, `basis: mount-root` ↔ the FullController default `rootBindingsApplyToAvatar: 0` — every clip binding paths through the module's own rig, so the internal hierarchy names in **Rig** below are load-bearing. `globalParams` is **empty**: nothing outside the module reads a name, so every param takes an instance prefix and two instances compose without colliding.
- **Dependencies**: **compose `anti-cull` alongside** — the decode runs only while a remote client evaluates the wearer's animator, and a view-culled wearer's prop freezes where it was last decoded. Distance-hide is not defeatable and is a declared limit, not a defect.
- **Required assets**: `assets/World.prefab` — the never-instantiated prefab whose transform every rig constraint sources, which is what makes the frame the same world origin on every client. Do not instantiate or delete it.

## Rig

The prefab is hand-maintained against this section; the numbers are `generate.py`'s CONFIG, and a retune happens there and lands here, never the other way round. Clip bindings name these paths verbatim, so a rename in the prefab silently unbinds the controller.

    Rig/                                   VRCPositionConstraint → World.prefab; local position (73, 932, 233)
      Prop/
        Coarse/
          Sender                           VRCPositionConstraint, 2 sources: Rig at weight 0.999664306640625,
                                             the prop's authority transform at 0.000335693359375 (= 2.75/8192)
          RecvX RecvY RecvZ                box receivers, face mode, size 6 on the read axis, localOnly
        Fine/
          Sender                           VRCPositionConstraint → the prop's authority transform; sphere sender, radius 0.05
          Anchor/                          VRCPositionConstraint → Rig; PositionOffset animated (cell centre)
            RecvX RecvY RecvZ              box receivers, face mode, size 6, localOnly
        Rot/
          Holder/                          VRCRotationConstraint → the authority transform; position pinned to Rig
            MarkA                          sphere sender at local (0, 0, 1)
            MarkB                          sphere sender at local (0, 1, 0)
          RecvAX … RecvBZ                  6 box receivers, face mode, size 2.5, localOnly
        Recon/
          ProxyA  ProxyB                   localPosition animated from the decoded components
          UpAim/                           VRCAimConstraint: AimAxis (0,1,0), source ProxyB, WorldUp None
            Recon                          VRCAimConstraint: AimAxis (0,0,1), source ProxyA,
                                             WorldUp ObjectRotationUp, WorldUpVector (0,1,0), WorldUpTransform UpAim
        Display/                           VRCPositionConstraint → Rig, PositionOffset animated;
                                             VRCRotationConstraint → Recon. Parent the visible prop here.

Four rig facts are the design, not preferences:

| Fact | Value | Why it is that |
|---|---|---|
| Rig park | `(73, 932, 233)` m, derived from `rigSeed` | Twelve receivers stacked where players spawn is how a contact cluster starts reading other people's dynamics; parking it is free, and the offset cancels because every client's copy uses the same one. |
| Receiver face | `size` 6 on the read axis (the per-shape maximum), 2.5 for rotation | `size` is the FULL extent. Face mode is a linear unlerp from the +Z face plane, so the read axis is the box's local Z and the other two only have to contain the sender. |
| Sender radius | 0.05 m, spheres | A sender is read by its nearest surface, so a sphere biases the reading by exactly its radius toward the face — a constant, folded into the walk's calibration. Changing the radius without regenerating skews every reading. |
| `Fine/Sender`, `Fine/Anchor`, `Fine/Recv*` under one `Rig` | not negotiable | This is what makes the fine stage bias-cancelling (below). Re-parenting the sender under the prop instead breaks it. |

**Empirical constants** (measured in the emulator; re-measure before changing any of them):

| Constant | Value | Where it lands |
|---|---|---|
| Coarse readout error, contact space | 0.39 mm worst case, avatar 4–8 km from world origin | `coarseNoise` in CONFIG; amplified by `range/coarseHalfSpan` to 1.16 m of world error, and the fine field is widened by twice that |
| Fine readout | float32-exact, zero noise; ≤1 frame stale under motion | why the fine stage sets system precision and the coarse stage's error costs bits, not accuracy |
| Fine-anchor settle | 1 frame to the cell centre, 2–4 frames to a coherent reading | `settleFrames` = 4 |
| Rotation error at 12 bits/component | 0.014° mean, 0.036° max, at 90° marker separation | `rotBits`; the bar it beats is Custom-Object-Sync's 0.176° |
| End-to-end position error at 7.8 km | 0.43 mm ≈ one float32 ulp of the prop's own coordinate | the precision floor; more bits here would be fake precision |

## How it works

**Position, per axis, in two stages.** A `VRCPositionConstraint` squeezes the prop toward the rig anchor — anchor weight `1 − g`, prop weight `g = coarseHalfSpan/range` — so the whole ±8192 m range lands inside ±2.75 m of a 6 m face receiver. An `IsLocal` successive-approximation walk (one state pair per bit, accepted above, rejected below) turns that reading into 13 bits naming a 2 m **cell**. The walk's accumulated cell index places a second anchor at that cell's centre, and a sender constrained to the prop is read at 1:1 by face receivers riding that anchor, which a second walk turns into 12 more bits. Anchor, receiver and sender share one hierarchy, so the float32 displacement the avatar's own distance from the world origin introduces appears identically on both sides of the subtraction and cancels bit-exactly — measured identical to the last bit with the avatar parked at 0 m and at 5 km.

**Why 13+12 and not 13+11.** The coarse stage does *not* cancel that displacement: at 8 km its world error runs to 1.16 m, more than half a cell, so the cell it picks can be one boundary out. The fine field is therefore **redundant** — it spans the cell plus twice the coarse error (4.4 m), not the cell (2 m) — so an off-by-one cell is still reconstructed exactly, at the cost of one bit per axis and no correction pass anywhere. That 4.4 m field sits inside the 6 m face with 0.8 m spare at each end, which is what keeps the readout off the two ways a face receiver lies: it saturates at 1.0 for about 20 mm past the face plane, and past that it reads exactly 0 — the same value as "nothing overlaps".

**Rotation without trig or physbones.** A rotation-only holder carries two markers on orthogonal 1 m arms; three face receivers per marker give six components, sent raw. Every client rebuilds the orientation with a `VRCAimConstraint` pair: `UpAim` aims +Y at proxy B, and `Recon` — **its child**, so the solver is forced to resolve `UpAim` first in the same frame — aims +Z at proxy A with `WorldUpType` **ObjectRotationUp** against `UpAim`. `ObjectUp` looks like the right token and silently degenerates to world up; it is never correct here. The `y` preset instead reads one marker in XZ and converts it to an angle *before* the wire with a 2D freeform-directional blend tree, which is an exact angle interpolator, magnitude-invariant, and wrong only inside the one sector where its output value wraps — so a second tree carries the same angle with its seam half a turn away, and the walk enters through whichever start state the marker's own Z reading selects.

**The wire, and why nothing tears.** Each axis's coarse byte, fine byte and nine bools share one `group:`, so word-channel pins them into one batch and `atomic: batch` applies them together: an adjacent-cell coarse always lands with its matched fine, which reconstructs the same position, so cell-boundary flicker needs no hysteresis anywhere. Each rotation component's byte and four bools share a cross-kind group the same way. The walks are multi-frame and that is safe — they run only on the wearer's own client, which cannot cull itself — but the handoff to the wire must not be, because word-channel's sender copies the word params on its own clock and would happily latch a half-written axis. So the walks fill scratch staging and one `Commit` state driver-copies a whole axis, all eleven words, in a single frame.

**Two anchors, not one.** The measurement anchor rides the walk's running cell index — a staged value, mid-cycle, local. The display anchor rides the committed word and is side-agnostic: the wearer decodes its own prop from the same words a remote does. They cannot be one node, because sharing would mean committing the coarse word before the fine walk has run, which is exactly the torn axis the commit exists to prevent.

**Costs.** 381 states and 13 layers for the committed configuration; 34 frames (~0.57 s) per local measure cycle, ~0.70 s per wire refresh, ~1.3 s worst case end to end. Twelve local-only receivers, zero physbones. `generate.py --check` holds regeneration byte-identical and asserts the packing and commit structure for all three configurations.

## Verifying the install

**TODO — this slot is written in the fixture phase**, alongside the emulator fixtures for the committed build and both presets. It will carry two things and nothing else: the cheapest observable that separates a correct install from a plausible-looking broken one, and what the emulator structurally cannot show for this entry.
