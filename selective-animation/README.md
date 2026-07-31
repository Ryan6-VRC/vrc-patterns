# selective-animation — tag a player by pointing at them (Module)

Point at someone and hold the gesture: their copy of your avatar changes, and the people you did not point at are unaffected — everyone your aim line crosses is pointed at, so read that literally. The tag persists on that person's client until you clear it, and a menu bool tags your own copy for you. A native `VRCRaycast` masked to the observer's own player capsule does the addressing, and a state latch on that observer's animator does the remembering — so the per-player state lives distributed across the people who hold it, and **nothing identifying anyone crosses the wire: 3 synced bits total**, the same three whether one person is tagged or twenty.

**Provenance:** VRLabs' MIT [`Selective-Animation`](https://github.com/VRLabs/Selective-Animation) established the mechanism and is the direct ancestor. It predates `VRCRaycast` and so reconstructed a hit flag out of geometry — two identically-configured FinalIK Grounders whose end transforms coincide on a hit and separate on a miss, plus a contact sender/receiver pair, across 16 GameObjects and 4 constraints. Native `_Hit` reports that flag directly, so all of it drops out along with the FinalIK dependency. Two things are inherited deliberately: the single-layer collision mask (below), and the wearer-facing laser, which is not decoration.

## Interface

- **Params:**
  - `SelectiveAnimation/Enable` (bool, in) — synced, **unsaved**. The master gate, and **off is the
    all-clear**: every client drops its latch at once, which is why this entry ships no separate
    failsafe control.
  - `SelectiveAnimation/Paint` (bool, out) — synced, **unsaved**. The held command; an observer latches
    on (their own `_Hit` AND this). Written only by the wearer's `localOnly` drivers.
  - `SelectiveAnimation/Erase` (bool, in) — synced, **unsaved**. A mode, not a second command: it flips
    what a hit writes, so pointing untags instead of tagging.
  - `SelectiveAnimation/SelfTag` (bool, in) — **unsynced**, unsaved. Tags your own copy. Being unsynced
    is load-bearing, not an economy — see **Before you compose it**.
  - `SelectiveAnimation/PaintMenu` (bool, in) — **unsynced**. Menu parity for the point gesture; ORed
    with it into the one synced `Paint`, so parity costs no bit.
  - `SelectiveAnimation/Ray_Hit`, `Ray_Ratio`, `Wall_Ratio` (sensing) — the two rays' outputs. Never
    synced: a natively-driven param is re-driven locally every frame, and a synced copy would read the
    wearer's replicated value on a clone instead of that clone's own ray.
  - `SelectiveAnimation/Tagged` (bool, out) — animator-local on each client, the consumption point for
    gating your own layers. `Clear` (float, AAP) is the clearance test; `One` is a Direct-tree weight.
  - `GestureRight` (VRC built-in) — FingerPoint is the affordance.
- **Seam:** VRCFury `FullController` on the prefab root (FX, `rootBindingsApplyToAvatar: 0` ↔ `basis: mount-root`), merging `built/SelectiveAnimation_Fx_Parameters.asset` and `assets/SelectiveAnimationMenu.asset` at prefix `Selective Animation`. `globalParams` exports **one** name, `SelectiveAnimation/Tagged` — everything else takes the instance prefix, menu control and animator param rewritten together, so no name of this module's can collide with a host avatar's. MA `BoneProxy` on the hand anchor alone — placement you can see while authoring; every animated binding targets `Beam`/`Payload`, which no BoneProxy touches.
- **Dependencies:** VRC SDK + VRCFury + Modular Avatar, and a **humanoid** avatar (the BoneProxy resolves Right Hand through the humanoid mapping). Composes well with `anti-cull` — see below.
- **Required assets:** `assets/SelectiveAnimationBeam.mat` (Unity Standard, self-contained — no Poiyomi or lilToon dependency) and `assets/SelectiveAnimationMenu.asset`, the four-control menu the seam merges. Both live in `assets/` rather than `built/` because neither is compiler output; the menu is hand-maintained against the **Params** list above. `Payload` is a placeholder sphere on the built-in default material.

## Before you compose it

- **The ray is a line, and there is no occlusion between players.** On each client the only candidate collider is *that client's own capsule*, so a person standing behind your target is not shadowed by them — everyone whose capsule the line crosses latches. This is the entry's defining failure mode, and the two things that bound it are the deliberately short range and the wearer-only beam: **look at the beam and see who is standing in it before you commit.** Lengthening the range widens the blast radius in direct proportion.
- **Aim `Origin` per rig — it is the entry's one install-time value.** `Origin` *is* the ray frame: both rays fire along its local `+Z` (a constant they never need edited), the beam is a plain child pointing the same way, and the hit transforms rest at range along it. So orienting `Origin` aims the ray, the beam and the rest pose together, and there is no second value to keep in step. Drag its blue `+Z` axis onto your index finger, or set it exactly with `Quaternion.LookRotation(hand.InverseTransformDirection((indexProximal.position - hand.position).normalized))`. Bone roll is a red herring — a direction along the bone's own long axis is invariant under roll; what varies between rigs is *which* local axis runs along the bone, and Unity's `forward` is correct on none of the rigs measured.
- **`Origin` carries both the offset and the aim**, and it is the node to edit — `AsChildAtRoot` discards edits made on the `Aim` proxy itself at build. Slide it to move the ray's start point; rotate it to aim.
- **A target who has you view-culled cannot be tagged**: their client is not running your animator, so no ray of yours evaluates there. This is why the command is **held** rather than pulsed — a held command latches the frame they turn back and their animator resumes, where a momentary one would have risen and fallen unseen. To paint people who are looking away, compose `anti-cull`, whose bounds inflation is what keeps a remote's animator running when you leave their view.
- **Keep `SelfTag` unsynced.** It is not just a saved bit: being unsynced is what distinguishes your own copy and its mirror clone from every remote (a remote reads its default forever), which is how the self-tag reaches a mirror without a mirror-detection rig. Declaring it synced would tag you on everyone's screen at once. The merged menu is what protects this — because the param takes an instance prefix, a host avatar declaring the same name cannot capture it and impose its own flags.
- **The wearer never sees a hit register.** Your own client carries no remote's capsule, so your ray reports nothing when you point at someone. Nothing is broken; there is simply no local confirmation to give, which is the whole reason the beam ships.

## How it works

Two rays leave the same transform with the same direction and range. The **player ray** is masked to `PlayerLocal` **alone** — not the SDK's `HitPlayers` mode, which also queries the `Player` layer. That removes the `Player`-layer path entirely: whatever colliders remote players may present there cannot be returned, so no other player's collider can stand in for the observer's own. What it does not do is make the hit set a singleton — a world collider or trigger on `PlayerLocal` is still a valid hit, and `HitWorlds` does not query that layer, so such an object would read as maximally clear and tag every observer whose ray crossed it. Whether VRChat permits world colliders there is unsettled and worth pinning before this claim is leaned on. Two things rest on the layer number itself and are **in-game-only**: that the local capsule is on `PlayerLocal` rather than `Player` at all (get this wrong and the ray is simply dead), and that nothing else shares the layer. VRLabs' shipped ancestor masks the same single layer, which is why it is the default here, but an inherited constant is not a measurement. The **world ray** exists only to keep tags from passing through geometry; a Direct blend tree subtracts the two `_Ratio` values into `Clear`, positive when the player hit is nearer than the world hit, and the latch requires it.

The latch itself is a **state, not a parameter** — the animator's own position is the memory, so no driver holds it. `Tagged` (ray-latched) and `SelfTagged` (menu-latched) play the same payload clip and are separate states because the wearer's own ray *can* hit the wearer's own capsule: sharing one state would expose a self-tag to the observer's untag edge, so erasing near your own body would clear it. A single-state form does exist — gate the self-exit on `IsLocal` — it just carries that defect. Both stamp the exported `SelectiveAnimation/Tagged`, and that export is also what carries the latch onto a clone: a clone traverses fresh from Entry and runs no drivers, so it cannot re-derive the latch, but it does inherit the driven value, and the entry ladder reads it back. Without that rung a tagged avatar would appear untagged in the observer's mirror.

**Durability is `runtime.md`'s cull table** and needs no re-measuring: view cull and distance-hide pause an observer's animator without rebuilding it, so the latch survives both; manual hide/show is the only genuine rebuild, so that — along with an avatar switch or reload — drops it. Re-pointing is the only repair, which is what holding the command is for.

Empirical constants (labeled in `controller.yaml`; `runtime.md` 90% rule):

| Constant | Value | Locked by |
|---|---|---|
| Range | `distance` on **both** raycasts, plus `BeamMesh`'s local `position.z` (half it) and `scale.z` — four fields, one number. The rays must share a transform *and* agree on `distance` **and** `applyTransformScale`, or their `_Ratio` values are normalised against different maxima and `Clear` is meaningless | chosen short so the no-occlusion line stays surveyable from the beam; widening it widens the blast radius. The beam is the only affordance bounding that, so a beam disagreeing with the rays is a safety defect, not a cosmetic one |
| Clearance tolerance | the `Clear greater` threshold on the `Aiming` commit and the untag edge | zero, biased against the expensive error. A target standing against a wall still clears it comfortably — a capsule surface stands proud of the wall by its own radius — so the negative slack an earlier revision carried bought nothing and admitted targets slightly *behind* geometry |
| Beam length | `BeamMesh`'s local position and scale carry the range, so `Beam`'s animated `scale.z` stays unitless and a retune touches only the prefab | structural |
| Payload | the `sa_tagged` / `sa_untagged` clip pair | the swap point — this is a placeholder |

**Two documented extensions.** A **class band** (green / spotlight / hidden rather than one bit) is a synced class param plus a `copy` in place of the latch's `set`: one int costs 8 bits, or 2 bools for up to four classes. **Stripping to one raycast** drops the world ray and the `Clear` condition, buying back the perf rating (`raycastCount` 1 is Excellent on both platforms, 2 is one grade below) at the cost of tags passing through walls. Neither changes the mechanism.

## Verifying the install

Post-bake the sync surface is exactly three bools — `Enable`, `Erase`, and `Paint` under whatever instance prefix VRCFury gave it, since only the five `globalParams` names survive verbatim. `SelfTag`, `PaintMenu` and both rays' outputs must read unsynced, and `SelectiveAnimation/Tagged` must appear **un-prefixed**: it is the documented export, and a consumer's layer conditioned on the bare name silently never fires if it was renamed. MA must have moved `Aim` onto the right hand — check the BoneProxy's `target` as well as the position, because in an unfocused or agent-driven editor MA's edit-time placement does not tick and the anchor reads at the avatar-root origin *with its target correctly resolved*, which is indistinguishable from a real failure. Enable the module and confirm the beam appears on your own copy and not on a remote clone, that its length tracks the world ray (walk it up to a wall), and that it changes colour under Paint and again under Erase.

What the emulator cannot show for this entry is **selectivity itself** — that the person you point at is the one who latches. The editor has no player colliders at all, and standing a capsule in for one is a false pass, because the client strips every collider off a real avatar. Substituting a collider on the `PlayerLocal` layer does exercise the machine — the param path, the clearance test, the latch, the `IsLocal` split — and that is what the entry was verified against; it proves nothing about where a real capsule sits or which client owns it. Selectivity needs two real clients.

## Rig

    SelectiveAnimation              root — VRCFury FullController + four Toggles
    ├─ Aim                          MA BoneProxy → Right Hand, AsChildAtRoot
    │  └─ Origin                    consumer-editable offset (position only — see above)
    │     │                         THE ray frame — its rotation is the one per-rig install value.
    │     │                         VRCRaycast ×2 both firing local +Z (constant): player ray
    │     │                         (HitCustomLayers, PlayerLocal alone) and world ray (HitWorlds);
    │     │                         same range and SnapToEnd. Origin's active flag IS the rig's
    │     │                         lifecycle — the Rig layer stows it whenever Enable is off
    │     ├─ Beam                    plain child, +Z down the ray; scale.z = the world _Ratio
    │     │  └─ BeamMesh             carries the range; owned Standard material, colour = the mode
    │     ├─ PlayerHit               result transform — MANDATORY: a raycast with none never registers
    │     └─ WallHit                 result transform. Both rest at local (0,0,range) so the rig reads
    │                                correctly before any ray has run: parented to the module root they
    │                                would sit at the avatar's feet and drag the beam down with them
    └─ Payload                      placeholder sphere, built-in default material — swap this

A `resultTransform` is not optional on either ray: without one the component never registers and never casts — no hit, no params, no error, no diagnostic.

## Rebuilding

`controller.yaml` → `CompileController` → `built/` (committed; the prefab references it by GUID — recompile is GUID-stable; regenerate controller + params asset as a unit over the committed `.meta`s). The prefab is hand-maintained against the Rig section above.
