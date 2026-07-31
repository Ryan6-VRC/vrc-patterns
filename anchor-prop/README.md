# anchor-prop — multi-anchor self-syncing prop (Module)

A wearer-only prop that rests at any of five anchors — stowed on the chest, held in either hand, at the mouth, or frozen in the world — and moves between them on a fist grip; swap the placeholder payload for your own prop (a pipe, a mic, a fan). One `VRCParentConstraint` multiplexes the five anchors (`gimmicks.md` §Anchor multiplexer — never the duplicate-object anchor swap) and the whole rest state rides **one synced int** — no per-anchor sync — while the design carries what a single-anchor prop never meets: hand-to-hand handoff, a mouth anchor that survives first-person head chop, and a freeze-in-the-world band. `allowSelf`-only sensing keeps it wearer-only — the deliberate opposite of the instance-grabbable `grab-prop`/`drop-on-player`.

**Provenance:** the anchor-multiplexer + self-syncing-mode-int mechanism as vendor-proven by a vendor reference implementation, and in-house by our own gesture-release prop lineage.

## Interface

- **Params:**
  - `AnchorProp/Mode` (int, out) — synced, **unsaved**. The rest mode, banded: 0 Hidden (off-is-reset), 1 Stowed, 2 HeldR, 3 HeldL, 4 Mouth, 11 World (attach band 1–9, world band 11–19). 8 bits pre-compressor, stamped with Set only, so nothing blocks Parameter Compressor membership. Written only by the wearer's `localOnly` drivers — no late-join park.
  - `AnchorProp/Enable` (bool, in) — **unsynced** menu intent; the mode int carries the outcome, so the menu costs 0 sync bits.
  - `AnchorProp/NearHandR/L`, `NearMouth`, `NearStow` (float, sensing) — proximity of the **prop's own sender** (private tag `AnchorProp`) at each anchor point (`allowSelf` only; `localOnly` — remotes never need them). Prop-near-anchor sensing, not `Hand`-tag sensing. Never synced/saved/menu-exposed.
  - `GestureRight`/`GestureLeft` (VRC built-ins) — Fist (1) is the grip gesture on both hands.
- **Seam:** VRCFury `FullController` on the prefab root with **two controller rows** — `built/AnchorProp_Fx.controller` (FX) and `built/AnchorProp_Gesture.controller` (Gesture) — plus `prms: built/AnchorProp_Fx_Parameters.asset` (the single sync-surface declaration) and `globalParams: [AnchorProp/Enable]` for the Toggle. `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`. MA `BoneProxy` on the four body anchors only; every animated binding targets `Container`/`WorldAnchor`, which no BoneProxy touches, and the anchors carry only object references (path-immune).
- **Dependencies:** VRC SDK + VRCFury + Modular Avatar, and a **humanoid** avatar (the Gesture-playable merge refuses a generic rig; the BoneProxies resolve Chest/hands/Head through the humanoid mapping).
- **Required assets:** none — `Payload` is a placeholder sphere on the built-in default material; swap it for your prop mesh, keep it under `Container`.

## Before you compose it

- **The grip seizes only the holding hand,** following the mode (2 = right, 3 = left); a handoff swaps which hand is seized, and the mouth anchor holds the prop with both hands free and un-seized. Gesture *params* keep firing — only the visible fingers are overridden.
- **World placements are per-client.** Expect centimeter-grade divergence between observers, and no late-sync for a joiner who arrives after the drop is stale — a fresh joiner sees the anchor freeze near wherever your hand is at their join, not the original spot. A prop whose world position must agree across clients is `grab-prop`/`drop-on-player` territory.
- **Repoint the anchors per avatar.** Slide the `*Offset` GOs until the prop sits right — they are the consumer-editable layer (`AsChildAtRoot` discards edits on the proxy GO itself at build). `MouthOffset` ships a short lift forward of the head bone (see **Rig**); adjust to the avatar's lips.

## How it works

Local edges arbitrate off the anchor-proximity sensors and gestures and stamp `Mode` on rest-state entry; remotes re-derive every pose from `Mode` alone. Anchor changes crossfade the constraint weights over the anchor crossfade below.

Empirical constants (labeled in the YAMLs; `runtime.md` 90% rule):

| Constant | Value |
|---|---|
| Anchor crossfade | the `duration` on every rest-state transition in `controller.yaml` — **one value across all of them**, including the remote Exit edges. A mismatched edge shows as one anchor snapping while the others slide |
| World-drop dwell | the `heldR_dwell` / `heldL_dwell` clip lengths — the dwell *is* the WorldArm state length, so **the two hands' clips must agree**; feel-tunable |
| Grip blend | the `duration` on the Grip/Open edges in `gesture.yaml` |
| Arm / disarm thresholds | >0 / <0.00001 |
| Grip pose muscle values | see `gesture.yaml`; feel-tunable |

## Verifying the install

Post-bake the sync surface is the `Mode` int alone, and MA must have moved the four anchors onto Chest, both hands, and Head. The cheapest check that separates a correct install from a plausible-looking broken one: enable → Stowed, then fist the prop and release → HeldR — that alone exercises the sensor, the mode stamp, and the constraint crossfade. A remote clone re-derives the pose from the synced int alone.

Two things this entry specifically flags for the emulator pass: the **remote crossfade through the Exit→Entry hop** (if remote anchor changes snap instead of gliding, the exit-transition duration isn't surviving the hub — move durations onto explicit remote edges), and the **mouth-anchor chop exemption** (world origin, `EnableHeadScaling` only after the runtimes settle — the baseline-cache trap; then first-person: `MouthOffset` holds its authored offset while the head reads ~0.0001).

## Rig

    AnchorProp                        root — VRCFury FullController (FX + Gesture rows) + Toggle
    ├─ Container      (0, 1.1, 0.14)  VRCParentConstraint, sources [source0 StowOffset,
    │  │                              source1 HandROffset, source2 HandLOffset,
    │  │                              source3 MouthOffset, source4 WorldAnchor];
    │  │                              VRCContactSender sphere r=0.03, tag AnchorProp
    │  └─ Payload                     sphere, built-in default material — swap for your mesh
    ├─ WorldAnchor                    VRCParentConstraint, sources [HandROffset, HandLOffset];
    │                                 FreezeToWorld animated by the world clip
    ├─ HandRSense / HandLSense / MouthSense / StowSense
    │                                 VRCContactReceiver proximity, tag [AnchorProp], allowSelf
    │                                 only, localOnly; the COMPONENT lives at the module root
    │                                 (a receiver parented under an MA-moved anchor escapes
    │                                 VRCFury's param rewrite and reads 0 forever —
    │                                 `nondestructive.md`) while its `rootTransform` points at
    │                                 the offset, so only the sensing shape rides the anchor
    ├─ StowAnchor     (0, 1.1, 0)     MA BoneProxy → Chest, AsChildAtRoot
    │  └─ StowOffset  (0, 0, 0.14)    consumer-editable; constraint + shape target
    ├─ HandRAnchor                    MA BoneProxy → Right Hand   └─ HandROffset
    ├─ HandLAnchor                    MA BoneProxy → Left Hand    └─ HandLOffset
    └─ MouthAnchor    (0, 1.4, 0)     MA BoneProxy → Head, + VRCHeadChop {MouthAnchor @1} — the
       │                              chop-exempt head anchor (the load-bearing piece): without
       │                              its own chop exemption, first-person head chop collapses the
       │                              anchor *offset* toward the head pivot (parent scale
       │                              multiplies child local position) and your full-size prop
       │                              floats inside your head instead of sitting at your lips
       └─ MouthOffset (0, 0, 0.09)    consumer-editable lip point

    On a proxy-head rig (`head-proxy`) the humanoid head is already exempt — the MouthAnchor's
    own chop component is then redundant but harmless (exemptions multiply at 1×1).

Constraints `Locked`; source weights swapped by the clips only. No `GrabBone` here by design — `grab-prop`/`drop-on-player` own that name.

## Rebuilding

`controller.yaml` + `gesture.yaml` → `CompileController` → `built/` (two controllers plus the params asset).
