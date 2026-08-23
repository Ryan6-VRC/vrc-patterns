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


def cell_nodes():
    """`grab-prop`'s prefab read as (guid, transforms, components), where transforms
    maps a Transform fileID -> (own name, parent name) and components map a component
    fileID -> its owning GameObject's name.

    Two things this composition needs it for. It names the target of any instance
    modification reaching into a nested `GrabProp`, so the pins below can say which
    node an override lands on rather than trusting a bare fileID. And it carries the
    `Container` <- `SourcePosition` parent edge: the cell's stale read is that
    hierarchy relation now, so a composition that re-parented the sample cell back
    out from under `Container` would lose the capture with every clip identical."""
    import re
    entry = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, "grab-prop"))
    prefab = os.path.join(entry, "GrabProp.prefab")
    meta = prefab + ".meta"
    if not (os.path.exists(prefab) and os.path.exists(meta)):
        raise SystemExit(
            f"REFUSE: the grab-prop entry is not at {entry} — this composition nests "
            "its prefab, and the cell's nodes cannot be resolved without it.")
    guid = re.search(r"guid: (\w+)", open(meta, encoding="utf-8").read()).group(1)
    docs = prefab_docs(prefab)
    go_name = {a: re.search(r"m_Name: (.*)", b).group(1).strip()
               for c, a, b in docs if c == 1 and "m_Name:" in b}
    owner = {a: go_name.get(int(re.search(r"m_GameObject: \{fileID: (\d+)", b).group(1)), "?")
             for c, a, b in docs if c in (4, 114) and "m_GameObject:" in b}
    father = {a: int(re.search(r"m_Father: \{fileID: (\d+)", b).group(1))
              for c, a, b in docs if c == 4}
    transforms = {a: (owner[a], owner.get(father[a], "<root>")) for a in father}
    return guid, transforms, {a: owner[a] for a in owner if a not in father}


def prefab_pins(assert_):
    """The handful of prefab pins CONVENTIONS assigns a composition's check:
    the drift classes nothing else reads (the cell's untouched sample edge,
    physbone params, Payload removals, controller wiring).

    The cell's own rig is NOT here — that is `grab-prop`'s prefab, nested rather
    than inline. What survives here is the half no entry can see: this composition
    holds four nested copies of that cell and can override any of them, and the
    capture order is now the `Container` <- `SourcePosition` hierarchy relation,
    which an instance override could re-parent or out-rank without touching a clip
    (`../../grab-prop/README.md` §How it works owns the measurement)."""
    import re
    cell_guid, cell_tf, cell_comp = cell_nodes()
    sp = [n for n, (nm, par) in cell_tf.items() if nm == "SourcePosition"]
    assert_(len(sp) == 1 and cell_tf[sp[0]][1] == "Container",
            "grab-prop cell: SourcePosition is a child of Container "
            f"(parent is {cell_tf[sp[0]][1]!r})" if len(sp) == 1
            else f"grab-prop cell: one SourcePosition node ({len(sp)} found)")
    sp_fid = sp[0] if len(sp) == 1 else None

    for prefab, props in (("GrabSync.prefab", [""]),
                          ("MultiGrabSync.prefab", ["_0", "_1", "_2", "_3"])):
        path = os.path.join(HERE, prefab)
        raw = open(path, encoding="utf-8").read()
        docs = prefab_docs(path)

        # Group modifications per PrefabInstance document — the four nested GrabProp
        # instances share one base fileID+guid, so a global grouping collapses them.
        mod_re = re.compile(
            r"- target: \{fileID: (\d+), guid: (\w+), type: 3\}\n"
            r"      propertyPath: ([^\n]+)\n      value: ([^\n]*)\n"
            r"      objectReference: \{fileID: (\d+)\}")
        params, added_sources, moved_cells = [], [], []
        for c, a, b in docs:
            if c != 1001:
                continue
            by_target = {}
            for fid, guid, pp, val, ref in mod_re.findall(b):
                by_target.setdefault((int(fid), guid), {})[pp] = (val, ref)
            for (fid, guid), m in by_target.items():
                if guid != cell_guid:
                    continue
                # An added source on the sample cell reorders the solve — the
                # operation measured as behaviour-changing even at weight 0, and
                # the shape the retired depth ladder wired in.
                if cell_comp.get(fid) == "SourcePosition" and any(
                        p.startswith("Sources.") for p in m):
                    added_sources.append(f"&{a} ({sorted(p for p in m if p.startswith('Sources.'))})")
                # A re-parent or a re-position of the sample cell breaks the
                # hierarchy relation the capture rests on.
                if fid == sp_fid and any(
                        p.startswith(("m_Father", "m_LocalPosition", "m_LocalRotation"))
                        for p in m):
                    moved_cells.append(f"&{a}")
                if m.get("parameter", ("",))[0].startswith("Grab"):
                    params.append(m["parameter"][0])
        assert_(not added_sources,
                f"{prefab}: no added source on the cell SourcePosition constraint "
                f"(found on {added_sources})")
        assert_(not moved_cells,
                f"{prefab}: no nested instance re-parents or re-poses SourcePosition "
                f"(found on {moved_cells})")
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
