# hsv-rgb — compute RGB from H/S/V and write a plain color property (Pattern, study)

Compute an RGB colour from `H`/`S`/`V` sliders and write it into a shader's plain `_Color`, for shaders that expose only a flat colour and no hue property of their own (the case `color-adjust` — which drives a shader's **own** hue channel, lilToon `_MainTexHSVG` or Poiyomi `_MainHueShift` — puts out of scope). Pure feed-forward (no feedback), so it just settles ~2–3 frames after an input change — oscillation is structurally impossible.

**Provenance:** generalized from the standard HSV→RGB algorithm, re-expressed as blend-tree math — no real-avatar naming.

## Ground truth

- Parameters, the tree, and the clips are `controller.yaml`. Its header is the design record and carries the whole lesson: the multiplicative `RGB = m + C·hue(H)` decomposition that dissolves the six-sector algorithm into 1D trapezoid keys, the WD-ON weight-deficit trap and the `(1−V)` sink that closes it, the one-writer-per-channel rule, and why the binding suffix is `.r`/`.g`/`.b`/`.a` rather than `.x`/`.y`/`.z`/`.w`. Read it before adapting anything here.
- `H`/`S`/`V` ship **not synced and not saved** — a consumer decides both.
- **Output:** the target material's `_Color`, written **by name** as per-channel material curves on a placeholder renderer path (`Body/SkinnedMeshRenderer`).
- **Seam** — a consumer adapts in two steps, in this order: **`RepathClips` first**, to repoint the placeholder renderer path at their own renderer; **then** pair `basis: avatar-root` with the MA merge component's `pathMode` per `_template`, or the repathed bindings land on the wrong node. Nothing ships as a seam — this is Pattern tier, lifted as YAML.
- **Dependencies:** the target renderer must expose an RGB `_Color` property. By-name binding is inert — silently does nothing — on a material lacking it. The Unity Standard material used in the measurement below is a scaffold, not a shipped asset; the consumer supplies their own.

## Behavior

`_Color` after an 8-frame settle, against a Unity Standard default of white. To re-measure after an edit, host the built controller on a bare `Animator` and tick it in edit mode (`docs/emulator.md` §"Pure controller math skips play mode entirely"), reading `_Color` from the renderer's **`MaterialPropertyBlock`** — `sharedMaterial` stays at the authored default and reads as a false negative.

| row | `H` | `S` | `V` | `_Color` `(.r, .g, .b, .a)` |
|---|---|---|---|---|
| desaturated (S=0.5) | 2/6 | 0.5 | 1 | (0.5000, 1.0000, 0.5000, 1.0000) |
| dimmed (V=0.5) | 4/6 | 1 | 0.5 | (0.0000, 0.0000, 0.5000, 1.0000) |

- **The sink fix:** the dimmed row reads `(0, 0, 0.5)`, not the `(1−V)·white = 0.5` bleed a missing sink would inject; the desaturated row reads `(0.5, 1, 0.5)`, its floor `m = V(1−S) = 0.5` filled by the `m` child rather than the default.
- **Binding lands:** both computed rows differ from the cloned material's default white `(1,1,1,1)`, which rules out a wrong `.x`/`.y`/`.z` suffix — that would read all-default on the MPB — and confirms the `.r`/`.g`/`.b` writes reach the material.
