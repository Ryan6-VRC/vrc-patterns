# _template — reference mold (Module)

A minimal one-param toggle. Copy this folder to start a new entry; it demonstrates every part of the skeleton, including the standard Module packaging. Not a shipping gimmick — a proof and a mold.

**Provenance:** authored for scaffolding; no upstream asset.

## Ground truth

- Parameters, states, and clips: `controller.yaml`. The set published to the host avatar: the prefab's VRCFury `FullController` `globalParams`. Everything else about the rig: `Template.prefab`.
- Dependencies: none.
- The seam is that `FullController` (FX), pairing `rootBindingsApplyToAvatar: 0` with `basis: mount-root`. CompileController is frame-blind, so no artifact states the pairing and it is load-bearing: the merged clip binds `Cube/MeshRenderer.enabled` relative to the prefab root, so **the toggled mesh must sit at child path `Cube`**. Mount it anywhere else and the parameter moves while nothing renders.
- `Cube` uses Unity's built-in default material, so the entry ships no `assets/`; an entry that ships owned self-contained content puts it there (`contact-tracker`'s `World.prefab`).

## Traps

- **Copying this folder copies its `built/` GUIDs.** Re-GUID the copy's `built/` `.meta`s and repoint the copy's prefab in the same edit — the gate names both entries as offenders otherwise (`CONVENTIONS.md` §An entry is a folder).

## Verifying the install

Drive `Template_Toggle` and watch the `Cube` renderer follow it. If the parameter moves but nothing renders, the merged clip is binding somewhere other than the child path `Cube` — the frame pairing under **Ground truth** is what went wrong.

Write this slot for the agent installing the entry, never as a log of past runs — `CONVENTIONS.md` §The README has the rule.
