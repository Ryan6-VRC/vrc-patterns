# grab-mux-sync — four grabbable props on one 4-object position sync (Composition)

Four props that live on the avatar, can each be grabbed off it, carried, and set down anywhere in the world — in the same place for everyone, late joiners included. While a prop moves it rides its natively-synced physbone grab, so motion costs zero wire; the shared object-sync build only ever carries rest poses, which is the regime where its speed ceiling and multi-object refresh stretch stop mattering. The packaged novelty is that division of authority — grab-mux in motion, absolute sync at rest, a per-client sample-and-hold bridging the gap between them — at **34 synced bits total** for all four props (29-bit wire + master enable + four placed bits).

## What it composes

| entry | what it contributes |
|---|---|
| `object-sync` | the 4-object y-mode build: absolute world position + heading for each rest pose |
| `word-channel` | the wire underneath it (reached through `object-sync`) |
| `grab-prop` | the grab physbone tuning and the release sample-and-hold, cloned per prop |
| `drag-bone` | heading from position history while a prop moves, cloned per prop (yaw variant) |
| `spring-damping` | the per-prop damper (the combined parent-constraint variation) |
| `anti-cull` | keeps a view-culled wearer's decode running (`object-sync`'s declared dependency) |

Its own contribution, belonging to no entry: the placement state machine that swaps each prop between home anchor, grab, held drop point, and reconstruction — and the timing that keeps a remote off a stale word.

## Install

Drop `GrabMuxSync.prefab` under your avatar root. The four `HomeAnchor`s are MA BoneProxies onto the humanoid **Chest**, so they resolve on any humanoid rig; the placeholder cubes hover chest-forward at four offsets — drag each `HomeAnchor/Offset` to taste, and swap each `Damped/Container` cube for your prop mesh. The root's two pinning constraints ship **disabled** and a VRCFury `ApplyDuringUpload` re-enables them at build, so the composition builds correctly from any scene position and scale; do not enable them in the editor (`../../docs/gimmicks.md` §Constraint patterns owns the swap and the trap it prevents). The menu front is the entry's own `Object Sync` toggle — one master enable, off is the reset that recalls all four props home.

The composition is single-instance for `object-sync`'s own reason (fixed collision tag strings), and its `generate.py` is the retune surface: the carried 4-object build's CONFIG, the release→swap delay, and the damper weight are all authored there, `--check` pinning both emitted documents and the prefab's `globalParams` blocks against it.

## The arrangement

    GrabMuxSync            VRCParentConstraint + VRCScaleConstraint -> World, both disabled in the editor
                           [VF FullController = GrabMux_Fx] [VF ApplyDuringUpload = assets/PinEnable.anim]
    ├─ ObjectSync4         the carried 4-object measure rig [VF FullController = ObjectSync_Fx]:
    │                        Rig/Prop0..3 (shared park, per-object tags), SyncProp0..3_Target, SyncProp0..3
    └─ Prop<N>/            ×4
       ├─ HomeAnchor       MA BoneProxy -> Chest; child Offset = the rest point
       ├─ GrabRig/         grab-prop's cell: GrabPosition -> GrabBone chain -> DropPosition; SourcePosition = the sample-and-hold
       ├─ DragRig/         drag-bone yaw: Follower (source = SourcePosition, upstream of the display chain) -> Drag_Rotation
       ├─ Carry            pose composer: position <- SourcePosition, rotation <- Drag_Rotation (two constraints, disjoint channels)
       ├─ Mux              sources [SyncProp<N>, Carry, HomeAnchor/Offset], weights animated one-hot
       └─ Damped           [Mux, self] — one combined damper, riding under the pinned root; holds Container (the visible prop)

This is `object-sync`'s pin → mux → damper → content idiom (its README §Composing against Sync owns the law), instanced per prop. `Sync<N>_Target` carries the consumer sources the entry deliberately ships empty — `[HomeAnchor/Offset, Carry]`, weights animated by the rig layers — and the entry's shipped per-object `Drop` toggles are **deleted** from the carried arrangement: the release choreography owns the rest hold instead, and a second writer plus an unbudgeted synced bit is what leaving them would cost.

**Who owns heading when.** The drag-bone is the heading source *everywhere a prop moves* — every client re-derives it from its own view of the grab at zero bits — and the synced 24-bit heading word is the truth *at rest*, which is what a late joiner's drag-bone (no position history) can never reconstruct. They agree on the wearer by construction, because the sync measures the heading the drag-bone held at the drop.

**The release choreography, per client.** On a witnessed `_IsGrabbed` falling edge: `SourcePosition`'s constraint pulses off→on→off (grab-prop's freeze-then-resample, widths verbatim — its README owns why the pulse is sample-delivery insurance), the wearer stamps `Placed<N>` (localOnly driver; the value syncs), and the display holds the local drop point through the Bridge state. A remote swaps to the reconstruction only after the Bridge timer — sized in `generate.py` as full measure ring + full wire loop + fine-stage re-lock + buffer, because until a post-release commit has crossed the wire, the word table still names a mid-carry pose. The swap is a damped glide over the remote-vs-wearer drop disagreement (IK-delay-sized), so the timer's exactness is not load-bearing. Every other placement state is entered by predicate on current values; Bridge is the sole edge-entered state, so no reset, cull resume, or missed edge can wedge a remote.

**Visibility** is `IsLocal OR grabbed OR (Enable AND sync-engaged)`, where sync-engaged latches like the entry's own `Follow` layer — engage on `Ch/Acquired` plus a one-time settle dwell, release only on Enable-off — so a cull resume never blinks the props. A prop at home shows on Enable alone (nothing decoded is displayed there), and a witnessed release enters the shown rest state directly, skipping the cold path's hide-and-dwell.

**`PinEnable.anim` is hand-maintained and ungated, so its content is specified here** (the object-sync-demo precedent): two float curves at `path: ""`, `VRCParentConstraint.m_Enabled` and `VRCScaleConstraint.m_Enabled`, both value 1.

## Known limits, recorded not fixed

- A late joiner landing inside the release→swap window rides a word table still holding the previous rest, then glides — bounded by the Bridge timer.
- A joiner who does not receive an in-progress grab (whether the live grab reaches late joiners is client-unconfirmed either way) shows a carried prop at its home anchor until the next release; the state machine is correct under both outcomes.
- The damper is live while carried, so the prop trails the hand by τ×speed (`../../docs/runtime.md` §Constraints owns the law; the weight is `generate.py`'s) — retune there if the lag reads wrong in a wear test.
- `Placed` is unsaved by design: a placed pose is runtime state (sample-and-hold captures plus an unsaved word table), so persisting the flag across sessions would point at nothing.

## Verifying the install

Enable on: four cubes at the wearer's chest, riding the body. **All four sitting at the world origin instead is the one high-value fingerprint**: `Sync<N>_Target`'s consumer sources are missing or dead, so every Sync-mediated path collapses to the origin-pinned rig — check those source lists first, not the state machines. Grab one, drag it, release: it must follow the hand (yawing to face travel), hold at the drop point on release, and a re-grab must pick up in place. On a remote clone with `Ch/Acquired` true, a placed prop sits at the same world point within quantization; the clone's un-placed props show at its own chest anchors immediately on Enable.

What the emulator structurally cannot show for this composition: everything `object-sync` declares, plus the whole remote-side grab family — the emulator does not regenerate a clone's `_IsGrabbed` from the wearer's grab (measured), so the remote Carried and Bridge states, the timed swap-and-glide, mid-grab late-join delivery, and carry/settle feel are a two-client operator checklist by construction.

## Provenance

The grab-mux-then-settle authority split is generalized from a private companion-doll rig (which also independently arrived at the mux → damper → content chain this composition instances); the composed entries carry their own ancestries (`object-sync` from VRLabs' Custom-Object-Sync, the wire from VRCFury's Parameter Compressor, `spring-damping` from VRLabs' constraint rigs). No vendor geometry ships; the props are placeholder cubes on Unity's built-in default material.
