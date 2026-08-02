# object-sync — absolute world position + rotation for a droppable prop (Module)

A prop that can be set down anywhere in the world and is in the same place for everyone, including a player who joins after it was dropped: a two-stage contact measure quantizes its world transform on the wearer's client and `word-channel` replicates the bits, with no physbone, no Rigidbody, and no synced position of its own. The packaged novelty is the redundant fine stage — a second, bias-cancelling readout wide enough to absorb the coarse stage's error — which puts millimetre placement anywhere in a ±8192 m world inside **29 synced bits**, refreshed end to end in ~0.7 s.

The generator ships one built configuration: one object, full rotation, 72 rotation bits on the wire. Two further configurations are generator paths — `y` (one object, heading only, 24 rotation bits) and `y_double` (two objects, heading only, time-multiplexed onto one measure rig) — carried in `generate.py`'s `PRESETS`, not committed as builds.

## Provenance

VRLabs **Custom-Object-Sync** (MIT, © VRLabs) is the studied ancestor. Two of its idioms are re-derived here: the successive-approximation threshold walk that turns an analog reading into bits, and the setter tree that drives a constraint's `PositionOffset` from decoded values. Its receive side is rejected wholesale — a multi-frame decode walk is exactly what a culling pause interrupts, so every decode here is a blend tree holding no state between frames — and so is its physics world-pin and its six rotation physbones. The transport is `vrc-patterns/word-channel`, whose protocol descends from VRCFury's Parameter Compressor. Nothing is ported from either; both are credited as ancestors.

## Interface

**Coming from Custom-Object-Sync / GestureTools:** your prop replaces `Container`'s `Marker` child, and `ObjectSync/Enable` is that rig's enable — off parks, on measures and displays. There is no per-object sync bit here, because there is no runtime object index: multi-object is a list in `generate.py`'s CONFIG, resolved at generation time into that many objects' worth of words.

- **Params in**: `ObjectSync/Enable` (bool, synced, **unsaved**, default off) — the master gate, on `globalParams`, so an outside driver or OSC can reach it under that bare name. Nothing else: the module measures a transform, not a parameter — the prefab ships an `Authority` node at its root as the source of `Rig/Prop/Coarse/Sender`, `Rig/Prop/Fine/Sender` and `Rig/Prop/Rot/Holder`, and the install step is to re-point or re-parent it at whatever your gimmick uses as the prop's authority transform (a grab bone, a drop anchor). All three must name the same transform or the position and rotation stages measure different objects.
- **Menu**: a bare VRCFury `Toggle` on `ObjectSync/Enable`, labelled `Object Sync` — one control, so no menu asset (`CONVENTIONS.md` §The Interface stanza), and the module is single-instance per avatar regardless, for the collision-tag reason under **Seam**.
- **Params out** (every client): `Prop/PX/{C,F}` + `Prop/PX/{C0..C4,F0..F3}` and the same per axis, `Prop/R{A,B}/{X,Y,Z}` + four bools each — the word table, driven by the receiver on remotes and by the encode layers on the wearer. `ObjectSync/Ch/Cycle` is word-channel's remote freshness counter. Everything else is `scratch:`.
- **Wire** (the only synced params, all unsaved): 4 index bools + 2 8-bit int slots + 9 bool slots = **29 bits**, 6 batches, ~0.70 s full refresh at 60 fps.
- **Seam**: VRCFury `FullController` on the prefab root, `basis: mount-root` ↔ the FullController default `rootBindingsApplyToAvatar: 0` — every clip binding paths through the module's own rig, so the internal hierarchy names in **Rig** below are load-bearing. `globalParams` is exactly `ObjectSync/Enable`, which the module's own `Toggle` drives by name and so has to carry; every other param takes an instance prefix. That makes the *parameters* instance-safe and nothing else — the four collision tags are fixed strings VRCFury's prefixing does not reach, and two copies park their contact clusters at the same point, so a second instance needs a regeneration with its own tags, not a second drop of the prefab.
- **Dependencies**: **compose `anti-cull` alongside** — the decode runs only while a remote client evaluates the wearer's animator, and a view-culled wearer's prop freezes where it was last decoded. Distance-hide is not defeatable and is a declared limit, not a defect.
- **Required assets**: `assets/World.prefab` — the never-instantiated prefab `Rig` sources, which is what makes the frame the same world origin on every client. A bare origin node; do not instantiate or delete it.

## Rig

The prefab is hand-maintained against this section; the numbers are `generate.py`'s CONFIG, and a retune happens there and lands here, never the other way round. Clip bindings name these paths verbatim, so a rename in the prefab silently unbinds the controller.

    Authority                              the prop's authority transform; re-pointed or re-parented at install
    Rig/                                   VRCParentConstraint → World.prefab, the ONE component pinning both
                                             position and rotation; the park rides source0's ParentPositionOffset
                                             (73, 932, 233), which resolves in SOURCE space and so is world-fixed
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
                                             VRCRotationConstraint → Recon
    Home                                   where a parked prop rests; an MA BoneProxy anchor or a
                                             plain child, the module never drives it
    Container/                             VRCParentConstraint, SOURCE ORDER source0 = Home,
                                             source1 = Rig/Prop/Display; both weights animated
      Marker                               placeholder — replace with the visible prop

With more than one object, three things gain the object name rather than staying bare: `Container` gains a child per object carrying the constraint (one parked node cannot hold two poses), each object gets its own collision-tag set (below), and the `m_IsActive` bindings pass from the enable's clips to the `Slice` layer's, which owns them alone.

A `y`-mode rig is this one with `MarkB`, `RecvAY`, the four `RecvB*`, `ProxyB` and `UpAim` deleted, and `Recon` re-parented to `Recon/` carrying `WorldUpType: Vector`, `WorldUpVector (0,1,0)` instead of the object-rotation up. Nothing else moves.

Seven rig facts are the design, not preferences:

| Fact | Value | Why it is that |
|---|---|---|
| Rig park | `(73, 932, 233)` m, derived from `rigSeed`, on the pin's **source** offset | Twelve receivers stacked where players spawn is how a contact cluster starts reading other people's dynamics; parking it is free, and the offset cancels because every client's copy uses the same one. It has to be the per-source offset: a constraint's own `PositionOffset` resolves in the constrained object's *parent* space, so putting the park there makes it ride the wearer's yaw and puts two clients' rigs hundreds of metres apart. |
| Receiver face | `size` 6 on the read axis (the per-shape maximum), 2.5 for rotation | `size` is the FULL extent. Face mode is a linear unlerp from the +Z face plane, so the read axis is the box's local Z and the other two only have to contain the sender. |
| Sender radius | 0.05 m, spheres | A sender is read by its nearest surface, so a sphere biases the reading by exactly its radius toward the face — a constant, folded into the walk's calibration. Changing the radius without regenerating skews every reading. |
| `Fine/Sender`, `Fine/Anchor`, `Fine/Recv*` under one `Rig` | not negotiable | This is what makes the fine stage bias-cancelling (below). Re-parenting the sender under the prop instead breaks it. |
| `Container` source order | source0 = `Home`, source1 = `Rig/<obj>/Display` | The enable clips write those two weights by index, not by name. Swapping the sources inverts the toggle with nothing to see in either file. |
| The gate's reach | the three subtree roots `Rig/<obj>/{Coarse,Fine,Rot}` carry the animated `m_IsActive` | Deactivating the subtree root kills a stage's senders and receivers together, and it is the *deactivation* that makes a clear stick — a live receiver re-asserts its parameter the next frame, which is exactly how a driver-only clear was measured failing. One writer owns this property: the enable's clips with one object, the `Slice` layer with several. |
| Collision tags | `ObjectSync{Obj}{Coarse,Fine,RotA,RotB}` — the object name appears only when there is more than one, so a single-object build is `ObjectSyncCoarse` … `ObjectSyncRotB` | One tag per sender group keeps the four readouts off each other's senders, since all four clusters sit at the same point. **Per-object sets are not optional**: measured with two objects sharing one set, *neither* converges, because each receiver reads the strongest sender in range rather than its own. Receivers are `allowSelf` only and every contact is `localOnly`, so nobody else's rig is on the hook either. |

**Empirical constants** (measured in the emulator; re-measure before changing any of them):

| Constant | Value | Where it lands |
|---|---|---|
| Coarse readout error, contact space | 0.39 mm worst case, avatar 4–8 km from world origin | `coarseNoise` in CONFIG; amplified by `range/coarseHalfSpan` to 1.16 m of world error, and the fine field is widened by twice that |
| Fine readout | float32-exact, zero noise; ≤1 frame stale under motion | why the fine stage sets system precision and the coarse stage's error costs bits, not accuracy |
| Fine-anchor settle | 1 frame to the cell centre, 2–4 frames to a coherent reading | `settleFrames` = 4 |
| Rotation error at 12 bits/component | 0.032° mean, 0.12° max, at 90° marker separation | `rotBits`; the bar it beats is Custom-Object-Sync's 0.176° |
| End-to-end position error, 2 m to 9.6 km | 0.7–1.8 mm, per axis inside `[−1.3, 0] mm` | the precision floor: the walk floors rather than rounds, so the residual is one-sided and stays under the 1.07 mm fine LSB. More bits here would be fake precision |

## How it works

**Position, per axis, in two stages.** A `VRCPositionConstraint` squeezes the prop toward the rig anchor — anchor weight `1 − g`, prop weight `g = coarseHalfSpan/range` — so the whole ±8192 m range lands inside ±2.75 m of a 6 m face receiver. An `IsLocal` successive-approximation walk (one state pair per bit, accepted above, rejected below) turns that reading into 13 bits naming a 2 m **cell**. The walk's accumulated cell index places a second anchor at that cell's centre, and a sender constrained to the prop is read at 1:1 by face receivers riding that anchor, which a second walk turns into 12 more bits. Anchor, receiver and sender share one hierarchy, so the float32 displacement the avatar's own distance from the world origin introduces appears identically on both sides of the subtraction and cancels bit-exactly — measured identical to the last bit with the avatar parked at 0 m and at 5 km.

**Why 13+12 and not 13+11.** The coarse stage does *not* cancel that displacement: at 8 km its world error runs to 1.16 m, more than half a cell, so the cell it picks can be one boundary out. The fine field is therefore **redundant** — it spans the cell plus twice the coarse error (4.4 m), not the cell (2 m) — so an off-by-one cell is still reconstructed exactly, at the cost of one bit per axis and no correction pass anywhere. That 4.4 m field sits inside the 6 m face with 0.8 m spare at each end, which is what keeps the readout off the two ways a face receiver lies: it saturates at 1.0 for about 20 mm past the face plane, and past that it reads exactly 0 — the same value as "nothing overlaps".

**Rotation without trig or physbones.** A rotation-only holder carries two markers on orthogonal 1 m arms; three face receivers per marker give six components, sent raw. Every client rebuilds the orientation with a `VRCAimConstraint` pair: `UpAim` aims +Y at proxy B, and `Recon` — **its child**, so the solver is forced to resolve `UpAim` first in the same frame — aims +Z at proxy A with `WorldUpType` **ObjectRotationUp** against `UpAim`. `ObjectUp` looks like the right token and silently degenerates to world up; it is never correct here. The `y` preset is a strict subset of the same rig — marker A's X and Z components on the wire, one `Recon` aim constraint with `WorldUpType` **Vector** `(0,1,0)`, no second marker and no `UpAim` — and it sends components rather than the heading itself because a parameter driver reads 0 from an AAP, so no walk can quantize a number a blend tree computed.

**The wire, and why nothing tears.** Each axis's coarse byte, fine byte and nine bools share one `group:`, so word-channel pins them into one batch and `atomic: batch` applies them together: an adjacent-cell coarse always lands with its matched fine, which reconstructs the same position, so cell-boundary flicker needs no hysteresis anywhere. Each rotation component's byte and four bools share a cross-kind group the same way. The walks are multi-frame and that is safe — they run only on the wearer's own client, which cannot cull itself — but the handoff to the wire must not be, because word-channel's sender copies the word params on its own clock and would happily latch a half-written axis. So the walks fill scratch staging and one `Commit` state driver-copies a whole axis, all eleven words, in a single frame.

**Two anchors, not one.** The measurement anchor rides the walk's running cell index — a staged value, mid-cycle, local. The display anchor rides the committed word and is side-agnostic: the wearer decodes its own prop from the same words a remote does. They cannot be one node, because sharing would mean committing the coarse word before the fine walk has run, which is exactly the torn axis the commit exists to prevent.

**The enable, and what it does not gate.** `ObjectSync/Enable` is one synced bit, so wearer and remotes park together. Off, a 1D tree on it deactivates the three measure subtrees and hands `Container` back to `Home`; each measuring layer takes an AnyState rung into a `Parked` state whose driver clears that layer's staging, residual, cell index and sense params — in that order, because a deactivated sensing component does not fall to zero, it *freezes* at its last live reading, and only a clear written after the deactivation sticks. What Enable does **not** gate is the wire: word-channel's 29 bits are allocated whether or not the prop is out, so gating it would save nothing and would cost the re-enable a full re-acquisition. The word table is left holding the last committed pose for the same reason — re-enabling shows the prop where it was, not at the origin.

**Coming back up is where a clear turns into a lie.** A cleared sense param reads 0, and 0 is a legal reading that quantizes to cell 0 — the far corner of the range — so a walk that samples before its reactivated receivers have re-acquired publishes a confident wrong answer rather than nothing. The only road out of `Parked` therefore runs through a `settleFrames` dwell, and the road to any `Commit` runs through every bit of the walk: both are transition structure, not a timing argument, and both are asserted structurally by `--check`. The multi-object `Slice` layer is the same discipline at slice granularity — deactivate every other object's rig, clear, settle, and only then unblock that object's walks, with a second AnyState rung making a walk that loses the rig mid-flight abandon instead of committing limbs measured against somebody else's senders.

**Costs.** 426 states and 13 layers for the committed configuration; 34 frames (~0.57 s) per local measure cycle and four more after an unpark, ~0.70 s per wire refresh, ~1.3 s worst case end to end. A two-object build costs a slice each instead: 47 frames per slice, so ~1.6 s round trip. Twelve local-only receivers per object, zero physbones. `generate.py --check` holds regeneration byte-identical, pins the committed document against the one `built/` was compiled from, and asserts packing, commit reachability, the wake dwell, the slice sequencing and the reconstruction shapes across all three configurations — including that no driver anywhere reads or writes an AAP param, which is the shape of the defect that cost y-mode its first design.

## Verifying the install

Cheapest observable: **toggle `Object Sync` off and on with the wearer standing away from the world origin and facing away from +Z**. Off, `Container` sits on `Home` on the wearer and on a remote clone alike; on, it reaches the prop's true world pose inside about a second — millimetres of position, hundredths of a degree of rotation, the same value on both sides because both decode the same words. The off-origin, off-axis stance is the part that is easy to skip and the part that catches the whole class: a rig frame that has quietly stayed avatar-relative is indistinguishable from a correct one at the origin, so read `Rig` while you are there and require exactly `(73, 932, 233)` with identity rotation on both clients. Local and clone disagreeing by more than quantization is the decode reading a different word table, not the wire being slow; a `Container` frozen off `Home` while `ObjectSync/Ch/Cycle` climbs on the clone is the rig rather than the wire (`../word-channel`'s own §Verifying owns the `Cycle` reading).

**Re-enabling sweeps, and it is a live defect rather than a quirk to expect.** The first unparked frame is the last synced pose — no origin flash, and it never touches world zero — but the wake dwell is `settleFrames` (4), and a reactivated contact receiver is **measured needing 7 frames** to re-acquire. The first walk out of `Parked` therefore samples receivers still reading 0, 0 quantizes to cell 0, and the prop flies to the ±8192 m corner before converging over ~0.4 s on the wearer and ~0.9 s on a remote. The dwell is sized from the fine-anchor settle, which is a different and smaller quantity than receiver re-acquisition. Multi-object pays it once per slice rather than once per unpark, where it shows as cell-scale rather than range-scale jitter because the fine stage's redundancy absorbs the rest. A live-to-live move is unaffected.

What the emulator structurally cannot show for this entry: everything `../word-channel` declares — its wire is this entry's wire — plus one that belongs to the measure rig. **Contacts are never simulated against a remote clone**, so the twelve receivers are only ever exercised on the wearer's own client, and nothing here can reach a fault that needs another player's dynamics to appear — which is also why the park is an argument rather than a measurement: `(73, 932, 233)` is empty in a test scene by construction, where a real world may put geometry or another player's props through it.
