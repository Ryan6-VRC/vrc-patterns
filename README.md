# vrc-patterns

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced
(`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by pattern

Keyed by capability — find the row that does what you need and jump to its entry. This table is the
per-entry index for the library; `docs/gimmicks.md` is the durable techniques doc and routes here as a
whole, not entry-by-entry.

| Capability | Tier | Entry |
|---|---|---|
| Hue / color slider (drive shader property) | Pattern (study) | [`color-adjust`](color-adjust/) |
| HSV→RGB compute (write RGB color) | Pattern (study) | [`hsv-rgb`](hsv-rgb/) |
| DBT math (add/subtract/multiply/divide/clamp/remap, min/max, smoothing, frametime) | Pattern (study) | [`blendtree-math`](blendtree-math/) |
| AAP exponential smoother (frametime-aware) | Pattern (study) | [`smooth-frametime`](smooth-frametime/) |
| Grab a prop, world-drop it, re-grab in place (0-bit drop) | Module | [`grabprop`](grabprop/) |
| — reference mold — | Module | [`_template/`](_template/) |

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in
  `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + validates every entry and checks controller decompile-equality for entries
with `built/`. Run it before merging.
