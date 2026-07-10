# vrc-patterns

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced
(`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by pattern

Left column = the pattern name as it appears in `docs/gimmicks.md`, so you can jump straight from
concept to implementation. (Substrate patterns whose canonical YAML lives in
`vrc-unity-tools/fixtures/animator-substrate/` are linked, not copied.)

| Pattern (`gimmicks.md`) | Tier | Entry |
|---|---|---|
| _(seed entries land here in a later session)_ | | |
| — reference mold — | Module | [`_template/`](_template/) |

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** this package is listed in a project's `vpm-manifest.json`; entries import at
  `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + lints every entry and checks decompile-equality for entries with `built/`.
Run it before merging.
