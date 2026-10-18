"""Build the control panel: one skinned, flat-shaded, low-poly mesh `ControlPanel`, its armature, its atlas.

Every interface number (plate extent, grip axis, the four rows, lamp parks, shape and bone names, bone rest
poses) is read from `rig.json`, which `../generate.py` emits; the constants below are only the look - bevels,
wells, channels, facet counts - and nothing outside this file reads them.

Frame: authored throughout in the **Unity** panel frame that `rig.json` states - X along the long axis
(handle A at -X), +Y the face normal, +Z the far edge, metres - and converted once, per vertex and per bone, by
`u2b`. The conversion carries the X negation absolute-grip-prop's `Hands_build.py` documents: an armature FBX
export (`bake_space_transform` off) maps Blender (x, y, z) to Unity (-x, z, -y), so a part authored at Unity -X
must sit at Blender +X. The panel is chiral (the slider chains root at -X), so a
dropped negation shows as a mirrored panel. Verify after any exporter change by re-importing the FBX and
reading bone heads in the Unity frame, never the Blender ones.

Rows, far edge to near: toggle buttons (domed caps in round wells, a dot lamp beyond each), the selector (one
strip: four near-full-width segments, `selector.segmentWidth` along X and the caps' diameter in Z, on the buttons'
joint, with seams between, in one shared tray whose two ends are rounded; the end segments' outer corners follow
the tray's rounding, concentric with it, and every other corner is square with the chamfer; beyond each segment the
button row's dot lamp, at the button dots' z offset from their caps), the discrete slider (a knob in a recessed
channel, detent ticks, one segment lamp per slot), the smooth slider (a knob in a channel, and the strip). Bones
are placed at `restPoses` exactly; the geometry is asserted against them.

The strip: one always-lit bar at `strip.z`, `strip.width` across Z (rig.json puts it in the discrete slider's
segment-lamp row geometry), from the track's low end (`strip.x`) to `STRIP_LEAD` past the knob's centre. It sits
permanently at a lit lamp's height (top at `lamps.raised`, `LAMP_THICK` deep), so it reads as high as a lit
segment. Its near-end verts are skinned to `Panel` and its far-end verts to the knob bone, so it stretches as the
knob translates. It shows the knob, not the accepted value; at rest the knob lands on the synced value.

Shells: the plate is one shell - bezel, necks and ridged grips unioned; cap wells, the selector tray, knob
channels and detent ticks cut - by Boolean modifiers (Manifold solver), so its parts never
show interior walls. Each cap, each knob, each lamp and the strip is its own closed shell, because each moves on
its own (a bone or a blendshape). A lamp is a thin disc or bar parked under the opaque face and raised through it by its
key; nothing else hides it. A cap's skirt and a knob's foot reach below their well or channel floor when sunk,
into the plate's solid, which hides them; the asserts keep them above the plate's underside.

Shapes: every lamp key raises its lamp by `lamps.raised - lamps.parked`. `Lamp_Sel<k>` also sinks cap k by
`selector.sink`, one key, so the chosen cap rests depressed and lit. `Controls_Retract` sinks every cap by
`controlsRetract.capDepth` and every knob by `controlsRetract.channelDepth` (flush with the face). Caps and
knobs ride bones that only translate, so a bind-space key holds at any chain or knob position. The strip has no
key and stays lit when retracted; it lies outside the knob's channel, so the retract never meets it.

Colour: a palette atlas of flat swatches, one material slot. Every face's UVs sit on one swatch centre, so a
consumer recolours a part by repainting its square. The emission atlas is black except the two lamp swatches (amber and the unused red).

Run: blender --background --factory-startup --python ControlPanel_build.py -- <rig.json> <out.blend> [<atlas dir>]
The atlas PNGs land in <atlas dir>, default beside the .blend.
"""
import sys, os, json, math, struct, zlib, bpy, bmesh

argv = sys.argv[sys.argv.index("--") + 1:]
rig_path, out_blend = argv[0], os.path.abspath(argv[1])
atlas_dir = os.path.abspath(argv[2]) if len(argv) > 2 else os.path.dirname(out_blend)
with open(rig_path, encoding="utf-8") as f:
    R = json.load(f)

PX0, PX1 = R["plate"]["x"]; PZ0, PZ1 = R["plate"]["z"]
TOP, BOTTOM = R["plate"]["top"], R["plate"]["bottom"]
GX, GR = R["grips"]["x"], R["grips"]["radius"]; GZ0, GZ1 = R["grips"]["z"]
RIDGE_R = R["grips"]["ridge"]   # the ridges' height proud of GR; generate.py's grip coverage check counts it
B = R["buttons"]; BL = R["buttonLamps"]; SEL = R["selector"]; SL = R["sliders"]
LAMP = R["lamps"]; RET = R["controlsRetract"]; NAMES = R["bones"]; REST = R["restPoses"]
for what, lst, n in (("bones.buttons", NAMES["buttons"], len(B["x"])), ("bones.buttonEnds", NAMES["buttonEnds"], len(B["x"])),
                     ("buttonLamps.shapes", BL["shapes"], len(B["x"])), ("bones.selector", NAMES["selector"], len(SEL["x"])),
                     ("bones.selectorEnds", NAMES["selectorEnds"], len(SEL["x"])), ("selector.shapes", SEL["shapes"], len(SEL["x"])),
                     ("bones.sliders", NAMES["sliders"], len(SL)), ("bones.knobs", NAMES["knobs"], len(SL))):
    assert len(lst) == n, f"{what} names {len(lst)} but the rows place {n}"
for s in SL:
    assert ("segments" in s) == (s["kind"] == "slider") and ("strip" in s) == (s["kind"] == "smooth"),         f"slider {s['name']}: a discrete slider carries segments, a smooth one a strip"
    assert s["bone"] in NAMES["sliders"] and s["end"] in NAMES["sliderEnds"] and s["knob"] in NAMES["knobs"], s["name"]

# ---- the look (m); nothing outside this file reads these ----------------------------------------------
CORNER = 0.014            # plate corner chamfer, leg length
BEZEL_H = 0.004           # bezel rise above the face
BEZEL_W = 0.004           # bezel width, outer edge to where it meets the face
TOP_CHAMFER = 0.0015      # bezel's outer top edge
BOTTOM_CHAMFER = 0.004
WELL_CLEAR = 0.003        # well radius beyond the cap
WELL_FLOOR = 0.004        # button well floor height; below the cap's lowest squash
WELL_CHAMFER = 0.0015
WELL_GAP = 0.003          # a selector well's floor under the lowest crown it must hold
SINK_MARGIN = 0.002       # what a sunk crown keeps above its floor and a sunk skirt or foot above the underside
CAP_SEG, WELL_SEG, LAMP_SEG, GRIP_SEG = 16, 16, 12, 8
SEL_ARC = 6               # facets on each rounded end of the selector tray and its end segments
SEL_CORNER = 0.002        # a selector segment's square corners
SEL_CHAMFER = 0.002       # a selector segment's top edge
CH_CLEAR = 0.002          # channel clearance around the knob, each side
CH_CORNER, CH_CHAMFER = 0.003, 0.0015
KNOB_LIFT, KNOB_CHAMFER, KNOB_CORNER = 0.0005, 0.003, 0.002   # foot above the channel floor at rest
FIN_W, FIN_H, FIN_SPAN = 0.003, 0.0025, 0.8   # the pointer fin across the knob top; span as a fraction of its Z
TICK_W, TICK_D, TICK_GAP, TICK_LEN = 0.002, 0.0015, 0.003, 0.006   # detent ticks off the channel's lamp side
LAMP_THICK = 0.002
STRIP_LEAD = 0.005        # the strip's far end past the knob's centre: its length at x_lo, so it is never degenerate
GRIP_END_CHAMFER = 0.004
RIDGES, RIDGE_W, RIDGE_GAP = 5, 0.007, 0.011   # count, width, gap (their height, RIDGE_R, is rig.json's)
NECK_HALF_Y, NECK_HALF_Z, NECK_Z, NECK_INTO = 0.007, 0.006, 0.058, 0.006

# ---- atlas -----------------------------------------------------------------------------------------------
ATLAS, GRID = 128, 4
SWATCHES = {   # name: (index, albedo sRGB, emission sRGB)
    "body":  (0, (44, 50, 58), None),
    "bezel": (1, (92, 98, 106), None),
    "cap":   (2, (226, 222, 210), None),
    "knob":  (3, (64, 124, 128), None),
    "amber": (4, (255, 170, 40), (255, 160, 30)),
    "red":   (5, (235, 45, 35), (255, 40, 25)),   # unused since the offline lamp was dropped; kept so the atlas holds
    "label": (6, (140, 143, 148), None),   # unused since the label strip was dropped; kept so the atlas holds
    "tick":  (7, (210, 208, 196), None),
    "well":  (8, (24, 27, 31), None),
    "grip":  (9, (30, 32, 36), None),
    "rail":  (10, (110, 116, 124), None),   # unused since the channels replaced the rail; kept so the atlas holds
}


def swatch_uv(name):
    i = SWATCHES[name][0]
    return ((i % GRID + 0.5) / GRID, 1.0 - (i // GRID + 0.5) / GRID)


def write_png(path, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", ATLAS, ATLAS, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write_atlases():
    cell = ATLAS // GRID
    by_index = {v[0]: v for v in SWATCHES.values()}
    fill = SWATCHES["body"]
    for kind, path in (("albedo", "ControlPanel_Albedo.png"), ("emission", "ControlPanel_Emission.png")):
        rows = []
        for py in range(ATLAS):
            row = []
            for px in range(ATLAS):
                sw = by_index.get((py // cell) * GRID + px // cell, fill)
                c = sw[1] if kind == "albedo" else (sw[2] or (0, 0, 0))
                row += c
            rows.append(row)
        write_png(os.path.join(atlas_dir, path), rows)


# ---- geometry primitives, Unity frame -------------------------------------------------------------------
def u2b(p):
    """Unity panel frame -> Blender. See the docstring: the X negation is load-bearing."""
    return (-p[0], -p[2], p[1])


def rect_pts(hx, hz, c):
    if c > 1e-6:
        return ((hx, hz - c), (hx - c, hz), (-hx + c, hz), (-hx, hz - c),
                (-hx, -hz + c), (-hx + c, -hz), (hx - c, -hz), (hx, -hz + c))
    return ((hx, hz), (-hx, hz), (-hx, -hz), (hx, -hz))


def ring_at(bm, pts, y, cx=0.0, cz=0.0):
    return [bm.verts.new((cx + px, y, cz + pz)) for px, pz in pts]


def rect_ring(bm, hx, hz, c, y, cx=0.0, cz=0.0):
    return ring_at(bm, rect_pts(hx, hz, c), y, cx, cz)


def loft(bm, rings):
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))


def box(bm, x0, x1, y0, y1, z0, z1, c=0.0):
    hx, hz, cx, cz = (x1 - x0) / 2, (z1 - z0) / 2, (x0 + x1) / 2, (z0 + z1) / 2
    loft(bm, [rect_ring(bm, hx, hz, c, y0, cx, cz), rect_ring(bm, hx, hz, c, y1, cx, cz)])


def revolve(bm, profile, axis, centre, seg):
    """profile: (t, r) along the axis; centre: the axis position in the other two coordinates."""
    rings = []
    for t, r in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg + math.pi / seg
            u, v = r * math.cos(a), r * math.sin(a)
            if axis == "Y":     # centre = (x, z)
                ring.append(bm.verts.new((centre[0] + u, t, centre[1] + v)))
            else:               # axis Z, centre = (x, y)
                ring.append(bm.verts.new((centre[0] + u, centre[1] + v, t)))
        rings.append(ring)
    loft(bm, rings)


def half_arc(cx, h, a0):
    """SEL_ARC facets of a half circle of radius h about (cx, 0), from angle a0 through a0 + pi."""
    return [(cx + h * math.cos(a), h * math.sin(a)) for a in (a0 + math.pi * i / SEL_ARC for i in range(SEL_ARC + 1))]


def seg_pts(h, side):
    """A selector segment's outline at half-depth h (CAP_R is the segment itself; other h are offsets of it by
    h - CAP_R): side 0 a rectangle with chamfered corners, -1 / +1 rounded on that X side by a half circle concentric
    with the tray's end, the inner side square. The point count is the same for every h, so outlines at several
    sizes loft."""
    c = SEL_CORNER * h / CAP_R
    hx = SEG_HX + h - CAP_R
    if side == 0:
        return rect_pts(hx, h, c)
    pts = half_arc(SEG_HX - CAP_R, h, -math.pi / 2) + [(-hx + c, h), (-hx, h - c), (-hx, -h + c), (-hx + c, -h)]
    return [(side * u, v) for u, v in pts]


def tray_pts(h):
    """The selector tray's outline at half-depth h, centred on the row: straight sides, both ends half circles
    concentric with the end segments' rounding."""
    e = TRAY_HX - CAP_R
    return half_arc(e, h, -math.pi / 2) + half_arc(-e, h, math.pi / 2)


def part(name, fill):
    bm = bmesh.new()
    fill(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def combine(base, unions, cuts):
    """Apply unions then cuts to `base` with Boolean modifiers; return (verts, polys) of the result."""
    solver = "MANIFOLD"
    for op, obs in (("UNION", unions), ("DIFFERENCE", cuts)):
        for o in obs:
            m = base.modifiers.new(f"{op}_{o.name}", "BOOLEAN")
            m.operation, m.solver, m.object = op, solver, o
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
    verts = [tuple(v.co) for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    for o in [base] + unions + cuts:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.meshes.remove(me)
    return verts, polys


def plain(ob):
    verts = [tuple(v.co) for v in ob.data.vertices]
    polys = [tuple(p.vertices) for p in ob.data.polygons]
    bpy.data.objects.remove(ob, do_unlink=True)
    return verts, polys


# ---- the layout, asserted against the rest poses ---------------------------------------------------------
HX, HZ = (PX1 - PX0) / 2, (PZ1 - PZ0) / 2
assert abs(PX0 + PX1) < 1e-9 and abs(PZ0 + PZ1) < 1e-9, "plate must be centred on the Panel bone"
CAP_R = B["capDiameter"] / 2
WELL_R = CAP_R + WELL_CLEAR
CAP_BOTTOM = TOP - B["travel"]          # a cap stands `travel` proud of the face; its skirt reaches as far below it
LAMP_DY = LAMP["raised"] - LAMP["parked"]
assert LAMP["parked"] < TOP < LAMP["raised"], "a lamp parks under the face and its key raises it through"


def near(a, b):
    return all(abs(p - q) < 1e-6 for p, q in zip(a, b))


TIP = B["capTop"] - B["chainRadius"]    # each cap chain's tip rests chainRadius under its crown
for row, bones, ends in ((B, NAMES["buttons"], NAMES["buttonEnds"]), (SEL, NAMES["selector"], NAMES["selectorEnds"])):
    for x, b, e in zip(row["x"], bones, ends):
        assert near(REST[f"Buttons/{b}/{e}"], (x, TIP, row["z"])), f"{e} rest pose is not the cap's tip"
        assert near(REST[f"Buttons/{b}"], (x, TIP - B["boneLength"], row["z"])), f"{b} rest pose is not the tip less boneLength"
for s in SL:
    assert near(REST[f"Sliders/{s['bone']}"], (s["rootX"], s["y"], s["z"])), f"{s['bone']} rest pose"
    assert near(REST[f"Sliders/{s['bone']}/{s['end']}"], (s["tipRestX"], s["y"], s["z"])), f"{s['end']} rest pose"
    assert abs(s["rootX"] + s["boneLength"] - s["tipRestX"]) < 2e-6, f"{s['bone']}: rootX + boneLength is not tipRestX"
    assert near(REST[s["knob"]], (s["x"][0], s["knobY"], s["z"])), f"{s['knob']} rest pose is not (x_lo, knobY, z)"
    assert abs(s["channelDepth"] - RET["channelDepth"]) < 1e-9, "a channel's depth is the knob's retract"

# Every cap: past flush its chain lets it sink `squish - travel` further. The selector's chosen cap also rests
# sunk `sink` by its lamp key, so a press takes it `sink + squish` down; inert, the retract stacks on the lamp
# key instead (the chain is off then, so the retract never meets a press). Its crown must stay above its well
# floor (or the floor would cut through it) and its skirt above the plate's underside.
BTN_DROP = max(B["squish"], RET["capDepth"])
SEL_DROP = max(SEL["sink"] + B["squish"], SEL["sink"] + RET["capDepth"])
SEL_FLOOR = B["capTop"] - SEL_DROP - WELL_GAP
for what, drop, floor in (("button", BTN_DROP, WELL_FLOOR), ("selector", SEL_DROP, SEL_FLOOR)):
    assert B["capTop"] - drop > floor + SINK_MARGIN, f"a fully sunk {what} cap's crown passes its well floor"
    assert CAP_BOTTOM - drop > BOTTOM + SINK_MARGIN, \
        f"a fully sunk {what} cap's skirt ({CAP_BOTTOM - drop:.4f}) leaves the plate's underside ({BOTTOM}) by the margin"
    assert floor > BOTTOM + BOTTOM_CHAMFER, f"the {what} well floor passes the plate's underside"
SEL_SIDE = [-1 if i == 0 else 1 if i == len(SEL["x"]) - 1 else 0 for i in range(len(SEL["x"]))]
SEL_WELL_H = CAP_R + WELL_CLEAR          # the tray's half-depth: WELL_CLEAR round every segment
SEG_HX = SEL["segmentWidth"] / 2
SEL_XS = sorted(SEL["x"])
assert list(SEL["x"]) == SEL_XS, "selector x runs low to high, so the first and last segments are the rounded ends"
assert SEG_HX >= CAP_R, "a selector segment is at least as wide as it is deep, so its rounded end is a half circle"
assert min(b - a for a, b in zip(SEL_XS, SEL_XS[1:])) > 2 * SEG_HX, "selector segments overlap: no seam between them"
TRAY_CX = (SEL_XS[0] + SEL_XS[-1]) / 2
TRAY_HX = (SEL_XS[-1] - SEL_XS[0]) / 2 + SEG_HX   # the segments' span; the tray outline adds WELL_CLEAR round it
assert all(abs(x - TRAY_CX) <= TRAY_HX - SEG_HX + 1e-9 for x in SEL_XS)


def slider_layout(s):
    lo, hi = s["x"]
    khx, khz = s["knobSize"][0] / 2, s["knobSize"][1] / 2
    cd = s["channelDepth"]
    lamps = s.get("segments")
    n = len(lamps["shapes"]) if lamps else 0
    return {"lo": lo, "hi": hi, "z": s["z"], "khx": khx, "khz": khz, "cd": cd, "floor": TOP - cd,
            "chx": (hi - lo) / 2 + khx + CH_CLEAR, "chz": khz + CH_CLEAR, "cx": (lo + hi) / 2,
            "foot": TOP - cd + KNOB_LIFT, "crown": TOP + cd, "lamps": lamps, "strip": s.get("strip"), "n": n,
            "pitch": (hi - lo) / n if n else None,
            "ticks": [lo + k * (hi - lo) / n for k in range(1, n)] if s["kind"] == "slider" else []}


SLY = [slider_layout(s) for s in SL]
for s, L in zip(SL, SLY):
    # Retracted, the knob's crown is flush with the face and its foot sinks into the plate's solid.
    assert L["foot"] - L["cd"] > BOTTOM + SINK_MARGIN, f"{s['name']}: a retracted knob's foot leaves the underside"
    assert L["foot"] > L["floor"], f"{s['name']}: the knob's foot passes its channel floor at rest"
    assert L["chz"] > L["khz"] and L["chx"] - (L["hi"] - L["lo"]) / 2 > L["khx"], f"{s['name']}: the channel fits the knob's travel"
    assert L["foot"] < TOP, f"{s['name']}: the knob sits in its channel"
    if L["lamps"]:
        lz = L["lamps"]["z"]
        gap = abs(lz - L["z"]) - L["chz"] - L["lamps"]["depth"] / 2
        assert gap > TICK_GAP + TICK_LEN + 0.002, f"{s['name']}: its lamps crowd its channel"
    if L["strip"]:
        st = L["strip"]
        assert SWATCHES.get(st["swatch"], (0, 0, None))[2], f"{s['name']}: strip swatch {st['swatch']!r} has no emission"
        assert abs(st["x"] - L["lo"]) < 1e-9, f"{s['name']}: the strip starts at x_lo"
        assert STRIP_LEAD > 0, f"{s['name']}: the strip needs a length at x_lo"
        # Where it pierces the face, its band clears the channel's flared mouth, so it never cuts the channel.
        gap = abs(st["z"] - L["z"]) - L["chz"] - CH_CHAMFER - st["width"] / 2
        assert gap > 0.002, f"{s['name']}: the strip's band ({gap * 1000:.1f} mm) crowds its channel"
        # Seated like a lit lamp: its top through the face, its bottom inside the plate's solid.
        assert LAMP["raised"] - LAMP_THICK < TOP < LAMP["raised"], f"{s['name']}: the strip is not seated through the face"


def octagon_inset(x, z):
    """Distance inside the plate's outer outline (negative outside)."""
    ax, az = abs(x), abs(z)
    return min(HX - ax, HZ - az, (HX + HZ - CORNER - ax - az) / math.sqrt(2))


def footprints():
    """(name, x0, x1, z0, z1) of everything set into or lit through the face, to prove nothing collides."""
    out = [(f"well {x}", x - WELL_R - WELL_CHAMFER, x + WELL_R + WELL_CHAMFER, B["z"] - WELL_R - WELL_CHAMFER,
            B["z"] + WELL_R + WELL_CHAMFER) for x in B["x"]]
    h = SEL_WELL_H + WELL_CHAMFER
    e = TRAY_HX + WELL_CLEAR + WELL_CHAMFER
    out.append(("selector tray well", TRAY_CX - e, TRAY_CX + e, SEL["z"] - h, SEL["z"] + h))
    r = SEL["lamps"]["diameter"] / 2
    out += [(f"selector lamp {x}", x - r, x + r, SEL["lamps"]["z"] - r, SEL["lamps"]["z"] + r) for x in SEL["x"]]
    r = BL["diameter"] / 2
    out += [(f"button lamp {x}", x - r, x + r, BL["z"] - r, BL["z"] + r) for x in B["x"]]
    for s, L in zip(SL, SLY):
        e = L["chx"] + CH_CHAMFER
        out.append((f"{s['name']} channel", L["cx"] - e, L["cx"] + e, L["z"] - L["chz"] - CH_CHAMFER, L["z"] + L["chz"] + CH_CHAMFER))
        if L["strip"]:   # its whole sweep, the knob from x_lo to x_hi
            st = L["strip"]
            out.append((f"{s['name']} strip", L["lo"], L["hi"] + STRIP_LEAD, st["z"] - st["width"] / 2, st["z"] + st["width"] / 2))
        for i in range(L["n"]):
            w, lz = L["pitch"] * L["lamps"]["widthFraction"], L["lamps"]["z"]
            cx = L["lo"] + (i + 0.5) * L["pitch"]
            out.append((f"{s['name']} lamp {i}", cx - w / 2, cx + w / 2, lz - L["lamps"]["depth"] / 2, lz + L["lamps"]["depth"] / 2))
        for i, tx in enumerate(L["ticks"]):
            z0, z1 = tick_z(L)
            out.append((f"{s['name']} tick {i}", tx - TICK_W / 2, tx + TICK_W / 2, z0, z1))
    return out


def tick_z(L):
    sgn = 1 if L["lamps"]["z"] > L["z"] else -1
    a = L["z"] + sgn * (L["chz"] + TICK_GAP)
    b = a + sgn * TICK_LEN
    return min(a, b), max(a, b)


FOOT = footprints()
for i, (na, a0, a1, b0, b1) in enumerate(FOOT):
    for c in ((a0, b0), (a0, b1), (a1, b0), (a1, b1)):
        assert octagon_inset(*c) > BEZEL_W + 0.002, f"{na} reaches the bezel"
    for nb, c0, c1, d0, d1 in FOOT[i + 1:]:
        assert not (a0 < c1 + 0.001 and c0 < a1 + 0.001 and b0 < d1 + 0.001 and d0 < b1 + 0.001), f"{na} collides with {nb}"


def plate_rings(bm):
    def ring(d, y):
        return rect_ring(bm, HX - d, HZ - d, CORNER - d * (math.sqrt(2) - 1), y)
    loft(bm, [ring(BOTTOM_CHAMFER, BOTTOM), ring(0.0, BOTTOM + BOTTOM_CHAMFER),
              ring(0.0, TOP + BEZEL_H - TOP_CHAMFER), ring(TOP_CHAMFER, TOP + BEZEL_H),
              ring(BEZEL_W - 0.001, TOP + BEZEL_H), ring(BEZEL_W, TOP)])


def grip_profile():
    r0, r1 = GR, GR + RIDGE_R
    prof = [(GZ0, r0 - GRIP_END_CHAMFER), (GZ0 + GRIP_END_CHAMFER, r0)]
    span = RIDGES * RIDGE_W + (RIDGES - 1) * RIDGE_GAP
    z = -span / 2 + (GZ0 + GZ1) / 2
    for _ in range(RIDGES):
        prof += [(z, r0), (z + 0.0015, r1), (z + RIDGE_W - 0.0015, r1), (z + RIDGE_W, r0)]
        z += RIDGE_W + RIDGE_GAP
    prof += [(GZ1 - GRIP_END_CHAMFER, r0), (GZ1, r0 - GRIP_END_CHAMFER)]
    return prof


def flared_cut(bm, pts_of, h, floor, chamfer, cx, cz):
    """A well or channel cutter: the outline at h from `floor` to just under the face, flared by `chamfer` at it."""
    loft(bm, [ring_at(bm, pts_of(h), floor, cx, cz), ring_at(bm, pts_of(h), TOP - chamfer, cx, cz),
              ring_at(bm, pts_of(h + chamfer), TOP, cx, cz), ring_at(bm, pts_of(h + chamfer + 0.003), TOP + 0.003, cx, cz)])


def build_plate():
    base = part("plate", plate_rings)
    unions = []
    for sx in (-1, 1):
        unions.append(part(f"grip{sx}", lambda bm, sx=sx: revolve(bm, grip_profile(), "Z", (sx * GX, 0.0), GRIP_SEG)))
        for sz in (-1, 1):
            unions.append(part(f"neck{sx}{sz}", lambda bm, sx=sx, sz=sz: box(
                bm, *sorted((sx * (HX - NECK_INTO), sx * GX)), -NECK_HALF_Y, NECK_HALF_Y,
                sz * NECK_Z - NECK_HALF_Z, sz * NECK_Z + NECK_HALF_Z)))
    cuts = []
    for i, x in enumerate(B["x"]):
        prof = [(WELL_FLOOR, WELL_R), (TOP - WELL_CHAMFER, WELL_R), (TOP, WELL_R + WELL_CHAMFER),
                (TOP + 0.003, WELL_R + WELL_CHAMFER + 0.003)]
        cuts.append(part(f"well{i}", lambda bm, x=x, prof=prof: revolve(bm, prof, "Y", (x, B["z"]), WELL_SEG)))
    cuts.append(part("seltray", lambda bm: flared_cut(bm, tray_pts, SEL_WELL_H, SEL_FLOOR, WELL_CHAMFER, TRAY_CX, SEL["z"])))
    for s, L in zip(SL, SLY):
        cuts.append(part(f"channel_{s['name']}", lambda bm, L=L: flared_cut(
            bm, lambda h: rect_pts(L["chx"] - L["chz"] + h, h, CH_CORNER), L["chz"], L["floor"], CH_CHAMFER, L["cx"], L["z"])))
        for k, tx in enumerate(L["ticks"]):
            z0, z1 = tick_z(L)
            cuts.append(part(f"tick_{s['name']}{k}", lambda bm, tx=tx, z0=z0, z1=z1: box(
                bm, tx - TICK_W / 2, tx + TICK_W / 2, TOP - TICK_D, TOP + 0.003, z0, z1)))
    return combine(base, unions, cuts)


def plate_swatch(c):
    x, y, z = c
    ax, eps = abs(x), 1e-5
    if ax > GX - GR - 0.0005:
        return "bezel" if math.hypot(ax - GX, y) > GR + 0.0008 else "grip"
    if ax > HX + 1e-4:
        return "bezel"                                   # necks
    if SEL_FLOOR - 1e-4 < y < TOP - eps:                # set into the face: never the underside
        for na, x0, x1, z0, z1 in FOOT:
            if x0 - 1e-4 <= x <= x1 + 1e-4 and z0 - 1e-4 <= z <= z1 + 1e-4:
                if "well" in na or "channel" in na:
                    return "well"
                if "tick" in na:
                    return "tick"
    inset = octagon_inset(x, z)
    if inset < 1e-4:
        return "body"                                    # outer wall
    if y > TOP + eps and inset < BEZEL_W + 1e-4:
        return "bezel"
    return "body"


def build_knob(L):
    kx, kz, y0, y1 = L["lo"], L["z"], L["foot"], L["crown"]
    top = y1 - FIN_H                                     # the fin tops out at the crown, so the retract sinks it flush too
    base = part("knob", lambda bm: loft(bm, [
        rect_ring(bm, L["khx"], L["khz"], KNOB_CORNER, y0, kx, kz),
        rect_ring(bm, L["khx"], L["khz"], KNOB_CORNER, top - KNOB_CHAMFER, kx, kz),
        rect_ring(bm, L["khx"] - KNOB_CHAMFER, L["khz"] - KNOB_CHAMFER, KNOB_CORNER / 2, top, kx, kz)]))
    fin = part("fin", lambda bm: box(bm, kx - FIN_W / 2, kx + FIN_W / 2, top - 0.001, y1,
                                     kz - L["khz"] * FIN_SPAN, kz + L["khz"] * FIN_SPAN, 0.0))
    return combine(base, [fin], []), (lambda c, top=top: "tick" if c[1] > top + 1e-5 else "knob")


def build_cap(x):
    prof = [(CAP_BOTTOM, CAP_R), (B["capTop"] - 0.0045, CAP_R), (B["capTop"] - 0.002, CAP_R - 0.0015),
            (B["capTop"] - 0.0005, CAP_R - 0.0055), (B["capTop"], CAP_R - 0.011)]
    return plain(part("cap", lambda bm: revolve(bm, prof, "Y", (x, B["z"]), CAP_SEG)))


def build_sel_cap(x, side):
    t = B["capTop"]
    return plain(part("selcap", lambda bm: loft(bm, [
        ring_at(bm, seg_pts(CAP_R, side), CAP_BOTTOM, x, SEL["z"]),
        ring_at(bm, seg_pts(CAP_R, side), t - SEL_CHAMFER, x, SEL["z"]),
        ring_at(bm, seg_pts(CAP_R - SEL_CHAMFER, side), t, x, SEL["z"])])))


def build_disc(x, z, d):
    prof = [(LAMP["parked"] - LAMP_THICK, d / 2), (LAMP["parked"], d / 2)]
    return plain(part("lamp", lambda bm: revolve(bm, prof, "Y", (x, z), LAMP_SEG)))


def build_bar(cx, cz, w, depth):
    return plain(part("bar", lambda bm: box(bm, cx - w / 2, cx + w / 2, LAMP["parked"] - LAMP_THICK, LAMP["parked"],
                                            cz - depth / 2, cz + depth / 2)))


# ---- assemble --------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

# (verts, polys, swatch fn, bone or fn(Unity vertex) -> bone, [(shape key, dy in Unity Y)])
PARTS = []
pv, pp = build_plate()
PARTS.append((pv, pp, plate_swatch, NAMES["root"], []))
for x, end in zip(B["x"], NAMES["buttonEnds"]):
    v, p = build_cap(x)
    PARTS.append((v, p, lambda c: "cap", end, [(RET["shape"], -RET["capDepth"])]))
for x, side, end, shape in zip(SEL["x"], SEL_SIDE, NAMES["selectorEnds"], SEL["shapes"]):
    v, p = build_sel_cap(x, side)
    PARTS.append((v, p, lambda c: "cap", end, [(shape, -SEL["sink"]), (RET["shape"], -RET["capDepth"])]))
for s, L in zip(SL, SLY):
    (kv, kp), kfn = build_knob(L)
    PARTS.append((kv, kp, kfn, s["knob"], [(RET["shape"], -L["cd"])]))
for x, shape in zip(B["x"], BL["shapes"]):
    v, p = build_disc(x, BL["z"], BL["diameter"])
    PARTS.append((v, p, lambda c: "amber", NAMES["root"], [(shape, LAMP_DY)]))
for x, shape in zip(SEL["x"], SEL["shapes"]):
    v, p = build_disc(x, SEL["lamps"]["z"], SEL["lamps"]["diameter"])
    PARTS.append((v, p, lambda c: "amber", NAMES["root"], [(shape, LAMP_DY)]))
for s, L in zip(SL, SLY):
    if L["strip"]:
        st = L["strip"]
        far = L["lo"] + STRIP_LEAD
        v, p = plain(part("strip", lambda bm, st=st, L=L, far=far: box(
            bm, L["lo"], far, LAMP["raised"] - LAMP_THICK, LAMP["raised"],
            st["z"] - st["width"] / 2, st["z"] + st["width"] / 2)))
        # Near end on the plate, far end on the knob bone: the strip stretches as the knob translates.
        PARTS.append((v, p, lambda c, sw=st["swatch"]: sw,
                      lambda co, knob=s["knob"], mid=(L["lo"] + far) / 2: knob if co[0] > mid else NAMES["root"], []))
        continue
    for i, shape in enumerate(L["lamps"]["shapes"]):
        v, p = build_bar(L["lo"] + (i + 0.5) * L["pitch"], L["lamps"]["z"], L["pitch"] * L["lamps"]["widthFraction"],
                         L["lamps"]["depth"])
        PARTS.append((v, p, lambda c: "amber", NAMES["root"], [(shape, LAMP_DY)]))

SHAPES = (BL["shapes"] + SEL["shapes"] + [sh for L in SLY if L["lamps"] for sh in L["lamps"]["shapes"]]
          + [RET["shape"]])
assert len(set(SHAPES)) == len(SHAPES), "a shape name repeats"

bm = bmesh.new()
face_swatch, vert_bone, shape_moves = [], [], {s: [] for s in SHAPES}
for verts, polys, fn, bone, keys in PARTS:
    bv = [bm.verts.new(u2b(co)) for co in verts]
    first = len(vert_bone)
    vert_bone += [bone(co) if callable(bone) else bone for co in verts]
    for shape, dy in keys:
        shape_moves[shape] += [(i, dy) for i in range(first, first + len(bv))]
    for poly in polys:
        bm.faces.new([bv[i] for i in poly])
        c = [sum(verts[i][k] for i in poly) / len(poly) for k in range(3)]
        face_swatch.append(fn(c))
assert all(shape_moves[s] for s in SHAPES), [s for s in SHAPES if not shape_moves[s]]
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
assert non_manifold == 0, f"{non_manifold} non-manifold edges: every shell must be closed"
bm.verts.index_update()
parent = list(range(len(bm.verts)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
for e in bm.edges:
    a, b = find(e.verts[0].index), find(e.verts[1].index)
    if a != b:
        parent[a] = b
shells = len({find(i) for i in range(len(bm.verts))})
assert shells == len(PARTS), f"{shells} shells for {len(PARTS)} parts: a part split or two merged"

me = bpy.data.meshes.new(R["mesh"])
bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = False
uv = me.uv_layers.new(name="UVMap")
for p, sw in zip(me.polygons, face_swatch):
    for li in p.loop_indices:
        uv.data[li].uv = swatch_uv(sw)
mat = bpy.data.materials.new(R["material"])
mat.diffuse_color = (0.03, 0.035, 0.045, 1.0)
me.materials.append(mat)
ob = bpy.data.objects.new(R["mesh"], me)
bpy.context.scene.collection.objects.link(ob)

# ---- armature: rig.json's restPoses, Unity frame ------------------------------------------------------------
# A bone built UP with roll ACROSS carries the Panel bone's orientation, so its Unity local rotation is identity
# and its m_LocalPosition a panel-frame offset: Buttons, Sliders and the knobs (the Lamps tree writes the knobs'
# positions). The slider chains point ALONG (+X) with roll UP, so each one's local +Y is the track.
TINY = 0.005
UP, ACROSS, ALONG = (0, 1, 0), (0, 0, 1), (1, 0, 0)
def add(p, d, s):
    return tuple(p[k] + d[k] * s for k in range(3))
root = NAMES["root"]
bones = [(root, None, (0.0, 0.0, 0.0), UP, 0.02, ACROSS),
         (NAMES["buttonsRoot"], root, tuple(REST[NAMES["buttonsRoot"]]), UP, 0.01, ACROSS)]
for bnames, enames in ((NAMES["buttons"], NAMES["buttonEnds"]), (NAMES["selector"], NAMES["selectorEnds"])):
    for b, e in zip(bnames, enames):
        head, tip = REST[f"Buttons/{b}"], REST[f"Buttons/{b}/{e}"]
        bones.append((b, NAMES["buttonsRoot"], tuple(head), UP, tip[1] - head[1], ACROSS))
        bones.append((e, b, tuple(tip), UP, TINY, ACROSS))
bones.append((NAMES["slidersRoot"], root, tuple(REST[NAMES["slidersRoot"]]), UP, 0.01, ACROSS))
for s in SL:
    head, tip = REST[f"Sliders/{s['bone']}"], REST[f"Sliders/{s['bone']}/{s['end']}"]
    bones += [(s["bone"], NAMES["slidersRoot"], tuple(head), ALONG, tip[0] - head[0], UP),
              (s["end"], s["bone"], tuple(tip), ALONG, TINY, UP)]
for s in SL:
    bones.append((s["knob"], root, tuple(REST[s["knob"]]), UP, 0.01, ACROSS))
want = {root} | {k.split("/")[-1] for k in REST}
assert {b[0] for b in bones} == want, f"bone table and restPoses disagree: {sorted({b[0] for b in bones} ^ want)}"

arm_data = bpy.data.armatures.new("Armature")
arm = bpy.data.objects.new("Armature", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, par, head, d, length, roll in bones:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = u2b(head), u2b(add(head, d, length))
    eb.use_connect = False
    if par:
        eb.parent = arm_data.edit_bones[par]
    eb.align_roll(u2b(roll))
bpy.ops.object.mode_set(mode="OBJECT")
for name, par, head, d, length, roll in bones:
    bn = arm_data.bones[name]
    got = tuple(bn.head_local)
    assert max(abs(got[k] - u2b(head)[k]) for k in range(3)) < 1e-6, (name, got)
    assert (bn.parent.name if bn.parent else None) == par, name
    yb, zb = bn.matrix_local.col[1][:3], bn.matrix_local.col[2][:3]
    assert sum(yb[k] * u2b(d)[k] for k in range(3)) > 0.9999, (name, "direction")
    assert sum(zb[k] * u2b(roll)[k] for k in range(3)) > 0.9999, (name, "roll")

ob.parent = arm
ob.modifiers.new("Armature", "ARMATURE").object = arm
for name in [b[0] for b in bones]:
    g = ob.vertex_groups.new(name=name)
    idx = [i for i, bn in enumerate(vert_bone) if bn == name]
    if idx:
        g.add(idx, 1.0, "REPLACE")

ob.shape_key_add(name="Basis", from_mix=False)
for shape in SHAPES:
    kb = ob.shape_key_add(name=shape, from_mix=False)
    for i, dy in shape_moves[shape]:
        kb.data[i].co.z += dy           # Unity +Y is Blender +Z
    kb.value = 0.0

os.makedirs(atlas_dir, exist_ok=True)
write_atlases()

me.calc_loop_triangles()
ub = [(-v.co.x, v.co.z, -v.co.y) for v in me.vertices]
lo = [min(c[k] for c in ub) for k in range(3)]; hi = [max(c[k] for c in ub) for k in range(3)]
print(f"AVATARPREP: build {R['mesh']} verts={len(me.vertices)} faces={len(me.polygons)} tris={len(me.loop_triangles)} "
      f"shells={shells} non_manifold_edges={non_manifold} bones={len(arm_data.bones)} "
      f"shapes={len(me.shape_keys.key_blocks) - 1} unity_bounds x[{lo[0]:.4f},{hi[0]:.4f}] "
      f"y[{lo[1]:.4f},{hi[1]:.4f}] z[{lo[2]:.4f},{hi[2]:.4f}] selector_floor={SEL_FLOOR:.4f} "
      f"sunk_skirt button={CAP_BOTTOM - BTN_DROP:.4f} selector={CAP_BOTTOM - SEL_DROP:.4f} underside={BOTTOM}")

os.makedirs(os.path.dirname(out_blend), exist_ok=True)
if os.path.exists(out_blend):
    os.remove(out_blend)          # no .blend1 left beside it
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
