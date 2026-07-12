# hsv-rgb — compute RGB from H/S/V and write a plain color property (Pattern, study)

Compute an RGB colour from `H`/`S`/`V` sliders and write it into a shader's plain `_Color`, for the case
a target shader exposes only a flat colour and no hue property of its own. This is the case `color-adjust`
names and puts out of scope: `color-adjust` drives a shader's **own** hue channel (lilToon `_MainTexHSVG`,
Poiyomi `_MainHueShift`); this entry **computes** RGB itself, in one blend tree, and writes a generic
`_Color`. Pure feed-forward (no feedback), so it just settles ~2–3 frames after an input change —
oscillation is structurally impossible.

**Study entry:** commits `built/` so the single compose Direct tree is legible in the Animator window
(`CONVENTIONS.md` permits this for a declared study entry).

**Provenance:** generalized from the standard HSV→RGB algorithm, re-expressed as blend-tree math — no
real-avatar naming.

## Interface

- **Params:** `H`, `S`, `V` — all float, in, **not synced/saved** (a consumer decides). Assumed in
  `[0, 1]` (`H` clamped, not cyclic — see below). `One` — float, constant `1.0`, never driven — is the
  full-weight helper for the Direct compose tree; leave it at its default. `C`/`M`/`OneMinusV` are
  computed AAPs, not inputs.
- **Output:** the target material's `_Color`, written **by name** as per-channel material curves
  (`.r`/`.g`/`.b`/`.a`) on a placeholder renderer path (`Body/SkinnedMeshRenderer` — a `SkinnedMeshRenderer`
  on a GameObject named `Body`).
- **Seam:** none shipped (Pattern tier, lifted as YAML). A consumer adapts in two steps, in order:
  **`RepathClips` first**, to repoint the placeholder renderer path at their own renderer; **then** honor
  the merge frame — `basis: avatar-root` must pair with the MA merge component's `pathMode` the way the
  `_template` entry documents, or the repathed bindings land on the wrong node.
- **Dependencies:** the target renderer must expose an RGB `_Color` property. By-name binding is inert —
  silently does nothing — on a material lacking `_Color`.
- **Required assets:** none. The Unity Standard material used in the proof below is only a scaffold, not a
  shipped asset; the consumer supplies their own material.

## One DBT, and the WD-ON sum-to-1 sink (the lesson)

**One always-on WD-ON Direct Blend Tree layer**, all the math as nested children — the shippable cost
model (`smooth-frametime` carries the same note): per-layer runtime cost is super-linear and the optimizers
merge blend-tree math into one tree regardless, so the internal cost is tree depth, not layer count. A
consumer lifts and uses this; it is not one-idiom-per-layer study scaffolding.

The decomposition factors `S` and `V` out multiplicatively — `RGB_c = m + C·hue_c(H)`, with `C = V·S`
(chroma), `m = V − C` (the achromatic floor), and `hue_c(H)` the fully-saturated channel colour, an exact
piecewise-linear **trapezoid in `H`** (an exact 1D tree). This is why the textbook six-sector branch never
appears — the sector index and its `X = C·(1 − |H·6 mod 2 − 1|)` term *are* those trapezoids. `C` and `m`
are both `≥ 0` for inputs in `[0, 1]` (`m = V(1−S) ≥ 0`), so both serve directly as Direct `directWeight`s
— the one hard `directWeight ≥ 0` constraint is satisfied for free.

**The `(1−V)` zero-sink per channel is load-bearing — the WD-ON trap this construction exists to
demonstrate.** Under WD-ON a Direct tree whose child weights sum to `Σw < 1` writes
`out = Σ(wᵢ·vᵢ) + (1 − Σw)·default` — the un-driven remainder fills from the **binding's default**. For an
AAP that default is `0` (harmless — the `C`/`m` computes rely on it). For a `_Color` channel the default is
the **material's colour** (white on a fresh Standard material). The naive `{ floor at weight m ; hue at
weight C }` sub-tree sums to `m + C = V`, so whenever `V < 1` it bleeds `(1−V)·white` into every channel —
correct *only* at `V = 1`. The third zero-value sink child at weight `(1−V)` closes each channel's
`Σw = m + C + (1−V) = 1`, killing the deficit and the default-bleed with it. This is `color-adjust`'s
"un-keyed channel reverts to the material default" trap (fact 1) reappearing at the sub-weight level —
the same sum-to-1 discipline the smoother's convex α-pair needs, here forced by WD-fill rather than by
overshoot. The measured behaviour below proves it: the `V = 0.5` row reads its computed RGB, **not** a
white-bleed.

Two adjacent facts the naive author gets wrong:

- **Every channel must be written every frame.** `.r`/`.g`/`.b`/`.a` each get one root child (a Direct
  sub-tree summing floor + hue + sink); a channel left unwritten reverts to the material default under
  WD-ON. One tree, not one Override layer per channel, so the channels also don't fight
  (`color-adjust` fact 2).
- **The binding suffix is `.r`/`.g`/`.b`/`.a`, not `.x`/`.y`/`.z`/`.w`.** `_Color` is a *Color* property;
  `color-adjust`'s `.x`/`.y`/`.z` worked only because `_MainTexHSVG` is a *Vector*. `_Color.x` parses and
  lints clean but the by-name write lands on nothing (a wrong suffix on a Color is silently inert). The MPB
  read below catches it — a wrong suffix would read all-default.

The 2D-hue-wheel approximation an agent might reach for first is both approximate *and* costlier than this
exact 1D decomposition — it is neither needed nor cheaper, so it is not built.

## Measured behavior

Proven by compiling the built controller to a fresh-GUID scratch copy, hosting it on a bare `Animator`
over a **cloned Unity Standard material** (default `_Color = (1, 1, 1, 1)` white) on a placeholder
`SkinnedMeshRenderer`, and ticking `Animator.Update(1/60)` in **edit mode** — no play mode
(`docs/verify.md` → "Pure controller math skips play mode entirely"). `SetFloat` the `H`/`S`/`V` inputs,
settle 8 frames, then read `_Color` from the renderer's **`MaterialPropertyBlock`** (where material
animation lands — `sharedMaterial` stays at the authored default and would read a false negative). Each
row is checked against `UnityEngine.Color.HSVToRGB(H, S, V)`; tolerance `2e-3`, max observed error `2e-5`.

| row | `H` | `S` | `V` | measured MPB `(.r, .g, .b, .a)` | `Color.HSVToRGB` | err |
|---|---|---|---|---|---|---|
| red | 0 | 1 | 1 | (1.0000, 0.0000, 0.0000, 1.0000) | (1, 0, 0) | 0.00000 |
| yellow | 1/6 | 1 | 1 | (1.0000, 1.0000, 0.0000, 1.0000) | (1, 1, 0) | 0.00002 |
| green | 2/6 | 1 | 1 | (0.0000, 1.0000, 0.0000, 1.0000) | (0, 1, 0) | 0.00002 |
| cyan | 3/6 | 1 | 1 | (0.0000, 1.0000, 1.0000, 1.0000) | (0, 1, 1) | 0.00000 |
| blue | 4/6 | 1 | 1 | (0.0000, 0.0000, 1.0000, 1.0000) | (0, 0, 1) | 0.00002 |
| magenta | 5/6 | 1 | 1 | (1.0000, 0.0000, 1.0000, 1.0000) | (1, 0, 1) | 0.00002 |
| white (S=0) | 0 | 0 | 1 | (1.0000, 1.0000, 1.0000, 1.0000) | (1, 1, 1) | 0.00000 |
| desaturated (S=0.5) | 2/6 | 0.5 | 1 | (0.5000, 1.0000, 0.5000, 1.0000) | (0.5, 1, 0.5) | 0.00001 |
| dimmed (V=0.5) | 4/6 | 1 | 0.5 | (0.0000, 0.0000, 0.5000, 1.0000) | (0, 0, 0.5) | 0.00001 |
| black (V=0) | 0 | 0 | 0 | (0.0000, 0.0000, 0.0000, 1.0000) | (0, 0, 0) | 0.00000 |

- **Six hue anchors** (S=V=1) land the primaries and secondaries exactly. `.a` holds `1.0000` on every
  row (the constant-alpha child).
- **The sink fix, measured:** the **dimmed** row (`V = 0.5`) reads `(0, 0, 0.5)` — its red and green
  channels are `0.0000`, **not** the `(1−V)·white = 0.5` bleed a missing sink would inject. The
  **desaturated** row (`S = 0.5`) reads `(0.5, 1, 0.5)`, its floor `m = V(1−S) = 0.5` correctly filled
  by the `m` child, not by the default. Both `V<1`/`S<1` rows match `Color.HSVToRGB` to `1e-5`, so the
  material default never bleeds in.
- **Binding lands:** every computed row differs from the cloned material's default white `(1,1,1,1)` (the
  dimmed row's `(0,0,0.5)` most starkly), which rules out a wrong `.x`/`.y`/`.z` suffix — that would read
  all-default on the MPB — and confirms the `.r`/`.g`/`.b` writes reach the material.
