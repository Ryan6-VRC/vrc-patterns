# drop-on-player — release-arbitrated prop: own head / another player / world (Module)

Grab the prop and release it: on your own head it anchors (a bone constraint); on another player's head it catches and follows them (a `box-tracker` 4-box cage with a tall head-catch zone); anywhere else it freezes in place (sample-and-hold). The three rest mechanisms are structurally different because you *cannot constrain to another avatar's transform* (`gimmicks.md` §Constraint patterns "Attaching a prop to a body point") — the release-time **arbitration** between them, plus the 2-bool mode sync that lets every client re-derive it, is what this entry ships. Module total: **2 synced bits** (`DropOnPlayer/Out`, `DropOnPlayer/Worn`).

**Provenance:** generalized from a private production avatar's carried-doll system; its tracking cage is `box-tracker`'s 4-box exact readout, lifted whole and wear-tested in-game. Not a compose of `grab-prop` + `box-tracker` — one compressed controller reusing their measured idioms.

## Ground truth

- Parameters, states, clips and the whole arbitration are `controller.yaml`. Its header is the design record — the 2-bool wire surface and what each combination means, the release ladder, how remotes and late joiners resolve, and the deliberate deltas from the source ancestor — and the per-state comments carry the rest. The published set is the prefab's VRCFury `FullController` `globalParams`, which is **empty**: with two controls the menu ships as an asset, so `RewriteParamName` takes control and parameter together and no name escapes to the host avatar.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `basis: mount-root`) merging `built/DropOnPlayer_Fx_Parameters.asset` and `built/DropOnPlayer_Fx_Menu.asset` at prefix `Drop On Player`, **plus one MA `BoneProxy`** on `HeadMount` → the wearer's Head bone. The mixed seam is deliberate: the proxy is what makes the anchor's placement visible while authoring. `HeadMount` is referenced only as a constraint source, so no VRCF clip binding paths through it.
- Everything else about the rig — every constraint source list, receiver shape, physbone force and rest offset — is in `DropOnPlayer.prefab`. See **Rig** for what each node is for.
- The four box-cage receivers are `localOnly: 0` **by necessity**, because remotes re-derive the chase from their own sensors; `SelfDetect` is `localOnly: 1`, a routing input whose outcome syncs as the pair.
- **Dependencies:** none beyond VRC SDK + VRCFury + Modular Avatar to build; **compose `anti-cull` alongside** (its README §When a module needs this) — the tracked and dropped modes replay choreography while the payload is away from the wearer.
- **Required assets:** `built/DropOnPlayer_Fx_Menu.asset`, the shipped menu, regenerated from `controller.yaml`'s `menu:` block like the rest of `built/`. `assets/World.prefab` — a never-instantiated scale reference that makes the tracking cage absolute-meters; do not instantiate or delete it. `Payload` is a placeholder sphere on Unity's built-in default material — swap it, keep it under `Container`.

## Before you compose it

**Anyone can grab it** (`allowGrabbing` on, native sync): a friend can take the prop off your head and put it on theirs, since the wearer's client arbitrates from wherever the prop currently is. `allowPosing` is off — persistence is always a constraint hold.

**Self-detection cannot be fooled by another wearer.** The `TrackingOffset` receiver is allowSelf-only on the standard `Head` tag, so a friend wearing the same module — or any other player's head — cannot trip your self-anchor, because their senders are "other".

**Loss is ANY-box, inherited from `box-tracker`.** One dead box breaks the exact reconstruction, so a target leaving even one box's core drops the prop. Tracking loss freezes it in place rather than snapping it home, for wearer and remote alike, because observers unload a distant target at different times.

## Measured

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

At rest on the wearer, `SelfDetect` must read 1.000 off the avatar's own standard `Head` sender. **Zero means the descriptor carries no head collider slots** — a module-scale minimal rig reads zero (`docs/emulator.md`) — and every release then arbitrates as a world drop, silently losing the anchored branch. `Container` sits at `HeadMount/AnchorOffset` with the cage below it at head-contact level; both offsets are per-avatar constants (see the Anchor offsets row).

For the tracker: with the prop grabbed, put a scripted `Head` sender (`docs/emulator.md`) into the catch column and release — the four `X+/X-/Y+/Z+` floats leave zero together, filters shut, and `Output` lands on the sender (the cage then eases `TrackedPoint` onto it). A partial box set that never all-fire means the column doesn't suit this avatar's head placement. Because loss is **ANY-box** (`box-tracker`), a target leaving even one box's ±1.5 m core drops the prop.

Two clients in-game, not the emulator: remote-side cage re-derivation (clone receivers hold spawn-time fossils and are never simulated), the witnessed grab/release choreography (`_IsGrabbed` does not transport to a clone), the remote release-settle dwell, chase feel under real IK, and culling against a genuinely distant or occluded player.

## Rig

The prefab is the shipped artifact and ships no builder — edit it in place. Constraint `Locked` is on and the clips swap source weights; the transform positions it carries are edit-time rest at chest-front.

    DropOnPlayer                      root — the VRCFury FullController seam
    ├─ Container                      VRCPositionConstraint multiplexing the three rest sources:
    │  │                              HeadMount/AnchorOffset, SourcePosition, TrackedPoint/RideOffset
    │  ├─ Payload                     placeholder sphere — swap for your prop, keep it under Container
    │  └─ TrackingOffset              self-only Head receiver → DropOnPlayer/SelfDetect; also the
    │                                 cage's park source
    ├─ SourcePosition                 VRCPositionConstraint [DropPosition, TrackingPoints] — the
    │                                 sample-and-hold cell; samples the cage while Tracked
    ├─ HeadMount                      MA BoneProxy → Head (AsChildAtRoot) + VRCHeadChop (AlwaysApply):
    │  │                              the local player's head bone zero-scales in first person, which
    │  │                              would otherwise collapse AnchorOffset onto the bone
    │  └─ AnchorOffset                the anchored rest point, in the head-bone frame
    ├─ TrackedPoint                   VRCPositionConstraint [TrackingPoints] — rides the cage
    │  └─ RideOffset                  tracked-mode rest point above the cage — the prop rides like a hat
    ├─ TrackingPoints                 the catch column, sized by its rest localScale together with the
    │  │                              scale constraint's ScaleAtRest. VRCParentConstraint
    │  │                              [TrackingOffset] parks it on the prop; VRCPositionConstraint
    │  │                              [Output, self] is box-tracker's crawl feedback loop, eased in by
    │  │                              the tracked clip; VRCScaleConstraint [World.prefab] makes the
    │  │                              cage absolute-meters
    │  ├─ X+ X- Y+ Z+                 box-tracker's 4-box cage — face-proximity Head receivers, one
    │  │                              rotated onto each named axis; that entry owns the geometry
    │  └─ Output                      the readout target: the Tracked tree writes its localPosition
    ├─ GrabPosition                   VRCPositionConstraint [AnchorOffset, Container]
    │  └─ GrabBone                    VRCPhysBone, grab-prop's rig verbatim — see that entry's Rig
    │     └─ GrabBone_End
    │        └─ FreezeRotation        VRCRotationConstraint FreezeToWorld — world-stable rotation frame
    │           └─ DropPosition       measures the grabbed tip
    ├─ FreezeToWorld                  VRCParentConstraint driving the root; inactive in the editor,
    │                                 VRCFury ApplyDuringUpload turns it on
    └─ EditorOnly                     edit-time alignment rig, ApplyDuringUpload turns it off: one
                                      constraint drives DropPosition from GrabPosition, a second pins
                                      RideOffset to Container, so the parked pose makes RideOffset
                                      auto-mirror TrackingOffset in any drag direction

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
