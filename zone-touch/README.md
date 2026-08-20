# zone-touch — N-zone touch reaction, sync-only-the-divergent-outcome (Module)

Touch zones on the avatar that react when someone touches them — a headpat, a poke — with the reaction showing on every client. Point three receivers at the parts you want touch-reactive; the machine debounces, arbitrates coincident touches, and plays the reaction. The packaged novelty is spending almost no sync on it: each client senses the toucher locally, so the common reaction reproduces everywhere at zero synced bits and zero latency, and the only things synced are what a remote cannot re-derive — the enable and a rare random-special outcome, **2 bits total**.

**Provenance:** a private production avatar's headpat mechanism, generalized (sync-only-the-divergent-outcome + level-handshake rearm, `gimmicks.md` §Contact patterns). Audio variant selection (parameter-indexed `VRCAnimatorPlayAudio`) is deliberately not shipped; the headpat is the worked example to copy when you add sound.

## Ground truth

- Parameters, the state ladder, the drivers and the clips: `controller.yaml`. Its header is the design record — the five vendor defects the structure is built against, why the enable and only the enable is synced, and the level-handshake rearm — and each state carries its own rationale at the site. The published set is the prefab's `globalParams` (`ZoneTouch/Enable` alone, driven by the VRCFury Toggle); everything else about the wiring is `ZoneTouch.prefab`.
- **Seam:** VRCFury `FullController` on the prefab root (FX), pairing `basis: mount-root` with `rootBindingsApplyToAvatar: 0`, and merging `built/ZoneTouch_Fx_Parameters.asset`. CompileController is frame-blind, so no artifact states that pairing. Pure VRCFury, no Modular Avatar half: the zone GOs are plain children the consumer moves or constrains — receiver roots only, safe to reparent *within* the module.
- **Required assets:** none. `ReactProxy` is a unit-scale wrapper the reaction clips animate, so their scale values read as multipliers of rest; the placeholder sphere is its child. Replace the child, keeping it under the wrapper, or replace the `zt_react`/`zt_special` clip content with your real reaction.
- Dependencies: VRC SDK + VRCFury.

## Before you compose it

- **Zones are yours to place — by constraint, never by reparent.** `Zones/Zone1..3` ship as unanchored children of the module root; anchor each to the body part it should sense with a VRCParentConstraint. The zone GOs are path-animated (the enable clips drive their `m_IsActive`), so anything that moves them out of the module subtree — reparenting under a bone, MA BoneProxy, VRCFury ArmatureLink — silently kills the enable clips (MA moves objects before VRCFury resolves FullController paths). Receiver tags are `Hand`/`Finger`, the community-standard toucher tags.
- **Arbitration is the transition ladder.** Coincident touches resolve Zone1 > Zone2 > Zone3 by list order — one machine, one writer, so there is no last-write-wins on the reaction rig. Re-order the ladder to re-prioritize.
- **Per-zone reactions are a clip swap.** `React1..3` all play `zt_react`; point a zone's state at its own clip for distinct reactions. Keep one machine — do not fork per-zone layers.
- **`Disabled` carries a second driver that is deliberately not `localOnly`** (`controller.yaml:58`, reasoned at the site): it zeroes the three zone floats on every client. Delete it, or make it `localOnly` to match the neighbour above it, and a touch held at the moment the module is disabled replays as a spurious React on re-enable — on remotes, where nobody is touching anything.

## Measured

Empirical constants (labeled in `controller.yaml`; `runtime.md`'s 90% rule governs changing any of them):

| Constant | Where it is authored |
|---|---|
| Debounce dwell | the `zt_cooldown` clip's length — the dwell *is* the `Cooldown` state length; feel-tunable, long enough that a re-touch inside the window reads as the same episode |
| Special chance | the `chance` field on each `React` entry's Random driver — **all three must agree** |
| Touch / release thresholds | the `Idle`→`React` and `React`→`Cooldown` zone conditions; asymmetric on purpose, release far below touch |

## Verifying the install

The sync surface is Enable + Special only. A foreign (`allowOthers`) sender on a zone fires its reaction once and holds without re-triggering while the touch persists; coincident Zone1+Zone2 resolves to React1, and releasing only sender 1 exits the machine. A re-touch inside the cooldown is ignored. Enable-off must kill the zone receivers on the clone as well as locally.

That remotes' own receivers fire for a real toucher is in-game-only — emulator clones hold spawn-time contact fossils (`verify.md`). The emulator reaches the local machine, the allow-flag matrix, and the synced-bool channel against a clone.

## Rig

    ZoneTouch                        root — VRCFury FullController + Toggle
    ├─ Zones
    │  ├─ Zone1                      VRCContactReceiver, proximity, self and foreign touchers,
    │  │                             not localOnly — every client senses for itself
    │  ├─ Zone2                      (same shape)
    │  └─ Zone3                      (same shape)
    └─ ReactProxy                    unit-scale wrapper — the clips animate this transform
       └─ Sphere                     placeholder, built-in default material — swap this

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
