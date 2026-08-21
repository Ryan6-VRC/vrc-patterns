# grab-sync — a grab-prop whose drop is the same place for everyone (Composition)

Grab a prop off your chest, carry it live on the native physbone sync, drop it anywhere — and every client, late joiners included, sees it at that exact spot with the heading it was dropped at: grab-prop's sample-and-hold choreography supplies the wearer's exact local feel, `object-sync`'s heading-only build replicates the drop as absolute truth, and `drag-bone` gives the carried prop a travel-direction heading. **29 synced bits** at one prop (the 27-bit wire + `ObjectSync/Enable` + `Placed0`), architected to grow to four props by regenerating `generate.py`'s `PROPS` list, not by rebuild.

## What it composes

| entry | what it contributes |
|---|---|
| `grab-prop` | the grab cell: clip-table choreography (both edge freezes), physbone tuning, home anchor |
| `object-sync` (`y` config, carried) | absolute world position + heading over the wire, late-join truth |
| `drag-bone` (`DragBone_Yaw`) | heading from position history while carried |
| `anti-cull` | compose alongside on the avatar, as both entries' READMEs require; not part of this prefab |

## Ground truth

`generate.py` owns everything derivable: the carried object-sync document (the entry's generator run unmodified — at one prop byte-identical to `object-sync/y/`, and `--check` pins that), the composition's chord document, the bridge-timer formula, and the crossfade length. `--check` also reads both prefabs' serialized wiring — every consumer source slot (`Sync_Target`, `Container`, `LocalPose`, `Follower`, the root pins), zero offsets on all of them (a baked source offset is scale-multiplied in the shipping client but not in the emulator, so it passes every emulator check and misplaces cross-client), and both `globalParams` blocks — the property-level surface a path-resolving audit cannot see. Its module docstring is the design record for the chord law; `docs/local/g5-attempt2-spec.md` argued the architecture. Run `generate.py --check`.

The rig's shape, stated once (the prefab owns the values):

    GrabSync            root: parent+scale pins → object-sync's World.prefab, shipped disabled,
                        ApplyDuringUpload (the entry's PinEnable.anim) re-enables at build;
                        FullController → built/ (globalParams exactly ObjectSync/*)
    ├─ ObjectSync       prefab variant of object-sync/y/: FullController removed-and-added →
    │                   the carried build; the shipped Drop toggle deleted (below); Sync_Target
    │                   takes ONE static source, LocalPose, never animated
    └─ Prop0
       ├─ HomeAnchor    MA BoneProxy → Chest; child Offset = the rest point (drag to taste)
       ├─ GrabRig       grab-prop's cell verbatim (GrabPosition → GrabBone → DropPosition;
       │                SourcePosition = the sample-and-hold), physbone parameter Grab0
       ├─ DragRig       DragBone_Yaw as shipped minus its freeze node; Follower ← LocalPose
       ├─ LocalPose     the MEASURED cell: position ← [SourcePosition], m_Enabled the only
       │                animated property (the release freeze); rotation ← [Drag_Rotation], static
       └─ Container     the DISPLAYED cell, payload inside: position and rotation ← [LocalPose, Sync];
                        weights animated by REMOTE chords only

**The chord law.** On the wearer no weight on the display path ever animates — IsLocal chords bind grab-prop's clip table (mapped: vanilla `Container` → `LocalPose`) with **one pinned deviation**: `grabbed` keeps the chain root anchored to `LocalPose` (`GrabPosition.IsActive` 1) instead of vanilla's root freeze, because a mid-chain freeze cell reads the sample on a fresh edge and captures home at release — vanilla's display survives only through its own cycle's stale edge, a solve-order property nothing serialized pins (measured; `generate.py`'s CHOREO header carries the frame evidence and the ruling). With the root anchored, the tip's release rest *is* the drop and the freeze is order-independent. The wearer rides `Container ≡ LocalPose` through WD-ON defaults; remote chords own the `Container` weights, moved only at the bridge→placed crossfade and the carried entry, both at least one animator frame from any physbone edge. `generate.py --check` asserts the chord law and the mapped binding-superset (the deviation asserted at its own value).

**Placement state.** One merged level-predicated layer per prop: a late joiner receives `Placed0` already true and reaches `RemotePlaced` with no edge witnessed; the witnessed-release `RemoteBridge` is the sole edge-entered path and its miss collapses to the level path. The wearer stamps `Placed0` in `LocalReleased` (localOnly driver; the value syncs). The bridge waits out the measure+wire pipeline because no freshness observable exists — `ObjectSync/Ch/Acquired` certifies a complete table since load, never one containing the post-release commit — and its length derives in `generate.py`, terms named.

**Enable, and the one trap to not re-create.** The composition mints no second enable: `ObjectSync/Enable` is the master gate (the "Grab Sync" Toggle on the ObjectSync variant drives it), off-is-reset — the off chord recalls home, clears `Placed0` on the wearer and `Grab0_IsGrabbed` on every client. The menu Toggle is the only writer: a fast off→on inside one animator evaluation permanently deafens the measure receivers for the session (`object-sync/README.md` §The gate's reach), so nothing may pulse it.

**Visibility** is `IsLocal OR grabbed OR (Enable AND engaged)`, where `engaged` (`GS/Engaged`) latches on `Acquired` delayed by at least one driver frame and releases only on Enable-off — deliberately looser than the entry's three-term consumer predicate, so a cull resume holds the last-decoded pose instead of blinking the prop (a stated deviation, mirroring the entry's own `Follow` latch; the cull-resume hold is on the two-client observation list). The wearer therefore sees the prop even with Enable off, parked home; remotes hide it.

## Deviations from the composed entries, each with its reason

- **The entries' own FreezeToWorld nodes are deleted** (grab-prop's root freeze + EditorOnly aligner, drag-bone's): the whole subtree sits under the GrabSync root pin, and `spring-damping/README.md` prices reusing a pin over adding a freeze (second component, capture edge, build-time gate).
- **drag-bone's Follower sources `LocalPose`, not the displayed `Container`** (the entry's §Combinations seam says container): on the wearer `Container ≡ LocalPose` so the seam's intent is preserved, and on a remote the drag bone must trail the *replayed* motion, never chase the bridge crossfade — sourcing the display would swing the heading through the glide.
- **object-sync's shipped Drop toggle is deleted**: the drop here is grab-prop's own choreography; a second `FreezeToWorld` writer on `Sync_Target` would violate the entry's two-writer rule, and deleting it reclaims its synced bit.
- **grab-prop's `GrabProp/Enable` Toggle is deleted with its seam**: one gimmick, one front; a second synced bit would buy nothing.

## Verifying the install

The cheapest observable set, off-origin and off-axis (a rig frame that quietly stayed avatar-relative reads correct at the origin): grab from home and from a placed spot — the container must never flash to home/chest on any frame of either edge; release — zero creep after the freeze lands, including after six rapid grab/whip/release cycles; a remote clone's `Container` must reach each drop at quantization scale (sub-millimetre, heading within ~0.05°) with `ObjectSync/Ch/Acquired` true, riding weights 0/1 only after the bridge. The wearer's at-rest heading must be bit-identical across seconds — any dither means the display is riding something live.

What the emulator structurally cannot show (two-client/operator items): remote `_IsGrabbed` regeneration and the transitions behind it as naturally triggered, the swap glide's feel, mid-grab late-join, the bridge dwell against real network settle, the cull-resume visibility hold, and client-jitter heading dither at rest (a declared client-tier residual).

## Provenance

`grab-prop`, `object-sync`, `drag-bone` and `anti-cull` are this library's own entries; their provenance chains (VRLabs Custom-Object-Sync and World-Constraint ancestry, VRCFury's Parameter Compressor) are recorded in each. The per-channel LocalPose/Container split is generalized from a private production avatar's doll rig, re-derived and measured rather than copied.
