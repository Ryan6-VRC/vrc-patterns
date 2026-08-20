# head-deform — grab-your-face head distortion, mirror-correct (Module)

Grab your own cheek in first person and pull — the head stretches wide; squeeze and it squishes, and anyone else can grab it too. A drop-in for **any stock avatar**: the deformation is head-bone *scale* (no mesh, no blendshapes shipped), carried by a `VRCScaleConstraint` that VRCFury retargets onto the humanoid Head at build. The interesting problems it packages are chop problems, not skinning problems:

- **The chain stays grabbable in first person.** VRChat shrinks the humanoid head (colliders and physbone chains included) to ~0 locally — a face-grab gimmick collapses with it. So the chain root carries its own `VRCHeadChop @1` self-exemption plus an always-on `VRCScaleConstraint` sourcing the module root, and its world scale never depends on what the chop, the exemption compensation, or a stripped-chop mirror clone did to its parent.
- **The stretch shows everywhere except where it must not.** The scale constraint is gated by `MirrorDetection/IsMirror`: OFF only on the real local copy (−1, driven — the client's chop owns the bone there), ON in the mirror clone (+1, driven — the client strips VRCHeadChop there, runtime.md §VRCHeadChop) and on remotes (parked default 1 — no chop exists there either).

**Two prefabs, one family** (variant-by-omission — `gimmicks.md` §Packaging): `HeadDeform.prefab` for conventional rigs merges `mirror-detect` + the stretch FX; `HeadDeformProxy.prefab` (a prefab variant) is for proxy-head rigs (`head-proxy`), where the grab chain ArmatureLinks under the already-exempt humanoid head, so its own self-exemption is redundant-but-portable — no compensation exists to leak into mirrors, so it removes the mirror-detect controller row and the `ConstraintRetarget`, which on this rig would target the proxy bone rather than the deforming head.

**Provenance:** generalized from a private production avatar's face-stretch system, both variants measured live; the mirror race is [`mirror-detect`](../mirror-detect/), the smoother is the standard DBT exponential (`smooth-frametime`).

## Ground truth

- Parameters, states and clips are `controller.yaml`, whose header is the design record: the three subtrees, why `MirrorDetection/IsMirror` parks at default 1, and where the consumer hook for sculpted deformation goes. The published set is the prefab's `globalParams` — `HeadDeform/Active` alone; everything else takes instance prefixes.
- **The enable's sync and save live on the prefab, not in the controller.** A VRCFury Toggle on the root carries `HeadDeform/Active` with `useGlobalParam` and gates the `Cheek_Root` GO; the controller only reads the parameter as the smoother's input gate, inside the tree, so switching off decays the deformation to rest instead of snapping it.
- **Seam:** VRCFury `FullController` on the prefab root (`basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`). A VRCFury `ArmatureLink` puts `Cheek_Root` on the humanoid **Head**; a VRCFury `ConstraintRetarget` — conventional prefab only — points the scale constraint's target at the humanoid Head at build.
- **Dependencies:** VRCFury. The conventional prefab additionally needs a rig whose humanoid head actually chops.
- **The proxy prefab needs a `head-proxy`-class rig plus one consumer wiring step:** point the `ScaleConstraint`'s `TargetTransform` at the **deforming** head bone. A cross-prefab object reference is structurally a scene-level assignment, and it ships empty — `head-proxy` §Reaching out of the prefab owns the mechanism and the silent-null trap.
- Required assets: none.

Sculpted deformation (cheek bulge blendshapes) is the documented consumer extension — a fourth 1D subtree on `HeadDeform/Smoothed` over your own clips, the hook annotated in `controller.yaml`.

## Before you compose it

- **Strangers can stretch your face.** The grab filter ships `allowSelf` + `allowOthers` — being poked is the point, but flip `allowOthers` off on the physbone for a self-only face.
- **Your own first-person view never shows the stretch.** Not a bug: the scale is gated off on the real local copy by design — you see it in mirrors and cameras, everyone else sees it always.

## Measured

The endpoints and the feel are wear-tested constants from the production source, and each lives once at its authoring site in `controller.yaml`: the `headscale_stretch` and `headscale_squish` clips' `WideTransform` scales are the two poses, the flat rest segment in the *Wide Scale* subtree is the squish deadband (a pair of 1D thresholds, not a property of a clip — squish engages only on a firm squeeze), and `HeadDeform/SmoothAmount`'s default is the smoother λ. Retune there, never in the built assets.

## Verifying the install

Play mode with Av3Emulator, avatar at the world origin, `EnableHeadScaling` flipped on only after the runtimes have run a few frames (`head-proxy` §Verifying the install owns this exempt-bone baseline cache trap). In the built hierarchy, `Cheek_Root` is ArmatureLink-renamed: the functional node is `Original Object` under `[VF###] Cheek_Root` beneath the humanoid Head (`nondestructive.md` §Merge behaviours). Then:

- Pull the chain with a real grab — the physbone re-asserts `CheekBone_Stretch` every frame, so a param write silently reverts, and a scripted `AttemptGrab` must target a mid-chain bone since the leaf end bone moves nothing. For squish, grab with `globalPosition` at the chain root to compress inward. The **local** copy's `ScaleConstraint.IsActive` reads **0** — that zero is the mirror race proving `IsMirror = −1`, the same observable `mirror-detect` names. `IsMirror` itself reads 0 in the emulator's parameter view (AAP-class, not the driven −1) — `ScaleConstraint.IsActive` is the settlement, not the param.
- The emulator's **non-local clone** is the remote leg; grab the *clone's* chain to see its humanoid head visibly scale (the pull itself does not transport — the emulator networks no grabs).
- A cheek chain that collapses with the head means the self-exemption didn't apply — chop component budget exceeded, or the consumer rig's head never chops.
- Wrong variant tells: the **local** copy's head scaling on the conventional prefab means the mirror-detect row is missing — you installed the proxy behavior on a conventional rig.

Mirror-side visuals are in-game checks — the emulator's mirror clone copies transforms instead of stripping VRCHeadChop (runtime.md §VRCHeadChop; `docs/emulator.md`).

## Rig

    HeadDeform                     root — VRCFury FullController [MirrorDetect_Fx + HeadDeform_Fx]
    │                              + VRCFury Toggle "Head Deform" (globalParam HeadDeform/Active;
    │                              ObjectToggle → Cheek_Root)
    ├─ WideTransform               plain GO — the FX writes its m_LocalScale; never anchor it to
    │                              anything scaled (it is the scale *source*)
    ├─ ScaleConstraint             VRCScaleConstraint, Locked and off at rest — the Mirror Gate
    │                              turns it on. Sources [WideTransform, root] + VRCFury
    │                              ConstraintRetarget → Head (conventional prefab only)
    └─ Cheek_Root                  VRCFury ArmatureLink → Head; VRCHeadChop {self @1};
       │                           VRCScaleConstraint ← root (insulation, always on);
       │                           VRCPhysBone (grabbable self+others, no posing,
       │                           param HeadDeform/CheekBone)
       ├─ Left_Cheek  → Left_Cheek_End
       └─ Right_Cheek → Right_Cheek_End

`HeadDeformProxy.prefab` = prefab variant of the above: removes the two-row FullController and the ConstraintRetarget, adds a one-row FullController (`HeadDeform_Fx` alone), and ships the scale constraint on at rest. Everything else inherits.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
