# leash-sync (Composition)

The `leash` entry with its stake shared: use `LeashSync.prefab` in place of `Leash.prefab` when other players, including one who joins after you staked the leash, should see the rope end where you staked it. The bare leash stakes by a capture each client makes when it sees the plant happen, so a client that joined afterwards has no stake and shows the leash at home. This composition sends the wearer's stake position through a position-only `object-sync` build and ends every other client's rope there. Synced cost: §Performance stats.

## How it works

- **Terms.** The **stake** is where a planted leash's far end is fixed; `Stake` is the node that holds it. A **remote** is any client other than the wearer's. The **reconstruction** is `object-sync`'s rebuilt copy of a position the wearer measured, at `ObjectSync/Rig/Prop/Display`.
- `LeashSync.prefab` is a prefab variant of `leash/Leash.prefab`. It inherits the leash rig whole and adds a nested `object-sync` rig, one constraint source on `Stake`, and a VRCFury `FullController` that plays both controllers.
- On the wearer, `object-sync` measures `Stake`. `Stake` follows the leash's grabbable far end until a plant freezes it, so the wire carries the far end, then the stake.
- `Stake` takes the reconstruction as a second position source. It stays at weight 0 wherever the leash behaves as the bare entry.
- The wearer raises one synced bool, `LeashSync/Planted`, a fixed delay (`ANNOUNCE`) after the leash's `Leash/Planted` rises. The delay is what makes the bool mean the remote's copy of the position is already the stake.
- A remote that reads the bool true, with `ObjectSync/Enable` on and its receiver certified (`OS/Ready`), moves its `Stake` onto the reconstruction and plants its leash there. A hand reaching for the stake on that client finds the leash's end, and picking it up works as on the bare leash.
- The wearer's own leash never reads the reconstruction. Its own capture is exact, and the parameters the OSC bridge reads behave as on the bare leash.

## Install guide

1. Drop `LeashSync.prefab` at the avatar root, unrotated. Do not add `Leash.prefab` as well. Edit the instance or an owned copy, never the package asset.
2. Drag `Collar/Offset` to the front of the neck, as for the leash (`../../leash/README.md` §Install guide).
3. Add `anti-cull` to the avatar (`../../anti-cull/README.md`). A remote rebuilds the stake only while it runs your animator, and a view-culled wearer's reconstruction stops updating.
4. Build. The expression menu gains the leash's `Leash` toggle and nothing else.
5. For the leash's pull on your movement, run `vrc-bridge` exactly as for the bare leash; nothing on its side changes.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- Use the leash as its README describes; this composition adds no control of its own.
- `ObjectSync/Enable` switches the sync on and off: synced, unsaved, on by default, not on the menu, and unprefixed so an OSC client can reach it. Off, the wearer stops measuring, and a remote already planted on the reconstruction stays there until the bool falls.
- `LeashSync/Planted` is internal and takes VRCFury's instance prefix.

## Additional notes

- **One instance per avatar**, as for the leash.
- **Another `object-sync` build can share the avatar.** This one uses its own contact tags and position (`RIG_SEED`), so it does not collide with `compositions/grab-sync`'s. `ObjectSync/Enable` is one parameter shared by every build on the avatar.
- **A late joiner shows the leash at home for a moment**, until its receiver has a whole position and the bool, then plants on the reconstruction.
- **A remote that saw the plant moves its stake once when the bool arrives**, from its own capture onto the reconstruction.
- **Do not enable the two constraints on `ObjectSync`.** They ship disabled and a build step enables them (`../../object-sync/README.md` §Composing against Sync owns why).
- **Do not rename anything under the prefab.** The clip paths are the hierarchy names.

## Performance stats

Against `Leash.prefab` on the same avatar:

```c++
Constraints:        +9       (50 with the leash demo)
Constraint Depth:   +3       (30 with the leash demo; inside Good)
Contact Receivers:  +6       (local-only: none count toward rank)
Contact Senders:    +2       (local-only)
FX Animator Layers: +9       (not a rank stat: the Announce layer and object-sync's 8)
Synced parameters:  +28 bits (not a rank stat: 26 wire, ObjectSync/Enable, LeashSync/Planted; 29 with the leash's own)
```

## Knobs

`ANNOUNCE`, `SETTLE` and `RIG_SEED` are `generate.py`'s; the wire is `object-sync`'s CONFIG at rotation `none` (§Changing it).

| Knob | What it does |
|---|---|
| `ANNOUNCE` | Seconds from `Leash/Planted` to the synced bool. It must outlast one `object-sync` measure cycle already under way at the freeze, the next whole cycle, and a wire refresh (`../../object-sync/README.md` §How it works has both); shorter lets a remote plant on the far end's position from before the plant. Longer delays every remote's stake and a re-plant's, since the bool stays down at least this long |
| `SETTLE` | Frames a remote holds `Stake` on the reconstruction before `StakeAim` freezes. A freeze captures its pose one solve late, so fewer frames risk capturing before `Stake` arrives; more only delay the plant |
| `RIG_SEED` | This build's contact tags and position, which move together. It must differ from every other `object-sync` build's on the avatar |

**Provenance:** composes `leash` and `object-sync`, each carrying its own ancestry. The arrangement (a variant of the entry prefab, one component playing the glue and a mounted `object-sync` build, a position-only rig) follows `compositions/grab-sync` and `compositions/sync-on-player`.

## Design notes

The state-by-state walk is `generate.py`'s module docstring; `controller.yaml` is the emitted machine.

**The glue is the leash's own controller, extended.** A remote that never saw the plant sits in the leash's `Free`, which keys the far end home. A second layer writing the same bindings would override the leash in every one of its states, so only a state in the leash's own layer can plant it. The generator therefore emits the leash's document at its shipped CONFIG and adds the remote states and `Stake`'s weights to it.

**`Stake` gains a source; nothing else is re-sourced.** Everything planted hangs off `Stake`: the rope's far end, the rope's second pendulum, and `StakeAim` and `StakeRoot` under it, where the leash's grabbable chain rests. One source moves all of it, and a constraint source is a value override on the variant rather than a change to the entry.

**A remote's `Stake` is live, not frozen.** It follows the reconstruction for as long as the remote is planted on it, so the rope end follows a later word refresh. `StakeAim` freezes after `SETTLE` frames, as the leash's does, so the resting chain holds still.

**The reconstruction is read directly, not through `Sync`.** The glue already tells the wearer from a remote, so `object-sync`'s own `Follow` switch would only add a hop.

**The bool falls at once and stays down at least `ANNOUNCE`,** so a remote sees every fall even when a re-plant follows immediately.

**`Rot/Holder` stays in a position-only rig.** The build still animates `Rot`'s active flag, and the holder's constraint keeps that node in the built avatar.

## Traps

- **A remote plants only from the leash's `Free` or `Planted`.** A remote mid-fade or holding the leash when the bool arrives stays in the leash's own machine until it reaches one of them.
- **The bool falling with no grab seen sends a remote's leash home in one frame.** That is a pick-up this client missed, from a cull or a join during the grab; the next plant or the next bool corrects it.
- **A reconstruction that moves after `StakeAim` froze moves the rope end, not the resting chain.** A hand then finds the chain's end where the stake was when the remote planted.

## What is not proven here

Needs two clients: a remote that saw the plant moving onto the reconstruction (an emulator clone never sees a grab, so every clone takes the late-join path); network timing of the bool against the words; another player's pick-up of a stake they did not see planted. Unverified anywhere: a release during a remote's pick-up fade, a cull resume while planted, and `ObjectSync/Enable` off.

## Changing it

- **Regenerate as a unit.** Run `python compositions/leash-sync/generate.py`, then recompile `built/` and `object-sync/built/` over their committed `.meta`s (`../../CONVENTIONS.md` §The gate). A change to the leash or to `object-sync` reaches this composition only through a regeneration.
- **Run the check after every prefab edit.** `python compositions/leash-sync/generate.py --check` holds `LeashSync.prefab` to the generator. Nothing runs it for you.

## Verifying the install

Run `--check` first. Then in play with a remote clone (`../../../docs/emulator.md` §Remote clone): plant the leash, walk away, spawn a clone, and wait for its receiver to certify and `ANNOUNCE` to pass. The clone's rope end, its `Stake` and its `ObjectSync/Rig/Prop/Display` then sit on the wearer's stake within `object-sync`'s precision (`../../object-sync/README.md` §How it works).

- **The clone's rope stays at home with `OS/Ready` true:** the bool never rose (read the wearer's prefixed `LeashSync/Planted`), or `ObjectSync/Enable` is off.
- **`OS/Ready` never rises:** the wire is not arriving; `anti-cull` missing in the client, or `ObjectSync/Enable` off on the wearer.
- **The clone's rope ends somewhere else, steadily:** the wearer is not measuring `Stake`. At rest, the wearer's own `ObjectSync/Rig/Prop/Display` should sit on its `Stake`; if it does not, check `Sync_Target`'s source and the contact tags with `--check`.

## Rig

    LeashSync                    the leash root (a variant of Leash.prefab): its FullController removed, one added
                                 playing built/LeashSync_Fx then object-sync/built/ObjectSync_Fx, with the Leash menu
    ├─ …                         the leash rig, unchanged except:
    ├─ Stake                     position ← [the leash's far end, ObjectSync/Rig/Prop/Display], weights animated
    └─ ObjectSync                nested object-sync/y/ObjectSync.prefab: its FullController, menu Toggle and
       │                         Sync_Target's Drop toggle removed; the rotation marker, its receivers, Recon and
       │                         Display's rotation constraint removed; Rig/Prop re-positioned and every contact
       │                         retagged to RIG_SEED
       ├─ Rig/Prop/Rot/Holder    kept, with no marker under it (Design notes)
       ├─ Rig/Prop/Display       the reconstruction, which Stake sources
       ├─ Sync_Target            parent ← Stake: what the wearer measures
       └─ Sync                   object-sync's switched output, unused here
