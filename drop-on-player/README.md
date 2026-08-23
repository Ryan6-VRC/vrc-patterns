# drop-on-player — release-arbitrated prop: own head / another player / world (Module)

Grab the prop and release it: on your own head it anchors (a bone constraint); on another player's head it catches and follows them (a `box-tracker` 4-box cage with a tall head-catch zone); anywhere else it freezes (sample-and-hold). The three rest mechanisms are structurally different because you *cannot constrain to another avatar's transform* (`gimmicks.md` §Constraint patterns "Attaching a prop to a body point") — the release-time **arbitration** between them, plus the 2-bool mode sync that lets every client re-derive it, is what this entry ships. Module total: **2 synced bits** (`DropOnPlayer/Out`, `DropOnPlayer/Worn`).

**Provenance:** generalized from a private production avatar's carried-doll system; its tracking cage is `box-tracker`'s 4-box exact readout, lifted whole and wear-tested in-game. Not a compose of `grab-prop` + `box-tracker` — one compressed controller reusing their measured idioms.

## Ground truth

Parameters — the synced `Out`/`Worn` pair (the pair *is* the rest mode: `00` disabled · `01` anchored · `11` tracked · `10` dropped), the unsynced menu intents (`Enable`, `ToHead`), and the sensing floats — are declared in `controller.yaml` with their sync/save flags and the arbitration rationale in its header. Two seam facts no artifact states:

- The four box-cage receivers are `localOnly: 0` **by necessity** — remotes re-derive the chase from them — while `SelfDetect` is `localOnly: 1` (routing input only; its outcome syncs as the pair). Menu intents stay unsynced, so the menu costs 0 extra synced bits.
- **Seam:** VRCFury `FullController` (FX, `basis: mount-root`) merging `built/`'s params + menu at prefix `Drop On Player`. `globalParams` is **empty**: with two controls the menu ships as an asset, so `RewriteParamName` takes control and parameter together and nothing escapes to the host avatar. **Plus one MA `BoneProxy`** on `HeadMount` → the wearer's Head bone — a mixed seam, needed so the anchor's placement is visible while authoring. `HeadMount` is referenced only as a constraint source; no VRCF clip binding paths through it.

**Dependencies:** VRC SDK + VRCFury + Modular Avatar to build; **compose `anti-cull` alongside** (its README §When a module needs this) — the tracked and dropped modes replay choreography while the payload is away from the wearer.

**Required assets:** `assets/World.prefab` — a never-instantiated absolute-meters scale reference the cage constraint-pins to; do not instantiate or delete it. The menu regenerates from `controller.yaml`'s `menu:` block. `Payload` is a placeholder sphere — swap it, keep it under `Container`.

## How it works

The prop (`Container`) multiplexes three position sources: anchored, grabbed/dropped (sample-and-hold), and tracked (riding the cage). The same four box receivers that track a target double as the "is another player's head here" sensor: parked they ride below the prop at head-contact level; tracking, they reconstruct the target's exact position, the cage eases onto it, then crawls to keep station (`box-tracker`). The prop rides the cage, never the raw readout.

**Release arbitration** (priority top-down, evaluated by the wearer): self receiver fires → anchored; all four boxes fire → tracked (the cage latches `allowOthers` shut); neither → a `grab-prop` release pulse → dropped. The winning branch's localOnly driver stamps the synced pair at release.

**Remotes** resolve from the synced pair rather than local sensors, freezing the prop on every release and self-correcting if the pair changes. **Tracking loss also freezes the prop in place** rather than snapping it home, for wearer and remote alike, since observers unload a distant target at different times. **Late joiners** dwell a boot timer, then resolve from the pair alone — anchored or hidden resolve at once, but a tracked or dropped prop stays hidden until a witnessed grab, fail-visible since that position never crossed the wire.

**Anyone can grab it** (`allowGrabbing` on, native sync): a friend can take the prop off your head and put it on theirs, since the wearer's client arbitrates from wherever the prop is. `allowPosing` is off — persistence is always a constraint hold.

## Empirical constants (90% rule — test before changing)

Values live at the sites named here, not in this README.

| Constant | Where it lives / the relation |
|---|---|
| Released pulse phases | the `released` clip's phase keys, owned by `grab-prop`'s rig — the remote release-settle below is defined against this pulse's length |
| Remote release-settle | = the `released` pulse length (remotes route by pair at pulse end); must cover the sync tick or a world drop flashes through a stale mode first |
| Remote boot dwell | the `timer` clip's length — long enough for the synced pair to arrive before a late joiner poses off it |
| Head-catch column | prefab `TrackingPoints` rest `localScale` + `ScaleAtRest` (zone side = 3 × scale/axis), taller than wide so lowering onto a head catches down the column; doubles as the arbitration zone |
| Crawl gain | per `box-tracker`'s crawl-gain row; boxes pinned absolute to `World.prefab` so avatar scale never skews the readout |
| Loss / acquire | **ANY** box near zero loses (one dead box breaks the exact reconstruction) / all four positive acquires |
| Physbone / anchor | physbone cloned from `grab-prop`'s rig (see its Rig); `AnchorOffset` must exceed `RideOffset` in local Y — head bone sits at the neck while the cage converges on head-contact center, so re-check per avatar |

## Verifying the install

At rest on the wearer, `SelfDetect` must read 1.000 off the avatar's own standard `Head` sender. **Zero means the descriptor carries no head collider slots** — a module-scale minimal rig reads zero (`docs/emulator.md`) — and every release then arbitrates as a world drop, silently losing the anchored branch.

For the tracker: with the prop grabbed, put a scripted `Head` sender (`docs/emulator.md`) into the catch column and release — the four `X+/X-/Y+/Z+` floats leave zero together, filters shut, `Output` lands on the sender. A partial box set that never all-fire means the column doesn't suit this avatar's head placement. Loss is **ANY-box** — a target leaving even one box's core drops the prop.

Two clients in-game, not the emulator: remote-side cage re-derivation (clone receivers hold spawn-time fossils and are never simulated), the witnessed grab/release choreography (`_IsGrabbed` does not transport to a clone), the remote release-settle dwell, chase feel under real IK, and culling against a genuinely distant or occluded player.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place; positions and constraint/physbone values live in the prefab. Constraint `Locked` on, source weights swapped by the clips. Topology and why each node exists:

    DropOnPlayer                   root — VRCFury FullController
    ├─ Container                   VRCPositionConstraint, 3 sources: AnchorOffset (anchored),
    │  │                           SourcePosition (grabbed/dropped), TrackedPoint/RideOffset (tracked)
    │  ├─ Payload                  placeholder sphere — swap for your prop, keep under Container
    │  ├─ TrackingOffset           self receiver (Head tag, allowSelf ON / allowOthers OFF, localOnly)
    │  │                           → SelfDetect; also the cage's park source
    │  └─ SourcePosition           the sample-and-hold cell; samples the cage while Tracked. Nesting it
    │                              under Container is load-bearing: Container's own constraint reads it
    │                              (source1), so Container solves in the earlier group and reads the
    │                              sample one frame stale — the capture authored by the hierarchy, not
    │                              the solver's roll (grab-prop §How it works owns the rule and the
    │                              measurement; runtime.md §Constraints owns the invariant). Never flatten it.
    ├─ HeadMount                   MA BoneProxy → Head (AsChildAtRoot) + VRCHeadChop: the local head
    │  │                           zero-scales in first person, which would collapse AnchorOffset
    │  └─ AnchorOffset             anchored rest point, in the head-bone frame
    ├─ TrackedPoint                rides the cage
    │  └─ RideOffset               tracked rest point, above the cage — the prop rides like a hat
    ├─ TrackingPoints              the catch column; park constraint rides the prop, crawl-feedback
    │  │                           constraint eases onto Output, scale constraint pins boxes to World.prefab
    │  ├─ X+ X- Y+ Z+              4 box receivers — box-tracker's cage; box-tracker owns the geometry
    │  └─ Output                   readout target: Tracked tree writes its exact sender localPosition
    ├─ GrabPosition                grab-prop's rig verbatim (values in that entry's Rig)
    │  └─ GrabBone → GrabBone_End → FreezeRotation (FreezeToWorld) → DropPosition — measures grabbed tip
    ├─ FreezeToWorld               VRCParentConstraint, world-stable frame, ApplyDuringUpload TurnOn
    └─ EditorOnly                  edit-time alignment rig (ApplyDuringUpload TurnOff): pins DropPosition
                                   from GrabPosition, and RideOffset to Container (parked ⇒ RideOffset
                                   auto-mirrors TrackingOffset)

**Self-detection correctness:** `TrackingOffset` is allowSelf-only on the standard `Head` tag, so a friend wearing the same module (or any other player's head) can't trip your self-anchor — their senders are "other".

## Rebuilding

`controller.yaml` → `CompileController` → `built/`

