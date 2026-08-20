# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace. YAML is the source of truth; built Unity assets are regenerable.

The general avatar-tooling doctrine an entry *embodies* — module seams and the build-order that constrains them, gimmick packaging, graph-layout legibility, whether a behaviour earns a layer at all or folds into a Direct tree, the binding schema — lives in the workspace docs (`nondestructive.md`, `gimmicks.md`, `animator-schema.md`). This file is only the mechanics a contributor **to vrc-patterns itself** needs: the entry's shape on disk, the README's shape and Interface slot, and the gate.

## An entry is a folder

    <entry-name>/
      README.md          # prose + the Interface stanza + provenance
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters, menu
      built/             # committed when a GUID references it, OR for a declared study/reference entry (see tiers): .controller + *_Parameters.asset + *_Menu.asset where the entry ships a menu (+ .meta)
      assets/            # owned, self-contained assets the entry ships (meshes, reference prefabs, materials)
      <entry>.prefab     # the drop-in, referencing built/ by GUID via an MA/VRCFury merge component

**Commit a prefab as an Editor saved it.** VRCFury back-fills each asset reference's resolved `id` beside its `objRef` the first time the prefab is inspected, and since venues mount this repo `file:` (writable), that write lands here as an uncommitted diff nobody made. Don't revert it: `objRef` alone cannot recover a reference whose asset disappears and returns, so the filled `id` is the shipping state and leaving it empty makes the diff recur. **The cached path must name the package** — `Packages/com.ryan6vrc.patterns/...`, never a venue-local path a different mount would never resolve; the gate catches a leak, but don't commit one in the first place.

**An entry may nest inside another entry**; `built/` and `assets/` are reserved and may not hold one — the gate does not fail a `controller.yaml` misfiled there, it ignores the directory, so the entry is simply never gated. Variant builds from one generator each take a subfolder (`object-sync/y/`), and every composition is a nested entry by definition (§compositions/). A nested entry is a full entry — same shape, same tier derivation, same gate.

**No two committed `.meta` under one top-level tree may declare the same GUID.** Copying any entry to make a variant — parent to child, or sibling to sibling — means re-GUIDing the copy's `built/` `.meta`s and repointing whatever references them in the same edit. The gate asserts it over every top-level tree and names both files; it matters past the gate too, because a consuming project mounts this library as a package and inherits the collision.

## Tier is derived, not assigned

One axis changes an entry's shape: **does it ship a GUID-consumer** (a prefab/asset referencing `built/`)? Read it off which files exist — the gate keys off the same signal. Three shapes exist:

- **Pattern** — `controller.yaml`, plus `built/` for the study/reference form (which every current Pattern is): a DBT graph is legible only in the animator window, so `built/` is committed and held to decompile-equality like any `built/`. A pure lift-and-recompile Pattern would ship `controller.yaml` alone — none exist yet.
- **Module** — adds `<entry>.prefab` (one or more variants), and `assets/` when it ships owned meshes/materials. `built/` committed; the prefab references it by GUID.
- **Structural Module** — a Module whose behaviour lives entirely in its prefab's components, **or in an owned non-animator asset the prefab references** (a constraint rig, or a shader; no animator either way): ships `<entry>.prefab` with **no `controller.yaml`** and no `built/`. The *non-animator* exclusion is load-bearing — `built/` is also an owned asset a prefab references by GUID, so widening the clause to include it would describe Module equally well and dissolve the axis. The compile pass skips the tier (nothing to compile) and the prefab-integrity pass (§The gate) still covers its prefab; a shader-carried entry's *assets* have no standing check, so correctness rests on the README install check.

A folder under `compositions/` is Module-shaped and gated as an entry, but is not a library entry — not catalogued, not lifted, and carrying no catalogued tier. §compositions/ owns it.

## `compositions/`

A **composition** is a runnable arrangement of two or more entries, committed as a prefab rather than written up, because prose is lossy about arrangement specifically: a graph of nodes, weights and solve order re-derives at about what building it fresh cost. It does **not** stamp the entry commits it was built against: the entries live beside it in this repo and are only ever checked out with it, so git already holds that state exactly, and `git bisect` answers "when did this stop loading" better than a hand-copied hash no gate reads.

Two rules an entry's shape does not already give it:

- **Never a vendor base.** An arrangement resting on a licensed avatar cannot be published, so a composition ships the rig and not the avatar — no vendor geometry, no scene reference reaching a base, and seams that resolve by humanoid bone rather than by name or object reference.
- **It may carry its own generated build of an entry it composes**, at its own CONFIG — a retune one arrangement wants would otherwise force another build, prefab and README claim into a public entry serving a single consumer. Drive the entry's generator unmodified and deviate after; a forked copy is a second canon for the same rig. The carried build is a nested entry, so the gate holds its `built/` to committed-equals-compiled like any other — regenerate it whenever the entry's generator or the compiler moves, never hand-tune it.

## The README's two readers

A README serves both a wide-skill-range human and an agent lifting the entry, in one document ordered by depth — not split into parallel human/agent halves (a split duplicates facts and rots). The **lead** is where a human stops; the **Interface stanza and body** are where the agent reads on. Each fact lives once and the reading order is the audience gradient: never restate the lead's "what" in agent terms below, and never pull mechanism up into the lead.

**The lead** (1–3 sentences under the title, before Provenance) says what a consumer *gets*, names the mechanism without explaining it, and ends on the packaged novelty — the one thing this entry exists to give — with its synced-bit cost. A Pattern with no wearer addresses the author lifting it in the same register: say plainly what it computes and costs. When an entry has structural shape a lead can't carry (a variant family, N anchor classes), a short list may follow — still what-it-*is*, the how deferred to **How it works**.

The register is the anti-cringe pin, load-bearing because the pull is toward a marketplace listing: describe don't sell ("a prop anyone in the instance can carry and set down", not "grab it off your body and pass it to a friend"), one example not an inventory ("swap the payload for your prop — a pipe, a mic", never a costume parade), name the mechanism don't gloss it, no cutesy enumerations ("headpats, cheek pokes, tail tugs" → "touch zones that react to a toucher").

**Tier label** in the title is the bare tier in parens — `(Module)`, `(Module, study)`, `(Pattern, study)`, `(Structural Module)` — and the catalog's Tier column uses the same word.

**Consumer-gotcha slot** (optional, Module tier), when a correct install still hits compose-time traps: one section, **Before you compose it**, after the Interface stanza.

**Empirical-constants table** attaches to the mechanism prose — inside **How it works** where the entry has one — never floating as an H2 between the lead and the Interface contract. An entry with no How-it-works (its mechanism carried by the lead + a Traps section) may keep a labelled constants block after the Interface stanza.

**Keep the relation, route the value.** A row names where the knob is authored (the `controller.yaml` clip, the prefab field), what turning it does and which way, and the relation that makes it legible (`g = w₀/(w₀+w₁)`; zone side = 3 × scale) — never the tuned number, which lives once at the authoring site so a retune touches one file. When a second entry clones the rig the value is physically copied (a prefab float and a clip key cannot reference another entry), and the canon's constants block **names its copy sites** — the route runs both ways, because a retune starts at the canon, where an inbound-only link is invisible. Three things stay quoted: a value the rig *produces* (a latch envelope, a worst-case error, a Pattern's Behavior row) is canon here and has no other home; a structural constant the entry's design rests on (synced-bit count, cage geometry, readout coefficients) is a managed echo that names its source, because re-deriving it *is* the design; and a `Rig` section, which is the declared spec its hand-maintained prefab is kept against.

**One explanation per mechanism, per document.** `controller.yaml` explains the graph at its authoring site; the README explains it for the consumer. Every other mention names the mechanism in a clause and routes to one of those two. A mechanism narrated at five sites gets retuned at four.

**Catalog invariant:** each `README.md` catalog row's "Build this" cell is the one-line compression of that entry's lead. They are authored together, and drift between them is the review check that holds register consistent across entries.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — which framework merges it (MA `MergeAnimator` vs VRCFury `FullController`), the anchor, and the **binding frame the merge resolves** (MA `basis:` ↔ `pathMode`; VRCF per-binding, `basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`). CompileController is frame-blind, so this is load-bearing — record it; `animator.md` owns the frame mechanics, `nondestructive.md` the build-order that makes the seam choice matter. A rest position the behaviour depends on (home, park, deploy point) ships anchored — an Anchor GO (MA `BoneProxy`, AsChildAtRoot) with an `Offset` child as the referenced target; only object-referenced, never path-animated, nodes may be proxied (`gimmicks.md` §Packaging owns the idiom) — and the gate enforces that half under a VRCFury merge. Anchor only where something breaks unanchored; otherwise ship a bare root.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

**The stanza is narration, and no gate reads it.** Nothing checks a Params row against `controller.yaml`, a Dependencies line against the prefab, or a Required-assets line against what actually ships — so a row that was true when written stays green forever after it stops being, and review is the only thing between a lifting agent and a confident wrong answer. Author each row from the artifact rather than from the entry's own prose, and quote the handle the component **serializes** rather than a name some project supplies for it: a `LayerMask` stores a bare index and a reference stores a GUID, so naming the friendly layer asserts something about the *host* project that the entry is in no position to know. Seam's anchor clause is the lone exception — the prefab-integrity pass enforces it under a VRCFury merge (§The gate) — and that it is alone is the part worth carrying.

**A module's menu ships as an asset once it has more than one control**, and a bare `Toggle` is reserved for a lone enable. Both follow from VRCFury's param-name rewrite and the name exposure `globalParams` buys — `gimmicks.md` §Packaging owns that mechanism and its failure modes.

The menu is authored as a `menu:` block in `controller.yaml` and lands in `built/` with everything else `CompileController` emits (`animator-schema.md` §menu), so it regenerates as a unit with the controller and params asset and the gate holds it to the same committed-equals-compiled check. A menu the schema cannot express — puppets, per-control icons — is the exception that stays hand-maintained in `assets/`, kept against the README's **Params** list the way a Module's prefab is kept against its **Rig** section.

**A bare `Toggle` needs one control *and* a module that cannot be instanced twice**, since two instances export the same un-prefixed name and collide. The second half is the test, and what enforces it varies — anatomical (`head-deform`: one head per avatar) or structural (`object-sync`: its contact collision tags are fixed strings VRCFury's param prefixing does not reach, so a second drop needs a regeneration with its own tags; its README §Seam records that). Either reason qualifies; a module that merely *usually* appears once does not. Single-instancing rules out only the module colliding with *itself* — the host-capture exposure (`gimmicks.md` §Packaging) is untouched — which is why two prefab *variants* that are alternatives, never composed together, may export the same name.

## Verifying the install (fixed README slot, Module tier)

An entry in this library is **assumed working** — it passed the gate to get in, and git holds how it got there. So this slot is not a record of what was proven; it is written for the agent who has just composed the entry onto an unfamiliar avatar and needs to know it landed. Two things only:

- The cheapest observable that distinguishes a correct install from a plausible-looking broken one, and what a wrong reading means (a cage at the avatar-root origin means the BoneProxy never resolved; a zero self-receiver means the descriptor has no collider slots).
- What the emulator structurally cannot show **for this entry**, so nobody burns a session on it. `docs/emulator.md` owns the general boundary — name only what is specific here.

Never append a run to this slot. A session that re-verifies an entry and finds it sound leaves the README alone; one that finds it broken fixes the entry, and edits the line that was wrong.

Pattern tier has no seam and so no install: it carries a **Behavior** slot instead — the numeric contract a consumer lifting the YAML is entitled to, and how to re-measure it after an edit.

## The gate

**The gate asks one question: does committed `built/` match what the compiler emits from its `controller.yaml` today?** A stale regeneration after a YAML edit is the common cause of a mismatch but not the only one — a change to the compiler's own emit filters fails a document whose YAML nobody touched. `built/` is a generated artifact, committed only so a prefab can resolve it by GUID and so a study entry opens in the animator window; nobody hand-maintains it, so decompile-equality is not a correctness proof of an entry and does not guard hand-authored content. Two consequences, both re-litigated before: a field the compiler emits that the schema does not model **does not matter** (if it matters, grow the schema — `animator-schema.md` is the door, never a stricter comparison here); and equality is asserted on the **decoded** document, never on bytes — Unity assigns `.controller` sub-asset fileIDs non-deterministically, so recompiling an unchanged entry rewrites most of the file, and a large regeneration diff is not evidence of drift.

`tools/gate.ps1` is the admission bar: compile + decompile-equality per entry, plus structural comparison of the emitted menu and `*_Parameters.asset` against the committed ones (a `.controller` stores neither — `ControllerFixpoint`'s class header owns why decompile-equality reaches neither, the entry walk, and its prunes). It does **not** round-trip the schema: that a decompile recompiles identically is `avatar-tools`' property, proven in its own fixpoint suites, and a break there is a tool bug that must not fail an entry's admission. A prefab-integrity pass loads every entry's prefab(s) and fails three things no reviewer can see in a committed artifact: a **missing MonoBehaviour script**, an **anchor seam** (a VRCFury `FullController`-merged binding pathing through a node carrying an MA relocator — the shape `nondestructive.md` rule 1 forbids; `CheckAvatar` names the anchor), and a **committed consuming-project path**. That pass is the one place the gate rules on hand-authored content; it still asserts nothing about how a rig behaves. **Regenerate `built/` as a unit** — controller + params asset + menu, over the committed `.meta`s so GUIDs hold — whenever the YAML changes; but when the emitted parameter list moved without a deliberate YAML edit, settle the cause first (a `scratch:` flip, or a name entering or leaving the compiler's reserved set) — regenerating blind commits it as though it had been reviewed. **Every entry is gated, at any depth**, and `built/`/`assets/` are never descended into. The prefab-integrity pass selects top-level trees and checks each whole, so a nested entry's prefabs are covered as part of its parent; its count line counts trees, not entries, and the two numbers are not comparable in either direction (a Structural Module is a tree that is not an entry).

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Per-entry checks (`generate.py --check`)

Freshness of committed generated files is not a check's job: **regenerate and read `git diff`** — an empty diff is the byte-identity proof, a non-empty one shows the drift itself, and regeneration is also the repair. The one assert that keeps that instrument valid stays: emission is deterministic across two calls, since a nondeterministic emit would make every regen diff read as drift.

Beyond that, a `--check` pins only the **hand-maintained surfaces no compile or gate reads** — prefab wiring, `globalParams` lists, cross-asset references, README-quoted figures, registry ids — and never the shape of the emitted document: a shape assert shadows the generator and is rewritten by the very edit it would catch (measured, across a full composition build, at zero of five shipped defects found while its green output was cited as verification evidence). What such an assert would encode lives as a comment at the emission site, or as a refusal in the generator, which fails the build rather than narrating it; a rule that generalizes beyond one entry belongs in `ControllerRules`, whose error-tier findings already fail every `CompileController` compile — and the gate compiles every entry, so the shared rule fires at admission. Nothing runs `--check` automatically and "gates green" never includes it; every check prints its scope negatively so a green run cannot be cited as more than it is, and a composition's check stays a handful of pins on its hand-edited prefab, never a suite.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is **public**: scrub project specifics, paths, and real names — including persona and private-project names in provenance lines. Cite an upstream open-source ancestor by name; refer to a private source avatar generically.
