# debug-display (Structural Module)

A numeric readout that floats in world space on any mesh you drop it on, printing up to twelve labelled values at once — animator floats you drive from a clip, alongside render-side facts an animator cannot reach: world position, camera distance, the observing client's frame rate. Text is MSDF glyphs rasterized in the fragment stage against a virtual plane, so the numbers parallax behind the mesh's silhouette rather than sitting on its surface. Labels are author-time and cost nothing at runtime; the whole entry syncs 0 bits.

Three display modes — camera-facing billboard, fixed to the object's own axes, or mapped onto the mesh's UVs — crossed independently with per-entry value sources, so one material mixes a world coordinate, a frame rate and an animator float in one grid.

## Provenance

Derived from [`lereldarion/unity-shaders`](https://github.com/lereldarion/unity-shaders) (MIT, © 2025 Lereldarion), ancestor `Shaders/Overlay_HUD.shader`. Generalized from a private project's coordinate-readout shader, which was itself a hand copy of that ancestor carrying no attribution — restoring the credit is part of what this entry is for.

**Upstream's, kept:** the `Font` metric ratios and the monospace fixed-cell scheme, `median()`, `compute_screenspace_scale_of_uv` and `sdf_blend_with_aa`, and the central idea — a fragment-stage ray-trace against a virtual plane through the object origin, with `Cull Back` making the silhouette a window. The `*_em` metrics still describe Geist Mono.

**Ours:** the 6-bit charset and its regenerated 64-slot atlas, the entry grid with per-entry decimals / right-pad / palette, the per-entry value sources, the object-fixed and UV modes, the crystal shell pass, the string→float label packing, and both procedural cubemaps.

**Deliberately not inherited:** upstream's depth-texture rangefinder. Its own comment reads "Cannot detect presence of Depth texture, this may be garbage", and that texture is not reliably present on avatars — camera-to-object distance needs no depth texture and is always correct.

**Bundled font.** The atlas rasterizes Geist Mono, SIL Open Font License 1.1 — see `assets/GeistMono-OFL.txt`, which ships because OFL requires the notice to accompany a bundled copy. Inheriting upstream's atlas PNG would have avoided the question; regenerating it does not, and regenerating is what a 64-slot charset requires.

**Two inherited bugs fixed here**, both of which printed a wrong number rather than failing:

- The ancestor's stereo guard tests `UNITY_SINGLE_PASS_STEREO`, the deprecated double-wide path. VRChat PC runs single-pass **instanced**, so both branches were dead and its "stereo-centre" camera helper returned a per-eye position — orienting the billboard plane differently in each eye. Guarded on `USING_STEREO_MATRICES` now, as Poiyomi does. **The readout's placement therefore differs from the ancestor's in VR, and that difference is the fix.**
- The local copy had dropped upstream's `"DisableBatching" = "True"` while still reading the object matrix. Dynamic batching bakes vertices to world space and leaves `unity_ObjectToWorld` identity, so a batched display prints the batch root's coordinates. Restored — and it matters more here than upstream, because a UV-mode quad is 4 vertices, well inside the eligible case.

## Interface

**Params** — none. No animator, no synced parameters, no menu. Values arrive either from the shader (render-side sources) or from a clip curve writing a material property.

**Seam** — none; nothing merges into any controller. The prefab's only component is an MA `BoneProxy` (Hips, `AsChildAtRoot`) with an `Offset` child carrying the display, per `CONVENTIONS.md` §Seam's rest-geometry rule — unanchored rest geometry loads at the avatar-root origin, i.e. the wearer's feet. Re-anchor the proxy wherever you want the readout to ride.

**Animation binding** — `material._E{i}_Value`, `i` in 0..11, on the display's `MeshRenderer`. A plain clip curve; the shader is unlocked, so there is no Poiyomi `Animated`-tag step. The material inspector has a copy button for each path. Verified end to end on a composed avatar, including that an MA `MergeAnimator` merging the clip into FX rewrites the curve's path through the `BoneProxy` relocation — the built clip binds `Armature/Hips/Anchor/Offset/Display`, which is where the proxy actually put the renderer.

**Dependencies** — Modular Avatar, for the `BoneProxy` only. Delete the anchor and the entry is dependency-free.

**Required assets** — all shipped and self-contained: the shader, its `.hlsl`, the glyph atlas, two cubemaps, and `WorldCoords.mat`. The material has zero dependencies outside this entry.

**Optional tool** — the `SetDisplayEntry` / `ReportDisplay` doors and the material inspector live in `vrc-unity-tools` (`com.ryan6vrc.avatar-tools`). Without it the entry still imports and renders unchanged, but it is **not fully configurable**: labels read as packed integers like `262143`, and `_E{i}_Format` is `[HideInInspector]`, so **decimals, right-pad, palette and value source are unreachable** short of a debug-inspector or YAML edit. Values, colours, grid dimensions and the mode enum stay editable. Unity also logs one "Could not create a custom UI" warning per inspect.

## Before you compose it

**`WorldCoords.mat` is a template, not a usable material.** It lives under `Packages/`, which `LAYOUT.md` makes read-only to our tooling — copy it into `Assets/` and configure the copy. `SetDisplayEntry` refuses a `Packages/` target and names this as the fix.

**Each display instance needs its own material** — for its *author-time* configuration, which is what actually collides. Labels, format bitfields, grid, mode, palettes and font size all live on the material, so two displays sharing one show the same layout and the same labels. The animated **value** does not collide: Unity drives `material._E{i}_Value` through a per-renderer `MaterialPropertyBlock`, measured, so two renderers on one shared material really can show different numbers. Do not rely on that — it makes a shared-material setup look half-correct, which is worse than uniformly wrong.

**Text size follows object scale, and turning that off makes small meshes lose their text entirely.** `_Font_Scale_Relative` ships **on**: `_Font_Size` is metres-per-ascender *at unit scale*, multiplied by the mean of the object's three axis scales. Turn it off and `_Font_Size` becomes an absolute physical size — the ancestor's behaviour — which is a trap worth naming, because `Cull Back` makes the mesh a window and the fragment stage only runs where the mesh rasterizes. Text that outgrows its mesh is therefore not clipped at the edge, it is **absent**. The anchor still scales correctly while the text does not, so what you see is a readout that moved and now prints wrong, rather than the obvious symptom. A **single scalar**, never per-axis: the plane basis is normalized precisely so a stretched mesh cannot distort the monospace grid, and a per-axis factor would put that distortion straight back. UV mode ignores the toggle — `_Font_Size` cancels out of it, so it is scale-relative either way.

**Mesh merging can relocate the text — check, do not assume either way.** Optimizers key merge decisions off the avatar root, and this display's anchor is not the avatar root, so a merge moves what the object matrix reports. Measured against `d4rkAvatarOptimizer` at its defaults on a composed humanoid: it collapsed the avatar's seven skinned meshes into one and **left both displays alone**, same transform, same material, still reading correctly. That is one optimizer at one setting, not a guarantee — the display is a `MeshRenderer` on an Overlay-queue shader carrying `DisableBatching`, and a different optimizer or a non-default setting can still take it. A per-GameObject opt-out exists in the optimizers that do it; use it if the readout is load-bearing.

**Object-fixed mode reads correctly from the object's −Z side, not its +Z side.** The text runs along the object's +X basis, and an observer standing on +Z looking back has their own right along world −X, so from there the whole grid renders mirrored. Nothing is wrong when that happens; turn the object around, or use billboard mode, which has no such side.

**Labels are author-time only, and that is the design.** There is no mechanism for a clip to drive text: ShaderLab has no string property, `Material` has no string setter, animator parameters are Float/Int/Bool/Trigger, and animation curves carry floats. A label packed into a material property costs nothing at runtime.

## Format contract

A managed echo of `DisplayGlyphs.cs` in `com.ryan6vrc.avatar-tools`, which is the canon for all of it. Re-read that file rather than this block if the two ever disagree.

| Constant | Value | Why it is this |
|---|---|---|
| Charset | 63 glyphs + space at 63 | 6-bit IDs. **Codepoint-ascending, non-negotiable:** `msdf-atlas-gen` lays a uniform grid out by codepoint regardless of the order the charset file requests, so a hand-grouped table renders every glyph as a different character. Space has no cell — it is the sentinel `Font::sdf()` early-returns on, and U+0020 would sort to ID 0 and collide |
| Label | 12 chars, 3 per `Vector` component | 4×6 = 24 bits is float32-exact but does **not** survive d4rk's text round-trip of material properties (`float.ToString()` is G7; 16777215 re-parses as 16777220, changing all four chars). 18 bits caps at 262143 — six digits, which survives |
| Label default | `(262143, 262143, 262143, 262143)` | All-space. A zeroed vector decodes as glyph 0 twelve times and prints `++++++++++++` |
| Format bitfield | decimals(3) palette(2) rpad(4) source(5), LSB-first | 14 bits, max 16383 — five digits, so G7-safe |
| Value field | 10 glyphs | A value whose rendered form (digits + sign + point + decimals) exceeds 10 columns prints the overflow glyph rather than truncating — the sign is emitted last, so truncation would drop it and print a confident positive. Magnitude ceiling 16,777,215 (float32's exact-integer limit). Decimals are exact **where the input is**: splitting the parts removes the multiply's overflow, but `frac(a)` still inherits `a`'s own quantization, so at `_Time.y ≈ 1000` the last digits are noise |
| Entries | 12 | A shader constant, not a preference: the fragment stage selects an entry with a `switch` over this many cases, and ShaderLab cannot declare a property array |
| `_Total_Width` | glyph **advances** | Not metres. One advance is derived from `_Font_Size`, so a metre-valued width would silently rescale the layout every time the font size moved |

**Right-pad, not an align-decimals flag.** The value right-aligns to `cell_width − rpad`, one subtraction. `rpad = max_decimals − entry_decimals` aligns decimal points across a grid column; an integer picks its own depth (`rpad 0` parks it at the cell's right edge). Right-alignment is deliberate — it makes values in the same grid column line up. rpad knows nothing about the label, so `label + value + rpad` over the cell width runs the value into the label; the value wins its region and the label's tail is overdrawn, which is visibly garbled and therefore a diagnostic. The inspector's preview is what catches it first.

**Value sources.** A source earns a slot only where an animator cannot measure the value; everything else uses source 0 and a float property. `Animator`, `WorldX/Y/Z`, `ScaleX/Y/Z`, `Azimuth`, `Elevation`, `CameraDistance`, `CameraFarPlane`, `ObserverFps`, `TimeSeconds`, `VRChatCameraMode`, `VRChatMirrorMode`, `StereoEyeIndex`. IDs are wire values baked into authored materials — append only, never renumber.

Compass convention is **ours**: azimuth 0° at world +Z increasing toward +X, range 0–360; elevation −90..+90. Full Euler is absent because it needs an arbitrary order convention. The two `_VRChat*` enum values are a managed echo of lilToon's declaration — re-read that source if a VRChat release moves them.

## Verifying the install

**The cheapest observable:** drop the prefab on an avatar and look at the readout. If the three numbers track the wearer moving, it landed. If they read near `0.00 / 0.00 / 0.00` and stay there, the `BoneProxy` never resolved and the display is sitting at the avatar-root origin — the same wrong-looking-plausible reading the batching trap produces, so check the proxy's target before suspecting anything subtler.

If the text is missing entirely but the mesh is visible, either the material's atlas slot is empty or the text has outgrown its window — check `_Font_Scale_Relative` and `_Font_Size` first if you scaled anything, since the two look identical on screen. **In UV mode neither is the first suspect** — a mesh with no UVs renders nothing on purpose, so check the mesh's `TEXCOORD0` before the slot, and the toggle does not apply there at all. If the shell looks flat grey rather than glassy, its cubemap slot is empty, or the cubemap imported as a `Texture2D` (`samplerCUBE` then receives nothing). All of these fail quietly by design of the render pipeline; none errors.

**To check whether a clip is actually driving an entry, read the renderer's `MaterialPropertyBlock`, not the material.** Unity applies animated material properties as a per-renderer override; `sharedMaterial.GetFloat("_E0_Value")` and `renderer.material.GetFloat(...)` both keep returning the **authored** value while the display visibly animates, so the obvious check reports "not driven" on a display that is driven. Use `renderer.GetPropertyBlock(mpb); mpb.GetFloat("_E0_Value")`. Related trap for anything inspecting a live avatar: touching `renderer.material` at all instantiates the material, which changes what `sharedMaterial` then compares equal to — read `sharedMaterial` and the property block, never `.material`.

**What cannot be checked outside the real client:** sources 13–15 (`VRChatCameraMode`, `VRChatMirrorMode`, `StereoEyeIndex`). They read 0 in the Editor whether or not the globals exist, so an Editor render cannot distinguish "correct, normal mode" from "never set". The stereo-centre billboard fix is likewise unobservable in a monoscopic render — it only manifests as per-eye disparity in a headset. `docs/verify.md` owns the general boundary.

## Regenerating the generated assets

Both generated binaries ship with the script that made them, because a generated image is not reproducible and a script is.

- `tools/generate_atlas.ps1` — fetch the `msdf-atlas-gen` release binary named in its header, run, delete the binary. It parses the charset out of `DisplayGlyphs.cs` rather than carrying a copy, and prints the `Font` constants to paste into `debug_display_common.hlsl`. It expects a "cell too constrained" warning; the header explains why that is correct and what the alternative costs.
- `tools/generate_cubemaps.py` — stdlib only, no PIL.

**Texture import settings are load-bearing, and Unity's defaults are wrong for all three.** The atlas must be uncompressed, non-sRGB, mip-free (it is distance data sampled at LOD 0, and sRGB would gamma-curve the distances); the cubemaps must import as `TextureCube` with mips on. A cubemap that imports as `Texture2D` leaves `samplerCUBE` with nothing and the shell renders flat grey without erroring.

**What the gate does and does not cover here.** It asserts the shaders compile (warming every declared keyword variant first, since variants compile lazily and a default-only check would be weaker than a one-time review), that each material's shader reference resolves, and that no material's texture slot carries a GUID from outside the entry — read as raw GUIDs out of the `.mat`, because a GUID into a package the venue lacks resolves to nothing and would otherwise vanish from a dependency walk. It does **not** assert the import settings themselves; those are pinned only in the committed `.meta`s, so a deliberate reimport can still change them and only this README will object.
