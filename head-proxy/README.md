# head-proxy (Module, study)

Throw your voice into a puppet or a prop: it speaks from there while your visible head stays where it is and stays yours to animate. Your viewpoint and hearing stay at your headset.

VRChat plays your voice from the humanoid Head, so this needs a re-rigged base: your armature gains non-deforming copies of the head and eye bones (the **proxy**), mapped as the humanoid Head and eyes. A position constraint holds the proxy on your real head and has a spare, empty second source slot. A separate gimmick (the **consumer**) brings the object the voice moves to (the **socket**), and you point the slot at it once per avatar.

Three prefabs: copy the rig from `HeadProxyRig.prefab`, a complete demo avatar; add `voice/HeadProxyVoice.prefab`, the consumer; compare against `voice/HeadProxyVoiceRig.prefab`, the demo avatar with the consumer added and the slot wired.

## How it works

- The demo FBX (`assets/HeadProxyRig.fbx`) carries a duplicate head bone and duplicate eye bones. Unity's humanoid Head and eyes map to the duplicates (`Head_Proxy`, `LeftEye_Proxy`, `RightEye_Proxy`), which deform nothing. The original `Head` keeps every vertex weight and follows the proxy's rotation by constraint.
- The humanoid Head is the voice origin, the IK head target, and the anchor of the first-person head chop (the client shrinks your head in your own view so it does not block the camera). A non-deforming proxy can move without moving any geometry, and the deform `Head` can be animated freely, scale included, except while the fake chop below holds its scale.
- `Head_Proxy`'s `VRCPositionConstraint` has two source slots: the deform `Head` at full weight, and an empty slot at zero weight.
- The consumer owns the socket `VoiceTarget` and an FX layer that swaps the two source weights on `HeadProxy/MoveHead`. An override on each avatar points the empty slot at the socket; `voice/WireVoiceTarget.cs.txt` writes it.
- Moving the humanoid head far enough makes the client release its chop, which would put your own full-size head over your camera. The base's `FakeChop` layer reproduces the chop with a scale constraint whenever `HeadProxy/MoveHead` is on, on your own copy only and never in a mirror.

## Install guide

Requires the VRC SDK, VRCFury, and this library's `mirror-detect` entry (without it the fake chop never engages).

1. Add the proxy bones to your armature in Blender (§Blender recipe), then map humanoid Head, LeftEye and RightEye to them. If Unity's auto-mapper assigned a hair bone as Jaw, drop that row from `humanDescription.human`: after the remap it fails avatar creation with "Head_Proxy is not an ancestor of \<hair bone\>".
2. Recreate on your base the objects and components `HeadProxyRig.prefab` carries (§Rig lists each), then point every constraint source and `VRCHeadChop` entry at your own bones. On the root: a VRCFury `FullController` merging `built/HeadProxy_Fx` and `mirror-detect`'s `MirrorDetect_Fx`, with `HeadProxy/MoveHead` in its `globalParams`, plus `FixWriteDefaults`. Leave the position constraint's second slot empty.
3. Add `voice/HeadProxyVoice.prefab` under the avatar root, or copy its parts into your own gimmick. Move `VoiceTarget` where the voice should come from: under a puppet's head, on a prop, in front of you.
4. If your armature path differs from `HeadProxyRig/Hips/Spine/Chest/Neck` (an `Armature/Hips/…` base does), edit the bindings in both `controller.yaml` and `voice/controller.yaml`, keeping the consumer's leading `/`. Then regenerate both `built/` folders with `CompileController` from this workspace's `avatar-tools` package (`CONVENTIONS.md` §The gate).
5. Wire the slot: run `voice/WireVoiceTarget.cs.txt` as an editor method body with `ROW` set to your avatar's prefab, or drag `VoiceTarget` into source 1 of `Head_Proxy`'s `VRCPositionConstraint` as a prefab-instance override.
6. Build. The expression menu gains a **Move Head** toggle.

## How to use

- **Move Head** on moves the voice origin and the IK head to `VoiceTarget`, and everyone hears you from there; your visible head stays home.

## Additional notes

- **One consumer per avatar.** There is one slot, and the shipped Toggle exports an unprefixed name.
- **The base alone is inert.**
- **Anything mounted on the humanoid Head moves with the voice.** A merge, bone proxy or accessory targeting humanoid Head lands on `Head_Proxy`; put head geometry under the deform `Head` instead.
- **Do not rename `Head_Proxy` or the bones above it.** The clips bind by path, and the wiring body finds `Head_Proxy` and `VoiceTarget` by name.

## Performance stats

```c++
FX Animator Layers: 4        (FakeChop, mirror-detect's MirrorDetection, the consumer's VoiceProjection and its Toggle's layer)
Constraints:        5        (Head rotation + scale, two eye rotations, Head_Proxy position; the consumer adds none; depth unmeasured)
VRCHeadChop:        1        (unranked)
Synced parameters:  1 bit    (HeadProxy/MoveHead)
```

## Knobs

| Knob | What it does |
|---|---|
| `VoiceTarget` placement | Where the voice and IK head go. Never under `Head`, `Head_NoChop` or `Head_Proxy`: the socket is `Head_Proxy`'s source, and the chop re-places the other two |
| `chop_constraint_restore` length (`controller.yaml`) | How long the restore pulse holds the deform head at scale 1 before the scale constraint switches off. Shorter risks a low-FPS client never sampling it and the head sticking near zero |
| `FakeChop_Zero` scale (prefab) | The scale the fake chop shrinks the deform head to |

**Provenance:** generalized from a private production avatar's head-chop architecture; client chop behaviour from the public VRChat docs, Av3Emulator's reimplementation (MIT), and in-game measurement on the production rig.

## Design notes

**The slot ships empty because the socket is composition.** A base should not carry an object that exists only for one module, and a weighted null source costs the base nothing: the solve skips it. A constraint source is an object reference with no path form, so the slot pointing across the prefab boundary can only live as a prefab-instance override on each avatar, which the wiring body writes. The body proves the slot names a `VoiceTarget` on the avatar, not that the consumer around it is complete.

**Consumer bindings are absolute.** Each starts with `/`, which VRCFury resolves from the avatar root instead of walking up from the FullController (`nondestructive.md` §Reference hardening), so a child named like an armature node under the consumer can never capture the path.

**The fake chop lives with the rig.** The chop release follows from moving the humanoid head, whatever moves it, so the base keeps `FakeChop` and any consumer gets the vision fix by driving `HeadProxy/MoveHead`.

**One `VRCHeadChop` on `Head_Proxy` carries the whole chop policy:** it exempts the proxy and `Head_NoChop` and chops the deform `Head`. The client's default chop targets the humanoid head, which here is the exempt proxy, so first-person hiding runs entirely through the explicit `Head` entry. A base expecting many head gimmicks publishes exempt docking slots like `Head_NoChop` rather than each module carrying its own `VRCHeadChop`. A self-interaction gimmick docked there needs no chop compensation or mirror detection; `head-deform`'s `HeadDeformProxy.prefab` is the worked composition.

**A base with a synced visemes toggle may key the move off it.** Turning visemes off and throwing the voice are one intent, so such a base can skip a separate bit: the consumer drops its Toggle and sync declaration and sets `HeadProxy/MoveHead` from the visemes parameter on every client. A lean, not a rule.

### Client chop model

The client's exempt-bone rules are `runtime.md` §Other load-bearing components (VRCHeadChop): an exempt bone follows the humanoid head wherever it goes, and the chop releases once a target bone is roughly half a metre to a metre from the avatar root. Two consequences on this rig:

- **Engage the move and `Head_NoChop` and its occupants relocate to the socket**, and even the deform head's *position* tracks it.
- **Do not source the humanoid head from anything the chop re-places, unless the two are co-located.** This rig sources `Head_Proxy` from the chop-listed deform `Head` and escapes only because they are co-located.

## Traps

- **A second declaration of `HeadProxy/MoveHead` decides its sync.** A parameter declaration is first-wins and taken whole across FullControllers (`nondestructive.md` §Merge behaviours), and the base's FullController on the root declares first, which is why the base declares the bit `scratch`. A module whose FullController is processed before the consumer's and declares it unsynced makes the move local-only, with no build error.
- **VRCFury's prefab fixer leaves the slot override alone.** It reverts property overrides only on VRCFury components, and this override sits on the `VRCPositionConstraint`.

## What is not proven here

No bake and no emulator session has run on the consumer half.

## Verifying the install

Run the wiring body; `already wired` means the slot names the socket, and a FAIL names what is wrong.

Then play mode with Av3Emulator, avatar **at the world origin**, `EnableHeadScaling` flipped on only **after** the runtimes have run a few frames: the emulator caches exempt-bone baselines on the first chop-enabled frame, and enabling early or off origin bakes a poisoned baseline that silently no-ops the exemption or throws docked objects far off. Then, reading at a pause:

- deform `Head.lossyScale` near zero, `Head_Proxy` and `Head_NoChop` near 1, in place.
- `MoveHead` on: `Head_Proxy` lands at `VoiceTarget`, and the exempt slot and any occupant follow it. `FakeChop` entering `Chopping` at all is the proof that `IsMirror` read −1 (a hard transition condition).
- `MoveHead` off: a restore pulse returns the deform head to scale 1 before the scale constraint switches off, so it never sticks near zero for a photo.

With the slot wired:

- **`Head_Proxy` stays home:** the consumer's bindings do not resolve (an armature path that differs, or a lost leading `/`), or the consumer's FullController lacks `HeadProxy/MoveHead` in `globalParams`, so its layer reads a prefixed name the Toggle never sets.
- **The move works but your own head appears over your camera:** the base's FullController lacks `HeadProxy/MoveHead` in `globalParams`, or the mirror-detect row is missing, so `FakeChop` never engages.

What the emulator cannot show: any mirror-side visual (its mirror copies every transform from your local copy each frame, `emulator.md`), the root-distance release (no capsule model), and the in-game ordering of the client chop against animator writes. Hand those to an in-game tester, in that order.

## Blender recipe

Duplicate the head bone and the eye bones **in place, in the same armature**. The head duplicate becomes a sibling of `Head` under `Neck` with `use_deform` off; deform weights stay on the originals, which never move. Parent the eye duplicates under the head duplicate. `assets/HeadProxyRig.fbx` is the owned bare armature (primitives only, exact bone names) and regenerates from this recipe.

## Rig

    HeadProxyRig                    avatar root: descriptor; VRCFury FullController [HeadProxy_Fx + MirrorDetect_Fx], globalParams [HeadProxy/MoveHead]; FixWriteDefaults
    ├─ Body                         demo skinned mesh
    ├─ HeadProxyRig/Hips/…/Neck
    │  ├─ Head                      deform, not humanoid; VRCRotationConstraint ← Head_Proxy; VRCScaleConstraint ← [FakeChop_Zero, FakeChop_One], off at rest
    │  │  ├─ LeftEye / RightEye     deform eyes; VRCRotationConstraint ← the proxy eyes
    │  │  └─ Head_NoChop            empty chop-exempt docking slot
    │  └─ Head_Proxy                humanoid Head, non-deform; VRCPositionConstraint ← [Head, empty slot]; VRCHeadChop
    │     └─ LeftEye_Proxy / RightEye_Proxy   humanoid eyes
    ├─ FakeChop_Zero                scale source near zero
    └─ FakeChop_One                 scale source at 1

    voice/HeadProxyVoice            the consumer
    └─ VoiceTarget                  the socket

    voice/HeadProxyVoiceRig         prefab variant of HeadProxyRig: HeadProxyVoice added under the root, slot 1 overridden to its VoiceTarget
