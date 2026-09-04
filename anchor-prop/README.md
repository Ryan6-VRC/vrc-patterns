# anchor-prop — multi-anchor self-syncing prop (Module)

A wearer-only prop that rests at any of five anchors — stowed on the chest, held in either hand, at the mouth, or frozen in the world — and moves between them on a fist grip; swap the placeholder payload for your own prop (a pipe, a mic, a fan). One `VRCParentConstraint` multiplexes the five anchors (`gimmicks.md` §Anchor multiplexer — never the duplicate-object anchor swap) and the whole rest state rides **one synced int**, so the design carries what a single-anchor prop never meets: hand-to-hand handoff, a mouth anchor that survives first-person head chop, and a freeze-in-the-world band. `allowSelf`-only sensing keeps it wearer-only — the deliberate opposite of the instance-grabbable `grab-prop`/`drop-on-player`.

**Provenance:** the anchor-multiplexer + self-syncing-mode-int mechanism as vendor-proven by a vendor reference implementation, and in-house by our own gesture-release prop lineage.

## Ground truth

`gesture.yaml` carries the grip half because humanoid muscle curves cannot live in FX. `Mode` is a plain int written with Set only by the wearer's `localOnly` drivers, so it stays Parameter-Compressor-eligible; the `Enable` menu intent is unsynced and the int carries the outcome.

- **Seam:** VRCFury `FullController` on the root with two controller rows (FX + Gesture); `basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`. MA `BoneProxy` sits on the four body anchors only, and every animated binding targets `Container`/`WorldAnchor`, which no BoneProxy touches (path-immune).
- **The contact receiver *component* lives at the module root, never under an MA-moved anchor.** A receiver parented under an MA-moved anchor escapes VRCFury's param rewrite and reads 0 forever (`nondestructive.md`); its `rootTransform` points at the offset instead, so only the sensing shape rides the anchor.
- **The `MouthAnchor` carries its own `VRCHeadChop` exemption.** Without it, first-person head chop collapses the anchor *offset* toward the head pivot (parent scale multiplies child local position) and a full-size prop floats inside your head instead of sitting at your lips. On a proxy-head rig (`head-proxy`) the humanoid head is already exempt, so the chop is redundant but harmless — exemptions multiply at 1×1.

## Before you compose it

- **The grip seizes only the holding hand**; a handoff swaps which hand is seized, and the mouth anchor holds the prop with both hands free and un-seized. Gesture *params* keep firing — only the visible fingers are overridden.
- **World placements are per-client.** Expect centimeter-grade divergence between observers, and no late-sync: a fresh joiner sees the freeze near wherever your hand is at their join, not the original spot. A world position that must agree across clients is `grab-prop`/`drop-on-player` territory.
- **Repoint the anchors per avatar** by sliding the `*Offset` GOs — they are the consumer-editable layer (`AsChildAtRoot` discards edits on the proxy GO itself at build). Swap the placeholder `Payload` sphere for your prop, kept under `Container`.
- **Humanoid only:** the Gesture-playable merge refuses a generic rig, and the BoneProxies resolve Chest/hands/Head through the humanoid mapping.

## Measured

Tuned constants live once at the sites named; `runtime.md`'s 90% rule governs changing any of them.

- **Anchor crossfade** — the `duration` on every rest-state transition in `controller.yaml`, one value across all of them including the remote Exit edges; a mismatched edge shows as one anchor snapping while the others slide.
- **World-drop dwell** — the `heldR_dwell` / `heldL_dwell` clip lengths; the two hands' clips must agree, feel-tunable.
- **Grip blend** — the `duration` on the Grip/Open edges in `gesture.yaml`.
- **Arm / disarm thresholds** — the proximity comparisons on the arm and disarm edges in `controller.yaml`: arm on positive proximity, disarm on an epsilon floor.

## Verifying the install

Post-bake the sync surface is the `Mode` int alone, and MA must have moved the four anchors onto Chest, both hands, and Head. The cheapest check separating a correct install from a plausible-broken one: enable → Stowed, then fist the prop and release → HeldR — that alone exercises the sensor, the mode stamp, and the constraint crossfade, and a remote clone re-derives the pose from the synced int. Two things need the emulator pass: the **remote crossfade through the Exit→Entry hop** (remote anchor changes that snap instead of gliding mean the exit-transition duration isn't surviving the hub — move durations onto explicit remote edges), and the **mouth-anchor chop exemption** in first-person (`EnableHeadScaling` only after the runtimes settle — the baseline-cache trap).
