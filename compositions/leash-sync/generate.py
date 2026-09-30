#!/usr/bin/env python3
"""leash-sync's two documents: the leash's machine with a late-join branch, and
its own position-only `object-sync` build.

    python compositions/leash-sync/generate.py           # writes both documents
    python compositions/leash-sync/generate.py --check   # asserts LeashSync.prefab, writes nothing

Output: `controller.yaml` (the glue, `LeashSync_Fx`) and `object-sync/controller.yaml`
(`ObjectSync_Fx`, one object, rotation `none`), each compiled with `CompileController`
into the `built/` beside it. Both entry generators are imported unmodified; this
file drives them at their shipped CONFIG and deviates after (CONVENTIONS.md
§compositions/).

WHAT IS SYNCED
--------------
The leash plants by a per-client FreezeToWorld capture, so a client that did not
witness the plant has no stake. This composition puts the wearer's stake on the
wire and ends every other client's rope at it:

  Sync_Target  object-sync's measured node, parent-constrained to the leash's
               `Stake` (the one source added to its shipped empty constraint).
               On the wearer `Stake` rides the proxy tip until a plant freezes
               it, so the wire carries the tip, then the stake.
  Display      object-sync's reconstruction (`Rig/Prop/Display`), read directly:
               the glue decides local against remote itself, so `Sync` and its
               Follow arbitration are not in the path.
  Stake        gains a second position source, `Display`, at rest weight 0. Every
               clip keys both weights: (1, 0) wherever the entry runs, (0, 1) in
               the remote sync states, where `Stake` is unfrozen and follows the
               reconstruction.
  LeashSync/Planted  one synced bool, set by the wearer ANNOUNCE seconds after
               `Leash/Planted` rises and cleared when it falls. The dwell outlasts
               a plant-to-remote word refresh, so a remote reading it true with
               `OS/Ready` true holds a table that already carries the stake.

THE GLUE (two layers)
---------------------
`Leash`: the entry's layer as its generator emits it, plus five remote states. A
remote engages on `!IsLocal AND LeashSync/Planted AND ObjectSync/Enable AND
OS/Ready` (object-sync's predicate with the flag) from two places:

  Free -> SyncSettle -> SyncPlant -> SyncPlanted   a client that never saw the
            plant (a late joiner): `Stake` onto the reconstruction for SETTLE
            frames with `StakeAim` live, then the entry's plant clip with
            `StakeAim` freezing on its first frame (so it captures a settled
            line) and `Stake` left live on the reconstruction.
  Planted -> SyncShift -> SyncPlanted              a client that saw the plant
            and froze its own capture: `Stake` moves onto the reconstruction and
            `StakeAim` re-captures after SETTLE frames. Two clients only; an
            emulator clone never sees a grab.
  SyncPlanted -> SyncPHeld   a pick-up: the entry's pick-up clip with `Stake` on
            the reconstruction until the moment the entry would unfreeze it,
            then back on the tip. SyncPHeld leaves like PHeld.
  SyncPlanted -> Free        the flag falling with no grab seen here (a missed
            pick-up): the leash goes home in one frame.

`Announce`: wearer-only, driver-only states keyed on `Leash/Planted`; it owns no
binding, so it cannot fight the machine.

Every state keys every binding its layer owns, and the entry's own states keep
their values, so the wearer's machine and its six published parameters are the
entry's.
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
LEASH_GEN = os.path.join(ROOT, "leash", "generate.py")
OS_GEN = os.path.join(ROOT, "object-sync", "generate.py")
GLUE_OUT = os.path.join(HERE, "controller.yaml")
SYNC_OUT = os.path.join(HERE, "object-sync", "controller.yaml")
PREFAB = os.path.join(HERE, "LeashSync.prefab")

CONTROLLER = "LeashSync_Fx"
# The nested object-sync rig's GO name under the prefab root: the emitted sync
# bindings prefix it, and --check reads it back off the prefab.
MOUNT = "ObjectSync"
# This composition's own object-sync namespace: the collision tags and the park derive from it together,
# so another object-sync build at the entry default (grab-sync's) can share the avatar.
RIG_SEED = "leash-sync/g1"
FLAG = "LeashSync/Planted"
# Seconds from Leash/Planted rising to the synced flag rising. Derived with margin:
# a measure cycle already under way at the freeze (33 frames) plus the next whole
# one, plus a full none-mode wire refresh (0.35 s) and a sync tick, is about 1.6 s.
ANNOUNCE = 2.0
# Frames a remote holds Stake on the reconstruction with StakeAim live before
# StakeAim freezes: a FreezeToWorld edge captures one solve late, so it is armed
# from a settled pose (docs/runtime.md §Constraints).
SETTLE = 3

FRZ = "Stake/VRCPositionConstraint.FreezeToWorld"
AFRZ = "Stake/StakeAim/VRCAimConstraint.FreezeToWorld"
W0 = "Stake/VRCPositionConstraint.Sources.source0.Weight"
W1 = "Stake/VRCPositionConstraint.Sources.source1.Weight"


def load(path, name):
    if not os.path.exists(path):
        raise SystemExit(f"REFUSE: {path} is missing; this composition drives that generator unmodified.")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def leash_config(lg):
    return dict(lg.CONFIG, controller=CONTROLLER)


def sync_config(og):
    cfg = dict(og.CONFIG)
    cfg["objects"] = [{"name": "Prop", "rotation": "none"}]
    cfg["mountPath"] = MOUNT
    cfg["rigSeed"] = RIG_SEED
    return cfg


def published(lg, og):
    """The shared component's globalParams: the leash's published list, then object-sync's derived one."""
    return lg.global_params(leash_config(lg)) + og.document(sync_config(og))[1]["facts"]["globalParams"]


# ------------------------------------------------------------ the glue ----
def t(frames):
    return round(frames / 60, 6)


def parse_clips(lines):
    """The leash document's clip table: name -> {"length": str|None, "set": {k: v}, "curves": {k: v}}."""
    clips, cur, sect = {}, None, None
    for ln in lines:
        m = re.match(r"^  (\w+):$", ln)
        if m:
            cur, sect = m.group(1), None
            clips[cur] = {"length": None, "set": {}, "curves": {}}
            continue
        m = re.match(r"^    length: (\S+)$", ln)
        if m:
            clips[cur]["length"] = m.group(1)
            continue
        if ln in ("    set:", "    curves:"):
            sect = ln.strip()[:-1]
            continue
        m = re.match(r'^      "([^"]+)": (.+)$', ln)
        if m and cur and sect:
            clips[cur][sect][m.group(1)] = m.group(2)
            continue
        if ln.strip():
            raise SystemExit(f"REFUSE: unread line in the leash clip table: {ln!r}")
    return clips


def stepped(keys):
    return "{ tangents: stepped, keys: [ " + ", ".join(f"[{a}, {b}]" for a, b in keys) + " ] }"


def curve_keys(cv):
    return [[float(x) for x in k.split(",")] for k in re.findall(r"\[([^\[\]]+)\]", cv.split("keys:")[1])]


def emit_clip(out, name, c):
    out.append(f"  {name}:")
    if c.get("seconds"):
        out.append(f"    seconds: {c['seconds']}")
    if c.get("length"):
        out.append(f"    length: {c['length']}")
    for sect in ("set", "curves"):
        if c.get(sect):
            out.append(f"    {sect}:")
            out.extend(f'      "{k}": {v}' for k, v in c[sect].items())


def glue_clips(entry):
    """The entry's clips with the two Stake source weights keyed at (1, 0), and the five sync clips."""
    for need in ("disabled", "free", "planted", "plant", "pheld"):
        if need not in entry:
            raise SystemExit(f"REFUSE: the leash document has no clip `{need}`; reconcile this generator with it.")
    out = {}
    for name, c in entry.items():
        c = {"length": c["length"], "set": dict(c["set"]), "curves": dict(c["curves"])}
        if c["curves"]:
            L = c["length"]
            c["curves"][W0] = stepped([(0, 1), (L, 1)])
            c["curves"][W1] = stepped([(0, 0), (L, 0)])
        else:
            c["set"][W0], c["set"][W1] = 1, 0
        out[name] = c

    def on_sync(src, frz_aim, seconds=None):
        s = dict(entry[src]["set"])
        s[FRZ], s[AFRZ], s[W0], s[W1] = 0, frz_aim, 0, 1
        return {"seconds": seconds, "set": s}

    out["sync_settle"] = on_sync("free", 0, t(SETTLE))      # home, Stake onto the reconstruction
    out["sync_shift"] = on_sync("planted", 0, t(SETTLE))    # planted, Stake onto the reconstruction
    out["sync_planted"] = on_sync("planted", 1)
    # The entry's plant with Stake live on the reconstruction; StakeAim's freeze curve is the entry's.
    p = entry["plant"]
    cv = dict(p["curves"])
    cv[FRZ] = stepped([(0, 0), (p["length"], 0)])
    cv[W0] = stepped([(0, 0), (p["length"], 0)])
    cv[W1] = stepped([(0, 1), (p["length"], 1)])
    out["sync_plant"] = {"length": p["length"], "curves": cv}
    # The entry's pick-up with Stake on the reconstruction until the frame the entry unfreezes it.
    h = entry["pheld"]
    keys = curve_keys(h["curves"][FRZ])
    off = next((a for a, b in keys if b == 0), None)
    if off is None:
        raise SystemExit("REFUSE: the leash pick-up clip never unfreezes Stake; SyncPHeld has no hand-off frame.")
    cv = dict(h["curves"])
    cv[FRZ] = stepped([(0, 0), (h["length"], 0)])
    cv[W0] = stepped([(0, 0), (off, 1), (h["length"], 1)])
    cv[W1] = stepped([(0, 1), (off, 0), (h["length"], 0)])
    out["sync_pheld"] = {"length": h["length"], "curves": cv}
    return out


def glue_document(lg, og):
    cfg = leash_config(lg)
    text, _ = lg.document(cfg)
    lines = text.rstrip("\n").split("\n")
    p = cfg["prefix"]
    EN, HELD, PL, IG, IP = (f"{p}/Enable", f"{p}/Held", f"{p}/Planted", f"{p}/Chain_IsGrabbed", f"{p}/Chain_IsPosed")

    def at(line):
        idx = [i for i, ln in enumerate(lines) if ln == line]
        if len(idx) != 1:
            raise SystemExit(f"REFUSE: the leash document carries {len(idx)} lines {line!r}, not one; "
                             "reconcile this generator with it.")
        return idx[0]

    i_par, i_lay, i_clips, i_menu = at("parameters:"), at("layers:"), at("clips:"), at("menu:")
    body_start = next(i for i, ln in enumerate(lines) if ln.strip() and not ln.startswith("#"))
    params = [ln for ln in lines[i_par + 1:i_lay] if ln.strip()]
    layer = lines[i_lay + 1:i_clips]
    while layer and not layer[-1].strip():
        layer.pop()
    entry_clips = parse_clips([ln for ln in lines[i_clips + 1:i_menu]])
    menu = lines[i_menu:]

    # The declarations object-sync's build shares through the one component. Enable matches the entry's
    # own declaration in type and flags; its default 1 wins because this controller sits first.
    sync_decl = og.document(sync_config(og))[0]
    for nm in ("ObjectSync/Enable", "OS/Ready"):
        if not re.search(rf"^  {re.escape(nm)}: ", sync_decl, re.M):
            raise SystemExit(f"REFUSE: the object-sync build no longer declares {nm}; the glue reads it.")
    params += [
        f"  {FLAG}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # the one bit this composition adds",
        "  ObjectSync/Enable: { type: float, default: 1, vrc: { type: bool, synced: true, saved: false } }",
        "  OS/Ready: { type: float, default: 0, vrc: { type: bool, synced: false, saved: false } }",
        "  IsLocal: bool   # VRC built-in",
    ]

    engage = f"IsLocal is false, {FLAG} is true, ObjectSync/Enable greater 0.5, OS/Ready greater 0.5"
    # Splice the two engage rungs into the entry's Free and Planted, after their own rungs.
    def rungs_end(state):
        s = layer.index(f"      {state}:")
        e = s + 1
        while e < len(layer) and not re.match(r"^      \w+:$|^    default:|^      #", layer[e]):
            e += 1
        return e
    for state, to in (("Planted", "SyncShift"), ("Free", "SyncSettle")):
        e = rungs_end(state)
        layer.insert(e, f"          - {{ to: {to}, when: [ {engage} ] }}")

    def state(name, clip, held, planted, trans, note=None):
        out = [f"      # {note}"] if note else []
        out += [f"      {name}:", f"        motion: {{ clip: {clip} }}",
                f"        behaviours: [ {{ driver: {{ set: {{ {HELD}: {held}, {PL}: {planted} }} }} }} ]",
                "        transitions:"]
        out += [f"          - {tr}" for tr in trans]
        return out

    off, grab = f"{{ to: Disabled, when: [ {EN} is false ] }}", f"{IG} is true"
    new = []
    new += state("SyncSettle", "sync_settle", 0, 0,
                 [off, f"{{ to: Held, when: [ {grab} ] }}", "{ to: SyncPlant, when: [], exitTime: 1.0 }"],
                 f"A remote with no stake of its own: Stake onto the reconstruction for {SETTLE} frames, StakeAim live.")
    new += state("SyncPlant", "sync_plant", 0, 1,
                 [f"{{ to: SyncPHeld, when: [ {grab} ] }}", "{ to: SyncPlanted, when: [], exitTime: 1.0 }"],
                 "The entry's plant with Stake live on the reconstruction; StakeAim freezes on the first frame.")
    new += state("SyncShift", "sync_shift", 0, 1,
                 [f"{{ to: SyncPHeld, when: [ {grab} ] }}", "{ to: SyncPlanted, when: [], exitTime: 1.0 }"],
                 f"A remote that froze its own capture: Stake onto the reconstruction, StakeAim live for {SETTLE} frames.")
    new += state("SyncPlanted", "sync_planted", 0, 1,
                 [off, f"{{ to: SyncPHeld, when: [ {grab} ] }}", f"{{ to: Free, when: [ {FLAG} is false ] }}"])
    new += state("SyncPHeld", "sync_pheld", 1, 0,
                 [off, f"{{ to: Plant, when: [ {IG} is false, {IP} is true ] }}",
                  f"{{ to: Free, when: [ {IG} is false, {IP} is false ] }}"],
                 "A pick-up from the reconstruction: Stake back on the tip where the entry would unfreeze it.")
    d = layer.index("    default: Load")
    layer[d:d] = new
    li = next(i for i, ln in enumerate(layer) if ln.startswith("      nodes: {"))
    layer[li] = layer[li][:-2] + (", SyncSettle: [270, 180], SyncPlant: [510, 260], SyncShift: [270, 580], "
                                  "SyncPlanted: [510, 500], SyncPHeld: [510, 420] }")

    announce = [
        "  # Wearer-only: the synced flag follows Leash/Planted, rising ANNOUNCE seconds late and falling at once.",
        "  - name: Announce",
        "    states:",
        "      Idle:",
        "        motion: ~",
        f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {FLAG}: 0 }} }} }} ]",
        "        transitions:",
        f"          - {{ to: Arming, when: [ IsLocal is true, {PL} is true ] }}",
        "      Arming:",
        "        motion: ~",
        "        transitions:",
        f"          - {{ to: Idle, when: [ {PL} is false ] }}",
        f"          - {{ to: Raised, when: [], exitTime: {ANNOUNCE} }}",
        "      Raised:",
        "        motion: ~",
        f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {FLAG}: 1 }} }} }} ]",
        "        transitions:",
        f"          - {{ to: Idle, when: [ {PL} is false ] }}",
        "    default: Idle",
        "    layout:",
        "      nodes: { Idle: [30, 180], Arming: [270, 180], Raised: [270, 260] }",
        "      entry: [50, 120]",
        "      any: [50, 40]",
        "      exit: [50, 80]",
    ]

    clips = glue_clips(entry_clips)
    out = [
        f"# {CONTROLLER} — GENERATED by compositions/leash-sync/generate.py; never hand-edit this file.",
        "# The leash entry's controller as leash/generate.py emits it at its shipped CONFIG, then two deviations:",
        f"# every clip keys Stake's two source weights, and a remote branch rides object-sync's reconstruction",
        f"# while {FLAG} and OS/Ready hold. generate.py's docstring is the design record.",
        f"# Announce {ANNOUNCE} s, settle {SETTLE} frames.",
        "",
    ]
    out += lines[body_start:i_par + 1] + params + [""] + ["layers:"] + layer + [""] + announce + ["", "clips:"]
    for name, c in clips.items():
        emit_clip(out, name, c)
    out += [""] + menu
    return "\n".join(out) + "\n"


# ------------------------------------------------------------- --check ----
def meta_guid(path):
    return re.search(r"guid: (\w+)", open(path + ".meta", encoding="utf-8").read()).group(1)


# One property-modification row; Unity may wrap the target mapping, so gaps match any whitespace.
MOD_RE = re.compile(r"- target: \{fileID:\s+(\d+),\s+guid:\s+(\w+),\s+type:\s+3\}\s*\n"
                    r"\s+propertyPath: ([^\n]+)\n\s+value: ([^\n]*)\n\s+objectReference: \{fileID:\s+(\d+)")


def docs_of(path):
    return [(int(m.group(1)), int(m.group(2)), m.group(3)) for m in re.finditer(
        r"^--- !u!(\d+) &(\d+)(?: stripped)?\n(.*?)(?=^--- |\Z)",
        open(path, encoding="utf-8").read(), re.M | re.S)]


class Resolver:
    """Names a (fileID, guid) object by walking stripped documents down the prefab chain to the real one:
    a Transform or component answers with its GameObject's name."""

    def __init__(self, files):
        self.by_guid = {meta_guid(f): docs_of(f) for f in files}

    MASK = (1 << 63) - 1

    def resolve(self, fid, guid):
        """(guid, classId, body) of the real document an id names. A stripped document follows its
        corresponding source; an id no document carries is an object inherited through one of the file's
        prefab instances, whose id Unity derives as (source id XOR instance id), masked to 63 bits."""
        docs = self.by_guid.get(guid)
        if docs is None:
            return None
        d = next(((c, b) for c, a, b in docs if a == fid), None)
        if d is None:
            for c, a, b in docs:
                if c != 1001:
                    continue
                src = re.search(r"m_SourcePrefab: \{fileID: 100100000, guid: (\w+)", b)
                hit = src and self.resolve((fid ^ a) & self.MASK, src.group(1))
                if hit:
                    return hit
            return None
        c, b = d
        m = re.search(r"m_CorrespondingSourceObject: \{fileID: (\d+), guid: (\w+)", b)
        if m and int(m.group(1)) != 0:
            return self.resolve(int(m.group(1)), m.group(2))
        return guid, c, b

    def name(self, fid, guid):
        hit = self.resolve(fid, guid)
        if hit is None:
            return None
        g, c, b = hit
        if c == 1:
            return re.search(r"m_Name: (.*)", b).group(1).strip()
        go = re.search(r"m_GameObject: \{fileID: (\d+)\}", b)
        return self.name(int(go.group(1)), g) if go else None

    def kind(self, fid, guid):
        """A component's kind: the VRCFury feature class, else 'constraint' for anything with Sources."""
        hit = self.resolve(fid, guid)
        if hit is None:
            return None
        b = hit[2]
        k = re.search(r"class: (\w+)", b)
        return k.group(1) if k else ("constraint" if "Sources:" in b else "?")


def check():
    lg, og = load(LEASH_GEN, "leash_generate"), load(OS_GEN, "object_sync_generate")
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    leash_pf = os.path.join(ROOT, "leash", "Leash.prefab")
    y_pf = os.path.join(ROOT, "object-sync", "y", "ObjectSync.prefab")
    os_pf = os.path.join(ROOT, "object-sync", "ObjectSync.prefab")
    R = Resolver([leash_pf, y_pf, os_pf, PREFAB])
    me = meta_guid(PREFAB)
    leash_g, y_g = meta_guid(leash_pf), meta_guid(y_pf)
    raw = open(PREFAB, encoding="utf-8").read()
    docs = docs_of(PREFAB)

    # The one merge door: exactly one FullController authored here, the entry's removed from the variant root.
    A(raw.count("class: FullController") == 1, f"exactly one FullController authored in LeashSync.prefab "
      f"(found {raw.count('class: FullController')}); a second un-unifies every shared name")
    fc = next((b for c, a, b in docs if c == 114 and "class: FullController" in b), "")
    insts = [(a, b) for c, a, b in docs if c == 1001]
    root_inst = next((b for a, b in insts if f"m_SourcePrefab: {{fileID: 100100000, guid: {leash_g}" in b), "")
    sync_inst = next(((a, b) for a, b in insts if f"m_SourcePrefab: {{fileID: 100100000, guid: {y_g}" in b), (None, ""))
    A(root_inst, "LeashSync.prefab is a variant of leash/Leash.prefab")
    A(sync_inst[1], "LeashSync.prefab nests object-sync/y/ObjectSync.prefab")

    def removed(inst):
        rows = re.findall(r"m_RemovedComponents:\n((?:    - \{fileID: .+\n)*)", inst)
        return {(int(f), g) for f, g in re.findall(r"fileID: (\d+), guid: (\w+)", "".join(rows))}

    def removed_gos(inst):
        rows = re.findall(r"m_RemovedGameObjects:\n((?:    - \{fileID: .+\n)*)", inst)
        return {(int(f), g) for f, g in re.findall(r"fileID: (\d+), guid: (\w+)", "".join(rows))}

    def fcs_of(path):
        return [a for c, a, b in docs_of(path) if c == 114 and "class: FullController" in b]

    lfc = fcs_of(leash_pf)
    A(lfc and all((a, leash_g) in removed(root_inst) for a in lfc), "the leash's own FullController is removed "
      "(this composition's component plays its controller instead)")

    # Controller and prms order: the glue first in both, or Enable's default-1 loses the first-wins merge.
    g = lambda rel: meta_guid(os.path.join(HERE, rel))
    for kind, a, b in (("controllers", f"built/{CONTROLLER}.controller", "object-sync/built/ObjectSync_Fx.controller"),
                       ("prms", f"built/{CONTROLLER}_Parameters.asset", "object-sync/built/ObjectSync_Fx_Parameters.asset"),):
        ia, ib = fc.find(g(a)), fc.find(g(b))
        A(ia != -1 and ib != -1 and ia < ib, f"{kind}: {a} before {b} ({ia}, {ib})")
    A(fc.find(g(f"built/{CONTROLLER}_Menu.asset")) != -1, f"menus: built/{CONTROLLER}_Menu.asset (the Leash toggle)")
    gp = re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"") for ln in b.splitlines()] for b in gp]
    want = published(lg, og)
    A(got == [want], f"globalParams == {want} (got {got}): the bridge's six names stay bare, the seal stays the seal")

    # The nested sync rig: named MOUNT, directly under the root, its own merge and menu fronts removed.
    si, sb = sync_inst
    nm = re.search(r"propertyPath: m_Name\s*\n\s*value: (.+)", sb)
    A(nm and nm.group(1).strip() == MOUNT, f"the sync instance is named {MOUNT!r} (the emitted bindings' prefix)")
    par = re.search(r"m_TransformParent: \{fileID: (\d+)\}", sb)
    ptf = R.resolve(int(par.group(1)), me) if par else None
    A(ptf and ptf[0] == leash_g and ptf[1] == 4 and "m_Father: {fileID: 0}" in ptf[2],
      "the sync instance hangs directly under the prefab root, the component's GameObject")
    kinds = {}
    for f, gg in removed(sb):
        kinds.setdefault(R.name(f, gg), []).append(R.kind(f, gg))
    for who, what in ((MOUNT, "FullController"), (MOUNT, "Toggle"), ("Sync_Target", "Toggle")):
        who_r = "ObjectSync" if who == MOUNT else who
        A(what in kinds.get(who_r, []), f"the sync instance removes {who_r}'s {what}")
    A("constraint" in kinds.get("Display", []), "the sync instance removes Display's rotation constraint (no rotation stage)")
    rgo = sorted(str(R.name(f, gg)) for f, gg in removed_gos(sb))
    A(rgo == sorted(["MarkA", "Recon", "RecvAX", "RecvAZ"]), f"the sync instance removes the rotation stage's "
      f"marker, receivers and Recon (got {rgo})")

    # Park and tags: the nested rig re-parked and retagged to RIG_SEED, both together.
    scfg = sync_config(og)
    want_park = tuple(float(v) for v in og.rig_offset(RIG_SEED))
    pm = {pp: val for f, gg, pp, val, ref in MOD_RE.findall(sb)
          if R.name(int(f), gg) == "Prop" and pp.startswith("m_LocalPosition.")}
    got_park = tuple(float(pm.get(f"m_LocalPosition.{a}", "nan")) for a in "xyz")
    A(got_park == want_park, f"Rig/Prop park == rig_offset({RIG_SEED!r}) {want_park} (got {got_park})")
    carriers = og.tag_carriers(scfg, "Prop")
    for tg in og.tag_set(scfg, "Prop"):
        n = sb.count(f"value: {tg}" + chr(10))
        A(n == carriers[tg], f"tag {tg} on exactly its stage's components ({n} of {carriers[tg]})")
    for tg in og.tag_set(og.CONFIG, og.CONFIG["objects"][0]["name"]):
        A(f"value: {tg}" + chr(10) not in raw, f"no component left on the entry-default tag {tg}")

    # The two constraint sources this composition adds, as property modifications.
    def mods(inst):
        return MOD_RE.findall(inst)

    def on(inst, who):
        return {pp: (val, int(ref)) for f, gg, pp, val, ref in mods(inst) if R.name(int(f), gg) == who
                and pp.startswith("Sources.")}

    def local(ref):
        return R.name(ref, me) if ref else None
    st = on(root_inst, "Stake")
    A(st.get("Sources.totalLength", ("",))[0] == "2", f"Stake's constraint carries two sources (got {st.get('Sources.totalLength')})")
    A(local(st.get("Sources.source1.SourceTransform", ("", 0))[1]) == "Display",
      "Stake's source1 is the sync rig's Display (the reconstruction)")
    A(st.get("Sources.source1.Weight", ("0",))[0] in ("0", None), "Stake's source1 rests at weight 0")
    tg = on(sb, "Sync_Target")
    A(tg.get("Sources.totalLength", ("",))[0] == "1", f"Sync_Target's constraint carries one source (got {tg.get('Sources.totalLength')})")
    A(local(tg.get("Sources.source0.SourceTransform", ("", 0))[1]) == "Stake", "Sync_Target's source0 is the leash's Stake")
    A(tg.get("Sources.source0.Weight", ("1",))[0] == "1", "Sync_Target's source0 weight 1")

    # Names the glue reads that object-sync owns must be names the sync build declares.
    glue = re.sub(r"#.*", "", open(GLUE_OUT, encoding="utf-8").read())
    roots = {og.CONFIG["prefix"].split("/")[0], og.CONFIG["internal"].split("/")[0], og.CONFIG["channel"].split("/")[0]}
    reached = sorted({n for n in re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", glue) if n.split("/")[0] in roots})
    declared = set(re.findall(r"^  ([^\s#:]+):", og.document(sync_config(og))[0], re.M))
    A(reached and not [n for n in reached if n not in declared],
      f"every object-sync name the glue reads is declared by its build ({reached})")
    print("OK" if ok else "FAILED")
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    lg, og = load(LEASH_GEN, "leash_generate"), load(OS_GEN, "object_sync_generate")
    with open(GLUE_OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(glue_document(lg, og))
    text, f = og.document(sync_config(og))
    os.makedirs(os.path.dirname(SYNC_OUT), exist_ok=True)
    with open(SYNC_OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    fa = f["facts"]
    print(f"wrote controller.yaml ({CONTROLLER}) and object-sync/controller.yaml: {fa['wireBits']} wire bits, "
          f"{fa['batchCount']} batches, ~{fa['cycleSeconds']:.2f}s refresh; globalParams {published(lg, og)}")


if __name__ == "__main__":
    main()
