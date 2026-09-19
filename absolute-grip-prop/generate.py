#!/usr/bin/env python3
"""absolute-grip-prop generator: emits the two controller documents beside this file.

    python absolute-grip-prop/generate.py           # writes readout.yaml and controller.yaml
    python absolute-grip-prop/generate.py --check   # asserts the prefab's silent surface, writes nothing

readout.yaml (GripReadout_Fx) is the palm readout plus three differentials: eight face-box readings of the grabber's built-in Hand palm-capsule sender -> capsule
half-length s, the capsule midpoint, a held ORIENTED sign pattern whose tree writes the signed palm axis to BOTH
axis proxies (ProxyA = +axis, ProxyB = -axis); plus |Mid|^2 as the lever proxy, HandDiff = HandL - HandR (the
handedness gate) and Cue = CueP - CueN (the axis sign, read off the FingerIndex sender at the two proxies).
Mechanism and the measurements behind every constant: README.md. controller.yaml (AbsoluteGripProp_Fx) is the
glue: grab-prop's cell (its clip table replicated binding for binding) plus the cage latch, a confirm dwell that
decides hand and sign once, four carry states that ride an AUTHORED grip pose, each with a recheck that re-reads the cue
and flips the sign after a dwell of steady contradiction, and a receiver stow on every latch loss before carry (a contact
that breaks behind shut filters and returns is only re-acquired by a stow). No capture.

Bidirectional grip (opt-in, AbsoluteGrip/Bidir): with the mode parameter on, the grab picks between the two holds the author
placed for that hand -- Frame/GripR and Frame/GripRF, Frame/GripL and Frame/GripLF -- by which one the prop's feature was
nearer to at the moment the readout settled. No generator constant names a grip: the four nodes live in the prefab, the clips
only ever select one. Only the wearer's copy decides; the decision crosses the wire as two bits (Palm/Decided, Palm/Down) and
every remote holds the prop's pre-grab attitude on the hand until they land, so a remote never shows the authored pose first
and then turns. Sensing is one sender and four Proximity receivers: MarkProxy copies the prop's attitude to the tip and Mark
stands MARK_H along the fixed feature direction in that frame, while each hold receiver rides its grip node's rotation on a
host at Frame's origin and sits MARK_H along that host's own feature direction, so Palm/Near{h} = Hold{h}F - Hold{h} is
metres of nearer-ness over HOLD_R. The read is taken in ReadP / ReadN, a per-sign state presenting the frame the carry will
present; the presented pose is a 1D blend on Palm/Flip between the carry clip and its F twin.

Arithmetic conventions (the schema's clamp rule: a Direct weight is clamped >= 0, so every sign lives in a clip
constant; signed values are only ever read through a 1D tree's blend parameter or a transition condition):
  R_j+/-  face readings of the opposed pair along tetrahedral direction d_j (reading = 1 - d_surface / D)
  E_j   = D(R_j+ + R_j-) - 2(D - F)              extent along d_j, metres
  m_j   = (R_j+ - R_j-) D / 2                     midpoint projection on d_j;  Mid = 3/4 sum_j m_j d_j
  s     = (SumE - sqrt(SumE^2 - qa*SumE2)) / qa   qa = 16k^2 - 4/3 = 8/3 at k = r/s = 0.5; sqrt by a 1D lookup
  S_L   = sum_j sigma_j (E_j - s)                  consistency residual of line L (the directions sum to 0)
  axis  = sum_j sigma_j (E_j - s) d_j              the held oriented pattern's vector, |axis| = 4/3 s
  MM    = |Mid|^2                                  the lever proxy: with the tip's along-axis offset ~0, |Mid| IS the lever
  HandDiff = HandL - HandR ; Cue = CueP - CueN     signed differentials, read only as transition conditions

Hop structure (one frame per AAP hop, runtime.md SAnimator evaluation):
  frame n  : E_j, SumE, Mid, G_k, S_L, O_P, HandDiff, Cue and the active state's P_k / T / axis from readings(n), S(n-1)
  frame n+1: Disc; D_ab = |S_a| - |S_b|; SumE_d1; the positive/negative halves of Mid
  frame n+2: SqrtDisc = lut(Disc); SumE_d2; MM from the halves
  frame n+3: S = 3/8 (SumE_d2 - SqrtDisc)
  frame n+4: CueScale = the 1D tree on S (the cue spheres' scale, 1 across the surveyed size band)
The cue trails the axis by two more stages (AAP write -> constraint solve moves the proxies -> the contacts sample
-> the animator reads), and the cue RADIUS trails S by the tree plus those same stages, so a grown sphere that swallows
a finger it previously missed pays a fresh two-step acquisition on top. That whole pipeline is what SETTLE_FILL primes
and the Confirm dwell is sized against.
"""
import itertools, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_READOUT = os.path.join(HERE, 'readout.yaml')

# ---------------- config ----------------
# Box geometry at WORKING scale (host localScale 1). F = +Z face plane from the box centre, D = depth; the box is
# (2F, 2F, D) full extents. Large so a remote client's IK-lagged hand sender, which trails the synced grab point
# during motion, stays inside every box's linear range. Any change regenerates everything.
F, D = 0.75, 1.5
K = 0.5                               # r/s on every VRChat Automatic base
QA = 16 * K * K - 4 / 3               # 8/3
MARGIN = 0.0004                       # keep-previous hysteresis in |S_L| metres
LUT_LO, LUT_HI, LUT_N = 0.0003, 0.16, 48  # sqrt lookup over Disc (m^2); must cover Disc over the whole S band (refused below). 48 knots over this wider ratio give a knot ratio of 1.143, slightly tighter than the 24-knot lookup it replaces, so widening the band does not grow the piecewise-linear sqrt error
RES_SETTLE = 0.002                    # |S_held| below this = the eight boxes agree on one capsule
# ---- the supported grabber size, and everything derived from it ----
# The cage rides the world-scale pin, so every radius and band in this file is true metres and the WEARER's scale never
# enters. What varies is the grabber's built-in palm and index capsules, which scale with the grabber's avatar. The range
# is declared here as palm height H in metres -- about a third of the smallest surveyed hand to three times the largest --
# and the S band, the sqrt lookup, the gate radius and the lever floor all derive from these four numbers below, so the
# claim "this entry supports H_MIN..H_MAX" is checkable rather than asserted.
H_MIN, H_MAX = 0.012, 0.20
S_SURVEY_LO, S_SURVEY_HI = 0.0185, 0.032   # the surveyed bases' readout half-length s = H/2, over palm heights 37..64 mm: the band CUE_R was argmaxed over and the cue rule keys on
H_SURVEY_MIN, H_SURVEY_MAX = 2 * S_SURVEY_LO, 2 * S_SURVEY_HI
S_LO, S_HI = H_MIN / 2, H_MAX / 2     # palm-plausible half-length band: the supported range in the readout's own units
FRAME = 0.016666668
FPS_FLOOR = 45                        # the lowest frame rate the frame-count dwells below are sized for (a clip length is wall-clock, so a slower client fills fewer frames): under it Arrive can miss the snap and the fill under-primes, which costs a bounce rather than a wrong latch for as long as CONFIRM_DWELL still outlasts the readout pipeline there
SETTLE_FILL = 6 / FPS_FLOOR           # 6 frames at the floor frozen after the latch: Res/S land ~4 frames after working scale, the cue ~9-10 now that the cue radius trails S (three hops, then the CueScale tree, then the contact solve) and a sphere that grew onto a finger it previously missed pays a fresh two-step acquisition. Still 6: the fill primes, and Confirm's dwell -- which outlasts the whole pipeline at the frame-rate floor -- is what guards the decision
SETTLE_TIMEOUT = 0.5                  # seconds after the latch before the loop reopens (Settling + Settled): also the stall after a Confirm bounce whose rung stays failed
CONFIRM_DWELL = 0.2                   # seconds every engage condition must hold before a carry state latches hand and sign (>= 5 frames down to 25 fps)
RECHECK_DWELL = 0.5                   # seconds the cue must read against the latched sign, never retreating past the bounce threshold, before a carry flips its sign. The readout's line has no orientation across a sample step near 90 degrees (a 30 fps observer watching the recorded fast swing sees 60 to 110 degrees between samples), so the ladder can land on the antipode there and the finger then reads at the other proxy for the rest of the grab; this is the recovery, and the dwell is what makes it not a flicker. Sized above the cue's longest contradiction while the grip was right: 0.13 s in the probe recording (11 bursts at 84 fps, the other-hand fast swing) and 0.23 s in the emulator harness at the 30 fps remote period, and above the transient reversals the ladder undoes by itself on every stretch the harness could score
DISABLED_DWELL = 0.25                 # seconds the receiver GOs stay off in Disabled and Reacquire (a one-frame bounce deafens them; a slow stow re-acquires a sender already inside)
# The gate radius is derived from the largest lever the supported range can present, not tuned against one base. With
# snapToHand the tip IS the client's grab point, so what the gate must reach is the palm capsule's SURFACE: a lever out
# from the palm axis, less the capsule radius, and the latch needs a reading above GATE_M there.
LEVER_SURVEY_MAX = 0.044              # m, the largest constructed lever over the surveyed hands (test-output/p8e/hand-geometry/palm.csv), on an H_SURVEY_MAX base
LEVER_VR_RATIO = 1.39                 # the one in-VR grab-point measurement (46 mm) against the constructed lever on that base (33 mm; runtime.md SPhysBones): in VR the client puts the grab point further out than the construction does
R_PALM_MAX = H_MAX / 4                # the palm capsule's radius at the top of the range (the SDK's automatic proportion, r = s/2 = H/4)
# LEVER_SURVEY_MAX * H_MAX / H_SURVEY_MAX * LEVER_VR_RATIO - R_PALM_MAX = 0.141 m of surface distance at the top of the
# range on that most extreme proportion, which wants GATE_R 0.157 at GATE_M. 0.15 is what ships: it covers that proportion
# to a palm height of 0.191 m, and the last 5 % of the declared range rides inside LEVER_VR_RATIO's own uncertainty (one
# measurement, one base). Above it the gate is the rung that refuses, which is legible (README SLimits).
# What 0.15 costs, in the terms a reviewer weighs it in: the acquisition cube grows from 0.12 to 0.30 m across, about 16x
# in volume; two palms are told apart only past GATE_M * GATE_R = 15 mm of nearer-ness, up from 6 mm, so more near-ties
# refuse -- a tie takes no latch and never mislatches; the wearer's own free hand cancels the differential (allowSelf is
# on for the gate, and must stay on: the wearer grabs their own prop) at 2.5x the old distance from the grabbed prop; and
# a remote's IK-lagged palm is admitted more easily, which the Confirm dwell and not the gate is sized to catch.
GATE_R = 0.15                         # HandL / HandR proximity sphere radius on the tip, metres: THE acquisition zone (a palm must read on one to latch) and the hand differential's scale
ACQ_SCALE = GATE_R / F                # box host scale between grabs: the eight boxes collapse to ONE coincident cage-aligned cube whose half-width equals the gate radius, so the sphere is the binding term in every direction (README)
ARRIVE_DWELL = 2 / FPS_FLOOR          # 2 frames at the floor a fresh grab waits in Arrive before Acquire polls: the bone snaps to the hand grab point in about a frame in-game, and a latch taken before it lands takes whatever palm was nearest the old position
SMOOTH_W = 0.5                        # Damped's target weight against its self weight of 1, both smoothers: it moves w/(1+w) of the way per frame; raising it shows more of the readout's pattern hops
BOUNCE_H = 0.7                        # bounce hysteresis: a Confirm bounce rung fires only once a reading has retreated to this fraction of its entry margin, or past 1/this of its entry ceiling, so a reading dithering on its entry threshold cannot flap Settled and Confirm (runtime.md: a bare threshold on a contact reading needs hysteresis)
GATE_M = 0.1                          # |HandDiff| the latch needs to decide the hand; two palms or none read under it and no latch is taken
CUE_R = 0.06                          # FingerIndex proximity sphere radius at each axis proxy, metres, at survey scale (the argmax of worst-case differential over the measured hands). Outside the survey the hosts are scaled by the readout's CueScale tree (Math layer), so the radius in play is CUE_R * CueScale
CUE_M = 0.05                          # |Cue| a decisive sign needs; client-tier margin, never retuned from emulator evidence (it reads ~20 % low there)
MM_MIN = (0.01 * H_MIN / H_SURVEY_MIN) ** 2   # |Mid|^2 below which the settle branch refuses (m^2); the lever itself only for a grab point near the palm's mid-plane (README). The lever scales with the hand, so an absolute floor sized at the survey is the binding rung below about 0.4x: this is the same 10 mm of lever carried down to H_MIN, about 3.2 mm. What that weakens: the on-axis refusal now only triggers within about 3 mm of the palm axis at the smallest supported hand, below the 8 mm the sensing review set at 1x. Deliberately not a scale-free MM > c*S^2 rung -- that is two more trees for a floor whose only job is to reject a lever near zero
# The four holds are authored in the prefab and nowhere here: no constant names a grip rotation or trim, and no clip writes one.
# The authored surface is the four hand stand-ins under EditorOnly/Jig/PropFrame (RightHand, LeftHand, RightHandFlipped,
# LeftHandFlipped, each the hand's pose in the parked prop's frame); each runtime grip node Frame/Grip{X} is that hand's inverse, materialized into the bare grip node by the
# jig's edit-mode solve. --check pins grip == inverse(hand) and reads the grips for the separation refusal below.
# ---- bidirectional grip: the mark rig and the two holds per hand (README SHow it works). Every geometry value here is mirrored in the prefab and pinned by --check; FLIP_DWELL and READ_DWELL are clip lengths.
FEATURE_DIR = (0.0, 0.0, 1.0)         # the feature direction, fixed by the entry and never authored: +Z of the prop's frame for the Mark sender, +Z of each hold host's frame for that hold's receiver, so a prop presented in a hold reads that hold's receiver at zero distance
MARK_H = 0.1                          # metres from the tip to the virtual feature the Mark sender stands at, along FEATURE_DIR; the hold receivers sit the same distance out, so sender and receiver centres share one sphere about the tip
MARK_R = 0.005                        # Mark sender sphere radius; it cancels in the differential (both hold readings shift alike) except within the sender's own radius of a hold, where that reading clamps at 1
HOLD_R = 0.25                         # hold receiver sphere radius, metres: both centres lie on the MARK_H sphere about the tip, so the largest separation either reading must span is 2*MARK_H, and both must stay off the zero clamp or the differential stops being a difference of distances. Not GATE_R's construction, where the clamp floor is a feature and two senders read two coincident receivers
HOLD_M = 0.196                        # |Palm/Near{h}| a decisive nearer-hold needs. A Proximity reading is 1 - d/HOLD_R, so HOLD_M*HOLD_R is metres of nearer-ness; for an antipodal hold pair the equivalent angular band about the bisecting plane solves HOLD_M*HOLD_R = 4*MARK_H*cos(pi/4)*sin(band/2), which at HOLD_R 0.25 makes that band 20 degrees, the dead band this entry shipped; a nearer pair is dead on more of the sphere than any band (dead_fraction measures it). Picked geometrically, never retuned from harness evidence (CUE_M's discipline); the harness scores the decision
HOLD_MIN_SEP = 90.0                   # degrees: the least separation between a hand's two hold directions --check accepts. Below it the dead band swallows near half the sphere of grab attitudes, all of it well before zero, and the nearer-hold read stops being a decision (hold_refusal prints the fraction and the remedy)
if not HOLD_R > 2 * MARK_H: raise SystemExit('REFUSE: HOLD_R must reach past the whole mark sphere (HOLD_R > 2 * MARK_H), or a hold reading sits on the zero clamp and the differential goes flat there')
FLIP_DWELL = 2 / FPS_FLOOR            # seconds the dispatch state holds after its driver sets Palm/Flip before Confirm's blend can sample it: a driver write reaches no reader on the evaluation that runs it, and a zero-length dispatch would let Confirm sample the unflipped blend once and bounce [EMPIRICAL: measured on the harness, the Frame weights move on the evaluation after the write]
READ_DWELL = FLIP_DWELL               # seconds Read{s} holds the settled pose in the frame the carry will present: the hold hosts follow that frame on the next solve, and a driver-free read needs one evaluation with the new value, which is the argument FLIP_DWELL rests on
MARK_TAG = 'GripMark'                 # the mark rig's own tag: the Hand boxes must never read the Mark, nor the hold receivers a palm
HOLDS = ['HoldR', 'HoldL', 'HoldRF', 'HoldLF']   # the four hold receivers, one per grip node, each on a host under Frame that rides its node's rotation
NEARS = ['NearR', 'NearL']            # the published differentials, Near{h} = Hold{h}F - Hold{h}: positive where the flipped hold is the nearer one
CONFIG = dict(glueName='AbsoluteGripProp_Fx',   # one build; the hammer's four holds are the prefab's, not a config's
              enableDefault=False)            # the enable's default; the prefab Toggle's defaultOn must agree
PREFIX = 'Palm/'
GLUE = 'AbsoluteGrip/'
MOUNT = 'GrabPosition/GrabBone/GrabBone_End/FreezeRotation/Cage'
GRAB_RADIUS = 0.03                    # physbone grab radius (with snapToHand the tip goes to the hand grab point, so this is reach, not core)
BONE_END = (0.0, 0.02, 0.0)           # GrabBone_End local position = the bone length
SQ3 = 1 / math.sqrt(3)
DIRS = [(SQ3, SQ3, SQ3), (SQ3, -SQ3, -SQ3), (-SQ3, SQ3, -SQ3), (-SQ3, -SQ3, SQ3)]   # T1..T4
def disc_range(s, n=4000):
    """min/max of Disc = SumE^2 - qa*SumE2 for a centred capsule of half-length s over a deterministic direction grid
    (Fibonacci sphere): E_j = s(|u.d_j| + 1) at k = 0.5."""
    lo, hi = float('inf'), float('-inf')
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - z * z); t = math.pi * (1 + 5 ** 0.5) * i
        u = (r * math.cos(t), r * math.sin(t), z)
        E = [s * (abs(sum(a * b for a, b in zip(u, d))) + 1) for d in DIRS]
        v = sum(E) ** 2 - QA * sum(e * e for e in E); lo = min(lo, v); hi = max(hi, v)
    return lo, hi
# The sqrt lookup clamps outside its knots, so a Disc the S band can produce but the lookup does not cover reads S
# wrong while the settle gate still passes: refuse rather than emit that.
_lo, _hi = disc_range(S_LO)[0], disc_range(S_HI)[1]
if not (LUT_LO <= _lo and LUT_HI >= _hi):
    raise SystemExit(f'REFUSE: sqrt lookup [{LUT_LO}, {LUT_HI}] does not cover Disc over the S band [{_lo:.5f}, {_hi:.5f}]')
PATS = list(itertools.product([1, -1], repeat=4))          # 16 oriented patterns
LINES = [p for p in PATS if p[0] == 1]                      # 8 lines, canonical rep sigma1 = +
PAIRINGS = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
READINGS = [f'T{j + 1}{s}' for j in range(4) for s in 'pm']
# Each box host's working rotation (Unity Euler, degrees): local +Z = +/-d_j. Animated to identity between grabs so the eight boxes
# coincide as one cube, and back to these at the latch. Pinned to the prefab's serialized rotations by --check and to DIRS by the
# refusal below, so neither the prefab nor this table can drift alone.
HOST_EULER = {'T1p': (324.7356, 45.0, 0.0), 'T1m': (35.2644, 225.0, 0.0), 'T2p': (35.2644, 135.0, 0.0), 'T2m': (324.7356, 315.0, 0.0),
              'T3p': (324.7356, 225.0, 0.0), 'T3m': (35.2644, 45.0, 0.0), 'T4p': (35.2644, 315.0, 0.0), 'T4m': (324.7356, 135.0, 0.0)}
def unity_euler_quat(e):
    """Unity's Quaternion.Euler: applied Z, then X, then Y (q = qy * qx * qz); returns (x, y, z, w)."""
    def axis(ax, deg):
        h = math.radians(deg) / 2; sn = math.sin(h); return tuple(sn * c for c in ax) + (math.cos(h),)
    def mul(a, b):
        ax, ay, az, aw = a; bx, by, bz, bw = b
        return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)
    return mul(mul(axis((0, 1, 0), e[1]), axis((1, 0, 0), e[0])), axis((0, 0, 1), e[2]))
def rot_vec(q, v):
    x, y, z, w = q; vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))
def qmul(a, b):
    """Unity's quaternion product (x, y, z, w): a * b, b applied first (rot_vec(qmul(a, b), v) == rot_vec(a, rot_vec(b, v)))."""
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)
def qinv(q): return (-q[0], -q[1], -q[2], q[3])
def same_rot(p, q, tol=1e-5):
    """one rotation, allowing the negated quaternion Unity may serialize instead."""
    return p is not None and q is not None and abs(abs(sum(x * y for x, y in zip(p, q))) - 1.0) < tol
for _n, _e in HOST_EULER.items():
    _j = int(_n[1]) - 1; _d = DIRS[_j] if _n[2] == 'p' else tuple(-c for c in DIRS[_j])
    if max(abs(a - b) for a, b in zip(rot_vec(unity_euler_quat(_e), (0, 0, 1)), _d)) > 1e-4:
        raise SystemExit(f'REFUSE: HOST_EULER[{_n}] does not point local +Z along {_d}')
GATES = ['HandL', 'HandR']                                  # the gate pair, hosts Cage/HandL, Cage/HandR
CUES = ['CueP', 'CueN']                                     # the cue pair, hosts Cage/Mid/ProxyA/CueP, Cage/Mid/ProxyB/CueN
def tag(sg): return ''.join('p' if x > 0 else 'm' for x in sg)
def line_of(sg): return sg if sg[0] == 1 else tuple(-x for x in sg)
def flipset(sg, ks): return tuple(sg[j] * (-1 if j in ks else 1) for j in range(4))
def hamming(a, b): return sum(x != y for x, y in zip(a, b))
def P(n): return PREFIX + n
def fmt(x):
    s = f'{x:.8g}'
    return s if ('.' in s or 'e' in s) else s + '.0'

# Every receiver's scene path, by receiver name: the one spelling of the tip subtree, read by the clip binding
# helper below and by the BIND table above it, so a node rename moves both together.
RECV_PATH = {**{r: f'{MOUNT}/{r}' for r in READINGS}, **{g: f'{MOUNT}/{g}' for g in GATES},
             'CueP': f'{MOUNT}/Mid/ProxyA/CueP', 'CueN': f'{MOUNT}/Mid/ProxyB/CueN'}

# Scene bindings riding the readout's leaf clips, as (path, sign): the aim pair reads these the frame they are
# written. The axis goes to both proxies, ProxyB negated, so the sign mux is two aim constraints and no extra AAP.
BIND = {P('MidX'): [(f'{MOUNT}/Mid/Transform.m_LocalPosition.x', 1)], P('MidY'): [(f'{MOUNT}/Mid/Transform.m_LocalPosition.y', 1)],
        P('MidZ'): [(f'{MOUNT}/Mid/Transform.m_LocalPosition.z', 1)]}
for ax in 'xyz':
    BIND[P('Axis' + ax.upper())] = [(f'{MOUNT}/Mid/ProxyA/Transform.m_LocalPosition.{ax}', 1), (f'{MOUNT}/Mid/ProxyB/Transform.m_LocalPosition.{ax}', -1)]
# The cue spheres' scale follows the sensed hand (config, CueScale): both hosts take the same value, sign +1.
BIND[P('CueScale')] = [(f'{RECV_PATH[c]}/Transform.m_LocalScale.{ax}', 1) for c in CUES for ax in 'xyz']

# ---------------- parameter + clip registry (readout document) ----------------
params = {}     # name -> spec dict
clips = {}      # clipname -> (param, value)
def param(name, spec): params[name] = spec
def clip_for(aap, value):
    """one clip per (aap, value); the clip writes the AAP as a parameter curve (and its BIND paths, if any)."""
    v = fmt(value).replace('-', 'n').replace('.', '_')
    name = aap.replace(PREFIX, '').replace('/', '_') + '__' + v
    clips[name] = (aap, value); return name
def lin(aap, terms, const=0.0, name=None):
    """Direct tree: aap = sum(coef * weightParam) + const. Merges duplicate weights; drops zero coefficients."""
    acc = {}
    for w, c in terms: acc[w] = acc.get(w, 0.0) + c
    if abs(const) > 1e-12: acc[P('One')] = acc.get(P('One'), 0.0) + const
    ch = [{'clip': clip_for(aap, c), 'directWeight': w} for w, c in acc.items() if abs(c) > 1e-12]
    if not ch: ch = [{'clip': clip_for(aap, 0.0), 'directWeight': P('One')}]
    return {'tree': 'direct', 'normalized': False, 'name': name or aap.replace(PREFIX, ''), 'directWeight': P('One'), 'children': ch}
def abs1d(aap, src, sign=1.0, name=None):
    """1D tree on a signed param: writes sign*|src| for |src| <= 1 (thresholds -1, 0, 1 with values 1, 0, 1)."""
    return {'tree': '1d', 'param': src, 'directWeight': P('One'), 'name': name or f'{aap.replace(PREFIX, "")} {"+" if sign > 0 else "-"}|{src.replace(PREFIX, "")}|',
            'children': [{'clip': clip_for(aap, sign), 'threshold': -1.0}, {'clip': clip_for(aap, 0.0), 'threshold': 0.0}, {'clip': clip_for(aap, sign), 'threshold': 1.0}]}
def half1d(aap, src, positive, R, name=None):
    """1D tree: writes max(src, 0) (positive) or max(-src, 0) for |src| <= R; saturates beyond."""
    lo, hi = (0.0, R) if positive else (R, 0.0)
    return {'tree': '1d', 'param': src, 'directWeight': P('One'), 'name': name or f'{aap.replace(PREFIX, "")} = {"+" if positive else "-"}half({src.replace(PREFIX, "")})',
            'children': [{'clip': clip_for(aap, lo), 'threshold': -R}, {'clip': clip_for(aap, 0.0), 'threshold': 0.0}, {'clip': clip_for(aap, hi), 'threshold': R}]}
def prod(aap, a, b, coef, name=None):
    """Direct product: aap += coef * a * b for AAPs a, b >= 0 (nested Direct; the inner weight is b)."""
    return {'tree': 'direct', 'normalized': False, 'name': name or f'{aap.replace(PREFIX, "")} += {fmt(coef)} {a.replace(PREFIX, "")} {b.replace(PREFIX, "")}',
            'directWeight': a, 'children': [{'clip': clip_for(aap, coef), 'directWeight': b}]}

def rd(j, s): return P(f'T{j + 1}{s}')
def E_terms(j, coef=1.0): return [(rd(j, 'p'), D * coef), (rd(j, 'm'), D * coef)]
E_CONST = -2 * (D - F)

# ---------------- parameters ----------------
for j in range(4):
    for s in 'pm': param(rd(j, s), {'type': 'float', 'default': 0.0})
for n in GATES + CUES + HOLDS: param(P(n), {'type': 'float', 'default': 0.0})   # the hold readings are declared here too: the Near trees weight on them
param(P('One'), {'type': 'float', 'default': 1.0, 'scratch': True})
R_M = 1.5                             # 1D half-tree range for |Mid| components (the working box)
scratch_aaps = [f'E{j+1}' for j in range(4)] + ['SumE', 'SumE_d1', 'SumE_d2', 'Disc', 'SqrtDisc'] + [f'G{k+1}' for k in range(4)] \
    + [f'SL_{tag(L)}' for L in LINES] + [f'D_{tag(a)}_{tag(b)}' for a, b in itertools.combinations(LINES, 2)] \
    + [f'O{i+1}' for i in range(3)] + [f'P{k+1}' for k in range(4)] + [f'T{i+1}{ab}' for i in range(3) for ab in 'ab'] \
    + [f'Mid{ax}{h}' for ax in 'XYZ' for h in 'pn']
for n in scratch_aaps: param(P(n), {'type': 'float', 'aap': True, 'scratch': True})
PUBLISHED = ['S', 'AxisX', 'AxisY', 'AxisZ', 'Res', 'Pattern', 'MidX', 'MidY', 'MidZ', 'MM', 'HandDiff', 'Cue', 'CueScale'] + NEARS
for n in PUBLISHED: param(P(n), {'type': 'float', 'aap': True})

# ---------------- Math layer (always-on) ----------------
math_children = []
for j in range(4): math_children.append(lin(P(f'E{j+1}'), E_terms(j), E_CONST))
math_children.append(lin(P('SumE'), sum((E_terms(j) for j in range(4)), []), 4 * E_CONST))
math_children.append(lin(P('SumE_d1'), [(P('SumE'), 1.0)]))
math_children.append(lin(P('SumE_d2'), [(P('SumE_d1'), 1.0)]))
# Mid = 3/4 sum_j m_j d_j, m_j = (R+ - R-) D/2 : linear in readings, same frame
for i, ax in enumerate('XYZ'):
    terms = []
    for j in range(4):
        c = 0.75 * DIRS[j][i] * D / 2
        terms += [(rd(j, 'p'), c), (rd(j, 'm'), -c)]
    math_children.append(lin(P(f'Mid{ax}'), terms, name=f'Mid{ax} = 3/4 sum m_j d_j'))
# Disc = SumE^2 - qa * sum E_j^2 : nested Direct products (both factors >= 0 AAPs)
disc_children = [{'tree': 'direct', 'normalized': False, 'name': 'SumE^2', 'directWeight': P('SumE'),
                  'children': [{'clip': clip_for(P('Disc'), 1.0), 'directWeight': P('SumE')}]}]
for j in range(4):
    disc_children.append({'tree': 'direct', 'normalized': False, 'name': f'-qa E{j+1}^2', 'directWeight': P(f'E{j+1}'),
                          'children': [{'clip': clip_for(P('Disc'), -QA), 'directWeight': P(f'E{j+1}')}]})
math_children.append({'tree': 'direct', 'normalized': False, 'name': 'Disc = SumE^2 - qa*SumE2', 'directWeight': P('One'), 'children': disc_children})
# SqrtDisc = lut(Disc): 1D piecewise-linear lookup, geometric knots
knots = [LUT_LO * (LUT_HI / LUT_LO) ** (i / (LUT_N - 1)) for i in range(LUT_N)]
math_children.append({'tree': '1d', 'param': P('Disc'), 'directWeight': P('One'), 'name': f'SqrtDisc = sqrt(Disc) lookup, {LUT_N} knots',
                      'children': [{'clip': clip_for(P('SqrtDisc'), math.sqrt(k)), 'threshold': k} for k in knots]})
# S = (SumE_d2 - SqrtDisc) / qa  (age-aligned inputs)
math_children.append(lin(P('S'), [(P('SumE_d2'), 1 / QA), (P('SqrtDisc'), -1 / QA)], name='S = (SumE_d2 - SqrtDisc)/qa'))
# CueScale = the cue spheres' scale, following the sensed hand OUTSIDE the survey and exactly 1 across it. CUE_R was the
# argmax of the worst-case cue differential over the surveyed hands; under the nearest-surface law a k-times hand read by
# a k-times sphere reads exactly what a 1x hand reads at 1x (the proxies sit at Mid +- axis, which already scale with the
# measured capsule), so CUE_M -- a client-tier margin, never retuned from emulator evidence -- carries over at every scale
# and the in-survey readings are unchanged by construction. One 1D tree on S, symmetric, with the survey flat between its
# two inner knots; the tree lerps in S, so the value is exactly S / S_SURVEY_LO below the survey and S / S_SURVEY_HI above.
# It clamps at the ends, so the no-data S (negative, -sqrt(LUT_LO)/qa) writes the bottom leaf and never 0 or a negative
# scale. The cue filters are never bound and a fresh overlap is a fresh acquisition episode with no deaf mode
# (runtime.md SContacts), so even a collapsed scale costs a re-acquisition, never a dead receiver.
CUE_SCALE_LEAVES = [(S_LO, S_LO / S_SURVEY_LO), (S_SURVEY_LO, 1.0), (S_SURVEY_HI, 1.0), (S_HI, S_HI / S_SURVEY_HI)]
# Refusal: a non-positive leaf would serialize a degenerate or mirrored cue host, which the clamp argument above rests on
# never happening -- and a zero-scale sphere reads 0 at every distance, which is a decisive-looking dead cue.
for _t, _v in CUE_SCALE_LEAVES:
    if not _v > 0: raise SystemExit(f'REFUSE: CueScale leaf at S = {_t} is {_v}; every leaf must be a positive scale')
math_children.append({'tree': '1d', 'param': P('S'), 'directWeight': P('One'), 'name': 'CueScale = S / nearer survey edge, 1 across the survey',
                      'children': [{'clip': clip_for(P('CueScale'), v), 'threshold': t} for t, v in CUE_SCALE_LEAVES]})
# G_k = 2 (E_k - S), same-frame from readings
for k in range(4): math_children.append(lin(P(f'G{k+1}'), E_terms(k, 2.0) + [(P('S'), -2.0)], 2 * E_CONST, name=f'G{k+1} = 2(E{k+1} - S)'))
# S_L = sum sigma_j (E_j - S)
for L in LINES:
    terms = []; const = 0.0
    for j in range(4): terms += E_terms(j, L[j]); const += L[j] * E_CONST
    terms.append((P('S'), -float(sum(L))))
    math_children.append(lin(P(f'SL_{tag(L)}'), terms, const, name=f'SL_{tag(L)} = sum sigma(E - S)'))
# D_ab = |S_a| - |S_b| for every line pair
for a, b in itertools.combinations(LINES, 2):
    n = P(f'D_{tag(a)}_{tag(b)}')
    math_children.append(abs1d(n, P(f'SL_{tag(a)}'), 1.0)); math_children.append(abs1d(n, P(f'SL_{tag(b)}'), -1.0))
# O_P = (E_b0 + E_b1) - (E_a0 + E_a1): the lighter pair of a Hamming-2 pairing is the one to flip (s cancels)
for i, (a, b) in enumerate(PAIRINGS):
    math_children.append(lin(P(f'O{i+1}'), E_terms(b[0]) + E_terms(b[1]) + E_terms(a[0], -1) + E_terms(a[1], -1), name=f'O{i+1} = mass{b} - mass{a}'))
# ---- lever proxy: MM = |Mid|^2 from the halves of Mid (1 hop behind their sources) ----
for ax in 'XYZ':
    for h, pos in (('p', True), ('n', False)): math_children.append(half1d(P(f'Mid{ax}{h}'), P(f'Mid{ax}'), pos, R_M))
mm = []
for ax in 'XYZ':
    Mp, Mn = P(f'Mid{ax}p'), P(f'Mid{ax}n')
    mm += [prod(P('MM'), Mp, Mp, 1.0), prod(P('MM'), Mn, Mn, 1.0)]
math_children.append({'tree': 'direct', 'normalized': False, 'name': 'MM = |Mid|^2', 'directWeight': P('One'), 'children': mm})
# ---- the two differentials: signed, so formed with a negative clip constant and read only as conditions ----
math_children.append(lin(P('HandDiff'), [(P('HandL'), 1.0), (P('HandR'), -1.0)], name='HandDiff = HandL - HandR'))
math_children.append(lin(P('Cue'), [(P('CueP'), 1.0), (P('CueN'), -1.0)], name='Cue = CueP - CueN'))
# The nearer-hold differentials, one per hand: positive means the flipped hold's receiver reads nearer the Mark than the authored
# hold's, in metres of nearer-ness over HOLD_R. Read only as a transition condition, in Read{s}.
for h in 'RL':
    math_children.append(lin(P('Near' + h), [(P(f'Hold{h}F'), 1.0), (P('Hold' + h), -1.0)], name=f'Near{h} = Hold{h}F - Hold{h}'))
math_layer = {'name': 'Palm/Math', 'states': {'Math (WD ON)': {'motion': {'tree': 'direct', 'normalized': False, 'name': 'Math', 'children': math_children}}}, 'default': 'Math (WD ON)'}

# ---------------- Select layer: 16 oriented-pattern states, one per sign pattern; rungs hop to Hamming neighbours ----------------
def D_cond(t, u):
    """condition 't better than u' (|S_t| < |S_u|) on the stored pair AAP."""
    ia, ib = LINES.index(t), LINES.index(u)
    if ia < ib: return f'{P("D_" + tag(t) + "_" + tag(u))} less 0'
    return f'{P("D_" + tag(u) + "_" + tag(t))} greater 0'
def state_name(sg): return f'S_{tag(sg)}'
def t_sign(sg, pair):
    """structural sign of T = 2(sigma_a W_a + sigma_b W_b) with W >= 0: +1/-1 if both sigmas agree, else 0 (either)."""
    s0, s1 = sg[pair[0]], sg[pair[1]]
    return s0 if s0 == s1 else 0
states = {}
for idx, sg in enumerate(PATS):
    L = line_of(sg); others = [t for t in LINES if t != L]
    ch = []
    # axis = sum sigma_j (E_j - S) d_j  -> Palm/Axis* and ProxyA / ProxyB localPosition (BIND)
    for i, ax in enumerate('XYZ'):
        terms = []; const = 0.0
        for j in range(4):
            c = sg[j] * DIRS[j][i]; terms += E_terms(j, c); const += c * E_CONST
        terms.append((P('S'), -sum(sg[j] * DIRS[j][i] for j in range(4))))
        ch.append(lin(P(f'Axis{ax}'), terms, const, name=f'Axis{ax}'))
    # P_k = 2 sum_{j != k} sigma_j (E_j - S)   (= S_sigma + S_(sigma flip k))
    for k in range(4):
        terms = []; const = 0.0
        for j in range(4):
            if j == k: continue
            terms += E_terms(j, 2 * sg[j]); const += 2 * sg[j] * E_CONST
        terms.append((P('S'), -2.0 * sum(sg[j] for j in range(4) if j != k)))
        ch.append(lin(P(f'P{k+1}'), terms, const, name=f'P{k+1}'))
    # T_a / T_b per pairing = 2 (sigma_a0 W_a0 + sigma_a1 W_a1)
    for i, (a, b) in enumerate(PAIRINGS):
        for lab, pr in (('a', a), ('b', b)):
            terms = []; const = 0.0
            for j in pr: terms += E_terms(j, 2 * sg[j]); const += 2 * sg[j] * E_CONST
            terms.append((P('S'), -2.0 * (sg[pr[0]] + sg[pr[1]])))
            ch.append(lin(P(f'T{i+1}{lab}'), terms, const, name=f'T{i+1}{lab}'))
    ch.append(lin(P('Pattern'), [], float(idx), name='Pattern stamp'))
    ch.append(abs1d(P('Res'), P(f'SL_{tag(L)}'), 1.0, name='Res = |S_held|'))
    # rungs
    rungs = []
    h1 = [t for t in others if hamming(sg, t) in (1, 3)]; h2 = [t for t in others if hamming(sg, t) == 2]
    for t in h1:
        k = next(j for j in range(4) if (sg[j] != t[j]) == (hamming(sg, t) == 1))
        target = flipset(sg, (k,))
        when = [f'{P("G" + str(k + 1))} greater {fmt(MARGIN)}',
                f'{P("P" + str(k + 1))} {"greater" if sg[k] > 0 else "less"} {fmt(MARGIN if sg[k] > 0 else -MARGIN)}']
        when += [D_cond(t, u) for u in others if u != t]
        rungs.append({'to': state_name(target), 'when': when, 'name': f'flip {k + 1}'})
    seen_pairings = set()
    for t in h2:
        flipped = tuple(j for j in range(4) if sg[j] != t[j])
        pi = next(i for i, (a, b) in enumerate(PAIRINGS) if set(a) == set(flipped) or set(b) == set(flipped))
        if pi in seen_pairings: continue
        seen_pairings.add(pi); a, b = PAIRINGS[pi]
        order = [D_cond(t, u) for u in others if u != t]
        for case in (1, -1):
            if t_sign(sg, a) * case < 0 or t_sign(sg, b) * case < 0: continue   # structurally impossible sign case
            op = 'greater' if case > 0 else 'less'; m = fmt(case * MARGIN)
            base = [f'{P("T" + str(pi + 1) + "a")} {op} {m}', f'{P("T" + str(pi + 1) + "b")} {op} {m}']
            # The pair's second rung carries no O condition: rungs are ordered, so an exact O = 0 tie (a stationary
            # palm with equal pair masses) still has a target instead of holding the wrong line until the timeout.
            rungs.append({'to': state_name(flipset(sg, a)), 'when': base + [f'{P("O" + str(pi + 1))} greater 0'] + order, 'name': f'flip {a[0]+1}{a[1]+1}'})
            rungs.append({'to': state_name(flipset(sg, b)), 'when': base + order, 'name': f'flip {b[0]+1}{b[1]+1}'})
    states[state_name(sg)] = {'motion': {'tree': 'direct', 'normalized': False, 'name': f'Select {tag(sg)}', 'children': ch}, 'transitions': rungs}
select_layer = {'name': 'Palm/Select', 'states': states, 'default': state_name(PATS[0])}

# ---------------- readout emit ----------------
def emit_motion(m, ind):
    pad = '  ' * ind; out = [f'{pad}tree: {m["tree"]}']
    if 'name' in m: out.append(f'{pad}name: "{m["name"]}"')
    if 'param' in m: out.append(f'{pad}param: {m["param"]}')
    if 'normalized' in m: out.append(f'{pad}normalized: {"true" if m["normalized"] else "false"}')
    if 'directWeight' in m: out.append(f'{pad}directWeight: {m["directWeight"]}')
    out.append(f'{pad}children:')
    for c in m['children']:
        if 'tree' in c:
            sub = emit_motion(c, ind + 2); sub[0] = f'{pad}  - ' + sub[0].lstrip(); out += sub
        elif 'threshold' in c: out.append(f'{pad}  - {{ clip: {c["clip"]}, threshold: {fmt(c["threshold"])} }}')
        else: out.append(f'{pad}  - {{ clip: {c["clip"]}, directWeight: {c["directWeight"]} }}')
    return out
def param_line(n, sp):
    fields = [f'type: {sp["type"]}']
    if 'default' in sp: fields.append(f'default: {fmt(sp["default"])}')
    if sp.get('aap'): fields.append('aap: true')
    if sp.get('scratch'): fields.append('scratch: true')
    return f'  {n}: {{ {", ".join(fields)} }}'
def emit_readout():
    L = ['# GENERATED by generate.py -- edit the generator, not this file. Mechanism and measurements: README.md.',
         f'# cage F={F} D={D} k={K} margin={MARGIN} m (|S| units); lut {LUT_N} knots over Disc [{LUT_LO}, {LUT_HI}] m^2;',
         '# published: S, Axis*, Res, Pattern, Mid*, MM = |Mid|^2, HandDiff = HandL - HandR, Cue = CueP - CueN; axis written to ProxyA (+) and ProxyB (-)',
         'schema: 1', 'controller: GripReadout_Fx', 'basis: mount-root', 'role: fx', '',
         'defaults:', '  writeDefaults: on', '  transition: { duration: 0, exitTime: none, interruption: none }', '', 'parameters:']
    for n, sp in params.items(): L.append(param_line(n, sp))
    L += ['', 'layers:']
    for layer in (math_layer, select_layer):
        L += [f'  - name: {layer["name"]}', '    states:']
        for sname, st in layer['states'].items():
            L.append(f'      "{sname}":'); L.append('        motion:'); L += emit_motion(st['motion'], 5)
            if st.get('transitions'):
                L.append('        transitions:')
                for r in st['transitions']:
                    L.append(f'          - {{ to: "{r["to"]}", name: "{r["name"]}", when: [ {", ".join(r["when"])} ] }}')
        L.append(f'    default: "{layer["default"]}"')
    L += ['', 'clips:']
    for cn, (aap, v) in clips.items():
        sets = [f'{aap}: {fmt(v)}'] + [f'"{path}": {fmt(sign * v)}' for path, sign in BIND.get(aap, [])]
        L.append(f'  {cn}: {{ set: {{ {", ".join(sets)} }} }}')
    return '\n'.join(L) + '\n'

# ---------------- glue document ----------------
# Every clip writes the layer's whole binding set (full ownership: on a scene binding a state writes only what its
# own clip writes, at either WD setting, so a delta clip inherits the previous state's values).
B_CONT_GO = 'Container/GameObject.m_IsActive'
B_BONE_GO = 'GrabPosition/GrabBone/GameObject.m_IsActive'
B_CONT_POS = 'Container/VRCPositionConstraint.m_Enabled'
B_SRC_ACT = 'Container/SourcePosition/VRCPositionConstraint.IsActive'
B_GP_ACT = 'GrabPosition/VRCPositionConstraint.IsActive'
B_GP_W0 = 'GrabPosition/VRCPositionConstraint.Sources.source0.Weight'
B_GP_W1 = 'GrabPosition/VRCPositionConstraint.Sources.source1.Weight'
B_ROT_EN = 'Container/Rotor/VRCRotationConstraint.m_Enabled'
B_ROT_W0 = 'Container/Rotor/VRCRotationConstraint.Sources.source0.Weight'   # HomeAnchor/Offset
B_ROT_W1 = 'Container/Rotor/VRCRotationConstraint.Sources.source1.Weight'   # Frame/GripR
B_ROT_W2 = 'Container/Rotor/VRCRotationConstraint.Sources.source2.Weight'   # Frame/GripL
B_ROT_W3 = 'Container/Rotor/VRCRotationConstraint.Sources.source3.Weight'   # Frame/GripRF (the right hand's flipped hold)
B_ROT_W4 = 'Container/Rotor/VRCRotationConstraint.Sources.source4.Weight'   # Frame/GripLF
B_FRM_W0 = f'{MOUNT}/Frame/VRCRotationConstraint.Sources.source0.Weight'   # Recon  (+Z at ProxyA = +axis)
B_FRM_W1 = f'{MOUNT}/Frame/VRCRotationConstraint.Sources.source1.Weight'   # ReconN (+Z at ProxyB = -axis)
B_DMP_EN = 'Container/Damped/VRCPositionConstraint.m_Enabled'                   # the placement smoother: source0 = self (never bound)
B_DMP_W1 = 'Container/Damped/VRCPositionConstraint.Sources.source1.Weight'      # Container (the tip): home
B_DMP_W2 = 'Container/Damped/VRCPositionConstraint.Sources.source2.Weight'      # Frame/GripR (the grab point plus that node's authored trim): right carry
B_DMP_W3 = 'Container/Damped/VRCPositionConstraint.Sources.source3.Weight'      # Frame/GripL: left carry
B_DMP_W4 = 'Container/Damped/VRCPositionConstraint.Sources.source4.Weight'      # Frame/GripRF: right carry, flipped hold
B_DMP_W5 = 'Container/Damped/VRCPositionConstraint.Sources.source5.Weight'      # Frame/GripLF: left carry, flipped hold
def recv_bindings(r):
    base = RECV_PATH[r]
    return {'go': f'{base}/GameObject.m_IsActive', 'self': f'{base}/VRCContactReceiver.allowSelf', 'others': f'{base}/VRCContactReceiver.allowOthers',
            'sx': f'{base}/Transform.m_LocalScale.x', 'sy': f'{base}/Transform.m_LocalScale.y', 'sz': f'{base}/Transform.m_LocalScale.z',
            'rx': f'{base}/Transform.localEulerAnglesRaw.x', 'ry': f'{base}/Transform.localEulerAnglesRaw.y', 'rz': f'{base}/Transform.localEulerAnglesRaw.z'}

RECV_GO = [recv_bindings(r)['go'] for r in READINGS + GATES + CUES]   # the twelve receiver GameObject actives
GRIPS = ['R', 'L', 'RF', 'LF']        # the rot_src values that name a grip node, in Rotor's and Damped's source order
STANDIN = {'R': 'RightHand', 'L': 'LeftHand', 'RF': 'RightHandFlipped', 'LF': 'LeftHandFlipped'}   # the jig's hand stand-in per grip node, under EditorOnly/Jig/PropFrame
def glue_clip(cont_go, bone_go, cont_pos, src_act, gp_act, gp_home, rot_en, rot_src, frame_sign, recv_go, filters_open, scale, place):
    """The full binding set as one `set:` map. gp_home selects GrabPosition source0 (home) vs source1; rot_src in
    {home, R, L, RF, LF} selects Rotor's source, one of the four authored grip nodes or the home offset; frame_sign
    +1/-1 selects Frame's Recon/ReconN. filters_open shuts the eight
    boxes' filters when False (the latch shuts them; True is open); the gate, cue and hold receivers' filters are never bound (the hand is read once, at the latch, and a shut sphere would
    reject the palm that leaves it and returns, which a remote's lagging palm does). scale selects the
    box hosts' pose as a unit: ACQ_SCALE = one coincident cage-aligned cube (identity rotation), 1 = the tetrahedral working cage.
    place in {home, hold, palm} drives the placement smoother on Damped: toward the tip, frozen, or toward the grip node
    rot_src names, whose local position is that node's authored trim off the grab point. A clip selects a grip node and never
    writes one; the mark rig's GameObjects are the mode Toggle's and no clip binds them."""
    if place == 'palm' and rot_src not in GRIPS: raise SystemExit(f'REFUSE: palm placement with no latched hand (rot_src={rot_src})')
    s = {B_CONT_GO: cont_go, B_BONE_GO: bone_go, B_CONT_POS: cont_pos, B_SRC_ACT: src_act, B_GP_ACT: gp_act,
         B_GP_W0: 1 if gp_home else 0, B_GP_W1: 0 if gp_home else 1,
         B_ROT_EN: rot_en, B_ROT_W0: 1 if rot_src == 'home' else 0,
         B_ROT_W1: 1 if rot_src == 'R' else 0, B_ROT_W2: 1 if rot_src == 'L' else 0, B_ROT_W3: 1 if rot_src == 'RF' else 0, B_ROT_W4: 1 if rot_src == 'LF' else 0,
         B_FRM_W0: 1 if frame_sign > 0 else 0, B_FRM_W1: 1 if frame_sign < 0 else 0,
         B_DMP_EN: 0 if place == 'hold' else 1, B_DMP_W1: SMOOTH_W if place == 'home' else 0,
         B_DMP_W2: SMOOTH_W if place == 'palm' and rot_src == 'R' else 0, B_DMP_W3: SMOOTH_W if place == 'palm' and rot_src == 'L' else 0,
         B_DMP_W4: SMOOTH_W if place == 'palm' and rot_src == 'RF' else 0, B_DMP_W5: SMOOTH_W if place == 'palm' and rot_src == 'LF' else 0}
    for r in READINGS:
        b = recv_bindings(r)
        s[b['go']] = recv_go; s[b['self']] = 1 if filters_open else 0; s[b['others']] = 1 if filters_open else 0
        s[b['sx']] = scale; s[b['sy']] = scale; s[b['sz']] = scale
        e = HOST_EULER[r] if scale == 1 else (0.0, 0.0, 0.0)
        s[b['rx']] = e[0]; s[b['ry']] = e[1]; s[b['rz']] = e[2]
    for c in GATES + CUES: s[recv_bindings(c)['go']] = recv_go
    return s

# grab-prop's seven values per state are its controller.yaml's, replicated; the rotation channel and the receiver
# set are this entry's. Comments beside each state carry the rationale.
FROZEN = dict(cont_go=1, bone_go=1, cont_pos=1, src_act=1, gp_act=0, gp_home=False, rot_en=0, rot_src='home', frame_sign=1, recv_go=1, filters_open=False, scale=1, place='hold')
def glue_clips(cfg):
  """The clip table: one build, and every carry and recheck clip in two versions, the authored hold and the flipped one."""
  return {
      # Off: receiver GOs and bone GO off; Container hidden. A stowed receiver reads exactly 0, and the Disabled
      # state's entry driver zeroes the twelve params so nothing stale gates the next enable. Held for DISABLED_DWELL
      # so the receiver off outlives one evaluation (a same-frame off/on leaves a receiver deaf for the session).
      'disabled': dict(length=DISABLED_DWELL, set=glue_clip(0, 0, 1, 1, 0, True, 1, 'home', 1, 0, True, ACQ_SCALE, 'home')),
      # Remote boot dwell (grab-prop's timer): hidden, bone alive so a grab in progress is not missed.
      'timer': dict(length=1.0, set=glue_clip(0, 1, 1, 1, 0, True, 1, 'home', 1, 1, True, ACQ_SCALE, 'home')),
      # Home: prop on the hip offset, Rotor riding the home attitude, cage at acquisition scale with filters open.
      'anchored': dict(set=glue_clip(1, 1, 1, 1, 1, True, 1, 'home', 1, 1, True, ACQ_SCALE, 'home')),
      # Grabbed, palm not yet latched: position rides the tip (grab-prop's grabbed), Rotor disabled = the prop holds
      # its pose, the eight boxes one coincident cube with filters open. Arrive plays it for the arrive dwell and hands
      # over to Acquire, which polls the latch every frame (an exit-time rung with conditions re-tests only once per
      # clip period, measured, so the dwell and the poll are two states).
      'acquire': dict(length=ARRIVE_DWELL, set=glue_clip(1, 1, 1, 1, 0, False, 0, 'home', 1, 1, True, ACQ_SCALE, 'hold')),
      # The latch: box filters shut at acquisition scale on frame 0 (what is inside now is what stays latched), box hosts
      # from the coincident cube to the tetrahedral working cage on frame 1 (scale and rotation step together). Two frames
      # long, played by LatchedR and LatchedL, whose entry drivers record the hand; Settling takes over at exit time.
      'latched': dict(length=2 * FRAME, set={k: v for k, v in glue_clip(1, 1, 1, 1, 0, False, 0, 'home', 1, 1, False, ACQ_SCALE, 'hold').items()
                                               if not re.search(r'Transform\.(m_LocalScale|localEulerAnglesRaw)\.[xyz]$', k)},
                      curves={**{k: {'tangents': 'stepped', 'keys': [[0, ACQ_SCALE], [FRAME, 1]]}
                                 for r in READINGS for k in (recv_bindings(r)['sx'], recv_bindings(r)['sy'], recv_bindings(r)['sz'])},
                              **{recv_bindings(r)['r' + ax]: {'tangents': 'stepped', 'keys': [[0, 0.0], [FRAME, HOST_EULER[r][i]]]}
                                 for r in READINGS for i, ax in enumerate('xyz')}}),
      # A latched contact that broke while the filters were shut and came back is never re-acquired by reopening
      # them (acquisition is an enter event); a slow receiver stow re-acquires a sender already inside. So every
      # loss after the latch and the settle timeout pass through here: all twelve receiver GOs off for the same dwell
      # Disabled uses, cage at acquisition scale with filters open, then Acquire.
      'reacquire': dict(length=DISABLED_DWELL, set=glue_clip(1, 1, 1, 1, 0, False, 0, 'home', 1, 0, True, ACQ_SCALE, 'hold')),
      # Latched, readout pipeline priming: working scale, filters shut, Rotor frozen. Nothing is polled here.
      'settling': dict(length=SETTLE_FILL, set=glue_clip(**FROZEN)),
      # Same pose; the engage rungs are conditional here (polled every frame), the timeout is the length.
      'settled': dict(length=SETTLE_TIMEOUT - SETTLE_FILL, set=glue_clip(**FROZEN)),
      # Carry, one clip per hand, sign and hold, played by Confirm and Carry alike: Rotor rides one of the latched hand's two grip nodes
      # (the F clip its flipped hold, the blend's 1-end),
      # Frame on the aim constraint for the latched sign, and the placement smoother eases the payload origin onto that hand's
      # grip node. Confirm plays it provisionally while every engage condition is re-tested each frame, so the length is Confirm's
      # dwell and its exit time the irreversible decision (Carry has no exit-time rung, so the length is inert there); a bounce
      # back to Settled freezes the pose it reached. Hand and sign are the state; the gate is never re-read while carrying, the cue is, by Recheck.
      **{f'carry{h}{s}{f}': dict(length=CONFIRM_DWELL, set=glue_clip(1, 1, 1, 1, 0, False, 1, h + f, 1 if s == 'P' else -1, 1, False, 1, 'palm')) for h in 'RL' for s in 'PN' for f in ('', 'F')},
      # Recheck, one clip per hand and sign: the carry pose unchanged, the length the recheck dwell (a state's exit time is its clip's
      # length, so the dwell needs a clip of its own). Played while the cue reads against the latched sign; the exit time flips the sign.
      **{f'recheck{h}{s}{f}': dict(length=RECHECK_DWELL, set=glue_clip(1, 1, 1, 1, 0, False, 1, h + f, 1 if s == 'P' else -1, 1, False, 1, 'palm')) for h in 'RL' for s in 'PN' for f in ('', 'F')},
      # grab-prop's release pulse (its sample window verbatim) plus the rotation freeze: Rotor disabled at t = 0.
      # Filters reopen and the cage collapses at t = 0, so the readout stops being consumed on the release frame.
      # The receivers ride a stepped off-then-on for the stow dwell at the head: a release can land one frame after a stow
      # state switched them off, and a receiver toggled off and on inside one evaluation with its sender inside (the tip is in
      # the hand) is deaf for the session; held off for the dwell, the re-enable is a slow stow that re-acquires.
      'released': dict(length=0.5, set={k: v for k, v in glue_clip(1, 1, 0, 1, 1, False, 0, 'home', 1, 1, True, ACQ_SCALE, 'hold').items() if k != B_SRC_ACT and k not in RECV_GO},
                       curves={B_SRC_ACT: {'tangents': 'stepped', 'keys': [[0, 0], [0.25, 1], [0.5, 0]]},
                               **{k: {'tangents': 'stepped', 'keys': [[0, 0], [DISABLED_DWELL, 1]]} for k in RECV_GO}}),
      # World-dropped: both freezes hold (the frozen transform IS the hold); a grab re-enters Acquire.
      'dropped': dict(set=glue_clip(1, 1, 0, 0, 1, False, 0, 'home', 1, 1, True, ACQ_SCALE, 'hold')),
      # Late-join park (grab-prop's waiting): hidden until a witnessed grab; the bone lives outside the hidden branch.
      'waiting': dict(set=glue_clip(0, 1, 1, 1, 1, True, 1, 'home', 1, 1, True, ACQ_SCALE, 'home')),
      # The flip dispatch: the settled pose held for FLIP_DWELL after the state's entry driver set Palm/Flip, so the blend in the
      # Confirm that follows has seen the new value on its first evaluation. The `latched` clip's stepped curves make it unusable here.
      'flip': dict(length=FLIP_DWELL, set=glue_clip(**FROZEN)),
      # The read, one clip per sign: the settled pose with Frame on that sign's aim constraint, so the hold receivers ride the frame
      # the carry will present and measure the candidates the carry will land on. Rotor is still disabled, so nothing visible moves.
      **{f'read{s}': dict(length=READ_DWELL, set=glue_clip(**dict(FROZEN, frame_sign=1 if s == 'P' else -1))) for s in 'PN'},
  }
# Refusal: a cue, gate or hold receiver whose filters a clip could shut is a receiver that never re-admits a contact that broke
# (a latched contact that fully breaks cannot re-latch while filters are shut): the pinky-side cue contact breaks during a
# curl, and a remote grabber's palm leaves the gate sphere on any fast swing. The hold receivers are always on for the same
# reason in its sharpest form: their sender can never leave them, so a bounce would come back deaf for the session.
# Refusal: a clip that wrote a grip node would make the authored hold the generator's rather than the author's. The clips select
# a node (Rotor's and Damped's source weights) and write none.
for cn, c in glue_clips(CONFIG).items():
    for k in list(c['set']) + list(c.get('curves', {})):
        if re.search(r'/(Cue[PN]|Hand[LR]|Hold(?:R|L|RF|LF))/VRCContactReceiver\.allow', k): raise SystemExit(f'REFUSE: clip {cn} binds a cue, gate or hold receiver filter ({k})')
        if re.search(r'/(MarkProxy|Hold(?:R|L|RF|LF))/GameObject', k): raise SystemExit(f'REFUSE: clip {cn} binds a mark rig GameObject ({k}); the mode Toggle owns MarkProxy and the hold hosts are never toggled')
        if re.search(r'/Frame/Grip(?:R|L|RF|LF)/', k): raise SystemExit(f'REFUSE: clip {cn} binds a grip node ({k}); a clip selects a grip node and never writes one')

ENABLE = GLUE + 'Enable'
BIDIR = GLUE + 'Bidir'                                                                  # the bidirectional mode: unsynced, saved, the second Toggle's global parameter
HAND = P('Hand')                                                                        # int, driver-set at the latch: 1 = right, 2 = left
FLIP = P('Flip')                                                                        # float, driver-set: 1 = present the flipped grip; read only by the carry blends
DECIDED, DOWN = P('Decided'), P('Down')                                                 # the two synced bits, written by the wearer's copy alone (every driver on them is localOnly)
HAND_OF = {'R': 1, 'L': 2}
LATCH = {'R': f'{P("HandDiff")} less {fmt(-GATE_M)}', 'L': f'{P("HandDiff")} greater {fmt(GATE_M)}'}   # the latch rungs: a decisive differential names the hand
HANDS = {h: f'{HAND} equals {v}' for h, v in HAND_OF.items()}                            # the engage rungs read the recorded hand
SIGNS = {'P': f'{P("Cue")} greater {fmt(CUE_M)}', 'N': f'{P("Cue")} less {fmt(-CUE_M)}'}
OPP = {'P': 'N', 'N': 'P'}
def bounce(cond):
    """the Confirm bounce rung for an entry condition: the complement, loosened by BOUNCE_H toward the failing side (a margin
    must retreat to BOUNCE_H of its entry value, a ceiling be overshot by 1/BOUNCE_H) so the two rungs never share a threshold.
    A reading between the two satisfies neither and rides Confirm's exit time into Carry, which is the hysteresis working."""
    p, op, v = cond.rsplit(' ', 2); v = float(v)
    nv = v * BOUNCE_H if op == 'greater' else (v / BOUNCE_H if v > 0 else v * BOUNCE_H)
    return f'{p} {"less" if op == "greater" else "greater"} {fmt(nv)}'
def hold_separation(q_X, q_XF):
    """(degrees between the two holds' feature directions, fraction of grab attitudes that read the dead band) for one hand's
    authored and flipped grip rotations, as serialized (x, y, z, w). The feature direction of a hold is q . FEATURE_DIR, and both
    receivers sit MARK_H out along theirs, so the whole read is that angle: the differential is HOLD_M only for a Mark far enough
    off the plane bisecting the two, and the closer the two holds the less of the sphere is far enough: dead_fraction measures it.
    The caller is --check, here and in any composition or venue that nests this cell: one implementation, one refusal string."""
    a, b = rot_vec(q_X, FEATURE_DIR), rot_vec(q_XF, FEATURE_DIR)
    theta = math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))
    return theta, dead_fraction(theta)
def dead_fraction(theta_deg, n=240):
    """fraction of the sphere of grab attitudes whose two hold readings differ by less than HOLD_M: the Mark at MARK_H along
    unit u against receivers at MARK_H along the two hold directions, |dist(u, a) - dist(u, b)| <= HOLD_M * HOLD_R, measured by
    midpoint quadrature over an equal-area (z, phi) grid. Closed forms hold only for an antipodal pair (a great-circle band of
    half-angle 2*asin(HOLD_M*HOLD_R / (4*MARK_H*cos(pi/4)))); nearer pairs are dead on a region no band describes, and a pair
    whose receivers sit closer than HOLD_M*HOLD_R apart is dead everywhere."""
    th = math.radians(theta_deg); s, c = math.sin(th / 2), math.cos(th / 2)
    if 2 * MARK_H * s <= HOLD_M * HOLD_R: return 1.0
    ax, az, bx = MARK_H * s, MARK_H * c, -MARK_H * s
    thr, dead = HOLD_M * HOLD_R, 0
    for i in range(n):
        z = -1 + (2 * i + 1) / n; r = math.sqrt(1 - z * z)
        for j in range(n):
            phi = (2 * j + 1) * math.pi / n
            x, y, w = MARK_H * r * math.cos(phi), MARK_H * r * math.sin(phi), MARK_H * z
            da = math.sqrt((x - ax) ** 2 + y * y + (w - az) ** 2); db = math.sqrt((x - bx) ** 2 + y * y + (w - az) ** 2)
            if abs(da - db) <= thr: dead += 1
    return dead / (n * n)
def hold_refusal(theta_deg):
    """The refusal string for a hold separation, or None. Read it off hold_separation's first return value."""
    if theta_deg >= HOLD_MIN_SEP: return None
    dead = dead_fraction(theta_deg)
    return (f'REFUSE: the two holds of this hand separate their feature directions by {theta_deg:.1f} deg, under HOLD_MIN_SEP {HOLD_MIN_SEP:g} deg; '
            f'{dead * 100:.0f}% of grab attitudes would read the dead band and take the authored hold. Remedy: turn the mesh under Damped so the '
            f'feature direction (prop-frame +Z) separates the two holds you mean, then re-author both grip nodes to it')
def glue_states(cfg):
    grabbed = 'GrabBone_IsGrabbed is true'; released = 'GrabBone_IsGrabbed is false'
    en_off = f'{ENABLE} is false'; bidir_on = f'{BIDIR} is true'
    local, remote = 'IsLocal is true', 'IsLocal is false'
    dec_t, dec_f, down_t, down_f = f'{DECIDED} is true', f'{DECIDED} is false', f'{DOWN} is true', f'{DOWN} is false'
    flip_lo, flip_hi = f'{FLIP} less 0.5', f'{FLIP} greater 0.5'
    settled = [f'{P("Res")} less {fmt(RES_SETTLE)}', f'{P("S")} greater {fmt(S_LO)}', f'{P("S")} less {fmt(S_HI)}', f'{P("MM")} greater {fmt(MM_MIN)}']
    all_pos = [f'{P(r)} greater 0' for r in READINGS]
    zero = {P(r): 0 for r in READINGS + GATES + CUES + HOLDS + NEARS}; zero[HAND] = 0
    # carry: the reopen precedes any plausible return. With the mode on the wearer passes through Lost, which clears the bits: the
    # re-acquisition that follows decides afresh, and a remote reaching its own Settled meanwhile must wait for that word, not
    # re-engage on the last grab's. Remotes read the mode's default and go straight to Acquire, as does the mode-off wearer.
    loss = sum(([{'to': 'Lost', 'when': [f'{P(r)} less 0.00001', bidir_on]}, {'to': 'Acquire', 'when': [f'{P(r)} less 0.00001']}] for r in READINGS), [])
    stow = [{'to': 'Reacquire', 'when': [f'{P(r)} less 0.00001']} for r in READINGS]      # latched but not carrying: the hand can be back before the reopen
    common = lambda: [{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]}]
    # The two bits are the wearer's alone: every driver naming them is localOnly, and the bit writes never share a driver entry
    # with a Palm/Flip write. Cleared where a grab ends (Released) and where the module resets (Disabled), never in Settled: a
    # Confirm bounce must not put a set-then-clear pair on the wire.
    bits_clear = {'driver': {'localOnly': True, 'set': {DECIDED: 0, DOWN: 0}}}
    # Every grab enters Arrive, or ArriveBi with the mode on. Arrive stamps the "decided, authored" word at once, so with the mode
    # off a remote's wait (Hold below) lasts at most the sync tick between its own grab and the wearer's write; ArriveBi leaves
    # both bits clear, so a remote holds the pre-grab attitude on the hand until the wearer's copy has decided.
    grab_rungs = lambda: [{'to': 'ArriveBi', 'when': [grabbed, bidir_on]}, {'to': 'Arrive', 'when': [grabbed]}]
    st = {
        'Timer': dict(clip='timer', transitions=[{'to': 'Disabled', 'when': ['IsLocal is true']}, {'to': 'Waiting', 'when': ['IsLocal is false'], 'exitTime': 1.0}]),
        'Disabled': dict(clip='disabled', behaviours=[{'driver': {'set': zero}}, bits_clear],
                         transitions=[{'to': 'Anchored', 'when': [f'{ENABLE} is true'], 'exitTime': 1.0}]),
        'Anchored': dict(clip='anchored', transitions=[{'to': 'Disabled', 'when': [en_off]}] + grab_rungs()),
        # A fresh grab waits here while the bone snaps to the hand grab point; loss and stow paths re-enter Acquire
        # directly, since the tip is already in the hand.
        'Arrive': dict(clip='acquire', behaviours=[{'driver': {'localOnly': True, 'set': {DECIDED: 1, DOWN: 0}}}], transitions=common() + [{'to': 'Acquire', 'when': [], 'exitTime': 1.0}]),
        'ArriveBi': dict(clip='acquire', transitions=common() + [{'to': 'Acquire', 'when': [], 'exitTime': 1.0}]),
        # The latch decides the hand: a decisive hand differential on the tip spheres, read at the one instant the tip is provably
        # in that palm (the snap-on grab put it there), enters the Latched state for that hand, whose entry driver records it. The
        # eight box readings are not geometry (the coincident acquisition cube contains the spheres, ACQ_SCALE) but proof that every
        # box has acquired the palm before Latched shuts its filter: after a stow each receiver re-acquires a sender already inside
        # over a few frames drawn per receiver, and a box whose filter shuts first never acquires (runtime.md). Two palms reading
        # alike, or none, take no latch; the gate is never read again.
        'Acquire': dict(clip='acquire', transitions=common() + [{'to': f'Latched{h}', 'when': [grabbed] + all_pos + [LATCH[h]]} for h in 'RL']),
        'Lost': dict(clip='acquire', behaviours=[bits_clear], transitions=common() + [{'to': 'Acquire', 'when': [], 'exitTime': 1.0}]),
        'Reacquire': dict(clip='reacquire', transitions=common() + [{'to': 'Acquire', 'when': [], 'exitTime': 1.0}]),
        **{f'Latched{h}': dict(clip='latched', behaviours=[{'driver': {'set': {HAND: HAND_OF[h]}}}], transitions=common() + [{'to': 'Settling', 'when': [], 'exitTime': 1.0}]) for h in 'RL'},
        'Settling': dict(clip='settling', transitions=common() + stow + [{'to': 'Settled', 'when': [], 'exitTime': 1.0}]),
        # Settled polls the engage conditions every frame. Ahead of the four engage rungs, in this order: the wearer's read rungs
        # (mode on, the sensed sign: the per-sign read state); a remote whose word is undecided holds; a remote whose word says
        # flipped dispatches. A remote whose word says the authored hold, and the wearer with the mode off, fall through to the
        # engage rungs. An undecided sign or lever falls through to the timeout, which stows: a palm that broke and returned
        # behind the shut box filters is inside the boxes and never re-enters. Entry clears Palm/Flip, so a bounce re-decides.
        'Settled': dict(clip='settled', behaviours=[{'driver': {'set': {FLIP: 0}}}],
                        transitions=common() + stow
                        + [{'to': f'Read{s}', 'when': settled + [SIGNS[s], local, bidir_on]} for s in 'PN']
                        + [{'to': 'Hold', 'when': [remote, dec_f] + settled + [SIGNS[s]]} for s in 'PN']
                        + [{'to': f'Flip{s}', 'when': [remote, dec_t, down_t] + settled + [SIGNS[s]]} for s in 'PN']
                        + [{'to': f'Confirm{h}{s}', 'when': settled + [HANDS[h], SIGNS[s]]} for h in 'RL' for s in 'PN']
                        + [{'to': 'Reacquire', 'when': [], 'exitTime': 1.0}]),
        # The read, one state per sign because the read must happen in the frame the carry will present: the hold hosts ride Frame, and
        # at sign N the frame is the sign-P frame turned half about +Y, so the sign-P reading ranks a different pair of world directions
        # than the sign-N carry will land on. Read{s} puts Frame on that sign's aim constraint for READ_DWELL with Rotor still disabled
        # (nothing visible moves), then dispatches at exit time: the flipped hold if this hand's differential names it, else the
        # authored hold's Confirm. Wearer-only -- a remote takes the word. A reading retreating past the bounce threshold returns to
        # Settled, which clears the flip, exactly as in Flip{s}.
        **{f'Read{s}': dict(clip=f'read{s}',
                            transitions=common() + stow + [{'to': 'Settled', 'when': [bounce(c)]} for c in settled + [SIGNS[s]]]
                            + [{'to': f'Flip{s}', 'when': [HANDS[h], f'{P("Near" + h)} greater {fmt(HOLD_M)}'], 'exitTime': 1.0} for h in 'RL']
                            + [{'to': f'Confirm{h}{s}', 'when': [HANDS[h]], 'exitTime': 1.0} for h in 'RL']) for s in 'PN'},
        # The flip dispatch, one per sign so its bounce rung is the sign's own: the entry driver sets Palm/Flip, the settled pose holds
        # for FLIP_DWELL, and the exit time engages the recorded hand's Confirm for this sign, whose blend then samples the flipped
        # clip on its first evaluation. A reading retreating past the bounce threshold returns to Settled, which clears the flip.
        # Remotes enter it too (from Settled on the word, from Carry on a changed word), so the driver is not localOnly.
        **{f'Flip{s}': dict(clip='flip', behaviours=[{'driver': {'set': {FLIP: 1}}}],
                            transitions=common() + stow + [{'to': 'Settled', 'when': [bounce(c)]} for c in settled + [SIGNS[s]]]
                            + [{'to': f'Confirm{h}{s}', 'when': [HANDS[h]], 'exitTime': 1.0} for h in 'RL']) for s in 'PN'},
        # A remote's wait for the wearer's word: the settled pose (attitude frozen, position riding the hand, exactly the acquisition
        # states' hold), left only when the word lands or the gate bounce-fails. Gated on the bit, not the mode (a remote reads the
        # unsynced mode's default), so with the mode off a fast third-party grab can hold for up to about one sync tick before
        # Arrive's write lands: position-only and benign. No timeout of its own, and Settled's cannot run from here: a remote whose word never
        # lands (the wearer's copy never reached Carry) holds for the grab, the same refusal the wearer shows.
        'Hold': dict(clip='settled', transitions=common() + stow + [{'to': 'Settled', 'when': [dec_t]}] + [{'to': 'Settled', 'when': [bounce(c)]} for c in settled]),
    }
    for h in 'RL':
        for s in 'PN':
            # Any readout condition failing during the dwell returns to Settled (the recorded hand cannot fail); the exit time is the engage.
            # The motion is a blend on Palm/Flip between the carry clip and its flipped twin: the state's sign stays the cue's thumb
            # truth, and presenting the other pose does not change which end of the palm line the thumb is on.
            st[f'Confirm{h}{s}'] = dict(blend=(f'carry{h}{s}', f'carry{h}{s}F'), transitions=common() + stow + [{'to': 'Settled', 'when': [bounce(c)]} for c in settled + [SIGNS[s]]]
                                        + [{'to': f'Carry{h}{s}', 'when': [], 'exitTime': 1.0}])
    for h in 'RL':
        for s in 'PN':
            # Carry keeps reading the cue: a decisive opposite sign enters Recheck, which plays the same pose for the recheck dwell and
            # flips the sign at its exit time; the cue retreating past the bounce threshold returns to Carry. A ladder reversal past the
            # orientation ambiguity is thereby a wrong grip for the dwell, not for the grab, and a cue that flickers (measured runs a
            # fraction of the dwell) never flips it. The hand is still never re-read. The return rung is Confirm's bounce hysteresis, so a
            # cue that has retreated only into the dead band still rides to the flip: the dwell is the guard, not the threshold, and a
            # Carry/Recheck flap only restarts it.
            # Entry stamps the wearer's decision on the wire: Decided, and Down copied from the flip the blend is presenting (a copy, not
            # a Set, so one driver serves both dispatch paths and a re-entry from Recheck re-asserts the same values). A remote whose
            # word changed under it (the wearer re-acquired mid-grab and decided the other way) re-confirms through Flip or Settled.
            st[f'Carry{h}{s}'] = dict(blend=(f'carry{h}{s}', f'carry{h}{s}F'),
                                      behaviours=[{'driver': {'localOnly': True, 'set': {DECIDED: 1}}}, {'driver': {'localOnly': True, 'copy': {DOWN: FLIP}}}],
                                      transitions=common() + loss + [{'to': f'Recheck{h}{s}', 'when': [SIGNS[OPP[s]]]},
                                                                     {'to': f'Flip{s}', 'when': [remote, dec_t, down_t, flip_lo]},
                                                                     {'to': 'Settled', 'when': [remote, dec_t, down_f, flip_hi]}])
            st[f'Recheck{h}{s}'] = dict(blend=(f'recheck{h}{s}', f'recheck{h}{s}F'), transitions=common() + loss + [{'to': f'Carry{h}{s}', 'when': [bounce(SIGNS[OPP[s]])]},
                                                                                                                                {'to': f'Carry{h}{OPP[s]}', 'when': [], 'exitTime': 1.0}])
    st.update({
        'Released': dict(clip='released', behaviours=[bits_clear], transitions=[{'to': 'Dropped', 'when': [], 'exitTime': 1.0}]),
        'Dropped': dict(clip='dropped', transitions=[{'to': 'Disabled', 'when': [en_off]}] + grab_rungs()),
        'Waiting': dict(clip='waiting', transitions=[{'to': 'Disabled', 'when': [en_off]}] + grab_rungs()),
    })
    # Refusal: a driver naming a synced bit without localOnly would run on every remote's copy of the animator; VRCFury's make-
    # synced-drivers-local pass skips merged layers, so nothing downstream rewrites the flag.
    for sname, s_ in st.items():
        for b in s_.get('behaviours', []):
            d = b['driver']
            names = set(d.get('set', {})) | set(d.get('copy', {}))
            if names & {DECIDED, DOWN} and not d.get('localOnly'): raise SystemExit(f'REFUSE: {sname} drives a synced bit without localOnly')
            if names & {DECIDED, DOWN} and FLIP in names: raise SystemExit(f'REFUSE: {sname} writes a synced bit and Palm/Flip in one driver entry')
    return st
LAYOUT = {'Timer': [30, 180], 'Waiting': [-210, 250], 'Disabled': [30, 250], 'Reacquire': [270, 250], 'Anchored': [-210, 390], 'Arrive': [-210, 530], 'ArriveBi': [-210, 620], 'Acquire': [30, 390],
          'LatchedR': [270, 340], 'LatchedL': [270, 440], 'Settling': [510, 390], 'Settled': [750, 390], 'ReadP': [750, 250], 'ReadN': [750, 530], 'FlipP': [870, 250], 'FlipN': [870, 530], 'Hold': [750, 620], 'Lost': [30, 530],
          'ConfirmRP': [990, 250], 'ConfirmRN': [990, 340], 'ConfirmLP': [990, 440], 'ConfirmLN': [990, 530],
          'CarryRP': [1230, 250], 'CarryRN': [1230, 340], 'CarryLP': [1230, 440], 'CarryLN': [1230, 530],
          'RecheckRP': [1470, 250], 'RecheckRN': [1470, 340], 'RecheckLP': [1470, 440], 'RecheckLN': [1470, 530],
          'Released': [510, 620], 'Dropped': [270, 620]}

# Names this document reads or drives that readout.yaml declares: declared here as scratch so readout.yaml alone
# emits them into a params asset. The four hold readings are receiver-written inputs of the readout's Near trees; this
# document only reads the two differentials, and zeroes all six at Disabled.
GLUE_READS = READINGS + GATES + CUES + ['Res', 'S', 'MM', 'HandDiff', 'Cue'] + HOLDS + NEARS
def glue_params(): return {P(n): {'type': 'float', 'scratch': True} for n in GLUE_READS}
# Refusal: the FullController merges the two documents first-wins per list, glue first, so a name both declare with
# different type, default or vrc flags silently takes the glue's (a glue-side Palm/One would read 0 and blank every
# tree that weights on it). `scratch`/`aap` are legibility markers and may differ.
for n, sp in glue_params().items():
    if n in params:
        for f in ('type', 'default', 'vrc'):
            a, b = sp.get(f, 0.0 if f == 'default' else None), params[n].get(f, 0.0 if f == 'default' else None)
            if a != b: raise SystemExit(f'REFUSE: {n} declared {f}={a!r} by the glue and {f}={b!r} by the readout; glue-first merge would win silently')

def emit_driver(d):
    parts = []
    if d.get('localOnly'): parts.append('localOnly: true')
    for op in ('set', 'copy'):
        if op in d: parts.append(f'{op}: {{ {", ".join(f"{k}: {v}" for k, v in d[op].items())} }}')
    return '{ ' + ', '.join(parts) + ' }'
def emit_glue(cfg=CONFIG):
    L = ['# GENERATED by generate.py -- edit the generator, not this file. Mechanism: README.md.',
         '# absolute-grip-prop glue: grab-prop\'s cell (clip table replicated binding for binding) + the cage latch that decides the',
         '# hand, the confirm dwell that decides the sign once, and four carry states riding an authored grip node, each with a recheck that flips the sign',
         '# after the cue has read against it for a dwell. Reads GripReadout_Fx\'s AAPs through',
         '# the shared FullController.',
         f'# thresholds: latch |HandDiff| > {GATE_M}; engage: Res settle {RES_SETTLE} m, S band [{S_LO}, {S_HI}] m, lever proxy MM > {MM_MIN:g} m^2, cue |Cue| > {CUE_M};',
         f'# arrive dwell {ARRIVE_DWELL:.4g} s, fill {SETTLE_FILL:.4g} s ({round(SETTLE_FILL / FRAME)} frames at 60 fps), confirm dwell {CONFIRM_DWELL} s, recheck dwell {RECHECK_DWELL} s, settle timeout {SETTLE_TIMEOUT} s, disabled / reacquire dwell {DISABLED_DWELL} s, acquisition cube half-width {F * ACQ_SCALE:g} m (= gate radius).',
         f'# bidirectional grip ({BIDIR}, off by default): four authored grip nodes, two per hand, and the grab takes the hold the prop\'s feature is nearer to at the read (feature direction {FEATURE_DIR} in the prop frame, {MARK_H} m out; hold radius {HOLD_R} m, margin |Near| > {HOLD_M}, an equivalent dead band of {dead_fraction(180.0) * 100:.0f}% of grab attitudes for an antipodal pair); read dwell {READ_DWELL:.4g} s, flip dwell {FLIP_DWELL:.4g} s; the wearer decides, two synced bits carry it, a remote holds its pre-grab attitude until they land.',
         'schema: 1', f'controller: {cfg["glueName"]}', 'basis: mount-root', 'role: fx', '',
         'defaults:', '  writeDefaults: on', '  transition: { duration: 0, exitTime: none, interruption: none }', '',
         'parameters:',
         f'  {ENABLE}: {{ type: bool, default: {"true" if cfg["enableDefault"] else "false"}, vrc: {{ synced: true, saved: false }} }}   # off is the reset',
         f'  {BIDIR}: {{ type: bool, default: false, vrc: {{ synced: false, saved: true }} }}   # the bidirectional mode, the second Toggle\'s: unsynced (a remote reads its default and waits for the bits instead), saved',
         '  GrabBone_IsGrabbed: bool     # minted by the grab physbone (parameter: GrabBone); never synced',
         '  IsLocal: bool                # VRC built-in',
         f'  {HAND}: {{ type: int, default: 0, scratch: true }}   # this document\'s own: the latched hand, driver-set on entry to LatchedR / LatchedL (1 / 2), 0 = none, read only by conditions; scratch because nothing outside the animator reads it',
         f'  {FLIP}: {{ type: float, default: 0.0, scratch: true }}   # this document\'s own: 1 = present the flipped grip, driver-set on entry to FlipP / FlipN (1) and Settled (0), read only by the carry blends; scratch because nothing outside the animator reads it',
         f'  {DECIDED}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # the wire: the wearer\'s copy has decided this grab (Carry, or Arrive with the mode off); cleared at Released and Disabled; every driver on it is localOnly',
         f'  {DOWN}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # the wire: the wearer\'s decision was the flipped grip, read only beside Decided; every driver on it is localOnly',
         '  # Readout names this document only reads or zeroes: declared scratch so readout.yaml alone emits them into a params asset.']
    for n, sp in glue_params().items(): L.append(param_line(n, sp))
    L += ['', 'layers:', f'  - name: {GLUE}Control', '    states:']
    for sname, st in glue_states(cfg).items():
        L.append(f'      {sname}:')
        if st.get('behaviours'):
            L.append('        behaviours:')
            for b in st['behaviours']:
                for kind, body in b.items(): L.append(f'          - {kind}: {emit_driver(body)}')
        if 'blend' in st:
            c0, c1 = st['blend']
            L += ['        motion:', '          tree: 1d', f'          param: {FLIP}', '          children:',
                  f'            - {{ clip: {c0}, threshold: 0.0 }}', f'            - {{ clip: {c1}, threshold: 1.0 }}']
        else:
            L.append(f'        motion: {{ clip: {st["clip"]} }}')
        L.append('        transitions:')
        for t in st['transitions']:
            fields = [f'to: {t["to"]}', f'when: [ {", ".join(t["when"])} ]']
            if 'exitTime' in t: fields.append(f'exitTime: {fmt(t["exitTime"])}')
            L.append(f'          - {{ {", ".join(fields)} }}')
    L += ['    default: Timer', '    layout:', '      nodes:']
    for n, xy in LAYOUT.items(): L.append(f'        {n}: [{xy[0]}, {xy[1]}]')
    L += ['      entry: [50, 120]', '      any:   [50, 40]', '      exit:  [50, 80]', '', 'clips:']
    for cn, c in glue_clips(cfg).items():
        L.append(f'  {cn}:')
        if 'length' in c: L.append(f'    length: {fmt(c["length"])}')
        L.append('    set:')
        for k, v in c['set'].items(): L.append(f'      "{k}": {fmt(v) if isinstance(v, float) else v}')
        if c.get('curves'):
            L.append('    curves:')
            for k, cv in c['curves'].items():
                keys = ', '.join(f'[{fmt(t) if isinstance(t, float) else t}, {fmt(v) if isinstance(v, float) else v}]' for t, v in cv['keys'])
                L.append(f'      "{k}": {{ tangents: {cv["tangents"]}, keys: [ {keys} ] }}')
    return '\n'.join(L) + '\n'

# ---------------- --check: the prefab's silent surface ----------------
def check():
    """Asserts what no compile or gate reads and whose breakage is silent at build. Writes nothing."""
    prefab = os.path.join(HERE, 'AbsoluteGripProp.prefab')
    if not os.path.exists(prefab): raise SystemExit(f'REFUSE: {prefab} missing')
    raw = open(prefab, encoding='utf-8').read()
    fails = []; seps = {}
    def a(cond, msg):
        if not cond: fails.append(msg)
    docs = re.findall(r'^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)', raw, re.M | re.S)
    def guid_of(meta):
        m = re.search(r'^guid: ([0-9a-f]{32})', open(os.path.join(HERE, meta), encoding='utf-8').read(), re.M); return m.group(1)
    g_glue = guid_of('built/AbsoluteGripProp_Fx.controller.meta'); g_read = guid_of('built/GripReadout_Fx.controller.meta')
    p_glue = guid_of('built/AbsoluteGripProp_Fx_Parameters.asset.meta'); p_read = guid_of('built/GripReadout_Fx_Parameters.asset.meta')
    # FullController: controllers and prms both glue-first (first-wins param merge, in each list); globalParams is the
    # derived wildcard for the one published prefix.
    fc = [b for _, _, b in docs if 'class: FullController' in b]
    a(len(fc) == 1, 'exactly one FullController')
    if fc:
        ctrl_guids = re.findall(r'controllers:.*?prms:', fc[0], re.S)[0]
        a([m for m in re.findall(r'guid: ([0-9a-f]{32})', ctrl_guids)] == [g_glue, g_read], 'controllers: [glue, readout] in that order, by GUID')
        prms = re.findall(r'prms:.*?globalParams:', fc[0], re.S)[0]
        a(re.findall(r'guid: ([0-9a-f]{32})', prms) == [p_glue, p_read], 'prms: [glue, readout] in that order, by GUID')
        gp = re.search(r'globalParams:\n((?:\s+- .*\n)*)', fc[0]); names = re.findall(r'- (\S+)', gp.group(1)) if gp else []
        a(names == [GLUE + '*'], f'globalParams == [{GLUE}*], got {names}')
        a('rootBindingsApplyToAvatar: 0' in fc[0], 'rootBindingsApplyToAvatar 0 (basis: mount-root)')
        a('Packages/com.ryan6vrc.patterns/' in fc[0] and 'Assets/' not in re.sub(r'id: [0-9a-f]{32}\|Packages[^\n]*', '', fc[0]), 'cached ids name the package, never a venue')
    # Identity map: component/transform fileID -> owning GameObject name, so every assert below names its node.
    names = {i: re.search(r'm_Name: (.*)', b).group(1) for t, i, b in docs if t == '1'}
    go_of = {i: m.group(1) for t, i, b in docs for m in [re.search(r'm_GameObject: \{fileID: (\d+)\}', b)] if m}
    def owner(i): return names.get(go_of.get(i))
    tf_of_go = {go_of[i]: i for t, i, b in docs if t == '4'}
    father = {i: m.group(1) for t, i, b in docs if t == '4' for m in [re.search(r'm_Father: \{fileID: (\d+)\}', b)] if m}
    def ancestors(go_id):
        """GameObject names from the parent upward."""
        out = []; tf = father.get(tf_of_go.get(go_id))
        while tf and tf != '0':
            out.append(owner(tf)); tf = father.get(tf)
        return out
    def go_id_of(node): return next((g for g, n in names.items() if n == node), None)
    def tf_doc(node): return next((b for t, i, b in docs if t == '4' and owner(i) == node), None)
    def vec3(b, key):
        m = re.search(rf'{key}: \{{x: ([-0-9.e]+), y: ([-0-9.e]+), z: ([-0-9.e]+)\}}', b) if b else None; return tuple(float(x) for x in m.groups()) if m else None
    def quat(b, key):
        m = re.search(rf'{key}: \{{x: ([-0-9.e]+), y: ([-0-9.e]+), z: ([-0-9.e]+), w: ([-0-9.e]+)\}}', b) if b else None; return tuple(float(x) for x in m.groups()) if m else None
    def near(u, v, tol=1e-6): return u is not None and v is not None and all(abs(x - y) < tol for x, y in zip(u, v))
    def sources(b):
        """[(source name or 'guid:<guid>', weight)] over the non-empty slots, in slot order."""
        out = []
        for m in re.finditer(r'SourceTransform: \{fileID: (\d+)(?:, guid: ([0-9a-f]{32}))?[^}]*\}\n\s+Weight: ([-0-9.e]+)', b):
            if m.group(1) == '0': continue
            out.append((f'guid:{m.group(2)}' if m.group(2) else owner(m.group(1)), float(m.group(3))))
        return out
    # Receivers: twelve, one per parameter, each writing the parameter its own name says, self+others, not local-only,
    # content type Avatar, and every host under Cage so the physbone's one ignore entry covers them all.
    recv = [(i, b) for _, i, b in docs if 'collisionTags' in b and 'receiverType' in b]
    want_recv = sorted(READINGS + GATES + CUES + HOLDS)
    a(sorted(owner(i) or '' for i, _ in recv) == want_recv, f'receivers named exactly {want_recv}, got {sorted(owner(i) or "" for i, _ in recv)}')
    a(len(recv) == 16, f'receiver count == 16 (the performance tier turns on it), got {len(recv)}')
    # The hold receivers: Proximity, self-only and local-only (the Mark is the wearer's own sender and the decision is the wearer's
    # alone), each on a host at Frame's origin so the grip node's trim never enters the reading, each carrying its shape MARK_H out
    # along the host's own feature direction, where the Mark lands when the prop is presented in that hold. They are never toggled
    # and never animated: a Proximity receiver bounced with its sender still inside comes back deaf for the session
    # (runtime.md SContacts), and this sender can never leave them, so the mode Toggle bounces the sender (MarkProxy) instead,
    # which is a fresh acquisition every time. That is the argument the deleted Constant mark boxes rested on, inverted.
    for i, b in recv:
        node = owner(i) or ''
        a(re.search(r'^  parameter: (.*)$', b, re.M).group(1) == P(node), f'receiver {node} writes {P(node)}')
        a('contentTypes: 1' in b, f'receiver {node} contentTypes Avatar')
        a('Cage' in ancestors(go_of[i]), f'receiver {node} sits under Cage (the physbone ignore entry)')
        if node in HOLDS:
            a('allowSelf: 1' in b and 'allowOthers: 0' in b, f'receiver {node} allowSelf 1 allowOthers 0 (the Mark is the wearer\'s own sender)')
            a('localOnly: 1' in b, f'receiver {node} localOnly 1 (the decision is the wearer\'s alone)')
            a('receiverType: 2' in b, f'receiver {node} proximity (the reading is a distance, and the differential of two is the decision)')
            a(re.search(rf'collisionTags:\n\s+- {MARK_TAG}\n(?!\s+- )', b), f'receiver {node} tag exactly [{MARK_TAG}]')
            a('shapeType: 0' in b and re.search(rf'^  radius: {HOLD_R:g}\n', b, re.M), f'receiver {node} sphere of radius {HOLD_R:g} (HOLD_R > 2*MARK_H, so neither reading clamps)')
            a(near(vec3(b, 'position'), tuple(c * MARK_H for c in FEATURE_DIR), 1e-6), f'receiver {node} shape at FEATURE_DIR * MARK_H {tuple(c * MARK_H for c in FEATURE_DIR)}')
            go = go_of[i]
            a(ancestors(go)[:1] == ['Frame'], f'{node} hosted on Frame (the sensed hand frame)')
            a(names.get(go) == node and re.search(r'^  m_IsActive: 1$', [bb for t, ii, bb in docs if t == '1' and ii == go][0], re.M), f'{node} host GameObject active (the hold receivers are never toggled)')
            tb = tf_doc(node)
            a(near(vec3(tb, 'm_LocalPosition'), (0, 0, 0)), f'{node} host at Frame\'s origin (the tip, so no grip trim enters the reading)')
            a(near(vec3(tb, 'm_LocalScale'), (1, 1, 1)), f'{node} host local scale 1 (whether a receiver shape offset scales with lossy scale is undistinguished on disk; scale 1 makes it moot)')
            hc = [bb for _, ii, bb in docs if 'RotationAtRest' in bb and 'AimVector' not in bb and owner(ii) == node]
            a(len(hc) == 1, f'{node} carries one rotation constraint')
            if hc:
                want_grip = 'Grip' + node[len('Hold'):]
                a(sources(hc[0]) == [(want_grip, 1.0)], f'{node} rotation constraint sources exactly {want_grip} at weight 1, got {sources(hc[0])}')
                a('RotationAtRest: {x: 0, y: 0, z: 0}' in hc[0] and all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'ParentRotationOffset: (\{[^}]*\})', hc[0])), f'{node} rotation constraint zeroed, source offset zero')
                a(re.search(r'^  Locked: 1$', hc[0], re.M) and re.search(r'^  IsActive: 1$', hc[0], re.M), f'{node} rotation constraint locked and active (it must track a grip node the author moves)')
            continue
        a('allowSelf: 1' in b and 'allowOthers: 1' in b, f'receiver {node} allowSelf 1 allowOthers 1 (serialized open)')
        a('localOnly: 0' in b, f'receiver {node} localOnly 0 (remotes re-derive)')
        a('receiverType: 2' in b, f'receiver {node} proximity')
        if node in READINGS:
            a(re.search(r'collisionTags:\n\s+- Hand\n(?!\s+- )', b), f'receiver {node} tag exactly [Hand]')
            a('shapeType: 2' in b and 'useFaceProximity: 1' in b, f'receiver {node} box / face mode')
            a(re.search(rf'^  size: \{{x: {2*F:g}, y: {2*F:g}, z: {D:g}\}}', b, re.M), f'receiver {node} size ({2*F:g}, {2*F:g}, {D:g})')
        else:
            tagw = 'FingerIndex' if node in CUES else node
            a(re.search(rf'collisionTags:\n\s+- {tagw}\n(?!\s+- )', b), f'receiver {node} tag exactly [{tagw}]')
            a('shapeType: 0' in b, f'receiver {node} sphere')
            R = CUE_R if node in CUES else GATE_R
            a(re.search(rf'^  radius: {R:g}\n', b, re.M), f'receiver {node} radius {R:g}')
            a('position: {x: 0, y: 0, z: 0}' in b, f'receiver {node} zero shape offset')
            tb = tf_doc(node)
            a(near(vec3(tb, 'm_LocalPosition'), (0, 0, 0)), f'{node} host local position zero (the readout AAPs own the proxies; the gate is the tip)')
            if node in CUES:
                a(near(vec3(tb, 'm_LocalScale'), (1, 1, 1)), f'{node} host serialized at local scale 1; the readout\'s CueScale tree owns it in play (config, CueScale), so the serialized value is the survey-scale radius')
            else:
                a(near(vec3(tb, 'm_LocalScale'), (1, 1, 1)), f'{node} host local scale 1, never animated')
            want_parent = {'CueP': 'ProxyA', 'CueN': 'ProxyB'}.get(node, 'Cage')
            a(ancestors(go_of[i])[:1] == [want_parent], f'{node} hosted on {want_parent}')
    # Box hosts: serialized at the working rotation (the clips animate identity between grabs) and the acquisition scale.
    for r in READINGS:
        tb = tf_doc(r)
        a(near(quat(tb, 'm_LocalRotation'), unity_euler_quat(HOST_EULER[r]), 1e-5) or near(quat(tb, 'm_LocalRotation'), tuple(-c for c in unity_euler_quat(HOST_EULER[r])), 1e-5), f'{r} host localRotation == HOST_EULER (local +Z along its tetrahedral direction)')
        a(near(vec3(tb, 'm_LocalScale'), (ACQ_SCALE,) * 3), f'{r} host serialized at the acquisition scale {ACQ_SCALE:g}')
    # The cue radius in play is CUE_R * lossyScale(CueP) * CueScale, so every node between the world-pinned Cage and a cue
    # host must be unit scale or the cue rule silently reads a different radius than the tree wrote. A scale on any of
    # these is invisible in a committed prefab and breaks nothing else.
    for node in ['FreezeRotation', 'Cage', 'Mid', 'ProxyA', 'ProxyB']:
        a(near(vec3(tf_doc(node), 'm_LocalScale'), (1, 1, 1)), f'{node} local scale 1 (the cue radius in play is CUE_R x lossyScale(CueP) x CueScale, and only CueScale may move it)')
    # Every VRC constraint's source list is sixteen keyable slots behind a totalLength. The editor solves the filled slots; the client
    # solves totalLength of them, so a slot filled past the length is a source that works in play mode and is a no-op in-game
    # (measured: a fourth source the left carry weighted moved nothing in the client until the length was 4).
    for t, i, b in docs:
        if t != '114' or 'FreezeToWorld:' not in b: continue    # every VRC constraint carries FreezeToWorld
        m = re.search(r'^    totalLength: (\d+)$', b, re.M)
        a(m is not None, f'{owner(i)} constraint carries no Sources.totalLength')
        if not m: continue
        filled = [int(k) for k in re.findall(r'source(\d+):\n\s+SourceTransform: \{fileID: (?!0\})', b)]
        a(filled == list(range(int(m.group(1)))), f'{owner(i)} constraint totalLength {m.group(1)} but filled slots {filled} (the client solves exactly the first totalLength slots)')
    # The placement smoother: Damped eases its origin toward the tip at home and toward the latched hand's grip node in carry.
    # Frame's origin is the tip: its rotation is the sensed hand frame, its position the client's grab point, so a grip node's
    # local position trims from the grab point (the same in both hands) and never from the sensed midpoint (per-hand capsule error).
    a(ancestors(go_id_of('Frame'))[:1] == ['Cage'], 'Frame is a child of Cage (its origin is the tip)')
    a(near(vec3(tf_doc('Frame'), 'm_LocalPosition'), (0, 0, 0)), 'Frame local position zero')
    pc = [b for _, i, b in docs if 'PositionAtRest' in b and owner(i) == 'Damped']
    a(len(pc) == 1, 'Damped carries one position constraint')
    if pc:
        want_dmp = ['Damped', 'Container'] + ['Grip' + g for g in GRIPS]
        a([s for s, _ in sources(pc[0])] == want_dmp, f'Damped position sources {want_dmp}, got {[s for s, _ in sources(pc[0])]}')
        a([w for _, w in sources(pc[0])] == [1.0, SMOOTH_W] + [0.0] * len(GRIPS), f'Damped position weights [1, {SMOOTH_W:g}, 0, 0, 0, 0] (self, home, then the four grip nodes) at rest')
        a('PositionAtRest: {x: 0, y: 0, z: 0}' in pc[0] and 'PositionOffset: {x: 0, y: 0, z: 0}' in pc[0], 'Damped position constraint zeroed, no offset')
        a(all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'ParentPositionOffset: (\{[^}]*\})', pc[0])), 'Damped position source offsets zero')
    # Physbone: the grab premise. With snapToHand the tip IS the client's hand grab point.
    pb = [b for _, _, b in docs if 'snapToHand' in b]
    a(len(pb) == 1, 'one physbone')
    if pb:
        b = pb[0]
        a('snapToHand: 1' in b, 'snapToHand 1 (the tip is the client hand grab point; the whole entry rests on it)')
        a('allowGrabbing: 1' in b, 'allowGrabbing')
        a(re.search(r'grabFilter:\n\s+allowSelf: 1\n\s+allowOthers: 1', b), 'grabFilter self+others')
        a(re.search(rf'^  radius: {GRAB_RADIUS:g}\n', b, re.M), f'grab radius {GRAB_RADIUS:g}')
        a('parameter: GrabBone' in b, 'physbone parameter GrabBone')
        for k, v in (('pull', 1), ('spring', 0), ('stiffness', 0.2), ('grabMovement', 1)):
            a(re.search(rf'^  {k}: {v:g}\n', b, re.M), f'physbone {k} {v:g} (grab-prop\'s dynamics; the tip\'s rigidity in the hand is now the roll)')
        ign = re.search(r'ignoreTransforms:\n((?:\s+- .*\n)+)', b)
        got = sorted(owner(x) or x for x in re.findall(r'fileID: (\d+)', ign.group(1))) if ign else []
        a(got == ['FreezeRotation'], f'ignoreTransforms == [FreezeRotation] (its subtree, DropPosition and Cage included, leaves the chain, and no zero-length node trails GrabBone_End), got {got}')
    a(near(vec3(tf_doc('GrabBone_End'), 'm_LocalPosition'), BONE_END), f'GrabBone_End local position {BONE_END}')
    # The cage tilt: cube diagonal to vertical (Quaternion.FromToRotation((1,1,1)/sqrt3, up)); a world-aligned cage
    # would make palm-down yaw a persistent two-line ambiguity (README SLimits).
    cage_tf = tf_doc('Cage')
    a(cage_tf is not None, 'one GameObject named Cage')
    a(near(quat(cage_tf, 'm_LocalRotation'), (-0.32505758, 0.0, 0.32505758, 0.88807383), 1e-3), 'Cage localRotation = cube-diagonal-up tilt')
    # The scale pin: Cage's scale constraint sources assets/World.prefab (never instantiated) at unit offset.
    g_world = guid_of('assets/World.prefab.meta')
    scale = [b for _, i, b in docs if 'ScaleAtRest' in b and owner(i) == 'Cage']
    a(len(scale) == 1 and [s for s, _ in sources(scale[0])] == [f'guid:{g_world}'] and 'ScaleOffset: {x: 1, y: 1, z: 1}' in scale[0],
      'Cage scale constraint sources assets/World.prefab alone at unit offset')
    # The mark rig: MarkProxy at the tip copies Damped's attitude (a translation-immune copy of the prop's pose, frozen through
    # acquisition), Mark stands MARK_H along the feature direction in that frame, and the sender is the wearer's own (localOnly).
    a(ancestors(go_id_of('MarkProxy'))[:1] == ['Cage'] and near(vec3(tf_doc('MarkProxy'), 'm_LocalPosition'), (0, 0, 0)), 'MarkProxy is a child of Cage at its origin (the tip)')
    snd = [b for _, i, b in docs if 'collisionTags' in b and 'receiverType' not in b and owner(i) == 'Mark']
    a(len(snd) == 1, 'one contact sender named Mark')
    if snd:
        a('shapeType: 0' in snd[0] and re.search(rf'^  radius: {MARK_R:g}\n', snd[0], re.M) and 'localOnly: 1' in snd[0], f'Mark is a localOnly sphere sender of radius {MARK_R:g}')
        a(re.search(rf'collisionTags:\n\s+- {MARK_TAG}\n(?!\s+- )', snd[0]), f'Mark tag exactly [{MARK_TAG}]')
        a(ancestors(go_id_of('Mark'))[:1] == ['MarkProxy'], 'Mark is a child of MarkProxy')
        a(near(vec3(tf_doc('Mark'), 'm_LocalPosition'), tuple(c * MARK_H for c in FEATURE_DIR), 1e-6), f'Mark local position == FEATURE_DIR * MARK_H {tuple(c * MARK_H for c in FEATURE_DIR)} (the same offset every hold receiver carries)')
    # The rotation channel: exact sources per node, zeroed (never activated) with identity source offsets, or the
    # authored grip lands wrong by the offset.
    for node, want_src in (('Rotor', ['Offset'] + ['Grip' + g for g in GRIPS]), ('Frame', ['Recon', 'ReconN']), ('Damped', ['Damped', 'Rotor']), ('MarkProxy', ['Damped'])):
        rc = [b for _, i, b in docs if 'RotationAtRest' in b and 'AimVector' not in b and owner(i) == node]
        a(len(rc) == 1, f'{node} carries one rotation constraint')
        if rc:
            a([s for s, _ in sources(rc[0])] == want_src, f'{node} sources {want_src}, got {[s for s, _ in sources(rc[0])]}')
            a('RotationAtRest: {x: 0, y: 0, z: 0}' in rc[0], f'{node} RotationAtRest zero (Zero, never Activate)')
            a(all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'ParentRotationOffset: (\{[^}]*\})', rc[0])), f'{node} source rotation offsets zero')
    # The sign mux: two aim constraints, +Z at ProxyA / ProxyB, both ObjectRotationUp against UpAim (ObjectUp
    # silently degenerates to world-up; object-sync SRig owns that measurement).
    for node, src, up in (('Recon', 'ProxyA', 1), ('ReconN', 'ProxyB', 1)):
        ac = [b for _, i, b in docs if 'AimAxis' in b and owner(i) == node]
        a(len(ac) == 1, f'{node} carries one aim constraint')
        if ac:
            a([s for s, _ in sources(ac[0])] == [src], f'{node} aims at {src}, got {[s for s, _ in sources(ac[0])]}')
            a('AimAxis: {x: 0, y: 0, z: 1}' in ac[0] and f'UpAxis: {{x: 0, y: {up}, z: 0}}' in ac[0], f'{node} AimAxis +Z, UpAxis {"+" if up > 0 else "-"}Y')
            a(ancestors(go_id_of(node))[:1] == ['UpAim'], f'{node} sits under UpAim (one solve group with its up helper)')
            m = re.search(r'WorldUpTransform: \{fileID: (\d+)\}', ac[0])
            a('WorldUp: 2' in ac[0] and m and owner(m.group(1)) == 'UpAim', f'{node} up mode ObjectRotationUp against UpAim')
    # The four authored holds: the single most silent surface in the entry, and the one thing here no constant pins a value for.
    # Each is a bare transform under Frame -- rotation is the hold, local position the trim off the grab point -- so the author
    # drags and turns it in the scene and nothing else in the rig moves. A constraint on one would make it derived.
    grips = {}
    for node in ['Grip' + g for g in GRIPS]:
        tb = tf_doc(node)
        a(tb is not None, f'node {node} exists')
        if tb:
            a(ancestors(go_id_of(node))[:1] == ['Frame'], f'{node} is a child of Frame')
            a(not any(('RotationAtRest' in b or 'AimAxis' in b or 'PositionAtRest' in b) and owner(i) == node for _, i, b in docs), f'{node} carries no constraint')
            grips[node] = quat(tb, 'm_LocalRotation')
    # The one author-side constraint: a hand's two holds must separate the fixed feature direction enough for the nearer-hold
    # read to be a decision. The same function runs on a composition's nested instance and in a venue.
    for h in 'RL':
        q, qf = grips.get('Grip' + h), grips.get('Grip' + h + 'F')
        if q and qf:
            theta, dead = hold_separation(q, qf)
            a(hold_refusal(theta) is None, f'{h}: {hold_refusal(theta)}')
            seps[h] = (theta, dead)
    # The jig: the authoring surface for the four holds. Each hand stand-in STANDIN[X] under EditorOnly/Jig/PropFrame is a bare
    # transform, the hand's pose in the parked prop's frame (PropFrame rides Damped); its child Grip carries two parent
    # constraints, one world-space onto PropFrame (so its local pose is the hand's inverse, the hold) and one local-space with
    # TargetTransform = Frame/Grip{X} (so the bare grip node's local pose is written from it). Nothing here runs at build: the
    # EditorOnly root is tagged EditorOnly, and VRCFury destroys that subtree before any feature runs, so no VRCFury component
    # may live under it (one there is dead, and the inspector says so). What is silent is a grip node whose serialized value is
    # not its hand's inverse: the edit-mode solver was dead when the prefab was saved (unity.md SSharp edges), so pin the
    # relation, and PropFrame's own saved pose at Damped's (the same dead solver leaves it at the origin, the stand-ins drawn
    # nowhere near the prop).
    def path_of(go):
        return '/'.join(list(reversed(ancestors(go)[:-1])) + [names[go]]) if names.get(go) else None
    by_path = {path_of(g): g for g in names if path_of(g)}
    def go_at(path): return by_path.get(path)
    def tf_id_at(path):
        g = go_at(path); return next((i for t, i, b in docs if t == '4' and go_of.get(i) == g), None) if g else None
    def tf_at(path):
        i = tf_id_at(path); return next((b for t, j, b in docs if t == '4' and j == i), None) if i else None
    def world_pose(path):
        """(rotation, position) of a node from the serialized chain, root first; every scale on the way is pinned unit."""
        q, p = (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
        for k in range(1, path.count('/') + 2):
            b = tf_at('/'.join(path.split('/')[:k]))
            if b is None: return None, None
            a(near(vec3(b, 'm_LocalScale'), (1.0, 1.0, 1.0)), f"{'/'.join(path.split('/')[:k])} at unit scale (world_pose folds no scale)")
            p = tuple(x + y for x, y in zip(p, rot_vec(q, vec3(b, 'm_LocalPosition')))); q = qmul(q, quat(b, 'm_LocalRotation'))
        return q, p
    def constraints_of(go): return [(i, b) for t, i, b in docs if t == '114' and 'FreezeToWorld:' in b and go_of.get(i) == go]
    eo = go_at('EditorOnly'); eo_doc = next((b for t, i, b in docs if t == '1' and i == eo), '')
    a(re.search(r'^  m_TagString: EditorOnly$', eo_doc, re.M) is not None, 'EditorOnly is tagged EditorOnly (the build strips the jig and its stand-in renderers)')
    JIG = 'EditorOnly/Jig/PropFrame'
    pfc = constraints_of(go_at(JIG)) if go_at(JIG) else []
    a(len(pfc) == 1 and 'ParentPositionOffset' in pfc[0][1] and sources(pfc[0][1]) == [('Damped', 1.0)], f'{JIG} carries one parent constraint sourcing exactly Damped at weight 1 (the parked prop frame)')
    for _, b in pfc:
        a(re.search(r'^  Locked: 1$', b, re.M) and re.search(r'^  IsActive: 1$', b, re.M) and 'SolveInLocalSpace: 0' in b and 'FreezeToWorld: 0' in b and 'TargetTransform: {fileID: 0}' in b, f'{JIG} constraint locked, active, world-space, not frozen, on itself')
        a('PositionAtRest: {x: 0, y: 0, z: 0}' in b and 'RotationAtRest: {x: 0, y: 0, z: 0}' in b and all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'Parent(?:Position|Rotation)Offset: (\{[^}]*\})', b)), f'{JIG} constraint zeroed with zero source offsets')
    jq, jp = world_pose(JIG); dq, dp = world_pose('Container/Damped')
    a(same_rot(jq, dq) and near(jp, dp, 1e-5), f"{JIG} is saved at Damped's world pose (the solve's own output; at the origin the stand-ins are drawn nowhere near the prop), got {jp} vs {dp}")
    grip_tf_id = {node: next((i for t, i, b in docs if t == '4' and owner(i) == node), None) for node in ['Grip' + g for g in GRIPS]}
    for g in GRIPS:
        hand = f'{JIG}/{STANDIN[g]}'; hb = tf_at(hand); inv = f'{hand}/Grip'; ib = tf_at(inv)
        a(hb is not None and ib is not None, f'{hand} and {inv} exist')
        if hb is None or ib is None: continue
        a(not constraints_of(go_at(hand)), f'{hand} carries no constraint (it is the authored hold; a constraint would make it derived)')
        ic = constraints_of(go_at(inv))
        a(len(ic) == 2 and all('ParentPositionOffset' in b for _, b in ic), f'{inv} carries exactly two parent constraints')
        world = [b for _, b in ic if 'SolveInLocalSpace: 0' in b]; local = [b for _, b in ic if 'SolveInLocalSpace: 1' in b]
        a(len(world) == 1 and sources(world[0]) == [('PropFrame', 1.0)] and 'TargetTransform: {fileID: 0}' in world[0], f"{inv}: one world-space parent constraint sourcing exactly PropFrame at weight 1 on itself (its local pose is then the hand's inverse)")
        a(len(local) == 1 and len(sources(local[0])) == 1 and re.search(rf'SourceTransform: \{{fileID: {tf_id_at(inv)}\}}\n\s+Weight: 1$', local[0], re.M) is not None and f'TargetTransform: {{fileID: {grip_tf_id["Grip" + g]}}}' in local[0], f'{inv}: one local-space parent constraint sourcing itself (by fileID: four nodes share the name Grip) at weight 1 with TargetTransform = Frame/Grip{g} (the grip node is written from it)')
        for _, b in ic:
            a(re.search(r'^  Locked: 1$', b, re.M) and re.search(r'^  IsActive: 1$', b, re.M) and 'FreezeToWorld: 0' in b, f'{inv} constraints locked, active, not frozen')
            a('PositionAtRest: {x: 0, y: 0, z: 0}' in b and 'RotationAtRest: {x: 0, y: 0, z: 0}' in b and all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'Parent(?:Position|Rotation)Offset: (\{[^}]*\})', b)), f'{inv} constraints zeroed with zero source offsets')
        hq, hp = quat(hb, 'm_LocalRotation'), vec3(hb, 'm_LocalPosition'); gq, gp = grips.get('Grip' + g), vec3(tf_doc('Grip' + g), 'm_LocalPosition')
        if hq and hp and gq and gp:
            want_q = qinv(hq); want_p = rot_vec(want_q, tuple(-c for c in hp))
            a(same_rot(quat(ib, 'm_LocalRotation'), gq) and near(vec3(ib, 'm_LocalPosition'), gp, 1e-5), f"{inv} serialized at its grip node's pose (the solve's own output, saved with it)")
            a(same_rot(gq, want_q) and near(gp, want_p, 1e-5), f'Frame/Grip{g} == inverse of {hand} (rotation and trim): the grip node is materialized from the hand by the jig, and a mismatch means the prefab was saved with the edit-mode solver dead; re-register it (README SInterface, its last line) and save again')
    # The placeholder demonstrates the feature direction: its head lies along prop-frame +Z, so the mode decides head-up against
    # head-down. Damped is the prop frame (PropFrame rides it), so Payload must not turn under it; its offset is free.
    a(same_rot(quat(tf_at('Container/Damped/Payload'), 'm_LocalRotation'), (0.0, 0.0, 0.0, 1.0)), 'placeholder Payload unrotated under Damped (else Shaft/Head +Z is not prop-frame +Z)')
    for prim in ('Shaft', 'Head'):
        pb = tf_at(f'Container/Damped/Payload/{prim}'); pp = vec3(pb, 'm_LocalPosition') if pb else None
        a(pp is not None and abs(pp[0]) < 1e-6 and abs(pp[1]) < 1e-6 and pp[2] > 0, f'placeholder {prim} lies along prop-frame +Z (the feature direction), got {pp}')
    # The hand-maintained seam pieces no compile reads: the Toggle's global parameter is the one published name (a rename
    # strands the menu with no error), the home BoneProxy targets Hips, and Damped's smoother weights are the entry's own.
    # Two bare Toggles, an exception to the one-bare-Toggle rule (CONVENTIONS.md) the two-instance collision already binding this
    # module makes cheap: the enable, and the mode, whose object action is the mark rig's hygiene (off, the receivers cost no frame time).
    tg = [b for _, _, b in docs if 'class: Toggle' in b and 'ns: VF.Model.Feature' in b]
    a(len(tg) == 2, f'exactly two VRCFury Toggles (the enable and the mode), got {len(tg)}')
    en = [b for b in tg if re.search(rf'^\s+globalParam: {re.escape(ENABLE)}$', b, re.M)]
    bi = [b for b in tg if re.search(rf'^\s+globalParam: {re.escape(BIDIR)}$', b, re.M)]
    a(len(en) == 1 and len(bi) == 1, f'one Toggle drives {ENABLE} and one drives {BIDIR}')
    if en:
        a(re.search(r'^\s+useGlobalParam: 1$', en[0], re.M), f'enable Toggle drives the global {ENABLE}')
        on = 1 if CONFIG['enableDefault'] else 0
        a(re.search(r'^\s+saved: 0$', en[0], re.M) and re.search(rf'^\s+defaultOn: {on}$', en[0], re.M), f'enable Toggle unsaved (off is the reset), defaultOn {on} == enableDefault')
        a('ObjectToggleAction' not in en[0], 'enable Toggle carries no object action')
    if bi:
        a(re.search(r'^\s+useGlobalParam: 1$', bi[0], re.M), f'mode Toggle drives the global {BIDIR}')
        a(re.search(r'^\s+saved: 1$', bi[0], re.M) and re.search(r'^\s+defaultOn: 0$', bi[0], re.M), 'mode Toggle saved, default off (the shipped default behaviour is the authored grip)')
        acts = re.findall(r'ObjectToggleAction.*?obj: \{fileID: (\d+)\}\n\s+mode: (\d+)', bi[0], re.S)
        a([names.get(o, o) for o, _ in acts] == ['MarkProxy'] and all(m == '0' for _, m in acts), f'mode Toggle turns on exactly MarkProxy, the sender (the hold receivers are always on, and bouncing one with its sender inside would deafen it), got {[(names.get(o, o), m) for o, m in acts]}')
    bp = [b for _, i, b in docs if 'boneReference' in b and owner(i) == 'HomeAnchor']
    a(len(bp) == 1 and re.search(r'^\s+boneReference: 0$', bp[0], re.M), 'HomeAnchor BoneProxy targets Hips')
    dm = [b for _, i, b in docs if 'RotationAtRest' in b and 'AimVector' not in b and owner(i) == 'Damped']
    a(dm and [w for _, w in sources(dm[0])] == [1.0, SMOOTH_W], f'Damped source weights [1, {SMOOTH_W:g}] (self, Rotor), got {[w for _, w in sources(dm[0])] if dm else None}')
    # Absence: a leftover from the copied prefab writes the same transform and wins silently.
    for gone in ('Held', 'ReconW', 'ReconU', 'ReconNU', 'MarkZp', 'MarkZm', 'MarkXp', 'MarkXm'):
        a(gone not in names.values(), f'no node named {gone}')
        a(not any(gone in [s for s, _ in sources(b)] for _, _, b in docs if 'SourceTransform' in b), f'no constraint sources {gone}')
    if fails:
        print('\n'.join('FAIL: ' + f for f in fails)); raise SystemExit(1)
    print(f'ok: prefab surface holds ({len(recv)} receivers; hold separation ' + ', '.join(f'{h} {t:.1f} deg, {d * 100:.0f}% dead band' for h, (t, d) in seps.items()) + ')')

if __name__ == '__main__':
    if '--check' in sys.argv: check(); sys.exit(0)
    text = emit_readout(); open(OUT_READOUT, 'w', newline='\n').write(text)
    nstates = len(states); ntrans = sum(len(s['transitions']) for s in states.values())
    def count_leaves(m): return sum(count_leaves(c) if 'tree' in c else 1 for c in m['children'])
    leaves = count_leaves(math_layer['states']['Math (WD ON)']['motion']) + sum(count_leaves(s['motion']) for s in states.values())
    print(f'wrote {OUT_READOUT}: {len(params)} params, {len(clips)} clips, {nstates + 1} states, {ntrans} transitions, {leaves} tree leaves, {len(text.splitlines())} lines')
    out = os.path.join(HERE, 'controller.yaml')
    glue = emit_glue(CONFIG); open(out, 'w', newline='\n').write(glue)
    print(f'wrote {out}: {len(glue_clips(CONFIG))} clips, {len(glue_states(CONFIG))} states, {len(glue.splitlines())} lines')
