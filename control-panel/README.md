# control-panel (Module)

A hand-held control panel that other players can operate: two grab handles to carry it and set it down, a row of push buttons, and a slider with a few detent positions (**slots**). Every client, late joiners included, sees the same lit buttons, the same slider slot, and the panel where it was left.

It is a reusable control surface, shipped as a worked example to copy and adapt. Two ways in:

- **Use it as it is:** drop `ControlPanel.prefab` on an avatar (§Install guide).
- **Lift the controls** (the `controls/` folder: `Panel.prefab` and its generated controller) into a build of your own (§Changing it).

The rest of the prefab is the worked example of carrying and placing the controls. This library's `two-hand-prop` entry carries the panel and its `object-sync` entry shares where it rests; a controller of this entry's own (the **glue**) decides which of the two moves the panel at each moment. The shape a **consumer** (whoever builds on the panel) is expected to make: a game with its own synced objects, whose buttons start and stop a round and whose slider sets the round's timer.

## How it works

- The panel rides `two-hand-prop`'s tilting prop. Each end carries an invisible grab handle: one hand carries the panel, two hands turn and tilt it, and a second player can steer while you hold it.
- Let go and the panel stays where it is. Your own client measures where it rests and sends that over `object-sync`'s synced position (its **word**), so every other client and every late joiner places it on that spot.
- Each button is a short physbone bone pointing out of the face, its cap skinned to the tip. A hand pushing the cap squashes the bone along its length (the physbone's squish). Grabbing is off and collision is on, so any player's hand presses it, yours included.
- Only your client reads the presses. A local-only receiver on each cap measures how far it is pushed down against a local-only sender lying at full-press depth under the button row. The panel senses its own parts, never the presser's hand.
- A press held for a moment toggles that button's synced on/off value, written by your client alone. Every client lights the button's lamp from the bool.
- The slider is one stretchy physbone bone along the slot, with the knob skinned to its tip. Grab the knob, slide it, and let go while posing it (a **pose release**, VRChat's own) to leave it there. Your client turns the knob's position into a synced slot number while you slide, with a margin past each boundary so the number does not flicker.
- The lamps are small glowing discs on the one mesh, each raised through the face by its own blendshape: one per button, one per slot, and an **offline lamp** another player's copy (the panel as their client draws it) shows until it has received the panel's synced position.
- What crosses the network: the on/off switch, whether the panel has left its rest on the avatar, which handle was grabbed first, the button bools, the slot number, and `object-sync`'s own switch and word (§Performance stats).

## Install guide

1. Drop one `ControlPanel.prefab` under the avatar root; one per avatar (§Additional notes). Edit the instance or an owned copy, never the package asset.
2. `TwoHandProp/HomeAnchor` attaches itself to the Hips at build. Drag its `Offset` child to place where the panel rests when not in use (its **home**); the panel moves there only in play (§Additional notes). It takes `Offset`'s rotation too. Some bases roll their Hips bone a quarter turn, which puts a rest authored in front at your side: turn `Offset` as well as moving it.
3. Add this library's `anti-cull` module to the avatar. A viewer whose client pauses your animator while you are off-screen misses the carry and the release, and its copy of the panel goes stale (`anti-cull` README §Traps).
4. If the avatar carries another `object-sync` build, make sure it declares `ObjectSync/Enable` on (§Traps).
5. Enter play mode or upload. The expression menu gains a `Control Panel` toggle, on by default. §Verifying the install tells a working install from a broken one.

Depends on the VRC SDK, VRCFury and Modular Avatar.

## How to use

- `ControlPanel/Enable` is the one menu control: synced, not saved, on by default. Off hides the panel on every client and brings it home; on again shows it at home.
- Grab one handle to carry the panel, grab the other as well to turn and tilt it, and let go to leave it in the world.
- Press a cap down: its lamp toggles the moment the cap passes most of its travel. A hand brushing across the caps toggles the first cap it pushes down.
- Grab the slider's knob and slide it; the slot's lamp follows your hand. Pose-release it to leave the knob where it is.
- **What a consumer reads.** `ControlPanel/Btn1` to `Btn4` are the button states and `ControlPanel/Slot` is the slider's slot, 0 at the knob's rest end. VRCFury leaves all five names unprefixed, so any controller on the avatar reads them by name. Declare them there as floats (the lamps read them as floats), unsynced, or not at all: a second declaration with other sync or save flags takes the name over (`gimmicks.md` §Packaging and interface). A button is a lasting on/off state, not a momentary pulse: read its level, or its change on your own copy. `ControlPanel/Detached` is true while the panel is away from home, carried or set down.

## Additional notes

- **One instance per avatar.** The menu control is a bare VRCFury `Toggle` and the published names carry no per-instance prefix, so two instances would share them; the entry's `object-sync` build also has one set of contact tags.
- **`ObjectSync/Enable` is shared and not on this panel's menu.** It is one parameter for every `object-sync` build on the avatar. This entry switches it on by default and never drives it, so another module's toggle that turns it off also stops this panel's word, and other players' copies light the offline lamp.
- **There is no menu path to the buttons or the slider.** `gimmicks.md` §Packaging and interface asks for every touch control to be reachable from the menu too, for desktop players and for testing; this entry ships none. A consumer that needs one adds menu controls to its own build.
- **In the editor the panel sits where it was authored, not at its home.** The constraints on `TwoHandProp/Body` ship switched off and the animator switches them on in play. Never enable or Activate the two constraints on the prefab root: they ship disabled at zero offsets and a VRCFury `ApplyDuringUpload` turns them on at build.
- **Do not rename anything inside the prefab.** The animations find their targets by path (§Traps).
- **A late joiner sees a set-down panel where it was left, or glides to it.** A panel at home shows at home. When the "away from home" bit arrives during the joiner's boot dwell, the panel stays hidden until the copy has the word, then appears there. A bit that lands after the dwell shows the panel at home first, then glides from home to the word (`grab-sync`'s accepted shape).
- **The buttons also work while the panel is carried.** A carried panel lags behind its carrier's hand on other clients, so a press on it lags more; whether to sense only while it is set down is open (§What is not proven here).

## Performance stats

```c++
PhysBone Components:  4        (two handles, the button cluster, the slider: Excellent's limit)
PhysBone Transforms:  15       (each handle 2, the button cluster 1 + 2 per button, the slider 2; Excellent allows 16)
PhysBone Colliders:   0        (collision checks 0: the button chain lists no collider; players' hands push it)
Contacts:             0 ranked (21 components, all local-only: the panel's 1 sender and 4 receivers, object-sync's 4 senders and 12 receivers)
Constraints:          22       (depth 9, read off an SDK bake; the module sets it)
Skinned Meshes:       1        (2448 triangles, 12 bones, 10 blendshapes at the shipped 5 slots; 1 material)
FX Animator Layers:   20       (not a rank stat: the glue 1, the controls 4, object-sync's 14, the Toggle's 1)
Synced parameters:    43 bits  (not a rank stat: the slot 8, the buttons 4, the switch, left-home and first-handle bits 3, ObjectSync/Enable 1, the word 27)
```

On a real avatar the panel can drop the performance rank. Excellent allows one skinned mesh, so the panel's mesh beside a body crosses to Good unless the build's optimizer merges them. Its four physbone components fill Excellent's allowance alone, so any other physbone crosses to Good too. The 43 synced bits can push an avatar past VRChat's 256-bit budget, where VRCFury's Parameter Compressor starts compressing menu toggles; a consumer's own `object-sync` build adds its own word. Each slot adds a blendshape; each button adds two physbone transforms, a receiver and a blendshape.

## Knobs

Two generators carry the knobs: `controls/generate.py` for the controls, `generate.py` for the frame around them. Edit a generator's CONFIG, rerun it, and recompile the `built/` folders that generator feeds (§Changing it). Each row gives the direction and the relation; the value lives in the code. `controls/generate.py`'s `validate()` refuses a controls value that breaks a relation below; the frame's CONFIG has no such guard.

| Knob | What it does |
|---|---|
| `N` (controls) | Slider slots. Sets the slot layer, the slot lamps and the mesh's slot blendshapes together, so a change rebuilds the mesh (§Changing it). Refused outside 2..255, the synced number's range, and wherever `hysteresis` is half a slot or more, so a large `N` needs a smaller `hysteresis` |
| `hysteresis` (controls) | How far past each slot boundary the knob must travel before the slot changes, as a fraction of the whole slider. Wider resists flicker at a boundary and makes the boundary feel sticky |
| `press`, `release` (controls) | Press depth, as fractions of a full press, at which a press is accepted, and below which every cap must rise before the next. Raising `press` demands a deeper press. Refused unless `release` is below `press` |
| `arm` (controls) | Seconds a press must stay past `press` before it counts; 0, the shipped value, stamps the frame the depth is crossed and emits no dwell state, because a delay before the stamp adds to every other player's wire and IK delay where a guard after it costs them nothing. Above 0 it rejects a brush that clears the cap within it, at that much latency on every press; a wider chain radius lengthens the time a face-level brush spends pressing, so the two are tuned together. Refused at or above `cooldown` |
| `cooldown` (controls) | Seconds from a release to the next accepted press: the floor between two toggles of one button. Refused at or under the wire's set-and-clear floor, below which two quick toggles can cancel on the wire (`gimmicks.md` §State machine patterns, the driver-copy edge detector) |
| `buttons` (controls) | The button layout the frame's mesh and `rig.json` read too: positions, the cap crown height and diameter, the cluster root's height, the chain radius, the visible travel (a full press), the total squish and the bone length. The count is refused outside one to eight and wherever a cap leaves the face or touches its neighbour: the caps are 30 mm across, so on 60 mm centres inside the 340 mm face six fit and a seventh does not. Each bone's tip rests one chain radius under its cap's crown, so the joint sphere is the press surface: a larger radius widens what a finger can land on and deepens the point where a hard press inverts (§Traps), and is refused where the sphere would reach the neighbouring cap at face level. The squish limit is squish over length; squish past the travel is how far the cap sinks into its well before it sits still. Changing any of these rebuilds the mesh and `Panel.prefab` |
| `boxMargin`, `boxWidth`, `senderRadius` (controls) | The receiver box is the squish plus the sender's diameter plus this margin deep, so the sender stays inside it over the whole squish, because a face-mode box reads 0 once the sender passes either face; the box's width; the sender's radius. The press thresholds are emitted over that depth. Refused when neighbouring boxes overlap |
| `slider` (controls) | The slot's run and position, and the slider bone's root, length, radius and `pull`. The stretch limit is the run over the bone length, which is what makes the stretch read as the knob's fraction along the slot. Refused when the bone's tip is not at the slot's start. `pull` is the rate the knob glides toward its rest or its pose when nothing holds it, a time constant near 1/(60 · pull) seconds at any frame rate: another player's copy sees a grab end before the pose arrives and glides toward zero in between, so a low pull shortens that dip, and the same glide is what carries a late joiner's copy onto the pose. At 0 nothing glides, so a late joiner keeps the knob at rest; the shipped 0.01 trades a shallow dip for a pose that takes a few seconds to arrive on a late joiner's copy. The frame's mesh reads the run, position and bone length from here |
| `mountPath`, `armature`, `mesh` (controls) | `mountPath` is where the `Panel` instance hangs, from the GameObject carrying the FullController; `armature` and `mesh` are the node names inside it. The lamp animations bind through all three. A consumer mounting the controls elsewhere regenerates with its own `mountPath` |
| `prefix`, `internal`, `tag` (controls) | The published prefix, the internal prefix (never under the published one), and the press contacts' private tag. `Panel.prefab`'s receivers, physbone parameters and tag are set to match by hand; `--check` compares them |
| `rigSeed` (frame) | The `object-sync` build's contact tags and park position, which move together. Unique among the avatar's `object-sync` builds |
| `bridge` (frame) | Seconds another player's copy holds its own replay of a release before it trusts the word: two word refreshes, Park's glide and a margin. Re-derive it, as its CONFIG comment gives, whenever the `object-sync` build's batch count or `syncDamp` changes |
| `acquire`, `resumeGrab` (frame) | Seconds a late joiner stays hidden while it settles onto the word, and seconds the panel stays hidden while a grab taken during a resume settles. Each covers a slow client's few frames with margin |
| `syncDamp` (frame) | How fast another player's copy glides from its replayed rest onto the word, per frame. Higher steps visibly; lower glides past one word refresh, so steps stack into a trailing lag. Frame-rate dependent (`spring-damping` README §Framerate dependence) |
| `handleSpacing` (frame) | The distance between the handles, set on every copy site `two-hand-prop` README §Knobs lists that this prefab keeps; `--check` holds each. Wider lengthens `two-hand-prop`'s handoff slide. The mesh's grips (`grips` in the frame's geometry) must sit at the handles, so a change rebuilds the mesh |
| Panel geometry (frame: `plate`, `grips`, `knob`, `buttonLamps`, `segments`, `offline`, `labelStrip`) | The mesh-only layout, emitted as `rig.json` for the Blender build beside the button and slider layout read from the controls CONFIG (§Traps). `plate`'s width must equal the controls CONFIG's `face`; the frame generator refuses a mismatch |
| Home rest (`TwoHandProp/HomeAnchor/Offset`, prefab) | Where the panel rests on the avatar when not in use |
| Enable default (the glue `controller.yaml`'s declaration and the `Toggle`'s default) | Written in both, which must agree; `--check` compares the Toggle's default to the glue's declaration |

The press thresholds, `arm`, `cooldown`, the cap layout and `syncDamp` are feel constants: the emulator measures what they do, only a headset shows whether they feel right.

**Provenance:** the carry, the two-handle arbitration and the handoff are `two-hand-prop`'s, which takes its grab cell, drop and late-join park from `grab-prop` (VRLabs World-Constraint ancestry) and its self-source damper from `spring-damping` (VRLabs Damping-Constraints, MIT). The placement is `object-sync`'s word (VRLabs Custom-Object-Sync ancestry) carried over `word-channel` (VRCFury Parameter Compressor ancestry), arbitrated against the cell in `compositions/grab-sync`'s shape, with the full-rotation word as `compositions/grip-sync` uses it; the nested sync build at its own CONFIG is `leash-stake`'s shape. The button machine's ladder, hold and cooldown are `zone-touch`'s. The Park repoint, the squish buttons with their self-sensing readout, the posed slider with its live quantizer and the blendshape lamps are this entry's own.

## Design notes

The state-by-state walk lives in three places: `generate.py`'s module docstring for the frame's construction and its clip table, the header of `controller.yaml` (the glue) for every frame decision the graph cannot show, and `controls/generate.py`'s docstring for the controls' nodes and layers. This section states what the rig guarantees and why.

**Park is a repoint, not an added source.** One new node, **Park**, holds where `two-hand-prop` thinks home is: the home rest, the word, or a glide between them, by its constraint weights. `two-hand-prop`'s prop node `Body` reads Park in the source slot where it read `HomeAnchor/Offset`, because an added source on `two-hand-prop`'s constraints can reorder its release frame with every animation unchanged (`two-hand-prop` README §Traps). Park belongs to this entry, so its own sources, `Body` among them, are outside that rule.

**Another player's copy glides from its own replay onto the word.** Each copy replays the carry from the grabs it saw, through its own view of the grabber's hand, so its release lands near the wearer's but not on it. Snapping onto the word would jump the panel by that error on every release, so the copy holds its replay for `bridge` and Park then glides it onto the word.

**A late joiner sees a set-down panel at the synced spot**, not hidden until a grab is witnessed: a joiner has to see a panel to walk up to it, by a hidden flush when the bit beats the boot dwell and by a visible glide from home when it does not. This is a design lean, not a measured necessity.

**A re-grab from the synced spot needs no settle state.** The one-hand carry freezes the panel's rotation where it stands, which on a copy at rest is the word's, so the carry starts from the word by construction; `compositions/grab-sync`'s `Reacquire` dwell exists for a sampled cell this frame does not have.

**The buttons press by squish.** With the angle limit at zero, a cap moves only straight down: in the emulator a sideways push still depressed it, and the bone end moved along the bone without scaling or turning, so the caps travel rigidly and the receivers ride the bone ends. Each button is its own chain under one physbone component, so the row costs one component.

**The readout senses the panel, not the hand.** A receiver reading a stranger's hand would depend on which senders their avatar carries and on join order, since a receiver that loads after a player joined may not sense them (`runtime.md` §Contacts). The cap's receiver against the panel's own sender reads depth from geometry alone, and local-only costs nothing against the rank.

**A press is a lasting synced bool, never a pulse.** A pulse sent while another player's client has your animator paused is lost; a level arrives on the next update. Only your client writes it, so every client agrees on one reading. One shared hold state waits for every cap to rise, so a finger resting across two caps cannot fire the second.

**The slider's grab bone does not collide.** A grab bone that collides is shoved by the reaching hand, the rule `two-hand-prop`'s handles already follow.

**Lamps are blendshapes on the one mesh.** Raising a parked disc through the face keeps the whole panel at one mesh and one material slot with no custom shader, which keeps it portable and maintainable.

**The controls are their own sub-entry.** `controls/` carries its own generator, controller and prefab so a consumer lifts exactly that folder, plus the model it skins.

## Traps

- **Never add a source to `two-hand-prop`'s constraints**, even at weight 0; repoint one. Park's sources are this entry's to change, and a change re-measures the release frame (§Verifying the install).
- **`ObjectSync/Enable`'s default is decided by declaration order, inside this FullController and across the avatar.** Inside, the glue and the controls declare it on and the `object-sync` build declares it off, so the `object-sync` controller and its parameters must stay after both, in both lists; `--check` pins the order. Across the avatar, a consumer's separate `object-sync` build declaring it off can bake it off for every build (`object-sync` README §Ground truth, its Seam bullet). Either way the panel stops sharing its rest and every other player's copy shows the offline lamp. Arm the consumer's build too, or check the baked default.
- **The lamp animations are path-bound.** They address the mesh as `mountPath` plus the mesh's name. Moving `Panel`, or renaming anything in it, leaves the lamps dark with no error while the presses and their bools still work.
- **A hard press can pop through.** When the presser's collider centre drops below a cap's resting tip, the solver pushes the tip the other way, it snaps back to rest, and the reading falls to 0 mid-press. The threshold is the tip's rest height, not how far it has squished, so only the seat depth moves it: with the tip one chain radius under the crown, a 30 mm radius puts it 20 mm below the face, the shipped 40 mm 30 mm below. The same radius is how far off centre a finger still moves a cap, so a wider one also dips the neighbours.
- **A sideways brush at face height counts as a press.** With `arm` at 0 any brush that pushes a cap past `press` toggles it, and since the hold and cooldown are shared across the row, a brush across several caps toggles only the first; `arm` above 0 rejects a brush that clears the cap within it.
- **One cap resting down blocks every button.** The shared hold state waits for every reading to fall below `release`, so a cap held down, or an object resting on it, stops every other button from firing.
- **The controls CONFIG owns the button and slider layout; the frame CONFIG owns the rest.** `generate.py` reads positions, bone length, travel, chain radius, cap diameter and the slot run from `controls/generate.py` into `rig.json`, so one edit moves the contacts, the physbones and the mesh together. The frame CONFIG holds only mesh geometry (plate, grips, knob, lamps, segments, offline lamp, label strip). The one shared number kept in both is the face width (`face` there, `plate.x` here), and the frame generator refuses a mismatch.
- **`Panel.prefab` does not follow the FBX.** The model is unpacked inside it, because an FBX prefab variant serializes no bone names for a binding or `--check` to address, so a re-export that moves a bone or changes a blendshape reaches nothing until the prefab is rebuilt (§Changing it). `controls/generate.py --check` fails on a moved bone's rest pose first.

## What is not proven here

The emulator has run the composed prefab: presses, the slider, a clone's lamps, a late joiner and the cull path on both a set-down and a carried panel. The release-frame lag was measured before the controls were nested under `Display`, a change that touches no constraint, and not again after. Not reached in the emulator:

- **A remote handoff and two-hand turn**, which no clone can witness, since a live grab never reaches it.
- **A mirror clone**, which has not been watched.

Everything below needs the shipping client:

- **The slider's drawn position across clients.** After a release made while the hand moves, each client may hold a slightly different knob position; whether they converge on the wearer's, stay apart until the next grab, or race, and what a late joiner receives, is unmeasured. The slot number is the wearer's and is synced.
- **A stranger's real hand on the buttons:** press depth, brush rejection, a double press across neighbouring caps, cap size against real hand colliders (which vary per avatar), and the feel of the round trip to the lamp.
- **The press thresholds against the client's receiver refresh**, which can skip frames the emulator never skips, so a light tap that crosses `press` for a frame or two may go unseen.
- **Join order:** you joining after the presser and the press still reading, which the self-sensing readout is built to guarantee.
- **A press on a carried panel**, which decides whether the buttons should sense only while it is set down.
- **What a plain release does to a knob that was posed before the grab**, and two players reaching for the knob at once.
- **The handles under delayed remote hands**, the size of each client's replay drift, and a release into `bridge` after a grab the copy saw.

## Changing it

- **Regenerate the frame as a unit.** Run `python control-panel/generate.py` from the repo root; it rewrites the glue's clip table from `two-hand-prop`'s current animations, `object-sync/controller.yaml` and `rig.json`. Recompile `built/` and `object-sync/built/` over their committed `.meta`s, addressing both paths as `Packages/com.ryan6vrc.patterns/control-panel/…` (`CONVENTIONS.md` §The gate). A retune of `two-hand-prop` reaches this entry only through that run.
- **Regenerate the controls.** Run `python control-panel/controls/generate.py`, then recompile `controls/built/` the same way.
- **Run both checks after any prefab edit**: `python control-panel/generate.py --check` for `ControlPanel.prefab`, `python control-panel/controls/generate.py --check` for `Panel.prefab`. Nothing runs them for you.
- **Edit the prefabs in place.** There is no builder: load the prefab's contents, edit, save. A save that recreates a GameObject re-mints its file IDs, so judge an edit by `--check`, not by the size of the diff.

**Changing `N` or the button layout** moves the mesh:

1. Set the controls CONFIG (the layout the frame reads from it); touch the frame CONFIG only for mesh-only geometry. Regenerate both.
2. Rebuild the mesh with `assets/ControlPanel_build.py` from `rig.json` (its docstring has the command) and export it with `assets/ControlPanel_export.py` over `assets/ControlPanel.fbx`, so its `.meta` and material remap hold.
3. Rebuild `Panel.prefab` over its existing asset, so `ControlPanel.prefab`'s nested reference holds: instantiate the FBX, unpack it completely, rename the root `Panel`, add the two physbones, the receivers and the sender with the values `rig()` in `controls/generate.py` emits, and save.
4. Recompile, and run both checks.

**Lifting the controls into your own build:**

1. Copy `controls/` and the assets `Panel.prefab` uses from `assets/` (`ControlPanel.fbx`, `ControlPanel.mat`, the two atlas PNGs). Re-GUID every copied `.meta` that would collide with this entry's, `built/` included, and repoint the copy (`CONVENTIONS.md` §An entry is a folder).
2. Set `mountPath` to where your `Panel` instance hangs below your FullController's GameObject; on an avatar that also carries `ControlPanel.prefab`, change `prefix`, `internal` and `tag` too. Regenerate and recompile.
3. Add the controls controller and its parameters to your FullController, and `<prefix>/*` to its `globalParams`.
4. The offline lamp reads `ObjectSync/Enable` and `OS/Ready`, which only an `object-sync` build merged in the **same** FullController provides; without one, every other player's copy shows the offline lamp for good. Merge your build there, with the controls ahead of it in both lists. The generator has no switch to leave the offline layer out.

## Verifying the install

Run both `--check`s first (§Changing it); they catch the hand-maintained prefab surface and nothing below. In the emulator, enter play only after a forced script reload once anything was compiled or saved, or the constraints can register without running; read `Body` against `HomeAnchor/Offset` right after entry before trusting anything else.

Enable on, in play: the panel rests at `HomeAnchor/Offset` on the hips. At the avatar root's origin instead, the BoneProxy never resolved. A menu toggle that does nothing means the enable came out of the build prefixed, or another declaration on the avatar captured `ControlPanel/Enable`; read the built name (`gimmicks.md` §Packaging and interface).

Carry it and let go: it stays in the world. A panel that drifts with the avatar after release means the root pin's `ApplyDuringUpload` never fired. A drop that springs back to where the grab began means the release frame is being read live: a source was added to a `two-hand-prop` constraint, or a carry node left `Body` (`two-hand-prop` README §Traps). The release is only trustworthy driven from `Update()` (`emulator.md` §Induce a physbone grab/pose).

Press a cap with a scripted collider: `CP/Press<i>` rises with depth, the button's bool flips the frame the reading passes the press threshold (or after `arm`, when it is set), and its lamp rises. The collider reaches the solver only once it is in the button physbone's `colliders` list and the physbone component has been cycled; never cycle the `Buttons` GameObject, which re-registers the receivers with the sender already inside them and leaves every reading at 0 for the session. A press that never stamps has three causes: a reading stuck at 0 (the receiver left its bone end, or its tag differs from the sender's), a reading that never reaches `press` (the press popped through), or another cap resting down. A bool that flips with a dark lamp means the lamp animations no longer find the mesh (§Traps). Only your own copy stamps; a clone never does.

Grab the knob, slide it and pose-release it: `ControlPanel/Slot` steps as the knob crosses each boundary and the lit segment follows. Spawn a non-local clone (`emulator.md` §Remote clone): its lamps follow your bools and slot a sync tick later, and its offline lamp is lit until its `OS/Ready` rises and dark after. An offline lamp that never clears on a clone means its word is not arriving or `ObjectSync/Enable` is off (§Traps, both orders).

## Rig

The prefabs are the shipped artifacts; `generate.py`'s docstring is the construction record of `ControlPanel.prefab`, and `controls/generate.py`'s of `Panel.prefab`.

    ControlPanel                 root: parent + scale constraint → object-sync's World.prefab, disabled, zero
                                 offsets, switched on at build by a VRCFury ApplyDuringUpload; the bare
                                 Toggle `Control Panel`; the FullController playing glue, controls, object-sync
    ├─ TwoHandProp               nested two-hand-prop/TwoHandProp_Full.prefab: its FullController, Toggle,
    │                            FreezeToWorld and placeholder meshes removed; handles respaced
    │  ├─ Body                   the prop: its home source repointed to Park (§Design notes)
    │  │  ├─ Display             shown and hidden by the animations
    │  │  │  └─ Panel            nested controls/Panel.prefab: the lift unit
    │  │  │     ├─ Armature/Panel        the panel bone; the local-only press sender lies along the button row
    │  │  │     │  ├─ Buttons            one VRCPhysBone over the button chains: squish only, collision on
    │  │  │     │  │  └─ Btn<i>/Btn<i>_End   one chain per button; the cap skins to the end, which carries
    │  │  │     │  │                         the local-only face-mode receiver CP/Press<i>
    │  │  │     │  └─ Slider/Slider_End  the posable stretch VRCPhysBone CP/Slider; the knob skins to the end
    │  │  │     └─ ControlPanel        the one skinned mesh: the lamp blendshapes, one material
    │  │  └─ CarryA, CarryB, AimNode, RestA, RestB   two-hand-prop's carry nodes
    │  ├─ HolderA, HolderB       the invisible grab handles
    │  └─ HomeAnchor             MA BoneProxy → Hips
    │     └─ Offset              the home rest
    ├─ Park                      position + rotation constraint over [HomeAnchor/Offset, ObjectSync/Sync,
    │                            Park itself, Body]; the glue animates the weights
    └─ ObjectSync                nested object-sync/ObjectSync.prefab (one object, full rotation): its
                                 FullController, Toggles, ApplyDuringUpload and pin removed; re-parked and
                                 retagged to rigSeed; Sync_Target ← Body, so the wearer measures the panel
