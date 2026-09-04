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

The demo carries NO post-generation deviation: the entry's document is emitted
and committed unmodified, and its one departure from the entry's shipped posture
— `Enable` defaults true — is `enableDefault: 1` in `demo_config()`.

THE WIRE
--------
`numberSlots` 4 / `boolSlots` 16 against the shipped 144-bit word table — 3
batches, 50 wire bits, 0.350 s full refresh, 11 sync states. 16 bool slots is
the size the table wants: at 144 bits the worst batch pins exactly 16 bool
words, so a wider slot set rides every batch idle. The entry's 28-bit default
stays for composed avatars that cannot afford more; this avatar carries no
other synced system. `batchSeconds` 0.1 and `indexLoops` 1 are the shipped
defaults and are deliberately not overridden. Three batches rather than two is what keeps
the tablet's Index readout reading as a counter.

THE SHARED COMPONENT (the prefab half this generator cannot author)
-------------------------------------------------------------------
The demo's `Demo_Fx` and its object-sync build merge through ONE FullController
on the prefab root — the sealed-interface coupling: the
entry publishes `Enable` alone, and everything else the tablet reads (`OS/D/*`
decoded AAPs, `OS/Ch/Wire/Idx*`, `OS/Ready`, `OSCh/Acquired`) is reachable only
because one component prefixes both controllers identically and the shared
names unify. The component's `globalParams` list is exactly the entry's
derived `ObjectSync/*` (matching `Enable` alone), and `--check` pins it.
Splitting the two controllers back onto two components
un-unifies every shared name with no build error — the param-rewrite memo is
per component (measured) — so `--check` also refuses a second
FullController. The `Drop` toggle stays deleted (its `FreezeToWorld` writer
would fight the Freeze mode; the entry's two-writer rule).

Both controllers sit at the prefab ROOT (the demo is a variant of the entry's
prefab, so the rig root IS the composition root) — bindings stay rig-relative
and this build emits at the default `mountPath ""`, unlike `grab-sync`, whose
rig is a nested child.
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
    # This demo removes the menu control, so with the entry's shipped
    # default-off nothing would ever turn sync on.
    cfg["enableDefault"] = 1
    return cfg


def main():
    mod = entry_module()
    cfg = demo_config(mod)
    text, f = mod.document(cfg)
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

        # The prefab is the hand-edited half — a wrong globalParams entry or a
        # split component lands silently (VRCFury exposes nothing and says
        # nothing) and no compile or gate reads either.
        want_gp = facts["globalParams"]
        print("  globalParams for the shared FullController (the entry's own "
              f"derived list): {want_gp}")
        # Demo_Fx binds sealed entry names directly (`OS/D/*`,
        # `OS/Ch/Wire/Idx*`, `OS/Ready`, `OSCh/Acquired`) — hard couplings to
        # the entry's CONFIG keys that unify only when the entry actually
        # declares the name. A rename upstream leaves this document binding a
        # name the entry does not declare: VRCFury mints a second prefixed
        # param, the tablet reads a flat zero, and no build errors. Comments
        # stripped first, so prose naming an entry-owned param cannot fail it.
        roots = {cfg["prefix"].split("/")[0], cfg["internal"].split("/")[0],
                 cfg["channel"].split("/")[0]}
        own = _re.sub(r"#.*", "", open(os.path.join(HERE, "controller.yaml"),
                                       encoding="utf-8").read())
        reached = sorted({n for n in
                          _re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", own)
                          if n.split("/")[0] in roots})
        declared = set(_re.findall(r"^  ([^\s#:]+):", text, _re.M))
        missing = [n for n in reached if n not in declared]
        assert_(reached and not missing,
                f"every entry-rooted name Demo_Fx binds is declared by this "
                f"build's document ({len(reached)} names) — undeclared: {missing}")
        pf_path = os.path.join(HERE, "ObjectSyncDemo.prefab")
        if os.path.exists(pf_path):
            body = open(pf_path, encoding="utf-8").read()
            # The sealed coupling: Demo_Fx and the object-sync build on ONE
            # FullController, authored on this variant root (the inherited
            # entry component is removed — remove-and-add, the one redirect a
            # VRCFury component supports). A second component holding either
            # controller un-unifies every shared name with no build error: the
            # param-rewrite memo is per component (measured).
            # Counted over FullController blocks that reference EITHER
            # controller, not over all of them — the composed anti-cull ships
            # its own component legitimately.
            fc_blocks = [m.group(0) for m in
                         _re.finditer(r"^--- !u!114 &-?\d+\n(.*?)(?=^--- |\Z)",
                                      body, _re.M | _re.S)
                         if "class: FullController" in m.group(0)]
            ours = [b for b in fc_blocks
                    if "Demo_Fx.controller" in b
                    or "object-sync-demo/object-sync/built/" in b]
            assert_(len(ours) == 1,
                    "Demo_Fx and the object-sync build share exactly ONE "
                    f"FullController (found in {len(ours)} components of "
                    f"{len(fc_blocks)} total)")
            # The demo is a VARIANT of the entry prefab, so the entry's own
            # FullController arrives inherited and text-invisible; only its
            # m_RemovedComponents row proves the double build is off.
            entry_pf = os.path.join(REPO, "object-sync", "ObjectSync.prefab")
            entry_guid = _re.search(
                r"^guid: ([0-9a-f]{32})$",
                open(entry_pf + ".meta", encoding="utf-8").read(), _re.M).group(1)
            entry_fcs = []
            for m in _re.finditer(r"^--- !u!114 &(-?\d+)\n(.*?)(?=^--- |\Z)",
                                  open(entry_pf, encoding="utf-8").read(),
                                  _re.M | _re.S):
                if "class: FullController" in m.group(2):
                    entry_fcs.append(m.group(1))
            removed = "".join(_re.findall(
                r"m_RemovedComponents:\n((?:    - \{fileID: .+\n)+)", body))
            gone = [a for a in entry_fcs
                    if f"fileID: {a}, guid: {entry_guid}" in removed]
            assert_(entry_fcs and gone == entry_fcs,
                    f"the inherited entry FullController(s) {entry_fcs} are "
                    f"removed — removed rows carry {gone}")
            blocks, cur, inside = [], [], False
            for ln in body.splitlines():
                if ln.strip() == "globalParams:":
                    inside, cur = True, []
                elif inside:
                    if ln.startswith("        - "):
                        cur.append(ln.split("- ", 1)[1].strip().strip("'\""))
                    else:
                        blocks.append(cur)
                        inside = False
            if inside:
                blocks.append(cur)
            entry_blocks = [b for b in blocks
                            if any(e.lstrip("!").startswith(f"{cfg['prefix']}/")
                                   or e.lstrip("!").startswith(f"{cfg['internal']}/")
                                   for e in b)]
            assert_(entry_blocks == [want_gp],
                    f"the one entry-touching globalParams block is exactly the "
                    f"entry's derived list {want_gp} — got {entry_blocks}")
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
