# held-prop — multi-anchor self-syncing prop (Module tier)

A prop that lives at a stow point on your body, is taken into the hand by a physical gesture, and
placed back the same way. One prop, one `VRCParentConstraint` multiplexing `[StowAnchor,
HandAnchor]` — never the duplicate-object anchor swap (`gimmicks.md` names it to warn against it).
Take/place arms on **own-hand-near + Fist** and commits on the gesture **release** — a zero-timer
anti-misfire: an accidental Fist near the prop does nothing until you let go near it. Module wire
surface: **one synced banded mode int** (8 bits pre-compressor; the VRCFury Parameter Compressor
reclaims the width, and nothing here blocks membership — only Add-type drivers do, this module
stamps with Set). The menu holds only the enable, unsynced — the int carries the outcome.

**Provenance:** the anchor-multiplexer + self-syncing-mode-int mechanism as vendor-proven by
a vendor reference implementation (sensor → synced mode → actuator separation, commit-on-gesture-release, the
invalid-value guard) and in-house by our own anchor multiplexer (our named pattern,
`gimmicks.md` §Constraint patterns). Nothing avatar-specific survives: placeholder payload,
plain-humanoid anchor targets, standard `Hand` tag sensing.

## Interface

- **Params:**
  - `HeldProp/Mode` (int, out) — synced, **unsaved**. The rest mode: 0 Hidden (off-is-reset),
    1 Stowed, 2 Held; values above 2 are invalid and guard-routed to Stowed on remotes. Written
    only by the wearer's `localOnly` drivers; remotes pose from it alone (every state re-derives,
    so there is no late-join park — the int arriving is the whole handshake).
  - `HeldProp/Enable` (bool, in) — **unsynced** menu intent (the VRCFury Toggle on the prefab
    root drives it via `globalParams`); the mode int carries the outcome, so the menu costs 0
    sync bits.
  - `HeldProp/NearProp`, `HeldProp/NearStow` (float, sensing) — own-hand proximity receivers
    (`allowSelf` only — self-touch as authorization, no stranger can take the prop; `localOnly` —
    remotes never need them). Never synced/saved/menu-exposed.
  - `GestureRight` (VRC built-in) — Fist (1) is the grip gesture. Re-key the FX conditions and
    swap the Gesture-layer mask for a left-hand prop.
- **Seam:** VRCFury `FullController` on the prefab root with **two controller rows** —
  `built/HeldProp_Fx.controller` (FX) and `built/HeldProp_Gesture.controller` (Gesture) — plus
  `prms: built/HeldProp_Fx_Parameters.asset` (the single sync-surface declaration; the Gesture
  document declares its shared param `scratch` precisely so no second, drift-prone copy exists)
  and `globalParams: [HeldProp/Enable]` for the Toggle. `rootBindingsApplyToAvatar: 0` ↔
  `basis: mount-root`. MA `BoneProxy` on the two anchors only — placement you can see while
  authoring (VRCF ArmatureLink snaps at build). The seam invariant holds by construction: every
  animated binding targets the `Container` subtree, which no BoneProxy touches; the anchors carry
  only constraint sources (object references, path-immune) — CONVENTIONS §Seam ordering.
- **Dependencies:** VRC SDK + VRCFury + Modular Avatar (the two BoneProxies), and a **humanoid**
  avatar — the Gesture-playable merge refuses a generic rig (VRCFury errors at build) and the
  anchor BoneProxies resolve `Chest`/`RightHand` through the humanoid mapping.
- **Required assets:** none — `Payload` is a placeholder sphere on Unity's built-in default
  material; swap it for your prop mesh, keep it under `Container`.

## The things to know before wearing it

- **The grip seizes the right hand while Held.** The Gesture-playable layer (masked to the right
  hand) overrides finger pose with the embedded grip clip whenever `Mode == 2`; gesture *params*
  keep firing — only the visible fingers are overridden. That is the feature; know it's there.
- **Repoint the anchors per avatar.** `StowAnchor` ships BoneProxy'd to **Chest**, `HandAnchor`
  to **Right Hand**. Move/re-target the proxies and slide the anchor GOs until the prop sits
  right — both are referenced only as constraint sources, so repointing is safe.
- **Growth path — more anchors:** a third anchor is a new `<X>Anchor` GO + constraint source +
  a mode band + a weights clip + arm/commit edges (never a second controller — the fork-drift
  trap). Others-grabbable and world-drop behavior are `grab-prop` / `drop-on-player` territory;
  compose, don't grow this entry into them.

## How it works

The FX machine is the drop-on-player split, minus the non-derivable bands: local edges arbitrate
off live sensors + gesture and stamp `Mode` on state entry; remote edges pose from `Mode` alone.
`TakeArmed`/`PlaceArmed` are local-only transients holding the origin pose — remotes see nothing
until the commit stamps the int. Disarm (hand leaves the zone) outranks commit in the ladder, so
a same-frame leave+release takes nothing. Anchor changes crossfade the constraint weights over
the transition (0.25 s), so the prop glides hand↔stow instead of teleporting.

Empirical constants (labeled in the YAMLs; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Anchor crossfade | 0.25 s | emulator sweep (this entry's build) |
| Grip blend | 0.15 s | same |
| Arm / disarm thresholds | >0 / <0.00001 | contact-tracker lineage |
| Grip pose muscle values | see gesture.yaml | eyeballed on the emulator rig; feel-tunable |

## Verified (Av3Emulator, this entry's build)

On the minimal humanoid rig, post-bake: sync surface = `Mode` synced int only (Enable + both
sensing floats unsynced); MA had genuinely moved `StowAnchor` under the Chest bone. Local flow:
enable → Stowed(1); fist at the prop **arms without committing** (Mode holds 1 while gripped);
release → Held(2) + weight crossfade; fist at the stow → release → Stowed(1); enable off →
Hidden(0), prop hidden (off-is-reset). Remote clone re-derived the Stowed pose from the synced
int alone (its own Enable never arrives — by design). Gesture half: the merged `HeldProp/Grip`
layer enters `Grip` on `Mode == 2`. **Named residuals** (in-game / real-avatar): finger-bone
muscle application (the test rig has no finger bones — stock humanoid retargeting; spot-check on
first real compose) and true network timing.

## Rig

    HeldProp                          root — VRCFury FullController (FX + Gesture rows) + Toggle
    ├─ Container      (0, 1.1, 0.14)  VRCParentConstraint, sources [source0 StowOffset, source1 HandOffset]
    │  ├─ Payload                     sphere, built-in default material — swap for your mesh
    │  └─ PropSense                   VRCContactReceiver proximity r=0.15, tags [Hand], allowSelf only,
    │                                 localOnly → HeldProp/NearProp (the take arm zone rides the prop)
    ├─ StowSense                      VRCContactReceiver proximity r=0.15, tags [Hand], allowSelf only,
    │                                 localOnly → HeldProp/NearStow. Lives at the module ROOT and is
    │                                 position-CONSTRAINED to StowOffset — a receiver parented under the
    │                                 MA-moved anchor escapes VRCFury's param rewrite and reads 0 forever
    │                                 (CONVENTIONS §Seam ordering; measured in this entry's build)
    ├─ StowAnchor     (0, 1.1, 0)     MA BoneProxy → Chest, AsChildAtRoot (zeroes to the bone at build)
    │  └─ StowOffset  (0, 0, 0.14)    plain GO — the consumer-editable stow offset; constraint source
    └─ HandAnchor                     MA BoneProxy → Right Hand, AsChildAtRoot
       └─ HandOffset  (0, 0, 0)       plain GO — the consumer-editable grip-alignment offset

Constraints `Locked`; source weights swapped by the clips only. Offsets are the editable layer
because `AsChildAtRoot` discards edits on the proxy GO itself at build. Unique object names — no
`GrabBone` here by design (`grab-prop`/`drop-on-player` own that name; CONVENTIONS §Naming).

## Rebuilding

`controller.yaml` + `gesture.yaml` → `CompileController` → `built/` (committed; the prefab
references both controllers by GUID — recompile is GUID-stable; regenerate built/ as a unit over
the committed `.meta`s). The prefab is hand-maintained against the Rig section above.
