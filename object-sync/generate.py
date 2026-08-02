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
+Z at proxy A with WorldUpType ObjectRotationUp against UpAim). Rotation `y` is
one marker read in XZ, converted to an angle by a 2D freeform-directional blend
tree (an exact angle interpolator) before the walk, so the wire carries one
12-bit angle and the receive side is a single Y rotation offset.

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

    # The synced objects. `rotation` is per-object and resolved at generation
    # time — full (6 components, aim-constraint reconstruction), y (one angle),
    # or none. See PRESETS below for the two non-committed generator paths.
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
    # Sectors in the y-mode angle lookup (each tree; the seam is one sector
    # wide, and the second tree's seam sits half a turn away).
    "lutSectors": 32,

    # Frames held between placing the fine anchor and sampling the fine
    # receiver. Measured coherent-readout lag is 2-4 frames; this is the max,
    # held unconditionally (see the README on why it is not adaptive).
    "settleFrames": 4,

    # Parks the contact cluster away from spawn-dense space. Any string; the
    # offset it derives is a rig fact the README's Rig section declares and the
    # prefab implements.
    "rigSeed": "object-sync/g3",

    # Passed to word-channel's build(). `atomic` is not a knob — see the module
    # docstring.
    "wire": {
        "numberSlots": 2,
        "boolSlots": 9,
        "indexLoops": 2,
        "batchSeconds": 0.1,
    },
}

# Generator paths kept honest by fixtures, not committed builds. Apply one by
# replacing CONFIG["objects"] (and, for y_double, the wire block).
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
    for label, lo, hi, span in (("coarse", d["coarseMin"], d["coarseMax"], c["faceSpan"]),
                                ("fine", d["fineMin"], d["fineMax"], c["faceSpan"]),
                                ("rotation", d["rotMin"], d["rotMax"], c["rotSpan"])):
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


def rot_comps(mode):
    if mode == "full":
        return FULL_COMPS
    if mode == "y":
        return ("Y",)
    if mode == "none":
        return ()
    raise SystemExit(f"REFUSE: rotation mode '{mode}' — full | y | none")


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
        for comp in rot_comps(ob["rotation"]):
            g = f"{o}/r{safe(comp)}"
            numbers.append({"name": f"{o}/R{comp}", "kind": "byte", "group": g})
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

    def clip(self, name, bindings):
        if name in self.clips:
            if self.clips[name] != bindings:
                raise SystemExit(
                    f"REFUSE: clip '{name}' declared twice with different "
                    f"content: {self.clips[name]} vs {bindings}")
            return name
        self.clips[name] = dict(bindings)
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
    out.extend(f"{motion_indent}    - {ch}" for ch in children)
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

    layers = list(wc["layers"])
    layers.append(floatify_layer(doc, c, bools))
    layers.append(decode_layer(doc, c, d))
    layers.append(display_layer(doc, c, d))
    if multi:
        layers.append(slice_layer(doc, c))
    for ob in c["objects"]:
        if ob["rotation"] == "y":
            layers.append(angle_layer(doc, c, d, ob))
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
            rot = f"Rig/{o}/Display/VRCRotationConstraint.RotationOffset"
            zero = {f"{rot}.{LOWER[x]}": 0 for x in AXES}
            b = dict(zero, **{f"{rot}.y": -180})
            step = dict(zero, **{f"{rot}.y": num(360 / 2 ** c["rotBits"])})
            kids.append("{ clip: " + doc.clip(f"ry_{safe(o)}_base", b) +
                        f", directWeight: {p}/One }}")
            kids.append("{ clip: " + doc.clip(f"ry_{safe(o)}_step", step) +
                        f", directWeight: {p}/D/{o}/RY }}")
    out = [f"  - name: {p}/Display", "    states:"]
    out.extend(tree_state("Display", "DisplaySum", kids))
    out.append("    default: Display")
    return out


def slice_layer(doc, c):
    """Multi-object time-multiplex: one object's senders and receivers are live
    per slice, so N objects cost one measure rig instead of N.

    A disabled sensing component freezes its parameter at the last written
    value, so every slice clears the other objects' sense params rather than
    trusting them to fall to zero (gimmicks.md off-state hygiene)."""
    p = c["prefix"]
    names = [ob["name"] for ob in c["objects"]]
    for o in names:
        doc.param(f"  {p}/Slice/{o}: {{ type: float, scratch: true }}",
                  f"{p}/Slice/{o}")
    # A slice holds long enough for the slowest walk in it to finish and commit.
    hold = num(round((max_walk_frames(c) + 2) / 60.0, 4))
    out = [f"  - name: {p}/Slice", "    states:"]
    for i, o in enumerate(names):
        sets = {f"{p}/Slice/{x}": (1 if x == o else 0) for x in names}
        for other in c["objects"]:
            x = other["name"]
            if x == o:
                continue
            for a in AXES:
                sets[f"{p}/Sense/{x}/C{a}"] = 0
                sets[f"{p}/Sense/{x}/F{a}"] = 0
            if other["rotation"] == "y":
                sets[f"{p}/Sense/{x}/RX"] = 0
                sets[f"{p}/Sense/{x}/RZ"] = 0
            else:
                for comp in rot_comps(other["rotation"]):
                    sets[f"{p}/Sense/{x}/R{comp}"] = 0
        nxt = names[(i + 1) % len(names)]
        out.extend(state(f"Slice_{o}", driver(sets=sets),
                         [f"{{ to: Slice_{nxt}, when: [], exitTime: {hold} }}"
                          "   # empty state: exitTime is literal seconds"]))
    out.append(f"    default: Slice_{names[0]}")
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
    g = ["IsLocal is true"]
    if multi:
        g.append(f"{c['prefix']}/Slice/{ob['name']} greater 0.5")
    return g


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

    out = [f"  - name: {lay}", "    states:"]
    out.extend(state("Idle", None,
                     [f"{{ to: CoarseStart, when: [ {', '.join(gate(c, ob, multi))} ] }}"]))
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
    for i in range(c["settleFrames"]):
        nxt = f"Settle{i + 1}" if i + 1 < c["settleFrames"] else "FineStart"
        out.extend(state(f"Settle{i}", None,
                         [f"{{ to: {nxt}, when: [ {p}/True is true ] }}"]))
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
    leave = [f"{{ to: CoarseStart, when: [ {', '.join(gate(c, ob, multi))} ] }}",
             "{ to: Idle, when: [ IsLocal is false ] }"]
    if multi:
        leave.append(f"{{ to: Idle, when: [ {p}/Slice/{o} less 0.5 ] }}")
    out.extend(state("Commit", driver(copies=commit), leave))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, ["Idle", "CoarseStart", "CoarseEnd", "FineStart", "Commit"] +
                           [f"Settle{i}" for i in range(c["settleFrames"])]))
    return out


def component_walk(doc, c, d, ob, comp, multi):
    """One 12-bit rotation component (or the y-mode angle), one layer.

    The y-mode entry splits in two: the angle lookup has a garbage sector at its
    wrap, so a second tree carries the same angle with its seam half a turn away
    and the walk enters through whichever start state the marker's own Z reading
    selects. The two differ only in the top bit — the low bits of an angle and
    of that angle plus half a turn are identical."""
    p, o = c["prefix"], ob["name"]
    lay = f"{p}/Enc/{o}/R{comp}"
    st, res = f"{p}/S/{o}/R{comp}", f"{p}/R/{o}/R{comp}"
    doc.param(f"  {st}: {{ type: float, scratch: true }}", st)
    doc.param(f"  {res}: {{ type: float, scratch: true }}", res)
    rbools = [f"{st}/B{j}" for j in range(c["rotBits"] - 8)]
    for nm in rbools:
        doc.param(f"  {nm}: {{ type: bool, scratch: true }}", nm)
    plan = bit_plan(c["rotBits"], st, rbools)
    ymode = ob["rotation"] == "y"
    clear = dict({st: 0}, **{b: 0 for b in rbools})

    out = [f"  - name: {lay}", "    states:"]
    extras = ["Idle", "Commit"]
    if ymode:
        sz = sense_param(doc, c, f"{p}/Sense/{o}/RZ")
        sense_param(doc, c, f"{p}/Sense/{o}/RX")
        out.extend(state("Idle", None, [
            f"{{ to: StartNear, when: [ {', '.join(gate(c, ob, multi))}, "
            f"{sz} greater {num(d['rotMid'])} ] }}",
            f"{{ to: StartFar, when: [ {', '.join(gate(c, ob, multi))} ] }}"]))
        for tag, src in (("StartNear", f"{p}/D/{o}/AngNear"),
                         ("StartFar", f"{p}/D/{o}/AngFar")):
            out.extend(state(tag, driver(sets=clear, copies={res: src}),
                             walk_rungs(res, 0, f"{tag[5:]}0A", f"{tag[5:]}0R")))
        # Near: ordinary top bit. Far: the tree it reads is the same angle
        # rotated half a turn, so the top bit is inverted and the residual keeps
        # its low bits either way.
        out.extend(state("Near0A", driver(adds={res: num(-0.5), st: 128}),
                         walk_rungs(res, 1, "R1A", "R1R")))
        out.extend(state("Near0R", None, walk_rungs(res, 1, "R1A", "R1R")))
        out.extend(state("Far0A", driver(adds={res: num(-0.5)}),
                         walk_rungs(res, 1, "R1A", "R1R")))
        out.extend(state("Far0R", driver(adds={st: 128}),
                         walk_rungs(res, 1, "R1A", "R1R")))
        extras += ["StartNear", "StartFar", "Near0A", "Near0R", "Far0A", "Far0R"]
        rows = [("Near0A", "Near0R"), ("Far0A", "Far0R")]
        rows += emit_walk_from(1, "R", c["rotBits"], res, plan, out, "Commit",
                               f"{p}/True")
    else:
        sr = sense_param(doc, c, f"{p}/Sense/{o}/R{comp}")
        out.extend(state("Idle", None,
                         [f"{{ to: Start, when: [ {', '.join(gate(c, ob, multi))} ] }}"]))
        out.extend(state("Start", driver(
            sets=clear,
            copies={res: f"{{ source: {sr}, sourceMin: {num(d['rotMin'])}, "
                         f"sourceMax: {num(d['rotMax'])}, destMin: 0, destMax: 1 }}"}),
            walk_rungs(res, 0, "R0A", "R0R")))
        extras.append("Start")
        rows = emit_walk("R", c["rotBits"], res, plan, None, out, "Commit",
                         f"{p}/True")
    commit = {f"{o}/R{comp}": st}
    for j in range(c["rotBits"] - 8):
        commit[f"{o}/R{comp}/B{j}"] = f"{st}/B{j}"
    first = "StartNear" if ymode else "Start"
    out.extend(state("Commit", driver(copies=commit),
                     [f"{{ to: Idle, when: [ {p}/True is true ] }}"]))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, extras))
    return out


def emit_walk_from(start, tag, nbits, resid, plan, out, exit_to, true_param):
    rows = []
    for b in range(start, nbits):
        kind, target, place = plan[b]
        acc, rej = f"{tag}{b}A", f"{tag}{b}R"
        adds, sets = {resid: num(-(0.5 ** (b + 1)))}, {}
        if kind == "byte":
            adds[target] = num(place)
        else:
            sets[target] = 1
        nxt = (walk_rungs(resid, b + 1, f"{tag}{b + 1}A", f"{tag}{b + 1}R")
               if b + 1 < nbits
               else [f"{{ to: {exit_to}, when: [ {true_param} is true ] }}"])
        out.extend(state(acc, driver(sets=sets or None, adds=adds), nxt))
        out.extend(state(rej, None, nxt))
        rows.append((acc, rej))
    return rows


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


def angle_layer(doc, c, d, ob):
    """XZ marker reading -> angle, twice, with the two seams half a turn apart.

    A 2D freeform-directional tree over unit-vector children is an exact angle
    interpolator and is magnitude-invariant, so the arm length never enters the
    result — but the sector spanning the value wrap carries garbage, so the
    consumer picks the tree whose seam faces away."""
    p, o = c["prefix"], ob["name"]
    n = c["lutSectors"]
    ux, uz = f"{p}/D/{o}/UX", f"{p}/D/{o}/UZ"
    near, far = f"{p}/D/{o}/AngNear", f"{p}/D/{o}/AngFar"
    for nm in (ux, uz, near, far):
        doc.param(f"  {nm}: {{ type: float, aap: true }}", nm)
    sx = sense_param(doc, c, f"{p}/Sense/{o}/RX")
    sz = sense_param(doc, c, f"{p}/Sense/{o}/RZ")

    kids = []
    for dest, src in ((ux, sx), (uz, sz)):
        kids.append("{ clip: " + doc.clip(f"ctr_{safe(dest)}_span", {dest: 1}) +
                    f", directWeight: {src} }}")
        kids.append("{ clip: " + doc.clip(f"ctr_{safe(dest)}_base",
                                          {dest: num(-d["rotMid"])}) +
                    f", directWeight: {p}/One }}")

    import math
    for label, dest in (("near", near), ("far", far)):
        sub = [f"    - tree: freeformDirectional2d",
               f"      name: Ang{label.capitalize()}",
               f"      param: {ux}", f"      paramY: {uz}",
               f"      directWeight: {p}/One", "      children:"]
        for k in range(n):
            th = -180.0 + k * (360.0 / n)
            v = (th + 180.0) / 360.0 if label == "near" else (th % 360.0) / 360.0
            cname = doc.clip(f"ang_{safe(o)}_{label}_{k:03d}",
                             {dest: num(round(v, 9))})
            sub.append(f"        - {{ clip: {cname}, "
                       f"x: {num(round(math.sin(math.radians(th)), 9))}, "
                       f"y: {num(round(math.cos(math.radians(th)), 9))} }}")
        kids.append(("TREE", sub))

    flat = []
    for k in kids:
        if isinstance(k, tuple):
            flat.append(k[1])
        else:
            flat.append(k)
    out = [f"  - name: {p}/Angle/{o}", "    states:",
           "      Angle:", "        motion:", "          tree: direct",
           "          name: AngleSum", "          children:"]
    for k in flat:
        if isinstance(k, list):
            out.extend("        " + ln for ln in k)
        else:
            out.append(f"            - {k}")
    out.append("    default: Angle")
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
    o(f"#   ~{facts['cycleSeconds']:.2f}s full refresh @60fps. Local measure cycle "
      f"{max_walk_frames(c)} frames (~{max_walk_frames(c) / 60:.2f}s).")
    o(f"# Rig park (deterministic from rigSeed '{c['rigSeed']}'): "
      f"({d['rigOffset'][0]}, {d['rigOffset'][1]}, {d['rigOffset'][2]}) m — the README's Rig section")
    o("#   is the spec the prefab is kept against.")
    o("#")
    o("# Per axis the coarse and fine words share one group, so word-channel pins them into one")
    o("# batch: an adjacent-cell coarse always arrives with its matched fine, and cell-boundary")
    o("# flicker reconstructs the same position with no hysteresis anywhere.")
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
    for name, bindings in f["clips"].items():
        if len(bindings) == 1:
            k, v = next(iter(bindings.items()))
            L.append(f"  {name}: {{ set: {{ {k}: {v} }} }}")
        else:
            L.append(f"  {name}:")
            L.append("    set:")
            for k, v in bindings.items():
                L.append(f"      {k}: {v}")
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

        assert_("ObjectUp" not in text,
                "no bare ObjectUp anywhere (it degenerates to world-up)")
        assert_(text.count("motion: ~") > 0 and "tree: direct" in text,
                "document carries both ladder states and Direct trees")
        assert_(all(f"  - name: {cfg['prefix']}/Enc/{ob['name']}/P{a}" in text
                    for ob in cfg["objects"] for a in AXES),
                "one encode layer per object per axis")

        d = facts["geometry"]
        assert_(d["fineSpan"] >= cfg["cellSize"] + 2 * d["coarseWorldError"],
                "fine field spans the cell plus twice the coarse world error "
                f"({d['coarseWorldError']:.3f} m)")
        assert_(d["faceGuard"] >= cfg["edgeGuard"],
                f"fine field sits {d['faceGuard']:.2f} m off each face edge")
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.2f}s refresh")
    return 0 if ok else 1


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
