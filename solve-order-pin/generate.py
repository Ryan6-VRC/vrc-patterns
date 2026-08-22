#!/usr/bin/env python3
"""Check-only: this entry generates nothing, but its prefab is hand-maintained
and two of its states fail silently.

    python solve-order-pin/generate.py --check   # asserts, writes nothing

`Ladder` ACTIVE in the serialized prefab: its constraints join the solver on the
object's first activation, so shipped inactive they never join and the module pins
nothing while looking identical in every static inspection.

`Ladder` holding more than a Transform: AAO merges a bare-Transform holder and
reparents the whole chain.

These pins read the ladder where it now lives; they were in
`compositions/grab-sync/generate.py` while it was inline there.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PREFAB = os.path.join(HERE, "SolveOrderPin.prefab")
DEPTH = 16


def prefab_docs(path):
    """Split a Unity YAML asset into (classId, anchor, body) documents."""
    return [(int(m.group(1)), int(m.group(2)), m.group(3))
            for m in re.finditer(r"^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)",
                                 open(path, encoding="utf-8").read(), re.M | re.S)]


def prefab_pins(assert_):
    docs = prefab_docs(PREFAB)
    raw = open(PREFAB, encoding="utf-8").read()

    go = {a: b for c, a, b in docs if c == 1}
    name = {a: re.search(r"m_Name: (.*)", b).group(1).strip() for a, b in go.items()}
    tf_go = {a: int(re.search(r"m_GameObject: \{fileID: (\d+)", b).group(1))
             for c, a, b in docs if c == 4}
    by_name = {n: a for a, n in name.items()}

    # the ladder: DEPTH nodes, each chained to its predecessor at weight 0, none solving
    depth_names = sorted(n for n in name.values() if re.fullmatch(r"Depth\d\d", n))
    assert_(depth_names == [f"Depth{i:02d}" for i in range(1, DEPTH + 1)],
            f"ladder is Depth01..{DEPTH:02d} ({len(depth_names)} nodes)")

    chained = 0
    for c, a, b in docs:
        if c != 114 or "cachedExecutionGroupIndex" not in b:
            continue
        owner = name.get(int(re.search(r"m_GameObject: \{fileID: (\d+)", b).group(1)), "")
        if not re.fullmatch(r"Depth\d\d", owner):
            continue
        assert_("IsActive: 0" in b, f"{owner}: constraint never solves (IsActive 0)")
        assert_("m_Enabled: 1" in b, f"{owner}: component enabled (d4rk strips a disabled one)")
        assert_("SolveInLocalSpace: 0" in b, f"{owner}: SolveInLocalSpace 0")
        src = re.search(r"SourceTransform: \{fileID: (\d+)\}", b)
        if owner == "Depth01":
            assert_(src is None or src.group(1) == "0", "Depth01 is the chain base (no source)")
            continue
        prev = f"Depth{int(owner[5:]) - 1:02d}"
        got = name.get(tf_go.get(int(src.group(1)), 0), "?") if src else "none"
        assert_(got == prev, f"{owner} sources {prev}")
        weight = re.search(r"SourceTransform: \{fileID: \d+\}\n      Weight: (\S+)", b)
        assert_(weight is not None and float(weight.group(1)) == 0,
                f"{owner}: source weight 0 (a nonzero weight would make it drive)")
        chained += 1
    assert_(chained == DEPTH - 1, f"ladder chain continuous ({DEPTH - 1} links)")

    # the holder: active at load, and not a bare Transform
    ladder = by_name.get("Ladder")
    assert_(ladder is not None, "prefab carries a Ladder holder")
    if ladder is not None:
        assert_(re.search(r"m_IsActive: 1", go[ladder]) is not None,
                "Ladder ACTIVE in the serialized prefab - inactive never joins the solver")
        comps = re.findall(r"component: \{fileID: (\d+)\}", go[ladder])
        assert_(len(comps) > 1,
                f"Ladder holds more than a Transform ({len(comps)} components) - "
                "AAO merges a Transform-only holder and reparents the chain")

    # the off-write's binding path must name the holder. Renaming the node compiles clean,
    # passes the gate, and animates nothing - the ladder then never switches off.
    yaml_src = open(os.path.join(HERE, "controller.yaml"), encoding="utf-8").read()
    bind = re.search(r'"([^"]+)/GameObject\.m_IsActive"', yaml_src)
    assert_(bind is not None, "controller.yaml carries a GameObject.m_IsActive binding")
    if bind is not None:
        assert_(bind.group(1) == "Ladder",
                f"off-write binds the holder by name (binds '{bind.group(1)}', node is 'Ladder')")

    # the animator half is wired to this entry's own build
    meta = os.path.join(HERE, "built", "SolveOrderPin_Fx.controller.meta")
    if os.path.exists(meta):
        guid = re.search(r"guid: (\w+)", open(meta, encoding="utf-8").read()).group(1)
        assert_(guid in raw, "FullController resolves to built/SolveOrderPin_Fx.controller")
    else:
        assert_(False, f"missing {os.path.relpath(meta, HERE)}")


def main():
    if "--check" not in sys.argv:
        raise SystemExit(__doc__.strip() + "\n\nNothing to generate; pass --check.")
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond

    prefab_pins(assert_)
    print("scope: the prefab's hand-maintained rig only - says nothing about whether "
          "the pin actually lands on a consuming avatar (that is a play-mode read, "
          "README section 'Verifying the install'), nor about the tip edge, which "
          "lives on the consumer's own constraint and is not in this file")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
