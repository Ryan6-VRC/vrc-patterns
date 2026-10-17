#!/usr/bin/env python3
"""control-panel controls generator: emits controls/controller.yaml (ControlPanelControls_Fx) from CONFIG.

    python control-panel/controls/generate.py            # writes controls/controller.yaml
    python control-panel/controls/generate.py --check    # asserts Panel.prefab's hand-built surface against CONFIG

The entry's own generate.py reads `controls`, `face` and rig() from here (rig.json, the mesh's numbers). Edit
CONFIG, rerun both generators, then recompile controls/built/ as a unit in a mounting Editor (CONVENTIONS.md
§The gate). Every output is a pure function of CONFIG; nothing here writes Unity assets: `--check` holds the
prefab to CONFIG afterwards.

WHAT THE CONTROLS ARE
---------------------
One self-contained subtree, `Panel.prefab`, lifted whole by a consumer: the model (assets/ControlPanel.fbx)
fully unpacked, so every bone is a named node a binding and `--check` can address, plus the components below
and nothing else. Unpacked, the prefab no longer follows the FBX: after a re-export that moves a bone, rebuild
it (`--check` pins each bone's rest pose, so a stale one fails there). Four rows, CONFIG `controls`: toggle
buttons, a selector, a discrete slider, a smooth slider.

  Buttons     the bone under Panel, root of ONE physbone (multiChildType Ignore) over every cap chain, the button
              row's Btn<i> -> Btn<i>_End and the selector row's Sel<k> -> Sel<k>_End. Angle limit zero, squish on,
              stretch zero, collision on, grabbing off: a hand pushing a cap down compresses that chain. The solver
              squishes by moving the End along the bone, never by scaling it, so a cap skinned to its End travels
              rigidly. Each tip rests `radius` below its cap's crown, so the joint sphere's top is the crown: that
              sphere is the press surface, wide across the cap when the radius is large (measured: a presser
              engages where its collider surface meets the sphere, within a millimetre). The tip's REST height is
              also where a hard press inverts: with pull 1 the solver re-seats the tip at rest before each collision
              step, so a presser whose centre passes below the rest tip pushes it up instead of down (measured). A
              deep seat (large radius) buys both the width and the overtravel; `squish` only sets how far the cap
              sinks past flush before it sits still.
  <cap>_End   each carries a local-only face-mode box receiver whose +Z face points up the press axis, reading the
              row sender's depth into the box (CP/Press<i>, CP/SelPress<k>).
  PressSender, SelSender   two local-only capsule senders on the Panel bone, one per cap row, lying along X at
              that row's Z and bottom-out depth, both tagged `tag`. A capsule lies at one Z, so it cannot serve two
              rows; validate() refuses a row sender reaching another row's receiver boxes, because the tag is shared.
              The readout senses the panel's own parts, never a hand, so it does not care which senders a stranger
              carries or when they joined.
  Sliders     the bone under Panel, root of ONE physbone (Ignore) over Sld_<name> -> Sld_<name>_End per slider, so
              one slider on the panel is grabbable at a time. It is a grab surface, not a readout: no angle limit
              (limit 0 does not project the hand onto the axis; it over-reads by about h^2/2d), snapToHand 1 (at 0
              the tip keeps the grab offset), grabMovement 1, pull 1, collision and posing off, no parameter. The tip
              rests `restOffset` past the box's -Z face (beyond the high track end); maxSquish 0.9 lets it reach `boxMargin/2` below the
              track's low end, maxStretch lets it reach a hand `boxHeight/2` above or below the far end. Released, it springs to
              rest and nothing reads it.
  Sld_<name>_End  a non-local sphere sender tagged per slider (`ControlPanel<name>`; the boxes may overlap).
  slider boxes   two non-local face-mode box receivers on the Panel bone, CP/<name>_Read, rotated Euler (0, -90, 0)
              so the +Z face points to -X, the track's LOW end, spanning the track plus `boxMargin` each side. The
              reading falls as the knob rises: r_hi at x_lo, r_lo at x_hi, `floor` half a margin past x_hi, 0 with
              the tip at rest outside. Why low: a sender leaving a face-mode box through its +Z face within one
              contact step reads 1.0 for that step before 0, and through the -Z face reads 0 at once (measured in
              av3emu). A release springs the tip to its rest past the high end, so the release must exit through
              the face that reads 0, the -Z face; with +Z at the high end every release read 1.0 for a step and the
              held branch stamped the top slot. Overshoot past the low end still exits through +Z, and its 1.0 is
              the low end's own value (past r_hi: knob 0, Slot 0, Level 0), so it lands where the hand went.
              Non-local, so every client runs the held branch for a remote's grab and its knob follows the hand.
  Knob_<name> a child of Panel in no chain, built UP/ACROSS so its m_LocalPosition is a panel-frame position; the
              knob mesh skins to it. Only the Lamps tree writes it.

THE LAYERS
----------
  Buttons     Idle -> the press ladder, buttons then selector caps, first match wins. A button press entering above
              `press` depth goes straight to Set<i> when the button reads off and Clear<i> when it reads on (a driver
              cannot invert); a selector press goes to StampSel<k>, which stamps ControlPanel/Select = k-1 (0-based, so
              the declared default 0 rests on cap 1) and re-stamps on a press of the chosen cap. Each stamps
              wearer-only the frame the depth is crossed, then Hold until every one of the row receivers is below
              `release`, then Cooldown for `cooldown` seconds, then Idle. Every guard is on the release side,
              because a delay before the stamp adds to the remote's wire and IK delay where one after it costs
              nothing they can see. With `arm` above 0 an Arm dwell sits before each stamp and falls back to Idle if
              the reading drops under `press` first. Lifted from zone-touch's ladder, hold and cooldown dwell.
  Sliders     writes exactly one thing, the AAP CP/Settling, through single-clip states (no Direct tree, so each
              holds what it writes): Idle 0; Held_<name>, the stamp ticks and Settle 1, so the knob memory holds the
              very frame a reading falls. Idle -> Held_<name> on Live and the reading above `floor`, not gated on
              IsLocal: remotes run it for Settling. Every held state leaves for Settle first on Live low, then on
              its reading under floor. A discrete slider's Held_<name> stamps ControlPanel/<name> wearer-only
              through Stamp_<name>_<k> on a crossing of boundary b/N by `hysteresis`. The reading falls as the slot
              rises (track fraction f = (r_hi - reading)/(r_hi - r_lo)), so an up rung is the reading LESS than
              r_hi - (b/N + h)(r_hi - r_lo) and a down rung GREATER than r_hi - (b/N - h)(r_hi - r_lo): up rungs
              highest boundary first, down rungs lowest first, so a jump lands on the slot the reading is in. The
              Settle rungs come first, so a released reading of 0 (under every up threshold) never stamps. A smooth
              slider alternates Held_<name>A <-> Held_<name>B every frame on the wearer, each entry copying the
              reading through convertRange (r_lo, r_hi) -> (1, 0) into ControlPanel/<name> (ascending source,
              descending destination: the inverted-range form runtime.md measured); remotes stay in A. Settle
              dwells `sliderSettle` seconds, re-entering a held state on any reading above floor (Live-gated, or a
              slider held as the panel goes inert would bounce Held <-> Settle until its chain switches off).
  Lamps       one state: a Direct tree weighted by CP/One. A 1D tree per button on its bool; one on Select lighting
              Lamp_Sel<k> (bar lit and cap sunk `travel`, one shape); one on each discrete slider's int lighting
              Lamp_Seg<k>, which shows what the wearer accepted. A smooth slider has no lamp shape: the mesh's
              always-lit strip runs from the track's low end to the knob (near end skinned to Panel, far end to
              Knob_<name>), so it shows the knob, which at rest lands on the synced value.
              Per slider, the knob memory CP/<name>_Knob (track fraction 0..1): a razor 1D on the reading, children
              at floor - RAZOR and floor. Above: the knob from the reading (r_hi -> 0, r_lo -> 1; the children sit
              at ascending thresholds r_lo then r_hi). Below: a 1D on
              Settling whose child 1 writes the AAP back to itself (holds where the hand let go; a WD-ON tree state
              reverts an AAP no child writes) and child 0 writes it from the synced value (a discrete slot's centre,
              (k + 1/2)/N; a smooth value as is). Then a 1D on the AAP writes Knob_<name>'s whole m_LocalPosition,
              x_lo at 0 and x_hi at 1. So on every client the knob follows the hand while held, holds while
              Settling is 1, then goes to the value.
  Live        Inert / Live on <internal>/Live, an AAP the frame's glue writes (1 only once every copy has settled
              onto the panel's synced rest; the glue's header owns why). Inert switches both physbones off and
              raises Controls_Retract, sinking every cap by `travel` and every knob by `channelDepth`; Live reverses
              them. Disabling Sliders breaks a grab network-wide. The press and slider rungs also require Live, so a
              stamp never lands while a chain is off. A consumer lifting the controls without the glue must write
              <internal>/Live itself: at its default 0 the controls stay sunk and dead.
  Offline     Online / Offline writing Lamp_Offline: offline on a remote copy until object-sync's word is
              trustworthy (not IsLocal, and ObjectSync/Enable or OS/Ready low). A state machine because a tree
              cannot read IsLocal without declaring it float.
Every state keys every binding its layer owns: Buttons owns none, Sliders CP/Settling, Lamps the lamp shapes, the
knob AAPs and the knob transforms, Live Controls_Retract and both physbones' m_Enabled, Offline Lamp_Offline.

CONFIG
------
  controller    the emitted controller's name.
  prefix        the published prefix: ControlPanel/Btn<i> (bool), ControlPanel/Select (int), ControlPanel/<name> per
                slider (int for a discrete slider, float 0..1 for a smooth one), all synced and unsaved.
  internal      the internal prefix (required): no published wildcard may reach it.
  mountPath     the Panel instance from the FullController's GameObject; every binding is prefixed with it.
  armature      the FBX armature node under the Panel instance (bones live under <armature>/Panel).
  mesh          the skinned mesh node under the Panel instance.
  face          the plate's full width along X (the frame CONFIG's plate.x spans the same; its generator refuses a
                mismatch).
  controls      the rows, in the panel frame: exactly one `buttons` and one `selector` row ({x: cap centres, z}; the
                selector also carries `segmentWidth`, each segment's extent along X, its depth in Z the caps'
                capDiameter: four near-full-width segments with seams between, in one shared tray), and
                sliders, each {kind: slider (discrete, N slots, `hysteresis` past each boundary as a fraction of the
                track) or smooth (a float, lit by the mesh's knob strip), name, x: (x_lo, x_hi) the knob's track, z,
                tag}. The frame generator reads the layout for the mesh.
  caps          the cap joint shared by both cap rows: the Buttons root's height, the crown `capTop` and
                `capDiameter`, the chain `radius`, the visible `travel` (crown to flush), the `squish` the chain
                allows (travel plus the sink past flush) and the bone length. maxSquish is squish over length.
                validate() refuses caps leaving the face, overlapping, or whose joint sphere's cut at face level
                reaches a neighbouring button cap. The selector row is exempt from that reach refusal by the
                operator's acceptance: its segments are wider than the sphere's reach, so the outer ~10 mm of each is
                dead (a press there dips it and its neighbour and stamps neither).
  press, release   press depth fractions of travel: a press is accepted at or above `press`, held until every cap
                receiver is at or below `release`; emitted as readings over the box's depth.
  boxMargin     the cap receiver box is `squish` plus the sender's diameter plus this deep, so the sender stays inside
                it over the whole squish (a face-mode box reads 0 once the sender passes either face, which would read
                as a release mid-press).
  boxWidth, senderRadius   cap contact geometry; validate() refuses boxes overlapping neighbours.
  arm           seconds a press must hold above `press` before it stamps; 0 stamps on the crossing and emits no dwell
                state (the shipped value: a brush then toggles a cap, and nothing delays the stamp).
  cooldown      seconds between a release and the next accepted press, above the wire's 0.2 s set/clear floor.
  retractTime   seconds the caps and knobs take to rise or sink when <internal>/Live changes (the Live crossfade).
  sliders       shared by every slider. `y` the chain's height (the box's vertical centre, so a grab from above or below the face reads); `radius`
                the chain radius (the capsule along the bone is the grab surface); `boxMargin` m past each track end;
                `senderRadius` r of the tip sphere; `restOffset` the tip's rest past the high track end + m (the
                box's -Z face), refused unless the resting sphere is wholly beyond that face (a sender inside the box
                reads above 0 and would hold every client in Held for ever); `boxAcross`, `boxHeight` the box's extent across the track and through `y`, centred on it (contact size
                limit 6 m); `knobY` the knob bone's rest height; `channelDepth` the knob channel's depth and the knob's
                retract; `settle` [EMPIRICAL] Settle's dwell, the wire plus IK delay between the grabber's release and
                the wearer's last stamp arriving. A slider box may overlap the cap receivers: the tags differ, so neither reads
                the other's sender.
  tag           the cap rows' sender/receiver tag (private).
Derived per slider (rig()['sliders']): run = x_hi - x_lo; box size run + 2m. The face-mode reading is
(size/2 + d + r)/size, d the sender's offset from the box centre along +Z; +Z is -X, so d = (x_lo + x_hi)/2 - x.
Readings r_lo = (m + r)/(run + 2m) at x_hi, r_hi = (run + m + r)/(run + 2m) at x_lo; floor = (m/2 + r)/(run + 2m)
at x_hi + m/2; the squish limit x_lo - m/2 reads (run + 1.5m + r)/(run + 2m), inside the +Z face while r < m/2
(refused otherwise); tip rest x_hi + m + restOffset; bone length
L = (run + 1.5 m + restOffset)/0.9; root at tip rest - L; maxStretch = sqrt(L^2 + (boxHeight/2)^2)/L - 1, the largest
over the sliders, since they share one component.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME = 1 / 60
SQUISH = 0.9     # the Sliders chain's maxSquish: the tip reaches the low track end's squish limit at this fraction
RAZOR = 0.0001   # the knob memory's razor width below `floor`
# A slider box's Unity Euler rotation: local +Z to panel -X, the track's low end. A release springs the tip past the
# high end, and it must leave through the -Z face, which reads 0 at once; leaving through +Z reads 1.0 for a step.
BOX_ROTATION = [0, -90, 0]

CONFIG = {
    "controller": "ControlPanelControls_Fx",
    "prefix": "ControlPanel",
    "internal": "CP",
    "mountPath": "TwoHandProp/Body/Display/Panel",
    "armature": "Armature",
    "mesh": "ControlPanel",
    "face": 0.34,
    "controls": [
        {"kind": "buttons", "x": (-0.09, -0.03, 0.03, 0.09), "z": 0.11},
        {"kind": "selector", "x": (-0.09, -0.03, 0.03, 0.09), "z": 0.04, "segmentWidth": 0.056},
        {"kind": "slider", "name": "Slot", "N": 5, "hysteresis": 0.02, "x": (-0.1, 0.1), "z": -0.04,
         "tag": "ControlPanelSlot"},
        {"kind": "smooth", "name": "Level", "x": (-0.1, 0.1), "z": -0.12, "tag": "ControlPanelLevel"},
    ],
    "caps": {"rootY": 0.02, "capTop": 0.03, "capDiameter": 0.03, "radius": 0.04, "travel": 0.01, "squish": 0.016,
             "boneLength": 0.03},
    "press": 0.75,
    "release": 0.3,
    "boxMargin": 0.002,
    "boxWidth": 0.02,
    "senderRadius": 0.004,
    "arm": 0,
    "cooldown": 0.25,
    "retractTime": 0.25,
    "sliders": {"y": 0.02, "radius": 0.02, "boxMargin": 0.02, "senderRadius": 0.005, "restOffset": 0.015,
                "boxAcross": 0.25, "boxHeight": 0.2, "knobY": 0.02, "channelDepth": 0.012, "settle": 0.5},
    "tag": "ControlPanelPress",
}

ROW_KINDS = ("buttons", "selector")
SLIDER_KINDS = ("slider", "smooth")
END_KEY = {"buttons": "buttonEnds", "selector": "selectorEnds"}


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


def r6(v):
    return round(v, 6)


def rows(c, kind):
    return [r for r in c["controls"] if r["kind"] == kind]


def sliders(c):
    return [r for r in c["controls"] if r["kind"] in SLIDER_KINDS]


def cap_rows(c):
    """(kind, row, bone prefix, receiver parameter prefix, sender name) for the button row, then the selector row."""
    return [("buttons", rows(c, "buttons")[0], "Btn", "Press", "PressSender"),
            ("selector", rows(c, "selector")[0], "Sel", "SelPress", "SelSender")]


def cap_geometry(c):
    b = c["caps"]
    span = b["squish"] + 2 * c["senderRadius"] + c["boxMargin"]
    tip = b["capTop"] - b["radius"]
    # Face mode reads (half + d + r) / size along the box's +Z, d the sender centre's offset from the box centre.
    # The box rides the cap tip, its centre `travel - span/2` below it: the reading is 0 with the cap at rest (the
    # sender's top surface on the box's bottom face) and depth / span as the cap goes down.
    centre = tip - (b["travel"] - span / 2)
    return span, tip, tip - b["boneLength"], centre


def slider_geometry(c, s):
    g = c["sliders"]
    lo, hi = s["x"]
    run, m, r, h = hi - lo, g["boxMargin"], g["senderRadius"], g["boxHeight"] / 2
    size = run + 2 * m
    tip = hi + m + g["restOffset"]
    length = (run + m / 2 + m + g["restOffset"]) / SQUISH
    # The box's +Z face points to -X (BOX_ROTATION): the reading (size/2 + d + r)/size, d = centre - x, falls as x
    # rises. rHi at x_lo, rLo at x_hi, floor at x_hi + m/2 (half a margin past the high end, toward the -Z face).
    return {"run": run, "size": size, "rLo": (m + r) / size, "rHi": (run + m + r) / size, "floor": (m / 2 + r) / size,
            "tipRestX": tip, "boneLength": length, "rootX": tip - length,
            "maxStretch": math.sqrt(length ** 2 + h ** 2) / length - 1, "centre": ((lo + hi) / 2, g["y"], s["z"])}


def aabb_overlap(a, b):
    return all(a[k][0] < b[k][1] and b[k][0] < a[k][1] for k in range(3))


def cap_receiver_aabbs(c, row):
    """Each cap receiver's panel-frame box over its whole squish (it rides the End down)."""
    span, tip, head, centre = cap_geometry(c)
    w = c["boxWidth"] / 2
    return [((x - w, x + w), (centre - c["caps"]["squish"] - span / 2, centre + span / 2), (row["z"] - w, row["z"] + w))
            for x in row["x"]]


def row_sender_aabb(c, row):
    span, tip, head, centre = cap_geometry(c)
    r = c["senderRadius"]
    y = tip - c["caps"]["travel"] - r
    half = (max(row["x"]) - min(row["x"]) + c["boxWidth"] + 2 * r) / 2
    xc = (max(row["x"]) + min(row["x"])) / 2
    return ((xc - half, xc + half), (y - r, y + r), (row["z"] - r, row["z"] + r))


def validate(c):
    for k in ("prefix", "internal"):
        if not c[k] or "/" in c[k]:
            refuse(f"{k} is one bare name segment, required.")
    if c["internal"].startswith(c["prefix"]):
        refuse("internal may not sit under prefix: the published wildcard would reach it.")
    kinds = [r.get("kind") for r in c["controls"]]
    if any(k not in ROW_KINDS + SLIDER_KINDS for k in kinds):
        refuse(f"controls kinds are {ROW_KINDS + SLIDER_KINDS} (got {kinds}).")
    if kinds.count("buttons") != 1 or kinds.count("selector") != 1:
        refuse("controls carries exactly one buttons row and one selector row: the Buttons ladder and its Hold are built for those two.")
    if not sliders(c):
        refuse("controls carries at least one slider (kind slider or smooth).")
    b = c["caps"]
    if b["travel"] <= 0 or b["travel"] >= b["squish"]:
        refuse("travel is positive and shorter than squish: the cap must sink past flush before the chain stops it.")
    if b["squish"] > 0.9 * b["boneLength"]:
        refuse("squish is at most 0.9 of the cap bone: maxSquish is squish over bone length and the solver needs some length left.")
    if b["radius"] <= 0:
        refuse("the cap chain radius is positive: a radius of 0 neither collides nor grabs.")
    if not 0 <= c["arm"] < c["cooldown"]:
        refuse("arm is 0 (no dwell) or positive and shorter than the cooldown.")
    if not 0 < c["release"] < c["press"] <= 1:
        refuse("0 < release < press <= 1: the hold band needs a gap.")
    if c["boxMargin"] <= 0:
        refuse("boxMargin is positive: the sender must stay inside the receiver box at full squish.")
    if c["senderRadius"] <= 0:
        refuse("senderRadius is positive.")
    if c["cooldown"] <= 0.2:
        refuse("cooldown at or under the wire's 0.2 s set/clear floor: two toggles could be a lost pair.")
    reach = math.sqrt(max(0.0, 2 * b["radius"] * b["travel"] - b["travel"] ** 2))
    crs = cap_rows(c)
    for kind, row, *_ in crs:
        lo_n = 2 if kind == "selector" else 1
        if not lo_n <= len(row["x"]) <= 8:
            refuse(f"the {kind} row carries {lo_n} to eight caps.")
        # A button cap is capDiameter wide along X; a selector segment is the row's own segmentWidth.
        width = row.get("segmentWidth", 0) if kind == "selector" else b["capDiameter"]
        if not width > 0:
            refuse("the selector row carries a positive segmentWidth (each segment's extent along X).")
        if any(abs(x) + width / 2 > c["face"] / 2 for x in row["x"]):
            refuse(f"the {kind} row leaves the panel face: |x| + its cap width / 2 is past face / 2"
                   + (" (the selector's shared tray spans its outer segments' ends)." if kind == "selector" else "."))
        xs = sorted(row["x"])
        if len(xs) > 1:
            gap = min(x1 - x0 for x0, x1 in zip(xs, xs[1:]))
            if gap <= width:
                refuse(f"neighbouring {kind} caps overlap or touch: the closest centres are no farther apart than one cap width"
                       + (" (segmentWidth; the seam between segments must be positive)." if kind == "selector" else "."))
            if c["boxWidth"] >= gap:
                refuse(f"{kind} receiver boxes overlap their neighbours' across X.")
            # Relaxed for the selector by the operator's acceptance: a segment is wider than its joint sphere's reach,
            # so the outer ~10 mm of each is dead (a press there dips it and its neighbour and stamps neither).
            if kind != "selector" and reach + width / 2 >= gap:
                refuse(f"a {kind} joint sphere reaches the neighbouring cap at face level: a finger on one cap would press the next.")
    (k1, row1, *_), (k2, row2, *_) = crs
    dz = abs(row1["z"] - row2["z"])
    if reach + b["capDiameter"] / 2 >= dz:
        refuse("a joint sphere reaches the other cap row at face level: the rows are too close in Z.")
    for (ka, ra, *_), (kb, rb, *_) in ((crs[0], crs[1]), (crs[1], crs[0])):
        if any(aabb_overlap(row_sender_aabb(c, ra), box) for box in cap_receiver_aabbs(c, rb)):
            refuse(f"the {ka} row's sender reaches a {kb} receiver box: both rows share the tag `{c['tag']}`, so a press on one row would read on the other.")

    g = c["sliders"]
    for k in ("radius", "boxMargin", "senderRadius", "boxAcross", "boxHeight", "channelDepth", "settle"):
        if g[k] <= 0:
            refuse(f"sliders.{k} is positive.")
    if g["senderRadius"] >= g["boxMargin"] / 2:
        refuse("sliders.senderRadius is at or over boxMargin / 2: at the squish limit (x_lo - boxMargin/2) the tip's sphere "
               "would reach the box's +Z face, which reads 1 while straddled.")
    if g["boxAcross"] > 6 or g["boxHeight"] > 6:
        refuse("a slider box side is past the 6 m contact size limit.")
    names, tags = [], [c["tag"]]
    for s in sliders(c):
        name = s.get("name", "")
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name) or name in ("Btn", "Select", "Sel", "Press", "One", "Live", "Settling"):
            refuse(f"slider name {name!r} is one capitalised identifier, not a name the controls already publish or use.")
        names.append(name)
        tags.append(s.get("tag"))
        lo, hi = s["x"]
        if not lo < hi:
            refuse(f"slider {name}: x is (x_lo, x_hi) with x_lo < x_hi: the knob value grows with x (the reading falls).")
        if max(abs(lo), abs(hi)) > c["face"] / 2:
            refuse(f"slider {name}: the track leaves the face (|x| past face / 2).")
        geo = slider_geometry(c, s)
        if geo["tipRestX"] - g["senderRadius"] <= hi + g["boxMargin"]:
            refuse(f"slider {name}: the resting tip's sphere (x {geo['tipRestX']:.4f}, radius {g['senderRadius']}) is not wholly "
                   f"beyond the box's -Z face at x_hi + boxMargin ({hi + g['boxMargin']:.4f}): a sender inside the box reads above "
                   "0 and would hold every client in Held for ever (restOffset must exceed senderRadius).")
        if geo["size"] > 6:
            refuse(f"slider {name}: the box's run + 2 boxMargin is past the 6 m contact size limit.")
        if s["kind"] == "slider":
            n = s["N"]
            if not isinstance(n, int) or n < 2 or n > 255:
                refuse(f"slider {name}: N is a whole number of slots, 2..255: the value is an 8-bit synced int.")
            if not 0 < s["hysteresis"] < 0.5 / n:
                refuse(f"slider {name}: hysteresis is positive and under half a slot, or a slot has no stable band.")
    if len(set(names)) != len(names):
        refuse(f"slider names repeat ({names}).")
    if None in tags or len(set(tags)) != len(tags):
        refuse(f"every slider carries its own tag, distinct from the cap rows' `{c['tag']}` (got {tags}).")


def names(c):
    """Bone and shape names: rig.json, the mesh and the bindings all read them from here."""
    out = {"root": "Panel", "buttonsRoot": "Buttons", "slidersRoot": "Sliders"}
    for kind, row, bone, _, sender in cap_rows(c):
        out[kind] = [f"{bone}{i + 1}" for i in range(len(row["x"]))]
        out[END_KEY[kind]] = [f"{bone}{i + 1}_End" for i in range(len(row["x"]))]
    out["sliders"] = [f"Sld_{s['name']}" for s in sliders(c)]
    out["sliderEnds"] = [f"Sld_{s['name']}_End" for s in sliders(c)]
    out["knobs"] = [f"Knob_{s['name']}" for s in sliders(c)]
    return out


def shapes(c):
    out = {"buttons": [f"Lamp_Btn{i + 1}" for i in range(len(rows(c, "buttons")[0]["x"]))],
           "selector": [f"Lamp_Sel{k + 1}" for k in range(len(rows(c, "selector")[0]["x"]))],
           "offline": "Lamp_Offline", "retract": "Controls_Retract"}
    for s in rows(c, "slider"):
        out[s["name"]] = [f"Lamp_Seg{k}" for k in range(s["N"])]
    return out


def rig(c):
    """Every number the Unity-side controls subtree is built to (contacts, physbones, bone rest poses)."""
    validate(c)
    b, g, I = c["caps"], c["sliders"], c["internal"]
    span, tip, head, centre = cap_geometry(c)
    w = r6(c["boxWidth"])
    nm = names(c)
    crs = cap_rows(c)
    senders = []
    for kind, row, bone, prm, sname in crs:
        senders.append({"name": sname, "row": kind, "shape": "Capsule", "radius": c["senderRadius"],
                        "height": r6(max(row["x"]) - min(row["x"]) + c["boxWidth"] + 2 * c["senderRadius"]),
                        "position": [r6((max(row["x"]) + min(row["x"])) / 2), r6(tip - b["travel"] - c["senderRadius"]), row["z"]],
                        "rotation": [0, 0, 90], "localOnly": True, "tag": c["tag"]})
    out_sliders = []
    for s in sliders(c):
        geo = slider_geometry(c, s)
        n = s["name"]
        e = {"name": n, "kind": s["kind"], "x": list(s["x"]), "z": s["z"], "y": g["y"], "tag": s["tag"],
             "read": f"{I}/{n}_Read", "knobParam": f"{I}/{n}_Knob", "value": f"{c['prefix']}/{n}",
             "bone": f"Sld_{n}", "end": f"Sld_{n}_End", "knob": f"Knob_{n}",
             "run": r6(geo["run"]), "boneLength": r6(geo["boneLength"]), "rootX": r6(geo["rootX"]),
             "tipRestX": r6(geo["tipRestX"]), "knobY": g["knobY"], "channelDepth": g["channelDepth"],
             "rLo": r6(geo["rLo"]), "rHi": r6(geo["rHi"]), "floor": r6(geo["floor"]),
             "receiver": {"shape": "Box", "useFaceProximity": True, "size": [r6(g["boxAcross"]), r6(g["boxHeight"]), r6(geo["size"])],
                          "position": [r6(v) for v in geo["centre"]], "rotation": BOX_ROTATION, "localOnly": False,
                          "allowSelf": True, "allowOthers": False, "tag": s["tag"], "param": f"{I}/{n}_Read"},
             "sender": {"shape": "Sphere", "radius": g["senderRadius"], "position": [0, 0, 0], "localOnly": False,
                        "tag": s["tag"]}}
        span_r = geo["rHi"] - geo["rLo"]
        if s["kind"] == "slider":
            N, h = s["N"], s["hysteresis"]
            e["N"] = N
            # Track fraction f = (rHi - reading)/span: f past b/N + h is the reading under rHi - (b/N + h) span.
            e["up"] = {bb: r6(geo["rHi"] - (bb / N + h) * span_r) for bb in range(1, N)}
            e["down"] = {bb: r6(geo["rHi"] - (bb / N - h) * span_r) for bb in range(1, N)}
        out_sliders.append(e)
    sel_root_z = r6(sum(row["z"] for _, row, *_ in crs) / len(crs))
    s0 = out_sliders
    bones = [("Buttons", [0, b["rootY"], sel_root_z])]
    for kind, row, bone, _, _ in crs:
        bones += [(f"Buttons/{bone}{i + 1}", [x, r6(head), row["z"]]) for i, x in enumerate(row["x"])]
        bones += [(f"Buttons/{bone}{i + 1}/{bone}{i + 1}_End", [x, r6(tip), row["z"]]) for i, x in enumerate(row["x"])]
    bones.append(("Sliders", [min(e["rootX"] for e in s0), g["y"], r6(sum(e["z"] for e in s0) / len(s0))]))
    for e in s0:
        bones += [(f"Sliders/{e['bone']}", [e["rootX"], g["y"], e["z"]]),
                  (f"Sliders/{e['bone']}/{e['end']}", [e["tipRestX"], g["y"], e["z"]]),
                  (e["knob"], [e["x"][0], g["knobY"], e["z"]])]
    return {
        "names": nm,
        "shapes": shapes(c),
        "receiver": {"shape": "Box", "useFaceProximity": True, "size": [w, w, r6(span)],
                     "position": [0, r6(centre - tip), 0], "rotation": [-90, 0, 0],
                     "localOnly": True, "allowSelf": True, "allowOthers": False, "tag": c["tag"],
                     "params": {kind: [f"{I}/{prm}{i + 1}" for i in range(len(row["x"]))] for kind, row, _, prm, _ in crs}},
        "senders": senders,
        "thresholds": {"press": r6(c["press"] * b["travel"] / span), "release": r6(c["release"] * b["travel"] / span)},
        "buttonsPhysBone": {"maxSquish": r6(b["squish"] / b["boneLength"]), "maxStretch": 0, "radius": b["radius"], "pull": 1,
                            "parameter": f"{I}/Buttons"},
        "capTip": {"rest": r6(tip), "bottom": r6(tip - b["travel"]), "floor": r6(tip - b["squish"])},
        "slidersPhysBone": {"maxSquish": SQUISH, "maxStretch": r6(max(slider_geometry(c, s)["maxStretch"] for s in sliders(c))),
                            "radius": g["radius"], "pull": 1, "grabMovement": 1, "parameter": ""},
        "sliders": out_sliders,
        # Rest poses in the Panel bone's frame (the panel frame): what the FBX must import as.
        "bones": dict(bones),
    }


def document(c):
    r = rig(c)
    P, I, M = c["prefix"], c["internal"], c["mountPath"]
    nm, sh = r["names"], r["shapes"]
    crs = cap_rows(c)
    nb = len(crs[0][1]["x"])
    ns = len(crs[1][1]["x"])
    BTN = [f"{P}/Btn{i + 1}" for i in range(nb)]
    SEL = f"{P}/Select"
    PRESS = r["receiver"]["params"]["buttons"]
    SPRESS = r["receiver"]["params"]["selector"]
    ONE, LIVE, SETTLING = f"{I}/One", f"{I}/Live", f"{I}/Settling"
    press, release = r["thresholds"]["press"], r["thresholds"]["release"]
    shape = f"{M}/{c['mesh']}/SkinnedMeshRenderer.blendShape."
    bone = f"{M}/{c['armature']}/Panel"
    LO = f"{shape}{sh['offline']}"
    RETRACT = f"{shape}{sh['retract']}"
    CHAINS = [f"{bone}/{nm['buttonsRoot']}/VRCPhysBone.m_Enabled", f"{bone}/{nm['slidersRoot']}/VRCPhysBone.m_Enabled"]
    SL = r["sliders"]
    gate = f"{LIVE} greater 0.5"

    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by control-panel/controls/generate.py; edit its CONFIG and rerun, never hand-edit this file.")
    o("# The controls subtree's machine: button and selector stamps, the slider readouts and knob memories, the lamps.")
    o("# The generator's docstring is the design record.")
    o(f"# Published (synced, unsaved, wearer-stamped, float in the animator): {', '.join(BTN)} (bool), {SEL} (int, 0-based),")
    o(f"# {', '.join(e['value'] + (' (int)' if e['kind'] == 'slider' else ' (float 0..1)') for e in SL)}.")
    o(f"# Cap press accepted at receiver reading {press}, held until every reading is under {release} (depth {c['press']} / {c['release']}")
    o(f"# of travel over a box {r['receiver']['size'][2]} m deep). Arm {c['arm']} s, cooldown {c['cooldown']} s.")
    for e in SL:
        o(f"# {e['name']}: the box's +Z face points to -X, so the reading falls as the knob rises: r_hi {e['rHi']} at x {e['x'][0]},")
        o(f"# r_lo {e['rLo']} at x {e['x'][1]}, floor {e['floor']}.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")
    o("parameters:")
    for p in BTN:
        o(f"  {p}: {{ type: float, default: 0, vrc: {{ type: bool, synced: true, saved: false }} }}")
    o(f"  {SEL}: {{ type: float, default: 0, vrc: {{ type: int, synced: true, saved: false }} }}")
    for e in SL:
        o(f"  {e['value']}: {{ type: float, default: 0, vrc: {{ type: {'int' if e['kind'] == 'slider' else 'float'}, synced: true, saved: false }} }}")
    for p in PRESS + SPRESS:
        o(f"  {p}: float   # sensing: a local-only cap receiver's press depth reading")
    for e in SL:
        o(f"  {e['read']}: float   # sensing: the non-local slider box's reading of the tip's track position")
    o(f"  {ONE}: {{ type: float, default: 1, scratch: true }}   # the Direct tree's constant weight")
    o(f"  {LIVE}: {{ type: float, default: 0, aap: true }}   # the frame's gate, written by the glue; matches its declaration")
    o(f"  {SETTLING}: {{ type: float, default: 0, aap: true }}   # the Sliders layer's one output: 1 while held or settling")
    for e in SL:
        o(f"  {e['knobParam']}: {{ type: float, default: 0, aap: true }}   # the knob memory, track fraction 0..1")
    o("  # Shared with the object-sync build through the one component; declarations match the entry's.")
    o("  ObjectSync/Enable: { type: float, default: 1, vrc: { type: bool, synced: true, saved: false } }")
    o("  OS/Ready: { type: float, default: 0, vrc: { type: bool, synced: false, saved: false } }")
    o("  IsLocal: bool   # VRC built-in")
    o("")
    o("layers:")
    # ---- Buttons ----
    arm = c["arm"] > 0
    # (stamp states, reading, arm state) per cap; a button stamps through Set/Clear, a selector cap through Sel<k>.
    o("  - name: Buttons")
    o("    states:")
    o("      # Remotes never leave Idle: the receivers are local-only, so their readings stay 0 there.")
    o("      Idle:")
    o("        motion: ~")
    o("        transitions:")
    for i in range(nb):
        if arm:
            o(f"          - {{ to: Arm{i + 1}, when: [ {gate}, {PRESS[i]} greater {press} ] }}")
        else:
            o(f"          - {{ to: Set{i + 1}, when: [ {gate}, {PRESS[i]} greater {press}, {BTN[i]} less 0.5 ] }}")
            o(f"          - {{ to: Clear{i + 1}, when: [ {gate}, {PRESS[i]} greater {press}, {BTN[i]} greater 0.5 ] }}")
    for k in range(ns):
        o(f"          - {{ to: {'ArmSel' if arm else 'StampSel'}{k + 1}, when: [ {gate}, {SPRESS[k]} greater {press} ] }}")
    if arm:
        o("      # The dwell: a cap pushed down by a hand passing sideways falls back before the clip ends. The stamp")
        o("      # rungs' condition is constant over the state (nothing writes Btn<i> here), so exit time is safe on them.")
        for i in range(nb):
            o(f"      Arm{i + 1}:")
            o("        motion: { clip: arm }")
            o("        transitions:")
            o(f"          - {{ to: Idle, when: [ {PRESS[i]} less {press} ] }}")
            o(f"          - {{ to: Set{i + 1}, when: [ {BTN[i]} less 0.5 ], exitTime: 1.0 }}")
            o(f"          - {{ to: Clear{i + 1}, when: [ {BTN[i]} greater 0.5 ], exitTime: 1.0 }}")
        for k in range(ns):
            o(f"      ArmSel{k + 1}:")
            o("        motion: { clip: arm }")
            o("        transitions:")
            o(f"          - {{ to: Idle, when: [ {SPRESS[k]} less {press} ] }}")
            o(f"          - {{ to: StampSel{k + 1}, when: [], exitTime: 1.0 }}")
    for i in range(nb):
        for name, v in (("Set", 1), ("Clear", 0)):
            o(f"      {name}{i + 1}:")
            o("        motion: { clip: tick }")
            o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {BTN[i]}: {v} }} }} }} ]")
            o("        transitions:")
            o("          - { to: Hold, when: [], exitTime: 1.0 }")
    o(f"      # Cap k stamps {SEL} = k - 1; a press on the chosen cap re-stamps the same value.")
    for k in range(ns):
        o(f"      StampSel{k + 1}:")
        o("        motion: { clip: tick }")
        o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {SEL}: {k} }} }} }} ]")
        o("        transitions:")
        o("          - { to: Hold, when: [], exitTime: 1.0 }")
    o("      Hold:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Cooldown, when: [ {', '.join(f'{p} less {release}' for p in PRESS + SPRESS)} ] }}")
    o("      # The floor between two toggles: no press rung leaves here.")
    o("      Cooldown:")
    o("        motion: { clip: cooldown }")
    o("        transitions:")
    o("          - { to: Idle, when: [], exitTime: 1.0 }")
    o("    default: Idle")
    o("    layout:")
    cols = [-690 + 240 * i for i in range(max(nb, ns) * 2)]
    nodes = (["Idle: [30, 180]"]
             + ([f"Arm{i + 1}: [{cols[i]}, 260]" for i in range(nb)] + [f"ArmSel{k + 1}: [{cols[nb + k]}, 260]" for k in range(ns)] if arm else [])
             + [f"Set{i + 1}: [{cols[i]}, 340]" for i in range(nb)] + [f"Clear{i + 1}: [{cols[i]}, 420]" for i in range(nb)]
             + [f"StampSel{k + 1}: [{cols[nb + k]}, 380]" for k in range(ns)] + ["Hold: [30, 520]", "Cooldown: [30, 600]"])
    o(f"      nodes: {{ {', '.join(nodes)} }}")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    # ---- Sliders ----
    o(f"  # Writes only {SETTLING}, through single-clip states: Idle 0, every other state 1. Remotes run the held and")
    o("  # settle branches too (the slider receivers are non-local); only the wearer stamps.")
    o("  - name: Sliders")
    o("    states:")
    o("      Idle:")
    o("        motion: { clip: settling_off }")
    o("        transitions:")
    for e in SL:
        o(f"          - {{ to: {held_entry(e)}, when: [ {gate}, {e['read']} greater {e['floor']} ] }}")
    for e in SL:
        settle_rungs = [f"          - {{ to: Settle, when: [ {LIVE} less 0.5 ] }}",
                        f"          - {{ to: Settle, when: [ {e['read']} less {e['floor']} ] }}"]
        if e["kind"] == "slider":
            N, V = e["N"], e["value"]
            o(f"      # Boundary b/N between slot b-1 and slot b, crossed by the hysteresis; the reading falls as the slot")
            o("      # rises. Up rungs highest b first, down rungs lowest b first, so a jump lands on the slot the reading")
            o("      # is in; the Settle rungs above catch a released 0 first.")
            o(f"      Held_{e['name']}:")
            o("        motion: { clip: settling_on }")
            o("        transitions:")
            for ln in settle_rungs:
                o(ln)
            for bb in range(N - 1, 0, -1):
                o(f"          - {{ to: Stamp_{e['name']}_{bb}, when: [ IsLocal is true, {gate}, {e['read']} less {e['up'][bb]}, {V} less {bb - 0.5} ] }}")
            for bb in range(1, N):
                o(f"          - {{ to: Stamp_{e['name']}_{bb - 1}, when: [ IsLocal is true, {gate}, {e['read']} greater {e['down'][bb]}, {V} greater {bb - 0.5} ] }}")
            for k in range(N):
                o(f"      Stamp_{e['name']}_{k}:")
                o("        motion: { clip: settling_tick }")
                o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {V}: {k} }} }} }} ]")
                o("        transitions:")
                o(f"          - {{ to: Held_{e['name']}, when: [], exitTime: 1.0 }}")
        else:
            o(f"      # The wearer alternates A <-> B every frame so each entry re-copies the reading; remotes stay in A.")
            for this, other in (("A", "B"), ("B", "A")):
                o(f"      Held_{e['name']}{this}:")
                o("        motion: { clip: settling_on }")
                o(f"        behaviours: [ {{ driver: {{ localOnly: true, copy: {{ {e['value']}: {{ source: {e['read']}, "
                  f"sourceMin: {e['rLo']}, sourceMax: {e['rHi']}, destMin: 1, destMax: 0 }} }} }} }} ]")
                o("        transitions:")
                for ln in settle_rungs:
                    o(ln)
                o(f"          - {{ to: Held_{e['name']}{other}, when: [ IsLocal is true, {ONE} greater 0.5 ] }}")
    o(f"      # The knob holds where the hand let go for the dwell, while the wearer's last stamp crosses the wire.")
    o("      Settle:")
    o("        motion: { clip: settle }")
    o("        transitions:")
    for e in SL:
        o(f"          - {{ to: {held_entry(e)}, when: [ {gate}, {e['read']} greater {e['floor']} ] }}")
    o("          - { to: Idle, when: [], exitTime: 1.0 }")
    o("    default: Idle")
    o("    layout:")
    sn = ["Idle: [30, 180]", "Settle: [30, 420]"]
    x = -210
    for e in SL:
        if e["kind"] == "slider":
            sn.append(f"Held_{e['name']}: [{x}, 300]")
            sn += [f"Stamp_{e['name']}_{k}: [{x - 240 * (e['N'] - k)}, 420]" for k in range(e["N"])]
            x -= 240 * (e["N"] + 1)
    x = 270
    for e in SL:
        if e["kind"] == "smooth":
            sn += [f"Held_{e['name']}A: [{x}, 300]", f"Held_{e['name']}B: [{x}, 420]"]
            x += 240
    o(f"      nodes: {{ {', '.join(sn)} }}")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    # ---- Lamps ----
    o("  # Every binding is written by exactly one weight-1 child, so the Direct sum is exact.")
    o("  - name: Lamps")
    o("    states:")
    o("      Lamps:")
    o("        motion:")
    o("          tree: direct")
    o("          name: Lamps")
    o("          children:")

    def tree1d(ind, name, param, children, weight=True, threshold=None):
        """A 1D tree as a list item. A child is (clip, threshold) or (subtree emitter, threshold)."""
        p = " " * ind
        o(f"{p}- tree: 1d")
        o(f"{p}  name: {name}")
        o(f"{p}  param: {param}")
        if weight:
            o(f"{p}  directWeight: {ONE}")
        if threshold is not None:
            o(f"{p}  threshold: {threshold}")
        o(f"{p}  children:")
        for ch, t in children:
            if callable(ch):
                ch(ind + 4, t)
            else:
                o(f"{p}    - {{ clip: {ch}, threshold: {t} }}")

    for i in range(nb):
        tree1d(12, f"Btn{i + 1}", BTN[i], [(f"btn{i + 1}_off", 0), (f"btn{i + 1}_on", 1)])
    tree1d(12, "Select", SEL, [(f"sel{k + 1}", k) for k in range(ns)])
    for e in SL:
        n, lo = e["name"], e["name"].lower()
        knob01 = [(f"{lo}_knob0", 0), (f"{lo}_knob1", 1)]
        if e["kind"] == "slider":
            tree1d(12, f"{n}_Lamps", e["value"], [(f"{lo}_seg{k}", k) for k in range(e["N"])])
            value_children = [(f"{lo}_detent{k}", k) for k in range(e["N"])]
        else:
            value_children = knob01

        def from_value(ind, t, e=e, n=n, vc=value_children):
            tree1d(ind, f"{n}_FromValue", e["value"], vc, False, t)

        def hold(ind, t, e=e, n=n, k01=knob01):
            tree1d(ind, f"{n}_Hold", e["knobParam"], k01, False, t)

        def released(ind, t, n=n, fv=from_value, hd=hold):
            tree1d(ind, f"{n}_Released", SETTLING, [(fv, 0), (hd, 1)], False, t)

        def held(ind, t, e=e, n=n, lo=lo):
            tree1d(ind, f"{n}_Held", e["read"], [(f"{lo}_knob1", e["rLo"]), (f"{lo}_knob0", e["rHi"])], False, t)

        o(f"            # {n}'s knob memory: the razor on the reading; below it the settle hold, then the synced value.")
        tree1d(12, f"{n}_Memory", e["read"], [(released, r6(e["floor"] - RAZOR)), (held, e["floor"])])
        tree1d(12, f"{n}_Knob", e["knobParam"], [(f"{lo}_at_lo", 0), (f"{lo}_at_hi", 1)])
    o("    default: Lamps")
    o("")
    # ---- Live ----
    o("  # Caps and knobs sunk and both chains off until the frame's glue says every copy has settled; the crossfade")
    o("  # smooths the shape.")
    o("  - name: Live")
    o("    states:")
    o("      Inert:")
    o("        motion: { clip: inert }")
    o("        transitions:")
    o(f"          - {{ to: Live, when: [ {LIVE} greater 0.5 ], duration: {c['retractTime']} }}")
    o("      Live:")
    o("        motion: { clip: live }")
    o("        transitions:")
    o(f"          - {{ to: Inert, when: [ {LIVE} less 0.5 ], duration: {c['retractTime']} }}")
    o("    default: Inert")
    o("    layout:")
    o("      nodes: { Inert: [30, 180], Live: [270, 180] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    # ---- Offline ----
    o("  # A remote shows the offline lamp until object-sync's word is trustworthy; the wearer never does.")
    o("  - name: Offline")
    o("    states:")
    o("      Offline:")
    o("        motion: { clip: offline }")
    o("        transitions:")
    o("          - { to: Online, when: [ IsLocal is true ] }")
    o("          - { to: Online, when: [ ObjectSync/Enable greater 0.5, OS/Ready greater 0.5 ] }")
    o("      Online:")
    o("        motion: { clip: online }")
    o("        transitions:")
    o("          - { to: Offline, when: [ IsLocal is false, ObjectSync/Enable less 0.5 ] }")
    o("          - { to: Offline, when: [ IsLocal is false, OS/Ready less 0.5 ] }")
    o("    default: Offline")
    o("    layout:")
    o("      nodes: { Offline: [30, 180], Online: [270, 180] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o("clips:")
    o(f"  tick: {{ seconds: {r6(FRAME)} }}")
    if arm:
        o(f"  arm: {{ seconds: {c['arm']} }}")
    o(f"  cooldown: {{ seconds: {c['cooldown']} }}")
    o(f"  settling_off: {{ set: {{ {SETTLING}: 0 }} }}")
    o(f"  settling_on: {{ set: {{ {SETTLING}: 1 }} }}")
    o(f"  settling_tick: {{ seconds: {r6(FRAME)}, set: {{ {SETTLING}: 1 }} }}")
    o(f"  settle: {{ seconds: {c['sliders']['settle']}, set: {{ {SETTLING}: 1 }} }}")
    LB = [f"{shape}{s}" for s in sh["buttons"]]
    for i in range(nb):
        for name, v in (("off", 0), ("on", 100)):
            o(f'  btn{i + 1}_{name}: {{ set: {{ "{LB[i]}": {v} }} }}')
    LSEL = [f"{shape}{s}" for s in sh["selector"]]
    for k in range(ns):
        o(f"  sel{k + 1}:")
        o("    set:")
        for j in range(ns):
            o(f'      "{LSEL[j]}": {100 if j == k else 0}')
    for e in SL:
        n, lo = e["name"], e["name"].lower()
        if e["kind"] == "slider":
            lamps = [f"{shape}{s}" for s in sh[n]]
            for k in range(e["N"]):
                o(f"  {lo}_seg{k}:")
                o("    set:")
                for j in range(e["N"]):
                    o(f'      "{lamps[j]}": {100 if j == k else 0}')
            for k in range(e["N"]):
                o(f"  {lo}_detent{k}: {{ set: {{ {e['knobParam']}: {r6((k + 0.5) / e['N'])} }} }}")
        o(f"  {lo}_knob0: {{ set: {{ {e['knobParam']}: 0 }} }}")
        o(f"  {lo}_knob1: {{ set: {{ {e['knobParam']}: 1 }} }}")
        kp = f"{bone}/{e['knob']}/Transform.m_LocalPosition"
        for cname, xv in (("at_lo", e["x"][0]), ("at_hi", e["x"][1])):
            o(f"  {lo}_{cname}:")
            o("    set:")
            for ax, v in (("x", xv), ("y", e["knobY"]), ("z", e["z"])):
                o(f'      "{kp}.{ax}": {v}')
    o(f'  inert: {{ set: {{ "{RETRACT}": 100, {", ".join(f"{chr(34)}{ch}{chr(34)}: 0" for ch in CHAINS)} }} }}')
    o(f'  live: {{ set: {{ "{RETRACT}": 0, {", ".join(f"{chr(34)}{ch}{chr(34)}: 1" for ch in CHAINS)} }} }}')
    o(f'  offline: {{ set: {{ "{LO}": 100 }} }}')
    o(f'  online: {{ set: {{ "{LO}": 0 }} }}')
    return "\n".join(L) + "\n"


def held_entry(e):
    return f"Held_{e['name']}" + ("A" if e["kind"] == "smooth" else "")


# ---- --check: Panel.prefab's hand-built surface, which no compile or gate reads ----
# Serialized enum values (VRC SDK): MultiChildType Ignore 0; AdvancedBool False 0 / True 1; LimitType None 0 / Angle 1;
# ImmobileType AllMotion 0; contact ShapeType Sphere 0 / Capsule 1 / Box 2; ReceiverType Proximity 2.
def docs_of(path):
    """fileID -> (class id, body, stripped)."""
    return {int(m.group(2)): (int(m.group(1)), m.group(4), bool(m.group(3))) for m in re.finditer(
        r"^--- !u!(\d+) &(-?\d+)( stripped)?\n(.*?)(?=^--- |\Z)", open(path, encoding="utf-8").read(), re.M | re.S)}


def fid(d, key):
    m = re.search(rf"^  {key}: \{{fileID: (-?\d+)", d, re.M)
    return int(m.group(1)) if m else None


def vec(d, key):
    m = re.search(rf"^  {key}: \{{x: (\S+), y: (\S+), z: (\S+)(?:, w: (\S+))?\}}", d, re.M)
    return tuple(float(v) for v in m.groups() if v is not None) if m else None


def field(d, key):
    m = re.search(rf"^  {key}:(.*)$", d, re.M)
    return m.group(1).strip() if m else None


def close(a, b, eps=1e-5):
    return a is not None and len(a) == len(b) and all(abs(x - y) <= eps for x, y in zip(a, b))


def quat(e):
    """Unity Euler degrees (applied Z, then X, then Y) -> (x, y, z, w)."""
    def axis(ax, deg):
        h = math.radians(deg) / 2
        v = [0.0, 0.0, 0.0]
        v[ax] = math.sin(h)
        return (v[0], v[1], v[2], math.cos(h))
    return qmul(qmul(axis(1, e[1]), axis(0, e[0])), axis(2, e[2]))


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def same_rot(got, want):
    return got is not None and abs(abs(sum(a * b for a, b in zip(got, want))) - 1) < 1e-5


def rotate(q, v):
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx)


def tags_of(d):
    m = re.search(r"^  collisionTags:\n((?:  - .+\n)+)", d, re.M)
    return [ln.split("- ", 1)[1].strip() for ln in m.group(1).splitlines()] if m else []


def check(c, prefab_path):
    """Panel.prefab against CONFIG. Reads the YAML textually; a field it cannot find is a FAIL, never a pass."""
    r = rig(c)
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    if not A(os.path.exists(prefab_path), f"{prefab_path} exists"):
        return False
    docs = docs_of(prefab_path)
    A(not any(st for _, _, st in docs.values()) and not any(cls == 1001 for cls, _, _ in docs.values()),
      "no prefab instance inside: the model is unpacked, so every bone is a named node")
    name = {i: field(d, "m_Name") for i, (cls, d, _) in docs.items() if cls == 1}
    tf = {i: d for i, (cls, d, _) in docs.items() if cls == 4}
    go_tf = {fid(d, "m_GameObject"): i for i, d in tf.items()}

    def path_of(t):
        parts = []
        while t in tf and fid(tf[t], "m_Father"):
            parts.append(name[fid(tf[t], "m_GameObject")])
            t = fid(tf[t], "m_Father")
        return "/".join(reversed(parts))

    tf_at = {path_of(t): t for t in tf}
    bone = f"{c['armature']}/Panel"
    # Bone rest poses in the Panel bone's frame (the panel frame); each step carries its parent's local rotation.
    for rel, want in r["bones"].items():
        if not A(f"{bone}/{rel}" in tf_at, f"bone {bone}/{rel} present"):
            continue
        pos, rot, acc = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), bone
        for seg in rel.split("/"):
            acc = f"{acc}/{seg}"
            d = tf[tf_at[acc]]
            pos = tuple(p + q for p, q in zip(pos, rotate(rot, vec(d, "m_LocalPosition"))))
            rot = qmul(rot, vec(d, "m_LocalRotation"))
        A(close(pos, tuple(want), 1e-4), f"{bone}/{rel} rests at {want} in the panel frame (got {[round(v, 5) for v in pos]})")
    for e in r["sliders"]:
        at = f"{bone}/Sliders/{e['bone']}"
        if at in tf_at:
            along = rotate(vec(tf[tf_at[at]], "m_LocalRotation"), (0, 1, 0))
            A(close(along, (1, 0, 0), 1e-4), f"{e['bone']}'s local +Y points along the track (+X) (got {[round(v, 4) for v in along]})")
        at = f"{bone}/{e['knob']}"
        if at in tf_at:
            A(same_rot(vec(tf[tf_at[at]], "m_LocalRotation"), (0, 0, 0, 1)),
              f"{e['knob']} carries no local rotation, so the knob clips' m_LocalPosition is a panel-frame position")
    root_go = next((fid(d, "m_GameObject") for d in tf.values() if not fid(d, "m_Father")), None)
    A(name.get(root_go) == "Panel", f"root is Panel (got {name.get(root_go)})")
    A(c["mesh"] in tf_at, f"mesh node {c['mesh']} present (the lamp clips bind {c['mountPath']}/{c['mesh']})")

    comps = [d for cls, d, _ in docs.values() if cls == 114]
    host = lambda d: path_of(go_tf.get(fid(d, "m_GameObject")))
    pbs = [d for d in comps if re.search(r"^  multiChildType:", d, re.M)]
    recv = [d for d in comps if re.search(r"^  receiverType:", d, re.M)]
    send = [d for d in comps if re.search(r"^  collisionTags:", d, re.M) and not re.search(r"^  receiverType:", d, re.M)]
    ncap = sum(len(v) for v in r["receiver"]["params"].values())
    nsl = len(r["sliders"])
    want_n = 2 + ncap + nsl + len(r["senders"]) + nsl
    A(len(comps) == want_n and len(pbs) == 2 and len(recv) == ncap + nsl and len(send) == len(r["senders"]) + nsl,
      f"two physbones, {ncap + nsl} receivers and {len(r['senders']) + nsl} senders, nothing else "
      f"(want {want_n} MonoBehaviours, got {len(comps)}: {len(pbs)} physbones, {len(recv)} receivers, {len(send)} senders)")

    def physbone(at, want, extra):
        d = next((p for p in pbs if host(p) == at), None)
        if not A(d is not None, f"a physbone on {at}"):
            return
        A(fid(d, "rootTransform") == tf_at.get(at), f"{at}: rootTransform is {at}")
        flds = {"parameter": want["parameter"], "maxSquish": want["maxSquish"], "maxStretch": want["maxStretch"],
                "radius": want["radius"], "pull": want["pull"], "spring": 0, "stiffness": 0, "gravity": 0,
                "multiChildType": "0", "immobileType": "0", "immobile": 1, "isAnimated": "0", "resetWhenDisabled": "1",
                "ignoreTransforms": "[]", "colliders": "[]"}
        flds.update(extra)
        for k, v in flds.items():
            got = field(d, k)
            good = (got is not None and abs(float(got) - v) < 1e-5) if isinstance(v, (int, float)) else got == v
            A(good, f"{at}: {k} == {v!r} (got {got!r})")

    physbone(f"{bone}/Buttons", r["buttonsPhysBone"], {"limitType": "1", "maxAngleX": 0, "snapToHand": "0",
                                                      "allowCollision": "1", "allowGrabbing": "0", "allowPosing": "0"})
    sp = r["slidersPhysBone"]
    physbone(f"{bone}/Sliders", sp, {"limitType": "0", "snapToHand": "1", "grabMovement": sp["grabMovement"],
                                     "allowCollision": "0", "allowGrabbing": "1", "allowPosing": "0"})

    def receiver(d, at, prm, rv, local):
        A(field(d, "parameter") == prm, f"{at}: parameter {prm} (got {field(d, 'parameter')})")
        A(tags_of(d) == [rv["tag"]], f"{at} {prm}: tags == [{rv['tag']}] (got {tags_of(d)})")
        for k, v in (("shapeType", "2"), ("useFaceProximity", "1"), ("receiverType", "2"), ("localOnly", local),
                     ("allowSelf", "1"), ("allowOthers", "0")):
            A(field(d, k) == v, f"{at} {prm}: {k} == {v} (got {field(d, k)})")
        A(fid(d, "rootTransform") in (0, tf_at.get(at)), f"{at} {prm}: rides its host")
        A(close(vec(d, "size"), tuple(rv["size"])), f"{at} {prm}: box size {rv['size']} (got {vec(d, 'size')})")
        A(close(vec(d, "position"), tuple(rv["position"])), f"{at} {prm}: box offset {rv['position']} (got {vec(d, 'position')})")
        A(same_rot(vec(d, "rotation"), quat(rv["rotation"])), f"{at} {prm}: box rotation Euler {rv['rotation']}")

    rv = r["receiver"]
    nm = r["names"]
    for kind in ("buttons", "selector"):
        for prm, b_, end in zip(rv["params"][kind], nm[kind], nm[END_KEY[kind]]):
            at = f"{bone}/Buttons/{b_}/{end}"
            d = next((x for x in recv if host(x) == at), None)
            if A(d is not None, f"a receiver on {at}"):
                receiver(d, at, prm, rv, "1")
    for e in r["sliders"]:
        d = next((x for x in recv if host(x) == bone and field(x, "parameter") == e["read"]), None)
        if A(d is not None, f"a {e['name']} slider box receiver ({e['read']}) on {bone}"):
            receiver(d, bone, e["read"], e["receiver"], "0")
        at = f"{bone}/Sliders/{e['bone']}/{e['end']}"
        d = next((x for x in send if host(x) == at), None)
        sv = e["sender"]
        if A(d is not None, f"a sender on {at}"):
            A(tags_of(d) == [sv["tag"]], f"{at}: sender tags == [{sv['tag']}] (got {tags_of(d)})")
            A(field(d, "shapeType") == "0" and field(d, "localOnly") == "0", f"{at}: a non-local sphere sender")
            A(fid(d, "rootTransform") in (0, tf_at.get(at)), f"{at}: sender rides its End")
            A(field(d, "radius") is not None and abs(float(field(d, "radius")) - sv["radius"]) < 1e-6, f"{at}: sender radius == {sv['radius']}")
            A(close(vec(d, "position"), tuple(sv["position"])), f"{at}: sender at the End's origin")
    row_senders = [d for d in send if host(d) == bone]
    A(len(row_senders) == len(r["senders"]), f"{len(r['senders'])} row senders on {bone} (got {len(row_senders)})")
    for sv in r["senders"]:
        d = next((x for x in row_senders if close(vec(x, "position"), tuple(sv["position"]))), None)
        if not A(d is not None, f"{sv['name']} ({sv['row']} row) on {bone} at {sv['position']} (top surface on bottom-out)"):
            continue
        A(tags_of(d) == [sv["tag"]], f"{sv['name']}: tags == [{sv['tag']}] (got {tags_of(d)})")
        A(field(d, "shapeType") == "1" and field(d, "localOnly") == "1", f"{sv['name']}: a local-only capsule")
        A(fid(d, "rootTransform") in (0, tf_at.get(bone)), f"{sv['name']}: rides {bone}")
        for k in ("radius", "height"):
            A(field(d, k) is not None and abs(float(field(d, k)) - sv[k]) < 1e-6, f"{sv['name']}: {k} == {sv[k]}")
        A(same_rot(vec(d, "rotation"), quat(sv["rotation"])), f"{sv['name']}: capsule lies along X")
    return ok


def main():
    if "--check" in sys.argv:
        good = check(CONFIG, os.path.join(HERE, "Panel.prefab"))
        print("OK" if good else "FAILED")
        return 0 if good else 1
    text = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    r = rig(CONFIG)
    print(f"wrote controls/controller.yaml ({CONFIG['controller']}): cap press/release readings "
          f"{r['thresholds']['press']}/{r['thresholds']['release']}; "
          + "; ".join(f"{e['name']} r_lo/r_hi/floor {e['rLo']}/{e['rHi']}/{e['floor']}, L {e['boneLength']}" for e in r["sliders"])
          + f"; Sliders maxStretch {r['slidersPhysBone']['maxStretch']}")


if __name__ == "__main__":
    sys.exit(main())
