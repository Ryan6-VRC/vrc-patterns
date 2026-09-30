# world-pose (Module)

An instrument that makes an avatar report where it is in the world. It publishes seven unsynced floats: the avatar root's position on three axes, its heading, and the head's heading. An OSC reader outside VRChat decodes them to metres and degrees. Use it to measure what the VRChat client actually does (the client tier of the workspace's `docs/verify.md`). It is not a way to share a position with other players: nothing it reads leaves the wearer's client.

## How it works

- The rig reads contact receivers in face-proximity mode: a box receiver whose value rises linearly as the sender's surface nearest the box's +Z face moves toward that face.
- Every box sits under `World`, a node held at the world origin and at world scale by two constraints. Both source `assets/World.prefab`, a prefab that is never instantiated and so resolves as the world origin on every client. So avatar scale moves no box, no sender and no decode constant.
- **Position.** Three boxes on `Pos`, at the world origin, each read one world axis. Their sender, `Pos/Sender`, is constrained to sit a small fixed fraction `g` (the **gain**) of the way from the world origin to the avatar root. So a root anywhere inside `range`, the metres per axis the rig must cover (§Knobs), puts the sender inside the boxes.
- **Heading.** On `Yaw`, a `Holder` node copies the avatar root's heading and carries a sender, `Mark`, a fixed distance ahead of it. Two boxes read `Mark` along world X and world Z; the two readings carry the sine and cosine of the heading.
- **Head heading.** `HeadYaw` repeats that with its `Holder` copying `HeadAnchor`: a node moved under the humanoid Head at build that keeps the rotation it was authored with. So the head heading decodes to 0° with the head at rest over a root at heading 0.
- Each of the three groups (`Pos`, `Yaw`, `HeadYaw`) has its own private collision tag. Every receiver and sender is local-only, and each receiver reacts to the wearer's own senders only. There is no animator layer and no menu.

## Install guide

1. Drop `WorldPose.prefab` onto the avatar as a direct child of the avatar root, at position 0, rotation 0 and scale 1. Edit the instance or an owned copy, never the package asset.
2. Leave the avatar in its rest pose in the scene. `HeadAnchor` finds the head on its own when the avatar builds and takes its frame from the head's pose at that moment.
3. Build or upload as usual. The avatar gains seven parameters under `Pose/` and no menu control.
4. In the client, turn OSC on, and read the parameters by §How to use.

Depends on the VRC SDK, VRCFury and Modular Avatar. The head heading needs a humanoid rig.

## How to use

The seven parameters are published under their bare names: VRCFury adds no `VF##_` instance prefix to them. They are unsynced and unsaved. Each is a **momentary** sensing output (`docs/osc.md` §Latching and momentary): it reports the pose now and holds nothing, so sample it.

| Parameter | Decodes to |
|---|---|
| `Pose/X`, `Pose/Y`, `Pose/Z` | The avatar root's world position in metres on that axis: `metres = posA + posB × reading` |
| `Pose/YawX`, `Pose/YawZ` | The avatar root's heading: `degrees = atan2(yawA + yawB × YawX, yawA + yawB × YawZ)` |
| `Pose/HeadYawX`, `Pose/HeadYawZ` | The head's heading: the same formula over the two `HeadYaw` readings |

Heading is Unity's: clockwise seen from above, 0 along world +Z. The constants are functions of `generate.py`'s CONFIG (§Knobs); `rig.json`'s `decode` block carries their values and each formula written out:

- `g = (boxSize / 2) / (range × (1 + MARGIN))`
- `posB = boxSize / g`, `posA = −(boxSize / 2 + senderRadius) / g`
- `yawB = yawBox / yawArm`, `yawA = −(yawBox / 2 + senderRadius) / yawArm`

**A reading of exactly 0 is not a position.** It means the receiver is not sensing: its component or GameObject is switched off, it has not yet acquired its sender, or the sender is outside the box. The position formula maps 0 to `posA`, a point that looks real, so reject a zero before decoding. A heading pair whose decoded sine and cosine are far from unit length is not a heading either.

**Resolution follows the gain.** A position error is the float32 error of the sender's world position, where the contact system measures it, multiplied by `1/g`. So a wider `range` coarsens the position reading in proportion; the headings do not depend on `range`.

**Read the first values over OSCQuery.** OSC output is change-only, and a reading that does not change is never re-sent (`docs/runtime.md` §Contacts), so a reader that starts while the avatar stands still can wait indefinitely. OSCQuery serves every declared parameter's current value on request (`docs/vrchat-client.md`); follow the stream after that.

## Additional notes

- **One instance per avatar.** The names are unprefixed, so two copies would write the same parameters.
- **`range` is measured from the world origin, not from where you spawn.** A world whose play space sits far from the origin needs a larger `range`; some way past it every position reading drops to 0 (§Traps).
- **The position boxes sit at the world origin, where many worlds spawn players.** They exist on the wearer's client only, react to the wearer only and accept avatar senders only, so nobody else's contacts reach them.
- **Nothing is shown.** The rig has no renderer. Its contacts cost nothing toward rank; its constraints count. It is an instrument: leave it off an avatar you do not need to measure.

## Performance stats

```c++
Contact Receivers:  7        (local-only: none count toward rank)
Contact Senders:    3        (local-only: none count toward rank)
Constraints:        5        (depth 3)
FX Animator Layers: 0
Synced parameters:  0 bits
```

## Knobs

Everything is `generate.py`'s CONFIG: edit, rerun, recompile `built/` as a unit and rebuild the prefab to `rig.json` (§Changing it). The values live in the code; `validate()` refuses a value that breaks a relation below. After any change every reader must decode with the new `rig.json` constants: stale constants mis-decode without any error.

| Knob | What it does |
|---|---|
| `prefix` | The published names' prefix, and the one a consumer renames. `globalParams`, VRCFury's list of names it leaves unprefixed, is `<prefix>/*`. Must be a parameter path with no spaces |
| `range` | Metres per axis about the world origin the position reads inside. It sets the gain, so it moves `posA`, `posB` and the resolution: wider reads further and coarser. The reading stays linear a margin past it (`MARGIN` in the code) |
| `boxSize` | The position boxes' edge. Larger raises the gain at the same range, which sharpens the resolution. The SDK caps a contact shape at 6, and the heading groups' parks (`PARK` in the code) must clear it |
| `senderRadius` | Every sender's radius. It enters `posA` and `yawA`. The position sender's surface must stay inside the box at `range`, so it must be small beside `boxSize` |
| `yawBox`, `yawArm` | The heading boxes' edge and `Mark`'s distance from its `Holder`. The arm plus the sender radius must stay inside half the box, and the box must clear the position boxes from its park |
| `tag` | The stem of the three private collision tags: `<tag>Pos`, `<tag>Yaw`, `<tag>HeadYaw` |
| `controller` | The emitted controller's name |

**Provenance:** the face-proximity box readout is `box-tracker`'s (VRLabs Contact-Tracker ancestry); the world pin, the scale pin and a sender held at a fixed fraction between the origin and a moving point are `object-sync`'s idioms. Generalized from a probe avatar built to measure client behaviour; the head proxy's framing follows `docs/runtime.md` §Constraints (VRC).

## Design notes

`generate.py`'s module docstring states the rig and the decode derivation; `rig.json` holds every number the prefab is built to.

**No layers, but a controller.** The receivers write their parameters directly, so no animator state is needed. The controller exists to declare the seven floats, so the build carries each one as an animator parameter as well as an expression parameter from the params asset. Declared in both places is the shape the client has been measured reading; a params-asset-only declaration is not (§What is not proven here).

**One tag per group.** Past the edge of `range` the position sender leaves its boxes and keeps moving outward, a fraction of the root's distance. On a shared tag it would reach the heading boxes on a long enough walk; on its own tag it cannot.

**The head proxy is a node the generator emits**, so `--check` holds it. `HeadAnchor` carries an MA `BoneProxy` on the humanoid Head in the mode that keeps the node's own world rotation, and it is authored at identity under the prefab root. After the move it sits under the head, framed to the avatar root at rest. A heading read from the head bone directly would carry that bone's rest frame, and a head bone that rests pitched near 90° sits at the branch where the heading's Euler decomposition flips 180° (`docs/runtime.md` §Constraints (VRC)).

**The pins are enabled in the prefab.** `object-sync` ships its pins disabled because a seam below them could capture a world pose while an editor-solved pin holds it at the origin. Nothing below `World` here captures a world pose.

## Traps

- **The prefab must sit at the avatar root's identity.** The position sender and the root-heading `Holder` both source the prefab root, standing in for the avatar root. A moved instance adds its offset to the position, rotating with the root; a rotated one adds its rotation to the heading.
- **Far out, every position reading drops to 0 together.** The three position boxes share one cube, so once the root is more than about `−posA` metres out on any axis the sender leaves the cube and all three read 0. Just before that, on the positive side, the axis reads 1 for `2 × senderRadius / g` metres.
- **The head heading at rest is the idle head pose.** An avatar's idle animation turns the head a little, and the readout reports it, so the head and root headings differ at rest.
- **A head posed in the scene at build offsets the head heading** by that pose, for as long as the avatar is worn.

## What is not proven here

Needs the client: whether a receiver's write reaches a parameter the params asset alone declares; the per-frame noise the client adds to a contact reading, which grows with the distance from the world origin (`docs/runtime.md` §Contacts) and reaches the position decode through `1/g`.

## Changing it

- **Regenerate as a unit.** Run `python generate.py`, recompile `built/` over the committed `.meta`s (`CONVENTIONS.md` §The gate), then rebuild whatever `rig.json` moved in the prefab: box sizes and rotations, sender radii, the sender weights `g` and `1 − g`, the `Mark` positions, the parks, the tags.
- **Run the check after every prefab edit.** `python generate.py --check` holds the prefab's hand-maintained surface to CONFIG. Nothing runs it for you.

## Verifying the install

Run `--check` first. Then in play with the avatar root at the world origin, unrotated: `Pose/X`, `Y` and `Z` decode to 0 m and `Pose/YawX`, `YawZ` to 0°; the head pair decodes to the idle head pose, near 0°. Move and turn the root: the decode follows it at any avatar scale.

- **Position off by an offset that turns with the root, or the root heading off by a constant:** the prefab is not at the avatar root's identity.
- **Position off by the same constant at every pose:** the prefab's sender radius differs from CONFIG's.
- **A head heading that tracks the root heading exactly while the head turns:** `HeadAnchor` never moved under the head. The avatar has no humanoid Head, or the BoneProxy was removed.
- **A head heading off by a constant at rest, beyond the idle pose:** the avatar was posed when it built.
- **`VF##_`-prefixed names on the reader:** `globalParams` lost `<prefix>/*`.
- **One group reading 0 throughout:** its boxes and sender carry different tags, or its receivers are switched off.
- **Nothing arriving on the stream:** OSC is off in the client, or the avatar is standing still; read over OSCQuery.

## Rig

    WorldPose                  root — VRCFury FullController (the built controller and params); at the avatar root, identity
    ├─ HeadAnchor              MA BoneProxy → Head, keeping its own rotation: the head proxy
    └─ World                   parent + scale constraints → assets/World.prefab, zero offset: world origin, world scale
       ├─ Pos                  three local-only face boxes, +Z faces on world X, Y, Z
       │  └─ Sender            position ← [WorldPose at g, World at 1 − g]; the <tag>Pos sender
       ├─ Yaw                  parked on world +X; two face boxes on world X and Z
       │  └─ Holder            rotation ← WorldPose, Y axis only
       │     └─ Mark           yawArm ahead on +Z; the <tag>Yaw sender
       └─ HeadYaw              parked on world −X; two face boxes on world X and Z
          └─ Holder            rotation ← HeadAnchor, Y axis only
             └─ Mark           the <tag>HeadYaw sender
