# grip-sync — an authored-grip prop whose rests are shared truth (Composition)

Take the prop off the wearer and it lands in the same authored grip in every hand on every client; set it down anywhere and everyone in the instance sees it resting exactly there, tilt included, a player who joins later too, and a re-grab picks it up from where it rests with no snap, from any join state. The carry is `absolute-grip-prop`'s: position from the natively synced physbone grab, orientation re-derived on every client from the grabber's palm, an authored grip pose under that frame. The rest is `object-sync`'s: the wearer's frozen pose crosses the wire as an absolute position and full rotation, so placement is exact rather than replayed. One prefab ships, **`GripSync.prefab`**: one prop on this composition's own full-rotation `object-sync` build at the mount prefix, one `Detached` bit on top of its 27-bit wire, **29 synced bits** with `Enable`, 24 contact receivers (12 on the tip, 12 at the sync rig's park), no FinalIK.

## What it composes

| entry | what it contributes |
|---|---|
| `absolute-grip-prop` | the grab/release cell, the palm readout, the hand latch and sign confirm, the authored per-hand grip |
| `object-sync` (entry root: full rotation) | absolute world position + rotation for the rest, late-join included |
| `word-channel` | the wire underneath (reached through `object-sync`) |

Its own contribution, belonging to no entry: the glue arbitrating cell against word (`controller.yaml`, grab-sync's thirteen-state skeleton transcribed with its one `Grabbed` state replaced by the cell's nineteen-state grip sub-graph; the header carries the transcription rules and every design decision), the park that force-aligns the cell's `Rotor` to the synced rotation on every remote so a re-grab starts from the word's attitude rather than a stale per-client freeze, and grab-sync's `Reacquire` dwell and `Resume` cull park carried over whole. It is the third composition of the cell-versus-word family, beside `grab-sync` (a captured-grip cell, a yaw word, a drag heading) and `sync-on-player` (a release-arbitration cell, a position-only word): the shared skeleton is re-derived here, not parameterised there, because grab-sync's graph is hand-authored and a swapped cell is a different document.

Why full rotation and not grab-sync's yaw word: the cell's `Rotor` is a full-axis rotation constraint and the drop freezes it whole on the wearer, so a yaw word would upright the rest on every remote and nowhere else. Why no drag bone: the cell already produces the rotation a drag heading would synthesise. Why not grab-sync for this job: grab-sync serves any prop at eight receivers and one glue controller and ships a four-prop form; this pays twelve tip receivers, a two-layer readout and a third controller for a prop that needs an authored grip. Both stay.

## Install

Drop `GripSync.prefab` under your avatar root. The home anchor is the cell's MA `BoneProxy` targeting **Hips**, so it resolves on any humanoid; drag `Prop/AbsoluteGripProp/HomeAnchor/Offset` to place the rest position, and swap your mesh in for the placeholder hammer at `Prop/Container/Display/Payload` (the entry's three-primitive hammer, whose grip the nested cell's grip nodes already hold), keeping it under `Display`, the node the clips gate for visibility and the cell's re-grab rest frame; the cell's own `Payload` is removed on the nested instance. Author the grip on the nested cell's `Frame/GripR` and `Frame/GripL` exactly as `../../absolute-grip-prop/README.md` §Interface says (its `generate.py --check` pins them on the entry prefab, not here). The menu Toggle **GripSync** fronts `ObjectSync/Enable`, declared default-**on**; off recalls the prop home on every client and is the reset. **Compose `anti-cull` alongside**: the drop is replayed choreography, the orientation is contact tracking and the word decodes only while a remote evaluates the wearer's animator.

**One of `GripSync`, `GrabSync` or `MultiGrabSync` per avatar, never two** — all generate at the entry's default `rigSeed`, so their contact clusters share tags and park. A *different* `object-sync` build can share the avatar at its own `rigSeed` (`../../object-sync/README.md` §Seam), and `ObjectSync/Enable` stays one bare param across every build: this Toggle arms them all, and this build's default-on declaration is first-wins-contested the moment another build shares the avatar.

**Do not enable the two constraints on the prefab root** to make the editor view look pinned — they ship disabled and a VRCFury `ApplyDuringUpload` enables them at build, so seams under them capture poses authored on the body rather than origin-parked ones (`../../../docs/gimmicks.md` §Constraint patterns). Their correct serialized state is all-zero offsets; if one has been disturbed, Zero it, never Activate.

## The arrangement

    GripSync               THE one pin: VRCParentConstraint + VRCScaleConstraint → World.prefab, zero offsets,
                           disabled in editor, ApplyDuringUpload enables at build; + the menu Toggle and the SHARED
                           FullController playing built/GripSync_Fx, readout/built/GripReadout_Fx and
                           object-sync/built/ObjectSync_Fx, glue FIRST in both the controllers list and the prms list
                           (controller.yaml's header owns why both orders are load-bearing)
    ├─ ObjectSync          nested instance of ../../object-sync/ObjectSync.prefab (the entry ROOT prefab: full
    │                      rotation, 12 receivers at the park). Sync_Target gains [Prop/Source w=1], static, never
    │                      animated: the encoder measures the mux output, undamped
    └─ Prop/
       ├─ AbsoluteGripProp nested entry instance: rig untouched but for three overrides — grab physbone parameter
       │                   → `Grab`; GrabPosition source0 → Prop/Container/Display (grab-prop's sanctioned two-source
       │                   repoint, so a re-grab from any word state starts ON the display); Container/Rotor gains
       │                   source3 = ObjectSync/Sync at weight 0, totalLength 4, zero offset (the remote park)
       ├─ Source           the mode mux: position [AbsoluteGripProp/Container/Damped, Sync, HomeAnchor/Offset],
       │                   rotation the same three, ALL axes — the cell's home slot is its own Rotor's full-axis
       │                   HomeAnchor/Offset, so home is value-continuous across the swap; grab-sync's Y-only mask
       │                   serves a drag heading this composition has no use for
       └─ Container        the damper (position and rotation, [Source, self]); Display, a plain child, is both the
                           visibility gate and GrabPosition's rest-anchor frame

This prefab is **not** a variant of either entry prefab: sync-on-player took a variant because its rig differs (nodes deleted, retagged, re-parked); here only the documents differ (mount prefixes), so both entries are nested instances customised by **removal**, the only redirect a VRCFury component supports (`../../../docs/nondestructive.md`), and those removals are recorded here because prose is most of what validates them (`generate.py --check` pins each). On the `object-sync` instance: its `FullController`, its menu `Toggle`, its root `ApplyDuringUpload` and its root pin pair are removed (the shared root component, the composition's Toggle and the composition's pin replace them; the entry's `PinEnable` curves then resolve to nothing, harmless and deliberate), and the Drop toggle on `Sync_Target` is removed (its `FreezeToWorld` writer would fight the glue). On the `absolute-grip-prop` instance: its `FullController` and `Toggle` are removed (its chords live in the glue, its readout is this composition's own regenerated build), its placeholder `Payload` hammer is removed, and its root `FreezeToWorld` GameObject is removed with the arming `ApplyDuringUpload` that rides it (the composition pin owns the world frame); `EditorOnly` is **kept** with its inherited TurnOff `ApplyDuringUpload`.

## The Rotor park, and the ring it closes

grab-sync makes a remote's re-grab snap-free by force-aligning its drag heading to the synced yaw. Here the cell's `Rotor` carries the rotation channel, and the cell freezes it (constraint disabled, holding its last write) from release through every re-acquisition state and re-enables it on the grip only at Confirm. So the park is a fourth `Rotor` source, `ObjectSync/Sync`, that the word states select (home to 0, word to 1, enabled): on a remote in `Synced` the cell's `Rotor` rides the word, the freeze at re-grab then holds the word's attitude, and the grip eases from it at Confirm. No second writer touches `Rotor`; `Damped`'s rotation smoother is unbound in every clip and always chases it. That carve, and grab-sync's `GrabPosition` carve, are the only two departures from the cell's clip values; `generate.py` emits them and its docstring is the record.

This is the first composition to add a source inside the cell subtree, so both precedents' safety clause ("no source this composition adds reaches the cell") does not cover it and the ring was measured rather than inherited. Frame lag under a per-frame ramp of the avatar root, at two ramp rates (identical counts, so the reading is frames and not an artefact of the drive): the cell's `Container` reads `SourcePosition` exactly one frame stale (the capture edge holds, as the hierarchy relation guarantees), `Sync` reads `Sync_Target` one frame stale, and every other node in the new ring is at most one frame behind its source. Re-verify after any change to the constraint graph; `../../grab-prop/README.md` §Verifying the install owns the method.

## Verifying it

Grab, carry, drop, re-grab on the wearer must feel exactly like the `absolute-grip-prop` demo: the cell bindings are that entry's clip table verbatim by construction, read live at emit time. On a remote clone: a drop glides to the exact spot inside about a second, rotation included (measured on a tilted home attitude: under a millimetre and hundredths of a degree from the wearer's rest); a fresh clone shows an already-placed prop **in place** with no fly-in (measured: hidden from spawn until the wire certified, then visible at the word on its first visible frame, never at home); a remote's re-grab from `Synced` starts from the word's attitude with no rotation snap; Enable off/on recalls home on both views. The wire itself is `../../object-sync/README.md` §Verifying the install.

What the emulator structurally cannot show: the grip itself, which needs a snap-on grab and a real palm at the tip (the entry's in-game checklist owns every item, and every one of them holds here unchanged), plus grab-sync's two-client items: animated `VRCPhysBone.m_Enabled` on a remote clone, the fresh-join re-grab, and real network timing on the bridge.

## Provenance

Each composed entry carries its own ancestry (`absolute-grip-prop`, `object-sync` READMEs). The cell-versus-word arbitration is `grab-sync`'s, itself the shape of a private doll rig, in-game-proven; the `Rotor` park is this composition's own re-derivation of that rig's heading park for a cell that carries full rotation.
