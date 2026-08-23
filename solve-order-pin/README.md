# solve-order-pin — deterministic solve order inside a cyclic constraint group (Module)

When VRC constraints form a cycle — a sample-and-hold cell, a capture-on-release freeze, any feedback web — which edge the solver treats as the stale one is not something authoring controls, and the same prefab bytes can play good on one session and bad on the next. This module aims at that choice: a chain of 16 inactive constraints whose tip you wire as a weight-0 source onto the constraint that must solve *last*, giving it a dependency path deeper than anything else on the avatar. Zero synced bits, drives nothing, and switches itself off after load so it costs nothing per frame.

**It biases an ambiguous cut. It will not repair a rig that breaks every session — check which you have before installing.** Depth is longest-path, so deepening a node drags everything downstream of it down too and a ladder can never invert two constraints joined by a source edge. Measured 5/5 against behaviour on a cell broken by an added in-ring source: every ring member tipped in turn, both starting states, the cut never moved and the broken cell stayed broken (`../../docs/runtime.md` §Constraints owns the measurement). So the symptom that indicates this module is **intermittency** — good one session, bad the next, no edit between. A deterministic break has a structural cause, and the fix is to remove the offending in-ring edge (`../grab-prop/README.md` §How it works owns the repoint), not to out-weigh it from outside.

**Provenance:** derived here, generalized out of this repo's own `compositions/grab-sync`. No external ancestor.

## Ground truth

The prefab owns the rig, `controller.yaml` the off-write. Seam facts no artifact states:

- **The tip edge is yours to wire, and it lands on your constraint, not ours.** Add `Depth16`'s Transform as an additional source at **weight 0** on the constraint that must solve last, and never remove or reorder that constraint's existing sources.
- **Wire it through the inspector or `SerializedObject`.** A reflection or `execute_code` write to a VRC constraint's `Sources` serializes nothing while every field reads back correct in edit mode (`../../docs/runtime.md` §Constraints owns the trap).
- **The prefab root ships active, and no timing protects it.** Its constraints join the solver on `OnEnable` at instantiation, which precedes any animation of them, so the off-write cannot land first. Switching the root off afterwards leaves them joined — that is what makes the module free per frame. Shipped inactive, or tidied off in edit mode, they never join and the rig pins nothing while looking identical. The off-write owns the **instance root's** `m_IsActive`, so park nothing under the instance and never aim a consumer toggle at it.

## Traps

**Depth is not the cut.** The ladder moves a constraint's group index and nothing else; where the solver cuts the ring is decided separately, and on a source-linked pair the ladder has been measured never to move it. Do not reason from a changed index to a changed behaviour — that inference is the module's original error.

**Sizing is a measurement, not a judgement.** Read the group index of the constraint the tipped one must solve *after* — that number is the depth already feeding it, and the ladder has to beat it. 16 is what one consumer measured sufficient, not a constant this module claims.

**It cannot tell you which side must be late.** That is a property of the consuming rig, and if that rig's own docs do not say, the only way to find out is to tip one side, test behaviourally, and flip if wrong. **Read "no change" as the wrong diagnosis, not the wrong side** — a tip that moves the indices and nothing else is the signature of a cut fixed by an in-ring edge, which no tip on any member will lift.

**A pin is a global reorder.** Everything downstream of the tipped constraint moves with it. Re-test the behaviour of any other order-sensitive rig on the avatar — re-reading their indices does not cover it, since an index can move while the cut holds and vice versa.

**The tip is an *added* source — the operation measured as behaviour-changing** (`../grab-prop/README.md` §How it works carries that measurement and the safer *repoint* alternative). This module aims that change deliberately; the install check is what licenses it.

**Do not strip, shorten, or re-parent.** Depth rides the source edges, not the hierarchy: the nodes are flat siblings, so an anchor move by Modular Avatar or VRCFury is safe and re-nesting them into a chain buys nothing.

**Optimizers**, measured against the shipped rig: d4rk leaves it intact including under Full, its protection being that the nodes stay active with components enabled — so disabling either invites removal. AAO's auto-merge takes only a Transform-only, non-animated node, so nothing here qualifies: every `Depth` node carries a constraint, and the root is the off-write's animation target. Never tag any of this `EditorOnly` — that deletes the subtree.

**Extending past 16:** duplicate the tip node, then **repoint the duplicate's source to the node it now follows** — a duplicate keeps the original's source, giving a fan-out rather than a longer chain, with no added depth and no error. Re-wire your tip edge to the new last node. On a composed avatar this is an added-object override on the instance; do not apply it back to this package.

## Verifying the install

`generate.py --check` and the gate cover the shipped rig and its build. Neither can see whether the tip edge you wired changed your rig's behaviour, which is the only thing that matters on your avatar.

**Verify by frame lag, never by comparing group indices.** The index is a depth; the cut is a separate output, and a cell can hold an inverted index and behave correctly — the index comparison this section used to prescribe reports such a rig as mis-pinned, which sends you to break a working avatar. `../../docs/runtime.md` §Constraints owns the lag method and the measurement behind it.

Read the lag on the built avatar in play, **past frame 1 and with `isPlaying` asserted**. `latestValidExecutionGroupIndex` serializes and retains its last valid value, so an edit-mode read, or a read on the entry frame, reports the previous session and looks entirely plausible.

Re-read after any change to the avatar's constraint graph; a new edge inside the cycle is what moves a cut, and it can arrive from anywhere.

The lag read predicts the consuming rig's local behaviour and has been measured to track it. Anything a **remote** observer sees still needs two clients in-game.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`. `generate.py --check` pins the hand-maintained rig.
