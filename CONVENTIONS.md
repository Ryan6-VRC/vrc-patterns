# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace. YAML is the source of truth; built Unity assets are regenerable.

Doctrine an entry *embodies* — seams, build order, gimmick packaging, the binding schema — lives in the workspace docs (`nondestructive.md`, `gimmicks.md`, `animator-schema.md`). This file is only what a contributor **to vrc-patterns itself** needs: the entry shape, the README slots, the gate.

## An entry is a folder

    <entry-name>/
      README.md          # human lead + provenance + Ground truth + traps + measured (§The README); routes to source, never restates it
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters, menu
      built/             # committed when a GUID references it, or for a declared study entry: .controller + *_Parameters.asset (+ *_Menu.asset) + .meta
      assets/            # owned, self-contained assets the entry ships
      <entry>.prefab     # the drop-in, referencing built/ by GUID via an MA/VRCFury merge component

**Commit a prefab as an Editor saved it.** VRCFury back-fills resolved `id`s beside each `objRef` on first inspection; commit that diff rather than reverting it (an empty `id` makes it recur), and the cached path must name the package, never a venue.

**Entries may nest** (variant builds take subfolders; every composition is a nested entry, and a nested entry is a full entry), but `built/` and `assets/` may not hold one — the gate ignores those directories, so an entry misfiled there is silently never gated.

**No two committed `.meta` under one top-level tree may declare the same GUID.** After copying an entry, re-GUID the copy's `built/` `.meta`s and repoint its prefab in the same edit; the gate names both offenders.

## Tier is derived, not assigned

One axis: does the entry ship a GUID-consumer referencing `built/`? Read the tier off which files exist.

- **Pattern** — `controller.yaml`, plus `built/` in the study form (every current Pattern): a DBT graph is legible only in the animator window.
- **Module** — adds `<entry>.prefab` (+ `assets/`).
- **Structural Module** — prefab only, no `controller.yaml`, no `built/`: behaviour lives in the prefab's components or an owned **non-animator** asset it references (the exclusion keeps `built/` from qualifying and dissolving the axis). Nothing compiles, and a shader-carried entry's assets have **no standing check** — correctness rests on the README install check.

## `compositions/`

A composition is a runnable arrangement of two or more entries, committed as a prefab rather than written up (prose is lossy about arrangement); gated as an entry but not a library entry — not catalogued, not lifted. A configuration that differs from an entry — a composition, a variant build — is a **prefab variant** of that entry's prefab wherever it shares the entry's rig, so the shared nodes are inherited rather than copied and an entry-side retune reaches them. Customising a VRCFury component on a variant is whole-component **remove-and-add**, never a property override on the inherited one; `../docs/nondestructive.md` owns why an override there does not survive a build. It does not stamp the entry commits it was built against: the entries are checked out beside it, so git already holds that state.

- **Never a vendor base.**
- It may carry its own generated build of a composed entry, at its own CONFIG: drive the entry's generator unmodified and deviate after (a forked copy is a second canon), and regenerate that `built/` like any other — never hand-tune it.

## The README

One document, two readers, one direction of trust: the lead is for a human deciding whether to build this; everything after exists only because the artifacts cannot say it. **An agent must never be able to satisfy from this file a lookup the source could answer** — if `controller.yaml`, `generate.py`, or the prefab can answer the question, the README routes there and stops. The catalog row's "Build this" cell is the lead's one-line compression, and the title carries the bare tier in parens.

Slots, in order:

- **Lead** — what a consumer *gets*, the packaged novelty, its synced-bit cost; describe, don't sell. Human register.
- **Provenance** — ancestry and attribution (§Provenance / PII; mandatory).
- **Ground truth** — a few lines naming which artifact owns what: parameters and behavior in `controller.yaml` (where the YAML is generator-emitted, `generate.py` owns it and its docstring is the design record), the published set in the prefab's `globalParams`, wiring in the prefab. Seam facts no artifact can state — a binding-frame pairing, an anchor rule, a consumer wiring step that ships as an empty reference — are stated here as facts with their failure signatures, and never behind a leading "none": a bullet that opens with "none" must also end there.
- **Traps** (or **Before you compose it**) — the agent-facing slot: what goes wrong, its symptom, and the site to check. Also the sanctioned home for domain knowledge demoted from `docs/` (`tool-design.md`'s ladder routes a measured surface to the entry that measured it).
- **Measured** — empirical constants and behavior figures. Every figure carries its method and venue, and is either pinned by the entry's `--check` or replaced by a route to its authoring site (name the knob, the direction, the relation): pinned or routed, no third state.
- **Verifying the install** (Module) or **Behavior** (Pattern) — unchanged remit: the cheapest observable distinguishing a correct install from a plausible broken one, plus what the emulator cannot show. For a Structural Module this section is the entry's only standing check, and says so.

No slot may carry: a parameter-by-parameter interface enumeration, prose narration of the state machine or solver, or transcriptions of serialized component values. A **Rig** section, where a hand-maintained prefab warrants one, is topology and rationale — the tree, and why each node is shaped the way it is — never the digit strings, which the prefab owns.

Two standing traps:

- **Route values, keep relations.** A tuned number lives once at its authoring site; the README names the knob, the direction, and the relation. Quote only what the rig *produces*, a structural constant whose re-derivation is the design (named as an echo of its source); when a clone physically copies a value, the canon names its copy sites.
- **Never append a verification run.** A sound re-verification leaves the README alone; a broken one fixes the entry and edits the line that was wrong.

And one rule is enforced rather than stated: **prose never speaks for the checks.** A README sentence attributing coverage to `--check` or the gate ("`--check` asserts/holds/refuses …") fails the gate's README lint — the check prints its own scope, and the README may say only "run `generate.py --check`". Figure pins live as asserts inside `--check`, never as claims in the README.

A module's menu ships as an asset once it has more than one control, authored as `controller.yaml`'s `menu:` block so it regenerates with everything else; a bare `Toggle` is reserved for a lone enable on a module that cannot be instanced twice (two instances export the same un-prefixed name). A menu the schema cannot express (puppets, per-control icons) stays hand-maintained in `assets/`.

## The gate

**One question: does committed `built/` match what the compiler emits from its `controller.yaml` today?** A compiler change can fail an entry whose YAML nobody touched. `built/` is generated — committed only for GUID resolution and animator-window study — so decompile-equality guards no hand-authored content. Two settled points: a field the compiler emits that the schema does not model does not matter (grow the schema in `animator-schema.md`, never strengthen the comparison); and equality is on the **decoded** document, never bytes — Unity assigns sub-asset fileIDs non-deterministically, so a large regeneration diff is not evidence of drift.

`tools/gate.ps1` runs it per entry at any depth (`built/`/`assets/` never descended), plus structural comparison of the emitted menu and params asset, plus a prefab-integrity pass failing three things no reviewer can see in a committed artifact: a missing MonoBehaviour script, an anchor seam (`nondestructive.md` rule 1; `CheckAvatar` names it), and a committed consuming-project path. That pass counts top-level trees, not entries. The gate does not round-trip the schema — that is `avatar-tools`' own fixpoint property, and a break there must not fail an entry.

**Regenerate `built/` as a unit** — controller + params + menu, over the committed `.meta`s so GUIDs hold. If the emitted parameter list moved without a deliberate YAML edit (a `scratch:` flip, the compiler's reserved set), settle that first — regenerating blind commits it as though it had been reviewed. The procedure is a `CompileController` run in any venue that `file:`-mounts this library, with both the source and the outDir addressed as `Packages/com.ryan6vrc.patterns/…` — Unity resolves those to the checkout, so the emit reads the entry's yaml and writes its `built/` into the working tree over already-imported `.meta`s, which is what holds the GUIDs. An absolute source path compiles and holds them too, so `gate.ps1`'s out-of-project run is equivalent here. Each regenerated `.meta` moves its `srchash:` line — that is the stamp tracking the source it was compiled from, not drift — and any `compiled-from:` path a `.meta` still carries empties, because the compiler stopped recording one; both are the stamp, and a regeneration that changed nothing else moves exactly these.

Study entries name every non-leaf blend-tree node and name clips by the value they write.

## Per-entry checks (`generate.py --check`)

Freshness of generated files is regenerate-and-read-`git diff`, never a disk pin (same trigger, less information, and regeneration is also the repair). A `--check` asserts emit determinism — what makes an empty regen diff mean "no drift" — plus only the **hand-maintained surfaces no compile or gate reads**: prefab wiring, `globalParams`, cross-asset references, README-quoted figures, registry ids. Never the emitted document's shape: a shape assert is rewritten by the very edit it would catch (measured — zero of five shipped defects caught, while cited as verification evidence); that knowledge is a comment at the emission site or a generator refusal, and a rule that generalizes belongs in `ControllerRules`, which already fails every compile and therefore the gate. Nothing runs `--check` automatically; "gates green" never includes it; every check prints its scope negatively. A composition's check is a handful of prefab pins, never a suite.

## Provenance / PII

This repo is **public**. Entries generalized from real assets record their origin and what was abstracted away; scrub paths, project specifics, persona and private-project names. Cite open-source ancestors by name; refer to a private source avatar generically.
