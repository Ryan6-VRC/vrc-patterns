# drop-on-player — release-arbitrated prop: own head / another player / world (Module)

Grab the prop and release it: on your own head it anchors (a bone constraint); on another player's head it catches and follows them (a `box-tracker` 4-box cage with a tall head-catch zone); anywhere else it freezes in place (sample-and-hold). The three rest mechanisms are structurally different because you *cannot constrain to another avatar's transform* (`gimmicks.md` §Constraint patterns "Attaching a prop to a body point") — the release-time **arbitration** between them, plus the 2-bool mode sync that lets every client re-derive it, is what this entry ships. Module total: **2 synced bits** (`DropOnPlayer/Out`, `DropOnPlayer/Worn`).

**Provenance:** generalized from a private production avatar's carried-doll system; its tracking cage is `box-tracker`'s 4-box exact readout, lifted whole and wear-tested in-game. Not a compose of `grab-prop` + `box-tracker` — one compressed controller reusing their measured idioms.

## Interface

- **Params:**
  - `DropOnPlayer/Out`, `DropOnPlayer/Worn` (bools, synced, **unsaved**) — the rest mode, written only by the wearer's localOnly drivers: `00` disabled · `01` anchored (own head) · `11` tracked (another player) · `10` dropped (world). Off-is-reset; both default false.
  - `DropOnPlayer/Enable`, `DropOnPlayer/ToHead` (bools, **unsynced**) — menu intents, local-only; the synced pair carries the outcome. `Enable` off hides the prop everywhere and resets; on restores it to your own head. `ToHead` (momentary) recalls a dropped/tracked prop to your head — the failsafe, and desktop's only path back for an affordance it can't otherwise reach.
  - `DropOnPlayer/{X+,X-,Y+,Z+}` + `SelfDetect` (floats), `GrabBone_IsGrabbed` (bool), `One` (scratch constant, excluded from the params asset) — sensing; never synced, never menu-exposed. The four box-cage receivers are `localOnly: 0` **by necessity** (remotes re-derive the chase); `SelfDetect` is `localOnly: 1` (routing input only — its outcome syncs as the pair).
- **Seam:** VRCFury `FullController` on the prefab root (FX, `basis: mount-root`) merging `built/DropOnPlayer_Fx_Parameters.asset`; `DropOnPlayer/Enable` + `DropOnPlayer/ToHead` ride `globalParams` with a VRCFury `Toggle` each as the menu front (ToHead as momentary/hold). **Plus one MA `BoneProxy`** on `HeadMount` → the wearer's Head bone — a mixed seam, needed so the anchor's placement is visible while authoring. `HeadMount` is referenced only as a constraint source; no VRCF clip binding paths through it.
- **Dependencies:** none beyond VRC SDK + VRCFury + Modular Avatar to build; **compose `anti-cull` alongside** (its README §When a module needs this) — the tracked and dropped modes replay choreography while the payload is away from the wearer.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference for the tracking cage (absolute meters). Do not instantiate or delete it. `Payload` is a placeholder sphere on Unity's built-in default material — swap it, keep it under `Container`.

## How it works

The prop (`Container`) multiplexes three position sources: `HeadMount/AnchorOffset` (anchored), `SourcePosition` (grabbed/dropped, sample-and-hold), `TrackedPoint/RideOffset` (tracked, riding the cage). The same four box receivers that track a target double as the "is another player's head here" sensor: parked, they ride `TrackingOffset` at head-contact level below the prop; tracking, they reconstruct the target's exact position and the cage eases onto it, then crawls to keep station (`box-tracker`). The prop rides the cage, never the raw readout.

**Release arbitration** (priority top-down, evaluated by the wearer): the self receiver fires (own standard Head sender at `TrackingOffset`) → anchored; all four boxes fire → tracked (the cage latches `allowOthers` shut and the readout crawler takes over); neither → a `grab-prop` release pulse → dropped. The winning branch's localOnly driver stamps the synced pair at release.

**Remotes** resolve from the synced pair rather than local sensors, freezing the prop in place on every release and self-correcting if the pair changes. **Tracking loss also freezes the prop in place** rather than snapping it home, for wearer and remote alike, since observers unload a distant target at different times. **Late joiners** dwell a boot timer, then resolve from the pair alone — anchored or hidden resolve immediately, but a tracked or dropped prop stays hidden until a witnessed grab, fail-visible since that position never crossed the wire.

**Anyone can grab it** (`allowGrabbing` on, native sync): a friend can take the prop off your head and put it on theirs, since the wearer's client arbitrates from wherever the prop currently is. `allowPosing` is off — persistence is always a constraint hold.

Empirical constants (90% rule — test before changing):

| Constant | Value |
|---|---|
| Released pulse phases | the `released` clip's phase keys (freeze, re-sample window, hold), owned by `grab-prop`'s rig — the remote release-settle constant below is defined against this pulse's length |
| Remote release-settle | = the `released` pulse length (remotes route by pair at pulse end); must cover the sync tick or a world drop flashes through a stale mode first |
| Remote boot dwell | the `timer` clip's length — long enough for the synced pair to arrive before a late joiner poses off it |
| Head-catch column | prefab `TrackingPoints` rest `localScale` + `ScaleAtRest` (zone side = 3 × scale/axis), taller than wide so lowering onto a head catches down the column; doubles as the release-arbitration zone. A non-uniform column costs one latch frame of skew |
| Tracking geometry / crawl gain | ×1 absolute boxes pinned to `World.prefab`, so avatar scale never skews the readout; gain per `box-tracker`'s crawl-gain row (prefab `source0` + the `tracked` clip's curve) |
| Loss / acquire thresholds | **ANY** of four <0.00001 / all four >0 — one dead box breaks the exact reconstruction, so loss triggers on any single box |
| Physbone constants | cloned from `grab-prop`'s rig — see that entry's Rig section |
| Anchor offsets | `HeadMount/AnchorOffset` (anchored) and `TrackedPoint/RideOffset` (tracked) local Y, plus `TrackingOffset`'s receiver radius — anchored must exceed tracked (the head bone sits at the neck while the cage converges on the head-contact center); per-avatar head size, re-check rather than trusting the shipped values |

## Verifying the install

At rest on the wearer, `SelfDetect` must read 1.000 off the avatar's own standard `Head` sender. **Zero means the descriptor carries no head collider slots** — a module-scale minimal rig reads zero (`docs/verify.md`) — and every release then arbitrates as a world drop, silently losing the anchored branch. `Container` sits at `HeadMount/AnchorOffset` with the cage below it at head-contact level; both offsets are per-avatar constants (see the Anchor offsets row).

For the tracker: with the prop grabbed, put a scripted `Head` sender (`docs/verify.md`) into the catch column and release — the four `X+/X-/Y+/Z+` floats leave zero together, filters shut, and `Output` lands on the sender (the cage then eases `TrackedPoint` onto it). A partial box set that never all-fire means the column doesn't suit this avatar's head placement. Because loss is **ANY-box** (`box-tracker`), a target leaving even one box's ±1.5 m core drops the prop.

Two clients in-game, not the emulator: remote-side cage re-derivation (clone receivers hold spawn-time fossils and are never simulated), the witnessed grab/release choreography (`_IsGrabbed` does not transport to a clone), the remote release-settle dwell, chase feel under real IK, and culling against a genuinely distant or occluded player.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. Constraint `Locked` on, source weights swapped by the clips; positions below are edit-time rest (0, 0.8, 0.25 ≈ chest-front).

    DropOnPlayer                      root — VRCFury FullController + 2 Toggles
    ├─ Container      (0, 0.8, 0.25)  VRCPositionConstraint [source0 HeadMount/AnchorOffset,
    │  │                              source1 SourcePosition, source2 TrackedPoint/RideOffset]
    │  ├─ Payload                     placeholder sphere — swap for your prop, keep under Container
    │  └─ TrackingOffset (0,-0.2,0)   VRCContactReceiver: tag Head, Constant radius 0.1, allowSelf ON
    │                                 allowOthers OFF localOnly ON → DropOnPlayer/SelfDetect; also the
    │                                 cage's park source (How it works)
    ├─ SourcePosition (0, 0.8, 0.25)  VRCPositionConstraint [source0 DropPosition, source1 TrackingPoints]
    │                                 — the sample-and-hold cell; samples the cage while Tracked
    ├─ HeadMount                      MA BoneProxy → Head (AsChildAtRoot — snaps to the head bone) +
    │  │                              VRCHeadChop (target HeadMount, scale 1, AlwaysApply): the local
    │  │                              player's head bone zero-scales in first person, which would
    │  │                              collapse AnchorOffset onto the bone
    │  └─ AnchorOffset (0, 0.25, 0)   the anchored rest point, in the head-bone frame (see the Anchor
    │                                 offsets row)
    ├─ TrackedPoint   (0, 0.8, 0.25)  VRCPositionConstraint [source0 TrackingPoints] — rides the cage
    │  └─ RideOffset  (0, 0.2, 0)     tracked-mode rest point, above the cage — the prop rides like a hat
    ├─ TrackingPoints (0, 0.8, 0.25)  localScale (0.05, 0.1, 0.05) = the 0.15×0.15×0.3 m catch column
    │  │                              (side = 3 × scale); VRCParentConstraint [TrackingOffset] (park — rides
    │  │                              the prop); VRCPositionConstraint [source0 Output, source1 self] — the
    │  │                              crawl feedback loop, source0 eased in by the tracked clip (box-tracker);
    │  │                              VRCScaleConstraint [World.prefab, ScaleOffset ×1] (absolute 6×6×3 m boxes)
    │  ├─ X+ X- Y+ Z+                 4 box GOs (box-tracker's cage), each a VRCContactReceiver: tag Head,
    │  │                              Proximity + useFaceProximity, size 6×6×3, radius 0.5, allowSelf OFF
    │  │                              allowOthers ON localOnly OFF; 90°-rotated per axis (+Z face → named
    │  │                              axis), localScale (0.5,0.5,1) — box-tracker owns the cage geometry
    │  └─ Output                      the readout target: the Tracked-state tree writes its localPosition
    │                                 (exact sender position)
    ├─ GrabPosition   (0, 0.8, 0.25)  VRCPositionConstraint [source0 AnchorOffset, source1 Container]
    │  └─ GrabBone                    VRCPhysBone (parameter GrabBone) — grab-prop's rig verbatim:
    │     │                           pull 1, stiffness 0.2, spring 0, gravity 0, immobile 1 AllMotion,
    │     │                           radius 0.075, grabMovement 1, maxStretch 100000, allowPosing OFF,
    │     │                           ignoreTransforms [DropPosition], isAnimated 0, resetWhenDisabled 0
    │     └─ GrabBone_End (0, .02, 0)
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation frame
    │           └─ DropPosition (0, -.02, 0)  measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint drives root, FreezeToWorld; inactive in editor,
    │                                 ApplyDuringUpload TurnOn
    └─ EditorOnly                     edit-time alignment rig, ApplyDuringUpload TurnOff:
                                      VRCPositionConstraint drives DropPosition from GrabPosition;
                                      a second pins RideOffset to Container (parked pose ⇒ RideOffset
                                      auto-mirrors TrackingOffset, any drag direction)

**Self-detection correctness:** the receiver is allowSelf-only on the standard `Head` tag, so a friend wearing the same module (or any other player's head) can't trip your self-anchor — their senders are "other".

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
