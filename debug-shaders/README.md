# debug-shaders (Structural Module)

Three overlay shaders for looking at what an avatar is actually doing, sharing one glassy crystal shell: a numeric readout that prints up to twelve labelled values in world space, a depth-derived surface probe that draws triangle edges or reconstructed normals, and a localized grading bubble that darkens, brightens or desaturates the scene inside a radius. Each renders on whatever mesh you drop it on, none syncs a bit, and none needs an animator.

| Shader | Prints | Sample prefab |
|---|---|---|
| `DebugDisplay` | twelve labelled values: animator floats alongside render-side facts an animator cannot reach (world position, camera distance, the observing client's frame rate) | `DebugDisplay.prefab` |
| `DebugOverlay` | triangle edges (wireframe) or reconstructed world normals, from the depth buffer | `DebugOverlay.prefab` |
| `GammaCrystal` | nothing — it grades the scene inside a sphere of influence, through a grab pass | `GammaCrystal.prefab` |

Two of the three read the scene depth texture, which nothing on an avatar provides — the sample prefabs ship the light that does. See §The depth texture.

## Provenance

All three derive from [`lereldarion/unity-shaders`](https://github.com/lereldarion/unity-shaders) (MIT, © 2025 Lereldarion), each from a named ancestor:

| Shader | Upstream ancestor |
|---|---|
| `DebugDisplay` | `Shaders/Overlay_HUD.shader` |
| `DebugOverlay` | `Shaders/Overlay_Wireframe.shader` and `Shaders/Overlay_Normals.shader`, merged |
| `GammaCrystal` | `Shaders/Overlay_Gamma_Adjust.shader` |

Upstream's own credit chain travels with the depth reconstruction and must not be dropped: the `unity_CameraInvProjection` patch that makes it work in BIRP VR is **d4rkpl4y3r's** ([gist](https://gist.github.com/d4rkc0d3r/886be3b6c233349ea6f8b4a7fcdacab3)), and the wireframe idea is **Neitri's** ([Neitri-Unity-Shaders](https://github.com/netri/Neitri-Unity-Shaders)).

Every one of these reached this entry through a private project's hand copies, which had drifted from upstream and from each other and carried no attribution at all except on `GammaCrystal` — and that one cited a shader name (`Overlay/GammaAdjust`) upstream has never used. Restoring the credit is part of what this entry is for.

**Upstream's, kept:** the depth-reconstruction matrix chain, both probe fragment bodies, the grab-pass gamma idea, the `Font` metric ratios and monospace fixed-cell scheme, `median()`, `compute_screenspace_scale_of_uv`, `sdf_blend_with_aa`, and the central readout idea — a fragment-stage ray-trace against a virtual plane through the object origin, with `Cull Back` making the silhouette a window. The `*_em` metrics still describe Geist Mono.

**Ours:** the crystal shell and rim (upstream has no equivalent pass), the merge of wireframe and normals into one shader, `GammaCrystal`'s volumetric sphere-of-influence model, its exposure/scotopic/core stages and scale handling, the 6-bit charset and its regenerated 64-slot atlas, the entry grid with per-entry decimals / right-pad / palette, the per-entry value sources, the object-fixed and UV display modes, the string→float label packing, and both reflection cubemaps.

**Deliberately not inherited:** upstream's depth-texture *rangefinder* in the readout — its own comment reads "Cannot detect presence of Depth texture, this may be garbage", and camera-to-object distance needs no depth texture and is always correct. That is why `DebugDisplay` alone works without a depth source. Also dropped: upstream's border-dissolve, billboard-sphere and trail modes.

**Bundled font.** The atlas rasterizes Geist Mono, SIL Open Font License 1.1 — see `assets/font/GeistMono-OFL.txt`, which ships because OFL requires the notice to accompany a bundled copy. The atlas, its charset digest and that notice all live in `assets/font/` — font-derived files a consumer never wires up by hand.

**One deliberate divergence from upstream, which is not a bug to reconcile.** The normals probe writes `GammaToLinearSpace(n * 0.5 + 0.5)` where upstream writes `LinearToGammaSpace`. VRChat runs Linear colour space, so the hardware converts the fragment output linear→sRGB on the way to the framebuffer; displaying the encoded value therefore means *emitting* the linear value whose sRGB encoding is that number. Upstream's direction is correct only in a Gamma-space project. Reverting it to match upstream washes every normal colour out non-linearly, so the divergence is load-bearing and the shader comment says so at the line.

**Three inherited bugs fixed here**, each of which drew a wrong picture rather than failing:

- The stereo guard tested `UNITY_SINGLE_PASS_STEREO`, the deprecated double-wide path. VRChat PC runs single-pass **instanced**, so both branches were dead and the "stereo-centre" camera helper returned a per-eye position — orienting the readout's billboard plane and the shell's rim anchor differently in each eye. Guarded on `USING_STEREO_MATRICES` now, as Poiyomi does, in `stereo_camera.hlsl`. **The readout's placement therefore differs from the ancestors' in VR, and that difference is the fix.** Not every occurrence of the old macro was this bug — `depth_reconstruct.hlsl` keeps one deliberately.
- `"DisableBatching" = "True"` had been dropped, and it is load-bearing for three different reasons. `GammaCrystal` reads the object matrix directly (translation column as the sphere centre, basis lengths as the scale), so a batched bubble centres on the world origin at unit scale. `DebugOverlay` reads no object matrix, but its fullscreen path builds a quad from `SV_VertexID` and writes NaN to every vertex past the fourth, so batching it with a neighbour destroys the neighbour. `DebugDisplay`'s case is the classic one: a batched readout prints the batch root's coordinates, and a UV-mode quad is 4 vertices, well inside the eligible case.
- Every ancestor material pointed `_Shell_ReflectionCube` at Poiyomi's `T_Shine_CM`, out of `com.poiyomi.toon` — see §Import settings for why that fails quietly rather than pinkly — and the two probe materials carried dead Standard-shader slots holding a *second* copy of that GUID on a property their shader never declares. Both are repointed at the owned cubemaps and the dead slots are stripped, which the gate's raw-GUID texture rule now holds.

## Shared code

Four `.hlsl` files under `assets/`, each with one job, because three shaders having to agree is what makes a copy drift:

- `stereo_camera.hlsl` — the two stereo-correct camera positions. Its own file because the readout's text pass needs them and wants none of the shell's uniforms.
- `crystal_shell.hlsl` — the shell property block, vertex stage, and `shell_rgb()`. The three shaders agree completely up to that colour and diverge only after it, which is why it returns a `half3` rather than being a fragment stage: `GammaCrystal` puts the result through the same grading it applies to the world, the other two return it.
- `depth_reconstruct.hlsl` — the clip→view matrix and the depth sampling around it. **Keeps one `UNITY_SINGLE_PASS_STEREO` guard on purpose:** there the guarded code is a half-width correction that only exists for the double-wide path, so it is correct to leave inert under instancing, and converting it to `USING_STEREO_MATRICES` would sample two clip-space units off in the right eye — the opposite of the fix above.
- `debug_display_common.hlsl` — everything the readout's text half needs, and nothing else.

## The depth texture

`DebugOverlay` in both modes, and `GammaCrystal`'s volumetric strength term, reconstruct world position from `_CameraDepthTexture`. **Nothing on an avatar populates it**, and its absence is silent: the probe renders a flat fill, the bubble grades uniformly, neither errors.

Both sample prefabs therefore carry a `DepthLight` child, and every setting on it is doing work — in forward rendering Unity builds the depth texture for screen-space shadows, so a shadow-casting directional light is what turns it on:

| Field | Value | Why |
|---|---|---|
| `type` | Directional | Only a directional light's shadows force the pass |
| `shadows` | Hard | Must be enabled, or there is no pass to force |
| `shadowStrength` | `0` | …so it casts nothing visible |
| `intensity` | `0.001` | Non-zero, imperceptible |
| `cullingMask` | Ignore Raycast only | Lights nothing an avatar is on |

Copy it wholesale. Losing `shadowStrength` puts hard shadows across the world from a light nobody can see; losing the culling mask relights every avatar in the instance.

A world with its own shadow-casting directional light populates the texture as well, which is the trap in judging `DepthLight` redundant: the shaders keep working in the venue where you tested and go flat in the next one. It is the guarantee, not the only source.

**In the Editor, the Scene view's lighting toggle gates the whole mechanism.** With it off no scene light renders, `DepthLight` included, so the texture is never built and all three depth-derived effects read exactly like a broken install — check it before suspecting the material, the mesh, or the shader. `Shader.GetGlobalTexture("_CameraDepthTexture")` returning null is the one-call confirmation, and it tracks that toggle in both directions — but read it against the view you are judging. The global holds whatever the last camera to render left there, so rendering a camera that requests no depth — a Game-view capture through a stock Main Camera — leaves it null and the check then reports a fault the Scene view does not have. That is a stale read, not damage: the next Scene-view render rebinds it, and a Scene-view capture both restores it and shows the true state.

## The sample mesh

`assets/DebugSphere.fbx` is **two things**, and a consumer replacing it should know which half they are dropping: a subdivision-3 icosphere (320 triangles, custom normals imported from the file) plus **six loose triangles at exactly 20× its radius**. The loose triangles inflate the renderer's bounds on purpose. A shader whose effect is screen-space — either probe in fullscreen mode, and the grading bubble always — stops rendering the moment its small mesh leaves the frustum, so bounds matching the visible sphere would cull the effect exactly when the camera turns toward what it was grading.

That 20× ratio is the only handle on the sphere's own size: `mesh.bounds` describes the inflation rig rather than anything visible, so `bounds.extents / 20` is how the sphere's radius is recovered. **The FBX carries a 50× import scale so the sphere is 0.15 m at unit scale**, and the shipped prefabs sit at scale 1.

That import scale is load-bearing, not cosmetic. `_AoE_MinDistance`, `_AoE_MaxDistance` and `_Core_Radius` are multiplied by the object's mean axis scale, so hosting the sphere at 50× to compensate for a small mesh multiplies every one of those distances by 50 as well — a 1 m falloff becomes 50 m, the grading never falls off inside any room, and the result is indistinguishable from the missing-depth-texture symptom above. Scale the mesh at import, not the transform.

**This mesh cannot host `DebugOverlay`'s fullscreen mode, and no material setting changes that.** The fullscreen path assigns NDC corners by `SV_VertexID` 0–3 and sends every higher id to `nan`, so covering the frame takes a mesh whose first *two* triangles are drawn from those four vertices. `IcoSphere`'s index buffer runs `0,1,2 / 3,4,5`, so exactly one triangle survives and the probe fills a diagonal half. `_Overlay_Screenspace_Vertex_Reorder` moves which half; it cannot supply the second triangle. A Unity **cube or quad** works unmodified — put the material on one of those to use fullscreen, and keep this sphere for mesh mode.

**`GammaCrystal`'s `_Core_Radius` is authored, not derived, and it is deliberately larger than the surface it traces** — the shipped 0.1541667 is 2.78% outside the icosphere's 0.15. The core is a smoothstep with a feathered inner edge, so a radius set exactly at the surface puts the feather *inside* the silhouette and the edge reads soft and undersized. On any non-spherical mesh there is no single surface radius to derive from at all, which is the other reason this stays a knob. Retune it by eye against the mesh you are using; scale-relative handling means the number then holds at any object scale.

None of the three shaders needs this mesh, and only `DebugOverlay`'s fullscreen mode needs any particular one. It ships because an icosphere's even topology reads better under a wireframe probe than a UV sphere's pole convergence, and because the bounds rig is worth having by default.

## Interface

**Params** — none, on any of the three. No animator, no synced parameters, no menu. Values arrive either from the shader (render-side sources) or from a clip curve writing a material property.

**Seam** — none; nothing merges into any controller. Each prefab's only avatar-framework component is an MA `BoneProxy` (Hips, `AsChildAtRoot`) with an `Offset` child carrying the renderer, per `CONVENTIONS.md` §Seam's rest-geometry rule — unanchored rest geometry loads at the avatar-root origin, i.e. the wearer's feet. Re-anchor the proxy wherever you want the thing to ride.

**Animation binding** — `DebugDisplay` only: `material._E{i}_Value`, `i` in 0..11, on the display's `MeshRenderer`. A plain clip curve; the shader is unlocked, so there is no Poiyomi `Animated`-tag step. The material inspector has a copy button for each path. Verified end to end on a composed avatar, including that an MA `MergeAnimator` merging the clip into FX rewrites the curve's path through the `BoneProxy` relocation.

**Dependencies** — Modular Avatar, for the `BoneProxy` only. Delete the anchor and the entry is dependency-free.

**Required assets** — all shipped and self-contained: three shaders, four `.hlsl`, the glyph atlas, two cubemaps, the sample mesh, and three materials. No material has a dependency outside this entry, which the gate enforces.

**Optional tool** — the material inspectors and the `SetDisplayEntry` / `ReportDisplay` doors live in `vrc-unity-tools` (`com.ryan6vrc.avatar-tools`). Without it every material still imports and renders unchanged, and every shader stays editable through Unity's default ShaderGUI — but `DebugDisplay` is **not fully configurable**: labels read as packed integers like `262143`, and `_E{i}_Format` is `[HideInInspector]`, so **decimals, right-pad, palette and value source are unreachable** short of a debug-inspector or YAML edit. Unity also logs one "Could not create a custom UI" warning per inspect.

## Before you compose it

**The shipped materials are templates, not usable materials.** They live under `Packages/`, which `LAYOUT.md` makes read-only to our tooling — copy one into `Assets/` and configure the copy. `SetDisplayEntry` refuses a `Packages/` target and names this as the fix.

**Each `DebugDisplay` instance needs its own material** — for its *author-time* configuration, which is what actually collides. Labels, format bitfields, grid, mode, palettes and font size all live on the material, so two displays sharing one show the same layout and the same labels. The animated **value** does not collide: Unity drives `material._E{i}_Value` through a per-renderer `MaterialPropertyBlock`, measured, so two renderers on one shared material really can show different numbers. Do not rely on that — it makes a shared-material setup look half-correct, which is worse than uniformly wrong.

**`GammaCrystal`'s three distances are metres at unit scale, multiplied by the object's mean axis scale.** `_AoE_Scale_Relative` ships **on**, and turning it off restores the ancestor's absolute metres along with the trap that motivated the toggle: the shell pass draws the mesh at its real size while the effect stays fixed, so scaling the object — or animating the scale, which is the obvious way to grow a bubble — slides the visible sphere out of the region it bounds and the core silhouette stops tracing the mesh it is matched to. A **single scalar**, never per-axis: the area of effect is spherical by construction, so a per-axis factor would ask for an ellipsoid the maths cannot express. A non-uniformly scaled object therefore still renders an ellipsoid shell around a spherical effect; use a uniform scale.

**`GammaCrystal` costs a `GrabPass`,** which the other two do not. It copies the framebuffer once per render, so it is the one shader here whose cost scales with resolution rather than with the mesh. Budget it as you would any screen-space avatar effect, and prefer toggling it off to leaving it neutral — a neutral bubble still grabs.

**Text size follows object scale, and turning that off makes small meshes lose their text entirely.** `DebugDisplay`'s `_Font_Scale_Relative` ships **on**: `_Font_Size` is metres-per-ascender *at unit scale*, multiplied by the mean of the object's three axis scales. Turn it off and `_Font_Size` becomes an absolute physical size — the ancestor's behaviour — which is a trap worth naming, because `Cull Back` makes the mesh a window and the fragment stage only runs where the mesh rasterizes. Text that outgrows its mesh is therefore not clipped at the edge, it is **absent**. The anchor still scales correctly while the text does not, so what you see is a readout that moved and now prints wrong. A **single scalar**, never per-axis: the plane basis is normalized precisely so a stretched mesh cannot distort the monospace grid. UV mode ignores the toggle — `_Font_Size` cancels out of it.

**Mesh merging can relocate anything here — check, do not assume either way.** Optimizers key merge decisions off the avatar root, and these anchors are not the avatar root, so a merge moves what the object matrix reports. Measured against `d4rkAvatarOptimizer` at its defaults on a composed humanoid: it collapsed the avatar's seven skinned meshes into one and **left both displays alone**, same transform, same material, still reading correctly. That is one optimizer at one setting, not a guarantee. A per-GameObject opt-out exists in the optimizers that do it; use it if the readout is load-bearing.

**Object-fixed display mode reads correctly from the object's −Z side, not its +Z side.** The text runs along the object's +X basis, and an observer standing on +Z looking back has their own right along world −X, so from there the whole grid renders mirrored. Nothing is wrong when that happens; turn the object around, or use billboard mode, which has no such side.

**Labels are author-time only, and that is the design.** There is no mechanism for a clip to drive text: ShaderLab has no string property, `Material` has no string setter, animator parameters are Float/Int/Bool/Trigger, and animation curves carry floats. A label packed into a material property costs nothing at runtime.

**Camera and mirror behaviour is deliberately not uniform across the three.** `DebugOverlay` suppresses only its *fullscreen takeover* in mirrors and the VRChat camera, still drawing on its mesh there, so a photo is not entirely covered by a wireframe. `GammaCrystal` renders no geometry at all in mirrors and does grade the VRChat camera, because a scene grade is what a photo should capture. Neither is an oversight; changing one to match the other is a design decision, not a cleanup.

## Format contract

A managed echo of `DisplayGlyphs.cs` in `com.ryan6vrc.avatar-tools`, which is the canon for all of it. Re-read that file rather than this block if the two ever disagree. Applies to `DebugDisplay` only.

| Constant | Value | Why it is this |
|---|---|---|
| Charset | 63 glyphs + space at 63 | 6-bit IDs. **Codepoint-ascending, non-negotiable:** `msdf-atlas-gen` lays a uniform grid out by codepoint regardless of the order the charset file requests, so a hand-grouped table renders every glyph as a different character. Space has no cell — it is the sentinel `Font::sdf()` early-returns on, and U+0020 would sort to ID 0 and collide |
| Label | 12 chars, 3 per `Vector` component | 4×6 = 24 bits is float32-exact but does **not** survive d4rk's text round-trip of material properties (`float.ToString()` is G7; 16777215 re-parses as 16777220, changing all four chars). 18 bits caps at 262143 — six digits, which survives |
| Label default | `(262143, 262143, 262143, 262143)` | All-space. A zeroed vector decodes as glyph 0 twelve times and prints `++++++++++++` |
| Format bitfield | decimals(3) palette(2) rpad(4) source(5), LSB-first | 14 bits, max 16383 — five digits, so G7-safe |
| Value field | 10 glyphs | A value whose rendered form (digits + sign + point + decimals) exceeds 10 columns prints the overflow glyph rather than truncating — the sign is emitted last, so truncation would drop it and print a confident positive. Magnitude ceiling 16,777,215 (float32's exact-integer limit). Decimals are exact **where the input is**: splitting the parts removes the multiply's overflow, but `frac(a)` still inherits `a`'s own quantization, so at `_Time.y ≈ 1000` the last digits are noise |
| Entries | 12 | A shader constant, not a preference: the fragment stage selects an entry with a `switch` over this many cases, and ShaderLab cannot declare a property array |
| `_Total_Width` | glyph **advances**, across all columns | Not metres. One advance is derived from `_Font_Size`, so a metre-valued width would silently rescale the layout every time the font size moved. The layout math wants the total; the inspector edits it **per column** (total ÷ columns), which is the number that decides whether a label clears its value |

**Right-pad, not an align-decimals flag.** The value right-aligns to `cell_width − rpad`, one subtraction. `rpad = max_decimals − entry_decimals` aligns decimal points across a grid column; an integer picks its own depth (`rpad 0` parks it at the cell's right edge). Right-alignment is deliberate — it makes values in the same grid column line up. rpad knows nothing about the label, so `label + value + rpad` over the cell width runs the value into the label; the value wins its region and the label's tail is overdrawn, which is visibly garbled and therefore a diagnostic. The material inspector catches it before anything renders, provided someone has it open: the offending entry gets a warning box, its shut fold carries a `(!)` or `(?)` in the title, and the summary at the top of the inspector names the entry even with every fold closed. `ReportDisplay` is the same check for an agent, which is what catches it when no inspector is open — `SetDisplayEntry` writes without one.

**Value sources.** A source earns a slot only where an animator cannot measure the value; everything else uses source 0 and a float property. `Animator`, `WorldX/Y/Z`, `ScaleX/Y/Z`, `Azimuth`, `Elevation`, `CameraDistance`, `CameraFarPlane`, `ObserverFps`, `TimeSeconds`, `VRChatCameraMode`, `VRChatMirrorMode`, `StereoEyeIndex`. IDs are wire values baked into authored materials — append only, never renumber.

Compass convention is **ours**: azimuth 0° at world +Z increasing toward +X, range 0–360; elevation −90..+90. Full Euler is absent because it needs an arbitrary order convention. The two `_VRChat*` enum values are a managed echo of lilToon's declaration — re-read that source if a VRChat release moves them.

## Verifying the install

**`DebugDisplay`** — drop the prefab on an avatar and look at the readout. If the three numbers track the wearer moving, it landed. If they read near `0.00 / 0.00 / 0.00` and stay there, the `BoneProxy` never resolved and the display is sitting at the avatar-root origin — the same wrong-looking-plausible reading the batching trap produces, so check the proxy's target before suspecting anything subtler. Text missing but mesh visible means either an empty atlas slot or text that outgrew its window; check `_Font_Scale_Relative` and `_Font_Size` first if you scaled anything. In UV mode neither is the first suspect — a mesh with no UVs renders nothing on purpose, so check `TEXCOORD0` before the slot.

**`DebugOverlay`** — point it at geometry with visible edges. Wireframe mode should draw edges that move with the camera, not with the mesh; a **uniform flat fill that responds to nothing is the depth texture missing**, not a broken install. Confirm the `DepthLight` child is active — and, in the Editor, that Scene-view lighting is on — before suspecting the shader.

**`GammaCrystal`** — walk the camera toward the sphere: the grading should deepen smoothly and reach full strength before you touch it. If nothing happens at all, check whether every effect is neutral (gamma 0 with exposure and scotopic off makes the fragment return the scene untouched — the inspector warns about exactly this). If the grading is uniform everywhere instead of falling off with distance, check the object's scale before the depth texture: the falloff distances are multiplied by mean axis scale, so a bubble hosted at 50× reaches 50× as far and looks exactly as flat.

**Any shader here** — a flat grey shell rather than a glassy one means its cubemap slot is empty, or the cubemap imported as a `Texture2D` (`samplerCUBE` then receives nothing). All of these fail quietly by design of the render pipeline; none errors.

**To check whether a clip is actually driving a display entry, read the renderer's `MaterialPropertyBlock`, not the material.** Unity applies animated material properties as a per-renderer override; `sharedMaterial.GetFloat("_E0_Value")` and `renderer.material.GetFloat(...)` both keep returning the **authored** value while the display visibly animates, so the obvious check reports "not driven" on a display that is driven. Use `renderer.GetPropertyBlock(mpb); mpb.GetFloat("_E0_Value")`. Related trap for anything inspecting a live avatar: touching `renderer.material` at all instantiates the material, which changes what `sharedMaterial` then compares equal to — read `sharedMaterial` and the property block, never `.material`.

**What cannot be checked outside the real client:** `DebugDisplay`'s sources 13–15 (`VRChatCameraMode`, `VRChatMirrorMode`, `StereoEyeIndex`) read 0 in the Editor whether or not the globals exist, so an Editor render cannot distinguish "correct, normal mode" from "never set" — which also means the camera and mirror behaviours above are Editor-invisible for all three shaders. The stereo-centre fix is likewise unobservable in a monoscopic render — it only manifests as per-eye disparity in a headset. `docs/verify.md` owns the general boundary.

## Regenerating the glyph atlas

`tools/generate_atlas.ps1` — fetch the `msdf-atlas-gen` release binary named in its header, run, delete the binary. It parses the charset out of `DisplayGlyphs.cs` rather than carrying a copy, and prints the `Font` constants to paste into `debug_display_common.hlsl`. It expects a "cell too constrained" warning; the header explains why that is correct and what the alternative costs.

This one ships because the atlas is not set dressing — it *is* the text rendering, its cell order is enforced by a test, and `debug_display_common.hlsl`'s `Font` constants have to be re-derived alongside it. The cubemaps have no equivalent script; see below.

## Import settings

**Load-bearing, and Unity's defaults are wrong for all three textures.** They are pinned only in the committed `.meta`s. Every one of these fails **silently** — no error, no pink material, just a wrong-looking or dead-looking shell — so verify them rather than trusting a fresh import, and re-check them after replacing either cubemap.

The atlas must be uncompressed, non-sRGB and mip-free: it is distance data sampled at LOD 0, and sRGB would gamma-curve the distances.

Both cubemaps need all six of:

| Field | Value | What a wrong value does |
|---|---|---|
| `textureShape` | `TextureCube` | Imports as `Texture2D`, `samplerCUBE` receives nothing, the shell renders flat grey |
| `cubemapConvolution` | `1` (Specular) | See below — the blur controls go inert |
| `enableMipMap` | `1` | No chain to sample, so there is nothing for the blur controls to read |
| `filterMode` | `2` (Trilinear) | The sampled mip is **fractional**, and a Bilinear sampler gives a point mip filter that snaps to one level, so the shell steps instead of blurring |
| `maxTextureSize` | `512` | Clamps the generated face size, so it is what actually sets VRAM here — both source images are large enough to be clamped by it rather than limited by their own dimensions |
| `textureCompression` | `1` (Compressed) | Uncompressed is roughly 4× the bytes for no visible gain on a smooth environment gradient |

As shipped and measured in-Editor, both land at **512-px faces, DXT1, 2.00 MB each — 4 MB of VRAM for the pair**, shared by all three shaders. 512 is an operator judgement that the shell looks right there, not a limit of the images: raising the clamp raises the cost about 4× per doubling and a replacement image only matters below it. Ten mip levels remain, so the LOD curve's mip-6 ceiling is still inside the chain.

**The two cubemaps are shipped images, not generated at build time.** `Cube_Iridescent.png` is procedural output; `Cube_Glass.png` was produced with OpenAI `gpt-image-1`. Neither generator is committed — the cubemaps are set dressing for shaders whose actual substance is elsewhere, and carrying a reproducible pipeline for two decorative gradients was not worth its maintenance. Swap either for any 1:1 image, subject to the table above. They replaced Poiyomi's `T_Shine_CM` and `T_iridescent_CM`, which every ancestor material referenced out of `com.poiyomi.toon`: a dependency that failed **quietly**, since only the texture slot pointed into the package, so a consumer without Poiyomi got a null cubemap and a silently wrong reflection rather than a pink material. Owning them removed the dependency and the quiet failure together, and pointing a material back at `com.poiyomi.toon` reintroduces both.

**Replacing a cubemap:** overwrite the PNG bytes and keep the existing `.meta`. The `.meta` carries both the import settings above and the GUID the materials resolve, so replacing it instead breaks every texture reference. Any 1:1 image works — Unity reads it as a spheremap and generates faces at half the power-of-two source width, then clamps to `maxTextureSize`.

**`cubemapConvolution` is the one that will waste your day.** At `1` (Specular / "Glossy Reflection") Unity bakes a prefiltered glossy-reflection chain, so mip *N* is a progressively wider convolved environment — exactly what a smoothness-driven `texCUBElod` is asking for. At `0` (None) the chain is plain minified copies, and `_Shell_Reflection_Smoothness` and `_Shell_Reflection_BlurMaxMip` both become **nearly inert with no other symptom**. Measured in texel space, one cubemap went from 97% of its mip-0 gradient retained at lod 3 to 10% on that single flip, with mip 0 bit-identical either way; face size, mip count, format and VRAM are unchanged **by the flip itself**, so it costs nothing but import time. Use Specular, not Diffuse — Diffuse is an irradiance chain and over-convolves the first mip. Feature size, feature sharpness, image content, mip filter (Box vs Kaiser: no measurable effect) and face resolution (1024 vs 512 on identical content: 55% vs 53%) were each measured and each ruled out, so do not diagnose a dead blur slider by looking at the image.

It is worth knowing *why* this is the setting rather than an oddity: both Poiyomi and lilToon sample a custom reflection cubemap as a stand-in for `unity_SpecCube0`, i.e. a reflection probe, which Unity always convolves — Poiyomi with `texCUBElod(cube, float4(dir, roughness * UNITY_SPECCUBE_LOD_STEPS))`. Of the eight cubemaps Poiyomi ships, seven carry `cubemapConvolution: 1` — the exception, `T_Default_CM.exr`, is its unconvolved default slot rather than a counterexample. A convolved chain is the convention this kind of texture assumes, and an unconvolved one is the anomaly.

**The shell's LOD follows the same convention,** in `crystal_shell.hlsl`: `mip = pR * (1.7 - 0.7 * pR) * _Shell_Reflection_BlurMaxMip`, where `pR = 1 - smoothness`. That is Unity's own perceptual-roughness remap, and at the slider's ceiling of 6 it is exactly lilToon's `pR * (10.2 - 4.2 * pR)`; 6 is where both vendors hardcode `UNITY_SPECCUBE_LOD_STEPS`, so the slider only ever trims blur below the convention rather than inventing travel above it. It replaced a bare linear ramp over `Range(0, 10)`, which under-blurred the mid range and spent its top third on mips a convolved chain has already flattened.

**Every shipped material's blur cap was re-fit to the new curve, per material, and any shell render captured before that is stale.** `WorldCoords.mat` ships smoothness 0.75 with the cap at 5.85 — the least-squares fit of the new curve to its old ramp across the whole slider, so it is the closest single value over the range rather than at one point. The two ported materials ship smoothness 0.7 with the cap at 4.83, a *point* match instead: their ancestors ran the old ramp at cap 7.2, i.e. mip 2.16, and the new curve reaches that at 4.83. Copying one material's cap to another is wrong — the fit depends on the ramp the material actually had.

## What the gate covers

It asserts that every shader compiles (warming every declared keyword variant first, since variants compile lazily and a default-only check would be weaker than a one-time review), that each material's shader reference resolves, that no material's texture slot carries a GUID from outside the entry, and that every prefab loads with no missing scripts. It does **not** assert the import settings above; those are pinned only in the committed `.meta`s, so a deliberate reimport can still change them and only this README will object.

Note for anyone running it: do **not** mount this repo as a package in the gate's own venue. The gate copies each entry into a scratch folder under `Assets/`, and a mounted copy collides with that on every GUID, failing all eighteen entries at once — a venue-level symptom that looks nothing like its cause.
