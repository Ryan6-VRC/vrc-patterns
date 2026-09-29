#!/usr/bin/env python3
"""grab-sync-persist: grab-sync, plus a placed prop that survives an avatar swap.

    python compositions/grab-sync-persist/generate.py           # writes the three documents
    python compositions/grab-sync-persist/generate.py --check   # asserts the prefab, writes nothing

Output, each compiled with `CompileController` into the `built/` beside it:

  controller.yaml             the glue: ../grab-sync/controller.yaml TRANSFORMED, never
                              hand-edited. Every byte of grab-sync's graph and clip table
                              carries over; the delta below is applied on top.
  persist/controller.yaml     the exchange with the bridge: `../../bridge-persist`'s generator,
                              driven unmodified at this composition's config (`persist_config`).
  object-sync/controller.yaml grab-sync's own single-prop sync build (its
                              `grabsync_single_config`, read live) at `wordRoot` NAMESPACE,
                              so the word table is published bare under the namespace.

The prefab's one FullController plays them glue, persist, sync, in that order in both lists.

WHY A TRANSFORM
---------------
The composition exists to show what persistence adds to a gimmick built on `object-sync`, so the
delta has to stay legible as a delta and has to follow grab-sync when grab-sync moves. Every
anchor the transform depends on (a state, a rung, a declaration, a clip row) is asserted, and a
missing one is a REFUSE naming it: an upstream edit fails this generator loudly instead of
emitting a glue that silently lacks a rung. Re-run after any edit to grab-sync's document, to
object-sync's generator or to bridge-persist's.

WHAT THE PERSIST LAYER TAKES OFF THE GLUE
-----------------------------------------
Everything about the bridge: the reserved names, the quiesce, Announce and Boot, the window, the
Enable mirror and restoring Enable. The layer drives `ObjectSync/Enable` off for the exchange,
which parks the glue in its own `Disabled`; it raises its flag (local, outside the namespace)
for the hold when the restored payload has the prop placed; it lowers the flag and sets Enable
from the mirror in one driver. Its payload is the sync build's word table plus `Detached`, both
read here at generation, so a word added upstream is reset with the rest.

THE GLUE'S DELTA
----------------
1. Namespace. `Detached` moves to `<NAMESPACE>/Detached`, so the bridge carries it with the
   words. The glue also declares `Place` and the flag. The synced bit count is grab-sync's.
2. `Place`. A local, unsynced control that sets the prop down where it stands without a grab,
   from the menu or over OSC: from `Anchored` it drops the prop, stamping `Detached` as a grab
   would, and consumes itself; `Disabled` clears it too, so a write while the prop is away is
   dropped rather than latched. Published bare by its own `globalParams` entry and fronted by
   the menu's button.
3. `Persist Place`, the one place state. Entered from `Disabled` on the wearer while the flag is
   up and `Detached` is true. A wearer's own `Sync` rides `Sync_Target`, which rides the mux, so
   only the sync build's reconstruction (`ObjectSync/Rig/Prop/Display`) shows the wearer the
   restored words: the mux gains that node as a fourth slot on both channels (the prefab's),
   every clip holds it at 0, and `persist_place` is `anchored` with the mux moved onto it, so
   the cell rides its rest frame live onto the reconstruction with the drag heading parked on
   it. Flag down, it goes to `Dropped`, which freezes the cell and unparks the heading where
   they settled, so a re-grab picks the prop up there and the resumed walks measure the restored
   pose rather than home. ACQUIRE could not serve: it holds the cell frozen at home. It has no
   Enable rung: Enable is off for its whole life and returns in the evaluation the flag falls.
4. `Disabled` writes `Detached` 0 on entry and the bridge writes `Detached` 1, so no entry into
   `Disabled` may land after the bridge's write. The glue enters `Disabled` at load (`Timer`'s
   wearer rung) and otherwise only when Enable falls. The layer drives Enable off within a few
   frames of load, before `Boot` reaches the bridge, and keeps it off until it lowers the flag,
   while the bridge writes nothing until its settle after `Boot` has passed. So the last entry
   into `Disabled` precedes the bridge's write, and `Persist Place` leaves for `Dropped`, never
   back through `Disabled`. A menu toggle of Enable inside the window breaks this, and is
   unguarded.
5. A remote's return. In grab-sync, Enable coming back on always finds `Detached` false, because
   switching off resets it; after a restore it can find it true. A remote in `Disabled` then
   goes to grab-sync's hidden late-join path (`Waiting`, then `Acquire` on `OS/Ready`) instead
   of `Anchored`, so it never shows the prop at home before gliding to the word.

THE HOLD
--------
How long the flag stays up: PLACE_SETTLE, the cell's own settle, and no longer. The quiesce's
zeroed words went out on the wire, the wire's refresh is counted in the wearer's frames, and a
remote re-engages the moment Enable returns. So at a wearer frame rate low enough that one
refresh outlasts the hold, a watching remote can glide in from a half-updated table. The hold
does not wait that refresh out, because every watching client would wait it on every swap at
every frame rate. It is one value, passed to the persist layer's config; nothing else reads it.
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
UPSTREAM = os.path.normpath(os.path.join(HERE, os.pardir, "grab-sync"))
UPSTREAM_DOC = os.path.join(UPSTREAM, "controller.yaml")
UPSTREAM_GEN = os.path.join(UPSTREAM, "generate.py")
PERSIST_GEN = os.path.join(REPO, "bridge-persist", "generate.py")
GLUE_DOC = os.path.join(HERE, "controller.yaml")
PERSIST_DOC = os.path.join(HERE, "persist", "controller.yaml")
SYNC_DOC = os.path.join(HERE, "object-sync", "controller.yaml")

CONTROLLER = "GrabSyncPersist_Fx"
PERSIST_CONTROLLER = "GrabSyncPersist_Persist_Fx"
NAMESPACE = "BridgePersist/GrabSyncPersist"
INTERNAL = "Persist/GrabSyncPersist"
DETACHED = f"{NAMESPACE}/Detached"
PLACE = "GrabSyncPersist/Place"
EN = "ObjectSync/Enable"
MOUNT = "ObjectSync"
DETACHED_SPEC = "{ type: bool, default: false, vrc: { synced: true, saved: false } }"

# The cell's settle: its constraint ring, the drag park and the delayed show. [EMPIRICAL: re-measure
# the placed pose at a low frame rate after any change to the cell or the mux]
PLACE_SETTLE = 0.5


MUX = "Prop/Source/VRC{ch}Constraint.Sources.source{i}.Weight"


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg} Reconcile generate.py's transform with "
                     "../grab-sync/controller.yaml before emitting.")


def load(path, name):
    if not os.path.exists(path):
        raise SystemExit(f"REFUSE: {path} is missing — this composition is built from it.")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_build():
    """grab-sync's single-prop sync config, read from its generator, at wordRoot NAMESPACE."""
    up = load(UPSTREAM_GEN, "grab_sync_generate")
    if not hasattr(up, "grabsync_single_config") or not hasattr(up, "entry_module"):
        refuse("grab-sync's generate.py no longer exposes grabsync_single_config/entry_module.")
    entry = up.entry_module()
    cfg = up.grabsync_single_config(entry)
    if cfg.get("mountPath") != MOUNT:
        refuse(f"grab-sync's single build mounts at {cfg.get('mountPath')!r}, not {MOUNT!r}.")
    cfg["wordRoot"] = NAMESPACE
    return entry, cfg


def words(entry, cfg):
    """[(name, declaration)] for every word the sync build publishes under the namespace."""
    out = []
    for ln in entry.document(cfg)[1]["params"]:
        m = re.match(rf"^  ({re.escape(NAMESPACE)}/[^:\s]+):\s*(.*?)\s*(#.*)?$", ln)
        if m:
            out.append((m.group(1), m.group(2)))
    if not out:
        raise SystemExit(f"REFUSE: the sync build declares nothing under {NAMESPACE}/ — its wordRoot "
                         "no longer publishes the word table there, and a restore would place nothing.")
    return out


def enable_spec(src):
    """grab-sync's Enable declaration, verbatim: the persist layer declares it identically."""
    m = re.findall(rf"^  {re.escape(EN)}:\s*(\{{.*?\}}\s*\}})", src, re.M)
    if len(m) != 1 or "synced: true" not in m[0] or "default:" not in m[0]:
        refuse(f"grab-sync no longer declares `{EN}` once, synced, with a default.")
    return m[0]


def persist_config(entry, cfg, src):
    """The persist layer's config: bridge-persist's generator runs on this, unmodified."""
    return {"namespace": NAMESPACE, "internal": INTERNAL, "controller": PERSIST_CONTROLLER,
            "id": None, "enable": (EN, enable_spec(src)),
            "payload": words(entry, cfg) + [(DETACHED, DETACHED_SPEC)],
            "placed": [DETACHED], "mirror": None, "hold": PLACE_SETTLE, "layer": "Persist"}


# ------------------------------------------------------------------ the header ---
HEADER = """\
# GrabSyncPersist glue controller — GENERATED by generate.py from ../grab-sync/controller.yaml; never hand-edit it, re-run the generator.
# grab-sync's header owns every design decision this graph carries unchanged; generate.py's docstring owns the delta item by item,
# and persist/controller.yaml (bridge-persist's layer) owns the exchange with the bridge. This glue reads no reserved name.
# State↔clip mapping, beyond grab-sync's: Place→dropped, Persist Place→persist_place.
# Glue value-sets gain the mux's fourth slot (source3 on both channels, the sync build's reconstruction): 0 in every grab-sync clip, 1 only in persist_place, which is `anchored` with the mux moved there.
# Detached lives at DETACHED: payload, synced, unsaved, default false — grab-sync's bit under the namespace.
# FLAG is the persist layer's flag, up for the hold while Enable is off; Persist Place rides it.
""".replace("DETACHED", DETACHED)


# --------------------------------------------------------------- the transform ---
def split_states(lines, start, stop):
    """{state name: (first, last+1)} for the 6-space state blocks inside lines[start:stop]."""
    heads = [(i, m.group(1)) for i in range(start, stop)
             for m in [re.match(r"^      ([A-Za-z_][\w ]*):\s*$", lines[i])] if m]
    dup = sorted({n for _, n in heads if [h for _, h in heads].count(n) > 1})
    if dup:
        refuse(f"grab-sync's layer declares the state(s) {dup} more than once; the transform would edit only the last.")
    return {n: (i, heads[k + 1][0] if k + 1 < len(heads) else stop) for k, (i, n) in enumerate(heads)}


def index_of(lines, text, what, lo=0, hi=None):
    hits = [i for i in range(lo, len(lines) if hi is None else hi) if lines[i] == text]
    if len(hits) != 1:
        refuse(f"{what}: expected exactly one line {text.strip()!r}, found {len(hits)}.")
    return hits[0]


def rename_detached(line):
    head, sep, tail = line.partition("#")
    return re.sub(r"(?<![\w/])Detached(?![\w/])", DETACHED, head) + sep + tail


def glue_states(flag):
    return [
        "      # Place: the wearer's no-grab drop, from a menu button or OSC. The cell rests on its home tip, so it",
        "      # freezes where it stands with no release pulse to heal it, and the stamp is the grab's own. The driver consumes the control.",
        "      Place:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, set: {{ {DETACHED}: 1, {PLACE}: 0 }} }}",
        "        motion: { clip: dropped }",
        "        transitions:",
        f"          - {{ to: Disabled, when: [ {EN} less 0.5 ] }}",
        "          - { to: Dropped,  when: [ ], exitTime: 1.0 }   # the stamp landed at entry",
        "      # The restored placement, wearer-only, while the persist layer holds its flag up with Enable off: the cell",
        "      # rides the reconstruction of the restored words. No Enable rung: Enable returns in the evaluation the flag falls.",
        "      Persist Place:",
        "        motion: { clip: persist_place }",
        "        transitions:",
        f"          - {{ to: Dropped, when: [ {flag} is false ] }}",
    ]


LAYOUT_ADD = {"Place": [260, 460], "Persist Place": [490, 250]}


def parse_clip_blocks(lines, lo, hi):
    """{clip name: (first, last+1)} for the 2-space clip heads inside lines[lo:hi]."""
    heads = [(i, m.group(1)) for i in range(lo, hi) for m in [re.match(r"^  ([\w]+):", lines[i])] if m]
    dup = sorted({n for _, n in heads if [h for _, h in heads].count(n) > 1})
    if dup:
        refuse(f"grab-sync's clip table declares the clip(s) {dup} more than once; the transform would edit only the last.")
    return {n: (i, heads[k + 1][0] if k + 1 < len(heads) else hi) for k, (i, n) in enumerate(heads)}


def transform(src, flag):
    lines = src.split("\n")

    # --- document head: grab-sync's header comment is replaced by ours.
    schema = index_of(lines, "schema: 1", "document head")
    body = lines[schema:]
    name_at = index_of(body, "controller: GrabSync_Fx", "controller name, below `schema: 1`")
    body[name_at] = f"controller: {CONTROLLER}"

    # --- parameters.
    p0 = index_of(body, "parameters:", "parameters block")
    l0 = index_of(body, "layers:", "layers block")
    det = [i for i in range(p0, l0) if re.match(r"^  Detached:\s", body[i])]
    if len(det) != 1 or DETACHED_SPEC not in body[det[0]]:
        refuse("grab-sync no longer declares `Detached` as one synced, unsaved bool defaulting false.")
    decl = [
        f"  {DETACHED}: {DETACHED_SPEC}   # grab-sync's Detached, as payload",
        f"  {PLACE}: {{ type: bool, default: false, vrc: {{ synced: false, saved: false }} }}   # the wearer's no-grab drop; published bare",
        f"  {flag}: {{ type: bool, default: false, scratch: true }}   # the persist layer's flag; local, never published",
    ]
    body = body[:det[0]] + decl + body[det[0] + 1:]

    # --- the graph: Detached renamed everywhere it is structural.
    l0 = index_of(body, "layers:", "layers block")
    c0 = index_of(body, "clips:", "clips block")
    body = body[:l0] + [rename_detached(l) for l in body[l0:c0]] + body[c0:]
    if any(re.search(r"(?<![\w/])Detached(?![\w/])", l.partition("#")[0]) for l in body[l0:c0]):
        refuse("a bare `Detached` survived the rename.")
    default = index_of(body, "    default: Timer", "Prop layer default", l0, c0)
    states = split_states(body, l0, default)
    for need in ("Timer", "Disabled", "Anchored", "Dropped", "Waiting"):
        if need not in states:
            refuse(f"grab-sync's layer has no `{need}` state.")
    # Delta item 4 rests on Timer's wearer rung being the glue's one load path into Disabled.
    a, b = states["Timer"]
    index_of(body, "          - { to: Disabled, when: [ IsLocal is true ] }", "Timer's wearer rung", a, b)
    # Every other way in must wait on Enable falling: Disabled resets Detached on entry, so a rung
    # that re-enters it while the layer holds Enable off would land after the bridge's write.
    for i in range(l0, default):
        if re.match(r"^\s+- \{ to: Disabled,", body[i]) and not a <= i < b \
                and not re.search(rf"when: \[ {re.escape(EN)} less 0\.5 \]", body[i]):
            refuse(f"a rung into Disabled does not wait on {EN} falling: {body[i].strip()!r}.")

    edits = []   # (index, replace_count, new lines), applied bottom-up
    a, b = states["Disabled"]
    d = index_of(body, f"          - driver: {{ localOnly: true, set: {{ {DETACHED}: 0 }} }}   # off-is-reset: recall home",
                 "Disabled's reset driver", a, b)
    edits.append((d + 1, 0, [f"          - driver: {{ localOnly: true, set: {{ {PLACE}: 0 }} }}   # a Place written while the prop was away does not fire at the next Anchored"]))
    en_on = index_of(body, f"          - {{ to: Anchored, when: [ {EN} greater 0.5 ] }}", "Disabled's enable rung", a, b)
    edits.append((en_on, 0, [
        f"          - {{ to: Persist Place, when: [ IsLocal is true, {flag} is true, {DETACHED} is true ] }}   # the persist layer's hold",
        f"          - {{ to: Waiting,  when: [ IsLocal is false, {DETACHED} is true, {EN} greater 0.5 ] }}   # a restore's return: hidden until the word, never shown at home"]))
    a, b = states["Anchored"]
    g = index_of(body, "          - { to: Grabbed,  when: [ Grab_IsGrabbed is true ] }", "Anchored's grab rung", a, b)
    edits.append((g + 1, 0, [f"          - {{ to: Place,    when: [ IsLocal is true, {PLACE} is true ] }}"]))
    edits.append((default, 0, glue_states(flag)))
    lay = [i for i in range(default, c0) if body[i].startswith("      nodes: {") and body[i].endswith("}")]
    if len(lay) != 1:
        refuse("the Prop layer's layout nodes line moved.")
    extra = ", ".join(f"{k}: [{x}, {y}]" for k, (x, y) in LAYOUT_ADD.items())
    edits.append((lay[0], 1, [body[lay[0]][:-1].rstrip() + ", " + extra + " }"]))
    for i, n, new in sorted(edits, key=lambda e: e[0], reverse=True):
        body[i:i + n] = new

    # --- clips: the fourth mux slot at 0 everywhere, then the place clip.
    c0 = index_of(body, "clips:", "clips block")
    begin = [i for i in range(c0, len(body)) if body[i].startswith("  # --- BEGIN GENERATED")]
    end = [i for i in range(c0, len(body)) if body[i] == "  # --- END GENERATED"]
    if len(begin) != 1 or len(end) != 1:
        refuse("grab-sync's clip table is no longer one BEGIN/END marker pair.")
    note = [i for i in range(l0, c0) if body[i].startswith("# Every clip = ")]
    if len(note) != 1:
        refuse("grab-sync's per-clip binding-count note moved.")
    blocks = parse_clip_blocks(body, begin[0] + 1, end[0])
    for need in ("anchored", "dropped"):
        if need not in blocks:
            refuse(f"grab-sync's clip table has no `{need}` clip.")
    out = []
    for name, (a, b) in blocks.items():
        blk = body[a:b]
        for ch in ("Position", "Rotation"):
            s2 = f'      "{MUX.format(ch=ch, i=2)}": '
            hit = [k for k, l in enumerate(blk) if l.startswith(s2)]
            if len(hit) != 1 or any(MUX.format(ch=ch, i=3) in l for l in blk):
                refuse(f"clip `{name}` does not hold exactly one {ch} mux source2 row and no source3.")
            blk.insert(hit[0] + 1, f'      "{MUX.format(ch=ch, i=3)}": 0')
        blocks[name] = blk
        out.extend(blk)

    rows = [l for l in blocks["anchored"][1:] if not l.startswith(("    seconds:", "    #"))]
    place = ["  persist_place:  # cell `anchored` + the mux on its fourth slot, the reconstruction; park on"] + rows
    want = {MUX.format(ch=ch, i=i): ("1" if i == 3 else "0") for ch in ("Position", "Rotation") for i in range(4)}
    seen = set()
    for k, l in enumerate(place):
        mm = re.match(r'^      "([^"]+)": (\S+)$', l)
        if mm and mm.group(1) in want:
            place[k] = f'      "{mm.group(1)}": {want[mm.group(1)]}'
            seen.add(mm.group(1))
    if seen != set(want):
        refuse(f"`anchored` does not carry every mux row (missing {sorted(set(want) - seen)}).")
    out += place

    body = (body[:note[0]] + ["# Every clip = grab-sync's bindings plus the mux's source3 weight on both channels."]
            + body[note[0] + 1:begin[0]] + out + body[end[0] + 1:])
    return HEADER.replace("FLAG", flag) + "\n" + "\n".join(body)


# ------------------------------------------------------------------ the check ---
def prefab_docs(path):
    return [(int(m.group(1)), int(m.group(2)), m.group(3)) for m in re.finditer(
        r"^--- !u!(\d+) &(\d+)(?: stripped)?\n(.*?)(?=^--- |\Z)",
        open(path, encoding="utf-8").read(), re.M | re.S)]


def meta_guid(path):
    return re.search(r"guid: (\w+)", open(path + ".meta", encoding="utf-8").read()).group(1)


def guid_index():
    """guid -> repo-relative path for every committed prefab, so a nested fileID can be followed."""
    repo = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
    out = {}
    for dp, dn, fn in os.walk(repo):
        dn[:] = [d for d in dn if d not in (".git", "built", "assets")]
        for f in fn:
            if f.endswith(".prefab.meta"):
                out[meta_guid(os.path.join(dp, f[:-5]))] = os.path.join(dp, f[:-5])
    return out, repo


def resolve(prefab, fid, _idx=[]):
    """(entry-relative prefab, node path under the instance root) for a transform fileID inside
    `prefab`, following nested instances: Unity names an object of a nested instance by
    instanceFileID XOR the source object's fileID."""
    if not _idx:
        _idx.append(guid_index())
    idx, repo = _idx[0]
    docs = prefab_docs(prefab)
    tf = {a: b for c, a, b in docs if c == 4}
    if fid in tf and "stripped" not in open(prefab, encoding="utf-8").read().split(f"&{fid}", 1)[1][:12]:
        names = {a: re.search(r"m_Name: (.*)", b).group(1).strip() for c, a, b in docs if c == 1 and "m_Name:" in b}
        parts, cur = [], fid
        while cur in tf:
            g = re.search(r"m_GameObject: \{fileID: (\d+)", tf[cur])
            parts.append(names.get(int(g.group(1)), "?") if g else "?")
            cur = int(re.search(r"m_Father: \{fileID: (\d+)", tf[cur]).group(1))
        return os.path.relpath(prefab, repo).replace(os.sep, "/"), "/".join(reversed(parts[:-1]))
    for c, a, b in docs:
        if c != 1001:
            continue
        g = re.search(r"m_SourcePrefab: \{fileID: 100100000, guid: (\w+)", b)
        inner = (fid ^ a) & 0x7FFFFFFFFFFFFFFF
        if g and g.group(1) in idx:
            src = idx[g.group(1)]
            if inner in {x for cc, x, _ in prefab_docs(src)} or any(
                    cc == 1001 for cc, _, _ in prefab_docs(src)):
                hit = resolve(src, inner)
                if hit:
                    return (os.path.relpath(src, repo).replace(os.sep, "/"), hit[1]) if hit[0] else hit
    return None


def check(entry, cfg):
    """The hand-maintained variant surface nothing else reads, each silent at build when broken."""
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)

    path = os.path.join(HERE, "GrabSyncPersist.prefab")
    raw = open(path, encoding="utf-8").read()
    docs = prefab_docs(path)
    base = os.path.join(UPSTREAM, "GrabSync.prefab")
    base_guid = meta_guid(base)
    base_docs = prefab_docs(base)
    inst = [b for c, a, b in docs if c == 1001]
    assert_(len(inst) == 1 and f"m_SourcePrefab: {{fileID: 100100000, guid: {base_guid}" in inst[0],
            "the prefab is a variant of ../grab-sync/GrabSync.prefab")
    inst = inst[0] if inst else ""

    # One FullController, ours, and the base's removed: the base's plays grab-sync's own glue, so a
    # surviving copy builds a second, sealed-apart instance of everything.
    fcs = [b for c, a, b in docs if c == 114 and "class: FullController" in b]
    assert_(len(fcs) == 1, f"exactly one FullController authored on the variant (found {len(fcs)})")
    fc = fcs[0] if fcs else ""
    removed = "".join(re.findall(r"m_RemovedComponents:\n((?:    - \{fileID: .+\n(?:      .+\n)?)+)", inst))
    base_root = [a for c, a, b in base_docs if c == 114 and ("class: FullController" in b or "class: Toggle" in b)]
    gone = [a for a in base_root if re.search(rf"fileID: {a},\s+guid: {base_guid}", removed)]
    assert_(len(base_root) == 2 and gone == base_root,
            f"the base root's FullController and Toggle are removed (base {base_root}, removed {gone})")

    # The order is load-bearing twice: the glue first arms Enable (first-wins), and the one component
    # is what unifies the persist layer's flag and Enable with the glue's.
    glue_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}.controller"))
    pers_g = meta_guid(os.path.join(HERE, "persist", "built", f"{PERSIST_CONTROLLER}.controller"))
    sync_g = meta_guid(os.path.join(HERE, "object-sync", "built", "ObjectSync_Fx.controller"))
    gp_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}_Parameters.asset"))
    pp_g = meta_guid(os.path.join(HERE, "persist", "built", f"{PERSIST_CONTROLLER}_Parameters.asset"))
    sp_g = meta_guid(os.path.join(HERE, "object-sync", "built", "ObjectSync_Fx_Parameters.asset"))
    menu_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}_Menu.asset"))
    ctl = re.findall(r"objRef: \{fileID: 9100000, guid: (\w+)", fc)

    def sect(k):
        m = re.search(r"\n        " + k + r":\n(.*?)\n        [a-zA-Z]+:", fc, re.S)
        return m.group(1) if m else ""
    prm = re.findall(r"objRef: \{fileID: 11400000, guid: (\w+)", sect("prms"))
    mnu = re.findall(r"objRef: \{fileID: 11400000, guid: (\w+)", sect("menus"))
    assert_(ctl == [glue_g, pers_g, sync_g],
            "controllers are [glue, persist, sync build] — glue first arms Enable; one component unifies the flag")
    assert_(prm == [gp_g, pp_g, sp_g] and mnu == [menu_g],
            "prms are [glue, persist, sync build] params in the same order, and the menu is this entry's own")
    want_gp = entry.document(cfg)[1]["facts"]["globalParams"] + [PLACE]
    blocks = re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"") for ln in b.splitlines()] for b in blocks]
    assert_(got == [want_gp], f"globalParams is the sync build's derived list plus Place {want_gp} (got {got})")

    # The flag must stay local: published, a host declaration could capture it and the bridge would
    # see it. VRCFury's grammar: a trailing * matches by prefix, anything else exactly.
    flag = load(PERSIST_GEN, "bridge_persist_generate").flag_name({"internal": INTERNAL})
    hits = [g for gl in got for g in gl
            if (g.endswith("*") and flag.startswith(g[:-1])) or g == flag]
    assert_(not hits, f"no globalParams entry reaches the persist layer's flag {flag} (reached by {hits})")

    # The mux's fourth slot, both channels: the sync build's reconstruction node, inside the list
    # length, at zero offset. A slot past totalLength is a client no-op however the clips weight
    # it, an offset places the restored prop off the words, and a same-named node elsewhere reads
    # identically in the inspector.
    rows = re.findall(r"- target: \{fileID: (\d+),\s+guid: (\w+),\s+type: 3\}\s*\n\s+propertyPath: ([^\n]+)\n"
                      r"\s+value: ([^\n]*)\n\s+objectReference: \{fileID: (\d+)", inst)
    mux = [(a, b) for c, a, b in base_docs if c == 114 and ("PositionAtRest" in b or "RotationAtRest" in b)
           and "AimVector" not in b and "totalLength: 3" in b
           and re.search(r"source2:\n      SourceTransform: \{fileID: [1-9]", b)]
    assert_(len(mux) == 2, f"the base carries the two three-slot mux constraints on Prop/Source (found {len(mux)})")
    for a, b in mux:
        m = {pp: (val, ref) for fid, g, pp, val, ref in rows if int(fid) == a and g == base_guid}
        ref = int(m.get("Sources.source3.SourceTransform", ("", "0"))[1])
        st = re.search(rf"^--- !u!4 &{ref} stripped\n(.*?)(?=^--- |\Z)", raw, re.M | re.S)
        cso = re.search(r"m_CorrespondingSourceObject: \{fileID: (\d+), guid: (\w+)", st.group(1)) if st else None
        node = resolve(base, int(cso.group(1))) if cso and cso.group(2) == base_guid else None
        slot3 = re.search(r"    source3:\n(.*?)\n    source4:", b, re.S)
        base_offs = [float(x) for x in re.findall(r"Offset: \{x: ([-0-9.e]+), y: ([-0-9.e]+), z: ([-0-9.e]+)\}",
                                                    slot3.group(1)) for x in x] if slot3 else [1.0]
        over = [pp for pp in m if pp.startswith("Sources.source3.Parent")]
        assert_(node == ("object-sync/y/ObjectSync.prefab", "Rig/Prop/Display")
                and m.get("Sources.totalLength", ("",))[0] == "4" and not over and not any(base_offs),
                f"mux constraint &{a}: source3 is the nested sync rig's Rig/Prop/Display, totalLength 4, zero offset "
                f"(got {node}, totalLength {m.get('Sources.totalLength', ('?',))[0]}, offset overrides {over})")
    return ok


def main():
    entry, cfg = sync_build()
    if "--check" in sys.argv:
        sys.exit(0 if check(entry, cfg) else 1)
    src = open(UPSTREAM_DOC, encoding="utf-8").read()
    persist = load(PERSIST_GEN, "bridge_persist_generate")
    pcfg = persist_config(entry, cfg, src)
    ptext, pf = persist.document(pcfg)
    text = transform(src, pf["flag"])
    menu = ["", "menu:", "  - toggle: GrabSync", f"    param: {EN}",
            "  - button: GrabSync Place", f"    param: {PLACE}", ""]
    text = text.rstrip("\n") + "\n" + "\n".join(menu)
    with open(GLUE_DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml: {CONTROLLER}, flag {pf['flag']}")
    os.makedirs(os.path.dirname(PERSIST_DOC), exist_ok=True)
    with open(PERSIST_DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(ptext)
    print(f"wrote persist/controller.yaml: {PERSIST_CONTROLLER}, Id {pf['id']}, hold {pf['hold']} s, "
          f"{len(pf['payload'])} payload names under {NAMESPACE}/")
    doc, f = entry.document(cfg)
    os.makedirs(os.path.dirname(SYNC_DOC), exist_ok=True)
    with open(SYNC_DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    facts = f["facts"]
    print(f"wrote object-sync/controller.yaml: {facts['wireBits']} wire bits, globalParams {facts['globalParams']}")


if __name__ == "__main__":
    main()
