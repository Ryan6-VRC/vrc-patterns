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

**Commit a prefab as an Editor saved it.** VRCFury caches each asset reference's resolved `id` beside its `objRef` and back-fills it the first time the prefab is inspected; since venues mount this repo `file:` (writable, not into `Library/PackageCache`), that write lands here as an uncommitted diff nobody made. Don't revert it as noise — `objRef` alone cannot recover a reference whose asset disappears and returns, so the filled `id` is the shipping state, and leaving it empty is what makes the diff recur.

## Tier is derived, not assigned

One axis changes an entry's shape: **does it ship a GUID-consumer** (a prefab/asset referencing `built/`)? Read it off which files exist — the gate keys off the same signal (a `controller.yaml` entry that also ships a prefab/`assets`/`built` must ship its built controller per document). Three shapes exist:

- **Pattern** — `controller.yaml`, plus `built/` for the study/reference form (which every current Pattern is): a DBT graph is legible only in the animator window, so `built/` is committed and held to decompile-equality like any `built/`. A pure lift-and-recompile Pattern would ship `controller.yaml` alone — none exist yet.
- **Module** — adds `<entry>.prefab` (one or more variants), and `assets/` when it ships owned meshes/materials. `built/` committed; the prefab references it by GUID.
- **Structural Module** — a Module whose behaviour lives entirely in its prefab's components, **or in an owned non-animator asset the prefab references** (a constraint rig, or a shader; no animator either way): ships `<entry>.prefab` with **no `controller.yaml`** and no `built/`. The *non-animator* exclusion is load-bearing rather than decorative — `built/` is also an owned asset a prefab references by GUID, so a widening that omitted it would describe Module equally well and dissolve the one axis tier is derived from. The compile/round-trip pass skips the tier (nothing to compile), and the gate's prefab-integrity pass (§The gate) asserts missing scripts plus, for a shader-carried entry, that its shaders compile and its materials resolve — behavioural correctness still rests on the README install check.

A folder under `compositions/` is Module-shaped but is not an entry — §compositions/ owns it.

## `compositions/`

A **composition** is a runnable arrangement of two or more entries, committed as a prefab rather than written up, because prose is lossy about arrangement specifically: a fact survives being stated, but a graph of nodes, weights and solve order re-derives at about what building it fresh cost. Its README records the entry commits it was built against, since a composition rots when anything it depends on changes shape.

Two rules an entry's shape does not already give it:

- **Never a vendor base.** An arrangement resting on a licensed avatar cannot be published, so a composition ships the rig and not the avatar — no vendor geometry, no scene reference reaching a base, and seams that resolve by humanoid bone rather than by name or object reference.
- **It may carry its own generated build of an entry it composes**, at its own CONFIG. An entry's `check()` pins a `controller.yaml` on disk for every label `preset_configs()` returns, so a retune one arrangement wants would otherwise force a fourth build, prefab and README claim into a public entry serving a single consumer. Drive the entry's generator unmodified and deviate after; a forked copy is a second canon for the same rig.

## The README's two readers

A README serves both a wide-skill-range human and an agent lifting the entry, in one document ordered by depth — not split into parallel human/agent halves (a split duplicates facts and rots). The **lead** is where a human stops; the **Interface stanza and body** are where the agent reads on. Each fact lives once and the reading order is the audience gradient: never restate the lead's "what" in agent terms below, and never pull mechanism up into the lead.

**The lead** (1–3 sentences under the title, before Provenance) says what a consumer *gets*, names the mechanism without explaining it, and ends on the packaged novelty — the one thing this entry exists to give — with its synced-bit cost. Describe the artifact ("a prop anyone in the instance can carry and set down"); do not perform a sales tour ("grab it off your body and pass it to a friend"). One concrete example orients in one clause ("swap the payload for your prop — a pipe, a mic"), never a costume parade ("a kiseru, a mic, a fan, a lollipop"). A Pattern with no wearer addresses the author lifting it, same register: say plainly what it computes and costs. When an entry has structural shape a lead can't carry (a variant family, N anchor classes), a short list may follow — still what-it-*is*, the how deferred to **How it works**.

The register is the anti-cringe pin, load-bearing because the pull is toward a marketplace listing: describe don't sell, one example not an inventory, name the mechanism don't gloss it, no cutesy enumerations ("headpats, cheek pokes, tail tugs" → "touch zones that react to a toucher").

**Tier label** in the title is the bare tier in parens — `(Module)`, `(Module, study)`, `(Pattern, study)`, `(Structural Module)` — and the catalog's Tier column uses the same word.

**Consumer-gotcha slot** (optional, Module tier), when a correct install still hits compose-time traps: one section, **Before you compose it**, after the Interface stanza.

**Empirical-constants table** attaches to the mechanism prose — inside **How it works** where the entry has one — never floating as an H2 between the lead and the Interface contract. An entry with no How-it-works (its mechanism carried by the lead + a Traps section) may keep a labelled constants block after the Interface stanza.

**Keep the relation, route the value.** A row names where the knob is authored (the `controller.yaml` clip, the prefab field), what turning it does and which way, and the relation that makes it legible (`g = w₀/(w₀+w₁)`; zone side = 3 × scale). It does not quote the tuned number — that lives once, at the authoring site, so a retune touches one file. That holds until a second entry clones the rig: a prefab float and a clip key cannot reference another entry, so the value is physically copied and the canon's constants block **names its copy sites**. The route runs both ways: a retune starts at the canon, where an inbound-only link is invisible. Three things stay quoted: a value the rig *produces* (a latch envelope, a worst-case error, a Pattern's Behavior row) is canon here and has no other home; a structural constant the entry's design rests on (synced-bit count, cage geometry, readout coefficients) is a managed echo that names its source, because re-deriving it *is* the design; and a `Rig` section, which is the declared spec its hand-maintained prefab is kept against.

**One explanation per mechanism, per document.** `controller.yaml` explains the graph at its authoring site; the README explains it for the consumer. Every other mention names the mechanism in a clause and routes to one of those two. A mechanism narrated at five sites gets retuned at four.

**Catalog invariant:** each `README.md` catalog row's "Build this" cell is the one-line compression of that entry's lead. They are authored together, and drift between them is the review check that holds register consistent across entries.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — which framework merges it (MA `MergeAnimator` vs VRCFury `FullController`), the anchor, and the **binding frame the merge resolves** (MA `basis:` ↔ `pathMode`; VRCF per-binding, `basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`). CompileController is frame-blind, so this is load-bearing — record it; `animator.md` owns the frame mechanics, `nondestructive.md` the build-order that makes the seam choice matter. A rest position the behaviour depends on (home, park, deploy point) ships anchored — an Anchor GO (MA `BoneProxy`, AsChildAtRoot) with an `Offset` child as the referenced target; only object-referenced, never path-animated, nodes may be proxied (`gimmicks.md` §Packaging owns the idiom) — and the gate enforces that half under a VRCFury merge. Anchor only where something breaks unanchored; otherwise ship a bare root.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

**A module's menu ships as an asset once it has more than one control**, and a bare `Toggle` is reserved for a lone enable. Both follow from VRCFury's param-name rewrite and the name exposure `globalParams` buys — `gimmicks.md` §Packaging owns that mechanism and its failure modes.

The menu is authored as a `menu:` block in `controller.yaml` and lands in `built/` with everything else `CompileController` emits (`animator-schema.md` §menu), so it regenerates as a unit with the controller and params asset and the gate holds it to the same committed-equals-compiled check. A menu the schema cannot express — puppets, per-control icons — is the exception that stays hand-maintained in `assets/`, kept against the README's **Params** list the way a Module's prefab is kept against its **Rig** section.

**A bare `Toggle` needs one control *and* a module that cannot be instanced twice**, since two instances export the same un-prefixed name and collide. The second half is the test, and what enforces it varies: `head-deform` is single-instance anatomically (one control, one head per avatar), `object-sync` because its contact collision tags are fixed strings VRCFury's param prefixing does not reach, so a second drop of the prefab needs a regeneration with its own tags (its README §Seam records that). Either reason qualifies; a module that merely *usually* appears once does not. Note what single-instancing does **not** buy — the host-capture exposure is untouched (`gimmicks.md` §Packaging), so it rules out only the module colliding with *itself*, which is why `head-deform`'s two prefab variants may both export `HeadDeform/Active` (they are alternatives, never composed together) while still resting on nobody else claiming that name.

## Verifying the install (fixed README slot, Module tier)

An entry in this library is **assumed working** — it passed the gate to get in, and git holds how it got there. So this slot is not a record of what was proven; it is written for the agent who has just composed the entry onto an unfamiliar avatar and needs to know it landed. Two things only:

- The cheapest observable that distinguishes a correct install from a plausible-looking broken one, and what a wrong reading means (a cage at the avatar-root origin means the BoneProxy never resolved; a zero self-receiver means the descriptor has no collider slots).
- What the emulator structurally cannot show **for this entry**, so nobody burns a session on it. `docs/verify.md` owns the general boundary — name only what is specific here.

Never append a run to this slot. A session that re-verifies an entry and finds it sound leaves the README alone; one that finds it broken fixes the entry, and edits the line that was wrong.

Pattern tier has no seam and so no install: it carries a **Behavior** slot instead — the numeric contract a consumer lifting the YAML is entitled to, and how to re-measure it after an edit.

## The gate

**The gate asks one question: was `built/` regenerated after its `controller.yaml` changed?** Everything below is that question asked of a different file, with one exception the prefab pass carries — it guards hand-authored content, and is called out where it appears. `built/` is a generated artifact — committed only so a prefab can resolve it by GUID and so a study entry opens in the animator window — and nobody hand-maintains it, so decompile-equality is not a correctness proof of an entry and does not guard hand-authored content. Two consequences worth stating, because both have been re-litigated: a field the compiler emits that the schema does not model **does not matter** (if it matters, grow the schema — `animator-schema.md` is the door, and a widen there is the fix, never a stricter comparison here); and equality is asserted on the **decoded** document, never on bytes, because Unity assigns `.controller` sub-asset fileIDs non-deterministically — recompiling an unchanged entry rewrites most of the file while changing nothing, so a byte diff would fail every entry on every run and a large regeneration diff is not evidence of drift.

`tools/gate.ps1` is the admission bar — compile + decompile-equality per entry, and where the entry ships a menu a direct comparison of the emitted `VRCExpressionsMenu` against the committed one (a `.controller` stores no menu, so decompile-equality is blind to it). It does **not** round-trip the schema: that a decompile recompiles identically is a property of `avatar-tools`, proven in that package's own fixpoint suites against fixtures spanning the schema vocabulary, and a break there is a tool bug that must not fail an entry's admission. A prefab-integrity pass loads every entry's prefab(s) and fails two things no reviewer can see in any committed artifact: a **missing MonoBehaviour script** (a dropped VRCFury/MA merge-component reference), and an **anchor seam** — a VRCFury `FullController`-merged binding pathing through a node carrying an MA relocator, the shape `nondestructive.md` rule 1 forbids because a clip cannot be repathed to follow that move (`CheckAvatar` names the anchor; `unity-tools.md` contracts it). That same pass carries the **asset assert** a shader-carried Structural Module needs, since such an entry has no `built/` and so no decompile-equality to stand in for it: shaders compile without error (with every declared local keyword warmed first — variants compile lazily, so a default-only check would be weaker than the one-time review it has to outlive), a material's shader reference resolves (not null, not `Hidden/InternalErrorShader`), and no material's **texture slot** carries a GUID from outside its own entry. All three are failures that render something *plausible* rather than erroring — a null cubemap is a wrong reflection, not a pink material — which is why they need a standing check rather than a one-time review. The texture rule reads **raw GUIDs out of the `.mat`** rather than walking resolved dependencies, because a GUID pointing into a package the venue lacks resolves to nothing: a dependency walk would see it only where it resolves, i.e. only where it is harmless, and stay silent in the venue the gate actually runs in. It is scoped to texture slots on purpose — a material's *shader* may legitimately live in another package (`anti-cull` references a VRChat Mobile shader deliberately), so widening it to every reference would fail a merged entry. This is the one pass guarding hand-authored content, and the only place the gate rules on a prefab's shape rather than a generated file's freshness; it still asserts nothing about how a rig behaves. The gate also does **not** check the `*_Parameters.asset` — regenerate `built/` as a unit (controller + params asset, over the committed `.meta`s so GUIDs hold) whenever the YAML changes.

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is **public**: scrub project specifics, paths, and real names — including persona and private-project names in provenance lines. Cite an upstream open-source ancestor by name; refer to a private source avatar generically.
