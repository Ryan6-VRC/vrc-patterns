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
`check()`'s `[committed vs disk]` block pins a `controller.yaml` on disk for
every label `preset_configs()` returns, so a `demo` preset would either fail
`--check` or force a fourth build, prefab and README claim into the public entry
for a single consumer. The composition drives the entry's generator from outside
instead: `object-sync/generate.py` is imported unmodified and the entry stays
byte-identical. `CONVENTIONS.md` §compositions/ is the rule this implements.

The demo carries exactly one post-generation deviation from the entry's emitted
document — `Enable` defaults true — applied in `demo_document()`, which owns the
reason. Every emission path goes through it, `--check` included.

THE WIRE
--------
`numberSlots` 4 / `boolSlots` 18 against the shipped 147-bit word table — 3
batches, 52 wire bits, 0.350 s full refresh, 11 sync states. Settled in
`docs/local/m3-brief.md` §The wire; the 28-bit shipped default stays for
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

1. `globalParams` on the `FullController`, extended from the shipped single
   entry to the enumerated list `--check` prints. Enumerated, not
   `allNonsyncedAreGlobal`: without it VRCFury prefixes every param with a
   per-build token and the tablet's blendtrees bind to names that do not exist.
   The list is the durable record and grows with its consumers — `Ch/Cycle`
   was added for a reconstruction-side consumer after the tablet's nine, and
   the rationale for each entry is in `global_params()` below. **Verify an
   extension on the BUILT avatar, not the source asset**: a name that failed to
   land reads as prefixed post-bake and as fine everywhere else.
2. Delete the shipped `Drop` VRCFury `Toggle`. Stage 4 builds Freeze as a mode
   on `Sync_Target`'s own constraint animating the same `FreezeToWorld`, and two
   writers on one property is what the entry's two-writer rule forbids.
   Deleting it also reclaims its synced bit.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
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

WIRE = {"numberSlots": 4, "boolSlots": 18}


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


def global_params(mod, cfg, facts):
    """What the demo prefab's `globalParams` has to enumerate.

    Derived from the emitted document, so a retune of the wire or the word table
    moves this list rather than silently leaving a consumer bound to a name
    VRCFury prefixed away. Three consumers, three reasons:

    - the six position words are what the tablet displays;
    - the index bools are what its Counter slot reconstructs a batch number
      from. They are synced **Bools**, and a blend tree evaluates only Floats —
      word-channel floatifies its *word* bools into `ObjectSync/B/…` but never
      its own index bits, so a consumer reads them through a state ladder, not
      a `blendtree-math` sum (stage 5 measured this the hard way);
    - `Sync_Valid` is the entry's own answer to "is the pose `Sync` reports
      correct on this client" — true on the wearer always, true on a remote
      once decoded, false on a remote otherwise. Gate the reconstruction view
      and any stand-in on THIS, not on `Ch/Cycle >= 2`: that re-derives a gate
      the entry already evaluates, and `Cycle` never leaves 0 on the wearer,
      which runs encode/send layers and no receive layers. `Cycle` is still
      exported by the entry as a freshness counter; add it back to this list
      in one line if a readout wants it."""
    o = cfg["objects"][0]["name"]
    return ([f"{cfg['prefix']}/Enable", f"{cfg['prefix']}/Sync_Valid"]
            + [f"{o}/P{a}/{stage}" for a in mod.AXES for stage in ("C", "F")]
            + [f"{cfg['channel']}/Wire/Idx{i}" for i in range(facts["indexBits"])])


def main():
    mod = entry_module()
    cfg = demo_config(mod)
    text, f = demo_document(mod, cfg)
    facts = f["facts"]

    if facts["batchCount"] != 3 or facts["wireBits"] != 52:
        raise SystemExit(
            f"REFUSE: this build emits {facts['batchCount']} batches / "
            f"{facts['wireBits']} wire bits, but the settled configuration is 3 "
            "/ 52 (m3-brief.md §The wire). Either the slot widths above or the "
            "entry's word table moved; re-derive the table before accepting it.")

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        assert_(demo_document(mod, cfg)[0] == text, "regeneration is byte-identical")
        assert_(f"  {cfg['prefix']}/Enable: {{ type: float, default: 1, " in text,
                "Enable defaults TRUE (demo-local deviation; see demo_document)")
        # The one property the widened slots could break: word-channel first-fits
        # runs into batches, so a wider batch pulls more groups into it and each
        # of those groups' bools have to fit alongside. `check_slots` refuses the
        # unplaceable case; this asserts the placement actually landed.
        nb, bb, gb = facts["numberBatches"], facts["boolBatches"], facts["groupBatch"]
        for g in facts["groups"]:
            i = gb.get(g)
            want_n = [w["name"] for w in facts["numberWords"] if w["group"] == g]
            want_b = [w["name"] for w in facts["boolWords"] if w["group"] == g]
            got_n = [w["name"] for w in (nb[i] if i is not None and i < len(nb) else [])]
            got_b = [w["name"] for w in (bb[i] if i is not None and i < len(bb) else [])]
            assert_(i is not None and all(n in got_n for n in want_n)
                    and all(n in got_b for n in want_b),
                    f"group {g}: {len(want_n)} number + {len(want_b)} bool words "
                    f"co-batched at batch {(i or 0) + 1}")
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8", newline="") as fh:
                assert_(fh.read().replace("\r\n", "\n") == text,
                        "controller.yaml on disk matches this config")
        else:
            assert_(False, f"controller.yaml is missing ({OUT})")
        print("  globalParams for the demo prefab:")
        for n in global_params(mod, cfg, facts):
            print(f"    {n}")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.3f}s refresh")
        sys.exit(0 if ok else 1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(f['layers'])} layers, "
          f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
          f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
          f"~{facts['cycleSeconds']:.3f}s refresh @60fps")


if __name__ == "__main__":
    main()
