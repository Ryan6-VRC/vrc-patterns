#!/usr/bin/env python3
"""bridge-persist generator: the avatar side of the bridge's persistence exchange, as one layer.

    python bridge-persist/generate.py        # writes this entry's own controller.yaml from CONFIG

A consumer drives `document(cfg)` with a config of its own and compiles the result into its own
`built/`, the way a composition drives `object-sync`'s generator: `compositions/grab-sync-persist`
is the worked consumer. The document is one controller holding one layer, merged through the
consumer's FullController beside the consumer's own glue. The glue never talks to the bridge: it
sees `Enable` go off, which parks it, and one local flag, which tells it the payload it is about to
read is a restored one it should place from.

WHAT THE LAYER DOES
-------------------
Wearer only, and only with `<namespace>/Id` non-zero; a remote, and a wearer at Id 0, sit in
`Load` for the whole session and write nothing.

  Load      the default. Nothing is written here: the wearer leaves on the first evaluation
            that reads IsLocal (entry rungs evaluate before it lands, so this is a level rung on
            a state, never an entry rung).
  Quiesce   drives Enable off and resets every payload name to its declared default.
  Boot      writes Announce (a copy of Id) and Boot (a random in (0, 1]) together, and drives
            Enable off and resets the payload AGAIN. A driver write made in the first state a
            layer writes from after a load does not reach the client's parameter (the emulator
            lands it, so no emulator run can show this), so nothing the exchange depends on rests
            on Quiesce alone.
  Wait      the window, WINDOW_SECS, in a state of its own entered the evaluation after Boot's
            write: a transition hands the rest of a frame's time to the state it enters, and a
            load hitch on the writing frame would otherwise be spent out of the window before the
            bridge's clock has started. `Restore` above 0 inside it (the bridge's 1, or a later
            value that overwrote it in the same frame) goes to Hold if any placed name reads
            true, else straight to Finish; the window running out goes to Finish.
  Hold      raises the flag and keeps it up for the hold, CONFIG's `hold`: the consumer's glue
            rides its prop onto the restored payload while measurement is still off. At the
            hold's end, `Restore` above 1 (the bridge's 3) goes to Await, anything else to Finish.
  Await     a calibration restore. An FBT calibration reloads the avatar on entering calibration
            mode, and until the user accepts, the client runs the animator but solves no
            constraint, so a placement the glue freezes then freezes at the serialized pose. The
            bridge writes 3 only for such a restore, at least 0.2 s after its 1, and 2 once the user
            has accepted. Flag up, Enable still off; `Restore` 2 goes to Settle. Enable switched
            on from the menu goes to Finish, and so does RELEASE_TIMEOUT_SECS with no 2.
  Settle    the hold again, flag still up, so the glue's placement settles on solving constraints
            before the flag falls; then Finish.
  Finish    sets Enable from the mirror, writes Restore 0 and lowers the flag. The copy and the
            set are two drivers, and both run on entry to this one state, so the glue sees the
            flag fall in the same evaluation Enable returns. On an expired window the mirror
            holds the reset's default, so the avatar boots as it would with no bridge.
  Mirror On / Mirror Off
            idle. Each keeps the mirror, re-entered whenever Enable changes, so the mirror is
            only ever written here and the layer's own Enable-off is never recorded. A non-zero
            Restore arriving here (a late or doubled 1, or a 3 or 2 after the layer moved on)
            re-enters the state, which puts the mirror back and returns Restore to 0.

Every state in the exchange has an exit that no value on the wire can withhold, timed or
unconditional, so a late, doubled or missing write delays the boot by the window at most. The one
longer wait is Await's, entered only on the bridge's 3 and left at RELEASE_TIMEOUT_SECS at most.

WHAT THE CONSUMER OWNS
----------------------
The payload names and their declarations, which of them mean "a prop is placed", Enable and its
declaration, the flag's name (under `internal`, outside the namespace, because every name under
the namespace that is not reserved is payload and would be restored), and the hold. Its glue
gains a place state per prop, entered from its Enable-off state while the flag is up and that
prop is placed, and left for its dropped state when the flag falls. It merges this controller
through the SAME FullController component as its glue, so the flag's instance prefix unifies.

CONFIG
------
Every key but `id` is required; `validate()` refuses a config missing any, naming each.

  namespace  `BridgePersist/<Name>`, the root the bridge watches; the four reserved leaves (Id,
             Announce, Boot, Restore) and the mirror, `<namespace>/Enabled` (the enable state,
             declared with Enable's default), are declared here and nowhere else.
  internal   the prefix for the layer's own local names (the flag). Required rather than
             defaulted so the collapsed shape, local names inside a published root, is not
             reachable by omission (docs/gimmicks.md §Packaging and interface).
  controller the emitted controller's name.
  id         the declared default of `<namespace>/Id`, 1..255 so every tool carries it as a
             byte; None mints one from the namespace. 0 switches the exchange off.
  enable     (name, spec): the consumer's enable parameter and its declaration, verbatim.
  payload    [(name, spec)]: every payload name the reset writes, each with its declaration
             verbatim, in the order to declare them. Each must sit under the namespace.
  placed     the payload names (bools) whose truth means a prop is placed and worth holding for.
  hold       seconds the flag stays up.
"""

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The wire contract's avatar-side constants (protocol version 3). The bridge's own waits, from
# Boot to its validity decision and from its last payload write to Restore 1, are the bridge's;
# they fit inside this window, which is why it is a contract value and not a consumer knob.
WINDOW_SECS = 1.0
# The longest Await waits for the bridge's release (Restore 2). Above the bridge's own limit on
# that wait, so a bridge that gives up never leaves the avatar holding on a release it will not send.
RELEASE_TIMEOUT_SECS = 120.0
RESERVED = ("Id", "Announce", "Boot", "Restore")
STEP_SECS = 0.02   # a carrier just long enough that exitTime 1.0 leaves on the next evaluation

CONFIG = {
    "namespace": "BridgePersist/Example",
    "internal": "Persist/Example",
    "controller": "BridgePersist_Example_Fx",
    "id": None,
    "enable": ("Example/Enable", "{ type: bool, default: true, vrc: { synced: true, saved: false } }"),
    "payload": [
        ("BridgePersist/Example/Placed", "{ type: bool, default: false, vrc: { synced: true, saved: false } }"),
        ("BridgePersist/Example/Value", "{ type: float, default: 0, vrc: { synced: false, saved: false } }"),
    ],
    "placed": ["BridgePersist/Example/Placed"],
    "hold": 0.5,
}
REQUIRED = ("namespace", "internal", "controller", "enable", "payload", "placed", "hold")


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


def minted_id(namespace):
    """A function of the namespace alone, so it is stable across regenerations; kept inside 1..255."""
    return int(hashlib.sha256(namespace.encode()).hexdigest(), 16) % 255 + 1


def spec_type_default(name, spec):
    """(animator type, default as a driver value) from a declaration: shorthand or longform."""
    s = spec.split("#", 1)[0].strip()
    if s in ("bool", "int", "float"):
        return s, 0
    t = re.search(r"\btype:\s*(bool|int|float)\b", s)
    if not s.startswith("{") or not t:
        refuse(f"{name}: cannot read a type from the declaration {spec!r}.")
    d = re.search(r"\bdefault:\s*([^,}\s]+)", s)
    v = d.group(1) if d else "0"
    if v in ("true", "false"):
        v = 1 if v == "true" else 0
    else:
        v = float(v)
        v = int(v) if v == int(v) else v
    return t.group(1), v


def fmt(v):
    return str(v) if not isinstance(v, float) else repr(v)


def validate(c):
    missing = [k for k in REQUIRED if k not in c]
    if missing:
        refuse(f"{', '.join(f'`{k}`' for k in missing)} missing: every key but `id` is required.")
    ns = c.get("namespace")
    for k in ("namespace", "internal"):
        if not isinstance(c.get(k), str) or not c[k]:
            refuse(f"`{k}` is required: a bare parameter path.")
        if c[k] != c[k].strip("/") or "//" in c[k] or "*" in c[k] or any(ch.isspace() for ch in c[k]):
            refuse(f"`{k}` {c[k]!r}: a bare parameter path, no leading or trailing '/', no empty segment, "
                   "no '*' and no whitespace.")
    if not ns.startswith("BridgePersist/") or ns.count("/") != 1:
        refuse(f"namespace {ns!r}: it must be `BridgePersist/<Name>`, one segment under the root the bridge watches.")
    inner = c["internal"]
    if inner == ns or inner.startswith(ns + "/") or ns.startswith(inner + "/"):
        refuse(f"internal {inner!r} overlaps the namespace {ns!r}: every name under the namespace that is not "
               "reserved is payload, so a flag there would be restored by the bridge.")
    en, en_spec = c["enable"]
    if en.startswith(ns + "/"):
        refuse(f"enable {en!r} sits under the namespace; the bridge would write it back mid-exchange.")
    reserved = {f"{ns}/{r}" for r in RESERVED}
    mirror = f"{ns}/Enabled"
    names = [n for n, _ in c["payload"]]
    if len(set(names)) != len(names):
        refuse(f"payload names repeat: {sorted({n for n in names if names.count(n) > 1})}.")
    for n in names:
        if not n.startswith(ns + "/"):
            refuse(f"payload name {n!r} is outside the namespace {ns!r}; the bridge carries only names under it.")
        if n in reserved:
            refuse(f"payload name {n!r} is a reserved name of the wire contract.")
        if n.startswith(inner + "/"):
            refuse(f"payload name {n!r} sits under internal {inner!r}.")
    if mirror in names:
        refuse(f"the mirror {mirror!r} is declared by this layer; leave it out of `payload`.")
    types = {n: spec_type_default(n, s) for n, s in c["payload"]}
    if not c["placed"]:
        refuse("`placed` names no payload name; the layer would never hold and the glue never place.")
    for n in c["placed"]:
        if n not in types or types[n][0] != "bool":
            refuse(f"placed name {n!r} is not a bool payload name.")
    # bool is an int subclass, and a True here would emit as 1.
    if not (isinstance(c["hold"], (int, float)) and not isinstance(c["hold"], bool) and c["hold"] > 0):
        refuse(f"hold {c['hold']!r}: a positive number of seconds.")
    ident = minted_id(ns) if c.get("id") is None else c["id"]
    if not (isinstance(ident, int) and not isinstance(ident, bool) and 0 <= ident <= 255):
        refuse(f"id {ident!r}: an int in 0..255, 0 meaning off.")
    en_type = spec_type_default(en, en_spec)
    if en_type[0] == "int":
        refuse(f"enable {en!r} is declared int; the layer reads it as a bool or a float.")
    return ident, mirror, types, en_type


def flag_name(c):
    return f"{c['internal']}/Hold"


def document(c):
    """(controller.yaml text, facts). Pure: a function of the config alone."""
    ident, mirror, types, (en_type, en_default) = validate(c)
    ns, en, en_spec = c["namespace"], c["enable"][0], c["enable"][1]
    ID, ANNOUNCE, BOOT, RESTORE = (f"{ns}/{r}" for r in RESERVED)
    FLAG = flag_name(c)
    mirror_default = "true" if en_default >= 0.5 else "false"
    en_on, en_off = ((f"{en} greater 0.5", f"{en} less 0.5") if en_type == "float"
                     else (f"{en} is true", f"{en} is false"))
    reset = {n: v for n, (_, v) in types.items()}
    reset[mirror] = 1 if en_default >= 0.5 else 0
    reset_s = ", ".join(f"{n}: {fmt(v)}" for n, v in reset.items())
    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by bridge-persist/generate.py; never hand-edit it, re-run the generator.")
    o("# The avatar side of the bridge's persistence exchange (wire contract version 3), as one layer merged through the consumer's")
    o("# FullController beside its glue. generate.py's docstring is the state-by-state design record.")
    o(f"# Namespace {ns}: Id, Announce, Boot, Restore reserved; every other name under it is payload and is reset here.")
    o(f"# Flag {FLAG}: local, outside the namespace, raised for the hold; the consumer's glue places from the payload while it is up.")
    o(f"# Id default {ident}: a variant declares its own in a controller listed first in both FullController lists; 0 switches this layer off.")
    o("")
    o("schema: 1")
    o(f"controller: {c['controller']}")
    o("basis: mount-root")
    o("role: fx")
    o("")
    o("defaults:")
    o("  writeDefaults: on")
    o("  transition: { duration: 0, exitTime: none, interruption: none }")
    o("")
    o("parameters:")
    o(f"  {ID}: {{ type: int, default: {ident}, vrc: {{ synced: false, saved: false }} }}   # the prefab's identity, carried as the default")
    o(f"  {ANNOUNCE}: {{ type: int, default: 0, vrc: {{ synced: false, saved: false }} }}   # a copy of Id, written with Boot")
    o(f"  {BOOT}: {{ type: float, default: 0, vrc: {{ synced: false, saved: false }} }}   # a random in (0, 1], once per load")
    o(f"  {RESTORE}: {{ type: int, default: 0, vrc: {{ synced: false, saved: false }} }}   # the bridge writes 1 after the payload, 3 to hold a calibration restore, 2 to release it; rests at 0")
    o(f"  {mirror}: {{ type: bool, default: {mirror_default}, vrc: {{ synced: false, saved: false }} }}   # payload: the enable state; default Enable's")
    for n, s in c["payload"]:
        o(f"  {n}: {s.split('#', 1)[0].strip()}")
    o(f"  {en}: {en_spec}")
    o(f"  {FLAG}: {{ type: bool, default: false, scratch: true }}   # local, never published: up for the hold")
    o("  IsLocal: bool")
    o("")
    o("layers:")
    o("  - name: Persist")
    o("    states:")
    o("      # A remote, and a wearer at Id 0, stay here for the session. Level rung: IsLocal lands after the entry rungs run.")
    o("      Load:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Quiesce, when: [ IsLocal is true, {ID} notEqual 0 ] }}")
    o("      Quiesce:")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {en}: 0, {reset_s} }} }}")
    o("        motion: { clip: step }")
    o("        transitions:")
    o("          - { to: Boot, when: [ ], exitTime: 1.0 }")
    o("      # The first writing state's writes do not reach the client's parameters, so the quiesce and the reset are written again here.")
    o("      Boot:")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, copy: {{ {ANNOUNCE}: {ID} }} }}")
    o(f"          - driver: {{ localOnly: true, random: {{ {BOOT}: {{ min: 0.001, max: 1 }} }} }}")
    o(f"          - driver: {{ localOnly: true, set: {{ {en}: 0, {reset_s} }} }}")
    o("        motion: { clip: step }")
    o("        transitions:")
    o("          - { to: Wait, when: [ ], exitTime: 1.0 }")
    o("      # The window, entered the evaluation after Boot's write so a load hitch on that frame cannot spend it.")
    o("      Wait:")
    o("        motion: { clip: window }")
    o("        transitions:")
    for p in c["placed"]:
        o(f"          - {{ to: Hold,   when: [ {RESTORE} greater 0, {p} is true ] }}")
    o(f"          - {{ to: Finish, when: [ {RESTORE} greater 0 ] }}   # restored, nothing placed: no hold")
    o("          - { to: Finish, when: [ ], exitTime: 1.0 }   # no bridge, or nothing to restore")
    o("      Hold:")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, set: {{ {FLAG}: 1 }} }}")
    o("        motion: { clip: hold }")
    o("        transitions:")
    o(f"          - {{ to: Await,  when: [ {RESTORE} greater 1 ], exitTime: 1.0 }}   # a calibration restore: hold until released")
    o("          - { to: Finish, when: [ ], exitTime: 1.0 }   # a swap restore")
    o("      # Flag up, Enable still off, until the bridge's release: after a calibration reload the client solves no constraint until the user accepts.")
    o("      Await:")
    o("        motion: { clip: release }")
    o("        transitions:")
    o(f"          - {{ to: Settle, when: [ {RESTORE} equals 2 ] }}   # the bridge's release: the user accepted")
    o(f"          - {{ to: Finish, when: [ {en_on} ] }}   # Enable switched on from the menu")
    o("          - { to: Finish, when: [ ], exitTime: 1.0 }   # no release: give up")
    o("      # The consumer's hold again, flag still up, so the placement settles on solving constraints before the flag falls.")
    o("      Settle:")
    o("        motion: { clip: hold }")
    o("        transitions:")
    o("          - { to: Finish, when: [ ], exitTime: 1.0 }")
    o("      # Two drivers, both run on entry to this one state: the glue sees the flag fall in the evaluation Enable returns.")
    o("      Finish:")
    o("        behaviours:")
    o(f"          - driver: {{ localOnly: true, copy: {{ {en}: {mirror} }} }}")
    o(f"          - driver: {{ localOnly: true, set: {{ {RESTORE}: 0, {FLAG}: 0 }} }}")
    o("        motion: { clip: step }")
    o("        transitions:")
    o(f"          - {{ to: Mirror On,  when: [ {en_on} ], exitTime: 1.0 }}")
    o("          - { to: Mirror Off, when: [ ], exitTime: 1.0 }")
    o("      # Idle. The mirror is written only here; a late or doubled Restore, or a late 3 or 2, re-enters, restoring the mirror and Restore 0.")
    for name, val, other, cond in (("Mirror On", 1, "Mirror Off", en_off), ("Mirror Off", 0, "Mirror On", en_on)):
        o(f"      {name}:")
        o("        behaviours:")
        o(f"          - driver: {{ localOnly: true, set: {{ {mirror}: {val}, {RESTORE}: 0 }} }}")
        o("        motion: ~")
        o("        transitions:")
        o(f"          - {{ to: {other}, when: [ {cond} ] }}")
        o(f"          - {{ to: {name}, when: [ {RESTORE} equals 1 ] }}")
        o(f"          - {{ to: {name}, when: [ {RESTORE} greater 1 ] }}")
    o("    default: Load")
    o("    layout:")
    o("      nodes: { Load: [30, 180], Quiesce: [30, 250], Boot: [30, 320], Wait: [30, 390], Hold: [270, 460], "
      "Await: [510, 460], Settle: [270, 530], Finish: [30, 530], Mirror On: [-90, 600], Mirror Off: [150, 600] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o("clips:")
    o(f"  step: {{ seconds: {STEP_SECS} }}")
    o(f"  window: {{ seconds: {WINDOW_SECS} }}   # WINDOW_SECS, the wire contract's")
    o(f"  hold: {{ seconds: {fmt(c['hold'])} }}   # CONFIG's hold")
    o(f"  release: {{ seconds: {RELEASE_TIMEOUT_SECS} }}   # RELEASE_TIMEOUT_SECS, the wire contract's")
    facts = {"id": ident, "flag": FLAG, "controller": c["controller"], "payload": list(reset), "hold": c["hold"]}
    return "\n".join(L) + "\n", facts


def main():
    text, f = document(CONFIG)
    with open(os.path.join(HERE, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote controller.yaml: {f['controller']}, Id {f['id']}, {len(f['payload'])} payload names, flag {f['flag']}")


if __name__ == "__main__":
    main()
