# head-proxy (Module, study)

Throw your voice into a puppet or a prop: it speaks from there while your visible head stays where it is and stays yours to animate. Your viewpoint and hearing stay at your headset.

VRChat plays your voice from the humanoid Head, so this needs a re-rigged base: your armature gains non-deforming copies of the head and eye bones (the **proxy**), mapped as the humanoid Head and eyes. A position constraint holds the proxy on your real head and has a spare, empty second source slot. A separate gimmick (the **consumer**) brings the object the voice moves to (the **socket**), and you point the slot at it once per avatar.

Three prefabs: copy the rig from `HeadProxyRig.prefab`, a complete demo avatar; add `voice/HeadProxyVoice.prefab`, the consumer; compare against `voice/HeadProxyVoiceRig.prefab`, the demo avatar with the consumer added and the slot wired.

## How it works

- The demo FBX (`assets/HeadProxyRig.fbx`) carries a duplicate head bone and duplicate eye bones. Unity's humanoid Head and eyes map to the duplicates (`Head_Proxy`, `LeftEye_Proxy`, `RightEye_Proxy`), which deform nothing. The original `Head` keeps every vertex weight and follows the proxy's rotation by constraint.
- The humanoid Head is the voice origin, the IK head target, and the anchor of the first-person head chop (the client shrinks your head in your own view so it does not block the camera). A non-deforming proxy can move without moving any geometry, and the deform `Head` can be animated freely, scale included, except while the fake chop below holds its scale.
- `Head_Proxy`'s `VRCPositionConstraint` has two source slots: the deform `Head` at full weight, and an empty slot at zero weight.
- The consumer owns five things:
  - the socket object `VoiceTarget`;
  - an FX layer that swaps the two source weights, keyed on `HeadProxy/MoveHead`;
  - a synced, unsaved declaration of that parameter;
  - the name in its VRCFury FullController's `globalParams`, so VRCFury does not prefix it;
  - the menu control.
- One wiring step joins them on each avatar you add the consumer to: an override that points the empty slot at the consumer's socket. `voice/WireVoiceTarget.cs.txt` writes it and checks it.
- Moving the humanoid head far enough makes the client release its chop, which would put your own full-size head over your camera. The base's `FakeChop` layer reproduces the chop with a scale constraint whenever `HeadProxy/MoveHead` is on, on your own copy only and never in a mirror.

## Install guide

Requires the VRC SDK, VRCFury, and this library's `mirror-detect` entry (without it the fake chop never engages).

1. Add the proxy bones to your armature in Blender (§Blender recipe), then map humanoid Head, LeftEye and RightEye to them. If Unity's auto-mapper assigned a hair bone as Jaw, drop that row from `humanDescription.human`: after the remap it fails avatar creation with "Head_Proxy is not an ancestor of \<hair bone\>".
2. Recreate on your base the objects and components `HeadProxyRig.prefab` carries (§Rig lists each), then point every constraint source and `VRCHeadChop` entry at your own bones. On the root: a VRCFury `FullController` merging `built/HeadProxy_Fx` and `mirror-detect`'s `MirrorDetect_Fx`, with `HeadProxy/MoveHead` in its `globalParams`, plus `FixWriteDefaults`. Leave the position constraint's second slot empty.
3. Add `voice/HeadProxyVoice.prefab` under the avatar root, or give your own gimmick the five consumer parts (§How it works). Move `VoiceTarget` where the voice should come from: under a puppet's head, on a prop, in front of you.
4. Most avatars need this step: if your armature path differs from `HeadProxyRig/Hips/Spine/Chest/Neck` (an `Armature/Hips/…` base does), edit the bindings in both `controller.yaml` and `voice/controller.yaml`, keeping the consumer's leading `/`. Then regenerate both `built/` folders with `CompileController` from this workspace's `avatar-tools` package (`CONVENTIONS.md` §The gate).
5. Wire the slot. By hand: drag `VoiceTarget` into source element 1 of `Head_Proxy`'s `VRCPositionConstraint` on your avatar, as an override on its prefab instance. With the script: paste `voice/WireVoiceTarget.cs.txt` as the body of a static editor method returning a string (or into MCP for Unity's `execute_code`) and set its `ROW` constant to your avatar's prefab path or scene hierarchy path; it prints `wired`, then `already wired` on every later run (§Wiring the slot).
6. Build. The expression menu gains a **Move Head** toggle.

## How to use

- **Move Head** sets `HeadProxy/MoveHead`: synced, unsaved, off at load. On, the voice origin and the IK head move to `VoiceTarget`, and everyone hears you from there; your visible head stays home.
- While it is on, your own view still hides your head (the fake chop), so a far socket never leaves your head over your camera.
- Open `voice/HeadProxyVoiceRig.prefab` to see the finished override.

## Additional notes

- **One consumer per avatar.** There is one slot, and the shipped Toggle exports an unprefixed name.
- **The base alone is inert.** With no consumer, nothing drives `HeadProxy/MoveHead`, the fake chop never engages, and the base spends no synced bit.
- **Anything mounted on the humanoid Head moves with the voice.** A merge, bone proxy or accessory targeting humanoid Head lands on `Head_Proxy`; put head geometry under the deform `Head` instead.
- **Do not rename `Head_Proxy` or the bones above it.** The clips bind by path, and the wiring body finds `Head_Proxy` and `VoiceTarget` by name.

## Performance stats

```c++
FX Animator Layers: 3        (FakeChop, mirror-detect's MirrorDetection, the consumer's VoiceProjection)
Constraints:        5        (Head rotation + scale, two eye rotations, Head_Proxy position; the consumer adds none; depth unmeasured)
VRCHeadChop:        1        (unranked)
Synced parameters:  1 bit    (the consumer's HeadProxy/MoveHead; the base alone declares none)
```

## Knobs

| Knob | What it does |
|---|---|
| `VoiceTarget` placement | Where the voice and IK head go. Never under `Head`, `Head_NoChop` or `Head_Proxy`: the socket is `Head_Proxy`'s source, and the chop re-places the other two. Far from the avatar root the client's chop releases and the fake chop carries your view (§Client chop model) |
| `chop_constraint_restore` length (`controller.yaml`) | How long the restore pulse holds the deform head at scale 1 before the scale constraint switches off. Shorter risks a low-FPS client never sampling it and the head sticking near zero. Regenerate `built/` as a unit after editing |
| `FakeChop_Zero` scale (prefab) | The scale the fake chop shrinks the deform head to |

**Provenance:** generalized from a private production avatar's head-chop architecture; client chop behaviour from the public VRChat docs, Av3Emulator's reimplementation (MIT), and in-game measurement on the production rig.

## Design notes

The state-by-state walk, and why the fake chop drives a scale constraint and is mirror-gated, are the headers of `controller.yaml` (the fake chop) and `voice/controller.yaml` (the move). This section states the remaining invariants and reasons.

**The slot ships empty because the socket is composition.** A base should not carry an object that exists only for one module, and a weighted null source costs the base nothing: the solve skips it. So the base keeps the constraint's source list two long with nothing in the second slot, and every consumer brings its own socket. The price is one wiring step per composed avatar, which is cheap and checkable (§Wiring the slot).

**Consumer bindings are absolute.** Each starts with `/`, which VRCFury resolves from the avatar root instead of walking up from the FullController (`nondestructive.md` §Reference hardening), so a child named like an armature node under the consumer can never capture the path.

**The seam bit's sync belongs to the consumer.** `FakeChop` reads `HeadProxy/MoveHead`, so the base declares it, but as `scratch`: an animator parameter with no expression-parameter entry. That leaves the consumer's synced, unsaved declaration as the only one (§Traps has what a second declaration does).

**The fake chop lives with the rig.** The chop release follows from moving the humanoid head, whatever moves it, so the base keeps `FakeChop` and any consumer gets the vision fix by driving the seam bit.

**One `VRCHeadChop` on `Head_Proxy` carries the whole chop policy:** it exempts the proxy and `Head_NoChop` and chops the deform `Head`. The client's default chop targets the humanoid head, which here is the exempt proxy, so first-person hiding runs entirely through the explicit `Head` entry. A base expecting many head gimmicks publishes exempt docking slots like `Head_NoChop` rather than each module carrying its own `VRCHeadChop`. A self-interaction gimmick docked there needs no chop compensation or mirror detection; `head-deform`'s `HeadDeformProxy.prefab` is the worked composition.

**A base with a synced visemes toggle may key the move off it.** Turning visemes off and throwing the voice are one intent, so such a base can skip a separate bit: the consumer drops its Toggle and sync declaration and sets `HeadProxy/MoveHead` from the visemes parameter on every client. A lean, not a rule.

### Client chop model

The client's exempt-bone rules are `runtime.md` §Other load-bearing components (VRCHeadChop): an exempt bone follows the humanoid head wherever it goes, and the chop releases once a target bone is roughly half a metre to a metre from the avatar root. Two consequences on this rig:

- **Engage the move and `Head_NoChop` and its occupants relocate to the socket**, and even the deform head's *position* tracks it.
- **Do not source the humanoid head from anything the chop re-places, unless the two are co-located.** This rig sources `Head_Proxy` from the chop-listed deform `Head` and escapes only because they are co-located. A far socket crosses the release distance, which is why the fake chop exists.

## Wiring the slot

A constraint source is an object reference with no path form, so a slot that points across a prefab boundary can only live as a prefab-instance override on the composed avatar: in its configuration prefab, or in the scene. Nothing else carries it, and a weighted null source is skipped by the solve with no error, so an unwired avatar builds, looks correct, and the voice simply never moves. That silent failure is what the check exists for.

`voice/WireVoiceTarget.cs.txt` is one idempotent editor body that both writes the override and checks it; its header lists the three result lines and the `WRITE = false` check-only mode. It refuses to overwrite a slot naming another object. Run it after every compose, reparent or prefab rebuild of a row. The override targets the `VRCPositionConstraint`, not a VRCFury component, so VRCFury's prefab fixer, which reverts property overrides on VRCFury components at play-mode entry and build, leaves it alone.

## Traps

- **`CheckAvatar` and `CheckAnimator` report the consumer's absolute bindings as unresolved.** Their binding walk honours a leading `/` only on a FullController carrying path-rewrite rules, which this one does not; VRCFury's own resolver handles it. `CheckAvatar` then reads CLASSIFY on a correct row. Confirm a binding by resolving its path, without the `/`, from the avatar root.
- **A second declaration of `HeadProxy/MoveHead` decides its sync.** A parameter declaration is first-wins and taken whole across FullControllers (`nondestructive.md` §Merge behaviours), and the base's FullController on the root declares first. Declaring it unsynced there, or in another module, makes the move local-only with no build error. Keep the base's declaration `scratch`.

## What is not proven here

The fake chop and the chop policy are measured on this rig in Av3Emulator; the client chop model, the release distance included, in-game on the production rig. The consumer half is checked statically in a Unity editor only: the composed row's slot names the consumer's socket, and each absolute binding resolves on the row the way VRCFury's resolver source reads it. Not run on the consumer half: a bake confirming `HeadProxy/MoveHead` comes out bare and synced, and an emulator session confirming the move lands `Head_Proxy` at `VoiceTarget`.

## Verifying the install

Run the wiring body with `WRITE = false` first; it must print `already wired`, and a FAIL names what is wrong.

Then play mode with Av3Emulator, avatar **at the world origin**, `EnableHeadScaling` flipped on only **after** the runtimes have run a few frames: the emulator caches exempt-bone baselines on the first chop-enabled frame, and enabling early or off origin bakes a poisoned baseline that silently no-ops the exemption or throws docked objects far off. Then, reading at a pause:

- deform `Head.lossyScale` near zero, `Head_Proxy` and `Head_NoChop` near 1, in place.
- `MoveHead` on: `Head_Proxy` lands at `VoiceTarget`, and the exempt slot and any occupant follow it. `FakeChop` entering `Chopping` at all is the proof that `IsMirror` read −1 (a hard transition condition).
- `MoveHead` off: a restore pulse returns the deform head to scale 1 before the scale constraint switches off, so it never sticks near zero for a photo.

When the voice never moves, the cause is one of these:

- **`Head_Proxy` stays home and the wiring body prints a FAIL:** the slot is empty or names the wrong object.
- **`Head_Proxy` stays home with the slot wired:** the consumer's bindings do not resolve (an armature path that differs, or a lost leading `/`), or the consumer's FullController lacks `HeadProxy/MoveHead` in `globalParams`, so its layer reads a prefixed name the Toggle never sets.
- **The move works but your own head appears over your camera:** the base's FullController lacks `HeadProxy/MoveHead` in `globalParams`, or the mirror-detect row is missing, so `FakeChop` never engages.
- **The move works for you and not for others:** another declaration of `HeadProxy/MoveHead` won unsynced (§Traps).

What the emulator cannot show: any mirror-side visual (its mirror copies every transform from your local copy each frame, `emulator.md`), the root-distance release (no capsule model, the very thing the fake chop exists for), and the in-game ordering of the client chop against animator writes. Hand those to an in-game tester, in that order.

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

    voice/HeadProxyVoice            consumer root: VRCFury FullController [HeadProxyVoice_Fx], globalParams [HeadProxy/MoveHead]; VRCFury Toggle "Move Head"
    └─ VoiceTarget                  the socket; fills Head_Proxy's empty slot on the row

    voice/HeadProxyVoiceRig         prefab variant of HeadProxyRig: HeadProxyVoice added under the root, slot 1 overridden to its VoiceTarget
