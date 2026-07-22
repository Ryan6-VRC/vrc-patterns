# vrc-patterns

> Part of the [Atelier](https://github.com/Ryan6-VRC/atelier) workspace — a code reference, not a standalone product. The docs that govern this code live in the meta-repo.

Reusable, verified VRChat avatar patterns, controllers, and drop-in gimmick modules — YAML-sourced
(`CompileController`), shaped as a VPM package. Read `CONVENTIONS.md` first; author against `_template/`.

## Find by what you want to build

Each row leads with the thing a wearer actually gets; the second column is the mechanism and its
sync cost. `docs/gimmicks.md` is the durable techniques doc and routes here as a whole, not
entry-by-entry.

| Build this | Mechanism / cost | Tier | Entry |
|---|---|---|---|
| A prop **anyone in the instance** can pick up, carry, and put down — it stays where it's left, re-grabbable in place | open grab physbone (native sync) + constraint sample-and-hold drop; **0 synced bits** | Module | [`grab-prop`](grab-prop/) |
| Hand your prop to a friend: release it on your head, **their** head, or leave it in the world | release arbitration → bone anchor / proximity cage / world freeze; 2 synced bits | Module | [`drop-on-player`](drop-on-player/) |
| A pipe, mic, fan, or lollipop you pull from your body with a fist, **pass hand to hand**, **hold in your teeth**, or leave floating mid-air — wearer-only | five-anchor constraint multiplexer, gesture-release commit, chop-exempt mouth anchor, FreezeToWorld band; 1 synced int | Module | [`anchor-prop`](anchor-prop/) |
| A companion that latches onto another player's hand or head and follows them | contact latching + trilateration cage; 1 synced bit | Module | [`contact-tracker`](contact-tracker/) |
| Same, with an exact absolute readout and unlimited travel, on a smaller contact budget | 4-receiver linear reconstruction + crawler servo | Module | [`contact-tracker-box`](contact-tracker-box/) |
| Give a dragged or tracked object a **facing** (it turns the way it moves) | rotation from position history: physbone pull-cord + aim constraint; **0 synced params, no controller** | Module | [`drag-bone`](drag-bone/) |
| Headpats, cheek pokes, tail tugs — touch zones with debounced reactions everyone sees | remote-firing receivers reproduce the common reaction per-client; only the divergent outcome syncs; 2 bits | Module | [`zone-touch`](zone-touch/) |
| **Grab your own face and stretch it** — squishable cheeks that work in first person, read correctly in mirrors, and strangers can join in | self-exempt VRCHeadChop chain + retargeted scale constraint + mirror-gated compensation | Module | [`head-deform`](head-deform/) |
| **Throw your voice into a puppet or prop** — viewpoint and voice move, your visible head stays — without your own head geometry blocking the camera | proxy-head rig (humanoid Head = non-deform proxy), VoiceTarget socket, auto fake-chop past the release gate | Module (study) | [`head-proxy`](head-proxy/) |
| Know whether this copy is your **real body, the mirror clone, or a remote** — the gate behind every "only in the mirror" trick | parameter-driver race; 3-valued, **0 synced bits** | Pattern (study) | [`mirror-detect`](mirror-detect/) |
| Bouncy ears, tails, and accessories that lag and spring — **without a PhysBone** | self-referencing constraints (the mechanical exponential smoother) | Module | [`spring-damping`](spring-damping/) |
| Keep your avatar rendering on remote clients when it leaves their view | renderer-bounds inflation (view-cull defeat; distance culling is undefeatable); 1 bit | Module | [`anti-cull`](anti-cull/) |
| A live hue / saturation / brightness radial for any lilToon or Poiyomi material | direct shader-property writes composed WD-ON | Pattern (study) | [`color-adjust`](color-adjust/) |
| A real color picker — RGB computed from H/S/V sliders in pure blend trees | HSV→RGB DBT compute | Pattern (study) | [`hsv-rgb`](hsv-rgb/) |
| The arithmetic behind analog gimmicks: add, multiply, clamp, remap, smooth any animator float — no scripts | DBT math library, per-primitive measured | Pattern (study) | [`blendtree-math`](blendtree-math/) |
| Framerate-independent easing for jittery inputs (OSC hardware, remote grabs) | frametime-aware AAP exponential smoother | Pattern (study) | [`smooth-frametime`](smooth-frametime/) |
| — reference mold — | | Module | [`_template/`](_template/) |

The physbone prop Modules (`grab-prop`, `drop-on-player`) are **usable by every player in the
instance**, not just the wearer: the grab physbone is open to everyone (`allowGrabbing: True`)
and natively synced, so anyone can take, carry, and place the prop — the wearer's client
arbitrates and syncs the outcome. That is the novelty those entries package. `anchor-prop` is the
deliberate opposite pole: **wearer-only by authorization** (`allowSelf`-only sensing — no
stranger can take your prop), anchored by constraint rather than carried by physbone.

## Using an entry

- **Agent, in-workspace:** read the entry's `controller.yaml` + README Interface stanza; lift/adapt.
- **Unity:** a project takes it as a package dependency (AvatarProject uses a `file:` ref in
  `Packages/manifest.json`); entries import at `Packages/com.ryan6vrc.patterns/<entry>/`.

## Gate

`tools/gate.ps1` compiles + validates every entry and checks controller decompile-equality for entries
with `built/`. Run it before merging.
