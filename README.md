# vrc-patterns

> Part of the [Atelier](https://github.com/Ryan6-VRC/atelier) workspace — a code reference, not a standalone product. The docs that govern this code live in the meta-repo.

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced (`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by what you want to build

Each row: the entry, what a wearer gets from it, then the mechanism and its sync cost. `docs/gimmicks.md` is the durable techniques doc and routes here as a whole, not entry-by-entry.

| Entry | Build this | Mechanism / cost | Tier |
|---|---|---|---|
| [`grab-prop`](grab-prop/) | A prop anyone in the instance can pick up, carry, and put down — it stays where it's left, re-grabbable in place | open grab physbone (native sync) + constraint sample-and-hold drop; 0 synced bits | Module |
| [`6dof-grab-prop`](6dof-grab-prop/) | A prop anyone can grab, turn in their hand like a real object, and set down — orientation recovered from the grabber's own palm sender, no install on their side | grab-prop's cell + 8 box receivers reading the built-in palm capsule into an oriented-pattern blend-tree readout + a VRC aim pair; relative capture by disable-hold; 1 synced bit | Module |
| [`drop-on-player`](drop-on-player/) | Hand your prop to a friend: release it on your head, their head, or leave it in the world | release arbitration → bone anchor / proximity cage / world freeze; 2 synced bits | Module |
| [`anchor-prop`](anchor-prop/) | A wearer-only prop that rests at five anchors — chest, either hand, mouth, or frozen in the world — moved by a fist grip | five-anchor constraint multiplexer, gesture-release commit, chop-exempt mouth anchor, FreezeToWorld band; 1 synced int | Module |
| [`contact-tracker`](contact-tracker/) | The primitive for interacting with another player's body — track a point on someone else by any contact tag, the position VRChat won't otherwise give you. Latch a prop, follower, or marker to them | contact latching + trilateration cage; 1 synced bit | Module |
| [`box-tracker`](box-tracker/) | Same, reconstructed to an exact absolute position on a smaller contact budget — generally supersedes contact-tracker | 4-receiver linear reconstruction + crawler servo; 1 synced bit | Module |
| [`drag-bone`](drag-bone/) | Give a facing to an object something else positions but never rotates — it turns the way it moves (not a grab affordance; pair it with grab-prop) | rotation from position history: physbone pull-cord + aim constraint; 0 synced params, no controller | Structural Module |
| [`selective-animation`](selective-animation/) | Point at someone and hold the tag button: their copy of you changes and the people you did not point at are unaffected, and it stays until you erase — plus a button that tags your own copy | per-client raycast masked to the observer's own capsule + an animator-local state latch, invalidated by an erase generation; 2 synced bits however many are tagged | Module |
| [`zone-touch`](zone-touch/) | Touch zones on the body that react when touched — a headpat, a poke. The common reaction fires instantly on every client (zero latency, no sync), while a rare random special outcome is synced so everyone still agrees on it | remote-firing receivers reproduce the common reaction per-client; only the divergent outcome syncs; 2 bits | Module |
| [`head-deform`](head-deform/) | Grab your own face and stretch it — squishable cheeks that work in first person, read correctly in mirrors, and strangers can join in | self-exempt VRCHeadChop chain + retargeted scale constraint + mirror-gated compensation | Module |
| [`head-proxy`](head-proxy/) | Throw your voice into a puppet or prop — it speaks from there while your visible head stays yours to animate; your viewpoint and hearing stay at your headset | proxy-head rig (humanoid Head = non-deform proxy), VoiceTarget socket, auto fake-chop past the release gate | Module, study |
| [`mirror-detect`](mirror-detect/) | Know whether this copy is your real body, the mirror clone, or a remote — the gate behind every "only in the mirror" trick | parameter-driver race; 3-valued, 0 synced bits | Pattern, study |
| [`spring-damping`](spring-damping/) | Physics-like secondary motion — bounce, positional lag, rotational lag — on any object without a PhysBone; a Quest-safe constraint building block to reuse wherever you need springiness or damping | self-referencing constraints (the mechanical exponential smoother) | Structural Module |
| [`anti-cull`](anti-cull/) | Keep your avatar's animator running on remote clients when it leaves their view — a view-culled avatar suspends its animator, freezing replayed-choreography gimmicks (dropped props, trackers) | renderer-bounds inflation (view-cull defeat; distance culling is undefeatable); 1 bit | Module |
| [`word-channel`](word-channel/) | A declared table of values — bytes, ranged floats, bools — replicated to every remote over a synced channel narrower than the table, late-join included, at a declared cadence | generated batch-counter multiplexer (VRCFury-compressor protocol, pause-hardened); demo 21 bits carrying 28 | Module |
| [`object-sync`](object-sync/) | A prop set down anywhere in the world that is in the same place for everyone, late joiners included — millimetre placement over a ±4096 m range, no physbone anywhere | two-stage contact measure (coarse cell + redundant bias-cancelling fine) + aim-constraint rotation, over word-channel; 28 synced bits (a 27-bit wire + the enable), ~0.7 s refresh | Module |
| [`color-adjust`](color-adjust/) | A live hue / saturation / brightness radial for any lilToon or Poiyomi material | direct shader-property writes composed WD-ON | Pattern, study |
| [`hsv-rgb`](hsv-rgb/) | A real color picker — RGB computed from H/S/V sliders in pure blend trees | HSV→RGB DBT compute | Pattern, study |
| [`blendtree-math`](blendtree-math/) | The arithmetic behind analog gimmicks: add, multiply, clamp, remap, smooth any animator float — no scripts | DBT math library, per-primitive measured | Pattern, study |
| [`smooth-frametime`](smooth-frametime/) | Framerate-independent easing for jittery inputs (OSC hardware, remote grabs) — an exponential smoother plus a constant-velocity hybrid that still settles cleanly | frametime-aware AAP smoothers: two exponential α-flavours + a linear/hybrid constant-velocity smoother | Pattern, study |
| [`quant-channel`](quant-channel/) | Continuous OSC-driven parameters replicated to remotes over binary-quantized synced bools, decoded and smoothed on the receiving side only — the wearer rides their own raw float | generated VRCFT-compatible bit channels + IsLocal-gated decode + frametime-compensated exponential smoothing, sender manifest included; demo 4 signed 3-bit axes + gate = 17 bits | Module |
| [`osc-wardrobe`](osc-wardrobe/) | Change your worn avatar from a button on your own menu — pick the next one from a radial instead of the avatar list (needs an OSC host running vrc-bridge; inert without it) | menu int → OSC host → inbound `/avatar/change`, avatar picked by a marker parameter's default; 0 synced bits, no animator | Structural Module |
| [`debug-shaders`](debug-shaders/) | Three overlay shaders for seeing what an avatar is doing, on any mesh you drop them on: a twelve-value numeric readout mixing animator floats with render-side facts an animator cannot reach, a depth-derived wireframe/normals probe, and a localized grading bubble | fragment-stage MSDF text on a ray-traced virtual plane; depth-buffer reconstruction; grab-pass gamma over a volumetric sphere of influence; 0 synced bits | Structural Module |
| [`_template/`](_template/) | — reference mold — | | Module |

## Compositions

Runnable arrangements of two or more entries, committed as prefabs because an arrangement is a graph and prose loses it. `CONVENTIONS.md` §compositions/ owns the rules.

| Composition | Build this | Composes |
|---|---|---|
| [`object-sync-demo`](compositions/object-sync-demo/) | A world-synced prop you hold, **point a raycast at a surface to place**, or freeze — with a hand-held **debug-shader tablet** reading its own wire live: the coarse and fine words, the batch index, and whether this client's receiver has a whole word table yet. Also the worked example for a hand-mounted `VRCRaycast` with a surface-aligned result, and for driving a debug readout from animator clips | `object-sync` · `word-channel` · `anti-cull` · `debug-shaders`; 52 wire bits, 3 batches, ~0.350 s |

## Using an entry

- **Agent, in-workspace:** the interface is the source — read the entry's `controller.yaml` (or `generate.py`) and its prefab, and lift/adapt from them. The README is orientation, traps, and measurements, never a substitute for reading them (CLAUDE.md rule 10).
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles every entry at any nesting depth and checks controller decompile-equality plus prefab integrity/provenance for entries with `built/` — it confirms freshness, not runtime correctness; the install steps in each entry's README are what that rests on. Run it before merging.
