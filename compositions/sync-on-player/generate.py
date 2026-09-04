#!/usr/bin/env python3
"""This composition's own `object-sync` build: the shipped entry's generator
run once, emitting beside this file instead of into the entry.

    python compositions/sync-on-player/generate.py           # writes the document

Output: `object-sync/controller.yaml` — one object, position only
(`rotation: "none"`), compiled with `CompileController` into the `built/`
beside it. The prefab does not point at `../../object-sync/built/`: the
entry's committed builds emit at mountPath "" and cannot merge through the
shared component below.

THE CONFIGURATION
-----------------
The entry's shipped CONFIG — the wire block, the shipped default-off
`enableDefault` (the BUILD never arms itself; the glue's params asset declares
`ObjectSync/Enable` default-1 and merges first, so the pattern spawns armed —
controller.yaml's header owns the mechanism) — at two deliberate deltas:

- `mountPath "ObjectSync"`: the sync rig is the nested GO of that name under
  the composition root, and the root's FullController is SHARED, carrying the
  glue controller and this build together — the sealed-interface coupling
  (the entry's §Seam; grab-sync is the worked precedent). Controller ORDER in
  that component is load-bearing (glue first, first-wins); controller.yaml's
  header owns the mechanism.
- `rigSeed "sync-on-player/g6"`: this composition's OWN namespace skew — tags
  and park derive from the seed together, which is what lets a different
  object-sync build (grab-sync at the entry default) compose beside this one
  on one avatar. The parameters stay sealed identical by design; only tags
  and park differ.

The build is position-only: `drop-on-player` ships one position channel, so
no drag bone, no heading, no rotation words exist anywhere in this
composition — the emitted surface is the `Sync`/`Sync_Target` pair and the
two collision tags printed in the document header.

The glue document's cell bindings are `drop-on-player/controller.yaml`'s clip
table transcribed by hand under the `Prop/DropOnPlayer/` prefix (its header
names the carves); nothing here checks that transcription.
"""

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "object-sync", "generate.py"))
OUT = os.path.join(HERE, "object-sync", "controller.yaml")

OBJECTS = [{"name": "Prop", "rotation": "none"}]

# The nested sync rig's GO name under the composition root — the hand-
# maintained pairing mountPath buys: the emitted bindings prefix this string.
MOUNT = "ObjectSync"

# The namespace skew: one string, from which tag_set derives the collision
# tags and rig_offset derives the park — together, never separately (the
# entry's CONFIG rigSeed comment owns why).
RIG_SEED = "sync-on-player/g6"


def entry_module():
    if not os.path.exists(ENTRY):
        raise SystemExit(
            f"REFUSE: the object-sync generator is not at {ENTRY} — this build "
            "is the entry's generator run at a different rigSeed and cannot "
            "emit a document without it.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_config(mod):
    cfg = dict(mod.CONFIG)
    cfg["objects"] = [dict(ob) for ob in OBJECTS]
    cfg["mountPath"] = MOUNT
    cfg["rigSeed"] = RIG_SEED
    return cfg


def main():
    mod = entry_module()
    cfg = sync_config(mod)
    text, f = mod.document(cfg)
    facts = f["facts"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(f['layers'])} layers, "
          f"{len(f['clips'])} clips, {facts['wireBits']} wire bits, "
          f"{facts['payloadBits']} payload bits, {facts['batchCount']} batches, "
          f"~{facts['cycleSeconds']:.3f}s refresh @60fps")
    print(f"park {mod.rig_offset(cfg['rigSeed'])}; tags {mod.tag_set(cfg, 'Prop')}")


if __name__ == "__main__":
    main()
