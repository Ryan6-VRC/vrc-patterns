# grab-sync-persist — a placed prop that survives an avatar swap (Composition)

A grabbable prop you can set down anywhere, which stays where you left it when you change into another avatar wearing the same prefab, for you and for everyone watching. It is `grab-sync` (the library's grab, carry and drop composition) plus `bridge-persist`, the library's layer that hands a gimmick's state to a small program on your PC, a *bridge*, and takes it back after the swap. Without a bridge the prefab behaves like `grab-sync`'s `GrabSync.prefab`, apart from a moment hidden at load and one extra menu button. The prefab is `GrabSyncPersist.prefab`. It is also the worked example of adding `bridge-persist` to a gimmick built on `object-sync`.

## How it works

- Grabbing, carrying, dropping and what late joiners see are all `grab-sync`'s, unchanged (`../grab-sync/README.md`).
- The avatar keeps measuring where the prop rests and stores it as *words*: the quantized world position and heading that `object-sync`, the library's module for syncing a dropped prop, already sends to other players. Beside them sits `Detached`, whether the prop is away from its home spot.
- The words and `Detached` live under `BridgePersist/GrabSyncPersist/` and keep those exact names on the built avatar, so the bridge can read and write them over OSC.
- On load, the `bridge-persist` layer switches the gimmick off, asks the bridge for the saved values, and waits a moment (`../../bridge-persist/README.md` has the exchange).
- If the bridge restores a placed prop, the layer raises its flag. The prop's own controller then moves the prop onto the restored words, keeps it there while the restored position reaches other players, and drops it there when the flag falls. Measurement resumes from that spot.
- If nothing answers, the avatar carries on as `GrabSync`.
- It uses no more synced parameters than `GrabSync`.

## Install guide

1. Keep `compositions/grab-sync/` and `bridge-persist/` in the package: this prefab is a variant of `GrabSync.prefab` and inherits its whole rig. Read `grab-sync`'s Install section; every rule there holds here (the Hips home anchor, where your mesh goes, the two root constraints that stay disabled).
2. Drop `GrabSyncPersist.prefab` under your avatar root, instead of `GrabSync.prefab`. Never beside `GrabSync` or its four-prop `MultiGrabSync`: all three use the same contact tags and put their measuring rigs in the same spot, and each puts its own toggle on `ObjectSync/Enable`.
3. Put the same prefab on every avatar you want the prop to follow you between. Persistence is on out of the box.
4. Run `vrc-bridge`, this workspace's OSC companion program (its own README covers installing and starting it), beside VRChat with VRChat's OSC switched on. Persistence is part of its standard setup.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- The menu gains **GrabSync**, the on/off toggle for the whole gimmick (as in `grab-sync`), and **GrabSync Place**.
- **GrabSync Place** sets the prop down where it stands, as if you had grabbed and released it there. It works while the prop is at home. Over OSC, send a bool `true` to `/avatar/parameters/GrabSyncPersist/Place`; the avatar clears it, and a write made while the prop is away is dropped.
- Set the prop down, then change avatar. On the new avatar the prop stays hidden for a moment, then appears where you left it. It stays there, with measurement off, for a moment more while it settles (`PLACE_SETTLE`), and other players see it when that ends; a grab in that window takes effect when it ends.
- The on/off state travels too: an avatar left switched off comes up switched off. Switching off always sends the prop home, so there is never a placed prop to restore from a switched-off avatar.
- With no bridge running, the prop is hidden through the layer's window after the avatar loads, then everything works as in `GrabSync`.

## Additional notes

- **Both avatars need the same prefab.** The bridge restores only onto an avatar announcing the same `Id` under the same prefix. A different prop built on this prefab needs its own `Id` (§Changing it), or the two restore onto each other.
- **Each swap moves the prop by one quantization step.** A restore lands the prop exactly on the saved words, which already sit within one fine step of where it rested, and the resumed measurement rounds down once more. So every swap shifts it by one fine step per axis; it does not drift while it rests.
- **What restores.** A swap between avatars wearing the prefab restores; `../../bridge-persist/README.md` §How to use lists what does not.
- **One persistent prefab per avatar**, and no persistent `MultiGrabSync` (§Design notes).

## Performance stats

```c++
Synced parameters:     29 bits (27 carry the words, plus Detached and Enable)
Unsynced parameters:   Place, and bridge-persist's (its README, Performance stats), beside the words and grab-sync's own
FX Animator Layers:    11 (the prop's own logic, bridge-persist's layer, nine for object-sync)
PhysBones:             2 (the grab bone, the drag bone)
Constraints:           25
Contacts:              8 receivers, 3 senders, all local-only (0 non-local)
Mesh Renderers:        1 (the placeholder sphere, one material slot)
Menu controls:         2
```

## Changing it

Everything the entry generates is `generate.py`'s: edit it, run it, and recompile `controller.yaml`, `persist/controller.yaml` and `object-sync/controller.yaml` into their `built/` folders (`../../CONVENTIONS.md` §The gate has the recompile procedure). Then run `python generate.py --check`.

**Giving a variant its own `Id`**, without regenerating: make a prefab variant of `GrabSyncPersist.prefab`, remove its root FullController, and add your own with the same controllers, prms, menu and `globalParams`, but with a controller of yours listed first in both the controllers and prms lists. That controller declares `BridgePersist/GrabSyncPersist/Id` as an unsynced, unsaved int with your value (1 to 255, so every tool carries it as a byte); first-wins takes the whole declaration. This entry's `--check` pins its own list order, so it does not apply to your variant; check the bake instead (§Verifying the install). `0` switches persistence off.

| Knob | What it does |
|---|---|
| `NAMESPACE` | The prefix every persistent name lives under, and the root the word table is published at (`object-sync`'s `wordRoot`). It must stay one segment under `BridgePersist/`, which is what the bridge watches, and nothing else on the avatar may declare under it. The shipped `Id` is minted from it, so changing it changes the `Id`; the prefab's `globalParams` must be edited to match (`--check` fails until it is). `Place` sits outside it. |
| `INTERNAL` | The prefix of `bridge-persist`'s local flag. It must stay outside the namespace and outside every `globalParams` entry; `--check` fails if one reaches it. |
| `PLACE_SETTLE` | How long the prop rides the restored words before it is dropped there: the hold, passed to `bridge-persist` as its `hold`. Other players see the prop when it ends. |

**Provenance:** the composition is `grab-sync` (whose provenance line covers the arbitration), `grab-prop`, `drag-bone`, `object-sync` and `bridge-persist`, each carrying its own ancestry.

## Design notes

`generate.py`'s docstring lists the delta from `grab-sync` item by item, with the reason for each; the emitted `controller.yaml` is the state-by-state walk, and `../../bridge-persist/generate.py` owns the exchange. What follows is what shapes the entry as a whole.

- **A transform, not a copy.** The entry exists to show what persistence adds to a working gimmick, and to keep adding it when that gimmick changes. `generate.py` reads `../grab-sync/controller.yaml`, transforms it into this entry's own, and refuses, naming the anchor, when an upstream edit moves one; a copy would drift silently instead.
- **The glue gains two states.** `Place`, the no-grab drop, and `Persist Place`, the one place state; everything about the bridge is `bridge-persist`'s layer.
- **The wearer sees the restored words only through the sync build's reconstruction.** The wearer's own `Sync` follows the prop rather than the words, so the mux on `Prop/Source` gains the reconstruction as a fourth slot, weighted only in `Persist Place`.
- **The hold is the prop's own settle, not the wire's refresh.** The switch-off at load put zeroed words on the wire, and remotes re-engage the moment the gimmick is switched back on. A hold lasting one full refresh of the word wire would cover that, and would keep the prop from every watching player for that long on every swap. At the settle alone, a remote watching a wearer whose frame rate is low enough that a refresh outlasts the hold can see the prop glide in from a half-updated table.
- **A remote returns through the late-join path.** In `grab-sync`, switching back on always finds `Detached` false. After a restore it finds it true, so a remote goes to `Waiting` rather than `Anchored` and shows the prop only once it can show it at the word.
- **`MultiGrabSync` would need a four-object sync build at `wordRoot` and a place state per prop.** The layer already takes several placed names; it would reset all four props' words and `Detached_0..3`, and hold whenever any of them is placed. Each prop needs its own `Persist Place` state keyed to its own `Detached`, and the fourth mux slot on its own mux.

## Traps

- **The controller order in the FullController is load-bearing.** The glue first arms Enable (first-wins); the three controllers in one component are what share `bridge-persist`'s flag with the glue. `--check` pins the order, the prms order and `globalParams`.
- **The fourth mux slot must sit inside the constraint's source list length.** A slot past it is solved in the editor and ignored by the client (`../../../docs/runtime.md` §Constraints (VRC)). `--check` pins the slot, its node and the length.
- **Changing Enable's default is a regeneration.** The reset and the mirror's default are both read from `grab-sync`'s Enable declaration when the layer is generated. A variant that declares a different Enable default in a first-listed controller boots switched on whenever no bridge answers.
- **Toggling the gimmick from the menu during a restore is unguarded.**
- **A bridge answer that arrives after the avatar gave up** is written into a running prefab. `Detached` keeps what the bridge wrote until the next grab or on/off cycle, so a watching remote takes its word path and rides the words while the resumed walks overwrite them. Through that overlap the words it reads are torn, so the remote's prop can swing far off before it settles at home.

## Verifying the install

- **Bake:** every name under `BridgePersist/GrabSyncPersist/`, and `GrabSyncPersist/Place`, keeps its exact name; `Detached` is the only synced one of them; `Id` carries your value. A `VF##_` prefix on any of them means the `BridgePersist/GrabSyncPersist/*` entry is missing from the FullController's `globalParams`: the build succeeds and the bridge reads nothing.
- **Nothing restores:** check that both avatars carry the same prefab and `Id` and that `Id` is not 0; that VRChat's OSC is on and the bridge was running before the outgoing avatar loaded (a bridge started later misses the first swap); and that the swap went straight from one avatar to the other. The bridge's log says why it skipped a restore.
- **Restores, but the prop appears at home:** `Persist Place` never ran. The glue and `persist/built/GrabSyncPersist_Persist_Fx` must sit in one FullController.
- **Emulator:** spawn the avatar somewhere other than where the prop was placed, or a restore that did nothing looks like one that worked. Once the wearer's animator is running, the prop never shows at the new home: it stays hidden until it appears at the saved spot. A remote clone spawned before the restore does the same, apart from the clone's own first frame, drawn before its animator runs. Test at a low frame rate as well as a high one: the wire's refresh is counted in the wearer's frames and the hold is not.
- The emulator announces the same avatar on every play entry, so to a bridge play, stop, play is a reload of the worn avatar, not a swap; the bridge needs its test-only reload-as-swap switch. Doubled OSC delivery and `/avatar/change` order across a real swap are the shipping client's to show.

## Rig

A prefab variant of `../grab-sync/GrabSync.prefab`; `../grab-sync/README.md` §The arrangement is the tree. The variant's deltas:

    GrabSyncPersist        root: GrabSync's FullController and menu Toggle REMOVED; its own FullController
                           ADDED, playing built/GrabSyncPersist_Fx, persist/built/GrabSyncPersist_Persist_Fx,
                           then object-sync/built/ObjectSync_Fx (same order in prms), menu
                           built/GrabSyncPersist_Fx_Menu, globalParams the sync build's derived list
                           (ObjectSync/*, BridgePersist/GrabSyncPersist/*) plus GrabSyncPersist/Place
    └─ Prop/
       └─ Source           both mux constraints gain source3 = ObjectSync/Rig/Prop/Display at weight 0,
                           zero offset, list length 4: the restore's placing slot, weighted only in Persist Place

The removals and the added component are the variant's whole VRCFury customisation, by remove-and-add (`../../../docs/nondestructive.md`). `--check` confirms both removals, the one added component, its list order and `globalParams`, the flag staying unpublished, and the fourth slot; an inspector shows the slot only as `Display`, the same name as `Prop/Container/Display`.
