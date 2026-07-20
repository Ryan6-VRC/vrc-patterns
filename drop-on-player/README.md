# drop-on-player — release-arbitrated prop: own head / another player / world (Module tier)

Grab the prop and release it: on your own head it anchors (a bone constraint — precise, and it
**late-syncs**); on another player's head it latches and follows them (a proximity cage — per-client
re-derivation, **no late-sync**); anywhere else it freezes in place (sample-and-hold — no late-sync).
The three rest mechanisms are structurally different because you *cannot constrain to another
avatar's transform* (`gimmicks.md` §Constraint patterns "Attaching a prop to a body point") — the
release-time **arbitration** between them, and the 2-bool mode sync that lets every client re-derive
the outcome, are what this entry ships. Module total: **2 synced bits** (`DropOnPlayer/Out`,
`DropOnPlayer/Worn`).

**Provenance:** generalized from a private production avatar's carried-doll system (grab-prop + contact-tracker composed).
Kept: release-routing arbitration, mode fusion with off-is-reset, the remote release-settle dwell,
freeze-on-loss. Abstracted away: the Custom-Object-Sync half (late-join-exact world drops — its 6 s
world-band dwell and ~¼ of the ancestor's FSM exist only for that), the 5-way self-body anchor
multiplexer, the Fist/HandOpen gesture grammar, the doll mesh. Not a compose of this library's
`grab-prop` + `contact-tracker` — one compressed controller reusing their measured idioms.

## Interface

- **Params:**
  - `DropOnPlayer/Out`, `DropOnPlayer/Worn` (bools, synced, **unsaved**) — the rest mode, written
    only by the wearer's localOnly drivers: `00` disabled · `01` anchored (own head) · `11` tracked
    (another player) · `10` dropped (world). Off-is-reset; both default false.
  - `DropOnPlayer/Enable`, `DropOnPlayer/ToHead` (bools, **unsynced**) — menu intents, local-only;
    the synced pair carries the outcome. `Enable` off hides the prop everywhere and resets; on
    restores it to your own head. `ToHead` (momentary) recalls a dropped/tracked prop to your head —
    the failsafe and the desktop-parity path for the one affordance a desktop user can't reach.
  - `DropOnPlayer/SelfDetect`, `DropOnPlayer/{X,Y,Z}±` (floats) + `GrabBone_IsGrabbed` (bool) —
    sensing; never synced, never menu-exposed. The cage receivers are `localOnly: 0` **by
    necessity** (remotes re-derive the chase); `SelfDetect` is `localOnly: 1` (routing input only —
    its outcome syncs as the pair).
- **Seam:** VRCFury `FullController` on the prefab root (FX, `basis: mount-root`) merging
  `built/DropOnPlayer_Fx_Parameters.asset`; `DropOnPlayer/Enable` + `DropOnPlayer/ToHead` ride
  `globalParams` with a VRCFury `Toggle` each as the menu front (ToHead as momentary/hold). **Plus
  one MA `BoneProxy`** on `HeadMount` → the wearer's Head bone (the mixed seam: the anchor's
  placement must be visible while authoring). `HeadMount` is referenced only as a constraint source
  and sender mount — no VRCF clip binding paths through it.
- **Dependencies:** none beyond VRC SDK + VRCFury + Modular Avatar to build; **compose `anti-cull`
  alongside** (its README §When a module needs this) — the tracked and dropped modes replay
  choreography while the payload is away from the wearer, and a remote client that view-culls the
  wearer stops replaying it.
- **Required assets:** `assets/World.prefab` — never-instantiated scale reference for the tracking
  cage (absolute meters). Do not instantiate or delete it. `Payload` is a placeholder sphere on
  Unity's built-in default material — swap it, keep it under `Container`.

## Empirical constants (90% rule — test before changing)

| Constant | Value | Locked by |
|---|---|---|
| Released pulse phases | freeze 0 s / sample 0.25 s / hold 0.5 s | grab-prop emulator sweep |
| Remote release-settle | 0.5 s (= pulse length; remotes route by pair at pulse end) | measured on the source avatar; in-game batch owns it |
| Remote boot dwell | 1.0 s (`timer` clip) | grab-prop in-game candidate |
| Cage acquisition / tracking scale / spread / brake | 0.15 · ×3 · ±0.5 · 1.0 s | contact-tracker emulator sweep |
| Loss / acquire thresholds | all six <0.00001 / >0 | contact-tracker |
| Arbitration zone | the cage's own acquisition radius (0.15 m) | **named open test** — no 7th receiver (the source had one); revisit if too tight for a comfortable drop |
| Physbone constants | cloned from grab-prop's rig | grab-prop sweeps |
| Anchor offsets | +0.15 above the head bone (anchored) / +0.10 above the cage centroid (tracked) | RemyDoll ancestry (head-contact center ≈ +0.1 over the bone); per-avatar head size — wear-test owns them |

## How it works

The prop (`Container`) multiplexes three position sources: `HeadMount` (anchored), `SourcePosition`
(the sample-and-hold cell — grabbed/dropped), `TrackingPoints` (the cage). The cage **rides the prop**
(parent constraint → `Container`) whenever it isn't tracking, so at the release instant the cage is
exactly at the prop — that is the arbitration geometry: the same six receivers that will track the
target are the "is another player's head here" sensor.

**Release arbitration** (the wearer's transition ladder, priority top-down): private-tag self
receiver fires → `Anchored`; all six cage floats fire → `Tracked` (the cage latches `allowOthers`
shut and the crawler takes over); neither → `Released` (the grab-prop pulse: freeze, re-sample the
settled tip, hold) → `Dropped`. The winning state's localOnly driver stamps the pair — for a world
drop **at release**, so the pair usually beats the remotes' 0.5 s settle window.

**Remotes** run the same graph gated on the pair instead of sensors: every release routes through
`Released` (visually a freeze-in-place), then to the pair's state; a stale pair self-corrects via
each mode state's remote edges. **Tracking loss** is per-client: the wearer's loss stamps `Dropped`
(freeze — never snap-home, observers unload the target at different times); a remote's own loss
falls to `Lost` (same freeze) *without* touching the pair, recovering on the next witnessed grab or
pair change. **Late joiners** dwell 1 s then: `01` → hat on your head (the pair late-syncs), `00` →
hidden, `1x` → `Waiting` hidden until a witnessed grab (fail-visible — the tracked/dropped position
never crossed the wire).

**Anyone can grab it** (`allowGrabbing` on, native sync): a friend can take the hat off your head
and put it on theirs — the wearer's client arbitrates from wherever the prop is, and their head is
"another player's head". `allowPosing` off — persistence is always a constraint hold.

## Verified (emulator) and handed off (in-game)

Emulator-proven in two batched sessions (Av3Emulator; details in the entry's PR):

- **Single avatar** (default polarity): full local lifecycle — boot → Disabled; Enable → Anchored
  on the own head (SelfDetect saturates); grab-carry; all three release-arbitration branches
  (self-tag → Anchored; scripted Head sender → Tracked with latch + spread + chase converging to
  0.000 m on a moving target; neither → Released pulse → Dropped frozen exactly at the drop spot,
  sample cell landed); loss → freeze with pair re-stamped `10`; ToHead recall; Enable-off from
  every rest mode drives the pair to `00` as one code and reopens the filters. Remote clone:
  pair replicates, boot dwell routes `01` → Anchored on the clone's head, `00` hides, live pair
  flips drive the remote Anchored→Tracked latch. localOnly drivers correctly never run on the clone.
- **Two avatars, `EnablePlayerContactPermissions` on** (per-player contact ids): the in-game
  permission asymmetry reproduces — at the wearer's own head the allowOthers cage reads 0.000
  while allowSelf SelfDetect reads 1.000; a *real second avatar's* synthesized Head sender fires
  the cage, release on their head latches Tracked, and the cage chases the moving player
  (re-converges across a 1.4 m step).

Needs two clients in-game (emulator boundary, `docs/verify.md`): remote-side cage re-derivation
(clone contact receivers freeze at their spawn-time values — never simulated), the witnessed
grab/release remote choreography (`_IsGrabbed` does not transport to the clone), the remote
release-settle dwell length, real-IK chase feel, and culling interaction with a genuinely
distant/occluded player. Late-join Waiting-hide is graph-proven off the pair; its in-game timing
rides the same second-client session.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. Constraint `Locked` on,
source weights swapped by the clips; positions below are edit-time rest (0, 0.8, 0.25 ≈ chest-front).

    DropOnPlayer                      root — VRCFury FullController + 2 Toggles
    ├─ Container      (0, 0.8, 0.25)  VRCPositionConstraint [source0 HeadMount/Offset, source1 SourcePosition,
    │  │                              source2 TrackedPoint]; holds the payload
    │  ├─ Payload                     placeholder sphere — swap for your prop, keep under Container
    │  └─ SelfDetect                  VRCContactReceiver: private tag, Proximity, radius 0.15,
    │                                 allowSelf ON allowOthers OFF localOnly ON → DropOnPlayer/SelfDetect
    ├─ SourcePosition (0, 0.8, 0.25)  VRCPositionConstraint [source0 DropPosition, source1 TrackingPoints]
    │                                 — the sample-and-hold cell; samples the cage while Tracked
    ├─ HeadMount                      MA BoneProxy → Head (AsChildAtRoot — snaps to the head bone)
    │  └─ Offset      (0, 0.15, 0)    the anchored rest point, in the head-bone frame: the head bone
    │                                 sits at the neck, so the prop needs this lift to sit on the
    │                                 head. Carries the VRCContactSender (private tag, Sphere,
    │                                 radius 0.1) — self-anchor detection fires where the prop rests
    ├─ TrackedPoint   (0, 0.8, 0.25)  VRCPositionConstraint [source0 TrackingPoints] + PositionOffset
    │                                 (0, 0.10, 0) — tracked-mode rest point: the cage converges on the
    │                                 target's head-contact center (inside the skull), this rides above it
    ├─ TrackingPoints (0, 0.8, 0.25)  localScale 0.15; VRCParentConstraint [Container] (park — rides the
    │  │                              prop); VRCPositionConstraint [sources 0–5 = probes, 6 = self (brake)];
    │  │                              VRCScaleConstraint [World.prefab, ScaleOffset ×3] (absolute meters)
    │  └─ X+ X- Y+ Y- Z+ Z-           6 probe GOs, each a VRCContactReceiver: tag Head, Proximity,
    │                                 radius 1 (×0.15 scale), allowSelf OFF allowOthers ON localOnly OFF
    ├─ GrabPosition   (0, 0.8, 0.25)  VRCPositionConstraint [source0 HeadMount, source1 Container]
    │  └─ GrabBone                    VRCPhysBone (parameter GrabBone) — grab-prop's rig verbatim:
    │     │                           pull 1, stiffness 0.2, spring 0, gravity 0, immobile 1 AllMotion,
    │     │                           radius 0.075, grabMovement 1, maxStretch 100000, allowPosing OFF,
    │     │                           ignoreTransforms [DropPosition], isAnimated 0, resetWhenDisabled 0
    │     └─ GrabBone_End (0, .02, 0)
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation frame
    │           └─ DropPosition (0, -.02, 0)  measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint drives root, FreezeToWorld; inactive in editor,
    │                                 ApplyDuringUpload TurnOn
    └─ EditorOnly                     VRCPositionConstraint drives DropPosition from GrabPosition —
                                      edit-time alignment; ApplyDuringUpload TurnOff

**Private tag:** the sender/receiver pair ships tag `DropOnPlayerSelfHead`. Private-tag + allowSelf-only
is the correctness of self-detection: a friend wearing the same module can't trip your self-anchor
(their sender is "other"), and your own `Head`-tag senders can't either (different tag).

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID —
recompile is GUID-stable, regenerate controller + params asset as a unit). The prefab is
hand-maintained against the Rig section above.
