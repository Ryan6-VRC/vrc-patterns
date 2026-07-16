# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace.
YAML is the source of truth; built Unity assets are regenerable.

## An entry is a folder

    <entry-name>/
      README.md          # prose + the Interface stanza + provenance
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters
      built/             # committed when a GUID references it, OR for a declared study/reference entry (see tiers): .controller + *_Parameters.asset (+ .meta)
      assets/            # owned, self-contained assets the entry ships (meshes, reference prefabs, materials)
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
  anchor needs edit-time placement (`grab-prop`).
- **Variants** are prefab-level only (shape/size/anchor overrides) and share the entry's one
  `controller.yaml` + `built/`. A variant that changes clips or receiver count is its own entry,
  never a second controller in the folder (the controller-fork drift trap).
- **Params:** sensing params (contact/PB outputs) never synced, saved, or menu-exposed; the enable is
  synced-unsaved (off-is-reset). The YAML `vrc:` block is the source of truth; the compiler emits it
  as `built/*_Parameters.asset` and the prefab's FullController **merges that asset (`prms`)** — the
  prefab a human studies is self-describing, and complex entries will need the merge anyway. Intent
  params ride `globalParams` (stable OSC-facing names; sensing stays instance-prefixed).
- **Menu front:** a VRCFury `Toggle` driving the global enable (`useGlobalParam`), never a
  hand-authored `VRCExpressionsMenu` asset — the Toggle's menu placement is a string path, so moving
  a control into a submenu is an edit, not nested-menu-asset surgery. The Toggle references its
  enable by name (`globalParam`), not by declaring it — so that name must be the one the FullController
  exports via `globalParams` (the `prms` param the enable rides — above). A Toggle param absent from
  `globalParams` leaves `RewriteParamName` free to instance-prefix the controller's copy while the
  Toggle drives the bare name: a stranded toggle, no build error.
- **No prefab builder.** The `<entry>.prefab` is the shipped artifact and its own source — the entry
  README's rig/constants section plus `controller.yaml` carry what a rebuild needs. Don't commit a
  regenerator script: reflection against a framework's internal model (VRCFury `VF.Model.*`) rots
  unrun and then lies about reproducing. Capture construction as prose; promote a genuinely reusable
  recipe to shared tooling, not per-entry `dev~/`.

## Naming: rest modes and anchors

Prop-family entries name states by **where the prop rests / who carries it**, and constraint-source
attachment GOs as `<X>Anchor` (`HomeAnchor`); future multi-anchor entries extend the family
(`gimmicks.md` "Anchor multiplexer"):

- **Grabbed** — carried by the grab physbone (native sync).
- **Anchored** — active constraint source to a named anchor GO; re-derivable, late-syncs.
- **Dropped** — disabled/zero-source constraint holding its transform (world-frozen); no late-sync.
- **Tracked** — crawler cage chasing a latched sender; no late-sync.

The off-state is named by what off *does* — `Disabled` (hides the module) and `Reset` (parks it
home) are different behaviors; don't force one word onto both. Transient states name their event
(`Released`, `Searching`, `Timer`, `Waiting`). State names must not be YAML literals — `On`/`Off`
parse as booleans (`animator-schema.md`).

## Asset-closure rule

VPM's identical-GUID-everywhere property holds only for in-package GUIDs. **Ship self-contained simple
materials** (Unity Standard or a VPM-pinnable shader) — never a Poiyomi/lilToon dependency in library
content (Poiyomi is not VPM-pinnable; a consumer without it gets pink materials). A material is shipped
only when it carries content: placeholder primitives (swap-me payload spheres, demo cubes) use Unity's
built-in default material, not an owned stock `.mat`. Any unavoidable external dependency is declared
loudly in the Interface stanza.

## The gate

`tools/gate.ps1` is the admission bar — compile + round-trip + decompile-equality per entry. It does
**not** check the `*_Parameters.asset` — regenerate `built/` as a unit (controller + params asset,
over the committed `.meta`s so GUIDs hold) whenever the YAML changes.

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is
**public**: scrub project specifics, paths, and real names; the "Remy" persona is acceptable.
