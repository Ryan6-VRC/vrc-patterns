# head-proxy — map the humanoid head to a fake, keep the deforming head yours (Module, study)

**The rig requirement comes first, because everything else follows from it: the FBX needs a duplicate head bone (and duplicate eye bones), so the humanoid rig can be assigned the fakes while you keep the real deforming bones.** Unity's humanoid Head is overloaded — viewpoint anchor, voice origin, IK target, first-person chop anchor — and whoever owns that bone, you don't. Handing the humanoid mapping a non-deforming proxy buys you:

- **Ventriloquism** — move voice, viewpoint, and IK head to a socket without moving your visible head geometry (throw your voice into a puppet, a held prop, a plushie across the room).
- **Chop-free gimmick anchoring** — self-interaction gimmicks docked under the exempt humanoid head need no chop compensation at all, and no mirror detection (the compensation that leaks into mirrors is what forces it on conventional rigs — `head-deform`'s two variants are exactly this fork).
- **A deform head you can animate freely** — scale included — because the humanoid solver doesn't own it.

`HeadProxyRig.prefab` is a complete minimal avatar over an owned bare armature (`assets/HeadProxyRig.fbx` — primitives, no vendor content). Study entry: lift the rig recipe, the controller YAML, and the wiring lessons; the prefab exists to make every claim measurable.

**Provenance:** generalized from a private production avatar's head-chop architecture; client chop behavior sourced from the public VRChat docs, Av3Emulator's reimplementation (MIT), and in-game measurement on the production rig. Nothing here rests on the closed client.

## The rig

```
Neck
├─ Head            deform bone, NOT humanoid; VRCRotationConstraint ← Head_Proxy
│  ├─ (all deforming geometry: head mesh, eyes, hair…)
│  └─ Head_NoChop  empty, chop-EXEMPT docking slot — modules dock here and stay
│                  first-person-visible without spending their own VRCHeadChop
└─ Head_Proxy      humanoid Head, non-deform; VRCPositionConstraint ← [Head @1, VoiceTarget @0]
   ├─ LeftEye_Proxy / RightEye_Proxy   humanoid eyes; the real eyes rotation-constrain to them
```

One `VRCHeadChop` on `Head_Proxy` carries the whole policy: `Head_Proxy @1`, `Head @0`, `Head_NoChop @1`. The client's default chop targets the *humanoid* head — here the proxy, exempted, so the entire humanoid-head subtree is un-chopped; first-person hiding is carried entirely by the explicit `Head @0` slot on the deform bone, which the default chop would never touch. On this rig that line is load-bearing, not defensive. A base expecting many head gimmicks publishes exempt *slots* like `Head_NoChop` instead of letting every module spend one of the 16 per-avatar VRCHeadChop components.

**Blender recipe.** Duplicate the head bone **in place, in the same armature** — the duplicate becomes a Neck sibling with `use_deform` off; deform weights stay on the original, which never moves. Same for the eye bones, parented under the proxy. Unity then maps humanoid Head/LeftEye/RightEye to the duplicates. Trap: Unity's auto-mapper tends to grab a hair bone as **Jaw**; after the proxy remap that stale entry fails avatar creation with "Head_Proxy is not an ancestor of \<hair bone\>" — drop the Jaw row from `humanDescription.human`.

## Client chop model (what the exemption actually does)

An exempted bone is not "left alone" — every frame the client re-places it at `humanoidHead.position + humanoidHead.rotation × cachedOffset` and scale-compensates it against its (shrunken) parent. Consequences:

- **Everything docked in an exempt slot follows the humanoid head.** Engage ventriloquism and `Head_NoChop` + its occupants relocate to the voice target; even the `@0` deform head's *position* tracks it (the re-place runs for every listed bone, exempt or not).
- **Feedback trap:** if the humanoid head is constraint-sourced from something the chop re-places, the loop closes and its fixed point depends on evaluation order and IK mode. The discriminating property is **displacement, not exemption** — any listed bone at non-zero offset from the humanoid head re-forms the loop. This rig sources `Head_Proxy` from the listed `@0` deform head and escapes only because they are co-located. Dock position sources on a node that is not re-placed, or is co-located with the humanoid head.
- **Root-distance release gate (in-game measured, not in any doc):** the client stops chopping once a target bone is roughly **0.5–1 m from the avatar root/capsule** — eyeballed, unpinned, plausibly scale-relative. This is why ventriloquism *needs* the fake chop below: send the humanoid head to a far socket and the released chop puts your full-size deform head exactly where your camera is.

## Ventriloquism (`HeadProxy/MoveHead`) — with the vision fix built in

`Head_Proxy`'s position constraint has two sources: the deform head (home, @1) and **`VoiceTarget`** (@0). `MoveHead` swaps the weights — voice, viewpoint, and IK head move to the socket; the visible geometry stays home. And because the relocated bone set eventually crosses the release gate, **the FakeChop layer auto-engages with the move**: it reproduces the chop with avatar animation (a `VRCScaleConstraint` driven to a 0.0001-scale source — never the bone's `m_LocalScale`, which VRCFury's WD-normalization Defaults layer would fight), gated `IsLocal && IsMirror < 0` via [`mirror-detect`](../mirror-detect/), merged as its own controller row. The mirror gate is not optional — the mirror clone runs your animator with `IsLocal` still true; delete the condition to demonstrate the failure. Disengaging routes through a ≥0.25 s restore pulse so the bone never sticks at ~0 for photos; at rest the layer holds zero bindings and the real chop owns the bone. With the mirror-detect row omitted, `IsMirror` parks at 0 and the fake chop never engages — the fail-safe direction (a possible vision block, never a wrong mirror).

## Reaching out of the prefab — the socket, and why it ships wired

`VoiceTarget` is a plain child of the avatar root, **wired as source1 in the same prefab as the constraint**. That placement is the lesson: a constraint-source object reference has no string-addressed form, so a reference that crosses a prefab boundary can only live as a scene-level override — and a scene copy silently loses it. The failure is silent by SDK behavior: a *weighted null source* is simply excluded from the solve, so the constraint no-ops and ventriloquism just stops moving the head, with nothing visibly broken (re-measure in the emulator: drive weight onto an unassigned source — the bone behaves as unconstrained).

So: the socket ships in-prefab, and **"point the socket at your gimmick" is the one consumer step** — re-source or constrain `VoiceTarget` to whatever should speak (a doll's head, a carried prop). When a module must reach the avatar across a prefab boundary, prefer the string-addressed seams — VRCFury's nearest-match binding rebase (a module-mounted FullController can bind avatar-armature paths), ArmatureLink bone/offset-path addressing, shadow-skeleton merges — and treat any unavoidable object reference as an explicit, documented install step whose presence the install check asserts.

## Composing head-deform on this rig

`head-deform`'s proxy variant (`HeadDeformProxy.prefab`) is the worked composition: the grab chain ArmatureLinks under the (exempt) humanoid head, so its self-exemption is redundant-but- portable, the mirror-detect row is omitted (`IsMirror` parks at 1 = scale always on — no compensation exists to leak into mirrors), and the consumer points its scale constraint's `TargetTransform` at the **deform** head — the humanoid-Head enum retarget would hit the proxy.

## Interface

- **Params:** `HeadProxy/MoveHead` (bool, in) — synced, unsaved: ventriloquism is remotely visible. `MirrorDetection/IsMirror` (float, consumed from the mirror-detect row; declared default 0 = fail-safe park).
- **Seam:** VRCFury `FullController` on the avatar root (`basis: avatar-root`) with two rows — `built/HeadProxy_Fx.controller` + `mirror-detect`'s `built/MirrorDetect_Fx.controller` — and a Toggle fronting `MoveHead` via `globalParams`. `FixWriteDefaults` ships alongside. This entry *is* an avatar, not a mergeable — composing its ideas onto another avatar means rebuilding the rig per the Blender recipe, not dropping the prefab.
- **Dependencies:** VRCFury.
- **Required assets:** `assets/HeadProxyRig.fbx` — owned bare armature, primitives only.

## Verifying the install

Play mode with Av3Emulator, avatar **at the world origin**, `EnableHeadScaling` flipped on only **after** the runtimes have run a few frames — the emulator caches exempt-bone baselines on the first chop-enabled frame; enabling early (or off origin) bakes a poisoned baseline and the exemption silently no-ops or throws docked objects hundreds of meters (that cache trap, not this entry, is the usual "it broke"). Then, reading at a pause:

- deform `Head.lossyScale` ≈ 0.0001, `Head_Proxy` ≈ 1, `Head_NoChop` ≈ 1, in place.
- `MoveHead` on → `Head_Proxy` lands at `VoiceTarget`; the exempt slot (+ any occupant) follows it — the head-anchored re-place, observed directly. `Chopping` engaging at all is the `IsMirror = −1` proof (hard transition condition).
- `MoveHead` off → the restore pulse returns the deform head to scale 1, then the constraint deactivates at rest weights.

What the emulator structurally cannot show: **any mirror-side visual** (its clones copy transforms instead of stripping VRCHeadChop), the **root-distance release gate** (no capsule model — the very thing the fake chop exists for), and in-game ordering of client chop vs animator writes. Hand those to an in-game tester, in that order.

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it and mirror-detect's controller by GUID — regenerate `built/` as a unit over the committed `.meta`s). The prefab is hand-maintained against the Rig section; the FBX regenerates from the Blender recipe above (primitives, exact bone names).
