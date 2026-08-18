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
import json
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
    """The committed controller.yaml as text, plus the build — the base
    `document()`'s frame with this instance's controller name."""
    f = base.build(c)
    L = []
    L.extend(f["header"])
    L.append("")
    L.append("schema: 1")
    L.append("controller: QuantChannelIndexPuppet_Fx")
    L.append("basis: mount-root          # no scene bindings; AAP trees only")
    L.append("role: fx")
    L.append("")
    L.append("defaults:")
    L.append("  writeDefaults: on")
    L.append("  transition: { duration: 0, exitTime: none, interruption: none }")
    L.append("")
    L.append("parameters:")
    L.extend(f["params"])
    L.append("")
    L.append("layers:")
    for block in f["layers"]:
        L.extend(block)
    L.append("")
    L.append("clips:")
    L.extend(f["clips"])
    return "\n".join(L) + "\n", f


def manifest_text(f):
    return json.dumps(f["manifest"], indent=2, sort_keys=False) + "\n"


def check(base):
    """Byte-identity of both emitted files against disk, and the prefab
    globalParams list — the base `check()`'s shape, one prefab."""
    c = CONFIG
    text, f = document(base, c)
    ok = True

    def assert_(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond

    print("[document]")
    assert_(document(base, c)[0] == text, "emission is deterministic across two calls")
    out = os.path.join(HERE, "controller.yaml")
    if os.path.exists(out):
        with open(out, encoding="utf-8", newline="") as fh:
            assert_(fh.read().replace("\r\n", "\n") == text,
                    "controller.yaml on disk matches CONFIG")
    else:
        assert_(False, f"controller.yaml is missing ({out})")

    print("[manifest]")
    mpath = os.path.join(HERE, "built", "manifest.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8", newline="") as fh:
            assert_(fh.read().replace("\r\n", "\n") == manifest_text(f),
                    "built/manifest.json on disk matches CONFIG")
    else:
        assert_(False, f"built/manifest.json is missing ({mpath})")
    for ch in f["manifest"]["channels"] + f["manifest"]["gates"]:
        assert_(ch["address"] == "/avatar/parameters/" + ch["name"],
                f"manifest address for {ch['name']} is the checked echo of its name")

    print("[prefab globalParams]")
    want = f["facts"]["interface"]
    path = os.path.join(HERE, "index-puppet.prefab")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        got, inside = [], False
        for ln in body.splitlines():
            if ln.strip() == "globalParams:":
                inside = True
            elif inside:
                if ln.strip().startswith("- "):
                    got.append(ln.strip()[2:].strip())
                else:
                    break
        assert_(got == want,
                f"index-puppet.prefab globalParams == the interface set ({len(want)} names)")
    else:
        assert_(False, "index-puppet.prefab is missing")

    print("OK" if ok else "FAILED")
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
        fh.write(manifest_text(f))
    facts = f["facts"]
    print(f"wrote controller.yaml + built/manifest.json — {facts['channelCount']} channels, "
          f"{facts['syncedBits']} synced bits, interface = {len(facts['interface'])} names")


if __name__ == "__main__":
    main()
