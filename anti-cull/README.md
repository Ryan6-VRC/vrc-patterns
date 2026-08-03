# anti-cull — bounds-inflation view-cull defeat (Module)

Keeps the avatar's **animator evaluating** on every remote client — the mesh rendering is not the point. Inflating the renderer bounds with a hidden 10 000-unit cube makes the combined bounds intersect every camera frustum, so **view (frustum) culling never skips the avatar** and its animator keeps running. Defeats view culling *only* — distance culling ("Hide Avatars Beyond" / closest-N) is a client-side unload nothing can defeat; module total **1 synced bit** (`AntiCull/Enable`).

**The cost is the mechanism, not a side effect.** Anti-cull works by making the avatar expensive for other people's clients: every remote client skins and draws it at all times, overriding the view-culling protection those clients would otherwise apply. Compose it deliberately, and only once per avatar.

**Provenance:** generalized from a private production avatar's anti-cull (VRLabs ancestry). Mechanism — cube, constraint values, layer — verbatim; the toggle, material, and world-anchor asset are this entry's own.

## Interface

- **Params:** `AntiCull/Enable` (bool, in) — synced, **unsaved**, **default ON**. The menu front (VRCFury Toggle on the prefab root, `defaultOn`) drives it. Default-on + unsaved is load-bearing: the avatar can never spawn already-culled with the toggle out of reach, and an off state never persists into a fresh load — turning it off is a per-session choice.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0`), so both clip bindings resolve **prop-root relative** (`basis: mount-root`). Pure VRCFury — no MA half. `AntiCull/Enable` is exported via `globalParams`; the Toggle drives it by name.
- **Dependencies:** none beyond the VRC SDK + VRCFury. Drop the prefab anywhere under the avatar.
- **Required assets:** none — self-contained (`assets/World.prefab`, `assets/AntiCull.mat`).

## When a module needs this

A remote client that culls the avatar stops evaluating its animator (`runtime.md` §Culling), so a module that maintains state through **continuously replayed choreography** — constraint sample-and-hold, contact tracking — silently diverges while culled: synced params keep arriving, but the local replay that turns them into state does not run. Compose anti-cull alongside any module that must hold sync continuously rather than just resync on late-join, and can carry state while out of view — a dropped prop (`grab-prop`), a tracked contact chain (`contact-tracker`), a prop parented to another player (`drop-on-player`). One instance covers the whole avatar; never stack one per module.

## How it works

The serialized state and the runtime state differ, which is why upload validation passes despite the runtime bounds being enormous:

- **As serialized** (what upload validation measures): `Culling` is inactive, scaled `(0,0,0)`, constraint `GlobalWeight 0`. It contributes nothing to the avatar's bounds.
- **At runtime**: the merged FX layer's default state `Enabled` plays unconditionally from the animator's first frame — part of avatar initialization itself — setting `m_IsActive → 1` and `GlobalWeight → 1`. The VRC Scale Constraint blends from rest `(0,0,0)` to source × offset = **10 000 world units**.

The constraint's one source is the transform inside `assets/World.prefab` — a prefab asset that is **never instantiated**, which a VRC constraint resolves as world origin on every client (`runtime.md` §Constraints; the same trick that anchors world-drop gimmicks). The cube's size is fixed in **world** units via the source's scale `(1,1,1)`, independent of avatar scale — shrink the avatar and the envelope doesn't shrink with it.

Nobody sees the cube: everyone is *inside* it, and a cube viewed from inside is entirely backface-culled. The material is an opaque white VRChat Mobile StandardLite (SDK-shipped shader, Quest-safe); invisibility comes from the geometry, not the shader.

## Rig

    AntiCull                 root — VRCFury FullController (FX, rootBindingsApplyToAvatar: 0)
    │                        + VRCFury Toggle "AntiCull" (defaultOn, drives AntiCull/Enable)
    └─ Culling               INACTIVE, scale (0,0,0), layer 12 — the serialized-small half
         MeshFilter          built-in Cube
         MeshRenderer        shadows off, assets/AntiCull.mat
         VRCScaleConstraint  IsActive 1, ScaleAtRest (0,0,0), ScaleOffset (10000, 10000, 10000),
                             GlobalWeight 0, Locked; source0 = assets/World.prefab's
                             transform, weight 1 (never instantiated → world origin)

Layer 12 is inherited from the source verbatim and unverified as load-bearing — kept because the source's production history covers this exact configuration, not a normalized one.

Editing-the-rig trap: a freshly script-added VRC constraint starts with `IsActive` **false** (`runtime.md` §Constraints), so a rebuild that skips the field silently never solves — the serialized `IsActive: 1` is load-bearing.

## Verifying the install

Nothing to drive — the default path inflates with zero input. In play, the `Culling` object should sit at kilometre scale and the renderer's bounds with it; toggled off, the renderer deactivates and contributes no bounds at all, since the GameObject-active write is the effective gate rather than the constraint (which just holds its last transform). Serialized rest state must stay inactive and zero-scale.

That inflated bounds actually defeat a remote client's view culling is in-game-only: the emulator cannot reproduce another client's culling decision (`docs/verify.md`).

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
