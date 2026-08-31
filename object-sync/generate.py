#!/usr/bin/env python3
"""object-sync generator: emits the three committed controller.yaml documents
(root = full, `y/`, `y_double/`) from CONFIG + PRESETS below; DEMOS configs are
emit-only smoke (emitted, and refused where unpackable, on every change; nothing
on disk).

Edit CONFIG, rerun (`python generate.py`), recompile each touched built/ — the
three controller.yaml documents committed here are generated output: never
hand-edit one, and check freshness by regenerating and reading git diff. That
discipline covers this repo's builds only: a consumer generating into their
own project owns the emitted document, and deviating there is fine as a
commented transform in their build script, never as a silent edit. `python
generate.py
--check` pins the hand-maintained surfaces instead (prefab wiring, README
figures) plus emit determinism — nothing about the emitted document's shape,
on purpose (CONVENTIONS.md §Per-entry checks; check()'s docstring owns the
argument).

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
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- CONFIG ----

CONFIG = {
    # PUBLISHED prefix — a FROZEN interface constant, never a per-build knob.
    # One name lives under it — `Enable` — so the derived `globalParams` is the
    # single wildcard `ObjectSync/*` matching exactly that. Everything else the
    # entry declares is SEALED: it takes the VRCFury instance prefix, and a
    # consumer that must read a sealed name (`Ready`, `<channel>/Acquired`, the
    # word table) merges its own controller through the SAME FullController
    # component as this build's — one component, identical prefixing, shared
    # names unify (docs/gimmicks.md §Packaging and interface owns the idiom).
    # A second build on one avatar varies `rigSeed` below, never this.
    "prefix": "ObjectSync",
    # The transport channel root, on its own PRIVATE root deliberately: it may
    # not sit under `prefix` (word-channel certifies `<channel>/Acquired`, an
    # unpublished name a published wildcard must not reach), and it may not
    # nest under `internal` either — word-channel's fragment-level namespace
    # check treats the channel's ROOT as published, so every `OS/*` internal
    # would read as a leak to it. Sealed like `internal`: no published wildcard
    # reaches it, so it keeps the instance prefix.
    "channel": "OSCh",
    # INTERNAL prefix, required. Every param a consumer must not bind — the
    # staging walks, the decoded AAPs, the sense receivers, the slice ring, and
    # (at `<internal>/Ch`) word-channel's wire and latches. It matches no
    # published wildcard, so all of it keeps the VRCFury instance prefix, which
    # is what lets two instances coexist (docs/nondestructive.md rule 2) and
    # what stops a host avatar capturing a name it happened to declare.
    "internal": "OS",
    # The wearer-facing control's label in the expression menu.
    "menuLabel": "Object Sync",
    # Where the rig sits relative to the GameObject carrying the FullController.
    # "" is the shipped entry shape: the component rides the rig root and every
    # binding is rig-relative (`Rig/…`, `Sync`). A consumer merging this build
    # through a SHARED component (the sealed-interface coupling above) sets it
    # to the nested GO's name — e.g. "ObjectSync" for a rig at
    # `<component GO>/ObjectSync` — and every emitted binding is prefixed so it
    # resolves from the component's own GameObject without leaning on VRCFury's
    # ancestor walk-up (operator-ruled 2026-08-31: the walk-up resolves today
    # and is still not a contract to build on). The GO name and this string are
    # a hand-maintained pairing: the consumer's own --check pins them.
    "mountPath": "",
    # `Enable`'s declared default, 0 or 1: at 1 the enable tree evaluates armed
    # from frame one, where a driver forcing it true leaves the one-frame off->on
    # that deafens every receiver (README §Rig, Enable row).
    "enableDefault": 0,

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
    # The frame-rate floor the multi-object slice ring's wall-clock escapes are
    # sized at. The ring's Run windows are COMPLETION-GATED (each shared walk
    # stamps a Slice/Done/* bit at commit, and Run advances only once every walk
    # its slice's mode runs has stamped), because the walks step one state per
    # FRAME while an exitTime is wall-clock SECONDS: the pre-fix window divided
    # the frame budget by a hard-coded 60, so at ~45 fps the heading pair
    # (27 frames) still fit while the position walk (33) was beheaded by the
    # Slice/Live abandon rung at ~F3 on every cycle — heading synced, position
    # words never committed, measured in-venue (G5, 2026-08-18). This constant
    # sizes only the escape bound a slice that CANNOT finish (dead rig, fine
    # stage escaping under fast motion) yields at; below this fps that bound can
    # fire before completion again, so it is set at the unfocused-editor floor
    # rather than a client figure.
    "sliceFloorFps": 12,

    # Parks the contact cluster away from spawn-dense space, and — since the
    # published prefix froze — seeds the collision tags too (tag_set). ONE seed
    # for both, deliberately: two builds on one avatar must vary tags AND park
    # together — distinct tags with a shared park still stack ~24 receivers at
    # one point, the cluster-summing bug (docs/runtime.md §Contacts) — so a
    # separate tag seed would only make the half-varied broken state reachable.
    # A second build is this one string changed, then a regeneration.
    # Any string; the offset it derives is a rig fact the README's Rig section
    # declares. The prefab implements it as the object node's transform
    # localPosition under the origin-pinned Rig, and this generator folds it
    # into the world-frame display/anchor bases — NEVER as a constraint source
    # offset, which the shipping client scales by the avatar's per-client scale
    # factor.
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
# holding controller.yaml + built/ + prefab; `python generate.py` rewrites all
# three documents, not just the root one.
PRESETS = {
    "y": {"objects": [{"name": "Prop", "rotation": "y"}]},
    "y_double": {"objects": [{"name": "PropA", "rotation": "y"},
                             {"name": "PropB", "rotation": "y"}]},
}

# Check-only DEMO configs (operator-ruled 2026-08-17): `--check` emits each —
# nothing lands on disk (no controller.yaml, no prefab, no built/) and nothing
# is asserted beyond byte-identical regeneration. At this scale every consumer
# writes their own CONFIG; these exist so the multi-object emission the
# committed builds cannot reach (mixed rotation modes, slice weighting, widened
# slots) still runs derive()'s refusals on every change. A DEMO may override the
# `wire` block — merged SHALLOWLY onto CONFIG's, because a dict replacement
# would silently drop `indexLoops: 1` back to word-channel's default of 2,
# costing an index bit and three Sync states per batch with no diagnostic.
DEMOS = {
    # The mount emission the committed builds cannot reach (all three ship at
    # mountPath "") — every prefixed binding site runs on every --check.
    "mounted": {"mountPath": "ObjectSync"},
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


def tag_digest(seed):
    """The collision tags' per-build discriminator, from the SAME seed as the
    park (the CONFIG rigSeed comment owns why they may not vary separately)."""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6]


def mnt(c, path):
    """A binding path in the frame the FullController resolves from. mountPath
    "" is the shipped shape (component on the rig root); set, every binding is
    prefixed so the same document merges through a component on the mount GO's
    PARENT — the sealed-interface shared component — with no walk-up in play."""
    mp = c.get("mountPath", "")
    if mp and (mp != mp.strip("/") or any(ch.isspace() for ch in mp)):
        # A leading "/" is CompileController's resolve-from-avatar-root escape
        # (docs/nondestructive.md): the binding would silently change frames
        # rather than fail, so a malformed mount is refused, never normalized.
        raise SystemExit(
            f"REFUSE: mountPath {mp!r} — a bare GO path, no leading/trailing "
            "'/' and no whitespace (a leading '/' re-frames every binding to "
            "the avatar root instead of the merge component).")
    return f"{mp}/{path}" if mp else path


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


def enable_default(c):
    """`Enable`'s declared default, refused to the int 0 or 1 — the wire type is
    bool, so a fractional value blends two exclusive clips and a bool or float
    spelling emits a `default:` token the schema does not have."""
    v = c["enableDefault"]
    if v.__class__ is not int or v not in (0, 1):
        raise SystemExit(
            f"REFUSE: `enableDefault` is {v!r} — it must be the int 0 or 1, "
            "since `Enable` is a bool on the wire and default-on is `1`.")
    return v


# The reconstruction node, named by BOTH the emitted display bindings and the
# README assert below — which is what makes README §Ground truth's published read
# rename-stable rather than merely documented.
DISPLAY_NODE = "Display"


def exit_when_true(c, exit_to):
    return [f"{{ to: {exit_to}, when: [ {c['internal']}/True is true ] }}"]


# ------------------------------------------------------------- the build ----

def build(c):
    d = derive(c)
    # Through the transport's refusal, not `c["internal"]` raw: an empty string
    # reads as a prefix everywhere below while matching no published wildcard, so
    # it would emit `/Sense/...` and `/Ch/Wire/...` with every guard here blind to
    # it (check_namespaces sees root "" in no published root; the prefab assert
    # degenerates to startswith("/")). A missing key raised KeyError rather than
    # naming the fix. Every other `c["internal"]` read below is reached only
    # through this function, so refusing once here covers them.
    wcm = load_word_channel()
    p, pub = wcm.internal_prefix(c), c["prefix"]
    numbers, bools, groups = word_table(c)
    check_slots(c, numbers, bools)

    wire_config = dict(c["wire"])
    wire_config.update({
        "channel": c["channel"],
        # The channel's internals nest under THIS entry's internal prefix, so one
        # `<internal>/*` covers both. Its published side stays `channel`, which is
        # why `Ch/Acquired` needs no rename to reach the published wildcard.
        "internal": f"{c['internal']}/Ch",
        # The word table is this entry's internal staging, not an interface a
        # consumer binds: object-sync publishes a decoded pose, never wire limbs.
        # Left at its bare `<object>/…` root, where no published wildcard reaches
        # it — moving it under `internal` would make word_float compose
        # `<internal>/B/<internal>/…` across every float twin.
        "publishWords": False,
        # FIXED, not a knob: the coherence unit a grouped measurement wants is
        # the batch, and set-atomic's pause residual buys nothing here.
        "atomic": "batch",
        "numbers": numbers,
        "bools": bools,
        "assemble": [],
    })
    wc = wcm.build(wire_config)
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
    doc.param(f"  {pub}/Enable: {{ type: float, default: {enable_default(c)}, "
              "vrc: { type: bool, synced: true, saved: false } }", f"{pub}/Enable")
    # `Ready` is minted in `floatify_layer`, not here: it is that layer's copy
    # of `<channel>/Acquired`, at `<internal>/Ready` — sealed, so a consumer's
    # engage reads it through the same-component merge and it and Follow's read
    # stay one param. Both read 0 on the WEARER forever, so "is the pose on
    # screen trustworthy" is `IsLocal OR Ready`, which is what Follow's rungs
    # evaluate.

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

    params = [ln for ln in wc["params"] if ln.strip() != "IsLocal: bool"
              and not ln.strip().startswith("IsLocal:")] + doc.params
    # The fragment's own refusal saw only the fragment's params. This one runs
    # over the WHOLE merged document, which is the population a consumer's
    # globalParams actually matches against.
    declared = [m.group(1) for m in
                (re.match(r"\s*([^\s#:]+):", ln) for ln in params
                 if ln.strip() and not ln.strip().startswith("#"))
                if m and m.group(1) not in wcm.BUILTINS]
    # ONE name — the interface is sealed (operator, 2026-08-31). `Ready` and
    # `<channel>/Acquired` are declared under sealed roots, so check_namespaces
    # holds the published wildcard to exactly `Enable`: a consumer reading past
    # it merges through the same FullController component instead (CONFIG's
    # prefix comment), and an OSC consumer wanting `Ready` marks it global in
    # their own install.
    published = [f"{c['prefix']}/Enable"]
    wcm.check_namespaces(published, declared)

    return {
        "header": header(c, d, facts, numbers, bools),
        "params": params,
        "layers": layers,
        "clips": doc.clips,
        "facts": dict(facts, **{
            "published": published,
            "globalParams": wcm.published_wildcards(published),
            "mountPath": c.get("mountPath", ""),
            "collisionTags": {ob["name"]: tag_set(c, ob["name"])
                              for ob in c["objects"]},
            "rigPark": rig_offset(c["rigSeed"]),
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
    the decode's inputs on one latency path.

    That copy is `<internal>/Ready` — sealed like everything but `Enable`, and
    still the one limb here that is not scratch: a same-component consumer's
    engage and Follow's own read the same driver write and cannot drift."""
    p, pub = c["internal"], c["prefix"]
    copies = {}
    for w in numbers + bools:
        f = word_float(p, w["name"])
        doc.param(f"  {f}: {{ type: float, scratch: true }}", f)
        copies[f] = w["name"]
    # NOT scratch: the certification has to reach the params asset, and a
    # same-component consumer binding it declares THESE flags or VRCFury throws
    # at build. Under `p` since the seal — it shares the instance prefix with
    # the consumer that merges beside it, and no wildcard may reach it.
    ready = f"{p}/Ready"
    doc.param(f"  {ready}: {{ type: float, default: 0, "
              "vrc: { type: bool, synced: false, saved: false } }", ready)
    copies[ready] = f"{c['channel']}/Acquired"
    out = [f"  - name: {pub}/Floatify", "    states:"]
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
    p = c["internal"]
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
    decode. Decode weights name only `B/` copies, never a word param — why
    that matters is `floatify_layer`'s docstring.

    Display: the base clip is the FIRST child of each axis's run so the
    running sum never leaves the working range — float32's ulp at range is
    this design's precision floor already."""
    p, pub = c["internal"], c["prefix"]
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
        anch = mnt(c, f"Rig/{o}/Fine/Anchor/VRCPositionConstraint.PositionOffset")
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

        disp = mnt(c, f"Rig/{o}/{DISPLAY_NODE}/VRCPositionConstraint.PositionOffset")
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
                node = mnt(c, f"Rig/{o}/Recon/Proxy{mk}/Transform.m_LocalPosition")
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
            node = mnt(c, f"Rig/{o}/Recon/ProxyA/Transform.m_LocalPosition")
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
    out = [f"  - name: {pub}/Decode", "    states:"]
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
    p, pub = c["internal"], c["prefix"]
    if len(c["objects"]) > 1:
        return None
    park, live = {}, {}
    for sub in ("Coarse", "Fine", "Rot"):
        b = mnt(c, f"Rig/{c['objects'][0]['name']}/{sub}/GameObject.m_IsActive")
        park[b], live[b] = 0, 1
    return ["- tree: 1d",
            "  name: EnableGate",
            f"  param: {pub}/Enable",
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

    The engage rung reads `Acquired` through its Floatify copy, never raw. The
    receiver certifies `Acquired` in the same driver that applies the final
    batch's words, so the raw param leads the decode's `B/` inputs by one frame
    — engaging on it renders the last group stale for the certifying frame of a
    head-landing cold join. The copy puts the gate on the decode's own latency
    path; `floatify_layer`'s docstring carries the mechanism.

    That copy is `<internal>/Ready` — sealed, read by a consumer through the
    same-component merge, so their engage still reads the same param — at the
    price that one spurious true frame on this AnyState rung latches for the
    session, the driver's every-frame rewrite notwithstanding.

    Releasing does not test `Acquired` — its only exit tests `Enable` alone, and
    the engage rung is an AnyState rung with `canTransitionToSelf: false`, which
    together are what make `Follow` LATCH: once engaged it stays engaged until
    Enable goes off, so a receiver falling to `Lost` mid-session does not drop
    the prop back to its target. Do not add a rung here without deciding what
    that does to the latch. The same latching is why flipping `Enable` on with a
    table already acquired snaps immediately instead of waiting a cycle —
    `Enable` never gated the wire, so the receiver keeps decoding through the
    toggle and `Acquired` stays true across it. Intended."""
    p, pub = c["internal"], c["prefix"]
    rides_target, rides_recon = {}, {}
    for ob in c["objects"]:
        s = mnt(c, f"{sync_path(c, ob['name'])}/VRCParentConstraint.Sources")
        rides_target[f"{s}.source0.Weight"] = 1
        rides_target[f"{s}.source1.Weight"] = 0
        rides_recon[f"{s}.source0.Weight"] = 0
        rides_recon[f"{s}.source1.Weight"] = 1
    target_clip = doc.clip("follow_target", rides_target)
    recon_clip = doc.clip("follow_recon", rides_recon)
    out = [f"  - name: {pub}/Follow", "    states:"]
    out.extend(state("Release", None, None, motion=f"{{ clip: {target_clip} }}"))
    out.extend(state("Local", None, None, motion=f"{{ clip: {target_clip} }}"))
    out.extend(state("Follow", None, None, motion=f"{{ clip: {recon_clip} }}"))
    out.extend([
        "    any:",
        "      - { to: Local, when: [ IsLocal is true ], canTransitionToSelf: false }"
        "   # the wearer's pose is authoritative from frame 1",
        f"      - {{ to: Follow, when: [ IsLocal is false, {pub}/Enable greater 0.5, "
        f"{p}/Ready greater 0.5 ], canTransitionToSelf: false }}"
        "   # a complete word table has landed on THIS client, read through the"
        " Floatify copy so the gate, a same-component consumer's gate and the"
        " decode inputs all share one latency path",
        f"      - {{ to: Release, when: [ IsLocal is false, {pub}/Enable less 0.5 ], "
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
    p = c["internal"]
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
    p = c["internal"]
    ob = next(x for x in c["objects"] if x["name"] == o)
    return ([f"{p}/Sense/Sh/C{a}" for a in AXES] +
            [f"{p}/Sense/Sh/R{comp}" for comp in rot_comps(ob["rotation"])])


def slice_done_param(c, walk):
    """The completion stamp one shared walk leaves for the Slice layer —
    written 1 by that walk's Commit_<o> drivers, cleared by every slice Enter
    and by the Slice layer's Parked."""
    return f"{c['internal']}/Slice/Done/{walk}"


def slice_done_walks(c, mode=None):
    """The shared walks a slice must see commit before it may hand off —
    keyed by the walk's layer tail (`P<axis>`, `Ry`, `R<comp>`). Position is
    every mode's; the heading pair joins for any rotating mode; the full-only
    component walks join for full. `mode` None is the union over the config's
    modes — the mint/clear set."""
    walks = [f"P{a}" for a in AXES]
    modes = ({ob["rotation"] for ob in c["objects"]} if mode is None
             else {mode})
    if modes - {"none"}:
        walks.append("Ry")
    if "full" in modes:
        walks += [f"R{comp}" for comp in full_only_comps(c)]
    return walks


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
    p, pub, d = c["internal"], c["prefix"], derive(c)
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
    for w in slice_done_walks(c):
        dp = slice_done_param(c, w)
        doc.param(f"  {dp}: {{ type: bool, scratch: true }}", dp)
        blocked[dp] = 0
    # The Run window is COMPLETION-GATED: the walks step one state per FRAME
    # while an exitTime is wall-clock SECONDS, so any fixed dwell is a frame
    # budget divided by an assumed fps — the pre-fix /60.0 beheaded the
    # position walk mid-fine-ladder at every fps under ~58 (the Slice/Live
    # abandon rung fired first), which read as heading synced, position words
    # zero forever. Run now advances when every walk its slice's mode runs has
    # stamped its Slice/Done/* bit, frame-true at any fps; the wall-clock
    # escapes below remain only as the yield bound on a slice that CANNOT
    # finish — a rig that never wakes (skip) or walks that never converge
    # (hold: fine stage escaping under fast motion) — sized at sliceFloorFps,
    # where they cost nothing in normal operation.
    hold = num(round((max_walk_frames(c) + c["settleFrames"] + 4)
                     / c["sliceFloorFps"], 4))
    skip = num(round((max_walk_frames(c) + c["settleFrames"] + 4)
                     / c["sliceFloorFps"], 4))

    slots = slice_schedule(c)
    seen = {o: 0 for o in names}
    labels = []
    for o in slots:
        labels.append((o, seen[o]))
        seen[o] += 1
    out = [f"  - name: {pub}/Slice", "    states:"]
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
        done_terms = ", ".join(f"{slice_done_param(c, w)} is true"
                               for w in slice_done_walks(c, mode[o]))
        out.extend(state(
            f"Run_{o}_{j}",
            driver(sets=run_sets),
            [f"{{ to: Enter_{no}_{nj}, when: [ {done_terms} ] }}"
             "   # completion-gated: every walk this mode runs has committed",
             f"{{ to: Enter_{no}_{nj}, when: [], exitTime: {hold} }}"
             "   # dead-slice yield bound only (walks that cannot finish); "
             "the gate clip declares its length, so exitTime is seconds"],
            motion=motion))
    first_o, first_j = labels[0]
    out.extend(state("Parked", driver(sets=blocked),
                     [f"{{ to: Enter_{first_o}_{first_j}, when: [ {pub}/Enable greater 0.5 ] }}"],
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
        g.append(f"{c['internal']}/Slice/Live greater 0.5")
    if full_only:
        g.append(f"{c['internal']}/Slice/FullLive greater 0.5")
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
    p, pub = c["internal"], c["prefix"]
    out = ["    any:",
           f"      - {{ to: Parked, when: [ {pub}/Enable less 0.5 ], "
           "canTransitionToSelf: false }"]
    if shared:
        out.append(f"      - {{ to: Parked, when: [ {p}/Slice/Live "
                   "less 0.5 ], canTransitionToSelf: false }")
    return out


def wake_up(c, shared):
    """The conditions that let a Parked encode layer start climbing again."""
    up = [f"{c['prefix']}/Enable greater 0.5"]
    if shared:
        up.append(f"{c['internal']}/Slice/Live greater 0.5")
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


def tag_set(c, o):
    """Contact collision tags for one object's sender groups — only the groups
    that object's rotation mode gives a carrier: a tag the prefab cannot carry
    is a spec-vs-artifact lie waiting for a reviewer.

    Deterministic from the frozen prefix plus `rigSeed`'s digest and — when
    there is more than one object — the object name. The seed term is what lets
    two sealed builds coexist on one avatar (the prefix froze, so it can no
    longer discriminate), and it is the park's own seed on purpose: tags and
    park must vary together (CONFIG's rigSeed comment). Per-object stays for a
    sharper, measured reason: two objects on one tag set, NEITHER converges,
    because every receiver reads whichever sender is strongest rather than its
    own."""
    base = c["prefix"].replace("/", "") + tag_digest(c["rigSeed"])
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
            b[mnt(c, f"Rig/{x}/{sub}/GameObject.m_IsActive")] = 1 if x == live_object else 0
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
    p, pub = c["internal"], c["prefix"]
    shared = ob is None
    scr = "Sh" if shared else ob["name"]
    commit_objs = c["objects"] if shared else [ob]
    lay = f"{pub}/Enc/{scr}/P{a}"
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
        done = ({slice_done_param(c, f"P{a}"): 1} if shared else None)
        out.extend(state(cs, driver(sets=done, copies=commit), leave))
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
    p, pub = c["internal"], c["prefix"]
    scr = "Sh" if shared else c["objects"][0]["name"]
    rot_obs = ([x for x in c["objects"] if x["rotation"] != "none"]
               if shared else [c["objects"][0]])
    lay = f"{pub}/Enc/{scr}/Ry"
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
        done = ({slice_done_param(c, "Ry"): 1} if shared else None)
        out.extend(state(cs, driver(sets=done, copies=commit),
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
    p, pub = c["internal"], c["prefix"]
    shared = ob is None
    scr = "Sh" if shared else ob["name"]
    commit_objs = ([x for x in c["objects"] if x["rotation"] == "full"]
                   if shared else [ob])
    lay = f"{pub}/Enc/{scr}/R{comp}"
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
        done = ({slice_done_param(c, f"R{comp}"): 1} if shared else None)
        out.extend(state(cs, driver(sets=done, copies=commit),
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
          f"~{len(slots) * per / 60:.2f}s ring @60fps — each slice deactivates every other")
        o("#   object's rig, clears the SHARED sense set, settles, unblocks the shared walks,")
        o("#   and hands off when they have COMMITTED (frame-true at any fps; a slice whose")
        o(f"#   walks cannot finish yields after {(max_walk_frames(c) + c['settleFrames'] + 4) / c['sliceFloorFps']:.2f}s, sized at {c['sliceFloorFps']} fps).")
        o(f"#   Ring (weighted, interleaved): {', '.join(slots)}.")
    o(f"# Rig park (deterministic from rigSeed '{c['rigSeed']}'): "
      f"({d['rigOffset'][0]}, {d['rigOffset'][1]}, {d['rigOffset'][2]}) m — the README's Rig section")
    o("#   is the spec the prefab is kept against. The park is the object node's transform")
    o("#   localPosition under the origin-pinned Rig; the World pin's source offset is ZERO,")
    o("#   because the client scales a source's offset by the avatar's per-client scale factor.")
    o(f"# Interface: SEALED — globalParams covers {p}/Enable alone; every other param takes the")
    o("#   VRCFury instance prefix. A consumer reading past it (Ready, the channel, the word")
    o("#   table) merges its controller through the SAME FullController component as this build:")
    o("#   one component prefixes identically, so the shared names unify; a second component is")
    o("#   a second sealed instance (that is what two builds on one avatar are).")
    if c.get("mountPath"):
        o(f"# Mount: every binding is prefixed {c['mountPath']}/ — the FullController carrying this")
        o("#   document sits on that GO's PARENT (the shared merge component), and the GO's name")
        o("#   and the prefix are a hand-maintained pairing the consumer's own --check pins.")
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
    """The hand-maintained surfaces no compile or gate reads — the prefabs'
    wiring and cross-asset pins, the README's quoted figures — plus the emit
    determinism that makes regenerate-and-read-git-diff a valid freshness
    instrument. Deliberately nothing else: freshness of the committed
    documents is regen + git diff, and nothing here asserts the emitted
    document's shape — the document is a pure function of this file, so a
    shape assert is rewritten by the very edit it would catch (measured,
    across a full composition build, at zero of five shipped defects found
    while its green output was cited as verification evidence). CONVENTIONS.md
    §Per-entry checks is the standard; a rule that generalizes lives in
    ControllerRules, where CompileController's graph-lint stage already
    refuses the compile (driver-on-animated-param, which this file once
    re-implemented in Python, is the worked instance)."""
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    # Determinism over every config, DEMOS included: the multi-object emission
    # the committed builds cannot reach is still emitted on every change —
    # derive() refuses an unpackable config loudly — and a nondeterministic
    # emit would make every regen diff read as drift.
    for label, cfg in check_configs().items():
        print(f"[{label}]")
        text, f = document(cfg)
        assert_(document(cfg)[0] == text, "regeneration is byte-identical")
        facts = f["facts"]
        print(f"  wire {facts['wireBits']} bits / {facts['payloadBits']} payload / "
              f"{facts['batchCount']} batches / ~{facts['cycleSeconds']:.2f}s refresh")

    # Per-object collision tags land in the HAND-MAINTAINED prefabs, and two
    # objects on one tag set is measured-broken — a config edit that collides
    # them regenerates green and ships a defect regeneration cannot fix.
    for label, cfg in committed_configs().items():
        tags = [tag_set(cfg, ob["name"]) for ob in cfg["objects"]]
        flat = [t for group in tags for t in group]
        assert_(len(set(flat)) == len(flat),
                f"{label}: collision tags are unique across objects and stages ({flat})")

    # `globalParams` is a VRCFury field with no CompileController spelling, so
    # the document cannot carry it and the README is where it is specified for
    # the prefab. Assert the line exists rather than letting it drift silently.
    print("[README]")
    readme = os.path.join(HERE, "README.md")
    if os.path.exists(readme):
        body = open(readme, encoding="utf-8").read()
        want_gp = document(CONFIG)[1]["facts"]["globalParams"]
        assert_(f"`globalParams` is exactly `{'`, `'.join(want_gp)}`" in body,
                f"README quotes the derived globalParams list ({', '.join(want_gp)}) "
                "— a consumer reads it from there to bind the interface")
        assert_(f"`source0 = Sync_Target`, `source1 = Rig/<obj>/{DISPLAY_NODE}`"
                in body,
                "README pins the two Sync sources in the order the Follow layer "
                "indexes them")
        # The assert above reads DISPLAY_NODE, so renaming the node breaks it —
        # which is what lets README §Ground truth publish that path as a read.
        # Below: the Rig table states the default in prose no figure reaches.
        want_ed = ("unsaved and default-off" if enable_default(CONFIG) == 0
                   else "unsaved and default-on")
        assert_(f"**{want_ed}**" in body,
                f"README's Rig table states the shipped Enable default "
                f"(`enableDefault` = {enable_default(CONFIG)} -> {want_ed})")
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

    # A build's prefab text, plus its base's when the build is a VARIANT. A variant serialises only
    # its overrides, so scanning its own file alone sees a fraction of the wiring: the world-pin
    # assert below reads zero cross-asset refs there and the offset assert passes over ~8% of the
    # offsets it covered when every build was a flat copy. Both scan the union instead, which is the
    # honest population for the proposition each makes - the pin THIS BUILD SHIPS resolves, and every
    # offset THIS BUILD SHIPS is zero - whether the node is authored here or inherited.
    #
    # A variant's base must be this entry's own root prefab. That is the inheritance the entry now
    # ships (README §Rig), and a variant pointing anywhere else is a wiring defect of exactly the
    # class these asserts exist to catch, so it fails loud rather than silently scanning less.
    def prefab_texts(label, pf_path):
        import re as _re2
        own = open(pf_path, encoding="utf-8").read()
        src = _re2.search(r"m_SourcePrefab: \{fileID: \d+, guid: ([0-9a-f]{32})", own)
        if src is None:
            return [own], "authored flat"
        root_meta = os.path.join(HERE, "ObjectSync.prefab.meta")
        root_guid = None
        if os.path.exists(root_meta):
            m2 = _re2.search(r"^guid: ([0-9a-f]{32})$", open(root_meta, encoding="utf-8").read(), _re2.M)
            root_guid = m2.group(1) if m2 else None
        assert_(src.group(1) == root_guid,
                f"{label}: is a prefab variant of THIS entry's root prefab "
                f"(base guid {src.group(1)}, entry root {root_guid})")
        if src.group(1) != root_guid:
            return [own], "variant of an unknown base"
        return [own, open(os.path.join(HERE, "ObjectSync.prefab"), encoding="utf-8").read()], \
               "variant, so counted with the base it inherits"

    # `globalParams` is a VRCFury field with no CompileController spelling, so no
    # compile and no gate reads it, and a wrong entry lands in silence. The
    # expectation is DERIVED from the published set (build() has already refused a
    # layout the wildcards cannot express exactly), so adding an internal param
    # never needs a prefab edit.
    print("[prefab globalParams]")
    for label, cfg in committed_configs().items():
        pf_path = os.path.join(HERE, *preset_dir(label), "ObjectSync.prefab")
        if not os.path.exists(pf_path):
            assert_(False, f"{label}: ObjectSync.prefab is missing")
            continue
        body_pf = open(pf_path, encoding="utf-8").read()
        want = document(cfg)[1]["facts"]["globalParams"]
        got, inside = [], False
        for ln in body_pf.splitlines():
            if ln.strip() == "globalParams:":
                inside = True
            elif inside:
                if ln.strip().startswith("- "):
                    got.append(ln.strip()[2:].strip().strip("'"))
                else:
                    break
        assert_(got == want,
                f"{label}: globalParams == the published prefix wildcards "
                f"({', '.join(want)}) — got {got}")
        assert_(not any(x.startswith(cfg["internal"] + "/") for x in got),
                f"{label}: no {cfg['internal']}/ entry reaches globalParams — the "
                "walks, the wire and the sense receivers stay instance-prefixed")

    # The sense receivers are SDK components whose `parameter` field is
    # hand-maintained in the prefab, and VRCFury rewrites one only when the name
    # is a declared param of the merged controller
    # (FullControllerBuilder.RewriteParamName). So a receiver left on a stale name
    # is not renamed, writes a bare orphan, and the walk reads zero — no build
    # error, and a symptom indistinguishable from a contact that never fires.
    # Subset rather than equality per build: `y` serialises none of its own and
    # inherits the root's, removing the rig nodes for the components it does not
    # use, while the root is an exact match and so covers the inherited set.
    print("[prefab sense receivers]")
    for label, cfg in committed_configs().items():
        pf_path = os.path.join(HERE, *preset_dir(label), "ObjectSync.prefab")
        if not os.path.exists(pf_path):
            continue      # the missing-prefab FAIL is already reported above
        own = open(pf_path, encoding="utf-8").read()
        # UNFILTERED: anchoring this scan on the current internal prefix made it
        # blind to exactly the defect it exists to catch — a receiver left on a
        # stale name simply fell out of the scan and reported no stray. Every
        # `parameter:` field is read, and the test is membership in the whole
        # declared param set, so a receiver naming anything the document does not
        # declare fails whatever prefix it carries.
        raw = re.findall(r"parameter: (\S+)", own)
        declared_all = set(re.findall(r"^  ([^\s#:]+):", document(cfg)[0], re.M))
        strays = sorted(set(raw) - declared_all)
        assert_(not strays,
                f"{label}: every contact receiver names a param this build "
                f"declares ({len(raw)} fields, {len(set(raw))} distinct) — "
                f"undeclared: {strays}")
        # Coverage, the other direction: the root authors one receiver per declared
        # sense param, so a param that gained no receiver is caught here. Only the
        # root — a variant serialises a subset and removes the rig nodes for the
        # rest, which makes equality dishonest there (`y` authors none at all).
        pre = f"{cfg['internal']}/Sense/"
        if label == "committed":
            sense_fields = set(x for x in raw if x.startswith(pre))
            sense_declared = set(x for x in declared_all if x.startswith(pre))
            assert_(sense_fields == sense_declared,
                    f"the root prefab's receivers cover its declared sense set "
                    f"({len(sense_declared)}) — missing "
                    f"{sorted(sense_declared - sense_fields)}")

    # Under the sealed interface the park and the collision tags are the ONLY
    # things that vary between two builds on one avatar (the parameters froze),
    # and both are hand-maintained prefab↔config pairings nothing else reads:
    # the tags are strings VRCFury's prefixing does not reach, and the park is
    # a plain transform localPosition the document pin cannot see. A pairing
    # that drifts regenerates green and ships the measured-broken states — two
    # builds' receivers reading each other's senders (shared tag), or ~24
    # receivers summing at one point (shared park, docs/runtime.md §Contacts).
    import re as _re
    print("[prefab park + collision tags]")

    def prefab_blocks(body):
        """(class-id, object-id, block-text) per serialized object."""
        out = []
        for part in body.split("--- !u!")[1:]:
            m = _re.match(r"(\d+) &(-?\d+)", part)
            if m:
                out.append((m.group(1), m.group(2), part))
        return out

    def named_transform_positions(texts, name):
        """Every m_LocalPosition of a GameObject named `name`, over the union
        of a build's own text and its variant base's."""
        found = []
        for body in texts:
            blks = prefab_blocks(body)
            gids = [oid for cls, oid, blk in blks
                    if cls == "1" and f"\n  m_Name: {name}\n" in blk]
            for cls, oid, blk in blks:
                if cls != "4":
                    continue
                gm = _re.search(r"m_GameObject: \{fileID: (-?\d+)\}", blk)
                if gm and gm.group(1) in gids:
                    pm = _re.search(r"m_LocalPosition: \{x: (\S+?), y: (\S+?), "
                                    r"z: (\S+?)\}", blk)
                    if pm:
                        found.append(tuple(float(v) for v in pm.groups()))
        return found

    for label, cfg in committed_configs().items():
        pf_path = os.path.join(HERE, *preset_dir(label), "ObjectSync.prefab")
        if not os.path.exists(pf_path):
            continue      # the missing-prefab FAIL is already reported above
        texts, how = prefab_texts(label, pf_path)
        derived = [t for ob in cfg["objects"] for t in tag_set(cfg, ob["name"])]
        found_tags = []
        for body in texts:
            for m in _re.finditer(r"collisionTags:\n((?:  - .+\n)+)", body):
                found_tags += _re.findall(r"  - (\S+)", m.group(1))
        missing = [t for t in derived if t not in set(found_tags)]
        assert_(not missing,
                f"{label}: the prefab carries every tag tag_set() derives "
                f"[{how}] — missing {missing}")
        # A variant's union scan reads the base's authored contacts too (`y`
        # deletes the RotB rig nodes but the base text keeps their components),
        # so the honest stray population for a variant includes the base
        # build's own derived set.
        allowed = set(derived)
        if how != "authored flat":
            allowed |= {t for ob in CONFIG["objects"]
                        for t in tag_set(CONFIG, ob["name"])}
        strays = sorted(set(found_tags) - allowed)
        assert_(not strays,
                f"{label}: no contact carries a tag outside the derived set "
                f"({len(set(found_tags))} distinct) — strays: {strays}")
        # The park: every object node's own transform sits at rig_offset, and a
        # variant may not override it — a modification row is a second author.
        want = tuple(float(v) for v in rig_offset(cfg["rigSeed"]))
        for ob in cfg["objects"]:
            got = named_transform_positions(texts, ob["name"])
            assert_(got and all(g == want for g in got),
                    f"{label}: {ob['name']}'s transform parks at "
                    f"rig_offset(rigSeed) {want} [{how}] — found {got}")
        # A variant override is a second author the union scan above cannot
        # see (it reads the base's authored value): flag a modification row
        # repositioning an OBJECT NODE's transform — the park carriers,
        # located by name in the base — or touching any tag list. The instance
        # ROOT's own localPosition overrides are ordinary variant placement.
        if how != "authored flat" and len(texts) > 1:
            base_blks = prefab_blocks(texts[1])
            park_gids = [oid for cls, oid, blk in base_blks if cls == "1"
                         and any(f"\n  m_Name: {ob['name']}\n" in blk
                                 for ob in cfg["objects"])]
            park_tids = [oid for cls, oid, blk in base_blks if cls == "4"
                         and (m2 := _re.search(
                             r"m_GameObject: \{fileID: (-?\d+)\}", blk))
                         and m2.group(1) in park_gids]
            mods = _re.findall(r"target: \{fileID: (-?\d+)[^}]*\}\s*\n\s*"
                               r"propertyPath: ([^\n]+)", texts[0])
            bad_mods = [(t, pth) for t, pth in mods
                        if (t in park_tids and pth.startswith("m_LocalPosition"))
                        or pth.startswith("collisionTags")]
            assert_(not bad_mods,
                    f"{label}: the variant overrides no park or tag "
                    f"(m_Modifications rows: {sorted(set(bad_mods))})")
        # The committed builds ship the FullController on the rig root, so a
        # committed config that grew a mount prefix has broken every binding.
        assert_(cfg.get("mountPath", "") == "",
                f"{label}: committed builds emit at mountPath \"\" — a mounted "
                "build is a consumer generation, never committed here")

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
        texts, how = prefab_texts(label, pf_path)
        offs = []
        for body in texts:
            offs += _re.findall(r"Parent(?:Position|Rotation)Offset: \{x: (\S+?), "
                                r"y: (\S+?), z: (\S+?)\}", body)
        bad = [o for o in offs if any(float(v) != 0 for v in o)]
        assert_(offs and not bad,
                f"{label}: all {len(offs)} source-space offsets in the prefab "
                f"are zero [{how}] ({bad[:2]})")

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
            texts, how = prefab_texts(label, pf_path)
            # `-?` because a cross-asset fileID is signed — the form an imported
            # model's transform takes. A reference shape this misses drops out of
            # the count, so an unmatched form fails loud rather than passing.
            refs = []
            for body in texts:
                refs += _re.findall(
                    r"SourceTransform: \{fileID: (-?\d+), guid: ([0-9a-f]{32})", body)
            # Exactly two, whatever the object count: the prefab ROOT is one node
            # carrying one VRCParentConstraint and one VRCScaleConstraint, and it
            # is the entry's only cross-asset source. Fewer means a reference went
            # null. A variant authors neither and inherits both, so the two are
            # found in the base — which is why the count is over the union.
            bad = [r for r in refs if r[1] != world_guid or r[0] not in world_tf]
            assert_(len(refs) == 2 and not bad,
                    f"{label}: the root's 2 world-pin sources both resolve to a "
                    f"Transform in this entry's World.prefab — expected 2 of "
                    f"(fileID in {sorted(world_tf)}, {world_guid}), "
                    f"found {len(refs)} [{how}]: {sorted(set(refs))}")

    print("scope: emit determinism and hand-maintained wiring only — freshness "
          "of committed generated files is regenerate-and-read-git-diff; "
          "document structure, prefab behavior and runtime are unverified here")
    return 0 if ok else 1


def preset_dir(label):
    """The committed full build owns the entry root; the two variants each own
    a subdirectory, so a human download can take exactly one build whole."""
    return () if label == "committed" else (label,)


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
