#!/usr/bin/env python3
"""This composition's own `object-sync` build: the shipped entry's generator
run once, emitting beside this file instead of into the entry.

    python compositions/sync-on-player/generate.py           # writes the document
    python compositions/sync-on-player/generate.py --check   # asserts, writes nothing

Output: `object-sync/controller.yaml` — one object, position only
(`rotation: "none"`), compiled with `CompileController` into the `built/`
beside it. The prefab does not point at `../../object-sync/built/`: the
entry's committed builds emit at mountPath "" and cannot merge through the
shared component below.

THE CONFIGURATION
-----------------
The entry's shipped CONFIG — the wire block, the shipped default-off
`enableDefault` (the BUILD never arms itself; the glue's params asset declares
`ObjectSync/Enable` default-1 and merges first, so the pattern spawns armed —
controller.yaml's header owns the mechanism, --check pins both orders) —
at two deliberate deltas:

- `mountPath "ObjectSync"`: the sync rig is the nested GO of that name under
  the composition root, and the root's FullController is SHARED, carrying the
  glue controller and this build together — the sealed-interface coupling
  (the entry's §Seam; grab-sync is the worked precedent). Controller ORDER in
  that component is load-bearing (glue first, first-wins); controller.yaml's
  header owns the mechanism and the check below pins the order.
- `rigSeed "sync-on-player/g6"`: this composition's OWN namespace skew — tags
  and park derive from the seed together, which is what lets a different
  object-sync build (grab-sync at the entry default) compose beside this one
  on one avatar. The parameters stay sealed identical by design; only tags
  and park differ.

The build is position-only: `drop-on-player` ships one position channel, so
no drag bone, no heading, no rotation words exist anywhere in this
composition — the emitted surface is the `Sync`/`Sync_Target` pair and the
two collision tags printed in the document header.

The glue document's cell bindings are EMITTED, not transcribed: this file's
`the glue document` section reads `drop-on-player/controller.yaml`'s clip table
live and writes the marked region of `controller.yaml`, so the copy cannot
drift because there is no copy. `--check` asserts only the hand-maintained
prefab wiring that fails silently at build.
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")

OBJECTS = [{"name": "Prop", "rotation": "none"}]

# The nested sync rig's GO name under the composition root — the hand-
# maintained pairing mountPath buys: the emitted bindings prefix this string,
# and the check below reads it back off the prefab.
MOUNT = "ObjectSync"

# The namespace skew: one string, from which tag_set derives the collision
# tags and rig_offset derives the park — together, never separately (the
# entry's CONFIG rigSeed comment owns why).
RIG_SEED = "sync-on-player/g6"


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(
            f"REFUSE: the object-sync generator is not at {ENTRY} — this build "
            "is the entry's generator run at a different rigSeed and cannot "
            "emit a document without it.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_config(mod):
    cfg = dict(mod.CONFIG)
    cfg["objects"] = [dict(ob) for ob in OBJECTS]
    cfg["mountPath"] = MOUNT
    cfg["rigSeed"] = RIG_SEED
    return cfg


def prefab_docs(path):
    """Split a Unity YAML asset into (classId, anchor, body) documents."""
    docs = []
    for m in re.finditer(r"^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)",
                         open(path, encoding="utf-8").read(),
                         re.M | re.S):
        docs.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return docs


def parse_mods(docs, raw):
    """Every PrefabInstance's modification rows, grouped per (target fileID,
    guid), plus removed component/GO fileID sets per source guid — with the
    vacuity guard: every serialized row must parse or the negative asserts
    read over an empty set."""
    mod_re = re.compile(
        r"- target: \{fileID:\s+(\d+),\s+guid:\s+(\w+),\s+type:\s+3\}\s*\n"
        r"      propertyPath: ([^\n]+)\n      value: ([^\n]*)\n"
        r"      objectReference: \{fileID:\s+(-?\d+)(?:,\s+guid:\s+(\w+))?")
    rem_re = re.compile(
        r"m_Removed(Components|GameObjects):\n((?:    - \{fileID: .+\n)+)")
    row_re = re.compile(r"fileID: (\d+), guid: (\w+)")
    mods, removed, parsed = {}, {"Components": set(), "GameObjects": set()}, 0
    for c, a, b in docs:
        if c != 1001:
            continue
        for fid, guid, pp, val, ref, refguid in mod_re.findall(b):
            parsed += 1
            mods.setdefault((int(fid), guid), {})[pp] = (val.strip(), int(ref), refguid)
        for kind, rows in rem_re.findall(b):
            for fid, guid in row_re.findall(rows):
                removed[kind].add((int(fid), guid))
    want_rows = raw.count("\n      propertyPath: ")
    return mods, removed, parsed, want_rows


def guid_of(rel):
    return re.search(r"guid: (\w+)",
                     open(os.path.join(HERE, rel) + ".meta",
                          encoding="utf-8").read()).group(1)


def entry_nodes(prefab_path):
    """(guid, transform-fileID->owner name, component-fileID->owner name, docs)
    for a hand-read entry prefab (flat, no nesting)."""
    guid = re.search(r"guid: (\w+)",
                     open(prefab_path + ".meta", encoding="utf-8").read()).group(1)
    docs = prefab_docs(prefab_path)
    go_name = {a: re.search(r"m_Name: (.*)", b).group(1).strip()
               for c, a, b in docs if c == 1 and "m_Name:" in b}
    owner = {}
    for c, a, b in docs:
        m = re.search(r"m_GameObject: \{fileID: (\d+)", b)
        if c in (4, 114, 208) and m:
            owner[a] = go_name.get(int(m.group(1)), "?")
    tf = {a: owner[a] for c, a, b in docs if c == 4 and a in owner}
    comp = {a: owner[a] for c, a, b in docs if c == 114 and a in owner}
    return guid, tf, comp, docs


def _num(s):
    try:
        return float(s)
    except ValueError:
        return None


def prefab_pins(assert_, mod, cfg):
    """The hand-maintained prefab surfaces no compile or gate reads, each of
    which fails silently at build: the variant's removals, retag and repark
    against the entry, and the composition's nested-instance wiring."""
    entry_pf = os.path.normpath(os.path.join(
        HERE, os.pardir, os.pardir, "object-sync", "ObjectSync.prefab"))
    dop_pf = os.path.normpath(os.path.join(
        HERE, os.pardir, os.pardir, "drop-on-player", "DropOnPlayer.prefab"))

    # --- the ObjectSync variant ---
    os_guid, os_tf, os_comp, os_docs = entry_nodes(entry_pf)
    var_path = os.path.join(HERE, "object-sync", "ObjectSync.prefab")
    var_raw = open(var_path, encoding="utf-8").read()
    var_docs = prefab_docs(var_path)
    mods, removed, parsed, want = parse_mods(var_docs, var_raw)
    assert_(parsed == want,
            f"variant: modification parser read every row ({parsed}/{want})")
    assert_(f"guid: {os_guid}" in var_raw,
            "variant: sources the entry prefab (a Regular re-save silently "
            "stops tracking entry-side retunes)")
    # The entry's own merge/pin/toggle surface is REMOVED: a leftover builds
    # the wire twice or arms a second world pin, with no build error.
    ent_vrcfury = [a for c, a, b in os_docs if c == 114
                   and re.search(r"class: (FullController|Toggle|ApplyDuringUpload)\b", b)]
    ent_pins = [a for c, a, b in os_docs if c == 114
                and os_comp.get(a) == "ObjectSync"
                and ("FreezeToWorld:" in b or "ScaleAtRest:" in b)]
    gone = [a for a in ent_vrcfury + ent_pins
            if (a, os_guid) in removed["Components"]]
    assert_(len(ent_vrcfury) == 4 and len(ent_pins) == 2
            and sorted(gone) == sorted(ent_vrcfury + ent_pins),
            f"variant: the entry's 4 VRCFury components (found {len(ent_vrcfury)}) "
            f"and the root pin pair (found {len(ent_pins)}) are all removed "
            f"(removed rows carry {len(gone)} of them)")
    # The rotation rig is gone: a leftover Rot/Recon subtree keeps its contacts
    # live at the park, summing into the position cluster with no error.
    os_go = {a: re.search(r"m_Name: (.*)", b).group(1).strip()
             for c, a, b in os_docs if c == 1 and "m_Name:" in b}
    rr_fids = sorted(a for a, n in os_go.items() if n in ("Rot", "Recon"))
    tf_go, tf_father = {}, {}
    for c, a, b in os_docs:
        if c != 4:
            continue
        mg = re.search(r"m_GameObject: \{fileID: (\d+)\}", b)
        mf = re.search(r"m_Father: \{fileID: (\d+)\}", b)
        if mg:
            tf_go[a] = int(mg.group(1))
        if mf:
            tf_father[a] = int(mf.group(1))
    go_tf = {g: t for t, g in tf_go.items()}

    def gone_or_under(g):
        t = go_tf.get(g)
        while t:
            if (tf_go[t], os_guid) in removed["GameObjects"]:
                return True
            t = tf_father.get(t)
        return False

    direct = [a for a in rr_fids if (a, os_guid) in removed["GameObjects"]]
    assert_(len(direct) >= 2 and all(gone_or_under(a) for a in rr_fids)
            and not re.search(r"value: (Rot|Recon)\s*$", var_raw, re.M),
            f"variant: Rot/ and Recon/ removed by fileID — {len(direct)} "
            f"subtree roots removed, {len(rr_fids)} named GOs all covered")
    # Repark + retag: the park and tags derive from ONE seed and move together.
    prop_mod = next((m for (fid, g), m in mods.items()
                     if g == os_guid and "m_LocalPosition.x" in m
                     and _num(m["m_LocalPosition.x"][0]) is not None
                     and float(m["m_LocalPosition.x"][0]) != 0), None)
    want_park = tuple(float(v) for v in mod.rig_offset(cfg["rigSeed"]))
    got_park = tuple(float(prop_mod[f"m_LocalPosition.{ax}"][0])
                     for ax in "xyz") if prop_mod else None
    assert_(got_park == want_park,
            f"variant: park override = rig_offset(rigSeed) {want_park} — got {got_park}")
    tags = mod.tag_set(cfg, "Prop")
    carriers = mod.tag_carriers(cfg, "Prop")
    for t in tags:
        n = var_raw.count(f"value: {t}\n")
        assert_(n == carriers[t],
                f"variant: tag {t} on exactly its stage's components "
                f"({n} of {carriers[t]})")
    for t in mod.tag_set(mod.CONFIG, mod.CONFIG["objects"][0]["name"]):
        assert_(f"value: {t}\n" not in var_raw,
                f"variant: no carrier left on the entry-default tag {t}")

    # --- the composition prefab ---
    comp_path = os.path.join(HERE, "SyncOnPlayer.prefab")
    comp_raw = open(comp_path, encoding="utf-8").read()
    comp_docs = prefab_docs(comp_path)
    cmods, cremoved, cparsed, cwant = parse_mods(comp_docs, comp_raw)
    assert_(cparsed == cwant,
            f"composition: modification parser read every row ({cparsed}/{cwant})")
    dop_guid, dop_tf, dop_comp, dop_docs = entry_nodes(dop_pf)

    # Nested drop-on-player: the FreezeToWorld node (and the ApplyDuringUpload
    # riding it) removed — a second world pin arming at build is silent.
    dop_go = {a: re.search(r"m_Name: (.*)", b).group(1).strip()
              for c, a, b in dop_docs if c == 1 and "m_Name:" in b}
    fids = [a for a, n in dop_go.items() if n == "FreezeToWorld"]
    assert_(fids and any((f, dop_guid) in cremoved["GameObjects"] for f in fids),
            "composition: drop-on-player `FreezeToWorld` GO removed")
    # The cell's stale edge: no instance modification re-poses SourcePosition,
    # and no added source on its constraint — the capture drops with every clip
    # identical (grab-prop README §How it works).
    sp_tf = [a for a, n in dop_tf.items() if n == "SourcePosition"]
    sp_cm = [a for a, n in dop_comp.items() if n == "SourcePosition"]
    bad_sp = [pp for (fid, g), m in cmods.items() if g == dop_guid
              for pp in m
              if (fid in sp_tf and pp.startswith(("m_LocalPosition",
                                                  "m_LocalRotation")))
              or (fid in sp_cm and pp.startswith("Sources."))]
    assert_(not bad_sp,
            f"composition: the cell's SourcePosition is untouched (found {bad_sp})")
    # GrabPosition repoint (the two-source repoint): source0 retargeted, weights
    # and source1 untouched — a re-grab from a word state starts on the display.
    gp_cm = [a for a, n in dop_comp.items() if n == "GrabPosition"]
    gp_mod = [m for (fid, g), m in cmods.items()
              if g == dop_guid and fid in gp_cm]
    assert_(any("Sources.source0.SourceTransform" in m for m in gp_mod)
            and not any(pp.startswith("Sources.source0.Weight")
                        or pp.startswith("Sources.source1")
                        or pp == "Sources.totalLength"
                        for m in gp_mod for pp in m),
            "composition: GrabPosition source0 repointed, weights and source1 "
            "untouched (two sources always — grab-prop §How it works)")
    # The cage park gains exactly one word-side source.
    tp_cm = [a for a, n in dop_comp.items() if n == "TrackingPoints"]
    tp_mod = [m for (fid, g), m in cmods.items()
              if g == dop_guid and fid in tp_cm]
    assert_(any(m.get("Sources.totalLength", ("",))[0] == "2" for m in tp_mod)
            and any("Sources.source1.SourceTransform" in m for m in tp_mod)
            and not any(pp.startswith("Sources.source0")
                        for m in tp_mod for pp in m),
            "composition: the cage park gains source1 (the word park) at "
            "totalLength 2, source0 untouched")
    # CagePark: a plain GO parked BELOW the prop (y<0) — the catch column is
    # mis-centered by one ride offset otherwise, with no error.
    cp = re.search(r"m_Name: CagePark", comp_raw)
    cp_y = re.search(
        r"m_Name: CagePark(?:.*\n)*?  m_LocalPosition: \{x: ([-\d.e]+), y: ([-\d.e]+)",
        comp_raw)
    assert_(cp and cp_y and float(cp_y.group(2)) < 0,
            "composition: CagePark exists with a below-the-prop offset "
            f"(y={cp_y.group(2) if cp_y else '?'})")
    # Sync_Target wired to the mux, statically. The nested instance is the
    # VARIANT, whose remapped fileIDs appear in no .prefab, so the row is
    # identified by its content: the one totalLength 0->1 write on the variant
    # instance is Sync_Target's shipped empty-list constraint gaining its source.
    var_guid = guid_of(os.path.join("object-sync", "ObjectSync.prefab"))
    st_mod = [m for (fid, g), m in cmods.items() if g == var_guid
              and m.get("Sources.totalLength", ("",))[0] == "1"]
    assert_(len(st_mod) == 1
            and st_mod[0].get("Sources.source0.Weight", ("",))[0] == "1"
            and "Sources.source0.SourceTransform" in st_mod[0],
            "composition: Sync_Target sources [Prop/Source w=1] (the encoder "
            "measures the mux output, undamped)")
    # The ONE pin: exactly the two constraint docs on the composition ROOT GO
    # serialize disabled at all-zero offsets — the shipping client scales a
    # source offset per client (runtime.md §Constraints), silently.
    root_go = next(re.search(r"m_GameObject: \{fileID: (\d+)\}", b).group(1)
                   for c, a, b in comp_docs
                   if c == 4 and "m_Father: {fileID: 0}" in b)
    pin_bodies = [b for c, a, b in comp_docs if c == 114
                  and f"m_GameObject: {{fileID: {root_go}}}" in b
                  and ("FreezeToWorld:" in b or "ScaleAtRest:" in b)]
    zeroed = [b for b in pin_bodies
              if re.search(r"ParentPositionOffset: \{x: 0, y: 0, z: 0\}", b)]
    assert_(len(pin_bodies) == 2 and len(zeroed) == 2
            and all("m_Enabled: 0" in b for b in pin_bodies),
            f"composition: the root pin pair serializes disabled at all-zero "
            f"offsets ({len(zeroed)}/2 zeroed, of {len(pin_bodies)} candidates)")


def shared_component_pins(assert_, mod, cfg):
    """The sealed-interface coupling: the ONE shared FullController's
    controller AND prms order (glue first in both — the animator param merge
    follows controllers order and the baked expression-parameter default
    follows prms order, so either inversion bakes Enable default-0 with no
    error), globalParams exactly the build's derived list, the mount pairing
    (the variant instance named MOUNT, hanging directly under the component's
    GO — the frame every emitted binding resolves from), the nested entry's
    FullController removal, the glue's entry-rooted names against what the
    build declares, and no second FullController on the sync side (a split
    component un-unifies every shared name with no build error)."""
    comp_path = os.path.join(HERE, "SyncOnPlayer.prefab")
    raw = open(comp_path, encoding="utf-8").read()
    docs = prefab_docs(comp_path)
    want_gp = mod.document(cfg)[1]["facts"]["globalParams"]
    n_fc = raw.count("class: FullController")
    assert_(n_fc == 1,
            f"shared: exactly ONE FullController authored here — a second "
            f"component un-unifies every shared name (found {n_fc})")
    fc = next((b for c2, a, b in docs
               if c2 == 114 and "class: FullController" in b), "")
    glue_g = guid_of("built/SyncOnPlayer_Fx.controller")
    sync_g = guid_of(os.path.join("object-sync", "built",
                                  "ObjectSync_Fx.controller"))
    gi, si = fc.find(glue_g), fc.find(sync_g)
    assert_(gi != -1 and si != -1 and gi < si,
            f"shared: the glue controller sits BEFORE the sync build in "
            f"controllers (glue at {gi}, sync at {si}) — first-wins in "
            "controllers order is half of what arms Enable")
    gp_g = guid_of("built/SyncOnPlayer_Fx_Parameters.asset")
    sp_g = guid_of(os.path.join("object-sync", "built",
                                "ObjectSync_Fx_Parameters.asset"))
    gpi, spi = fc.find(gp_g), fc.find(sp_g)
    assert_(gpi != -1 and spi != -1 and gpi < spi,
            f"shared: the glue params asset sits BEFORE the sync build's in "
            f"prms — the baked Enable default merges in that order "
            f"({gpi}, {spi})")
    blocks = re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"")
            for ln in b.splitlines()] for b in blocks]
    assert_(got == [want_gp],
            f"shared: the component's globalParams is exactly the build's "
            f"derived list {want_gp} — got {got}")
    var_guid = guid_of(os.path.join("object-sync", "ObjectSync.prefab"))
    inst = next((b for c2, a, b in docs if c2 == 1001
                 and f"m_SourcePrefab: {{fileID: 100100000, guid: {var_guid}"
                 in b), "")
    iname = re.search(r"propertyPath: m_Name\s*\n\s*value: (.+)", inst)
    assert_(inst != "" and iname is not None
            and iname.group(1).strip() == MOUNT,
            f"shared: the sync instance (source {var_guid}) is named "
            f"{MOUNT!r} — got {iname.group(1).strip() if iname else None!r}")
    fc_go = re.search(r"m_GameObject: \{fileID: (\d+)\}", fc)
    root_tf = next((str(a) for c2, a, b in docs if c2 == 4 and fc_go
                    and f"m_GameObject: {{fileID: {fc_go.group(1)}}}" in b),
                   None)
    parent = re.search(r"m_TransformParent: \{fileID: (\d+)\}", inst)
    assert_(root_tf is not None and parent is not None
            and parent.group(1) == root_tf,
            f"shared: the sync instance hangs directly under the component's "
            f"GO (parent {parent.group(1) if parent else None}, component GO "
            f"transform {root_tf})")
    dop_pf = os.path.normpath(os.path.join(
        HERE, os.pardir, os.pardir, "drop-on-player", "DropOnPlayer.prefab"))
    dop_guid, dop_tf, dop_comp, dop_docs = entry_nodes(dop_pf)
    dop_fcs = [a for c2, a, b in dop_docs
               if c2 == 114 and "class: FullController" in b]
    mods, removed, parsed, want = parse_mods(docs, raw)
    gone = [a for a in dop_fcs if (a, dop_guid) in removed["Components"]]
    assert_(len(dop_fcs) >= 1 and gone == dop_fcs,
            f"shared: the nested entry instance removes the entry's own "
            f"FullController ({dop_fcs}) — removed rows carry {gone}")
    # The glue hard-codes sealed entry names (`OS/Ready`, the stage AAPs):
    # rename `internal` or `channel` upstream and the glue recompiles green
    # while every engage rung gates forever on a param nothing writes.
    roots = {cfg["prefix"].split("/")[0],
             cfg["internal"].split("/")[0],
             cfg["channel"].split("/")[0]}
    own = re.sub(r"#.*", "",
                 open(os.path.join(HERE, "controller.yaml"),
                      encoding="utf-8").read())
    reached = sorted({n for n in
                      re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", own)
                      if n.split("/")[0] in roots})
    declared = set(re.findall(r"^  ([^\s#:]+):",
                              mod.document(cfg)[0], re.M))
    missing = [n for n in reached if n not in declared]
    assert_(len(reached) > 0 and not missing,
            f"shared: every entry-rooted name the glue binds is declared by "
            f"its sync build ({len(reached)} names) — undeclared: {missing}")
    rig = open(os.path.join(HERE, "object-sync", "ObjectSync.prefab"),
               encoding="utf-8").read()
    assert_("class: FullController" not in rig,
            "shared: object-sync/ObjectSync.prefab carries no FullController "
            "— the shared root component is the only merge door")


# ========================================================== the glue document ===
# Emits the marked region of `controller.yaml` — the transcribed clip table. The
# splice is textual, so nothing outside the markers is read or written.
#
# Cell bindings are read live at emit time from
# ../../drop-on-player/controller.yaml, and ../../box-tracker/controller.yaml for
# the carved cage; the tables below map a glue clip to an entry clip by NAME.
# Freezing a cell value here forks the entry (CONVENTIONS.md §compositions/) — the
# only literals below are glue-side: GLUE_KEYS, VALUE_SETS, the dwells, the
# per-clip notes.

CELL_DOC = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "drop-on-player", "controller.yaml"))
CAGE_DOC = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "box-tracker", "controller.yaml"))
GLUE_DOC = os.path.join(HERE, "controller.yaml")

BEGIN = ("  # --- BEGIN GENERATED by generate.py: cell bindings from drop-on-player "
         "(+ box-tracker), glue from VALUE_SETS.")
END = "  # --- END GENERATED"

PREFIX = "Prop/DropOnPlayer/"
GP0 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source0.Weight"
GP1 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source1.Weight"

# The GrabPosition repoint: word states hold (1,0) so the parked cell root rides
# the word through the repointed Display (grab-prop §How it works sanctions the
# two-source repoint; the header owns why these four take it).
GP_CARVE = {"acquireflush", "synced", "acquiring", "resume"}

# Acquiring's carve: the four cage filters shut over the `synced` set, so the boxes
# lock onto the head they held at entry (the header owns the discriminator). Same
# shape as GP_CARVE — generated clip content, so no --check reads it.
FILTER_CARVE = {"acquiring"}
FILTER_KEYS = tuple(PREFIX + f"TrackingPoints/{f}/VRCContactReceiver.allowOthers"
                    for f in ("X+", "X-", "Y+", "Z+"))

# The glue's own bindings, in emit order. Every value-set clip carries all ten.
GLUE_KEYS = (
    "Prop/GameObject.m_IsActive",
    "Prop/Source/VRCPositionConstraint.Sources.source0.Weight",
    "Prop/Source/VRCPositionConstraint.Sources.source1.Weight",
    "Prop/Source/VRCPositionConstraint.Sources.source2.Weight",
    "Prop/Source/VRCPositionConstraint.Sources.source3.Weight",
    "Prop/Container/VRCPositionConstraint.Sources.source0.Weight",
    "Prop/Container/VRCPositionConstraint.Sources.source1.Weight",
    PREFIX + "TrackingPoints/VRCParentConstraint.Sources.source0.Weight",
    PREFIX + "TrackingPoints/VRCParentConstraint.Sources.source1.Weight",
    "Prop/Container/Display/GameObject.m_IsActive",
)

# (root, mux0..3, damper0..1, park0..1, display) in GLUE_KEYS order; `None` on
# display means the clip owns it as a curve instead (the delayed show). This table
# is the canon for these digits; the header's value-set block echoes it.
VALUE_SETS = {
    "HIDDEN":         (1, 0, 1, 0, 0, 1, 0, 1, 0, 0),
    "HIDDEN-OFF":     (0, 0, 1, 0, 0, 1, 0, 1, 0, 0),
    "ANCHOR":         (1, 1, 0, 0, 0, 1, 0, 1, 0, 1),
    "CELL":           (1, 0, 1, 0, 0, 1, 0, 1, 0, 1),
    "CAGE":           (1, 0, 0, 1, 0, 1, 0, 1, 0, 1),
    "WORD-RIGID":     (1, 0, 0, 0, 1, 1, 0, 0, 1, None),
    "WORD-RIGID-OFF": (1, 0, 0, 0, 1, 1, 0, 0, 1, 0),
    "WORD-DAMPED":    (1, 0, 0, 0, 1, 0.1, 1, 0, 1, 1),
    "WORD-CELL-ON":   (1, 0, 0, 0, 1, 0.1, 1, 0, 1, 1),
    "WORD-CELL-OFF":  (1, 0, 0, 0, 1, 1, 0, 0, 1, 0),
}

DISPLAY_DELAY = "{ tangents: stepped, keys: [ [0, 0], [0.1, 1] ] }"

# `timer` is the one clip whose glue keys are not appended: the root leads, and
# the park pair sits with the cell's own TrackingPoints block. Cosmetic — the
# compiled clip is a set, not a sequence — but reproducing it keeps the emit diff
# free of noise that would hide a real one.
PACKED = {"disabled", "readout_xn", "readout_yp", "readout_zp"}

# The cage's gain-guard curve closes a clip's curve block, with its note above it.
# `body` is emitted immediately before this key.
GAIN_CURVE = PREFIX + "TrackingPoints/VRCPositionConstraint.Sources.source0.Weight"

TIMER_ANCHOR = PREFIX + "TrackingPoints/VRCParentConstraint.m_Enabled"


# Dwells. PULSE transcribes from the entry (its release pulse is the sample
# window this composition inherits); BRIDGE, SEEK and DWELL are this document's
# own, derived in the header. Resume waits the full release-to-committed-word
# latency FROM the resume, which is pulse + bridge — the relation, so a bridge
# retune carries. Copy sites: the header derivation for all three, and README.md's
# verifying section for SEEK. Retune together.
BRIDGE = 2.0    # [EMPIRICAL] header: 0.97 s worst case + grab-sync's proportional buffer
SEEK = 5.0      # [EMPIRICAL] the wearer-side loss grace
DWELL = 0.75    # [EMPIRICAL, derived] Acquiring: rejects a crossing at or above ~0.5 m/s (header)

READOUT_LEAD = (
    'Readout leaves (entry verbatim, prefixed; coefficients and box geometry are ONE unit —',
    "the entry's clip table owns them). The set rides the one-frame floor (box-tracker's stretch rule): every child of the readout state stays tiny, so the latch clip's gain guard plays in ~real frames.",
)

# Comment alignment, matched to the committed document: the value-set clips align
# their notes at column 16, the readout group one field deeper.
NOTE_COL = {
    'timer': 16,
    'disabled': 16,
    'anchored': 16,
    'grabbed': 16,
    'released': 16,
    'dropped': 16,
    'waiting': 16,
    'tracked': 16,
    'seeking': 16,
    'acquireflush': 16,
    'synced': 16,
    'acquiring': 16,
    'bridge': 16,
    'reacquire': 16,
    'resume': 16,
    'resume_grab': 16,
    'readout_xp': 22,
    'readout_xn': 22,
    'readout_yp': 22,
    'readout_zp': 22,
}

CLIPS = (
    ('timer', 'timer', 'HIDDEN', None,
     ('cell `timer` + HIDDEN  [EMPIRICAL: remote boot dwell = clip length, entry parity]',),
     None,
     None),
    ('disabled', 'disabled', 'HIDDEN-OFF', None,
     ('cell `disabled` + HIDDEN (root kill: an off module is not grabbable and senses nothing)',),
     None,
     None),
    ('anchored', 'anchored', 'ANCHOR', None,
     ('cell `anchored` + ANCHOR (shows immediately)',),
     None,
     None),
    ('grabbed', 'grabbed', 'CELL', None,
     ('cell `grabbed` + CELL (cage parked riding the prop, filters open — entry semantics)',),
     None,
     None),
    ('released', 'released', 'CELL', None,
     ('cell `released` (pulse curve verbatim) + CELL  [EMPIRICAL: sample window [0.25, 0.50) s — grab-prop sweep]',),
     None,
     None),
    ('dropped', 'dropped', 'CELL', None,
     ('cell `dropped` + CELL (the frozen capture IS the hold)',),
     None,
     None),
    ('waiting', 'waiting', 'HIDDEN', None,
     ('cell `waiting` + HIDDEN (fail-visible: never show at a guessed spot)',),
     None,
     None),
    ('tracked', 'tracked', 'CAGE', None,
     ('cell `tracked` verbatim (latch curves included) + CAGE; rides the readout tree at weight One',),
     None,
     ('curves', ("Gain guard: zero across the latch/mis-decode frames, 0.7 by clip end (box-tracker's crawl block; entry transcription).",))),
    ('seeking', '@seeking', 'CAGE', '@seek',
     ('tracked-cell + box-tracker Searching cage (header carve): self-hold at the loss point, filters reopened, zone recollapsed  [EMPIRICAL: dwell = clip length = the {SEEK} s loss grace]',),
     None,
     None),
    ('acquireflush', 'dropped', 'WORD-RIGID', '0.15',
     ('cell `dropped` + WORD-RIGID; GrabPosition (1,0) carve — the parked cell root rides the word. Delayed show: the park↔word ring flushes one hop per frame; 0.1 s covers 3 frames at 30 fps, and every entry is from a hidden state so the hide never blinks  [EMPIRICAL: dwell = clip length]',),
     None,
     None),
    ('synced', 'dropped', 'WORD-DAMPED', None,
     ('cell `dropped` + WORD-DAMPED (Synced — riding the word, filters open); GrabPosition (1,0) carve; damper (0.1,1)',),
     None,
     None),
    ('acquiring', 'dropped', 'WORD-DAMPED', '@acquire',
     ('`synced` with the four cage filters SHUT (header carve): the boxes stay locked on the head they held at entry; nothing visible moves  [EMPIRICAL: dwell = clip length = DWELL {DWELL} s — header derivation]',),
     None,
     None),
    ('bridge', 'dropped', 'CELL', '@bridge',
     ('cell `dropped` verbatim + CELL (the witnessed capture, IK-close)  [EMPIRICAL: bridge timer = clip length; pulse {PULSE} + bridge {BRIDGE} = {RESUME} s — header derivation]',),
     None,
     None),
    ('reacquire', 'grabbed', 'WORD-CELL-ON', '0.1',
     ('cell `grabbed` (SourcePosition wake; root frozen on the word) + WORD-CELL damped (header)  [EMPIRICAL: dwell = clip length]',),
     None,
     None),
    ('resume', 'dropped', 'WORD-RIGID-OFF', '@resume',
     ('cell `dropped` + WORD-RIGID, Display off — `synced` with the damper at passthrough and the display hidden; GrabPosition (1,0) carve  [EMPIRICAL: dwell = clip length = pulse {PULSE} + bridge {BRIDGE}]',),
     None,
     None),
    ('resume_grab', 'grabbed', 'WORD-CELL-OFF', '0.1',
     ("cell `grabbed` + WORD-CELL, Display off — the cell populates behind a hidden prop and Grabbed shows it at the hand  [EMPIRICAL: dwell = clip length, reacquire's]",),
     None,
     None),
    ('readout_xp', 'readout_xp', None, None,
     (),
     READOUT_LEAD,
     None),
    ('readout_xn', 'readout_xn', None, None,
     (),
     None,
     None),
    ('readout_yp', 'readout_yp', None, None,
     (),
     None,
     None),
    ('readout_zp', 'readout_zp', None, None,
     (),
     None,
     None),
)


def _num(v):
    r = round(float(v), 4)
    return str(int(r)) if r == int(r) else str(r)


def _sec(v):
    return str(round(float(v), 4))


def parse_clips(path):
    """The bounded clip-table subset these documents use: 2-space clip names,
    4-space set:/curves:/length rows, 6-space bindings quoted or bare. Values stay
    verbatim strings so a transcribed value is byte-exact, and dict order
    preserves the source's own binding order, which the emit reproduces.

    box-tracker writes bare keys with per-key inline notes where the other two
    quote theirs, so this normalizes both away: `verbatim` is about values, not
    spelling."""
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
            clips[cur] = {"set": {}, "curves": {}, "len": None, "lenkey": "seconds"}
            continue
        if cur is None:
            continue
        m = re.match(r"^    (seconds|length): ([\d.]+)", line)
        if m:
            clips[cur]["len"], clips[cur]["lenkey"] = m.group(2), m.group(1)
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
                val = re.sub(r"\s+#.*$", "", val)
            clips[cur][sect][m.group(1)] = val
    return clips


def _cell(entry, cage, name, src):
    """The cell half of one clip, already prefixed: an entry clip by name, or the
    Seeking fusion the header carves."""
    if src == "@seeking":
        # tracked cell + box-tracker's `searching` cage verbatim — the self-hold
        # configuration is that entry's to own.
        s = {k: v for k, v in entry["tracked"]["set"].items()
             if not k.startswith("TrackingPoints/")}
        s.update(cage["searching"]["set"])
        return s, {}
    if src not in entry:
        raise SystemExit(
            f"REFUSE: drop-on-player/controller.yaml has no clip `{src}` — "
            f"a glue clip transcribes it, and this generator will not invent a "
            f"cell. Reconcile CLIPS against the entry's table.")
    e = entry[src]
    return dict(e["set"]), dict(e["curves"])


def emit_clips(entry, cage):
    # PULSE is read live: the pulse is the entry's, and three of this document's
    # dwells are defined as it or as a relation over it.
    pulse = float(entry["released"]["len"])
    dwells = {"@pulse": pulse, "@bridge": BRIDGE, "@resume": pulse + BRIDGE,
              "@acquire": DWELL, "@seek": SEEK}
    out = []
    for name, src, setname, dwell, note, lead, body in CLIPS:
        cs, cc = _cell(entry, cage, name, src)
        rows = {PREFIX + k: v for k, v in cs.items()}
        curves = {PREFIX + k: v for k, v in cc.items()}
        if name in GP_CARVE:
            rows[GP0], rows[GP1] = "1", "0"
        if name in FILTER_CARVE:
            for k in FILTER_KEYS:
                assert k in rows, f"filter carve: {k} not in the cell set"
                rows[k] = "0"

        if setname is not None:
            vals = VALUE_SETS[setname]
            glue = {}
            for k, v in zip(GLUE_KEYS, vals):
                if v is None:
                    curves[k] = DISPLAY_DELAY
                else:
                    glue[k] = _num(v)
            if name == "timer":
                merged = {GLUE_KEYS[0]: glue[GLUE_KEYS[0]]}
                for k, v in rows.items():
                    merged[k] = v
                    if k == TIMER_ANCHOR:
                        merged[GLUE_KEYS[7]] = glue[GLUE_KEYS[7]]
                        merged[GLUE_KEYS[8]] = glue[GLUE_KEYS[8]]
                rows = merged
                glue = {k: v for k, v in glue.items()
                        if k not in (GLUE_KEYS[0], GLUE_KEYS[7], GLUE_KEYS[8])}
            rows.update(glue)

        if dwell is None:            # inherited: the entry's value AND its spelling
            length = float(entry[src]["len"]) if src in entry and entry[src]["len"] else None
            lenkey = entry[src]["lenkey"] if src in entry and entry[src]["len"] else "seconds"
        else:
            length = dwells.get(dwell, dwell)
            lenkey = entry["released"]["lenkey"] if dwell == "@pulse" else "seconds"

        if out and name not in PACKED:
            out.append("")
        if lead:
            out.extend("  # " + t for t in lead)
        note = tuple(t.format(PULSE=_sec(pulse), BRIDGE=_sec(BRIDGE),
                              RESUME=_sec(pulse + BRIDGE), SEEK=_num(SEEK),
                              DWELL=_sec(DWELL))
                     for t in note)
        head = f"  {name}:"
        if note:
            out.append(head + " " * max(1, NOTE_COL[name] - len(head)) + "# " + note[0])
            out.extend(" " * NOTE_COL[name] + "# " + t for t in note[1:])
        else:
            out.append(head)
        if length is not None:
            out.append(f"    {lenkey}: {_sec(length)}")
        out.append("    set:")
        out.extend(f'      "{k}": {v}' for k, v in rows.items())
        if curves:
            gain = curves.pop(GAIN_CURVE, None)
            out.append("    curves:")
            out.extend(f'      "{k}": {v}' for k, v in curves.items())
            if gain is not None:
                if body:
                    out.extend("      # " + t for t in body[1])
                out.append(f'      "{GAIN_CURVE}": {gain}')
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


def write_glue():
    n = splice(GLUE_DOC, BEGIN, END,
               emit_clips(parse_clips(CELL_DOC), parse_clips(CAGE_DOC)))
    print(f"wrote controller.yaml: {len(CLIPS)} clips, {n} lines emitted")


def main():
    mod = entry_module()
    cfg = sync_config(mod)

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        # The seed skew against the entry default: a shared tag is the
        # cross-build sender bleed, a shared park the cluster-summing bug —
        # both silent, both only visible with two builds on one avatar.
        tags = mod.tag_set(cfg, "Prop")
        entry_tags = mod.tag_set(mod.CONFIG, mod.CONFIG["objects"][0]["name"])
        assert_(not set(tags) & set(entry_tags),
                "tags disjoint from the entry default's")
        assert_(tuple(mod.rig_offset(cfg["rigSeed"]))
                != tuple(mod.rig_offset(mod.CONFIG["rigSeed"])),
                "park disjoint from the entry default's")
        prefab_pins(assert_, mod, cfg)
        shared_component_pins(assert_, mod, cfg)
        sys.exit(0 if ok else 1)

    write_glue()

    text, f = mod.document(cfg)
    facts = f["facts"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(f['layers'])} layers, "
          f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
          f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
          f"~{facts['cycleSeconds']:.3f}s refresh @60fps")
    print(f"park {mod.rig_offset(cfg['rigSeed'])}; tags {mod.tag_set(cfg, 'Prop')}")


if __name__ == "__main__":
    main()
