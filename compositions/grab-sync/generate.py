#!/usr/bin/env python3
"""This composition's own `object-sync` builds: the shipped entry's generator
run twice, emitting beside this file instead of into the entry.

    python compositions/grab-sync/generate.py           # writes both documents
    python compositions/grab-sync/generate.py --check   # asserts, writes nothing

Output: `object-sync/controller.yaml` (four heading-only objects, for
MultiGrabSync) and `object-sync-single/controller.yaml` (one heading-only
object, for GrabSync), each compiled with `CompileController` into the `built/`
beside it. Neither prefab points at `../../object-sync/built/`: the entry's
committed builds emit at mountPath "" and cannot merge through the shared
component below.

The builds live here and not as entry presets for `object-sync-demo`'s reason
(its generate.py header): `committed_configs()` emits a public document per
label, and these configurations have one consumer each. The entry's generator
is imported unmodified; the entry stays byte-identical.

THE CONFIGURATION
-----------------
Both builds are the entry's shipped CONFIG — the wire block, the default
`rigSeed` (each is the only object-sync build on its avatar, so the default
tags and park hold), the shipped default-off `Enable` (the glue controller's
first-wins declaration is what arms it), no menu — at `mountPath "ObjectSync"`:
the sync rig is the nested GO of that name under each composition root, and the
root's FullController is SHARED, carrying the glue controller and the sync
build together. That sharing is the whole coupling mechanism since the entry
sealed its interface: one component prefixes both
controllers identically, so the glue's reads of `OS/Ready` and the entry's
writes are one parameter, with no `globalParams` exposure beyond the entry's
own derived list (`ObjectSync/*`, matching `Enable` alone). Controller ORDER in
that component is load-bearing — the glue sits first, so its `Enable`
declaration (default 1) wins the first-wins param merge; controller.yaml's
header owns the mechanism and the check below pins the order.

The four-object build's names are `PropA..PropD` (one letter per slot, matching
the glue controller's layers and the prefab's four prop GameObjects); the
emitted surface is the `SyncProp{X}` / `SyncProp{X}_Target` pairs and a
per-object collision-tag set, both printed in the document header. The single
build is the entry's own default single `Prop`, matching the nested `y/` prefab
instance GrabSync composes.
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")
OUT_SINGLE = os.path.join(HERE, "object-sync-single", "controller.yaml")

OBJECTS = [{"name": n, "rotation": "y"} for n in ("PropA", "PropB", "PropC", "PropD")]

# multi.yaml's per-prop suffixes, read off OBJECTS so the letters have one source:
# the layer, the params, the clip names and the binding paths all take these.
PROPS = tuple(ob["name"][len("Prop"):] for ob in OBJECTS)

# The nested sync rig's GO name under each composition root — the hand-
# maintained pairing mountPath buys: the emitted bindings prefix this string,
# and the check below reads it back off both prefabs.
MOUNT = "ObjectSync"


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
    cfg["mountPath"] = MOUNT
    return cfg


def grabsync_single_config(mod):
    """GrabSync's own single-prop heading-only build: the entry's `y` preset at
    the mount prefix. The nested rig stays the entry's committed `y/` prefab —
    same default rigSeed, so the tags it carries and the park it sits at are
    exactly what this document derives."""
    cfg = dict(mod.CONFIG)
    cfg["objects"] = [{"name": "Prop", "rotation": "y"}]
    cfg["mountPath"] = MOUNT
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
    """The prefab pins nothing else reads and whose breakage is silent: the
    cell's untouched sample edge on every nested GrabProp instance.

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
                          ("MultiGrabSync.prefab", ["A", "B", "C", "D"])):
        path = os.path.join(HERE, prefab)
        raw = open(path, encoding="utf-8").read()
        docs = prefab_docs(path)

        # Group modifications per PrefabInstance document — the four nested GrabProp
        # instances share one base fileID+guid, so a global grouping collapses them.
        # Unity wraps a long flow mapping at ~80 columns, so any inter-token
        # gap inside `target:` may be a newline plus indent — match gaps with
        # \s+ (a save once flipped every entry to the wrapped form and the
        # single-line regex parsed zero modifications, passing the negative
        # asserts below vacuously; the count assert after the loop is the
        # guard against that whole failure class).
        mod_re = re.compile(
            r"- target: \{fileID:\s+(\d+),\s+guid:\s+(\w+),\s+type:\s+3\}\s*\n"
            r"      propertyPath: ([^\n]+)\n      value: ([^\n]*)\n"
            r"      objectReference: \{fileID:\s+(\d+)\}")
        added_sources, moved_cells, parsed = [], [], 0
        for c, a, b in docs:
            if c != 1001:
                continue
            by_target = {}
            for fid, guid, pp, val, ref in mod_re.findall(b):
                parsed += 1
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
                        p.startswith(("m_LocalPosition", "m_LocalRotation"))
                        for p in m):
                    moved_cells.append(f"&{a}")
        # The vacuity guard: every serialized modification row must have been
        # parsed, or the negative asserts below pass over an empty set.
        want_rows = raw.count("\n      propertyPath: ")
        assert_(parsed == want_rows,
                f"{prefab}: the modification parser read every row "
                f"({parsed} of {want_rows}) — a shortfall means the serialized "
                "shape moved (or a row carries an external objectReference the "
                "regex does not model) and every assert below it is vacuous")
        assert_(not added_sources,
                f"{prefab}: no added source on the cell SourcePosition constraint "
                f"(found on {added_sources})")
        assert_(not moved_cells,
                f"{prefab}: no nested instance re-poses SourcePosition "
                f"(found on {moved_cells})")


def shared_component_pins(assert_, mod):
    """The sealed-interface coupling, pinned per prefab. Everything here is a
    hand-maintained pairing only this check reads: the shared FullController's
    controller AND prms order (glue first in both — the animator param merge
    follows controllers order and the baked expression-parameter default
    follows prms order, so either inversion disarms Enable; controller.yaml's
    header owns the mechanism), its globalParams (exactly the entry's derived
    list — the seal), the mount pairing (the sync instance, resolved by its
    source-prefab guid, is named MOUNT and hangs directly under the component's
    GO — the frame every emitted binding resolves from), the glue documents'
    entry-rooted names against what each sync build declares (the seal made
    those hard-coded couplings to the entry's CONFIG keys), and the absence of
    any second FullController on the sync side (a split component un-unifies
    every shared name with no build error — the per-builder rewrite memo is
    per component, measured 2026-08-31)."""
    import re as _re

    def meta_guid(rel):
        return _re.search(r"guid: (\w+)",
                          open(os.path.join(HERE, rel) + ".meta",
                               encoding="utf-8").read()).group(1)

    for (prefab, glue_ctrl, sync_dir, cfg_fn) in (
            ("GrabSync.prefab", "GrabSync_Fx", "object-sync-single",
             grabsync_single_config),
            ("MultiGrabSync.prefab", "MultiGrabSync_Fx", "object-sync",
             grabsync_config)):
        # globalParams is asserted from the SAME config the prefab's sync
        # build was generated with — equal across the two today, but only
        # because the derivation ignores `objects`.
        want_gp = mod.document(cfg_fn(mod))[1]["facts"]["globalParams"]
        path = os.path.join(HERE, prefab)
        raw = open(path, encoding="utf-8").read()
        docs = prefab_docs(path)
        assert_(raw.count("class: FullController") == 1,
                f"{prefab}: exactly ONE FullController authored here — a second "
                f"component un-unifies every shared name "
                f"(found {raw.count('class: FullController')})")
        # Every ordering and membership read below is scoped to THAT
        # component's own document — a whole-file find() would keep passing
        # after a controller moved onto some other component.
        fc = next((b for c2, a, b in docs
                   if c2 == 114 and "class: FullController" in b), "")
        glue_g = meta_guid(f"built/{glue_ctrl}.controller")
        sync_g = meta_guid(f"{sync_dir}/built/ObjectSync_Fx.controller")
        gi, si = fc.find(glue_g), fc.find(sync_g)
        assert_(gi != -1 and si != -1 and gi < si,
                f"{prefab}: the glue controller sits BEFORE the sync build in "
                f"controllers ({glue_ctrl} at {gi}, {sync_dir} at {si}) — "
                "first-wins in controllers order is half of what arms Enable")
        # The OTHER half: the baked expression-parameter default comes from
        # the prms list's assets, merged in ITS order — reorder prms alone
        # and Enable bakes default 0 with controllers order still green.
        gp_g = meta_guid(f"built/{glue_ctrl}_Parameters.asset")
        sp_g = meta_guid(f"{sync_dir}/built/ObjectSync_Fx_Parameters.asset")
        gpi, spi = fc.find(gp_g), fc.find(sp_g)
        assert_(gpi != -1 and spi != -1 and gpi < spi,
                f"{prefab}: the glue params asset sits BEFORE the sync build's "
                f"in prms — the baked Enable default merges in that order "
                f"({gpi}, {spi})")
        if prefab == "GrabSync.prefab":
            # The nested y/ instance INHERITS the entry's own FullController,
            # which never appears as text here — only its m_RemovedComponents
            # row proves the double build is off. Derive the anchor from the
            # y/ prefab rather than pinning a literal.
            y_pf = os.path.normpath(os.path.join(
                HERE, os.pardir, os.pardir, "object-sync", "y", "ObjectSync.prefab"))
            y_guid = _re.search(r"guid: (\w+)",
                                open(y_pf + ".meta", encoding="utf-8").read()).group(1)
            y_fcs = [a for c2, a, b2 in prefab_docs(y_pf)
                     if c2 == 114 and "class: FullController" in b2]
            removed = "".join(_re.findall(
                r"m_RemovedComponents:\n((?:    - \{fileID: .+\n)+)", raw))
            gone = [a for a in y_fcs
                    if f"fileID: {a}, guid: {y_guid}" in removed]
            assert_(y_fcs and gone == y_fcs,
                    f"{prefab}: the nested y/ instance removes the entry's own "
                    f"FullController ({y_fcs}) — removed rows carry {gone}")
        blocks = _re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
        got = [[ln.split("- ", 1)[1].strip().strip("'\"")
                for ln in b.splitlines()] for b in blocks]
        assert_(got == [want_gp],
                f"{prefab}: the shared component's globalParams is exactly the "
                f"entry's derived list {want_gp} — got {got}")
        # The mount pairing, both halves: the SYNC INSTANCE (resolved by its
        # source-prefab guid, never by scanning every m_Name in the file) is
        # named MOUNT, and it is a DIRECT CHILD of the shared component's
        # GameObject — the emitted `ObjectSync/…` bindings resolve from that
        # GO, so one extra nesting level kills every binding silently.
        nested_g = meta_guid(os.path.join("..", "..", "object-sync", "y",
                                          "ObjectSync.prefab")
                             if prefab == "GrabSync.prefab"
                             else os.path.join("object-sync", "ObjectSync.prefab"))
        inst = next((b for c2, a, b in docs if c2 == 1001
                     and f"m_SourcePrefab: {{fileID: 100100000, guid: {nested_g}"
                     in b), "")
        iname = _re.search(r"propertyPath: m_Name\s*\n\s*value: (.+)", inst)
        assert_(inst and iname and iname.group(1).strip() == MOUNT,
                f"{prefab}: the sync instance (source {nested_g}) is named "
                f"{MOUNT!r} — got {iname.group(1).strip() if iname else None!r}")
        fc_go = _re.search(r"m_GameObject: \{fileID: (\d+)\}", fc)
        root_tf = next((str(a) for c2, a, b in docs if c2 == 4 and fc_go
                        and f"m_GameObject: {{fileID: {fc_go.group(1)}}}" in b),
                       None)
        parent = _re.search(r"m_TransformParent: \{fileID: (\d+)\}", inst)
        assert_(root_tf and parent and parent.group(1) == root_tf,
                f"{prefab}: the sync instance hangs directly under the shared "
                f"component's GO (parent {parent.group(1) if parent else None}, "
                f"component GO transform {root_tf})")
    # The glue documents hard-code sealed entry names (`OS/Ready` today),
    # which couples them to the entry's CONFIG keys with nothing else
    # watching: rename `internal` or `channel` upstream and both glues
    # recompile green while every engage rung gates forever on a param
    # nothing writes. So: every entry-rooted name a glue binds must be a
    # name its own sync build's document declares.
    roots = {mod.CONFIG["prefix"].split("/")[0],
             mod.CONFIG["internal"].split("/")[0],
             mod.CONFIG["channel"].split("/")[0]}
    # multi.yaml is not iterated: it is generated FROM controller.yaml, so its
    # binding set is the same set under a suffix and this pin cannot fail there
    # without failing here first.
    for glue, cfg_fn in (("controller.yaml", grabsync_single_config),):
        own = _re.sub(r"#.*", "",
                      open(os.path.join(HERE, glue), encoding="utf-8").read())
        reached = sorted({n for n in
                          _re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", own)
                          if n.split("/")[0] in roots})
        declared = set(_re.findall(r"^  ([^\s#:]+):",
                                   mod.document(cfg_fn(mod))[0], _re.M))
        missing = [n for n in reached if n not in declared]
        assert_(reached and not missing,
                f"{glue}: every entry-rooted name it binds is declared by its "
                f"sync build ({len(reached)} names) — undeclared: {missing}")

    # The sync side carries no FullController of its own anywhere: the rig
    # prefab used to own one, and a leftover builds the wire twice.
    rig = open(os.path.join(HERE, "object-sync", "ObjectSync.prefab"),
               encoding="utf-8").read()
    assert_("class: FullController" not in rig,
            "object-sync/ObjectSync.prefab carries no FullController — the "
            "shared root component is the only merge door")


# ========================================================= the glue documents ===
# Emits the marked region of `controller.yaml` (its clip table) and of
# `multi.yaml` (that document at four suffixed props). Both splices are textual,
# so nothing outside the markers is read or written.
#
# Cell bindings are read live from ../../grab-prop/controller.yaml at emit time;
# the tables below map a glue clip to an entry clip by NAME. Freezing a cell value
# here forks the entry (CONVENTIONS.md §compositions/) — the only literals below
# are glue-side: GLUE_KEYS, VALUE_SETS, the dwells, the per-clip notes.

CELL_DOC = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "grab-prop", "controller.yaml"))
GLUE_DOC = os.path.join(HERE, "controller.yaml")
MULTI_DOC = os.path.join(HERE, "multi.yaml")

BEGIN = "  # --- BEGIN GENERATED by generate.py: cell bindings from grab-prop, glue from VALUE_SETS."
END = "  # --- END GENERATED"
MULTI_BEGIN = "# --- BEGIN GENERATED by generate.py: controller.yaml at four suffixed props."
MULTI_END = "# --- END GENERATED"

PREFIX = "Prop/GrabProp/"
GP0 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source0.Weight"
GP1 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source1.Weight"

# The GrabPosition repoint, and the ONLY departure from the entry's values: word
# states hold (1,0) so the parked cell root rides the word through the repointed
# Display. grab-prop/README.md §How it works sanctions the two-source repoint;
# controller.yaml's header owns why exactly these three states take it.
GP_CARVE = {"acquire", "synced", "resume"}

# The glue's own bindings, in emit order after the root. Every clip carries all
# fourteen; VALUE_SETS supplies the values.
GLUE_KEYS = (
    "Prop/GameObject.m_IsActive",
    "Prop/Source/VRCPositionConstraint.Sources.source0.Weight",
    "Prop/Source/VRCPositionConstraint.Sources.source1.Weight",
    "Prop/Source/VRCPositionConstraint.Sources.source2.Weight",
    "Prop/Source/VRCRotationConstraint.Sources.source0.Weight",
    "Prop/Source/VRCRotationConstraint.Sources.source1.Weight",
    "Prop/Source/VRCRotationConstraint.Sources.source2.Weight",
    "Prop/Container/VRCPositionConstraint.Sources.source0.Weight",
    "Prop/Container/VRCPositionConstraint.Sources.source1.Weight",
    "Prop/Container/VRCRotationConstraint.Sources.source0.Weight",
    "Prop/Container/VRCRotationConstraint.Sources.source1.Weight",
    "Prop/DragBone_Yaw/Follower/DragBone/VRCPhysBone.m_Enabled",
    "Prop/DragBone_Yaw/Follower/VRCRotationConstraint.IsActive",
    "Prop/Container/Display/GameObject.m_IsActive",
)

# The four sets controller.yaml's header names — HOME, CARRY, ACQUIRE, SYNC —
# each with the root-kill and show/hide variants the states actually need. Values
# are in GLUE_KEYS order; `None` on Display means the clip owns it as a curve
# instead (the delayed show). This table is the canon for these digits; the
# header's value-set block echoes it and says so.
VALUE_SETS = {
    "HOME-HIDE":    (1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0),
    "HOME-OFF":     (0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0),
    "HOME-SHOW":    (1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, None),
    "CARRY":        (1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1),
    "ACQUIRE-SHOW": (1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, None),
    "ACQUIRE-HIDE": (1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0),
    "SYNC":         (1, 0, 1, 0, 0, 1, 0, 0.1, 1, 0.2, 1, 0, 1, 1),
}

# The delayed show, shared by the two states that re-enable a frozen Prop.
DISPLAY_DELAY = "{ tangents: stepped, keys: [ [0, 0], [0.1, 1] ] }"

# Dwells this document owns; the entry's own lengths transcribe with the cell.
# Resume waits the full release-to-committed-word latency FROM the resume, which
# is pulse + bridge — the relation, not a second number, so a bridge retune
# carries. Copy sites for the two bridge constants: each document's header
# derivation, and README.md's MultiGrabSync section. Retune all three together.
BRIDGE = 2.4          # [EMPIRICAL] controller.yaml's header derives it at N=1
MULTI_BRIDGE = 6.0    # [EMPIRICAL] multi.yaml's header RE-derives it at N=4 — never copied from N=1


CLIPS = (
    ('timer', 'timer', 'HOME-HIDE', None,
     ('cell `timer` + HOME hidden  [EMPIRICAL: dwell = clip length]',),
     None),
    ('disabled', 'disabled', 'HOME-OFF', None,
     ('cell `disabled` + HOME hidden',),
     None),
    ('anchored', 'anchored', 'HOME-SHOW', None,
     ('cell `anchored` + HOME visible (home rot + park)',),
     ('curves', ("Delayed show, same mechanism as acquire's: with Prop frozen through Disabled, re-enable needs", '2-3 frames for the rotation ring to flush; Anchored is only ever entered from hidden states, so', 'this hide can never blink a visible prop.'))),
    ('grabbed', 'grabbed', 'CARRY', None,
     ('cell `grabbed` + CARRY',),
     None),
    ('released', 'released', 'CARRY', None,
     ('cell `released` (pulse verbatim) + CARRY  [EMPIRICAL: sample window [0.25, 0.50) s]',),
     None),
    ('dropped', 'dropped', 'CARRY', None,
     ('cell `dropped` + CARRY',),
     None),
    ('waiting', 'waiting', 'HOME-HIDE', None,
     ('cell `waiting` + HOME hidden (fail-visible: never show at a guessed spot)',),
     None),
    ('acquire', 'dropped', 'ACQUIRE-SHOW', 0.15,
     ('cell `dropped` + ACQUIRE (rigid word flush); GrabPosition (1,0) — root rides the word',),
     ('top', ('Delayed show: the rotation ring is one CYCLIC constraint group (grouping ignores weights), so the', 'word yaw propagates one hop per frame — 2-3 frames. Display stays hidden while it flushes; 0.1 s', 'covers 3 frames at 30 fps. The Display child is what makes hidden-but-solving possible.'))),
    ('bridge', 'dropped', 'CARRY', 'BRIDGE',
     ('cell `dropped` + CARRY  [EMPIRICAL: bridge timer = clip length; pulse+bridge ≈ {RESUME} s]',),
     None),
    ('synced', 'dropped', 'SYNC', None,
     ('cell `dropped` + SYNC (damped word); GrabPosition (1,0) — root rides the word',),
     None),
    ('resume', 'dropped', 'ACQUIRE-HIDE', 'RESUME',
     ('cell `dropped` + ACQUIRE, hidden; GrabPosition (1,0). `synced` with the damper at', 'passthrough and Display off — five changed bindings, and the only five.', '[EMPIRICAL: dwell = clip length = pulse {PULSE} + bridge {BRIDGE}]'),
     None),
    ('resume_grab', 'grabbed', 'ACQUIRE-HIDE', 0.1,
     ('cell `grabbed` + ACQUIRE, hidden — `reacquire` with the damper at passthrough and', 'Display off, so the cell populates behind a hidden prop and Grabbed shows it at the', 'hand. Park stays on here and Grabbed unparks, exactly as reacquire→Grabbed does.', "[EMPIRICAL: dwell = clip length, reacquire's]"),
     None),
    ('reacquire', 'grabbed', 'SYNC', 0.1,
     ('cell `grabbed` (Container/SourcePosition wake; root frozen on the word) + SYNC glue  [EMPIRICAL: dwell = clip length]',),
     None),
)

# multi.yaml re-derives two dwells at N=4, so those two notes differ there.
NOTES_MULTI = {
    'bridge': ('cell `dropped` + CARRY  [EMPIRICAL: bridge timer = clip length; pulse+bridge = {RESUME} s (header derivation)]',),
    'resume': ('cell `dropped` + ACQUIRE, hidden; GrabPosition (1,0). `synced` with the damper at', 'passthrough and Display off — five changed bindings, and the only five.', "[EMPIRICAL: dwell = clip length = pulse {PULSE} + bridge {BRIDGE}, the header's N=4 derivation]"),
}


def _num(v):
    """1 -> '1', 0.1 -> '0.1', 2.9000000000000004 -> '2.9'."""
    r = round(float(v), 4)
    return str(int(r)) if r == int(r) else str(r)


def _sec(v):
    """A clip length always prints with a decimal point: 1 -> '1.0'."""
    return str(round(float(v), 4))


def parse_clips(path):
    """The bounded clip-table subset these documents use: 2-space clip names,
    4-space set:/curves:/length rows, 6-space bindings quoted or bare. Values are
    kept as verbatim strings so a transcribed value is byte-exact, and dict order
    preserves the entry's own binding order, which the emit reproduces."""
    clips, cur, sect, started = {}, None, None, False
    for line in open(path, encoding="utf-8"):
        if re.match(r"^clips:", line):
            started, cur = True, None
            continue
        if not started:
            continue
        m = re.match(r"^  ([\w+-]+):", line)
        if m:
            cur, sect = m.group(1), None
            clips[cur] = {"set": {}, "curves": {}, "len": None,
                          "lenkey": "seconds"}
            continue
        if cur is None:
            continue
        m = re.match(r"^    (seconds|length): ([\d.]+)", line)
        if m:
            clips[cur]["len"] = m.group(2)
            clips[cur]["lenkey"] = m.group(1)   # transcribes with the value
            continue
        if re.match(r"^    set:", line):
            sect = "set"
            continue
        if re.match(r"^    curves:", line):
            sect = "curves"
            continue
        m = (re.match(r'^      "([^"]+)": (.+?)\s*$', line)
             or re.match(r'^      ([\w+./-]+(?:/[\w+.-]+)*): (.+?)\s*$', line))
        if m and sect:
            val = m.group(2)
            if not val.startswith(("{", "[")):
                val = re.sub(r"\s+#.*$", "", val)   # box-tracker-style inline notes
            clips[cur][sect][m.group(1)] = val
    return clips


def emit_clips(cell, suffix="", bridge=BRIDGE, notes=None, col=16, cont=16):
    """The clip table: one clip per CLIPS row, cell bindings read from `cell`
    (grab-prop's parsed document) under PREFIX, glue bindings from VALUE_SETS.

    `suffix` is multi.yaml's per-prop letter — it renames the clip and moves every
    binding from Prop/ to Prop<X>/, which is the whole difference between the two
    documents. `notes` overrides the note block for a clip whose empirical text
    differs at N=4."""
    # The pulse is the entry's release pulse, read live: Resume's dwell is
    # defined as pulse + bridge, so both follow a retune on either side.
    pulse = float(cell["released"]["len"])
    dwells = {"BRIDGE": bridge, "RESUME": pulse + bridge}
    out = []
    for name, src, setname, dwell, note, body in CLIPS:
        if src not in cell:
            raise SystemExit(
                f"REFUSE: grab-prop/controller.yaml has no clip `{src}` — "
                f"`{name}` transcribes it, and this generator will not invent a "
                f"cell. Reconcile CLIPS against the entry's table.")
        e = cell[src]
        rows, curves = {}, {}
        vals = VALUE_SETS[setname]
        rows[GLUE_KEYS[0]] = _num(vals[0])
        for k, v in e["set"].items():
            rows[PREFIX + k] = v
        for k, v in e["curves"].items():
            curves[PREFIX + k] = v
        if name in GP_CARVE:
            rows[GP0], rows[GP1] = "1", "0"
        for k, v in zip(GLUE_KEYS[1:], vals[1:]):
            if v is None:
                curves[k] = DISPLAY_DELAY
            else:
                rows[k] = _num(v)

        def ren(key):
            return key.replace("Prop/", f"Prop{suffix}/", 1) if suffix else key

        length = dwells[dwell] if dwell in dwells else dwell
        lenkey = "seconds"
        if length is None:
            length = float(e["len"]) if e["len"] else None
            lenkey = e["lenkey"]         # inherited: keep the entry's spelling
        text = (notes or {}).get(name, note)
        text = [t.format(PULSE=_sec(pulse), BRIDGE=_sec(bridge),
                         RESUME=_sec(pulse + bridge)) for t in text]

        head = f"  {name}{suffix}:"
        out.append(head + " " * max(1, col - len(head)) + "# " + text[0])
        out.extend(" " * cont + "# " + t for t in text[1:])
        if body and body[0] == "top":
            out.extend("    # " + t for t in body[1])
        if length is not None:
            out.append(f"    {lenkey}: {_sec(length)}")
        out.append("    set:")
        out.extend(f'      "{ren(k)}": {v}' for k, v in rows.items())
        if curves:
            if body and body[0] == "curves":
                out.extend("    # " + t for t in body[1])
            out.append("    curves:")
            out.extend(f'      "{ren(k)}": {v}' for k, v in curves.items())
    return out


def splice(path, begin, end, body):
    """Replace the marked region, leaving every byte outside it alone.

    Refuses unless the file carries exactly one marker pair, in order — a
    duplicated or missing marker would otherwise silently swallow hand-authored
    prose. This is an emitter refusal, not a --check assert.

    Reads in default text mode and writes with newline="\\n", matching
    object-sync/generate.py: the working tree is CRLF under core.autocrlf and the
    blob is LF, and preserving CRLF here would mix line endings inside one file."""
    lines = open(path, encoding="utf-8").read().split("\n")
    bi = [i for i, l in enumerate(lines) if l == begin]
    ei = [i for i, l in enumerate(lines) if l == end]
    if len(bi) != 1 or len(ei) != 1 or bi[0] >= ei[0]:
        raise SystemExit(
            f"REFUSE: {os.path.basename(path)} must carry exactly one "
            f"{begin.strip()!r} ... {end.strip()!r} pair, in that order — "
            f"found {len(bi)} begin, {len(ei)} end.")
    out = lines[:bi[0] + 1] + body + lines[ei[0]:]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))
    return len(body)


def multi_body(cell):
    """multi.yaml's whole body: controller.yaml's document at four suffixed props.

    Three shapes, not one transform. `layers:` and `clips:` repeat wholesale under
    the rename; `parameters:` does NOT — only the two per-prop declarations
    multiply, while Enable, Ready and the two built-ins stay singular; and the
    controller name is a literal override, not a suffix."""
    src = open(GLUE_DOC, encoding="utf-8").read().split("\n")
    head = src[src.index("schema: 1"):src.index("parameters:")]
    head = [l.replace("GrabSync_Fx", "MultiGrabSync_Fx") for l in head]
    lay_at = src.index("layers:")
    clips_at = src.index("clips:")
    layers = src[lay_at + 1:clips_at]
    while layers and not layers[-1].strip():
        layers.pop()
    # Whatever sits between the last layer and `clips:` (the binding-count note)
    # single-sources from controller.yaml rather than being restated here.
    tail = []
    while layers and (layers[-1].startswith("#") or not layers[-1].strip()):
        tail.insert(0, layers.pop())
    while tail and not tail[0].strip():
        tail.pop(0)

    out = list(head)
    out.append("parameters:")
    for k in PROPS:
        out.append(f"  Detached{k}:            {{ type: bool, default: false, "
                   f"vrc: {{ synced: true, saved: false }} }}")
    for k in PROPS:
        out.append(f"  Grab{k}_IsGrabbed:      bool               "
                   f"# sensing — minted by the grab physbone (parameter: Grab{k})")
    out.extend(l for l in src[src.index("parameters:") + 1:lay_at]
               if l.strip() and not re.match(r"^  (Detached|Grab_IsGrabbed):", l))
    out.append("")
    out.append("layers:")
    for k in PROPS:
        out.extend(_suffix_line(l, k) for l in layers)
        out.append("")
    out.extend(tail)
    out.append("clips:")
    for k in PROPS:
        out.extend(emit_clips(cell, suffix=k, bridge=MULTI_BRIDGE,
                              notes=NOTES_MULTI, col=17, cont=16))
    return out


def _suffix_line(line, k):
    """Rename inside the structural part of a line only — a comment is prose and
    is emitted verbatim, exactly as the hand copies had it."""
    head, sep, tail = line.partition("#")
    for c in sorted((c[0] for c in CLIPS), key=len, reverse=True):
        head = re.sub(r"(?<![\w/])" + c + r"(?![\w])", c + k, head)
    head = re.sub(r"(?<![\w])Detached(?![\w])", "Detached" + k, head)
    head = re.sub(r"(?<![\w])Grab_IsGrabbed(?![\w])", f"Grab{k}_IsGrabbed", head)
    head = re.sub(r'(?<![\w])Prop(?=[/\s"]|$)', "Prop" + k, head)
    return head + sep + tail


def write_glue():
    cell = parse_clips(CELL_DOC)
    n = splice(GLUE_DOC, BEGIN, END, emit_clips(cell))
    print(f"wrote controller.yaml: {len(CLIPS)} clips, {n} lines emitted")
    n = splice(MULTI_DOC, MULTI_BEGIN, MULTI_END, multi_body(cell))
    print(f"wrote multi.yaml: {len(PROPS)} props x {len(CLIPS)} clips, "
          f"{n} lines emitted")


def main():
    mod = entry_module()
    builds = {"multi": (grabsync_config(mod), OUT),
              "single": (grabsync_single_config(mod), OUT_SINGLE)}

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        prefab_pins(assert_)
        shared_component_pins(assert_, mod)

        # The nested object-sync rig prefab is hand-authored (generate.py emits only the controller),
        # so its node names and collision tags must track OBJECTS by hand. A drift silently breaks
        # every binding the regenerated controller writes through Rig/<name> and Sync<name>, and the
        # contact tags it references -- and nothing else reads the prefab against the controller, so
        # a rename that updates OBJECTS but forgets a node here compiles and gates clean while the
        # avatar's sync is dead. Pin both against the generator's own naming. (The single build's
        # rig is the ENTRY's committed y/ prefab, whose own --check pins its nodes and tags.)
        import re as _re
        cfg = builds["multi"][0]
        flat = [t for ob in cfg["objects"] for t in mod.tag_set(cfg, ob["name"])]
        sync_prefab = os.path.join(HERE, "object-sync", "ObjectSync.prefab")
        sync_text = open(sync_prefab, encoding="utf-8").read()
        sync_names = set(_re.findall(r"m_Name: (.+)", sync_text))
        missing_nodes = [nm for ob in cfg["objects"]
                         for nm in (ob["name"], mod.sync_path(cfg, ob["name"]),
                                    mod.sync_target_path(cfg, ob["name"]))
                         if nm not in sync_names]
        assert_(not missing_nodes,
                f"ObjectSync.prefab node names track OBJECTS (missing {missing_nodes})")
        missing_tags = [t for t in flat if t not in sync_text]
        assert_(not missing_tags,
                f"ObjectSync.prefab collision tags track OBJECTS (missing {missing_tags})")
        # Per-tag carrier counts, same reason as the entry's own check: a
        # single retagged component keeps the tag SET intact and only the
        # counts see it. The rig prefab is authored flat, so counts are honest.
        tag_rows = _re.findall(r"^  - (\S+)$", sync_text, _re.M)
        want_n = {t: n for ob in cfg["objects"]
                  for t, n in mod.tag_carriers(cfg, ob["name"]).items()}
        off = {t: (tag_rows.count(t), n) for t, n in want_n.items()
               if tag_rows.count(t) != n}
        assert_(not off,
                f"ObjectSync.prefab: each tag sits on exactly its stage's "
                f"components — off (got, want): {off}")

        sys.exit(0 if ok else 1)

    write_glue()

    for label, (cfg, out) in builds.items():
        text, f = mod.document(cfg)
        facts = f["facts"]
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"wrote {os.path.relpath(out, HERE)}: {len(f['layers'])} layers, "
              f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
              f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
              f"~{facts['cycleSeconds']:.3f}s refresh @60fps")


if __name__ == "__main__":
    main()
