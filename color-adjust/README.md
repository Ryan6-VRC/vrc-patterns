# color-adjust — hue/color slider on the shader's own property (Pattern, study)

Two ways to give a user a hue/color slider by driving a shader's own property directly (no HSV→RGB
compute pass — that approach is out of scope for this entry): lilToon's vec4 `_MainTexHSVG` (three
sliders composed in one WD-ON Direct tree) and Poiyomi's scalar `_MainHueShift` (one slider, one tree).

**Study entry:** this entry commits `built/` so the compose Direct tree and the counterexample layer are
legible in the Animator window (CONVENTIONS permits this for a declared study/reference entry).

**Provenance:** generalized from vendor costume color-adjust clips.

## Interface

- **Params:** `HueSlider`, `SatSlider`, `ValSlider`, `HueShift` — all float, in, synced + saved.
  `HueSlider`/`SatSlider`/`ValSlider` drive the lilToon `_MainTexHSVG` channels `.x`/`.y`/`.z` (defaults
  0/1/1); `HueShift` drives the Poiyomi `_MainHueShift` scalar (default 0). `ShowBroken` — bool, in,
  synced + saved — toggles the `BrokenDemo` layer between a correct clip and the counterexample (below).
  `One` — float, constant `1.0`, never driven — is the full-weight helper for the Direct compose tree;
  leave it at its default.
- **Seam:** none shipped — this is Pattern tier, lifted as YAML. A consumer adapts in two steps, in
  order: **`RepathClips` first**, to repoint the `Body/SkinnedMeshRenderer` (and `BodyBroken`) placeholder
  paths at their own renderer; **then** honor the merge frame — `basis: avatar-root` must pair with the MA
  merge component's `pathMode` the same way the `_template` entry documents, or the repathed bindings land
  on the wrong node.
- **Dependencies:** shader family, by property name, not declared elsewhere — the lilToon sliders
  (`HueSlider`/`SatSlider`/`ValSlider`) require the target material to be lilToon (`_MainTexHSVG` is a
  lilToon-only vec4 property); the Poiyomi slider (`HueShift`) requires a Poiyomi material
  (`_MainHueShift`). By-name property binding is inert — silently does nothing — on a renderer whose
  material is the wrong shader.
- **Required assets:** none.

## Driving a vec4: the two facts that pull against each other

`_MainTexHSVG` is one vec4 property with four channels packed together, but the animator only keys
individual float channels. Two facts govern how you drive it, and they conflict:

1. **Un-keyed channels revert.** Under WD-ON, a channel a clip does not key snaps to the material's
   serialized default — it is *not* held at whatever it was. So a naive "hue clip" that keys only `.x`
   silently resets saturation and value.
2. **Per-channel Override layers fight.** Give each of H/S/V its own Override layer and every layer
   writes the whole vec4, so the last override layer wins all four channels and the earlier sliders go
   dead — one slider ends up controlling the material and the rest are inert.

**The fix satisfies both: one WD-ON Direct tree in which each slider's 1D sub-tree writes only its own
channel** (`.x`, or `.y`, or `.z`), plus a constant `.w`. Each channel has exactly one writer, so the
three sliders compose (no override fight) and every channel is always written (no revert). This is the
`blendtree-math` "stack independent writes in one Direct tree" idiom applied to a vec4.

The `BrokenDemo` layer keeps the counterexample for study, on its own placeholder mesh (`BodyBroken`) so
it can't clobber the compose layer: `broken-hue_only_x` keys only `.x`; `ShowBroken` toggles it against
`broken_baseline` (all four channels), making fact 1 directly observable.

## Behavior

`_MainTexHSVG` against a lilToon default of `(0, 1, 1, 1)`. To re-measure after an edit, read the
renderer's `MaterialPropertyBlock` — material animation lands there, and `sharedMaterial` stays at
the authored value and reads as a false negative (`docs/verify.md`):

- **Each slider drives only its channel:** HueSlider=0.8 → `(0.8, 1, 1, 1)`; SatSlider=0.3 →
  `(0, 0.3, 1, 1)`; ValSlider=0.2 → `(0, 1, 0.2, 1)`.
- **The three compose:** Hue=0.6, Sat=0.4, Val=0.9 → `(0.6, 0.4, 0.9, 1.0)` — all three take effect at
  once.
- **The trap:** driving `broken-hue_only_x` (keys only `.x=1`) yields `(1, 1, 1, 1)` — the
  un-keyed `.y`/`.z`/`.w` took the **material default** `(1, 1, 1)`, confirming fact 1. Here the default
  happens to equal the intended hold, so the damage is invisible; on a material whose default differs
  (a pre-saturated body, say), the same clip would silently reset saturation. Treat any clip that
  doesn't account for every channel it means to hold as unsafe.
