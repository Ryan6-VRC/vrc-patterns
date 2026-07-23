# vrc-patterns

> Part of the [Atelier](https://github.com/Ryan6-VRC/atelier) workspace — a code reference, not a standalone product. The docs that govern this code live in the meta-repo.

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced (`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by what you want to build

Each row: the entry, what a wearer gets from it, then the mechanism and its sync cost. `docs/gimmicks.md` is the durable techniques doc and routes here as a whole, not entry-by-entry.

| Entry | Build this | Mechanism / cost | Tier |
|---|---|---|---|
| [`grab-prop`](grab-prop/) | A prop **anyone in the instance** can pick up, carry, and put down — it stays where it's left, re-grabbable in place | open grab physbone (native sync) + constraint sample-and-hold drop; **0 synced bits** | Module |
| [`drop-on-player`](drop-on-player/) | Hand your prop to a friend: release it on your head, **their** head, or leave it in the world | release arbitration → bone anchor / proximity cage / world freeze; 2 synced bits | Module |
| [`anchor-prop`](anchor-prop/) | A **wearer-only** prop that rests at five anchors — chest, either hand, mouth, or frozen in the world — moved by a fist grip | five-anchor constraint multiplexer, gesture-release commit, chop-exempt mouth anchor, FreezeToWorld band; **1 synced int** | Module |
| [`contact-tracker`](contact-tracker/) | The primitive for interacting with **another player's body** — track a point on someone else by any contact tag, the position VRChat won't otherwise give you. Latch a prop, follower, or marker to them | contact latching + trilateration cage; 1 synced bit | Module |
| [`box-tracker`](box-tracker/) | Same, reconstructed to an exact absolute position, on a smaller contact budget | 4-receiver linear reconstruction + crawler servo | Module |
| [`drag-bone`](drag-bone/) | Give a dragged or tracked object a **facing** (it turns the way it moves) | rotation from position history: physbone pull-cord + aim constraint; **0 synced params, no controller** | Structural Module |
| [`zone-touch`](zone-touch/) | Touch zones on the body that react when touched — a headpat, a poke. The common reaction fires **instantly on every client** (zero latency, no sync), while a rare **random** special outcome is synced so everyone still agrees on it | remote-firing receivers reproduce the common reaction per-client; only the divergent outcome syncs; 2 bits | Module |
| [`head-deform`](head-deform/) | **Grab your own face and stretch it** — squishable cheeks that work in first person, read correctly in mirrors, and strangers can join in | self-exempt VRCHeadChop chain + retargeted scale constraint + mirror-gated compensation | Module |
| [`head-proxy`](head-proxy/) | **Throw your voice into a puppet or prop** — viewpoint and voice move, your visible head stays — without your own head geometry blocking the camera | proxy-head rig (humanoid Head = non-deform proxy), VoiceTarget socket, auto fake-chop past the release gate | Module, study |
| [`mirror-detect`](mirror-detect/) | Know whether this copy is your **real body, the mirror clone, or a remote** — the gate behind every "only in the mirror" trick | parameter-driver race; 3-valued, **0 synced bits** | Pattern, study |
| [`spring-damping`](spring-damping/) | Bouncy ears, tails, and accessories that lag and spring — **without a PhysBone** | self-referencing constraints (the mechanical exponential smoother) | Structural Module |
| [`anti-cull`](anti-cull/) | Keep your avatar rendering on remote clients when it leaves their view | renderer-bounds inflation (view-cull defeat; distance culling is undefeatable); 1 bit | Module |
| [`color-adjust`](color-adjust/) | A live hue / saturation / brightness radial for any lilToon or Poiyomi material | direct shader-property writes composed WD-ON | Pattern, study |
| [`hsv-rgb`](hsv-rgb/) | A real color picker — RGB computed from H/S/V sliders in pure blend trees | HSV→RGB DBT compute | Pattern, study |
| [`blendtree-math`](blendtree-math/) | The arithmetic behind analog gimmicks: add, multiply, clamp, remap, smooth any animator float — no scripts | DBT math library, per-primitive measured | Pattern, study |
| [`smooth-frametime`](smooth-frametime/) | Framerate-independent easing for jittery inputs (OSC hardware, remote grabs) — an exponential smoother plus a **novel constant-velocity hybrid** that still settles cleanly | frametime-aware AAP smoothers: two exponential α-flavours + a linear/hybrid constant-velocity smoother | Pattern, study |
| [`_template/`](_template/) | — reference mold — | | Module |

The physbone prop Modules (`grab-prop`, `drop-on-player`) are **usable by every player in the instance**, not just the wearer: the grab physbone is open to everyone (`allowGrabbing: True`) and natively synced, so anyone can take, carry, and place the prop — the wearer's client arbitrates and syncs the outcome. That is the novelty those entries package. `anchor-prop` is the deliberate opposite pole: **wearer-only by authorization** (`allowSelf`-only sensing — no stranger can take your prop), anchored by constraint rather than carried by physbone.

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + validates every entry and checks controller decompile-equality for entries with `built/`. Run it before merging.
