#!/usr/bin/env python3
"""object-sync generator: emits the three committed controller.yaml documents
(root = full, `y/`, `y_double/`) from CONFIG + PRESETS below; DEMOS configs are
check-only (probed and packable on every change, nothing on disk).

Edit CONFIG, rerun (`python generate.py`), recompile each touched built/ — the
three controller.yaml documents committed here are generated output, pinned
byte-for-byte by --check, so hand-editing one desynchronises it from this
generator. That pin covers this repo's builds only: a consumer generating into
their own project owns the emitted document, and deviating there is fine as a
commented transform in their build script, never as a silent edit. `python
generate.py
--check` runs the self-test (byte-identical regeneration, the packing table for
every build, the structural assertions on every emitted document, and the
on-disk pin for all three).

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
(measured — see the README). The coarse stage is not: at range its world-space
error runs to over a quarter-cell, which is why the fine field is REDUNDANT —
it spans the cell plus twice the guarded error, not one cell, so a cell chosen
one boundary out is still reconstructed exactly. That redundancy is what buys
12+12 bits per axis rather than 12+11.

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
    # 4096/12/12 is the ruled uniform geometry (operator, 2026-08-16): every
    # word is byte+4 bools, every position group 2 bytes + 8 bools, at a finer
    # LSB (~0.78 mm) for a +/-4096 m working volume — accepted, not a bit
    # harvest.
    "range": 4096.0,
    "cellSize": 2.0,
    "coarseBits": 12,
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
    # offset it derives is a rig fact the README's Rig section declares. The
    # prefab implements it as the object node's transform localPosition under
    # the origin-pinned Rig, and this generator folds it into the world-frame
    # display/anchor bases — NEVER as a constraint source offset, which the
    # shipping client scales by the avatar's per-client scale factor.
    "rigSeed": "object-sync/g3",

    # Passed to word-channel's build(). Neither `atomic` nor `indexLoops` is a
    # knob here: the discipline is batch (module docstring), and indexLoops is
    # inert under batch — there is no pause-alias probability to divide and Lost
    # re-locks at any counter value, so a wider counter would buy nothing and
    # cost an index bit plus three Sync states per batch (word-channel's CONFIG
    # carries the same note at the knob).
    "wire": {
        "numberSlots": 2,
        # 8, not 9: at 12+12 bits a position group's bool tail is exactly 4+4,
        # so the ninth slot the 13-bit geometry needed would ride every batch
        # idle — one synced bit for nothing. Batch counts are unchanged.
        "boolSlots": 8,
        "indexLoops": 1,
        "batchSeconds": 0.1,
    },
}

# The two other COMMITTED builds (operator-ruled 2026-08-02: all three variants
# ship as built artifacts, so a GitHub download is usable without this
# workspace). Each overrides CONFIG["objects"] only and rides CONFIG's wire
# block unchanged; each emits into its own subdirectory (`y/`, `y_double/`)
# holding controller.yaml + built/ + prefab, and `--check` pins all three
# on-disk documents byte-identical, not just the root one.
PRESETS = {
    "y": {"objects": [{"name": "Prop", "rotation": "y"}]},
    "y_double": {"objects": [{"name": "PropA", "rotation": "y"},
                             {"name": "PropB", "rotation": "y"}]},
}

# Check-only DEMO configs (operator-ruled 2026-08-17): the full `--check`
# structural suite runs over each, but nothing lands on disk — no
# controller.yaml, no prefab, no built/. At this scale every consumer writes
# their own CONFIG; these exist so the multi-object emission the committed
# builds cannot reach (mixed rotation modes, slice weighting, widened slots)
# is emitted, probed and packable on every change. A DEMO may override the
# `wire` block — merged SHALLOWLY onto CONFIG's, because a dict replacement
# would silently drop `indexLoops: 1` back to word-channel's default of 2,
# costing an index bit and three Sync states per batch with no diagnostic.
DEMOS = {
    "six": {
        "objects": [{"name": "Prop0", "rotation": "full", "slices": 3},
                    {"name": "Prop1", "rotation": "y"},
                    {"name": "Prop2", "rotation": "y"},
                    {"name": "Prop3", "rotation": "y"},
                    {"name": "Prop4", "rotation": "y"},
                    {"name": "Prop5", "rotation": "y"}],
        "wire": {"numberSlots": 4, "boolSlots": 16},
    },
}


# ------------------------------------------------------- derived geometry ----

def derive(c):
    """Every number the emitted document uses, derived once and range-checked.

    Refusals here are the entry's own fail-loud edge: a config that would emit a
    silently-saturating readout is rejected by name, never generated."""
    names = [ob["name"] for ob in c["objects"]]
    reserved = {"Sh", "Live", "FullLive"} & set(names)
    if reserved or len(set(names)) != len(names):
        raise SystemExit(
            f"REFUSE: object names {sorted(reserved) or names} — names must be "
            "unique, and Sh/Live/FullLive are the shared-walk scratch namespace: "
            "an object named one of them declares params byte-identical to the "
            "shared set, which Doc.param's duplicate guard cannot distinguish.")
    for ob in c["objects"]:
        k = ob.get("slices", 1)
        if not (isinstance(k, int) and k >= 1):
            raise SystemExit(
                f"REFUSE: {ob['name']} slices {k!r} — a slice weight is a "
                "positive integer count of turns in the ring")
        if k != 1 and len(c["objects"]) == 1:
            raise SystemExit(
                f"REFUSE: {ob['name']} slices {k} — a slice weight is a share "
                "of the multi-object ring, and a single-object build emits no "
                "Slice layer, so the key would change nothing while the header "
                "claimed it did. Drop it.")
    # Per-slice contact budget: one object's rig live at a time, so the active
    # cluster is that object's own receivers — coarse 3 + fine 3 + one per
    # rotation component (6/2/0 by mode). The ceiling guards FUTURE modes, not
    # today's constants — every current mode passes by arithmetic — because
    # ~24 receivers clustered in one spot read wrong values under the client's
    # cross-player summing bug (runtime.md §Contacts), and the whole rig parks
    # at one point.
    worst = max((6 + len(rot_comps(ob["rotation"])) for ob in c["objects"]),
                default=0)
    if worst > 16:
        raise SystemExit(
            f"REFUSE: a slice would run {worst} live receivers in one cluster — "
            "the ceiling is 16, margin under the ~24-receiver summing bug "
            "(runtime.md §Contacts). Trim the mode's component count.")
    cells = 2 ** c["coarseBits"]
    if abs(2 * c["range"] / c["cellSize"] - cells) > 1e-9:
        raise SystemExit(
            f"REFUSE: coarseBits {c['coarseBits']} spans {cells} cells of "
            f"{c['cellSize']} m = {cells * c['cellSize']} m, but range "
            f"{c['range']} needs {2 * c['range']} m — pick cellSize = "
            f"{2 * c['range'] / cells} or coarseBits = "
            f"{round((2 * c['range'] / c['cellSize'])).bit_length() - 1}")
    for k in ("coarseBits", "fineBits", "rotBits"):
        if not 9 <= c[k] <= 14:
            raise SystemExit(
                f"REFUSE: {k} is {c[k]} — the accepted range is 9..14 bits. The "
                "floor is the wire format: a word is one byte plus its bool "
                "tail. The ceiling is the SAR walk's own threshold fuzz — EPS "
                f"admits a mis-decision worth EPS/2 = {EPS / 2:g} of full scale, "
                "which stays under one LSB through 14 bits (2^-14 = 6.1e-5) and "
                "exceeds it from 15 on, so a 15th bit would quantize the fuzz "
                "rather than the reading.")
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
        # the range (the float32 ulp at range is the precision floor this
        # design is built to, not a defect it introduces).
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
    readings, so each takes its own group — a torn set of six independent
    readings is a stale orientation, never one no marker ever held. `y`'s two
    components are ONE value — a heading — and want the same adjacent-cell
    coherence a position axis wants, so they share a group when the slots can
    hold it, and the pair layer's single commit publishes both limbs in one
    frame whatever the slots do (`pair_layer`)."""
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
    complaining about a group it cannot place.

    The bool refusal runs the REAL packing — word-channel's own `group_runs` +
    `pack_runs` over the declared table — and reports what the worst batch
    actually needs. The estimate it replaces (`numberSlots x rotation bools`)
    assumed every number slot in some batch fills with a rotation component,
    which is an upper bound the declaration order need not reach: it refused
    tables that pack fine, and it said nothing at all about a batch made worse
    by mixed widths."""
    w = c["wire"]
    axis_nums, axis_bools = 2, (c["coarseBits"] - 8) + (c["fineBits"] - 8)
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
    wc = load_word_channel()
    nbatches, _ = wc.pack_runs(
        wc.group_runs(numbers, w["numberSlots"], "number"), w["numberSlots"])
    need = []
    for batch in nbatches:
        gs = {n.get("group") for n in batch if n.get("group") is not None}
        need.append(sum(1 for b in bools if b.get("group") in gs))
    worst = max(need) if need else 0
    if w["boolSlots"] < worst:
        i = need.index(worst)
        raise SystemExit(
            f"REFUSE: boolSlots {w['boolSlots']} < {worst} — number batch "
            f"{i + 1} carries {', '.join(n['name'] for n in nbatches[i])} and "
            f"their groups pin {worst} bool words to that same batch, which is "
            "where a group's bools have to ride. Raise boolSlots to "
            f"{worst}, or drop numberSlots so fewer groups share a batch.")


# --------------------------------------------------------- emit helpers -----

class Doc:
    """Accumulates params, clips and layers, refusing a duplicate name whose
    content differs — the one class of generator bug a merged document invites."""

    def __init__(self):
        self.params = []
        self._pnames = {}
        self.clips = {}
        self.layers = []

    def param(self, line, name=None):
        # Re-declaring a param with the SAME line is how several layers claim a
        # shared scratch param, and is fine. A second declaration that differs is
        # a generator bug: whichever call ran first silently wins, and the loser
        # gets a param of the wrong type or default with no diagnostic anywhere.
        # `clip` below is the model.
        if name is not None:
            if name in self._pnames:
                if self._pnames[name] != line:
                    raise SystemExit(
                        f"REFUSE: param '{name}' declared twice with different "
                        f"content:\n  {self._pnames[name].strip()}\n  "
                        f"{line.strip()}")
                return
            self._pnames[name] = line
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
              # it takes the first rung instead of stalling the walk. A reading
              # inside the overlap takes the accept rung (it is listed first)
              # and the walk cannot recover, so the mis-decision it admits is
              # bounded by EPS x the largest threshold = EPS/2 = 5e-5 of full
              # scale. That is under one LSB through 14 bits (2^-14 = 6.1e-5)
              # and over it from 15 — which is where derive() caps the widths,
              # NOT at the 16 the wire format alone would allow.


def walk_rungs(resid, b, accept, reject):
    t = 0.5 ** (b + 1)
    return [f"{{ to: {accept}, when: [ {resid} greater {num(t * (1 - EPS))} ] }}",
            f"{{ to: {reject}, when: [ {resid} less {num(t * (1 + EPS))} ] }}"]


def emit_walk(tag, nbits, resid, plan, extra_add, out, exit_rungs):
    """The SAR ladder: one state pair per bit, accept above, reject below.

    `extra_add` is an additional param to accumulate the bit's place value into
    (the running cell index the local anchor rides) — None for a stage that has
    no anchor. `exit_rungs` are the final pair's outgoing transitions verbatim —
    a single exit, a per-object commit fan-out, or the first rungs of a second
    ladder walked back-to-back in the same layer. Returns the layout rows."""
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
               if b + 1 < nbits else exit_rungs)
        out.extend(state(acc, driver(sets=sets or None, adds=adds), nxt))
        out.extend(state(rej, None, nxt))
        layout.append((acc, rej))
    return layout


def exit_when_true(c, exit_to):
    return [f"{{ to: {exit_to}, when: [ {c['prefix']}/True is true ] }}"]


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
    # This entry merges the fragment's header, params and layers, and builds the
    # document's `clips:` section from `Doc` alone — so a clip line the fragment
    # emitted would be dropped on the floor and the layer referencing it would
    # compile against a clip that does not exist. Only word-channel's `assemble:`
    # block emits any and `wire_config` passes `assemble: []`, so this is
    # unreachable today; it is here to keep it that way.
    if wc["clips"]:
        raise SystemExit(
            f"REFUSE: word-channel emitted {len(wc['clips'])} clip line(s) this "
            "generator has nowhere to put. Merge them into Doc.clips before "
            "lifting this refusal — dropping them leaves a layer bound to a "
            "clip that was never emitted.")
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
    # This entry declares NO validity param of its own. The transport already
    # emits one — `<channel>/Acquired`, false until this client's receiver has
    # applied a complete word table — and it is on word-channel's globalParams,
    # so a consumer binds it by name without help from here. A second name
    # restating it would be a second thing to keep true. The trap worth naming
    # here: Acquired reads 0 on the WEARER forever, because the wearer runs
    # sender layers only and its own pose never touches the decode. "Is the
    # pose on screen trustworthy" is therefore `IsLocal OR Ch/Acquired`, which
    # is what Follow's own rungs evaluate.

    layers = list(wc["layers"])
    layers.append(floatify_layer(doc, c, numbers, bools))
    layers.append(decode_display_layer(doc, c, d))
    layers.append(follow_layer(doc, c))
    if multi:
        # The shared walk set: the slice serializes measurement, so the walks
        # walk ONCE per slice against shared staging and fan the commit out to
        # the live object's words — layers and walk states flat in N.
        layers.append(slice_layer(doc, c))
        for a in AXES:
            layers.append(position_walk(doc, c, d, a))
        modes = {ob["rotation"] for ob in c["objects"]}
        if modes - {"none"}:
            layers.append(pair_layer(doc, c, d, shared=True))
        if "full" in modes:
            for comp in full_only_comps(c):
                layers.append(component_walk(doc, c, d, comp))
    else:
        ob = c["objects"][0]
        for a in AXES:
            layers.append(position_walk(doc, c, d, a, ob=ob))
        if ob["rotation"] == "y":
            layers.append(pair_layer(doc, c, d, shared=False))
        elif ob["rotation"] == "full":
            for comp in FULL_COMPS:
                layers.append(component_walk(doc, c, d, comp, ob=ob))
    state_count = refuse_duplicate_states(layers)

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
            # The per-client per-frame decode-side cost: every word limb plus
            # Acquired through the one Floatify driver. Quoted in the README's
            # cost accounting from here, never hand-counted.
            "floatifyLimbs": len(numbers) + len(bools) + 1,
            "sliceSchedule": slice_schedule(c) if multi else None,
            "stateCount": state_count,
            "layerCount": len(layers),
        }),
    }


def refuse_duplicate_states(layers):
    """Two ladders now share layers (the serial pair; per-object commit
    fan-outs), which makes a silently-duplicated state name reachable for the
    first time — the exact generator-bug class `Doc` refuses for params and
    clips, closed here for states. A duplicate key in the emitted YAML would
    compile to whichever state the loader keeps, with every probe reading the
    first. Returns the total state count — the document's own figure for the
    README's cost accounting."""
    total = 0
    for block in layers:
        name, seen, in_states = None, set(), False
        for ln in block:
            if ln.startswith("  - name: "):
                name = ln.split("- name: ", 1)[1].strip()
            elif ln.startswith("    ") and not ln.startswith("     ") \
                    and ln.rstrip().endswith(":"):
                in_states = ln.strip() == "states:"
            elif in_states and ln.startswith("      ") \
                    and not ln.startswith("       ") and ln.rstrip().endswith(":"):
                s = ln.strip()[:-1]
                if s in seen:
                    raise SystemExit(
                        f"REFUSE: layer {name} declares state '{s}' twice — "
                        "the second silently shadows the first in every "
                        "name-keyed reader, this self-test included.")
                seen.add(s)
                total += 1
    return total


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

def word_float(p, name):
    """`/B/` is the decode's copy namespace — every word limb's one-frame-old
    float mirror, bytes and bools alike — not a bool namespace."""
    return f"{p}/B/{name}"


def floatify_layer(doc, c, numbers, bools):
    """Word bools AND byte words -> float scratch, every frame.

    A blend tree evaluates only Float parameters — a bool named as a weight
    reads 0 forever — and a parameter driver runs on state ENTER, so the copy
    needs a state the layer re-enters every frame. Two states alternating is
    that; the decode reads the floats one frame behind the words.

    The bytes ride the same copy for coherence, not for type: a tree could
    read them raw, and that fast path was a measured one-frame 2 m display
    excursion per cell crossing (±62 m across a coarse byte boundary, where
    the byte moves and the bool tail compensates). One driver snapshots a
    committed axis whole — commit and receive both land a word's limbs in a
    single driver frame — so every limb reaches the decode one frame later
    TOGETHER and the assembled pair can never mix old and new.

    `<channel>/Acquired` rides the same copy for the same reason: the receiver
    certifies it in the very driver that applies the final batch's words, so a
    gate reading it raw fires one frame before the copies of those words land —
    and on a head-landing cold join the Follow engage would render the last
    group fully stale for that frame. Engaging on the copy keeps the gate and
    the decode's inputs on one latency path."""
    p = c["prefix"]
    copies = {}
    for w in numbers + bools:
        f = word_float(p, w["name"])
        doc.param(f"  {f}: {{ type: float, scratch: true }}", f)
        copies[f] = w["name"]
    acq_copy = f"{p}/B/Acquired"
    doc.param(f"  {acq_copy}: {{ type: float, scratch: true }}", acq_copy)
    copies[acq_copy] = f"{c['channel']}/Acquired"
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
                f", directWeight: {word_float(p, byte_word)} }}")
    for k, w in enumerate(bws):
        kids.append("{ clip: " + doc.clip(f"asm_{base}_{w}", {dest: w}) +
                    f", directWeight: {word_float(p, bool_words[k])} }}")
    return kids


def decode_display_layer(doc, c, d):
    """ONE single-state Direct layer carrying both the decode (Floatify copies
    -> assembled `D/` AAPs) and the display (D/ AAPs -> the display rig's
    constraint offsets and proxy positions) — merged because two single-state
    DBT layers were paying a layer for an ordering the runtime does not sell
    anyway: an AAP read is one frame behind its write for same-layer and
    cross-layer trees alike (runtime.md §Animator evaluation), so the display
    children read `D/` at exactly the latency the separate-layer shape had,
    and every `D/` value a display child reads is stale TOGETHER — uniform
    age, not the OS2b mixed-age class.

    Side-agnostic: every client (the wearer included) reads the same Floatify
    copies of the word params and assembles the same AAPs. No state is carried
    across frames, so a culling pause costs staleness and never a corrupt
    decode. Decode weights name only `B/` copies, never a word param —
    `--check`'s decode-coherence probe holds that, and why it matters is
    `floatify_layer`'s docstring.

    Display: the base clip is the FIRST child of each axis's run so the
    running sum never leaves the working range — float32's ulp at range is
    this design's precision floor already."""
    p = c["prefix"]
    multi = len(c["objects"]) > 1
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
    for ob in c["objects"]:
        o = ob["name"]
        # The MEASURE anchor rides the walk's running cell index (staged, local,
        # mid-cycle); the DISPLAY anchor rides the committed word. They are the
        # same arithmetic on two different sources, and they cannot be one node:
        # committing coarse early enough to share it would let the wire latch an
        # axis whose fine half is still a cycle old.
        # Both bases fold the rig park in, so every animated offset is a WORLD
        # coordinate against the origin-pinned Rig and no constraint offset
        # anywhere carries the park as a standing ~900 m constant. The park may
        # never ride a constraint SOURCE offset: the shipping client multiplies
        # a source's offset by the avatar's per-client scale factor (asset
        # sources included; measured in-client), making such a park a
        # cross-client displacement of (s_local - s_remote) x park.
        anch = f"Rig/{o}/Fine/Anchor/VRCPositionConstraint.PositionOffset"
        abase = {f"{anch}.{LOWER[a]}": num(-c["range"] + c["cellSize"] / 2
                                           + d["rigOffset"][i])
                 for i, a in enumerate(AXES)}
        kids.append("{ clip: " + doc.clip(f"anch_{safe(o)}_base", abase) +
                    f", directWeight: {p}/One }}")
        for a in AXES:
            z = {f"{anch}.{LOWER[x]}": 0 for x in AXES}
            cell = dict(z, **{f"{anch}.{LOWER[a]}": num(c["cellSize"])})
            # Multi-object: the SHARED cell index weights every object's anchor
            # cell clip. Inactive objects' anchors ride it harmlessly — their
            # receivers are deactivated, and an incoming object's own CoarseEnd
            # rewrites K before its fine stage samples anything (settle +
            # liveness + escape are all still in that path).
            kacc_w = f"{p}/K/Sh/P{a}" if multi else f"{p}/K/{o}/P{a}"
            kids.append("{ clip: " + doc.clip(f"anch_{safe(o)}_{LOWER[a]}_cell", cell) +
                        f", directWeight: {kacc_w} }}")

        disp = f"Rig/{o}/Display/VRCPositionConstraint.PositionOffset"
        base = {f"{disp}.{LOWER[a]}": num(d["posBase"] + d["rigOffset"][i])
                for i, a in enumerate(AXES)}
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
    out = [f"  - name: {p}/Decode", "    states:"]
    out.extend(tree_state("Decode", "DecodeDisplay", kids))
    out.append("    default: Decode")
    return out


def enable_subtree(doc, c):
    """The enable's reach into the measure rig, as a 1D tree rather than a layer.

    Only the measure subtrees: whether the wearer's rig is sensing. The
    Sync_Target/Sync pair is not in here — Sync is `follow_layer`'s alone
    (it needs IsLocal and so cannot be a tree at all), and Sync_Target is the
    consumer's write surface, which nothing in this document may bind.

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
    """Which source `Sync` rides.

    `Sync` is ALWAYS active and always driven; this layer only moves weight
    between its two sources. One rule covers every state — `Sync` rides
    `Sync_Target` unless the decoded pose is valid, and the reconstruction when
    it is — so Enable-off, a pre-gate remote and a culled decode are the same
    case rather than three, and the module hides nothing. What a remote shows
    while the pose is undecoded is the consumer's call, made against a prop that
    could be anywhere; `<channel>/Acquired` is what they make it on.

    The weights are never both 0, which is what keeps the measured weight-0
    write out of the driven path: at weight 0 a VRCParentConstraint does not
    release, it writes the captured *AtRest pose every frame in the constrained
    object's parent frame — a live writer parked on a baked value. Here one
    source always holds weight 1.

    THREE states over two clips, because the wearer and a pre-gate remote hold
    the same pose and opposite validity, and one state cannot say both. `Local`
    and `Release` share the target-riding clip; `Follow` carries the other. No
    state drives a validity param: the transport certifies `<channel>/Acquired`
    itself, and this layer only reads it.

    A layer rather than a tree because the condition is `!IsLocal AND Enable`
    and IsLocal is a bool built-in: a blend tree reads 0 from it forever.

    Engaging additionally waits on the transport's own correctness output. A
    fresh clone starts with every word at 0, 0 quantizes to cell 0, and cell 0 is
    the far corner of the range — so engaging before the first full word table
    arrives would put the prop at the corner in front of a late joiner.
    `<channel>/Acquired` is exactly that proposition and carries no mode
    dependence: a `Cycle` threshold would, because under `atomic: batch` a
    receiver re-locks from Lost at any counter value and can enter AT a tail,
    taking its first increment after one batch. What a cold join costs depends
    on where in the loop it re-locks, and under `batch` that is any counter
    value: land on a head (1 of batchCount phases) and the first tail certifies;
    land anywhere else and `Lost` handed the walk a false SawHead, so the first
    tail copies false and certification waits for the SECOND — the same tail a
    two-tail counter test would have engaged on. So `Acquired` is never slower
    than that test and is one loop faster on the head phase; it is the mode
    independence that is the reason to prefer it, not a latency win.

    The engage rung reads `Acquired` through its Floatify copy (`B/Acquired`),
    never raw. The receiver certifies `Acquired` in the same driver that applies
    the final batch's words, so the raw param leads the decode's `B/` inputs by
    one frame — engaging on it renders the last group stale for the certifying
    frame of a head-landing cold join. The copy puts the gate on the decode's
    own latency path; `floatify_layer`'s docstring carries the mechanism.

    Releasing does not test `Acquired` — its only exit tests `Enable` alone, and
    the engage rung is an AnyState rung with `canTransitionToSelf: false`, which
    together are what make `Follow` LATCH: once engaged it stays engaged until
    Enable goes off, so a receiver falling to `Lost` mid-session does not drop
    the prop back to its target. Do not add a rung here without deciding what
    that does to the latch. The same latching is why flipping `Enable` on with a
    table already acquired snaps immediately instead of waiting a cycle —
    `Enable` never gated the wire, so the receiver keeps decoding through the
    toggle and `Acquired` stays true across it. Intended."""
    p = c["prefix"]
    rides_target, rides_recon = {}, {}
    for ob in c["objects"]:
        s = f"{sync_path(c, ob['name'])}/VRCParentConstraint.Sources"
        rides_target[f"{s}.source0.Weight"] = 1
        rides_target[f"{s}.source1.Weight"] = 0
        rides_recon[f"{s}.source0.Weight"] = 0
        rides_recon[f"{s}.source1.Weight"] = 1
    target_clip = doc.clip("follow_target", rides_target)
    recon_clip = doc.clip("follow_recon", rides_recon)
    out = [f"  - name: {p}/Follow", "    states:"]
    out.extend(state("Release", None, None, motion=f"{{ clip: {target_clip} }}"))
    out.extend(state("Local", None, None, motion=f"{{ clip: {target_clip} }}"))
    out.extend(state("Follow", None, None, motion=f"{{ clip: {recon_clip} }}"))
    out.extend([
        "    any:",
        "      - { to: Local, when: [ IsLocal is true ], canTransitionToSelf: false }"
        "   # the wearer's pose is authoritative from frame 1",
        f"      - {{ to: Follow, when: [ IsLocal is false, {p}/Enable greater 0.5, "
        f"{p}/B/Acquired greater 0.5 ], canTransitionToSelf: false }}"
        "   # a complete word table has landed on THIS client, read through the"
        " Floatify copy so the gate and the decode inputs share one latency path",
        f"      - {{ to: Release, when: [ IsLocal is false, {p}/Enable less 0.5 ], "
        "canTransitionToSelf: false }"])
    out.append("    default: Release")
    out.extend(["    layout:", "      nodes:",
                "        Release: [30, 180]", "        Local:   [270, 260]",
                "        Follow:  [270, 100]",
                "      entry: [50, 120]", "      any:   [50, 40]",
                "      exit:  [50, 80]"])
    return out


def sense_union(c):
    """Every shared sense param a multi-object build declares, in FULL_COMPS
    order: the position stages plus the union of rotation components any
    object's mode reads. Receivers on EVERY object's rig name these — one
    param set, at most one live writer, because the slice gate clip flips the
    outgoing and incoming rigs in one evaluation (no co-active frame). The
    slice's Enter clear must cover this whole union or a y slice's untouched
    full-only component would hand the next full slice a frozen reading."""
    p = c["prefix"]
    out = {}
    for a in AXES:
        out[f"{p}/Sense/Sh/C{a}"] = 0
        out[f"{p}/Sense/Sh/F{a}"] = 0
    comps = set()
    for ob in c["objects"]:
        comps |= set(rot_comps(ob["rotation"]))
    for comp in FULL_COMPS:
        if comp in comps:
            out[f"{p}/Sense/Sh/R{comp}"] = 0
    return out


def slice_wake_params(c, o):
    """What a slice waits to see live before unblocking its object's walks.

    Coarse and rotation receivers only, and MODE-SCOPED to the object: a y rig
    never writes the full-only components, so waiting on those would burn the
    whole skip window on every y slice. The fine receiver rides the anchor,
    which is parked at cell 0 until that object's coarse walk has run, so it
    legitimately reads 0 here — its liveness is checked later, inside the walk,
    where the anchor is already placed."""
    p = c["prefix"]
    ob = next(x for x in c["objects"] if x["name"] == o)
    return ([f"{p}/Sense/Sh/C{a}" for a in AXES] +
            [f"{p}/Sense/Sh/R{comp}" for comp in rot_comps(ob["rotation"])])


def slice_schedule(c):
    """The ring of slices, weighted and INTERLEAVED: an object with `slices: k`
    appears k times, never in two consecutive slots (ring-wise). Adjacency is not a style point: an adjacent
    repeat's own Enter drops `Live`, which drives every shared walk through the
    abandon rung and clears staging mid-ladder — the second slot would tear
    down the very walk it was bought to extend, discarding up to a full ladder
    and repaying the settle."""
    total = sum(ob.get("slices", 1) for ob in c["objects"])
    # Deal heaviest-first into the even indices, then the odd: on a ring this
    # is adjacency-free for every weighting with max <= total//2 — a quotient
    # placement with linear probing refused feasible rings (2,2,3 among them)
    # while its message blamed the weight — so the refusal below fires exactly
    # when the bound it states is actually violated.
    flat = []
    for ob in sorted(c["objects"], key=lambda x: -x.get("slices", 1)):
        flat += [ob["name"]] * ob.get("slices", 1)
    slots = [None] * total
    for name, pos in zip(flat, [*range(0, total, 2), *range(1, total, 2)]):
        slots[pos] = name
    for i, name in enumerate(slots):
        if name == slots[(i + 1) % total]:
            raise SystemExit(
                f"REFUSE: the slice ring places '{name}' in consecutive slots "
                f"({slots}) — its weight is too large for the ring (max is "
                "half the total, rounded down). Lower the weight or add "
                "objects.")
    return slots


def slice_layer(doc, c):
    """Multi-object time-multiplex: one object's measure rig is live per slice,
    so N objects cost one rig instead of N — and, with the walks shared, one
    walk set instead of N.

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
    the geometry could have produced.

    Shared-walk consequences, both load-bearing. The Enter/Parked clear covers
    the WHOLE shared sense union — with one param set, a stale reading is no
    longer the outgoing object's own value on its own param but the seed of a
    cross-object publish: liveness gates satisfied by the previous object's
    frozen readings walk object A's position into object B's words. And `Run`
    is the only writer of `Slice/Live` (plus `Slice/FullLive` for full-mode
    objects), so Live=1 always means exactly one `Slice/<o>`=1, with an Enter
    frame between any two — which is what the walks' abandon rung and the
    `Commit_<o>` routing conditions rest on."""
    p, d = c["prefix"], derive(c)
    names = [ob["name"] for ob in c["objects"]]
    mode = {ob["name"]: ob["rotation"] for ob in c["objects"]}
    for o in names:
        doc.param(f"  {p}/Slice/{o}: {{ type: float, scratch: true }}",
                  f"{p}/Slice/{o}")
    doc.param(f"  {p}/Slice/Live: {{ type: float, scratch: true }}",
              f"{p}/Slice/Live")
    if any(m == "full" for m in mode.values()):
        doc.param(f"  {p}/Slice/FullLive: {{ type: float, scratch: true }}",
                  f"{p}/Slice/FullLive")
    gates = {o: doc.clip(f"slice_gate_{safe(o)}", gate_bindings(c, o), seconds=1)
             for o in names}
    parked_clip = doc.clip("slice_gate_park", gate_bindings(c, None), seconds=1)
    blocked = dict(sense_union(c), **{f"{p}/Slice/{x}": 0 for x in names})
    blocked[f"{p}/Slice/Live"] = 0
    if any(m == "full" for m in mode.values()):
        blocked[f"{p}/Slice/FullLive"] = 0
    # The run window holds the slowest walk in the slice plus its Parked climb
    # and its Commit hop; the skip window bounds how long a dead rig may hold
    # the slice before the next object gets its turn.
    hold = num(round((max_walk_frames(c) + c["settleFrames"] + 4) / 60.0, 4))
    skip = num(round((max_walk_frames(c) + c["settleFrames"] + 4) / 60.0, 4))

    slots = slice_schedule(c)
    seen = {o: 0 for o in names}
    labels = []
    for o in slots:
        labels.append((o, seen[o]))
        seen[o] += 1
    out = [f"  - name: {p}/Slice", "    states:"]
    for i, (o, j) in enumerate(labels):
        motion = f"{{ clip: {gates[o]} }}"
        no, nj = labels[(i + 1) % len(labels)]
        # Deactivate every other object's rig AND block every walk, in one
        # frame, before anything is cleared. Wait for this object's reactivated
        # receivers to come live rather than counting frames at them; the skip
        # rung is there so one dead rig cannot starve the other objects of
        # their slices. Advancing on it is safe — the walks carry the same
        # gate, so a skipped slice measures nothing rather than measuring
        # zeros.
        run_sets = {f"{p}/Slice/{x}": (1 if x == o else 0) for x in names}
        run_sets[f"{p}/Slice/Live"] = 1
        if any(m == "full" for m in mode.values()):
            run_sets[f"{p}/Slice/FullLive"] = 1 if mode[o] == "full" else 0
        out.extend(state(
            f"Enter_{o}_{j}", driver(sets=blocked),
            [f"{{ to: Run_{o}_{j}, when: [ {', '.join(live(d, slice_wake_params(c, o)))} ] }}",
             f"{{ to: Enter_{no}_{nj}, when: [], exitTime: {skip} }}"
             "   # a rig that never wakes must not starve the other slices"],
            motion=motion))
        out.extend(state(
            f"Run_{o}_{j}",
            driver(sets=run_sets),
            [f"{{ to: Enter_{no}_{nj}, when: [], exitTime: {hold} }}"
             "   # the gate clip declares its length, so exitTime is seconds"],
            motion=motion))
    first_o, first_j = labels[0]
    out.extend(state("Parked", driver(sets=blocked),
                     [f"{{ to: Enter_{first_o}_{first_j}, when: [ {p}/Enable greater 0.5 ] }}"],
                     motion=f"{{ clip: {parked_clip} }}"))
    out.extend(off_ladder(c))
    out.append("    default: Parked")
    return out


def max_walk_frames(c):
    """The slowest ladder's frame count — what the slice hold/skip windows and
    the header's cycle math are sized on. The serial pair walks TWO rotBits
    ladders back-to-back, so it has its own term: sizing the window on the
    position ladder alone would, at a geometry where 2·rotBits+3 exceeds it
    (legal from coarseBits 9 / rotBits 12 up), abandon every rotation cycle at
    the window's edge, forever."""
    pos = 2 + c["coarseBits"] + 1 + c["settleFrames"] + 1 + c["fineBits"] + 1
    frames = [pos]
    multi = len(c["objects"]) > 1
    modes = {ob["rotation"] for ob in c["objects"]}
    pair = (multi and modes - {"none"}) or (not multi and "y" in modes)
    if pair:
        frames.append(2 + 2 * c["rotBits"] + 1)
    if "full" in modes:
        frames.append(2 + c["rotBits"] + 1)
    return max(frames)


def sense_param(doc, c, name):
    """Contact receiver outputs stay out of `scratch:` — a human reading the
    merged FX sees what the rig is measuring, and they cost no sync bits."""
    if not doc.has_param(name):
        doc.param(f"  {name}: float            # contact receiver (localOnly)", name)
    return name


def gate(c, shared, full_only=False):
    """A walk's standing entry conditions. Shared (multi-object) walks gate on
    `Slice/Live` — set only inside a Run window, so a walk never climbs during
    an Enter's clear frame. `full_only` adds the `Slice/FullLive` term for the
    component layers only a full-mode object feeds: without it they would climb
    during a y slice (blocked today only by the cleared sense reading) and,
    having no y-mode Commit to route to, park at the ladder top until the next
    Enter dropped Live."""
    g = ["IsLocal is true", f"{c['prefix']}/Enable greater 0.5"]
    if shared:
        g.append(f"{c['prefix']}/Slice/Live greater 0.5")
    if full_only:
        g.append(f"{c['prefix']}/Slice/FullLive greater 0.5")
    return g


def off_ladder(c, shared=False):
    """The AnyState rungs that yank an encode layer out of its walk.

    The state is `Parked`, not `Off`: a bare `Off` in value position infers as
    the boolean false and every `to:` naming it would silently retarget.

    `canTransitionToSelf: false` is what makes each rung a one-shot — it fires
    from whatever state the walk was in, Parked's driver clears once, and nothing
    re-enters. The clear sticks because the same frame's gate clip has already
    deactivated the receiver GOs, and a deactivated sensing component never
    writes again (it only freezes what it last wrote, which is what the clear is
    for).

    The `Live` rung is what keeps a multi-object slice honest: every slice
    change passes through an Enter state that drops `Live` for at least a frame,
    so a walk mid-ladder ABANDONS rather than running on to a Commit and
    publishing limbs measured against another object's senders. It replaces the
    per-object `Slice/<o>` rung the unshared walks carried — a shared walk
    belongs to no object, and `Live` is the one param that says 'some rig is
    live and it is still the one I started against' (Run's single driver makes
    Live=1 equivalent to exactly one Slice/<o>=1, with an Enter frame between
    any two)."""
    p = c["prefix"]
    out = ["    any:",
           f"      - {{ to: Parked, when: [ {p}/Enable less 0.5 ], "
           "canTransitionToSelf: false }"]
    if shared:
        out.append(f"      - {{ to: Parked, when: [ {p}/Slice/Live "
                   "less 0.5 ], canTransitionToSelf: false }")
    return out


def wake_up(c, shared):
    """The conditions that let a Parked encode layer start climbing again."""
    up = [f"{c['prefix']}/Enable greater 0.5"]
    if shared:
        up.append(f"{c['prefix']}/Slice/Live greater 0.5")
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
    coarse_why = ("self-restoring: the coarse receiver's box spans the whole "
                  "working volume and the squeeze constraint keeps its sender "
                  "inside, so a 0 means only re-acquisition or a prop outside "
                  "the range — both clear on their own")
    fine_why = ("NOT self-restoring: the fine receiver rides the measurement "
                "anchor, which only a fresh coarse commit moves, so a teleport "
                "out of the cell leaves this waiting on a stage it cannot reach")
    marker_why = ("self-restoring: the marker rides a rigid arm on a holder "
                  "pinned to the rig and cannot leave its receiver's box, so a "
                  "0 means re-acquisition and nothing else")
    scr = "Sh" if multi else c["objects"][0]["name"]
    # Position: the walk-entry states are Idle plus every commit state (a
    # commit's loop back into the walk is a walk entry too). Shared layers fan
    # commits out per object; single-object layers have the one Commit.
    commit_states = ([f"Commit_{ob['name']}" for ob in c["objects"]]
                     if multi else ["Commit"])
    for a in AXES:
        lay = f"{p}/Enc/{scr}/P{a}"
        for st in ["Idle"] + commit_states:
            rows.append({"layer": lay, "state": st,
                         "params": [f"{p}/Sense/{scr}/C{a}"], "escape": None,
                         "why": coarse_why})
        rows.append({"layer": lay, "state": f"Settle{c['settleFrames'] - 1}",
                     "params": [f"{p}/Sense/{scr}/F{a}"], "escape": "Idle",
                     "why": fine_why})
    modes = {ob["rotation"] for ob in c["objects"]}
    # The pair layer's ONE liveness site is Idle, covering both heading senses:
    # Start samples both in a single driver and the Z ladder walks a residual
    # frozen there, so no mid-ladder state reads a sense param at all.
    if (multi and modes - {"none"}) or (not multi and "y" in modes):
        rows.append({"layer": f"{p}/Enc/{scr}/Ry", "state": "Idle",
                     "params": [f"{p}/Sense/{scr}/R{x}" for x in Y_COMPS],
                     "escape": None, "why": marker_why})
    if "full" in modes:
        comps = full_only_comps(c) if multi else FULL_COMPS
        for comp in comps:
            rows.append({"layer": f"{p}/Enc/{scr}/R{comp}", "state": "Idle",
                         "params": [f"{p}/Sense/{scr}/R{comp}"],
                         "escape": None, "why": marker_why})
    if multi:
        labels, seen = [], {}
        for o in slice_schedule(c):
            j = seen.get(o, 0)
            labels.append((o, j))
            seen[o] = j + 1
        for i, (o, j) in enumerate(labels):
            no, nj = labels[(i + 1) % len(labels)]
            rows.append({
                "layer": f"{p}/Slice", "state": f"Enter_{o}_{j}",
                "params": slice_wake_params(c, o),
                "escape": f"Enter_{no}_{nj}",
                "why": "self-restoring (coarse and marker sources, as above), "
                       "and bounded anyway by the skip rung that stops one dead "
                       "rig starving the other slices"})
    return rows


def tag_set(c, o):
    """Contact collision tags for one object's sender groups — only the groups
    that object's rotation mode gives a carrier: a tag the prefab cannot carry
    is a spec-vs-artifact lie waiting for a reviewer.

    Deterministic from the prefix and — when there is more than one object — the
    object name, the same rule the `Sync` pair follows and for a sharper reason:
    measured with two objects on one tag set, NEITHER converges, because every
    receiver reads whichever sender is strongest rather than its own."""
    base = c["prefix"].replace("/", "")
    mid = o if len(c["objects"]) > 1 else ""
    mode = next(x for x in c["objects"] if x["name"] == o)["rotation"]
    stages = ["Coarse", "Fine"]
    if mode != "none":
        stages.append("RotA")
    if mode == "full":
        stages.append("RotB")
    return [f"{base}{mid}{s}" for s in stages]


def gate_bindings(c, live_object):
    """m_IsActive across every object's three measure subtrees, with one
    object's live. `live_object` None parks them all."""
    b = {}
    for ob in c["objects"]:
        x = ob["name"]
        for sub in ("Coarse", "Fine", "Rot"):
            b[f"Rig/{x}/{sub}/GameObject.m_IsActive"] = 1 if x == live_object else 0
    return b


def sync_path(c, o):
    """The output node — mount a prop under it, or list it as a constraint source.

    Half of the whole consumer surface: `Sync_Target` in, `Sync` out. `Sync`
    carries ONE VRCParentConstraint whose two sources are the consumer's input
    and the entry's reconstruction, and `follow_layer` picks between them, so a
    consumer never multiplexes local against remote — the module owns that, once,
    and `Sync` reports a pose correct for whichever client is reading it.

    One object owns the bare pair; several take a suffixed pair each
    (`SyncA`/`SyncA_Target`, the shape Custom-Object-Sync ships as
    `SyncPositionA`/`SyncPositionA Target`), because one input is one
    consumer-driven frame and one output follows one reconstruction."""
    return "Sync" if len(c["objects"]) == 1 else f"Sync{o}"


def sync_target_path(c, o):
    """The input node — the consumer's, and the transform the senders measure.

    The entry never binds it (`check` holds that): the consumer owns its source
    list, a composed toggle may own its `FreezeToWorld`, and measuring it means
    measuring the prop's authority on the only client that measures at all."""
    return "Sync_Target" if len(c["objects"]) == 1 else f"Sync{o}_Target"


def position_walk(doc, c, d, a, ob=None):
    """One axis, one layer: coarse walk -> anchor -> settle -> fine walk ->
    atomic commit. IsLocal-gated; a remote sits in Idle forever.

    `ob` set is the single-object shape: staging, sense params and the one
    Commit all belong to that object. `ob` None is the SHARED multi-object
    shape — the layer that makes walk states flat in N: one `Sh` staging set
    walked once per slice, receivers on every object's rig multiplexed onto
    the shared sense params (at most one live writer — the slice gate clip
    flips rigs in one evaluation), and a per-object `Commit_<o>` fan-out
    routing the finished words to whichever object's slice is live."""
    p = c["prefix"]
    shared = ob is None
    scr = "Sh" if shared else ob["name"]
    commit_objs = c["objects"] if shared else [ob]
    lay = f"{p}/Enc/{scr}/P{a}"
    sc = sense_param(doc, c, f"{p}/Sense/{scr}/C{a}")
    sf = sense_param(doc, c, f"{p}/Sense/{scr}/F{a}")
    st = f"{p}/S/{scr}/P{a}"
    res = f"{p}/R/{scr}/P{a}"
    kacc, kfloat = f"{st}/Kacc", f"{p}/K/{scr}/P{a}"
    for nm in (f"{st}/C", f"{st}/F", f"{res}/C", f"{res}/F", kacc, kfloat):
        doc.param(f"  {nm}: {{ type: float, scratch: true }}", nm)
    cbools = [f"{st}/C{j}" for j in range(c["coarseBits"] - 8)]
    fbools = [f"{st}/F{j}" for j in range(c["fineBits"] - 8)]
    for nm in cbools + fbools:
        doc.param(f"  {nm}: {{ type: bool, scratch: true }}", nm)

    # Walk-entry conditions: the gate, plus liveness on the very param the state
    # it leads to is about to sample.
    enter = gate(c, shared) + live(d, [sc])
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
                     kacc, out, exit_when_true(c, "CoarseEnd"))
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
    # The fan-out: single-object exits to its one Commit unconditionally;
    # shared exits to whichever object's slice is live. Live=1 implies exactly
    # one Slice/<o>=1 (Run's single driver), so exactly one rung is open; if
    # the slice ends here first, the Live AnyState rung abandons instead.
    if shared:
        fine_exit = [f"{{ to: Commit_{x['name']}, when: [ {p}/Slice/{x['name']} "
                     "greater 0.5 ] }" for x in commit_objs]
    else:
        fine_exit = exit_when_true(c, "Commit")
    out.extend(state(
        "FineStart",
        driver(sets=dict({f"{st}/F": 0}, **{b: 0 for b in fbools}),
               copies={f"{res}/F": f"{{ source: {sf}, sourceMin: {num(d['fineMin'])}, "
                                   f"sourceMax: {num(d['fineMax'])}, destMin: 0, destMax: 1 }}"}),
        walk_rungs(f"{res}/F", 0, "F0A", "F0R")))
    rows += emit_walk("F", c["fineBits"], f"{res}/F",
                      bit_plan(c["fineBits"], f"{st}/F", fbools),
                      None, out, fine_exit)
    # The loop back into the walk is a walk entry too: a rig that dies mid-run
    # must not restart against a receiver reading 0.
    leave = [f"{{ to: CoarseStart, when: [ {', '.join(enter)} ] }}",
             "{ to: Idle, when: [ IsLocal is false ] }"]
    commit_states = []
    for x in commit_objs:
        o = x["name"]
        commit = {f"{o}/P{a}/C": f"{st}/C", f"{o}/P{a}/F": f"{st}/F"}
        for j in range(c["coarseBits"] - 8):
            commit[f"{o}/P{a}/C{j}"] = f"{st}/C{j}"
        for j in range(c["fineBits"] - 8):
            commit[f"{o}/P{a}/F{j}"] = f"{st}/F{j}"
        cs = f"Commit_{o}" if shared else "Commit"
        commit_states.append(cs)
        out.extend(state(cs, driver(copies=commit), leave))
    park = dict({f"{st}/C": 0, f"{st}/F": 0, f"{res}/C": 0, f"{res}/F": 0,
                 kacc: 0, kfloat: 0, sc: 0, sf: 0},
                **{b: 0 for b in cbools + fbools})
    out.extend(state("Parked", driver(sets=park),
                     [f"{{ to: Idle, when: [ {', '.join(wake_up(c, shared))} ] }}"]))
    out.extend(off_ladder(c, shared))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, ["Idle", "CoarseStart", "CoarseEnd", "FineStart"]
                           + commit_states + ["Parked"] +
                           [f"Settle{i}" for i in range(c["settleFrames"])]))
    return out


def full_only_comps(c):
    """The components only a full-mode object reads — everything outside the
    heading pair the shared pair layer owns."""
    return tuple(x for x in FULL_COMPS if x not in Y_COMPS)


def pair_layer(doc, c, d, shared):
    """The serial heading pair: A/X and A/Z sampled in ONE driver, walked as two
    back-to-back ladders off the frozen residuals, published by one commit.

    A heading's two components are one value, and BOTH halves of that need a
    single frame: the sampling and the publication. The parallel-plus-barrier
    shape this replaces bought publication atomicity on top of walks that
    sampled simultaneously by construction; a naive serialization keeps the
    cheap half and loses the one that matters — two samples ~13 frames apart on
    a yawing prop commit, atomically, an angle the marker never held. So
    `Start`'s one driver copies BOTH residuals, the X ladder walks its frozen
    residual, its final pair steps straight into the Z ladder's first decision
    (no hop state, no mid-ladder sense read, no second liveness gate — Idle's
    single gate covers both senses), and one Commit publishes all 24 bits.
    Against the old shape this deletes the barrier layer, its done-flags and
    their cross-layer races, at 2 + 2·rotBits + 1 frames — under the position
    ladder, so cycle time is untouched; the old README's anti-serialization
    argument priced the ladder against the wrong critical path.

    `shared` (multi-object) commits fan out per rotating object exactly like
    `position_walk`'s. Full-mode objects ride this layer for A/X + A/Z too:
    their two readings are independent values, but sharing one sample frame and
    one commit driver costs an independent pair nothing — each component's word
    group still lands whole in one frame."""
    p = c["prefix"]
    scr = "Sh" if shared else c["objects"][0]["name"]
    rot_obs = ([x for x in c["objects"] if x["rotation"] != "none"]
               if shared else [c["objects"][0]])
    lay = f"{p}/Enc/{scr}/Ry"
    sts, ress, senses, clear = {}, {}, {}, {}
    for comp in Y_COMPS:
        sts[comp] = f"{p}/S/{scr}/R{comp}"
        ress[comp] = f"{p}/R/{scr}/R{comp}"
        doc.param(f"  {sts[comp]}: {{ type: float, scratch: true }}", sts[comp])
        doc.param(f"  {ress[comp]}: {{ type: float, scratch: true }}", ress[comp])
        senses[comp] = sense_param(doc, c, f"{p}/Sense/{scr}/R{comp}")
        clear[sts[comp]] = 0
        for j in range(c["rotBits"] - 8):
            b = f"{sts[comp]}/B{j}"
            doc.param(f"  {b}: {{ type: bool, scratch: true }}", b)
            clear[b] = 0

    enter = gate(c, shared) + live(d, [senses[x] for x in Y_COMPS])
    out = [f"  - name: {lay}", "    states:"]
    out.extend(state("Idle", None,
                     [f"{{ to: Start, when: [ {', '.join(enter)} ] }}"]))
    out.extend(state("Start", driver(
        sets=clear,
        copies={ress[x]: f"{{ source: {senses[x]}, sourceMin: {num(d['rotMin'])}, "
                         f"sourceMax: {num(d['rotMax'])}, destMin: 0, destMax: 1 }}"
                for x in Y_COMPS}),
        walk_rungs(ress["A/X"], 0, "X0A", "X0R")))
    rows = emit_walk("X", c["rotBits"], ress["A/X"],
                     bit_plan(c["rotBits"], sts["A/X"],
                              [f"{sts['A/X']}/B{j}"
                               for j in range(c["rotBits"] - 8)]),
                     None, out, walk_rungs(ress["A/Z"], 0, "Z0A", "Z0R"))
    if shared:
        z_exit = [f"{{ to: Commit_{x['name']}, when: [ {p}/Slice/{x['name']} "
                  "greater 0.5 ] }" for x in rot_obs]
    else:
        z_exit = exit_when_true(c, "Commit")
    rows += emit_walk("Z", c["rotBits"], ress["A/Z"],
                      bit_plan(c["rotBits"], sts["A/Z"],
                               [f"{sts['A/Z']}/B{j}"
                                for j in range(c["rotBits"] - 8)]),
                      None, out, z_exit)
    commit_states = []
    for x in rot_obs:
        o = x["name"]
        commit = {}
        for comp in Y_COMPS:
            commit[f"{o}/R{comp}"] = sts[comp]
            for j in range(c["rotBits"] - 8):
                commit[f"{o}/R{comp}/B{j}"] = f"{sts[comp]}/B{j}"
        cs = f"Commit_{o}" if shared else "Commit"
        commit_states.append(cs)
        out.extend(state(cs, driver(copies=commit),
                         [f"{{ to: Idle, when: [ {p}/True is true ] }}"]))
    park = dict(clear, **{ress[x]: 0 for x in Y_COMPS},
                **{senses[x]: 0 for x in Y_COMPS})
    out.extend(state("Parked", driver(sets=park),
                     [f"{{ to: Idle, when: [ {', '.join(wake_up(c, shared))} ] }}"]))
    out.extend(off_ladder(c, shared))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, ["Idle", "Start"] + commit_states + ["Parked"]))
    return out


def component_walk(doc, c, d, comp, ob=None):
    """One marker component, one layer, one atomic commit per reading.

    `ob` set is the single-object full build: all six components, each an
    independent reading with its own walk — a torn set of them is a stale
    orientation, never one no marker held. `ob` None is the shared multi-object
    shape for the components ONLY a full-mode object reads (A/Y, B/*): gated on
    `Slice/FullLive` so it never climbs during a y slice, with commits fanned
    out per full-mode object only — a y object declares no words for these
    components, so a commit routed to it would copy into params that do not
    exist."""
    p = c["prefix"]
    shared = ob is None
    scr = "Sh" if shared else ob["name"]
    commit_objs = ([x for x in c["objects"] if x["rotation"] == "full"]
                   if shared else [ob])
    lay = f"{p}/Enc/{scr}/R{comp}"
    st, res = f"{p}/S/{scr}/R{comp}", f"{p}/R/{scr}/R{comp}"
    doc.param(f"  {st}: {{ type: float, scratch: true }}", st)
    doc.param(f"  {res}: {{ type: float, scratch: true }}", res)
    rbools = [f"{st}/B{j}" for j in range(c["rotBits"] - 8)]
    for nm in rbools:
        doc.param(f"  {nm}: {{ type: bool, scratch: true }}", nm)
    plan = bit_plan(c["rotBits"], st, rbools)
    clear = dict({st: 0}, **{b: 0 for b in rbools})

    out = [f"  - name: {lay}", "    states:"]
    sr = sense_param(doc, c, f"{p}/Sense/{scr}/R{comp}")
    enter = gate(c, shared, full_only=shared) + live(d, [sr])
    out.extend(state("Idle", None,
                     [f"{{ to: Start, when: [ {', '.join(enter)} ] }}"]))
    out.extend(state("Start", driver(
        sets=clear,
        copies={res: f"{{ source: {sr}, sourceMin: {num(d['rotMin'])}, "
                     f"sourceMax: {num(d['rotMax'])}, destMin: 0, destMax: 1 }}"}),
        walk_rungs(res, 0, "R0A", "R0R")))
    if shared:
        end_rungs = [f"{{ to: Commit_{x['name']}, when: [ {p}/Slice/{x['name']} "
                     "greater 0.5 ] }" for x in commit_objs]
    else:
        end_rungs = exit_when_true(c, "Commit")
    rows = emit_walk("R", c["rotBits"], res, plan, None, out, end_rungs)
    commit_states = []
    for x in commit_objs:
        o = x["name"]
        commit = {f"{o}/R{comp}": st}
        for j in range(c["rotBits"] - 8):
            commit[f"{o}/R{comp}/B{j}"] = f"{st}/B{j}"
        cs = f"Commit_{o}" if shared else "Commit"
        commit_states.append(cs)
        out.extend(state(cs, driver(copies=commit),
                         [f"{{ to: Idle, when: [ {p}/True is true ] }}"]))
    park = dict(clear, **{res: 0, sr: 0})
    out.extend(state("Parked", driver(sets=park),
                     [f"{{ to: Idle, when: [ {', '.join(wake_up(c, shared))} ] }}"]))
    out.extend(off_ladder(c, shared))
    out.append("    default: Idle")
    out.extend(walk_layout(rows, ["Idle", "Start"] + commit_states + ["Parked"]))
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
    obj_desc = ", ".join(
        f"{ob['name']} (rotation {ob['rotation']}"
        + (f", slices {ob['slices']}" if ob.get("slices", 1) != 1 else "") + ")"
        for ob in c["objects"])
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
        slots = slice_schedule(c)
        o(f"# Local measure cycle: {len(slots)} slices x {per} frames = "
          f"~{len(slots) * per / 60:.2f}s ring — each slice deactivates every other object's")
        o("#   rig, clears the SHARED sense set, settles, and only then unblocks the shared")
        o(f"#   walks. Ring (weighted, interleaved): {', '.join(slots)}.")
    o(f"# Rig park (deterministic from rigSeed '{c['rigSeed']}'): "
      f"({d['rigOffset'][0]}, {d['rigOffset'][1]}, {d['rigOffset'][2]}) m — the README's Rig section")
    o("#   is the spec the prefab is kept against. The park is the object node's transform")
    o("#   localPosition under the origin-pinned Rig; the World pin's source offset is ZERO,")
    o("#   because the client scales a source's offset by the avatar's per-client scale factor.")
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

def committed_configs():
    """The three builds with on-disk artifacts: byte-pinned controller.yaml,
    hand-maintained prefab, compiled built/. Only these feed the prefab scans,
    the committed-vs-disk pin, and main()'s disk writes."""
    out = {"committed": CONFIG}
    for name, over in PRESETS.items():
        cfg = dict(CONFIG)
        cfg.update(over)
        out[name] = cfg
    return out


def check_configs():
    """Everything the structural suite runs over: the committed builds plus the
    check-only DEMOS. A DEMO's `wire` merges shallowly onto CONFIG's (see the
    DEMOS comment for the indexLoops trap a replacement reintroduces)."""
    out = committed_configs()
    for name, over in DEMOS.items():
        cfg = dict(CONFIG)
        for k, v in over.items():
            if k == "wire":
                w = dict(CONFIG["wire"])
                w.update(v)
                cfg["wire"] = w
            else:
                cfg[k] = v
        out[name] = cfg
    return out


def check():
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    for label, cfg in check_configs().items():
        print(f"[{label}]")
        pf = cfg["prefix"]
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
        # `atomic: batch` asserted on the MACHINE, not on the header line that
        # describes it: a header comment survives any regression it names. The
        # two structural signatures are that no latch double-buffer exists (set
        # mode is the only thing that emits `<channel>/Latch/…`) and that Lost
        # re-locks at any counter value rather than only at a loop head.
        assert_(f"{cfg['channel']}/Latch/" not in text,
                "no latch params anywhere — a latch is set-atomic's double "
                "buffer and cannot exist under batch")
        assert_("re-lock at any exact counter value" in text,
                "the receiver's Lost rungs carry batch mode's any-counter "
                "re-locking, not a loop-head-only entry")

        # Every axis commits its whole word in one driver — probed inside the
        # ENCODE layer's own block, because word-channel's receiver copies the
        # same words in one driver too and would satisfy a document-wide probe
        # while the producer was writing them a limb at a time. Multi-object
        # walks are SHARED (`Enc/Sh/…`) with per-object Commit_<o> fan-outs, so
        # the probe additionally pins the routing: every rung into an object's
        # commit carries that object's own `Slice/<o>` condition — one of the
        # two guards (with the Live abandon rung) that replaced the old
        # per-object gate()/off_ladder/leave triple.
        multi = len(cfg["objects"]) > 1
        scr = "Sh" if multi else cfg["objects"][0]["name"]
        rot_names = [ob["name"] for ob in cfg["objects"]
                     if ob["rotation"] != "none"]
        full_names = [ob["name"] for ob in cfg["objects"]
                      if ob["rotation"] == "full"]

        def commit_routed(lay, o):
            rungs = [ln for ln in rung_block(text, lay).splitlines()
                     if f"to: Commit_{o}," in ln]
            return rungs and all(f"{pf}/Slice/{o} greater 0.5" in ln
                                 for ln in rungs)

        for ob in cfg["objects"]:
            o = ob["name"]
            for a in AXES:
                lay = f"{pf}/Enc/{scr}/P{a}"
                names = [f"{o}/P{a}/C", f"{o}/P{a}/F"]
                names += [f"{o}/P{a}/C{j}" for j in range(cfg["coarseBits"] - 8)]
                names += [f"{o}/P{a}/F{j}" for j in range(cfg["fineBits"] - 8)]
                assert_(one_driver_has(rung_block(text, lay), names),
                        f"{o}/P{a}: all {len(names)} words in one commit driver")
                if multi:
                    assert_(commit_routed(lay, o),
                            f"{lay}: every rung into Commit_{o} requires "
                            f"Slice/{o}")
            mode = ob["rotation"]
            if mode == "none":
                continue
            # The heading pair is one VALUE: all 24 bits of A/X + A/Z leave in
            # one driver (the pair layer's commit), or a client reconstructs an
            # angle from two measure cycles. Single-object full mode keeps a
            # walk per component instead — six independent readings.
            if multi or mode == "y":
                names = []
                for comp in Y_COMPS:
                    names.append(f"{o}/R{comp}")
                    names += [f"{o}/R{comp}/B{j}"
                              for j in range(cfg["rotBits"] - 8)]
                lay = f"{pf}/Enc/{scr}/Ry"
                assert_(one_driver_has(rung_block(text, lay), names),
                        f"{o}: all {len(names)} heading words in the pair "
                        "layer's one commit driver")
                if multi:
                    assert_(commit_routed(lay, o),
                            f"{lay}: every rung into Commit_{o} requires "
                            f"Slice/{o}")
            if mode == "full":
                comps = full_only_comps(cfg) if multi else FULL_COMPS
                for comp in comps:
                    names = [f"{o}/R{comp}"]
                    names += [f"{o}/R{comp}/B{j}"
                              for j in range(cfg["rotBits"] - 8)]
                    lay = f"{pf}/Enc/{scr}/R{comp}"
                    assert_(one_driver_has(rung_block(text, lay), names),
                            f"{o}/R{comp}: all {len(names)} words in one "
                            "commit driver")
                    if multi:
                        assert_(commit_routed(lay, o),
                                f"{lay}: every rung into Commit_{o} requires "
                                f"Slice/{o}")

        # Coherent SAMPLING, the half of heading coherence a barrier never
        # bought and a naive serialization loses: the pair layer's Start copies
        # BOTH residuals in its single driver, so the Z ladder walks a value
        # frozen in the same frame as X's — no state between Start and the
        # commit reads a sense param.
        if any(ob["rotation"] != "none" for ob in cfg["objects"]) \
                and (multi or cfg["objects"][0]["rotation"] == "y"):
            start = state_block(rung_block(text, f"{pf}/Enc/{scr}/Ry"), "Start")
            assert_(all(f"{pf}/R/{scr}/R{x}: {{ source: {pf}/Sense/{scr}/R{x}"
                        in start for x in Y_COMPS),
                    "pair layer Start samples BOTH heading residuals in one "
                    "driver frame")
            body_after = rung_block(text, f"{pf}/Enc/{scr}/Ry")
            n_copies = body_after.count(f"source: {pf}/Sense/{scr}/R")
            assert_(n_copies == 2,
                    f"pair layer reads its senses exactly once each at Start "
                    f"({n_copies} sense copies) — no mid-ladder resample")

        # Decode coherence: every word limb — bytes included — reaches the
        # decode through the SAME Floatify copy, so an axis's assembled pair
        # flips in one frame. A tree weight read straight off a byte word is a
        # fast path the copy does not delay, and that mixed-latency assembly
        # was a measured one-frame display excursion: 2 m per cell crossing,
        # ±62 m across a coarse byte boundary (emulator + shipping client).
        # The copy line is asserted VERBATIM (`B/<word>: <word>`) in BOTH
        # Floatify states, so neither a wrong source nor an Even/Odd divergence
        # can pass; and the raw-weight negative sweeps the WHOLE document, so a
        # future layer cannot reopen the fast path outside Decode.
        word_names = [w["name"] for w in facts["numberWords"]] + \
                     [w["name"] for w in facts["boolWords"]]
        flo = rung_block(text, f"{pf}/Floatify")
        for st in ("Even", "Odd"):
            blk = state_block(flo, st)
            assert_(all(f"{pf}/B/{n}: {n}" in blk for n in word_names),
                    f"Floatify {st} copies all {len(word_names)} word params "
                    "(bytes and bools), each from its own word")
            assert_(f"{pf}/B/Acquired: {cfg['channel']}/Acquired" in blk,
                    f"Floatify {st} copies {cfg['channel']}/Acquired — the "
                    "engage gate rides the decode's own latency path")
        dec = rung_block(text, f"{pf}/Decode")
        assert_(all(f"directWeight: {pf}/B/{n} }}" in dec
                    for n in (w["name"] for w in facts["numberWords"])),
                "every decode byte weight reads the Floatify copy")
        assert_(not any(f"directWeight: {n} }}" in text for n in word_names),
                "no tree weight anywhere reads a raw word param (the fast "
                "path that skews the assembly)")

        # Negative control for every one_driver_has probe (the commit-driver
        # assertions above): it must be able to fail.
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
        # The scaled-source-offset defect class: the shipping client multiplies a constraint
        # SOURCE's offset by the avatar's per-client scale factor (asset-source
        # pins included), so a park on one becomes a cross-client displacement.
        # The document must never animate a source-space offset, and the two
        # world-frame bases must fold the park so the prefab's pin can stay at
        # zero source offset.
        assert_("ParentPositionOffset" not in text,
                "no source-space offset is animated anywhere — the client "
                "scales those by per-client avatar scale")
        for ob in cfg["objects"]:
            bases = f["clips"][f"disp_{safe(ob['name'])}_base"][0]
            anchb = f["clips"][f"anch_{safe(ob['name'])}_base"][0]
            assert_(all(str(v) == num(d0["posBase"] + d0["rigOffset"][i])
                        for i, v in enumerate(bases.values()))
                    and all(str(v) == num(-cfg["range"] + cfg["cellSize"] / 2
                                          + d0["rigOffset"][i])
                            for i, v in enumerate(anchb.values())),
                    f"{ob['name']}: display and anchor bases fold the rig park "
                    "(world-frame offsets against the origin-pinned Rig)")
        assert_("freeformDirectional" not in text,
                "no freeform-directional tree anywhere (the angle lookup is gone)")
        assert_(text.count("motion: ~") > 0 and "tree: direct" in text,
                "document carries both ladder states and Direct trees")
        assert_(all(f"  - name: {cfg['prefix']}/Enc/{scr}/P{a}" in text
                    for a in AXES)
                and text.count(f"  - name: {cfg['prefix']}/Enc/") ==
                len([1 for a in AXES]) + (
                    (1 if rot_names else 0) +
                    (len(full_only_comps(cfg)) if full_names else 0)
                    if multi else
                    (1 if cfg["objects"][0]["rotation"] == "y" else 0) +
                    (len(FULL_COMPS)
                     if cfg["objects"][0]["rotation"] == "full" else 0)),
                "exactly the planned encode layers: one per axis plus the "
                "rotation set — shared once for multi, per-object for one")

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
        cleared = parked_clears(text, f"{pf}/Enc/{scr}/PX")
        want = {f"{pf}/Sense/{scr}/CX", f"{pf}/Sense/{scr}/FX",
                f"{pf}/S/{scr}/PX/C", f"{pf}/S/{scr}/PX/F",
                f"{pf}/R/{scr}/PX/C", f"{pf}/R/{scr}/PX/F",
                f"{pf}/K/{scr}/PX", f"{pf}/S/{scr}/PX/Kacc"}
        assert_(want <= cleared,
                f"{scr}/PX Parked clears staging, residual, cell index and both "
                f"sense params ({len(cleared)} params; missing {want - cleared})")
        # The barrier's Enable-drop property, re-homed: the pair layer parks on
        # Enable/Live like every walk, and its Parked driver clears the very
        # staging its commits read — so the frame Enable drops cannot publish
        # cleared staging (the AnyState rung outranks the commit rung, same
        # layer, no cross-layer flag race left to have).
        if rot_names and (multi or cfg["objects"][0]["rotation"] == "y"):
            pc = parked_clears(text, f"{pf}/Enc/{scr}/Ry")
            pwant = set()
            for x in Y_COMPS:
                pwant |= {f"{pf}/S/{scr}/R{x}", f"{pf}/R/{scr}/R{x}",
                          f"{pf}/Sense/{scr}/R{x}"}
                pwant |= {f"{pf}/S/{scr}/R{x}/B{j}"
                          for j in range(cfg["rotBits"] - 8)}
            assert_(pwant <= pc,
                    f"pair layer Parked clears both components' staging, "
                    f"residuals and senses (missing {pwant - pc})")

        # Defect B and its single-object twin: a Commit must be reachable ONLY
        # by walking every bit, and the one road out of Parked runs through the
        # re-acquisition dwell. Neither a slice entry nor an unpark may reach a
        # Commit whose staging was cleared and never recomputed. In the pair
        # layer the final pair is the SECOND ladder's (`Z…`) — a commit
        # reachable off the X ladder would publish a heading half-walked.
        plan = []
        for a in AXES:
            plan.append((f"{pf}/Enc/{scr}/P{a}", f"F{cfg['fineBits'] - 1}",
                         [f"Commit_{o}" for o in
                          (x["name"] for x in cfg["objects"])] if multi
                         else ["Commit"]))
        if rot_names and (multi or cfg["objects"][0]["rotation"] == "y"):
            plan.append((f"{pf}/Enc/{scr}/Ry", f"Z{cfg['rotBits'] - 1}",
                         [f"Commit_{o}" for o in rot_names] if multi
                         else ["Commit"]))
        if full_names:
            comps = full_only_comps(cfg) if multi else FULL_COMPS
            for comp in comps:
                plan.append((f"{pf}/Enc/{scr}/R{comp}", f"R{cfg['rotBits'] - 1}",
                             [f"Commit_{o}" for o in full_names] if multi
                             else ["Commit"]))
        for lay, last, ends in plan:
            tr = transitions_of(text, lay)
            for end in ends:
                into = {s for s, tg in tr.items() if end in tg}
                assert_(into == {last + "A", last + "R"},
                        f"{lay}: {end} reachable only from the final walk pair "
                        f"({sorted(into)})")
            assert_(tr.get("Parked") == ["Idle"],
                    f"{lay}: Parked exits only to Idle ({tr.get('Parked')})")
            # The abandon guard that replaced the per-object slice rung: every
            # shared walk layer bails to Parked the frame `Slice/Live` drops.
            if multi:
                assert_(any("to: Parked" in r and f"{pf}/Slice/Live less 0.5" in r
                            and "canTransitionToSelf: false" in r
                            for r in any_rungs(text, lay)),
                        f"{lay}: AnyState abandon rung on Slice/Live")

        # Driver hygiene over the sense params, all configs: receivers are the
        # ONLY live writers — every driver write naming a /Sense/ param is a
        # clear (`set` to 0), in a slice Enter/Parked or a walk's Parked. A
        # driver COPY into a sense param would fake liveness; with the params
        # shared, faked liveness walks one object's position into another's
        # words.
        bad_sense = [(op, dst, v) for op, dst, v in driver_ops(text)
                     if "/Sense/" in dst and not (op == "set" and v == "0")]
        assert_(not bad_sense,
                f"every driver write to a sense param is a clear-to-0 "
                f"({bad_sense[:2]})")

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
        # Plus the shared-walk additions: the ring is read off the EMITTED text
        # (weighted, interleaved, counts exact), every Enter and Parked clear
        # covers the whole shared sense union (the assertion standing between a
        # graceful wait and a cross-object publish), and Run is the sole writer
        # of Live/FullLive.
        if multi:
            tr = transitions_of(text, f"{pf}/Slice")
            slice_block = rung_block(text, f"{pf}/Slice")
            ring = [s.split("Enter_", 1)[1].rsplit("_", 1)[0]
                    for s in tr if s.startswith("Enter_")]
            want_counts = {ob["name"]: ob.get("slices", 1)
                           for ob in cfg["objects"]}
            assert_({o: ring.count(o) for o in want_counts} == want_counts,
                    f"ring carries each object exactly its weight ({ring})")
            assert_(all(ring[i] != ring[(i + 1) % len(ring)]
                        for i in range(len(ring))),
                    f"no object holds two consecutive slices, ring-wise ({ring})"
                    " — an adjacent repeat's Enter would tear down its own walk")
            union = set(sense_union(cfg))
            labels, seen = [], {}
            for o in ring:
                j = seen.get(o, 0)
                labels.append((o, j))
                seen[o] = j + 1
            full_modes = {ob["name"]: ob["rotation"] for ob in cfg["objects"]}
            any_full = "full" in full_modes.values()
            for i, (o, j) in enumerate(labels):
                gate_clip = f["clips"][f"slice_gate_{safe(o)}"][0]
                assert_(all(str(gate_clip[f"Rig/{x['name']}/{s}/GameObject.m_IsActive"])
                            == ("1" if x["name"] == o else "0")
                            for x in cfg["objects"]
                            for s in ("Coarse", "Fine", "Rot")),
                        f"slice {o}: its three subtrees live, every other object's dead")
                no, nj = labels[(i + 1) % len(labels)]
                assert_(tr.get(f"Enter_{o}_{j}") == [f"Run_{o}_{j}",
                                                     f"Enter_{no}_{nj}"],
                        f"slice {o}#{j}: entry waits for live, then yields "
                        "rather than starving")
                entry = rung_text(text, f"{pf}/Slice", f"Enter_{o}_{j}")
                assert_(all(f"{q} {eps}" in entry for q in slice_wake_params(cfg, o)),
                        f"slice {o}#{j}: unblocks only once all "
                        f"{len(slice_wake_params(cfg, o))} of its coarse and marker "
                        "receivers read live")
                esets = state_sets(slice_block, f"Enter_{o}_{j}")
                assert_(union <= set(esets) and
                        all(esets[k] == "0" for k in union),
                        f"slice {o}#{j}: Enter clears the WHOLE shared sense "
                        f"union (missing {union - set(esets)})")
                rsets = state_sets(slice_block, f"Run_{o}_{j}")
                want_run = {f"{pf}/Slice/Live": "1",
                            f"{pf}/Slice/{o}": "1"}
                if any_full:
                    want_run[f"{pf}/Slice/FullLive"] = \
                        "1" if full_modes[o] == "full" else "0"
                assert_(all(rsets.get(k) == v for k, v in want_run.items())
                        and all(rsets.get(f"{pf}/Slice/{x['name']}") ==
                                ("1" if x["name"] == o else "0")
                                for x in cfg["objects"]),
                        f"slice {o}#{j}: Run raises Live + exactly its own "
                        "Slice flag" + (" + FullLive per mode" if any_full else ""))
            psets = state_sets(slice_block, "Parked")
            assert_(union <= set(psets),
                    f"Slice Parked clears the whole shared sense union "
                    f"(missing {union - set(psets)})")
            assert_("enable_park" not in f["clips"],
                    "no enable clips at all with several objects — the Slice layer "
                    "owns m_IsActive (one property, one writer)")
            assert_(all("m_IsActive" in k
                        for k in f["clips"]["slice_gate_park"][0]),
                    "the Slice layer's parked clip is what Enable reaches the subtrees through")
            assert_(all(str(v) == "0" for v in
                        f["clips"]["slice_gate_park"][0].values()),
                    "parking the Slice layer deactivates every object's rig")

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
            # Scoped to the single-object branch where enable_park EXISTS: on a
            # multi config the old document-level spelling read `.get(...)`'s
            # empty fallback and passed vacuously.
            assert_(not any(k.startswith(("Sync", "Sync_Target"))
                            for k in park),
                    "the enable's tree reaches the measure rig only — Sync is "
                    "the Follow layer's alone, and Sync_Target is the consumer's")

        # THE FENCE, and it stays a pure negative because the correct answer
        # here really is "nothing": Sync_Target is the consumer's node — their
        # carry constraint owns its source list, a composed Drop toggle owns its
        # FreezeToWorld — and anything UNDER Sync is the consumer's own subtree.
        # Two systems animating one component is the defect the split prevents.
        surface = [k for _, (bs, _s) in f["clips"].items() for k in bs
                   if k.split("/")[0].startswith("Sync")]
        targets = {sync_target_path(cfg, ob["name"]) for ob in cfg["objects"]}
        syncs = {sync_path(cfg, ob["name"]) for ob in cfg["objects"]}
        trespass = [k for k in surface
                    if k.split("/")[0] in targets
                    or (k.split("/")[0] in syncs and "/" in k
                        and not k.split("/", 1)[1].startswith("VRCParentConstraint."))]
        assert_(not trespass,
                f"no clip binding touches Sync_Target or anything under Sync "
                f"({trespass[:2]})")

        # AN ALLOWLIST, not a blocklist. The old fence could be a pure negative
        # because the entry drove nothing on the surface; now it drives Sync's
        # two weights, so a blocklist cannot express the boundary and any
        # binding a later edit adds would pass in silence. Pin the exact set.
        want = {f"{sync_path(cfg, ob['name'])}/VRCParentConstraint.Sources."
                f"source{i}.Weight"
                for ob in cfg["objects"] for i in (0, 1)}
        assert_(set(surface) == want,
                f"the document binds EXACTLY Sync's two source weights "
                f"({sorted(set(surface) ^ want)[:2]})")

        # Totality and exclusivity over the weight pair, in one assertion: a
        # partial clip lets WD-ON strand a stale weight, and a both-zero state
        # reintroduces the measured weight-0 write (a VRCParentConstraint at
        # weight 0 writes the captured rest every frame rather than releasing).
        rides_t = f["clips"]["follow_target"][0]
        rides_r = f["clips"]["follow_recon"][0]
        assert_(set(rides_t) == set(rides_r) == want,
                "both Follow clips are total over the weight vector")
        for ob in cfg["objects"]:
            con = f"{sync_path(cfg, ob['name'])}/VRCParentConstraint.Sources"
            assert_(str(rides_t[f"{con}.source0.Weight"]) == "1"
                    and str(rides_t[f"{con}.source1.Weight"]) == "0"
                    and str(rides_r[f"{con}.source0.Weight"]) == "0"
                    and str(rides_r[f"{con}.source1.Weight"]) == "1",
                    f"{ob['name']}: exactly one source holds weight 1 in either "
                    "clip — never both zero")
            assert_(f"{con[:-8]}.GlobalWeight" not in text
                    and f"{con[:-8]}.IsActive" not in text,
                    f"{ob['name']}: Sync is never released by GlobalWeight or "
                    "IsActive — it is always active and always driven")

        # Each state rides the clip its name claims, and none of them drives a
        # validity param: the transport certifies `<channel>/Acquired` itself,
        # and a second writer here would be a second thing to keep true.
        fol = rung_block(text, f"{pf}/Follow")
        for st, clip in (("Release", "follow_target"),
                         ("Local", "follow_target"),
                         ("Follow", "follow_recon")):
            body = state_block(fol, st)
            rides = "the reconstruction" if clip.endswith("recon") else "Sync_Target"
            assert_(f"motion: {{ clip: {clip} }}" in body
                    and "behaviours:" not in body,
                    f"{st} rides {rides} and drives nothing")
        assert_("Sync_Valid" not in text,
                "no Sync_Valid anywhere: the retired name is not re-declared "
                "beside the transport's Acquired")
        acq = f"{cfg['channel']}/Acquired"
        assert_(f"  {acq}: {{ type: float, default: 0, "
                "vrc: { type: bool, synced: false, saved: false } }" in text,
                f"{acq} is declared unsynced and default false — a synced copy "
                "would carry the wearer's decode state to every client")

        rungs = any_rungs(text, f"{pf}/Follow")
        engaging = [r for r in rungs if r.startswith("- { to: Follow")]
        assert_(len(engaging) == 1
                and "IsLocal is false" in engaging[0]
                and f"{pf}/Enable greater 0.5" in engaging[0]
                and f"{pf}/B/Acquired greater 0.5" in engaging[0]
                and f"{acq} greater" not in engaging[0],
                "the one rung into Follow requires !IsLocal AND Enable AND the "
                "FLOATIFY COPY of Ch/Acquired — raw Acquired certifies in the "
                "same driver frame that writes the final batch's words, one "
                "frame ahead of their copies, so engaging on it would render "
                "the last group stale on a head-landing cold join")
        exits = [r for r in rungs if r.startswith("- { to: Release")]
        assert_(len(exits) == 1 and "Acquired" not in exits[0]
                and "Cycle" not in exits[0],
                "the one rung out of Follow tests Enable alone — with the "
                "engage rung's canTransitionToSelf: false, that is what makes "
                "Follow latch rather than drop the prop on a receiver hiccup")
        assert_(any(r.startswith("- { to: Local") and "IsLocal is true" in r
                    for r in rungs)
                and any(r.startswith("- { to: Release")
                        and f"{pf}/Enable less 0.5" in r for r in rungs),
                "the wearer takes Local on IsLocal alone, and Enable-off takes "
                "a remote to Release")
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
        assert_(f"`globalParams` is exactly `{CONFIG['prefix']}/Enable` and "
                f"`{CONFIG['channel']}/Acquired`" in body,
                "README specifies both globalParams entries — without the second "
                "a consumer cannot bind the transport's validity bool by name")
        assert_("`source0 = Sync_Target`, `source1 = Rig/<obj>/Display`" in body,
                "README pins the two Sync sources in the order the Follow layer "
                "indexes them")
        assert_("Home" not in body,
                "README carries no home/park concept either")
        # Synced cost is the wire PLUS `Enable`, and word-channel's own accounting
        # cannot see the second term — Enable is this entry's param, not the
        # transport's. Both figures are quoted in the lead and the Wire bullet,
        # so pin both to the generator rather than to a reviewer's arithmetic.
        cfacts = document(CONFIG)[1]["facts"]
        wire_bits = cfacts["wireBits"]
        assert_(f"= **{wire_bits} bits**" in body,
                f"README's Wire bullet states the {wire_bits}-bit transport wire")
        assert_(f"**{wire_bits + 1} synced bits**" in body,
                f"README's lead states {wire_bits + 1} synced bits total "
                f"(wire {wire_bits} + {CONFIG['prefix']}/Enable)")
        # The geometry pins the wire-bit pair cannot see: the 8192->4096 bump
        # measurably moved NEITHER wireBits figure, so without these a fully
        # stale README passes. Every figure is read off derive()'s output, and
        # the two squeeze weights use exact dyadic repr — num()'s 9-decimal
        # rounding would pin a value the prefab must not carry.
        gm = cfacts["geometry"]
        g_w = CONFIG["coarseHalfSpan"] / CONFIG["range"]
        for frag, why in (
                (f"±{num(CONFIG['range'])} m", "working volume"),
                (f"{CONFIG['coarseBits']}+{CONFIG['fineBits']}", "bit split"),
                (f"({num(gm['fineSpan'])} m)", "redundant fine field"),
                (f"{num(round(gm['fineLSB'] * 1000, 5))} mm", "fine LSB"),
                (repr(g_w), "squeeze weight g"),
                (repr(1 - g_w), "squeeze weight 1-g")):
            assert_(frag in body, f"README carries the current {why} ({frag})")
        # Cost accounting pinned per committed build: state/layer counts and
        # the Floatify limb count are the generator's own figures.
        dfacts = {lbl: document(cfg2)[1]["facts"]
                  for lbl, cfg2 in committed_configs().items()}
        s0, l0 = dfacts["committed"]["stateCount"], dfacts["committed"]["layerCount"]
        assert_(f"**{s0} states and {l0} layers**" in body,
                f"README's Costs states the root build's {s0}/{l0}")
        assert_(f"({dfacts['y']['stateCount']}/{dfacts['y']['layerCount']} and "
                f"{dfacts['y_double']['stateCount']}/{dfacts['y_double']['layerCount']} "
                in body,
                "README's Costs states the y and y_double state/layer counts")
        fl = dfacts["committed"]["floatifyLimbs"]
        assert_(f"({fl - 1}+1 params" in body,
                f"README's Floatify accounting matches the generator ({fl - 1}+1)")
    else:
        assert_(False, "README.md is missing")

    # The prefabs are hand-maintained, so the document pin cannot see a park
    # creeping back onto a constraint source offset — and the emulator cannot
    # either, because its SDK does not apply the shipping client's per-client
    # scaling of source offsets. Scan the committed prefabs directly: every
    # source-space offset must be exactly zero.
    print("[prefab source offsets]")
    import re as _re
    for label in committed_configs():
        pf_path = os.path.join(HERE, *preset_dir(label), "ObjectSync.prefab")
        if not os.path.exists(pf_path):
            assert_(False, f"{label}: ObjectSync.prefab is missing")
            continue
        body = open(pf_path, encoding="utf-8").read()
        offs = _re.findall(r"Parent(?:Position|Rotation)Offset: \{x: (\S+?), "
                           r"y: (\S+?), z: (\S+?)\}", body)
        bad = [o for o in offs if any(float(v) != 0 for v in o)]
        assert_(offs and not bad,
                f"{label}: all {len(offs)} source-space offsets in the prefab "
                f"are zero ({bad[:2]})")

    # A zero offset is only half the pin: the other half is that the pin still
    # RESOLVES. Both of Rig's constraints source a transform inside this entry's
    # own never-instantiated `assets/World.prefab`, and that reference is what
    # makes the frame world-absolute on every client — but nothing else in this
    # repo watches it. Break the reference and both sources resolve to null,
    # which writes nothing, so `Rig` quietly becomes avatar-relative — the one
    # failure the README calls indistinguishable from a correct rig at the
    # origin, invisible to the gate (which reads missing scripts, not missing
    # asset refs) and to any check taken at the origin.
    #
    # A reference is a `(fileID, guid)` PAIR and both halves have to be checked
    # against the asset, because a dangling reference is byte-identical to a live
    # one — nothing rewrites the referring prefab when its target breaks, so the
    # text alone can never show it. Hence three reads, not one:
    #   - the asset itself must exist (a surviving `.meta` beside a deleted
    #     `World.prefab` yields a perfectly good GUID for a dead pin),
    #   - the referenced fileID must still name a Transform inside it (overwrite
    #     the asset in place and Unity keeps the path, and so the `.meta` GUID,
    #     while assigning fresh fileIDs),
    #   - the GUID must match the `.meta`, read from there rather than written as
    #     a literal so an inconsistent churn — an Editor rewriting the package's
    #     meta without re-saving these prefabs — surfaces as a mismatch.
    # A churn that consistently rewrites meta and prefabs together passes, and
    # should: the reference still resolves.
    print("[prefab world pin resolves]")
    world_pf = os.path.join(HERE, "assets", "World.prefab")
    meta = world_pf + ".meta"
    world_guid, world_tf = None, set()
    assert_(os.path.exists(world_pf),
            "assets/World.prefab exists — a GUID outliving its asset reads "
            "exactly like a live reference")
    if os.path.exists(world_pf):
        world_tf = set(_re.findall(r"^--- !u!4 &(-?\d+)$",
                                   open(world_pf, encoding="utf-8").read(), _re.M))
    if os.path.exists(meta):
        m = _re.search(r"^guid: ([0-9a-f]{32})$", open(meta, encoding="utf-8").read(),
                       _re.M)
        world_guid = m.group(1) if m else None
    assert_(world_guid is not None,
            f"assets/World.prefab.meta carries a GUID ({world_guid})")
    assert_(bool(world_tf), f"assets/World.prefab carries a Transform ({world_tf})")
    if world_guid is not None and world_tf:
        for label in committed_configs():
            pf_path = os.path.join(HERE, *preset_dir(label), "ObjectSync.prefab")
            if not os.path.exists(pf_path):
                continue      # the missing-prefab FAIL is already reported above
            body = open(pf_path, encoding="utf-8").read()
            # `-?` because a cross-asset fileID is signed — the form an imported
            # model's transform takes. A reference shape this misses drops out of
            # the count, so an unmatched form fails loud rather than passing.
            refs = _re.findall(
                r"SourceTransform: \{fileID: (-?\d+), guid: ([0-9a-f]{32})", body)
            # Exactly two, whatever the object count: Rig is one node carrying one
            # VRCParentConstraint and one VRCScaleConstraint, and it is the
            # entry's only cross-asset source. Fewer means a reference went null.
            bad = [r for r in refs if r[1] != world_guid or r[0] not in world_tf]
            assert_(len(refs) == 2 and not bad,
                    f"{label}: Rig's 2 world-pin sources both resolve to a "
                    f"Transform in this entry's World.prefab — expected 2 of "
                    f"(fileID in {sorted(world_tf)}, {world_guid}), "
                    f"found {len(refs)}: {sorted(set(refs))}")

    # Each committed build is the one artifact its `built/` was compiled from,
    # so a generator change that moves any of the three documents is a defect
    # until that variant's built/ is recompiled.
    print("[committed vs disk]")
    for label, cfg in committed_configs().items():
        on_disk = os.path.join(HERE, *preset_dir(label), "controller.yaml")
        if os.path.exists(on_disk):
            with open(on_disk, encoding="utf-8", newline="") as fh:
                assert_(fh.read().replace("\r\n", "\n") == document(cfg)[0],
                        f"{label}: controller.yaml on disk matches its CONFIG")
        else:
            assert_(False, f"{label}: controller.yaml is missing "
                           f"({os.path.relpath(on_disk, HERE)})")
    return 0 if ok else 1


def preset_dir(label):
    """The committed full build owns the entry root; the two variants each own
    a subdirectory, so a human download can take exactly one build whole."""
    return () if label == "committed" else (label,)


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
            ops.append((op, dst.strip(), src if op == "copy" else val))
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


def state_block(layer_text, name):
    """One state's own lines out of a layer block — its motion, driver and
    transitions, and nothing of the state after it."""
    lines = layer_text.splitlines()
    try:
        i = lines.index(f"      {name}:")
    except ValueError:
        return ""
    end = next((j for j in range(i + 1, len(lines))
                if lines[j].startswith("      ") and not lines[j].startswith("       ")),
               len(lines))
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


def state_sets(layer_text, name):
    """One state's driver `set:` writes, key -> raw value string — the surface
    the clear-totality probes read (parked_clears collapses values away; these
    need them)."""
    body = state_block(layer_text, name)
    out, in_set = {}, False
    for ln in body.splitlines():
        s = ln.strip()
        if ln.startswith("              ") and not ln.startswith("               ") \
                and s.endswith(":"):
            in_set = s == "set:"
        elif in_set and ln.startswith("                ") and ":" in s:
            k, v = s.split(":", 1)
            out[k.strip()] = v.strip()
        elif s and not ln.startswith("              "):
            in_set = False
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
    for label, cfg in committed_configs().items():
        text, f = document(cfg)
        outdir = os.path.join(HERE, *preset_dir(label))
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(outdir, "controller.yaml")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        facts = f["facts"]
        print(f"wrote {os.path.relpath(out, HERE)}: {facts['stateCount']} states, "
              f"{len(f['layers'])} layers, {len(f['clips'])} clips, "
              f"{facts['wireBits']} wire bits, {facts['payloadBits']} payload bits, "
              f"{facts['batchCount']} batches, ~{facts['cycleSeconds']:.2f}s refresh "
              f"@60fps, Floatify {facts['floatifyLimbs']} limbs")


if __name__ == "__main__":
    main()
