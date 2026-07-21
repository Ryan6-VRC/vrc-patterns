# headchop-mount — chop-exempt head mount, first-person visibility toggleable (Module tier)

A head-riding mount whose payload stays full-size in the wearer's own first-person view: VRChat
shrinks the humanoid head bone (and everything under it) to ~0 locally so your own head doesn't
fill the camera, and a `VRCHeadChop` targeting the mount at `scaleFactor 1` exempts it. The menu
toggle animates the VRCHeadChop *holder* GO active — the component's `activeInHierarchy` gate —
so the payload flips between visible-to-yourself and chopped with the head. The payload sits as
a **sibling** of the holder, deliberately: the toggle gates only the exemption component, never
the payload's own GO-active — a payload *under* the holder would vanish in every view when
toggled off. Mirrors and other
players are unaffected in both states. Replace `Payload` (a default-material cube) with your
accessory — including an *interactive* one: the chop shrinks colliders and physbone chains
with the head, so a self-grabbable or self-touchable head gimmick (the face-stretch class)
needs exactly this exemption to stay usable in first person (`head-proxy-rig` §Head-distortion
gimmicks carries the full recipe, mirror compensation included).

**Provenance:** generalized from a private production avatar's head-chop architecture; the
self-exemption mechanism is the same one Modular Avatar's `VisibleHeadAccessoryProcessor` uses
(exempt proxy child of the head, accessories reparented under it).

## The component contract

From the public VRChat docs unless marked otherwise:

- `scaleFactor` clamps 0–1: 0 = chopped, 1 = full size. `globalScaleFactor` multiplies all of a
  component's bones. `applyCondition` restricts to VR / non-VR.
- **Budget: 16 components per avatar (SDK build error past it), 32 bones per component.** A
  component is spent per module that self-exempts — a base that expects many head gimmicks
  should publish exempt *slots* instead and let modules dock (see `head-proxy-rig`).
- The effect is first-person-local only: mirror clones and remote clients never apply it.
- The component is animator-gateable — `activeInHierarchy && enabled` — which is what the
  toggle here drives.
- Components overlapping on one bone **multiply** (the result is at or below the lowest
  factor); you cannot un-chop a bone another component chopped (Av3Emulator's
  reimplementation, MIT; not in the public docs).

On a proxy-head rig (`head-proxy-rig` — humanoid Head mapped to an exempt proxy bone) this
module is redundant but harmless: the whole humanoid-head subtree is already exempt, so the
toggle changes nothing.

## Interface

- **Params:** `HeadChopMount/FirstPerson` (bool, in) — **unsynced**, saved, default on: a
  preference ("show my own accessory") that survives avatar load — and head chop is
  first-person-local, so remotes see no difference in either state and a synced bit would buy
  nothing.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔
  `basis: mount-root`) merging `built/HeadChopMount_Fx.controller` + params;
  `HeadChopMount/FirstPerson` rides `globalParams`, a VRCFury `Toggle` (`useGlobalParam`,
  `defaultOn`) is the menu front. A VRCFury `ArmatureLink` reparents `Mount` onto the humanoid
  **Head** bone with `alignPosition`/`alignRotation` (snaps at build, not in edit mode — the
  edit-mode placement is cosmetic). Link and animation deliberately share one framework: the
  merged clip binds `Mount/ChopExempt` GO-active by path, and VRCFury repaths its own merged
  bindings across its own link; an MA BoneProxy anchor would strand that binding
  (`docs/nondestructive.md` owns the mechanism).
- **Dependencies:** VRCFury. The consumer avatar's humanoid Head must actually chop — see the
  proxy-rig note above.
- **Required assets:** none.

## Verifying the install

Play mode with Av3Emulator, avatar **at the world origin**, and enable the control's
`EnableHeadScaling` only **after** the runtimes have run a few frames — the emulator caches
each exempt bone's rest state on its first chop-enabled frame, so enabling too early (or off
origin) bakes a poisoned baseline and the exemption silently no-ops (positions can land
hundreds of meters out). Then: the humanoid head's `lossyScale` reads ~0.0001 while `Payload`
reads its authored scale in place; drive `HeadChopMount/FirstPerson` off and `Payload` follows
the head to ~0.0001. A payload that never chops with the toggle off means the consumer rig's
humanoid head isn't in the chop set (proxy rig), or the ArmatureLink didn't land on the head.

The emulator's mirror clone is a transform-copy puppet — it inherits the local copy's chopped
scales instead of stripping the component like the client does, so **all mirror-side visuals
are in-game checks**, not emulator ones.
