# leash (Module)

A leash anyone can grab, drag and stake to the ground, whose far end the avatar reports over OSC so the `vrc-bridge` mapping `osc_leash` can pull the wearer toward it. The same rig turns an existing tail into the leash. The shipped demo is a plain tube hanging from the hips.

## How it works

- The part people see never simulates. Each visible bone carries a parent constraint with two sources, a bone of an invisible copy of the chain (the **proxy**) and a joint of a drawn **rope**, and the animator slides the weight between them.
- The proxy carries the one grabbable physbone, stretched so its tip follows a hand anywhere. It hangs from `Holder`, which sits on the hips while the leash is free or held.
- Letting go after a pose (the in-game "pose" release) **plants** it. `Stake` freezes where the tip was, `Holder` fades to a node set so the proxy's tip rests exactly on the stake, and the visible bones fade onto the rope drawn from the hips to the stake.
- A hand at the stake grabs the proxy's tip. That is a **pick-up**: `Holder` fades back to the hips under the live grab and the visible bones fade back onto the proxy. A plain release sends the leash home; a pose release plants it again where the hand let go.
- A level box cage at the collar senses a point a fixed fraction of the way from the collar to the proxy tip (one over CONFIG's `ratio`), so its three readings give the tip's offset out to `ratio` times half a box. The animator publishes whether the leash is held or planted.
- Nothing is synced but the enable. A grab is natively networked, so every client runs the same fades from the same grab; the sensing is the wearer's alone.

## Install guide

1. Drop `Leash.prefab` at the avatar root, unrotated. `Collar` snaps to the Chest and `HipsAnchor` to the Hips on their own; drag `Collar/Offset` to the front of the neck.
2. For the demo, that is all: the tube under `HipsAnchor` is the visible leash. To use your own tail instead, follow §Adding it to a tail.
3. Build. The expression menu gains a `Leash` toggle, on by default and saved.
4. Run `vrc-bridge` with `[leash] enabled` and the same prefix, ratio, span and sender radius as this entry's CONFIG (the bridge's defaults match the shipped ones).

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

The OSC surface, all bare under `Leash/`, is the bridge mapping's contract:

| Parameter | Type | What writes it |
|---|---|---|
| `Leash/Right`, `Leash/Up`, `Leash/Forward` | float, sensing | one face-proximity box each on `Sense`, in the wearer's yaw frame |
| `Leash/Present` | bool, sensing | a Constant box of the same size on `Sense` |
| `Leash/Held` | bool, latching | the animator: 1 while a hand holds the leash, free or picked up |
| `Leash/Planted` | bool, latching | the animator: 1 from a plant until the next pick-up |

A reading decodes to metres as `ratio × (boxSize × reading − (boxSize/2 + senderRadius))`, and a reading of exactly 0 means the tip is outside the boxes. None of these is synced or saved. `Leash/Enable` is the one intent: synced, saved, default on, in the menu, and it takes VRCFury's instance prefix like everything the bridge does not read.

## Additional notes

- **One instance per avatar.** The published names are bare, so two copies would write the same parameters.
- **Off keeps the tail a tail.** With the toggle off the leash stays on the hips and the proxy physbone stays live, so a tail consumer keeps its physics; only the plant, the published flags and the sensing stop.
- **Only you sense the leash.** The boxes and the sender are local-only with a private tag, so nobody else's avatar can feed the bridge.
- **Your hand and anyone else's can grab it.** Who may grab or pose is the physbone's own filter, and the emulator cannot test either (`docs/emulator.md`).

## Performance stats

```c++
Constraints:        41       (5, plus 1 per visible bone, plus 4 per chain segment + 5 for the rope)
Constraint Depth:   27       (the demo; rank Good)
PhysBones:          3        (the proxy + 2 rope pendulums)
Contact Receivers:  4        (all local-only)
Contact Senders:    1        (local-only)
FX Animator Layers: 1        (7 states)
Skinned Meshes:     1        (the demo tube; a tail consumer adds none)
Synced parameters:  1 bit
```

## Knobs

Everything is `generate.py`'s CONFIG: edit, rerun, recompile `built/` as a unit, rebuild the prefab to `rig.json` (§Changing it). The values live in the code; `validate()` refuses the ones that break a relation below.

| Knob | What it does |
|---|---|
| `chain` | The consumer's chain, root first: each bone's visible binding path and its local pose under its parent. It sets the proxy, the rope's joint count, one visible constraint per bone, and `L`, the chain's rest chord that places `StakeRoot` |
| `leafVisible` | Whether the last bone gets a visible constraint. On for a mesh skinned to the tip; off for an unweighted `_end` leaf, which then rides its parent |
| `physbone` | The consumer's own settings for the proxy. `maxStretch`, grab and pose on, collision off and `resetWhenDisabled` on are fixed by the leash. `immobile` is the feel trade: World immobile above 0 makes a planted proxy's tip swing off the stake while the wearer walks, invisibly but away from the hand that reaches for it; World 0 or AllMotion holds it still, at a cost to the free feel no one has measured |
| `plantFade` | Frames for the plant's fades. Shorter makes the visible bones jump further per frame onto the rope; refused under 6, where the proxy is thrown |
| `pickupFade` | Frames for the pick-up's fades, at least `plantFade`. The grabbed tip trails the moving root through the whole fade and catches up in two frames after it, so the last frames show a jump either way |
| `cycleFrames` | Frames the proxy stays off after a plant, which clears its pose and rests it on the stake. A grab in those frames misses |
| `ratio`, `boxSize`, `senderRadius` | The sensing geometry. The bridge's `ratio`, `span` and `sender_radius` must match, or every reading decodes wrong. Raising `ratio` reaches further and resolves coarser |
| `tag` | The private collision tag the boxes and the sender share |
| `rope` | The pendulums' physbone and the spring-damping weights on the rope joints (`spring-damping`); the rope's swing is framerate-dependent |
| `enableDefault` | The enable's default |

**Provenance:** the idea's ancestor is OSCLeash (MIT, ZenithVal), which the bridge half re-derives; nothing here is ported from it. The rope's joint smoothing is `spring-damping`'s, its world pin `object-sync`'s idiom. The proxy chain, the plant and the pick-up are this entry's own.

## Design notes

The state-by-state walk is `generate.py`'s module docstring; `rig.json` holds every number the prefab is built to. This section states the invariants and why.

**The proxy rests tip-on-stake.** At a plant `Holder` goes not to the stake but to `StakeRoot`, a node one chain length back along the line toward the hips, captured and frozen in the plant frame and turned so the rested chain's tip lands on the stake. So a hand reaching for the stake finds the tip, nothing of the proxy pokes past the hand on a pick-up, a pose release from that grab re-plants exactly where the hand let go, and the proxy's root never moves while planted. `StakeAim`'s aim is frozen with the stake so the line stays the one captured at the plant.

**Moving a physbone's root under a live grab re-solves; it never resets.** Every fade moves `Holder` while someone may be holding the tip. The chain re-solves between the new root and the hand, a frame or more behind the root's travel, which is why a fade is never a switch.

**The plant ends with a cycle, after the fades land.** Turning the proxy's GameObject off and on with `resetWhenDisabled` returns it to rest and clears `_IsPosed` in the same frame, so the planted proxy lies straight along the leash line with no stale pose. Run inside the fade it shows; run after, it moves nothing visible.

**`_IsPosed` is read as a level at the release, never as an edge.** A re-grab leaves it set and only a plain release or the cycle clears it, so the machine asks "posed?" in the frame `_IsGrabbed` falls.

**The sensing cage is level and reads a scaled-down point.** `Sense` takes the collar's position and the avatar root's yaw only, so pitching the chest never tilts the frame. The sender rides `SenseProxy`, constrained to the collar carrier and the proxy tip in the weights `1 − 1/ratio` and `1/ratio`, which divides the offset by the ratio and multiplies the box's reach by it. The tip, not the stake, is what is read, so free, held and planted all report the same point.

**`globalParams` names the chain's base and its suffixes.** VRCFury rewrites a physbone's base parameter and the controller's `_IsGrabbed` separately, so the list carries `Leash/Chain*` rather than the bare base (`docs/gimmicks.md` §Packaging and interface). The enable stays prefixed because the bridge never reads it.

**Not built, a follow-on:** a slack-aware rope that goes straight at full length and loops deeper when short, blending the Bezier's control-point share by a proximity reading of the span. The rope here keeps one droop at every span.

## Adding it to a tail

The consumer seams are three: the collar point (`Collar`, an MA `BoneProxy` on the Chest), `HipsAnchor` (the chain's mount, the Hips for a tail), and the chain. The tail's own bones become the visible bones; the tail stops simulating itself.

**What the generator does.** Given the tail's bones in CONFIG's `chain` (each bone's path from the avatar root, starting with `/`, and its local pose), it emits a controller whose clips drive those bones' constraint weights, and a `rig.json` holding the proxy (a copy of the tail's hierarchy, same local poses, under `Holder`), the physbone fields for it, one two-source constraint per visible bone with its sources and any rotation offset the rope joint's frame needs, a rope of as many segments as the tail, and `StakeRoot`'s pose from the tail's rest chord.

**What you do by hand.** Build that `rig.json` in the prefab (the proxy, the rope's joints and the per-bone constraints), copy the tail's physbone settings into CONFIG and disable or remove the `VRCPhysBone` on the visible tail, point `HipsAnchor` at the tail's parent bone, then run `generate.py --check-prefab <your prefab>`.

**Worked example: a vendor tail.** The `Manuka_tail` chain is nine transforms, `Manuka_tail` through `.007` plus a `.007_end` leaf, eight segments and about 0.88 m. It takes `leafVisible: False`, so eight visible constraints; the rope grows to eight segments; the rig comes to 50 constraints by the stats formula. The tail's vendor physbone uses World immobile above 0, which is the `physbone.immobile` trade in §Knobs. Its rest pose curves, so `L` is its chord, not the sum of its bones.

## Traps

- **A tail whose bones do not point along +Z needs its rope rotation offsets.** The rope joints face along the rope with +Y up; `rig.json` gives each visible bone the offset that keeps its own axes. The demo's offsets are identity, so a non-zero one has not run.
- **Re-enabling reports Present one frame before the readings.** The Constant box acquires a step before the Proximity boxes, so for one frame Present is 1 with all three readings at 0. The bridge treats a 0 reading as no position, so it waits.
- **A plant from a long stretch morphs visibly.** Through the plant's fade the posed proxy rides `Holder` rigidly toward `StakeRoot`, so the visible bones blend between the rope and a proxy sliding off it; the further the hand had pulled, the bigger the step.
- **A pick-up trails the hand.** Through the pick-up's fade the grabbed tip lags the moving root and catches up two frames after it lands; the visible bones follow the proxy, so the tail end jumps once at the end.
- **A grab during the plant's fades snaps the visible bones onto the rope for a frame.** The grab exit is taken, and the pick-up's clip starts from the planted pose.
- **Turning the leash off while planted drops the plant in one frame**, and turning it on again comes up free.
- **Readings are in the avatar's own scale.** The boxes and the sender scale with the wearer, so at twice the height a reading means half as far in the world.
- **Do not rename anything under the prefab.** The clip paths are the hierarchy names.
- **Leave `assets/World.prefab` alone.** `Rope/Frame` is pinned to it at zero offset; never press Activate on that constraint.

## What is not proven here

Everything above is emulator evidence. In-client only: another player's grab and the grab and pose filters; a remote's and a late joiner's view (a late joiner does not see a live grab, and the frozen stake is each client's own capture, so a joiner sees the leash home until the next plant it witnesses); how immobile trades free feel for planted stillness on a real tail; the pull itself, which is the bridge's.

## Changing it

- **Regenerate as a unit.** Run `python generate.py`, recompile `built/` over the committed `.meta`s (`CONVENTIONS.md` §The gate), then rebuild whatever `rig.json` moved in the prefab: node poses, constraint sources and weights, the physbone fields, the rope's joints.
- **Run the check after every prefab edit.** `python generate.py --check` holds `Leash.prefab` to `rig.json`: `globalParams`, the FullController's assets, the four boxes' tags, size, rotation and flags, the sender, `SenseProxy`'s two weights, the proxy's poses and physbone, `StakeRoot`'s pose, every constraint's sources and the rope's world pin. `--check-prefab <path>` runs the same on a consumer's prefab, skipping the entry's own assets. Nothing runs it for you.

## Verifying the install

Run `--check` first. Then in play: the proxy tip and the tube's end sit together, and `Leash/Present` reads 1. Finding `Holder` or `Sense` at the avatar's feet means a `BoneProxy` never resolved. Grab the tube's end and drag it: `Leash/Held` rises and the three readings decode to the hand's offset from the collar. A decode that is off by a constant means the bridge's settings do not match CONFIG; one that reads nothing means `globalParams` lost a name and the parameter came out prefixed. Pose-release it: `Leash/Planted` rises, the tube turns into a rope from the hips to where you let go and stays there while you walk. Grab its end again: `Leash/Held` rises, `Planted` falls and the tube follows your hand; a plain release sends it home.

## Rig

    Leash                        root — VRCFury FullController (built/Leash_Fx, its menu and params)
    ├─ Collar                    MA BoneProxy → Chest; constraint source only
    │  └─ Offset                 the collar point: drag to the front of the neck
    ├─ HipsAnchor                MA BoneProxy → Hips; the chain's mount
    │  └─ V0 … V6                the demo's visible bones: parent constraint [proxy bone, rope joint]
    ├─ Sense                     position ← Collar/Offset; four local-only boxes: Right, Up, Forward, Present
    ├─ Holder                    parent ← [HipsAnchor, StakeRoot], weights animated
    │  └─ Chain → P1 … P6        the proxy: VRCPhysBone `Leash/Chain` on Chain
    ├─ Stake                     position ← the proxy tip; FreezeToWorld animated
    │  └─ StakeAim               aim ← HipsAnchor; FreezeToWorld animated with the stake's
    │     └─ StakeRoot           where Holder rests the proxy tip-on-stake
    ├─ SenseProxy                position ← [Sense, proxy tip] at the ratio's two weights; the sender
    ├─ Rope
    │  ├─ PendA, PendS           the Bezier's control points: one-bone pendulum physbones at each end
    │  └─ Frame                  pinned to assets/World.prefab; J0 … J6 (Bernstein position + aim),
    │                            T1 … T5 and M1 … M5 (the spring-damping pairs)
    └─ Tube                      the demo's 8-sided tube, skinned to V0 … V6, default material
