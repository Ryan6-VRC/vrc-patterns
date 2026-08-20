#!/usr/bin/env python3
"""quant-channel generator: emits controller.yaml + built/manifest.json from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ — the controller.yaml
committed here is generated output and the repo gate holds built/ to it, so hand-
editing it desynchronises the document from both this generator and the compiled
controller. That governs this repo's build only: a consumer calling build(config)
into their own project owns the emitted document, and deviating there is fine as
a commented transform in their build script, never as a silent edit.

One CONFIG describes a set of smoothed, binary-synced OSC parameter channels and
emits three coupled artifacts: the avatar-side FX layer (decode + smoothing), the
expression-parameter declarations (wire bools, float companions, outputs, the
sentinel), and the channel manifest JSON a sender (vrc-bridge) loads to know how
to encode. The manifest is authoritative on the sender side; the sentinel — an
unsynced Int whose DEFAULT VALUE is the manifest id, served over OSCQuery within
0.14 s of /avatar/change (docs/osc.md) — is how the bridge learns which manifest
the worn avatar means.

Wire contract, fixed for VRCFaceTracking compatibility (do not renegotiate here):
a signed channel at n bits is synced bools `<Name>1 <Name>2 <Name>4 …` plus
`<Name>Negative`; decode is x̂ = ±k/(2ⁿ−1) where k sums bit weights 2^i/(2ⁿ−1).
The float companion `<Name>` is a declared UNSYNCED float: VRChat's unchecked
inbound path is unreliable, so every OSC-written param must be declared
(docs/osc.md) — and it carries the wearer's full precision, which is the local
half of the design. There is NO on-avatar encoder: encoding is sender-side
everywhere (the bridge; VRCFT for face tracking).

Decode is gated on IsLocal, structurally: two IsLocal-switched states, the local
one smoothing the raw float, the remote one decoding bits then smoothing. This
deliberately fixes the measured defect in the studied reference rig, whose
generated decoder ran ungated so the wearer saw the quantized reconstruction
despite being sent full floats. The wearer can also be forced down the Remote
branch deliberately, by the unsynced `QC/PreviewRemote` debug door — so IsLocal
is not the sole selector, and nothing on the wire changes when it is set (README
§Verifying carries the fidelity limit). Only the active state is evaluated, so the
frametime rig is duplicated into any state that needs it — a rig living only in
Remote would freeze a local frametime smoother's dt at whatever it last read.

Smoothing is the exponential 1D-on-keep tree (OSCmooth's shape, credited as
convention ancestor): blend param = keep, input subtree at threshold 0, feedback
subtree at threshold 1, children thresholded ±1 so signed values survive — a
0/1-thresholded smoother rectifies the negative half to 0 (measured; probe 1).
Frametime compensation is BACKWARD Euler: keep = 1/(1 + dt/τ), computed by the
Normalize-Blend-Values divide idiom fed U = FrameTime·(1/τ) through the multiply
idiom. Chosen by measurement over both of smooth-frametime's flavours: its
clamp01 (forward Euler, mix = clamp(dt/τ)) undershoots below τ and becomes a
literal passthrough at dt ≥ τ — no smoothing exactly where frame rate is worst
(measured: τ_eff for backward Euler stays bounded, ≈1.05τ @60 fps, 1.21τ
@15 fps, 1.57τ @5 fps, always erring toward MORE smoothing) — and its remap
(tabulated 1−e^(−x)) is exact only as densely as its 1D keys sample the
operating band, a per-channel tuning surface an emitter would have to guess.
1/τ is held in a param default (`QC/InvTau/…`), so τ is install-time tunable
without editing trees.
The keep value sits 3 AAP hops from FrameTime (rig → U → keep), so it reads a
3-frame-stale dt — inert at any steady frame rate.

Per channel and per side (`local:` / `remote:`), `frametime:` selects the single
live knob: true → `tau` (keep derived per frame, above); false → `lambda`, a
fixed keep held in a per-channel param default. Local defaults to
{frametime: false, lambda: 0} — a passthrough, because the sender's own
smoothing (manifest `floatTau`) owns local feel; a non-zero local side exists
for raw-sensor senders (VRCFT eye gaze). Remote τ below the ~0.083 s sync tick
is a near-no-op — the remote input is a tick staircase, and a smoother that
settles between ticks reproduces it (README).

`bits: 0` is a plain-synced-float channel: no wire bools, no decode; the float
companion itself is declared synced (8-bit on the wire) and the remote side
smooths it directly. The analogue of the bridge's quant_level=0 mode.

Name lint (fail-loud at generate time): a channel name must not end in a digit
(`X` and `X1` collide — `X`'s bit-1 param IS `X1`'s float companion, and
VRCFT's discovery regex recovers bit indices from trailing digits the same
way), must not extend another channel's name by digits alone, and must not
contain spaces (the client rewrites a space to `_` and serves only that
address while the emulator resolves the verbatim spelling — one name would
mean two addresses). After the lint, address = "/avatar/parameters/" + name is
single-valued, and the manifest's `address` field is a CHECKED ECHO of it: the
bridge loader verifies the equality and fails loud, so the field cannot drift
into a second source of truth.

Fragment mode, for a generator composing these channels into its own controller
(import via importlib.util.spec_from_file_location — the folder name is not an
identifier): `build(config)` returns the emitted pieces without writing a file:

    {"header":   [comment lines describing the channels],
     "params":   [lines for a `parameters:` block; includes the built-in
                  `IsLocal` — the importer dedupes it against its own],
     "layers":   [blocks, one per layer, each a list of lines indented for a
                  `layers:` block],
     "clips":    [clip lines indented for a `clips:` block],
     "manifest": {the manifest dict, json-ready},
     "facts":    {syncedBits, channelCount, wireNames per channel}}

The importer owns the document frame (schema/controller/basis/role/defaults)
and merges these under its own sections; `main()` below is itself the first
consumer and the committed config's byte-identity check (`--check`).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The sentinel's name is a FIXED global address (operator-ruled), not derived from
# CONFIG: the bridge fetches exactly this node on every avatar, and two quant
# installs on one avatar collide on it by design — the manifest id is an
# avatar-scoped identity, so a second channel set merges into this CONFIG.
SENTINEL = "QuantChannel/Manifest"

# Internal-param prefix. Everything under it stays OFF the prefab's globalParams,
# so a merged build instance-prefixes it; nothing outside the module may bind it BY THE
# BARE NAME. QC/PreviewRemote is the one member a driver is meant to reach — as the
# instance-prefixed name OSCQuery serves, which is why it alone is declared, not scratch.
QC = "QC"

CONFIG = {
    # Manifest id (identity; `revision` is content). Registry: 1-999 vrc-patterns,
    # 1000+ third parties — the README's registry table is the ledger. Ids >255 are
    # live-validated (docs/osc.md); the SDK inspector still truncates a >255 default
    # on any keystroke in its row, so regenerate rather than hand-edit the asset.
    "manifestId": 1,
    "revision": 1,
    # The committed build is the synthetic demo in the studied reference rig's own
    # shape: two touchpads = four signed 3-bit axes + one gate bool = 17 synced
    # bits (vs 33 for four synced floats + a bool). The demo/ nested entry is the
    # consumer (two 2D trees on a debug transform); this entry is the substrate.
    "channels": [
        {"name": "QDemo/LX", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "QDemo/LY", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "QDemo/RX", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "QDemo/RY", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
    ],
    # Gate bools: declared synced, exported bare, consumed by whatever tree the
    # channels feed (the demo weights its 2D trees on Enable). The studied rig's
    # Enable — dropped by the sender after idle — is this, sender-driven.
    "gates": ["QDemo/Enable"],
}


def refuse(msg):
    raise SystemExit("REFUSE: " + msg)


def lint_names(channels, gates):
    names = [ch["name"] for ch in channels]
    all_names = names + list(gates)
    for n in all_names:
        if " " in n:
            refuse(f"name '{n}' contains a space — the client rewrites it, the emulator does not; one name, two addresses")
    for n in names:
        if n[-1].isdigit():
            refuse(f"channel name '{n}' ends in a digit — it collides with the wire-bool grammar (<Name><2^i>) and with VRCFT's trailing-digit bit recovery")
        for m in names:
            if m != n and m.startswith(n) and m[len(n):].isdigit():
                refuse(f"channel name '{m}' is '{n}' plus digits — '{n}'s wire bools and '{m}'s float companion collide")
    # The whole EMITTED namespace must be collision-free, not just the config's base
    # names: a channel also owns its derived wire bools and its /Smoothed output, so a
    # gate named 'Foo1' beside channel 'Foo', or a channel named 'FooNegative', would
    # declare one parameter twice — with contradictory declarations.
    owners = {}

    def claim(name, owner):
        if name in owners:
            refuse(f"name '{name}' is emitted twice: by {owner} and by {owners[name]}")
        owners[name] = owner

    for ch in channels:
        bits, neg = wire_bools(ch)
        me = f"channel '{ch['name']}'"
        claim(ch["name"], me)
        for b in bits + neg:
            claim(b, f"{me} (a derived wire bool)")
        claim(ch["name"] + "/Smoothed", f"{me} (its output)")
    for g in gates:
        claim(g, f"gate '{g}'")
    claim(SENTINEL, "the sentinel")
    # Clip keys flatten '/' to '_' (san), so two channel names differing only there
    # would emit duplicate clip keys — one channel's trees driven by the other's clips.
    sans = {}
    for n in names:
        if san(n) in sans:
            refuse(f"channel names '{sans[san(n)]}' and '{n}' collide after the '/' -> '_' clip-key flattening")
        sans[san(n)] = n


def san(name):
    """Clip-key-safe form of a channel name."""
    return name.replace("/", "_")


def tau_label(tau):
    return "Tau" + repr(tau).replace(".", "_").replace("-", "m")


def fmt(v):
    """Deterministic float formatting for clip constants."""
    return format(v, ".9g")


def side(ch, which):
    s = dict(ch.get(which) or {})
    s.setdefault("frametime", False)
    if s["frametime"]:
        if "tau" not in s:
            refuse(f"channel '{ch['name']}' {which}: frametime: true needs `tau`")
        if "lambda" in s:
            refuse(f"channel '{ch['name']}' {which}: frametime: true and `lambda` together — one knob per side; tau owns a compensated side")
        if not (s["tau"] > 0):
            refuse(f"channel '{ch['name']}' {which}: tau must be > 0")
    else:
        s.setdefault("lambda", 0.0)
        if "tau" in s:
            refuse(f"channel '{ch['name']}' {which}: `tau` without frametime: true is dead config — set frametime: true or use `lambda`")
        if not (0.0 <= s["lambda"] < 1.0):
            refuse(f"channel '{ch['name']}' {which}: lambda (keep fraction) must be in [0, 1)")
    return s


def wire_bools(ch):
    n = ch["bits"]
    bits = [f"{ch['name']}{1 << i}" for i in range(n)]
    neg = [f"{ch['name']}Negative"] if ch.get("signed") and n > 0 else []
    return bits, neg


def smoother_lines(o, ind, ch, input_param, keep_param, tag):
    """The probe-validated signed-safe exponential smoother: 1D on keep,
    input subtree at threshold 0, feedback at threshold 1, children ±1."""
    name, s = ch["name"], san(ch["name"])
    o(f"{ind}- tree: 1d")
    o(f"{ind}  name: \"{name} smooth ({tag})\"")
    o(f"{ind}  param: {keep_param}")
    o(f"{ind}  directWeight: {QC}/One")
    o(f"{ind}  children:")
    for (label, p, thr) in ((f"{name} take input", input_param, "0.0"),
                            (f"{name} keep old", f"{name}/Smoothed", "1.0")):
        o(f"{ind}    - tree: 1d")
        o(f"{ind}      name: \"{label}\"")
        o(f"{ind}      param: {p}")
        o(f"{ind}      threshold: {thr}")
        o(f"{ind}      children:")
        o(f"{ind}        - {{ clip: Sm_{s}_neg, threshold: -1.0 }}")
        o(f"{ind}        - {{ clip: Sm_{s}_pos, threshold: 1.0 }}")


def decode_lines(o, ind, ch):
    """Bit-weight sum → QC/<Name>/Decoded; sign is a 1D root on Negative
    selecting a ± subtree (OSCmooth's shape) — ±0 is 0 structurally, which is
    what makes VRCFT's Negative-at-zero-magnitude harmless."""
    name, s, n = ch["name"], san(ch["name"]), ch["bits"]
    bits, neg = wire_bools(ch)

    def mag(sign, thr):
        o(f"{ind}    - tree: direct")
        o(f"{ind}      name: \"{name} {'+' if sign > 0 else '-'}mag\"")
        o(f"{ind}      threshold: {thr}")
        o(f"{ind}      children:")
        for i, b in enumerate(bits):
            o(f"{ind}        - {{ clip: Dec_{s}_{'p' if sign > 0 else 'n'}{1 << i}, directWeight: {b} }}")

    if neg:
        o(f"{ind}- tree: 1d")
        o(f"{ind}  name: \"{name} decode\"")
        o(f"{ind}  param: {neg[0]}")
        o(f"{ind}  directWeight: {QC}/One")
        o(f"{ind}  children:")
        mag(+1, "0.0")
        mag(-1, "1.0")
    else:
        o(f"{ind}- tree: direct")
        o(f"{ind}  name: \"{name} decode\"")
        o(f"{ind}  directWeight: {QC}/One")
        o(f"{ind}  children:")
        for i, b in enumerate(bits):
            o(f"{ind}    - {{ clip: Dec_{s}_p{1 << i}, directWeight: {b} }}")


def rig_lines(o, ind):
    """The owned frametime rig (blendtree-math's shape): linear Time ramp +
    sibling FrameTime = Time − LastTime calc. Duplicated per state that needs
    it — only the active IsLocal state evaluates."""
    o(f"{ind}- {{ clip: QC_Time_Ramp, directWeight: {QC}/One }}")
    o(f"{ind}- tree: direct")
    o(f"{ind}  name: \"FrameTime = Time - LastTime\"")
    o(f"{ind}  directWeight: {QC}/One")
    o(f"{ind}  children:")
    o(f"{ind}    - {{ clip: QC_FrameTime_Pos, directWeight: {QC}/Time }}")
    o(f"{ind}    - {{ clip: QC_FrameTime_Neg, directWeight: {QC}/LastTime }}")
    o(f"{ind}    - {{ clip: QC_LastTime_Set,  directWeight: {QC}/Time }}")


def keep_lines(o, ind, label):
    """U = FrameTime·(1/τ) via the multiply idiom, then keep = 1/(1+U) via the
    Normalize-Blend-Values divide idiom (probe 1's construction C)."""
    o(f"{ind}- tree: direct")
    o(f"{ind}  name: \"U = dt/tau ({label})\"")
    o(f"{ind}  directWeight: {QC}/One")
    o(f"{ind}  children:")
    o(f"{ind}    - tree: direct")
    o(f"{ind}      directWeight: {QC}/FrameTime")
    o(f"{ind}      children:")
    o(f"{ind}        - {{ clip: U_One_{label}, directWeight: {QC}/InvTau/{label} }}")
    o(f"{ind}- tree: direct")
    o(f"{ind}  name: \"Keep = 1/(1+U) ({label})\"")
    o(f"{ind}  directWeight: {QC}/One")
    o(f"{ind}  normalized: true")
    o(f"{ind}  children:")
    o(f"{ind}    - {{ clip: Keep_Dummy, directWeight: {QC}/U/{label} }}")
    o(f"{ind}    - {{ clip: Keep_One_{label}, directWeight: {QC}/One }}")


def build(config):
    """Fragment entry point: compute the channels and return the emitted pieces
    (docstring above carries the contract)."""
    c = config
    channels = c["channels"]
    gates = list(c.get("gates") or [])
    if not channels:
        refuse("no channels declared")
    if not (1 <= int(c["manifestId"])):
        refuse("manifestId must be >= 1")
    for ch in channels:
        n = ch["bits"]
        if not (0 <= n <= 8):
            refuse(f"channel '{ch['name']}': bits must be 0..8 (0 = plain synced float)")
        if n == 0 and ch.get("signed"):
            refuse(f"channel '{ch['name']}': signed is meaningless at bits: 0 — a synced float already carries sign")
    lint_names(channels, gates)          # after the bits check: the lint derives the wire bools

    sides = {"local": [side(ch, "local") for ch in channels],
             "remote": [side(ch, "remote") for ch in channels]}

    # Distinct compensated taus per side, in first-declared order (deterministic).
    def taus(which):
        seen = []
        for s in sides[which]:
            if s["frametime"] and s["tau"] not in seen:
                seen.append(s["tau"])
        return seen

    taus_by_side = {w: taus(w) for w in ("local", "remote")}
    any_ft = any(taus_by_side.values())
    synced = sum((ch["bits"] + (1 if ch.get("signed") and ch["bits"] else 0)) if ch["bits"] else 8
                 for ch in channels) + len(gates)

    header = []
    o = header.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o(f"# quant-channel: {len(channels)} smoothed binary-synced OSC channel{'s' if len(channels) != 1 else ''}"
      f"{' + ' + str(len(gates)) + ' gate bool' + ('s' if len(gates) != 1 else '') if gates else ''}"
      f" = {synced} synced bits.")
    o("# Wire: VRCFT-compatible <Name>1/2/4… (+ <Name>Negative when signed), decode x̂ = ±k/(2ⁿ−1);")
    o("# an unsynced declared float <Name> carries the wearer's full precision. No on-avatar encoder.")
    o("# Two IsLocal-switched states: Local smooths the raw float (the wearer does not see the")
    o("# quantized reconstruction — the gate the studied reference rig lacked); Remote decodes")
    o(f"# bits then smooths. The unsynced {QC}/PreviewRemote door deliberately puts the WEARER on")
    o("# the Remote branch to preview that decode — the one way a local copy shows steps.")
    o("# Frametime-compensated keep = 1/(1 + dt/τ) (backward Euler — probe-")
    o("# measured over forward Euler, which turns into a passthrough at dt ≥ τ); τ tunable via")
    o(f"# the {QC}/InvTau/* param defaults. Sentinel {SENTINEL} default = manifest id {c['manifestId']}")
    o("# (revision " + str(c["revision"]) + "); built/manifest.json is the sender-side contract.")

    params = []
    o = params.append
    o("  IsLocal: bool              # VRC built-in")
    o(f"  {QC}/One: {{ type: float, default: 1.0, scratch: true }}   # constant full-weight helper, never driven")
    o("  # Sentinel: unsynced Int whose DEFAULT is the manifest id — the bridge fetches it over")
    o("  # OSCQuery to pick the manifest. Synced unchecked, never NotSynced (a NotSynced param")
    o("  # is not registered and 404s). The SDK inspector truncates a >255 default on any")
    o("  # keystroke in its row — regenerate, don't hand-edit.")
    o(f"  {SENTINEL}: {{ type: int, default: {c['manifestId']}, vrc: {{ synced: false, saved: false }} }}")
    # Declared rather than scratch: OSC has to be able to write it (osc.md — leave nothing
    # OSC-written animator-only), and animator type bool because only transitions read it.
    o("  # Preview door: force the Remote branch on the WEARER — their own /Smoothed then shows")
    o(f"  # the stepped decode. Unsynced (zero wire bits), unsaved, {QC}-prefixed so a merged build")
    o("  # instance-prefixes it; drive it by the name OSCQuery serves.")
    o(f"  {QC}/PreviewRemote: {{ type: bool, default: false, vrc: {{ synced: false, saved: false }} }}")
    for ch in channels:
        name, n = ch["name"], ch["bits"]
        if n:
            o(f"  # {name}: {n}-bit{' signed' if ch.get('signed') else ''} channel"
              f" ({n + (1 if ch.get('signed') else 0)} synced bits + free unsynced float)")
            o(f"  {name}: {{ type: float, vrc: {{ synced: false }} }}   # OSC float companion — declared (osc.md: leave nothing OSC-written animator-only)")
            bits, neg = wire_bools(ch)
            for b in bits + neg:
                # Animator type FLOAT, asset type bool: the client writes a bool expression
                # param into a same-named float animator param as 0/1, which is what lets a
                # blend tree read it — the standard binary-param shape (OSCmooth, VRCFT).
                o(f"  {b}: {{ type: float, vrc: {{ type: bool, synced: true, saved: false }} }}")
        else:
            o(f"  # {name}: plain synced float channel (8 wire bits; no bools, no decode)")
            o(f"  {name}: {{ type: float, vrc: {{ synced: true, saved: false }} }}")
        o(f"  {name}/Smoothed: {{ type: float, aap: true }}   # the output consumers bind")
        o(f"  {QC}/{name}/Decoded: {{ type: float, aap: true, scratch: true }}" if n else
          f"  # (bits: 0 — remote smooths {name} directly, no Decoded)")
        for which, tag in (("local", "L"), ("remote", "R")):
            s = side(ch, which)
            if not s["frametime"]:
                o(f"  {QC}/{name}/Lambda{tag}: {{ type: float, default: {fmt(s['lambda'])}, scratch: true }}   # fixed keep, install-tunable")
    for g in gates:
        o(f"  {g}: {{ type: float, vrc: {{ type: bool, synced: true, saved: false }} }}   # gate — consumers weight trees on it")
    if any_ft:
        o(f"  # Frametime rig ({QC}-internal; duplicated into each IsLocal state that compensates)")
        for pn in ("Time", "LastTime", "FrameTime"):
            o(f"  {QC}/{pn}: {{ type: float, aap: true, scratch: true }}")
        o(f"  {QC}/Dummy: {{ type: float, aap: true, scratch: true }}   # divide-idiom weight-sum inflator")
        for which in ("local", "remote"):
            for t in taus_by_side[which]:
                lb = tau_label(t)
                if f"  {QC}/InvTau/{lb}:" not in "\n".join(params):
                    o(f"  {QC}/InvTau/{lb}: {{ type: float, default: {fmt(1.0 / t)}, scratch: true }}   # 1/τ, τ = {fmt(t)} s — install-tunable")
                    o(f"  {QC}/U/{lb}: {{ type: float, aap: true, scratch: true }}")
                    o(f"  {QC}/Keep/{lb}: {{ type: float, aap: true, scratch: true }}")

    def state_lines(which, tag):
        L = []
        o2 = L.append
        ind = "            "
        used_taus = taus_by_side[which]
        if used_taus:
            rig_lines(o2, ind)
            for t in used_taus:
                keep_lines(o2, ind, tau_label(t))
        for ch, s in zip(channels, sides[which]):
            if which == "remote" and ch["bits"]:
                decode_lines(o2, ind, ch)
                input_param = f"{QC}/{ch['name']}/Decoded"
            else:
                input_param = ch["name"]
            keep = (f"{QC}/Keep/{tau_label(s['tau'])}" if s["frametime"]
                    else f"{QC}/{ch['name']}/Lambda{tag}")
            smoother_lines(o2, ind, ch, input_param, keep, which)
        return L

    layer = []
    o = layer.append
    o("  - name: QuantChannel")
    o("    states:")
    o("      \"Local (WD ON)\":")
    o("        motion:")
    o("          tree: direct")
    o("          name: LocalRoot")
    o("          children:")
    layer.extend(state_lines("local", "L"))
    o("        transitions:")
    o("          - { to: \"Remote (WD ON)\", when: [ IsLocal is false ] }")
    o(f"          - {{ to: \"Remote (WD ON)\", when: [ {QC}/PreviewRemote is true ] }}")
    o("      \"Remote (WD ON)\":")
    o("        motion:")
    o("          tree: direct")
    o("          name: RemoteRoot")
    o("          children:")
    layer.extend(state_lines("remote", "R"))
    o("        transitions:")
    o(f"          - {{ to: \"Local (WD ON)\", when: [ IsLocal is true, {QC}/PreviewRemote is false ] }}")
    o(f"    # {QC}/PreviewRemote (unsynced debug door) forces the wearer down the Remote branch and")
    o("    # holds them there; Remote->Local needs IsLocal AND the toggle clear, so a wearer who")
    o("    # flips it off returns to their raw float. A remote is unaffected either way.")
    o("    # Default Remote + mutual IsLocal transitions: correct on frame 1 either way, and")
    o("    # self-correcting if IsLocal lands late. IsLocal never changes mid-session after that.")
    o("    default: \"Remote (WD ON)\"")

    clips = []
    o = clips.append
    for ch in channels:
        s = san(ch["name"])
        o(f"  Sm_{s}_neg: {{ set: {{ {ch['name']}/Smoothed: -1.0 }} }}")
        o(f"  Sm_{s}_pos: {{ set: {{ {ch['name']}/Smoothed: 1.0 }} }}")
        if ch["bits"]:
            D = (1 << ch["bits"]) - 1
            for i in range(ch["bits"]):
                w = (1 << i) / D
                o(f"  Dec_{s}_p{1 << i}: {{ set: {{ {QC}/{ch['name']}/Decoded: {fmt(w)} }} }}")
            if ch.get("signed"):
                for i in range(ch["bits"]):
                    w = (1 << i) / D
                    o(f"  Dec_{s}_n{1 << i}: {{ set: {{ {QC}/{ch['name']}/Decoded: {fmt(-w)} }} }}")
    if any_ft:
        o("  # frametime rig: slope-1 linear ramp (tangents: linear is REQUIRED — flat tangents")
        o("  # stair-step Time and dt reads 0 most frames); huge range outlives any session.")
        o(f"  QC_Time_Ramp: {{ curves: {{ {QC}/Time: {{ tangents: linear, keys: [ [0, 0], [10000000, 10000000] ] }} }} }}")
        o(f"  QC_FrameTime_Pos: {{ set: {{ {QC}/FrameTime: 1.0 }} }}")
        o(f"  QC_FrameTime_Neg: {{ set: {{ {QC}/FrameTime: -1.0 }} }}")
        o(f"  QC_LastTime_Set:  {{ set: {{ {QC}/LastTime: 1.0 }} }}")
        o(f"  Keep_Dummy: {{ set: {{ {QC}/Dummy: 0.0 }} }}")
        done = set()
        for which in ("local", "remote"):
            for t in taus_by_side[which]:
                lb = tau_label(t)
                if lb in done:
                    continue
                done.add(lb)
                o(f"  U_One_{lb}: {{ set: {{ {QC}/U/{lb}: 1.0 }} }}")
                o(f"  Keep_One_{lb}: {{ set: {{ {QC}/Keep/{lb}: 1.0 }} }}")

    manifest = {
        "schema": 1,
        "id": int(c["manifestId"]),
        "revision": int(c["revision"]),
        "channels": [
            {"name": ch["name"],
             "address": "/avatar/parameters/" + ch["name"],
             "bits": ch["bits"],
             "signed": bool(ch.get("signed", False)),
             "floatTau": ch.get("floatTau", 0.0),
             "declaredWidths": {"bools": ch["bits"] + (1 if ch.get("signed") and ch["bits"] else 0)}}
            for ch in channels
        ],
        "gates": [
            {"name": g, "address": "/avatar/parameters/" + g} for g in gates
        ],
    }

    interface = []
    for ch in channels:
        bits, neg = wire_bools(ch)
        interface += [ch["name"]] + bits + neg + [f"{ch['name']}/Smoothed"]
    interface += gates + [SENTINEL]

    return {
        "header": header,
        "params": params,
        "layers": [layer],
        "clips": clips,
        "manifest": manifest,
        "facts": {
            "syncedBits": synced,
            "channelCount": len(channels),
            "interface": interface,
        },
    }


def document(c, controller="QuantChannel_Fx"):
    """The committed controller.yaml as text, plus the build. `main()` writes
    it; `--check` re-derives it and compares against disk. An instance build
    (`index-puppet/`) reuses this frame under its own controller name — the
    frame has one home, so a frame change reaches every build or none."""
    f = build(c)
    L = []
    L.extend(f["header"])
    L.append("")
    L.append("schema: 1")
    L.append("controller: " + controller)
    L.append("basis: mount-root          # no scene bindings; AAP trees only")
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
    L.extend(f["clips"])
    return "\n".join(L) + "\n", f


def manifest_text(f):
    return json.dumps(f["manifest"], indent=2, sort_keys=False) + "\n"


def check_files(document_fn, c, here, prefabs, extra=()):
    """The check body, shared with instance builds: byte-identity of both emitted
    files against disk, and each prefab's globalParams list — which no compile
    reads. `extra` is (condition, message) pairs an instance appends (its registry
    asserts); returns ok rather than exiting so the caller owns the exit code."""
    text, f = document_fn(c)
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond

    print("[document]")
    assert_(document_fn(c)[0] == text, "emission is deterministic across two calls")
    out = os.path.join(here, "controller.yaml")
    if os.path.exists(out):
        with open(out, encoding="utf-8", newline="") as fh:
            assert_(fh.read().replace("\r\n", "\n") == text,
                    "controller.yaml on disk matches CONFIG")
    else:
        assert_(False, f"controller.yaml is missing ({out})")

    print("[manifest]")
    mpath = os.path.join(here, "built", "manifest.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8", newline="") as fh:
            assert_(fh.read().replace("\r\n", "\n") == manifest_text(f),
                    "built/manifest.json on disk matches CONFIG")
    else:
        assert_(False, f"built/manifest.json is missing ({mpath})")
    for ch in f["manifest"]["channels"] + f["manifest"]["gates"]:
        assert_(ch["address"] == "/avatar/parameters/" + ch["name"],
                f"manifest address for {ch['name']} is the checked echo of its name")

    print("[prefab globalParams]")
    # The prefabs carry VRCFury prefix wildcards (`<Set>/*`), not the enumerated
    # interface — adding a channel must not require a prefab edit. Expected list =
    # the interface's name-set prefixes in order of first appearance; `QC/*` is
    # deliberately never among them, so internals stay instance-prefixed.
    want, seen = [], set()
    for n in f["facts"]["interface"]:
        p = n.split("/")[0] + "/*"
        if p not in seen:
            seen.add(p)
            want.append(p)
    for prefab in prefabs:
        path = os.path.join(here, prefab)
        if not os.path.exists(path):
            assert_(False, f"{prefab} is missing")
            continue
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        got, inside = [], False
        for ln in body.splitlines():
            if ln.strip() == "globalParams:":
                inside = True
            elif inside:
                if ln.strip().startswith("- "):
                    got.append(ln.strip()[2:].strip())
                else:
                    break
        assert_(got == want,
                f"{prefab} globalParams == the interface prefix wildcards ({', '.join(want)})")

    for cond, msg in extra:
        assert_(cond, msg)

    print("scope: reproducibility and hand-maintained wiring only — document "
          "structure, prefab behavior and runtime are unverified here")
    print("OK" if ok else "FAILED")
    return ok


def check():
    """Everything the repo gate cannot see, over this root build's files."""
    ok = check_files(document, CONFIG, HERE,
                     ("quant-channel.prefab",
                      os.path.join("demo", "quant-channel-demo.prefab")))
    sys.exit(0 if ok else 1)


def main():
    if "--check" in sys.argv:
        check()
        return
    text, f = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.makedirs(os.path.join(HERE, "built"), exist_ok=True)
    with open(os.path.join(HERE, "built", "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(manifest_text(f))
    facts = f["facts"]
    print(f"wrote controller.yaml + built/manifest.json — {facts['channelCount']} channels, "
          f"{facts['syncedBits']} synced bits, interface = {len(facts['interface'])} names")


if __name__ == "__main__":
    main()
