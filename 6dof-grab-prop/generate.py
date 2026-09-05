#!/usr/bin/env python3
"""6dof-grab-prop generator: emits the two controller documents beside this file.

    python 6dof-grab-prop/generate.py           # writes readout.yaml and controller.yaml
    python 6dof-grab-prop/generate.py --check   # asserts the prefab's silent surface, writes nothing

readout.yaml (PalmReadout_Fx) is the palm-orientation readout: eight face-box readings of the grabber's built-in
Hand palm-capsule sender -> capsule half-length s (half the overall length, caps included: at k = 0.5 the axis
segment and the two caps each span s), the capsule midpoint, a held ORIENTED sign pattern whose tree
writes the signed palm axis, and the roll-lever gate. Mechanism and the measurements behind every constant:
README.md. controller.yaml (SixDofGrabProp_Fx) is the glue: grab-prop's cell (its clip table replicated binding
for binding) plus the cage latch, the relative capture and the roll-mode select.

Arithmetic conventions (the schema's clamp rule: a Direct weight is clamped >= 0, so every sign lives in a clip
constant; signed values are only ever read through a 1D tree's blend parameter or a transition condition):
  R_j+/-  face readings of the opposed pair along tetrahedral direction d_j (reading = 1 - d_surface / D)
  E_j   = D(R_j+ + R_j-) - 2(D - F)              extent along d_j, metres
  m_j   = (R_j+ - R_j-) D / 2                     midpoint projection on d_j;  Mid = 3/4 sum_j m_j d_j
  s     = (SumE - sqrt(SumE^2 - qa*SumE2)) / qa   qa = 16k^2 - 4/3 = 8/3 at k = r/s = 0.5; sqrt by a 1D lookup
  S_L   = sum_j sigma_j (E_j - s)                  consistency residual of line L (the directions sum to 0)
  axis  = sum_j sigma_j (E_j - s) d_j              the held oriented pattern's vector, |axis| = 4/3 s
  Lever = |Mid|^2 |axis|^2 - (Mid.axis)^2 - t^2 |axis|^2   > 0  <=>  tip-to-axis distance > t (tip = cage origin)

Hop structure (one frame per AAP hop, runtime.md SAnimator evaluation):
  frame n  : E_j, SumE, Mid, G_k, S_L, O_P and the active state's P_k / T / axis from readings(n) and S(n-1)
  frame n+1: Disc; D_ab = |S_a| - |S_b|; SumE_d1; the positive/negative halves of Mid and axis
  frame n+2: SqrtDisc = lut(Disc); SumE_d2; |Mid|^2, Mid.axis, |axis|^2 from the halves
  frame n+3: S = 3/8 (SumE_d2 - SqrtDisc); halves of Mid.axis
  frame n+4: Lever
The lever's lag is irrelevant: it is a per-grab constant (tip and palm are both rigid in the grabbing hand) and
is read once, at the Settling exit.
"""
import itertools, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_READOUT = os.path.join(HERE, 'readout.yaml')
OUT_GLUE = os.path.join(HERE, 'controller.yaml')

# ---------------- config ----------------
# Box geometry at WORKING scale (host localScale 1). F = +Z face plane from the box centre, D = depth; the box is
# (2F, 2F, D) full extents. Larger than P8c's 0.15/0.3 so a remote client's IK-lagged hand sender, which trails
# the synced grab point during motion, stays inside every box's linear range. Any change regenerates everything.
F, D = 0.75, 1.5
K = 0.5                               # r/s on every VRChat Automatic base
QA = 16 * K * K - 4 / 3               # 8/3
MARGIN = 0.0004                       # keep-previous hysteresis in |S_L| metres
LUT_LO, LUT_HI, LUT_N = 0.0012, 0.03, 24  # sqrt lookup over Disc (m^2); must cover Disc over the whole S band (refused below)
LEVER_T = 0.02                        # roll-lever threshold, metres: below it roll falls back to world-up
ACQ_SCALE = 0.12                      # receiver host scale between grabs; the smallest whose guaranteed core covers the grab geometry (README)
RES_SETTLE = 0.002                    # |S_held| below this = the eight boxes agree on one capsule
S_LO, S_HI = 0.012, 0.045             # palm-plausible half-length band (surveyed bases: s ~ 19..32 mm)
SETTLE_TIMEOUT = 1.0                  # seconds after the latch before the loop reopens (Settling + Following + Settled)
CAPTURE_DWELL = 0.25                  # seconds after the latch before a capture may fire (Settling + Following)
SETTLE_FILL = 0.1                     # seconds the prop stays frozen after the latch while the readout pipeline primes; then it rides the frame
DISABLED_DWELL = 0.25                 # seconds the receiver GOs stay off in Disabled (a one-frame bounce deafens them)
FRAME = 0.016666668
PREFIX = 'Palm/'
GLUE = 'SixDofGrabProp/'
MOUNT = 'GrabPosition/GrabBone/GrabBone_End/FreezeRotation/Cage'
GRAB_RADIUS = 0.03                    # physbone grab radius; with BONE_END it sizes the acquisition core (README)
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
def tag(sg): return ''.join('p' if x > 0 else 'm' for x in sg)
def line_of(sg): return sg if sg[0] == 1 else tuple(-x for x in sg)
def flipset(sg, ks): return tuple(sg[j] * (-1 if j in ks else 1) for j in range(4))
def hamming(a, b): return sum(x != y for x, y in zip(a, b))
def P(n): return PREFIX + n
def fmt(x):
    s = f'{x:.8g}'
    return s if ('.' in s or 'e' in s) else s + '.0'

# Scene bindings riding the readout's leaf clips: the aim pair reads these the frame they are written.
BIND = {P('MidX'): f'{MOUNT}/Mid/Transform.m_LocalPosition.x', P('MidY'): f'{MOUNT}/Mid/Transform.m_LocalPosition.y',
        P('MidZ'): f'{MOUNT}/Mid/Transform.m_LocalPosition.z',
        P('AxisX'): f'{MOUNT}/Mid/ProxyA/Transform.m_LocalPosition.x', P('AxisY'): f'{MOUNT}/Mid/ProxyA/Transform.m_LocalPosition.y',
        P('AxisZ'): f'{MOUNT}/Mid/ProxyA/Transform.m_LocalPosition.z'}

# ---------------- parameter + clip registry (readout document) ----------------
params = {}     # name -> spec dict
clips = {}      # clipname -> (param, value)
def param(name, spec): params[name] = spec
def clip_for(aap, value):
    """one clip per (aap, value); the clip writes the AAP as a parameter curve (and its BIND path, if any)."""
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
param(P('One'), {'type': 'float', 'default': 1.0, 'scratch': True})
R_M, R_A, R_MA = 1.5, 0.2, 0.2        # 1D half-tree ranges: |Mid| (working box), |axis| (= 4s/3), |Mid.axis|
scratch_aaps = [f'E{j+1}' for j in range(4)] + ['SumE', 'SumE_d1', 'SumE_d2', 'Disc', 'SqrtDisc'] + [f'G{k+1}' for k in range(4)] \
    + [f'SL_{tag(L)}' for L in LINES] + [f'D_{tag(a)}_{tag(b)}' for a, b in itertools.combinations(LINES, 2)] \
    + [f'O{i+1}' for i in range(3)] + [f'P{k+1}' for k in range(4)] + [f'T{i+1}{ab}' for i in range(3) for ab in 'ab'] \
    + [f'Mid{ax}{h}' for ax in 'XYZ' for h in 'pn'] + [f'Ax{ax}{h}' for ax in 'XYZ' for h in 'pn'] + ['MM', 'MA', 'AA', 'MAp', 'MAn']
for n in scratch_aaps: param(P(n), {'type': 'float', 'aap': True, 'scratch': True})
for n in ['S', 'AxisX', 'AxisY', 'AxisZ', 'Res', 'Pattern', 'MidX', 'MidY', 'MidZ', 'Lever']: param(P(n), {'type': 'float', 'aap': True})

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
# ---- lever gate ----
# halves of Mid and axis (1 hop behind their sources)
for ax in 'XYZ':
    for h, pos in (('p', True), ('n', False)):
        math_children.append(half1d(P(f'Mid{ax}{h}'), P(f'Mid{ax}'), pos, R_M))
        math_children.append(half1d(P(f'Ax{ax}{h}'), P(f'Axis{ax}'), pos, R_A))
# |Mid|^2 = sum (p^2 + n^2);  Mid.axis = sum (Mp Ap + Mn An - Mp An - Mn Ap);  |axis|^2 = 16/9 S^2
mm = []; ma = []
for ax in 'XYZ':
    Mp, Mn, Ap, An = P(f'Mid{ax}p'), P(f'Mid{ax}n'), P(f'Ax{ax}p'), P(f'Ax{ax}n')
    mm += [prod(P('MM'), Mp, Mp, 1.0), prod(P('MM'), Mn, Mn, 1.0)]
    ma += [prod(P('MA'), Mp, Ap, 1.0), prod(P('MA'), Mn, An, 1.0), prod(P('MA'), Mp, An, -1.0), prod(P('MA'), Mn, Ap, -1.0)]
math_children.append({'tree': 'direct', 'normalized': False, 'name': 'MM = |Mid|^2', 'directWeight': P('One'), 'children': mm})
math_children.append({'tree': 'direct', 'normalized': False, 'name': 'MA = Mid.axis', 'directWeight': P('One'), 'children': ma})
math_children.append(prod(P('AA'), P('S'), P('S'), 16 / 9, name='AA = |axis|^2 = 16/9 S^2'))
math_children.append(half1d(P('MAp'), P('MA'), True, R_MA)); math_children.append(half1d(P('MAn'), P('MA'), False, R_MA))
lever_children = [prod(P('Lever'), P('MM'), P('AA'), 1.0), prod(P('Lever'), P('MAp'), P('MAp'), -1.0), prod(P('Lever'), P('MAn'), P('MAn'), -1.0),
                  {'tree': 'direct', 'normalized': False, 'name': f'-t^2 AA', 'directWeight': P('One'), 'children': [{'clip': clip_for(P('Lever'), -LEVER_T * LEVER_T), 'directWeight': P('AA')}]}]
math_children.append({'tree': 'direct', 'normalized': False, 'name': 'Lever = MM AA - MA^2 - t^2 AA', 'directWeight': P('One'), 'children': lever_children})
math_layer = {'name': 'Palm/Math', 'states': {'Math (WD ON)': {'motion': {'tree': 'direct', 'normalized': False, 'name': 'Math', 'children': math_children}}}, 'default': 'Math (WD ON)'}

# ---------------- Select layer: 16 oriented-pattern states ----------------
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
    # axis = sum sigma_j (E_j - S) d_j  -> Palm/Axis* and ProxyA.localPosition (BIND)
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
def emit_readout():
    L = ['# GENERATED by generate.py -- edit the generator, not this file. Mechanism and measurements: README.md.',
         f'# cage F={F} D={D} k={K} margin={MARGIN} m (|S| units); lut {LUT_N} knots over Disc [{LUT_LO}, {LUT_HI}] m^2; lever t={LEVER_T} m',
         'schema: 1', 'controller: PalmReadout_Fx', 'basis: mount-root', 'role: fx', '',
         'defaults:', '  writeDefaults: on', '  transition: { duration: 0, exitTime: none, interruption: none }', '', 'parameters:']
    for n, sp in params.items():
        fields = [f'type: {sp["type"]}']
        if 'default' in sp: fields.append(f'default: {fmt(sp["default"])}')
        if sp.get('aap'): fields.append('aap: true')
        if sp.get('scratch'): fields.append('scratch: true')
        L.append(f'  {n}: {{ {", ".join(fields)} }}')
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
        if aap in BIND: L.append(f'  {cn}: {{ set: {{ {aap}: {fmt(v)}, "{BIND[aap]}": {fmt(v)} }} }}')
        else: L.append(f'  {cn}: {{ set: {{ {aap}: {fmt(v)} }} }}')
    return '\n'.join(L) + '\n'

# ---------------- glue document ----------------
# Every clip writes the whole binding set (full ownership: on a scene binding a state writes only what its own
# clip writes, at either WD setting, so a delta clip inherits the previous state's values).
B_CONT_GO = 'Container/GameObject.m_IsActive'
B_BONE_GO = 'GrabPosition/GrabBone/GameObject.m_IsActive'
B_CONT_POS = 'Container/VRCPositionConstraint.m_Enabled'
B_SRC_ACT = 'Container/SourcePosition/VRCPositionConstraint.IsActive'
B_GP_ACT = 'GrabPosition/VRCPositionConstraint.IsActive'
B_GP_W0 = 'GrabPosition/VRCPositionConstraint.Sources.source0.Weight'
B_GP_W1 = 'GrabPosition/VRCPositionConstraint.Sources.source1.Weight'
B_ROT_EN = 'Container/Rotor/VRCRotationConstraint.m_Enabled'
B_ROT_W0 = 'Container/Rotor/VRCRotationConstraint.Sources.source0.Weight'   # HomeAnchor/Offset
B_ROT_W1 = 'Container/Rotor/VRCRotationConstraint.Sources.source1.Weight'   # Held
B_FRM_W0 = f'{MOUNT}/Mid/Frame/VRCRotationConstraint.Sources.source0.Weight'   # Recon (6 DOF)
B_FRM_W1 = f'{MOUNT}/Mid/Frame/VRCRotationConstraint.Sources.source1.Weight'   # ReconW (world-up roll)
B_HELD_EN = f'{MOUNT}/Mid/Frame/Held/VRCRotationConstraint.m_Enabled'
def recv_bindings(r):
    base = f'{MOUNT}/{r}'
    return {'go': f'{base}/GameObject.m_IsActive', 'self': f'{base}/VRCContactReceiver.allowSelf', 'others': f'{base}/VRCContactReceiver.allowOthers',
            'sx': f'{base}/Transform.m_LocalScale.x', 'sy': f'{base}/Transform.m_LocalScale.y', 'sz': f'{base}/Transform.m_LocalScale.z'}

def glue_clip(cont_go, bone_go, cont_pos, src_act, gp_act, gp_home, rot_en, rot_home, frame6, held_en, recv_go, filters_open, scale):
    """The full binding set as one `set:` map. gp_home / rot_home select source0 (home) vs source1; frame6 selects Recon vs ReconW."""
    s = {B_CONT_GO: cont_go, B_BONE_GO: bone_go, B_CONT_POS: cont_pos, B_SRC_ACT: src_act, B_GP_ACT: gp_act,
         B_GP_W0: 1 if gp_home else 0, B_GP_W1: 0 if gp_home else 1,
         B_ROT_EN: rot_en, B_ROT_W0: 1 if rot_home else 0, B_ROT_W1: 0 if rot_home else 1,
         B_FRM_W0: 1 if frame6 else 0, B_FRM_W1: 0 if frame6 else 1, B_HELD_EN: held_en}
    for r in READINGS:
        b = recv_bindings(r)
        s[b['go']] = recv_go; s[b['self']] = 1 if filters_open else 0; s[b['others']] = 1 if filters_open else 0
        s[b['sx']] = scale; s[b['sy']] = scale; s[b['sz']] = scale
    return s

# grab-prop's seven values per state are its controller.yaml's, replicated; the six new bindings and the
# receiver set are this entry's. Comments beside each state carry the rationale.
GLUE_CLIPS = {
    # Off: receiver GOs and bone GO off; Container hidden. The receiver floats freeze at their last value, so
    # the Disabled state's entry driver zeroes them. Held for DISABLED_DWELL so the receiver off outlives one
    # evaluation (a same-frame off/on leaves a receiver deaf for the session).
    'disabled': dict(length=DISABLED_DWELL, set=glue_clip(0, 0, 1, 1, 0, True, 1, True, True, 0, 0, True, ACQ_SCALE)),
    # Remote boot dwell (grab-prop's timer): hidden, bone alive so a grab in progress is not missed.
    'timer': dict(length=1.0, set=glue_clip(0, 1, 1, 1, 0, True, 1, True, True, 0, 1, True, ACQ_SCALE)),
    # Home: prop on the hip offset, Rotor riding the home attitude, cage at acquisition scale with filters open.
    'anchored': dict(set=glue_clip(1, 1, 1, 1, 1, True, 1, True, True, 0, 1, True, ACQ_SCALE)),
    # Grabbed, palm not yet latched: position rides the tip (grab-prop's grabbed), Rotor disabled = the prop holds
    # its pose, Held driven onto Rotor, cage still at acquisition scale with filters open.
    'acquire': dict(set=glue_clip(1, 1, 1, 1, 0, False, 0, False, True, 1, 1, True, ACQ_SCALE)),
    # The latch: filters shut at acquisition scale on frame 0 (what is inside now is what stays latched), hosts to
    # working scale on frame 1. Two frames long; Settling takes over at exit time.
    'latched': dict(length=2 * FRAME, set={k: v for k, v in glue_clip(1, 1, 1, 1, 0, False, 0, False, True, 1, 1, False, ACQ_SCALE).items()
                                             if not re.search(r'Transform\.m_LocalScale\.[xyz]$', k)},
                    curves={k: {'tangents': 'stepped', 'keys': [[0, ACQ_SCALE], [FRAME, 1]]}
                            for r in READINGS for k in (recv_bindings(r)['sx'], recv_bindings(r)['sy'], recv_bindings(r)['sz'])}),
    # Latched, readout pipeline priming: working scale, filters shut, Rotor still frozen, Held converging onto it.
    'settling': dict(length=SETTLE_FILL, set=glue_clip(1, 1, 1, 1, 0, False, 0, False, True, 1, 1, False, 1)),
    # Riding the still-settling frame: Held disabled (its local pose under Frame is the fill-end capture), Rotor
    # follows Held, so rotation moves as soon as the pipeline is primed; Held6/Held5 re-take the capture at settle.
    'following': dict(length=CAPTURE_DWELL - SETTLE_FILL, set=glue_clip(1, 1, 1, 1, 0, False, 1, False, True, 0, 1, False, 1)),
    # Same pose as following; the capture rungs are conditional here (polled every frame), the timeout is the length.
    'settled': dict(length=SETTLE_TIMEOUT - CAPTURE_DWELL, set=glue_clip(1, 1, 1, 1, 0, False, 1, False, True, 0, 1, False, 1)),
    # Carry, 6 DOF: Rotor rides Held; Held's own constraint stays on for the entry frame (so its local pose is
    # taken against the Frame the mode just selected) and disables on the next = the capture.
    'held6': dict(length=2 * FRAME, set={k: v for k, v in glue_clip(1, 1, 1, 1, 0, False, 1, False, True, 1, 1, False, 1).items() if k != B_HELD_EN},
                  curves={B_HELD_EN: {'tangents': 'stepped', 'keys': [[0, 1], [FRAME, 0]]}}),
    # Carry, roll fallback: as held6 with Frame on ReconW (world-up).
    'held5': dict(length=2 * FRAME, set={k: v for k, v in glue_clip(1, 1, 1, 1, 0, False, 1, False, False, 1, 1, False, 1).items() if k != B_HELD_EN},
                  curves={B_HELD_EN: {'tangents': 'stepped', 'keys': [[0, 1], [FRAME, 0]]}}),
    # grab-prop's release pulse (its sample window verbatim) plus the rotation freeze: Rotor disabled at t = 0.
    # Filters reopen and the cage collapses at t = 0, so the readout stops being consumed on the release frame.
    'released': dict(length=0.5, set={k: v for k, v in glue_clip(1, 1, 0, 1, 1, False, 0, False, True, 0, 1, True, ACQ_SCALE).items() if k != B_SRC_ACT},
                     curves={B_SRC_ACT: {'tangents': 'stepped', 'keys': [[0, 0], [0.25, 1], [0.5, 0]]}}),
    # World-dropped: both freezes hold (the frozen transform IS the hold); a grab re-enters Acquire.
    'dropped': dict(set=glue_clip(1, 1, 0, 0, 1, False, 0, False, True, 0, 1, True, ACQ_SCALE)),
    # Late-join park (grab-prop's waiting): hidden until a witnessed grab; the bone lives outside the hidden branch.
    'waiting': dict(set=glue_clip(0, 1, 1, 1, 1, True, 1, True, True, 0, 1, True, ACQ_SCALE)),
}

ENABLE = GLUE + 'Enable'
def glue_states():
    grabbed = 'GrabBone_IsGrabbed is true'; released = 'GrabBone_IsGrabbed is false'
    en_off = f'{ENABLE} is false'
    all_pos = [grabbed] + [f'{P(r)} greater 0' for r in READINGS]
    settled = [f'{P("Res")} less {fmt(RES_SETTLE)}', f'{P("S")} greater {fmt(S_LO)}', f'{P("S")} less {fmt(S_HI)}']
    loss = [{'to': 'Acquire', 'when': [f'{P(r)} less 0.00001']} for r in READINGS]
    return {
        'Timer': dict(clip='timer', transitions=[{'to': 'Disabled', 'when': ['IsLocal is true']}, {'to': 'Waiting', 'when': ['IsLocal is false'], 'exitTime': 1.0}]),
        'Disabled': dict(clip='disabled', behaviours=[{'driver': {'set': {P(r): 0 for r in READINGS}}}],
                         transitions=[{'to': 'Anchored', 'when': [f'{ENABLE} is true'], 'exitTime': 1.0}]),
        'Anchored': dict(clip='anchored', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Acquire', 'when': [grabbed]}]),
        'Acquire': dict(clip='acquire', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]}, {'to': 'Latched', 'when': all_pos}]),
        'Latched': dict(clip='latched', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]}, {'to': 'Settling', 'when': [], 'exitTime': 1.0}]),
        'Settling': dict(clip='settling', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]},
                                                       {'to': 'Following', 'when': [], 'exitTime': 1.0}]),
        'Following': dict(clip='following', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]},
                                                         {'to': 'Settled', 'when': [], 'exitTime': 1.0}]),
        'Settled': dict(clip='settled', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]},
                                                     {'to': 'Held6', 'when': settled + [f'{P("Lever")} greater 0']},
                                                     {'to': 'Held5', 'when': settled + [f'{P("Lever")} less 0']},
                                                     {'to': 'Acquire', 'when': [], 'exitTime': 1.0}]),
        'Held6': dict(clip='held6', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]}] + loss),
        'Held5': dict(clip='held5', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Released', 'when': [released]}] + loss),
        'Released': dict(clip='released', transitions=[{'to': 'Dropped', 'when': [], 'exitTime': 1.0}]),
        'Dropped': dict(clip='dropped', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Acquire', 'when': [grabbed]}]),
        'Waiting': dict(clip='waiting', transitions=[{'to': 'Disabled', 'when': [en_off]}, {'to': 'Acquire', 'when': [grabbed]}]),
    }
LAYOUT = {'Timer': [30, 180], 'Waiting': [-210, 250], 'Disabled': [30, 250], 'Anchored': [-210, 390], 'Acquire': [30, 390],
          'Latched': [270, 390], 'Settling': [510, 390], 'Following': [750, 390], 'Settled': [990, 390], 'Held6': [1230, 320], 'Held5': [1230, 460],
          'Released': [510, 530], 'Dropped': [270, 530]}

def emit_glue():
    L = ['# GENERATED by generate.py -- edit the generator, not this file. Mechanism: README.md.',
         '# 6dof-grab-prop glue: grab-prop\'s cell (clip table replicated binding for binding) + the cage latch, the relative',
         '# capture by disable-hold and the roll-mode select. Reads PalmReadout_Fx\'s AAPs through the shared FullController.',
         f'# thresholds: Res settle {RES_SETTLE} m, S band [{S_LO}, {S_HI}] m, lever gate sign of Palm/Lever (t={LEVER_T} m in readout.yaml),',
         f'# fill {SETTLE_FILL} s, capture dwell {CAPTURE_DWELL} s, settle timeout {SETTLE_TIMEOUT} s, disabled dwell {DISABLED_DWELL} s, acquisition host scale {ACQ_SCALE}.',
         'schema: 1', 'controller: SixDofGrabProp_Fx', 'basis: mount-root', 'role: fx', '',
         'defaults:', '  writeDefaults: on', '  transition: { duration: 0, exitTime: none, interruption: none }', '',
         'parameters:',
         f'  {ENABLE}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # off is the reset',
         '  GrabBone_IsGrabbed: bool     # minted by the grab physbone (parameter: GrabBone); never synced',
         '  IsLocal: bool                # VRC built-in',
         '  # Readout names this document only reads: declared scratch so readout.yaml alone emits them into a params asset.']
    for r in READINGS: L.append(f'  {P(r)}: {{ type: float, scratch: true }}')
    for n in ('Res', 'S', 'Lever'): L.append(f'  {P(n)}: {{ type: float, scratch: true }}')
    L += ['', 'layers:', f'  - name: {GLUE}Control', '    states:']
    for sname, st in glue_states().items():
        L.append(f'      {sname}:')
        if st.get('behaviours'):
            L.append('        behaviours:')
            for b in st['behaviours']:
                for kind, body in b.items():
                    sets = ', '.join(f'{k}: {v}' for k, v in body['set'].items())
                    L.append(f'          - {kind}: {{ set: {{ {sets} }} }}')
        L.append(f'        motion: {{ clip: {st["clip"]} }}')
        L.append('        transitions:')
        for t in st['transitions']:
            fields = [f'to: {t["to"]}', f'when: [ {", ".join(t["when"])} ]']
            if 'exitTime' in t: fields.append(f'exitTime: {fmt(t["exitTime"])}')
            L.append(f'          - {{ {", ".join(fields)} }}')
    L += ['    default: Timer', '    layout:', '      nodes:']
    for n, xy in LAYOUT.items(): L.append(f'        {n}: [{xy[0]}, {xy[1]}]')
    L += ['      entry: [50, 120]', '      any:   [50, 40]', '      exit:  [50, 80]', '', 'clips:']
    for cn, c in GLUE_CLIPS.items():
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
    prefab = os.path.join(HERE, 'SixDofGrabProp.prefab')
    if not os.path.exists(prefab): raise SystemExit(f'REFUSE: {prefab} missing')
    raw = open(prefab, encoding='utf-8').read()
    fails = []
    def a(cond, msg):
        if not cond: fails.append(msg)
    docs = re.findall(r'^--- !u!(\d+) &(\d+)\n(.*?)(?=^--- |\Z)', raw, re.M | re.S)
    def guid_of(meta):
        m = re.search(r'^guid: ([0-9a-f]{32})', open(os.path.join(HERE, meta), encoding='utf-8').read(), re.M); return m.group(1)
    g_glue = guid_of('built/SixDofGrabProp_Fx.controller.meta'); g_read = guid_of('built/PalmReadout_Fx.controller.meta')
    p_glue = guid_of('built/SixDofGrabProp_Fx_Parameters.asset.meta'); p_read = guid_of('built/PalmReadout_Fx_Parameters.asset.meta')
    # FullController: controllers and prms both glue-first (first-wins param merge, in each list); globalParams exactly the enable.
    fc = [b for _, _, b in docs if 'class: FullController' in b]
    a(len(fc) == 1, 'exactly one FullController')
    if fc:
        ctrl_guids = re.findall(r'controllers:.*?prms:', fc[0], re.S)[0]
        a([m for m in re.findall(r'guid: ([0-9a-f]{32})', ctrl_guids)] == [g_glue, g_read], 'controllers: [glue, readout] in that order, by GUID')
        prms = re.findall(r'prms:.*?globalParams:', fc[0], re.S)[0]
        a(re.findall(r'guid: ([0-9a-f]{32})', prms) == [p_glue, p_read], 'prms: [glue, readout] in that order, by GUID')
        gp = re.search(r'globalParams:\n((?:\s+- .*\n)*)', fc[0]); names = re.findall(r'- (\S+)', gp.group(1)) if gp else []
        a(names == [ENABLE], f'globalParams == [{ENABLE}], got {names}')
        a('rootBindingsApplyToAvatar: 0' in fc[0], 'rootBindingsApplyToAvatar 0 (basis: mount-root)')
        a(f'Packages/com.ryan6vrc.patterns/' in fc[0] and 'Assets/' not in re.sub(r'id: [0-9a-f]{32}\|Packages[^\n]*', '', fc[0]), 'cached ids name the package, never a venue')
    # Identity map: component/transform fileID -> owning GameObject name, so every assert below names its node.
    names = {i: re.search(r'm_Name: (.*)', b).group(1) for t, i, b in docs if t == '1'}
    go_of = {i: m.group(1) for t, i, b in docs for m in [re.search(r'm_GameObject: \{fileID: (\d+)\}', b)] if m}
    def owner(i): return names.get(go_of.get(i))
    def sources(b):
        """[(source name or 'guid:<guid>', weight)] over the non-empty slots, in slot order."""
        out = []
        for m in re.finditer(r'SourceTransform: \{fileID: (\d+)(?:, guid: ([0-9a-f]{32}))?[^}]*\}\n\s+Weight: ([-0-9.e]+)', b):
            if m.group(1) == '0': continue
            out.append((f'guid:{m.group(2)}' if m.group(2) else owner(m.group(1)), float(m.group(3))))
        return out
    # Receivers: eight, one per reading, each writing the parameter its own name says, tag Hand, self+others,
    # not local-only, box face proximity at the generator's size.
    recv = [(i, b) for _, i, b in docs if 'collisionTags' in b and 'receiverType' in b]
    a(sorted(owner(i) or '' for i, _ in recv) == sorted(READINGS), f'receivers named exactly T1p..T4m, got {sorted(owner(i) or "" for i, _ in recv)}')
    for i, b in recv:
        a(re.search(r'^  parameter: (.*)$', b, re.M).group(1) == P(owner(i) or ''), f'receiver {owner(i)} writes {P(owner(i) or "")}')
        a(re.search(r'collisionTags:\n\s+- Hand\n(?!\s+- )', b), 'receiver tag exactly [Hand]')
        a('allowSelf: 1' in b and 'allowOthers: 1' in b, 'receiver allowSelf 1 allowOthers 1')
        a('localOnly: 0' in b, 'receiver localOnly 0 (remotes re-derive)')
        a('shapeType: 2' in b and 'receiverType: 2' in b and 'useFaceProximity: 1' in b, 'receiver box / proximity / face mode')
        a(re.search(rf'^  size: \{{x: {2*F:g}, y: {2*F:g}, z: {D:g}\}}', b, re.M), f'receiver size ({2*F:g}, {2*F:g}, {D:g})')
        a('contentTypes: 1' in b, 'receiver contentTypes Avatar')
    # Physbone: the grab premise. Bone length and grab radius size the acquisition core (README SBefore you compose it).
    pb = [b for _, _, b in docs if 'snapToHand' in b]
    a(len(pb) == 1, 'one physbone')
    if pb:
        b = pb[0]
        a('snapToHand: 0' in b, 'snapToHand 0 (the tip is a rigid hand point)')
        a('allowGrabbing: 1' in b, 'allowGrabbing')
        a(re.search(r'grabFilter:\n\s+allowSelf: 1\n\s+allowOthers: 1', b), 'grabFilter self+others')
        a(re.search(rf'^  radius: {GRAB_RADIUS:g}\n', b, re.M), f'grab radius {GRAB_RADIUS:g} (the latch core is sized against it)')
        a('parameter: GrabBone' in b, 'physbone parameter GrabBone')
        ign = re.search(r'ignoreTransforms:\n((?:\s+- .*\n)+)', b)
        got = sorted(owner(x) or x for x in re.findall(r'fileID: (\d+)', ign.group(1))) if ign else []
        a(got == ['Cage', 'DropPosition'], f'ignoreTransforms == [Cage, DropPosition], got {got}')
    end_tf = [b for t, i, b in docs if t == '4' and owner(i) == 'GrabBone_End']
    pos = re.search(r'm_LocalPosition: \{x: ([-0-9.e]+), y: ([-0-9.e]+), z: ([-0-9.e]+)\}', end_tf[0]) if end_tf else None
    a(pos is not None and all(abs(float(pos.group(k + 1)) - BONE_END[k]) < 1e-6 for k in range(3)), f'GrabBone_End local position {BONE_END}, got {pos.groups() if pos else None}')
    # The cage tilt: cube diagonal to vertical (Quaternion.FromToRotation((1,1,1)/sqrt3, up)); a world-aligned cage
    # would make palm-down yaw a persistent two-line ambiguity (README SLimits).
    cage_tf = [b for t, i, b in docs if t == '4' and owner(i) == 'Cage']
    a(len(cage_tf) == 1, 'one GameObject named Cage')
    if cage_tf:
        rot = re.search(r'm_LocalRotation: \{x: ([-0-9.e]+), y: ([-0-9.e]+), z: ([-0-9.e]+), w: ([-0-9.e]+)\}', cage_tf[0])
        want = (-0.32505758, 0.0, 0.32505758, 0.88807383)
        a(rot is not None and all(abs(float(rot.group(k + 1)) - want[k]) < 1e-3 for k in range(4)), f'Cage localRotation = cube-diagonal-up tilt, got {rot.groups() if rot else None}')
    # The scale pin: Cage's scale constraint sources assets/World.prefab (never instantiated) at unit offset.
    g_world = guid_of('assets/World.prefab.meta')
    scale = [b for _, i, b in docs if 'ScaleAtRest' in b and owner(i) == 'Cage']
    a(len(scale) == 1 and [s for s, _ in sources(scale[0])] == [f'guid:{g_world}'] and 'ScaleOffset: {x: 1, y: 1, z: 1}' in scale[0],
      'Cage scale constraint sources assets/World.prefab alone at unit offset')
    # The rotation channel: exact sources per node, zeroed (never activated) with identity source offsets, or the
    # capture is wrong by the offset.
    for node, want_src in (('Rotor', ['Offset', 'Held']), ('Held', ['Rotor']), ('Frame', ['Recon', 'ReconW']), ('Damped', ['Damped', 'Rotor'])):
        rc = [b for _, i, b in docs if 'RotationAtRest' in b and 'AimVector' not in b and owner(i) == node]
        a(len(rc) == 1, f'{node} carries one rotation constraint')
        if rc:
            a([s for s, _ in sources(rc[0])] == want_src, f'{node} sources {want_src}, got {[s for s, _ in sources(rc[0])]}')
            a('RotationAtRest: {x: 0, y: 0, z: 0}' in rc[0], f'{node} RotationAtRest zero (Zero, never Activate)')
            a(all(o == '{x: 0, y: 0, z: 0}' for o in re.findall(r'ParentRotationOffset: (\{[^}]*\})', rc[0])), f'{node} source rotation offsets zero')
    if fails:
        print('\n'.join('FAIL: ' + f for f in fails)); raise SystemExit(1)
    print(f'ok: prefab surface holds ({len(recv)} receivers)')

if __name__ == '__main__':
    if '--check' in sys.argv: check(); sys.exit(0)
    text = emit_readout(); open(OUT_READOUT, 'w', newline='\n').write(text)
    glue = emit_glue(); open(OUT_GLUE, 'w', newline='\n').write(glue)
    nstates = len(states); ntrans = sum(len(s['transitions']) for s in states.values())
    def count_leaves(m): return sum(count_leaves(c) if 'tree' in c else 1 for c in m['children'])
    leaves = count_leaves(math_layer['states']['Math (WD ON)']['motion']) + sum(count_leaves(s['motion']) for s in states.values())
    print(f'wrote {OUT_READOUT}: {len(params)} params, {len(clips)} clips, {nstates + 1} states, {ntrans} transitions, {leaves} tree leaves, {len(text.splitlines())} lines')
    print(f'wrote {OUT_GLUE}: {len(GLUE_CLIPS)} clips, {len(glue_states())} states, {len(glue.splitlines())} lines')
