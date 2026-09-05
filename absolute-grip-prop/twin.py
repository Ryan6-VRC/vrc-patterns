"""Per-frame twin of the compiled grip readout (readout.yaml), evaluated from generate.py's own tree + rung structures.
Not a build input: it is the reference the Unity edit-tick / play replay is scored against (README SVerifying).
Sweep CSVs were recorded at P8c's box geometry (F 0.15, D 0.3); load() re-expresses them at generate.py's F, D exactly
under the naive nearest-surface model (the surface distance is unchanged, only the face plane moves).

Frame model (Unity Animator.Update): each layer first evaluates its transitions against the parameter values as
they stand at frame start (last frame's clip writes), then the active states' motions write this frame's AAPs from
the current inputs and those same frame-start values. Direct-tree children sum weight x clip value with the weight
clamped >= 0; a 1D tree blends the two threshold-neighbours of its blend parameter (clamped at the ends).

  python twin.py score  <sweep>...           scorer-metric scoring at the client floor (sweeps: P8_SWEEPS, else the
                                             workspace's test-output/p8/probe-04 two directories above this repo)
  python twin.py dump   <sweep> <out.csv>    per-frame outputs on clean readings (the Unity edit-tick comparison reference)
  python twin.py compare <unity.csv> <twin.csv>
  python twin.py truth  <sweep>...           twin Mid / MM against the CSV's true centre and axis (tip = cage origin)

The gate and cue inputs (Palm/HandL, HandR, CueP, CueN) stay at their defaults here: the recorded sweeps carry a palm only,
so HandDiff and Cue read 0 on both sides of a compare and the twin proves the palm half of the readout, not the differentials.
"""
import csv, math, os, random, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate as G
# The recorded sweeps live in the Atelier workspace's test-output (disposable); override with P8_SWEEPS.
SWEEPS = os.environ.get('P8_SWEEPS') or os.path.join(HERE, '..', '..', 'test-output', 'p8', 'probe-04')
READ_COLS = [f'T{j+1}{s}' for j in range(4) for s in 'pm']
INPUTS = [G.P(c) for c in READ_COLS]

# ---------------- compile the generator's structures into evaluators ----------------
def compile_tree(m, scale_param=None):
    """flatten a tree into leaf records: (list of weight params, list of (1d param, lo, hi, is_upper)) -> too slow; instead
    keep a recursive evaluator closure per tree."""
    kind = m['tree']; children = m['children']
    if kind == 'direct':
        subs = []
        for c in children:
            w = c.get('directWeight')
            if 'tree' in c: subs.append((w, ('tree', compile_tree(c))))
            else:
                aap, val = G.clips[c['clip']]; subs.append((w, ('leaf', aap, val)))
        def ev(vis, scale, out):
            for w, sub in subs:
                wt = max(0.0, vis.get(w, 0.0)) * scale
                if wt == 0.0: continue
                if sub[0] == 'leaf': out[sub[1]] = out.get(sub[1], 0.0) + wt * sub[2]
                else: sub[1](vis, wt, out)
        return ev
    if kind == '1d':
        p = m['param']; ch = sorted(children, key=lambda c: c['threshold'])
        thr = [c['threshold'] for c in ch]; leaves = [G.clips[c['clip']] for c in ch]
        def ev(vis, scale, out):
            x = vis.get(p, 0.0)
            if x <= thr[0]: idx = [(0, 1.0)]
            elif x >= thr[-1]: idx = [(len(thr) - 1, 1.0)]
            else:
                for i in range(len(thr) - 1):
                    if thr[i] <= x <= thr[i + 1]:
                        f = (x - thr[i]) / (thr[i + 1] - thr[i]); idx = [(i, 1 - f), (i + 1, f)]; break
            for i, w in idx:
                aap, val = leaves[i]; out[aap] = out.get(aap, 0.0) + scale * w * val
        return ev
    raise ValueError(kind)
MATH = compile_tree(G.math_layer['states']['Math (WD ON)']['motion'])
SELECT = {name: compile_tree(st_['motion']) for name, st_ in G.select_layer['states'].items()}
def parse_cond(c):
    parts = c.rsplit(' ', 2); return parts[0], parts[1], float(parts[2])
RUNGS = {name: [(r['to'], [parse_cond(c) for c in r['when']]) for r in st_['transitions']] for name, st_ in G.select_layer['states'].items()}
DEFAULT_STATE = G.select_layer['default']
def cond_ok(vis, p, op, v):
    x = vis.get(p, 0.0); return x > v if op == 'greater' else x < v
def defaults():
    vis = {n: float(sp.get('default', 0.0)) for n, sp in G.params.items()}
    for n, sp in G.params.items():
        if sp.get('aap'): vis[n] = 0.0
    return vis

class Twin:
    def __init__(self): self.vis = defaults(); self.state = DEFAULT_STATE; self.hops = 0
    def step(self, readings):
        """readings: dict col -> value (T1p..T4m). Returns the visible AAP dict after this frame's writes."""
        vis = self.vis
        for to, conds in RUNGS[self.state]:                       # transition ladder, first match
            if all(cond_ok(vis, p, op, v) for p, op, v in conds): self.state = to; self.hops += 1; break
        inp = dict(vis)
        for c in READ_COLS: inp[G.P(c)] = readings[c]
        out = {}
        MATH(inp, 1.0, out); SELECT[self.state](inp, 1.0, out)
        new = dict(inp); new.update(out); self.vis = new
        return new

# ---------------- sweeps ----------------
DIRS = G.DIRS
F0, D0 = 0.15, 0.3    # the sweeps' recorded box geometry
def reexpress(R):
    """reading at (F0, D0) -> reading at (G.F, G.D): dsurf = (1-R) D0 is unchanged, the face plane moves out by G.F - F0."""
    d = (1.0 - R) * D0 + (G.F - F0)
    return max(0.0, 1.0 - d / G.D)
def load(name):
    rows = list(csv.DictReader(open(os.path.join(SWEEPS, f'sweep-{name}.csv'))))
    for r in rows:
        for c in READ_COLS: r[c] = repr(reexpress(float(r[c])))
    return rows
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def ang(u, w):
    nu = math.sqrt(dot(u, u)); nw = math.sqrt(dot(w, w))
    if nu == 0 or nw == 0: return 90.0
    return math.degrees(math.acos(max(-1, min(1, dot(u, w) / (nu * nw)))))
def lang(u, w): return min(ang(u, w), 180 - ang(u, w))
def axis_of(vis): return (vis[G.P('AxisX')], vis[G.P('AxisY')], vis[G.P('AxisZ')])
def clean_axis(vis, readings, state):
    """the held pattern's line on the noise-free readings, with the twin's own S (what the prop would ride)."""
    sg = G.PATS[int(round(vis[G.P('Pattern')]))]; s = vis[G.P('S')]
    E = [G.D * (readings[f'T{j+1}p'] + readings[f'T{j+1}m']) + G.E_CONST for j in range(4)]
    return tuple(sum(sg[j] * (E[j] - s) * DIRS[j][i] for j in range(4)) for i in range(3))
def score(rows, sigma, seed=1, fps=60, WIN=12, shift=1):
    """probe-04's metrics on the twin: flip >10 deg, twitch 5-10, wrong >5 from truth, jitter noisy-vs-clean, plus
    orientation errors. Each segment start is a fresh grab: the first WIN frames settle, orientation is then free."""
    rng = random.Random(seed); tw = Twin(); held = None; seg_prev = None; since = 0
    flips = twitch = wrong = orient = n = 0; jit = []; axerr = []; settle = []; sw = 0; flip_sign = 1
    for i in range(len(rows) - shift):
        r = rows[i]; rr = rows[i + shift]
        clean = {c: float(rr[c]) for c in READ_COLS}
        if min(clean.values()) <= 0:
            tw.step(clean); continue
        noisy = {c: v + rng.gauss(0, sigma) / G.D for c, v in clean.items()}
        ut = (float(r['ux']), float(r['uy']), float(r['uz']))
        if rr['seg'] != seg_prev:
            if seg_prev is not None: settle.append(sw)
            seg_prev = rr['seg']; since = 0; held = None; sw = 0
        else: since += 1
        vis = tw.step(noisy)
        v = axis_of(vis); vc = clean_axis(vis, clean, tw.state)
        if since == WIN - 1: flip_sign = 1 if dot(vc, ut) >= 0 else -1      # relative capture at grab
        if since < WIN:
            if lang(vc, ut) > 5: sw += 1
            continue
        vc = tuple(flip_sign * x for x in vc); v = tuple(flip_sign * x for x in v)
        axerr.append(lang(vc, ut))
        if held is not None:
            j = lang(vc, held)
            if j > 10: flips += 1
            elif j > 5: twitch += 1
        held = vc; n += 1
        if lang(vc, ut) > 5: wrong += 1
        if dot(vc, ut) < 0: orient += 1
        jit.append(lang(v, vc))
    m = n / fps / 60; axerr.sort()
    return dict(frames=n, fpm=flips / m, tpm=twitch / m, wrong=wrong / n, orient=orient / n, jit_med=st.median(jit), jit_max=max(jit),
                ax_med=st.median(axerr), ax_p99=axerr[int(0.99 * len(axerr))], ax_max=axerr[-1], settle_wrong=settle, hops=tw.hops)
OUT_COLS = ['frame', 'Pattern', 'AxisX', 'AxisY', 'AxisZ', 'S', 'Res', 'MidX', 'MidY', 'MidZ', 'MM', 'HandDiff', 'Cue']
def dump(rows, path):
    tw = Twin()
    with open(path, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(OUT_COLS)
        for i, r in enumerate(rows):
            vis = tw.step({c: float(r[c]) for c in READ_COLS})
            w.writerow([i] + [repr(vis[G.P(c)]) for c in OUT_COLS[1:]])
def compare(unity_csv, twin_csv, valid_from=None):
    a = list(csv.DictReader(open(unity_csv))); b = list(csv.DictReader(open(twin_csv)))
    n = min(len(a), len(b)); pat_mis = []; ax = []; s_d = []
    for i in range(n):
        if int(round(float(a[i]['Pattern']))) != int(round(float(b[i]['Pattern']))): pat_mis.append(i)
        ax.append(max(abs(float(a[i][c]) - float(b[i][c])) for c in ('AxisX', 'AxisY', 'AxisZ')))
        s_d.append(abs(float(a[i]['S']) - float(b[i]['S'])))
    extra = {}
    for c in ('MidX', 'MidY', 'MidZ', 'MM', 'HandDiff', 'Cue'):
        if c in a[0] and c in b[0]: extra[f'{c}_absdiff_max'] = max(abs(float(a[i][c]) - float(b[i][c])) for i in range(n))
    return dict(frames=n, pattern_mismatch_frames=len(pat_mis), first_mismatches=pat_mis[:20],
                axis_absdiff_max=max(ax), axis_absdiff_p99=sorted(ax)[int(0.99 * n)], s_absdiff_max=max(s_d), **extra)
def truth(rows, settle=12):
    """Mid and MM against the CSV's true capsule centre (cx,cy,cz) and axis (ux,uy,uz), tip at the cage origin.
    MM is the lever proxy: |Mid|^2 stands in for the squared perpendicular distance from the origin to the axis line, exact
    when the tip has no along-axis offset; the refuse is MM > G.MM_MIN once the pipeline has filled (skips the first
    `settle` frames of each segment). Reports the proxy's error against the true lever and the refuse's agreement."""
    tw = Twin(); seg = None; since = 0; mid_err = []; mm_err = []; ref_ok = 0; ref_n = 0; lev_true = []
    for r in rows:
        clean = {c: float(r[c]) for c in READ_COLS}
        vis = tw.step(clean)
        if r['seg'] != seg: seg = r['seg']; since = 0
        else: since += 1
        if since < settle or min(clean.values()) <= 0: continue
        c = (float(r['cx']), float(r['cy']), float(r['cz'])); u = (float(r['ux']), float(r['uy']), float(r['uz']))
        m = (vis[G.P('MidX')], vis[G.P('MidY')], vis[G.P('MidZ')])
        mid_err.append(math.sqrt(sum((a - b) ** 2 for a, b in zip(m, c))))
        cu = dot(c, u) / math.sqrt(dot(u, u)); lev = math.sqrt(max(0.0, dot(c, c) - cu * cu)); lev_true.append(lev)
        mm_err.append(abs(math.sqrt(max(0.0, vis[G.P('MM')])) - lev))
        want = lev * lev > G.MM_MIN; got = vis[G.P('MM')] > G.MM_MIN
        ref_n += 1; ref_ok += (want == got)
    mid_err.sort(); mm_err.sort()
    return dict(frames=ref_n, mid_err_med=mid_err[len(mid_err) // 2], mid_err_max=mid_err[-1], mm_lever_err_med=mm_err[len(mm_err) // 2],
                mm_lever_err_max=mm_err[-1], refuse_agree=ref_ok / ref_n, lever_truth_min=min(lev_true), lever_truth_max=max(lev_true))
if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'score':
        for name in sys.argv[2:]:
            rows = load(name)
            for sig in [0.0, 0.000045, 0.0001]:
                r = score(rows, sig)
                print(f"{name} sigma={sig*1e3:.3f}mm | fpm {r['fpm']:.2f} tpm {r['tpm']:.1f} wrong {r['wrong']*100:.3f}% orient {r['orient']*100:.3f}% jit med/max {r['jit_med']:.3f}/{r['jit_max']:.3f} ax med/p99/max {r['ax_med']:.2f}/{r['ax_p99']:.2f}/{r['ax_max']:.2f} settle-wrong {r['settle_wrong']} hops {r['hops']}")
    elif cmd == 'dump': dump(load(sys.argv[2]), sys.argv[3]); print('wrote', sys.argv[3])
    elif cmd == 'compare': print(compare(sys.argv[2], sys.argv[3]))
    elif cmd == 'truth':
        for name in sys.argv[2:]: print(name, truth(load(name)))
