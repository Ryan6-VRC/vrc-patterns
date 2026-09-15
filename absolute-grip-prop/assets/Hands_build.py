"""Build the grip jig's hand stand-ins: `HandR` and `HandL`, one closed low-poly mesh each.

These are the jig's authoring instrument, never shipped geometry: four of them ride `EditorOnly/Jig/PropFrame`
and you drag one until the prop sits in it as you mean it to. So the only thing they owe you is that a glance
tells you which hand, which way the palm faces, and where the fingers close.

Pose: **fingerpoint**, not a fist. A VRChat physbone grab is the grip press, which puts the hand in the
fingerpoint or handgun gesture for as long as it is held - index extended, middle/ring/pinky curled onto the
grip, thumb alongside. A stand-in shaped as a fist would lie about where the prop can sit. Handgun differs
only in the thumb's lift, which moves nothing the prop occupies, so one pose serves both.

**Box-modelled, the way a low-poly hand is actually made**, and that is the load-bearing decision. The palm
is one lofted cage whose cross-section is subdivided across Z into the four finger lanes, so its knuckle-end
ring already contains four faces - one per finger, two verts wide. A finger is not attached to the palm: its
first ring *is* those palm verts, and each phalanx is another ring bridged onto the last. The thumb is the
same move on one face of the palm's +Z side. Nothing is unioned, nothing interpenetrates, and because the
stand-ins are drawn translucent that matters more than it would opaque - an assembly of shells shows every
interior wall through the surface, which no amount of shaping fixes. Two earlier builds learned this the
expensive way: swept shells per part, then a metaball field. Watch `shells=1` in the printed line.

Frame: authored throughout in **Unity's** hand-frame coordinates, the frame the prefab's hold transforms and
every other number in this entry are written in - origin at the client's grab point, +Y from the palm capsule
midpoint toward that point (the midpoint is PALM_Y down -Y), +Z along the palm axis toward the thumb, fingers
of a right hand along -X. The whole mesh is built in that frame and converted once, at the end, by `to_blender`.

Chirality: `HandL` is built by the same code with `mirror`, negating X before the frame conversion. Never the
same mesh under a negative scale - that renders inside-out, and Standard has no cull toggle to rescue it.
+Z stays the thumb side for both, which is the prefab's own convention. Winding is not tracked through either
the mirror or the conversion (both reverse it); `recalc_face_normals` settles it at the end, which it can
because the result is closed and manifold.

The `.blend` is an intermediate and must land **outside** this folder: Unity imports a `.blend` wherever it
finds one, so a copy left here becomes a second `HandR`/`HandL` competing with the FBX's.

Run: blender --background --factory-startup --python Hands_build.py -- <scratch>/Hands.blend
"""
import sys, math, bpy, bmesh

out_blend = sys.argv[sys.argv.index("--") + 1]

PALM_Y = -0.046            # grab point to palm capsule midpoint, -Y; the client's number, not ours to pick
PALM_HALF_T = 0.0150       # half the palm's thickness

# Palm cage rings, wrist -> knuckles: (x, width scale, thickness scale). The last must stay width 1.0, since
# its ring supplies the finger lanes' own vertices.
PALM_RINGS = ((0.048, 0.82, 0.92), (0.020, 0.95, 1.00), (-0.016, 1.00, 0.98), (-0.045, 1.00, 0.90))

# Finger lane widths, thumb side first; the palm is exactly as wide as the four together, as a hand is.
LANE_W = (0.021, 0.021, 0.019, 0.017)

CURL = (-70.0, -90.0, -45.0)        # MCP, PIP, DIP flexion, degrees about +Z; sweeps -X -> +Y -> +X
POINT = (-6.0, -3.0, -2.0)          # the extended index: not dead straight, a shade of droop
SEGS = (                            # phalanx lengths per finger, proximal -> distal
    (0.038, 0.023, 0.018),
    (0.045, 0.028, 0.022),
    (0.042, 0.026, 0.020),
    (0.034, 0.021, 0.017),
)
# Per finger ring, as fractions of the lane's own half-width and the palm's half-thickness. The knuckle ring
# is the palm's, so a finger narrows out of the hand rather than starting at finger width.
FINGER_PROFILE = ((0.90, 0.66), (0.82, 0.60), (0.66, 0.48))

THUMB_RING = 0                      # palm ring whose +Z side face becomes the thumb's root
# (direction, length) per phalanx. Kept close in +Z: fingerpoint tucks the thumb alongside the index, and
# splaying it reads as a separate spike rather than part of the hand.
THUMB = (((-0.70, 0.42, 0.48), 0.034), ((-0.94, 0.14, 0.24), 0.028))
THUMB_PROFILE = ((0.78, 0.70), (0.60, 0.55))


def norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return (v[0] / m, v[1] / m, v[2] / m)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def lane_bounds():
    """The 9 cross-section Z values: a boundary per lane edge, a midpoint per lane, thumb side first."""
    edges = [sum(LANE_W) / 2]
    for w in LANE_W:
        edges.append(edges[-1] - w)
    zs = []
    for i in range(len(LANE_W)):
        zs += [edges[i], (edges[i] + edges[i + 1]) / 2]
    zs.append(edges[-1])
    return zs, edges


ZS, EDGES = lane_bounds()
NLOOP = 2 * len(ZS)                 # 9 across the top, 9 back along the bottom


def palm_ring(bm, x, ws, ts):
    """One cross-section loop: across the top thumb-side to pinky-side, then back along the bottom."""
    hi, lo = PALM_Y + PALM_HALF_T * ts, PALM_Y - PALM_HALF_T * ts
    top = [bm.verts.new((x, hi, z * ws)) for z in ZS]
    bot = [bm.verts.new((x, lo, z * ws)) for z in reversed(ZS)]
    return top + bot


def finger_face(ring, i):
    """The four palm verts... six, rather: a lane spans two top verts, its midpoint, and their two mirrors."""
    return [ring[2 * i], ring[2 * i + 1], ring[2 * i + 2],
            ring[NLOOP - 3 - 2 * i], ring[NLOOP - 2 - 2 * i], ring[NLOOP - 1 - 2 * i]]


def curl_dirs(angles):
    """Successive flexions about +Z from an initial -X, the direction a finger closes over the palm."""
    dirs, a, out = [], 0.0, []
    for step in angles:
        a += math.radians(step)
        out.append(((-math.cos(a), -math.sin(a), 0.0), a))
    return out


def bridge(bm, a, b):
    """Quads between two equal-length rings; both wrap."""
    n = len(a)
    for j in range(n):
        k = (j + 1) % n
        bm.faces.new((a[j], a[k], b[k], b[j]))


def build_finger(bm, base, lane_i):
    """Extrude a lane's palm face out through its phalanges. The base ring is the palm's own vertices."""
    half_w = LANE_W[lane_i] / 2
    half_t = PALM_HALF_T * PALM_RINGS[-1][2]
    angles = POINT if lane_i == 0 else CURL
    centre = (PALM_RINGS[-1][0], PALM_Y, (EDGES[lane_i] + EDGES[lane_i + 1]) / 2)
    prev = base
    for k, ((d, a), L) in enumerate(zip(curl_dirs(angles), SEGS[lane_i])):
        centre = tuple(centre[m] + d[m] * L for m in range(3))
        ws, ts = FINGER_PROFILE[k]
        w, h = half_w * ws, half_t * ts
        # A hexagon, ordered to match finger_face: the lane midpoints become the ridge down the finger.
        ring = []
        for dz, dy in ((1, 0.5), (0, 1), (-1, 0.5), (-1, -0.5), (0, -1), (1, -0.5)):
            oy = dy * h
            ring.append(bm.verts.new((centre[0] - oy * math.sin(a),
                                      centre[1] + oy * math.cos(a),
                                      centre[2] + dz * w)))
        bridge(bm, prev, ring)
        prev = ring
    bm.faces.new(prev)


def frame_for(d):
    """A stable (side, up) pair for a direction, side leaning +X and up leaning +Y so ring order is kept."""
    d = norm(d)
    side = cross(d, (0.0, 1.0, 0.0))
    side = norm(side) if math.sqrt(sum(c * c for c in side)) > 1e-6 else (1.0, 0.0, 0.0)
    if side[0] < 0:
        side = tuple(-c for c in side)
    up = norm(cross(side, d))
    if up[1] < 0:
        up = tuple(-c for c in up)
    return side, up


def build_thumb(bm, rings):
    """Same move as a finger, on a face of the palm's +Z side, so the thenar is palm geometry."""
    r0, r1 = rings[THUMB_RING], rings[THUMB_RING + 1]
    base = [r0[0], r0[NLOOP - 1], r1[NLOOP - 1], r1[0]]     # (+x,+y) (+x,-y) (-x,-y) (-x,+y)
    centre = [sum(v.co[m] for v in base) / 4 for m in range(3)]
    half_x = abs(r0[0].co[0] - r1[0].co[0]) / 2
    half_y = PALM_HALF_T * PALM_RINGS[THUMB_RING][2]
    prev = base
    for (d, L), (ws, ts) in zip(THUMB, THUMB_PROFILE):
        side, up = frame_for(d)
        d = norm(d)
        centre = [centre[m] + d[m] * L for m in range(3)]
        w, h = half_x * ws, half_y * ts
        ring = []
        for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
            ring.append(bm.verts.new(tuple(
                centre[m] + sx * w * side[m] + sy * h * up[m] for m in range(3))))
        bridge(bm, prev, ring)
        prev = ring
    bm.faces.new(prev)


def to_blender(bm):
    """Unity hand-frame -> Blender, undoing what the export round-trip does.

    The **x negation** is the part that is easy to lose: `bake_space_transform` lands Y and Z as the mapping
    in `Hands_export.py` says, but reflects X, so a hand authored with its fingers along -X arrives in Unity
    with them along +X - the opposite hand. Nothing in the sibling `GripHammer_Particles` meshes could show
    this, both being mirror-symmetric about that axis; a chiral mesh is the first to. Verify it after any
    exporter change by reading the imported mesh's bounds, never the Blender ones.
    """
    for v in bm.verts:
        x, y, z = v.co
        v.co = (-x, -z, y)


def build(name, mirror):
    bm = bmesh.new()
    rings = [palm_ring(bm, x, ws, ts) for x, ws, ts in PALM_RINGS]
    for r in range(len(rings) - 1):
        for j in range(NLOOP):
            k = (j + 1) % NLOOP
            if r == THUMB_RING and j == NLOOP - 1:
                continue                     # the thumb's root; leaving it open welds the thumb to the palm
            bm.faces.new((rings[r][j], rings[r][k], rings[r + 1][k], rings[r + 1][j]))
    bm.faces.new(rings[0])                   # wrist cap; the knuckle end is spoken for by the four lanes
    for i in range(len(LANE_W)):
        build_finger(bm, finger_face(rings[-1], i), i)
    build_thumb(bm, rings)

    if mirror:
        for v in bm.verts:
            v.co.x = -v.co.x
    to_blender(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new(name)
    non_manifold = [e for e in bm.edges if not e.is_manifold]
    seen, sizes = set(), []          # keyed by BMVert, never .index: a new bmesh vert is -1 until index_update
    for v0 in bm.verts:
        if v0 in seen:
            continue
        stack, n = [v0], 0
        seen.add(v0)
        while stack:
            v = stack.pop(); n += 1
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in seen:
                    seen.add(o); stack.append(o)
        sizes.append(n)
    bm.verts.index_update()
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(bpy.data.materials.new(name))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.calc_loop_triangles()
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    print(f"AVATARPREP: {name} verts={len(me.vertices)} faces={len(me.polygons)} tris={len(me.loop_triangles)} "
          f"non_manifold_edges={len(non_manifold)} shells={len(sizes)} "
          f"bounds x[{min(xs):.4f},{max(xs):.4f}] y[{min(ys):.4f},{max(ys):.4f}] z[{min(zs):.4f},{max(zs):.4f}]")


bpy.ops.wm.read_factory_settings(use_empty=True)
build("HandR", mirror=False)
build("HandL", mirror=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
