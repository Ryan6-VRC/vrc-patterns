# solve-order-pin — deterministic solve order inside a cyclic constraint group (Module)

When VRC constraints form a cycle — a sample-and-hold cell, a capture-on-release freeze, any feedback web — which edge the solver treats as the stale one is not something authoring controls, and the same prefab bytes can play good on one session and bad on the next. This module makes that choice deterministic: a chain of 16 inactive constraints whose tip you wire as a weight-0 source onto the constraint that must solve *last*, giving it a dependency path deeper than anything else on the avatar. Zero synced bits, drives nothing, and switches itself off after load so it costs nothing per frame.

**Provenance:** derived here, generalized out of this repo's own `compositions/grab-sync`. No external ancestor.

## Ground truth

The prefab owns the rig, `controller.yaml` the off-write. Seam facts no artifact states:

- **The tip edge is yours to wire, and it lands on your constraint, not ours.** Add `Ladder/Depth16`'s Transform as an additional source at **weight 0** on the constraint that must solve last, and never remove or reorder that constraint's existing sources.
- **Wire it through the inspector or `SerializedObject`.** A reflection or `execute_code` write to a VRC constraint's `Sources` serializes nothing while every field reads back correct in edit mode (`../../docs/runtime.md` §Constraints owns the trap).
- **`Ladder` ships active, and no timing protects it.** Its constraints join the solver on `OnEnable` at instantiation, which precedes any animation of them, so the off-write cannot land first. Switching the object off afterwards leaves them joined — that is what makes the module free per frame. Shipped inactive, or tidied off in edit mode, they never join and the rig pins nothing while looking identical.

## Traps

**The graph reads backwards.** Tracing it naively suggests the constraint that *reads* should be the deeper one. It is the other way round: the ladder does not make your constraint later in any ordinary sense, it biases where the solver cuts the ring.

**Sizing is a measurement, not a judgement.** Read the group index of the constraint the tipped one must solve *after* — that number is the depth already feeding it, and the ladder has to beat it. 16 is what one consumer measured sufficient, not a constant this module claims.

**It cannot tell you which side must be late.** That is a property of the consuming rig, and if that rig's own docs do not say, the only way to find out is to tip one side, test, and flip if wrong. A wrong-side tip inverts the order rather than failing, and reads as a clean pass.

**A pin is a global reorder.** Everything downstream of the tipped constraint moves with it. Re-read the indices on any other order-sensitive rig on the avatar.

**The tip is an *added* source — the operation measured as behaviour-changing** (`../grab-prop/README.md` §How it works carries that measurement and the safer *repoint* alternative). This module aims that change deliberately; the install check is what licenses it.

**Do not strip, shorten, or re-parent.** Depth rides the source edges, not the hierarchy: the nodes are flat siblings, so an anchor move by Modular Avatar or VRCFury is safe and re-nesting them into a chain buys nothing.

**Optimizers**, measured against the shipped rig: d4rk leaves it intact including under Full, its protection being that the nodes stay active with components enabled — so disabling either invites removal. AAO leaves it intact twice over: it will not merge a transform that is an animation target, which `Ladder` is by virtue of the off-write, and `Ladder` also carries an otherwise-pointless inactive constraint so it is never a bare Transform. Either alone suffices; the constraint stays as the half that survives someone retargeting the animation. Without both, the chain is silently reparented and renamed. Never tag any of this `EditorOnly` — that deletes the subtree.

**Extending past 16:** duplicate the tip node, then **repoint the duplicate's source to the node it now follows** — a duplicate keeps the original's source, giving a fan-out rather than a longer chain, with no added depth and no error. Re-wire your tip edge to the new last node. On a composed avatar this is an added-object override on the instance; do not apply it back to this package.

## Verifying the install

`generate.py --check` and the gate cover the shipped rig and its build. Neither can see whether the tip edge you wired actually moved the order, which is the only thing that matters on your avatar.

On a **fresh play entry**, on the built avatar, read `LatestValidExecutionGroupIndex` on both constraints (`../grab-prop/README.md` §How it works owns the observable). The pin is correct when the constraint that must read stale holds an index **both `>= 0` and strictly less than** the tipped constraint's. Neither half is decoration: a never-solved constraint reports `-1`, and the field retains its last valid value, so a bare comparison — or a reading taken after changing the rig mid-session — passes on a rig doing nothing at all (measured: a ladder deleted mid-session still read as a clean pass).

Re-read after any change to the avatar's constraint graph; a new deep chain feeding the other side of the cycle is what defeats a ladder, and it can arrive from anywhere.

This shows the order, never the consuming rig's behaviour. Anything a remote observer sees needs two clients in-game.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`. `generate.py --check` pins the hand-maintained rig.
