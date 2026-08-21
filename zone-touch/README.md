# zone-touch — N-zone touch reaction, sync-only-the-divergent-outcome (Module)

Touch zones on the avatar that react when someone touches them — a headpat, a poke — with the reaction showing on every client. Point three receivers at the parts you want touch-reactive; the machine debounces, arbitrates coincident touches, and plays the reaction. The packaged novelty is spending almost no sync on it: each client senses the toucher locally, so the common reaction reproduces everywhere at zero synced bits and zero latency, and the only things synced are what a remote cannot re-derive — the enable and a rare random-special outcome, **2 bits total**.

**Provenance:** a private production avatar's headpat mechanism, generalized (sync-only-the-divergent-outcome + level-handshake rearm, `gimmicks.md` §Contacts). Audio variant selection (parameter-indexed `VRCAnimatorPlayAudio`) is deliberately not shipped; the headpat is the worked example to copy when you add sound.

## Ground truth

`controller.yaml` owns the parameters, the state machine, and the clips. What the artifacts cannot state:

- **`ZoneTouch/Enable` must stay synced.** It is the menu front (a VRCFury Toggle) and it gates **remote** sensing too — unsynced would leave every remote's receivers alive while the wearer believes the module is off. `globalParams` is exactly `[ZoneTouch/Enable]`.
- **`ZoneTouch/Special` is the one divergent bit**, written only by the wearer's `localOnly` drivers; its falling edge — dropped on Cooldown/Disabled entry — is the signal a remote rearms on. `ZoneTouch/RollHit` is local roll residue, excluded from the params asset.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`). Pure VRCFury, no MA half. Dependencies: VRC SDK + VRCFury. No required assets — `ReactProxy` is a unit-scale wrapper the reaction clips scale (values read as multipliers of rest); swap its placeholder-sphere child or the `zt_react`/`zt_special` clip content for your reaction.

## Before you compose it

- **Zones are yours to place — by constraint, never by reparent.** `Zones/Zone1..3` ship as unanchored children of the module root; anchor each to the body part it should sense with a VRCParentConstraint. The zone GOs are path-animated (the enable clips drive their `m_IsActive`), so anything that moves them out of the module subtree — reparenting under a bone, MA BoneProxy, VRCFury ArmatureLink — silently kills the enable clips (MA moves objects before VRCFury resolves FullController paths). Receiver tags are `Hand`/`Finger` (community-standard toucher tags).
- **Arbitration is the transition ladder.** Coincident touches resolve Zone1 > Zone2 > Zone3 by list order — one machine, one writer, so there is no last-write-wins on the reaction rig. Re-order the ladder to re-prioritize.
- **Per-zone reactions are a clip swap.** `React1..3` all play `zt_react`; point a zone's state at its own clip for distinct reactions. Keep one machine — do not fork per-zone layers.

## How it works

`Disabled` (default, fail-safe) disables every zone receiver GO, and a second **non-`localOnly`** driver zeroes `Zone1..3` on every client. A disabled receiver freezes its float at its last reading, so without that zeroing a touch held at disable time would replay a spurious React on re-enable. `Idle` arbitrates by the ladder; a touch enters that zone's `React`, rolls the special odds once on entry (`localOnly` Random driver), plays the reaction, and holds while the touch persists — no self-retrigger. Release enters `Cooldown` (the debounce dwell), which also drops `Special`. A local roll routes to `Special`; remotes follow the synced bool in and out, including a late joiner arriving mid-special.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value |
|---|---|
| Debounce dwell | the `zt_cooldown` clip's length — the dwell *is* the `Cooldown` state length; feel-tunable, long enough that a re-touch inside the window reads as the same episode |
| Special chance | the `chance` field on each `React` entry's Random driver — **all three must agree** |
| Touch / release thresholds | >0 / <0.00001 |

## Verifying the install

The sync surface is Enable + Special only. A foreign (`allowOthers`) sender on a zone fires its reaction once and holds without re-triggering while the touch persists; coincident Zone1+Zone2 resolves to React1, and releasing only sender 1 exits the machine. A re-touch inside the cooldown is ignored. Enable-off must kill the zone receivers on the clone as well as locally.

That remotes' own receivers fire for a real toucher is in-game-only — emulator clones hold spawn-time contact fossils (`verify.md`). The emulator reaches the local machine, the allow-flag matrix, and the synced-bool channel against a clone.

## Rig

    ZoneTouch                        root — VRCFury FullController + Toggle
    ├─ Zones
    │  ├─ Zone1                      VRCContactReceiver proximity, tags [Hand, Finger],
    │  │                             allowSelf+allowOthers, localOnly:0 → ZoneTouch/Zone1
    │  ├─ Zone2                      (same, → ZoneTouch/Zone2)
    │  └─ Zone3                      (same, → ZoneTouch/Zone3)
    └─ ReactProxy                    unit-scale wrapper — the clips scale this transform
       └─ Sphere                     placeholder sphere, built-in default material — swap this

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
