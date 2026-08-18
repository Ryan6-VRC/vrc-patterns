#!/usr/bin/env python3
"""index-puppet instance: the base entry's channels at the bridge's shipped
`index_puppet` addresses — manifest id 2.

A second worked configuration of `../generate.py`, emitted through its fragment
door (`build(config)`): four signed 3-bit axes at `IndexPuppet/{Left,Right}_{X,Y}`
plus the `IndexPuppet/Enable` gate — the exact wire vrc-bridge's `index_puppet`
mapping drives from its `[puppet]` settings, so the shipped sender needs no
embedder code for the avatar side to move. The values here are the bridge's
defaults on purpose: the directory's puppet cross-check refuses to arm a manifest
whose `bits`/`floatTau` disagree with the `[puppet]` table actually driving these
addresses, so a change on either side is a change to both (the entry README's
registry table is the ledger; bump `revision` here and reinstall the manifest).

Same discipline as the base: edit CONFIG, rerun (`python generate.py`), recompile
`built/` in a mounting Editor — never hand-edit `controller.yaml` or
`built/manifest.json` (`--check` holds both to byte-identity, plus the prefab's
`globalParams` list, which no gate reads).
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(os.path.dirname(HERE), "generate.py")


def load_base():
    # The folder name is not an identifier, so the documented import is by path.
    spec = importlib.util.spec_from_file_location("quant_channel_generate", BASE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONFIG = {
    "manifestId": 2,
    "revision": 1,
    # bits/signed/floatTau mirror vrbridge's PuppetSettings defaults
    # (quant_level=3, signed hardcoded, float_smooth_tau_secs=0.12): the
    # cross-check compares field-for-field and refuses the arm on any drift.
    "channels": [
        {"name": "IndexPuppet/Left_X", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "IndexPuppet/Left_Y", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "IndexPuppet/Right_X", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
        {"name": "IndexPuppet/Right_Y", "bits": 3, "signed": True,
         "local": {"frametime": False, "lambda": 0.0},
         "remote": {"frametime": True, "tau": 0.15},
         "floatTau": 0.12},
    ],
    # The sender drops it after idle (touch_active_idle_secs); consumers weight
    # their trees on it, same contract as the base config's gate.
    "gates": ["IndexPuppet/Enable"],
}


def document(base, c):
    """The base `document()`'s frame under this instance's controller name —
    one frame home, so a base frame change reaches this build through `--check`."""
    return base.document(c, controller="QuantChannelIndexPuppet_Fx")


def check(base):
    """The base check body over this instance's files, plus the registry assert
    the base cannot make for itself: two generators now pin manifest ids, and the
    README table is narration no gate reads — the collision must fail here."""
    ok = base.check_files(
        lambda c: document(base, c), CONFIG, HERE, ("index-puppet.prefab",),
        extra=((CONFIG["manifestId"] != base.CONFIG["manifestId"],
                "manifestId does not collide with the base config's"),))
    sys.exit(0 if ok else 1)


def main():
    base = load_base()
    if "--check" in sys.argv:
        check(base)
        return
    text, f = document(base, CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.makedirs(os.path.join(HERE, "built"), exist_ok=True)
    with open(os.path.join(HERE, "built", "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(base.manifest_text(f))
    facts = f["facts"]
    print(f"wrote controller.yaml + built/manifest.json — {facts['channelCount']} channels, "
          f"{facts['syncedBits']} synced bits, interface = {len(facts['interface'])} names")


if __name__ == "__main__":
    main()
