# vrc-patterns

> Part of the [Atelier](https://github.com/Ryan6-VRC/atelier) workspace — a code reference, not a standalone product. The docs that govern this code live in the meta-repo.

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced
(`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by pattern

Keyed by capability — find the row that does what you need and jump to its entry. This table is the
per-entry index for the library; `docs/gimmicks.md` is the durable techniques doc and routes here as a
whole, not entry-by-entry.

| Capability | Tier | Entry |
|---|---|---|
| Hue / color slider (drive shader property) | Pattern (study) | [`color-adjust`](color-adjust/) |
| HSV→RGB compute (write RGB color) | Pattern (study) | [`hsv-rgb`](hsv-rgb/) |
| DBT math (add/subtract/multiply/divide/clamp/remap, min/max, smoothing, frametime) | Pattern (study) | [`blendtree-math`](blendtree-math/) |
| AAP exponential smoother (frametime-aware) | Pattern (study) | [`smooth-frametime`](smooth-frametime/) |
| Grab a prop, world-drop it, re-grab in place (0-bit drop, usable by everyone) | Module | [`grab-prop`](grab-prop/) |
| Latch onto + track another player's point (hand/head), 1 synced bit | Module | [`contact-tracker`](contact-tracker/) |
| Same, at 4 receivers instead of 6 — exact within a fixed ±1.5 m volume, no chase (low contact budget) | Module | [`contact-tracker-box`](contact-tracker-box/) |
| Recover rotation from a point's position history — yaw or all-axes, 0 synced params / no controller (for position-only sources: grab-prop, contact-tracker) | Module | [`drag-bone`](drag-bone/) |
| Grab a prop, release-arbitrated to own head / another player's head / world (2 synced bits, usable by everyone) | Module | [`drop-on-player`](drop-on-player/) |
| Stow/hand multi-anchor prop, physical gesture take/place + grip pose (1 synced int) | Module | [`held-prop`](held-prop/) |
| N-zone touch reaction, debounced + arbitrated, sync-only-the-divergent-outcome (2 synced bits) | Module | [`zone-touch`](zone-touch/) |
| Keep a head accessory full-size in your own first-person view, menu-toggleable (VRCHeadChop self-exemption) | Module | [`headchop-mount`](headchop-mount/) |
| Proxy-head rig: chop inversion, ventriloquism (voice/viewpoint off the deform head), mirror-gated fake chop, driver-race mirror detection | Module (study) | [`head-proxy-rig`](head-proxy-rig/) |
| Secondary motion — spring bounce / positional + rotational lag, no PhysBone (self-referencing constraints) | Module | [`spring-damping`](spring-damping/) |
| — reference mold — | Module | [`_template/`](_template/) |

The physbone prop Modules (`grab-prop`, `drop-on-player`) are **usable by every player in the
instance**, not just the wearer: the grab physbone is open to everyone (`allowGrabbing: True`)
and natively synced, so anyone can take, carry, and place the prop — the wearer's client
arbitrates and syncs the outcome. That is the novelty those entries package. `held-prop` is the
deliberate opposite pole: **wearer-only by authorization** (`allowSelf`-only sensing — no
stranger can take your prop), anchored by constraint rather than carried by physbone.

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in
  `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + validates every entry and checks controller decompile-equality for entries
with `built/`. Run it before merging.
