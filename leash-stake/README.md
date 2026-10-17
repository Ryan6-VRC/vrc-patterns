# leash-stake (Module)

A leash you can stake. Anyone can grab it and drag it. Released with a pose, it stays planted where the hand let go, and every client, late joiners included, sees it there. Held or planted, it hangs as a rope with a little sag that swings as you move. With the optional `vrc-bridge` desktop app running (it reads your avatar's parameters over OSC and drives your movement), a held or planted leash pulls you toward its end. The leash is a short strand your avatar already has, such as a collar chain or a necklace; three or four bones suit it best (§Traps).

Two ways in: drop the shipped demo, a collar whose four-bone rope hangs from the neck (§Install guide, four steps), or turn a strand you already have into the leash (§Using your own strand, which runs `generate.py`).

## How it works

- The strand is never grabbed itself. It keeps its own physbone, with grabbing turned off. A hand grabs an invisible one-bone grab bone instead, whose resting point `Home` is part way along the strand.
- Each strand bone has one parent constraint with two sources: its own physics, and a joint on a curve from `Start` (the strand's root) to `Stake` (the leash's far end). Free, the bone follows its own physics, which changes nothing. Held or planted, it follows the curve. The animator fades between the two.
- The curve is a quadratic Bezier: a smooth curve bent toward one control point. That point is the tip of a pendulum, a one-bone physbone hanging down from the `Start`/`Stake` midpoint, so the curve's middle hangs about half the pendulum's length below the straight line, a little deeper at short distances because the curve ends one last-bone length short of `Stake`. The pendulum trails when you walk or the hand moves, and swings back past rest when you stop.
- The pendulum runs on every client, so everyone sees the same sag and their own copy of the swing.
- `Stake` follows the grab bone's tip, so a held strand runs from your neck to the hand.
- A pose release (VRChat's: letting go of a grab while posing it) plants the leash. `Stake` freezes in the world. The grab bone moves onto `Stake` and switches off for a moment, which clears its pose so it can be grabbed there.
- Grabbing the planted end picks it up: the strand runs to the hand again. A plain release sends the strand back onto its own physics, and a pose release plants it again.
- Three contact boxes at `Start` read where `Stake` is, for the bridge: right, forward and up. They take your position and your avatar's yaw only, so tilting your chest never tilts the reading. The animator also publishes whether the leash is held or planted.
- The planted position is shared through a nested position-only `object-sync` (`../object-sync/README.md`). You measure `Stake`; a synced bool tells other clients when the position they have is the planted one, and they end their strand there.
- A grab is networked by VRChat itself, so every client runs the same fades. The sensing boxes run on your client only.

## Install guide

For the demo collar:

1. Drop `LeashStake.prefab` at the avatar root, unrotated. Edit the instance or an owned copy, never the package asset. The prefab's `Mount` node snaps itself to your Neck bone, and the demo adds a visible collar and a four-bone rope there.
2. Add `anti-cull` to the avatar (`../anti-cull/README.md`). Without it, another player who looks away stops running your animator and loses the planted position.
3. Build. The expression menu gains a `Leash` submenu.
4. For the pull, run `vrc-bridge` with `[leash]` enabled in its config. Both sides ship matching defaults; a changed sensing knob must change on both (§Knobs).

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- Reach for the strand and grab it; it follows your hand anywhere within reach. A plain release lets it fall back onto its own physics.
- Release it with a pose and it stays planted where your hand was, hanging as a rope from your neck, while you walk around it.
- Grab the planted end to pick it up; a plain release lets it fall back onto its own physics, a pose release plants it again.
- With the bridge running, a held or planted leash pulls you toward its end.
- The `Leash` submenu holds five controls. `Enable` drives `Leash/Enable`; off is the reset: it drops a planted leash, frees the strand, and switches the grab bone and the sensing off. `Self-grab` off stops your own hands grabbing or posing the leash, while everyone else still can. `Slack (held)` and `Slack (planted)` set how far you can move before the bridge pulls, held and planted, across the bridge's `slack_min`..`slack_max` (0.5 m to 4 m by default). `Unplant` drops a planted leash back onto its strand from wherever you stand.

## Additional notes

- **One instance per avatar.** The published names are unprefixed, and `ObjectSync/Enable` is one parameter shared by every `object-sync` build on the avatar.
- **Another `object-sync` build can share the avatar.** This one parks and tags its contacts from its own `rigSeed`, so they do not collide with another build's.
- **A late joiner sees the leash free for a moment**, until its copy of the sync rig has a whole position and the synced bool, then plants it there. A leash held at the moment someone joins reads as free to them, since a live grab does not reach a late joiner (`../../docs/runtime.md` §PhysBones).
- **Only you sense the leash.** The boxes and their sender are local-only on a private tag, so no other avatar can feed your bridge.
- **`Self-grab` writes the grab bone's filters.** The bone's `allowGrabbing` and `allowPosing` are `Other`, so a grab reads its filters, and the `SelfGrab` layer animates both filters' `allowSelf`. Only your own client tests the self case, so `Leash/SelfGrab` is unsynced. With it off, a grab of yours lands on the next nearest grabbable chain, if one is in reach.
- **The bridge reads seven parameters**, published without VRCFury's prefix and none of them synced. `Leash/Right`, `Leash/Forward` and `Leash/Up` are momentary readings, so sample them; `rig.json`'s `sensing.decode` turns one into metres (`Up` positive upward), and a reading of exactly 0 means `Stake` is outside the boxes. `Leash/Held` and `Leash/Planted` latch until the leash changes state. `Leash/Slack` and `Leash/SlackPlanted` are radial fractions 0..1 the bridge maps onto its `slack_min`..`slack_max` metres: free travel before it pulls, held and planted. A bridge that has not heard one change reads it once over OSCQuery.
- **Do not rename anything under the prefab.** The animation clips find their targets by hierarchy path, so a rename silently breaks them.
- **The only menu is the `Leash` submenu.** `object-sync/built/ObjectSync_Fx_Menu.asset` is generated with the sync build and stays unwired.

## Performance stats

```c++
Constraints:        5 + 3 per strand bone, plus 9 for the sync rig (26 on the demo; an optimizer may drop the sync rig's unused ones)
Constraint Depth:   13       (on a test body wearing the demo, built; within the Excellent rank limit)
PhysBones:          2        (the grab bone and the pendulum, 4 transforms; no colliders, no collision checks; the demo adds its rope's own)
Contact Receivers:  9        (3 sensing boxes and 6 in the sync rig; all local-only, none count toward rank)
Contact Senders:    3        (local-only)
FX Animator Layers: 11       (not a rank stat: the leash's machine, self-grab and announce, and object-sync's 8)
Bones:              0        (the grab bone and the pendulum bind no mesh; the demo adds its collar's 5)
Skinned Meshes:     1        (the demo collar: 1092 triangles, 3 materials; a strand of your own adds no mesh)
Synced parameters:  29 bits  (not a rank stat: Leash/Enable, the announce bool, ObjectSync/Enable and 26 wire bits)
```

The demo collar adds a skinned mesh, so an avatar already at the Good rank's skinned-mesh limit drops to Medium. The grab bone and the pendulum are two counted physbone components (three on the demo), against the Excellent rank's 4. The 29 synced bits can push an avatar past VRChat's 256-bit parameter budget, where VRCFury's Parameter Compressor starts compressing menu toggles, `Leash/Enable` among them.

## Knobs

Everything is `generate.py`'s CONFIG, or a consumer's JSON over it (§Using your own strand). `validate()` refuses the values it can check against a relation below; §Changing it says what to rebuild.

| Knob | What it does |
|---|---|
| `prefix` | The published names' prefix and the grab bone's `<prefix>/Handle`. The bridge's `prefix` must match |
| `internal` | The announce bool's prefix. Required, and never under `prefix`, so the published wildcard cannot reach it |
| `ratio`, `boxSize`, `senderRadius` | The sensing geometry: the bridge's `ratio`, `span` and `sender_radius`, so a mismatch mis-decodes every reading. Raising `ratio` reaches further and resolves coarser |
| `slackRange`, `slack`, `slackPlanted` | The bridge's `slack_min` and `slack_max`, and the held and planted free travel in metres inside them, emitted as `Leash/Slack`'s and `Leash/SlackPlanted`'s defaults as fractions of that range. `slackRange` must match the bridge |
| `chain`, `endpoint` | The strand's bones, root first, and the last bone's visible end. They set `Start`'s pose, the curve's joints and one strand constraint per bone. `endpoint` must equal the strand physbone's `endpointPosition` |
| `homeAt`, `home` | Where the grab bone rests: `homeAt` of the way along the strand from its root (1 is the tip), or `home`, a pose measured where your strand settles. The grab volume is a sphere around this point |
| `handle` | `radius` is that sphere's size; it must cover the strand's swing. `length` × (1 + `maxStretch`) is the reach. `pull` and `spring` are the release's feel: how fast the strand retracts after a plain release |
| `rope` | `sag` is the nominal depth of the curve's middle below the straight line (the pendulum is twice that long); a short distance or a long last bone deepens it a little (0.19 m at 0.3 m on the demo, 0.16 m at 2 m). `pull` is the pendulum's only restoring force and `spring` its overshoot; near 1 it barely settles |
| `mount`, `mountRot` | The bone the demo's `Mount` snaps to, and `Mount`'s rest rotation against the avatar root, which sets the strand's twist on the curve |
| `fade` | Frames of the strand's fade each way. Shorter moves the strand further per frame |
| `cycle` | Seconds a plant holds the grab bone off; a grab then misses. `validate()` refuses under three frames |
| `announce` | Seconds from a plant to the synced bool. It must outlast an `object-sync` measure cycle and a wire refresh (`../object-sync/README.md` §How it works), or a remote plants at the position from before the plant |
| `rigSeed` | The sync rig's contact tags and park, which move together. Unique among the avatar's `object-sync` builds |
| `tag`, `controller`, `enableDefault`, `selfGrabDefault` | The sensing contacts' private tag, the emitted controller's name, `Leash/Enable`'s and `Leash/SelfGrab`'s defaults |

**Provenance:** the idea's ancestor is OSCLeash (MIT, ZenithVal), which the bridge half re-derives; nothing here is ported from it. The planted position rides `object-sync`, merged through one component the way `compositions/grab-sync` merges it. The worked example's strand is the necklace on PINKPUDDING's Peridot costume. The grab bone on the strand, the self-sourced fade, the plant and the pendulum rope are this entry's own.

## Design notes

`generate.py`'s module docstring is the node-by-node and state-by-state walk; `rig.json` holds every number the prefab is built to. What follows is why.

**The strand stays its own physbone.** A physbone's settings bake when the chain starts, so one chain cannot be a loose necklace and a stretched leash. Leaving the strand alone keeps its free behaviour as the vendor shipped it; the grab bone carries the stretch, the grab and the pose.

**Self at full weight is a no-op.** A constraint on a bone inside a live chain reads the solved pose and the solver keeps solving underneath, so a free strand is the vendor's physics (to float precision, in av3emu) and a release fades onto the chain's current pose with nothing toggled.

**`Home` hangs from `Start`, never from a strand bone.** Under a strand bone the line would write that bone onto the grab bone's tip, its own child, and the grab bone would chase itself a bone length a frame.

**The curve ends on `Stake`, not on the grab bone's tip.** In the plant frame the tip has already reset while `Holder` has not moved, so a curve read off the tip flashes to the collar for a frame.

**The last bone's visible end lands on `Stake`**, so the hand holds the strand's end and its root stays in its socket.

**One pendulum, not a chain of springy joints.** A quadratic Bezier needs one control point, and one physbone is the cheapest moving thing that trails and overshoots. Gravity does nothing to a bone already resting straight down.

**The sag is fixed.** A physbone's length cannot change at runtime, so the pendulum sets one nominal sag at every distance; a leash has no real length for the sag to fade against, and fading it would cost a contact pair every client simulates.

**`Line` and `Mid` hang under `Stake`.** A constraint on a parent's target solves before its children's (`../../docs/runtime.md` §Constraints), so everything that reads `Stake` reads this frame's `Stake`.

**`Holder` is frozen through a pick-up**, because it follows `Stake`, which rides the grab bone's own tip.

**A remote has one planted state**, reached from free (a late joiner) or from planted (a client that saw the plant). A remote's pick-up is the wearer's own pick-up state, since the wearer unfreezes `Stake` the moment a pick-up starts. A remote that saw the plant goes free if the synced bool is still down `announce` + 1 s in, which is a wearer who pressed `Unplant` before announcing; a bool that arrives later still reaches the planted state from free. The planted clip is one frame long, so that rung's exit time counts frames.

**`ObjectSync/Enable` defaults on here** although `object-sync`'s own build declares it off: the leash's controller and parameters sit first in the one `FullController`, so its declaration wins that merge, and `--check` pins the order. A second `object-sync` build on another component can win instead (`../object-sync/README.md` §Ground truth, its Seam bullet).

## Traps

- **A release fade compounds down the strand, and a longer strand compounds more.** Each bone's self source rides its parent's already-blended pose, so the strand's end lags on the curve and catches up toward the fade's end. It is worst after a pick-up, whose curve still ends at the old planted spot: in av3emu the four-bone demo's last fade frame jumped about half a metre, a seven-bone rope's twice that. A longer `fade` spreads the jump.
- **A grab near the strand can land on a neighbour.** VRChat takes the nearest grabbable bone, so another chain whose sphere is nearer than the grab bone's (a body or costume chain under a necklace) takes the grab. Place `Home` and size `radius` against the neighbours, not just the strand.
- **A held strand is rigid pieces spaced along a curve.** Each bone keeps its mesh at rest length, so a stretched chain's links spread apart; a skinned rope stretches between its bones instead. Fewer bones draw a coarser curve and compound less on release.
- **The joints aim against world up.** Where the curve runs straight up or down, a joint's twist is undefined and a chain's links may spin; a round rope hides it.
- **A hand within a last-bone length of `Start` bunches the strand**: the last joint sits that length from `Stake` toward the control point, so the bones cross.
- **Readings are in the avatar's own scale.** The contact shapes scale with the wearer, so at twice the height a decoded metre is two in the world (this rig is unmeasured at scale).
- **Avatar Optimizer renames the rig.** Trace and Optimize merges a component-less node away and hoists its children as `<parent>$<child>$<n>`: on the demo, `Mount` goes and `Start` reads `Mount$Start$0` under the Neck. Search a built avatar by suffix.
- **A strand twisting only while held** has the wrong `mountRot`.

## What is not proven here

Needs the client: another player's grab, and the grab filter written by `Self-grab`; a remote that saw the plant moving onto the shared position (an emulator clone never sees a grab); the network timing of the synced bool against the position; the release's feel and the swing's; the sag and swing a remote draws; the pull itself, which is the bridge's. Unverified anywhere: the joints' twist where the curve runs vertical, and the strand bunched within a last-bone length of `Start`. Also unverified: a stretched skinned strand near the client's 10 m bounds cap, and avatar scale.

## Using your own strand

The seams are three: the bone the strand hangs from (`Mount`), the strand's bones, and the strand's own physbone.

1. **Write the strand's keys** in a JSON file in your venue: `chain` (each bone's binding path from the avatar root, starting with `/`, and its local pose as the prefab carries it, bone 0's pose being in the frame of the bone it hangs from), `endpoint` (its physbone's `endpointPosition`), `controller`, and any knob to change, `handle.radius` especially.
2. **Generate and compile.** `python generate.py --config <json> --out <folder>` writes `controller.yaml` and `rig.json` there; compile that `controller.yaml` into a built folder with `CompileController`. You share this entry's `object-sync` build, so `rigSeed` is not yours to set.
3. **Make an owned copy of the rig.** Delete the demo collar, `Mount/Leash`, which takes its strand constraints with it.
4. **Retarget `Mount`'s BoneProxy** to the bone the strand hangs from, attaching as a child at its root (the demo keeps its rotation instead), so `Start`'s pose is bone 0's local pose there. A dragged costume bone works: Modular Avatar resolves the target before Merge Armature moves it.
5. **Set the rig's nodes to `rig.json`:** `Start` and `Home` from `start` and `home`, `Stake/Line` (at `Stake`'s origin, its aim from `line`) and its children from `line.joints`, `Stake/Mid` and its pendulum from `rope`, the grab bone's physbone and `HTip` from `handle`, and the sensing contacts and `SenseProxy`'s weights from `sensing`.
6. **Replace the `FullController`**, removing it and adding one (`../../docs/nondestructive.md` §A VRCFury component on a prefab variant): your controller then this entry's `object-sync/built` controller, your menu, your parameters then `object-sync`'s, and `rig.json`'s `globalParams`.
7. **On each strand bone**, add a parent constraint with sources itself and its `Stake/Line/J<k>`, weights 1 and 0, zero offsets, and the joint source's rotation offset from `rig.json`'s `strand`. Turn the strand's own physbone's grabbing off, as an override on your avatar, never on the vendor prefab.
8. **Place `Home` where the strand settles.** In play, read the strand's bones once still, take the point `homeAt` along them in `Start`'s frame, write it as `home`, regenerate and set `Home` again. A strand under gravity droops off its authored rest.
9. **Check it** on a flattened copy of the avatar (instantiated, so every prefab instance is unpacked, and saved as a prefab): `python generate.py --config <json> --check-prefab <flattened prefab>`. It finds the leash by its `FullController` publishing `<prefix>/*`, and the strand's bones by their `/`-rooted paths.

**Worked example: a necklace.** PINKPUDDING's Peridot costume hangs a three-bone necklace from a static `Necklace` bone under the Neck, its physbone on the first bone and the costume's chest capsule as its collider. `Mount` targets `Necklace` by a BoneProxy sub-path from the avatar root. It takes the `rope` defaults. `Home` sits at the settled midpoint with the radius widened to cover both ends, and the strand's very end is still contested by the body's breast chain and the costume's chest ribbon.

## Changing it

- **Regenerate as a unit.** Run `python generate.py`, then recompile `built/` and `object-sync/built/` over their committed `.meta`s (`../CONVENTIONS.md` §The gate). A change to `object-sync`'s CONFIG reaches this entry only through that regeneration.
- **Some knobs also live in the prefab.** `chain`, `endpoint`, `homeAt` or `home`, `mountRot`, `handle`, `rope`, the sensing knobs and `prefix` move nodes and components `rig.json` describes; rebuild those to it. Edit an existing owned copy in place: the strand constraints reference the joints by object, and a scene instance's leftover transform overrides on `Stake`'s children land relative to their new parent.
- **The demo's model comes from a Blender file**, `assets/Blender~/Leash.blend`. Re-export over `assets/Leash.fbx` so its `.meta` and material remaps hold, and keep its bone rest poses equal to CONFIG's `chain`.
- **Run the check after every prefab edit.** `python generate.py --check` holds `LeashStake.prefab` to CONFIG and names each offender. Nothing runs it for you.

## Verifying the install

Run `--check` (or `--check-prefab`) first. In the editor the sync rig's contacts sit parked far from the avatar; that is correct, and a build moves them. Then in play:

- **No `Leash` submenu in the menu:** the `FullController` lost its menu row.
- **Grab at `Home`.** `Leash/Held` rises and the strand runs from your neck to the hand. `Leash/Held` never rising while the strand follows means the grab bone's parameter came out prefixed: `globalParams` lost `Leash/*`. A strand twitching or leaving its curve means its own physbone still takes grabs. `Start` and `Home` at their authored place instead of on your neck means the BoneProxy never resolved.
- **Drag it.** The three readings decode to `Stake`'s offset from `Start`. Off by a fixed amount means the bridge's `sender_radius` differs; off by a factor, its `ratio` or `span`. `Leash/Held` rising with no pull means the bridge's `[leash]` is off or its `prefix` differs.
- **Pose-release it.** `Leash/Planted` rises and the strand runs from your neck to where you let go, holding while you walk.
- **Watch the rope.** It sags by `sag` and swings when you walk and stop. A straight strand means the joints' middle source is not the pendulum's tip, or the pendulum lost its physbone. The strand's end trailing `Stake` while you walk means `Line` is not under `Stake`.
- **Press `Unplant` while planted.** `Leash/Planted` falls and the strand fades back onto its own physics.
- **Spawn a remote clone after the plant** (`../../docs/emulator.md` §Remote clone, its animator set to always animate) and wait for its sync rig's ready flag and `announce`: the clone's `Stake` and strand end sit on your planted spot within `object-sync`'s precision, and its rope sags as yours does. Ready never rising means the position is not arriving, or the clone's animator stopped. The clone's strand staying free with ready up means the synced bool never rose, or `ObjectSync/Enable` is off.

## Rig

    LeashStake                   root: VRCFury FullController (§Using your own strand, step 6, has its rows)
    ├─ Mount                     MA BoneProxy → Neck, keeping its rotation (yours: the strand's parent, at its root)
    │  ├─ Leash                  the demo's model (assets/Leash.fbx, unpacked)
    │  │  ├─ Armature/Collar     the collar band's bone; its frame is Mount's
    │  │  │  └─ V0 … V3          the demo strand: its own physbone on V0, grabbing off; each bone a parent
    │  │  │                      constraint [itself, Stake/Line/J<k>]
    │  │  └─ Leash               the skinned collar and rope; built-in Standard materials in assets/
    │  └─ Start                  the strand's root, at bone 0's rest pose
    │     └─ Home                where the grab bone rests: static
    ├─ Holder                    parent ← [Home, Stake], weights and FreezeToWorld animated
    │  └─ HB0 → HTip             the grab bone: VRCPhysBone `Leash/Handle` on HB0, collision off
    ├─ Far                       position ← HTip
    ├─ Stake                     position ← [Far, ObjectSync/Rig/Prop/Display], weights and FreezeToWorld animated
    │  ├─ Mid                    position ← [Start, Stake] at a half each
    │  │  └─ P0 → PTip           the pendulum: a one-bone physbone pointing down, twice `sag` long; grabbing,
    │  │                         posing, collision off. PTip is the curve's control point
    │  └─ Line                   at Stake's origin, aim at PTip along −Z
    │     ├─ J0                  position ← Start; aim at J1
    │     ├─ J1 … J(n−2)         position ← [Start, PTip, J(n−1)] by the Bezier's terms at the joint's share of
    │     │                      the rest length; aim at the next joint
    │     └─ J(n−1)              static, one last-bone length back from Stake toward PTip
    ├─ Sense                     position ← Start; three local-only face boxes, Leash/Right, Leash/Forward, Leash/Up
    ├─ SenseProxy                position ← [Sense, Stake] at the ratio's two weights; the sender
    └─ ObjectSync                nested object-sync/y/ObjectSync.prefab: its FullController and both Toggles
                                 removed; the rotation stage's marker, receivers and reconstruction removed
                                 (Rot/Holder stays); Rig/Prop re-parked and every contact retagged to rigSeed;
                                 Sync_Target parent ← Stake; Rig/Prop/Display is the shared position a remote reads
