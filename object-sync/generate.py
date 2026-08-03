#!/usr/bin/env python3
"""object-sync generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ — controller.yaml is
generated output and never hand-edited. `python generate.py --check` runs the
self-test (byte-identical regeneration, the packing table for every preset, and
the structural assertions on the emitted document).

WHAT THIS BUILDS
----------------
Late-synced absolute world position (+ rotation) for a droppable prop, measured
with contacts only, carried over `../word-channel` as transport. Nothing here is
a physbone and nothing is a Rigidbody.

Per axis the measure is two-stage, both stages reading a face-mode box receiver
(a pure linear unlerp along local -Z from the +Z face plane — `runtime.md`
§Contacts):

  coarse — a VRCPositionConstraint squeezes the source object toward the rig
           anchor (anchor weight 1-g, object weight g, g = coarseHalfSpan/range),
           mapping +/-range into +/-coarseHalfSpan metres of a 6 m face. An
           IsLocal SAR walk quantizes the reading into `coarseBits`, which name a
           cell of `cellSize` metres.
  fine   — the walk's accumulated cell index k places a local anchor at that
           cell's centre; a sender constrained to the source object is read at
           1:1 by face receivers riding that anchor, and a second SAR walk
           quantizes the offset into `fineBits`.

The fine stage is bias-cancelling: anchor, receiver and sender ride one
hierarchy, so the avatar's own float32 displacement cancels bit-exactly
(measured — see the README). The coarse stage is not: at range 8192 m with the
avatar kilometres from the world origin its world-space error runs past a metre,
which is why the fine field is REDUNDANT — it spans the cell plus twice that
error, not one cell, so a cell chosen one boundary out is still reconstructed
exactly. That redundancy is what buys 13+12 bits per axis rather than 13+11.

Rotation `full` needs no trig: a rotation-only holder carries two markers
on orthogonal arms, each marker's three components measured by the same face
readout and sent raw; every client rebuilds the orientation with a
VRCAimConstraint pair (`UpAim` aiming +Y at proxy B, `Recon` as its CHILD aiming
+Z at proxy A with WorldUpType ObjectRotationUp against UpAim). Rotation `y` is a
strict subset of that: marker A's X and Z components on the wire, and one
`Recon` aim constraint with WorldUpType Vector (0,1,0) — no second marker, no
UpAim, and no angle anywhere. An angle wire format is not merely more expensive,
it is impossible: a parameter driver reads 0 from an AAP (measured), so no walk
can ever quantize a number a blend tree computed.

WIRE DISCIPLINE
---------------
Each axis's coarse and fine words share one `group:`, so word-channel pins them
into one batch and `atomic: batch` applies them together: an adjacent-cell coarse
with its matched fine reconstructs the same position, so cell-boundary flicker
needs no hysteresis. Each rotation component's byte and bools likewise share a
cross-kind group. `atomic` is FIXED to "batch" here — a measurement payload wants
per-batch coherence, and the set-atomic discipline's pause residual buys nothing
a grouped measurement needs.

THE PRODUCER IS MULTI-FRAME, THE COMMIT IS NOT
----------------------------------------------
The SAR walks are IsLocal-only and take one frame per bit; that is safe, since a
local client cannot be culled from its own view. What must never be multi-frame
is the handoff to the wire: word-channel's sender copies the word params on its
own clock, so a walk writing them bit by bit would let it latch a torn axis. The
walk therefore fills SCRATCH staging params and one `Commit` state driver-copies
a whole axis (both bytes and all its bools) into the word params in a single
frame.

PROVENANCE
----------
VRLabs Custom-Object-Sync (MIT, (c) VRLabs) is the studied ancestor: the SAR
threshold walk (`CustomObjectSyncCreator.cs:1414-1555`) and the setter tree that
drives a constraint offset from decoded bits (`:591-670`) are its idioms,
re-derived here. Its receive-side multi-frame decode walk is rejected — every
decode here is a blend tree that holds no state across frames. The transport is
`../word-channel`, itself generalized from VRCFury's Parameter Compressor.
"""

import hashlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- CONFIG ----

CONFIG = {
    # Param prefix for everything this entry declares. The channel prefix must
    # sit under it but differ, or word-channel's own internals collide.
    "prefix": "ObjectSync",
    "channel": "ObjectSync/Ch",
    # The wearer-facing control's label in the expression menu.
    "menuLabel": "Object Sync",

    # The synced objects. `rotation` is per-object and resolved at generation
    # time — full (6 components, two markers, aim pair), y (2 components, one
    # marker, one aim against world up), or none. See PRESETS below for the two
    # non-committed generator paths.
    "objects": [{"name": "Prop", "rotation": "full"}],

    # Position measure. range is the half-extent about the rig anchor, so the
    # working volume is +/-range metres on each axis. coarseBits must span it at
    # cellSize resolution: 2*range/cellSize == 2**coarseBits.
    "range": 8192.0,
    "cellSize": 2.0,
    "coarseBits": 13,
    "fineBits": 12,
    # Worst-case coarse readout error IN CONTACT SPACE, measured. The squeeze
    # amplifies it by range/coarseHalfSpan, and the fine field is widened by
    # twice the amplified figure — which is what makes a cell chosen one
    # boundary out still reconstruct exactly. Retune this, not the guard.
    "coarseNoise": 0.00039,
    # Receiver face (a box contact's `size` is the FULL extent; 6 is the
    # editor-enforced per-shape maximum) and how much of the coarse face the
    # squeeze uses — the slack keeps the readout off the saturation band at the
    # face plane and off the exact-zero floor at the far edge.
    "faceSpan": 6.0,
    "coarseHalfSpan": 2.75,
    # Metres of face that must remain unused at BOTH edges of every readout.
    "edgeGuard": 0.15,
    # Sphere senders read their nearest surface, so every reading carries a
    # constant offset of exactly the sender radius toward the face. Folded into
    # the calibration below, never left for the consumer to discover.
    "senderRadius": 0.05,

    # Rotation measure. The markers ride rigid arms, so the working volume is
    # exactly +/-armLength and only the face guard has to be paid for.
    "rotBits": 12,
    "armLength": 1.0,
    "rotSpan": 2.5,

    # Frames held between placing the fine anchor and sampling the fine
    # receiver. Measured coherent-readout lag is 2-4 frames; this is the max,
    # held unconditionally (see the README on why it is not adaptive).
    "settleFrames": 4,
    # How long the fine stage waits for its receiver before abandoning back to
    # the coarse stage. Sized well above contact re-acquisition (7 frames
    # measured) because it costs nothing in normal operation: it fires only when
    # the fine sender is outside its box, which nothing but a fresh coarse cell
    # can fix.
    "fineEscapeFrames": 30,

    # Parks the contact cluster away from spawn-dense space. Any string; the
    # offset it derives is a rig fact the README's Rig section declares and the
    # prefab implements.
    "rigSeed": "object-sync/g3",

    # Passed to word-channel's build(). Neither `atomic` nor `indexLoops` is a
    # knob here: the discipline is batch (module docstring), and indexLoops is
    # inert under batch — there is no pause-alias probability to divide and Lost
    # re-acquires at any counter value, so a wider counter would buy nothing and
    # cost an index bit plus three Sync states per batch (word-channel's CONFIG
    # carries the same note at the knob).
    "wire": {
        "numberSlots": 2,
        "boolSlots": 9,
        "indexLoops": 1,
        "batchSeconds": 0.1,
    },
}

# Generator paths kept honest by fixtures, not committed builds. Apply one by
# replacing CONFIG["objects"]; both presets ride CONFIG's wire block unchanged.
PRESETS = {
    "y": {"objects": [{"name": "Prop", "rotation": "y"}]},
    "y_double": {"objects": [{"name": "PropA", "rotation": "y"},
                             {"name": "PropB", "rotation": "y"}]},
}


# ------------------------------------------------------- derived geometry ----

def derive(c):
    """Every number the emitted document uses, derived once and range-checked.

    Refusals here are the entry's own fail-loud edge: a config that would emit a
    silently-saturating readout is rejected by name, never generated."""
    cells = 2 ** c["coarseBits"]
    if abs(2 * c["range"] / c["cellSize"] - cells) > 1e-9:
        raise SystemExit(
            f"REFUSE: coarseBits {c['coarseBits']} spans {cells} cells of "
            f"{c['cellSize']} m = {cells * c['cellSize']} m, but range "
            f"{c['range']} needs {2 * c['range']} m — pick cellSize = "
            f"{2 * c['range'] / cells} or coarseBits = "
            f"{round((2 * c['range'] / c['cellSize'])).bit_length() - 1}")
    for k in ("coarseBits", "fineBits", "rotBits"):
        if not 9 <= c[k] <= 16:
            raise SystemExit(
                f"REFUSE: {k} is {c[k]} — a word is one byte plus its bool "
                "tail, so 9..16 bits is the expressible range")
    guard_raw = c["coarseNoise"] * c["range"] / c["coarseHalfSpan"]
    coarse_guard = round(0.05 * -(-guard_raw // 0.05), 4)
    fine_span = c["cellSize"] + 2 * coarse_guard
    if fine_span > c["faceSpan"] - 2 * c["edgeGuard"]:
        raise SystemExit(
            f"REFUSE: the fine field spans {fine_span} m (cell {c['cellSize']} "
            f"+ 2x coarse guard {coarse_guard}) but only "
            f"{c['faceSpan'] - 2 * c['edgeGuard']} m of the {c['faceSpan']} m "
            "face is usable — the readout would saturate at the face plane and "
            "read exactly 0 past it. Shrink cellSize, or widen faceSpan (6 m is "
            "the per-shape maximum, so shrinking the cell is the move).")
    rot_span_needed = 2 * c["armLength"]
    if rot_span_needed > c["rotSpan"]:
        raise SystemExit(
            f"REFUSE: the rotation markers sweep {rot_span_needed} m but the "
            f"rotation face is {c['rotSpan']} m — shorten armLength or widen "
            "rotSpan")
    r = c["senderRadius"]
    d = {
        "cells": cells,
        "coarseGuard": coarse_guard,
        "coarseWorldError": guard_raw,
        "fineSpan": fine_span,
        "fineLSB": fine_span / 2 ** c["fineBits"],
        "coarseGain": c["coarseHalfSpan"] / c["range"],
        "rotLSB": rot_span_needed / 2 ** c["rotBits"],
        "faceGuard": (c["faceSpan"] - fine_span) / 2,
        "rotGuard": (c["rotSpan"] - rot_span_needed) / 2,
        # Readout calibration: a face receiver reads 0 at the -Z face and 1 at
        # the +Z face plane, and the sphere sender's nearest surface sits one
        # radius nearer the plane. sourceMin/sourceMax below take a reading to
        # the walk's 0..1 residual.
        "coarseMin": 0.5 - c["coarseHalfSpan"] / c["faceSpan"] + r / c["faceSpan"],
        "coarseMax": 0.5 + c["coarseHalfSpan"] / c["faceSpan"] + r / c["faceSpan"],
        "fineMin": 0.5 - fine_span / 2 / c["faceSpan"] + r / c["faceSpan"],
        "fineMax": 0.5 + fine_span / 2 / c["faceSpan"] + r / c["faceSpan"],
        "rotMin": 0.5 - c["armLength"] / c["rotSpan"] + r / c["rotSpan"],
        "rotMax": 0.5 + c["armLength"] / c["rotSpan"] + r / c["rotSpan"],
        # The y-mode branch test: which half-turn the marker is in.
        "rotMid": 0.5 + r / c["rotSpan"],
        # Display base offset, summed FIRST so the running total never exceeds
        # the range (float32 ulp at 8192 m is ~0.98 mm — the precision floor
        # this design is built to, not a defect it introduces).
        "posBase": -c["range"] + c["cellSize"] / 2 - fine_span / 2,
        "rigOffset": rig_offset(c["rigSeed"]),
    }
    # The edge guard's second job. It keeps every legal in-volume reading a
    # clear margin off both face edges, which means a reading of exactly 0 is
    # never something the geometry can produce — it is the signature of a
    # receiver that has not registered with the contact manager yet, or a sender
    # out of range. Half the guaranteed margin is the liveness threshold: below
    # every legal reading, above the only illegal one.
    d["livenessEps"] = round(c["edgeGuard"] / max(c["faceSpan"], c["rotSpan"]) / 2, 6)
    for label, lo, hi, span in (("coarse", d["coarseMin"], d["coarseMax"], c["faceSpan"]),
                                ("fine", d["fineMin"], d["fineMax"], c["faceSpan"]),
                                ("rotation", d["rotMin"], d["rotMax"], c["rotSpan"])):
        if lo <= d["livenessEps"]:
            raise SystemExit(
                f"REFUSE: the {label} readout's lowest legal value {lo:.4f} is "
                f"at or below the liveness threshold {d['livenessEps']} — a live "
                "receiver at the low end of the working volume would be "
                "indistinguishable from one that has not acquired, and every "
                "walk gates on that distinction. Widen edgeGuard's readout "
                "margin, or shrink the working span.")
        near, far = lo * span, (1 - hi) * span
        if min(near, far) < c["edgeGuard"] - 1e-9:
            raise SystemExit(
                f"REFUSE: the {label} readout runs to within "
                f"{min(near, far):.3f} m of a face edge (guard is "
                f"{c['edgeGuard']} m). Past the +Z face plane the parameter "
                "saturates at 1 for ~20 mm and then drops to exactly 0, which "
                "also means 'no overlap' — the working volume has to stay off "
                "both edges.")
    return d


def rig_offset(seed):
    """Deterministic park for the contact cluster. Whole metres, so the rig's
    own coordinates stay float32-exact."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return (((h[0] << 8 | h[1]) % 1024) - 512,
            512 + ((h[2] << 8 | h[3]) % 512),
            ((h[4] << 8 | h[5]) % 1024) - 512)


AXES = ("X", "Y", "Z")
LOWER = {"X": "x", "Y": "y", "Z": "z"}
# Marker A rides local +Z (the aim axis), marker B local +Y (the up axis).
FULL_COMPS = ("A/X", "A/Y", "A/Z", "B/X", "B/Y", "B/Z")


Y_COMPS = ("A/X", "A/Z")


def rot_comps(mode):
    if mode == "full":
        return FULL_COMPS
    if mode == "y":
        return Y_COMPS
    if mode == "none":
        return ()
    raise SystemExit(f"REFUSE: rotation mode '{mode}' — full | y | none")


def rot_groups(c, ob):
    """(group label, [components]) for one object's rotation words.

    `full`'s six components belong to two different markers and are independent
    values, so each takes its own group. `y`'s two components are ONE value — a
    heading — and want the same adjacent-cell coherence a position axis wants,
    so they share a group when the slots can hold it."""
    o, mode = ob["name"], ob["rotation"]
    comps = rot_comps(mode)
    if mode == "y":
        w, rb = c["wire"], c["rotBits"] - 8
        if w["numberSlots"] >= len(comps) and w["boolSlots"] >= len(comps) * rb:
            return [(f"{o}/ry", list(comps))]
        # One group each: the slots cannot hold both components in one batch, so
        # the two halves of a heading may land a batch apart and a fast spin can
        # briefly reconstruct an angle neither snapshot held.
        return [(f"{o}/r{safe(x)}", [x]) for x in comps]
    return [(f"{o}/r{safe(x)}", [x]) for x in comps]


def safe(name):
    """A parameter/binding name flattened into a clip identifier."""
    out = []
    for ch in name:
        out.append(ch.lower() if (ch.isalnum() or ch == "_") else "_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def num(v):
    """Shortest exact-enough decimal. Determinism lives here: every number in
    the document goes through this one formatter."""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    s = repr(round(v, 9))
    return s


# ------------------------------------------------------------ word table ----

def word_table(c):
    """The declared word table, per object, per axis/component.

    Declaration order IS the packing order (word-channel first-fits runs into
    batches), so an axis's two bytes are adjacent and its bools follow in the
    same object order — that is what lets the bool packer reach each number
    group's batch index."""
    cb, fb, rb = c["coarseBits"], c["fineBits"], c["rotBits"]
    numbers, bools, groups = [], [], []
    for ob in c["objects"]:
        o = ob["name"]
        for a in AXES:
            g = f"{o}/p{LOWER[a]}"
            numbers.append({"name": f"{o}/P{a}/C", "kind": "byte", "group": g})
            numbers.append({"name": f"{o}/P{a}/F", "kind": "byte", "group": g})
            for j in range(cb - 8):
                bools.append({"name": f"{o}/P{a}/C{j}", "group": g})
            for j in range(fb - 8):
                bools.append({"name": f"{o}/P{a}/F{j}", "group": g})
            groups.append(g)
        for g, comps in rot_groups(c, ob):
            for comp in comps:
                numbers.append({"name": f"{o}/R{comp}", "kind": "byte", "group": g})
            for comp in comps:
                for j in range(rb - 8):
                    bools.append({"name": f"{o}/R{comp}/B{j}", "group": g})
            groups.append(g)
    return numbers, bools, groups


def check_slots(c, numbers, bools):
    """Pre-flight the wire block against the table's group shapes, so the
    refusal names the knob rather than surfacing as word-channel's packer
    complaining about a group it cannot place."""
    w = c["wire"]
    axis_nums, axis_bools = 2, (c["coarseBits"] - 8) + (c["fineBits"] - 8)
    rot_bools = c["rotBits"] - 8
    if w["numberSlots"] < axis_nums:
        raise SystemExit(
            f"REFUSE: numberSlots {w['numberSlots']} < {axis_nums} — an axis's "
            "coarse and fine bytes must ride one batch or a cell-boundary "
            "flicker splits across snapshots")
    if w["boolSlots"] < axis_bools:
        raise SystemExit(
            f"REFUSE: boolSlots {w['boolSlots']} < {axis_bools} — an axis needs "
            f"{c['coarseBits'] - 8} coarse + {c['fineBits'] - 8} fine bools in "
            "its batch")
    if rot_bools and w["boolSlots"] < w["numberSlots"] * rot_bools:
        raise SystemExit(
            f"REFUSE: boolSlots {w['boolSlots']} < numberSlots "
            f"{w['numberSlots']} x {rot_bools} rotation bools — up to "
            f"{w['numberSlots']} rotation components first-fit into one number "
            "batch, and every one of them needs its bools in that same batch. "
            f"Raise boolSlots to {w['numberSlots'] * rot_bools} or drop "
            "numberSlots.")


# --------------------------------------------------------- emit helpers -----

class Doc:
    """Accumulates params, clips and layers, refusing a duplicate name whose
    content differs — the one class of generator bug a merged document invites."""

    def __init__(self):
        self.params = []
        self._pnames = set()
        self.clips = {}
        self.layers = []

    def param(self, line, name=None):
        if name is not None:
            if name in self._pnames:
                return
            self._pnames.add(name)
        self.params.append(line)

    def has_param(self, name):
        return name in self._pnames

    def clip(self, name, bindings, seconds=None):
        # `seconds` matters wherever a state holding this clip exits on
        # exitTime: a set-clip with no declared length floors at one frame, and
        # exitTime would then read in 1/60 s units instead of seconds.
        entry = (dict(bindings), seconds)
        if name in self.clips:
            if self.clips[name] != entry:
                raise SystemExit(
                    f"REFUSE: clip '{name}' declared twice with different "
                    f"content: {self.clips[name]} vs {entry}")
            return name
        self.clips[name] = entry
        return name


def driver(sets=None, adds=None, copies=None):
    out = ["          - driver:"]
    for label, body in (("set", sets), ("add", adds), ("copy", copies)):
        if not body:
            continue
        out.append(f"              {label}:")
        for k, v in body.items():
            out.append(f"                {k}: {v}")
    return out


def state(name, behaviours=None, transitions=None, motion="~"):
    out = [f"      {name}:", f"        motion: {motion}"]
    if behaviours:
        out.append("        behaviours:")
        out.extend(behaviours)
    if transitions:
        out.append("        transitions:")
        out.extend(f"          - {t}" for t in transitions)
    return out


def tree_state(name, tree_name, children, motion_indent="        "):
    out = [f"      {name}:", f"{motion_indent}motion:",
           f"{motion_indent}  tree: direct",
           f"{motion_indent}  name: {tree_name}",
           f"{motion_indent}  children:"]
    for ch in children:
        if isinstance(ch, list):
            # A nested subtree; its own lines already carry the `- `/`  ` shape.
            out.extend(f"{motion_indent}    {ln}" for ln in ch)
        else:
            out.append(f"{motion_indent}    - {ch}")
    return out


# ------------------------------------------------------------ the walks -----

def bit_plan(nbits, byte_param, bool_params):
    """MSB-first: where each bit of a word lands in staging.

    The byte carries the top 8 bits, the bool tail the rest — which is exactly
    how word-channel splits a >8-bit value across a number slot and bool slots,
    so no re-packing happens between the walk and the wire."""
    plan = []
    for b in range(nbits):
        if b < 8:
            plan.append(("byte", byte_param, 2 ** (7 - b)))
        else:
            plan.append(("bool", bool_params[b - 8], 1))
    return plan


def decode_weights(nbits, nbools):
    """Place value of the byte and of each bool, MSB-first."""
    return 2 ** nbools, [2 ** (nbools - 1 - k) for k in range(nbools)]


EPS = 0.0001  # COS's threshold fuzz: the accept and reject rungs overlap by
              # this fraction of the threshold so a reading landing exactly on
              # it takes the first rung instead of stalling the walk. The
              # mis-decision it admits is bounded by EPS x 2^-1 of full scale,
              # which is under one LSB at every width this generator accepts.


def walk_rungs(resid, b, accept, reject):
    t = 0.5 ** (b + 1)
    return [f"{{ to: {accept}, when: [ {resid} greater {num(t * (1 - EPS))} ] }}",
            f"{{ to: {reject}, when: [ {resid} less {num(t * (1 + EPS))} ] }}"]


def emit_walk(tag, nbits, resid, plan, extra_add, out, exit_to, true_param):
    """The SAR ladder: one state pair per bit, accept above, reject below.

    `extra_add` is an additional param to accumulate the bit's place value into
    (the running cell index the local anchor rides) — None for a stage that has
    no anchor. Returns the list of layout rows."""
    layout = []
    for b in range(nbits):
        kind, target, place = plan[b]
        acc, rej = f"{tag}{b}A", f"{tag}{b}R"
        adds, sets = {}, {}
        adds[resid] = num(-(0.5 ** (b + 1)))
        if kind == "byte":
            adds[target] = num(place)
        else:
            sets[target] = 1
        if extra_add is not None:
            adds[extra_add] = num(2 ** (nbits - 1 - b))
        nxt = (walk_rungs(resid, b + 1, f"{tag}{b + 1}A", f"{tag}{b + 1}R")
               if b + 1 < nbits
               else [f"{{ to: {exit_to}, when: [ {true_param} is true ] }}"])
        out.extend(state(acc, driver(sets=sets or None, adds=adds), nxt))
        out.extend(state(rej, None, nxt))
        layout.append((acc, rej))
    return layout


# ------------------------------------------------------------- the build ----

def build(c):
    d = derive(c)
    p = c["prefix"]
    numbers, bools, groups = word_table(c)
    check_slots(c, numbers, bools)

    wire_config = dict(c["wire"])
    wire_config.update({
        "channel": c["channel"],
        # FIXED, not a knob: the coherence unit a grouped measurement wants is
        # the batch, and set-atomic's pause residual buys nothing here.
        "atomic": "batch",
        "numbers": numbers,
        "bools": bools,
        "assemble": [],
    })
    wc = load_word_channel().build(wire_config)
    facts = wc["facts"]
    for g in groups:
        if g not in facts["groupBatch"]:
            raise SystemExit(f"REFUSE: group '{g}' was not pinned to a batch")

    doc = Doc()
    multi = len(c["objects"]) > 1

    doc.param("  IsLocal: bool              # VRC built-in", "IsLocal")
    doc.param(f"  {p}/True: {{ type: bool, default: true, scratch: true }}   "
              "# constant for +1-frame hops", f"{p}/True")
    doc.param(f"  {p}/One: {{ type: float, default: 1, scratch: true }}      "
              "# Direct-tree carrier weight", f"{p}/One")
    # The wearer-facing enable. Declared FLOAT in the animator so trees can read
    # it, BOOL on the wire so the menu Toggle and the params asset see a bool —
    # one synced bit, and the schema's sanctioned spelling for a toggle a blend
    # tree has to weigh. Unsaved: off is the reset, and the prop never resurrects
    # "on" at avatar load.
    doc.param(f"  {p}/Enable: {{ type: float, default: 0, "
              "vrc: { type: bool, synced: true, saved: false } }", f"{p}/Enable")

    layers = list(wc["layers"])
    layers.append(floatify_layer(doc, c, bools))
    layers.append(decode_layer(doc, c, d))
    layers.append(display_layer(doc, c, d))
    layers.append(follow_layer(doc, c))
    if multi:
        layers.append(slice_layer(doc, c))
    for ob in c["objects"]:
        for a in AXES:
            layers.append(position_walk(doc, c, d, ob, a, multi))
        for comp in rot_comps(ob["rotation"]):
            layers.append(component_walk(doc, c, d, ob, comp, multi))

    return {
        "header": header(c, d, facts, numbers, bools),
        "params": [ln for ln in wc["params"] if ln.strip() != "IsLocal: bool"
                   and not ln.strip().startswith("IsLocal:")] + doc.params,
        "layers": layers,
        "clips": doc.clips,
        "facts": dict(facts, **{
            "geometry": d,
            "groups": groups,
            "numberWords": numbers,
            "boolWords": bools,
            "axisBits": c["coarseBits"] + c["fineBits"],
            "payloadBitsTotal": facts["payloadBits"],
        }),
    }


def load_word_channel():
    path = os.path.normpath(os.path.join(HERE, "..", "word-channel", "generate.py"))
    if not os.path.exists(path):
        raise SystemExit(
            f"REFUSE: word-channel's generator is not at {path} — this entry "
            "composes it as a fragment (its docstring carries the contract) "
            "and cannot emit a document without it")
    spec = importlib.util.spec_from_file_location("word_channel_generate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------- the layers ---

def bool_float(p, name):
    return f"{p}/B/{name}"


def floatify_layer(doc, c, bools):
    """Word bools -> float scratch, every frame.

    A blend tree evaluates only Float parameters — a bool named as a weight
    reads 0 forever — and a parameter driver runs on state ENTER, so the copy
    needs a state the layer re-enters every frame. Two states alternating is
    that; the decode reads the floats one frame behind the words."""
    p = c["prefix"]
    copies = {}
    for b in bools:
        f = bool_float(p, b["name"])
        doc.param(f"  {f}: {{ type: float, scratch: true }}", f)
        copies[f] = b["name"]
    out = [f"  - name: {p}/Floatify", "    states:"]
    for cur, nxt in (("Even", "Odd"), ("Odd", "Even")):
        out.extend(state(cur, driver(copies=copies),
                         [f"{{ to: {nxt}, when: [ {p}/True is true ] }}"]))
    out.append("    default: Even")
    out.extend(["    layout:", "      nodes:",
                "        Even: [30, 180]", "        Odd:  [270, 180]",
                "      entry: [50, 120]", "      any:   [50, 40]",
                "      exit:  [50, 80]"])
    return out


def assemble_children(doc, c, dest, byte_word, bool_words, nbits):
    """One value reassembled from its byte word and bool tail: the generalized
    form of word-channel's hi*256+lo idiom. Every addend is an integer times an
    integral weight below 2^24, so the sum is exact."""
    p = c["prefix"]
    nb = nbits - 8
    bw, bws = decode_weights(nbits, nb)
    kids = []
    base = safe(dest)
    kids.append("{ clip: " + doc.clip(f"asm_{base}_{bw}", {dest: bw}) +
                f", directWeight: {byte_word} }}")
    for k, w in enumerate(bws):
        kids.append("{ clip: " + doc.clip(f"asm_{base}_{w}", {dest: w}) +
                    f", directWeight: {bool_float(p, bool_words[k])} }}")
    return kids


def decode_layer(doc, c, d):
    """Side-agnostic: every client (the wearer included) reads the same word
    params and assembles the same AAPs. No state is carried across frames, so a
    culling pause costs staleness and never a corrupt decode."""
    p = c["prefix"]
    kids = []
    for ob in c["objects"]:
        o = ob["name"]
        for a in AXES:
            for stage, bits in (("C", c["coarseBits"]), ("F", c["fineBits"])):
                dest = f"{p}/D/{o}/P{a}/{stage}"
                doc.param(f"  {dest}: {{ type: float, aap: true }}", dest)
                kids += assemble_children(
                    doc, c, dest, f"{o}/P{a}/{stage}",
                    [f"{o}/P{a}/{stage}{j}" for j in range(bits - 8)], bits)
        for comp in rot_comps(ob["rotation"]):
            dest = f"{p}/D/{o}/R{comp}"
            doc.param(f"  {dest}: {{ type: float, aap: true }}", dest)
            kids += assemble_children(
                doc, c, dest, f"{o}/R{comp}",
                [f"{o}/R{comp}/B{j}" for j in range(c["rotBits"] - 8)],
                c["rotBits"])
    out = [f"  - name: {p}/Decode", "    states:"]
    out.extend(tree_state("Decode", "DecodeSum", kids))
    out.append("    default: Decode")
    return out


def display_layer(doc, c, d):
    """Decoded AAPs -> the display rig's constraint offsets and proxy
    positions. The base clip is the FIRST child of each axis's run so the
    running sum never leaves the working range: float32's ulp at 8192 m is
    ~0.98 mm and this design's precision floor sits there already."""
    p = c["prefix"]
    kids = []
    for ob in c["objects"]:
        o = ob["name"]
        # The MEASURE anchor rides the walk's running cell index (staged, local,
        # mid-cycle); the DISPLAY anchor rides the committed word. They are the
        # same arithmetic on two different sources, and they cannot be one node:
        # committing coarse early enough to share it would let the wire latch an
        # axis whose fine half is still a cycle old.
        anch = f"Rig/{o}/Fine/Anchor/VRCPositionConstraint.PositionOffset"
        abase = {f"{anch}.{LOWER[a]}": num(-c["range"] + c["cellSize"] / 2)
                 for a in AXES}
        kids.append("{ clip: " + doc.clip(f"anch_{safe(o)}_base", abase) +
                    f", directWeight: {p}/One }}")
        for a in AXES:
            z = {f"{anch}.{LOWER[x]}": 0 for x in AXES}
            cell = dict(z, **{f"{anch}.{LOWER[a]}": num(c["cellSize"])})
            kids.append("{ clip: " + doc.clip(f"anch_{safe(o)}_{LOWER[a]}_cell", cell) +
                        f", directWeight: {p}/K/{o}/P{a} }}")

        disp = f"Rig/{o}/Display/VRCPositionConstraint.PositionOffset"
        base = {f"{disp}.{LOWER[a]}": num(d["posBase"]) for a in AXES}
        kids.append("{ clip: " + doc.clip(f"disp_{safe(o)}_base", base) +
                    f", directWeight: {p}/One }}")
        for a in AXES:
            zero = {f"{disp}.{LOWER[x]}": 0 for x in AXES}
            cell = dict(zero, **{f"{disp}.{LOWER[a]}": num(c["cellSize"])})
            lsb = dict(zero, **{f"{disp}.{LOWER[a]}": num(d["fineLSB"])})
            kids.append("{ clip: " + doc.clip(f"disp_{safe(o)}_{LOWER[a]}_cell", cell) +
                        f", directWeight: {p}/D/{o}/P{a}/C }}")
            kids.append("{ clip: " + doc.clip(f"disp_{safe(o)}_{LOWER[a]}_lsb", lsb) +
                        f", directWeight: {p}/D/{o}/P{a}/F }}")
        if ob["rotation"] == "full":
            for mk in ("A", "B"):
                node = f"Rig/{o}/Recon/Proxy{mk}/Transform.m_LocalPosition"
                b = {f"{node}.{LOWER[x]}": num(-c["armLength"]) for x in AXES}
                kids.append("{ clip: " + doc.clip(f"prox_{safe(o)}_{mk.lower()}_base", b) +
                            f", directWeight: {p}/One }}")
                for a in AXES:
                    z = {f"{node}.{LOWER[x]}": 0 for x in AXES}
                    step = dict(z, **{f"{node}.{LOWER[a]}": num(d["rotLSB"])})
                    kids.append(
                        "{ clip: " + doc.clip(
                            f"prox_{safe(o)}_{mk.lower()}_{LOWER[a]}", step) +
                        f", directWeight: {p}/D/{o}/R{mk}/{a} }}")
        elif ob["rotation"] == "y":
            # A strict subset of the full-mode reconstruction: one marker, read
            # in XZ, aimed at by a single constraint whose up comes from a world
            # vector rather than a second marker. Marker A's Y offset is
            # identically zero under yaw, so the proxy's Y is pinned there.
            node = f"Rig/{o}/Recon/ProxyA/Transform.m_LocalPosition"
            b = {f"{node}.x": num(-c["armLength"]), f"{node}.y": 0,
                 f"{node}.z": num(-c["armLength"])}
            kids.append("{ clip: " + doc.clip(f"prox_{safe(o)}_yaw_base", b) +
                        f", directWeight: {p}/One }}")
            for a in ("X", "Z"):
                z = {f"{node}.{LOWER[x]}": 0 for x in AXES}
                step = dict(z, **{f"{node}.{LOWER[a]}": num(d["rotLSB"])})
                kids.append("{ clip: " + doc.clip(
                    f"prox_{safe(o)}_yaw_{LOWER[a]}", step) +
                    f", directWeight: {p}/D/{o}/RA/{a} }}")
    sub = enable_subtree(doc, c)
    if sub:
        kids.append(sub)
    out = [f"  - name: {p}/Display", "    states:"]
    out.extend(tree_state("Display", "DisplaySum", kids))
    out.append("    default: Display")
    return out


def enable_subtree(doc, c):
    """The enable's reach into the measure rig, as a 1D tree rather than a layer.

    Only the measure subtrees: whether the wearer's rig is sensing. The
    consumer's Container is not in here — see `follow_layer`, which needs
    IsLocal and so cannot be a tree at all.

    None with several objects, where the Slice layer owns `m_IsActive` outright
    (one property, one writer) and Enable reaches it through that layer's Parked
    clip. The wire is not gated either way: it is the transport, its bits are
    allocated whether or not the prop is out, and a receiver that kept decoding
    through the toggle is what makes re-enabling instant."""
    p = c["prefix"]
    if len(c["objects"]) > 1:
        return None
    park, live = {}, {}
    for sub in ("Coarse", "Fine", "Rot"):
        b = f"Rig/{c['objects'][0]['name']}/{sub}/GameObject.m_IsActive"
        park[b], live[b] = 0, 1
    return ["- tree: 1d",
            "  name: EnableGate",
            f"  param: {p}/Enable",
            f"  directWeight: {p}/One",
            "  children:",
            f"    - {{ clip: {doc.clip('enable_park', park)}, threshold: 0 }}",
            f"    - {{ clip: {doc.clip('enable_live', live)}, threshold: 1 }}"]


def follow_layer(doc, c):
    """Whether the entry's hands are on the consumer's prop at all.

    The driven property is `IsActive`, and that choice is a measurement, not a
    preference. Only two configurations of a VRCParentConstraint are actually
    hands-off — `IsActive` false, and a source list of length ZERO. A constraint
    holding one source at Weight 0 is NOT: measured in play, it drives its
    transform to the captured rest every frame, exactly as GlobalWeight 0 does.
    So the weight cannot be the gate here; `Container` ships its one source
    (the reconstruction) at a fixed Weight 1 and this layer switches the whole
    component. Off, the prop moves under whatever else drives it, which locally
    is the whole point: the wearer's copy is never touched, so a grab has no
    latency and no fight, and only remotes reconstruct.

    A layer rather than a tree because the condition is `!IsLocal AND Enable`
    and IsLocal is a bool built-in: a blend tree reads 0 from it forever."""
    p = c["prefix"]
    release, engage = {}, {}
    for ob in c["objects"]:
        b = f"{container_path(c, ob['name'])}/VRCParentConstraint.IsActive"
        release[b], engage[b] = 0, 1
    out = [f"  - name: {p}/Follow", "    states:"]
    out.extend(state("Release", None, None,
                     motion=f"{{ clip: {doc.clip('follow_release', release)} }}"))
    out.extend(state("Follow", None, None,
                     motion=f"{{ clip: {doc.clip('follow_engage', engage)} }}"))
    out.extend([
        "    any:",
        f"      - {{ to: Follow, when: [ IsLocal is false, {p}/Enable greater 0.5 ], "
        "canTransitionToSelf: false }",
        "      - { to: Release, when: [ IsLocal is true ], canTransitionToSelf: false }",
        f"      - {{ to: Release, when: [ {p}/Enable less 0.5 ], "
        "canTransitionToSelf: false }"])
    out.append("    default: Release")
    out.extend(["    layout:", "      nodes:",
                "        Release: [30, 180]", "        Follow:  [270, 180]",
                "      entry: [50, 120]", "      any:   [50, 40]",
                "      exit:  [50, 80]"])
    return out


def all_sense(c):
    p = c["prefix"]
    out = {}
    for ob in c["objects"]:
        x = ob["name"]
        for a in AXES:
            out[f"{p}/Sense/{x}/C{a}"] = 0
            out[f"{p}/Sense/{x}/F{a}"] = 0
        for comp in rot_comps(ob["rotation"]):
            out[f"{p}/Sense/{x}/R{comp}"] = 0
    return out


def slice_wake_params(c, o):
    """What a slice waits to see live before unblocking its object's walks.

    Coarse and rotation receivers only. The fine receiver rides the anchor,
    which is parked at cell 0 until that object's coarse walk has run, so it
    legitimately reads 0 here — its liveness is checked later, inside the walk,
    where the anchor is already placed."""
    p = c["prefix"]
    ob = next(x for x in c["objects"] if x["name"] == o)
    return ([f"{p}/Sense/{o}/C{a}" for a in AXES] +
            [f"{p}/Sense/{o}/R{comp}" for comp in rot_comps(ob["rotation"])])


def slice_layer(doc, c):
    """Multi-object time-multiplex: one object's measure rig is live per slice,
    so N objects cost one rig instead of N.

    The layer OWNS `m_IsActive` on every object's three measure subtrees — the
    enable's own clips deliberately leave that binding alone here, because two
    layers writing one property is a fight decided by layer order rather than by
    anything either file says. The enable's authority survives as the AnyState
    rung into Parked, whose clip deactivates all of them.

    Each slice runs deactivate -> clear -> wait for live -> walk, in that order
    and by transition structure rather than by hoping the timing works out. The
    clear only sticks because the same frame's gate clip has already deactivated
    the other objects' receivers: a live receiver re-asserts its parameter the
    next frame, which is exactly how a driver-only clear failed (measured: an
    off-slice object's sense params held ~0.5, not 0). The walks are unblocked
    only at `Run`, and only once this object's receivers actually read something
    the geometry could have produced."""
    p, d = c["prefix"], derive(c)
    names = [ob["name"] for ob in c["objects"]]
    for o in names:
        doc.param(f"  {p}/Slice/{o}: {{ type: float, scratch: true }}",
                  f"{p}/Slice/{o}")
    gates = {o: doc.clip(f"slice_gate_{safe(o)}", gate_bindings(c, o), seconds=1)
             for o in names}
    parked_clip = doc.clip("slice_gate_park", gate_bindings(c, None), seconds=1)
    blocked = dict(all_sense(c), **{f"{p}/Slice/{x}": 0 for x in names})
    # The run window holds the slowest walk in the slice plus its Parked climb
    # and its Commit hop; the skip window bounds how long a dead rig may hold
    # the slice before the next object gets its turn.
    hold = num(round((max_walk_frames(c) + c["settleFrames"] + 4) / 60.0, 4))
    skip = num(round((max_walk_frames(c) + c["settleFrames"] + 4) / 60.0, 4))

    out = [f"  - name: {p}/Slice", "    states:"]
    for i, o in enumerate(names):
        motion = f"{{ clip: {gates[o]} }}"
        # Deactivate every other object's rig AND block every walk, in one
        # frame, before anything is cleared.
        nxt_obj = names[(i + 1) % len(names)]
        # Wait for this object's reactivated receivers to come live rather than
        # counting frames at them; the skip rung is there so one dead rig cannot
        # starve the other objects of their slices. Advancing on it is safe —
        # the walks carry the same gate, so a skipped slice measures nothing
        # rather than measuring zeros.
        out.extend(state(
            f"Enter_{o}", driver(sets=blocked),
            [f"{{ to: Run_{o}, when: [ {', '.join(live(d, slice_wake_params(c, o)))} ] }}",
             f"{{ to: Enter_{nxt_obj}, when: [], exitTime: {skip} }}"
             "   # a rig that never wakes must not starve the other slices"],
            motion=motion))
        out.extend(state(
            f"Run_{o}",
            driver(sets={f"{p}/Slice/{x}": (1 if x == o else 0) for x in names}),
            [f"{{ to: Enter_{nxt_obj}, when: [], exitTime: {hold} }}"
             "   # the gate clip declares its length, so exitTime is seconds"],
            motion=motion))
    out.extend(state("Parked", driver(sets=blocked),
                     [f"{{ to: Enter_{names[0]}, when: [ {p}/Enable greater 0.5 ] }}"],
                     motion=f"{{ clip: {parked_clip} }}"))
    out.extend(off_ladder(c))
    out.append("    default: Parked")
    return out


def max_walk_frames(c):
    pos = 2 + c["coarseBits"] + 1 + c["settleFrames"] + 1 + c["fineBits"] + 1
    rot = 2 + c["rotBits"] + 1
    return max(pos, rot)


def sense_param(doc, c, name):
    """Contact receiver outputs stay out of `scratch:` — a human reading the
    merged FX sees what the rig is measuring, and they cost no sync bits."""
    if not doc.has_param(name):
        doc.param(f"  {name}: float            # contact receiver (localOnly)", name)
    return name


def gate(c, ob, multi):
    g = ["IsLocal is true", f"{c['prefix']}/Enable greater 0.5"]
    if multi:
        g.append(f"{c['prefix']}/Slice/{ob['name']} greater 0.5")
    return g


def off_ladder(c, ob=None, multi=False):
    """The AnyState rungs that yank an encode layer out of its walk.

    The state is `Parked`, not `Off`: a bare `Off` in value position infers as
    the boolean false and every `to:` naming it would silently retarget.

    `canTransitionToSelf: false` is what makes each rung a one-shot — it fires
    from whatever state the walk was in, Parked's driver clears once, and nothing
    re-enters. The clear sticks because the same frame's gate clip has already
    deactivated the receiver GOs, and a deactivated sensing component never
    writes again (it only freezes what it last wrote, which is what the clear is
    for).

    The second rung is what keeps a multi-object slice honest: a walk whose
    object just lost the measure rig must ABANDON rather than run on to its
    Commit and publish limbs measured against another object's senders."""
    p = c["prefix"]
    out = ["    any:",
           f"      - {{ to: Parked, when: [ {p}/Enable less 0.5 ], "
           "canTransitionToSelf: false }"]
    if multi:
        out.append(f"      - {{ to: Parked, when: [ {p}/Slice/{ob['name']} "
                   "less 0.5 ], canTransitionToSelf: false }")
    return out


def wake_up(c, ob, multi):
    """The conditions that let a Parked encode layer start climbing again."""
    up = [f"{c['prefix']}/Enable greater 0.5"]
    if multi:
        up.append(f"{c['prefix']}/Slice/{ob['name']} greater 0.5")
    return up


def live(d, params):
    """Liveness conditions for the sense params a walk is about to sample.

    A reactivated receiver reads exactly 0 until it re-registers with the
    contact manager — measured at 7 frames in the emulator, and not a quantity
    this entry controls or can bound for the shipping client. A timed dwell
    against it is a guess; this is not. Sampling early is the one failure this
    design refuses to have, because 0 is a legal-looking reading that quantizes
    to cell 0 and puts the prop at the corner of the range with full confidence.
    Gating instead makes the failure graceful: a rig that never wakes leaves the
    walk waiting, and the wire holds its last committed pose."""
    return [f"{x} greater {num(d['livenessEps'])}" for x in params]


def liveness_audit(c, d):
    """Every state that waits on a receiver reading, and why waiting there is
    survivable. This is the audit the in-venue stall bought.

    A liveness wait is safe only if its condition can be restored WITHOUT the
    machine advancing past the wait. Where that holds, the source is
    self-restoring and the wait is a wait. Where it does not, the wait is a
    deadlock and needs a bounded escape to whatever stage does restore it.

    `--check` reads this table and holds the emitted document to it, including
    the completeness direction: a liveness condition on a rung this table does
    not name fails, so a new gate cannot be added without an audit entry."""
    p = c["prefix"]
    multi = len(c["objects"]) > 1
    rows = []
    for ob in c["objects"]:
        o = ob["name"]
        for a in AXES:
            lay = f"{p}/Enc/{o}/P{a}"
            for st in ("Idle", "Commit"):
                rows.append({
                    "layer": lay, "state": st,
                    "params": [f"{p}/Sense/{o}/C{a}"], "escape": None,
                    "why": "self-restoring: the coarse receiver's box spans the "
                           "whole working volume and the squeeze constraint keeps "
                           "its sender inside, so a 0 means only re-acquisition "
                           "or a prop outside the range — both clear on their own"})
            rows.append({
                "layer": lay, "state": f"Settle{c['settleFrames'] - 1}",
                "params": [f"{p}/Sense/{o}/F{a}"], "escape": "Idle",
                "why": "NOT self-restoring: the fine receiver rides the "
                       "measurement anchor, which only a fresh coarse commit "
                       "moves, so a teleport out of the cell leaves this waiting "
                       "on a stage it cannot reach"})
        for comp in rot_comps(ob["rotation"]):
            rows.append({
                "layer": f"{p}/Enc/{o}/R{comp}", "state": "Idle",
                "params": [f"{p}/Sense/{o}/R{comp}"], "escape": None,
                "why": "self-restoring: the marker rides a rigid arm on a holder "
                       "pinned to the rig and cannot leave its receiver's box, so "
                       "a 0 means re-acquisition and nothing else"})
        if multi:
            rows.append({
                "layer": f"{p}/Slice", "state": f"Enter_{o}",
                "params": slice_wake_params(c, o), "escape": f"Enter_{next_object(c, o)}",
                "why": "self-restoring (coarse and marker sources, as above), and "
                       "bounded anyway by the skip rung that stops one dead rig "
                       "starving the other slices"})
    return rows


def next_object(c, o):
    names = [x["name"] for x in c["objects"]]
    return names[(names.index(o) + 1) % len(names)]


def tag_set(c, o):
    """Contact collision tags for one object's four sender groups.

    Deterministic from the prefix and — when there is more than one object — the
    object name, the same rule `Container` follows and for a sharper reason:
    measured with two objects on one tag set, NEITHER converges, because every
    receiver reads whichever sender is strongest rather than its own."""
    base = c["prefix"].replace("/", "")
    mid = o if len(c["objects"]) > 1 else ""
    return [f"{base}{mid}{s}" for s in ("Coarse", "Fine", "RotA", "RotB")]


def gate_bindings(c, live_object):
    """m_IsActive across every object's three measure subtrees, with one
    object's live. `live_object` None parks them all."""
    b = {}
    for ob in c["objects"]:
        x = ob["name"]
        for sub in ("Coarse", "Fine", "Rot"):
            b[f"Rig/{x}/{sub}/GameObject.m_IsActive"] = 1 if x == live_object else 0
    return b


def container_path(c, o):
    """The consumer's node. One object owns `Container` outright; several take a
    child each, because one constraint follows one reconstruction."""
    return "Container" if len(c["objects"]) == 1 else f"Container/{o}"


def position_walk(doc, c, d, ob, a, multi):
    """One axis, one layer: coarse walk -> anchor -> settle -> fine walk ->
    atomic commit. IsLocal-gated; a remote sits in Idle forever."""
    p, o = c["prefix"], ob["name"]
    lay = f"{p}/Enc/{o}/P{a}"
    sc = sense_param(doc, c, f"{p}/Sense/{o}/C{a}")
    sf = sense_param(doc, c, f"{p}/Sense/{o}/F{a}")
    st = f"{p}/S/{o}/P{a}"
    res = f"{p}/R/{o}/P{a}"
    kacc, kfloat = f"{st}/Kacc", f"{p}/K/{o}/P{a}"
    for nm in (f"{st}/C", f"{st}/F", f"{res}/C", f"{res}/F", kacc, kfloat):
        doc.param(f"  {nm}: {{ type: float, scratch: true }}", nm)
    cbools = [f"{st}/C{j}" for j in range(c["coarseBits"] - 8)]
    fbools = [f"{st}/F{j}" for j in range(c["fineBits"] - 8)]
    for nm in cbools + fbools:
        doc.param(f"  {nm}: {{ type: bool, scratch: true }}", nm)

    # Walk-entry conditions: the gate, plus liveness on the very param the state
    # it leads to is about to sample.
    enter = gate(c, ob, multi) + live(d, [sc])
    out = [f"  - name: {lay}", "    states:"]
    out.extend(state("Idle", None,
                     [f"{{ to: CoarseStart, when: [ {', '.join(enter)} ] }}"]))
    out.extend(state(
        "CoarseStart",
        driver(sets=dict({f"{st}/C": 0, kacc: 0}, **{b: 0 for b in cbools}),
               copies={f"{res}/C": f"{{ source: {sc}, sourceMin: {num(d['coarseMin'])}, "
                                   f"sourceMax: {num(d['coarseMax'])}, destMin: 0, destMax: 1 }}"}),
        walk_rungs(f"{res}/C", 0, "C0A", "C0R")))
    rows = emit_walk("C", c["coarseBits"], f"{res}/C",
                     bit_plan(c["coarseBits"], f"{st}/C", cbools),
                     kacc, out, "CoarseEnd", f"{p}/True")
    out.extend(state("CoarseEnd", driver(copies={kfloat: kacc}),
                     [f"{{ to: Settle0, when: [ {p}/True is true ] }}"]))
    # The fine-anchor settle IS this entry's own quantity — the anchor takes one
    # frame to reach the cell centre and the readout up to four to cohere — so it
    # stays a dwell. Its last hop gates on the fine receiver being live, and
    # carries the one ESCAPE in the machine, because this is the only liveness
    # wait whose condition it cannot itself restore: the fine receiver rides the
    # measurement anchor, and only a fresh coarse commit moves that. Teleport the
    # prop out of the current cell mid-walk and the fine sender leaves its box
    # for good — measured in-venue, 2 of 5 instantaneous teleports stalling the
    # position stage indefinitely while rotation kept tracking. Falling back to
    # Idle rather than straight to CoarseStart keeps the coarse liveness
    # precondition in the path instead of stepping around it.
    escape = num(round(c["fineEscapeFrames"] / 60.0, 4))
    for i in range(c["settleFrames"]):
        last = i + 1 == c["settleFrames"]
        nxt = "FineStart" if last else f"Settle{i + 1}"
        when = live(d, [sf]) if last else [f"{p}/True is true"]
        rungs = [f"{{ to: {nxt}, when: [ {', '.join(when)} ] }}"]
        if last:
            rungs.append(
                f"{{ to: Idle, when: [], exitTime: {escape} }}"
                "   # motionless state: exitTime is literal seconds. The fine "
                "sender left its box; restage the cell.")
        out.extend(state(f"Settle{i}", None, rungs))
    out.extend(state(
        "FineStart",
        driver(sets=dict({f"{st}/F": 0}, **{b: 0 for b in fbools}),
               copies={f"{res}/F": f"{{ source: {sf}, sourceMin: {num(d['fineMin'])}, "
                                   f"sourceMax: {num(d['fineMax'])}, destMin: 0, destMax: 1 }}"}),
        walk_rungs(f"{res}/F", 0, "F0A", "F0R")))
    rows += emit_walk("F", c["fineBits"], f"{res}/F",
                      bit_plan(c["fineBits"], f"{st}/F", fbools),
                      None, out, "Commit", f"{p}/True")
    commit = {f"{o}/P{a}/C": f"{st}/C", f"{o}/P{a}/F": f"{st}/F"}
    for j in range(c["coarseBits"] - 8):
        commit[f"{o}/P{a}/C{j}"] = f"{st}/C{j}"
    for j in range(c["fineBits"] - 8):
        commit[f"{o}/P{a}/F{j}"] = f"{st}/F{j}"
    # The loop back into the walk is a walk entry too: a rig that dies mid-run
    # must not restart against a receiver reading 0.
    leave = [f"{{ to: CoarseStart, when: [ {', '.join(enter)} ] }}",
             "{ to: Idle, when: [ IsLocal is false ] }"]
    if multi:
        leave.append(f"{{ to: Idle, when: [ {p}/Slice/{o} less 0.5 ] }}")
    out.extend(state("Commit", driver(copies=commit), leave))
    park = dict({f"{st}/C": 0, f"{st}/F": 0, f"{res}/C": 0, f"{res}/F": 0,
                 kacc: 0, kfloat: 0, sc: 0, sf: 0},
                **{b: 0 for b in cbools + fbools})
    out.extend(state("Parked", driver(sets=park),
                     [f"{{ to: Idle, when: [ {', '.join(wake_up(c, ob, multi))} ] }}"]))
    out.extend(off_ladder(c, ob, multi))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, ["Idle", "CoarseStart", "CoarseEnd", "FineStart",
                                  "Commit", "Parked"] +
                           [f"Settle{i}" for i in range(c["settleFrames"])]))
    return out


def component_walk(doc, c, d, ob, comp, multi):
    """One marker component, one layer. Both rotation modes use this walk
    unchanged — `y` is `full` with four of the six components dropped."""
    p, o = c["prefix"], ob["name"]
    lay = f"{p}/Enc/{o}/R{comp}"
    st, res = f"{p}/S/{o}/R{comp}", f"{p}/R/{o}/R{comp}"
    doc.param(f"  {st}: {{ type: float, scratch: true }}", st)
    doc.param(f"  {res}: {{ type: float, scratch: true }}", res)
    rbools = [f"{st}/B{j}" for j in range(c["rotBits"] - 8)]
    for nm in rbools:
        doc.param(f"  {nm}: {{ type: bool, scratch: true }}", nm)
    plan = bit_plan(c["rotBits"], st, rbools)
    clear = dict({st: 0}, **{b: 0 for b in rbools})

    out = [f"  - name: {lay}", "    states:"]
    extras = ["Idle", "Commit", "Start", "Parked"]
    sr = sense_param(doc, c, f"{p}/Sense/{o}/R{comp}")
    enter = gate(c, ob, multi) + live(d, [sr])
    out.extend(state("Idle", None,
                     [f"{{ to: Start, when: [ {', '.join(enter)} ] }}"]))
    out.extend(state("Start", driver(
        sets=clear,
        copies={res: f"{{ source: {sr}, sourceMin: {num(d['rotMin'])}, "
                     f"sourceMax: {num(d['rotMax'])}, destMin: 0, destMax: 1 }}"}),
        walk_rungs(res, 0, "R0A", "R0R")))
    rows = emit_walk("R", c["rotBits"], res, plan, None, out, "Commit",
                     f"{p}/True")
    commit = {f"{o}/R{comp}": st}
    for j in range(c["rotBits"] - 8):
        commit[f"{o}/R{comp}/B{j}"] = f"{st}/B{j}"
    out.extend(state("Commit", driver(copies=commit),
                     [f"{{ to: Idle, when: [ {p}/True is true ] }}"]))
    out.extend(state("Parked", driver(sets=dict(clear, **{res: 0, sr: 0})),
                     [f"{{ to: Idle, when: [ {', '.join(wake_up(c, ob, multi))} ] }}"]))
    out.extend(off_ladder(c, ob, multi))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, extras))
    return out


def walk_layout(rows, extras):
    """Two lanes: accepted bits above, rejected below, one column per bit — the
    arrangement that makes a ladder readable in the animator window at all."""
    out = ["    layout:", "      nodes:"]
    for i, name in enumerate(extras):
        out.append(f"        {name}: [{-540 + 240 * (i % 2)}, {180 + 90 * (i // 2)}]")
    for i, (acc, rej) in enumerate(rows):
        x = 30 + 240 * i
        out.append(f"        {acc}: [{x}, 180]")
        out.append(f"        {rej}: [{x}, 300]")
    out.extend(["      entry: [50, 120]", "      any:   [50, 40]",
                "      exit:  [50, 80]"])
    return out


# ------------------------------------------------------------- the header ---

def header(c, d, facts, numbers, bools):
    p = c["prefix"]
    h = []
    o = h.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o("# object-sync: absolute world position (+rotation) for droppable props, measured with")
    o("# contacts only and carried over word-channel. No physbones, no Rigidbody.")
    o("#")
    obj_desc = ", ".join(f"{ob['name']} (rotation {ob['rotation']})" for ob in c["objects"])
    o(f"# Objects: {obj_desc}")
    o(f"# Position: +/-{num(c['range'])} m about the rig anchor, {c['coarseBits']} coarse bits "
      f"({num(c['cellSize'])} m cells) + {c['fineBits']} fine bits")
    o(f"#   over a {num(d['fineSpan'])} m redundant field (cell + 2 x {num(d['coarseGuard'])} m coarse guard,")
    o(f"#   the guard covering the coarse stage's own {num(round(d['coarseWorldError'], 3))} m worst-case world error),")
    o(f"#   fine LSB {num(round(d['fineLSB'] * 1000, 4))} mm, {num(d['faceGuard'])} m of face left on each side of the field.")
    if any(ob["rotation"] != "none" for ob in c["objects"]):
        o(f"# Rotation: {c['rotBits']} bits per component, {num(c['armLength'])} m arms in a "
          f"{num(c['rotSpan'])} m face ({num(d['rotGuard'])} m guard),")
        o(f"#   component LSB {num(round(d['rotLSB'] * 1000, 4))} mm.")
    o(f"# Wire: {facts['wireBits']} synced bits carrying {facts['payloadBits']} payload bits in "
      f"{facts['batchCount']} batches, atomic=batch,")
    o(f"#   ~{facts['cycleSeconds']:.2f}s full refresh @60fps.")
    if len(c["objects"]) == 1:
        o(f"# Local measure cycle: {max_walk_frames(c)} frames (~{max_walk_frames(c) / 60:.2f}s); "
          f"an unpark costs {c['settleFrames']} more, waiting out contact re-acquisition")
        o("#   before the first sample, so the wire holds its last committed pose rather than")
        o("#   publishing a cleared one.")
    else:
        per = max_walk_frames(c) + 2 * c["settleFrames"] + 5
        o(f"# Local measure cycle: {len(c['objects'])} slices x {per} frames = "
          f"~{len(c['objects']) * per / 60:.2f}s — each slice deactivates every other object's")
        o("#   rig, clears, settles, and only then unblocks its walks.")
    o(f"# Rig park (deterministic from rigSeed '{c['rigSeed']}'): "
      f"({d['rigOffset'][0]}, {d['rigOffset'][1]}, {d['rigOffset'][2]}) m — the README's Rig section")
    o("#   is the spec the prefab is kept against.")
    o("#")
    o("# Per axis the coarse and fine words share one group, so word-channel pins them into one")
    o("# batch: an adjacent-cell coarse always arrives with its matched fine, and cell-boundary")
    o("# flicker reconstructs the same position with no hysteresis anywhere.")
    o("#")
    o("# Collision tags the prefab must carry, one set per object (measured: two objects sharing")
    o("# a tag set leaves NEITHER converging, since every receiver reads the strongest sender in")
    o("# range rather than its own):")
    for ob in c["objects"]:
        o(f"#   {ob['name']}: " + ", ".join(tag_set(c, ob["name"])))
    return h


# --------------------------------------------------------------- assembly ---

def document(c):
    f = build(c)
    p = c["prefix"]
    L = []
    L.extend(f["header"])
    L.append("")
    L.append("schema: 1")
    L.append(f"controller: {p.replace('/', '')}_Fx")
    L.append("basis: mount-root          # clip paths bind under the module root — see the README's Rig section")
    L.append("role: fx")
    L.append("")
    L.append("defaults:")
    L.append("  writeDefaults: on")
    L.append("  transition: { duration: 0, exitTime: none, interruption: none }")
    L.append("")
    L.append("parameters:")
    L.extend(f["params"])
    L.append("")
    L.append("layers:")
    for block in f["layers"]:
        L.extend(block)
    L.append("")
    L.append("clips:")
    for name, (bindings, seconds) in f["clips"].items():
        if len(bindings) == 1 and seconds is None:
            k, v = next(iter(bindings.items()))
            L.append(f"  {name}: {{ set: {{ {k}: {v} }} }}")
        else:
            L.append(f"  {name}:")
            if seconds is not None:
                L.append(f"    seconds: {num(seconds)}   "
                         "# declared length: the holding state exits on exitTime, in seconds")
            L.append("    set:")
            for k, v in bindings.items():
                L.append(f"      {k}: {v}")
    L.append("")
    L.append("# One control, so a bare Toggle rather than a menu asset — and the module is")
    L.append("# single-instance per avatar anyway, since its collision tags are fixed strings")
    L.append("# VRCFury's param prefixing does not reach (the README's Rig section).")
    L.append("menu:")
    L.append(f"  - toggle: {c['menuLabel']}")
    L.append(f"    param: {p}/Enable")
    L.append("    value: 1")
    return "\n".join(L) + "\n", f


# ------------------------------------------------------------- self-test ----

def preset_configs():
    out = {"committed": CONFIG}
    for name, over in PRESETS.items():
        cfg = dict(CONFIG)
        cfg.update(over)
        out[name] = cfg
    return out


def check():
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    for label, cfg in preset_configs().items():
        print(f"[{label}]")
        text, f = document(cfg)
        text2, _ = document(cfg)
        assert_(text == text2, "regeneration is byte-identical")
        facts = f["facts"]
        d0 = facts["geometry"]

        # Packing: every declared group's number words AND bool words in one batch.
        nb, bb, gb = facts["numberBatches"], facts["boolBatches"], facts["groupBatch"]
        for g in facts["groups"]:
            i = gb.get(g)
            want_n = [w["name"] for w in facts["numberWords"] if w["group"] == g]
            want_b = [w["name"] for w in facts["boolWords"] if w["group"] == g]
            got_n = [w["name"] for w in (nb[i] if i is not None and i < len(nb) else [])]
            got_b = [w["name"] for w in (bb[i] if i is not None and i < len(bb) else [])]
            assert_(i is not None and all(n in got_n for n in want_n)
                    and all(n in got_b for n in want_b),
                    f"group {g}: {len(want_n)} number + {len(want_b)} bool words "
                    f"co-batched at batch {(i or 0) + 1}")
        assert_("atomic=batch" in text, "atomic is batch in the emitted header")

        # Every axis commits its whole word in one driver.
        for ob in cfg["objects"]:
            for a in AXES:
                names = [f"{ob['name']}/P{a}/C", f"{ob['name']}/P{a}/F"]
                names += [f"{ob['name']}/P{a}/C{j}" for j in range(cfg["coarseBits"] - 8)]
                names += [f"{ob['name']}/P{a}/F{j}" for j in range(cfg["fineBits"] - 8)]
                assert_(one_driver_has(text, names),
                        f"{ob['name']}/P{a}: all {len(names)} words in one commit driver")
            for comp in rot_comps(ob["rotation"]):
                names = [f"{ob['name']}/R{comp}"]
                names += [f"{ob['name']}/R{comp}/B{j}" for j in range(cfg["rotBits"] - 8)]
                assert_(one_driver_has(text, names),
                        f"{ob['name']}/R{comp}: all {len(names)} words in one commit driver")

        # Negative control: the assertion above must be able to fail.
        assert_(not one_driver_has(text, [cfg["objects"][0]["name"] + "/PX/C",
                                          "NoSuchWord/Never"]),
                "commit-driver probe rejects a word that is not there")

        # A driver reads 0 from an AAP — measured, and the defect that forced
        # y-mode's redesign. This is the assertion that would have caught it.
        aaps = aap_params(text)
        bad_src = [(op, dst, src) for op, dst, src in driver_ops(text)
                   if src in aaps]
        bad_dst = [(op, dst, src) for op, dst, src in driver_ops(text)
                   if dst in aaps]
        assert_(bool(aaps), f"{len(aaps)} AAP params declared (probe has teeth)")
        assert_(not bad_src, f"no driver reads an AAP param {bad_src[:2]}")
        assert_(not bad_dst, f"no driver writes an AAP param {bad_dst[:2]}")

        assert_("ObjectUp" not in text,
                "no bare ObjectUp anywhere (it degenerates to world-up)")
        assert_("freeformDirectional" not in text,
                "no freeform-directional tree anywhere (the angle lookup is gone)")
        assert_(text.count("motion: ~") > 0 and "tree: direct" in text,
                "document carries both ladder states and Direct trees")
        assert_(all(f"  - name: {cfg['prefix']}/Enc/{ob['name']}/P{a}" in text
                    for ob in cfg["objects"] for a in AXES),
                "one encode layer per object per axis")

        # Rotation reconstruction: `y` is `full` minus marker B, so its decode
        # drives ProxyA's X and Z and never mentions ProxyB.
        for ob in cfg["objects"]:
            o = ob["name"]
            pa = f"Rig/{o}/Recon/ProxyA/Transform.m_LocalPosition"
            if ob["rotation"] == "y":
                assert_(all(f"{pa}.{ax}" in text for ax in "xyz")
                        and f"Rig/{o}/Recon/ProxyB" not in text,
                        f"{o}: single-marker aim chain — ProxyA driven, no ProxyB")
                assert_(f"directWeight: {cfg['prefix']}/D/{o}/RA/X" in text
                        and f"directWeight: {cfg['prefix']}/D/{o}/RA/Z" in text,
                        f"{o}: ProxyA rides the received X and Z components")
            elif ob["rotation"] == "full":
                assert_(f"Rig/{o}/Recon/ProxyB/Transform.m_LocalPosition" in text,
                        f"{o}: full mode drives both marker proxies")

        # The enable: a lone synced bit, a bare Toggle on it, and a Parked state
        # in every layer that measures — which clears what a deactivated sensing
        # component would otherwise leave frozen at its last live reading.
        pf = cfg["prefix"]
        assert_(f"  {pf}/Enable: {{ type: float, default: 0, "
                "vrc: { type: bool, synced: true, saved: false }" in text,
                "Enable is a float in the animator and a synced unsaved bool on the wire")
        assert_(f"  - toggle: {cfg['menuLabel']}" in text
                and f"    param: {pf}/Enable" in text,
                "menu block carries one Toggle bound to Enable")
        enc = [ln.split("- name: ")[1] for ln in text.splitlines()
               if "  - name: " + pf in ln and ("/Enable" not in ln)]
        measuring = [n for n in enc if "/Enc/" in n or n.endswith("/Slice")]
        assert_(text.count("- { to: Parked, when: [ " + pf + "/Enable less 0.5 ], "
                           "canTransitionToSelf: false }") == len(measuring),
                f"all {len(measuring)} measuring layers park on Enable false")
        assert_("Off:" not in text and "to: Off" not in text,
                "the parked state is not named Off (a bare Off infers as false)")
        for ob in cfg["objects"]:
            o = ob["name"]
            cleared = parked_clears(text, f"{pf}/Enc/{o}/PX")
            want = {f"{pf}/Sense/{o}/CX", f"{pf}/Sense/{o}/FX",
                    f"{pf}/S/{o}/PX/C", f"{pf}/S/{o}/PX/F",
                    f"{pf}/R/{o}/PX/C", f"{pf}/R/{o}/PX/F",
                    f"{pf}/K/{o}/PX", f"{pf}/S/{o}/PX/Kacc"}
            assert_(want <= cleared,
                    f"{o}/PX Parked clears staging, residual, cell index and both "
                    f"sense params ({len(cleared)} params; missing {want - cleared})")

        # Defect B and its single-object twin: a Commit must be reachable ONLY
        # by walking every bit, and the one road out of Parked runs through the
        # re-acquisition dwell. Neither a slice entry nor an unpark may reach a
        # Commit whose staging was cleared and never recomputed.
        for ob in cfg["objects"]:
            o = ob["name"]
            for lay, last in ([(f"{pf}/Enc/{o}/P{a}", f"F{cfg['fineBits'] - 1}")
                               for a in AXES] +
                              [(f"{pf}/Enc/{o}/R{comp}", f"R{cfg['rotBits'] - 1}")
                               for comp in rot_comps(ob["rotation"])]):
                tr = transitions_of(text, lay)
                into = {s for s, tg in tr.items() if "Commit" in tg}
                assert_(into == {last + "A", last + "R"},
                        f"{lay}: Commit reachable only from the final walk pair "
                        f"({sorted(into)})")
                assert_(tr.get("Parked") == ["Idle"],
                        f"{lay}: Parked exits only to Idle ({tr.get('Parked')})")

        # Liveness: every transition that leads a walk into sampling a sense
        # param carries that param's own liveness condition. A reactivated
        # receiver reads exactly 0, 0 quantizes to cell 0, and cell 0 is the
        # corner of the range — so this is the assertion standing between a
        # graceful wait and a confident wrong answer.
        eps = f"greater {num(d0['livenessEps'])}"
        audit = liveness_audit(cfg, d0)
        for row in audit:
            rungs = rung_text(text, row["layer"], row["state"])
            assert_(all(f"{q} {eps}" in rungs for q in row["params"]),
                    f"{row['layer']}/{row['state']}: waits on "
                    f"{len(row['params'])} receiver reading(s)")
            # The audit's whole point: a wait whose condition it cannot restore
            # must have a way out, or an in-venue teleport stalls it forever.
            if row["escape"]:
                assert_(f"to: {row['escape']}, when: [], exitTime:" in rungs,
                        f"{row['layer']}/{row['state']}: bounded escape to "
                        f"{row['escape']} ({row['why'][:40]}...)")
            else:
                assert_("exitTime:" not in rungs,
                        f"{row['layer']}/{row['state']}: no escape needed — "
                        f"{row['why'][:60]}...")
        # Completeness: no liveness condition anywhere the audit does not name.
        named = {(r["layer"], r["state"]) for r in audit}
        assert_(liveness_sites(text, num(d0["livenessEps"])) == named,
                "every liveness wait in the document is an audited one "
                f"({sorted(liveness_sites(text, num(d0['livenessEps'])) - named)})")
        assert_(all(d0["livenessEps"] < d0[k]
                    for k in ("coarseMin", "fineMin", "rotMin")),
                f"liveness threshold {d0['livenessEps']} sits below every legal "
                f"reading (lowest is {min(d0['coarseMin'], d0['fineMin'], d0['rotMin']):.4f})")

        # Defect A: the slice must deactivate a rig, not merely stop reading it.
        if len(cfg["objects"]) > 1:
            tr = transitions_of(text, f"{pf}/Slice")
            for ob in cfg["objects"]:
                o = ob["name"]
                gate = f["clips"][f"slice_gate_{safe(o)}"][0]
                assert_(all(str(gate[f"Rig/{x['name']}/{s}/GameObject.m_IsActive"])
                            == ("1" if x["name"] == o else "0")
                            for x in cfg["objects"]
                            for s in ("Coarse", "Fine", "Rot")),
                        f"slice {o}: its three subtrees live, every other object's dead")
                nxt = cfg["objects"][(cfg["objects"].index(ob) + 1)
                                     % len(cfg["objects"])]["name"]
                assert_(tr.get(f"Enter_{o}") == [f"Run_{o}", f"Enter_{nxt}"],
                        f"slice {o}: entry waits for live, then yields rather than starving")
                entry = rung_text(text, f"{pf}/Slice", f"Enter_{o}")
                assert_(all(f"{q} {eps}" in entry for q in slice_wake_params(cfg, o)),
                        f"slice {o}: unblocks only once all "
                        f"{len(slice_wake_params(cfg, o))} of its coarse and marker "
                        "receivers read live")
            assert_("enable_park" not in f["clips"],
                    "no enable clips at all with several objects — the Slice layer "
                    "owns m_IsActive (one property, one writer)")
            assert_(all("m_IsActive" in k
                        for k in f["clips"]["slice_gate_park"][0]),
                    "the Slice layer's parked clip is what Enable reaches the subtrees through")
            for ob in cfg["objects"]:
                assert_(all(str(v) == "0" for v in
                            f["clips"]["slice_gate_park"][0].values()),
                        "parking the Slice layer deactivates every object's rig")
                break

        # Per-object collision tags: two objects on one tag set is measured-broken.
        tags = [tag_set(cfg, ob["name"]) for ob in cfg["objects"]]
        flat = [t for group in tags for t in group]
        assert_(len(set(flat)) == len(flat),
                f"collision tags are unique across objects and stages ({flat})")

        if len(cfg["objects"]) == 1:
            park = f["clips"]["enable_park"][0]
            live_c = f["clips"]["enable_live"][0]
            assert_(set(park) == set(live_c) and park and
                    all(str(park[k]) != str(live_c[k]) for k in park),
                    f"enable_park / enable_live cover the same {len(park)} bindings "
                    "with opposite values")
            for ob in cfg["objects"]:
                assert_(all(str(park[f"Rig/{ob['name']}/{s}/GameObject.m_IsActive"]) == "0"
                            for s in ("Coarse", "Fine", "Rot")),
                        f"{ob['name']}: parking deactivates all three measure subtrees")
        assert_(not any(k.startswith("Container")
                        for k in f["clips"].get("enable_park", ({},))[0]),
                "the enable's tree reaches the measure rig only — Container is the "
                "Follow layer's alone")

        # The consumer surface: one layer switching Container's whole constraint,
        # and the wearer's side never in the engaged branch. `IsActive` and NOT a
        # source weight — measured, a VRCParentConstraint holding one source at
        # Weight 0 drives its transform to the captured rest every frame, the same
        # park GlobalWeight 0 gives. Only IsActive false (or a zero-length source
        # list) is the hands-off no-op this entry needs.
        release = f["clips"]["follow_release"][0]
        engage = f["clips"]["follow_engage"][0]
        assert_(set(release) == set(engage) and release
                and all(str(release[k]) == "0" and str(engage[k]) == "1"
                        for k in release),
                f"follow_release / follow_engage cover the same {len(release)} "
                "Container binding(s), released 0 / engaged 1")
        for ob in cfg["objects"]:
            con = f"{container_path(cfg, ob['name'])}/VRCParentConstraint"
            assert_(f"{con}.IsActive" in release,
                    f"{ob['name']}: Follow switches Container's IsActive")
            assert_(not any(k.startswith(f"{con}.Sources") for k in release)
                    and not any(k.startswith(f"{con}.Sources") for k in engage)
                    and f"{con}.GlobalWeight" not in text,
                    f"{ob['name']}: neither a source weight nor GlobalWeight is "
                    "animated — both park the prop rather than releasing it")
            assert_(f"{con}.Sources.source1" not in text,
                    f"{ob['name']}: Container carries no second source anywhere "
                    "in the document")
        rungs = any_rungs(text, f"{pf}/Follow")
        engaging = [r for r in rungs if r.startswith("- { to: Follow")]
        assert_(len(engaging) == 1
                and "IsLocal is false" in engaging[0]
                and f"{pf}/Enable greater 0.5" in engaging[0],
                "the one rung into Follow requires !IsLocal AND Enable — so the "
                "wearer's own copy is never driven, at zero decode latency")
        assert_(any(r.startswith("- { to: Release") and "IsLocal is true" in r
                    for r in rungs)
                and any(r.startswith("- { to: Release")
                        and f"{pf}/Enable less 0.5" in r for r in rungs),
                "either IsLocal or Enable-off releases Container on its own")
        assert_(f"    default: Release" in rung_block(text, f"{pf}/Follow"),
                "Follow's default state is Release — hands off until proven remote")
        assert_("Home" not in text,
                "no Home anywhere: no path, no clip, no park pose (stow belongs "
                "to a composed system, not to this entry)")

        d = facts["geometry"]
        assert_(d["fineSpan"] >= cfg["cellSize"] + 2 * d["coarseWorldError"],
                "fine field spans the cell plus twice the coarse world error "
                f"({d['coarseWorldError']:.3f} m)")
        assert_(d["faceGuard"] >= cfg["edgeGuard"],
                f"fine field sits {d['faceGuard']:.2f} m off each face edge")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.2f}s refresh")

    # `globalParams` is a VRCFury field with no CompileController spelling, so
    # the document cannot carry it and the README is where it is specified for
    # the prefab. Assert the line exists rather than letting it drift silently.
    print("[README]")
    readme = os.path.join(HERE, "README.md")
    if os.path.exists(readme):
        body = open(readme, encoding="utf-8").read()
        assert_(f"`globalParams` is exactly `{CONFIG['prefix']}/Enable`" in body,
                "README specifies Enable as the one globalParams entry")
        assert_("exactly one source, `Rig/<obj>/Display`" in body,
                "README pins the single Container source the Follow layer indexes")
        assert_("Home" not in body,
                "README carries no home/park concept either")
    else:
        assert_(False, "README.md is missing")

    # The committed build is the one artifact `built/` was compiled from, so a
    # generator change that moves it is a defect until built/ is regenerated.
    print("[committed vs disk]")
    on_disk = os.path.join(HERE, "controller.yaml")
    if os.path.exists(on_disk):
        with open(on_disk, encoding="utf-8", newline="") as fh:
            assert_(fh.read().replace("\r\n", "\n") == document(CONFIG)[0],
                    "controller.yaml on disk matches the committed CONFIG")
    else:
        assert_(False, "controller.yaml is missing")
    return 0 if ok else 1


def driver_ops(text):
    """Every (op, destination, source) a parameter driver performs, read off the
    emitted document. `driver()` and word-channel's emitter share these indents,
    so one scan covers both."""
    ops, op = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s == "- driver:":
            op = None
        elif ln.startswith("              ") and not ln.startswith("               ") \
                and s.endswith(":"):
            op = s[:-1]
        elif op and ln.startswith("                ") and ":" in s:
            dst, val = s.split(":", 1)
            val = val.strip()
            src = val.split("source:", 1)[1].split(",")[0].strip() \
                if val.startswith("{") and "source:" in val else val
            ops.append((op, dst.strip(), src if op == "copy" else None))
        elif s and not ln.startswith("              "):
            op = None
    return ops


def liveness_sites(text, eps):
    """(layer, state) for every rung that waits on a receiver reading.

    The discriminator is a `/Sense/` param compared against the liveness
    threshold: a walk's own bit rungs compare residuals, never sense params."""
    out, layer, st = set(), None, None
    for ln in text.splitlines():
        if ln.startswith("  - name: "):
            layer, st = ln.split("- name: ", 1)[1].strip(), None
        elif ln.startswith("      ") and not ln.startswith("       ") \
                and ln.rstrip().endswith(":"):
            st = ln.strip()[:-1]
        elif layer and st and "/Sense/" in ln and f"greater {eps}" in ln:
            out.add((layer, st))
    return out


def rung_text(text, layer, state_name):
    """The raw transition lines of one state — the surface the liveness
    assertions read, since a condition list is what they are about."""
    lines = text.splitlines()
    try:
        i = lines.index(f"  - name: {layer}")
    except ValueError:
        return ""
    end = next((j for j in range(i + 1, len(lines))
                if lines[j].startswith("  - name: ")), len(lines))
    body = lines[i:end]
    try:
        s = body.index(f"      {state_name}:")
    except ValueError:
        return ""
    out = []
    for ln in body[s + 1:]:
        if ln.startswith("      ") and not ln.startswith("       "):
            break
        if ln.strip().startswith("- { to: "):
            out.append(ln)
    return "\n".join(out)


def rung_block(text, layer):
    """One layer's whole emitted block, for the assertions whose claim is about
    the machine rather than about any one state."""
    lines = text.splitlines()
    try:
        i = lines.index(f"  - name: {layer}")
    except ValueError:
        return ""
    end = next((j for j in range(i + 1, len(lines))
                if lines[j].startswith("  - name: ")), len(lines))
    return "\n".join(lines[i:end])


def any_rungs(text, layer):
    """One layer's AnyState rungs, raw. The conditions ARE the claim wherever a
    gate is what makes a branch unreachable, so these are read as text rather
    than reduced to destinations the way `transitions_of` does."""
    body = rung_block(text, layer).splitlines()
    try:
        s = body.index("    any:")
    except ValueError:
        return []
    out = []
    for ln in body[s + 1:]:
        if not ln.startswith("      "):
            break
        out.append(ln.strip())
    return out


def transitions_of(text, layer):
    """state name -> its transition targets, in ladder order, for one layer.

    Deliberately structural: what a state can reach is the property the walk's
    integrity rests on, and it is not something a timing argument can stand in
    for."""
    lines = text.splitlines()
    try:
        i = lines.index(f"  - name: {layer}")
    except ValueError:
        return {}
    end = next((j for j in range(i + 1, len(lines))
                if lines[j].startswith("  - name: ")), len(lines))
    out, cur = {}, None
    for ln in lines[i:end]:
        if ln.startswith("    ") and not ln.startswith("     "):
            # A layer-level key (`any:`, `default:`, `layout:`) — its rungs
            # belong to the machine, not to the state that happened to precede it.
            cur = None
        elif ln.startswith("      ") and not ln.startswith("       ") \
                and ln.rstrip().endswith(":"):
            cur = ln.strip()[:-1]
            out[cur] = []
        elif cur and ln.strip().startswith("- { to: "):
            out[cur].append(ln.strip().split("to: ", 1)[1].split(",")[0]
                            .replace("}", "").strip())
    return {k: v for k, v in out.items() if v or k in out}


def parked_clears(text, layer):
    """The params one layer's Parked state sets, read off the emitted text."""
    lines = text.splitlines()
    try:
        i = lines.index(f"  - name: {layer}")
    except ValueError:
        return set()
    end = next((j for j in range(i + 1, len(lines))
                if lines[j].startswith("  - name: ")), len(lines))
    body = lines[i:end]
    try:
        s = body.index("      Parked:")
    except ValueError:
        return set()
    out = set()
    for ln in body[s + 1:]:
        if ln.startswith("      ") and not ln.startswith("       "):
            break
        if ln.startswith("                ") and ":" in ln:
            out.add(ln.strip().split(":", 1)[0])
    return out


def aap_params(text):
    return {ln.split(":", 1)[0].strip() for ln in text.splitlines()
            if "aap: true" in ln and ln.startswith("  ")}


def one_driver_has(text, names):
    """True when some single `copy:` block in the document lists every name."""
    blocks, cur = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s == "copy:":
            cur = []
            blocks.append(cur)
        elif cur is not None:
            if s.endswith(":") or not s or ln.startswith("          -") or ln.startswith("        "):
                if ":" in s and ln.startswith("                "):
                    cur.append(s.split(":", 1)[0].strip())
                else:
                    cur = None
            else:
                cur = None
    return any(all(n in b for n in names) for b in blocks)


def main():
    if "--check" in sys.argv:
        sys.exit(check())
    text, f = document(CONFIG)
    out = os.path.join(HERE, "controller.yaml")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    facts = f["facts"]
    states = text.count("        motion:") + text.count("        motion: ~")
    print(f"wrote {out}: {len(f['layers'])} layers, {len(f['clips'])} clips, "
          f"{facts['wireBits']} wire bits, {facts['payloadBits']} payload bits, "
          f"{facts['batchCount']} batches, ~{facts['cycleSeconds']:.2f}s refresh @60fps")


if __name__ == "__main__":
    main()
