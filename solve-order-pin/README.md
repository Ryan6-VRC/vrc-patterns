# solve-order-pin — deterministic solve order inside a cyclic constraint group (Module)

When VRC constraints form a cycle, which edge the solver treats as the stale one is not something authoring controls: the same prefab bytes can play good on one session and bad on the next. This module makes that choice deterministic. It ships a chain of 16 inactive constraints whose tip you wire as a weight-0 source onto the constraint that must solve *last*, giving it a dependency path deeper than anything else on the avatar. Costs **zero synced bits**, drives nothing, and switches its own GameObject off after load so it costs nothing per frame.

Reach for it when a rig built on a constraint cycle — a sample-and-hold cell, a capture-on-release freeze, any feedback web — works on some sessions and not others with no edit between.

**Provenance:** derived here, generalized out of this repo's own `compositions/grab-sync`. No external ancestor.

## Ground truth

The prefab owns the rig; `controller.yaml` owns the off-write and its header carries why the timing is shaped the way it is. Seam facts no artifact states:

- **The tip edge is yours to wire, and it lands on your constraint, not ours.** Add `Ladder/Depth16`'s Transform as an additional source at **weight 0** on the constraint that must solve last. Never remove or reorder that constraint's existing sources. Nothing ships pre-wired, and nothing validates that you did it — the install check below is the only thing that will tell you.
- **Wire it through the inspector or `SerializedObject`.** A reflection or `execute_code` write to a VRC constraint's `Sources` serializes nothing while every field reads back correct in edit mode (`../../docs/runtime.md` §Constraints owns the boxing trap). This is the module's one install step, so it is the one place that trap is guaranteed to bite.
- **`Ladder` ships active, and the off-write must not race that.** Its constraints join the solver when the object first becomes active, and switching it off afterwards leaves them joined — which is the whole reason the module can cost nothing per frame. Shipping it already inactive, or "tidying" it off in edit mode, never joins them and produces a rig that looks identical and pins nothing. The off-write lands a few frames after load (measured at play frame 3, constraints joined from frame 0), so the window is comfortable rather than tight — but it is a window, and a rebuild that moved the write into the very first evaluation has never been measured. The state graph in `controller.yaml` is load-bearing timing, not a formality.

## Traps

**The cycle is why this works, and the graph reads backwards without it.** Inside a cycle every node reaches every other, so depth is ill-defined and the solver cuts the ring somewhere. The ladder does not make your constraint "later" in an ordinary sense — it biases *where the cut falls*. Tracing the graph naively suggests the reader should be the deeper node; it is the other way round, and that is the whole mechanism.

**Sizing is a measurement, not a judgement.** Read the group index of the constraint the tipped one must solve *after* — that number is the depth of the deepest path already feeding it. The ladder has to beat it. 16 is what one consumer measured sufficient, not a constant this module claims; take the reading on your own avatar before assuming it.

**This module cannot tell you which side must be late.** That is a property of the consuming rig — which constraint depends on reading a one-frame-stale value — and if that rig's own documentation does not say, the only way to find out is to tip one side, test the behaviour, and flip if wrong. A wrong-side tip inverts the order rather than failing loudly, and reads as a clean pass on the metric below.

**A pin is a global reorder.** Everything downstream of the tipped constraint moves with it, not just the cycle you aimed at. After installing, re-read the indices on any other order-sensitive constraint rig on the avatar.

**The tip is an *added* source, which is the operation measured as behaviour-changing** — `../grab-prop/README.md` §How it works carries that measurement and the safer *repoint* alternative. This module performs the risky operation deliberately; the install check is what licenses it.

**Never read the index after changing the rig in the same play session.** The group index retains its last valid value, so a rig whose ladder has been removed outright still reports a healthy pass until the solver re-derives. Every trustworthy reading is taken on a **fresh play entry** (measured — a ladder deleted mid-session read as a clean pass, and re-derivation then showed the unpinned values).

**Do not strip, shorten, or re-parent.** Depth rides the source edges, not the hierarchy — the 16 nodes are flat siblings, which is why an anchor move by Modular Avatar or VRCFury is safe and why re-parenting them into a chain buys nothing.

**Optimizers**, measured against the shipped rig: d4rk leaves it intact under both its stock and Full presets — its protection is that the nodes stay active with their components enabled, so setting either off invites removal. AAO leaves it intact too, and does so **twice over**: it will not merge away a transform that is an animation target, which `Ladder` is by virtue of the off-write, and `Ladder` also carries an otherwise-pointless inactive constraint so that it is never a bare Transform. Either alone is sufficient (measured, by removing each in turn); the constraint stays because it is the half that survives someone retargeting or removing the animation, and without both the chain is silently reparented and renamed. Never tag any of this `EditorOnly` — that deletes the subtree outright.

**Extending past 16:** duplicate the tip node, then **repoint the duplicate's source to the node it now follows** — a duplicate keeps the original's source and gives you a fan-out, not a longer chain, with no added depth and no error. Re-wire your tip edge to the new last node. On a composed avatar the extension is an added-object override on the instance; do not apply it back to this package.

## Verifying the install

The module drives nothing, so there is no behaviour to watch. `generate.py --check` and the gate cover the shipped rig and its build; neither can see the one thing that matters on your avatar, which is whether the tip edge you wired actually moved the order. That is this metric, and nothing else checks it.

On a **fresh play entry**, on the built avatar, read `LatestValidExecutionGroupIndex` on both constraints (the observable, and how it was established, live in `../grab-prop/README.md` §How it works). The pin is correct when the constraint that must read stale holds an index that is **both `>= 0` and strictly less than** the tipped constraint's. The `>= 0` half is not decoration: a never-solved constraint reports `-1`, so a bare comparison passes on an inactive or unregistered rig that is doing nothing at all.

Re-read it after any change to the avatar's constraint graph — a new deep chain feeding the other side of the cycle is what defeats a ladder, and it can arrive from anywhere on the avatar.

What this cannot show: whether the consuming rig's *behaviour* is right, only that the order is what you asked for. Two clients in-game remain the authority on anything a remote observer sees.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`. `generate.py --check` pins the prefab's hand-maintained rig.
