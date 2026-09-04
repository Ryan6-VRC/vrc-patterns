# head-proxy — map the humanoid head to a fake, keep the deforming head yours (Module, study)

**The rig requirement comes first: the FBX needs a duplicate head bone, and duplicate eye bones.** Unity's humanoid Head is overloaded — voice origin, IK target, first-person chop anchor — and whoever owns that bone, you don't. Handing the humanoid mapping a non-deforming proxy buys ventriloquism (move your voice origin and IK head to a socket without moving your visible head geometry), chop-free gimmick anchoring (self-interaction gimmicks docked under the exempt humanoid head need no chop compensation or mirror detection — `head-deform`'s `HeadDeformProxy.prefab` is the worked composition on this rig), and a deform head you can animate freely, scale included, because the humanoid solver doesn't own it.

`HeadProxyRig.prefab` is a complete minimal avatar over an owned bare armature — lift the rig recipe, the controller YAML, and the wiring lessons.

**Provenance:** generalized from a private production avatar's head-chop architecture; client chop behavior sourced from the public VRChat docs, Av3Emulator's reimplementation (MIT), and in-game measurement on the production rig.

## The rig

```
Neck
├─ Head            deform bone, NOT humanoid; VRCRotationConstraint ← Head_Proxy
│  ├─ (all deforming geometry: head mesh, eyes, hair…)
│  └─ Head_NoChop  empty, chop-EXEMPT docking slot: modules dock here and stay first-person-visible
└─ Head_Proxy      humanoid Head, non-deform; VRCPositionConstraint ← [Head @1, VoiceTarget @0]
   ├─ LeftEye_Proxy / RightEye_Proxy   humanoid eyes; the real eyes rotation-constrain to them
```

One `VRCHeadChop` on `Head_Proxy` carries the whole policy: `Head_Proxy @1`, `Head @0`, `Head_NoChop @1` — the client's default chop targets the humanoid head (here, the exempted proxy), so first-person hiding runs entirely through the explicit `Head @0` slot. A base expecting many head gimmicks publishes exempt *slots* like `Head_NoChop` instead of spending one of the 16 per-avatar VRCHeadChop components per module.

**Blender recipe.** Duplicate the head bone and eye bones **in place, in the same armature** — the duplicates become Neck siblings with `use_deform` off (deform weights stay on the originals, which never move), the eye duplicates parented under the proxy; Unity then maps humanoid Head/LeftEye/RightEye to them. Trap: Unity's auto-mapper tends to grab a hair bone as **Jaw**; after the proxy remap that stale entry fails avatar creation with "Head_Proxy is not an ancestor of \<hair bone\>" — drop the Jaw row from `humanDescription.human`.

## Client chop model

Three rules govern anything docked in an exempt slot:

- **An exempt bone still follows the humanoid head.** Engage ventriloquism and `Head_NoChop` and its occupants relocate to the voice target; even the `@0` deform head's *position* tracks it.
- **Do not source the humanoid head from anything the chop re-places, unless the two are co-located.** This rig sources `Head_Proxy` from the listed `@0` deform head and escapes only because they are co-located.
- **The chop releases once a target bone is roughly 0.5–1 m from the avatar root or capsule.** This is why the fake chop below exists: it reproduces the chop so a far-relocated voice target doesn't leave your full-size deform head sitting exactly where your camera is.

## Ventriloquism (`HeadProxy/MoveHead`) — with the vision fix built in

`MoveHead` swaps the weights of `Head_Proxy`'s position constraint — the voice origin and IK head move to `VoiceTarget`; the visible geometry stays home. Your **viewpoint and hearing do not follow**: both are locked to your VR headset, and animating the head bone never moves the camera — only the voice's *source* relocates. Because the relocated bone set eventually crosses the release gate, **the FakeChop layer auto-engages with the move**: it reproduces the chop with avatar animation (a `VRCScaleConstraint` driven to a near-zero-scale source, never the bone's `m_LocalScale` directly), gated `IsLocal && IsMirror < 0` via [`mirror-detect`](../mirror-detect/). The mirror gate is not optional — the mirror clone runs your animator with `IsLocal` still true; delete the condition to demonstrate the failure. With the mirror-detect row omitted, `IsMirror` parks at 0 and the fake chop never engages — the fail-safe direction, a possible vision block rather than a wrong mirror.

## Reaching out of the prefab — the socket, and why it ships wired

`VoiceTarget` is a plain child of the avatar root, **wired as source1 in the same prefab as the constraint**. That placement is the lesson: a constraint-source object reference has no string-addressed form, so a reference that crosses a prefab boundary can only live as a scene-level override — and a scene copy silently loses it. The failure is silent by SDK behavior: a *weighted null source* is simply excluded from the solve, so the constraint no-ops and ventriloquism just stops moving the head, with nothing visibly broken.

So: the socket ships in-prefab, and **"point the socket at your gimmick" is the one consumer step** — re-source or constrain `VoiceTarget` to whatever should speak (a doll's head).

## Interface

- **Seam:** a VRCFury `FullController` on the avatar root (`basis: avatar-root`) with two rows — `HeadProxy_Fx` + `mirror-detect`'s `MirrorDetect_Fx` — a Toggle fronting `MoveHead` via `globalParams`, plus `FixWriteDefaults`. This entry *is* an avatar, not a mergeable — composing its ideas means rebuilding the rig per the Blender recipe, not dropping the prefab.
- **Dependencies:** VRCFury.
- **Required assets:** `assets/HeadProxyRig.fbx` — owned bare armature, primitives only, no vendor content.

## Verifying the install

Play mode with Av3Emulator, avatar **at the world origin**, `EnableHeadScaling` flipped on only **after** the runtimes have run a few frames — the emulator caches exempt-bone baselines on the first chop-enabled frame, and enabling early (or off origin) bakes a poisoned baseline that silently no-ops the exemption or throws docked objects hundreds of meters. Then, reading at a pause:

- deform `Head.lossyScale` ≈ 0.0001, `Head_Proxy` ≈ 1, `Head_NoChop` ≈ 1, in place.
- `MoveHead` on → `Head_Proxy` lands at `VoiceTarget`; the exempt slot (+ any occupant) follows it — the head-anchored re-place, observed directly. `Chopping` engaging at all is the `IsMirror = −1` proof (hard transition condition).
- `MoveHead` off → a restore pulse (the `chop_constraint_restore` clip's length, floored by low-FPS sampling) returns the deform head to scale 1 before the constraint deactivates at rest weights, so it never sticks at ~0 for a photo.

What the emulator structurally cannot show: **any mirror-side visual** (its clones copy transforms instead of stripping VRCHeadChop — runtime.md §VRCHeadChop), the **root-distance release gate** (no capsule model — the very thing the fake chop exists for), and in-game ordering of client chop vs animator writes. Hand those to an in-game tester, in that order.

## Rebuilding

The FBX regenerates from the Blender recipe above (primitives, exact bone names).
