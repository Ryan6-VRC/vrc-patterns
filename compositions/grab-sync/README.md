# grab-sync — a grabbable prop whose drop is shared truth (Composition)

Grab the prop off your hip, carry it, set it down anywhere: everyone in the instance sees it in that spot — a player who joins later included — and a re-grab picks it up from where it rests with no snap, from any join state. Grabbing is a physbone (natively networked, so remotes see the carry live), heading comes from a drag bone trailing the motion, and the drop's absolute position and yaw ride `object-sync`'s 28-bit word so placement is exact rather than replayed. One synced bit of its own (`Detached`) on top of the entry's wire.

## What it composes

| entry | what it contributes |
|---|---|
| `grab-prop` | the grab/release cell: physbone grab, the constraint-freeze drop capture, home recall |
| `drag-bone` | yaw heading from a drag sim trailing the carry |
| `object-sync` (`y/`) | absolute world position + heading for the drop, late-join included |
| `word-channel` | the wire underneath (reached through `object-sync`) |

Its own contribution, belonging to no entry: the ten-state glue layer arbitrating cell against word (`controller.yaml` — its header carries every design ruling), the park that force-aligns the drag heading to the synced yaw on every remote so re-grab is snap-free, and the `Reacquire` dwell that keeps a remote's re-grab from flashing the stale cell.

## Install

Drop `GrabSync.prefab` under your avatar root. The home anchor is an MA `BoneProxy` targeting **Hips**, so it resolves on any humanoid; drag `Prop/GrabProp/HomeAnchor/Offset` to place the rest position, and swap your mesh in for the sphere under `Prop/GrabProp/Container/Payload`, keeping it under `Container` (`../../grab-prop/README.md` owns the cell's rig rules). The menu Toggle **GrabSync** fronts `ObjectSync/Enable`, declared default-**on**; off recalls the prop home on every client.

**One instance per avatar, and never beside any other `object-sync` build** — every configuration of that entry shares the parameter prefix and the collision tags (`../../object-sync/README.md` §Seam owns the rule).

**Do not enable the two constraints on the prefab root** to make the editor view look pinned — they ship disabled and a VRCFury `ApplyDuringUpload` enables them at build, so seams under them capture poses authored on the body rather than origin-parked ones (`../../../docs/gimmicks.md` §Constraint patterns). Their correct serialized state is all-zero offsets; if one has been disturbed, Zero it, never Activate.

## The arrangement

    GrabSync               THE one pin: VRCParentConstraint + VRCScaleConstraint → World.prefab, zero
                           offsets, disabled in editor, ApplyDuringUpload enables at build; + the menu
                           Toggle and the FullController playing built/GrabSync_Fx
    ├─ ObjectSync          nested instance of ../../object-sync/y/ (heading-only), consumed through its
    │                      published interface (ObjectSync/*); its own FullController stays
    └─ Prop/
       ├─ GrabProp         nested grab-prop instance: rig untouched, grab physbone parameter → `Grab`
       ├─ DragBone_Yaw     nested drag-bone instance + the park glue (a yaw-only rotation constraint on
       │                   Follower ← Container, normally inactive)
       ├─ Source           the mode mux: position [GrabProp/Container, Sync, HomeAnchor/Offset],
       │                   rotation [Drag_Rotation, Sync, home] — weights are the glue's value-sets
       └─ Container        the display + damper (payload rides it); Display, a plain child, is both the
                           visibility gate and GrabPosition's rest-anchor frame (the two-source repoint
                           ../../grab-prop/README.md §How it works sanctions)

Unlike `object-sync-demo`, this prefab is **not** a variant of the entry prefab — the entry is a nested child and the composition root carries the only pin. The nested instances are customised by **removal**, the only redirect a VRCFury component supports (`../../../docs/nondestructive.md`), and those removals are recorded here because nothing validates them: `grab-prop`'s `FullController` and `Toggle` are removed (its chords live in the glue controller), `object-sync`'s shipped Drop toggle on `Sync_Target` is removed (its `FreezeToWorld` writer would fight the glue), and the `object-sync` root's own pin pair is removed so the built avatar holds exactly one World-sourced pin — the entry's `PinEnable` curves then resolve to nothing, which is harmless and deliberate.

The glue's state graph, its value-sets, the engage-on-`ObjectSync/Ready` gate, and every operator ruling live in `controller.yaml`'s header — read it there, not here.

## Verifying it

Grab, carry, drop, re-grab on the wearer must feel exactly like the `grab-prop` demo — the cell bindings are that entry's clip table verbatim, and the transcription diff is the check. On a remote clone: a drop glides to the exact spot within ~3 s; a fresh clone shows an already-placed prop **in place** (no fly-in) and its re-grab shows no heading snap; Enable off/on recalls home on both views. The wire itself is `../../object-sync/README.md` §Verifying the install. What the emulator structurally cannot show: animated `VRCPhysBone.m_Enabled` on a remote clone — the fresh-join re-grab — needs the shipping client, two clients in-game.

## Provenance

Each composed entry carries its own ancestry (`grab-prop`, `drag-bone`, `object-sync` READMEs). The cell-versus-word arbitration — one controller subsuming the grab cell's chords and parking the drag heading on the synced yaw — is the shape of a private doll rig, in-game-proven, re-derived here against the shipped entries.
