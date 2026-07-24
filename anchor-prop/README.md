# anchor-prop — multi-anchor self-syncing prop (Module)

A wearer-only prop that rests at any of five anchors — stowed on the chest, held in either hand, at the mouth, or frozen in the world — and moves between them on a fist grip. Swap the placeholder payload for your own prop (a pipe, a mic, a fan). One `VRCParentConstraint` multiplexes the five anchors and the whole rest state rides **one synced int** — no per-anchor sync — while the design carries what a single-anchor prop never meets: hand-to-hand handoff, a mouth anchor that survives first-person head chop, and a freeze-in-the-world band. `allowSelf`-only sensing keeps it wearer-only — the deliberate opposite of the instance-grabbable `grab-prop`/`drop-on-player`.

The five anchor classes, each a distinct mechanism (`gimmicks.md` §Anchor multiplexer — never the duplicate-object anchor swap):

- **Stow** (Chest) — a plain BoneProxy body anchor.
- **Either hand, with hand-to-hand handoff** — the transfer commits on the *receiving* hand while the giving hand still holds; handoff is its own arbitration case, not two independent takes (**How it works**).
- **Mouth** (Head) — the head anchor a serious multiplexer needs: it holds the prop hands-free and survives the first-person head chop that would otherwise collapse it (**Rig** carries the chop mechanism).
- **World** — a freeze-where-you-let-go band. Per-client capture: each client freezes at its own view of the release, so placements diverge by network delay — casual-prop grade, not a shared reference frame (`grab-prop`'s physbone sample-and-hold is the tighter drop; compose, don't grow this entry into it).

**Provenance:** the anchor-multiplexer + self-syncing-mode-int mechanism as vendor-proven by a vendor reference implementation (sensor → synced mode → actuator separation, commit-on-gesture-release, mouth anchor with chop handling, world-drop bands, hand-to-hand direction states) and in-house by our own gesture-release prop lineage. Nothing avatar-specific survives: placeholder payload, plain-humanoid anchor targets, a private contact tag.

## Interface

- **Params:**
  - `AnchorProp/Mode` (int, out) — synced, **unsaved**. The rest mode, banded: 0 Hidden (off-is-reset), 1 Stowed, 2 HeldR, 3 HeldL, 4 Mouth, 11 World (attach band 1–9, world band 11–19). 8 bits pre-compressor, stamped with Set only, so nothing blocks Parameter Compressor membership. Written only by the wearer's `localOnly` drivers; remotes re-derive every pose from it alone — no late-join park.
  - `AnchorProp/Enable` (bool, in) — **unsynced** menu intent (the VRCFury Toggle drives it via `globalParams`); the mode int carries the outcome, so the menu costs 0 sync bits.
  - `AnchorProp/NearHandR/L`, `NearMouth`, `NearStow` (float, sensing) — proximity of the **prop's own sender** (private tag `AnchorProp`) at each anchor point (`allowSelf` only — no stranger can take your prop; `localOnly` — remotes never need them). Prop-near-anchor sensing, not `Hand`-tag sensing, is what makes per-hand discrimination possible: a Hand-tag receiver on the prop cannot tell which hand arrived. Never synced/saved/menu-exposed.
  - `GestureRight`/`GestureLeft` (VRC built-ins) — Fist (1) is the grip gesture on both hands.
- **Seam:** VRCFury `FullController` on the prefab root with **two controller rows** — `built/AnchorProp_Fx.controller` (FX) and `built/AnchorProp_Gesture.controller` (Gesture) — plus `prms: built/AnchorProp_Fx_Parameters.asset` (the single sync-surface declaration; the Gesture document declares its shared param `scratch` so no second, drift-prone copy exists) and `globalParams: [AnchorProp/Enable]` for the Toggle. `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`. MA `BoneProxy` on the four body anchors only — placement you can see while authoring; every animated binding targets `Container`/`WorldAnchor`, which no BoneProxy touches, and the anchors carry only object references (path-immune).
- **Dependencies:** VRC SDK + VRCFury + Modular Avatar, and a **humanoid** avatar (the Gesture-playable merge refuses a generic rig; the BoneProxies resolve Chest/hands/Head through the humanoid mapping).
- **Required assets:** none — `Payload` is a placeholder sphere on the built-in default material; swap it for your prop mesh, keep it under `Container`.

## Before you compose it

- **The grip seizes only the holding hand.** Two Gesture-playable layers, masked per hand; the grip follows the mode (2 = right, 3 = left), so a handoff swaps which hand is seized. Gesture *params* keep firing — only the visible fingers are overridden.
- **The mouth anchor holds the prop without your hands.** While at the mouth both hands are free and un-seized; take it back with either hand (fist at your lips, release).
- **World placements are per-client.** Expect centimeter-grade divergence between observers, and no late-sync for a joiner who arrives after the drop is stale (the mode int replays the band, each client re-freezes at its current view of your hand — a *fresh* joiner sees the anchor freeze near wherever your hand is at their join, not the original spot). A prop whose world position must agree across clients is `grab-prop`/`drop-on-player` territory.
- **Repoint the anchors per avatar.** Slide the `*Offset` GOs until the prop sits right — they are the consumer-editable layer (`AsChildAtRoot` discards edits on the proxy GO itself at build). `MouthOffset` ships a short lift forward of the head bone (see **Rig**); adjust to the avatar's lips.

## How it works

Every take, place, and handoff **arms** on prop-near-anchor + Fist and **commits** on the gesture *release* — a zero-timer anti-misfire; a world drop additionally needs a held fist dwell clear of every anchor, because a bare fist-and-release is an everyday idle gesture. The menu holds only the enable, unsynced — the int carries the outcome. Local edges arbitrate off those live sensors + gestures and stamp `Mode` on rest-state entry; remotes re-derive from `Mode` alone through the **entry-dispatch hub**: each rest state exits on a foreign mode value, the entry ladder is the priority encoder, and an invalid value parks in `Guard` (poses Stowed, stamps nothing) until a valid mode arrives — park over wrong-state. Arm states are local-only transients holding the origin pose; disarm (the prop leaves the zone) outranks commit, so a same-frame leave+release takes nothing, and a handoff commits on the *receiving* hand's release while the giving hand still holds. The `HeldR`/`HeldL` arm ladders rank mouth > stow > handoff > world, so anchor proximity always beats the bare-fist world arm. Anchor changes crossfade the constraint weights over the anchor crossfade below — the prop glides.

Empirical constants (labeled in the YAMLs; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Anchor crossfade | the `duration` on every rest-state transition in `controller.yaml` — **one value across all of them**, including the remote Exit edges | held-prop lineage (emulator sweep). This is the glide; a mismatched edge shows as one anchor snapping while the others slide |
| World-drop dwell | the `heldR_dwell` / `heldL_dwell` clip lengths — the dwell *is* the WorldArm state length, so **the two hands' clips must agree** | chosen against idle-fist misfire (a bare fist-and-release is an everyday gesture); feel-tunable |
| Grip blend | the `duration` on the Grip/Open edges in `gesture.yaml` | held-prop lineage |
| Arm / disarm thresholds | >0 / <0.00001 | contact-tracker lineage |
| Grip pose muscle values | see `gesture.yaml` | eyeballed on the emulator rig; feel-tunable |

## Verifying the install

Post-bake the sync surface is the `Mode` int alone — Enable and all four sensing floats unsynced — and MA must have moved the four anchors onto Chest, both hands, and Head. Drive the local flow: enable → Stowed; fist at the prop arms without committing (mode holds while the grip is held); release → HeldR with the weight crossfade; fist the *left* hand at the prop, release it → HeldL (the handoff); fist at the lips, release → Mouth; hold a fist clear of every anchor past the world-drop dwell, release → World with `WorldAnchor.FreezeToWorld` reading 1; enable off → Hidden. A remote clone re-derives each pose from the synced int alone.

Two things this entry specifically flags for the emulator pass: the **remote crossfade through the Exit→Entry hop** (if remote anchor changes snap instead of gliding, the exit-transition duration isn't surviving the hub — move durations onto explicit remote edges), and the **mouth-anchor chop exemption** (world origin, `EnableHeadScaling` only after the runtimes settle — the baseline-cache trap; then first-person: `MouthOffset` holds its authored offset while the head reads ~0.0001). Finger-bone muscle application and true network timing land on the first real compose, in-game.

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

Constraints `Locked`; source weights swapped by the clips only. Unique object names (CONVENTIONS §Naming); no `GrabBone` here by design — `grab-prop`/`drop-on-player` own that name.

## Rebuilding

`controller.yaml` + `gesture.yaml` → `CompileController` → `built/` (committed; the prefab references both controllers and the params asset by GUID — recompile is GUID-stable; regenerate `built/` as a unit over the committed `.meta`s). The prefab is hand-maintained against the Rig section above.
