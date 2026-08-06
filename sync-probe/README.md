# sync-probe — in-game synced-parameter delivery probe (Module)

Measures what the shipping client actually delivers of another player's synced parameters — the delivery schedule, loss, downshift, pauses, and snapshot coherence — with no OSC monitoring of any remote client: the wearer's remote copy relays what it received onto world-anchored contacts, and the observing client's own receivers mirror that into its OSC surface. Two clients each wear one copy and measure each other symmetrically; the packaged novelty is the analog contact relay that gets a remote copy's received bytes out same-frame, for **49 synced bits** (four rate-ladder counters, a torn-snapshot pair, one reset bool).

This is an instrument, not a capability: it exists to settle `word-channel`'s `BATCH_SECONDS`, whether VRCFury's extra-frame guard matters in the shipping client, whether params downshift with distance, and whether snapshot coherence holds — each with a measured in-game number. Wear it, log it, read the answers off the log.

## Provenance

The rate-ladder senders are `word-channel`'s Send/Extra cadence idiom verbatim (itself the VRCFury Parameter Compressor's, source-studied); the bare 0.1 s rung deliberately strips the guard hop that idiom exists for — the experimental deviation this probe tests, produced by this entry's own generator rather than any change to `word-channel`. The world park, face-mode analog readout, edge-guard discipline, and calibration approach descend from `object-sync`'s measured rig; the frametime rig is lifted from `blendtree-math`. VRLabs Custom-Object-Sync (MIT, © VRLabs) is those entries' studied ancestor and is credited through them.

## Interface

- **Params in**: `SyncProbe/Reset` (bool, synced, unsaved) — the only control: while true, tallies clear on every client and stride baselines re-stage. The menu button drives it; an OSC writer may drive the bare name directly.
- **Params out, synced (the instruments, 48 bits)**: `SyncProbe/R05|R10B|R10G|R20` (Int counters: 0.05 s, 0.1 s bare, 0.1 s guarded, 0.2 s cadences), `SyncProbe/TornA|TornB` (Int pair, B = 255 − A written in one driver).
- **Params out, unsynced (the OSC surface an external logger records; all on `globalParams`, so the names survive the VRCFury rewrite)**: `SyncProbe/Rx/{R05,R10B,R10G,R20,TornA,TornB,ScanVal,ScanSel,ScanStrobe,HbA,HbB,Prox}` (receiver mirrors of the *other* player's relay, floats 0..1), `SyncProbe/FpsBand` (Int 0–8, this client's frame-rate band — edges in `generate.py` CONFIG).
- **Menu**: one `Reset` button in a `SyncProbe` submenu, merged from the built menu asset.
- **Seam**: VRCFury `FullController` on the prefab root (`basis: mount-root` ↔ `rootBindingsApplyToAvatar: 0` — every clip binding paths through the module's own `Rig`). `globalParams` is exactly the OSC surface plus the wire names above; everything else takes instance prefixes.
- **Dependencies**: **compose `anti-cull` alongside** — a view-culled remote copy stops relaying, and a downshift you measure must not be a culled animator. Distance-hide is not defeatable: turn it off in client settings during runs. The measurement needs exactly **two** clients wearing this build in the instance; more wearers do not break the contacts (unique tags, `allowOthers` receivers read the strongest sender per tag) but make readings ambiguous about whose delivery is being relayed.
- **Required assets**: `assets/World.prefab` — the never-instantiated constraint source that makes the rig frame the same world origin on every client. Do not instantiate or delete it.

## Before you compose it

- **Single-instance per avatar**: the twelve collision tags (`P12…`) are fixed strings VRCFury's prefixing does not reach; a second copy needs a regeneration with its own tags.
- **Both accounts wear the same build.** The relay is symmetric — each client's receivers read only the other player's senders (`allowSelf: false`, receivers `localOnly`) — so one avatar serves both roles.
- **Reset before every measurement segment.** A fresh observer's first delivery lands as one spurious `Big` per rung (stride baseline acquisition); reset clears it, and the level-held reset also re-stages baselines so releasing it never mints another.

## How it works

**Senders (wearer's client only).** Each rung is a state loop publishing a local float counter to its synced Int and then incrementing, as two driver behaviours in list order — a driver `Add` clips a synced Int at 255, so wrap is an explicit state that publishes 0 by `Set` and re-seeds the counter. The three guarded rungs dwell `exitTime` seconds then take one conditional-hop frame (the compressor's guard); the bare rung is a pure exit-time flip-flop whose wrap states are themselves ticks, so no conditional hop exists anywhere on its path. The torn pair rides two complementary counters written by one driver each 0.1 s tick — a `convertRange` inversion was measured off by one (205 → 49; the float remap truncates on the Int copy), so complement-by-construction replaced it. `FpsBand` is a threshold ladder over the frametime rig, giving the logger this client's own frame clock as a declared Int.

**Relay (the remote copy, running on the observing client).** A pump layer driver-copies the six wire Ints to floats every frame (a blend tree reads an Int as 0), and one Direct tree drives each relay sender's local z as `z = 0.15 + value·0.02` — analog position encoding, one contact channel per byte, same-frame coherent because the value rides a tree *weight* with no dependent AAP hops. A per-bit binary relay was rejected by arithmetic before it was built: every AAP hop costs one frame (`docs/gimmicks.md`), so an 8-stage bit cascade settles incoherently over ~15 frames, longer than the 6-frame delivery interval it would have to relay. Face-mode box receivers read the senders float32-exact (`object-sync` measured the primitive at 12 bits per channel; this uses 8), and the mirrors reach OSC as declared unsynced params — the live client's OSC emission of *undeclared* animator params is unreliable (`docs/osc.md`), so nothing here is animator-only.

**Decoding a mirror.** With this rig's geometry (box size 6 face-forward at cell z 2.925, sender sphere r 0.05, rest 0.15, step 0.02), a receiver value `p` decodes as **`count = 300·p − 13.75`** — emulator-verified exact against the sender's true value on every channel. `ScanSel` uses step 0.24: **`register = (6·p − 0.275) / 0.24`**. A mirror at exactly 0 is "not acquired" (relay collapse or out of range), never a legal value — the rest offset guarantees count 0 reads as p ≈ 0.046.

**Tallies (the on-board cross-check).** Per rung, a Direct subtree computes `Delta = Cur − Prev` and a transition ladder buckets each change as stride 1 / 2 / 3 / 4–15 / big-jump (≥16), with the mod-256 wrap ranges as explicit OR rungs; a driver adds the tally (floats — unsynced, never clipped) and re-stages `Prev`. The torn tally counts a `TornA + TornB ≠ 255` persisting ≥3 frames (a real torn tick persists ~a full tick; a render-frame boundary does not). Tallies exist to catch a lying relay: if post-hoc stride counts from the live streams disagree with them, the relay lied. Two declared bounds: classification takes ~5 frames, so the 0.05 s rung's tally is **advisory** (its truth is the live relay stream, which has full per-frame throughput); and a pause's resume can occasionally land one rung's jump in S4 instead of Big (observed once in emulator testing, mechanism unpinned) — read S4+Big jointly as "non-small stride" when cross-checking pauses.

**Scan bus.** A cycler round-robins the 21 tally registers (5 buckets × 4 rungs + torn count) onto three analog lines — value (saturating at 255 via the copy's range clamp), select index, and a strobe that flips as each register latches, so a logger trusts value/select only between strobe edges. One full sweep is ~31.5 s at the 1.5 s dwell.

**Heartbeat, the anomaly classifier.** A two-state flip-flop of complementary GO-active clips — pure local time, zero network dependence — keeps exactly one of two Constant senders active. At the observer: heartbeat clean + counters skipping = genuine sync loss; both mirrors frozen with exactly one high = animator pause, not loss (emulator-verified under an induced pause); both zero = relay collapse (anchor broke); erratic = contact trouble, discard the interval.

**Proximity rider.** One proximity pair on the avatar roots: the observer's radius-3 receiver reads the other player's sender, giving cross-player analog contact fidelity against the measured `1 − dist/radius` model plus a free close-range inter-player distance channel. Nothing depends on it.

Empirical constants (change any of these only with a re-measurement; the authored values live in `generate.py` CONFIG and the prefab):

| Constant | Value | Why |
|---|---|---|
| Relay step / rest | 0.02 m per count, 0.15 m rest | 255 counts end at 5.25 m inside a size-6 face receiver with ≥0.15 m guard both ends — 0 stays unambiguously "not acquired" (`object-sync`'s edge-guard rationale) |
| Decode formula | `count = 300·p − 13.75` | geometry above + the 0.05 m sender-sphere nearest-surface bias; emulator-verified exact (225 → 225, torn 167/88, scan 5/255) |
| Big-jump threshold | stride ≥ 16 | separates pause/cull-resume (expected) from loss (the measurement) — 1.6 s at a 0.1 s tick |
| Torn persistence | 3 frames | a real torn tick persists ~a full network tick; a render-frame boundary is 1 frame |
| Scan dwell | 1.5 s/register | several contact-latency periods per register at the observer's worst frame rate |
| Heartbeat half-period | 0.5 s | slow enough to read over contacts, fast enough to date an anomaly within a second |
| Receiver cells | ≤ 8 receivers per 5×5×5 broadphase cell, two sites 10 m apart | the ~24-receiver cross-player misread bug (`docs/runtime.md` §Contacts); receivers are `localOnly`, so only the observing client's own 8 exist per cell |
| Rig park | source-space offset (15, 25, 10) | world-fixed on every client (a constraint's own `PositionOffset` rides the wearer's yaw — `docs/runtime.md` §Constraints); elevated to clear floor geometry; |v| ≈ 31 m, inside the ~50 m world-origin bound against speculative world-bounds culling of contacts |

## Rig

The prefab is hand-maintained against this section; clip bindings name these paths verbatim, so a rename silently unbinds the relay.

    SyncProbe                    root — VRCFury FullController (FX, rootBindingsApplyToAvatar: 0),
    │                            menus row → built menu (prefix SyncProbe), globalParams = the OSC surface
    ├─ Rig                       VRCParentConstraint → assets/World.prefab transform, Locked, IsActive;
    │  │                         park on source0's ParentPositionOffset (15, 25, 10)
    │  ├─ R05 R10B R10G R20      rung cells at x 0, y 0/1.2/2.4/3.6
    │  │    S                    sphere sender r 0.05, tag P12<rung>, z animated 0.15..5.25
    │  │    X                    box receiver (1,1,6) at z 2.925, face mode, Proximity, localOnly,
    │  │                         allowSelf 0, allowOthers 1 → SyncProbe/Rx/<rung>
    │  ├─ Torn/A Torn/B          same S/X pair shape, x 10, y 0/1.2, tags P12TornA/P12TornB
    │  ├─ Scan/Val Scan/Sel      same S/X pair shape, x 10, y 2.4/3.6 (Sel step 0.24)
    │  ├─ Scan/SStrobe+XStrobe   scale-driven sphere sender + Constant box (1,1,1), tag P12Strobe
    │  └─ Hb/SA SB + XA XB       GO-active clip-driven senders + Constant receivers, tags P12HbA/B
    ├─ ProxS                     sphere sender on the root (rides the wearer), tag P12Prox
    └─ ProxX                     Proximity sphere receiver r 3, allowOthers → SyncProbe/Rx/Prox

Every animated sender sits under its own offset-carrying parent and is animated in z alone — the relay's rest clip writes each sender's full local vector, so a sender authored at a lateral offset would be animated back to y 0, out of its receiver's box (measured: `ScanSel` read 0 while `ScanVal` read exact).

## Verifying the install

Cheapest observable, one play session with av3emu: spawn a non-local clone (`NonLocalSyncInterval = 0.1` — the default 0.2 halves the wire rate), set its Animator to AlwaysAnimate, and the local avatar's `Rx` mirrors must decode to the clone's own counter values via `count = 300·p − 13.75`, exactly. A mirror stuck at 0 with the clone's senders visibly moving is the receiver not acquiring (check the world park: `Rig` must sit at exactly (15, 25, 10) with the avatar elsewhere and facing off-axis). Wire counters advancing on the wearer with `Rx` all 0 and no clone is correct — receivers only read another player.

What the emulator structurally cannot show for this entry: **real network loss** — av3emu's sampler is lossless, so stride-2+ tallies here are sampling effects (the bare rung outrunning the 0.1 s sampler — 109 stride-2 skips against the guarded rung's 1 in one 45 s run — is the guard's *mechanism* made visible, not a network measurement); the shipping client's delivery to a distance-hidden avatar's paused animator; and everything the probe exists to measure in-game, which lands in the operator's runbook, not here. The emulator's OSC socket also cannot open while a live VRChat client holds UDP 9000 on the same machine — `EnableAvatarOSC` self-clears; close the client or take the OSC leg to it directly.

## Rebuilding

`generate.py` → `controller.yaml` → `CompileController` → `built/`. The prefab is hand-maintained against §Rig; regenerate `built/` as a unit over the committed `.meta`s whenever CONFIG changes.
