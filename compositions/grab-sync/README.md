# grab-sync — grabbable props whose drops are shared truth (Composition)

Grab a prop off your hip, carry it, set it down anywhere: everyone in the instance sees it in that spot — a player who joins later included — and a re-grab picks it up from where it rests with no snap, from any join state. Grabbing is a physbone (natively networked, so remotes see the carry live), heading comes from a drag bone trailing the motion, and the drop's absolute position and yaw ride `object-sync`'s word so placement is exact rather than replayed. Two prefabs ship: **`GrabSync.prefab`** (one prop, the entry's stock `y/` build, one `Detached` bit on top of its 28-wire) and **`MultiGrabSync.prefab`** (four props on this composition's own regenerated four-object build — 29 wire bits time-sliced across the props, plus `Detached_0..3`).

## What it composes

| entry | what it contributes |
|---|---|
| `grab-prop` | the grab/release cell: physbone grab, the constraint-freeze drop capture, home recall |
| `drag-bone` | yaw heading from a drag sim trailing the carry |
| `object-sync` (`y/`) | absolute world position + heading for the drop, late-join included |
| `word-channel` | the wire underneath (reached through `object-sync`) |

Its own contribution, belonging to no entry: the ten-state glue layer arbitrating cell against word (`controller.yaml` — its header carries every design ruling), the park that force-aligns the drag heading to the synced yaw on every remote so re-grab is snap-free, and the `Reacquire` dwell that keeps a remote's re-grab from flashing the stale cell.

## Install

Drop `GrabSync.prefab` under your avatar root. The home anchor is an MA `BoneProxy` targeting **Hips**, so it resolves on any humanoid; drag `Prop/GrabProp/HomeAnchor/Offset` to place the rest position, and swap your mesh in for the sphere at `Prop/Container/Display/Payload`, keeping it under `Display` — the node the clips gate for visibility and GrabPosition's rest-anchor frame; the cell's own `Payload` is removed on every nested `GrabProp` (`../../grab-prop/README.md` owns the cell's rig rules). The menu Toggle **GrabSync** fronts `ObjectSync/Enable`, declared default-**on**; off recalls the prop home on every client.

**One prefab per avatar — GrabSync or MultiGrabSync, never both, and never beside any other `object-sync` build** — every configuration of that entry shares the parameter prefix, and a second live build's contact clusters park at the same point (`../../object-sync/README.md` §Seam owns the rule).

**Do not enable the two constraints on the prefab root** to make the editor view look pinned — they ship disabled and a VRCFury `ApplyDuringUpload` enables them at build, so seams under them capture poses authored on the body rather than origin-parked ones (`../../../docs/gimmicks.md` §Constraint patterns). Their correct serialized state is all-zero offsets; if one has been disturbed, Zero it, never Activate.

## The arrangement

    GrabSync               THE one pin: VRCParentConstraint + VRCScaleConstraint → World.prefab, zero
                           offsets, disabled in editor, ApplyDuringUpload enables at build; + the menu
                           Toggle and the FullController playing built/GrabSync_Fx
    ├─ ObjectSync          nested instance of ../../object-sync/y/ (heading-only), consumed through its
    │                      published interface (ObjectSync/*); its own FullController stays
    ├─ CaptureOrderPin     nested instance of ../../solve-order-pin/, keeping its own FullController;
    │                      its Ladder/Depth16 tip is a weight-0 source on the cell's SourcePosition
    │                      (§Capture order); not scaffolding, do not strip
    └─ Prop/
       ├─ GrabProp         nested grab-prop instance: rig untouched, grab physbone parameter → `Grab`
       ├─ DragBone_Yaw     nested drag-bone instance + the park glue (a yaw-only rotation constraint on
       │                   Follower ← Container, normally inactive)
       ├─ Source           the mode mux: position [GrabProp/Container, Sync, HomeAnchor/Offset],
       │                   rotation [Drag_Rotation, Sync, home] — weights are the glue's value-sets
       └─ Container        the display + damper (payload rides it); Display, a plain child, is both the
                           visibility gate and GrabPosition's rest-anchor frame (the two-source repoint
                           ../../grab-prop/README.md §How it works sanctions)

Unlike `object-sync-demo`, this prefab is **not** a variant of the entry prefab — the entry is a nested child and the composition root carries the only pin. The nested instances are customised by **removal**, the only redirect a VRCFury component supports (`../../../docs/nondestructive.md`), and those removals are recorded here because nothing validates them: `grab-prop`'s `FullController` and `Toggle` are removed (its chords live in the glue controller) along with its placeholder `Payload` sphere on every nested instance (the visible payload lives under `Prop/Container/Display`); `object-sync`'s shipped Drop toggle on `Sync_Target` is removed (its `FreezeToWorld` writer would fight the glue), as are its root's own menu `Toggle` and `ApplyDuringUpload` (the composition fronts Enable and arms the one pin itself); and the `object-sync` root's own pin pair is removed so the built avatar holds exactly one World-sourced pin — the entry's `PinEnable` curves then resolve to nothing, which is harmless and deliberate. The nested `solve-order-pin` instance is the one whose `FullController` is deliberately **kept**: it carries the animation that switches the ladder off after load, and removing it the way `grab-prop`'s was would leave the ladder running forever — working, but paying for itself every frame.

The glue's state graph, its value-sets, the engage-on-`ObjectSync/Ready` gate, and every operator ruling live in `controller.yaml`'s header — read it there, not here.

## Capture order — why CaptureOrderPin exists

The cell's release capture survives only when `GrabProp/Container` reads `SourcePosition` one frame stale, and which edge of the cell's constraint cycle carries that stale read is authored nowhere: the same serialized prefab has play-tested good and bad with no edit between, and duplicate-swaps, re-saves, and per-build play certification all just re-roll it (each was tried). `../../solve-order-pin/` is the fix and owns the mechanism, the sizing measurement, and the install seam — read it there.

What is this composition's alone: **`SourcePosition` is the constraint that must solve last**, so the tip edge lands there, and the entry cannot work that out for itself — it says so, and this line is the answer. `MultiGrabSync` runs one ladder with a tip edge into each of its four props' `SourcePosition`.

The pass observable, per prop, on a fresh play entry: cell `Container`'s `LatestValidExecutionGroupIndex` at or above 0 **and less than** `SourcePosition`'s. Re-read it after any change to the avatar's constraint graph that feeds `Container` or the cell ring — the defeating case is a new deep chain into the `Container` side, and it can come from anywhere on the avatar, not just this module.

One idiom collision this composition is uniquely exposed to, because it holds both: the root pins ship `m_Enabled` off and are flipped on at build by `ApplyDuringUpload`, while the pin's ladder ships **active** and is switched off by its own animation after load. The two look like the same "disabled thing enabled later" pattern and are opposites — normalizing either to match the other breaks that side. The entry's README owns why its half is shaped that way.

## MultiGrabSync — the same composition at four props

`MultiGrabSync.prefab` is `GrabSync` with the `Prop` subtree and its glue layer four times over (`Prop_0..3`, `Grab_0..3`, `Detached_0..3`, homes spread along hip X) and the sync child swapped for **this composition's own four-object build**: `generate.py` drives the entry's generator unmodified at `Prop0..Prop3`, heading-only, one slice each, emitting `object-sync/controller.yaml` beside this file — its header carries the wire, ring, and per-object collision-tag facts the rig prefab is kept against. The rig prefab (`object-sync/ObjectSync.prefab`) is the entry's hand-maintained `y_double/` shape extended to four objects — standalone rather than a variant, because every object is renamed and doubled, which is exactly the delta class variants propagate badly. The glue document is `multi.yaml`: `controller.yaml` at four suffixed layers, kept in lockstep with it — an edit to one is an edit to both. Its one own number is the Bridge timer, **re-derived from the four-object build's measure ring + wire refresh, never copied from the one-prop value** — the derivation is in `multi.yaml`'s header, and it re-derives again if the object count or slice weights change.

`Enable` stays module-wide: off recalls **all four** props, and the two menu items (`GrabSync` / `MultiGrabSync`) are the same toggle under different names — whichever prefab is worn fronts `ObjectSync/Enable`.

## Verifying it

Grab, carry, drop, re-grab on the wearer must feel exactly like the `grab-prop` demo — the cell bindings are that entry's clip table verbatim, and the transcription diff is the check. On a remote clone: a drop glides to the exact spot within ~3 s; a fresh clone shows an already-placed prop **in place** (no fly-in) and its re-grab shows no heading snap; Enable off/on recalls home on both views. The wire itself is `../../object-sync/README.md` §Verifying the install. What the emulator structurally cannot show: animated `VRCPhysBone.m_Enabled` on a remote clone — the fresh-join re-grab — needs the shipping client, two clients in-game.

## Provenance

Each composed entry carries its own ancestry (`grab-prop`, `drag-bone`, `object-sync` READMEs). The cell-versus-word arbitration — one controller subsuming the grab cell's chords and parking the drag heading on the synced yaw — is the shape of a private doll rig, in-game-proven, re-derived here against the shipped entries.
