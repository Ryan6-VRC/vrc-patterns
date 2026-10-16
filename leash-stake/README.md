# leash-stake (Module)

A leash you can stake. Anyone can grab it and drag it. Released with a pose, it stays planted where the hand let go, and every client, late joiners included, sees it there. With the optional `vrc-bridge` desktop app running (it reads your avatar's parameters over OSC and drives your movement), a held or planted leash pulls you toward its end. The leash is a strand your avatar already has, such as a collar chain or a necklace.

Two ways in: drop the shipped demo, a collar whose rope hangs from the neck (§Install guide, four steps), or turn a strand you already have into the leash (§Using your own strand, which runs `generate.py`).

## How it works

- The strand is never grabbed itself. It keeps its own physbone, with grabbing turned off. A hand grabs an invisible one-bone grab bone instead, whose resting point `Home` is part way along the strand.
- Each strand bone has one parent constraint with two sources: its own physics, and a point on a straight line from `Start` (the strand's root) to `Stake` (the leash's far end). Free, the bone follows its own physics, which changes nothing. Held or planted, it follows that line. The animator fades between the two.
- `Stake` follows the grab bone's tip, so a held strand runs from your neck to the hand.
- A pose release (VRChat's: letting go of a grab while posing it) plants the leash. `Stake` freezes in the world. The grab bone moves onto `Stake` and switches off for a moment, which clears its pose so it can be grabbed there.
- Grabbing the planted end picks it up: the strand runs to the hand again. A plain release sends the strand back onto its own physics, and a pose release plants it again.
- Two contact boxes at `Start` read where `Stake` is, for the bridge. They take your position and your avatar's yaw only, so tilting your chest never tilts the reading. The animator also publishes whether the leash is held or planted.
- The planted position is shared through a nested position-only `object-sync` (`../object-sync/README.md`). You measure `Stake`; a synced bool tells other clients when the position they have is the planted one, and they end their strand there.
- A grab is networked by VRChat itself, so every client runs the same fades. The sensing runs on your client only.

## Install guide

For the demo collar:

1. Drop `LeashStake.prefab` at the avatar root, unrotated. Edit the instance or an owned copy, never the package asset. The prefab's `Mount` node snaps itself to your Neck bone, and the demo adds a visible collar and rope there.
2. Add `anti-cull` to the avatar (`../anti-cull/README.md`). Without it, another player who looks away stops running your animator and loses the planted position.
3. Build. The expression menu gains a `Leash` toggle.
4. For the pull, run `vrc-bridge` with `[leash]` enabled in its config. Both sides ship matching defaults; a changed sensing knob must change on both (§Knobs).

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- Reach for the strand and grab it; it follows your hand anywhere within reach. A plain release lets it fall back onto its own physics.
- Release it with a pose and it stays planted where your hand was, drawn as a line from your neck, while you walk around it.
- Grab the planted end to pick it up; a plain release lets it fall back onto its own physics, a pose release plants it again.
- With the bridge running, a held or planted leash pulls you toward its end.
- The `Leash` toggle drives `Leash/Enable`. Off is the reset: it drops a planted leash, frees the strand, and switches the grab bone and the sensing off.

## Additional notes

- **One instance per avatar.** The published names are unprefixed, and `ObjectSync/Enable` is one parameter shared by every `object-sync` build on the avatar.
- **Another `object-sync` build can share the avatar.** This one parks and tags its contacts from its own `rigSeed`, so they do not collide with another build's.
- **A late joiner sees the leash free for a moment**, until its copy of the sync rig has a whole position and the synced bool, then plants it there. A leash held at the moment someone joins reads as free to them, since a live grab does not reach a late joiner (`../../docs/runtime.md` §PhysBones).
- **Only you sense the leash.** The boxes and their sender are local-only on a private tag, so no other avatar can feed your bridge.
- **Who may grab it is the grab bone's own filter.** Anyone can by default; the emulator cannot test the grab filter (`../../docs/emulator.md` §Induce a physbone grab/pose).
- **The bridge reads five parameters**, published without VRCFury's prefix and none of them synced. `Leash/Right` and `Leash/Forward` are momentary readings, so sample them; `rig.json`'s `sensing.decode` turns one into metres, and a reading of exactly 0 means `Stake` is outside the boxes. `Leash/Held` and `Leash/Planted` latch until the leash changes state. `Leash/Slack` is a default the bridge reads once: metres of free travel before it pulls.
- **Do not rename anything under the prefab.** The animation clips find their targets by hierarchy path, so a rename silently breaks them.
- **The only menu is the `Leash` toggle.** `object-sync/built/ObjectSync_Fx_Menu.asset` is generated with the sync build and stays unwired.

## Performance stats

```c++
Constraints:        6 + 2 per strand bone, plus 9 for the sync rig (29 on the demo; an optimizer may drop the sync rig's unused ones)
Constraint Depth:   12       (on the demo avatar, built; within the Excellent rank limit)
PhysBones:          1        (the grab bone, 2 transforms; no colliders, no collision checks)
Contact Receivers:  8        (2 sensing boxes, 6 in the sync rig; all local-only, none count toward rank)
Contact Senders:    3        (local-only)
FX Animator Layers: 10       (not a rank stat: the leash, its announce, and object-sync's 8)
Bones:              2        (the grab bone; the demo adds its collar's 8)
Skinned Meshes:     1        (the demo collar: 1092 triangles, 3 materials; a strand of your own adds no mesh)
Synced parameters:  29 bits  (not a rank stat: Leash/Enable, the announce bool, ObjectSync/Enable and 26 wire bits)
```

The demo collar adds a skinned mesh, so an avatar already at the Good rank's skinned-mesh limit drops to Medium. The 29 synced bits can push an avatar past VRChat's 256-bit parameter budget, where VRCFury's Parameter Compressor starts compressing menu toggles, `Leash/Enable` among them.

## Knobs

Everything is `generate.py`'s CONFIG, or a consumer's JSON over it (§Using your own strand). `validate()` refuses the values that break a relation below; §Changing it says what to rebuild.

| Knob | What it does |
|---|---|
| `prefix` | The published names' prefix and the grab bone's `<prefix>/Handle`. The bridge's `prefix` must match |
| `internal` | The announce bool's prefix. Required, and never under `prefix`, so the published wildcard cannot reach it |
| `ratio`, `boxSize`, `senderRadius` | The sensing geometry: the bridge's `ratio`, `span` and `sender_radius`, so a mismatch mis-decodes every reading. Raising `ratio` reaches further and resolves coarser |
| `slack` | `Leash/Slack`'s default: free travel before the bridge pulls |
| `chain`, `endpoint` | The strand's bones, root first, and the last bone's visible end. They set `Start`'s pose, the line's points and one strand constraint per bone. `endpoint` must equal the strand physbone's `endpointPosition` |
| `homeAt`, `home` | Where the grab bone rests: `homeAt` of the way along the strand from its root (1 is the tip), or `home`, a pose measured where your strand settles. The grab volume is a sphere around this point |
| `handle` | `radius` is that sphere's size; it must cover the strand's swing. `length` × (1 + `maxStretch`) is the reach. `pull` and `spring` are the release's feel: how fast the line retracts after a plain release |
| `mount`, `mountRot` | The bone the demo's `Mount` snaps to, and `Mount`'s rest rotation against the avatar root, which sets the strand's twist on the line |
| `fade` | Frames of the strand's fade each way. Shorter moves the strand further per frame |
| `cycle` | Seconds a plant holds the grab bone off; a grab then misses. `validate()` refuses under three frames |
| `announce` | Seconds from a plant to the synced bool. It must outlast an `object-sync` measure cycle and a wire refresh (`../object-sync/README.md` §How it works), or a remote plants at the position from before the plant |
| `rigSeed` | The sync rig's contact tags and park, which move together. Unique among the avatar's `object-sync` builds |
| `tag`, `controller`, `enableDefault` | The sensing contacts' private tag, the emitted controller's name, `Leash/Enable`'s default |

**Provenance:** the idea's ancestor is OSCLeash (MIT, ZenithVal), which the bridge half re-derives; nothing here is ported from it. The planted position rides `object-sync`, merged through one component the way `compositions/grab-sync` merges it. The worked example's strand is the necklace on PINKPUDDING's Peridot costume. The grab bone on the strand, the self-sourced fade and the plant are this entry's own.

## Design notes

`generate.py`'s module docstring is the node-by-node and state-by-state walk; `rig.json` holds every number the prefab is built to. What follows is why.

**The strand stays its own physbone.** A physbone's settings bake when the chain starts, so one chain cannot be a loose necklace and a stretched leash. Leaving the strand alone keeps its free behaviour as the vendor shipped it; the grab bone carries the stretch, the grab and the pose.

**Self at full weight is a no-op.** A constraint on a bone inside a live chain reads the solved pose and the solver keeps solving underneath, so a free strand is the vendor's physics (to float precision, in av3emu) and a release fades onto the chain's current pose with nothing toggled.

**`Home` hangs from `Start`, never from a strand bone.** Under a strand bone the line would write that bone onto the grab bone's tip, its own child, and the grab bone would chase itself a bone length a frame.

**The line ends on `Stake`, not on the grab bone's tip.** In the plant frame the tip has already reset while `Holder` has not moved, so a line read off the tip flashes to the collar for a frame.

**The last bone's visible end lands on `Stake`**, so the hand holds the strand's end and its root stays in its socket.

**`Holder` is frozen through a pick-up**, because it follows `Stake`, which rides the grab bone's own tip.

**A remote has one planted state**, reached from free (a late joiner) or from planted (a client that saw the plant). A remote's pick-up is the wearer's own pick-up state, since the wearer unfreezes `Stake` the moment a pick-up starts.

**`ObjectSync/Enable` defaults on here** although `object-sync`'s own build declares it off: the leash's controller and parameters sit first in the one `FullController`, so its declaration wins that merge, and `--check` pins the order. A second `object-sync` build on another component can win instead (`../object-sync/README.md` §How it works, its Seam bullet).

## Traps

- **A release fade compounds down the strand.** Each bone's self source rides its parent's already-blended pose, so the strand's end lags on the line and catches up toward the fade's end, worst after a pick-up, whose line still ends at the old planted spot. In av3emu after a 2.3 m pick-up, a three-bone necklace's per-frame steps rose from 0.15 to 0.39 m through the fade, and a seven-bone rope's last frame jumped over a metre.
- **A grab near the strand can land on a neighbour.** VRChat takes the nearest grabbable bone, so another chain whose sphere is nearer than the grab bone's (a body or costume chain under a necklace) takes the grab. Place `Home` and size `radius` against the neighbours, not just the strand.
- **A held strand is rigid pieces spaced along a line.** Each bone keeps its mesh at rest length, so a stretched chain's links spread apart; a skinned rope stretches between its bones instead.
- **A hand closer to the root than the last bone is long folds the strand**, since the last point then sits behind `Start`.
- **Readings are in the avatar's own scale.** The contact shapes scale with the wearer, so at twice the height a decoded metre is two in the world (this rig is unmeasured at scale).
- **Avatar Optimizer renames the rig.** Trace and Optimize merges a component-less node away and hoists its children as `<parent>$<child>$<n>`: on the demo, `Mount` goes and `Start` reads `Mount$Start$0` under the Neck. Search a built avatar by suffix.
- **A strand twisting only while held** has the wrong `mountRot`.

## What is not proven here

Needs the client: another player's grab and the grab filter; a remote that saw the plant moving onto the shared position (an emulator clone never sees a grab); the network timing of the synced bool against the position; the release's feel; the pull itself, which is the bridge's. Unverified anywhere: a stretched skinned strand near the client's 10 m bounds cap, and avatar scale.

## Using your own strand

The seams are three: the bone the strand hangs from (`Mount`), the strand's bones, and the strand's own physbone.

1. **Write the strand's keys** in a JSON file in your venue: `chain` (each bone's binding path from the avatar root, starting with `/`, and its local pose as the prefab carries it, bone 0's pose being in the frame of the bone it hangs from), `endpoint` (its physbone's `endpointPosition`), `controller`, and any knob to change, `handle.radius` especially.
2. **Generate and compile.** `python generate.py --config <json> --out <folder>` writes `controller.yaml` and `rig.json` there; compile that `controller.yaml` into a built folder with `CompileController`. You share this entry's `object-sync` build, so `rigSeed` is not yours to set.
3. **Make an owned copy of the rig.** Delete the demo collar, `Mount/Leash`, which takes its strand constraints with it.
4. **Retarget `Mount`'s BoneProxy** to the bone the strand hangs from, attaching as a child at its root (the demo keeps its rotation instead), so `Start`'s pose is bone 0's local pose there. A dragged costume bone works: Modular Avatar resolves the target before Merge Armature moves it.
5. **Set the rig's nodes to `rig.json`:** `Start` and `Home` from `start` and `home`, and `Line`'s children from `line.joints`.
6. **Replace the `FullController`**, removing it and adding one (`../../docs/nondestructive.md` §A VRCFury component on a prefab variant): your controller then this entry's `object-sync/built` controller, your menu, your parameters then `object-sync`'s, and `globalParams` `Leash/*` and `ObjectSync/*`.
7. **On each strand bone**, add a parent constraint with sources itself and its `Line/J<k>`, weights 1 and 0, zero offsets, and the joint source's rotation offset from `rig.json`'s `strand`. Turn the strand's own physbone's grabbing off, as an override on your avatar, never on the vendor prefab.
8. **Place `Home` where the strand settles.** In play, read the strand's bones once still, take the point `homeAt` along them in `Start`'s frame, write it as `home`, regenerate and set `Home` again. A strand under gravity droops off its authored rest.
9. **Check it** on a flattened copy of the avatar (instantiated, so every prefab instance is unpacked, and saved as a prefab): `python generate.py --config <json> --check-prefab <flattened prefab>`. It finds the leash by its `FullController` publishing `<prefix>/*`, and the strand's bones by their `/`-rooted paths.

**Worked example: a necklace.** PINKPUDDING's Peridot costume hangs a three-bone necklace from a static `Necklace` bone under the Neck, its physbone on the first bone and the costume's chest capsule as its collider. `Mount` targets `Necklace` by a BoneProxy sub-path from the avatar root. The middle point splits the line by the first two bones' lengths. `Home` sits at the settled midpoint with the radius widened to cover both ends, and the strand's very end is still contested by the body's breast chain and the costume's chest ribbon.

## Changing it

- **Regenerate as a unit.** Run `python generate.py`, then recompile `built/` and `object-sync/built/` over their committed `.meta`s (`../CONVENTIONS.md` §The gate). A change to `object-sync`'s CONFIG reaches this entry only through that regeneration.
- **Some knobs also live in the prefab.** `chain`, `endpoint`, `homeAt` or `home`, `mountRot` and `handle` move nodes and components `rig.json` describes; rebuild those to it.
- **The demo's model comes from a Blender file**, `assets/Blender~/Leash.blend`. Re-export over `assets/Leash.fbx` so its `.meta` and material remaps hold, and keep its bone rest poses equal to CONFIG's `chain`.
- **Run the check after every prefab edit.** `python generate.py --check` holds `LeashStake.prefab` to CONFIG and names each offender. Nothing runs it for you.

## Verifying the install

Run `--check` (or `--check-prefab`) first. In the editor the sync rig's contacts sit parked far from the avatar; that is correct, and a build moves them. Then in play:

- **No `Leash` toggle in the menu:** the `FullController` lost its menu row.
- **Grab at `Home`.** `Leash/Held` rises and the strand runs from your neck to the hand. `Leash/Held` never rising while the strand follows means the grab bone's parameter came out prefixed: `globalParams` lost `Leash/*`. A strand twitching or leaving its line means its own physbone still takes grabs. `Start` and `Home` at their authored place instead of on your neck means the BoneProxy never resolved.
- **Drag it.** The two readings decode to `Stake`'s offset from `Start`. Off by a fixed amount means the bridge's `sender_radius` differs; off by a factor, its `ratio` or `span`. `Leash/Held` rising with no pull means the bridge's `[leash]` is off or its `prefix` differs.
- **Pose-release it.** `Leash/Planted` rises and the strand runs from your neck to where you let go, holding while you walk.
- **Spawn a remote clone after the plant** (`../../docs/emulator.md` §Remote clone, its animator set to always animate) and wait for its sync rig's ready flag and `announce`: the clone's `Stake` and strand end sit on your planted spot within `object-sync`'s precision. Ready never rising means the position is not arriving, or the clone's animator stopped. The clone's strand staying free with ready up means the synced bool never rose, or `ObjectSync/Enable` is off.

## Rig

    LeashStake                   root: VRCFury FullController (§Using your own strand, step 6, has its rows)
    ├─ Mount                     MA BoneProxy → Neck, keeping its rotation (yours: the strand's parent, at its root)
    │  ├─ Leash                  the demo's model (assets/Leash.fbx, unpacked)
    │  │  ├─ Armature/Collar     the collar band's bone; its frame is Mount's
    │  │  │  └─ V0 … V6          the demo strand: its own physbone on V0, grabbing off; each bone a parent
    │  │  │                      constraint [itself, Line/J<k>]
    │  │  └─ Leash               the skinned collar and rope; built-in Standard materials in assets/
    │  └─ Start                  the strand's root, at bone 0's rest pose
    │     └─ Home                where the grab bone rests: static
    ├─ Holder                    parent ← [Home, Stake], weights and FreezeToWorld animated
    │  └─ HB0 → HTip             the grab bone: VRCPhysBone `Leash/Handle` on HB0, collision off
    ├─ Far                       position ← HTip
    ├─ Stake                     position ← [Far, ObjectSync/Rig/Prop/Display], weights and FreezeToWorld animated
    ├─ Line                      position ← Stake, aim at Start along −Z, so +Z runs along the leash
    │  ├─ J0                     position ← Start
    │  ├─ J1 … J(n−2)            position ← [Start, the last point] by rest bone lengths
    │  └─ J(n−1)                 static, one last-bone length back from Stake
    ├─ Sense                     position ← Start; two local-only face boxes, Leash/Right and Leash/Forward
    ├─ SenseProxy                position ← [Sense, Stake] at the ratio's two weights; the sender
    └─ ObjectSync                nested object-sync/y/ObjectSync.prefab: its FullController and both Toggles
                                 removed; the rotation stage's marker, receivers and reconstruction removed
                                 (Rot/Holder stays); Rig/Prop re-parked and every contact retagged to rigSeed;
                                 Sync_Target parent ← Stake; Rig/Prop/Display is the shared position a remote reads
