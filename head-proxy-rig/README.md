# head-proxy-rig — proxy-head rig: chop inversion, ventriloquism, mirror-gated fake chop (study, prefab-shipping)

A working reconstruction of the **proxy-head architecture**: the humanoid Head (and eyes) are
mapped to non-deforming *proxy* bones, the real deforming head sits outside the humanoid rig,
and VRCHeadChop policy + constraints wire the two together. `HeadProxyRig.prefab` is a complete
demo avatar (Felis-derived — `assets/NOTICE`, VN3); everything below is measured on it or
sourced as labeled. Study entry: lift the ideas and the controller YAML, not the prefab.

**Provenance:** generalized from a private production avatar's head-chop architecture. Mirror
detection is the standard parameter-driver race (VRLabs-lineage). Client chop behavior is
sourced from the public VRChat docs, Av3Emulator's reimplementation (MIT), and in-game
measurement on the production rig; nothing here rests on the closed client.

## The rig

```
Neck
├─ Head            deform bone, NOT humanoid; VRCRotationConstraint ← Head_Proxy
│  ├─ (hair, ears, eyes… — all deforming geometry)
│  └─ Head_NoChop  empty, chop-EXEMPT docking slot (+ SlotPayload demo occupant)
└─ Head_Proxy      humanoid Head, non-deform; VRCPositionConstraint ← Head @1, VoiceTarget @0
   ├─ Eye_Proxy.L/R  humanoid eyes; real eyes rotation-constrain to them
```

One `VRCHeadChop` on `Head_Proxy` carries the whole policy: `Head_Proxy @1`, `Head @0`,
`Head_NoChop @1`.

**The inversion this buys.** The client's default chop targets the *humanoid* head — here the
proxy, exempted at @1, so the entire humanoid-head subtree is un-chopped. First-person hiding
is carried **entirely by the explicit `Head @0` slot** on the deform bone, which the default
chop would never touch (it's outside the humanoid rig). On this rig that line is load-bearing,
not defensive.

**Why build this.** The humanoid head bone is overloaded: viewpoint anchor, voice origin, IK
target, chop anchor. Splitting it from the deforming head lets you (a) move voice/viewpoint
without moving geometry — ventriloquism, below; (b) anchor self-interaction gimmicks (grabbable
cheeks, self-pat receivers) under an exempt humanoid head so they need **no chop compensation
at all** — a gimmick built for a conventional rig must scale-compensate its chopped parent, and
that compensation leaks into mirrors (where the client strips VRCHeadChop), which is why the
conventional variant of such a gimmick needs mirror detection and the proxy-rig variant of the
same gimmick doesn't; (c) animate the deform head freely (scale included) since the humanoid
solver doesn't own it.

**Blender side.** Duplicate the head bone in-place in the same armature — the duplicate becomes
a Neck sibling, `use_deform` off, deform weights stay on the original; same for the eye bones,
parented under the proxy. Unity then maps humanoid Head/LeftEye/RightEye to the duplicates.
Trap: Unity's auto-mapper tends to grab a hair bone as **Jaw**; after the proxy remap that
stale entry fails avatar creation with "Head_Proxy is not an ancestor of \<hair bone\>" — drop
the Jaw row from `humanDescription.human`.

## Client chop model (what the exemption actually does)

An exempted bone is not "left alone" — every frame the client re-places it at
`humanoidHead.position + humanoidHead.rotation × cachedOffset` and scale-compensates it against
its (shrunken) parent. Consequences, all measured on this prefab in the emulator and consistent
with in-game behavior of the production rig:

- **Everything docked in an exempt slot follows the humanoid head.** Engage ventriloquism and
  `Head_NoChop` + its occupant relocate to the voice target; even the `@0` deform head's
  *position* tracks it (the re-place runs for every listed bone, exempt or not).
- **Feedback trap:** if the humanoid head is constraint-sourced from something docked in an
  exempt slot, the re-place closes a loop whose fixed point depends on evaluation order and IK
  mode. Dock position sources on non-exempt nodes.
- **Root-distance release gate (in-game measured, not in any doc):** the client stops chopping
  a target bone once it's roughly **0.5–1 m from the avatar root/capsule** — eyeballed,
  unpinned, plausibly scale-relative. This is why ventriloquism in a tracking mode where the
  capsule follows the (relocated) humanoid head releases the chop and your own mesh blocks the
  camera. To pin it: walk the target outward in steps, at two clearly different avatar heights
  (if the release distance moves with height, it's a `ScaleFactor` multiple, not meters).

## Head-distortion gimmicks (the face-stretch class)

The same mechanics govern any interactive head distortion — grabbable cheeks, squishable face,
self-pat receivers. The chop scales the whole head subtree, **colliders and physbone chains
included**: a face-stretch chain parented under a chopped head collapses to ~0 in first person
and you can't grab your own face — which is the entire gimmick. So:

- **Self-exempt the chain root** (`VRCHeadChop @1` targeting its own root — the mechanism
  `headchop-mount` packages) to keep it grabbable in first person. The distortion itself
  (bone scale/position driven by the physbone, or blendshapes) needs nothing further.
- **On a conventional rig, the exempt chain additionally needs a mirror-side scale
  compensation**: the exemption's scale-correction against the chopped parent is written into
  real transforms, and the mirror clone — where the client *strips* VRCHeadChop, leaving the
  parent unchopped — inherits it as visible distortion. The fix is a `VRCScaleConstraint`
  reading the chopped bone, `IsActive`-gated by mirror detection at the **opposite polarity
  from the fake chop: active in the mirror (`IsMirror > 0`), off on the real local copy.**
  Getting that polarity backwards is the natural mistake — the fake chop protects the mirror
  *from* an effect, the compensation applies an effect *only in* the mirror.
- **On this proxy rig, none of that is needed**: the chain anchors to the exempt humanoid head
  (`Head_Proxy`), whose scale never actually shrinks, so no compensation is written and there
  is nothing to leak into mirrors. Deleting the mirror-detection dependency is the concrete
  payoff of the inversion.

## Ventriloquism (`HeadProxy/MoveHead`)

`Head_Proxy`'s position constraint has two sources: the deform head (home, @1) and
`VoiceTarget` (@0). The `VoiceProjection` layer swaps the weights — voice, viewpoint, and IK
head move to the socket; the deforming head never moves. The socket is a plain child of the
avatar root: re-source it (or constrain it) to whatever should speak.

## Fake chop (`HeadProxy/FakeChop`) — for when the real chop releases

Reproduces the chop with avatar animation, gated `IsLocal && IsMirror < 0`. Two decisions are
load-bearing:

- **Drive a `VRCScaleConstraint`'s `IsActive`** (sources: a scale-0.0001 GO and a scale-1 GO),
  **never the bone's `m_LocalScale` directly.** Constraints apply after the animator, so
  nothing races the client's own chop of the same bone — and keeping `m_LocalScale` out of
  every clip keeps it out of VRCFury's WD-normalization Defaults layer, which otherwise writes
  scale-1 to the bone on every idle frame (measured defeating the emulator's chop; in-game
  ordering against the client's write is exactly the fight you don't want to depend on).
- **The mirror gate is not optional.** The mirror clone runs your animator with your parameter
  values and `IsLocal` is true there too — an `IsLocal`-only fake chop shrinks your head in
  every mirror and photo. `IsMirror < 0` (strictly: the driver-race value for "real local
  copy") is the only correct gate. Delete the condition to demonstrate the failure.

Disengaging routes through `Restoring` — a ≥0.25 s pulse on the scale-1 source — so the bone
doesn't stay stuck at ~0 for photos; Idle then holds **zero bindings** and the real chop owns
the bone at rest.

## Mirror detection (`MirrorDetection` layer) — the driver race

`Init` forks on `IsLocal`; the local branch forks on `DetectMirror` (default false). The real
local copy evaluates first: `DetectMirror` still false → `NotMirror` writes `IsMirror = -1` and
a `localOnly` driver sets `DetectMirror = 1`. The mirror clone instantiates later **with copied
parameter values** and no driver execution — it forks straight to `Mirror`, `IsMirror = +1`.
Remotes park at 0. Three-valued, zero synced bits, no scene objects. The layer is
self-contained — lift it whole.

## Interface

- **Params:** `HeadProxy/MoveHead`, `HeadProxy/FakeChop` (bool, in) — synced, unsaved.
  `MirrorDetection/DetectMirror` (bool) and `MirrorDetection/IsMirror` (float AAP, -1/0/+1) are
  internal — never synced, never menu-exposed.
- **Seam:** VRCFury `FullController` on the avatar root itself (`basis: avatar-root` — clip
  paths bind from the root); the two menu Toggles (`useGlobalParam`) front `MoveHead` and
  `FakeChop`, and both ride `globalParams`. `FixWriteDefaults` ships alongside. This entry *is*
  an avatar, not a mergeable — composing its ideas onto another avatar means rebuilding the
  rig, not dropping the prefab.
- **Dependencies:** VRCFury. The demo FBX ships in `assets/` (VN3 — see `NOTICE`).

## Verifying the install

Play mode with Av3Emulator, avatar **at the world origin**, and flip the control's
`EnableHeadScaling` on only **after** the runtimes have run a few frames: the emulator caches
exempt-bone baselines on the first chop-enabled frame, so enabling early (or off origin) bakes
a poisoned baseline — the exemption silently no-ops or throws docked objects hundreds of
meters (that is the cache trap, not this entry breaking). Then, reading at a pause (frame
boundary — mid-frame reads race the chop pass):

- deform `Head.lossyScale` ≈ 0.0001, `Head_Proxy` ≈ 1, `Head_NoChop` ≈ 1 (compensated through
  the chopped parent), `SlotPayload` at its authored scale, in place.
- `MoveHead` on → `Head_Proxy` at `VoiceTarget`, and the exempt slot (+ occupant) follows it.
- `FakeChop` on (with `EnableHeadScaling` off, simulating the released gate) → deform head
  ≈ 0.0001 via the constraint; off → `Restoring` pulse returns it to 1 and the constraint
  deactivates. That `Chopping` engages at all is the `IsMirror = -1` proof — it's a hard
  transition condition.

What the emulator structurally cannot show for this entry: **any mirror-side visual** (its
clones copy the local copy's transforms instead of stripping VRCHeadChop — mirror correctness
of the fake chop is an in-game check), the **root-distance release gate** (no capsule model),
and the in-game ordering of client chop vs animator writes. Hand those three to an in-game
tester, in that order.
