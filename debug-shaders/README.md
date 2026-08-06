# debug-shaders (Structural Module)

Three overlay shaders for looking at what an avatar is actually doing, sharing one glassy crystal shell: `DebugDisplay` prints up to twelve labelled values on a plane through the object origin, `DebugOverlay` draws triangle edges or reconstructed world normals from the scene depth buffer, and `GammaCrystal` grades the scene inside a sphere of influence through a grab pass. Each renders on whatever mesh you drop it on, all configuration is material-side, and none of the three syncs a bit or needs an animator.

Reach for `DebugDisplay` when you want to read a number in-world — an animator float, or a render-side fact an animator cannot measure (world position, camera distance, the observing client's frame rate). Reach for `DebugOverlay` to see surface shape a material is hiding. Reach for `GammaCrystal` to darken, brighten or desaturate what surrounds you, bounded to a radius.

## Provenance

All three derive from [`lereldarion/unity-shaders`](https://github.com/lereldarion/unity-shaders) (MIT, © 2025 Lereldarion): `DebugDisplay` from `Shaders/Overlay_HUD.shader`, `DebugOverlay` from `Overlay_Wireframe.shader` and `Overlay_Normals.shader` merged into one, `GammaCrystal` from `Overlay_Gamma_Adjust.shader`. Each was modified privately for one avatar first; this entry generalizes that set. Upstream's credit chain travels with the depth reconstruction and must not be dropped: the `unity_CameraInvProjection` patch that makes it work in BIRP VR is **d4rkpl4y3r's** ([gist](https://gist.github.com/d4rkc0d3r/886be3b6c233349ea6f8b4a7fcdacab3)), and the wireframe idea is **Neitri's** ([Neitri-Unity-Shaders](https://github.com/netri/Neitri-Unity-Shaders)). Ours are the crystal shell and rim, the merge of the two probes, `GammaCrystal`'s sphere-of-influence model and its exposure/scotopic/core stages, and `DebugDisplay`'s charset, atlas, entry grid and value sources.

The glyph atlas rasterizes **Geist Mono**, SIL Open Font License 1.1 — `assets/font/GeistMono-OFL.txt` ships because OFL requires the notice to accompany a bundled copy.

## Configuring a material

Every knob is a material property, grouped below the way the inspectors in `Editor/` group them. Copy a shipped material into `Assets/` before editing — the originals live under `Packages/`, which is read-only.

**Crystal shell — all three shaders, identical properties** (`Shell enabled` gates the whole pass; turning it off leaves only the probe/readout/grading):

| Property | What it does |
|---|---|
| `_Shell_Reflection_Color` (Color / Mask) | HDR tint and, through its alpha, a second multiplier on the reflection |
| `_Shell_ReflectionCube` | the cubemap the shell reflects; two owned ones ship, and either may be swapped for any 1:1 image |
| `_Shell_Reflection_Strength` | reflection brightness, 0–4 |
| `_Shell_Reflection_Smoothness` | 0–1; drives the sampled mip through Unity's perceptual-roughness remap, so lower is blurrier |
| `_Shell_Reflection_BlurMaxMip` | the LOD that remap reaches at roughness 1. Ranged 0–6 because 6 is `UNITY_SPECCUBE_LOD_STEPS`, where a convolved chain is already flat — the slider only ever trims blur below the convention |
| `_Shell_Rim_Color` (Color / Alpha) | HDR rim tint; alpha is its strength multiplier |
| `_Shell_Rim_Strength` | rim brightness, 0–4 |
| `_Shell_Rim_Border` / `_Shell_Rim_Blur` | where the fresnel rim's smoothstep sits, and how wide its transition is |
| `_Shell_Rim_FresnelPower` | how tightly the rim hugs the silhouette — higher is thinner |
| `_Shell_Rim_VRParallaxStrength` | 0 puts the rim on the stereo-centre camera (both eyes see the same rim, flat but stable), 1 on the per-eye camera (parallaxes properly) |

**`DebugDisplay`** — a mode bar plus three sections. `_Display_Mode` picks **Billboard** (the plane faces the viewer), **Object** (the plane is fixed to the object's basis) or **UV** (the readout is laid into the mesh's `TEXCOORD0`).

| Property | What it does |
|---|---|
| `_Grid_Columns` × `_Grid_Rows` | the cell grid the entries land in, up to 12 cells; entries past the grid are not drawn |
| `_Total_Width` | layout width in **glyph advances**, not metres, so font size and layout stay independent. A cell needs 12 (label) + 10 (value) = 22 advances to avoid clipping; the inspector edits it per column (total ÷ columns), which is the number that decides whether a label clears its value |
| `_Font_Size` | metres per ascender **at unit scale** |
| `_Font_Scale_Relative` | on (default), `_Font_Size` is multiplied by the object's mean axis scale so text always fits its mesh; off restores the ancestor's absolute physical size. A single scalar, never per-axis — the plane basis is normalized so a stretched mesh cannot distort the monospace grid. UV mode ignores it (`_Font_Size` cancels out) |
| `_Text_Depth_Offset` | pushes the text plane fore/aft of the object origin, ±0.5 |
| `_Palette_0..3` | the four HDR text colours each entry chooses between |

Each of the twelve entries carries a **label**, a **value**, and a packed **format** — decimals, palette index, right-pad, and value source. The label is a string packed into a `Vector`; the format is a bitfield on a `[HideInInspector]` float. Both packings, the charset, and the enumerated value sources are a **managed echo of `Editor/DisplayGlyphs.cs`**, which is canon — read it rather than deriving anything here. Two facts an author cannot get from that file: **right-pad is not an align-decimals flag** — the value right-aligns to `cell_width − rpad`, so `rpad = max_decimals − entry_decimals` is what lines decimal points up down a grid column (the inspector's *Auto-align* button writes exactly that); and **labels are author-time only, by construction** — ShaderLab has no string property and animation curves carry floats, so no clip can ever drive text.

**`DebugOverlay`** — `_Probe_Mode` selects **Wireframe** (triangle edges) or **Normal** (reconstructed world normals). `_Overlay_Fullscreen` takes the probe over the whole frame instead of the mesh; `_Overlay_Screenspace_Vertex_Reorder` permutes which NDC corner each vertex id lands on, for a mesh whose winding puts them the wrong way round. Fullscreen has a mesh requirement — see §Traps.

**`GammaCrystal`** — grading, then the area it applies to.

| Property | What it does |
|---|---|
| `_Gamma_Adjust_Value` | the grade itself, ±5. Negative brightens, positive darkens |
| `_Transmit_Emission` | on, values above 1 bypass the **gamma** stage, so emissive surfaces stay emissive. Exposure is applied before the split and scotopic after it, so both still reach them |
| `_Exposure_Enable` / `_Exposure_Value` | an optional linear exposure stage, ±5 EV stops |
| `_Scotopic_Enable` / `_Scotopic_Strength` / `_Scotopic_Tint` | an optional desaturation toward a tint, modelling night vision |
| `_AoE_Scale_Relative` | on (default), the three distances below are multiplied by the object's **mean axis scale**, so the effect tracks the mesh you can see; off restores the ancestor's absolute metres, and then scaling or animating the object slides the visible sphere out of the region it bounds. A single scalar: the area of effect is spherical by construction, so scale the host uniformly |
| `_AoE_MinDistance` / `_AoE_MaxDistance` | metres from the sphere centre at which the grading is at full strength and at zero — the falloff band |
| `_Core_Radius` / `_Core_Intensity` | a denser inner region that reads as the bubble's core. **Authored per material against the mesh you are on, not derived** — the core is a feathered smoothstep, so the radius that reads as tracing the silhouette sits slightly outside the surface, and a non-spherical mesh has no single radius to derive from. Retune by eye; scale-relative handling then holds it at any object scale |
| `_Shell_Grading_Resist` | how much the shell resists **gamma and exposure** — 0 lets it go dark with the scene, 1 leaves it untouched and too bright. Scotopic tint is deliberately not resisted and always applies at full strength, because it is a hue shift rather than a brightness crush |

## Interface

**Params** — none, on any of the three. No animator, no synced parameters, no menu. Values arrive from the shader (render-side sources) or from a clip curve writing a material property.

**Seam** — none, and no framework component of any kind: each prefab is a bare root with the renderer under it, plus the `DepthLight` on the two that read depth. **Parent it where you want it to ride** — no shader here depends on a rest position, so nothing anchors one for you.

**Animation binding** — `DebugDisplay` only: `material._E{i}_Value`, `i` in 0..11, on the display's `MeshRenderer`. A plain clip curve; the shader is unlocked, so there is no Poiyomi `Animated`-tag step, and the material inspector has a copy button per path.

**Dependencies** — none. The shaders, the `ShaderGUI` inspectors and the `DisplayGlyphs` format canon they read all ship in this entry, so everything is editable on a bare install of this package alone.

**Required assets** — all shipped and self-contained: three shaders, four `.hlsl`, the glyph atlas, two cubemaps, `assets/DebugSphere.fbx`, three template materials.

## Traps

**Two of the three need a depth texture, and nothing on an avatar provides one.** `DebugOverlay` in both modes and `GammaCrystal`'s strength term read `_CameraDepthTexture`; in forward rendering Unity builds it for the screen-space shadow pass, so a **shadow-casting directional light** is what turns it on. Both sample prefabs carry a `DepthLight` child for exactly that — copy it wholesale rather than reconstructing its values, which the prefab holds. A world's own shadow-casting light populates the texture too, which is the trap in judging `DepthLight` redundant: it keeps working in the venue you tested and goes flat in the next one. Absence is silent — flat fill, uniform grading, no error.

**In the Editor, the Scene view's lighting toggle gates that whole mechanism.** With it off no scene light renders, `DepthLight` included, so the texture is never built and all three depth-derived effects read exactly like a broken install. `Shader.GetGlobalTexture("_CameraDepthTexture")` returning null confirms it and tracks the toggle both ways — but read it against the view you are judging: the global holds whatever camera rendered last, so a Game-view capture through a stock Main Camera leaves it null. That is a stale read, not damage; the next Scene-view render rebinds it.

**`DebugOverlay`'s fullscreen mode has a mesh requirement no material setting can satisfy.** The path assigns NDC corners by `SV_VertexID` 0–3 and sends higher ids to `nan`, so it needs a mesh whose first *two* triangles are drawn from those four vertices. Measured: a Unity **Cube** or **Quad** covers the frame; a Unity Plane draws nothing; this entry's `DebugSphere` survives one triangle and fills a diagonal half, which `_Overlay_Screenspace_Vertex_Reorder` moves but can never complete. Use a cube or quad for fullscreen, and keep the sphere for mesh mode — but note what you give up: `DebugSphere` carries six loose triangles at 20× its radius purely to inflate the renderer's bounds, and a stock cube or quad has none. A screen-space effect stops rendering the moment its small mesh leaves the frustum, which is exactly when the camera turns toward what it was covering, so inflate the replacement's bounds too.

**Scale the host mesh at import, not on the transform.** `DebugSphere.fbx` carries a 50× import scale (0.15 m sphere at unit scale) and the prefabs sit at scale 1. Hosting a small mesh at 50× to compensate instead multiplies `_AoE_MinDistance`, `_AoE_MaxDistance` and `_Core_Radius` by 50 as well — a 1 m falloff becomes 50 m, the grading never falls off inside any room, and the symptom is indistinguishable from a missing depth texture.

**Each `DebugDisplay` instance needs its own material,** because the author-time configuration is what collides: labels, formats, grid, mode and palettes all live on the material. The animated *value* does not collide — Unity drives `material._E{i}_Value` through a per-renderer `MaterialPropertyBlock`, measured — but do not lean on that, since it makes a shared-material setup look half-correct.

**`GammaCrystal` costs a `GrabPass`,** which the other two do not: one framebuffer copy per render, scaling with resolution rather than mesh. Prefer toggling it off to leaving it neutral — a neutral bubble still grabs.

**Object display mode reads correctly from the object's −Z side.** The text runs along +X, so an observer on +Z sees the grid mirrored. Turn the object around, or use billboard mode, which has no side.

**Camera and mirror behaviour deliberately differs across the three.** `DebugOverlay` suppresses only its fullscreen takeover in mirrors and the VRChat camera, still drawing on its mesh; `GammaCrystal` suppresses its *grading* in mirrors while its crystal shell keeps drawing, and the pair is deliberate: a mirror reflects a scene the bubble has already graded, so grading the reflection too would darken that region twice, while a shell that bailed would leave the object missing from its own reflection as you held it. It does grade the VRChat camera, because a scene grade is what a photo should capture. Changing one to match the other is a design decision, not a cleanup.

**Mesh merging can relocate any of this.** Optimizers key merge decisions off the avatar root, and wherever you parented these is not it. Measured against `d4rkAvatarOptimizer` at defaults on a composed humanoid, both displays were left alone — one optimizer at one setting, not a guarantee. Use the per-GameObject opt-out where a readout is load-bearing.

## Verifying the install

**`DebugDisplay`** — the readout's numbers should track the wearer moving. Stuck near `0.00` means the prefab is still sitting at the avatar-root origin — it ships unparented, so that reading is "never placed", not a fault. Mesh visible but text absent means an outgrown window (`Cull Back` makes the mesh a window, so oversized text is absent rather than clipped) — check `_Font_Scale_Relative` and `_Font_Size`; in UV mode check the mesh has `TEXCOORD0` first.

**`DebugOverlay`** — edges should move with the camera, not the mesh. A uniform flat fill responding to nothing is the depth texture missing, not a broken install.

**`GammaCrystal`** — walk toward it: the grading should deepen and reach full strength before you touch the sphere. No change at all usually means every stage is neutral (gamma 0, exposure and scotopic off returns the scene untouched — the inspector warns about this). Grading that is uniform everywhere is the object-scale trap above, before it is the depth texture.

**Any of the three** — a flat grey shell rather than a glassy one means the cubemap slot is empty or the texture imported as a `Texture2D`, so `samplerCUBE` receives nothing.

**To check whether a clip is driving a display entry, read the renderer's `MaterialPropertyBlock`, not the material.** `sharedMaterial.GetFloat("_E0_Value")` keeps returning the authored value while the display visibly animates; use `renderer.GetPropertyBlock(mpb)`. Never touch `renderer.material` on a live avatar — that instantiates it and changes what `sharedMaterial` compares equal to.

**What the Editor cannot show:** `VRChatCameraMode`, `VRChatMirrorMode` and `StereoEyeIndex` read 0 whether or not the globals exist, so the camera and mirror behaviours above are Editor-invisible, and the stereo-centre handling only manifests as per-eye disparity in a headset. `docs/verify.md` owns the general boundary.

## Shipped assets

Texture import settings are load-bearing and Unity's defaults are wrong for all three: the atlas must be uncompressed, non-sRGB and mip-free, and both cubemaps need `TextureCube` shape, Specular convolution, mips, and a trilinear filter. They are pinned only in the committed `.meta`s, every wrong value fails **silently** (a wrong reflection or a dead blur slider, never a pink material), and replacing a cubemap therefore means overwriting the PNG bytes and keeping the existing `.meta` — which also carries the GUID the materials resolve.

`tools/generate_atlas.ps1` regenerates the glyph atlas, parsing the charset out of `Editor/DisplayGlyphs.cs` and printing the `Font` constants to paste into `debug_display_common.hlsl`; its header carries the procedure. The cubemaps are shipped images with no generator — swap either for any 1:1 image, subject to the settings above.
