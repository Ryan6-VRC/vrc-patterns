# color-adjust — hue/color slider on the shader's own property (Pattern, study)

Two ways to give a user a hue/color slider by driving a shader's own property directly (no HSV→RGB compute pass — out of scope here): lilToon's vec4 `_MainTexHSVG` (three sliders composed in one WD-ON Direct tree) and Poiyomi's scalar `_MainHueShift` (one slider, one tree).

**Provenance:** generalized from vendor costume color-adjust clips.

## Ground truth

The vec4-driving mechanism: under WD-ON an un-keyed channel reverts to the material default, and per-channel Override layers fight (each writes the whole vec4, last wins), so the fix is one WD-ON Direct tree in which each slider's 1D sub-tree writes only its own channel plus a constant `.w`. `BrokenDemo` is the counterexample kept for study. Pattern tier, no seam shipped: a consumer adapts in order — **`RepathClips` first** onto their own renderer (placeholder paths `Body`/`BodyBroken`), **then** pair `basis: avatar-root` with the MA merge component's `pathMode` per `_template`, or the repathed bindings land on the wrong node.

## Traps — Dependencies

The lilToon sliders require the target material to be lilToon (`_MainTexHSVG` is lilToon-only); `HueShift` requires Poiyomi (`_MainHueShift`). By-name property binding is inert — silently does nothing — on a renderer whose material is the wrong shader. **lilToon is necessary and not sufficient for Hue and Sat:** tone correction applies to the sampled `_MainTex` alone (`lil_common_frag.hlsl:312-317`) and `_Color` multiplies in after it (`:357`), so where the color lives in the `_Color` tint over a white or greyscale texture the RGB→HSV step sees saturation 0, the hue add and the saturation multiply are both inert, and the tint rides through untouched — Val is a straight brightness multiply and is the one leg that still works. The hue must live in the texture. A second precondition on the same property: `_MainTexHSVG` compiles out where `LIL_FEATURE_MAIN_TONE_CORRECTION` is undefined (`:315`), which only a hand-narrowed Shader Setting pass produces — stock lilToon defines it, and lilToon's own optimizer re-enables it for any material holding a non-default HSVG.

## Behavior

`_MainTexHSVG` against a lilToon default of `(0, 1, 1, 1)`. To re-measure after an edit, read the renderer's `MaterialPropertyBlock`, not `sharedMaterial`, which stays at the authored value and reads as a false negative (`docs/verify.md`). A correct install with Hue=0.6, Sat=0.4, Val=0.9 yields `(0.6, 0.4, 0.9, 1.0)` — all three sliders take effect at once, no fight. The trap: `Broken_HueOnly_RevertsUnkeyed` (keys only `.x=1`) yields `(1, 1, 1, 1)` — the un-keyed `.y`/`.z`/`.w` took the **material default**; here the default happens to equal the intended hold so the damage is invisible, but on a material whose default differs (a pre-saturated body) the same clip would silently reset saturation.
