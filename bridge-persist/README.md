# bridge-persist — carry a gimmick's state across an avatar swap (Pattern)

A generated animator layer, with no prefab of its own, that lets a gimmick you built keep its state when you change into another avatar wearing the same gimmick. It talks to `vrc-bridge`, the OSC companion program of the Atelier workspace this library belongs to, which remembers the gimmick's parameters and writes them back into the new avatar. You generate the layer, merge it beside your gimmick's own controller, and give your controller one extra state per thing it has to put back. Everything about the bridge stays in this layer. `compositions/grab-sync-persist` is the worked consumer: a dropped prop that stays where you left it.

## How it works

- The parameters to carry live under one name prefix, `BridgePersist/<Name>/`, the **namespace**. VRCFury normally prefixes a module's parameter names per instance; every name under the namespace is kept exact instead, so the bridge can read and write it by name over OSC. Four names under it are reserved for the exchange: `Id`, `Announce`, `Boot` and `Restore`. Every other name under it is **payload**, which the bridge saves and restores.
- `Id` is the gimmick's identity, carried as the parameter's declared default. The bridge restores only onto an avatar announcing the same `Id` under the same namespace. `Id` 0 switches the layer off.
- On load, on the wearer only, the layer switches the gimmick off through its enable parameter and resets every payload name to its declared default. It then writes `Announce` (a copy of `Id`) and `Boot` (a random number) and waits a fixed window, `WINDOW_SECS`.
- The bridge answers inside the window by writing the saved payload and then `Restore` 1. If the payload shows something placed, the layer raises a local **flag** for the **hold**, the time the consumer needs to put it back. It then sets the enable from the mirror (below) and writes `Restore` 0.
- If the window runs out, the layer sets the enable from the mirror, which the reset left at the enable's declared default, so the gimmick boots as it would with no bridge. The payload stays at its defaults.
- Whether the gimmick was switched on is payload too: the layer mirrors the enable parameter into `<namespace>/Enabled` while it idles, so the new avatar comes up on or off as the old one was.
- It adds no synced parameter.

## Install guide

1. Build your gimmick first. The layer assumes it has one enable parameter whose off state parks it, and that off resets anything placed (so a switched-off gimmick never has something placed to restore).
2. Choose a namespace `BridgePersist/<Name>` that nothing else on the avatar declares under, and move every parameter you want carried under it. A parameter you need to stay local, the flag included, goes outside it. A gimmick built on `object-sync` moves its word table there with that entry's `wordRoot` option, which also adds `BridgePersist/<Name>/*` to the sync build's derived `globalParams`; `../compositions/grab-sync-persist` is the worked case.
3. Write a config for `generate.py`, a dict of the keys in §Knobs, and pass it to `document(config)` from your own build script, the way a composition drives `object-sync`'s generator. A declaration, which `enable` and `payload` carry, is the value string of an entry under `parameters:` in the controller document, such as `"{ type: bool, default: false, vrc: { synced: true, saved: false } }"`. `hold` is in seconds. The folder's hyphen rules out an `import` statement, so load the generator by path, as `load()` in `../compositions/grab-sync-persist/generate.py` does; that file's `words()` and `persist_config()` are the recipe for building the payload list from a sync build. `document()` returns the document's text and a dict of facts: `flag` is the flag's name, which step 6 uses, and `id`, `controller`, `payload` and `hold` report what was built. Compile the text with `CompileController` into your own `built/`.
4. Add the compiled controller and its parameters asset to your gimmick's own VRCFury `FullController`, in both the `controllers` and `prms` lists. It must be the same component: that is what makes your controller and this layer share the flag. Keep your own controller first, so your declarations stay the ones the build keeps where the two overlap. With an `object-sync` build, the order is your controller, this layer, then the sync build, and the `prms` list keeps the same order.
5. Add `BridgePersist/<Name>/*` to that FullController's `globalParams`.
6. In your controller, declare the flag by the name in the facts' `flag`, never typed by hand, as the layer declares it: `{ type: bool, default: false, scratch: true }`. Add one place state per thing to put back. Enter it from that thing's off state while the flag is up and the thing reads placed, and leave it for the thing's resting state when the flag falls (§Design notes has the rules it must keep).
7. On remotes, route the return. After a restore the enable comes back with a placed name already true, which the gimmick without persistence never produces. For each thing, send that case to the path a late joiner takes, not to the home state. Without it, remotes show the thing at home first, and nothing errors. In `grab-sync-persist` it is the glue's rung from `Disabled` into `Waiting`; delta item 5 in its generator's docstring gives the reasoning.
8. Run `vrc-bridge` beside VRChat, with VRChat's OSC on.

Depends on the VRC SDK and VRCFury.

## How to use

- Nothing to operate. Swap between avatars wearing the same gimmick and the state follows.
- A world join, a rejoin, Reset Avatar, or a swap through an avatar without the gimmick restores nothing. Those are the bridge's rules.

## Additional notes

- **The gimmick is off for a moment at every load** wherever `Id` is not 0, bridge or no bridge: from the layer's first evaluation until the window closes, or until the hold ends after a restore.
- **One layer per namespace.** The bridge restores several namespaces on one avatar independently, and the avatar keeps them independent only when each layer has an enable of its own. Two gimmicks built on `object-sync` share `ObjectSync/Enable`, so the first layer to finish switches it back on while the other is still holding it off.
- **The bridge restores the whole payload or none of it.** A payload name the old avatar never changed from its default stays at the default the reset wrote.

## Performance stats

```c++
Synced parameters:     0 bits added (no rank-gated component: no physbone, contact, constraint or renderer)
Unsynced parameters:   4 reserved + the enable mirror (namespaced, OSC-visible), 1 flag (local); the payload is yours
FX Animator Layers:    1
States:                8
```

## Knobs

`CONFIG` in `generate.py` is this entry's own example build; a consumer passes its own config to `document()`. Every key is required except `id`.

| Knob | What it does |
|---|---|
| `namespace` | `BridgePersist/<Name>`, one segment under `BridgePersist/`. The prefix the bridge watches; the reserved names and the mirror are declared under it. |
| `internal` | The prefix for the layer's own local names; the flag is `<internal>/Hold`. It must not overlap the namespace, since anything under the namespace would be restored. |
| `controller` | The emitted controller's name. |
| `id` | The declared default of `Id`, a byte; 0 switches the layer off. Left `None`, it is minted from the namespace, so it is stable across regenerations. |
| `enable` | The gimmick's enable parameter and its declaration, verbatim. The layer declares it identically; a bool or float, never an int. |
| `payload` | Every payload name with its declaration, verbatim. All of them are reset at load; each must sit under the namespace. |
| `placed` | The payload bools that mean something is placed. With none of them true after a restore, the layer skips the hold. |
| `hold` | How long the flag stays up after a restore that has something placed: the consumer's own settle time, nothing the bridge waits on. A consumer whose state reaches remotes through a synced wire weighs that wire's refresh against the wait every watching player pays; `grab-sync-persist` holds for its settle alone (`PLACE_SETTLE`). |

`validate()` refuses a config that breaks any rule above, and a few more (a missing key, a repeated or reserved payload name, the mirror listed in `payload`, an enable under the namespace), naming the offender.

`WINDOW_SECS` is not a knob: it is the wire contract's, and the bridge's own waits fit inside it.

**Provenance:** this workspace's own design, built against `vrc-bridge`'s persistence mapping.

## Design notes

`generate.py`'s docstring is the state-by-state walk; the emitted `controller.yaml` is the graph. What follows is why it is shaped this way.

- **The bridge's side of the exchange lives in one layer, not in the consumer's controller.** A consumer that must persist several things, or already has a complicated controller, gains one state per thing to put back and nothing else.
- **Invariants the docstring gives the reasons for:** the switch-off and the reset are written twice, because the client drops the first write after a load; the window runs in a state of its own; `Announce` and `Boot` go out together and the bridge orders them; every state in the exchange leaves on a timer or unconditionally, so no wire value can hold it; the mirror is written only while idle.
- **What the consumer's state must keep.** Entered only from the thing's off state, it knows the gimmick is parked and the payload final. It needs no rung on the enable, because the flag falls in the evaluation the enable returns. The off state must not be entered again after the bridge's write, or its own reset overwrites what was restored. So in the consumer's graph every transition into the off state, except the one it takes at load, waits on the enable falling; the layer holds the enable off throughout, so only a menu toggle in the window can then re-enter it. `grab-sync-persist`'s generator refuses a glue that breaks this rule.
- **Each hand-off between the two layers costs a frame.** The consumer's state is entered one frame after the flag rises and left one frame after it falls.

## Traps

- **A bridge write that lands after the window closed lands on a running gimmick.** The layer returns `Restore` to 0 and puts the mirror back, but every other payload name holds what the bridge wrote until the gimmick overwrites it. The consumer says in its own README what that does.
- **A switch from the menu during the window is unguarded.**
- **The flag must stay local.** Published, a host avatar's declaration of the same name could capture it. Keep `internal` out of every `globalParams` wildcard.
- **The layer and the consumer's controller must sit in one FullController component.** Split across two, the flag gets a different prefix on each side and the consumer's state never fires, with no build error.

## What is not proven here

- The double write at load is there for the shipping client and cannot be shown in the emulator.
- Doubled OSC delivery and the order of `/avatar/change` across a real swap are the shipping client's to show.

## Changing it

Edit `generate.py`, run `python generate.py`, and recompile `controller.yaml` into `built/` (`../CONVENTIONS.md` §The gate has the procedure). A consumer re-runs its own build script, which calls `document()` on its config, and recompiles its own copy.

**Giving a copy of a gimmick its own `Id` without regenerating:** declare `<namespace>/Id` in a controller of your own listed first in both FullController lists; the first declaration of a name is the one the build keeps.

## Verifying the install

- **Bake:** every name under the namespace keeps its exact name, and `Id` carries your value. A `VF##_` prefix on any of them means `BridgePersist/<Name>/*` is missing from `globalParams`: the build succeeds and the bridge reads nothing. The flag should carry a `VF##_` prefix.
- **Nothing restores:** both avatars need the same namespace and `Id`, and `Id` must not be 0. The bridge has to have been running before the outgoing avatar loaded, and the swap has to go straight from one avatar to the other. The bridge's log says why it skipped a restore.
- **Restores, but nothing is put back:** the consumer's state never fired. Check that it reads the flag by the exact name the layer declares, and that both controllers sit in one FullController.
- **Emulator:** spawn the avatar away from where the thing was placed, or a restore that did nothing looks like one that worked. The emulator announces the same avatar on every play entry, so the bridge needs its test-only reload-as-swap switch.
