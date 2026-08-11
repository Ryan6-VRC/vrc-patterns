# osc-wardrobe — change your worn avatar from your own menu (Structural Module)

Press a button on your expression menu and your avatar changes. The menu sends an int, an OSC host on your PC turns it into VRChat's `/avatar/change`, and the client swaps. **Zero animator layers, no synced bits, no controller** — the two parameters exist only to reach the wire.

**Provenance:** built against VRChat's own inbound `/avatar/change` support (2025.1.2, widened in 2025.4.2). No borrowed code.

This entry is **half of a system and inert on its own.** It ships the avatar side; the swap is performed by [`vrc-bridge`](https://github.com/Ryan6-VRC/vrc-bridge)'s `osc_wardrobe` mapping, which is where the avatar-id table lives. Nothing here has any effect without that running.

## Interface

- **Params:** `OscWardrobe/Manifest` (Int, unsynced, **not saved**, ships at 0 — set it to your manifest id) — the marker the host reads to learn *which* wardrobe this avatar has. `OscWardrobe/Slot` (Int, unsynced, **not saved**, default 0) — the button press. Both are declared for OSC's sake only: nothing on the avatar reads either one.
- **Seam:** none. No merge, no anchor, no binding frame, no controller — an MA Parameters component and a menu, so the prefab drops anywhere under the avatar and no path can break.
- **Dependencies:** Modular Avatar.
- **Required assets:** an OSC host running `vrc-bridge`'s `osc_wardrobe`, with a manifest whose `id` matches this avatar's `OscWardrobe/Manifest` default. Without it the buttons do nothing at all.

**Single-instance.** Both parameter names are MA-declared and therefore un-prefixed, so two copies collide — and the marker is *definitionally* one per avatar, since its whole job is to identify this avatar's wardrobe. A second instance is incoherent, not merely redundant.

## Installing it

Drop the prefab under your avatar, then make two edits on the instance:

1. **Set `OscWardrobe/Manifest`'s default** on the MA Parameters component to your manifest's `id`. It ships at **0**, which no manifest can claim — so if you skip this step the bridge says so loudly instead of silently adopting whoever's manifest happens to be id 1.
2. **Rename the eight `Slot N` objects** to whatever those avatars are. The GameObject name is the menu label — see **Rig** for why that, and not the control's own name field.

Then write the matching manifest on the bridge side. Delete buttons you do not want; a slot with no manifest row warns in the bridge log and changes nothing, so leaving all eight is also fine.

## Before you compose it

**Valid marker ids are 1–255.** MA's inspector clamps an Int default to `0..255` and re-clamps it whenever you touch the sync type, so a larger number silently becomes 255 as you type it. Nothing warns. (This is MA's clamp specifically — the VRChat SDK inspector has its own, separate truncation on large Int defaults, which `runtime.md` §Parameters owns.)

**Do not set the sync type to "Not Synced".** It sits in the same dropdown as Int and reads like the right answer for a parameter you do not want replicated — but in MA it means *do not register this in Expression Parameters at all*. The marker then 404s over OSCQuery forever and the slot write lands on the client's unchecked animator-only path, both silently. The correct authoring is **Int with Synced unchecked**, which is what the prefab ships.

**Neither parameter may be marked Saved,** and MA's own defaults fight you here: a freshly added Menu Item comes with Synced and Saved *on*, and MA merges those flags with the host avatar's declaration by OR — the host wins, with no build error. A saved slot restores non-zero on your next avatar load and swaps you again immediately. If you add a ninth button by hand, clear Synced and Saved on it and turn Auto value off.

## How it works

There is no mechanism on the avatar, which is the point. A menu Button writes `OscWardrobe/Slot`, VRChat emits the change over OSC, and the host maps the value to an avatar id and sends `/avatar/change` back. `OscWardrobe/Manifest` is never written at runtime — only its *default* matters, because the host reads it over OSCQuery to decide which table applies. That indirection is what lets two avatars carry different wardrobes: give each its own manifest and its own marker default.

Four consequences worth knowing:

- **VRChat only swaps to avatars in your favorites, recents, own uploads, or purchases.** A button that does nothing is far more likely an ineligible avatar than a broken rig — and nothing will tell you so, because the client acknowledges every request identically whether it can wear the avatar or not. Your profile page on vrchat.com shows what you are actually wearing.
- **Pressing a button with the game menu open works** — measured, which matters because the menu is the only place you can press it from.
- **Buttons, not toggles.** The host swaps on the press and ignores the release. The SDK holds a Button active for a minimum 0.2 s however briefly you tap it, which is what guarantees the value reaches the wire.
- **Nothing here is synced,** so remote players see none of it and it costs no sync bits. They just see you change avatar, the way they always do.

## Verifying the install

Read the **baked** parameters, not the authored ones — MA rewrites flags at build, and the OR-merge above only shows up post-build. Enter play mode (or bake) and check the generated `VRCExpressionParameters` for:

| | |
|---|---|
| `OscWardrobe/Manifest` | Int, `networkSynced` **false**, `saved` **false**, default = your id |
| `OscWardrobe/Slot` | Int, `networkSynced` **false**, `saved` **false**, default 0 |

and the generated menu for a `Wardrobe` submenu holding your buttons, each `Button` type with parameter `OscWardrobe/Slot` and its own value. A submenu that is missing entirely means the Menu Installer is not above the Menu Item; buttons whose values are not what you authored mean Auto value got left on somewhere.

Then, with the bridge running: press a button and watch its log. It names the slot and the avatar id it sent, so a press that logs a send but does not swap is an eligibility or id problem, and a press that logs nothing is an avatar-side problem — unless the bridge has already reported one of the states below, each of which it says once rather than per press.

A press reporting the marker was read from something that does not identify itself as VRChat is neither: most likely another OSCQuery app holds the bridge's target slot, since VRCFaceTracking and VRCOSC both advertise themselves and either can take it before a VRChat client is found. Pressing again works once a VRChat client is discovered and takes the slot. If one is already running, its service is not being recognised — `vrc-bridge/docs/design.md` §Target selection has the ranking rule.

## Rig

    OscWardrobe                MA Parameters: both params Int + localOnly, not saved, not internal
    │                          MA Menu Installer (installs at the avatar's root menu)
    │                          MA Menu Item: SubMenu, MenuSource = Children, label "Wardrobe"
    ├─ Slot 1                  MA Menu Item: Button, param OscWardrobe/Slot, value 1,
    │                          Auto value OFF, Synced OFF, Saved OFF, label empty
    ├─ Slot 2 … Slot 8         the same, values 2…8

**The menu label is the GameObject name.** MA reads `label` if set and otherwise falls back to the object's name; the control's own `name` field is never read, so editing it does nothing. The buttons ship with `label` empty on purpose, which makes renaming the object in the hierarchy the whole edit. The submenu is the exception — it carries `label = "Wardrobe"` so the menu reads that regardless of what the root object is called.

**Auto value is off on every button, deliberately.** With it on, MA allocates values to menu items sharing one Int parameter in hierarchy order — which happens to produce 1…8 and therefore looks correct, while making a reorder of the objects silently remap every button. The values are authored so that reordering, deleting, or adding a button changes nothing but itself.
