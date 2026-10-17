# control-panel (Module)

A hand-held control panel other players can operate: two grab handles to carry it and set it down, and four rows of controls on its face. Four push buttons, a four-way selector, a slider with a few detent positions (**slots**), and a smooth slider. Every client, late joiners included, sees the same lamps, the same knob positions, and the panel where it was left.

It is a reusable control surface, shipped as a worked example to copy and adapt. Two ways in:

- **Use it as it is:** drop `ControlPanel.prefab` on an avatar (§Install guide).
- **Lift the controls** (the `controls/` folder: `Panel.prefab` and its generated controller) into a build of your own (§Changing it).

The rest of the prefab is the worked example of carrying and placing the controls. This library's `two-hand-prop` entry carries the panel and its `object-sync` entry shares where it rests; a controller of this entry's own (the **glue**) decides which of the two moves the panel at each moment. The shape a **consumer** (whoever builds on the panel) is expected to make: a game with its own synced objects, whose buttons start and stop a round, whose selector picks a mode, and whose sliders set the round's timer and difficulty.

## How it works

- The panel rides `two-hand-prop`'s tilting prop. Each end carries an invisible grab handle: one hand carries the panel, two hands turn and tilt it, and a second player can steer while you hold it. The face is mounted tipped 45° toward the holder, since the two-hand carry keeps the panel level side to side. At home it follows the hips' heading but never their lean, so a grab from home starts level.
- Let go and the panel stays where it is. Your own client measures where it rests and sends that over `object-sync`'s synced position (its **word**), so every other client and every late joiner places it on that spot.
- **Buttons and selector.** Each button cap and each selector segment rides a short physbone bone pointing out of the face. A hand pushing it down squashes the bone along its length (the physbone's squish). Grabbing is off and collision is on, so any player's hand presses it, yours included.
- Only your client reads the presses. A local-only receiver under each cap measures how far it is pushed down against a local-only sender lying under its row. The panel senses its own parts, never the presser's hand.
- A button press toggles that button's synced on/off value. A selector press sets the synced choice to that segment; the chosen segment glides down and stays sunk with its dot lit, while the one it replaces glides up and its dot fades.
- **Sliders.** Each slider is a grabbable physbone bone lying along its track, under the knob's channel. Grab anywhere along the track and the bone's tip jumps to your hand. A box receiver along the track reads where the tip is, on every client.
- The bone carries the knob's position **only while held**. Let go and it springs back past the track's high end, where nothing reads it. The knob is drawn by the animator from a **knob memory**: it follows the reading while held, holds where your hand let go for a short **settle**, then lands on the synced value.
- While you slide, your client writes the synced value: the slot number on the discrete slider, a 0..1 level on the smooth one. Only your client writes it, so every client lands the knob in the same place.
- **The controls work only on a set-down panel that every copy has settled onto.** Carried, at home, or for a few seconds after a drop, the panel is **inert**: caps and knobs sink flush, both physbones are off, and a hand goes straight through them. Each other player's copy replays your drop through its own delayed view of your hands, so a press judged on your copy before theirs settles would land on a different cap than the one they see.
- The lamps are small glowing shapes on the one mesh, each raised through the face by its own blendshape: a dot per button, a dot per selector segment, and a segment per slot. The smooth slider's lamp is an always-lit strip from the track's low end to its knob.
- What crosses the network: the on/off switch, whether the panel has left its rest on the avatar, which handle is primary, the four button bools, the selector choice, the slot number, the level, and `object-sync`'s own switch and word (§Performance stats).

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
- Press a button cap down: its dot toggles the moment the cap passes most of its travel. A hand brushing across the caps toggles the first cap it pushes down.
- Press a selector segment near its middle: it sinks, stays sunk, and its dot lights. A press near the seam between two segments does nothing (§Traps).
- Grab a slider anywhere along its track, drag, and let go. The knob follows your hand, holds for a moment, then settles on the value you set: the middle of the slot on the discrete slider, exactly where you let go on the smooth one. One slider at a time: while you hold one, the other cannot be grabbed.
- **What a consumer reads.** All synced, not saved, written by the wearer's client alone:
  - `ControlPanel/Btn1` to `Btn4`: the button states, bools.
  - `ControlPanel/Select`: the selector's choice, an int counted from 0, so 0 is the first segment (the handle A end) and the panel starts with it chosen.
  - `ControlPanel/Slot`: the discrete slider's slot, an int from 0 at the track's low end (the handle A end).
  - `ControlPanel/Level`: the smooth slider, a float from 0 at the low end to 1 at the high end.
  - `ControlPanel/Detached`: true while the panel is away from home, carried or set down.
- VRCFury leaves these names unprefixed, so any controller on the avatar reads them by name. Declare them in your controller as animator floats with no expression-parameter entry of your own, or not at all: a second expression-parameter declaration takes the name over with its own sync and save flags (`gimmicks.md` §Packaging and interface). A button is a lasting on/off state, not a momentary pulse: read its level, or its change on your own copy. `Level` crosses the wire as a synced float, at half the resolution an int would give.

## Additional notes

- **One instance per avatar.** The menu control is a bare VRCFury `Toggle` and the published names carry no per-instance prefix, so two instances would share them; the entry's `object-sync` build also has one set of contact tags.
- **`ObjectSync/Enable` is shared and not on this panel's menu.** It is one parameter for every `object-sync` build on the avatar. This entry switches it on by default and never drives it, so another module's toggle that turns it off also stops this panel's word (§Traps).
- **There is no menu path to the controls.** `gimmicks.md` §Packaging and interface asks for every touch control to be reachable from the menu too, for desktop players and for testing; this entry ships none. A consumer that needs one adds menu controls to its own build.
- **In the editor the panel sits where it was authored, not at its home.** The constraints on `TwoHandProp/Body` ship switched off and the animator switches them on in play. Never enable or Activate the two constraints on the prefab root: they ship disabled at zero offsets and a VRCFury `ApplyDuringUpload` turns them on at build.
- **Do not rename anything inside the prefab.** The animations find their targets by path (§Traps).
- **A late joiner sees a set-down panel where it was left, or glides to it.** A panel at home shows at home. When the "away from home" bit arrives during the joiner's boot dwell, the panel stays hidden until the copy has the word, then appears there. A bit that lands after the dwell shows the panel at home first, then glides from home to the word (`grab-sync`'s accepted shape).
- **After a drop the controls stay inert for `bridge + settle + liveMargin` seconds** on your copy, then the caps and knobs rise. Another player's copy raises its own caps and knobs `liveMargin` earlier, so a player who presses the moment they see caps up can still be early by up to that margin plus their own frame-rate-dependent glide.
- **Lifting the panel cancels a slider grab.** The panel goes inert the moment a handle is grabbed, which switches the slider physbone off and breaks the grab on every client. The knob holds where the hand was, then lands on the value.

## Performance stats

The panel alone, read off a composition bake and the SDK's scan:

```c++
PhysBone Components:  4        (two handles, the button and selector chains, the sliders: Excellent's limit)
PhysBone Transforms:  26       (Buttons 17, Sliders 5, each handle 2; past Excellent's 16, so Good)
PhysBone Colliders:   0        (collision checks 0: no chain lists a collider; players' hands push the caps)
Contacts:             4 ranked (the two slider boxes and the two tip senders; 30 components in all, 26 local-only:
                                the 2 row senders, the 8 cap receivers, object-sync's 16)
Constraints:          23       (depth 9)
Skinned Meshes:       1        (3016 triangles, 25 bones, 14 blendshapes at the shipped 5 slots; 1 material)
FX Animator Layers:   20       (not a rank stat: the glue 1, the controls 4, object-sync's 14, the Toggle's 1)
Synced parameters:    59 bits  (not a rank stat: the controls 28, which are the buttons 4, Select 8, Slot 8,
                                Level 8; the switch, left-home and primary-handle bits 3; ObjectSync/Enable 1; the word 27)
```

The panel alone ranks Good, set by its physbone transforms, so an avatar wearing it is Good at best. Beside it, the avatar has room for one more skinned mesh, four more physbone components and 38 more physbone transforms before Medium. Its 4 ranked contacts are half of Excellent's 8. The 59 synced bits can push an avatar past VRChat's 256-bit budget, where VRCFury's Parameter Compressor starts compressing menu toggles; a consumer's own `object-sync` build adds its own word.

Each button or selector segment adds two physbone transforms, a local-only receiver and a blendshape. Each slot adds a blendshape. A slider adds two physbone transforms, two ranked contacts, a knob bone and 8 synced bits; the controls take at most one discrete slider, since its segment lamps carry no slider name.

## Knobs

Two generators carry the knobs: `controls/generate.py` for the controls, `generate.py` for the frame around them. Edit a generator's CONFIG, rerun it, and recompile the `built/` folders that generator feeds (§Changing it). Each row gives the direction and the relation; the value lives in the code. `controls/generate.py`'s `validate()` refuses a controls value that breaks a relation below; the frame's CONFIG has no such guard.

| Knob | What it does |
|---|---|
| `controls` (controls) | The four rows, in the panel frame, which the frame's mesh and `rig.json` read too. Exactly one `buttons` row and one `selector` row (cap centres along X, the row's Z; the selector adds `segmentWidth`), and at least one slider: `kind: slider` (discrete, `N` slots, `hysteresis`) or `kind: smooth`, each with a `name`, a track `x` from its low end to its high end, a `z` and its own contact `tag`. Refused where a row leaves the face, a row's caps overlap or touch, a row holds more than eight caps, or the two cap rows sit close enough in Z for a joint sphere or a row sender to reach the other row (the rows share one tag). Every change here rebuilds the mesh and `Panel.prefab` (§Changing it) |
| `N`, `hysteresis` (a discrete slider) | Slots, and how far past each slot boundary the knob must travel before the slot changes, as a fraction of the track. `N` sets the stamp states, the segment lamps and the mesh's segment blendshapes together, so a change rebuilds the mesh and `Panel.prefab`. Refused outside 2..255, the synced int's range, and wherever `hysteresis` is half a slot or more. Wider hysteresis resists flicker at a boundary and makes the boundary feel sticky |
| `segmentWidth` (the selector row) | Each segment's extent along X; its depth is the caps' `capDiameter`. Wider segments shrink the seams and widen each segment's dead edges, because the press sphere's reach does not grow with it (§Traps). Refused where the seam between segments closes |
| `caps` (controls) | The joint both cap rows share: the cluster root's height, the crown `capTop` and `capDiameter`, the chain `radius`, the visible `travel` (crown to flush), the total `squish` the chain allows, and the bone length. Each bone's tip rests one chain radius under its crown, so the joint sphere is the press surface: a larger radius widens what a finger can land on and deepens the point where a hard press inverts (§Traps), and is refused for the button row where the sphere would reach the neighbouring cap at face level. Squish past the travel is how far the cap sinks into its well before it sits still. Changing any of these rebuilds the mesh and `Panel.prefab` |
| `press`, `release` (controls) | Press depth, as fractions of `travel`, at which a press is accepted, and below which every cap in both rows must rise before the next. Raising `press` demands a deeper press. Refused unless `release` is below `press` |
| `arm` (controls) | Seconds a press must stay past `press` before it counts; 0, the shipped value, stamps the frame the depth is crossed and emits no dwell state, because a delay before the stamp adds to every other player's wire and IK delay where a guard after it costs them nothing. Above 0 it rejects a brush that clears the cap within it, at that much latency on every press. A wider chain radius lengthens the time a face-level brush spends pressing, so the two are tuned together. Refused at or above `cooldown` |
| `cooldown` (controls) | Seconds from a release to the next accepted press: the floor between two toggles of one button. Refused at or under the wire's set-and-clear floor, below which two quick toggles can cancel on the wire (`gimmicks.md` §State machine patterns, the driver-copy edge detector) |
| `boxMargin`, `boxWidth`, `senderRadius` (controls, top level) | The cap receivers: each box is the squish plus the sender's diameter plus this margin deep, so the sender stays inside it over the whole squish, because a face-mode box reads 0 once the sender passes either face; the box's width; the row sender's radius. The press thresholds are emitted over that depth. Refused when neighbouring boxes overlap |
| `sliders.y`, `sliders.radius` (controls) | The chains' height above the panel bone, which is also the slider box's vertical centre, and the chain radius: the capsule along the bone is the grab surface, so a larger radius takes a grab from further off the track |
| `sliders.boxMargin`, `sliders.senderRadius` (controls) | How far the slider box reaches past each track end, and the tip sender's radius. The margin sets the low end's squish limit (half a margin past the low end) and the **floor**, the reading half a margin past the high end, below which the reading counts as a release. Refused where the sender's radius reaches half the margin, because the tip at the squish limit would then straddle the box's full-reading face |
| `sliders.restOffset` (controls) | How far past the box's zero-reading face the tip rests, and with it the bone length. Refused unless the resting tip's sphere is wholly outside the box: a resting tip inside reads above 0 and would hold every client in its held state for ever |
| `sliders.boxHeight`, `sliders.boxAcross` (controls) | The slider box's extent through the face and across the track, centred on the track. A taller box reads a grab further above or below the face (the chain's stretch limit is derived to reach it); a wider one reads a hand further off the track. Contact size limit 6 m |
| `sliders.knobY`, `sliders.channelDepth` (controls) | The knob bone's rest height, and the depth of the knob's channel, which is also how far inert sinks the knob. A channel change rebuilds the mesh |
| `sliders.settle` [EMPIRICAL] (controls) | Seconds the knob holds where the hand let go before it lands on the synced value: the wire and IK delay between the grabber's release and the wearer's last stamp arriving. Shorter lands sooner and risks a remote's knob landing on the value before the last stamp, then jumping. Not the frame's `settle`, below |
| `retractTime` (controls) | Seconds the caps and knobs take to sink flush or rise when the controls go inert or live |
| `selectorKeep` [EMPIRICAL] (controls) | The fraction of the selector segments' glide position kept each frame as they move to a new choice: higher glides slower, 0 snaps. Per frame, so the glide takes longer in seconds at a lower frame rate. Refused outside [0, 1), since at 1 nothing moves |
| `mountPath`, `armature`, `mesh` (controls) | `mountPath` is where the `Panel` instance hangs, from the GameObject carrying the FullController; `armature` and `mesh` are the node names inside it. The lamp and knob animations bind through all three. A consumer mounting the controls elsewhere regenerates with its own `mountPath` |
| `prefix`, `internal`, `tag` (controls) | The published prefix, the internal prefix (never under the published one), and the cap rows' private contact tag; each slider's tag is its row's `tag`, distinct from it and from each other. `Panel.prefab`'s receivers, senders and tags are set to match by hand; `--check` compares them |
| `rigSeed` (frame) | The `object-sync` build's contact tags and park position, which move together. Unique among the avatar's `object-sync` builds |
| `bridge` (frame) | Seconds another player's copy holds its own replay of a release before it trusts the word: two word refreshes, Park's glide and a margin. Re-derive it, as its CONFIG comment gives, whenever the `object-sync` build's batch count or `syncDamp` changes |
| `acquire`, `resumeGrab` (frame) | Seconds a late joiner stays hidden while it settles onto the word, and seconds the panel stays hidden while a grab taken during a resume settles. Each covers a slow client's few frames with margin |
| `settle`, `liveMargin` (frame) | `settle` is another player's copy's inert wait after it starts gliding onto the word, sized to the glide closing a hand's worth of replay error to a millimetre at a low frame rate; `liveMargin` covers the wire's delay between your release and their copy seeing it. Your copy's controls go live `bridge + settle + liveMargin` after a drop. Shorter makes the panel usable sooner and risks a press landing on the wrong cap for a player whose copy has not settled |
| `tilt` (frame) | Degrees the face is mounted about the handle axis; negative tips it toward the holder's side when handle A is in the left hand. The carry keeps the panel level side to side, so this is its only resting tilt, at home included. `--check` holds the `Panel` instance's rotation to it |
| `syncDamp` (frame) | How fast another player's copy glides from its replayed rest onto the word, per frame. Higher steps visibly; lower glides past one word refresh, so steps stack into a trailing lag. Frame-rate dependent (`spring-damping` README §Framerate dependence) |
| `handleSpacing` (frame) | The distance between the handles, set on every copy site `two-hand-prop` README §Knobs lists that this prefab keeps; `--check` holds each. Wider lengthens `two-hand-prop`'s handoff slide. The mesh's grips (`grips` in the frame's geometry) must sit at the handles, so a change rebuilds the mesh |
| Lamp sizes (frame: `buttonLamps`, `segments`, `knob`) | `buttonLamps` places the button dots and sets their diameter; each selector segment takes the same dot at the same offset. `segments` sets a discrete slider's segment row (its offset from the track, its depth, and each lamp's width as a fraction of a slot); the smooth slider's strip sits in the same row geometry. `knob` is the knob's footprint. Each rebuilds the mesh only |
| Panel geometry (frame: `plate`, `grips`, `lamps`, `strip`) | The rest of the mesh-only layout, emitted into `rig.json` for the Blender build beside the rows read from the controls CONFIG. `plate`'s width must equal the controls CONFIG's `face`, and the frame generator refuses a mismatch; `plate.bottom` must leave room under a chosen selector segment pressed to its squish limit, which the mesh builder asserts. `strip.swatch` is the strip's atlas colour, refused without emission |
| Home rest (`TwoHandProp/HomeAnchor/Offset`, prefab) | Where the panel rests on the avatar when not in use |
| Enable default (the glue `controller.yaml`'s declaration and the `Toggle`'s default) | Written in both, which must agree; `--check` compares the Toggle's default to the glue's declaration |

The press thresholds, `arm`, `cooldown`, the cap layout, `segmentWidth`, `sliders.settle`, `selectorKeep`, the lamp sizes and `syncDamp` are feel constants: the emulator measures what they do, only a headset shows whether they feel right.

**Provenance:** the carry, the two-handle arbitration and the handoff are `two-hand-prop`'s, which takes its grab cell, drop and late-join park from `grab-prop` (VRLabs World-Constraint ancestry) and its self-source damper from `spring-damping` (VRLabs Damping-Constraints, MIT). The placement is `object-sync`'s word (VRLabs Custom-Object-Sync ancestry) carried over `word-channel` (VRCFury Parameter Compressor ancestry), arbitrated against the cell in `compositions/grab-sync`'s shape, with the full-rotation word as `compositions/grip-sync` uses it; the nested sync build at its own CONFIG is `leash-stake`'s shape. The button machine's ladder, hold and cooldown are `zone-touch`'s. The Park repoint, the squish buttons and selector with their self-sensing readout, the grab-surface sliders with the knob memory in the lamp tree, and the blendshape lamps are this entry's own.

## Design notes

The state-by-state walk lives in three places: `generate.py`'s module docstring for the frame's construction and its clip table, the header of `controller.yaml` (the glue) for every frame decision the graph cannot show, and `controls/generate.py`'s docstring for the controls' nodes, layers and slider geometry. This section states what the rig guarantees and why.

**Park is a repoint, not an added source.** One new node, **Park**, holds where `two-hand-prop` thinks home is: the home rest, the word, or a glide between them, by its constraint weights. `two-hand-prop`'s prop node `Body` reads Park in the source slot where it read `HomeAnchor/Offset`, because an added source on `two-hand-prop`'s constraints can reorder its release frame with every animation unchanged (`two-hand-prop` README §Traps). Park belongs to this entry, so its own sources, `Body` among them, are outside that rule.

**Another player's copy glides from its own replay onto the word.** Each copy replays the carry from the grabs it saw, through its own view of the grabber's hand, so its release lands near the wearer's but not on it. Snapping onto the word would jump the panel by that error on every release, so the copy holds its replay for `bridge` and Park then glides it onto the word.

**A late joiner sees a set-down panel at the synced spot**, not hidden until a grab is witnessed: a joiner has to see a panel to walk up to it, by a hidden flush when the bit beats the boot dwell and by a visible glide from home when it does not. This is a design lean, not a measured necessity.

**A re-grab from the synced spot needs no settle state.** The one-hand carry freezes the panel's rotation where it stands, which on a copy at rest is the word's, so the carry starts from the word by construction; `compositions/grab-sync`'s `Reacquire` dwell exists for a sampled cell this frame does not have.

**The caps press by squish.** With the angle limit at zero, a cap moves only straight down, and the bone end moves along the bone without scaling or turning, so the caps travel rigidly and the receivers ride the bone ends. Every button and selector chain sits under one physbone component, so both rows cost one component.

**The cap readout senses the panel, not the hand.** A receiver reading a stranger's hand would depend on which senders their avatar carries and on join order, since a receiver that loads after a player joined may not sense them (`runtime.md` §Contacts). The cap's receiver against the panel's own sender reads depth from geometry alone, and local-only costs nothing against the rank.

**A press is a lasting synced value, never a pulse.** A pulse sent while another player's client has your animator paused is lost; a level arrives on the next update. Only your client writes it, so every client agrees on one reading. One shared hold state waits for every cap in both rows to rise, so a finger resting across two caps cannot fire the second.

**The sliders read the tip only while held.** A released physbone's resting place is each client's own, so nothing reads the chain after a release: the synced value is the truth, and every client draws the knob from it. While held, the tip sits on the hand point, and the face-mode box reads its track position exactly, with the hand above or below the face. The chain has no angle limit because a limit of zero does not project the hand onto the track: the tip sits on the track at the hand's distance from the root, over-reading by about h²/2d for a hand h off the face at distance d from the root.

**The slider contacts are non-local; the cap contacts are local-only.** A remote sees the grabber's hand live, so every client reads the slider box itself and its knob follows the hand under it; that costs four ranked contacts. A cap press needs no such echo: the lamp follows the synced value a tick later, and the caps' readout stays off the rank.

**One physbone component holds both sliders, so one slider is grabbable at a time.** A grab is per component, so a second hand on the other slider gets nothing. The alternative, a component per slider, would cost a fifth physbone component, past Excellent's limit of four.

**The knob memory lives in the lamp tree.** The knob is drawn on every client from the reading while held and from the synced value after the settle, so every copy lands it in the same place while only the wearer writes the value. The `Sliders` layer only says whether a slider is held or settling (`CP/Settling`); the walk is `controls/generate.py`'s docstring.

**The slider box faces its zero side to the tip's rest.** A sender leaving a face-mode box through its +Z face reads full for one contact step before 0; one leaving through the −Z face reads 0 directly. A release springs the tip out past the high end, so the −Z face sits there and a release stamps nothing. The reading therefore falls as the knob rises.

**There is no offline lamp.** Another player's copy goes live only once it has settled on the word, so a copy that has not received the word already shows its caps and knobs sunk and dead. That is the whole signal, and the controls read nothing of `object-sync`'s.

**The slider chains do not collide.** A grab bone that collides is shoved by the reaching hand, the rule `two-hand-prop`'s handles already follow.

**Lamps are blendshapes on the one mesh.** Raising a parked shape through the face keeps the whole panel at one mesh and one material slot with no custom shader, which keeps it portable and maintainable. The smooth slider's strip needs no shape: its far end is skinned to the knob bone.

**The controls are their own sub-entry.** `controls/` carries its own generator, controller and prefab so a consumer lifts exactly that folder, plus the model it skins.

## Traps

- **Never add a source to `two-hand-prop`'s constraints**, even at weight 0; repoint one. Park's sources are this entry's to change, and a change re-measures the release frame (§Verifying the install).
- **`ObjectSync/Enable`'s default is decided by declaration order, inside this FullController and across the avatar.** Inside, the glue declares it on and the `object-sync` build declares it off, so the `object-sync` controller and its parameters must stay after the glue's, in both lists; `--check` pins the order. Across the avatar, a consumer's separate `object-sync` build declaring it off can bake it off for every build (`object-sync` README §Ground truth, its Seam bullet). Either way the panel stops sharing its rest: another player's copy holds its own replay of the drop with the controls sunk for good, and a late joiner never shows a set-down panel. Arm the consumer's build too, or check the baked default.
- **The lamp and knob animations are path-bound.** They address the mesh and the knob bones through `mountPath`. Moving `Panel`, or renaming anything in it, leaves the lamps dark and the knobs parked with no error while the presses and the published values still work.
- **Posing stays off on the slider chain.** A posed tip left inside a slider box reads above the floor on every client, and holds every client in that slider's held state for ever.
- **Overshoot past the high end releases.** Drag past the low end and the tip stops at the squish limit, still reading the low end's value. Drag past the high end and the reading falls under the floor, which counts as a release: the knob holds and lands on the last value stamped. A hand dragged behind the chain's root can read full for a step, which maps to the low end's own value.
- **A hand near a slider chain's root end blocks the other slider.** A grab within about 20 to 40 mm of the root end, beyond the low end of the track, takes the panel's one slider grab with nothing read. The other slider cannot be grabbed until that hand lets go.
- **A chosen selector segment is pressed above where it looks.** The chosen segment rests sunk by `travel`, but its press sphere stays at the unsunk height, so a finger meets it `travel` above its visible top.
- **Each selector segment has dead edges.** A press counts only within the joint sphere's reach at face level from a segment's centre, `sqrt(2 · radius · travel − travel²)` plus the presser's own radius; nearer a seam both segments dip and neither stamps. The selector's segments are wider than the joint sphere's reach, which is why `validate()` lets the selector row through the reach refusal it holds the button row to.
- **Every `Sliders` state writes `CP/Settling`, `Idle` included.** On this rig, in the emulator, a write-defaults-on state playing a single clip reverted an AAP that clip did not write to its default on entry. So no state here relies on holding a value it does not write; a new state in this layer writes `CP/Settling` too.
- **A hard press can pop through.** When the presser's collider centre drops below a cap's resting tip, the solver pushes the tip the other way, it snaps back to rest, and the reading falls to 0 mid-press. The threshold is the tip's rest height, not how far it has squished, so only the seat depth moves it: the tip sits one chain radius under the crown. The same radius is how far off centre a finger still moves a cap, so a wider one also dips the neighbours.
- **A sideways brush at face height counts as a press.** With `arm` at 0 any brush that pushes a cap past `press` toggles it, and since the hold and cooldown are shared across both rows, a brush across several caps toggles only the first; `arm` above 0 rejects a brush that clears the cap within it.
- **One cap resting down blocks every cap.** The shared hold state waits for every reading in both rows to fall below `release`, so a cap held down, or an object resting on it, stops every other button and segment from firing.
- **`Panel.prefab` does not follow the FBX.** The model is unpacked inside it, because an FBX prefab variant serializes no bone names for a binding or `--check` to address, so a re-export that moves a bone or changes a blendshape reaches nothing until the prefab is rebuilt (§Changing it). `controls/generate.py --check` fails on a moved bone's rest pose first.

## What is not proven here

The emulator has run the composed prefab: presses, the selector, both sliders under a scripted grab (the reading, the stamps, the knob memory, overshoot, the one-grab rule), inert while held, a clone's lamps and knobs, a late joiner, and the cull path on both a set-down and a carried panel. Not reached in the emulator:

- **A remote's held and settle branches.** A live grab never reaches a clone, so a remote's knob following the grabber's hand, and its hold at release, are unwatched.
- **A remote handoff and two-hand turn**, for the same reason.
- **A mirror clone**, which has not been watched.
- **The release-frame lag with the controls nested under `Display`**, which touches no constraint and has not been read.

Everything below needs the shipping client:

- **The slider on a remote**: whether its knob tracks the grabber's hand, and whether `sliders.settle` covers the wire and IK delay so the knob lands without a jump.
- **The look and feel:** the lamp sizes, the double sink of a chosen selector segment pressed again, and how the selector's dead edges feel to a real finger.
- **A stranger's real hand on the caps:** press depth, brush rejection, a double press across neighbouring caps, cap size against real hand colliders (which vary per avatar), and the feel of the round trip to the lamp.
- **The press thresholds against the client's receiver refresh**, which can skip frames the emulator never skips, so a light tap that crosses `press` for a frame or two may go unseen.
- **Join order:** you joining after the presser and the press still reading, which the self-sensing readout is built to guarantee.
- **The handles under delayed remote hands**, the size of each client's replay drift, and a release into `bridge` after a grab the copy saw.

## Changing it

- **Regenerate the frame as a unit.** Run `python control-panel/generate.py` from the repo root; it rewrites the glue's clip table from `two-hand-prop`'s current animations, `object-sync/controller.yaml` and `rig.json`. Recompile `built/` and `object-sync/built/` over their committed `.meta`s, addressing both paths as `Packages/com.ryan6vrc.patterns/control-panel/…` (`CONVENTIONS.md` §The gate). A retune of `two-hand-prop` reaches this entry only through that run.
- **Regenerate the controls.** Run `python control-panel/controls/generate.py`, then recompile `controls/built/` the same way. The frame's `rig.json` reads the controls CONFIG, so run the frame generator after it too.
- **Run both checks after any prefab edit**: `python control-panel/generate.py --check` for `ControlPanel.prefab`, `python control-panel/controls/generate.py --check` for `Panel.prefab`. Nothing runs them for you.
- **Edit the prefabs in place.** There is no builder: load the prefab's contents, edit, save. A save that recreates a GameObject re-mints its file IDs, so judge an edit by `--check`, not by the size of the diff.

**Changing the rows, `caps` or the slider geometry** moves the mesh:

1. Set the controls CONFIG (the layout the frame reads from it); touch the frame CONFIG only for mesh-only geometry. Regenerate both.
2. Rebuild the mesh with `assets/ControlPanel_build.py` from `rig.json` (its docstring has the command) and export it with `assets/ControlPanel_export.py` over `assets/ControlPanel.fbx`, so its `.meta` and material remap hold.
3. Rebuild `Panel.prefab` over its existing asset, so `ControlPanel.prefab`'s nested reference holds: instantiate the FBX, unpack it completely, rename the root `Panel`, add the two physbones, the cap receivers, the slider box receivers and the four senders with the values `rig()` in `controls/generate.py` emits, and save.
4. Recompile, and run both checks. A rebuilt `Panel.prefab` can drop the nested instance's `Panel` name or tilt override in `ControlPanel.prefab`; the frame's `--check` names it, and you re-apply it.

**Lifting the controls into your own build:**

1. Copy `controls/` and the assets `Panel.prefab` uses from `assets/` (`ControlPanel.fbx`, `ControlPanel.mat`, the two atlas PNGs). Re-GUID every copied `.meta` that would collide with this entry's, `built/` included, and repoint the copy (`CONVENTIONS.md` §An entry is a folder).
2. Set `mountPath` to where your `Panel` instance hangs below your FullController's GameObject; on an avatar that also carries `ControlPanel.prefab`, change `prefix`, `internal`, `tag` and each slider's `tag` too. Regenerate and recompile.
3. Add the controls controller and its parameters to your FullController, and `<prefix>/*` to its `globalParams`.
4. Write `<internal>/Live` (a float the controls declare at 0) from your own controller: 1 where the controls may be used, 0 elsewhere. At 0 the caps and knobs stay sunk and both chains off, so without a writer the controls are dead. The entry's glue writes it 1 only once every copy has settled onto the word.

The controls read nothing of `object-sync`'s, so they need no sync build beside them.

## Verifying the install

Run both `--check`s first (§Changing it); they catch the hand-maintained prefab surface and nothing below. In the emulator, enter play only after a forced script reload once anything was compiled or saved, or the constraints can register without running; read `Body` against `HomeAnchor/Offset` right after entry before trusting anything else. The emulator's parameter list does not show AAPs (`CP/Live`, `CP/Settling`, the knob memories): read the physbones' `enabled`, the `Controls_Retract` weight and the knob bones' positions instead.

Enable on, in play: the panel rests at `HomeAnchor/Offset` on the hips. At the avatar root's origin instead, the BoneProxy never resolved. A menu toggle that does nothing means the enable came out of the build prefixed, or another declaration on the avatar captured `ControlPanel/Enable`; read the built name (`gimmicks.md` §Packaging and interface).

Carry it and let go: it stays in the world. A panel that drifts with the avatar after release means the root pin's `ApplyDuringUpload` never fired. A drop that springs back to where the grab began means the release frame is being read live: a source was added to a `two-hand-prop` constraint, or a carry node left `Body` (`two-hand-prop` README §Traps). The release is only trustworthy driven from `Update()` (`emulator.md` §Induce a physbone grab/pose).

Set the panel down and wait: the caps and knobs rise `bridge + settle + liveMargin` later on your copy and a clone's `liveMargin` sooner, and before then a scripted collider passes through them without a reading.

Press a cap with a scripted collider: `CP/Press<i>` rises with depth, the button's bool flips the frame the reading passes the press threshold (or after `arm`, when it is set), and its dot rises. A press on a selector segment sets `ControlPanel/Select` and sinks and lights that segment. The collider reaches the solver only once it is in the `Buttons` physbone's `colliders` list and the physbone component has been cycled; never cycle the `Buttons` GameObject, which re-registers the receivers with the sender already inside them and leaves every reading at 0 for the session. A press that never stamps has three causes: a reading stuck at 0 (the receiver left its bone end, or its tag differs from the sender's), a reading that never reaches `press` (the press popped through), or another cap resting down. A stamp with a dark lamp means the lamp animations no longer find the mesh (§Traps). Only your own copy stamps; a clone never does.

Grab a slider with the tip placed on the hand point and sweep it: `CP/<name>_Read` falls as the knob rises, `ControlPanel/Slot` steps as the knob crosses each boundary and the lit segment follows, `ControlPanel/Level` follows within a frame, and the knob bone tracks the hand. Let go: the knob holds for `sliders.settle`, then lands on the slot's centre or the level. While one slider is held, `AttemptGrab` on the other returns nothing. Discriminators:

- Caps and knobs sunk and both chains off on a set-down panel: nothing writes `CP/Live` 1, so the glue never reached `Placed` (or, in a lifted build, your controller does not write it).
- The knob runs opposite to the hand and every release stamps slot 0: the slider box faces the wrong way (`controls/generate.py --check` names its rotation).
- A knob that never leaves its held state: the resting tip sits inside its box.
- A reading stuck at 0 under a held tip: the tip sender's tag differs from its box's.
- A knob that never moves while the value steps: the knob animations no longer find the knob bone (§Traps).

Spawn a non-local clone (`emulator.md` §Remote clone) and set the published values by hand: its lamps follow the bools, the choice and the slot, and its knobs land on the slot's centre and the level, a sync tick later. Lift the panel while a slider is held: the slider leaves its held state, holds the hand's value, then lands, and the knobs sink.

## Rig

The prefabs are the shipped artifacts; `generate.py`'s docstring is the construction record of `ControlPanel.prefab`, and `controls/generate.py`'s of `Panel.prefab`.

    ControlPanel                 root: parent + scale constraint → object-sync's World.prefab, disabled, zero
                                 offsets, switched on at build by a VRCFury ApplyDuringUpload; the bare
                                 Toggle `Control Panel`; the FullController playing glue, controls, object-sync
    ├─ TwoHandProp               nested two-hand-prop/TwoHandProp_Full.prefab: its FullController, Toggle,
    │                            FreezeToWorld and placeholder meshes removed; handles respaced
    │  ├─ Body                   the prop: its home source repointed to Park (§Design notes)
    │  │  ├─ Display             shown and hidden by the animations
    │  │  │  └─ Panel            nested controls/Panel.prefab, tilted about X: the lift unit
    │  │  │     ├─ Armature/Panel        the panel bone: two local-only capsule senders, one under each cap row,
    │  │  │     │                        and the two non-local slider box receivers CP/Slot_Read, CP/Level_Read
    │  │  │     │  ├─ Buttons            one VRCPhysBone over both cap rows: squish only, collision on
    │  │  │     │  │  ├─ Btn<i>/Btn<i>_End   a button chain; the cap skins to the end, which carries the
    │  │  │     │  │  │                      local-only face-mode receiver CP/Press<i>
    │  │  │     │  │  └─ Sel<k>/Sel<k>_End   a selector chain; receiver CP/SelPress<k>
    │  │  │     │  ├─ Sliders            one VRCPhysBone over both slider chains: grab only, no angle limit
    │  │  │     │  │  └─ Sld_<name>/Sld_<name>_End   the end carries the non-local tip sender ControlPanel<name>
    │  │  │     │  └─ Knob_<name>        in no chain; the knob skins to it, the lamp tree writes its position
    │  │  │     └─ ControlPanel        the one skinned mesh: the lamp blendshapes and Controls_Retract, the
    │  │  │                            Level strip skinned from Panel to Knob_Level, one material
    │  │  └─ CarryA, CarryB, AimNode, RestA, RestB   two-hand-prop's carry nodes
    │  ├─ HolderA, HolderB       the invisible grab handles
    │  └─ HomeAnchor             MA BoneProxy → Hips
    │     └─ Offset              the home rest
    ├─ HomeLevel                 rotation constraint on HomeAnchor/Offset, Y only: the home rest's heading
    │                            without the hips' lean
    ├─ Park                      position + rotation constraint over [HomeAnchor/Offset (HomeLevel for the
    │                            rotation), ObjectSync/Sync, Park itself, Body]; the glue animates the weights
    └─ ObjectSync                nested object-sync/ObjectSync.prefab (one object, full rotation): its
                                 FullController, Toggles, ApplyDuringUpload and pin removed; re-parked and
                                 retagged to rigSeed; Sync_Target ← Body, so the wearer measures the panel
