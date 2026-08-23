# solve-order-pin — deterministic solve order inside a cyclic constraint group (Module)

When VRC constraints form a cycle — a sample-and-hold cell, a capture-on-release freeze, any feedback web — which edge the solver treats as the stale one is not something authoring controls once the contested constraints drive targets on separate branches, and the same prefab bytes can play good on one session and bad on the next. This module aims at that choice: a chain of 16 inactive constraints whose tip you wire as a weight-0 source onto the constraint that must solve *last*, giving it a dependency path deeper than anything else on the avatar. Zero synced bits, drives nothing, and switches itself off after load so it costs nothing per frame.

**First check whether the contested pair can be given a target-hierarchy relation instead** — when one constraint's driven target transform is a hierarchy ancestor of the other's, the ancestor side solves in the earlier group and reads the descendant stale by construction, an order nothing registration-dependent can flip (`../../docs/runtime.md` §Constraints owns the rule; `../grab-prop/README.md` §How it works is the shipped consumer). That authors the order outright, so it beats biasing one. This module remains for cycles where no such relation can be authored — the two constraints drive transforms on separate branches, or the hierarchy is fixed by something else.

**It biases an ambiguous cut. It will not repair a rig that breaks every session — check which you have before installing.** Depth is longest-path, so deepening a node drags everything downstream of it down too and a ladder can never invert two constraints joined by a source edge — tipping a cycle's source node raised it 13 groups and raised the constraint reading it one group further still. Measured 5/5 against behaviour on a cell broken by an added in-ring source: every ring member tipped in turn, both starting states, the cut never moved and the broken cell stayed broken. So the symptom that indicates this module is **intermittency** — good one session, bad the next, no edit between. A deterministic break has a structural cause, and the fix is to remove the offending in-ring edge (`../grab-prop/README.md` §How it works owns the repoint), not to out-weigh it from outside.

**Provenance:** derived here, generalized out of this repo's own `compositions/grab-sync`, which no longer installs it — that cell's stale edge is now authored by the hierarchy relation above. No external ancestor; no consumer in this repo.

## Ground truth

The prefab owns the rig, `controller.yaml` the off-write. Seam facts no artifact states:

- **The tip edge is yours to wire, and it lands on your constraint, not ours.** Add `Depth16`'s Transform as an additional source at **weight 0** on the constraint that must solve last, and never remove or reorder that constraint's existing sources.
- **Wire it through the inspector or `SerializedObject`.** A reflection or `execute_code` write to a VRC constraint's `Sources` serializes nothing while every field reads back correct in edit mode (`../../docs/runtime.md` §Constraints owns the trap).
- **The prefab root ships active, and no timing protects it.** Its constraints join the solver on `OnEnable` at instantiation, which precedes any animation of them, so the off-write cannot land first. Switching the root off afterwards leaves them joined — that is what makes the module free per frame. Shipped inactive, or tidied off in edit mode, they never join and the rig pins nothing while looking identical. The off-write owns the **instance root's** `m_IsActive`, so park nothing under the instance and never aim a consumer toggle at it.

## Traps

**Depth is not the cut.** The ladder moves a constraint's group index; where the solver cuts the ring is decided separately, and on a pair joined by an in-ring source edge no tip has been measured to move it. Never reason from a changed index to a changed behaviour.

**Sizing is a measurement, not a judgement.** Read the group index of the constraint the tipped one must solve *after* — that number is the depth already feeding it, and the ladder has to beat it. Take that read in play, past frame 1: `latestValidExecutionGroupIndex` serializes and retains its last valid value, so an edit-mode or entry-frame read reports the previous session and looks entirely plausible. 16 is what one consumer measured sufficient, not a constant this module claims.

**It cannot tell you which side must be late.** That is a property of the consuming rig, and if that rig's own docs do not say, the only way to find out is to tip one side, test behaviourally, and flip if wrong. **Read "no change" as the wrong diagnosis, not the wrong side** — a tip that moves the indices and nothing else is the signature of a cut fixed by an in-ring edge, which no tip on any member will lift.

**A pin is a global reorder.** Everything downstream of the tipped constraint moves with it. Re-test the behaviour of any other order-sensitive rig on the avatar — re-reading their indices does not cover it, since an index can move while the cut holds and vice versa.

**The tip is an *added* source — the operation measured as behaviour-changing** (`../grab-prop/README.md` §How it works carries that measurement and the safer *repoint* alternative). This module aims that change deliberately; the install check is what licenses it.

**Do not strip, shorten, or re-parent.** Depth rides the source edges, not the hierarchy: the nodes are flat siblings, so an anchor move by Modular Avatar or VRCFury is safe and re-nesting them into a chain buys nothing.

**Optimizers**, measured against the shipped rig: d4rk leaves it intact including under Full, its protection being that the nodes stay active with components enabled — so disabling either invites removal. AAO's auto-merge takes only a Transform-only, non-animated node, so nothing here qualifies: every `Depth` node carries a constraint, and the root is the off-write's animation target. Never tag any of this `EditorOnly` — that deletes the subtree.

**Extending past 16:** duplicate the tip node, then **repoint the duplicate's source to the node it now follows** — a duplicate keeps the original's source, giving a fan-out rather than a longer chain, with no added depth and no error. Re-wire your tip edge to the new last node. On a composed avatar this is an added-object override on the instance; do not apply it back to this package.

## Verifying the install

`generate.py --check` and the gate cover the shipped rig and its build. Neither can see whether the tip edge you wired changed your rig's behaviour, which is the only thing that matters on your avatar.

**Verify by frame lag, never by comparing group indices.** The index is a depth; the cut is decided separately, and the two disagree — measured across six `grab-prop` cells on one avatar, against behaviour confirmed by grabbing, an index comparison predicted behaviour 5/6 and the relative frame lag 6/6. The miss was a cell holding an inverted index and behaving correctly, which the index check calls mis-pinned and sends you to break a working avatar.

**The lag method:** in play, ramp a transform upstream of the cycle a fixed step per frame and record how many frames behind each node lands. Lag above the cycle is common-mode and cancels, so only the step across the contested edge counts, and the node reading across the stale edge lands exactly one frame further back than its own source. Lag is in frames, so halving the ramp rate must not change the reading — that invariance is what separates it from an artifact of the drive.

Re-verify after any change to the avatar's constraint graph; a new edge inside the cycle is what moves a cut, and it can arrive from anywhere.

The lag read predicts the consuming rig's local behaviour and has been measured to track it. Anything a **remote** observer sees still needs two clients in-game.

## Rebuilding

`controller.yaml` → `CompileController` → `built/`. `generate.py --check` pins the hand-maintained rig.
