#!/usr/bin/env python3
"""grab-sync-persist: grab-sync, plus a placed prop that survives an avatar swap.

    python compositions/grab-sync-persist/generate.py           # writes both documents
    python compositions/grab-sync-persist/generate.py --check   # asserts the prefab, writes nothing

Output, each compiled with `CompileController` into the `built/` beside it:

  controller.yaml             the glue: ../grab-sync/controller.yaml TRANSFORMED, never
                              hand-edited. Every byte of grab-sync's graph and clip table
                              carries over; the persistence delta below is applied on top.
  object-sync/controller.yaml grab-sync's own single-prop sync build (its
                              `grabsync_single_config`, read live) at `wordRoot` NAMESPACE,
                              so the word table is published bare under the namespace.

WHY A TRANSFORM
---------------
The composition exists to show how a gimmick built on `object-sync` is extended to persist,
so the delta has to stay legible as a delta and has to follow grab-sync when grab-sync moves.
Every anchor the transform depends on (a state, a rung, a declaration, a clip row) is
asserted, and a missing one is a REFUSE naming it: an upstream edit fails this generator
loudly instead of emitting a glue that silently lacks a rung. Re-run after any edit to
grab-sync's document or to object-sync's generator.

THE DELTA
---------
1. Namespace. `Detached` moves to `<NAMESPACE>/Detached`, so the bridge carries it with the
   words. Beside it the four reserved names of the wire contract (`Id`, `Announce`, `Boot`,
   `Restore`) and `Enabled`, the enable state mirrored into payload so the bridge stays
   generic. Everything under the namespace comes out bare through the sync build's derived
   `<NAMESPACE>/*` wildcard; everything under it except the reserved four is payload.
2. `Id` ships non-zero: `ID`, minted from the namespace string, so it is stable across
   regenerations. A variant declares its own in a controller it lists first (first-wins
   takes the whole declaration). 0 means off: Timer's rung into the branch needs a non-zero
   Id, and at 0 the next rung takes the same evaluation, so the boot is grab-sync's.
3. The restore branch (`Persist …`), wearer-only, entered from Timer on the first evaluation
   that has `IsLocal`. Quiesce drives `ObjectSync/Enable` off and resets the payload there,
   ahead of `Boot`, because the walks commit the home pose a fraction of a second into the
   load and a committed home pose is what the next swap would otherwise snapshot. A driver
   write made on the first evaluation after load does not reach the client's parameter, so
   nothing the branch depends on rests on a write made in its first state alone: Enable is set
   off in Quiesce, again in Announce, and again in Boot, a clip length later. Nothing else in
   the branch writes Enable, so it then stays off until the prop is placed, which is both the quiesce (no walk can overwrite a
   restored word) and far past the receiver-deaf floor at any frame rate. `Boot` follows
   `Announce` by ANNOUNCE_LEAD, twice the contract's lead: the bridge handles each datagram on
   its own thread and reads `Announce` when `Boot` arrives, so the lead is what orders the two,
   and the client holds the `Announce` row until it opens the avatar's stream, which shortens
   the interval the bridge sees below the glue's own. The lead runs in its own state,
   `Persist Lead`, entered the evaluation after the write: a transition hands the rest of the
   frame's delta to the state it enters, so a lead in the writing state is consumed by the
   load-hitch frame that entered it.
4. Placement. A wearer's own `Sync` rides `Sync_Target`, which rides the mux, so only the
   sync build's reconstruction (`ObjectSync/Rig/Prop/Display`) shows the wearer the restored
   words. The mux gains that node as a fourth slot on both channels (the prefab's), every
   clip holds it at 0, and `persist_place` is `anchored` with the mux moved onto it: the cell
   rides its rest frame live onto the reconstruction and the drag heading stays parked on
   it. It holds there, measurement still off, for one full wire refresh at the sync build's floor
   frame rate (place_len()), because remotes re-engage the moment Enable returns and must read the
   restored table rather than the quiesce's zeroed one. `Persist Resume` then plays `dropped`, which freezes the cell and unparks the heading
   where they settled, so a re-grab picks the prop up there and the resumed walks measure the
   restored pose rather than home. ACQUIRE could not serve: it holds the cell frozen at home.
5. Enable. `Disabled` copies Enable into `Enabled` and `Anchored` writes 1; no state inside
   the branch copies Enable into it (its resets write Enable's default), so the branch's
   own Enable-off is never recorded as disabled. The
   restore sets Enable from the payload: placed means on, otherwise `Persist Home` copies
   `Enabled` back into Enable, which after the reset is Enable's default. The reset value and
   `Enabled`'s declared default are both read off grab-sync's Enable declaration at generation, so
   changing Enable's default is a regeneration, never a first-listed declaration in a variant.
6. `Place`. A local, unsynced control that sets the prop down where it stands without a grab,
   from the menu or over OSC: from `Anchored` it drops the prop, stamping `Detached` as a grab
   would, and consumes itself; `Disabled` clears it too, so a write while the prop is away is
   dropped rather than latched. It is published bare by its own `globalParams` entry and
   fronted by the menu's button.
7. A remote's return. In grab-sync, Enable coming back on always finds `Detached` false, because
   switching off resets it; after a restore it can find it true. A remote in `Disabled` then goes
   to grab-sync's hidden late-join path (`Waiting`, then `Acquire` on `OS/Ready`) instead of
   `Anchored`, so it never shows the prop at home before gliding to the word.

The synced bit count is grab-sync's: `Detached` moves, nothing else synced is added.
"""

import hashlib
import importlib.util
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM = os.path.normpath(os.path.join(HERE, os.pardir, "grab-sync"))
UPSTREAM_DOC = os.path.join(UPSTREAM, "controller.yaml")
UPSTREAM_GEN = os.path.join(UPSTREAM, "generate.py")
GLUE_DOC = os.path.join(HERE, "controller.yaml")
SYNC_DOC = os.path.join(HERE, "object-sync", "controller.yaml")

CONTROLLER = "GrabSyncPersist_Fx"
NAMESPACE = "BridgePersist/GrabSyncPersist"
DETACHED = f"{NAMESPACE}/Detached"
ENABLED = f"{NAMESPACE}/Enabled"
ID, ANNOUNCE, BOOT, RESTORE = (f"{NAMESPACE}/{n}" for n in ("Id", "Announce", "Boot", "Restore"))
PLACE = "GrabSyncPersist/Place"
EN = "ObjectSync/Enable"
MOUNT = "ObjectSync"

# The shipped identity. Stable because it is a function of the namespace alone; kept inside
# 1..255 so the expression-parameter default carries it exactly on every tool that clamps an
# int to a byte.
MINTED_ID = int(hashlib.sha256(NAMESPACE.encode()).hexdigest(), 16) % 255 + 1

# The wire contract's avatar-side waits, as clip lengths (ANNOUNCE_LEAD_SECS, BOOT_WAIT_SECS,
# WRITE_WAIT_SECS). The bridge carries the same numbers, so change none of them here alone.
# ANNOUNCE_LEAD is the glue's Announce-to-Boot dwell: twice the contract's 0.1 s, which is a lead on the
# wire, because the client holds the Announce row until it opens the avatar's stream.
ANNOUNCE_LEAD = 0.2
BOOT_WAIT = 0.5
WRITE_WAIT = 2.0
# How long Persist Place holds Enable off with the prop on the restored words. Two floors, the
# longer wins. The cell's settle: its constraint ring, the drag park and the delayed show.
# [EMPIRICAL: re-measure the placed pose at a low frame rate after any change to the cell or the
# mux] And one full wire refresh at the sync build's floor frame rate (its sliceFloorFps): the
# quiesce's zeroed words went out on the wire, the refresh is counted in the wearer's frames, and
# a remote re-engages the moment Enable returns, so the restored table has to have crossed the wire
# by then or the remote glides in from a torn table. Step 4 is written at the end of the hold, so
# it must stay inside the bridge's ACK_WAIT_SECS; place_len() refuses otherwise.
PLACE_SETTLE = 0.5
ACK_WAIT = 5.0        # the bridge's, per the wire contract; read here only to refuse a hold it would abandon


def place_len(entry, cfg):
    facts = entry.document(cfg)[1]["facts"]
    refresh = facts["cycleSeconds"] * 60 / cfg["sliceFloorFps"]
    hold = max(PLACE_SETTLE, math.ceil(refresh * 10) / 10)
    if hold > ACK_WAIT - 0.5:
        raise SystemExit(f"REFUSE: Persist Place would hold {hold} s (one wire refresh at {cfg['sliceFloorFps']} fps), "
                         f"leaving under 0.5 s of the bridge's {ACK_WAIT} s wait for step 4. Shorten the sync "
                         "build's refresh, or take the change to the wire contract.")
    return hold

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


def word_lines(entry, cfg):
    lines = [ln for ln in entry.document(cfg)[1]["params"] if ln.startswith(f"  {NAMESPACE}/")]
    if not lines:
        raise SystemExit(f"REFUSE: the sync build declares nothing under {NAMESPACE}/ — its wordRoot "
                         "no longer publishes the word table there, and a restore would place nothing.")
    return lines


def payload(words):
    """Every payload name the restore resets, in declaration order: the words, Detached, Enabled."""
    return [ln.split(":", 1)[0].strip() for ln in words] + [DETACHED, ENABLED]


# ------------------------------------------------------------------ the header ---
HEADER = """\
# GrabSyncPersist glue controller — GENERATED by generate.py from ../grab-sync/controller.yaml; never hand-edit it, re-run the generator.
# grab-sync's header owns every design decision this graph carries unchanged; generate.py's docstring owns the persistence delta item by item, and README.md §Design notes what shapes it as a whole.
# State↔clip mapping, beyond grab-sync's: Place→dropped, Persist Lead→persist_announce, Persist Wait→persist_boot_wait, Persist Write→persist_write_wait, Persist Place→persist_place, Persist Resume→dropped, every other Persist state→disabled.
# Glue value-sets gain the mux's fourth slot (source3 on both channels, the sync build's reconstruction): 0 in every grab-sync clip, 1 only in persist_place, which is `anchored` with the mux moved there.
# Detached lives at {detached}: payload, synced, unsaved, default false — grab-sync's bit under the namespace.
# Enabled ({enabled}) mirrors Enable into payload: Disabled copies it, Anchored writes 1, no state in the restore branch copies Enable into it (its resets write the default). Its default equals Enable's.
# Id default {id} is this prefab's identity; a variant declares its own in a controller listed first in both FullController lists. 0 is off.
""".format(detached=DETACHED, enabled=ENABLED, id=MINTED_ID)


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


def emit_persist_states(pl):
    reset = ", ".join(f"{n}: 0" if n != ENABLED else f"{n}: {{default}}" for n in pl)
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
        "      # The restore branch, wearer-only. A driver write made on the first evaluation after load does not reach the client's",
        "      # parameter, so nothing the branch depends on rests on a write made in its first state alone.",
        "      # The rule it holds: every state in it has an exit that no value on the wire can",
        "      # withhold, a timed or unconditional one, so a late, doubled or missing OSC write can delay the boot but never hold it.",
        "      # A driver's write lands on the state's entry, before any exit can fire, so no hop waits on its own driver's value.",
        "      Persist Quiesce:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, set: {{ {EN}: 0, {reset} }} }}",
        "        motion: { clip: disabled }",
        "        transitions:",
        "          - { to: Persist Announce, when: [ ], exitTime: 1.0 }",
        "      Persist Announce:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, copy: {{ {ANNOUNCE}: {ID} }} }}",
        f"          - driver: {{ localOnly: true, set: {{ {EN}: 0 }} }}   # the quiesce again: the first state's write does not reach the client",
        "        motion: { clip: disabled }",
        "        transitions:",
        "          - { to: Persist Lead, when: [ ], exitTime: 1.0 }",
        "      # The lead is its own state, entered the evaluation after the Announce write, so a load-hitch frame's delta",
        "      # credited to the writing state cannot consume it.",
        "      Persist Lead:",
        "        motion: { clip: persist_announce }",
        "        transitions:",
        "          - { to: Persist Boot, when: [ ], exitTime: 1.0 }",
        "      Persist Boot:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, random: {{ {BOOT}: {{ min: 0.001, max: 1 }} }} }}",
        f"          - driver: {{ localOnly: true, set: {{ {EN}: 0 }} }}   # the quiesce once more, a clip length later",
        "        motion: { clip: disabled }",
        "        transitions:",
        "          - { to: Persist Wait, when: [ ], exitTime: 1.0 }",
        "      # Step 1 or nothing: no bridge, or nothing to restore, and the boot goes on as Id 0's does, one wait later.",
        "      Persist Wait:",
        "        motion: { clip: persist_boot_wait }",
        "        transitions:",
        f"          - {{ to: Persist Ack,  when: [ {RESTORE} equals 1 ] }}",
        "          - { to: Persist Home, when: [ ], exitTime: 1.0 }",
        "      Persist Ack:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, set: {{ {RESTORE}: 2, {reset} }} }}   # step 2: payload the snapshot does not name stays at its default",
        "        motion: { clip: persist_write_wait }",
        "        transitions:",
        f"          - {{ to: Persist Write, when: [ {RESTORE} notEqual 1 ] }}   # our 2, or the bridge's 3",
        "          - { to: Persist Abort, when: [ ], exitTime: 1.0 }   # a duplicate 1 overwrote our 2 and the bridge never saw it",
        "      # Step 3 lands a settle after the payload, so the payload reads current here.",
        "      Persist Write:",
        "        motion: { clip: persist_write_wait }",
        "        transitions:",
        f"          - {{ to: Persist Place, when: [ {RESTORE} equals 3, {DETACHED} is true ] }}",
        f"          - {{ to: Persist Home,  when: [ {RESTORE} equals 3 ] }}   # restored at home: Enable from the payload",
        "          - { to: Persist Abort, when: [ ], exitTime: 1.0 }",
        "      # The cell rides the reconstruction of the restored words while measurement is still off.",
        "      Persist Place:",
        "        motion: { clip: persist_place }",
        "        transitions:",
        "          - { to: Persist Resume, when: [ ], exitTime: 1.0 }",
        "      Persist Resume:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, set: {{ {EN}: 1, {RESTORE}: 0 }} }}   # step 4; placed means enabled",
        "        motion: { clip: dropped }",
        "        transitions:",
        "          - { to: Dropped, when: [ ], exitTime: 1.0 }",
        "      Persist Home:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, copy: {{ {EN}: {ENABLED} }} }}   # the restored enable state, or the default",
        f"          - driver: {{ localOnly: true, set: {{ {RESTORE}: 0 }} }}",
        "        motion: { clip: disabled }",
        "        transitions:",
        "          - { to: Disabled, when: [ ], exitTime: 1.0 }   # unconditional: a late bridge write cannot hold the branch here",
        "      Persist Abort:",
        "        behaviours:",
        f"          - driver: {{ localOnly: true, set: {{ {RESTORE}: 0, {reset} }} }}   # no step 3 in time: defaults, then boot",
        "        motion: { clip: disabled }",
        "        transitions:",
        "          - { to: Persist Home, when: [ ], exitTime: 1.0 }",
    ]


LAYOUT_ADD = {"Place": [260, 460], "Persist Quiesce": [800, 110], "Persist Announce": [800, 170], "Persist Lead": [1040, 170],
              "Persist Boot": [800, 230], "Persist Wait": [800, 290], "Persist Ack": [1040, 290],
              "Persist Write": [1040, 350], "Persist Place": [1040, 410], "Persist Resume": [1040, 470],
              "Persist Home": [800, 410], "Persist Abort": [800, 350]}


def parse_clip_blocks(lines, lo, hi):
    """{clip name: (first, last+1)} for the 2-space clip heads inside lines[lo:hi]."""
    heads = [(i, m.group(1)) for i in range(lo, hi) for m in [re.match(r"^  ([\w]+):", lines[i])] if m]
    dup = sorted({n for _, n in heads if [h for _, h in heads].count(n) > 1})
    if dup:
        refuse(f"grab-sync's clip table declares the clip(s) {dup} more than once; the transform would edit only the last.")
    return {n: (i, heads[k + 1][0] if k + 1 < len(heads) else hi) for k, (i, n) in enumerate(heads)}


def transform(src, words, hold):
    lines = src.split("\n")
    pl = payload(words)

    # --- document head: grab-sync's header comment is replaced by ours.
    schema = index_of(lines, "schema: 1", "document head")
    body = lines[schema:]
    name_at = index_of(body, "controller: GrabSync_Fx", "controller name, below `schema: 1`")
    body[name_at] = f"controller: {CONTROLLER}"

    # --- parameters.
    p0 = index_of(body, "parameters:", "parameters block")
    l0 = index_of(body, "layers:", "layers block")
    det = [i for i in range(p0, l0) if re.match(r"^  Detached:\s", body[i])]
    if len(det) != 1 or not re.search(r"\{ type: bool, default: false, vrc: \{ synced: true, saved: false \} \}", body[det[0]]):
        refuse("grab-sync no longer declares `Detached` as one synced, unsaved bool defaulting false.")
    en = [i for i in range(p0, l0) if re.match(rf"^  {re.escape(EN)}:\s", body[i])]
    m = re.search(r"default: ([\d.]+)", body[en[0]]) if len(en) == 1 else None
    if not m or "synced: true" not in body[en[0]]:
        refuse(f"grab-sync no longer declares `{EN}` once, synced, with a default.")
    en_default = float(m.group(1))
    enabled_default = "true" if en_default >= 0.5 else "false"
    decl = [
        f"  {DETACHED}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # grab-sync's Detached, as payload",
        f"  {ID}: {{ type: int, default: {MINTED_ID}, vrc: {{ synced: false, saved: false }} }}   # this prefab's identity, carried as the default; 0 = off",
        f"  {ANNOUNCE}: {{ type: int, default: 0, vrc: {{ synced: false, saved: false }} }}   # a driver copy of Id, written before Boot",
        f"  {BOOT}: {{ type: float, default: 0, vrc: {{ synced: false, saved: false }} }}   # a driver random in (0, 1], once per load",
        f"  {RESTORE}: {{ type: int, default: 0, vrc: {{ synced: false, saved: false }} }}   # the handshake, written by both sides; rests at 0",
        f"  {ENABLED}: {{ type: bool, default: {enabled_default}, vrc: {{ synced: false, saved: false }} }}   # payload: the enable state; default = Enable's",
        f"  {PLACE}: {{ type: bool, default: false, vrc: {{ synced: false, saved: false }} }}   # the wearer's no-grab drop; published bare",
    ] + words
    body = body[:det[0]] + decl + body[det[0] + 1:]

    # --- the graph: Detached renamed everywhere it is structural.
    l0 = index_of(body, "layers:", "layers block")
    c0 = index_of(body, "clips:", "clips block")
    body = body[:l0] + [rename_detached(l) for l in body[l0:c0]] + body[c0:]
    if any(re.search(r"(?<![\w/])Detached(?![\w/])", l.partition("#")[0]) for l in body[l0:c0]):
        refuse("a bare `Detached` survived the rename.")
    default = index_of(body, "    default: Timer", "Prop layer default", l0, c0)
    states = split_states(body, l0, default)
    for need in ("Timer", "Disabled", "Anchored", "Dropped"):
        if need not in states:
            refuse(f"grab-sync's layer has no `{need}` state.")

    edits = []   # (index, replace_count, new lines), applied bottom-up
    a, b = states["Timer"]
    t = index_of(body, "          - { to: Disabled, when: [ IsLocal is true ] }", "Timer's wearer rung", a, b)
    edits.append((t, 0, [f"          - {{ to: Persist Quiesce, when: [ IsLocal is true, {ID} notEqual 0 ] }}   # the restore branch; at Id 0 the next rung takes the same evaluation"]))
    a, b = states["Disabled"]
    d = index_of(body, f"          - driver: {{ localOnly: true, set: {{ {DETACHED}: 0 }} }}   # off-is-reset: recall home", "Disabled's reset driver", a, b)
    edits.append((d + 1, 0, [f"          - driver: {{ localOnly: true, copy: {{ {ENABLED}: {EN} }} }}   # the enable mirror: this state's Enable, never the branch's",
                             f"          - driver: {{ localOnly: true, set: {{ {PLACE}: 0 }} }}   # a Place written while the prop was away does not fire at the next Anchored"]))
    en_on = index_of(body, f"          - {{ to: Anchored, when: [ {EN} greater 0.5 ] }}", "Disabled's enable rung", a, b)
    edits.append((en_on, 0, [f"          - {{ to: Waiting,  when: [ IsLocal is false, {DETACHED} is true, {EN} greater 0.5 ] }}   # a restore's return: hidden until the word, never shown at home"]))
    a, b = states["Anchored"]
    mo = index_of(body, "        motion: { clip: anchored }", "Anchored's motion", a, b)
    if any(body[i] == "        behaviours:" for i in range(a, b)):
        refuse("Anchored gained behaviours upstream; the enable mirror's insertion assumes it has none.")
    edits.append((mo + 1, 0, ["        behaviours:",
                              f"          - driver: {{ localOnly: true, set: {{ {ENABLED}: 1 }} }}   # the enable mirror"]))
    g = index_of(body, "          - { to: Grabbed,  when: [ Grab_IsGrabbed is true ] }", "Anchored's grab rung", a, b)
    edits.append((g + 1, 0, [f"          - {{ to: Place,    when: [ IsLocal is true, {PLACE} is true ] }}"]))
    edits.append((default, 0, emit_persist_states(pl)))
    lay = [i for i in range(default, c0) if body[i].startswith("      nodes: {") and body[i].endswith("}")]
    if len(lay) != 1:
        refuse("the Prop layer's layout nodes line moved.")
    extra = ", ".join(f"{k}: [{x}, {y}]" for k, (x, y) in LAYOUT_ADD.items())
    edits.append((lay[0], 1, [body[lay[0]][:-1].rstrip() + ", " + extra + " }"]))
    for i, n, new in sorted(edits, key=lambda e: e[0], reverse=True):
        body[i:i + n] = new
    body = [l.replace("{default}", "1" if en_default >= 0.5 else "0") for l in body]

    # --- clips: the fourth mux slot at 0 everywhere, then the persistence clips.
    c0 = index_of(body, "clips:", "clips block")
    begin = [i for i in range(c0, len(body)) if body[i].startswith("  # --- BEGIN GENERATED")]
    end = [i for i in range(c0, len(body)) if body[i] == "  # --- END GENERATED"]
    if len(begin) != 1 or len(end) != 1:
        refuse("grab-sync's clip table is no longer one BEGIN/END marker pair.")
    note = [i for i in range(l0, c0) if body[i].startswith("# Every clip = ")]
    if len(note) != 1:
        refuse("grab-sync's per-clip binding-count note moved.")
    blocks = parse_clip_blocks(body, begin[0] + 1, end[0])
    for need in ("disabled", "anchored", "dropped"):
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

    def rows(name):
        return [l for l in blocks[name][1:] if not l.startswith(("    seconds:", "    #"))]

    def clip(name, src, secs, note):
        return [f"  {name}:" + " " * max(1, 16 - len(name) - 3) + f"# {note}",
                f"    seconds: {secs}"] + rows(src)

    out += clip("persist_announce", "disabled", ANNOUNCE_LEAD,
                "cell `disabled` + HOME hidden, as Disabled; the Announce-to-Boot lead = clip length (the wire contract's)")
    out += clip("persist_boot_wait", "disabled", BOOT_WAIT,
                "cell `disabled` + HOME hidden; the wait for step 1 = clip length (the wire contract's)")
    out += clip("persist_write_wait", "disabled", WRITE_WAIT,
                "cell `disabled` + HOME hidden; the wait for step 3 = clip length (the wire contract's)")
    place = clip("persist_place", "anchored", hold,
                 "cell `anchored` + the mux on its fourth slot, the reconstruction; park on  dwell = generate.py's place_len()")
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
    return HEADER + "\n" + "\n".join(body)


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

    glue_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}.controller"))
    sync_g = meta_guid(os.path.join(HERE, "object-sync", "built", "ObjectSync_Fx.controller"))
    gp_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}_Parameters.asset"))
    sp_g = meta_guid(os.path.join(HERE, "object-sync", "built", "ObjectSync_Fx_Parameters.asset"))
    menu_g = meta_guid(os.path.join(HERE, "built", f"{CONTROLLER}_Menu.asset"))
    ctl = re.findall(r"objRef: \{fileID: 9100000, guid: (\w+)", fc)
    def sect(k):
        m = re.search(r"\n        " + k + r":\n(.*?)\n        [a-zA-Z]+:", fc, re.S)
        return m.group(1) if m else ""
    prm = re.findall(r"objRef: \{fileID: 11400000, guid: (\w+)", sect("prms"))
    mnu = re.findall(r"objRef: \{fileID: 11400000, guid: (\w+)", sect("menus"))
    assert_(ctl == [glue_g, sync_g],
            "controllers are [glue, sync build], glue first — first-wins arms Enable and takes Id")
    assert_(prm == [gp_g, sp_g] and mnu == [menu_g],
            "prms are [glue params, sync params], glue first, and the menu is this entry's own")
    want_gp = entry.document(cfg)[1]["facts"]["globalParams"] + [PLACE]
    blocks = re.findall(r"globalParams:\n((?:        - .+\n)+)", fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"") for ln in b.splitlines()] for b in blocks]
    assert_(got == [want_gp], f"globalParams is the sync build's derived list plus Place {want_gp} (got {got})")

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
    words = word_lines(entry, cfg)
    hold = place_len(entry, cfg)
    text = transform(open(UPSTREAM_DOC, encoding="utf-8").read(), words, hold)
    menu = ["", "menu:", "  - toggle: GrabSync", f"    param: {EN}",
            "  - button: GrabSync Place", f"    param: {PLACE}", ""]
    text = text.rstrip("\n") + "\n" + "\n".join(menu)
    with open(GLUE_DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml: {CONTROLLER}, Id {MINTED_ID}, place hold {hold} s, {len(payload(words))} payload names under {NAMESPACE}/")
    doc, f = entry.document(cfg)
    os.makedirs(os.path.dirname(SYNC_DOC), exist_ok=True)
    with open(SYNC_DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    facts = f["facts"]
    print(f"wrote object-sync/controller.yaml: {facts['wireBits']} wire bits, globalParams {facts['globalParams']}")


if __name__ == "__main__":
    main()
