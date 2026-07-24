# drop-on-player — release-arbitrated prop: own head / another player / world (Module)

Grab the prop and release it: on your own head it anchors (a bone constraint — precise, and it **late-syncs**); on another player's head it catches and follows them (a `box-tracker` 4-box cage with a tall head-catch zone — per-client re-derivation, **no late-sync**); anywhere else it freezes in place (sample-and-hold — no late-sync). The three rest mechanisms are structurally different because you *cannot constrain to another avatar's transform* (`gimmicks.md` §Constraint patterns "Attaching a prop to a body point") — the release-time **arbitration** between them, and the 2-bool mode sync that lets every client re-derive the outcome, are what this entry ships. Module total: **2 synced bits** (`DropOnPlayer/Out`, `DropOnPlayer/Worn`).

**Provenance:** generalized from a private production avatar's carried-doll system (grab-prop + a proximity tracker composed). Kept: release-routing arbitration, mode fusion with off-is-reset, the remote release-settle dwell, freeze-on-loss. Abstracted away: the Custom-Object-Sync half (late-join-exact world drops — its 6 s world-band dwell and ~¼ of the ancestor's FSM exist only for that), the 5-way self-body anchor multiplexer, the Fist/HandOpen gesture grammar, the doll mesh. Its tracker is **`box-tracker`'s** — the 4-box exact readout, lifted whole and wear-tested in-game, replacing the ancestor's 6-sphere crawler-servo; see that entry's README for the reconstruction math. Not a compose of `grab-prop` + `box-tracker` — one compressed controller reusing their measured idioms.

## Interface

- **Params:**
  - `DropOnPlayer/Out`, `DropOnPlayer/Worn` (bools, synced, **unsaved**) — the rest mode, written
    only by the wearer's localOnly drivers: `00` disabled · `01` anchored (own head) · `11` tracked
    (another player) · `10` dropped (world). Off-is-reset; both default false.
  - `DropOnPlayer/Enable`, `DropOnPlayer/ToHead` (bools, **unsynced**) — menu intents, local-only;
    the synced pair carries the outcome. `Enable` off hides the prop everywhere and resets; on
    restores it to your own head. `ToHead` (momentary) recalls a dropped/tracked prop to your head —
    the failsafe and the desktop-parity path for the one affordance a desktop user can't reach.
  - `DropOnPlayer/{X+,X-,Y+,Z+}` + `SelfDetect` (floats), `GrabBone_IsGrabbed` (bool), `One`
    (scratch constant, excluded from the params asset) — sensing; never synced, never menu-exposed.
    The four box-cage receivers are `localOnly: 0` **by necessity** (remotes re-derive the chase);
    `SelfDetect` is `localOnly: 1` (routing input only — its outcome syncs as the pair) and reads
    the wearer's own **standard Head sender** (allowSelf + tag `Head`, Constant) — no custom sender
    to place or tune.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `basis: mount-root`) merging `built/DropOnPlayer_Fx_Parameters.asset`; `DropOnPlayer/Enable` + `DropOnPlayer/ToHead` ride `globalParams` with a VRCFury `Toggle` each as the menu front (ToHead as momentary/hold). **Plus one MA `BoneProxy`** on `HeadMount` → the wearer's Head bone (the mixed seam: the anchor's placement must be visible while authoring). `HeadMount` is referenced only as a constraint source — no VRCF clip binding paths through it.
- **Dependencies:** none beyond VRC SDK + VRCFury + Modular Avatar to build; **compose `anti-cull` alongside** (its README §When a module needs this) — the tracked and dropped modes replay choreography while the payload is away from the wearer, and a remote client that view-culls the wearer stops replaying it.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference for the tracking cage (absolute meters). Do not instantiate or delete it. `Payload` is a placeholder sphere on Unity's built-in default material — swap it, keep it under `Container`.

## How it works

The prop (`Container`) multiplexes three position sources: `HeadMount/AnchorOffset` (anchored), `SourcePosition` (the sample-and-hold cell — grabbed/dropped), `TrackedPoint/RideOffset` (the cage, plus the hat lift). The cage **rides `TrackingOffset`** (parent constraint) whenever it isn't tracking — the sensed point 0.2 *below* the prop — so at the release instant the cage sits at head-contact level while the prop sits at hat level: the same four box receivers that will track the target are the "is another player's head here" sensor, centered where a head actually is. That sensor is a **vertical catch column** — 0.15 m wide/deep, **0.3 m tall** — so lowering the prop onto a head catches reliably down the whole column (a taller arbitration zone than the old flat 0.15 m cube). While tracking, the four boxes reconstruct the target's exact position (`box-tracker`) and the cage eases onto it over ~0.5 s, then crawls to keep station (`box-tracker`'s acquisition ease-in — the prop glides onto the head rather than snapping); the prop rides the cage (`TrackedPoint`), never the raw readout, so it never sees the readout's lead.

**Release arbitration** (the wearer's transition ladder, priority top-down): the self receiver fires (own standard Head sender at `TrackingOffset`) → `Anchored`; all four boxes fire → `Tracked` (the cage latches `allowOthers` shut and the readout crawler takes over); neither → `Released` (the grab-prop pulse: freeze, re-sample the settled tip, hold) → `Dropped`. The winning state's localOnly driver stamps the pair — for a world drop **at release**, so the pair usually beats the remotes' 0.5 s settle window.

**Remotes** run the same graph gated on the pair instead of sensors: every release routes through `Released` (visually a freeze-in-place), then to the pair's state; a stale pair self-corrects via each mode state's remote edges. **Tracking loss** is per-client: the wearer's loss stamps `Dropped` (freeze — never snap-home, observers unload the target at different times); a remote's own loss falls to `Lost` (same freeze) *without* touching the pair, recovering on the next witnessed grab or pair change. **Late joiners** dwell 1 s then: `01` → hat on your head (the pair late-syncs), `00` → hidden, `1x` → `Waiting` hidden until a witnessed grab (fail-visible — the tracked/dropped position never crossed the wire).

**Anyone can grab it** (`allowGrabbing` on, native sync): a friend can take the hat off your head and put it on theirs — the wearer's client arbitrates from wherever the prop is, and their head is "another player's head". `allowPosing` off — persistence is always a constraint hold.

Empirical constants (90% rule — test before changing):

| Constant | Value | Locked by |
|---|---|---|
| Released pulse phases | freeze 0 s / sample 0.25 s / hold 0.5 s | grab-prop emulator sweep |
| Remote release-settle | 0.5 s (= pulse length; remotes route by pair at pulse end) | measured on the source avatar; in-game batch owns it |
| Remote boot dwell | 1.0 s (`timer` clip) | grab-prop in-game candidate |
| Head-catch column | 0.15 × 0.15 × **0.3 m** (`TrackingPoints` ScaleAtRest 0.05/0.1/0.05; side = 3 × scale) | in-game wear-test — tall so lowering onto a head reliably catches. Doubles as the arbitration zone |
| Tracking geometry / crawl gain | ×1 absolute 6×6×3 m boxes (World.prefab, faces ±1.5 m) · steady g ≈ 0.39 (source0 0.65 : self 1); Tracked clip eases source0 0 → 0.65 over 0.5 s | `box-tracker` — exact readout, no convergence dwell; a 0.5 s acquisition ease-in (g from 0 = a clean freeze) damps the first-frame gap. Retune the clip end key + prefab source0 together; clip-owned, not live-scrubbable |
| Loss / acquire thresholds | **ANY** of four <0.00001 / all four >0 | `box-tracker` — one dead box breaks the exact reconstruction (vs the old ALL-six) |
| Physbone constants | cloned from grab-prop's rig | grab-prop sweeps |
| Anchor offsets | +0.25 above the head bone (anchored) / +0.2 above the cage centroid (tracked); self-detect receiver radius 0.1 | anchored must exceed tracked: the head bone sits at the neck while the cage converges on the head-contact center — wear-tested in-game; per-avatar head size, wear-test owns them |

## Verifying the install

At rest on the wearer, `SelfDetect` must read 1.000 off the avatar's own standard `Head` sender. **Zero means the descriptor carries no head collider slots** — a module-scale minimal rig reads zero (`docs/verify.md`) — and every release then arbitrates as a world drop, silently losing the anchored branch. `Container` sits at `HeadMount/AnchorOffset` with the cage 0.2 below it at head-contact level; both offsets are per-avatar head-size constants, so re-check them on a new base rather than trusting the shipped values.

For the tracker: with the prop grabbed, put a scripted `Head` sender (`docs/verify.md`) into the 0.3 m catch column and release — the four `X+/X-/Y+/Z+` floats leave zero together, filters shut, and `Output` lands on the sender (the cage then eases `TrackedPoint` onto it over ~0.5 s). A partial box set that never all-fire means the column no longer suits this avatar's head placement. Because loss is **ANY-box** (`box-tracker`), a target leaving even one box's ±1.5 m core drops the prop — a smaller effective range than the old ALL-six, by design.

Two clients in-game, not the emulator: remote-side cage re-derivation (clone receivers hold spawn-time fossils and are never simulated), the witnessed grab/release choreography (`_IsGrabbed` does not transport to a clone), the remote release-settle dwell, chase feel under real IK, and culling against a genuinely distant or occluded player.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. Constraint `Locked` on, source weights swapped by the clips; positions below are edit-time rest (0, 0.8, 0.25 ≈ chest-front).

    DropOnPlayer                      root — VRCFury FullController + 2 Toggles
    ├─ Container      (0, 0.8, 0.25)  VRCPositionConstraint [source0 HeadMount/AnchorOffset,
    │  │                              source1 SourcePosition, source2 TrackedPoint/RideOffset]
    │  ├─ Payload                     placeholder sphere — swap for your prop, keep under Container
    │  └─ TrackingOffset (0,-0.2,0)   the sensed point below the prop — VRCContactReceiver: tag Head,
    │                                 Constant radius 0.1, allowSelf ON allowOthers OFF localOnly ON →
    │                                 DropOnPlayer/SelfDetect (the wearer's own standard Head sender);
    │                                 also the cage's park source, so at release the cage sits at
    │                                 head-contact level while the prop sits at hat level
    ├─ SourcePosition (0, 0.8, 0.25)  VRCPositionConstraint [source0 DropPosition, source1 TrackingPoints]
    │                                 — the sample-and-hold cell; samples the cage while Tracked
    ├─ HeadMount                      MA BoneProxy → Head (AsChildAtRoot — snaps to the head bone) +
    │  │                              VRCHeadChop (target HeadMount, scale 1, AlwaysApply): the local
    │  │                              player's head bone zero-scales in first person, which would
    │  │                              collapse AnchorOffset onto the bone — the chop exemption keeps
    │  │                              the wearer's own anchored prop at its offset
    │  └─ AnchorOffset (0, 0.25, 0)   the anchored rest point, in the head-bone frame: the head bone
    │                                 sits at the neck, so this lift is necessarily larger than
    │                                 TrackingOffset (which measures from the head-contact center)
    ├─ TrackedPoint   (0, 0.8, 0.25)  VRCPositionConstraint [source0 TrackingPoints] — rides the cage
    │  └─ RideOffset  (0, 0.2, 0)     tracked-mode rest point, above the cage (which converges on the
    │                                 target's head-contact center, inside the skull) — the prop rides
    │                                 like a hat. Mirrors TrackingOffset; the EditorOnly rig keeps the
    │                                 two aligned in edit mode (drag TrackingOffset, this follows)
    ├─ TrackingPoints (0, 0.8, 0.25)  localScale (0.05, 0.1, 0.05) = the 0.15×0.15×0.3 m catch column
    │  │                              (side = 3 × scale); VRCParentConstraint [TrackingOffset] (park — rides
    │  │                              the prop); VRCPositionConstraint [source0 Output, source1 self] — steady
    │  │                              g ≈ 0.39 (0.65:1) crawl feedback; the Tracked clip eases source0 0 → 0.65 over 0.5 s;
    │  │                              VRCScaleConstraint [World.prefab, ScaleOffset ×1] (absolute 6×6×3 m boxes)
    │  ├─ X+ X- Y+ Z+                 4 box GOs (box-tracker's cage), each a VRCContactReceiver: tag Head,
    │  │                              Proximity + useFaceProximity, size 6×6×3, radius 0.5, allowSelf OFF
    │  │                              allowOthers ON localOnly OFF; 90°-rotated per axis (+Z face → named
    │  │                              axis), localScale (0.5,0.5,1) — a 1.5³ local cube, so the rotations are
    │  │                              shape-invariant and the non-uniform parent scale gives a clean column
    │  └─ Output                      the readout target: the Tracked-state tree writes its localPosition
    │                                 (exact sender position); source0 of the crawl constraint (feedback)
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

**Self-detection correctness:** the receiver is allowSelf-only on the standard `Head` tag, so a friend wearing the same module (or any other player's head) can't trip your self-anchor — their senders are "other". The old private sender/receiver tag pair is gone; the standard sender needs no placement.

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID — recompile is GUID-stable, regenerate controller + params asset as a unit). The prefab is hand-maintained against the Rig section above.
