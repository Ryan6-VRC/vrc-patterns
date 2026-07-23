# vrc-patterns conventions

Reusable avatar building blocks. Primary reader: an agent with the full Atelier workspace. YAML is the source of truth; built Unity assets are regenerable.

The general avatar-tooling doctrine an entry *embodies* — module seams and the build-order that constrains them, gimmick packaging, graph-layout legibility, the binding schema — lives in the workspace docs (`nondestructive.md`, `gimmicks.md`, `animator-schema.md`). This file is only the mechanics a contributor **to vrc-patterns itself** needs: the entry's shape on disk, the README's shape and Interface slot, and the gate.

## An entry is a folder

    <entry-name>/
      README.md          # prose + the Interface stanza + provenance
      controller.yaml    # the YAML source (CompileController); declares basis, role, parameters
      built/             # committed when a GUID references it, OR for a declared study/reference entry (see tiers): .controller + *_Parameters.asset (+ .meta)
      assets/            # owned, self-contained assets the entry ships (meshes, reference prefabs, materials)
      <entry>.prefab     # the drop-in, referencing built/ by GUID via an MA/VRCFury merge component

## Tier is derived, not assigned

One axis changes an entry's shape: **does it ship a GUID-consumer** (a prefab/asset referencing `built/`)? Read it off which files exist — the gate keys off the same signal (a `controller.yaml` entry that also ships a prefab/`assets`/`built` must ship its built controller per document). Three shapes exist:

- **Pattern** — `controller.yaml`, plus `built/` for the study/reference form (which every current Pattern is): a DBT graph is legible only in the animator window, so `built/` is committed and held to decompile-equality like any `built/`. A pure lift-and-recompile Pattern would ship `controller.yaml` alone — none exist yet.
- **Module** — adds `<entry>.prefab` (one or more variants), and `assets/` when it ships owned meshes/materials. `built/` committed; the prefab references it by GUID.
- **Structural Module** — a Module whose behaviour lives entirely in its prefab's components (a constraint rig, no animator): ships `<entry>.prefab` with **no `controller.yaml`** and no `built/`. The compile/round-trip pass skips it (nothing to compile), but the gate's prefab-integrity pass (§The gate) still asserts its prefab imports with no missing scripts — script integrity only; behavioural correctness rests on the README install check.

## The README's two readers

A README serves both a wide-skill-range human and an agent lifting the entry, in one document ordered by depth — not split into parallel human/agent halves (a split duplicates facts and rots). The **lead** is where a human stops; the **Interface stanza and body** are where the agent reads on. Each fact lives once and the reading order is the audience gradient: never restate the lead's "what" in agent terms below, and never pull mechanism up into the lead.

**The lead** (1–3 sentences under the title, before Provenance) says what a consumer *gets*, names the mechanism without explaining it, and ends on the packaged novelty — the one thing this entry exists to give — with its synced-bit cost. Describe the artifact ("a prop anyone in the instance can carry and set down"); do not perform a sales tour ("grab it off your body and pass it to a friend"). One concrete example orients in one clause ("swap the payload for your prop — a pipe, a mic"), never a costume parade ("a kiseru, a mic, a fan, a lollipop"). A Pattern with no wearer addresses the author lifting it, same register: say plainly what it computes and costs. When an entry has structural shape a lead can't carry (a variant family, N anchor classes), a short list may follow — still what-it-*is*, the how deferred to **How it works**.

The register is the anti-cringe pin, load-bearing because the pull is toward a marketplace listing: describe don't sell, one example not an inventory, name the mechanism don't gloss it, no cutesy enumerations ("headpats, cheek pokes, tail tugs" → "touch zones that react to a toucher").

**Tier label** in the title is the bare tier in parens — `(Module)`, `(Module, study)`, `(Pattern, study)`, `(Structural Module)` — and the catalog's Tier column uses the same word.

**Consumer-gotcha slot** (optional, Module tier), when a correct install still hits compose-time traps: one section, **Before you compose it**, after the Interface stanza.

**Empirical-constants table** attaches to the mechanism prose — inside **How it works** where the entry has one — never floating as an H2 between the lead and the Interface contract. An entry with no How-it-works (its mechanism carried by the lead + a Traps section) may keep a labelled constants block after the Interface stanza.

**Catalog invariant:** each `README.md` catalog row's "Build this" cell is the one-line compression of that entry's lead. They are authored together, and drift between them is the review check that holds register consistent across entries.

## The Interface stanza (fixed README slot)

`controller.yaml` already carries `basis`, `role`, `parameters`. The README's Interface stanza carries what the YAML cannot, so adapting an entry never means reverse-engineering the prefab:

- **Params** — in/out, synced/saved.
- **Seam** — which framework merges it (MA `MergeAnimator` vs VRCFury `FullController`), the anchor, and the **binding frame the merge resolves** (MA `basis:` ↔ `pathMode`; VRCF per-binding, `basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0`). CompileController is frame-blind, so this is load-bearing — record it; `nondestructive.md` owns the frame mechanics and the build-order that makes the seam choice matter. A module's rest geometry (home, park, deploy point) **ships anchored to the avatar** — an Anchor GO (MA `BoneProxy`, AsChildAtRoot) with an `Offset` child as the referenced target; only object-referenced, never path-animated, nodes may be proxied (`gimmicks.md` §Packaging owns the idiom). Unanchored rest geometry loads at the avatar-root origin — the wearer's feet.
- **Dependencies** — physbones/contacts/menu params the entry assumes exist.
- **Required assets** — and any hard external dependency.

## Verifying the install (fixed README slot, Module tier)

An entry in this library is **assumed working** — it passed the gate to get in, and git holds how it got there. So this slot is not a record of what was proven; it is written for the agent who has just composed the entry onto an unfamiliar avatar and needs to know it landed. Two things only:

- The cheapest observable that distinguishes a correct install from a plausible-looking broken one, and what a wrong reading means (a cage at the avatar-root origin means the BoneProxy never resolved; a zero self-receiver means the descriptor has no collider slots).
- What the emulator structurally cannot show **for this entry**, so nobody burns a session on it. `docs/verify.md` owns the general boundary — name only what is specific here.

Never append a run to this slot. A session that re-verifies an entry and finds it sound leaves the README alone; one that finds it broken fixes the entry, and edits the line that was wrong.

Pattern tier has no seam and so no install: it carries a **Behavior** slot instead — the numeric contract a consumer lifting the YAML is entitled to, and how to re-measure it after an edit.

## The gate

`tools/gate.ps1` is the admission bar — compile + round-trip + decompile-equality per entry, plus a prefab-integrity pass: it loads every entry's prefab(s) and fails any that import with a missing MonoBehaviour script (catching a dropped VRCFury/MA merge-component reference). That pass is script integrity only — it does not assert a rig behaves. The gate also does **not** check the `*_Parameters.asset` — regenerate `built/` as a unit (controller + params asset, over the committed `.meta`s so GUIDs hold) whenever the YAML changes.

Study/reference entries name every non-leaf blend-tree node (`name:`) and name clips by the value they write.

## Provenance / PII

Entries generalized from real assets record their origin and what was abstracted away. This repo is **public**: scrub project specifics, paths, and real names — including persona and private-project names in provenance lines. Cite an upstream open-source ancestor by name; refer to a private source avatar generically.
