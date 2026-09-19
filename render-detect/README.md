# render-detect — is this region on this client's screen? (Module)

`RenderDetect/IsRendering` is true on a client while any camera there renders the `Bounds` box, and false while none does. Each client answers for itself, at 0 synced bits. Build on it for anything that should change only when nobody is looking, or should stop costing anything while unseen. This entry holds the one child `Animator` sanctioned on an avatar (`docs/gimmicks.md` §Packaging owns the rule); §The exception's boundary is what keeps it the only one.

**Provenance:** the mechanism is VRLabs' [IsRendering-Detection](https://github.com/VRLabs/IsRendering-Detection) (MIT, © 2023 VRLabs LLC; contributors hfcRed and Dreadrith). This entry re-authors its FX side as `controller.yaml`, seats it on a VRCFury `FullController`, and drops the source's debounce layer and demo containers.

## How it works

Culling is the measurement. `Sensor` carries an `Animator` in `CullCompletely`, and Unity stops such an Animator on any frame where no camera renders a renderer beneath it. `Bounds` is a SkinnedMeshRenderer with no mesh and no material: it never draws anything, but its `localBounds` still take part in culling, so that box is the region being watched. The avatar's own FX cannot observe this, which is why a second Animator is the instrument rather than a convenience.

Two writers share one flag. Each frame it runs, the sensor's one-state controller (`assets/`) turns `Heartbeat` on, and each frame the FX layer turns it off, so the heartbeat is on only while the sensor is running. `Receiver` (`allowSelf`, `localOnly: 0`) turns the heartbeat into the parameter on every copy of the avatar.

## The exception's boundary

A child Animator falls under this exception only while all of these hold:

- it is set to `CullCompletely`, with the watched renderer beneath it;
- its controller has one state and one clip, and no parameters;
- that clip's only write is the heartbeat FX reads back;
- everything keyed on the result lives in FX;
- its GameObject carries no VRCFury component and no MA Merge Animator.

An Animator set to `AlwaysAnimate`, or one whose clip moves or shows anything a viewer sees, is not this exception whatever else it does.

## Traps

- **Evaluation order is load-bearing.** The sensor's "on" must land after FX's "off" in the same frame, which holds only where the avatar's FX is applied before regular Animators. A controller-driven parent does that, and so does a playable graph stepped before the animation phase. Av3Emulator does not: it runs FX through a script-created graph in GameTime mode, which evaluates after regular Animators, so FX's write always wins there and `IsRendering` reads false in the emulator whatever the camera sees. That the VRChat client orders them correctly rests on the source's in-client record; this entry has not established it.
- **Nothing in the merged controller may bind the Sensor Animator.** VRCFury lifts child Animators off the avatar before it merges this controller, restores them afterwards, and drops every binding that resolves to nothing in between. The source enables its sensor from FX; under VRCFury that binding vanishes, so the sensor ships enabled. VRCFury also deletes, as junk, any child Animator whose GameObject carries a VRCFury component, and MA's `deleteAttachedAnimator` does the same on a Merge Animator's GameObject. Both are silent, which is what the last boundary item guards.
- **One instance per avatar.** VRCFury does not rewrite contact tags, so a second instance's heartbeat lights the first instance's receiver. The output is published bare through `globalParams: [RenderDetect/*]`.
- **The Scene view is a camera.** In the editor it culls the sensor in like any other camera, so point it away before reading the negative branch.
- **Cost:** one more Animator against `animatorCount` (`docs/optimization.md`), one sender, one receiver, one renderer. AAO keeps the rig, since it treats every renderer and every controller-carrying Animator as an entry point. d4rk keeps it too: it won't merge a renderer that has no mesh, and it excludes a sub-animator's whole subtree from merging.

## Knobs

`Bounds` is the watched region: its `localBounds` set the size and its transform sets the placement. Move `Bounds`, never `Heartbeat` or `Receiver`, which must stay overlapping.

## Verifying the install

A bake (`OnPreprocessAvatar`) should show `Sensor` with its Animator enabled, still set to `CullCompletely`, and still holding its controller, while `Receiver` writes the bare `RenderDetect/IsRendering`. In the emulator, a scratch sender tagged `RenderDetect` on `Receiver` should drive the parameter true, which proves the receiver and the naming; the camera-driven true branch cannot appear there (§Traps). To prove the race, host `built/RenderDetect_Fx.controller` on a plain parent Animator with the sensor beneath it in play mode: the heartbeat should follow the camera onto and off the box. The in-client check is to look at the box and away from it.
