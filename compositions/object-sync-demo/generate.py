#!/usr/bin/env python3
"""This composition's own `object-sync` build: the shipped entry's generator,
run over a widened wire, emitting beside this file instead of into the entry.

    python compositions/object-sync-demo/generate.py           # writes the document
    python compositions/object-sync-demo/generate.py --check   # asserts, writes nothing

Output: `object-sync/controller.yaml` beside this file. Compile it with
`CompileController` into `built/` beside it; the composition's VRCFury
`FullController` points at that build, never at `../../object-sync/built/`.

WHY THE BUILD LIVES HERE AND NOT IN THE ENTRY
---------------------------------------------
A `demo` preset in the entry would force a fourth build, prefab and README
claim into the public entry for a single consumer — `committed_configs()`
emits a document on disk for every label it returns. The composition drives
the entry's generator from outside instead: `object-sync/generate.py` is
imported unmodified and the entry stays byte-identical. `CONVENTIONS.md`
§compositions/ is the rule this implements.

The demo carries exactly one post-generation deviation from the entry's emitted
document — `Enable` defaults true — applied in `demo_document()`, which owns the
reason. Every emission path goes through it, `--check` included.

THE WIRE
--------
`numberSlots` 4 / `boolSlots` 16 against the shipped 144-bit word table — 3
batches, 50 wire bits, 0.350 s full refresh, 11 sync states. Settled in
`docs/local/m3-brief.md` §The wire at 18 slots / 52 bits for the 147-bit
table, retuned with the 12+12 geometry (operator-ruled 2026-08-17): at 144
bits the worst batch pins 16 bool words, so the two extra slots rode every
batch idle; the 28-bit shipped default stays for
composed avatars that cannot afford more, and this avatar carries no other
synced system. `batchSeconds` 0.1 and `indexLoops` 1 are the shipped defaults
and are deliberately not overridden. Three batches rather than two is what keeps
the tablet's Index readout reading as a counter.

WHAT STILL HAS TO HAPPEN ON THE DEMO'S PREFAB (stage 3/5, not here)
-------------------------------------------------------------------
The demo's copy of `ObjectSync.prefab` needs two edits this generator cannot
make — `globalParams` is a VRCFury field with no `CompileController` spelling,
and the `Drop` toggle is a component. **A VRCFury component cannot be edited in
place on a prefab: remove it and add a modified copy.**

1. `globalParams` on the `FullController`, replaced by the scoped match list
   `--check` prints. A match grammar, not an enumeration and not
   `allNonsyncedAreGlobal`: VRCFury matches a trailing `*` by prefix and lets a
   leading `!` exclude, so the composition scopes its own namespace and excludes
   what must stay capturable-proof, in four entries that never need touching. An
   enumeration is what rots — the stale name is dropped silently while the new
   one takes a per-build prefix, and the tablet's blendtrees bind to names that
   do not exist. The rationale for each entry is in `global_params()` below.
   **Verify any change on the BUILT avatar, not the source asset**: an entry that
   failed to land reads as prefixed post-bake and as fine everywhere else.
2. Delete the shipped `Drop` VRCFury `Toggle`. Stage 4 builds Freeze as a mode
   on `Sync_Target`'s own constraint animating the same `FreezeToWorld`, and two
   writers on one property is what the entry's two-writer rule forbids.
   Deleting it also reclaims its synced bit.
"""

import glob
import importlib.util
import os
import re as _re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The repo root — `compositions/<name>/` is always two levels down, the same
# arithmetic ENTRY below uses to reach the entry it composes.
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
# The entry is a sibling in this same checkout, which is what makes the wrong
# source unreachable rather than something a reader has to remember: whichever
# branch is checked out supplies both the composition and the entry it builds.
# When this generator lived in the venue it resolved the entry through
# `Packages/manifest.json`, because a static path there could name a different
# checkout than the Editor had loaded — a full green `--check` against the
# pre-refactor surface, measured.
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")

WIRE = {"numberSlots": 4, "boolSlots": 16}


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(
            f"REFUSE: the object-sync generator is not at {ENTRY} — this build "
            "is the entry's generator run over a different wire and cannot "
            "emit a document without it.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def demo_config(mod):
    cfg = dict(mod.CONFIG)
    cfg["wire"] = dict(mod.CONFIG["wire"], **WIRE)
    return cfg


def demo_document(mod, cfg):
    """The entry's document with the demo's one post-generation deviation applied.

    EVERY caller goes through here, `--check`'s byte-identical assertion
    included — a transform applied outside the regeneration path would make that
    assertion prove something other than what it says.

    THE DEVIATION: `Enable` defaults TRUE on this avatar.
    The shipped entry defaults it off, and that is the right posture for a
    composed avatar — a prop that resurrects itself on every avatar load is a
    worse failure than one that needs a toggle. This demo removes the menu
    control (m3-brief.md §Menu), so with the shipped default nothing would ever
    turn sync on: unsaved params re-default on every avatar load and every swap.

    A driver layer that stamped `Enable=1` on state entry was tried first and is
    the reason this deviation exists rather than that one. It leaves an OFF
    window exactly one frame wide, and one frame is the width that kills the
    measure rig: a VRChat contact receiver disabled and re-enabled WITHIN one
    frame, with its sender still inside its volume, is permanently deaf —
    `OnDisable` disposes the manager-side collision list that alone feeds
    `paramValue`, and `OnEnter` re-fires only on a sender RE-entering. The
    fingerprint is `IsColliding()` true, `paramValue` exactly 0,
    `restoreParamValue` holding the last real reading, and the whole rig reads
    zeros for the session. Defaulting the param true removes the OFF window
    instead of timing around it, so the trap is unreachable here rather than
    merely avoided.

    `vrc-patterns` is NOT touched: the entry keeps `default: 0` and its own
    `--check` keeps asserting that string. This is a consumer artifact in our
    project, which is what `CompileController` actually consumes.
    """
    text, f = mod.document(cfg)
    p = cfg["prefix"]
    shipped = (f"  {p}/Enable: {{ type: float, default: 0, "
               "vrc: { type: bool, synced: true, saved: false } }")
    ours = shipped.replace("default: 0", "default: 1")
    if text.count(shipped) != 1:
        raise SystemExit(
            f"REFUSE: the demo's Enable-default transform expected exactly one "
            f"occurrence of\n    {shipped}\nand found {text.count(shipped)}. The "
            "entry's declaration moved (generate.py emits it near the other "
            "wearer-facing params); re-derive the line before accepting a build "
            "whose sync silently never arms.")
    return text.replace(shipped, ours), f


def global_params(cfg):
    """The demo prefab's `globalParams`, as a match grammar rather than a list.

    A composition scopes its own namespace once instead of enumerating every name
    its two FullControllers share: VRCFury matches a trailing `*` by prefix and
    lets a leading `!` exclude, winning wherever it sits in the list. Enumerating
    is what drifts — rename a param upstream and the stale entry is dropped in
    silence while the new name takes an instance prefix, severing the link
    between the two merged controllers with the build still green. That is not
    hypothetical; it is what this list did before it was scoped.

    `Ch/Wire/Idx*` stays exposed deliberately: the tablet's Counter slot
    reconstructs a batch number from the index bools, and they are synced Bools a
    blend tree cannot read, so the readout walks them through a state ladder
    rather than a `blendtree-math` sum. Excluding the whole `Wire/` subtree would
    kill that readout.

    What the two exclusions have in common is **carried state**, not syncedness:
    a `globalParams` name is capturable, and a host avatar declaring it wins with
    *its* synced and saved flags (`../../../docs/gimmicks.md` §Packaging). The
    wire slots cross the network, so a captured one carries the host's `saved`
    across avatar loads; `Ch/Cycle` accumulates (+1 per loop tail), so a host
    capturing it as *synced* would put the wearer's count on every client — the
    argument `../../word-channel/README.md` §Ground truth makes for keeping it off
    every list. Note `Ch/Cycle` is itself unsynced, which is why "exclude the
    synced ones" is the wrong reading of this list.

    Everything else under the prefix goes bare and is meant to: the decoded AAPs
    and `Acquired` because consumers read them, and the per-client scratch
    (`Ch/SawHead`, `Ch/True`, `One`, the `B/…` floats) because it is recomputed
    from the wire every frame — capture cannot corrupt what nothing accumulates.
    That is the boundary to reason from when adding a param, not "is it
    interface".

    Entry-side exposure is unchanged by scoping — the six decoded AAPs the tablet
    displays and `<channel>/Acquired` all sit under the prefix. Gate the
    reconstruction view, the damper and any stand-in on `Acquired`, never on a
    `Ch/Cycle` threshold: the counter's thresholds are apply-discipline-dependent
    and it never leaves 0 on the wearer. `Acquired` reads 0 on the wearer and
    stays 1 through an Enable-off, so the consumer predicate is
    `IsLocal OR (Enable AND Ch/Acquired)` — all three terms, which is what the
    damper's rungs carry."""
    p, ch = cfg["prefix"], cfg["channel"]
    return [f"{p}/*", f"!{ch}/Cycle", f"!{ch}/Wire/Num*", f"!{ch}/Wire/Bool*"]


def main():
    mod = entry_module()
    cfg = demo_config(mod)
    text, f = demo_document(mod, cfg)
    facts = f["facts"]

    if facts["batchCount"] != 3 or facts["wireBits"] != 50:
        raise SystemExit(
            f"REFUSE: this build emits {facts['batchCount']} batches / "
            f"{facts['wireBits']} wire bits, but the settled configuration is 3 "
            "/ 50 (THE WIRE above). Either the slot widths above or the "
            "entry's word table moved; re-derive the table before accepting it.")

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        assert_(demo_document(mod, cfg)[0] == text, "regeneration is byte-identical")
        # The Enable-default deviation, the slot packing, and the on-disk
        # document are NOT re-asserted here: demo_document() refuses a build
        # where its transform found no line to rewrite, check_slots refuses an
        # unpackable config, the REFUSE above pins the settled 3-batch/50-bit
        # wire, and freshness of the committed document is regenerate-and-read-
        # git-diff (CONVENTIONS.md §Per-entry checks).
        # Printing the list left the prefab unpinned, and the prefab is the
        # hand-edited half — a wrong entry there lands silently (VRCFury exposes
        # nothing and says nothing) and no compile or gate reads globalParams.
        # Scoping the list shortened it; it did not make it self-checking, and a
        # mistyped wildcard fails exactly as quietly as a mistyped name once did.
        # word-channel's generator carries the same assert for the same reason.
        want_gp = global_params(cfg)
        print("  globalParams for the demo prefab:")
        for n in want_gp:
            print(f"    {n}")
        # A stale exclusion fails the OPPOSITE way to a stale enumeration, so it
        # needs its own assert. An enumeration going stale under-exposes and the
        # break is loud in behaviour; a `!` whose stem no longer names anything
        # silently WIDENS the list, handing the wire slots to the first host
        # avatar that declares them. Zero matches is the whole failure mode.
        for entry in [e for e in want_gp if e.startswith("!")]:
            stem = entry[1:].rstrip("*")
            assert_(stem in text,
                    f"exclusion `{entry}` still names a declared param — the stem "
                    f"`{stem}` appears in the emitted document (a rename upstream "
                    f"leaves this matching nothing, and the exclusion widens to "
                    f"expose what it was written to withhold)")
        pf_path = os.path.join(HERE, "ObjectSyncDemo.prefab")
        if os.path.exists(pf_path):
            body = open(pf_path, encoding="utf-8").read()
            blocks, cur, inside = [], [], False
            for ln in body.splitlines():
                if ln.strip() == "globalParams:":
                    inside, cur = True, []
                elif inside:
                    if ln.startswith("        - "):
                        # A leading `!` is a YAML tag indicator, so Unity writes
                        # every negation single-quoted — strip that, not the `!`.
                        cur.append(ln.split("- ", 1)[1].strip().strip("'\""))
                    else:
                        blocks.append(cur)
                        inside = False
            if inside:
                blocks.append(cur)
            # Keyed on the prefix, not on a member name: the scoped list holds no
            # bare param name for a membership test to find.
            entry_blocks = [b for b in blocks
                            if any(e.lstrip("!").startswith(f"{cfg['prefix']}/") for e in b)]
            assert_(len(entry_blocks) == 2 and all(b == want_gp for b in entry_blocks),
                    f"both of the prefab's object-sync globalParams blocks are "
                    f"exactly the {len(want_gp)} entries above, in order "
                    f"({[b for b in entry_blocks if b != want_gp][:1]})")
            # This arrangement pins two rigs to world through the composed
            # entries' own never-instantiated `World.prefab` assets, and a broken
            # reference there resolves to null — the rig silently rides the avatar
            # instead of the world, which reads correct at the origin. The entry's
            # own `--check` guards its three prefabs; this prefab is a fourth
            # consumer of the same assets, and a composition is exactly what rots
            # when something it composes changes shape. Resolve each reference
            # against whichever entry owns its GUID rather than naming the two
            # entries here, so composing a third pinned entry needs no edit.
            world = {}
            for meta in glob.glob(os.path.join(REPO, "*", "assets",
                                               "World.prefab.meta")):
                asset = meta[:-len(".meta")]
                g = _re.search(r"^guid: ([0-9a-f]{32})$",
                               open(meta, encoding="utf-8").read(), _re.M)
                if g and os.path.exists(asset):
                    world[g.group(1)] = (
                        os.path.basename(os.path.dirname(os.path.dirname(meta))),
                        set(_re.findall(r"^--- !u!4 &(-?\d+)$",
                                        open(asset, encoding="utf-8").read(), _re.M)))
            refs = _re.findall(
                r"SourceTransform: \{fileID: (-?\d+), guid: ([0-9a-f]{32})", body)
            dangling = [r for r in refs
                        if r[1] not in world or r[0] not in world[r[1]][1]]
            assert_(bool(refs) and not dangling,
                    f"all {len(refs)} of the prefab's cross-asset pin sources "
                    f"resolve to a Transform in a composed entry's World.prefab "
                    f"({sorted({world[g][0] for _, g in refs if g in world})}) "
                    f"— dangling: {sorted(set(dangling))}")
        else:
            assert_(False, f"ObjectSyncDemo.prefab is missing ({pf_path})")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.3f}s refresh")
        print("scope: emit determinism and hand-maintained wiring only — freshness "
              "of committed generated files is regenerate-and-read-git-diff; "
              "document structure, prefab behavior and runtime are unverified here")
        sys.exit(0 if ok else 1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(f['layers'])} layers, "
          f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
          f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
          f"~{facts['cycleSeconds']:.3f}s refresh @60fps")


if __name__ == "__main__":
    main()
