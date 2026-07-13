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
- **Module** — adds `<entry>.prefab`. `built/` committed; the prefab references it by GUID.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries
what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — MA MergeAnimator vs VRCFury FullController, the anchor, and the binding frame
  (`basis:` ↔ MA `pathMode`). CompileController is frame-blind, so the merge component's frame is
  load-bearing — record it.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

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
