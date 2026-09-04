# grab-sync — grabbable props whose drops are shared truth (Composition)

Grab a prop off your hip, carry it, set it down anywhere: everyone in the instance sees it in that spot — a player who joins later included — and a re-grab picks it up from where it rests with no snap, from any join state. Grabbing is a physbone (natively networked, so remotes see the carry live), heading comes from a drag bone trailing the motion, and the drop's absolute position and yaw ride `object-sync`'s word so placement is exact rather than replayed. Two prefabs ship: **`GrabSync.prefab`** (one prop, this composition's own single-prop `y` build at the mount prefix — `object-sync-single/` — one `Detached` bit on top of its 27-bit wire — 29 synced bits with `Enable`) and **`MultiGrabSync.prefab`** (four props on this composition's own regenerated four-object build — 29 wire bits time-sliced across the props, plus `Detached_0..3`).

## What it composes

| entry | what it contributes |
|---|---|
| `grab-prop` | the grab/release cell: physbone grab, the constraint-freeze drop capture, home recall |
| `drag-bone` | yaw heading from a drag sim trailing the carry |
| `object-sync` (`y/`) | absolute world position + heading for the drop, late-join included |
| `word-channel` | the wire underneath (reached through `object-sync`) |

Its own contribution, belonging to no entry: the thirteen-state glue layer arbitrating cell against word (`controller.yaml` — its header carries every design decision), the park that force-aligns the drag heading to the synced yaw on every remote so re-grab is snap-free, and the `Reacquire` dwell that keeps a remote's re-grab from flashing the stale cell.

## Install

Drop `GrabSync.prefab` under your avatar root. The home anchor is an MA `BoneProxy` targeting **Hips**, so it resolves on any humanoid; drag `Prop/GrabProp/HomeAnchor/Offset` to place the rest position, and swap your mesh in for the sphere at `Prop/Container/Display/Payload`, keeping it under `Display` — the node the clips gate for visibility and GrabPosition's rest-anchor frame; the cell's own `Payload` is removed on every nested `GrabProp` (`../../grab-prop/README.md` owns the cell's rig rules). The menu Toggle **GrabSync** fronts `ObjectSync/Enable`, declared default-**on**; off recalls the prop home on every client.

**One prefab per avatar — GrabSync or MultiGrabSync, never both** — both generate at the entry's default `rigSeed`, so their contact clusters share tags and park. A *different* `object-sync` build can share the avatar: the entry's interface is sealed per FullController component, and coexistence needs only a distinct `rigSeed` on the other build (`../../object-sync/README.md` §Seam owns the rules). `ObjectSync/Enable` stays global and shared — the menu toggle here arms every sealed build on the avatar at once, by design.

**Do not enable the two constraints on the prefab root** to make the editor view look pinned — they ship disabled and a VRCFury `ApplyDuringUpload` enables them at build, so seams under them capture poses authored on the body rather than origin-parked ones (`../../../docs/gimmicks.md` §Constraint patterns). Their correct serialized state is all-zero offsets; if one has been disturbed, Zero it, never Activate.

## The arrangement

    GrabSync               THE one pin: VRCParentConstraint + VRCScaleConstraint → World.prefab, zero
                           offsets, disabled in editor, ApplyDuringUpload enables at build; + the menu
                           Toggle and the SHARED FullController playing built/GrabSync_Fx and
                           object-sync-single/built/ObjectSync_Fx, in that order (controller.yaml's
                           header owns why the order is load-bearing)
    ├─ ObjectSync          nested instance of ../../object-sync/y/ (heading-only), its FullController
    │                      removed: the root's SHARED FullController plays this composition's own
    │                      mounted single-prop build (object-sync-single/) beside the glue — the
    │                      sealed-interface coupling, glue FIRST (first-wins arms Enable)
    └─ Prop/
       ├─ GrabProp         nested grab-prop instance: rig untouched, grab physbone parameter → `Grab`
       ├─ DragBone_Yaw     nested drag-bone instance + the park glue (a rotation constraint on
       │                   Follower ← Container, normally inactive — yaw-only transitively, via Source)
       ├─ Source           the mode mux: position [GrabProp/Container, Sync, HomeAnchor/Offset],
       │                   rotation [Drag_Rotation, Sync, home] — weights are the glue's value-sets;
       │                   the rotation constraint affects Y only (drag-bone's yaw-only consumer
       │                   contract): the home slot rides the hips, and a full-axis follow would tilt
       │                   the anchored prop with the wearer's IK lean
       └─ Container        the display + damper (payload rides it); Display, a plain child, is both the
                           visibility gate and GrabPosition's rest-anchor frame (the two-source repoint
                           ../../grab-prop/README.md §How it works sanctions)

Unlike `object-sync-demo`, this prefab is **not** a variant of the entry prefab — the entry is a nested child and the composition root carries the only pin. The nested instances are customised by **removal**, the only redirect a VRCFury component supports (`../../../docs/nondestructive.md`), and those removals are recorded here because prose is most of what validates them: `grab-prop`'s `FullController` and `Toggle` are removed (its chords live in the glue controller) along with its placeholder `Payload` sphere on every nested instance (the visible payload lives under `Prop/Container/Display`); `object-sync`'s own `FullController` is removed — the shared root component replaces it (run `generate.py --check`); its shipped Drop toggle on `Sync_Target` is removed (its `FreezeToWorld` writer would fight the glue), as are its root's own menu `Toggle` and `ApplyDuringUpload` (the composition fronts Enable and arms the one pin itself); and the `object-sync` root's own pin pair is removed so the built avatar holds exactly one World-sourced pin — the entry's `PinEnable` curves then resolve to nothing, which is harmless and deliberate.

## Capture order

The cell's release capture survives only when `GrabProp/Container` reads `Container/SourcePosition` one frame stale, and that edge is fixed by the cell's own hierarchy — the sample node is a child of the node whose constraint reads it, which puts that reader in the earlier solve group by construction (`../../grab-prop/README.md` §How it works owns the rule and its measurement). Nothing outside the cell arranges it, and no source added anywhere on this composition reaches it.

What this composition holds that the entry cannot see is five nested copies of that cell, each one an instance override away from losing the relation: a nested modification that re-parents or re-poses `SourcePosition`, or adds a source to its constraint, drops the capture with every clip and every compiled value identical. Run `generate.py --check`. The entry's pass criterion then applies per prop — `Container` reads stale, verified by frame lag — `MultiGrabSync`'s four included, with nothing per-prop left to wire.

## MultiGrabSync — the same composition at four props

`MultiGrabSync.prefab` is `GrabSync` with the `Prop` subtree and its glue layer four times over (`Prop_0..3`, `Grab_0..3`, `Detached_0..3`, homes spread along hip X) and the sync child swapped for **this composition's own four-object build**: `generate.py` drives the entry's generator unmodified at `Prop0..Prop3`, heading-only, one slice each, emitting `object-sync/controller.yaml` beside this file — its header carries the wire, ring, and per-object collision-tag facts the rig prefab is kept against. The rig prefab (`object-sync/ObjectSync.prefab`) is the entry's hand-maintained `y_double/` shape extended to four objects — standalone rather than a variant, because every object is renamed and doubled, which is exactly the delta class variants propagate badly. The glue document is `multi.yaml`: `controller.yaml` at four suffixed layers, kept in lockstep with it — an edit to one is an edit to both. Its one own number is the Bridge timer, **re-derived from the four-object build's measure ring + wire refresh, never copied from the one-prop value** — the derivation is in `multi.yaml`'s header, and it re-derives again if the object count or slice weights change.

`Enable` stays module-wide: off recalls **all four** props, and the two menu items (`GrabSync` / `MultiGrabSync`) are the same toggle under different names — whichever prefab is worn fronts `ObjectSync/Enable`.

## Verifying it

Grab, carry, drop, re-grab on the wearer must feel exactly like the `grab-prop` demo — the cell bindings are that entry's clip table verbatim, and the transcription diff is the check. On a remote clone: a drop glides to the exact spot within ~3 s; a fresh clone shows an already-placed prop **in place** (no fly-in) and its re-grab shows no heading snap; Enable off/on recalls home on both views. The wire itself is `../../object-sync/README.md` §Verifying the install. What the emulator structurally cannot show: animated `VRCPhysBone.m_Enabled` on a remote clone — the fresh-join re-grab — needs the shipping client, two clients in-game.

## Provenance

Each composed entry carries its own ancestry (`grab-prop`, `drag-bone`, `object-sync` READMEs). The cell-versus-word arbitration — one controller subsuming the grab cell's chords and parking the drag heading on the synced yaw — is the shape of a private doll rig, in-game-proven, re-derived here against the shipped entries.
