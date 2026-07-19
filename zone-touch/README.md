# zone-touch — N-zone touch reaction, sync-only-the-divergent-outcome (Module tier)

Three touch zones, one reaction machine, **2 synced bits**. Every client's copy of the avatar
senses the toucher with its own receivers (`localOnly: 0`, `allowSelf`+`allowOthers`), so the
common-case reaction reproduces on all clients at zero synced bits and zero latency; the two bits
are spent on what remotes genuinely cannot re-derive — the enable (off must silence *remote*
sensing too) and the outcome of a local random roll selecting the rare special reaction. Remotes
re-arm on the special bool's **falling edge**: the wearer's dwell is the single clock, no remote
timers to skew, late-join-safe because both bits are unsaved default-0.

**Provenance:** a private production avatar's headpat mechanism, generalized (sync-only-the-divergent-outcome
+ level-handshake rearm, `gimmicks.md` §Contacts). The vendor baseline it corrects is the
commercial touch-spots class — its five shipped defects are this entry's emulator assertion list
(synced+saved sensing, no debounce, no arbitration, AnyState self-retrigger, default-on kill
switch). Audio variant selection (parameter-indexed `VRCAnimatorPlayAudio`) is deliberately not
shipped — asset closure; the headpat is the worked example to copy when you add sound.

## Interface

- **Params:**
  - `ZoneTouch/Enable` (bool, in) — synced, **unsaved**. The menu front (VRCFury Toggle). Synced
    because receivers fire per-client: an unsynced enable would leave every remote's sensing
    alive while the wearer believes the module is off.
  - `ZoneTouch/Special` (bool, out) — synced, **unsaved**. The divergent outcome. Written only by
    the wearer's `localOnly` drivers (set on Special entry, cleared on Cooldown/Disabled entry —
    the falling edge is the remote rearm signal).
  - `ZoneTouch/Zone1..3` (float, sensing) — proximity receivers, never synced/saved.
  - `ZoneTouch/RollHit` (bool, scratch) — local roll residue, excluded from the params asset.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔
  `basis: mount-root`), merging `built/ZoneTouch_Fx_Parameters.asset`; `globalParams:
  [ZoneTouch/Enable]`, Toggle drives it. Pure VRCFury — no MA half: the zone GOs are plain
  children the consumer moves or constrains (they are receiver roots only, safe to reparent).
- **Dependencies:** VRC SDK + VRCFury.
- **Required assets:** none — `ReactProxy` is a placeholder sphere on the built-in default
  material; the reaction clips scale it. Replace the `zt_react`/`zt_special` clip content (or
  the whole proxy) with your real reaction.

## The things to know before wearing it

- **Zones are yours to place.** `Zones/Zone1..3` ship as unanchored children of the module root.
  Move each onto the body part it should sense (parent or constrain it there). Receiver tags are
  `Hand`/`Finger` (community-standard toucher tags).
- **Arbitration is the transition ladder.** Coincident touches resolve Zone1 > Zone2 > Zone3 by
  list order — one machine, one writer, so there is no last-write-wins on the reaction rig
  (the vendor failure). Re-order the ladder to re-prioritize.
- **Per-zone reactions are a clip swap.** `React1..3` all play `zt_react`; point a zone's state
  at its own clip for distinct reactions. Keep one machine — do not fork per-zone layers.
- **The special odds live in one driver field** (`chance: 0.02` on each React entry — the
  consumer-tunable knob; keep the three in agreement).

## How it works

`Disabled` (default — the failsafe polarity the vendor inverted) disables every zone receiver GO,
so the synced enable gates sensing on every client. `Idle` waits on the arbitration ladder; a
touch enters that zone's `React`, which rolls the special odds once on entry (`localOnly` Random
driver — remotes' RollHit stays 0), plays the reaction once, and **holds while the touch
persists** (no AnyState, no self edge — the machine, not the clip, decides when a new episode
starts). Release enters `Cooldown` (0.5 s debounce — no zone edge leaves it, so a re-touch
inside the window is ignored), which also drops `Special` — the falling edge. A local roll hit
routes to `Special` (stamps the bool); remotes reach `Special` from Idle or React the moment the
bool arrives, and leave it only on the falling edge (or enable-off). A late joiner mid-special
lands in Idle and follows the bool in — nothing to save.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Debounce dwell | 0.5 s | emulator sweep (this entry's build); feel-tunable |
| Special chance | 0.02 | consumer preference, not physics |
| Touch / release thresholds | >0 / <0.00001 | contact-tracker lineage |

**Verified (Av3Emulator, this entry's build):** sync surface = Enable + Special only; a foreign
sender (`allowOthers`) fired Zone1 and the pulse played once, holding without re-trigger while
touched; coincident Zone1+Zone2 resolved to React1 (releasing sender 1 alone exited the machine —
the ladder discriminator); a re-touch inside the 0.5 s cooldown was ignored (proxy pinned at 1.000)
and fired cleanly after it; the forced roll entered Special on both clients (local scale 2.0, clone
2.0 via the synced bool) and the release **falling edge** re-armed both; enable-off killed the zone
receivers on the local *and* the clone.

**Remote-side sensing is in-game-only to *prove*** (emulator clones hold spawn-time contact
fossils — `verify.md`): the emulator verifies the local machine, the allow-flag matrix, and the
synced-bool channel against a clone; that remotes' own receivers fire for a real toucher is the
same `localOnly: 0` mechanism the headpat and the vendor package both demonstrate live in-game.

## Rig

    ZoneTouch                        root — VRCFury FullController + Toggle
    ├─ Zones
    │  ├─ Zone1                      VRCContactReceiver proximity r=0.1, tags [Hand, Finger],
    │  │                             allowSelf+allowOthers, localOnly:0 → ZoneTouch/Zone1
    │  ├─ Zone2                      (same, → ZoneTouch/Zone2)
    │  └─ Zone3                      (same, → ZoneTouch/Zone3)
    └─ ReactProxy                    sphere, built-in default material — the placeholder output

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID —
recompile is GUID-stable; regenerate controller + params asset as a unit over the committed
`.meta`s). The prefab is hand-maintained against the Rig section above.
