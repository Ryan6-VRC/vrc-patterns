# _template — reference mold (Module)

A minimal one-param toggle: drive `Template_Toggle` and a `Cube` renderer follows. Copy this folder to start a new entry — it demonstrates the skeleton and the standard Module packaging, not a shipping gimmick.

**Provenance:** authored for scaffolding; no upstream asset.

## Ground truth

- **Parameters and behavior:** `controller.yaml` — `basis`, `role`, the `Template_Toggle` bool, and its clip. The prefab's `globalParams` publishes `Template_Toggle` under that bare name.
- **Wiring:** the prefab. A VRCFury `FullController` (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`) merges `built/`; a VRCFury `Toggle` (`useGlobalParam`) is the menu front.
- **Seam fact no artifact states:** CompileController is frame-blind, so the merged clip binds `Cube/MeshRenderer.enabled` relative to the prefab root — the toggled mesh must sit at child path `Cube`. Move it and the toggle drives nothing, silently.

## Verifying the install

Drive `Template_Toggle` and watch the `Cube` renderer follow. If the toggle moves but nothing renders, the merged clip is binding somewhere other than child path `Cube` — the frame pairing in **Ground truth** is what went wrong.

Write this slot for the agent installing the entry, never as a log of past runs — `CONVENTIONS.md` §The README has the rule.
