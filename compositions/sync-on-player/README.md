# sync-on-player — drop-on-player's release arbitration on a position-only object-sync (Composition)

Grab a prop off your head and release it: on your own head it anchors, on another player's head it catches and rides them, anywhere else it freezes — and unlike the bare `drop-on-player`, every client including a late joiner sees a placed or tracked prop **in the right place**, because the drop's absolute position rides `object-sync`'s word. The entry's fail-visible gap — "a tracked or dropped prop stays hidden until a witnessed grab, since that position never crossed the wire" — is what this composition closes: remotes ride the reconstruction until their own cage can latch, and a settled-word detector hands them off to live tracking with no pop — "settled" is deliberately loose: a slow walking carry hands off mid-motion, and only a brisk mover holds the remote on the word (the detector's ε and the full derivation live in `controller.yaml`'s header, §Settle). Synced cost: **29 bits** — the entry's 2-bit mode pair + `ObjectSync/Enable` + this build's 26-bit position-only wire.

## What it composes

| entry | what it contributes |
|---|---|
| `drop-on-player` | the release arbitration (own head / other head / world), the 2-bit mode pair, the box cage, the grab/freeze cell |
| `object-sync` (position-only) | absolute world position for the tracked and dropped modes, late-join included |
| `box-tracker` | the Searching configuration `Seeking` ports (via `drop-on-player`, whose cage is that entry's) |
| `word-channel` | the wire underneath (reached through `object-sync`) |

Its own contribution, belonging to no entry: the seventeen-state glue arbitrating cell, cage, and word (`controller.yaml` — its header carries every design decision and carve), the settled-word detector that gates remote cage acquisition, the sensor-first remote edge-latch, and the wearer's 5 s loss-grace dwell.

## Install

Drop `SyncOnPlayer.prefab` under your avatar root. Swap your mesh in for the sphere at `Prop/Container/Display/Payload`, keeping it under `Display` — the node the clips gate for visibility and the repointed grab rest frame. The menu ships as an asset (an **Enable** toggle and a momentary **Recall to Head** button) under the FullController's menu prefix; Enable is declared default-**on** and unsaved, so the prop spawns armed at the head and an off never persists into a fresh load. `DropOnPlayer/HeadMount` is an MA `BoneProxy` targeting **Head**, so the anchor resolves on any humanoid; drag its `AnchorOffset` child to place the anchored rest.

**Compose `anti-cull` alongside** — its README owns the one-instance rule; the tracked and dropped modes replay choreography and decode the word only while a remote client evaluates the wearer's animator.

**Instance rule**: never two object-sync builds sharing a namespace, collision tags, or park on one avatar — duplicate copies of this prefab included. A different-`rigSeed` build (`compositions/grab-sync` at the entry default) composes beside this one, each paying its own wire — this build generates at `rigSeed "sync-on-player/g6"` (`generate.py`), which skews its tags and park off the default together. **`ObjectSync/Enable` stays one bare param across every sealed build on the avatar**: the Enable toggle here arms a composed grab-sync too, by design (the entry's §Seam), and this build's default-on declaration is first-wins-contested the moment another build shares the avatar.

**Do not enable the two constraints on the prefab root** to make the editor view look pinned — they ship disabled and a VRCFury `ApplyDuringUpload` enables them at build, so seams under them capture poses authored on the body rather than origin-parked ones (`../../../docs/gimmicks.md` §Constraint patterns). Their correct serialized state is all-zero offsets; if one has been disturbed, Zero it, never Activate.

## The arrangement

    SyncOnPlayer           THE one pin: VRCParentConstraint + VRCScaleConstraint → World.prefab, zero
                           offsets, disabled in editor, ApplyDuringUpload enables at build; + the SHARED
                           FullController playing built/SyncOnPlayer_Fx and object-sync/built/ObjectSync_Fx,
                           in that order, with the menu asset (controller.yaml's header owns why both the
                           controllers order and the prms order are load-bearing)
    ├─ ObjectSync          this composition's own position-only build at its own rigSeed, a PREFAB VARIANT
    │  │                   of the entry prefab: Rot/ and Recon/ deleted, Display's rotation constraint
    │  │                   deleted, contacts retagged and the rig re-parked per the generated document,
    │  │                   the entry's own FullController/Toggle/ApplyDuringUpload/pin pair and
    │  │                   Sync_Target's Drop toggle REMOVED (remove-only — the shared root component is
    │  │                   the only merge door). Sync_Target gains [Prop/Source w=1], static, never
    │  │                   animated: the encoder measures the mux output, undamped.
    │  └─ Sync/CagePark    plain constraint-free child, the word-side cage park: it carries
    │                      Container/TrackingOffset's below-the-prop offset, so at a latch the cage sits
    │                      at word − RideOffset and the prop at cage + RideOffset = word (value-continuous)
    └─ Prop/
       ├─ DropOnPlayer     nested entry instance. Removed: the root FreezeToWorld node, whose arming
       │                   ApplyDuringUpload rides that GO and goes with it (the composition pin owns
       │                   the world frame; EditorOnly keeps its own inherited TurnOff
       │                   ApplyDuringUpload, riding the kept GO), the Payload sphere, and the entry's FullController (the glue's machine replaces it
       │                   whole). Overridden:
       │                   the grab physbone's parameter → `Grab`; GrabPosition's source0 → the
       │                   composition Display (grab-prop's sanctioned two-source repoint, so a re-grab
       │                   from any word state starts ON the display); TrackingPoints' park constraint
       │                   gains source1 = CagePark. Everything else — the cell (Container with
       │                   SourcePosition nested under it, the structural stale edge, UNTOUCHED),
       │                   HeadMount/AnchorOffset, TrackedPoint/RideOffset, the cage, EditorOnly — is the
       │                   entry's rig whole.
       ├─ Source           the mode mux: VRCPositionConstraint, 4 sources [AnchorOffset, entry Container
       │                   (the cell), TrackedPoint/RideOffset (the cage), ObjectSync/Sync (the word)] —
       │                   weights are the glue's value-sets
       └─ Container        the damper: VRCPositionConstraint [Source, self]; child Display is the
                           visibility gate and the payload mount

The nested instances are customised by **removal**, the only redirect a VRCFury component supports (`../../../docs/nondestructive.md`), and those removals are recorded above and pinned by `generate.py --check`.

The park↔word ring this adds exists in the constraint graph on every client — solve order derives from sources and targets and never consults weights. The safety argument: the cell's capture edge is hierarchy-authored and no source this composition adds touches any cell-ring constraint, and every edge of the new ring tolerates a one-frame stale read (park, encode-measure, display are all continuous follows). Verify by frame lag over the new ring's edges, never by group index — `../../grab-prop/README.md` §Verifying the install is the method.

## Before you compose it

- **A wrong remote latch is stable once made**: the cage follows the wrong head faithfully until an edge (wearer re-grab or recall, a pair re-stamp, Enable cycle). Prevention — the settled-word gate, the catch-column geometry — is the whole defense; the wearer's view is always correct and the wire never carries the error. Contacts carry no identity (every head is the standard `Head` tag), so geometry and timing are the only discriminators and the wearer's recall is the standing cure.
- **The wearer's loss grace arms windows**: through a `Seeking` dwell the pair holds 11, so a bystander head entering the reopened zone latches authoritatively, and remotes' own re-latches can diverge per-client with no self-correction until an edge. Accepted at sign-off; the two-client checklist exercises it.
- **A joiner mid-carry over a stale `01` sees the prop anchored** until the release re-stamps the pair — accepted at zero bits. Stale `10`/`11` joiners ride the word trailing the carry, the transport's declared stepped reconstruction.
- **The word is live in every mode** (`Sync_Target` always measures the mux), so an anchored prop's word carries the wearer's head position — unread by design: every state that could read it routes to `Anchored` first.
- **Enable-off mid-grab keeps the entry's stale-`_IsGrabbed` simplification** — no force-release driver ships, matching the entry; a consumer needing a clean force-release adds a driver clearing `Grab` to the off state.
- The wearer's rejoin resets the unsaved pair to 00: prop home.

## Verifying it

Grab, carry, release on the wearer must feel exactly like the `drop-on-player` demo — the cell bindings are that entry's clip table verbatim, and its release ladder (own head / other head / world) is unchanged. The transition set is checked by hand against the entry's `controller.yaml` — every entry rung must survive, re-route under a decision the glue header names, or be dead by reachability — and an edit to either machine's transitions re-runs that check. `SelfDetect` must read 1.000 at rest on the wearer's own head sender — a module-scale minimal rig reads 0 (`docs/emulator.md`) and silently loses the anchored branch, so verify on a full avatar. On a remote clone: a drop glides to the exact spot in ~1 s; a fresh clone shows an already-placed prop **in place** (no fly-in); Enable off/on recalls to the head on both views; a local tracking loss seeks 5 s at the loss point, then freezes in place. The wire itself is `../../object-sync/README.md` §Verifying the install.

What the emulator structurally cannot show — every item below needs a real second player's client: their IK-delayed body senders, that client's own arbitration, real network timing (`../../../docs/verify.md`) — handed to the in-game two-client checklist instead: the remote edge-latch on a moving recipient and its ≤-one-pulse disagreement flash; wrong-head and crowd behavior under the settled gate, the slow-carry variant and the Seeking-window bystander latch included; the avatar-swap reacquire; FBT sway against the detector's ε at rest and at range; re-latch robustness where word-vs-rendered disagreement approaches the cage half-width; Seeking against real occlusion loss; cull resume in Tracked and SyncedTrack; the Enable double-click receiver-deafness class; chase feel.

## Rebuilding

`generate.py` emits `object-sync/controller.yaml` (the entry's generator unmodified, at this composition's CONFIG); both documents compile with `CompileController` into the `built/` beside each.

## Provenance

Each composed entry carries its own ancestry (`drop-on-player`, `object-sync`, `box-tracker` READMEs). The cell-versus-cage-versus-word arbitration — release arbitration kept whole under a composed absolute-position word, with the settled-word acquisition gate and the loss-grace dwell — is the shape of a private production avatar's carried-doll system, in-game-proven, re-derived here against the shipped entries.
