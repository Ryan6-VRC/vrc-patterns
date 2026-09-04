# hsv-rgb — compute RGB from H/S/V and write a plain color property (Pattern, study)

Compute an RGB colour from `H`/`S`/`V` sliders and write it into a shader's plain `_Color`, for shaders that expose only a flat colour and no hue property of their own (the case `color-adjust` — which drives a shader's **own** hue channel, lilToon `_MainTexHSVG` or Poiyomi `_MainHueShift` — puts out of scope). Pure feed-forward (no feedback), so it just settles ~2–3 frames after an input change; oscillation is structurally impossible.

**Provenance:** generalized from the standard HSV→RGB algorithm, re-expressed as blend-tree math — no real-avatar naming.

## Ground truth

The output is the target material's `_Color`, written **by name** as per-channel material curves on a placeholder renderer path (`Body/SkinnedMeshRenderer`).

**Seam:** shipped as YAML only (Pattern tier), so a consumer adapts in two steps, in order — **`RepathClips` first**, to repoint the placeholder renderer path at their own renderer; **then** pair `basis: avatar-root` with the MA merge component's `pathMode` per `_template`, or the repathed bindings land on the wrong node.

**Dependencies:** the target renderer must expose an RGB `_Color` property; by-name binding is inert — silently does nothing — on a material lacking it. The Unity Standard material below is only a scaffold, not a shipped asset; the consumer supplies their own.

## Two traps the naive author gets wrong

- **Every channel must be written every frame.** `.r`/`.g`/`.b`/`.a` each get one root child (floor + hue + sink); an unwritten channel reverts to the material default under WD-ON. One tree, not one Override layer per channel, so the channels also don't fight (`color-adjust` fact 2).
- **The binding suffix is `.r`/`.g`/`.b`/`.a`, not `.x`/`.y`/`.z`/`.w`.** `_Color` is a *Color* property; `color-adjust`'s `.x`/`.y`/`.z` worked only because `_MainTexHSVG` is a *Vector*. `_Color.x` parses and lints clean but the by-name write lands on nothing (a wrong suffix on a Color is silently inert).

## Behavior

`_Color` after an 8-frame settle, against a Unity Standard default of white. To re-measure after an edit, host the built controller on a bare `Animator` and tick it in edit mode (`docs/emulator.md` §"Pure controller math skips play mode entirely"), reading `_Color` from the renderer's **`MaterialPropertyBlock`** — `sharedMaterial` stays at the authored default and reads as a false negative.

| row | `H` | `S` | `V` | `_Color` `(.r, .g, .b, .a)` |
|---|---|---|---|---|
| desaturated (S=0.5) | 2/6 | 0.5 | 1 | (0.5000, 1.0000, 0.5000, 1.0000) |
| dimmed (V=0.5) | 4/6 | 1 | 0.5 | (0.0000, 0.0000, 0.5000, 1.0000) |

- **The sink fix:** the dimmed row reads `(0, 0, 0.5)`, not the `(1−V)·white = 0.5` bleed a missing sink would inject; the desaturated row reads `(0.5, 1, 0.5)`, its floor `m = V(1−S) = 0.5` filled by the `m` child rather than the default.
- **Binding lands:** both computed rows differ from the cloned material's default white `(1,1,1,1)`, which rules out a wrong `.x`/`.y`/`.z` suffix — that would read all-default on the MPB — and confirms the `.r`/`.g`/`.b` writes reach the material.
