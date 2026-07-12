# vrc-patterns

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced
(`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by pattern

Left column = the pattern name as it appears in `docs/gimmicks.md`, so you can jump straight from
concept to implementation.

| Pattern (`gimmicks.md`) | Tier | Entry |
|---|---|---|
| Hue / color slider (drive shader property) | Pattern (study) | [`color-adjust`](color-adjust/) |
| HSV→RGB compute (write RGB color) | Pattern (study) | [`hsv-rgb`](hsv-rgb/) |
| DBT math (add/subtract/multiply/divide/clamp/remap, min/max, smoothing, frametime) | Pattern (study) | [`blendtree-math`](blendtree-math/) |
| AAP exponential smoother (frametime-aware) | Pattern (study) | [`smooth-frametime`](smooth-frametime/) |
| — reference mold — | Module | [`_template/`](_template/) |

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in
  `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + validates every entry and checks controller decompile-equality for entries
with `built/`. Run it before merging.
