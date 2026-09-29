# grab-sync-persist — a placed prop that survives an avatar swap (Composition)

A grabbable prop you can set down anywhere, which stays where you left it when you change into another avatar wearing the same prefab, for you and for everyone watching. It is `grab-sync` (the library's grab, carry and drop composition) with one addition: a small program on your PC, a *bridge*, carries the prop's state across the swap over OSC. Without a bridge the prefab behaves like `grab-sync`'s `GrabSync.prefab`, apart from a moment hidden at load and one extra menu button.

## How it works

- Grabbing, carrying, dropping and what late joiners see are all `grab-sync`'s, unchanged (`../grab-sync/README.md`).
- The avatar keeps measuring where the prop rests and stores it as *words*: the quantized world position and heading that `object-sync`, the library's module for syncing a dropped prop, already sends to other players. Beside them sit whether the prop is away from its home spot (`Detached`) and whether the gimmick is switched on (`Enabled`).
- All of them live under one name prefix, `BridgePersist/GrabSyncPersist/`, and keep those exact names on the built avatar, so a program outside VRChat can read and write them over OSC.
- The bridge (`vrc-bridge`, its persistence mapping) remembers the last values it saw. When you change avatar, the new avatar pauses its own position measurement, tells the bridge which prefab it is (its `Id`), and asks whether there is anything to restore.
- If there is, a short exchange on the `Restore` parameter resets those parameters, lets the bridge write the saved values back, and hands the prop back to the avatar. The prop appears at the saved spot and measurement resumes from there.
- If nothing answers within a moment, the avatar carries on as `GrabSync`.
- It uses no more synced parameters than `GrabSync`.

## Install guide

1. Keep `compositions/grab-sync/` in the package: this prefab is a variant of `GrabSync.prefab` and inherits its whole rig. Read `grab-sync`'s Install section; every rule there holds here (the Hips home anchor, where your mesh goes, the two root constraints that stay disabled).
2. Drop `GrabSyncPersist.prefab` under your avatar root, instead of `GrabSync.prefab`. Never beside `GrabSync` or its four-prop `MultiGrabSync`: all three use the same contact tags and put their measuring rigs in the same spot, and each puts its own toggle on `ObjectSync/Enable`.
3. Put the same prefab on every avatar you want the prop to follow you between. Persistence is on out of the box.
4. Run `vrc-bridge`, this workspace's OSC companion program (its own README covers installing and starting it), beside VRChat with VRChat's OSC switched on. Persistence is part of its standard setup.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- The menu gains **GrabSync**, the on/off toggle for the whole gimmick (as in `grab-sync`), and **GrabSync Place**.
- **GrabSync Place** sets the prop down where it stands, as if you had grabbed and released it there. It works while the prop is at home. Over OSC, send a bool `true` to `/avatar/parameters/GrabSyncPersist/Place`; the avatar clears it, and a write made while the prop is away is dropped.
- Set the prop down, then change avatar. On the new avatar the prop stays hidden for a moment, then appears where you left it. Measurement stays off for up to a couple of seconds more while the restored position reaches other players; a grab in that window takes effect when it ends.
- The on/off state travels too: an avatar left switched off comes up switched off. Switching off always sends the prop home, so there is never a placed prop to restore from a switched-off avatar.
- With no bridge running, the prop is hidden for about a second after the avatar loads, then everything works as in `GrabSync`.

## Additional notes

- **Both avatars need the same prefab.** The bridge restores only onto an avatar announcing the same `Id` under the same prefix. A different prop built on this prefab needs its own `Id` (§Changing it), or the two restore onto each other.
- **Each swap moves the prop by one quantization step.** A restore lands the prop exactly on the saved words, which already sit within one fine step of where it rested, and the resumed measurement rounds down once more. So every swap shifts it by one fine step per axis; it does not drift while it rests.
- **What restores.** A swap between avatars wearing the prefab restores. A world join, a rejoin, Reset Avatar, or a swap through an avatar without the prefab restores nothing; those are the bridge's rules.
- **One persistent prefab per avatar**, and no persistent `MultiGrabSync` (§Design notes).

## Performance stats

```c++
Synced parameters:     29 bits (27 carry the words, plus Detached and Enable)
Unsynced parameters:   6 (Id, Announce, Boot, Restore, Enabled, Place) beside the words and grab-sync's own
FX Animator Layers:    10 (one for this prefab's own logic, nine for object-sync)
PhysBones:             2 (the grab bone, the drag bone)
Constraints:           25
Contacts:              8 receivers, 3 senders, all local-only (0 non-local)
Mesh Renderers:        1 (the placeholder sphere, one material slot)
Menu controls:         2
```

## Changing it

Everything the entry generates is `generate.py`'s: edit it, run it, and recompile `controller.yaml` and `object-sync/controller.yaml` into their `built/` folders (`../../CONVENTIONS.md` §The gate has the recompile procedure). Then run `python generate.py --check`.

**Giving a variant its own `Id`**, without regenerating: make a prefab variant of `GrabSyncPersist.prefab`, remove its root FullController, and add your own with the same controllers, prms, menu and `globalParams`, but with a controller of yours listed first in both the controllers and prms lists. That controller declares `BridgePersist/GrabSyncPersist/Id` as an unsynced, unsaved int with your value (1 to 255, so every tool carries it as a byte); first-wins takes the whole declaration. This entry's `--check` pins its own list order, so it does not apply to your variant; check the bake instead (§Verifying the install). `0` switches persistence off.

| Knob | What it does |
|---|---|
| `NAMESPACE` | The prefix every persistent name lives under, and the root the word table is published at (`object-sync`'s `wordRoot`). It must stay under `BridgePersist/`, which is what the bridge watches, and nothing else on the avatar may declare under it. The shipped `Id` is minted from it, so changing it changes the `Id`; the prefab's `globalParams` must be edited to match (`--check` fails until it is). `Place` sits outside it. |
| `ANNOUNCE_LEAD`, `BOOT_WAIT`, `WRITE_WAIT` | The wire contract's avatar-side waits: the least time from writing `Announce` to writing `Boot`, how long the avatar waits for the bridge to answer `Boot`, and how long it waits for the saved values. The bridge carries the same numbers; change none of them on one side alone. |
| `PLACE_SETTLE` | The least time the prop rides the restored words before it is frozen there. The hold actually used is the longer of this and one full refresh of the word wire at the sync build's floor frame rate (`place_len()`), and the generator refuses a hold that leaves the bridge under half a second of its wait for the final step. |

**Provenance:** the composition is `grab-sync` (whose provenance line covers the arbitration), `grab-prop`, `drag-bone` and `object-sync`, each carrying its own ancestry. The restore exchange is this workspace's own design, built against `vrc-bridge`'s persistence mapping.

## Design notes

`generate.py`'s docstring lists the delta from `grab-sync` item by item, with the reason for each; the emitted `controller.yaml` is the state-by-state walk. What follows is what shapes the entry as a whole.

- **A transform, not a copy.** The entry exists to show what persistence adds to a working gimmick, and to keep adding it when that gimmick changes. `generate.py` rewrites `../grab-sync/controller.yaml` and refuses, naming the anchor, when an upstream edit moves one; a copy would drift silently instead.
- **Quiesce first, and hold until the wire has caught up.** The branch switches measurement off on the wearer's first evaluation, before `Boot`, and keeps it off until the restored words have crossed the wire once at the floor frame rate. The wire's refresh is counted in the wearer's frames, and remotes re-engage the moment measurement returns, so a hold measured in seconds alone lets a remote at a low wearer frame rate glide in from a half-updated table.
- **A remote returns through the late-join path.** In `grab-sync`, switching back on always finds `Detached` false. After a restore it finds it true, so a remote goes to `Waiting` rather than `Anchored` and shows the prop only once it can show it at the word.
- **Nothing on the wire can hold the branch.** Inbound OSC can arrive late, doubled or reordered, so every state in the branch has a timed or unconditional exit; a bad sequence delays the boot by at most the contract's waits and never leaves the prop hidden.
- **`MultiGrabSync` would need more than a loop.** The exchange runs once per prefix while placement is per prop: one coordinating layer owning the reserved names, a place state per prop released together, a four-object sync build at `wordRoot`, `Detached_0..3`, and the fourth mux slot on each prop's mux.

## Traps

- **Changing Enable's default is a regeneration.** The restore's reset and `Enabled`'s default are both read from `grab-sync`'s Enable declaration when the glue is generated. A variant that declares a different Enable default in a first-listed controller boots switched on whenever no bridge answers.
- **The glue must stay first in both FullController lists.** The sync build declares Enable default off; the glue's first-wins declaration is what arms it. `--check` pins the order.
- **The fourth mux slot must sit inside the constraint's source list length.** A slot past it is solved in the editor and ignored by the client (`../../../docs/runtime.md` §Constraints (VRC)). `--check` pins the slot, its node and the length.
- **Toggling the gimmick from the menu during a restore is unguarded.** The window is the first few seconds after load.
- **A bridge answer that arrives after the avatar gave up** is written into a running prefab: the resumed walks overwrite the words, but `Detached` keeps what the bridge wrote until the next grab or on/off cycle.

## Verifying the install

- **Bake:** every name under `BridgePersist/GrabSyncPersist/`, and `GrabSyncPersist/Place`, keeps its exact name; `Detached` is the only synced one of them; `Id` carries your value. A `VF##_` prefix on any of them means the `BridgePersist/GrabSyncPersist/*` entry is missing from the FullController's `globalParams`: the build succeeds and the bridge reads nothing.
- **Nothing restores:** check that both avatars carry the same prefab and `Id` and that `Id` is not 0; that VRChat's OSC is on and the bridge was running before the outgoing avatar loaded (a bridge started later misses the first swap); and that the swap went straight from one avatar to the other. The bridge logs why it skipped a restore.
- **Emulator:** spawn the avatar somewhere other than where the prop was placed, or a restore that did nothing looks like one that worked. Once the wearer's animator is running, the prop never shows at the new home: it stays hidden until it appears at the saved spot. A remote clone spawned before the restore does the same. Test at a low frame rate as well as a high one, since the hold is counted in frames on the wire.
- The emulator announces the same avatar on every play entry, so to a bridge play, stop, play is a reload of the worn avatar, not a swap; the bridge needs its test-only reload-as-swap switch. Doubled OSC delivery and `/avatar/change` order across a real swap are the shipping client's to show.

## Rig

A prefab variant of `../grab-sync/GrabSync.prefab`; `../grab-sync/README.md` §The arrangement is the tree. The variant's deltas:

    GrabSyncPersist        root: GrabSync's FullController and menu Toggle REMOVED; its own FullController
                           ADDED, playing built/GrabSyncPersist_Fx then object-sync/built/ObjectSync_Fx (same
                           order in prms), menu built/GrabSyncPersist_Fx_Menu, globalParams the sync build's
                           derived list (ObjectSync/*, BridgePersist/GrabSyncPersist/*) plus GrabSyncPersist/Place
    └─ Prop/
       └─ Source           both mux constraints gain source3 = ObjectSync/Rig/Prop/Display at weight 0,
                           zero offset, list length 4: the restore's placing slot, weighted only in Persist Place

The removals and the added component are the variant's whole VRCFury customisation, by remove-and-add (`../../../docs/nondestructive.md`). `--check` confirms both removals, the one added component, its list order and `globalParams`, and the fourth slot; an inspector shows the slot only as `Display`, the same name as `Prop/Container/Display`.
