# anti-cull — bounds-inflation view-cull defeat (Module)

Keeps the avatar's **animator evaluating** on every remote client. The mesh rendering is not the point — a view-culled avatar has its animator *suspended*, which freezes any gimmick that holds state through continuously replayed choreography (a dropped prop, a contact tracker). Inflating the renderer bounds with a hidden 10 000-unit cube makes the combined bounds intersect every camera frustum, so **view (frustum) culling never skips the avatar** and its animator keeps running. Defeats view culling *only* — distance culling ("Hide Avatars Beyond" / closest-N) is a client-side unload nothing can defeat. Module total: **1 synced bit** (`AntiCull/Enable`).

**The cost is the mechanism, not a side effect.** Anti-cull works by making the avatar expensive for other people's clients: every remote client skins and draws it at all times, overriding the view-culling protection those clients would otherwise apply. Compose it deliberately, and only once per avatar.

**Provenance:** generalized from a private production avatar's anti-cull (VRLabs ancestry — VRLabs ships this mechanism *inside* its contact-tracker prefabs because trackers are unreliable without it; it was split out to share one instance across gimmicks). Mechanism verbatim — cube, constraint values, layer — and in-game efficacy is carried by the source's production history across every avatar it ships on. Abstracted away: the source is permanently on (no parameters, no menu; its disable clip sat unwired on disk); the toggle is this entry's addition, and the material and world-anchor asset are freshly authored.

## Interface

- **Params:** `AntiCull/Enable` (bool, in) — synced, **unsaved**, **default ON**. The menu front (VRCFury Toggle on the prefab root, `defaultOn`) drives it. Default-on + unsaved is load-bearing: the controller's default state inflates on the animator's first frame, so the avatar can never spawn already-culled with the toggle out of reach, and an off state never persists into a fresh load. Turning it off is a per-session choice.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0`), so both clip bindings resolve **prop-root relative** (`basis: mount-root`). Pure VRCFury — no MA half. `AntiCull/Enable` is exported via `globalParams`; the Toggle drives it by name.
- **Dependencies:** none beyond the VRC SDK + VRCFury. Drop the prefab anywhere under the avatar.
- **Required assets:** none — self-contained (`assets/World.prefab`, `assets/AntiCull.mat`).

## When a module needs this

A remote client that culls the avatar stops evaluating its animator (`runtime.md` §Culling). Any module that maintains state through **continuously replayed choreography** — constraint sample-and-hold, contact tracking — silently diverges while culled: synced params keep arriving, but the local replay that turns them into state does not run. Compose anti-cull alongside any module that (a) must hold sync continuously rather than just resync on late-join, and (b) can carry state while the avatar is out of view — a dropped prop (`grab-prop`), a tracked contact chain (`contact-tracker`), a prop parented to another player (`drop-on-player`). One instance covers the whole avatar; never stack one per module.

## How it works

Two problems pull the design in opposite directions: VRChat's upload validation rejects an avatar whose bounding box is huge, but a cull-defeating renderer must be huge from the first frame it exists on a remote client — if the avatar could load small and *then* wait for an enable, a client that culled it immediately would never run the animator that enables it.

The resolution is that the serialized state and the runtime state differ:

- **As serialized** (what upload validation measures): `Culling` is inactive, scaled `(0,0,0)`, constraint `GlobalWeight 0`. It contributes nothing to the avatar's bounds.
- **At runtime**: the merged FX layer's default state `Enabled` plays unconditionally from the animator's first frame — part of avatar initialization itself — setting `m_IsActive → 1` and `GlobalWeight → 1`. The VRC Scale Constraint blends from rest `(0,0,0)` to source × offset = **10 000 world units**.

The constraint's one source is the transform inside `assets/World.prefab` — a prefab asset that is **never instantiated**, which a VRC constraint resolves as world origin on every client (`runtime.md` §Constraints; the same trick that anchors world-drop gimmicks). For a *scale* constraint what matters is the source's scale, `(1,1,1)`: the cube's size is fixed in **world** units, independent of avatar scale — shrink the avatar and the envelope doesn't shrink with it. That, plus keeping the serialized rest scale at zero, is what the constraint buys over animating `m_LocalScale` directly. (Known caveat, inherited: remote distance-culling can displace such an origin between hide/shows — `runtime.md`.)

Nobody sees the cube: everyone is *inside* it, and a cube viewed from inside is entirely backface-culled — zero visible geometry, shadows off, no overdraw. The material is an opaque white VRChat Mobile StandardLite (SDK-shipped shader, Quest-safe); nothing about it is special — invisibility comes from the geometry, not the shader.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place.

    AntiCull                 root — VRCFury FullController (FX, rootBindingsApplyToAvatar: 0)
    │                        + VRCFury Toggle "AntiCull" (defaultOn, drives AntiCull/Enable)
    └─ Culling               INACTIVE, scale (0,0,0), layer 12 — the serialized-small half
         MeshFilter          built-in Cube
         MeshRenderer        shadows off, assets/AntiCull.mat
         VRCScaleConstraint  IsActive 1, ScaleAtRest (0,0,0), ScaleOffset (10000, 10000, 10000),
                             GlobalWeight 0, Locked; source0 = assets/World.prefab's
                             transform, weight 1 (never instantiated → world origin)

Layer 12 is inherited from the source verbatim and unverified as load-bearing — kept because the source's production history covers this exact configuration, not a normalized one.

Editing-the-rig trap: a freshly script-added VRC constraint starts with `IsActive` **false** (measured: the animator drives `GlobalWeight` to 1 and the scale still reads rest, no error), so a rebuild that skips the field silently never solves. Serialized `IsActive: 1` is load-bearing.

## Verifying the install

Nothing to drive — the default path inflates with zero input. In play, the `Culling` object should sit at kilometre scale and the renderer's bounds with it; toggled off, the renderer deactivates and contributes no bounds at all, since the GameObject-active write is the effective gate rather than the constraint (which just holds its last transform). Serialized rest state must stay inactive and zero-scale — that half is what keeps the uploaded bounds honest.

That inflated bounds actually defeat a remote client's view culling is in-game-only: the emulator cannot reproduce another client's culling decision (`docs/verify.md`).

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID — recompile is GUID-stable). The prefab is hand-maintained against the Rig section above.
