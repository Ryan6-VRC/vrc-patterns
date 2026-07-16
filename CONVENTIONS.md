# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace.
YAML is the source of truth; built Unity assets are regenerable.

## An entry is a folder

    <entry-name>/
      README.md          # prose + the Interface stanza + provenance
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters
      built/             # committed when a GUID references it, OR for a declared study/reference entry (see tiers): .controller (+ *_Parameters.asset) (+ .meta)
      assets/            # owned, self-contained materials/meshes
      <entry>.prefab     # the drop-in, referencing built/ by GUID via an MA/VRCFury merge component

## Tier is derived, not assigned

The one axis that changes behavior: **does the entry ship a GUID-consumer** (a prefab/asset that
references `built/`)? Read it off which files exist:

- **Pattern** — `controller.yaml` only. No `built/`: an agent lifts the YAML and recompiles in its
  own project with its own GUID. Committing `built/` here is review noise UNLESS the entry is a
  declared study/reference entry — then `built/` is the point (a DBT graph is legible only in the
  animator window), and the gate holds it to decompile-equality like any `built/`.
- **Asset-bound** — adds `assets/`. `built/` committed (an asset references it).
- **Module** — adds `<entry>.prefab` (one or more prefab variants). `built/` committed; the prefab
  references it by GUID.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries
what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — which framework merges it (MA `MergeAnimator` vs VRCFury `FullController`), the anchor,
  and the **binding frame the merge resolves**: MA `basis:` ↔ `pathMode`; VRCF resolves per binding
  relative to the component's object (`rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`), plus any
  `rewriteBindings`. CompileController is frame-blind, so this is load-bearing — record it.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

## Module tier

A Module entry is a drop-in gimmick: the prefab composes onto an avatar and ships its own menu front
(`gimmicks.md` §Packaging — enable/options/failsafe inside the module, never left to the consumer).

- **Seam ruling:** VRCFury (`FullController`/`Toggle`/`ApplyDuringUpload`) for behavior; MA `BoneProxy`
  only for anchors whose placement must be visible while authoring (VRCF ArmatureLink snaps at build).
  **Invariant:** VRCF-animated clip bindings live on the prop subtree and never path through an
  MA-moved node — the build-time reparent breaks them silently. Pure-VRCF is the default when no
  anchor needs edit-time placement (`grabprop`).
- **Variants** are prefab-level only (shape/size/anchor overrides) and share the entry's one
  `controller.yaml` + `built/`. A variant that changes clips or receiver count is its own entry,
  never a second controller in the folder (the controller-fork drift trap).
- **Params:** sensing params (contact/PB outputs) never synced, saved, or menu-exposed; the enable is
  synced-unsaved (off-is-reset). The Toggle/menu component is the sync authority for its param;
  `built/*_Parameters.asset` is legibility only.
- **No prefab builder.** The `<entry>.prefab` is the shipped artifact and its own source — the entry
  README's rig/constants section plus `controller.yaml` carry what a rebuild needs. Don't commit a
  regenerator script: reflection against a framework's internal model (VRCFury `VF.Model.*`) rots
  unrun and then lies about reproducing. Capture construction as prose; promote a genuinely reusable
  recipe to shared tooling, not per-entry `dev~/`.

## Asset-closure rule

VPM's identical-GUID-everywhere property holds only for in-package GUIDs. **Ship self-contained simple
materials** (Unity Standard or a VPM-pinnable shader) — never a Poiyomi/lilToon dependency in library
content (Poiyomi is not VPM-pinnable; a consumer without it gets pink materials). Any unavoidable
external dependency is declared loudly in the Interface stanza.

## The gate

`tools/gate.ps1` is the admission bar — compile + round-trip + decompile-equality per entry. It does
**not** check the `*_Parameters.asset`, so keep that `vrc:` synced/saved surface in step with the YAML by hand.

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is
**public**: scrub project specifics, paths, and real names; the "Remy" persona is acceptable.
