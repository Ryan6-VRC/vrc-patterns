# anti-cull — bounds-inflation view-cull defeat (Module)

Keeps the avatar's **animator evaluating** on every remote client — the mesh rendering is not the point. A hidden oversized cube inflates the renderer bounds so the combined bounds intersect every camera frustum, so **view (frustum) culling never skips the avatar** and its animator keeps running. Defeats view culling *only*: distance culling ("Hide Avatars Beyond" / closest-N) is a client-side unload nothing can defeat. Module total **1 synced bit** (`AntiCull/Enable`).

**The cost is the mechanism, not a side effect.** Anti-cull makes the avatar expensive for other people's clients: every remote client skins and draws it at all times, overriding the view-culling protection those clients would otherwise apply. Compose it deliberately, and only once per avatar.

**Provenance:** generalized from a private production avatar's anti-cull (VRLabs ancestry). Mechanism — cube, constraint values, layer — verbatim; the toggle, material, and world-anchor asset are this entry's own.

## Ground truth

A VRCFury `Toggle` (`defaultOn`) is the menu front. Default-on + unsaved is load-bearing: the avatar can never spawn already-culled with the toggle out of reach, and an off state never persists into a fresh load — turning it off is a per-session choice. Seam: VRCFury `FullController` (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`), pure VRCFury with no MA half; self-contained (`assets/World.prefab`, `assets/AntiCull.mat`). Drop the prefab anywhere under the avatar.

The serialized and runtime states differ, which is why upload validation passes despite an enormous runtime envelope: as serialized the `Culling` child is inactive, its scale and its constraint's `GlobalWeight` both zero, contributing nothing to bounds. At runtime the merged FX default state plays from the animator's first frame — part of initialization — raising `m_IsActive` and `GlobalWeight`, and the VRC Scale Constraint blends from its rest scale to source × the constraint's `ScaleOffset`. That source is the transform inside `assets/World.prefab`, a prefab asset **never instantiated**, which a VRC constraint resolves as world origin on every client (`runtime.md` §Constraints). Its scale fixes the cube in **world** units independent of avatar scale — shrink the avatar and the envelope does not shrink with it. Nobody sees the cube: everyone is *inside* it and a cube viewed from inside is backface-culled; the material is opaque white VRChat Mobile StandardLite (SDK-shipped, Quest-safe), so invisibility comes from the geometry, not the shader.

## Traps

- **When a module needs this:** a culled remote client stops evaluating the avatar's animator (`runtime.md` §Culling), so a module holding state through **continuously replayed choreography** — constraint sample-and-hold, contact tracking — silently diverges while culled: synced params keep arriving, but the local replay that turns them into state does not run. Compose anti-cull alongside any module that must hold sync continuously (not just resync on late-join) and can carry state out of view — `grab-prop`, `contact-tracker`, `box-tracker`, `drop-on-player`. One instance covers the whole avatar; never stack one per module.
- **Layer 12** is inherited from the source verbatim and unverified as load-bearing — kept because the source's production history covers this exact configuration, not a normalized one.
- **Editing the rig:** a freshly script-added VRC constraint starts with `IsActive` **false** (`runtime.md` §Constraints), so a rebuild that skips the field silently never solves — the serialized `IsActive: 1` is load-bearing.

## Verifying the install

Nothing to drive — the default path inflates with zero input. In play, the `Culling` object should sit at kilometre scale and the renderer's bounds with it; toggled off, the renderer deactivates and contributes no bounds at all, since the GameObject-active write is the effective gate rather than the constraint (which just holds its last transform). Serialized rest state must stay inactive and zero-scale. That inflated bounds actually defeat a remote client's view culling is in-game-only: the emulator cannot reproduce another client's culling decision (`docs/emulator.md`).
