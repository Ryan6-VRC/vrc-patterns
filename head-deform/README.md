# head-deform — grab-your-face head distortion, mirror-correct (Module tier)

Grab your own cheek in first person and pull — the head stretches wide; squeeze and it squishes.
Anyone else can grab it too. A drop-in for **any stock avatar**: the deformation is head-bone
*scale* (no mesh, no blendshapes shipped), carried by a `VRCScaleConstraint` that VRCFury
retargets onto the humanoid Head at build. The interesting problems it packages are chop
problems, not skinning problems:

- **The chain stays grabbable in first person.** VRChat shrinks the humanoid head (colliders and
  physbone chains included) to ~0 locally — a face-grab gimmick collapses with it. The chain
  root carries its own `VRCHeadChop @1` self-exemption plus an always-on `VRCScaleConstraint`
  sourcing the module root, so its world scale never depends on what the chop, the exemption
  compensation, or a stripped-chop mirror clone did to its parent.
- **The stretch shows everywhere except where it must not.** The scale constraint is gated by
  `MirrorDetection/IsMirror`: OFF only on the real local copy (−1, driven — there the client's
  chop owns the bone, and a competing scale write perturbs the exemption arithmetic of anything
  docked under the head), ON in the mirror clone (+1, driven — the client strips VRCHeadChop
  there, so the full-size head must visibly stretch) and on remotes (parked default 1 — no chop
  exists there either).

**Two prefabs, one family** (variant-by-omission — `gimmicks.md` §Packaging): `HeadDeform.prefab`
for conventional rigs merges `mirror-detect` + the stretch FX; `HeadDeformProxy.prefab` (a prefab
variant) is for proxy-head rigs (`head-proxy`), where the chain anchors under the already-exempt
humanoid head — it removes the mirror-detect controller row (`IsMirror` parks at 1, scale
always-on) and the `ConstraintRetarget` (the humanoid-Head enum would hit the proxy bone, not the
deforming head).

**Provenance:** generalized from a private production avatar's face-stretch system, both variants
measured live; the mirror race is [`mirror-detect`](../mirror-detect/), the smoother is the
standard DBT exponential (`smooth-frametime`).

## Interface

- **Params:**
  - `HeadDeform/Active` (bool, in) — the enable, carried entirely by the VRCFury Toggle on the
    prefab root (`useGlobalParam`, **saved, default on, synced** — remotes must see the chain
    appear). It gates the `Cheek_Root` GO and rides *inside* the smoother tree as the input
    weight, so switching off decays the deformation to rest instead of snapping.
  - `HeadDeform/CheekBone` (physbone parameter → `_Stretch`/`_Squish`/`_IsGrabbed`) — never
    synced; the grab itself is natively synced, every client re-derives the pull locally.
  - `MirrorDetection/IsMirror` (float, consumed) — declared here with **default 1**, the variant
    switch: see `mirror-detect` §Behavior for why only the driven −1 may be special.
  - `HeadDeform/SmoothAmount` (float, default 0.9) — smoother λ, install-time tunable, unsynced.
    `HeadDeform/Smoothed` (AAP) and `One` are internal.
- **Seam:** VRCFury `FullController` on the prefab root (`basis: mount-root` ↔
  `rootBindingsApplyToAvatar: 0`); `globalParams: [HeadDeform/Active]` only — everything else
  takes instance prefixes. A VRCFury `ArmatureLink` puts `Cheek_Root` on the humanoid **Head**;
  a VRCFury `ConstraintRetarget` (conventional prefab only) points the scale constraint's target
  at the humanoid Head at build. Link and animation share the VRCFury framework; the animated
  nodes (`ScaleConstraint`, `WideTransform`) stay direct children of the module root, untouched
  by the link.
- **Dependencies:** VRCFury. Conventional prefab: a rig whose humanoid head actually chops.
  Proxy prefab: a `head-proxy`-class rig, plus one consumer wiring step — point the
  `ScaleConstraint`'s `TargetTransform` at the **deforming** head bone (a cross-prefab object
  reference is structurally a scene-level assignment; `head-proxy` §Reaching out of the prefab
  owns the mechanism and the silent-null trap).
- **Required assets:** none. Sculpted deformation (cheek bulge blendshapes, etc.) is the
  documented consumer extension: a fourth 1D subtree on `HeadDeform/Smoothed` over your own
  blendshape clips — the hook is annotated in `controller.yaml`.

## The things to know before wearing it

- **Strangers can stretch your face.** The grab filter ships `allowSelf` + `allowOthers` — being
  poked is the point, but flip `allowOthers` off on the physbone for a self-only face.
- **The stretch endpoints are feel constants** (wide 4.5/1.1/1.1, squish 0.3/1.4/1.2, squish
  deadband to −0.25, λ 0.9) — wear-tested on the production source; retune in `controller.yaml`,
  not in the built assets.
- **Your own first-person view never shows the stretch.** Not a bug: the scale is gated off on
  the real local copy by design. You see it in mirrors and cameras; everyone else sees it always.

## Verifying the install

Play mode with Av3Emulator, avatar at the world origin, `EnableHeadScaling` flipped on only
after the runtimes have run a few frames (the exempt-bone baseline cache trap — see
`head-proxy`). Then:

- Pull the chain with a real grab (the physbone re-asserts `CheekBone_Stretch` every frame, so a
  param write silently reverts; a scripted `AttemptGrab` must target a mid-chain bone — grabbing
  the leaf end bone moves nothing, measured) → `WideTransform.localScale` chases the stretch
  through `Smoothed`; the **local** copy's `ScaleConstraint.IsActive` reads **0** — that zero is the
  mirror race proving `IsMirror = −1`, the same observable `mirror-detect` names.
- The emulator's **non-local clone** is the remote leg: its `IsMirror` parks at 1 and its scale
  constraint is active. The pull itself does not transport (the emulator networks no grabs) —
  grab the *clone's* chain to see its humanoid head visibly scale.
- In first person the cheek chain holds its authored scale while the head reads ~0.0001 — the
  self-exemption landed. A chain that collapses with the head means the exemption didn't apply
  (chop component budget exceeded, or the consumer rig's head never chops).
- Wrong variant tells: the **local** copy's head scaling on the conventional prefab means the
  mirror-detect row is missing (parked at 1) — you installed the proxy behavior on a
  conventional rig.

Mirror-side visuals are in-game checks — the emulator's mirror clone copies transforms instead
of stripping VRCHeadChop (`docs/verify.md`).

## Rig

    HeadDeform                     root — VRCFury FullController [MirrorDetect_Fx + HeadDeform_Fx]
    │                              + VRCFury Toggle "Head Deform" (globalParam HeadDeform/Active,
    │                              saved, defaultOn; ObjectToggle → Cheek_Root)
    ├─ WideTransform               plain GO — the FX writes its m_LocalScale; never anchor it to
    │                              anything scaled (it is the scale *source*)
    ├─ ScaleConstraint             VRCScaleConstraint (IsActive 0 at rest, Locked), sources
    │                              [WideTransform @1, root @0] + VRCFury ConstraintRetarget → Head
    │                              (conventional prefab only)
    └─ Cheek_Root  (0, 1.145, 0)   VRCFury ArmatureLink → Head; VRCHeadChop {self @1};
       │                           VRCScaleConstraint ← root @1 (insulation, always on);
       │                           VRCPhysBone (grabbable self+others, no posing, maxStretch 6,
       │                           limit Hinge 5°/45°, radius 0.025, param HeadDeform/CheekBone)
       ├─ Left_Cheek  → Left_Cheek_End   (+0.04 x)
       └─ Right_Cheek → Right_Cheek_End  (+0.04 x)

`HeadDeformProxy.prefab` = prefab variant of the above: removes the two-row FullController and
the ConstraintRetarget, adds a one-row FullController (`HeadDeform_Fx` alone), ships the scale
constraint IsActive 1. Everything else inherits.

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; regenerate as a unit over the
committed `.meta`s — the prefabs reference the controller by GUID). The prefabs are
hand-maintained against the Rig section above.
