# _template — reference mold (Module tier)

A minimal one-param toggle. Copy this folder to start a new entry; it demonstrates every part of the
skeleton, including the standard Module packaging. Not a shipping gimmick — a proof and a mold.

**Provenance:** authored for scaffolding; no upstream asset.

## Interface

- **Params:** `Template_Toggle` (bool, in) — synced, unsaved. Drives the `Cube` renderer on/off.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔
  `basis: mount-root`) merging `built/Template_Fx.controller` + `built/Template_Fx_Parameters.asset`
  (`prms`), with `Template_Toggle` in `globalParams`; a VRCFury `Toggle` (`useGlobalParam`) is the
  menu front. CompileController is frame-blind, so the pairing is load-bearing: the merged clip binds
  `Cube/MeshRenderer.enabled` relative to the prefab root, so the toggled mesh must sit at child
  path `Cube`.
- **Dependencies:** none (self-contained).
- **Required assets:** none — `Cube` uses Unity's built-in default material. `assets/` holds owned
  self-contained content when an entry ships any (see `contact-tracker`'s `World.prefab`).
