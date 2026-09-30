# leash (Module)

A leash anyone can grab, drag and stake where they let go, whose far end the avatar reports over OSC so an external bridge (`vrc-bridge`, its `osc_leash` mapping) can pull the wearer toward it. The same rig can take over an existing tail. The shipped demo is a plain tube hanging from the hips.

## How it works

- The leash you see (the demo tube, or your tail) has no physbone of its own. Each of its bones follows two invisible guides through a two-source parent constraint, and the animator slides the weight between them.
- One guide is the **proxy**: an invisible copy of those bones carrying the one grabbable physbone, allowed to stretch far so its last bone (the **tip**) follows a hand. The proxy hangs from `Holder`, which sits on the hips while the leash is free or held.
- The other guide is the **rope**: a curve of constraint-placed joints from `RopeRoot` (bone 0's rest point on the hips) to the stake, sagging on two small pendulum physbones.
- Letting go with a pose (VRChat's physbone pose release) **plants** the leash. `Stake` freezes where the tip was. `Holder` fades to `StakeRoot`, a frozen node placed so the resting proxy's tip lies on the stake. The visible bones fade onto the rope.
- Grabbing the planted end grabs the proxy's tip: a **pick-up**. `Holder` fades back to the hips under the live grab, and the visible bones fade back onto the proxy. A plain release sends the leash home; a pose release plants it again where the hand let go.
- Three contact boxes at the neck, held level, read where the tip is. They read a point a fixed fraction of the way out to it (the `ratio` knob), which multiplies the boxes' reach by the same factor. The animator also publishes whether the leash is held or planted.
- Nothing is synced but the menu toggle. A grab is networked by VRChat itself, so every client runs the same fades; the sensing runs on the wearer's client only.

## Install guide

1. Drop `Leash.prefab` at the avatar root, unrotated. Edit the instance or an owned copy, never the package asset. `Collar` snaps to the Chest and `HipsAnchor` to the Hips on their own; drag `Collar/Offset` to the front of the neck.
2. For the demo, that is all: the tube under `HipsAnchor` is the leash. Taking over your own tail is a build, not an install step (§Ground truth).
3. Build. The expression menu gains a `Leash` toggle.
4. For the pull, run `vrc-bridge` with its `[leash]` section enabled. Its `prefix`, `ratio`, `span` and `sender_radius` must equal this entry's `prefix`, `ratio`, `boxSize` and `senderRadius`; both sides ship matching defaults.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- Grab the tube's end and walk it anywhere; it stretches to follow your hand. A plain release lets it spring back to your hips.
- Release it with a pose and it stays staked where your hand was, drawn as a rope from your hips, while you walk around it.
- Grab the staked end to pick it up; a plain release sends it home, a pose release stakes it again.
- With the bridge running, a held or staked leash pulls you toward its end.

The bridge reads six parameters, published without VRCFury's prefix and none of them synced. `Leash/Right`, `Leash/Up`, `Leash/Forward` (one face-proximity box each, in your yaw frame) and `Leash/Present` (a Constant box of the same size) are momentary sensing outputs: each reports the tip where it is now and holds nothing, so sample them. `rig.json`'s `sensing.decode` turns a reading into metres; a reading of exactly 0 means the tip is outside the boxes. `Leash/Held` and `Leash/Planted` are latching: the animator sets them and holds them until the leash changes state. The menu toggle drives `Leash/Enable`, the only synced parameter: saved, on by default (CONFIG `enableDefault`), and under VRCFury's instance prefix.

## Additional notes

- **One instance per avatar.** The published names are unprefixed, so two copies would write the same parameters.
- **Off leaves the tail a tail.** With the toggle off the leash stays on the hips and the proxy physbone stays live, so a tail keeps its physics; the plant, the published flags and the sensing stop. Turning it off while planted drops the plant in one frame.
- **Only you sense the leash.** The boxes and their sender are local-only on a private tag, so no other avatar can feed your bridge.
- **Who may grab it is the proxy physbone's own filter.** Anyone can by default; the emulator cannot test either filter (`emulator.md`).
- **A late joiner sees the leash at home** until the next plant they witness: a live grab does not reach them and the stake is each client's own capture (`runtime.md` §PhysBones).
- **Do not rename anything under the prefab.** The clip paths are the hierarchy names.
- **Leave `assets/World.prefab` alone.** `Rope/Frame` is pinned to it and its source offset must stay zero, so never press Activate on that constraint.

## Performance stats

```c++
Constraints:        41       (5, plus 1 per visible bone, plus 4 per chain segment and 5 for the rope)
Constraint Depth:   27       (the demo; past Excellent, inside Good)
PhysBones:          3        (11 transforms: the proxy and 2 per rope pendulum)
Contact Receivers:  4        (local-only: none count toward rank)
Contact Senders:    1        (local-only)
FX Animator Layers: 1
Skinned Meshes:     1        (the demo tube, one default-material slot; a tail consumer deletes it)
Synced parameters:  1 bit
```

## Knobs

Everything is `generate.py`'s CONFIG: edit, rerun, recompile `built/` as a unit, rebuild the prefab to `rig.json` (§Changing it). The values live in the code; `validate()` refuses the ones that break a relation below.

| Knob | What it does |
|---|---|
| `prefix` | The published names' prefix, and the proxy physbone's `<prefix>/Chain`. The bridge's `prefix` must match |
| `chain` | The consumer's bones, root first: each one's binding path and local pose. It sets the proxy, the rope's segment count, one visible constraint per bone, and the poses of `RopeRoot` and `StakeRoot`, from the bones' rest pose |
| `leafVisible` | Whether the last bone gets a visible constraint: on for a mesh skinned to the tip, off for an unweighted end leaf, which then rides its parent |
| `physbone` | The consumer's own settings for the proxy; what makes it a leash is fixed in `FIXED_PHYSBONE`. `immobile` is the feel trade: World immobile swings a planted proxy's tip off the stake while the wearer walks, invisibly but away from the hand reaching for it, and World 0 or AllMotion holds it still at an unmeasured cost to the free feel |
| `plantFade` | Frames for the plant's fades. Shorter makes the visible bones jump further per frame; `validate()` sets a floor below which the proxy is thrown |
| `pickupFade` | Frames for the pick-up's fades, at least `plantFade` (§Traps) |
| `cycleFrames` | Frames the proxy stays off after a plant, which clears its pose and rests it on the stake. A grab in those frames misses |
| `ratio`, `boxSize`, `senderRadius` | The sensing geometry, the bridge's `ratio`, `span` and `sender_radius` in that order; a mismatch mis-decodes every reading. Raising `ratio` reaches further and resolves coarser |
| `tag` | The private collision tag the boxes and the sender share |
| `rope` | The pendulums' physbone and the spring-damping weights on the rope joints (`spring-damping`), whose swing is framerate-dependent |
| `controller`, `enableDefault` | The emitted controller's name and the toggle's default |

**Provenance:** the idea's ancestor is OSCLeash (MIT, ZenithVal), which the bridge half re-derives; nothing here is ported from it. The rope's joint smoothing is `spring-damping`'s, its world pin `object-sync`'s idiom. The proxy chain, the plant and the pick-up are this entry's own.

## Design notes

The state-by-state walk is `generate.py`'s module docstring; `rig.json` holds every number the prefab is built to.

**The proxy rests tip-on-stake.** Planted, `Holder` sits on `StakeRoot`, not on the stake. So a hand reaching for the stake finds the tip, not the proxy's root. A pose release from that grab re-plants where the hand let go, and the proxy's root never moves while planted. `StakeAim` is frozen with the stake so the leash line stays the one captured at the plant.

**Every move of `Holder` is a fade.** Someone may be holding the tip, and a physbone whose root moves under a live grab re-solves rather than resetting, but behind the root's travel, so a switch would throw the proxy.

**The plant ends with a proxy cycle, after the fades land.** Turning the proxy off and on with `resetWhenDisabled` clears its pose and returns it to rest, so the planted proxy lies straight along the leash line; run after the fades, the cycle moves nothing visible.

**`_IsPosed` is read when `_IsGrabbed` falls.** A re-grab leaves it set, so the machine reads it as a level at the release, never as an edge.

**The tip is what is read, not the stake**, so free, held and planted all report one point. The sensing frame takes the collar's position and the avatar root's yaw only, so pitching the chest never tilts it.

**`Leash/Chain*` is on `globalParams`** so an OSC reader can see the grab and the pose themselves; the wildcard keeps the physbone's base name and the controller's suffixed names matched (`gimmicks.md` §Packaging and interface). The toggle takes VRCFury's instance prefix: the bridge never reads it.

**Off keeps the proxy live**, against `gimmicks.md`'s off-state hygiene, because for a tail consumer the proxy is the tail's only physics.

## Ground truth

The consumer seams are three: the collar point (`Collar/Offset`, under an MA `BoneProxy` on the Chest), `HipsAnchor` (the chain's mount: the Hips for a tail), and the chain.

**Taking over a tail.** The tail's own bones become the visible bones and stop simulating themselves.

- *What the generator does:* from the tail's bones in CONFIG's `chain` (each bone's path from the avatar root, starting with `/`, and its local pose as the vendor prefab carries it) it emits a controller that drives those bones' constraint weights, and a `rig.json` with the proxy, its physbone fields, `RopeRoot`, one two-source constraint per visible bone with its rope rotation offset, a rope of as many segments as the tail, and `StakeRoot`'s pose.
- *The rope rotation offsets* are taken against a frame set on bone 0's segment and carried down the chain by the minimal rotation between segments, so a tail lying along a straight rope keeps each bone's rest twist against its parent.
- *`RopeRoot`* is an unrotated child of `HipsAnchor` at bone 0's rest position. The rope starts there and `StakeAim` aims at it, so a planted bone 0 stays on its socket; a rope started at `HipsAnchor` itself holds bone 0 off its socket by bone 0's own offset.
- *What you do by hand:* work on an owned copy of this folder in your venue, since `generate.py` rewrites `controller.yaml` and `rig.json` beside itself. Put the rig under the avatar root in an avatar prefab (a variant of the vendor's leaves the vendor untouched), build the proxy, `RopeRoot` and the rope from `rig.json`, and put each visible constraint on the tail's own bone. Delete `HipsAnchor/V0` and `Tube`, and retarget `HipsAnchor`'s BoneProxy to the tail's parent bone.
- *The proxy's physbone:* copy the tail's `VRCPhysBone` whole onto the proxy root, then set the leash-owned fields (`FIXED_PHYSBONE` and `parameter`) and CONFIG's `physbone` values over it, and empty its colliders and ignore list. CONFIG carries no curves, so the whole-component copy is what keeps the vendor's radius and other curves. Then remove the tail's own `VRCPhysBone` (a disabled one still counts toward rank); the proxy's collision is off, so the tail's colliders stop acting.
- *Checking it:* `generate.py --check-prefab <avatar prefab>` holds the rig's own nodes, `RopeRoot` and the rope's start included, resolving every path from the FullController's GameObject, so it runs on the avatar prefab the rig sits in. It skips every `/`-rooted bone, so compare each tail bone's constraint against `rig.json`'s `visible` list yourself: sources proxy then joint, rest weights 1 and 0, zero position offsets, and the joint source's rope rotation offset.

**Worked example: a vendor tail.** Nine transforms whose `_end` leaf carries no skin weight take `leafVisible: False`: eight visible constraints on the tail's own bones, an eight-segment rope, and 50 constraints, as §Performance stats's formula gives and a bake census of the build matches. The bones point along +Y rather than +Z, so every rope rotation offset is non-identity. Bone 0 sits 68 mm from the hips' origin, the gap `RopeRoot` closes. The vendor physbone's World immobile carries over as the `physbone` trade in §Knobs.

## Traps

- **A tail whose bones do not point along +Z needs its rope rotation offsets.** On the rope a bone takes the joint's frame, +Z along the rope and +Y up, and `rig.json` gives each visible bone the offset that keeps its own axes. A tail twisting only while planted has wrong offsets.
- **A plant from a long stretch morphs visibly.** Through the plant's fades the posed proxy rides `Holder` rigidly toward `StakeRoot`, so the visible bones blend between the rope and a proxy sliding off it; the further the hand had pulled, the bigger the step.
- **A pick-up trails the hand**, through the whole fade and for a few frames after it, so the visible end catches up in large steps at the end whatever `pickupFade` is.
- **A grab during the plant's fades throws the proxy.** The machine takes the pick-up, but its clip starts from the planted pose, so the visible bones snap onto the rope and the tip leaves the hand for a few frames.
- **`Present` can read 1 while a reading is still 0**, as on re-enabling, when the Constant box can acquire before the Proximity boxes. A reading of 0 is never a position: treat it as no reading whatever `Present` says, as the bridge does.
- **A plant made while walking captures a little behind the tip.** The stake trails the tip by about one frame of the wearer's travel.
- **Readings are in the avatar's own scale.** The boxes and the sender scale with the wearer, so at twice the height a decoded metre is two in the world.
- **The rope's up is the chain parent's +Y at rest.** The rope rotation offsets and `StakeRoot` are computed with the chain parent's +Y as world up, which holds for the Hips on an upright rest pose; a chain parent rotated at rest tilts every bone on the rope by that rotation.
- **Unequal bones stretch unevenly on the rope.** The rope's joints are evenly spaced, so a bone shorter than its rope segment stretches on the rope and a longer one compresses, with the mesh skinned to it.
- **A held tail's visible end stops short of the hand.** An unweighted end leaf (`leafVisible: False`) keeps its rest length on its parent while the proxy's last segment stretches to the hand, so the visible end falls short by that segment's stretch.
- **A planted rope bent hard at its first joint twists bone 1.** The joints aim with world up, so where the rope turns sharply at `J1` bone 1 rolls against bone 0: 30° under a 1 m walk with a 30° turn, recovering as the rope straightens.
- **The demo tube can cull.** Its bounds ride its root bone at the hips, so a leash staked far away can vanish when only its far end is on screen.

## What is not proven here

Needs the client: another player's grab and the grab and pose filters; a remote's and a late joiner's view; how immobile trades free feel for planted stillness on a real tail; the pull itself, which is the bridge's. Unverified anywhere: a real hand's grab during the plant's fades, a plant made while walking, and avatar scale.

## Changing it

- **Regenerate as a unit.** Run `python generate.py`, recompile `built/` over the committed `.meta`s (`CONVENTIONS.md` §The gate), then rebuild whatever `rig.json` moved in the prefab.
- **Run the check after every prefab edit.** `python generate.py --check` holds `Leash.prefab` to CONFIG. Of the rope it reads only the start: `RopeRoot`'s pose, `J0` and each Bezier point's first source on it, and the pendulums' ends there. It does not read the joints' smoothing and aims, the pendulum physbones or `Sense`'s constraint; rebuild those from `rig.json` and read them yourself. Nothing runs it for you.

## Verifying the install

Run `--check` first. Then in play: the tube's end sits on the proxy tip and `Leash/Present` reads 1. `Holder` and `Sense` hanging at their authored heights rather than on your hips and neck means a `BoneProxy` never resolved. Grab the end and drag it: `Leash/Held` rises and the three readings decode to the hand's offset from the collar point. A decode off by a fixed amount means the bridge's `sender_radius` differs; off by a factor, its `ratio` or `span`. `Leash/Held` never rising while the tube follows the hand means the physbone came out prefixed: `globalParams` lost `Leash/Chain*`. A tail that twitches or moves twice still carries its own physbone. Pose-release it: `Leash/Planted` rises and the tube becomes a rope to where you let go. Grab its end again: `Held` rises, `Planted` falls and the tube follows your hand; a plain release sends it home.

## Rig

    Leash                        root — VRCFury FullController (built/Leash_Fx, its menu and params)
    ├─ Collar                    MA BoneProxy → Chest
    │  └─ Offset                 the collar point: drag to the front of the neck
    ├─ HipsAnchor                MA BoneProxy → Hips; the chain's mount
    │  ├─ RopeRoot               bone 0's rest point: where the rope starts
    │  └─ V0 … V6                the demo's visible bones: parent constraint [proxy bone, rope joint]
    ├─ Sense                     position ← Collar/Offset; four local-only boxes: Right, Up, Forward, Present
    ├─ Holder                    parent ← [HipsAnchor, StakeRoot], weights animated
    │  └─ Chain → P1 … P6        the proxy: VRCPhysBone `Leash/Chain` on Chain
    ├─ Stake                     position ← the proxy tip; FreezeToWorld animated
    │  └─ StakeAim               aim ← RopeRoot; FreezeToWorld animated with the stake's
    │     └─ StakeRoot           where Holder rests the proxy tip-on-stake
    ├─ SenseProxy                position ← [Sense, proxy tip] at the ratio's two weights; the sender
    ├─ Rope
    │  ├─ Frame                  pinned to assets/World.prefab; under it J0 … J6 (position, aim at the
    │  │                         next joint), T1 … T5 (the Bezier: position over RopeRoot, the two
    │  │                         pendulum tips and Stake) and M1 … M5 (spring-damping between T and J)
    │  └─ PendA, PendS           position + aim at each end; the pendulum physbone on their Bone child
    └─ Tube                      the demo tube, skinned to V0 … V6, default material
