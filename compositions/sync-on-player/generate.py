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
The entry's shipped CONFIG — the wire block, the shipped default-off `Enable`
(this composition keeps it off: entry parity, the menu Toggle is the arm) —
at two deliberate deltas:

- `mountPath "ObjectSync"`: the sync rig is the nested GO of that name under
  the composition root, and the root's FullController is SHARED, carrying the
  glue controller and this build together — the sealed-interface coupling
  (the entry's §Seam; grab-sync is the worked precedent). Controller ORDER in
  that component is load-bearing (glue first, first-wins); controller.yaml's
  header owns the mechanism and the check below pins the order.
- `rigSeed "sync-on-player/g6"` (operator-approved 2026-08-31, G6 rulings):
  this composition's OWN namespace skew — tags and park derive from the seed
  together, which is what lets a different object-sync build (grab-sync at
  the entry default) compose beside this one on one avatar. The parameters
  stay sealed identical by design; only tags and park differ.

The build is position-only: `drop-on-player` ships one position channel, so
no drag bone, no heading, no rotation words exist anywhere in this
composition — the emitted surface is the `Sync`/`Sync_Target` pair and the
two collision tags printed in the document header.
"""

import importlib.util
import os
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

# The namespace skew (G6 ruling 16 as shipped by G7): one string, from which
# tag_set derives the collision tags and rig_offset derives the park —
# together, never separately (the entry's CONFIG rigSeed comment owns why).
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


# ---------------------------------------------------------------------------
# The transcription assert (G6 spec §Glue): cell bindings transcribe VERBATIM
# from drop-on-player's clip table — values unchanged, paths gaining the
# Prop/DropOnPlayer/ prefix — with the exceptions carved EXPLICITLY here and
# nowhere else. The diff compares CLIPS, not transitions: the transition set is
# checked by hand against the entry's controller.yaml (T2), which this assert
# structurally cannot see.

PREFIX = "Prop/DropOnPlayer/"

# glue clip -> the entry clip whose cell bindings it transcribes
CELL_SOURCE = {
    "timer": "timer", "disabled": "disabled", "anchored": "anchored",
    "grabbed": "grabbed", "released": "released", "dropped": "dropped",
    "waiting": "waiting", "tracked": "tracked",
    "bridge": "dropped", "acquireflush": "dropped", "synced": "dropped",
    "resume": "dropped", "reacquire": "grabbed", "resume_grab": "grabbed",
    # fusions (handled specially below):
    #   provisional = released cell + tracked cage (+ both clips' curves)
    #   seeking     = tracked cell + box-tracker `searching` cage
}

# The GrabPosition repoint carve: word states hold (1,0) so the parked cell
# root rides the word through the repointed Display (spec ruling 9 + grab-sync
# §How it works' sanctioned two-source repoint).
GP_CARVE = {"acquireflush", "synced", "resume"}
GP0 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source0.Weight"
GP1 = PREFIX + "GrabPosition/VRCPositionConstraint.Sources.source1.Weight"

# The 9 glue bindings every clip adds (excluded from the entry diff; pinned by
# the value-set collapse assert below).
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

# Value-sets (spec §Value-sets): (root, mux0..3, damper0..1, park0..1, display)
# display None = curve-owned (asserted present as a curve instead).
VALUE_SETS = {
    "HIDDEN":      (1, (0, 1, 0, 0), (1, 0), (1, 0), 0),
    "HIDDEN-OFF":  (0, (0, 1, 0, 0), (1, 0), (1, 0), 0),   # disabled's root kill
    "ANCHOR":      (1, (1, 0, 0, 0), (1, 0), (1, 0), 1),
    "CELL":        (1, (0, 1, 0, 0), (1, 0), (1, 0), 1),
    "CAGE":        (1, (0, 0, 1, 0), (1, 0), (1, 0), 1),
    "WORD-RIGID":  (1, (0, 0, 0, 1), (1, 0), (0, 1), None),
    "WORD-RIGID-ON": (1, (0, 0, 0, 1), (1, 0), (0, 1), 1),
    "WORD-RIGID-OFF": (1, (0, 0, 0, 1), (1, 0), (0, 1), 0),
    "WORD-DAMPED": (1, (0, 0, 0, 1), (0.1, 1), (0, 1), 1),
    "WORD-CELL-ON":  (1, (0, 0, 0, 1), (1, 0), (0, 1), 1),
    "WORD-CELL-OFF": (1, (0, 0, 0, 1), (1, 0), (0, 1), 0),
}
CLIP_SET = {
    "timer": "HIDDEN", "disabled": "HIDDEN-OFF", "waiting": "HIDDEN",
    "anchored": "ANCHOR",
    "grabbed": "CELL", "released": "CELL", "dropped": "CELL", "bridge": "CELL",
    "tracked": "CAGE", "provisional": "CAGE", "seeking": "CAGE",
    "acquireflush": "WORD-RIGID", "resume": "WORD-RIGID-OFF",
    "synced": "WORD-DAMPED",
    "reacquire": "WORD-CELL-ON", "resume_grab": "WORD-CELL-OFF",
}


def prefab_docs(path):
    """Split a Unity YAML asset into (classId, anchor, body) documents."""
    import re
    docs = []
    for m in re.finditer(r"^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)",
                         open(path, encoding="utf-8").read(),
                         re.M | re.S):
        docs.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return docs


def parse_mods(docs, raw):
    """Every PrefabInstance's modification rows, grouped per (target fileID,
    guid), plus removed component/GO fileID sets per source guid — with
    grab-sync's vacuity guard: every serialized row must parse or the negative
    asserts read over an empty set."""
    import re
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
    import re
    return re.search(r"guid: (\w+)",
                     open(os.path.join(HERE, rel) + ".meta",
                          encoding="utf-8").read()).group(1)


def entry_nodes(prefab_path):
    """(guid, name->transform-fileIDs, name->component-fileIDs-by-owner) for a
    hand-read entry prefab (flat, no nesting)."""
    import re
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
    tf = {a: owner[a] for c, a, b in docs if c == 4 for a in [a] if a in owner}
    comp = {a: owner[a] for c, a, b in docs if c == 114 and a in owner}
    return guid, tf, comp, docs


def prefab_pins(assert_, mod, cfg):
    """The hand-maintained surfaces no compile or gate reads (CONVENTIONS §Per-
    entry checks): the variant's removals/retag/repark against the entry, and
    the composition's nested-instance wiring — the removal record the README
    carries in prose, pinned where a fileID can carry it."""
    import re
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
    # the entry's own merge/pin/toggle surface is REMOVED (the shared root
    # component is the only merge door; the composition root carries the one pin)
    # A MonoBehaviour doc never carries its C# type name — VRCFury features are
    # identified by their managedReference `class:` line, constraints by their
    # distinctive serialized fields (FreezeToWorld / ScaleAtRest).
    ent_vrcfury = [a for c, a, b in os_docs if c == 114
                   and re.search(r"class: (FullController|Toggle|ApplyDuringUpload)\b", b)]
    ent_pins = [a for c, a, b in os_docs if c == 114
                and os_comp.get(a) == "ObjectSync"
                and ("FreezeToWorld:" in b or "ScaleAtRest:" in b)]
    gone = [a for a in ent_vrcfury + ent_pins
            if (a, os_guid) in removed["Components"]]
    assert_(len(ent_vrcfury) == 4 and len(ent_pins) == 2
            and sorted(gone) == sorted(ent_vrcfury + ent_pins),
            f"variant: the entry's 4 VRCFury components (root FC/Toggle/ADU + "
            f"Sync_Target Drop toggle; found {len(ent_vrcfury)}) and the root "
            f"pin pair (found {len(ent_pins)}) are all removed "
            f"(removed rows carry {len(gone)} of them)")
    # the rotation rig is gone: removed-GO rows exist and neither node name
    # survives anywhere in the variant's own text (an added-back or renamed
    # node would resurface as a name row)
    assert_(len(removed["GameObjects"]) >= 2
            and not re.search(r"value: (Rot|Recon)\s*$", var_raw, re.M),
            f"variant: Rot/ and Recon/ removed "
            f"({len(removed['GameObjects'])} removed-GO rows)")
    # repark + retag: the park and tags derive from ONE seed and move together
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

    # nested drop-on-player: FreezeToWorld + Payload GOs removed
    dop_go = {a: re.search(r"m_Name: (.*)", b).group(1).strip()
              for c, a, b in dop_docs if c == 1 and "m_Name:" in b}
    for node in ("FreezeToWorld", "Payload"):
        fids = [a for a, n in dop_go.items() if n == node]
        assert_(fids and any((f, dop_guid) in cremoved["GameObjects"] for f in fids),
                f"composition: drop-on-player `{node}` GO removed")
    # the cell's stale edge: no instance modification re-parents/re-poses
    # SourcePosition, and no added source on its constraint (grab-sync's pins)
    sp_tf = [a for a, n in dop_tf.items() if n == "SourcePosition"]
    sp_cm = [a for a, n in dop_comp.items() if n == "SourcePosition"]
    bad_sp = [pp for (fid, g), m in cmods.items() if g == dop_guid
              for pp in m
              if (fid in sp_tf and pp.startswith(("m_Father", "m_LocalPosition",
                                                  "m_LocalRotation")))
              or (fid in sp_cm and pp.startswith("Sources."))]
    assert_(not bad_sp,
            f"composition: the cell's SourcePosition is untouched (found {bad_sp})")
    # GrabPosition repoint (the sanctioned two-source repoint): source0 retargeted
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
    # the park gains exactly one word-side source
    tp_cm = [a for a, n in dop_comp.items()
             if n == "TrackingPoints"]
    tp_mod = [m for (fid, g), m in cmods.items()
              if g == dop_guid and fid in tp_cm]
    assert_(any(m.get("Sources.totalLength", ("",))[0] == "2" for m in tp_mod)
            and any("Sources.source1.SourceTransform" in m for m in tp_mod)
            and not any(pp.startswith("Sources.source0")
                        for m in tp_mod for pp in m),
            "composition: the cage park gains source1 (the word park) at "
            "totalLength 2, source0 untouched")
    # CagePark: an added plain GO named CagePark, parked BELOW the prop (y<0)
    cp = re.search(r"m_Name: CagePark", comp_raw)
    cp_y = re.search(
        r"m_Name: CagePark(?:.*\n)*?  m_LocalPosition: \{x: ([-\d.e]+), y: ([-\d.e]+)",
        comp_raw)
    assert_(cp and cp_y and float(cp_y.group(2)) < 0,
            "composition: CagePark exists with a below-the-prop offset "
            f"(y={cp_y.group(2) if cp_y else '?'})")
    # Sync_Target wired to the mux, statically. The nested instance is the
    # VARIANT, whose remapped fileIDs appear in no .prefab (unity.md §Reading
    # serialized assets), so the row is identified by its content: the one
    # totalLength 0→1 write on the variant instance is Sync_Target's shipped
    # empty-list constraint gaining its single source.
    var_guid = guid_of(os.path.join("object-sync", "ObjectSync.prefab"))
    st_mod = [m for (fid, g), m in cmods.items() if g == var_guid
              and m.get("Sources.totalLength", ("",))[0] == "1"]
    assert_(len(st_mod) == 1
            and st_mod[0].get("Sources.source0.Weight", ("",))[0] == "1"
            and "Sources.source0.SourceTransform" in st_mod[0],
            "composition: Sync_Target sources [Prop/Source w=1] (the encoder "
            "measures the mux output, undamped)")
    # the ONE pin: exactly the two constraint docs on the composition ROOT GO
    # (every VRC constraint serializes FreezeToWorld:, so ownership is the
    # discriminator) serialize disabled at all-zero offsets — never Activate a
    # world pin (runtime.md §Constraints)
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
    """The sealed-interface coupling (T2 subsume), pinned per grab-sync's
    template: everything here is a hand-maintained pairing only this check
    reads — the ONE shared FullController's controller AND prms order (glue
    first in both: the animator param merge follows controllers order and the
    baked expression-parameter default follows prms order, so either inversion
    disarms the glue's Enable default-1 — controller.yaml's header owns the
    mechanism), the shipped menu entry and its prefix, globalParams exactly
    the build's derived list (the seal), the mount pairing (the variant
    instance named MOUNT, hanging directly under the component's GO — the
    frame every emitted binding resolves from), the nested entry's recorded
    FullController removal plus its physbone `parameter` override (the two T2
    remove-and-add edits nothing else validates), the glue's entry-rooted
    names against what the build's document declares, and the absence of any
    second FullController on the sync side (a split component un-unifies
    every shared name with no build error — the rewrite memo is per
    component)."""
    import re
    comp_path = os.path.join(HERE, "SyncOnPlayer.prefab")
    raw = open(comp_path, encoding="utf-8").read()
    docs = prefab_docs(comp_path)
    want_gp = mod.document(cfg)[1]["facts"]["globalParams"]
    n_fc = raw.count("class: FullController")
    assert_(n_fc == 1,
            f"shared: exactly ONE FullController authored here — a second "
            f"component un-unifies every shared name (found {n_fc})")
    # Every ordering and membership read below is scoped to THAT component's
    # own document — a whole-file find() would keep passing after a
    # controller moved onto some other component.
    fc = next((b for c2, a, b in docs
               if c2 == 114 and "class: FullController" in b), "")
    glue_g = guid_of("built/SyncOnPlayer_Fx.controller")
    sync_g = guid_of(os.path.join("object-sync", "built",
                                  "ObjectSync_Fx.controller"))
    gi, si = fc.find(glue_g), fc.find(sync_g)
    assert_(gi != -1 and si != -1,
            f"shared: the component carries both built controllers by GUID "
            f"(glue at {gi}, sync at {si})")
    assert_(gi == -1 or si == -1 or gi < si,
            "shared: the glue controller sits BEFORE the sync build — "
            "first-wins in controllers order is half of what arms Enable")
    # The OTHER half: the baked expression-parameter default comes from the
    # prms list's assets, merged in ITS order — reorder prms alone and Enable
    # bakes default 0 with controllers order still green.
    gp_g = guid_of("built/SyncOnPlayer_Fx_Parameters.asset")
    sp_g = guid_of(os.path.join("object-sync", "built",
                                "ObjectSync_Fx_Parameters.asset"))
    gpi, spi = fc.find(gp_g), fc.find(sp_g)
    assert_(gpi != -1 and spi != -1 and gpi < spi,
            f"shared: the glue params asset sits BEFORE the sync build's in "
            f"prms — the baked Enable default merges in that order "
            f"({gpi}, {spi})")
    # The menu asset is the T4 drive surface (the entry's params vanish at
    # T2), so its entry and prefix are pinned, not just its existence.
    menu_g = guid_of("built/SyncOnPlayer_Fx_Menu.asset")
    assert_(menu_g in fc and "prefix: Sync On Player" in fc,
            "shared: the glue menu asset rides the component's menus at "
            "prefix `Sync On Player`")
    blocks = re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"")
            for ln in b.splitlines()] for b in blocks]
    assert_(got == [want_gp],
            f"shared: the component's globalParams is exactly the build's "
            f"derived list {want_gp} — got {got}")
    # The mount pairing, both halves: the variant instance (resolved by its
    # source-prefab guid, never by scanning every m_Name) is named MOUNT, and
    # it is a DIRECT CHILD of the component's GO — the emitted `ObjectSync/…`
    # bindings resolve from that GO, so one extra nesting level kills every
    # binding silently.
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
    # The two T2 edits on the nested entry instance. The entry's own
    # FullController never appears as text here — only its
    # m_RemovedComponents row proves the double build is off; derive the
    # anchor from the entry prefab rather than pinning a literal.
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
    # The physbone `parameter` override mints `Grab_IsGrabbed` for the glue's
    # conditions (a VRC-SDK component override — survives the build where a
    # VRCFury one would not).
    gb_cm = [a for a, n in dop_comp.items() if n == "GrabBone"]
    got_prm = [m["parameter"][0] for (fid, g), m in mods.items()
               if g == dop_guid and fid in gb_cm and "parameter" in m]
    assert_(got_prm == ["Grab"],
            f"shared: the grab physbone's `parameter` overrides to `Grab` "
            f"— got {got_prm}")
    # The glue hard-codes sealed entry names (`OS/Ready`, the stage AAPs),
    # which couples it to the entry's CONFIG keys with nothing else watching:
    # rename `internal` or `channel` upstream and the glue recompiles green
    # while every engage rung gates forever on a param nothing writes. So:
    # every entry-rooted name the glue binds must be a name its own sync
    # build's document declares.
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
    # The sync side carries no FullController of its own anywhere: the entry
    # prefab used to own one, and a leftover builds the wire twice.
    rig = open(os.path.join(HERE, "object-sync", "ObjectSync.prefab"),
               encoding="utf-8").read()
    assert_("class: FullController" not in rig,
            "shared: object-sync/ObjectSync.prefab carries no FullController "
            "— the shared root component is the only merge door")


def parse_clips(path):
    """The bounded clip-table subset both documents use: 2-space clip names,
    4-space set:/curves:/length rows, 6-space quoted bindings. Values kept as
    verbatim strings so the diff is exact."""
    import re
    clips, cur, sect = {}, None, None
    started = False
    for line in open(path, encoding="utf-8"):
        if re.match(r"^clips:", line):
            started, cur = True, None
            continue
        if not started:
            continue
        m = re.match(r"^  ([\w+-]+):", line)
        if m:
            cur = m.group(1)
            clips[cur] = {"set": {}, "curves": {}, "len": None}
            sect = None
            continue
        if cur is None:
            continue
        m = re.match(r"^    (seconds|length): ([\d.]+)", line)
        if m:
            clips[cur]["len"] = m.group(2)
            continue
        if re.match(r"^    set:", line):
            sect = "set"
            continue
        if re.match(r"^    curves:", line):
            sect = "curves"
            continue
        m = re.match(r'^      "([^"]+)": (.+?)\s*$', line) \
            or re.match(r'^      ([\w+./-]+(?:/[\w+.-]+)*): (.+?)\s*$', line)
        if m and sect:
            val = m.group(2)
            if not val.startswith(("{", "[")):
                val = re.sub(r"\s+#.*$", "", val)
            clips[cur][sect][m.group(1)] = val
    return clips


def _num(s):
    try:
        return float(s)
    except ValueError:
        return None


def transcription_pins(assert_):
    entry = parse_clips(os.path.join(HERE, os.pardir, os.pardir,
                                     "drop-on-player", "controller.yaml"))
    boxt = parse_clips(os.path.join(HERE, os.pardir, os.pardir,
                                    "box-tracker", "controller.yaml"))
    glue = parse_clips(os.path.join(HERE, "controller.yaml"))

    def diff_cell(name, expect_set, expect_curves):
        g = glue.get(name)
        if g is None:
            assert_(False, f"clip `{name}` exists in the glue document")
            return
        bad = []
        for k, v in expect_set.items():
            got = g["set"].get(k)
            if got is None or _num(got) != _num(v) and got != v:
                bad.append(f"{k}: want {v!r} got {got!r}")
        for k, v in expect_curves.items():
            got = g["curves"].get(k)
            if got != v:
                bad.append(f"curve {k}: want {v!r} got {got!r}")
        extra = [k for k in list(g["set"]) + list(g["curves"])
                 if k.startswith(PREFIX) and k not in GLUE_KEYS
                 and k not in expect_set and k not in expect_curves]
        assert_(not bad and not extra,
                f"`{name}` transcribes its cell verbatim"
                + (f" — mismatched: {bad[:4]}" if bad else "")
                + (f" — untranscribed extras: {extra[:4]}" if extra else ""))

    # The plain transcriptions, GP carve applied where ruled.
    for name, src in CELL_SOURCE.items():
        e = entry[src]
        eset = {PREFIX + k: v for k, v in e["set"].items()}
        ecur = {PREFIX + k: v for k, v in e["curves"].items()}
        if name in GP_CARVE:
            eset[GP0], eset[GP1] = "1", "0"
        diff_cell(name, eset, ecur)

    # provisional = released cell + tracked cage; tracked owns scale x/y by
    # curve and Output by the readout DBT, so released's static copies drop.
    import re
    rel, trk = entry["released"], entry["tracked"]
    fset = dict(rel["set"])
    for k, v in trk["set"].items():
        if k.startswith("TrackingPoints/"):
            fset[k] = v
    for k in list(fset):
        if re.search(r"TrackingPoints/[XYZ][+-]/Transform\.m_LocalScale\.[xy]$", k) \
           or "TrackingPoints/Output/" in k:
            del fset[k]
    fcur = dict(trk["curves"])
    fcur.update(rel["curves"])
    diff_cell("provisional",
              {PREFIX + k: v for k, v in fset.items()},
              {PREFIX + k: v for k, v in fcur.items()})

    # seeking = tracked cell + box-tracker's `searching` cage verbatim (the
    # self-hold configuration is that entry's to own).
    sset = {k: v for k, v in trk["set"].items()
            if not k.startswith("TrackingPoints/")}
    sset.update(boxt["searching"]["set"])
    diff_cell("seeking", {PREFIX + k: v for k, v in sset.items()}, {})

    # readout leaves: entry values verbatim, padded to the pulse length so
    # TrackedProvisional's blend-tree exitTime is well-defined.
    for name in ("readout_xp", "readout_xn", "readout_yp", "readout_zp"):
        e = entry[name]
        diff_cell(name, {PREFIX + k: v for k, v in e["set"].items()}, {})
        assert_(glue[name]["len"] == "0.5",
                f"`{name}` padded to the pulse length (0.5) — got {glue[name]['len']}")

    # Empirical lengths transcribe too: the pulse and the boot dwell.
    assert_(glue["released"]["len"] == entry["released"]["len"],
            f"released pulse length transcribes ({entry['released']['len']})")
    assert_(glue["provisional"]["len"] == entry["released"]["len"],
            "provisional dwell = the pulse length (ruling 13)")
    assert_(glue["timer"]["len"] == entry["timer"]["len"],
            f"boot dwell transcribes ({entry['timer']['len']})")

    # Value-set collapse: every clip's glue bindings match its declared set.
    for name, setname in CLIP_SET.items():
        root, mux, damper, park, disp = VALUE_SETS[setname]
        want = dict(zip(GLUE_KEYS,
                        (root, *mux, *damper, *park,
                         disp if disp is not None else "CURVE")))
        g = glue[name]
        bad = []
        for k, v in want.items():
            if v == "CURVE":
                if k not in g["curves"]:
                    bad.append(f"{k}: expected curve-owned")
                continue
            got = g["set"].get(k)
            if got is None or _num(got) != float(v):
                bad.append(f"{k}: want {v} got {got!r}")
        assert_(not bad, f"`{name}` holds value-set {setname}"
                + (f" — off: {bad[:4]}" if bad else ""))


def main():
    mod = entry_module()
    cfg = sync_config(mod)

    if "--check" in sys.argv:
        ok = True

        def assert_(cond, msg):
            nonlocal ok
            print(("  ok   " if cond else "  FAIL ") + msg)
            ok = ok and cond

        text, f = mod.document(cfg)
        facts = f["facts"]
        assert_(mod.document(cfg)[0] == text, "regeneration is byte-identical")
        tags = mod.tag_set(cfg, "Prop")
        assert_(len(tags) == len(set(tags)),
                f"collision tags unique across stages ({len(tags)} tags: {tags})")
        entry_tags = mod.tag_set(mod.CONFIG, mod.CONFIG["objects"][0]["name"])
        assert_(not set(tags) & set(entry_tags),
                f"tags disjoint from the entry default's (a shared tag is the "
                f"cross-build sender bleed the rigSeed skew exists to prevent)")
        assert_(tuple(mod.rig_offset(cfg["rigSeed"]))
                != tuple(mod.rig_offset(mod.CONFIG["rigSeed"])),
                "park disjoint from the entry default's (tags and park skew "
                "together — the cluster-summing bug needs both)")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} "
              f"payload / {facts['batchCount']} batches / "
              f"~{facts['cycleSeconds']:.3f}s refresh")
        print(f"  park {mod.rig_offset(cfg['rigSeed'])}")
        transcription_pins(assert_)
        prefab_pins(assert_, mod, cfg)
        shared_component_pins(assert_, mod, cfg)
        print("scope: emit determinism, the seed-skew facts, the per-state "
              "cell-binding transcription diff (exceptions carved at the "
              "carve tables above), the value-set collapse, and the "
              "shared-component pins (orders, globalParams, mount, the T2 "
              "removals); the glue's TRANSITION set is checked by hand "
              "against the entry's (T2 — recorded in the README), and the "
              "prefab pins land with the prefab (T-stage build); freshness "
              "of the committed documents is regenerate-and-read-git-diff")
        sys.exit(0 if ok else 1)

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
