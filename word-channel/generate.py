#!/usr/bin/env python3
"""word-channel generator: emits controller.yaml from CONFIG below.

Edit CONFIG, rerun (`python generate.py`), recompile built/ — the controller.yaml
committed here is generated output, and the repo gate holds built/ to it, so hand-
editing it desynchronises the document from this generator and from the compiled
controller both. That governs this repo's build only: a consumer calling
build(config) into their own project owns the document it emits, and deviating
there is fine as a commented transform in their build script, never as a silent
edit. The protocol is the VRCFury Parameter
Compressor's (studied from com.vrcfury.vrcfury source; batches advanced on a
0.1 s exit-time plus one guaranteed extra frame, a synced batch index the
receiver routes on, latch double-buffering so a word set applies atomically),
generalized to carry a declared word table, with two hardenings the compressor
lacks, both bought by an emulator-measured failure (see the README's pause
fixture):

1. The index is a batch COUNTER spanning `indexLoops` full loops, not a
   position-in-cycle. A receiver resumed from a culling pause slips a mixed
   apply only when the counter aliased across the whole pause AND it froze in
   a non-tail state: P ~ (2/period) * (batchCount-1)/batchCount per resume,
   where period = batchCount * indexLoops. A finite counter cannot detect an
   unbounded pause deterministically; width buys probability, and the
   residual is declared, not hidden.
2. `group:` pins words into one batch, so an aliased resume can only mix WHOLE
   words from two real snapshots — never split one word's limbs into garbage.
   A group may span number and bool words (a 12-bit value = one byte word +
   4 bool words): the packer pins both kinds to the same batch index, padding
   bool batches forward when needed (a padded slot costs nothing — the wire
   params exist every tick regardless), and refuses when declaration order
   makes alignment impossible.

Under `atomic: batch` the receiver re-acquires from Lost at ANY exact counter
value, not only a loop head: applies are per-batch and the counter alone names
the batch, so a missed sync tick costs ~one batch of staleness instead of a
full loop. `set` keeps loop-head-only re-acquisition — a whole-table apply
needs one coherent loop.

VRLabs Custom-Object-Sync (MIT) is the studied ancestor for the receive side's
other trap: its multi-frame receiver decode walks are what a culling pause
interrupts. Here every receive state decodes in one frame; the only multi-frame
structure is the batch loop itself, re-derived from the wire counter alone.

Wire cost = indexBits + 8*numberSlots + boolSlots synced bits.
State count = 3*batchCount*indexLoops + 2, independent of word widths.

Fragment mode, for a generator composing this channel into its own controller
(import via importlib.util.spec_from_file_location — the folder name is not an
identifier): `build(config)` returns the emitted pieces without writing a file:

    {"header":  [comment lines describing the wire],
     "params":  [lines for a `parameters:` block; includes `IsLocal` — the
                 importer dedupes it against its own],
     "layers":  [blocks, one per layer, each a list of lines indented for a
                 `layers:` block],
     "clips":   [clip lines indented for a `clips:` block — the block's own key
                 and any framing are the importer's, empty when nothing
                 assembles],
     "facts":   {batchCount, period, indexBits, wireBits, payloadBits,
                 cycleSeconds, numberBatches, boolBatches, groupBatch}}

The importer owns the document frame (schema/controller/basis/role/defaults)
and merges these under its own sections; `main()` below is itself the first
consumer and the committed config's byte-identity check.
"""

import os

CONFIG = {
    # Param prefix. All params live under this; the FullController's
    # globalParams exposes only the interface set (words + Cycle).
    "channel": "WordChannel",
    # Wire slots per batch: each number slot is one synced 8-bit int, each
    # bool slot one synced bit. More slots = fewer batches = lower latency,
    # at more synced bits.
    "numberSlots": 2,
    "boolSlots": 2,
    # How many loops one counter period spans (>=1). Each extra loop divides
    # the pause-alias probability and usually costs one index bit + a state
    # row per batch. Buys nothing under `atomic: batch` — no pause-alias
    # artifact exists there and Lost re-acquires at any counter value, so a
    # wider counter only costs bits and states. Leave it 1 there.
    "indexLoops": 2,
    # Seconds each batch holds before the guaranteed extra frame. 0.1 is
    # VRChat's measured network tick; 0.2 is the community-safe fallback if
    # in-game Cycle rate shows the tick intermittently outrun (README).
    "batchSeconds": 0.1,
    # Apply discipline on the receiver:
    #   set   — latch double-buffer; the whole word table applies atomically at
    #           each loop tail (VRCFury's discipline). Residual: a culling
    #           pause that resumes counter-aliased slips ONE apply mixing whole
    #           words from the two bracketing snapshots (measured ~2/period
    #           per resume), corrected at the next apply.
    #   batch — each batch applies directly on receipt; no latches. Coherence
    #           unit is the batch (= any group), always; cross-batch values
    #           may lag each other up to one loop, pause or no pause, and no
    #           pause-specific artifact exists. Lost re-acquires at any
    #           counter value (docstring), so a missed tick costs ~one batch.
    # Toggle-bus payloads want set (partial outfits flicker otherwise);
    # grouped measurement payloads usually want batch.
    "atomic": "set",
    # Number words, packed into number slots per batch, in declared order.
    #   kind byte  — carried as a float holding an integral 0..255
    #   kind float — carried as a float in [min,max], quantized to 255 wire
    #                steps (an 8-bit synced float's own resolution)
    #   group      — words sharing a group label are pinned into ONE batch
    #                (declare them adjacent; group size <= numberSlots).
    #                A label shared with bool words pins both kinds to the
    #                same batch index (docstring).
    "numbers": [
        {"name": "Pos/Hi", "kind": "byte", "group": "pos"},
        {"name": "Pos/Lo", "kind": "byte", "group": "pos"},
        {"name": "Level", "kind": "float", "min": -1, "max": 1},
    ],
    # Bool words, boolSlots per batch: a bare name, or {"name":..,"group":..}
    # to pin into a number group's batch.
    "bools": ["Flag/A", "Flag/B", "Flag/C", "Flag/D"],
    # Reassembly demos: an always-on Direct-tree AAP computing hi*256+lo, the
    # worked idiom for consuming two byte limbs as one 16-bit word.
    "assemble": [
        {"name": "Pos/Assembled", "hi": "Pos/Hi", "lo": "Pos/Lo"},
    ],
}


def norm_bool(b):
    return {"name": b} if isinstance(b, str) else b


def group_runs(items, slots, kind_label):
    """Split declared items into indivisible runs (a run = one group or one
    ungrouped item), refusing non-adjacent groups and runs over the slot
    count."""
    seen_groups = set()
    runs = []
    i = 0
    while i < len(items):
        g = items[i].get("group")
        if g is None:
            runs.append([items[i]])
            i += 1
            continue
        if g in seen_groups:
            raise SystemExit(f"REFUSE: group '{g}' is not declared adjacent")
        seen_groups.add(g)
        run = []
        while i < len(items) and items[i].get("group") == g:
            run.append(items[i])
            i += 1
        if len(run) > slots:
            raise SystemExit(
                f"REFUSE: group '{g}' has {len(run)} {kind_label} words but "
                f"only {slots} {kind_label} slots — a group must fit one batch")
        runs.append(run)
    return runs


def pack_runs(runs, slots):
    """First-fit runs into batches in declared order; returns (batches,
    group->batch index)."""
    batches, cur, where = [], [], {}
    for run in runs:
        if len(cur) + len(run) > slots:
            batches.append(cur)
            cur = []
        g = run[0].get("group")
        if g is not None:
            where[g] = len(batches)
        cur.extend(run)
    if cur:
        batches.append(cur)
    return batches, where


def pack_bools_pinned(runs, slots, pin):
    """Pack bool runs in declared order, padding batches forward so a run
    whose group is pinned (by the number packing) lands at that batch index.
    Deterministic; refuses when order makes the pin unreachable."""
    batches, cur, where = [], [], {}
    for run in runs:
        g = run[0].get("group")
        target = pin.get(g) if g is not None else None
        if len(cur) + len(run) > slots:
            batches.append(cur)
            cur = []
        if target is not None:
            at = len(batches)
            if at > target:
                raise SystemExit(
                    f"REFUSE: bool group '{g}' cannot reach number batch "
                    f"{target + 1} (the next free bool batch is {at + 1}) "
                    "— declare it earlier or widen boolSlots")
            while len(batches) < target:
                batches.append(cur)
                cur = []
        if g is not None:
            where[g] = len(batches)
        cur.extend(run)
    if cur:
        batches.append(cur)
    return batches, where


def chunk(lst, n):
    if n <= 0:
        return []
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def index_bits(period):
    # ids 1..period; 0 reserved for "nothing sent yet"
    bits = 1
    while (1 << bits) < period + 1:
        bits += 1
    return bits


def id_pattern(sync_id, bits):
    # MSB-first: Idx0 is the most significant bit
    return [bool(sync_id & (1 << (bits - 1 - i))) for i in range(bits)]


def cond(param, val):
    return f"{param} is {'true' if val else 'false'}"


def lost_fallback_rungs(cur_bits, next_bits, idx_names):
    """DNF of NOT(cur) AND NOT(next) over the index bits, contradictions
    pruned, subsumed rungs dropped — the wire-desync escape to Lost."""
    rungs = []
    seen = set()
    for i, ci in enumerate(cur_bits):
        for j, nj in enumerate(next_bits):
            want = {}
            ok = True
            for (bit, v) in ((i, not ci), (j, not nj)):
                if bit in want and want[bit] != v:
                    ok = False
                    break
                want[bit] = v
            if not ok:
                continue
            key = frozenset(want.items())
            if key in seen:
                continue
            seen.add(key)
            rungs.append(want)
    keys = [frozenset(r.items()) for r in rungs]
    kept = [r for r, k in zip(rungs, keys)
            if not any(o < k for o in keys)]
    kept.sort(key=lambda r: (len(r), sorted(r.items())))
    return [[cond(idx_names[b], v) for b, v in sorted(r.items())] for r in kept]


def build(config):
    """Fragment entry point: compute the channel and return its emitted pieces
    (docstring above carries the contract). `main()` assembles the same pieces
    into the committed controller.yaml."""
    c = config
    p = c["channel"]
    numbers = c["numbers"]
    bools = [norm_bool(b) for b in c["bools"]]
    nslots, bslots = c["numberSlots"], c["boolSlots"]
    loops = c.get("indexLoops", 2)
    if loops < 1:
        raise SystemExit("REFUSE: indexLoops must be >= 1")
    batch_seconds = c.get("batchSeconds", 0.1)
    atomic = c.get("atomic", "set")
    if atomic not in ("set", "batch"):
        raise SystemExit("REFUSE: atomic must be 'set' or 'batch'")
    if numbers and nslots < 1:
        raise SystemExit("REFUSE: number words declared but numberSlots < 1 — they would silently never replicate")
    if bools and bslots < 1:
        raise SystemExit("REFUSE: bool words declared but boolSlots < 1 — they would silently never replicate")
    nbatches, ngroup = pack_runs(group_runs(numbers, nslots, "number"), nslots)
    bbatches, bgroup = pack_bools_pinned(
        group_runs(bools, bslots, "bool"), bslots, ngroup)
    batch_count = max(len(nbatches), len(bbatches))
    if batch_count < 2:
        raise SystemExit(
            "REFUSE: the word table fits in the slots in one batch — plain "
            "synced params need no channel. Shrink the slots or grow the table.")
    group_batch = dict(ngroup)
    group_batch.update(bgroup)
    period = batch_count * loops
    bits = index_bits(period)
    idx = [f"{p}/Wire/Idx{i}" for i in range(bits)]
    nwire = [f"{p}/Wire/Num{i}" for i in range(nslots)]
    bwire = [f"{p}/Wire/Bool{i}" for i in range(bslots)]
    wire_bits = bits + 8 * nslots + bslots
    payload_bits = 8 * len(numbers) + len(bools)
    cycle_s = batch_count * (batch_seconds + 1 / 60)  # at 60 fps; the Extra state costs one full frame

    def latch(name):
        return f"{p}/Latch/{name}"

    def batch_words(b):
        ns = nbatches[b] if b < len(nbatches) else []
        bs = [x["name"] for x in (bbatches[b] if b < len(bbatches) else [])]
        return ns, bs

    header = []
    o = header.append
    o("# GENERATED by generate.py — edit its CONFIG and rerun; never hand-edit this file.")
    o("# word-channel: a multiplexing transport for a declared word table over a narrow")
    o(f"# synced channel: {bits} index bit{'s' if bits > 1 else ''} + {nslots} synced int slot{'s' if nslots != 1 else ''} + {bslots} synced bool slot{'s' if bslots != 1 else ''}")
    nbyte = sum(1 for w in numbers if w["kind"] == "byte")
    nfloat = len(numbers) - nbyte
    kinds = " + ".join(x for x in [f"{nbyte} byte{'s' if nbyte != 1 else ''}" if nbyte else "",
                                   f"{nfloat} ranged float{'s' if nfloat != 1 else ''}" if nfloat else "",
                                   f"{len(bools)} bool{'s' if len(bools) != 1 else ''}" if bools else ""] if x)
    o(f"# = {wire_bits} synced bits carrying {payload_bits} bits of words ({kinds})")
    o(f"# in {batch_count} batches, atomic={atomic} (~{cycle_s:.2f}s full refresh; two loops worst case after a dropped")
    o("# snapshot). Protocol provenance: VRCFury Parameter Compressor, hardened — generate.py's")
    o("# docstring carries the design; the README's pause fixture carries the measured failure")
    o("# the hardenings answer.")
    o("#")
    o(f"# Sender (IsLocal): a {period}-value batch counter ({loops} loop{'s' if loops > 1 else ''} of {batch_count} batches) walks Send states;")
    o("# the first batch of each loop latches the whole table minus its own batch (its own")
    o("# words go to the wire live, so no driver reads a latch it wrote the same frame —")
    o(f"# VRCFury's trick), then each batch holds {batch_seconds}s plus one guaranteed frame (the Extra")
    o("# states; an exit-time alone can fire early and outrun the sync tick, losing a")
    if atomic == "batch":
        o("# snapshot). Receiver (!IsLocal): routes purely on the wire counter — re-acquires")
        o("# from Lost at ANY exact counter value (applies are per-batch and the counter alone")
        o("# names the batch, so a missed tick costs ~one batch of staleness, not a loop),")
        o("# advances only on the exact successor value, falls to Lost on any other, and")
        o("# applies each batch directly on receipt (Cycle increments at each loop tail: the")
        o("# freshness signal). No latches exist; the coherence unit is the batch, so a pause")
        o("# can never mix or split a group.")
    else:
        o("# snapshot). Receiver (!IsLocal): routes purely on the wire counter — enters only at")
        o("# a loop head from Lost, advances only on the exact successor value, falls to Lost on")
        o("# any other, and applies the buffered set atomically at each loop tail (Cycle")
        o("# increments there: the freshness signal). A receiver resumed from a culling pause")
        o("# re-derives its position from the counter; only a pause spanning exactly the counter")
        o(f"# period (P ~ 1/{period} per resume) can slip one mixed apply through, whole words only,")
        o("# corrected at the next apply.")

    params = []
    o = params.append
    o("  IsLocal: bool              # VRC built-in")
    o(f"  {p}/True: {{ type: bool, default: true, scratch: true }}   # constant for +1-frame hops")
    o("  # Interface — the word table. Producers write these on the wearer; consumers read")
    o("  # them on every client. Unsynced (the wire below carries them); in the params asset")
    o("  # for legibility and OSC reach.")
    for w in numbers:
        if w["kind"] == "byte":
            o(f"  {w['name']}: float            # byte word: integral 0..255")
        else:
            o(f"  {w['name']}: float            # float word: [{w['min']},{w['max']}], 255 wire steps")
    for b in bools:
        o(f"  {b['name']}: bool")
    o(f"  {p}/Cycle: float           # remote freshness: +1 per loop tail (float: driver Add clips an Int at 255)")
    if atomic == "batch":
        o("  # Lost re-acquires at any counter value here, so a receiver can enter AT a tail and")
        o("  # take its first increment one batch later: Cycle >= 2 is the earliest proof a whole")
        o("  # word table has been received, Cycle >= 1 only proves the wire is moving.")
    o("  # Wire — the only synced params.")
    for i in idx:
        o(f"  {i}: {{ type: bool, vrc: {{ synced: true, saved: false }} }}")
    for n in nwire:
        o(f"  {n}: {{ type: int, vrc: {{ synced: true, saved: false }} }}")
    for b in bwire:
        o(f"  {b}: {{ type: bool, vrc: {{ synced: true, saved: false }} }}")
    if atomic == "set":
        o("  # Latches — the double buffer, both directions. Scratch: internal residue.")
        for w in numbers:
            o(f"  {latch(w['name'])}: {{ type: float, scratch: true }}")
        for b in bools:
            o(f"  {latch(b['name'])}: {{ type: bool, scratch: true }}")
    for a in c["assemble"]:
        o(f"  {a['name']}: {{ type: float, aap: true }}   # hi*256+lo, one-frame lag")

    sync = []
    o = sync.append
    o(f"  - name: {p}/Sync")
    o("    states:")
    o("      Split:")
    o("        motion: ~")
    o("        transitions:")
    o("          - { to: Lost, when: [ IsLocal is false ] }")
    o("          - { to: Send0, when: [ IsLocal is true ] }")
    # Sender states: one per counter value
    for s in range(period):
        b = s % batch_count
        ns, bs = batch_words(b)
        sync_id = s + 1
        pat = id_pattern(sync_id, bits)
        words_txt = ", ".join([w["name"] for w in ns] + bs) or "(index only)"
        o(f"      # counter {sync_id}/{period} = batch {b + 1}/{batch_count}: {words_txt}")
        o(f"      Send{s}:")
        o("        motion: ~")
        o("        behaviours:")
        if b == 0 and atomic == "set":
            own = {w["name"] for w in ns} | set(bs)
            latch_copies = [(latch(w["name"]), w["name"]) for w in numbers if w["name"] not in own]
            latch_copies += [(latch(x["name"]), x["name"]) for x in bools if x["name"] not in own]
            if latch_copies:
                o("          # coherent snapshot: latch every word this batch does not itself send")
                o("          - driver:")
                o("              copy:")
                for d, src in latch_copies:
                    o(f"                {d}: {src}")
        o("          - driver:")
        o("              set:")
        for k, name in enumerate(idx):
            o(f"                {name}: {1 if pat[k] else 0}")
        if ns or bs:
            o("              copy:")
        for k, w in enumerate(ns):
            src = w["name"] if (b == 0 or atomic == "batch") else latch(w["name"])
            if w["kind"] == "float":
                o(f"                {nwire[k]}: {{ source: {src}, sourceMin: {w['min']}, sourceMax: {w['max']}, destMin: 0, destMax: 254 }}")
            else:
                o(f"                {nwire[k]}: {src}")
        for k, x in enumerate(bs):
            src = x if (b == 0 or atomic == "batch") else latch(x)
            o(f"                {bwire[k]}: {src}")
        o("        transitions:")
        o(f"          - {{ to: Extra{s}, when: [], exitTime: {batch_seconds} }}   # empty state: exitTime is literal seconds")
        o(f"      Extra{s}:")
        o("        motion: ~")
        o("        transitions:")
        o(f"          - {{ to: Send{(s + 1) % period}, when: [ {p}/True is true ] }}   # conditional hop = the guaranteed +1 frame")
    # Receiver states: one per counter value
    o("      Lost:")
    o("        motion: ~")
    o("        transitions:")
    if atomic == "batch":
        for s in range(period):
            pat = id_pattern(s + 1, bits)
            conds = ", ".join(cond(idx[k], pat[k]) for k in range(bits))
            note = "   # re-acquire at any exact counter value (batch applies need no coherent loop)" if s == 0 else ""
            o(f"          - {{ to: Recv{s}, when: [ {conds} ] }}{note}")
    else:
        for lp in range(loops):
            head_id = lp * batch_count + 1
            pat = id_pattern(head_id, bits)
            conds = ", ".join(cond(idx[k], pat[k]) for k in range(bits))
            o(f"          - {{ to: Recv{lp * batch_count}, when: [ {conds} ] }}   # re-acquire only at a loop head")
    for s in range(period):
        b = s % batch_count
        ns, bs = batch_words(b)
        last = b == batch_count - 1
        cur = id_pattern(s + 1, bits)
        nxt_s = (s + 1) % period
        nxt = id_pattern(nxt_s + 1, bits)
        o(f"      Recv{s}:")
        o("        motion: ~")
        o("        behaviours:")
        o("          - driver:")
        o("              copy:")
        for k, w in enumerate(ns):
            dst = w["name"] if (last or atomic == "batch") else latch(w["name"])
            if w["kind"] == "float":
                o(f"                {dst}: {{ source: {nwire[k]}, sourceMin: 0, sourceMax: 254, destMin: {w['min']}, destMax: {w['max']} }}")
            else:
                o(f"                {dst}: {nwire[k]}")
        for k, x in enumerate(bs):
            dst = x if (last or atomic == "batch") else latch(x)
            o(f"                {dst}: {bwire[k]}")
        if last:
            if atomic == "set":
                o("                # atomic apply: the earlier batches' buffered words land with this batch's")
                for j in range(batch_count - 1):
                    jns, jbs = batch_words(j)
                    for w in jns:
                        o(f"                {w['name']}: {latch(w['name'])}")
                    for x in jbs:
                        o(f"                {x}: {latch(x)}")
            o("          - driver:")
            o(f"              add: {{ {p}/Cycle: 1 }}")
        o("        transitions:")
        adv = ", ".join(cond(idx[k], nxt[k]) for k in range(bits))
        o(f"          - {{ to: Recv{nxt_s}, when: [ {adv} ] }}")
        for rung in lost_fallback_rungs(cur, nxt, idx):
            o(f"          - {{ to: Lost, when: [ {', '.join(rung)} ] }}")
    o("    default: Split")
    o("    layout:")
    o("      nodes:")
    o("        Split:  [30, 180]")
    o("        Lost:   [510, 180]")
    for s in range(period):
        y = 260 + 90 * s
        o(f"        Send{s}: [-330, {y}]")
        o(f"        Extra{s}: [-570, {y}]")
        o(f"        Recv{s}: [270, {y}]")
    o("      entry: [50, 120]")
    o("      any:   [50, 40]")
    o("      exit:  [50, 80]")

    layers = [sync]
    if c["assemble"]:
        asm = []
        o = asm.append
        o(f"  - name: {p}/Assemble")
        o("    states:")
        o("      Assemble:")
        o("        motion:")
        o("          tree: direct")
        o("          name: AssembleSum")
        o("          children:")
        for a in c["assemble"]:
            base = a["name"].replace("/", "_").lower()
            o(f"            - {{ clip: asm_{base}_hi, directWeight: {a['hi']} }}")
            o(f"            - {{ clip: asm_{base}_lo, directWeight: {a['lo']} }}")
        o("    default: Assemble")
        layers.append(asm)

    clips = []
    if c["assemble"]:
        o = clips.append
        for a in c["assemble"]:
            base = a["name"].replace("/", "_").lower()
            o(f"  asm_{base}_hi: {{ set: {{ {a['name']}: 256 }} }}")
            o(f"  asm_{base}_lo: {{ set: {{ {a['name']}: 1 }} }}")

    return {
        "header": header,
        "params": params,
        "layers": layers,
        "clips": clips,
        "facts": {
            "batchCount": batch_count,
            "period": period,
            "indexBits": bits,
            "wireBits": wire_bits,
            "payloadBits": payload_bits,
            "cycleSeconds": cycle_s,
            "numberBatches": nbatches,
            "boolBatches": bbatches,
            "groupBatch": group_batch,
        },
    }


def main():
    c = CONFIG
    p = c["channel"]
    f = build(c)
    L = []
    L.extend(f["header"])
    L.append("")
    L.append("schema: 1")
    L.append(f"controller: {p}_Fx")
    L.append("basis: mount-root          # no scene bindings; drivers + AAP trees only")
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
    if f["clips"]:
        L.append("# Reassembly endpoints: each writes the AAP scaled per limb; the Direct tree's")
        L.append("# weight (the limb param, 0..255) multiplies it, so the sum is hi*256 + lo.")
        L.append("clips:")
        L.extend(f["clips"])
    text = "\n".join(L) + "\n"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controller.yaml")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    facts = f["facts"]
    print(f"wrote {out}: atomic={c.get('atomic', 'set')}, {facts['batchCount']} batches x {c.get('indexLoops', 2)} loops (period {facts['period']}), "
          f"{facts['wireBits']} wire bits, {facts['payloadBits']} payload bits, ~{facts['cycleSeconds']:.2f}s cycle @60fps, "
          f"mixed-apply P~{2 * (facts['batchCount'] - 1) / facts['batchCount'] / facts['period']:.2f}/resume")


if __name__ == "__main__":
    main()
