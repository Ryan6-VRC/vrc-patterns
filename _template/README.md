# _template — reference mold (Module)

A minimal one-param toggle: drive `Template_Toggle` and a `Cube` renderer follows. Copy this folder to start a new entry — it demonstrates the skeleton and the standard Module packaging, not a shipping gimmick.

**Provenance:** authored for scaffolding; no upstream asset.

The one non-obvious thing: CompileController is frame-blind, so the merged clip binds `Cube/MeshRenderer.enabled` relative to the prefab root (`basis: mount-root` ↔ the FullController's `rootBindingsApplyToAvatar: 0`). The toggled mesh must sit at child path `Cube`; move it and the toggle drives nothing, silently. If the toggle moves but nothing renders, that pairing is what went wrong.
