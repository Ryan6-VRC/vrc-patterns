# selective-animation — tag a player by pointing at them (Module)

Point at someone and hold the tag button: everyone whose capsule your aim line crosses gets tagged on their own client, until you erase; a second button tags your own copy. A native `VRCRaycast` masked to the observer's own capsule addresses the hit, and a state latch on that observer's animator remembers it, so the per-player state lives distributed across the people who hold it — **nothing identifying anyone crosses the wire: 2 synced bits total**, the same two whether one person is tagged or twenty.

**Provenance:** VRLabs' MIT [`Selective-Animation`](https://github.com/VRLabs/Selective-Animation) is the direct ancestor; native `VRCRaycast` replaces its FinalIK-based hit reconstruction.

## Ground truth

- Parameters and their flags, the layers and clips, and the shipped menu: `controller.yaml`. Its header is the design record — the per-observer raycast argument every condition rests on, the latch-as-state and its mirror-clone export, and the erase-parity trade that was priced and refused.
- The set published to the host avatar is the prefab's VRCFury `FullController` `globalParams`: exactly one name, `SelectiveAnimation/Tagged`, the bool a consumer gates its own layers on. Everything else about the rig is `SelectiveAnimation.prefab` — see **Rig** for its topology.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`), merging `built/SelectiveAnimation_Fx_Parameters.asset` and `built/SelectiveAnimation_Fx_Menu.asset` at prefix `Selective Animation`. The hand anchor is a VRCFury `ArmatureLink` (`Aim` → Right Hand, non-recursive) and **must not become an MA `BoneProxy`**: this module animates *through* that anchor, so one framework must own both the move and the animation, or the bindings are dropped from the merged FX — warned, but with the warning naming the clip and the layer rather than the anchor (`nondestructive.md` owns the build-order mechanism; `CONVENTIONS.md`: *only object-referenced, never path-animated, nodes may be proxied*). A second anchor of a different framework anywhere above an animated node in this subtree re-breaks the rig the same way.
- **Dependencies:** VRC SDK + VRCFury, and a **humanoid** avatar (the `ArmatureLink` resolves Right Hand through the humanoid mapping). No Modular Avatar. Composes well with `anti-cull` — see below.
- **Required assets:** `assets/SelectiveAnimationBeam.mat` (Unity Standard, self-contained — no Poiyomi or lilToon dependency) and `built/SelectiveAnimation_Fx_Menu.asset`, the shipped menu, regenerated from the `menu:` block in `controller.yaml` like the rest of `built/`. The material carries the beam's colour; nothing animates it. `Payload` is a placeholder sphere on the built-in default material.

## Before you compose it

- **The ray is a line: there is no occlusion between players.** Each client's only candidate collider is *that client's own capsule*, so everyone whose capsule the line crosses latches, and you get no local confirmation of who else it crossed. Range is kept deliberately short and the beam is wearer-only for this reason: **look at the beam and see who is standing in it before you commit.**
- **Erase is a parity bit, and that leaves one residue you cannot see.** Each erase flips `Gen`; an erase is level-triggered, not momentary, so a paused observer's animator picks it up on resume. Parity is not a counter — an **even** number of erases spanning one pause leaves that observer tagged, and you have no way to learn it happened, since you never register a hit. The repair is one more erase.
- **Aim `Origin` per rig — its rotation is the entry's one install-time value.** `Origin` *is* the ray frame: orienting it aims the ray, the beam and the rest pose together, so there is one value to set, not several. Edit `Origin`, not `Aim` — `ArmatureLink` replaces `Aim`'s transform at build, so edits on `Aim` itself do not survive. Set the rotation with `Quaternion.LookRotation(hand.InverseTransformDirection((indexProximal.position - hand.position).normalized))` rather than dragging the gizmo: `Aim` sits at the module root while you author, with nothing on the hand to eyeball `Origin` against, so verify in play mode.
- **Keep `Beam` a child of `Origin`.** Its own flag is gated on `IsLocal` alone; "only while held" comes from `Origin`, which the rig stows on release. Reparent it elsewhere and it burns permanently on the wearer's screen, with nothing in the controller to catch it.
- **A target who has you view-culled cannot be tagged**: their client is not running your animator, so no ray of yours evaluates there. The command is **held** rather than pulsed for this reason — it latches the frame their animator resumes. Compose `anti-cull` to paint people who are looking away; its bounds inflation keeps a remote's animator running when you leave their view.
- **Keep `SelfTag` unsynced.** It is not just a saved bit: being unsynced is what distinguishes your own copy and its mirror clone from every remote (a remote reads its default forever), which is how the self-tag reaches a mirror without a mirror-detection rig. Declaring it synced would tag you on everyone's screen at once.

## The raycast component

`runtime.md` keeps only the structural fact about `VRCRaycast` and routes here for the rest, because the whole entry rests on it.

Every `VRCRaycast` copy runs its own ray and a client's only player capsule is its own, so each client raycasts a different world: point at someone and **they** register the hit while you never do. That is an unresolved upstream bug (feedback 1818) and simultaneously the mechanism that makes per-observer targeting cost zero synced bits — this entry is built on the bug behaving as a feature, so a fix upstream would break it. Mask **`PlayerLocal` alone** via `HitCustomLayers`, never `HitPlayers`, which also queries `Player` and so reintroduces other players' capsules; **which layer a real capsule actually occupies is in-game-unverified**, inherited from VRLabs' shipped ancestor rather than measured, so treat it as the entry's one load-bearing assumption about the client. A **miss** reports differently per `MissBehavior` (`DoNothing`, `SnapToStart`, `SnapToEnd`): under this entry's `SnapToEnd` both rays write `_Hit` false with `_Ratio` 1.0 and the result at origin + direction × range, which is exactly why two misses subtract to a `Clear` of zero and cannot commit (**Empirical constants**); `DoNothing` instead freezes `_Ratio`/`_Distance` at the last hit behind a false `_Hit`, which would make a stale reading commit — do not switch to it. A rig that *wants* the freeze reads the false `_Hit` as its gate and holds deliberately: `compositions/object-sync-demo` raycasts world surfaces rather than players and does exactly that.

The **player ray** is masked to `PlayerLocal` **alone**: the local capsule must be on that layer or the ray is dead. `PlayerLocal` is the *project's* name for that mask and never the component's — `customCollisionLayers` serializes as a bare Unity `LayerMask` (`m_Bits: 1024`, bit 10 and nothing else), so what the prefab pins is **layer index 10**, which reads as `PlayerLocal` only because `ProjectSettings/TagManager.asset` puts that name in row 10 the way a VRChat avatar project does. That is the checkable half of the in-game-unverified caveat above: what needs a client is which layer a real capsule occupies, but what costs five seconds is confirming the host project numbers `PlayerLocal` 10 — a host that orders layers differently masks whatever sits at 10 there, with no name anywhere to mismatch on and no warning at build or runtime, only a ray that never hits. Read `m_Bits` against the host's TagManager before trusting a composed copy, and never quote a layer *name* off this component as if it declared one. A world collider placed on `PlayerLocal` is still a valid hit — `HitWorlds` doesn't query that layer, so such an object reads as maximally clear and tags every observer whose ray crosses it. The **world ray** exists only to keep tags from passing through geometry: a Direct blend tree subtracts the two `_Ratio` values into `Clear`, positive when the player hit is nearer, and the latch requires it.

**Durability is `runtime.md`'s cull table.** View cull and distance-hide pause an observer's animator without rebuilding it, so the latch survives both; manual hide/show, an avatar switch, or a reload drop it. Re-pointing is the only repair.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value |
|---|---|
| Range | `distance` on **both** raycasts, plus `BeamMesh`'s `position.z` (half it) and `scale.z`. The rays must share a transform and agree on `distance`/`applyTransformScale`, or `Clear` is meaningless. Kept short: widening it widens the no-occlusion blast radius (**Before you compose it**). |
| Clearance tolerance | the `Clear greater` threshold on the latch's commit — **zero**; a stale reading (two misses) also subtracts to exactly zero, so it can't commit either. |
| Gate depth | the `Casting` → `Armed` chain in the `Compute` tree, two stages. Shorten it and a frozen sensing set commits on the press frame; lengthen it and the opening frames of a legitimate sweep are dropped. |
| Beam length | `BeamMesh`'s local position and scale carry the range, so `Beam`'s animated `scale.z` stays unitless and a retune touches only the prefab. |
| Payload | the `sa_tagged` / `sa_untagged` clip pair — the swap point for a real payload. |

## Verifying the install

Post-bake the sync surface is exactly two bools — `Tag` and `Gen` under whatever instance prefix VRCFury gave it. `Erase`, `SelfTag` and both rays' outputs must read unsynced, and `SelectiveAnimation/Tagged` must appear **un-prefixed**: it is the documented export, and a consumer's layer conditioned on the bare name silently never fires if it was renamed.

**The one check is the beam under the held button, and it must be done in play mode.** Hold `Tag`: the beam appears on your own copy, not on a remote clone, tracks the world ray as you walk it to a wall, and vanishes on release — and `Aim` must have landed under the right hand, which only happens at build. If the beam never appears, or appears and never goes away, the merged clips lost their bindings: check that nothing above an animated node carries a non-VRCFury anchor (**Ground truth**). The build warns rather than failing quietly — VRCFury reports the dropped binding paths, and reports removing a layer of this module's because it "doesn't do anything" — but no message names the anchor, so read those warnings as pointing at the module, never at the cause.

What the emulator cannot show for this entry is **selectivity itself** — that the person you point at is the one who latches. The editor has no player colliders at all; substituting a collider on the `PlayerLocal` layer exercises the machine but is a false pass, since a real client strips every collider off a real avatar, and it proves nothing about where a real capsule sits or which client owns it. Selectivity needs two real clients. One emulator behavior is worth knowing before you read `Origin`'s params: av3emulator rediscovers raycasts (with contacts and physbones) in one per-frame pass that **skips inactive GameObjects**, so while the rig has `Origin` stowed neither ray's params are being written — they hold their last values, and resume updating the frame `Origin` comes back. So a read taken during the stow is a fossil, not a zero, and the two-frame `Clear` gate above is the thing that makes that safe rather than the prefab's active flag. `Origin` still ships **active** so the animator owns the whole lifecycle from the first evaluation.

## Rig

    SelectiveAnimation              root — VRCFury FullController
    ├─ Aim                          VRCFury ArmatureLink → Right Hand, non-recursive;
    │                               VRCFury's and not MA's — see Ground truth
    │  └─ Origin                    THE ray frame: consumer-editable offset and aim, and its
    │     │                         rotation is the one per-rig install value — see Before you
    │     │                         compose it. VRCRaycast ×2 both firing local +Z (constant):
    │     │                         player ray (HitCustomLayers, PlayerLocal alone) and world ray
    │     │                         (HitWorlds); same range and SnapToEnd. Origin's active flag IS
    │     │                         the rig's lifecycle — the Compute tree stows it whenever Tag is
    │     │                         released. Ships ACTIVE — see Verifying the install
    │     ├─ Beam                    plain child, +Z down the ray; scale.z = the world _Ratio.
    │     │  │                       MUST stay under Origin — see Before you compose it
    │     │  └─ BeamMesh             carries the range; owned Standard material, which carries the colour
    │     ├─ PlayerHit               result transform — MANDATORY, see below
    │     └─ WallHit                 result transform. Both rest at local (0,0,range) so the rig reads
    │                                correctly before any ray has run: parented to the module root they
    │                                would sit at the avatar's feet and drag the beam down with them
    └─ Payload                      placeholder sphere, built-in default material — swap this

A `resultTransform` is not optional on either ray: without one the component never registers and never casts — no hit, no params, no error, no diagnostic.

The `resultTransform` is **oriented as well as placed**: its `up` is the hit surface normal. This entry reads position only — `PlayerHit` and `WallHit` feed the beam's length, nothing reads their rotation — but an entry that wants to sit something flat against whatever it hits gets that from the same transform.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`.
