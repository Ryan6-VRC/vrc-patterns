#!/usr/bin/env python3
"""contact-radar generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ in a mounting Editor —
the controller.yaml committed here is generated output and the repo gate holds
built/ to it, so hand-editing it desynchronises the document from both this
generator and the compiled controller. `--check` asserts the hand-maintained
prefab surface no compile or gate reads (README §Verifying).

What it builds: K per-sender "slots", one FX layer each. A slot is three
coincident face-proximity box receivers (X+, Y+, Z+) whose `allowOthers` flag is
the latch: a sender whose overlap with a receiver began while the flag was shut
stays invisible to that receiver for the whole overlap, however the flag moves
later, and only a full exit and re-entry admits it (emulator-measured, README
§How it works). Exactly one slot is Open (flag up) at a time; the others are
Armed (flag shut) so hands already inside are blind to them. When the Open slot
reads a hand it Latches (flag shut, boxes expanded to the hold cube) and the
next Armed slot in ring order Opens in the same animator evaluation, so the
two land in one collision step and the admission windows tile. The latched
slot then reconstructs its hand's position exactly (box-tracker's readout,
three boxes and a configured sender radius) and computes r² = x²+y²+z² in a
piecewise-linear lookup; the burst fires when r² crosses the burst radius.

Two modes, one flag: `dwell` keeps the slot until the hand leaves the hold cube
and re-bursts each time it crosses back inside the burst radius after retreating
past the re-arm radius; `entry` releases the slot at the burst, so the hand has
to leave the acquisition cube and come back for another. A released slot
Recycles: its boxes collapse to near zero for `stepSeconds` and restore with the
flag shut, a fresh overlap episode that rejects every hand still inside
(measured), then it queues as Armed.

Rules the emitted document keeps, each bought by a measurement or a doc line:
- Every step-spanning dwell is authored in seconds >= 2/60: the collision scene
  steps at most 60 times a second and a collapse or stow shorter than a step is
  skipped silently (docs/runtime.md §Contacts).
- Every slot state writes every flag (Open, Armed) and the burst toggle, zeros
  included: an AAP holds its last clip-written value and a scene binding holds
  whatever last wrote it (docs/runtime.md §Animator evaluation).
- The burst states carry the readout tree: the buffer spawns where Output sits
  on the frame it enables, and only a tree state keeps writing that position.
- Latch writes x, y, z to holdHalf so the first r² computed in TrackOut is
  3h², far outside the sphere; the guard is the state sequence, no settle AAP.
- Timed dwells are plain clips, never a curve inside a Direct tree (the tree's
  duration is data — docs/animator-schema.md §motions).
- Recycle's collapse/restore takes stepped tangents; a bare curve eases.
- The parameter driver lives only in Disabled (off-state hygiene, localOnly false:
  every client zeroes its own receiver floats).
- An admission can land on some of a slot's three coincident boxes and not the
  others when the overlap begins on the very frame the slot opens (measured), and
  a slot holding a partial reading can never satisfy the three-way Latch — so
  Open steps aside to Partial on any single reading and Recycles a step later if
  the other two never arrive. An Open slot that stalls blocks every admission on
  the avatar; the recycled hand is merely invisible until it re-enters.
- One rung fires per frame per layer; the ring rule's exclusivity rests on
  every rung also requiring the slot's OWN Armed flag, which is one frame stale:
  a slot that entered Armed this frame is skipped by its neighbours (they read
  its Armed as 0) and skips itself (it reads its own as 0), so two slots can
  never open on one firing.

Fragment mode: `document(overrides)` returns the document text and a facts
dict; `entry-mode/generate.py` is the second consumer.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "controller": "ContactRadar_Fx",
    "mode": "dwell",            # dwell | entry
    "K": 4,                     # slots; each is one layer and 3 receivers
    "tags": ["HandR"],
    "acqHalf": 0.9,             # acquisition cube half-extent, m (entry mode's re-arm surface)
    "holdHalf": 1.0,            # hold cube half-extent, m — h in the readout
    "burstRadius": 0.6,         # R_in, m
    "rearmRadius": 0.7,         # R_out, m (dwell only)
    "senderRadius": 0.05,       # r, m — the hand sender's radius; a capsule reads as a constant bias
    "stepSeconds": 0.035,       # every step-spanning dwell; >= 2 collision steps
    "lookupSegments": 16,       # x² table resolution over [-h, h]
    "epsilon": 1e-5,            # the any-box loss floor
    "boxSize": 1.0,             # the receiver box `size` on every axis; the Boxes scale multiplies it
    "prefix": "CR",             # internal param namespace; never published
    "enable": "ContactRadar/Enable",
}


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def fmt(v):
    return format(float(v), ".9g")


def lint(c):
    if c["mode"] not in ("dwell", "entry"):
        refuse("mode must be dwell or entry")
    if c["K"] < 2:
        refuse("K must be >= 2 — one slot has nothing to hand off to")
    if c["holdHalf"] < c["acqHalf"]:
        refuse("holdHalf must be >= acqHalf — the latch expands, never shrinks")
    if c["burstRadius"] + c["senderRadius"] >= c["acqHalf"]:
        refuse("burstRadius + senderRadius must be < acqHalf — the burst must be reachable inside the cube")
    if c["mode"] == "dwell":
        if c["rearmRadius"] <= c["burstRadius"]:
            refuse("rearmRadius must be > burstRadius")
        if c["rearmRadius"] + c["senderRadius"] >= c["acqHalf"]:
            refuse("rearmRadius + senderRadius must be < acqHalf — a dwell re-arm must be reachable on axis")
    if c["stepSeconds"] < 2 / 60:
        refuse("stepSeconds must be >= 2/60 — a dwell shorter than two collision steps can be skipped")
    if 2 * c["holdHalf"] > 6:
        refuse("2*holdHalf exceeds the SDK's serialized box limit (6 m) — a sanity bound on the working volume")
    if c["lookupSegments"] < 4:
        refuse("lookupSegments must be >= 4")
    if "/" in c["prefix"] or not c["prefix"]:
        refuse("prefix must be a bare segment")
    if c["enable"].count("/") != 1:
        refuse("enable must be one prefixed name (Module/Enable) — the wildcard for a bare name matches nothing")


def slot_name(c, k):
    return f"{c['prefix']}/Slot{k}"


def boxes_path(k):
    return f"Cage/Slot{k}/Boxes"


def out_path(k):
    return f"Cage/Slot{k}/Output"


def emit_layer(o, c, k, ks):
    P = c["prefix"]
    en = c["enable"]
    mode = c["mode"]
    me = slot_name(c, k)
    eps = c["epsilon"]
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    off = f"          - {{ to: Disabled, when: [ {en} is false ] }}"
    o(f"  - name: Slot{k}")
    o("    states:")
    o("      Disabled:                        # Enable off — boxes stowed, flag shut, readings zeroed on every client")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: false, set: {{ {me}/X+: 0, {me}/Y+: 0, {me}/Z+: 0 }} }}")
    o(f"        motion: {{ clip: slot{k}_off }}")
    o("        transitions:")
    o(f"          - {{ to: Armed, when: [ {en} is true ], exitTime: 1.0 }}   # quantized: an Enable cycle spans a step")
    o("      Armed:                        # flag shut: every hand already inside stays invisible to this slot")
    o(f"        motion: {{ clip: slot{k}_armed }}")
    o("        transitions:")
    o(off)
    for i in ks:
        if i == k:
            continue
        between = []
        m = i % len(ks) + 1
        while m != k:
            between.append(m)
            m = m % len(ks) + 1
        si = slot_name(c, i)
        conds = [f"{si}/Open greater 0.5", f"{si}/X+ greater 0", f"{si}/Y+ greater 0", f"{si}/Z+ greater 0",
                 f"{me}/Armed greater 0.5"]
        conds += [f"{slot_name(c, m)}/Armed less 0.5" for m in between]
        o(f"          - {{ to: Open, when: [ {', '.join(conds)} ] }}   # ring: slot {i} fired, nothing Armed between")
    conds = [f"{slot_name(c, j)}/Open less 0.5" for j in ks if j != k]
    conds += [f"{slot_name(c, j)}/Armed less 0.5" for j in ks if j < k]
    conds += [f"{me}/Armed greater 0.5"]
    o(f"          - {{ to: Open, when: [ {', '.join(conds)} ], exitTime: 1.0 }}   # self-open: nothing Open, no lower Armed; re-checked only on a crossing")
    o("      Open:                         # flag up: only overlaps beginning now are admitted")
    o(f"        motion: {{ clip: slot{k}_open }}")
    o("        transitions:")
    o(off)
    o(f"          - {{ to: Latch, when: [ {me}/X+ greater 0, {me}/Y+ greater 0, {me}/Z+ greater 0 ] }}")
    for ax in ("X+", "Y+", "Z+"):
        o(f"          - {{ to: Partial, when: [ {me}/{ax} greater 0 ] }}")
    o("      Partial:                      # one box read a hand the others did not: a step's grace to complete, else Recycle — an Open slot may never stall")
    o(f"        motion: {{ clip: slot{k}_open_wait }}")
    o("        transitions:")
    o(off)
    o(f"          - {{ to: Latch, when: [ {me}/X+ greater 0, {me}/Y+ greater 0, {me}/Z+ greater 0 ] }}")
    o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Latch:                        # flag shut + hold cube in one write; x,y,z parked at h so the first r² reads 3h²")
    o(f"        motion: {{ clip: slot{k}_latch }}")
    o("        transitions:")
    o(off)
    o("          - { to: TrackOut, when: [], exitTime: 1.0 }")
    o("      TrackOut:                     # readout live, burst off; outside the burst radius")
    emit_tree(o, c, k, hold=f"slot{k}_hold")
    o("        transitions:")
    o(off)
    for ax in ("X+", "Y+", "Z+"):
        o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")
    target = "TrackIn" if mode == "dwell" else "Burst"
    o(f"          - {{ to: {target}, when: [ {me}/r2 less {fmt(rin2)} ] }}")
    if mode == "dwell":
        o("      TrackIn:                      # inside the burst radius; the buffer GO is on (one burst per entry)")
        emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
        o("        transitions:")
        o(off)
        for ax in ("X+", "Y+", "Z+"):
            o(f"          - {{ to: Recycle, when: [ {me}/{ax} less {fmt(eps)} ] }}")
        o(f"          - {{ to: TrackOut, when: [ {me}/r2 greater {fmt(rout2)} ] }}")
    else:
        o("      Burst:                        # the buffer GO on for the tree's own dwell, then release")
        emit_tree(o, c, k, hold=f"slot{k}_hold_burst")
        o("        transitions:")
        o(off)
        o("          - { to: Recycle, when: [], exitTime: 1.0 }")
    o("      Recycle:                      # collapse a step, restore a step, flag shut: every hand inside is re-rejected")
    o(f"        motion: {{ clip: slot{k}_recycle }}")
    o("        transitions:")
    o(off)
    o("          - { to: Armed, when: [], exitTime: 1.0 }")
    o("    default: Disabled")
    o("    layout:")
    o(f"      nodes: {{ Disabled: [30, 180], Armed: [30, 270], Open: [30, 360], Partial: [270, 360], Latch: [30, 450], TrackOut: [-210, 540], {target}: [270, 540], Recycle: [30, 630] }}")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")


def emit_tree(o, c, k, hold):
    P = c["prefix"]
    me = slot_name(c, k)
    h = c["holdHalf"]
    N = c["lookupSegments"]
    o("        motion:")
    o("          tree: direct")
    o(f"          name: Slot{k} readout")
    o("          normalized: false")
    o("          children:")
    o(f"            - {{ clip: {hold}, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_read_bias, directWeight: {P}/One }}")
    o(f"            - {{ clip: slot{k}_read_xp, directWeight: {me}/X+ }}")
    o(f"            - {{ clip: slot{k}_read_yp, directWeight: {me}/Y+ }}")
    o(f"            - {{ clip: slot{k}_read_zp, directWeight: {me}/Z+ }}")
    for ax in ("x", "y", "z"):
        o("            - tree: 1d")
        o(f"              name: Slot{k} {ax}²")
        o(f"              param: {me}/{ax}")
        o(f"              directWeight: {P}/One")
        o("              children:")
        for i in range(N + 1):
            t = -h + 2 * h * i / N
            o(f"                - {{ clip: slot{k}_sq_{i}, threshold: {fmt(t)} }}")


def emit_clips(o, c, k):
    me = slot_name(c, k)
    B = boxes_path(k)
    O = out_path(k)
    h = c["holdHalf"]
    r = c["senderRadius"]
    step = c["stepSeconds"]
    N = c["lookupSegments"]
    acq = 2 * c["acqHalf"] / c["boxSize"]
    hold = 2 * c["holdHalf"] / c["boxSize"]
    collapsed = 0.001
    burst = f"{O}/Burst/GameObject.m_IsActive"

    def cfg(active, flag, scale, opn, armed, burst_on):
        d = {f"{B}/GameObject.m_IsActive": active}
        for ax in ("X+", "Y+", "Z+"):
            d[f"{B}/{ax}/VRCContactReceiver.allowOthers"] = flag
        if scale is not None:
            for ax in ("x", "y", "z"):
                d[f"{B}/Transform.m_LocalScale.{ax}"] = fmt(scale)
        d[f"{me}/Open"] = opn
        d[f"{me}/Armed"] = armed
        d[burst] = burst_on
        return d

    def clip(name, sets, seconds=None, comment=None):
        body = ", ".join(f"{k2}: {v}" for k2, v in sets.items())
        sec = f"seconds: {fmt(seconds)}, " if seconds else ""
        o(f"  {name}: {{ {sec}set: {{ {body} }} }}" + (f"   # {comment}" if comment else ""))

    o(f"  # Slot {k} configurations — every one writes the box stow, the flag, the scale, both protocol flags and the burst toggle.")
    clip(f"slot{k}_off", cfg(0, 0, acq, 0, 0, 0), step, "stowed; a stow shorter than a step comes back deaf")
    clip(f"slot{k}_armed", cfg(1, 0, acq, 0, 1, 0), step, "Armed 1 — the ring rule reads it one frame late")
    clip(f"slot{k}_open", cfg(1, 1, acq, 1, 0, 0), None, "Open 1 — the flag up")
    clip(f"slot{k}_open_wait", cfg(1, 1, acq, 1, 0, 0), step, "Open 1 held a step: the partial-admission grace")
    latch = cfg(1, 0, hold, 0, 0, 0)
    latch.update({f"{me}/x": fmt(h), f"{me}/y": fmt(h), f"{me}/z": fmt(h)})
    clip(f"slot{k}_latch", latch, step, "flag shut + hold cube in one write; x,y,z parked at h (r² reads 3h²)")
    clip(f"slot{k}_hold", cfg(1, 0, hold, 0, 0, 0), None, "tracking configuration, burst off")
    clip(f"slot{k}_hold_burst", cfg(1, 0, hold, 0, 0, 1), None, "tracking configuration, burst on")
    rec = cfg(1, 0, None, 0, 0, 0)
    body = ", ".join(f"{k2}: {v}" for k2, v in rec.items())
    o(f"  slot{k}_recycle:   # collapse for a step, restore for a step; stepped so nothing eases through the collapse")
    o(f"    seconds: {fmt(2 * step)}")
    o(f"    set: {{ {body} }}")
    o("    curves:")
    for ax in ("x", "y", "z"):
        o(f"      {B}/Transform.m_LocalScale.{ax}: {{ tangents: stepped, keys: [ [0, {fmt(collapsed)}], [{fmt(step)}, {fmt(acq)}], [{fmt(2 * step)}, {fmt(acq)}] ] }}")
    o(f"  # Slot {k} readout: c = 2h·V − h − r per axis (face proximity is linear from the +Z face; V is the box reading),")
    o("  # summed under the non-normalized Direct root into both the AAPs and Output's localPosition (metres, cage frame).")
    two_h = fmt(2 * h)
    bias = fmt(-h - r)
    clip(f"slot{k}_read_xp", {f"{me}/x": two_h, f"{O}/Transform.m_LocalPosition.x": two_h})
    clip(f"slot{k}_read_yp", {f"{me}/y": two_h, f"{O}/Transform.m_LocalPosition.y": two_h})
    clip(f"slot{k}_read_zp", {f"{me}/z": two_h, f"{O}/Transform.m_LocalPosition.z": two_h})
    clip(f"slot{k}_read_bias", {f"{me}/x": bias, f"{me}/y": bias, f"{me}/z": bias,
                                f"{O}/Transform.m_LocalPosition.x": bias,
                                f"{O}/Transform.m_LocalPosition.y": bias,
                                f"{O}/Transform.m_LocalPosition.z": bias})
    o(f"  # Slot {k} x² table: {N} segments over [−h, h]; each 1D tree blends the two nearest, a chord that overestimates by ≤ w²/4.")
    for i in range(N + 1):
        t = -h + 2 * h * i / N
        clip(f"slot{k}_sq_{i}", {f"{me}/r2": fmt(t * t)})


def document(overrides=None):
    """The controller.yaml text for CONFIG updated by `overrides`, plus a facts dict."""
    c = dict(CONFIG)
    c.update(overrides or {})
    lint(c)
    K = c["K"]
    ks = list(range(1, K + 1))
    P = c["prefix"]
    rin2 = c["burstRadius"] ** 2
    rout2 = c["rearmRadius"] ** 2
    L = []
    o = L.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o(f"# contact-radar: {K} per-sender slots, mode {c['mode']}, tags {c['tags']}, 3 face-proximity boxes each.")
    if c["mode"] == "dwell":
        o(f"# Burst at r² < {fmt(rin2)} (R_in {c['burstRadius']} m), re-arm at r² > {fmt(rout2)} (R_out {c['rearmRadius']} m).")
    else:
        o(f"# Burst at r² < {fmt(rin2)} (R_in {c['burstRadius']} m); the slot releases at the burst and the")
        o(f"# acquisition cube face ({c['acqHalf']} m) is the re-arm surface.")
    o(f"# Cube half-extents: acquisition {c['acqHalf']} m, hold {c['holdHalf']} m; sender radius {c['senderRadius']} m; step dwell {c['stepSeconds']} s.")
    o("# Per-client: every copy of the avatar senses on its own client (receivers localOnly 0);")
    o("# one synced bit (the enable) and nothing else crosses the wire. generate.py's docstring")
    o("# carries the mechanism; the README carries the traps and the measurements.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root          # paths bind against the module prefab root (VRCFury FullController seam)")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")
    o("parameters:")
    o(f"  {c['enable']}: {{ type: bool, default: true, vrc: {{ synced: true, saved: false }} }}  # the Toggle; off is the reset")
    o(f"  {P}/One: {{ type: float, default: 1, scratch: true }}   # constant direct weight, never driven")
    for k in ks:
        me = slot_name(c, k)
        o(f"  # Slot {k}: receiver floats (never a clip), the readout AAPs, and the two protocol flags.")
        for ax in ("X+", "Y+", "Z+"):
            o(f"  {me}/{ax}: float")
        for ax in ("x", "y", "z", "r2"):
            o(f"  {me}/{ax}: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Open: {{ type: float, aap: true, scratch: true }}")
        o(f"  {me}/Armed: {{ type: float, aap: true, scratch: true }}")
    o("")
    o("layers:")
    for k in ks:
        emit_layer(o, c, k, ks)
    o("")
    o("clips:")
    for k in ks:
        emit_clips(o, c, k)
    facts = {"K": K, "mode": c["mode"], "receivers": 3 * K, "syncedBits": 1,
             "acqScale": 2 * c["acqHalf"] / c["boxSize"], "holdScale": 2 * c["holdHalf"] / c["boxSize"]}
    return "\n".join(L) + "\n", facts


def check_files(overrides, here, prefab):
    """The prefab surface no compile or gate reads: slot count, receiver tags and
    flags, the box size the coefficients assume, the enable on globalParams, and
    the two World.prefab pins on Cage. Reads the prefab YAML textually; a field
    it cannot find is a FAIL, never a pass."""
    c = dict(CONFIG)
    c.update(overrides or {})
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond
        return cond

    path = os.path.join(here, prefab)
    if not os.path.exists(path):
        print("  FAIL " + prefab + " is missing")
        return False
    body = open(path, encoding="utf-8").read()
    docs = body.split("--- !u!")
    names = re.findall(r"^  m_Name: (Slot\d+)$", body, re.M)
    assert_(len(names) == c["K"], f"{prefab}: {len(names)} Slot GameObjects == K {c['K']}")
    recv = [d for d in docs if "collisionTags:" in d and "receiverType:" in d]
    assert_(len(recv) == 3 * c["K"], f"{prefab}: {len(recv)} receivers == 3K")
    for d in recv:
        tags = re.findall(r"^  - (\S+)$", d.split("collisionTags:")[1].split("allowSelf")[0], re.M)
        assert_(tags == c["tags"], f"receiver tags {tags} == {c['tags']}")
        for fld, want in (("allowSelf", "0"), ("localOnly", "0"), ("useFaceProximity", "1"),
                          ("receiverType", "2"), ("shapeType", "2")):
            m = re.search(rf"^  {fld}: (\S+)$", d, re.M)
            assert_(m is not None and m.group(1) == want, f"receiver {fld} == {want}")
        m = re.search(r"^  size: \{x: (\S+), y: (\S+), z: (\S+)\}$", d, re.M)
        assert_(m is not None and all(float(v) == c["boxSize"] for v in m.groups()),
                f"receiver size == boxSize {c['boxSize']} on every axis")
        m = re.search(r"^  parameter: (\S+)$", d, re.M)
        assert_(m is not None and re.fullmatch(rf"{c['prefix']}/Slot\d+/[XYZ]\+", m.group(1)) is not None,
                f"receiver parameter {m.group(1) if m else None} under {c['prefix']}/Slot<k>/")
    ok = check_seam(assert_, c, here, body) and ok
    # Unity's YAML writer wraps long lines, so the pin's `type: 3}` tail may sit on the next line.
    world = re.findall(r"SourceTransform: \{fileID: \d+, guid: ([0-9a-f]{32}),\s*type: 3\}", body)
    assert_(len(world) >= 2, f"constraint sources pointing at a prefab asset (the World.prefab pins on Cage): {len(world)} (need 2)")
    print("OK" if ok else "FAILED")
    return ok


def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def check_seam(assert_, c, here, body):
    """The FullController's silent surface: globalParams exactly the enable, and its two
    objRefs pointing at THIS folder's built/ — a component built by copying a configured one
    keeps the donor's objRef and silently runs the donor's controller."""
    ok = True
    gp = re.search(r"globalParams:\n((?:\s+- .*\n)*)", body)
    got = [ln.strip()[2:] for ln in gp.group(1).splitlines()] if gp else None
    ok = assert_(got == [c["enable"]], f"globalParams == [{c['enable']}] (got {got})") and ok
    refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 2\}", body)
    want = [meta_guid(os.path.join(here, "built", c["controller"] + ".controller")),
            meta_guid(os.path.join(here, "built", c["controller"] + "_Parameters.asset"))]
    ok = assert_(refs == want, f"FullController objRefs == built/{c['controller']} controller + params GUIDs (got {refs})") and ok
    return ok


def check_variant(overrides, here, prefab, base_prefab, base_config=None):
    """A prefab VARIANT's file holds only its overrides, so the receiver surface is the base
    prefab's and is checked there; what the variant file itself states is its source, the
    slot removals taking the base K down to this K, and its own FullController seam."""
    c = dict(CONFIG)
    c.update(overrides or {})
    b = dict(CONFIG)
    b.update(base_config or {})
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond
        return cond

    path = os.path.join(here, prefab)
    if not os.path.exists(path):
        print("  FAIL " + prefab + " is missing")
        return False
    body = open(path, encoding="utf-8").read()
    src = re.search(r"m_SourcePrefab: \{fileID: \d+, guid: ([0-9a-f]{32}), type: 3\}", body)
    assert_(src is not None and src.group(1) == meta_guid(base_prefab), f"{prefab} is a variant of {os.path.basename(base_prefab)}")
    removed = re.search(r"m_RemovedGameObjects:\n((?:\s+- \{.*\n)*)", body)
    n = len(removed.group(1).splitlines()) if removed else 0
    assert_(n == b["K"] - c["K"], f"{n} removed GameObjects == base K {b['K']} - K {c['K']} (the removed slots)")
    rc = re.search(r"m_RemovedComponents:\n((?:\s+- \{.*\n)*)", body)
    assert_(rc is not None and len(rc.group(1).splitlines()) == 1, "exactly one removed component (the inherited FullController)")
    ok = check_seam(assert_, c, here, body) and ok
    print("OK" if ok else "FAILED")
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check_files({}, HERE, "ContactRadar.prefab") else 1)
    text, facts = document({})
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml — mode {facts['mode']}, K={facts['K']}, {facts['receivers']} receivers, {facts['syncedBits']} synced bit")


if __name__ == "__main__":
    main()
