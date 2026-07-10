# _template — reference mold (Module tier)

A minimal one-param toggle. Copy this folder to start a new entry; it demonstrates every part of the
skeleton. Not a shipping gimmick — a proof and a mold.

**Provenance:** authored for scaffolding; no upstream asset.

## Interface

- **Params:** `Template_Toggle` (bool, in) — synced, saved. Drives the `Cube` renderer on/off.
- **Seam:** MA MergeAnimator on the prefab root, `layerType: FX`; `basis: avatar-root` ↔ MA
  `pathMode: Relative`. CompileController is frame-blind, so this pairing is load-bearing: the merged
  clip binds `Cube/MeshRenderer.enabled` relative to the merge root, so the toggled mesh must sit at
  child path `Cube`.
- **Dependencies:** none (self-contained).
- **Required assets:** `assets/Template_Mat.mat` (Unity `Standard` shader — self-contained, no
  Poiyomi/lilToon).
