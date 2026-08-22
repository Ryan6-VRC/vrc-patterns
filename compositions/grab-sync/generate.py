#!/usr/bin/env python3
"""This composition's own `object-sync` build: the shipped entry's generator run
at four heading-only objects, emitting beside this file instead of into the entry.

    python compositions/grab-sync/generate.py           # writes the document
    python compositions/grab-sync/generate.py --check   # asserts, writes nothing

Output: `object-sync/controller.yaml` beside this file. Compile it with
`CompileController` into `object-sync/built/` beside it; MultiGrabSync's nested
sync instance points at that build, never at `../../object-sync/built/`.

The build lives here and not as a fourth entry preset for `object-sync-demo`'s
reason (its generate.py header): `committed_configs()` emits a public document
per label, and this configuration has one consumer. The entry's generator is
imported unmodified; the entry stays byte-identical.

THE CONFIGURATION
-----------------
Four objects, heading-only, one slice each — `MultiGrabSync.prefab`'s four
props, none hotter than another. Everything else is the entry's shipped CONFIG:
the wire block, the shipped default-off `Enable` (the glue controller's
host-capture declaration is what arms it, same as GrabSync at N=1), no menu.
Object names `Prop0..Prop3` follow the entry's own multi-object example; the
emitted surface is the `SyncProp{N}` / `SyncProp{N}_Target` pairs and a
per-object collision-tag set, both printed in the document header.

The composition's glue reaches only the published interface
(`ObjectSync/Enable`, `ObjectSync/Ready`), so its `globalParams` needs no
internal namespaces and no grammar beyond those two names.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")

OBJECTS = [{"name": f"Prop{i}", "rotation": "y"} for i in range(4)]


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(
            f"REFUSE: the object-sync generator is not at {ENTRY} — this build "
            "is the entry's generator run at a different object list and cannot "
            "emit a document without it.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def grabsync_config(mod):
    cfg = dict(mod.CONFIG)
    cfg["objects"] = [dict(ob) for ob in OBJECTS]
    return cfg


def main():
    mod = entry_module()
    cfg = grabsync_config(mod)
    text, f = mod.document(cfg)
    facts = f["facts"]

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        assert_(mod.document(cfg)[0] == text, "regeneration is byte-identical")
        tags = [mod.tag_set(cfg, ob["name"]) for ob in cfg["objects"]]
        flat = [t for ts in tags for t in ts]
        assert_(len(flat) == len(set(flat)),
                f"collision tags unique across objects and stages ({len(flat)} tags)")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.3f}s refresh")
        print("scope: emit determinism only — freshness of the committed document "
              "is regenerate-and-read-git-diff; the hand-extended rig prefab is "
              "verified against the document's printed tag and node lists, not here")
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
