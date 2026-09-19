# render-detect — is this region on this client's screen? (Module)

`RenderDetect/IsRendering` is true on a client while any camera there renders the `Bounds` box, and false while none does. Each client answers for itself, at 0 synced bits. Build on it for anything that should change only when nobody is looking, or should stop costing anything while unseen. For viewers other than the wearer, the false branch reaches FX only while the avatar's animator is still running for them: compose `anti-cull` alongside (§Traps). This entry's mechanism is the one sanctioned child `Animator` on an avatar (`docs/gimmicks.md` §Packaging owns the rule); §The exception's boundary is what keeps it the only one.

**Provenance:** the mechanism is VRLabs' [IsRendering-Detection](https://github.com/VRLabs/IsRendering-Detection) (MIT, © 2023 VRLabs LLC; contributors hfcRed and Dreadrith). This entry re-authors the FX side as `controller.yaml`, seats it on a VRCFury `FullController`, and drops the source's demo containers along with the debounce layer that drove them. It also deviates from the source's prefab in four ways:
- the sensor ships enabled rather than being enabled from FX (§Traps says why);
- `Bounds` carries no material slot, where the source has one empty slot;
- the heartbeat is inactive at rest;
- the contacts are smaller.

That a zero-slot mesh-less renderer still counts as rendered is established in the editor, not in the client.

## How it works

Culling is the measurement. `Sensor` carries an `Animator` in `CullCompletely`, and Unity stops such an Animator on any frame where no camera renders a renderer beneath it. `Bounds` is a SkinnedMeshRenderer with no mesh: it never draws anything, but its `localBounds` still take part in culling, so that box is the region being watched. The avatar's own FX cannot observe this, which is why a second Animator is the instrument rather than a convenience.

Two writers share one flag. Each frame it runs, the sensor's one-state controller (`assets/`) turns `Heartbeat` on, and each frame the FX layer turns it off, so the heartbeat is on only while the sensor is running. `Receiver` turns the heartbeat into the parameter on every copy of the avatar, so each client reports its own view.

## The exception's boundary

A child Animator falls under this exception only while all of these hold:

- it is set to `CullCompletely`, with the watched renderer beneath it;
- its controller has one state and one clip, and no parameters;
- that clip's only write is the heartbeat, which FX also writes off every frame;
- nothing binds the Animator itself, and everything keyed on the result lives in FX;
- its GameObject carries no VRCFury component and no MA Merge Animator.

An Animator set to `AlwaysAnimate`, or one whose clip moves or shows anything a viewer sees, is not this exception whatever else it does. The exception is the mechanism, not a count: a second watched region would be a second sensor on its own contact tag, which this entry does not ship.

## Traps

- **Remote viewers need the avatar's animator running.** `Bounds` is one of the avatar's own renderers. When it leaves a remote viewer's screen along with the rest of the avatar, that viewer's copy is view-culled (`docs/runtime.md` §Culling): FX pauses with the sensor, nothing writes the heartbeat off, and `IsRendering` holds true. The false branch therefore fires for another player only while some other part of the avatar stays on their screen. The wearer's own copy never pauses, so the wearer's view works regardless. Compose `vrc-patterns/anti-cull` to keep FX running for every viewer. Its bounds belong to the avatar, not to the sensor, so it must not be placed under `Sensor`.
- **Evaluation order is load-bearing.** The sensor's "on" must land after FX's "off" in the same frame, which holds only where the avatar's FX is applied before regular Animators. A controller-driven parent does that, and so does a playable graph stepped before the animation phase. Av3Emulator inverts it (`docs/emulator.md` owns the ordering), so `IsRendering` reads false in the emulator whatever the camera sees. That the VRChat client orders them correctly rests on the source's in-client record; this entry has not established it.
- **The output is raw; debounce it where you consume it.** `IsRendering` flips on the frame the sensor starts or stops. The heartbeat starts inactive and the sensor counts as visible only after a render, so a brief false right after load is expected. That is inferred from the mechanism, not measured. A consumer that acts on false should hold its reaction behind a short dwell, or an "only when unseen" change can fire on spawn in plain view. The source's dropped four-state layer debounced only its demo containers; the parameter it tells consumers to read was raw there too.
- **Nothing in the merged controller may bind the Sensor Animator.** VRCFury lifts child Animators off the avatar before it merges this controller, restores them afterwards, and drops the bindings it merged that resolve to nothing in between. The source enables its sensor from FX; under VRCFury that binding vanishes, so the sensor ships enabled.
  - VRCFury also deletes, as junk, any child Animator whose GameObject carries a VRCFury component.
  - An MA Merge Animator with `deleteAttachedAnimator` set deletes the Animator on its own GameObject.
  - Both happen silently, which is what the last boundary item guards.
- **One instance per avatar.** VRCFury does not rewrite contact tags, so a second instance's heartbeat lights the first instance's receiver. The output is published bare through the FullController's `globalParams`.
- **The Scene view is a camera.** In the editor it culls the sensor in like any other camera, so point it away before reading the negative branch.
- **Cost:** one more Animator against `animatorCount` (`docs/optimization.md`), plus one sender, one receiver and one renderer. AAO keeps the sensor Animator because it carries a controller. d4rk won't merge a renderer that has no mesh.

## Knobs

`Bounds` is the watched region: its `localBounds` set the size and its transform sets the placement. Keep those bounds non-zero, because AAO strips a mesh-less renderer whose bounds are empty, and the sensor then watches nothing. Move `Bounds`, never `Heartbeat` or `Receiver`, which must stay overlapping. d4rk excludes from merging only what the sensor's clip animates, so a real mesh placed under `Sensor` to be watched can be merged into the body and stop being beneath the sensor.

## Verifying the install

**Bake (`OnPreprocessAvatar`).** `Sensor` should keep its Animator enabled, set to `CullCompletely` and holding its controller, and `Receiver` should write the bare `RenderDetect/IsRendering`.

**Emulator.** A scratch sender tagged `RenderDetect` on `Receiver` should drive the parameter true. That proves the receiver and the naming; the camera-driven true branch cannot appear there (§Traps).

**The race.** In play mode, put a plain Animator carrying `built/RenderDetect_Fx.controller` on the prefab root, since clip paths are root-relative. The heartbeat should follow a camera onto and off the box.
- The editor must render: an unfocused editor driven over MCP renders nothing, so every renderer reads invisible and the heartbeat stays off.
- Force renders with a camera writing to a `RenderTexture`, or keep the editor focused.

**In-client.** One client proves only the wearer's own copy: look at the box, then away. The remote case the entry exists for needs a second client watching the avatar, once with `anti-cull` composed and once without, to confirm the failure mode in §Traps.
