#!/usr/bin/env python3
"""entry-mode instance: `../generate.py`'s document at mode `entry`, K=3.

The second worked configuration of the base generator, emitted through its
`document(overrides)` door. The slot releases at the burst instead of holding
the hand across a re-arm band, so the acquisition cube face is the re-arm
surface: the cube sits 0.10 m outside the sphere so an on-axis poke has to
retract that far to burst again — the same hysteresis distance as dwell's band. `ContactRadarEntry.prefab` beside this
file is a prefab VARIANT of `../ContactRadar.prefab` — it removes `Slot4`, removes
each kept slot's `Marker` (the payload flashes for the burst state's few frames
here, so a mesh inside it would flash) and replaces the root FullController with
one pointing at this folder's `built/` (the README §Entry mode states all three,
since a removal is unvalidated).

Same discipline as the base: edit CONFIG, rerun (`python generate.py`),
recompile `built/` in a mounting Editor — never hand-edit `controller.yaml`;
check freshness by regenerating and reading git diff. `--check` runs the base
check over this folder's prefab at this CONFIG.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(os.path.dirname(HERE), "generate.py")


def load_base():
    # The folder name is not an identifier, so the documented import is by path.
    spec = importlib.util.spec_from_file_location("contact_radar_generate", BASE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONFIG = {
    "controller": "ContactRadarEntry_Fx",
    "mode": "entry",
    "K": 3,
    "acqHalf": 1.1,             # the re-arm surface in this mode: a hand must retract 0.10 m past the sphere to burst again
    "holdHalf": 1.2,
    "burstRadius": 1.0,
}


def main():
    base = load_base()
    if "--check" in sys.argv:
        sys.exit(0 if base.check_variant(CONFIG, HERE, "ContactRadarEntry.prefab",
                                         os.path.join(os.path.dirname(HERE), "ContactRadar.prefab")) else 1)
    text, facts = base.document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml — mode {facts['mode']}, K={facts['K']}, {facts['receivers']} receivers, {facts['syncedBits']} synced bit")


if __name__ == "__main__":
    main()
