# zone-touch — N-zone touch reaction with a tiered rarity table, sync-only-the-divergent-outcome (Module)

Touch zones on the avatar that react when someone touches them — a headpat, a poke — with the reaction showing on every client. Point three receivers at the parts you want touch-reactive; the machine debounces, arbitrates coincident touches, and plays the reaction. Each touch also rolls a rarity table: most touches play the common reaction, a few land a tiered special — uncommon, rare, super rare — that every client shows for at least a set floor, or for a lockout of at least the clip during which the zones are dead everywhere. The packaged novelty is spending almost no sync on it: each client senses the toucher locally, so the common reaction reproduces everywhere at zero synced bits and zero latency, and the only things synced are what a remote cannot re-derive — the enable and the rolled tier, **3 bits total**.

**Provenance:** a private production avatar's headpat mechanism, generalized (sync-only-the-divergent-outcome + level-handshake rearm, `gimmicks.md` §Contacts); the tier table and the lockout are the shape of a sibling grip-prop gimmick on the same avatar, and the range-and-compare roll is how both ancestors rolled their rare. Audio variant selection (parameter-indexed `VRCAnimatorPlayAudio`) is deliberately not shipped; the headpat is the worked example to copy when you add sound, and a per-client common variant is a second Random driver on React entry that is *not* `localOnly` (every client picks its own, nothing crosses the wire).

## Ground truth

What the artifacts cannot state:

- **`ZoneTouch/Enable` must stay synced.** It is the menu front (a VRCFury Toggle) and it gates **remote** sensing too — unsynced would leave every remote's receivers alive while the wearer believes the module is off. `globalParams` is exactly `[ZoneTouch/Enable]`.
- **`ZoneTouch/SpecialA` + `SpecialB` are the divergent bits**, a 2-bit tier code (A = 1, B = 2, A+B = 3, none = 0) written only by the wearer's `localOnly` drivers, both bits in one driver so they cross as one snapshot; the code returning to 0 — dropped on Cooldown/Disabled entry — is the signal a remote rearms on. A fourth tier costs a third bool. `ZoneTouch/Roll` is local roll residue, excluded from the params asset; it stays unsynced because its sentinel sits above what a synced int can carry.
- **A special plays out in full on every client, short of the kill switch.** Its clip length is a floor under the synced pair: the wearer cannot release it early, and a remote leaves only on the falling edge; only Enable-off pre-empts it, and an Enable-off inside the wire floor is a special no remote sees. Tier 3 makes the floor the whole reaction — a lockout of at least the clip, during which every client, wearer included, ignores the zones; the hold then persists while the touch does, and the dwell follows. The floor exists because a set→clear pair narrower than ~0.2 s is never seen remotely (`runtime.md` §Parameters); without it a tap released inside that window was a special no remote ever showed.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`). Pure VRCFury, no MA half. Dependencies: VRC SDK + VRCFury. No required assets — `ReactProxy` is a unit-scale wrapper the reaction clips scale (values read as multipliers of rest); swap its placeholder-sphere child or the `zt_react`/`zt_special*` clip content for your reaction.

## Before you compose it

- **Zones are yours to place — by constraint, never by reparent.** `Zones/Zone1..3` ship as unanchored children of the module root; anchor each to the body part it should sense with a VRCParentConstraint. The zone GOs are path-animated (the enable clips drive their `m_IsActive`), so anything that moves them out of the module subtree — reparenting under a bone, MA BoneProxy, VRCFury ArmatureLink — silently kills the enable clips (MA moves objects before VRCFury resolves FullController paths). Receiver tags are `Hand`/`Finger` (community-standard toucher tags).
- **Arbitration is the transition ladder.** Coincident touches resolve Zone1 > Zone2 > Zone3 by list order — one machine, one writer, so there is no last-write-wins on the reaction rig. Re-order the ladder to re-prioritize.
- **Per-zone reactions are a clip swap.** `React1..3` all play `zt_react`; point a zone's state at its own clip for distinct reactions. Keep one machine — do not fork per-zone layers.
- **The table is yours to retune, in three places that must agree.** The bands are the `Roll less N` rungs at the top of each React state, rarest first and identical across the three; a band's odds are its width over the roll range, so a wider band listed above a narrower one silently swallows it. Fewer tiers: delete a tier's rungs and its `Special`/`Held` pair. Any touch that reaches React rolls: the roll lands one evaluation after entry, and on that evaluation the tier rungs outrank the release rung.
- **`Held<k>` replays the tier clip while the touch persists.** It re-enters the same clip from the start and loops it, which the shipped constant clips hide; an animated reaction restarts there, so author it to loop cleanly or point `Held<k>` at a separate sustain clip.

## How it works

`Disabled` (default, fail-safe) disables every zone receiver GO, and a second **non-`localOnly`** driver zeroes `Zone1..3` on every client. A disabled receiver freezes its float at its last reading, so without that zeroing a touch held at disable time would replay a spurious React on re-enable. `Idle` arbitrates by the ladder; a touch enters that zone's `React`, rolls the table once on entry (`localOnly` Random driver), plays the reaction, and holds while the touch persists — no self-retrigger. A roll that lands a band routes the wearer to that tier's `Special`, which stamps the code and holds its clip length ignoring the zones, then `Held` keeps the reaction until release. Release enters `Cooldown` (the debounce dwell), which also drops the code. Remotes follow the synced pair in and out, including a late joiner arriving mid-special, and follow a fresh tier from `Cooldown` without waiting out the dwell.

A tier is two states because an exit-time rung re-checks its conditions only on a crossing (`animator-schema.md` §transitions), so one state holding the floor and exiting on release would quantize the release to the floor period.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value |
|---|---|
| Debounce dwell | the `zt_cooldown` clip's length — the dwell *is* the `Cooldown` state length; feel-tunable, and above the wire floor so the cleared code is on the wire before the next tier can be set |
| Roll range | the `max` of each React entry's Random driver — **all three must agree**; each band's odds are its width over this |
| Tier bands | the `Roll less N` cutoffs at the top of each React state, cumulative, disjoint, rarest first — **all three ladders must agree** |
| Roll sentinel | the out-of-band value the parameter default, `Disabled` and each `Special<k>` write — five sites that must agree and sit above the widest cutoff, or a stale copy fires a tier |
| Tier hold floor | each `zt_special<k>` clip's `seconds:` — the minimum the code stays set, the wire floor plus a low-frame-rate margin; a lockout tier's clip *is* the reaction, and the width the wire sees is the clip give or take about two frames |

## Verifying the install

The sync surface is Enable + the tier pair only. A foreign (`allowOthers`) sender on a zone fires its reaction once and holds without re-triggering while the touch persists; coincident Zone1+Zone2 resolves to React1, and releasing only sender 1 exits the machine. A re-touch inside the cooldown is ignored. Enable-off must kill the zone receivers on the clone as well as locally.

**The tap arm.** With a clone spawned at `AlwaysAnimate`, force a tier by writing `ZoneTouch/Roll` through the runtime's `Ints` mirror on the frame the wearer enters `React` — never by editing the bands — and tap a zone with a scripted sender for about six placed frames (the receiver reads it about five frames after placement, so that is a two-to-four-frame touch). Sample the tier pair per frame on the wearer's mirror and the clone's, and the clone's `ReactProxy` scale, which is the readable tier (a clone's FX has no state names). Expect: the pair set at least the tier's clip on both, the clone rising one sync tick later and showing the tier's scale, the wearer passing `Held` for one frame; for tier 3, a second tap a second in leaves both copies where they are and the clone's own receiver reading it changes nothing. A recorder on `EditorApplication.update` must gate on `Time.frameCount` — it fires several times per player frame, so an ungated "three-tick" tap is under one frame and no receiver sees it.

That remotes' own receivers fire for a real toucher is in-game-only — the toucher's real body senders and that client's timing have no emulator stand-in, though a clone's receivers do simulate against scripted senders (`emulator.md` §Remote clone). The emulator reaches the local machine, the allow-flag matrix, the tier ladder, the floors, and the synced-pair channel against a clone.

## Rig

    ZoneTouch                        root — VRCFury FullController + Toggle
    ├─ Zones
    │  ├─ Zone1                      VRCContactReceiver proximity, tags [Hand, Finger],
    │  │                             allowSelf+allowOthers, localOnly:0 → ZoneTouch/Zone1
    │  ├─ Zone2                      (same, → ZoneTouch/Zone2)
    │  └─ Zone3                      (same, → ZoneTouch/Zone3)
    └─ ReactProxy                    unit-scale wrapper — the clips scale this transform
       └─ Sphere                     placeholder sphere, built-in default material — swap this
