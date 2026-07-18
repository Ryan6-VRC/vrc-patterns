# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace.
YAML is the source of truth; built Unity assets are regenerable.

The general avatar-tooling doctrine an entry *embodies* — module seams and the build-order that
constrains them, gimmick packaging, graph-layout legibility, the binding schema — lives in the
workspace docs (`nondestructive.md`, `gimmicks.md`, `animator-schema.md`). This file is only the
mechanics a contributor **to vrc-patterns itself** needs: the entry's shape on disk, the README
Interface slot, and the gate.

## An entry is a folder

    <entry-name>/
      README.md          # prose + the Interface stanza + provenance
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters
      built/             # committed when a GUID references it, OR for a declared study/reference entry (see tiers): .controller + *_Parameters.asset (+ .meta)
      assets/            # owned, self-contained assets the entry ships (meshes, reference prefabs, materials)
      <entry>.prefab     # the drop-in, referencing built/ by GUID via an MA/VRCFury merge component

## Tier is derived, not assigned

One axis changes an entry's shape: **does it ship a GUID-consumer** (a prefab/asset referencing
`built/`)? Read it off which files exist — the gate keys off the same signal (any prefab/`assets`/`built`
entry must ship a built controller per document). Two shapes exist:

- **Pattern** — `controller.yaml`, plus `built/` for the study/reference form (which every current
  Pattern is): a DBT graph is legible only in the animator window, so `built/` is committed and held to
  decompile-equality like any `built/`. A pure lift-and-recompile Pattern would ship `controller.yaml`
  alone — none exist yet.
- **Module** — adds `<entry>.prefab` (one or more variants), and `assets/` when it ships owned
  meshes/materials. `built/` committed; the prefab references it by GUID.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries
what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — which framework merges it (MA `MergeAnimator` vs VRCFury `FullController`), the anchor,
  and the **binding frame the merge resolves** (MA `basis:` ↔ `pathMode`; VRCF per-binding,
  `basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`). CompileController is frame-blind, so this is
  load-bearing — record it; `nondestructive.md` owns the frame mechanics and the build-order that makes
  the seam choice matter.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

## The gate

`tools/gate.ps1` is the admission bar — compile + round-trip + decompile-equality per entry. It does
**not** check the `*_Parameters.asset` — regenerate `built/` as a unit (controller + params asset,
over the committed `.meta`s so GUIDs hold) whenever the YAML changes.

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is
**public**: scrub project specifics, paths, and real names; the "Remy" persona is acceptable.
