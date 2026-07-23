# zone-touch — N-zone touch reaction, sync-only-the-divergent-outcome (Module)

Touch zones on the avatar that react when someone touches them — a headpat, a poke — with the reaction showing on every client. Point three receivers at the parts you want touch-reactive; the machine debounces, arbitrates coincident touches, and plays the reaction. The packaged novelty is spending almost no sync on it: each client senses the toucher locally, so the common reaction reproduces everywhere at zero synced bits and zero latency, and the only things synced are what a remote cannot re-derive — the enable and a rare random-special outcome, **2 bits total**.

**Provenance:** a private production avatar's headpat mechanism, generalized (sync-only-the-divergent-outcome + level-handshake rearm, `gimmicks.md` §Contacts). The vendor baseline it corrects is the commercial touch-spots class, whose five shipped defects this entry inverts: synced+saved sensing, no debounce, no arbitration, AnyState self-retrigger, default-on kill switch. Audio variant selection (parameter-indexed `VRCAnimatorPlayAudio`) is deliberately not shipped — asset closure; the headpat is the worked example to copy when you add sound.

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
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`), merging `built/ZoneTouch_Fx_Parameters.asset`; `globalParams: [ZoneTouch/Enable]`, Toggle drives it. Pure VRCFury — no MA half: the zone GOs are plain children the consumer moves or constrains (they are receiver roots only, safe to reparent).
- **Dependencies:** VRC SDK + VRCFury.
- **Required assets:** none — `ReactProxy` is a unit-scale wrapper the reaction clips animate (clip scale values read as multipliers of rest); the placeholder sphere is its child. Replace the child (keep it under the wrapper) or the `zt_react`/`zt_special` clip content with your real reaction.

## Before you compose it

- **Zones are yours to place — by constraint, never by reparent.** `Zones/Zone1..3` ship as unanchored children of the module root; anchor each to the body part it should sense with a VRCParentConstraint. The zone GOs are path-animated (the enable clips drive their `m_IsActive`), so anything that moves them out of the module subtree — reparenting under a bone, MA BoneProxy, VRCFury ArmatureLink — silently kills the enable clips (MA moves objects before VRCFury resolves FullController paths). Receiver tags are `Hand`/`Finger` (community-standard toucher tags).
- **Arbitration is the transition ladder.** Coincident touches resolve Zone1 > Zone2 > Zone3 by list order — one machine, one writer, so there is no last-write-wins on the reaction rig (the vendor failure). Re-order the ladder to re-prioritize.
- **Per-zone reactions are a clip swap.** `React1..3` all play `zt_react`; point a zone's state at its own clip for distinct reactions. Keep one machine — do not fork per-zone layers.
- **The special odds live in one driver field** (`chance: 0.02` on each React entry — the consumer-tunable knob; keep the three in agreement).

## How it works

`Disabled` (default — the failsafe polarity the vendor inverted) disables every zone receiver GO, so the synced enable gates sensing on every client. `Idle` waits on the arbitration ladder; a touch enters that zone's `React`, which rolls the special odds once on entry (`localOnly` Random driver — remotes' RollHit stays 0), plays the reaction once, and **holds while the touch persists** (no AnyState, no self edge — the machine, not the clip, decides when a new episode starts). Release enters `Cooldown` (0.5 s debounce — no zone edge leaves it, so a re-touch inside the window is ignored), which also drops `Special` — the falling edge. A local roll hit routes to `Special` (stamps the bool); remotes reach `Special` from Idle or React the moment the bool arrives, and leave it only on the falling edge (or enable-off). A late joiner mid-special lands in Idle and follows the bool in — nothing to save.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Debounce dwell | 0.5 s | emulator sweep; feel-tunable |
| Special chance | 0.02 | consumer preference, not physics |
| Touch / release thresholds | >0 / <0.00001 | contact-tracker lineage |

## Verifying the install

The sync surface is Enable + Special only. A foreign (`allowOthers`) sender on a zone fires its reaction once and holds without re-triggering while the touch persists; coincident Zone1+Zone2 resolves to React1, and releasing only sender 1 exits the machine — that is the ladder discriminator working. A re-touch inside the cooldown is ignored. Enable-off must kill the zone receivers on the clone as well as locally.

That remotes' own receivers fire for a real toucher is in-game-only — emulator clones hold spawn-time contact fossils (`verify.md`). The emulator reaches the local machine, the allow-flag matrix, and the synced-bool channel against a clone.

## Rig

    ZoneTouch                        root — VRCFury FullController + Toggle
    ├─ Zones
    │  ├─ Zone1                      VRCContactReceiver proximity r=0.1, tags [Hand, Finger],
    │  │                             allowSelf+allowOthers, localOnly:0 → ZoneTouch/Zone1
    │  ├─ Zone2                      (same, → ZoneTouch/Zone2)
    │  └─ Zone3                      (same, → ZoneTouch/Zone3)
    └─ ReactProxy                    unit-scale wrapper — the clips animate this transform
       └─ Sphere        (0.06)      placeholder sphere, built-in default material — swap this

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID — recompile is GUID-stable; regenerate controller + params asset as a unit over the committed `.meta`s). The prefab is hand-maintained against the Rig section above.
