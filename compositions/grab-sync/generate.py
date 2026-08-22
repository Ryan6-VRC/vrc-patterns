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


def prefab_docs(path):
    """Split a Unity YAML asset into (classId, anchor, body) documents."""
    import re
    docs = []
    for m in re.finditer(r"^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)",
                         open(path, encoding="utf-8").read(),
                         re.M | re.S):
        docs.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return docs


def prefab_pins(assert_):
    """The handful of prefab pins CONVENTIONS assigns a composition's check:
    the drift classes nothing else reads (ladder shape, tip edges, physbone
    params, Payload removals, controller wiring)."""
    import re
    for prefab, props in (("GrabSync.prefab", [""]),
                          ("MultiGrabSync.prefab", ["_0", "_1", "_2", "_3"])):
        path = os.path.join(HERE, prefab)
        raw = open(path, encoding="utf-8").read()
        docs = prefab_docs(path)

        # ladder: 16 nodes, each constraint inactive, chained to its predecessor
        go_name = {a: re.search(r"m_Name: (.*)", b).group(1)
                   for c, a, b in docs if c == 1 and "m_Name:" in b}
        tf_go = {a: int(re.search(r"m_GameObject: \{fileID: (\d+)", b).group(1))
                 for c, a, b in docs if c == 4}
        depth_names = sorted(n for n in go_name.values() if re.fullmatch(r"Depth\d\d", n))
        assert_(depth_names == [f"Depth{i:02d}" for i in range(1, 17)],
                f"{prefab}: ladder is Depth01..16 ({len(depth_names)} nodes)")
        chained = 0
        for c, a, b in docs:
            if c != 114 or "cachedExecutionGroupIndex" not in b:
                continue
            owner = go_name.get(int(re.search(r"m_GameObject: \{fileID: (\d+)", b).group(1)), "")
            if not re.fullmatch(r"Depth\d\d", owner):
                continue
            assert_(re.search(r"IsActive: 0", b) is not None, f"{prefab}: {owner} IsActive off")
            src = re.search(r"SourceTransform: \{fileID: (\d+)\}", b)
            if owner == "Depth01":
                assert_(src is None or src.group(1) == "0", f"{prefab}: Depth01 has no source")
            else:
                prev = f"Depth{int(owner[5:]) - 1:02d}"
                got = go_name.get(tf_go.get(int(src.group(1)), 0), "?") if src else "none"
                assert_(got == prev, f"{prefab}: {owner} sources {prev}")
                chained += 1
        assert_(chained == 15, f"{prefab}: ladder chain continuous (15 links)")

        # tip edges: per prop, source1 -> transform + explicit weight 0 + totalLength 2.
        # Group modifications per PrefabInstance document — the four nested GrabProp
        # instances share one base fileID+guid, so a global grouping collapses them.
        mod_re = re.compile(
            r"- target: \{fileID: (\d+), guid: (\w+), type: 3\}\n"
            r"      propertyPath: ([^\n]+)\n      value: ([^\n]*)\n"
            r"      objectReference: \{fileID: (\d+)\}")
        params, tip_count = [], 0
        for c, a, b in docs:
            if c != 1001:
                continue
            by_target = {}
            for fid, guid, pp, val, ref in mod_re.findall(b):
                by_target.setdefault((fid, guid), {})[pp] = (val, ref)
            for t, m in by_target.items():
                if "Sources.source1.SourceTransform" in m:
                    tip_count += 1
                    assert_(m.get("Sources.source1.Weight", ("?",))[0] == "0",
                            f"{prefab}: tip weight 0 recorded (instance &{a})")
                    assert_(m.get("Sources.totalLength", ("?",))[0] == "2",
                            f"{prefab}: tip totalLength 2 (instance &{a})")
                if m.get("parameter", ("",))[0].startswith("Grab"):
                    params.append(m["parameter"][0])
        assert_(tip_count == len(props), f"{prefab}: {len(props)} tip edge(s)")
        params = sorted(params)
        assert_(params == sorted("Grab" + s for s in props),
                f"{prefab}: physbone parameters {params}")
        payload_removals = raw.count("4257538466046114012, guid: db55e975")
        assert_(payload_removals == len(props),
                f"{prefab}: Payload removed on all {len(props)} GrabProp instance(s)")

        # FullController wired to this composition's own build
        ctrl = "GrabSync_Fx" if prefab == "GrabSync.prefab" else "MultiGrabSync_Fx"
        meta = os.path.join(HERE, "built", ctrl + ".controller.meta")
        guid = re.search(r"guid: (\w+)", open(meta, encoding="utf-8").read()).group(1)
        assert_(guid in raw, f"{prefab}: FullController resolves to built/{ctrl}.controller")


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
        prefab_pins(assert_)
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.3f}s refresh")
        print("scope: emit determinism plus the prefab pins above - freshness of "
              "the committed document is regenerate-and-read-git-diff; the sync "
              "rig prefab's node/tag lists are verified against the document's "
              "printed header, not here")
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
