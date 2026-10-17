"""Build the control panel: one skinned, flat-shaded, low-poly mesh `ControlPanel`, its armature, its atlas.

Every interface number (plate extent, grip axis, button and slider positions, lamp parks, shape and bone names)
is read from `rig.json`, which `../generate.py` emits; the constants below are only the look - bevels, wells,
rail, facet counts - and nothing outside this file reads them.

Frame: authored throughout in the **Unity** panel frame that `rig.json` and the contract state - X along the
long axis (handle A at -X), +Y the face normal, +Z the far edge, metres - and converted once, per vertex and
per bone, by `u2b`. The conversion carries the X negation absolute-grip-prop's `Hands_build.py` documents: an
armature FBX export (`bake_space_transform` off) maps Blender (x, y, z) to Unity (-x, z, -y), so a part authored
at Unity -X must sit at Blender +X. The panel is chiral (the slider and its root are on one side, the offline
lamp on the other), so a dropped negation shows as the slider at the wrong end. Verify after any exporter
change by re-importing the FBX and reading bone heads in the Unity frame, never the Blender ones.

Shells: the plate is one shell - bezel, rail, necks and ridged grips unioned, cap wells, rail notches and the
label recess cut - by Boolean modifiers (Manifold solver), so its parts never show interior walls. Each cap,
the knob and each lamp is its own closed shell, because each moves on its own (a bone or a blendshape). A
lamp is a thin disc or bar parked under the opaque face and raised through it by its key; nothing else hides it.

Colour: a palette atlas of flat swatches, one material slot. Every face's UVs sit on one swatch centre, so a
consumer recolours a part by repainting its square. The emission atlas is black except the two lamp swatches.

Run: blender --background --factory-startup --python ControlPanel_build.py -- <rig.json> <out.blend> [<atlas dir>]
The atlas PNGs land in <atlas dir>, default beside the .blend.
"""
import sys, os, json, math, struct, zlib, bpy, bmesh

argv = sys.argv[sys.argv.index("--") + 1:]
rig_path, out_blend = argv[0], os.path.abspath(argv[1])
atlas_dir = os.path.abspath(argv[2]) if len(argv) > 2 else os.path.dirname(out_blend)
with open(rig_path, encoding="utf-8") as f:
    R = json.load(f)

N = R["N"]
PX0, PX1 = R["plate"]["x"]; PZ0, PZ1 = R["plate"]["z"]
TOP, BOTTOM = R["plate"]["top"], R["plate"]["bottom"]
GX, GR = R["grips"]["x"], R["grips"]["radius"]; GZ0, GZ1 = R["grips"]["z"]
B = R["buttons"]; BL = R["buttonLamps"]; S = R["slider"]; SG = R["segments"]; OFF = R["offline"]
NAMES = R["bones"]

# ---- the look (m); nothing outside this file reads these ----------------------------------------------
CORNER = 0.014            # plate corner chamfer, leg length
BEZEL_H = 0.004           # bezel rise above the face
BEZEL_W = 0.004           # bezel width, outer edge to where it meets the face
TOP_CHAMFER = 0.0015      # bezel's outer top edge
BOTTOM_CHAMFER = 0.004
WELL_CLEAR = 0.003        # well radius beyond the cap
WELL_FLOOR = 0.004        # well floor height; below the cap's lowest squash
WELL_CHAMFER = 0.0015
CAP_SEG, WELL_SEG, LAMP_SEG, GRIP_SEG = 16, 16, 12, 8
RAIL_W, RAIL_H = 0.006, 0.0045           # across Z; rise above the face
RAIL_RUN = 0.008                          # rail past each slot end, kept inside the knob's half-width
NOTCH_W, NOTCH_D = 0.002, 0.003
KNOB_H, KNOB_LIFT, KNOB_CHAMFER = 0.014, 0.0005, 0.003
FIN_W, FIN_H, FIN_SPAN = 0.003, 0.0025, 0.8   # the pointer fin across the knob top; span as a fraction of its Z
LABEL_HALF_Z, LABEL_HALF_X, LABEL_DEPTH = 0.005, 0.13, 0.0008
LAMP_THICK = 0.002
GRIP_END_CHAMFER = 0.004
RIDGES, RIDGE_W, RIDGE_GAP, RIDGE_R = 5, 0.007, 0.011, 0.0025   # count, width, gap, extra radius
NECK_HALF_Y, NECK_HALF_Z, NECK_Z, NECK_INTO = 0.007, 0.006, 0.058, 0.006

# ---- atlas -----------------------------------------------------------------------------------------------
ATLAS, GRID = 128, 4
SWATCHES = {   # name: (index, albedo sRGB, emission sRGB)
    "body":  (0, (44, 50, 58), None),
    "bezel": (1, (92, 98, 106), None),
    "cap":   (2, (226, 222, 210), None),
    "knob":  (3, (64, 124, 128), None),
    "amber": (4, (255, 170, 40), (255, 160, 30)),
    "red":   (5, (235, 45, 35), (255, 40, 25)),
    "label": (6, (140, 143, 148), None),
    "tick":  (7, (210, 208, 196), None),
    "well":  (8, (24, 27, 31), None),
    "grip":  (9, (30, 32, 36), None),
    "rail":  (10, (110, 116, 124), None),
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


def rect_ring(bm, hx, hz, c, y, cx=0.0, cz=0.0):
    if c > 1e-6:
        pts = ((hx, hz - c), (hx - c, hz), (-hx + c, hz), (-hx, hz - c),
               (-hx, -hz + c), (-hx + c, -hz), (hx - c, -hz), (hx, -hz + c))
    else:
        pts = ((hx, hz), (-hx, hz), (-hx, -hz), (hx, -hz))
    return [bm.verts.new((cx + px, y, cz + pz)) for px, pz in pts]


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


# ---- the parts -------------------------------------------------------------------------------------------
HX, HZ = (PX1 - PX0) / 2, (PZ1 - PZ0) / 2
assert abs(PX0 + PX1) < 1e-9 and abs(PZ0 + PZ1) < 1e-9, "plate must be centred on the Panel bone"
CAP_R = B["capDiameter"] / 2
WELL_R = CAP_R + WELL_CLEAR
CAP_BOTTOM = TOP - B["travel"]          # a cap stands `travel` proud of the face, bottoming out flush
SX0, SX1 = S["x"]; SZ = S["z"]
PITCH = (SX1 - SX0) / N
BOUNDS_X = [SX0 + k * PITCH for k in range(1, N)]
RAIL_HX = (SX1 - SX0) / 2 + RAIL_RUN
KHX, KHZ = S["knob"][0] / 2, S["knob"][1] / 2
assert RAIL_RUN < KHX, "the rail's ends must hide inside the knob at either end of the slot"
LAMP_DY = BL["raised"] - BL["parked"]


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


def build_plate():
    base = part("plate", plate_rings)
    unions = [part("rail", lambda bm: box(bm, -RAIL_HX, RAIL_HX, TOP - 0.002, TOP + RAIL_H,
                                          SZ - RAIL_W / 2, SZ + RAIL_W / 2, 0.0015))]
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
    for k, bx in enumerate(BOUNDS_X):
        cuts.append(part(f"notch{k}", lambda bm, bx=bx: box(
            bm, bx - NOTCH_W / 2, bx + NOTCH_W / 2, TOP + RAIL_H - NOTCH_D, TOP + RAIL_H + 0.003,
            SZ - RAIL_W, SZ + RAIL_W)))
    lz = R["labelStrip"]["z"]
    cuts.append(part("label", lambda bm: box(bm, -LABEL_HALF_X, LABEL_HALF_X, TOP - LABEL_DEPTH, TOP + 0.003,
                                             lz - LABEL_HALF_Z, lz + LABEL_HALF_Z)))
    return combine(base, unions, cuts)


def octagon_inset(x, z):
    """Distance inside the plate's outer outline (negative outside)."""
    ax, az = abs(x), abs(z)
    return min(HX - ax, HZ - az, (HX + HZ - CORNER - ax - az) / math.sqrt(2))


def plate_swatch(c):
    x, y, z = c
    ax, eps = abs(x), 1e-5
    if ax > GX - GR - 0.0005:
        return "bezel" if math.hypot(ax - GX, y) > GR + 0.0008 else "grip"
    if ax > HX + 1e-4:
        return "bezel"                                   # necks
    if y < TOP - eps:
        for bx in B["x"]:
            if math.hypot(x - bx, z - B["z"]) < WELL_R + WELL_CHAMFER + 0.0006:
                return "well"
        if ax <= LABEL_HALF_X + 1e-4 and abs(z - R["labelStrip"]["z"]) <= LABEL_HALF_Z + 1e-4:
            return "label"
    if y > TOP + eps and abs(z - SZ) <= RAIL_W / 2 + 1e-4 and ax <= RAIL_HX + 1e-4:
        if y < TOP + RAIL_H - eps and any(abs(x - bx) <= NOTCH_W / 2 + 1e-4 for bx in BOUNDS_X):
            return "tick"
        return "rail"
    inset = octagon_inset(x, z)
    if inset < 1e-4:
        return "body"                                    # outer wall
    if y > TOP + eps and inset < BEZEL_W + 1e-4:
        return "bezel"
    return "body"


def build_knob():
    kx, ky = SX0, TOP
    y0, y1 = ky + KNOB_LIFT, ky + KNOB_H
    base = part("knob", lambda bm: loft(bm, [
        rect_ring(bm, KHX, KHZ, 0.002, y0, kx, SZ), rect_ring(bm, KHX, KHZ, 0.002, y1 - KNOB_CHAMFER, kx, SZ),
        rect_ring(bm, KHX - KNOB_CHAMFER, KHZ - KNOB_CHAMFER, 0.001, y1, kx, SZ)]))
    fin = part("fin", lambda bm: box(bm, kx - FIN_W / 2, kx + FIN_W / 2, y1 - 0.001, y1 + FIN_H,
                                     SZ - KHZ * FIN_SPAN, SZ + KHZ * FIN_SPAN, 0.0))
    return combine(base, [fin], []), (lambda c: "tick" if c[1] > y1 + 1e-5 else "knob")


def build_cap(x):
    prof = [(CAP_BOTTOM, CAP_R), (B["capTop"] - 0.0045, CAP_R), (B["capTop"] - 0.002, CAP_R - 0.0015),
            (B["capTop"] - 0.0005, CAP_R - 0.0055), (B["capTop"], CAP_R - 0.011)]
    return plain(part("cap", lambda bm: revolve(bm, prof, "Y", (x, B["z"]), CAP_SEG)))


def build_disc(x, z, d):
    prof = [(BL["parked"] - LAMP_THICK, d / 2), (BL["parked"], d / 2)]
    return plain(part("lamp", lambda bm: revolve(bm, prof, "Y", (x, z), LAMP_SEG)))


def build_bar(cx):
    w = PITCH * SG["widthFraction"]
    return plain(part("seg", lambda bm: box(bm, cx - w / 2, cx + w / 2, BL["parked"] - LAMP_THICK, BL["parked"],
                                            SG["z"] - SG["depth"] / 2, SG["z"] + SG["depth"] / 2)))


# ---- assemble --------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

# (verts, polys, swatch fn, bone, shape key)
PARTS = []
pv, pp = build_plate()
PARTS.append((pv, pp, plate_swatch, NAMES["root"], None))
(kv, kp), kfn = build_knob()
PARTS.append((kv, kp, kfn, NAMES["knob"], None))
for i, x in enumerate(B["x"]):
    v, p = build_cap(x)
    PARTS.append((v, p, lambda c: "cap", NAMES["buttonEnds"][i], None))
for i, x in enumerate(B["x"]):
    v, p = build_disc(x, BL["z"], BL["diameter"])
    PARTS.append((v, p, lambda c: "amber", NAMES["root"], BL["shapes"][i]))
assert len(SG["shapes"]) == N, "segments.shapes must name N keys"
for i in range(N):
    v, p = build_bar(SX0 + (i + 0.5) * PITCH)
    PARTS.append((v, p, lambda c: "amber", NAMES["root"], SG["shapes"][i]))
v, p = build_disc(OFF["x"], OFF["z"], OFF["diameter"])
PARTS.append((v, p, lambda c: "red", NAMES["root"], OFF["shape"]))

bm = bmesh.new()
face_swatch, vert_bone, shape_verts = [], [], {}
for verts, polys, fn, bone, shape in PARTS:
    bv = [bm.verts.new(u2b(co)) for co in verts]
    vert_bone += [bone] * len(bv)
    if shape:
        shape_verts[shape] = list(range(len(vert_bone) - len(bv), len(vert_bone)))
    for poly in polys:
        bm.faces.new([bv[i] for i in poly])
        c = [sum(verts[i][k] for i in poly) / len(poly) for k in range(3)]
        face_swatch.append(fn(c))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
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

# ---- armature: the contract's bone table, Unity frame --------------------------------------------------
TINY = 0.005
UP, ACROSS, ALONG = (0, 1, 0), (0, 0, 1), (1, 0, 0)
def add(p, d, s):
    return tuple(p[k] + d[k] * s for k in range(3))
bones = [(NAMES["root"], None, (0.0, 0.0, 0.0), UP, 0.02, ACROSS),
         (NAMES["buttonsRoot"], NAMES["root"], (0.0, TOP, B["z"]), UP, 0.01, ACROSS)]
for i, x in enumerate(B["x"]):
    head = (x, B["capTop"] - B["boneLength"], B["z"])
    bones.append((NAMES["buttons"][i], NAMES["buttonsRoot"], head, UP, B["boneLength"], ACROSS))
    bones.append((NAMES["buttonEnds"][i], NAMES["buttons"][i], add(head, UP, B["boneLength"]), UP, TINY, ACROSS))
slider_head = (S["rootX"], TOP, SZ)
slider_tip = add(slider_head, ALONG, S["boneLength"])
assert abs(slider_tip[0] - SX0) < 1e-9, "slider rootX + boneLength must land on the slot's start"
bones += [(NAMES["slider"], NAMES["root"], slider_head, ALONG, S["boneLength"], UP),
          (NAMES["sliderEnd"], NAMES["slider"], slider_tip, ALONG, TINY, UP),
          (NAMES["knob"], NAMES["root"], (SX0, TOP, SZ), ALONG, 0.01, UP)]

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
for name in {b[0] for b in bones}:
    g = ob.vertex_groups.new(name=name)
    idx = [i for i, bn in enumerate(vert_bone) if bn == name]
    if idx:
        g.add(idx, 1.0, "REPLACE")

ob.shape_key_add(name="Basis", from_mix=False)
for shape in BL["shapes"] + SG["shapes"] + [OFF["shape"]]:
    kb = ob.shape_key_add(name=shape, from_mix=False)
    for i in shape_verts[shape]:
        kb.data[i].co.z += LAMP_DY        # Unity +Y is Blender +Z
    kb.value = 0.0

os.makedirs(atlas_dir, exist_ok=True)
write_atlases()

me.calc_loop_triangles()
ub = [(-v.co.x, v.co.z, -v.co.y) for v in me.vertices]
lo = [min(c[k] for c in ub) for k in range(3)]; hi = [max(c[k] for c in ub) for k in range(3)]
print(f"AVATARPREP: build {R['mesh']} verts={len(me.vertices)} faces={len(me.polygons)} tris={len(me.loop_triangles)} "
      f"shells={shells} non_manifold_edges={non_manifold} bones={len(arm_data.bones)} "
      f"shapes={len(me.shape_keys.key_blocks) - 1} unity_bounds x[{lo[0]:.4f},{hi[0]:.4f}] "
      f"y[{lo[1]:.4f},{hi[1]:.4f}] z[{lo[2]:.4f},{hi[2]:.4f}] N={N}")

os.makedirs(os.path.dirname(out_blend), exist_ok=True)
if os.path.exists(out_blend):
    os.remove(out_blend)          # no .blend1 left beside it
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
