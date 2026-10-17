#!/usr/bin/env python3
"""leash-stake generator: emits the leash's controller, its object-sync build and rig.json from CONFIG.

    python leash-stake/generate.py                  # writes controller.yaml, object-sync/controller.yaml, rig.json
    python leash-stake/generate.py --check          # asserts LeashStake.prefab's hand-maintained surface
    python leash-stake/generate.py --config C --out D   # a consumer's strand: C's keys over CONFIG, written to D
    python leash-stake/generate.py --config C --check-prefab P   # a consumer's flattened prefab against C

A consumer keeps its strand's keys in a JSON file beside its own built/ and drives this generator
unmodified; it shares this entry's object-sync build, so `rigSeed` is not a consumer key.

Edit CONFIG, rerun, then recompile both built/ folders as a unit in a mounting Editor (CONVENTIONS.md
§The gate). Every output is a pure function of CONFIG. controller.yaml is the leash's FX (the machine
and the wearer's announce); object-sync/controller.yaml is a position-only `object-sync` build driven
through that entry's generator unmodified; rig.json is every number the prefab is built to. Nothing
here writes Unity assets: `--check` holds the prefab to CONFIG afterwards.

WHAT THE RIG IS
---------------
An existing strand (a collar chain, the demo's rope) becomes a leash. The strand keeps its own physbone,
grabbing off; nothing of ours sits under it. A hand grabs our handle instead, homed at a point on the strand.

  Mount     MA BoneProxy onto the bone the strand hangs from (the demo: the Neck).
  Start     a child of Mount at the strand's first bone's rest pose: the socket.
  Home      a static child of Start at a point on the strand as it settles in play, `homeAt` of the way
            from the socket to the tip: the handle's root, so a grab there takes the handle. Never under a strand bone:
            the line would write that bone onto the handle's tip, the handle's own child, and the root
            would chase its tip a bone length a frame.
  Holder    parent of the handle; two sources, Home (free, held) and Stake (planted); FreezeToWorld
            animated (frozen through a pick-up, so no root moves under the live grab).
  HB0/HTip  the handle: a one-bone grabbable, posable physbone `<prefix>/Handle`, collision off.
  Far       position-constrained to HTip.
  Stake     position-constrained to Far, and to object-sync's reconstruction on a remote; FreezeToWorld
            captures it at a plant. The line and the sensing read Stake, never Far: Far solves before
            Holder in the Holder <- Stake <- Far <- HTip cycle, so sourcing Far flashes the line to the
            collar for the plant frame.
  Mid       under Stake, position-constrained to the Start/Stake midpoint; its child P0 is the pendulum, a
            one-bone physbone pointing straight down to PTip (twice `rope.sag` long), grabbing, posing and
            collision off. It runs on every client, so every copy swings.
  Ctrl      under Stake, position-constrained to [PTip, Mid]; the Rope layer slides the weights from the tip
            (close in) to the plain midpoint (at `rope.taut`): the curve's control point.
  Line      under Stake at its origin, aimed at Ctrl along -Z. Its children are the curve's joints: J0 on
            Start, the last joint a static child one last-bone length back from Stake toward Ctrl (so the
            last bone's visible end lands on Stake, along the curve's end tangent), the joints between on
            the quadratic Bezier [Start, Ctrl, last joint] at their share of the rest length. Every joint
            but the last aims at the next one, world up. Line, Mid and Ctrl ride under Stake so Stake's
            constraint solves before theirs: beside it they read Stake a frame late.
  span      a sphere receiver on Line/J0 (radius taut - senderRadius) and a sender on Stake, not local-only,
            allow-self only, on `<tag>Span`: `<internal>/Span` reads the Start-Stake distance on every client.
  strand    each bone takes one parent constraint, sources itself and its joint, weights animated:
            (1, 0) free, (0, 1) held and planted. Self at 1 writes back the bone's own solved pose, a
            no-op; the physbone keeps solving underneath, so a release fades onto the strand's own
            current physics.
  Sense     the level carrier: position from Start, rotation from the avatar root's yaw (it rides the
            prefab root). Three local face-proximity boxes, Right, Forward and Up; SenseProxy carries the
            sender 1/ratio of the way from Sense to Stake.

THE MACHINE (layer `<prefix>`)
-----------------------------
  Load      the default, on the Disabled clip; clears Held and Planted and hands on to Free or Disabled, so
            neither clear rests on the first state after a load (docs/runtime.md §Parameters).
  Disabled  enable off: the handle off, the sensing stowed, the strand free; clears the handle's stale
            grab flags (a disabled physbone holds them).
  Free      Holder on Home, the strand free.
  Held      the strand on the line. Entered and left with a `fade`-frame transition blend.
            _IsPosed is read as a level when _IsGrabbed falls, never as an edge.
  Plant     `cycle` seconds: Stake freezes, Holder onto Stake, the handle component off; resetWhenDisabled
            then rests the handle at the stake with its pose cleared.
  Planted   Stake frozen, Holder on Stake, the handle live and grabbable at the stake. `<prefix>/Unplant`
            (the wearer's button, unsynced) fades it Free. A remote that saw the plant goes Free if
            <internal>/Announce is still false `announce` + REMOTE_WAIT seconds in: the wearer unplanted
            before the flag rose. A flag that arrives later still engages SyncPlanted from Free.
  PHeld     a pick-up: Stake unfrozen and on the hand, Holder frozen where the stake stood.
  SyncPlanted  a remote's plant: Stake unfrozen and on object-sync's reconstruction. Engaged from Free
            (a late joiner, with the fade) or Planted (a client that saw the plant), on
            !IsLocal AND <internal>/Announce AND ObjectSync/Enable AND OS/Ready. A grab there is a
            pick-up (PHeld); the flag falling with no grab seen goes Free.
Every state keys every binding the layer owns (work under either Write Defaults mode).
Held is 1 in Held and PHeld; Planted is 1 in Plant, Planted and SyncPlanted; both 0 elsewhere.

`SelfGrab` (layer `SelfGrab`): `<prefix>/SelfGrab`, unsynced, writes the handle's grabFilter.allowSelf and
poseFilter.allowSelf. Only the wearer's own client tests the self case, so no bit rides the wire.

`Rope` (layer `Rope`, every client): one 1D blend on `<internal>/Span` writing Ctrl's two weights, sampled from
the sag table in rig.json (a rope of length `taut` hanging as a parabola, capped at `sag`).

`Announce` (wearer only): `<internal>/Announce`, the one synced bool this entry adds besides the enables,
rises `announce` seconds after `<prefix>/Planted` does and falls with it, so a pick-up drops it. The dwell outlasts a plant-to-remote object-sync refresh, so a
remote reading it true with OS/Ready holds a word table that already carries the stake.

CONFIG
------
  prefix        the published prefix; the bridge's `LeashSettings.prefix`.
  internal      the internal prefix (required): no published wildcard may reach it.
  controller    the emitted controller's name.
  tag, boxSize, senderRadius, ratio   the sensing geometry; the bridge's span, sender_radius, ratio.
  slackRange    the bridge's `LeashSettings.slack_min`/`slack_max`, metres: a slack radial's 0..1 spans it.
  slack, slackPlanted   metres of free travel before the bridge pulls, held and planted: the defaults of
                `<prefix>/Slack` and `<prefix>/SlackPlanted`, emitted as fractions of slackRange.
  selfGrabDefault   `<prefix>/SelfGrab`'s default: the wearer may grab and pose their own handle.
  mount         the humanoid bone Mount's BoneProxy targets on the demo.
  mountRot      Mount's rest rotation against the avatar root (Unity Euler degrees); frames world up.
  chain         the strand's bones, root first: each one's binding path (from the prefab root, or
                '/'-rooted from the avatar root), local position and rotation (Unity Euler degrees).
                Bone 0's pose is in Mount's frame, and becomes Start's.
  endpoint      the last bone's endpoint offset, as its physbone's endpointPosition: its visible end.
  homeAt        where Home sits along the strand, a fraction of its length from the socket (1 is the tip).
  home          Home's local pose under Start as measured on the settled strand, or None for the point
                `homeAt` along the rest pose.
  handle        the handle physbone's settings; FIXED_HANDLE holds what makes it a handle.
  rope          the curve: `sag` (metres below the chord close in), `taut` (the span where it runs straight),
                the pendulum's `pull` and `spring` (FIXED_PENDULUM holds the rest), the span sender's radius.
  fade          frames of the strand's transition blend each way.
  cycle         seconds the plant holds the handle off.
  announce      seconds from Planted to the synced flag.
  rigSeed       this build's object-sync tags and park; differs from every other object-sync build.
  enableDefault `<prefix>/Enable`'s default (synced, saved).
"""

import importlib.util
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
OS_GEN = os.path.join(ROOT, "object-sync", "generate.py")
SYNC_OUT = os.path.join(HERE, "object-sync", "controller.yaml")
FRAME = 1 / 60

CONFIG = {
    "prefix": "Leash",
    "internal": "LeashStake",
    "controller": "LeashStake_Fx",
    "tag": "LeashSense",
    "boxSize": 6.0,
    "senderRadius": 0.05,
    "ratio": 10,
    "slackRange": (0.5, 4.0),
    "slack": 1.5,
    "slackPlanted": 2.5,
    "selfGrabDefault": True,
    "mount": "Neck",
    "mountRot": (0, 0, 0),
    # The demo's rope (assets/Leash.fbx, unpacked under Mount at local zero): its Collar bone's frame is Mount's.
    "chain": [
        {"bone": "Mount/Leash/Armature/Collar/V0", "pos": (0, -0.015, 0.0652), "rot": (165, 0, 0)},
        {"bone": "Mount/Leash/Armature/Collar/V0/V1", "pos": (0, 0.3, 0)},
        {"bone": "Mount/Leash/Armature/Collar/V0/V1/V2", "pos": (0, 0.3, 0)},
        {"bone": "Mount/Leash/Armature/Collar/V0/V1/V2/V3", "pos": (0, 0.3, 0)},
    ],
    "endpoint": (0, 0.165, 0),
    # The midpoint: a hand reaching for the strand anywhere along it is near it, however the strand swings.
    "homeAt": 0.5,
    "home": None,
    # pull and spring are the release's feel: how fast the line retracts with the handle after a plain release.
    "handle": {"length": 0.05, "radius": 0.05, "maxStretch": 100, "pull": 0.2, "spring": 0.2, "stiffness": 0.2},
    # The held and planted curve. sag: how far the curve's middle hangs below the straight line at close spans;
    # taut: the Start-to-Stake span at which it runs straight; between, it fades as a rope of length `taut` would.
    # pull and spring are the pendulum's swing (spring is the overshoot); senderRadius the span contact's sender.
    "rope": {"sag": 0.3, "taut": 1.5, "pull": 0.2, "spring": 0.98, "senderRadius": 0.02},
    "fade": 10,
    "cycle": 0.05,
    "announce": 2.0,
    "rigSeed": "leash-stake/g1",
    "enableDefault": True,
}

# What makes the handle a handle, whatever its feel. Grabbing and posing are Other so the filters are read;
# both filters bake allowSelf and allowOthers on, and the SelfGrab layer animates allowSelf.
FIXED_HANDLE = {"gravity": 0.0, "grabMovement": 1.0, "allowGrabbing": "Other", "allowPosing": "Other",
                "allowCollision": "False", "resetWhenDisabled": True, "isAnimated": False,
                "integrationType": "Simplified", "limitType": "None"}
# What makes the pendulum a pendulum: it hangs straight down from the midpoint (gravity is inert on a rest pointing
# down; pull is the restoring force and spring the momentum), nothing grabs, poses or collides with it.
FIXED_PENDULUM = {"gravity": 1.0, "stiffness": 0.0, "radius": 0.0, "allowGrabbing": "False", "allowPosing": "False",
                  "allowCollision": "False", "isAnimated": False, "integrationType": "Simplified", "limitType": "None",
                  "parameter": ""}
# Unity HumanBodyBones values the demo Mount's BoneProxy may target.
HUMAN = {"Hips": 0, "Spine": 7, "Chest": 8, "Neck": 9, "Head": 10, "UpperChest": 54}
# Box shape rotations putting each face-proximity box's +Z face on the carrier's named axis.
AXES = (("Right", (0, 90, 0)), ("Forward", (0, 0, 0)), ("Up", (270, 0, 0)))
SYNC_MOUNT = "ObjectSync"
# Everything that reads Stake's position rides under it: a constraint on an ancestor's target solves first, so
# the curve never reads Stake a frame late (beside Stake, the line ran one frame of the wearer's travel behind it).
LINE, MID, CTRL = "Stake/Line", "Stake/Mid", "Stake/Ctrl"
# Seconds past `announce` a remote's Planted waits for the flag before taking an unplant as read.
REMOTE_WAIT = 1.0


def refuse(msg):
    raise SystemExit(f"REFUSE: {msg}")


# ---- quaternion helpers (x, y, z, w), Unity conventions ----
def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qaxis(axis, deg):
    h = math.radians(deg) / 2
    s = math.sin(h)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h))


def euler(e):
    """Unity's Quaternion.Euler: Z, then X, then Y (q = qy * qx * qz)."""
    return qmul(qmul(qaxis((0, 1, 0), e[1]), qaxis((1, 0, 0), e[0])), qaxis((0, 0, 1), e[2]))


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def rot(q, v):
    return qmul(qmul(q, (v[0], v[1], v[2], 0.0)), qinv(q))[:3]


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return tuple(x / n for x in a)


def from_basis(r, u, f):
    """The quaternion whose columns are (r, u, f): it maps X->r, Y->u, Z->f."""
    m = ((r[0], u[0], f[0]), (r[1], u[1], f[1]), (r[2], u[2], f[2]))
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1) * 2
        return ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2
        return (s / 4, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2
        return ((m[0][1] + m[1][0]) / s, s / 4, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2
    return ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, s / 4, (m[1][0] - m[0][1]) / s)


def look(f, up=(0, 1, 0)):
    """Quaternion.LookRotation(f, up)."""
    f = norm(f)
    if abs(dot(f, norm(up))) > 0.999:
        up = (0, 0, 1)
    r = norm(cross(up, f))
    return from_basis(r, cross(f, r), f)


def fromto(a, b):
    """The minimal rotation taking direction a onto direction b (Quaternion.FromToRotation)."""
    a, b = norm(a), norm(b)
    c = dot(a, b)
    if c < -0.999999:
        ax = cross((1, 0, 0), a) if abs(a[0]) < 0.9 else cross((0, 1, 0), a)
        return qaxis(norm(ax), 180)
    x, y, z = cross(a, b)
    return tuple(v / math.sqrt(2 * (1 + c)) for v in (x, y, z, 1 + c))


def to_euler(q):
    """Unity eulerAngles (degrees) of q, for the prefab's Euler hint; the check compares quaternions."""
    x, y, z, w = q
    sx = 2 * (w * x - y * z)
    ex = math.degrees(math.asin(max(-1, min(1, sx))))
    ey = math.degrees(math.atan2(2 * (w * y + x * z), 1 - 2 * (x * x + y * y)))
    ez = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (x * x + z * z)))
    return tuple(round(v % 360, 4) for v in (ex, ey, ez))


def r6(v):
    return tuple(round(x, 6) for x in v)


# ---- the geometry ----
def validate(c):
    n = len(c["chain"])
    if n < 2:
        refuse("chain needs at least two bones: the line spreads its joints between the first and the last.")
    for k in ("prefix", "internal"):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", c.get(k) or ""):
            refuse(f"{k} is one bare name segment, required.")
    if c["internal"] == c["prefix"] or c["internal"].startswith(c["prefix"] + "/"):
        refuse("internal may not sit under prefix: the published wildcard would reach it.")
    if not 0 < c["senderRadius"] < c["boxSize"] / 2:
        refuse("senderRadius must be positive and smaller than half the box.")
    if c["boxSize"] > 6:
        refuse("boxSize above 6: the SDK editor caps a contact shape at 6 units.")
    if not (isinstance(c["ratio"], (int, float)) and c["ratio"] >= 1):
        refuse("ratio must be 1 or more (1 senses Stake itself).")
    if not (isinstance(c["fade"], int) and c["fade"] >= 1):
        refuse("fade is a whole number of frames, at least 1.")
    if c["mount"] not in HUMAN:
        refuse(f"mount is one of {sorted(HUMAN)}: the demo's BoneProxy targets a humanoid bone; a consumer retargets it by hand.")
    if not c["announce"] > 0:
        refuse("announce is seconds from the plant to the synced bool, positive; it must also outlast an object-sync "
               "measure cycle and a wire refresh, which this cannot check.")
    if c["cycle"] < 3 * FRAME - 1e-9:
        refuse("cycle under 3 frames: the handle must stay off across at least one physbone step at any frame rate.")
    if not 0 < c["homeAt"] <= 1:
        refuse("homeAt is a fraction of the strand's length from the socket, above 0 and at most 1.")
    if c["handle"]["length"] <= 0 or c["handle"]["radius"] <= 0:
        refuse("handle length and radius are positive.")
    if length(c["endpoint"]) <= 0:
        refuse("endpoint is the last bone's visible end; a zero endpoint leaves the last bone no length to place.")
    if len({b["bone"] for b in c["chain"]}) != n:
        refuse("chain bone paths repeat.")
    rp = c["rope"]
    if not (rp["sag"] > 0 and rp["taut"] > 0):
        refuse("rope sag and taut are positive metres.")
    if not 0 < rp["senderRadius"] < rp["taut"]:
        refuse("rope senderRadius is positive and under taut.")
    if rp["taut"] - rp["senderRadius"] > 3:
        refuse("rope taut minus senderRadius is the span receiver's radius, which the SDK caps at 3.")
    lo, hi = c["slackRange"]
    if not 0 <= lo < hi:
        refuse("slackRange is (min, max) metres, 0 <= min < max.")
    for k in ("slack", "slackPlanted"):
        if not lo <= c[k] <= hi:
            refuse(f"{k} lies in slackRange {c['slackRange']}: a radial cannot reach a default outside it.")


def geometry(c):
    """Poses in Mount's frame: each bone's position and rotation, the tip, and each segment's length."""
    pos, rq = [], []
    p, q = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    for i, b in enumerate(c["chain"]):
        p = add(p, rot(q, b["pos"])) if i else tuple(map(float, b["pos"]))
        q = qmul(q, euler(b.get("rot", (0, 0, 0)))) if i else euler(b.get("rot", (0, 0, 0)))
        pos.append(p)
        rq.append(q)
    tip = add(pos[-1], rot(rq[-1], c["endpoint"]))
    seg = [length(sub(pos[i + 1], pos[i])) for i in range(len(pos) - 1)] + [length(c["endpoint"])]
    # Each bone's rotation offset against its joint, whose frame is +Z along the line, +Y toward world up.
    # The reference frame is bone 0's segment framed world-up, carried bone to bone by the minimal rotation
    # between segments, so a strand lying straight keeps each bone's rest twist against its parent.
    M = euler(c["mountRot"])
    ends = pos[1:] + [tip]
    offs, F, dprev = [], None, None
    for i in range(len(pos)):
        d = rot(M, sub(ends[i], pos[i]))
        F = look(d) if F is None else qmul(fromto(dprev, d), F)
        dprev = d
        offs.append(qmul(qinv(F), qmul(M, rq[i])))
    return {"pos": pos, "rot": rq, "tip": tip, "seg": seg, "L": sum(seg), "offsets": offs}


def home_pose(c, g):
    """Home under Start: CONFIG's measured pose, else the point `homeAt` along the rest strand, the handle
    pointing along the segment it lands on."""
    if c["home"]:
        return tuple(c["home"]["pos"]), euler(c["home"].get("rot", (0, 0, 0)))
    ends = g["pos"][1:] + [g["tip"]]
    left = c["homeAt"] * g["L"]
    for k in range(len(ends)):
        if left <= g["seg"][k] + 1e-9 or k == len(ends) - 1:
            d = sub(ends[k], g["pos"][k])
            pt = add(g["pos"][k], tuple(x * left / g["seg"][k] for x in d))
            break
        left -= g["seg"][k]
    s_inv = qinv(g["rot"][0])
    return rot(s_inv, sub(pt, g["pos"][0])), look(rot(s_inv, d))


def joints(c, g):
    """The curve's joints under Line: name, and either position-constraint weights over [Start, Ctrl, last joint]
    (the quadratic Bezier's Bernstein terms at the joint's share of the rest length) plus the next joint it aims
    at, or the last joint's static local position (one last-bone length back from Stake toward Ctrl)."""
    n = len(c["chain"])
    span = g["L"] - g["seg"][-1]
    last = f"{LINE}/J{n - 1}"
    out = []
    cum = 0.0
    for k in range(n):
        if k == n - 1:
            out.append({"name": f"J{k}", "static": [0, 0, round(-g["seg"][-1], 6)]})
        elif k == 0:
            out.append({"name": "J0", "sources": ["Mount/Start"], "weights": [1.0], "aim": f"{LINE}/J{k + 1}"})
        else:
            t = cum / span
            out.append({"name": f"J{k}", "sources": ["Mount/Start", CTRL, last],
                        "weights": [round((1 - t) ** 2, 6), round(2 * t * (1 - t), 6), round(t * t, 6)],
                        "aim": f"{LINE}/J{k + 1}"})
        cum += g["seg"][k]
    return out


def sag_height(rp, s):
    """The curve's sag at span s: a rope of length taut hanging as a parabola (arc length s + 8h^2/3s), capped at
    sag, and held at that cap (or at the parabola's peak) closer in."""
    taut, sag = rp["taut"], rp["sag"]
    disc = taut * taut - 32 * sag * sag / 3
    s_hold = (taut + math.sqrt(disc)) / 2 if disc >= 0 else taut / 2
    s = max(s, s_hold)
    return 0.0 if s >= taut else min(sag, math.sqrt(3 * s * (taut - s) / 8)), s_hold


def rope_rig(c, g):
    """The pendulum, the control point and the span contact pair, with the sag table the Rope layer blends."""
    rp, p, I = c["rope"], c["prefix"], c["internal"]
    radius = rp["taut"] - rp["senderRadius"]
    _, s_hold = sag_height(rp, 0)
    spans = [s_hold + (rp["taut"] - s_hold) * u for u in (0, 0.25, 0.5, 0.7, 0.85, 0.95)] + [rp["taut"]]
    # The receiver reads 1 - (span - senderRadius) / radius: 0 at taut and beyond, 1 with the two on each other.
    table = [{"span": round(rp["senderRadius"], 6), "reading": 1.0, "weight": round(sag_height(rp, s_hold)[0] / rp["sag"], 6)}]
    for s in spans:
        table.append({"span": round(s, 6), "reading": round(1 - (s - rp["senderRadius"]) / radius, 6),
                      "weight": round(sag_height(rp, s)[0] / rp["sag"], 6)})
    table.sort(key=lambda e: e["reading"])
    pb = {"pull": rp["pull"], "spring": rp["spring"]}
    pb.update(FIXED_PENDULUM)
    return {
        "mid": {"path": MID, "sources": ["Mount/Start", "Stake"], "weights": [0.5, 0.5]},
        "pendulum": {"bone": f"{MID}/P0", "tip": f"{MID}/P0/PTip", "tipLocalPosition": [0, round(-2 * rp["sag"], 6), 0], "physbone": pb},
        "ctrl": {"path": CTRL, "sources": [f"{MID}/P0/PTip", MID], "weights": [1.0, 0.0]},
        "span": {"parameter": f"{I}/Span", "tag": f"{c['tag']}Span",
                 "receiver": {"path": f"{LINE}/J0", "radius": round(radius, 6)},
                 "sender": {"path": "Stake", "radius": rp["senderRadius"]}},
        "sag": {"height": rp["sag"], "taut": rp["taut"], "table": table},
    }


def sync_gen():
    if not os.path.exists(OS_GEN):
        refuse(f"{OS_GEN} is missing; this entry drives object-sync's generator unmodified.")
    spec = importlib.util.spec_from_file_location("object_sync_generate", OS_GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_config(c, og):
    cfg = dict(og.CONFIG)
    cfg["objects"] = [{"name": "Prop", "rotation": "none"}]
    cfg["mountPath"] = SYNC_MOUNT
    cfg["rigSeed"] = c["rigSeed"]
    return cfg


def global_params(c, og):
    """One wildcard per published prefix: this entry's, then object-sync's derived list."""
    return [f"{c['prefix']}/*"] + og.document(sync_config(c, og))[1]["facts"]["globalParams"]


def handle_physbone(c):
    h = c["handle"]
    pb = {"pull": h["pull"], "spring": h["spring"], "stiffness": h["stiffness"], "radius": h["radius"],
          "maxStretch": h["maxStretch"]}
    pb.update(FIXED_HANDLE)
    pb["parameter"] = f"{c['prefix']}/Handle"
    return pb


def rig(c, og):
    validate(c)
    g = geometry(c)
    hp, hq = home_pose(c, g)
    p = c["prefix"]
    reach = round(c["handle"]["length"] * (1 + c["handle"]["maxStretch"]), 3)
    return {
        "_comment": "GENERATED by leash-stake/generate.py from its CONFIG; never hand-edit. The numbers LeashStake.prefab is built to.",
        "prefix": p,
        "globalParams": global_params(c, og),
        "mount": c["mount"],
        "start": {"path": "Mount/Start", "localPosition": r6(g["pos"][0]), "localRotation": r6(g["rot"][0])},
        "home": {"path": "Mount/Start/Home", "localPosition": r6(hp), "localRotation": r6(hq), "localEuler": to_euler(hq)},
        "handle": {"physbone": handle_physbone(c), "tipLocalPosition": [0, 0, c["handle"]["length"]],
                   "reach": reach},
        "line": {"path": LINE, "aimAxis": [0, 0, -1], "upAxis": [0, 1, 0], "aimAt": CTRL, "jointAimAxis": [0, 0, 1], "joints": joints(c, g)},
        "rope": rope_rig(c, g),
        "strand": [{"path": b["bone"], "joint": f"{LINE}/J{k}", "jointRotationOffset": r6(to_euler(g["offsets"][k])),
                    "jointRotationOffsetQ": r6(g["offsets"][k]), "segment": round(g["seg"][k], 6)}
                   for k, b in enumerate(c["chain"])],
        "length": round(g["L"], 6),
        "sensing": {"tag": c["tag"], "boxSize": c["boxSize"], "senderRadius": c["senderRadius"],
                    "proxyWeights": [round(1 - 1 / c["ratio"], 6), round(1 / c["ratio"], 6)],
                    "decode": f"{c['ratio']} * ({c['boxSize']} * reading - ({c['boxSize'] / 2} + {c['senderRadius']}))",
                    "boxes": [{"parameter": f"{p}/{a}", "rotation": list(e)} for a, e in AXES]},
        "fade": c["fade"],
        "cycle": c["cycle"],
    }


# ---- the controller ----
def secs(frames):
    return round(frames * FRAME, 6)


def document(c, og):
    r = rig(c, og)
    p, I = c["prefix"], c["internal"]
    EN, HELD, PL, SLACK, SLACKP = f"{p}/Enable", f"{p}/Held", f"{p}/Planted", f"{p}/Slack", f"{p}/SlackPlanted"
    SELF, UNPLANT = f"{p}/SelfGrab", f"{p}/Unplant"
    lo, hi = c["slackRange"]
    frac = {k: round((c[k] - lo) / (hi - lo), 6) for k in ("slack", "slackPlanted")}
    IG, IP, FLAG = f"{p}/Handle_IsGrabbed", f"{p}/Handle_IsPosed", f"{I}/Announce"
    HOLD = "Holder/VRCParentConstraint"
    STK = "Stake/VRCPositionConstraint"
    PB = "Holder/HB0/VRCPhysBone.m_Enabled"
    FILTERS = [f"Holder/HB0/VRCPhysBone.{f}.allowSelf" for f in ("grabFilter", "poseFilter")]
    SENSE = "Sense/GameObject.m_IsActive"
    STRAND = [f"{s['path']}/VRCParentConstraint.Sources.source" for s in r["strand"]]

    def clip(home, hfrz, pb, sfrz, sync, line, sense):
        s = {f"{HOLD}.Sources.source0.Weight": home, f"{HOLD}.Sources.source1.Weight": 1 - home,
             f"{HOLD}.FreezeToWorld": hfrz, PB: pb, f"{STK}.FreezeToWorld": sfrz,
             f"{STK}.Sources.source0.Weight": 1 - sync, f"{STK}.Sources.source1.Weight": sync, SENSE: sense}
        for v in STRAND:
            s[v + "0.Weight"] = 1 - line
            s[v + "1.Weight"] = line
        return s

    clips = {
        "disabled": (None, clip(1, 0, 0, 0, 0, 0, 0)),
        "free": (None, clip(1, 0, 1, 0, 0, 0, 1)),
        "held": (None, clip(1, 0, 1, 0, 0, 1, 1)),
        "plant": (c["cycle"], clip(0, 0, 0, 1, 0, 1, 1)),
        "planted": (None, clip(0, 0, 1, 1, 0, 1, 1)),
        "pheld": (None, clip(0, 1, 1, 0, 0, 1, 1)),
        "sync_planted": (None, clip(0, 0, 1, 0, 1, 1, 1)),
        "self_on": (None, {f: 1 for f in FILTERS}),
        "self_off": (None, {f: 0 for f in FILTERS}),
    }
    CTRLW = f"{CTRL}/VRCPositionConstraint.Sources.source"
    sag = r["rope"]["sag"]["table"]
    for k, e in enumerate(sag):
        clips[f"sag{k}"] = (None, {CTRLW + "0.Weight": e["weight"], CTRLW + "1.Weight": round(1 - e["weight"], 6)})
    fade = secs(c["fade"])

    L = []
    o = L.append
    o(f"# {c['controller']} — GENERATED by leash-stake/generate.py; edit its CONFIG and rerun, never hand-edit this file.")
    o("# The leash's machine and the wearer's announce. generate.py's docstring is the state-by-state record; rig.json the prefab's numbers.")
    o(f"# Published, bare (globalParams): {', '.join(r['globalParams'])}. {HELD} is 1 in Held and PHeld, {PL} in Plant,")
    o(f"# Planted and SyncPlanted, both latching. {EN} is the one synced menu intent; {FLAG} the synced announce.")
    o(f"# Fade {c['fade']} frames, plant cycle {c['cycle']} s, announce {c['announce']} s. Strand rest length {r['length']} m.")
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
    o(f"  {EN}: {{ type: bool, default: {'true' if c['enableDefault'] else 'false'}, vrc: {{ synced: true, saved: true }} }}")
    for a, _ in AXES:
        o(f"  {p}/{a}: {{ type: float, vrc: {{ synced: false, saved: false, osc: true }} }}   # face-proximity box, sensing")
    o(f"  {HELD}: {{ type: bool, vrc: {{ synced: false, saved: false, osc: true }} }}   # latching, driven here")
    o(f"  {PL}: {{ type: bool, vrc: {{ synced: false, saved: false, osc: true }} }}   # latching, driven here")
    o(f"  {SLACK}: {{ type: float, default: {frac['slack']}, vrc: {{ synced: false, saved: true, osc: true }} }}   # held slack, 0..1 over the bridge's {lo}-{hi} m")
    o(f"  {SLACKP}: {{ type: float, default: {frac['slackPlanted']}, vrc: {{ synced: false, saved: true, osc: true }} }}   # planted slack, the same range")
    o(f"  {SELF}: {{ type: bool, default: {'true' if c['selfGrabDefault'] else 'false'}, vrc: {{ synced: false, saved: true }} }}   # the wearer may grab their own handle")
    o(f"  {UNPLANT}: {{ type: bool, vrc: {{ synced: false, saved: false }} }}   # the wearer's button")
    o(f"  {IG}: {{ type: bool, vrc: {{ synced: false, saved: false }} }}   # the handle physbone")
    o(f"  {IP}: {{ type: bool, vrc: {{ synced: false, saved: false }} }}   # the handle physbone")
    o(f"  {FLAG}: {{ type: bool, default: false, vrc: {{ synced: true, saved: false }} }}   # the stake is on the wire")
    # Shared with the object-sync build through the one component. Enable's default 1 wins because this
    # controller sits first in the component's controllers and prms.
    o(f"  {r['rope']['span']['parameter']}: float   # the span contact pair, every client")
    o("  ObjectSync/Enable: { type: float, default: 1, vrc: { type: bool, synced: true, saved: false } }")
    o("  OS/Ready: { type: float, default: 0, vrc: { type: bool, synced: false, saved: false } }")
    o("  IsLocal: bool   # VRC built-in")
    o("")
    off = f"{{ to: Disabled, when: [ {EN} is false ] }}"
    posed = f"{IG} is false, {IP} is true"
    plain = f"{IG} is false, {IP} is false"
    engage = f"IsLocal is false, {FLAG} is true, ObjectSync/Enable greater 0.5, OS/Ready greater 0.5"

    def state(name, cl, held, planted, trans, extra=None, note=None):
        if note:
            o(f"      # {note}")
        o(f"      {name}:")
        o(f"        motion: {{ clip: {cl} }}")
        sets = f"{HELD}: {held}, {PL}: {planted}" + (f", {extra}" if extra else "")
        o(f"        behaviours: [ {{ driver: {{ set: {{ {sets} }} }} }} ]")
        o("        transitions:")
        for tr in trans:
            o(f"          - {tr}")

    o("layers:")
    o(f"  - name: {p}")
    o("    states:")
    state("Load", "disabled", 0, 0, [f"{{ to: Free, when: [ {EN} is true ] }}", off],
          note="The default: its clear is repeated by whichever state it hands to, one evaluation later.")
    state("Disabled", "disabled", 0, 0, [f"{{ to: Free, when: [ {EN} is true ] }}"], extra=f"{IG}: 0, {IP}: 0",
          note="The handle is off, so its stale grab flags stay cleared.")
    state("Free", "free", 0, 0, [off, f"{{ to: Held, when: [ {IG} is true ], duration: {fade} }}",
                                 f"{{ to: SyncPlanted, when: [ {engage} ], duration: {fade} }}"])
    state("Held", "held", 1, 0, [off, f"{{ to: Plant, when: [ {posed} ] }}",
                                 f"{{ to: Free, when: [ {plain} ], duration: {fade} }}"],
          note="_IsPosed is a level read when _IsGrabbed falls: posed plants, plain goes home.")
    state("Plant", "plant", 0, 1, ["{ to: Planted, when: [], exitTime: 1.0 }"],
          note="Freeze the stake, Holder onto it, the handle off for the cycle so it rests there unposed.")
    # The planted clip is one frame long, so the wait is in frames; above 1 the rung is tested once.
    wait = round((c["announce"] + REMOTE_WAIT) / FRAME, 3)
    state("Planted", "planted", 0, 1, [off, f"{{ to: PHeld, when: [ {IG} is true ] }}",
                                       f"{{ to: SyncPlanted, when: [ {engage} ] }}",
                                       f"{{ to: Free, when: [ {UNPLANT} is true ], duration: {fade} }}",
                                       f"{{ to: Free, when: [ IsLocal is false, {FLAG} is false ], exitTime: {wait}, duration: {fade} }}"],
          note="Unplant is the wearer's; the exit-time rung is a remote whose flag never rose.")
    state("PHeld", "pheld", 1, 0, [off, f"{{ to: Plant, when: [ {posed} ] }}",
                                   f"{{ to: Free, when: [ {plain} ], duration: {fade} }}"],
          note="A pick-up: Holder frozen where the stake stood, so no root moves under the live grab.")
    state("SyncPlanted", "sync_planted", 0, 1, [off, f"{{ to: PHeld, when: [ {IG} is true ] }}",
                                                 f"{{ to: Free, when: [ {FLAG} is false ], duration: {fade} }}"],
          note="A remote: Stake on object-sync's reconstruction until the flag falls.")
    o("    default: Load")
    o("    layout:")
    o("      nodes: { Load: [30, 180], Disabled: [-210, 260], Free: [30, 260], Held: [30, 340], Plant: [30, 420], "
      "Planted: [30, 500], PHeld: [270, 420], SyncPlanted: [270, 580] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o(f"  # Whether the wearer's own hand may grab or pose the handle; the filters are read at each grab.")
    o("  - name: SelfGrab")
    o("    states:")
    for name, cl, cond in (("Anyone", "self_on", f"{SELF} is false"), ("OthersOnly", "self_off", f"{SELF} is true")):
        o(f"      {name}:")
        o(f"        motion: {{ clip: {cl} }}")
        o("        transitions:")
        o(f"          - {{ to: {'OthersOnly' if name == 'Anyone' else 'Anyone'}, when: [ {cond} ] }}")
    o("    default: Anyone")
    o("    layout:")
    o("      nodes: { Anyone: [30, 180], OthersOnly: [270, 180] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o(f"  # Every client: the curve's control point slides from the pendulum's tip to the plain midpoint as the span")
    o(f"  # reaches taut ({r['rope']['sag']['taut']} m): the sag a rope of that length would show, capped at {r['rope']['sag']['height']} m.")
    o("  - name: Rope")
    o("    states:")
    o("      Sag:")
    o("        motion:")
    o("          tree: 1d")
    o(f"          param: {r['rope']['span']['parameter']}")
    o("          children:")
    for k, e in enumerate(sag):
        o(f"            - {{ clip: sag{k}, threshold: {e['reading']} }}   # span {e['span']} m")
    o("    default: Sag")
    o("    layout:")
    o("      nodes: { Sag: [30, 180] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o(f"  # Wearer-only: the synced flag follows {PL}, rising {c['announce']} s late and falling at once.")
    o("  - name: Announce")
    o("    states:")
    o("      Idle:")
    o("        motion: ~")
    o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {FLAG}: 0 }} }} }} ]")
    o("        transitions:")
    o(f"          - {{ to: Arming, when: [ IsLocal is true, {PL} is true ] }}")
    o("      Arming:")
    o("        motion: ~")
    o("        transitions:")
    o(f"          - {{ to: Idle, when: [ {PL} is false ] }}")
    o(f"          - {{ to: Raised, when: [], exitTime: {c['announce']} }}")
    o("      Raised:")
    o("        motion: ~")
    o(f"        behaviours: [ {{ driver: {{ localOnly: true, set: {{ {FLAG}: 1 }} }} }} ]")
    o("        transitions:")
    o(f"          - {{ to: Idle, when: [ {PL} is false ] }}")
    o("    default: Idle")
    o("    layout:")
    o("      nodes: { Idle: [30, 180], Arming: [270, 180], Raised: [270, 260] }")
    o("      entry: [50, 120]")
    o("      any: [50, 40]")
    o("      exit: [50, 80]")
    o("")
    o("clips:")
    for name, (seconds, s) in clips.items():
        o(f"  {name}:")
        if seconds:
            o(f"    seconds: {seconds}")
        o("    set:")
        for k, v in s.items():
            o(f'      "{k}": {v}')
    o("")
    o("menu:")
    o(f"  - submenu: {p}")
    o("    controls:")
    o(f"      - {{ toggle: Enable, param: {EN} }}")
    o(f"      - {{ toggle: Self-grab, param: {SELF} }}")
    o(f"      - {{ radial: Slack (held), param: {SLACK} }}")
    o(f"      - {{ radial: Slack (planted), param: {SLACKP} }}")
    o(f"      - {{ button: Unplant, param: {UNPLANT} }}")
    return "\n".join(L) + "\n", r


# ---- --check: the prefab surface no compile or gate reads ----
def meta_guid(path):
    m = re.search(r"^guid: ([0-9a-f]{32})$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def docs_of(path):
    return {int(m.group(2)): (int(m.group(1)), m.group(3)) for m in re.finditer(
        r"^--- !u!(\d+) &(-?\d+)(?: stripped)?\n(.*?)(?=^--- |\Z)", open(path, encoding="utf-8").read(), re.M | re.S)}


def fid(d, key):
    m = re.search(rf"^  {key}: \{{fileID: (-?\d+)", d, re.M)
    return int(m.group(1)) if m else None


def vec(d, key):
    m = re.search(rf"^  {key}: \{{x: (\S+), y: (\S+), z: (\S+)(?:, w: (\S+))?\}}", d, re.M)
    return tuple(float(v) for v in m.groups() if v is not None) if m else None


def field(d, key):
    m = re.search(rf"^  {key}: (.*)$", d, re.M)
    return m.group(1).strip() if m else None


class Prefab:
    """A prefab file read textually. Paths are relative to the mount, the FullController's GameObject.
    An object inside a nested prefab instance is resolved down its source chain to the real document
    (`index` maps a GUID to a prefab path); a flattened consumer prefab needs no index."""

    MASK = (1 << 63) - 1

    def __init__(self, path, index=None, nested=False, published=None):
        self.path, self.docs, self.index, self._sub = path, docs_of(path), index or {}, {}
        self.body = open(path, encoding="utf-8").read()
        self.go_of = {i: fid(d, "m_GameObject") for i, (cls, d) in self.docs.items() if cls != 1}
        if nested:
            return
        # The leash's own FullController: the only one on the entry; on a flattened avatar, the one publishing
        # `published` (the `<prefix>/*` wildcard).
        fcs = [(i, d) for i, (cls, d) in self.docs.items() if cls == 114 and "class: FullController" in d
               and (published is None or re.search(rf"^\s+- '?{re.escape(published)}'?$", d, re.M))]
        if len(fcs) != 1:
            refuse(f"{path}: expected exactly one FullController" + (f" publishing {published}" if published else "")
                   + f", found {len(fcs)}")
        self.fc = fcs[0][1]
        self.mount = next((i for i, (cls, d) in self.docs.items() if cls == 4 and self.go_of[i] == self.go_of[fcs[0][0]]), None)

    def sub(self, guid):
        if guid not in self._sub:
            p = self.index.get(guid)
            self._sub[guid] = Prefab(p, self.index, nested=True) if p else None
        return self._sub[guid]

    def instance_mods(self, inst):
        return re.findall(r"- target: \{fileID:\s+(-?\d+),\s+guid:\s+(\w+),\s+type:\s+3\}\s*\n\s+propertyPath: ([^\n]+)\n"
                          r"\s+value: ([^\n]*)\n\s+objectReference: \{fileID:\s+(-?\d+)", self.docs[inst][1])

    @staticmethod
    def source_of(body):
        m = re.search(r"m_CorrespondingSourceObject: \{fileID: (-?\d+), guid: (\w+)", body)
        return (int(m.group(1)), m.group(2)) if m and m.group(1) != "0" else None

    def resolve(self, f):
        """(file, id) of the real document id f names here: a stripped document follows its source; an id no
        document carries is inherited through one of this file's instances (source id XOR instance id)."""
        d = self.docs.get(f)
        if d is None:
            for i, (cls, b) in self.docs.items():
                if cls == 1001:
                    src = re.search(r"m_SourcePrefab: \{fileID: 100100000, guid: (\w+)", b)
                    s = self.sub(src.group(1)) if src else None
                    hit = s.resolve((f ^ i) & self.MASK) if s else None
                    if hit:
                        return hit
            return None
        so = self.source_of(d[1])
        if so:
            s = self.sub(so[1])
            return s.resolve(so[0]) if s else None
        return self, f

    def local_name(self, t):
        """A plain transform's GameObject name in this file."""
        go = self.docs[self.go_of[t]][1]
        m = re.search(r"^  m_Name: (.*)$", go, re.M)
        return m.group(1).strip() if m else None

    def local_path(self, t):
        """A plain transform's path from its file's root, the root's own name excluded."""
        parts = []
        while fid(self.docs[t][1], "m_Father") not in (0, None):
            parts.append(self.local_name(t))
            t = fid(self.docs[t][1], "m_Father")
        return "/".join(reversed(parts))

    def path_of(self, t):
        """The transform's path from the mount, or None outside the mount's subtree or unresolvable."""
        parts = []
        while t is not None:
            if t == self.mount:
                return "/".join(reversed(parts))
            d = self.docs.get(t)
            if d is None:
                return None
            if self.source_of(d[1]) is None:
                parts.append(self.local_name(t))
                t = fid(d[1], "m_Father")
                if t == 0:
                    return None
                continue
            # A stripped transform inside a nested instance: its path in the source, under the instance root,
            # whose own name is the instance's m_Name override, under the instance's parent here.
            inst = fid(d[1], "m_PrefabInstance")
            real = self.resolve(t)
            if real is None:
                return None
            rp = real[0].local_path(real[1])
            name = next((v.strip() for f, g, pp, v, ref in self.instance_mods(inst) if pp == "m_Name"), None)
            if name is None:
                return None
            parts.extend(reversed([name] + ([rp] if rp else [])))
            tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)\}", self.docs[inst][1])
            t = int(tp.group(1)) if tp else None

    def root_path(self, t):
        """A plain transform's path from the file's root, '/'-rooted: an avatar path on a flattened consumer."""
        return "/" + self.local_path(t) if t in self.docs and self.source_of(self.docs[t][1]) is None else None

    def by_path(self):
        """Paths from the mount, and '/'-rooted paths from the file's root for everything outside it."""
        out = {}
        for i, (cls, d) in self.docs.items():
            if cls == 4 and self.source_of(d) is None:
                p = self.path_of(i)
                out[p if p is not None else self.root_path(i)] = i
        return out

    def transform(self, path):
        t = self.by_path().get(path)
        return self.docs[t][1] if t is not None else None

    def components(self, path, has=None):
        t = self.by_path().get(path)
        if t is None:
            return []
        go = self.go_of[t]
        return [d for i, (cls, d) in self.docs.items() if cls not in (1, 4) and self.go_of.get(i) == go
                and (has is None or re.search(has, d, re.M))]

    def sources(self, d):
        """The constraint's sources up to totalLength: (path or asset guid, weight, position offset, rotation
        offset as a quaternion)."""
        m = re.search(r"^    totalLength: (\d+)", d, re.M)
        n = int(m.group(1)) if m else 0
        out = []
        for k in range(n):
            blk = d.split(f"    source{k}:")[1] if f"    source{k}:" in d else ""
            m = re.search(r"SourceTransform: \{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}))?", blk)
            w = re.search(r"Weight: (\S+)", blk)
            po = re.search(r"ParentPositionOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            ro = re.search(r"ParentRotationOffset: \{x: (\S+), y: (\S+), z: (\S+)\}", blk)
            tgt = (m.group(2) or self.path_of(int(m.group(1))) or self.root_path(int(m.group(1)))) if m else None
            out.append((tgt, float(w.group(1)) if w else None,
                        tuple(float(x) for x in po.groups()) if po else None,
                        euler(tuple(float(x) for x in ro.groups())) if ro else None))
        return out


def tags_of(d):
    m = re.search(r"^  collisionTags:\n((?:  - .*\n)*)", d, re.M)
    return [ln[4:].strip() for ln in m.group(1).splitlines()] if m else None


def same_rotation(got, want):
    return got is not None and abs(sum(a * b for a, b in zip(got, want))) > 1 - 1e-5


def close(a, b, eps=1e-4):
    return a is not None and b is not None and len(a) == len(b) and all(abs(x - y) <= eps for x, y in zip(a, b))


ZERO3 = (0.0, 0.0, 0.0)
ZERO_Q = (0.0, 0.0, 0.0, 1.0)
ENUM = {"True": "1", "False": "0", "Other": "2", True: "1", False: "0", "Simplified": "0", "Advanced": "1", "None": "0"}


def source_faults(src, want):
    """Each (path, weight, position offset, rotation quaternion or None) in want against the parsed sources."""
    if [a for a, *_ in src] != [w[0] for w in want]:
        return [f"sources {[w[0] for w in want]} (got {[a for a, *_ in src]})"]
    out = []
    for (a, w, po, ro), (_, ww, wpo, wro) in zip(src, want):
        if w is None or abs(w - ww) > 1e-6:
            out.append(f"{a} weight {ww} (got {w})")
        if wpo is not None and po is not None and not close(po, wpo):
            out.append(f"{a} position offset {wpo} (got {po})")
        if wro is not None and not same_rotation(ro or ZERO_Q, wro):
            out.append(f"{a} rotation offset {wro} (got {ro})")
    return out


def own_offsets(d):
    return [f"{k} (got {vec(d, k)})" for k in ("PositionOffset", "RotationOffset")
            if vec(d, k) is not None and not close(vec(d, k), ZERO3)]


def index_of(*roots):
    out = {}
    for rt in roots:
        for dp, _, fs in os.walk(rt):
            for f in fs:
                if f.endswith(".prefab.meta"):
                    out[meta_guid(os.path.join(dp, f[:-5]))] = os.path.join(dp, f[:-5])
    return out


def check(c, prefab_path, entry=True):
    """LeashStake.prefab (or a consumer's flattened prefab at the same CONFIG) against rig.json's numbers.
    Reads the YAML textually; a field it cannot find is a FAIL, never a pass."""
    og = sync_gen()
    r = rig(c, og)
    ok = True

    def A(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)
        return cond

    if not os.path.exists(prefab_path):
        print("  FAIL " + prefab_path + " is missing")
        return False
    P = Prefab(prefab_path, index_of(os.path.join(ROOT, "object-sync")) if entry else None,
               published=None if entry else f"{c['prefix']}/*")
    s = r["sensing"]

    # The FullController seam: globalParams exactly the published wildcards; on the entry, this entry's built/
    # in order (the leash's controller and params ahead of object-sync's, or Enable's default loses the merge).
    gp = re.findall(r"globalParams:\n((?:\s+- .+\n)+)", P.fc)
    got = [[ln.split("- ", 1)[1].strip().strip("'\"") for ln in b.splitlines()] for b in gp]
    A(got == [r["globalParams"]], f"globalParams == {r['globalParams']} (got {got}): the bridge reads {c['prefix']}/* bare")
    if entry:
        g = lambda rel: meta_guid(os.path.join(HERE, rel))
        for kind, a, b in (("controllers", f"built/{c['controller']}.controller", "object-sync/built/ObjectSync_Fx.controller"),
                           ("prms", f"built/{c['controller']}_Parameters.asset", "object-sync/built/ObjectSync_Fx_Parameters.asset")):
            ia, ib = P.fc.find(g(a)), P.fc.find(g(b))
            A(ia != -1 and ib != -1 and ia < ib, f"FullController {kind}: {a} before {b}")
        A(P.fc.find(g(f"built/{c['controller']}_Menu.asset")) != -1, f"FullController menus: built/{c['controller']}_Menu.asset")
    else:
        # A consumer plays its own controller and params ahead of this entry's object-sync build, or the sync build's
        # ObjectSync/Enable default (off) wins the first-wins merge and the stake never syncs.
        for kind, rel in (("controllers", "object-sync/built/ObjectSync_Fx.controller"),
                          ("prms", "object-sync/built/ObjectSync_Fx_Parameters.asset")):
            block = P.fc.split(f"        {kind}:")[1] if f"        {kind}:" in P.fc else ""
            block = re.split(r"\n        [a-zA-Z]", block, maxsplit=1)[0]
            refs = re.findall(r"objRef: \{fileID: \d+, guid: ([0-9a-f]{32})", block)
            want = meta_guid(os.path.join(HERE, rel))
            A(want in refs and refs.index(want) > 0, f"FullController {kind}: the consumer's own entry before this entry's {rel} (got {refs})")

    # Sensing: two boxes on Sense, one sender on SenseProxy, one private tag, the geometry the decode assumes.
    boxes = P.components("Sense", r"^  receiverType:")
    A(len(boxes) == len(s["boxes"]), f"Sense carries {len(s['boxes'])} receivers (got {len(boxes)})")
    for want in s["boxes"]:
        d = next((b for b in boxes if re.search(rf"^  parameter: {re.escape(want['parameter'])}$", b, re.M)), None)
        if not A(d is not None, f"a Sense receiver writes {want['parameter']}"):
            continue
        A(tags_of(d) == [s["tag"]], f"{want['parameter']}: tags == [{s['tag']}] (got {tags_of(d)})")
        A(close(vec(d, "size"), (s["boxSize"],) * 3), f"{want['parameter']}: box size {s['boxSize']} on every axis")
        A(same_rotation(vec(d, "rotation"), euler(want["rotation"])), f"{want['parameter']}: box rotation puts its +Z face on its axis")
        for fld, v in (("shapeType", "2"), ("localOnly", "1"), ("allowSelf", "1"), ("allowOthers", "0"),
                       ("useFaceProximity", "1"), ("receiverType", "2"), ("contentTypes", "1")):
            A(field(d, fld) == v, f"{want['parameter']}: {fld} == {v} (got {field(d, fld)})")
        A(close(vec(d, "position"), ZERO3), f"{want['parameter']}: shape offset zero")
    snd = P.components("SenseProxy", r"^  collisionTags:")
    if A(len(snd) == 1, "SenseProxy carries one contact sender"):
        d = snd[0]
        A(tags_of(d) == [s["tag"]], f"sender tags == [{s['tag']}] (got {tags_of(d)})")
        A(field(d, "radius") is not None and abs(float(field(d, "radius")) - s["senderRadius"]) < 1e-6, f"sender radius == {s['senderRadius']}")
        A(field(d, "shapeType") == "0" and field(d, "localOnly") == "1", "sender is a local-only sphere")
        A(close(vec(d, "position"), ZERO3), "sender shape offset zero")

    # Constraint sources and rest weights (the Free clip's; the animator overwrites them in play).
    def one(path, has, want, label):
        cs = P.components(path, has)
        if A(len(cs) == 1, f"{path} carries one {label}"):
            bad = source_faults(P.sources(cs[0]), want) + own_offsets(cs[0])
            A(not bad, f"{path} {label} sources {[w[0] for w in want]} at {[w[1] for w in want]}, zero offsets"
              + (f": {bad}" if bad else ""))
            return cs[0]

    one("Sense", r"^  PositionAtRest:", [("Mount/Start", 1, None, None)], "position constraint")
    A(not P.components("Sense", r"^  RotationAtRest:"), "Sense carries no rotation constraint: it takes the avatar root's yaw by riding the root")
    one("SenseProxy", r"^  PositionAtRest:", [("Sense", s["proxyWeights"][0], None, None), ("Stake", s["proxyWeights"][1], None, None)],
        "position constraint")
    one("Holder", r"^  RotationAtRest:", [("Mount/Start/Home", 1, ZERO3, ZERO_Q), ("Stake", 0, ZERO3, ZERO_Q)], "parent constraint")
    one("Far", r"^  PositionAtRest:", [("Holder/HB0/HTip", 1, None, None)], "position constraint")
    one("Stake", r"^  PositionAtRest:", [("Far", 1, None, None), (f"{SYNC_MOUNT}/Rig/Prop/Display", 0, None, None)],
        "position constraint")
    ln = r["line"]
    line_cs = P.components(ln["path"], r"^  Sources:")
    lp = [x for x in line_cs if not re.search(r"^  AimAxis:", x, re.M)]
    la = [x for x in line_cs if re.search(r"^  AimAxis:", x, re.M)]
    d = P.transform(ln["path"])
    A(d is not None and close(vec(d, "m_LocalPosition"), ZERO3) and not lp,
      f"{ln['path']} sits on Stake's origin with no position constraint: under Stake it reads Stake's solved position")
    if A(len(la) == 1 and [x[0] for x in P.sources(la[0])] == [ln["aimAt"]], f"{ln['path']} aim <- {ln['aimAt']}"):
        A(close(vec(la[0], "AimAxis"), tuple(ln["aimAxis"])) and close(vec(la[0], "UpAxis"), tuple(ln["upAxis"]))
          and field(la[0], "WorldUp") == "0",
          f"{ln['path']} aims {ln['aimAxis']} at {ln['aimAt']}, up {ln['upAxis']} against scene up, so +Z runs along the curve's end")
        A(not own_offsets(la[0]), f"{ln['path']} aim offset zero")
    for j in ln["joints"]:
        path = f"{ln['path']}/{j['name']}"
        d = P.transform(path)
        if not A(d is not None, f"{path} exists"):
            continue
        if "static" in j:
            A(same_rotation(vec(d, "m_LocalRotation"), ZERO_Q), f"{path}: unrotated under Line")
            A(close(vec(d, "m_LocalPosition"), tuple(j["static"])), f"{path}: static at {j['static']} (the last bone's length back from Stake toward Ctrl)")
            A(not P.components(path, r"^  Sources:"), f"{path}: no constraint")
        else:
            one(path, r"^  PositionAtRest:", [(a, w, None, None) for a, w in zip(j["sources"], j["weights"])], "position constraint")
            aims = P.components(path, r"^  AimAxis:")
            if A(len(aims) == 1 and [x[0] for x in P.sources(aims[0])] == [j["aim"]], f"{path} aim <- {j['aim']}"):
                A(close(vec(aims[0], "AimAxis"), tuple(ln["jointAimAxis"])) and close(vec(aims[0], "UpAxis"), tuple(ln["upAxis"]))
                  and field(aims[0], "WorldUp") == "0" and not own_offsets(aims[0]),
                  f"{path} aims {ln['jointAimAxis']} at the next joint, up {ln['upAxis']} against scene up, offset zero")

    # The rope: the pendulum on the midpoint, the control point, the span contact pair.
    rp = r["rope"]
    one(rp["mid"]["path"], r"^  PositionAtRest:", [(a, w, None, None) for a, w in zip(rp["mid"]["sources"], rp["mid"]["weights"])],
        "position constraint")
    A(not P.components(rp["mid"]["path"], r"^  RotationAtRest:"), f"{rp['mid']['path']} carries no rotation constraint: the pendulum hangs in the root's frame")
    pen = rp["pendulum"]
    d = P.transform(pen["tip"])
    A(d is not None and close(vec(d, "m_LocalPosition"), tuple(pen["tipLocalPosition"])), f"{pen['tip']} at {pen['tipLocalPosition']} (twice the sag)")
    d = P.transform(pen["bone"])
    A(d is not None and close(vec(d, "m_LocalPosition"), ZERO3) and same_rotation(vec(d, "m_LocalRotation"), ZERO_Q),
      f"{pen['bone']} at its parent's origin, unrotated, so the pendulum rests straight down")
    pbs = P.components(pen["bone"], r"^  maxStretch:")
    if A(len(pbs) == 1, f"{pen['bone']} carries one physbone"):
        for fld, v in pen["physbone"].items():
            got = field(pbs[0], fld)
            good = (got or "") == v if fld == "parameter" else (got == ENUM[v] if isinstance(v, (bool, str)) else
                                                               got is not None and abs(float(got) - v) < 1e-6)
            A(good, f"pendulum physbone {fld} == {v!r} (got {got})")
        A(fid(pbs[0], "rootTransform") in (0, None), "pendulum physbone roots on its own bone")
    one(rp["ctrl"]["path"], r"^  PositionAtRest:", [(a, w, None, None) for a, w in zip(rp["ctrl"]["sources"], rp["ctrl"]["weights"])],
        "position constraint")
    sp = rp["span"]
    rc = [x for x in P.components(sp["receiver"]["path"], r"^  receiverType:")]
    if A(len(rc) == 1, f"{sp['receiver']['path']} carries the span receiver"):
        x = rc[0]
        A(field(x, "parameter") == sp["parameter"] and tags_of(x) == [sp["tag"]], f"span receiver writes {sp['parameter']} on [{sp['tag']}]")
        A(field(x, "radius") is not None and abs(float(field(x, "radius")) - sp["receiver"]["radius"]) < 1e-6,
          f"span receiver radius == {sp['receiver']['radius']} (the sag table's readings assume it)")
        for fld, v in (("shapeType", "0"), ("localOnly", "0"), ("allowSelf", "1"), ("allowOthers", "0"), ("receiverType", "2"),
                       ("contentTypes", "1")):
            A(field(x, fld) == v, f"span receiver {fld} == {v} (got {field(x, fld)}): every client reads its own span")
        A(close(vec(x, "position"), ZERO3), "span receiver shape offset zero")
    ss = P.components(sp["sender"]["path"], r"^  collisionTags:")
    if A(len(ss) == 1, f"{sp['sender']['path']} carries the span sender"):
        x = ss[0]
        A(tags_of(x) == [sp["tag"]] and field(x, "shapeType") == "0" and field(x, "localOnly") == "0"
          and abs(float(field(x, "radius") or "nan") - sp["sender"]["radius"]) < 1e-6 and close(vec(x, "position"), ZERO3),
          f"span sender: a {sp['sender']['radius']} m sphere on [{sp['tag']}], not local-only, offset zero")

    # The handle: its pose and the physbone that makes it one.
    d = P.transform("Holder/HB0/HTip")
    A(d is not None and close(vec(d, "m_LocalPosition"), tuple(r["handle"]["tipLocalPosition"])),
      f"Holder/HB0/HTip at {r['handle']['tipLocalPosition']}")
    pbs = P.components("Holder/HB0", r"^  maxStretch:")
    if A(len(pbs) == 1, "Holder/HB0 carries one physbone"):
        for fld, v in r["handle"]["physbone"].items():
            got = field(pbs[0], fld)
            good = got == v if fld == "parameter" else (got == ENUM[v] if isinstance(v, (bool, str)) else
                                                        got is not None and abs(float(got) - v) < 1e-6)
            A(good, f"handle physbone {fld} == {v} (got {got})")
        A(fid(pbs[0], "rootTransform") in (0, None), "handle physbone roots on HB0 itself")
        for flt in ("grabFilter", "poseFilter"):
            m = re.search(rf"^  {flt}:\n    allowSelf: (\d+)\n    allowOthers: (\d+)", pbs[0], re.M)
            A(m is not None and m.groups() == ("1", "1"),
              f"handle {flt} bakes allowSelf and allowOthers on (SelfGrab animates allowSelf) (got {m and m.groups()})")

    # Start and Home: the socket, and the static tip the handle homes at.
    for key in ("start", "home"):
        e = r[key]
        d = P.transform(e["path"])
        if A(d is not None, f"{e['path']} exists"):
            A(close(vec(d, "m_LocalPosition"), tuple(e["localPosition"]), 2e-4), f"{e['path']}: local position {e['localPosition']}")
            A(same_rotation(vec(d, "m_LocalRotation"), tuple(e["localRotation"])), f"{e['path']}: local rotation")
            A(not P.components(e["path"]), f"{e['path']}: no components (a static node)")
    if entry:
        bp = P.components("Mount", r"^  boneReference:")
        if A(len(bp) == 1, "Mount carries one MA BoneProxy"):
            A(field(bp[0], "boneReference") == str(HUMAN[r["mount"]]), f"Mount BoneProxy targets {r['mount']}")
            # AsChildKeepRotation (3): position snaps to the bone, world rotation stays the avatar root's, so a
            # vendor's bone roll never tilts the demo strand.
            A(field(bp[0], "attachmentMode") == "3", f"Mount BoneProxy keeps its rotation (got {field(bp[0], 'attachmentMode')})")

    # The strand's own physbone: its endpoint is CONFIG's, the last bone's visible end the line lands on Stake.
    first = r["strand"][0]["path"]
    spb = P.components(first, r"^  endpointPosition:") or P.components(first.rsplit("/", 1)[0], r"^  endpointPosition:")
    if A(len(spb) == 1, f"the strand's physbone sits on {first} or its parent"):
        A(close(vec(spb[0], "endpointPosition"), tuple(c["endpoint"])),
          f"strand physbone endpointPosition == endpoint {tuple(c['endpoint'])} (got {vec(spb[0], 'endpointPosition')})")
    # The strand: one parent constraint per bone, sources [itself, its joint], rest weights (1, 0).
    for st in r["strand"]:
        if st["path"].startswith("/") and entry:
            continue
        st_path = st["path"]
        cs = P.components(st_path, r"^  RotationAtRest:")
        if A(len(cs) == 1, f"strand {st_path} carries one parent constraint"):
            want = [(st_path, 1, ZERO3, ZERO_Q), (st["joint"], 0, ZERO3, tuple(st["jointRotationOffsetQ"]))]
            bad = source_faults(P.sources(cs[0]), want)
            A(not bad, f"{st_path} sources [itself, {st['joint']}] at [1, 0], joint rotation offset "
              f"{st['jointRotationOffset']}" + (f": {bad}" if bad else ""))
        grab = P.components(st_path, r"^  allowGrabbing:")
        for d in grab:
            A(field(d, "allowGrabbing") == "0", f"{st_path}'s own physbone has grabbing off (the handle takes every grab)")

    if entry:
        check_sync(c, og, P, A)
    print("OK" if ok else "FAILED")
    return ok


def check_sync(c, og, P, A):
    """The nested object-sync rig: named SYNC_MOUNT under the root, its own fronts and rotation stage
    removed, re-parked and retagged to rigSeed, Sync_Target measuring Stake."""
    y_pf = os.path.join(ROOT, "object-sync", "y", "ObjectSync.prefab")
    y_g = meta_guid(y_pf)
    insts = [i for i, (cls, d) in P.docs.items() if cls == 1001 and f"m_SourcePrefab: {{fileID: 100100000, guid: {y_g}" in d]
    if not A(len(insts) == 1, "LeashStake.prefab nests object-sync/y/ObjectSync.prefab once"):
        return
    inst = insts[0]
    sb = P.docs[inst][1]
    mods = P.instance_mods(inst)

    def real(f, g):
        s = P.sub(g)
        return s.resolve(int(f)) if s else None

    def nm(f, g):
        hit = real(f, g)
        if hit is None:
            return None
        s, i = hit
        cls, d = s.docs[i]
        if cls != 1:
            s, i = s.resolve(fid(d, "m_GameObject")) or (None, None)
        m = re.search(r"^  m_Name: (.*)$", s.docs[i][1], re.M) if s else None
        return m.group(1).strip() if m else None

    def kind(f, g):
        hit = real(f, g)
        if hit is None:
            return None
        d = hit[0].docs[hit[1]][1]
        k = re.search(r"class: (\w+)", d)
        return k.group(1) if k else ("constraint" if "Sources:" in d else "?")

    name = next((v.strip() for f, g, pp, v, ref in mods if pp == "m_Name"), None)
    A(name == SYNC_MOUNT, f"the sync instance is named {SYNC_MOUNT!r} (the emitted bindings' prefix)")
    tp = re.search(r"m_TransformParent: \{fileID: (-?\d+)\}", sb)
    A(tp and int(tp.group(1)) == P.mount, "the sync instance hangs directly under the prefab root, the component's GameObject")

    removed = re.findall(r"m_RemovedComponents:\n((?:    - \{fileID: .+\n)*)", sb)
    kinds = {}
    for f, g in re.findall(r"fileID: (-?\d+), guid: (\w+)", "".join(removed)):
        kinds.setdefault(nm(f, g), []).append(kind(f, g))
    for who, what in ((SYNC_MOUNT, "FullController"), (SYNC_MOUNT, "Toggle"), ("Sync_Target", "Toggle")):
        A(what in kinds.get(who, []), f"the sync instance removes {who}'s {what}")
    A("constraint" in kinds.get("Display", []), "the sync instance removes Display's rotation constraint (no rotation stage)")
    rgos = re.findall(r"m_RemovedGameObjects:\n((?:    - \{fileID: .+\n)*)", sb)
    rgo = sorted(str(nm(f, g)) for f, g in re.findall(r"fileID: (-?\d+), guid: (\w+)", "".join(rgos)))
    A(rgo == sorted(["MarkA", "Recon", "RecvAX", "RecvAZ"]), f"the sync instance removes the rotation stage's marker, receivers and Recon (got {rgo})")

    scfg = sync_config(c, og)
    want_park = tuple(float(v) for v in og.rig_offset(c["rigSeed"]))
    pm = {pp: v for f, g, pp, v, ref in mods if nm(f, g) == "Prop" and pp.startswith("m_LocalPosition.")}
    got_park = tuple(float(pm.get(f"m_LocalPosition.{a}", "nan")) for a in "xyz")
    A(got_park == want_park, f"Rig/Prop park == rig_offset({c['rigSeed']!r}) {want_park} (got {got_park})")
    carriers = og.tag_carriers(scfg, "Prop")
    for tg in og.tag_set(scfg, "Prop"):
        n = sb.count(f"value: {tg}\n")
        A(n == carriers[tg], f"tag {tg} on exactly its stage's components ({n} of {carriers[tg]})")
    for tg in og.tag_set(og.CONFIG, og.CONFIG["objects"][0]["name"]):
        A(f"value: {tg}\n" not in P.body, f"no component left on the entry-default tag {tg}")
    tg = {pp: (v, int(ref)) for f, g, pp, v, ref in mods if nm(f, g) == "Sync_Target" and pp.startswith("Sources.")}
    A(tg.get("Sources.totalLength", ("",))[0] == "1", f"Sync_Target's constraint carries one source (got {tg.get('Sources.totalLength')})")
    ref = tg.get("Sources.source0.SourceTransform", ("", 0))[1]
    A(ref and P.path_of(ref) == "Stake", "Sync_Target's source0 is Stake")
    A(tg.get("Sources.source0.Weight", ("1",))[0] == "1", "Sync_Target's source0 weight 1")

    # Names the leash's controller reads that object-sync owns must be names its build declares.
    glue = re.sub(r"#.*", "", open(os.path.join(HERE, "controller.yaml"), encoding="utf-8").read())
    roots = {og.CONFIG["prefix"].split("/")[0], og.CONFIG["internal"].split("/")[0], og.CONFIG["channel"].split("/")[0]}
    reached = sorted({n for n in re.findall(r"[A-Za-z][A-Za-z0-9_]*/[A-Za-z0-9_/]+", glue) if n.split("/")[0] in roots})
    declared = set(re.findall(r"^  ([^\s#:]+):", og.document(scfg)[0], re.M))
    A(reached and not [n for n in reached if n not in declared], f"every object-sync name the controller reads is declared by its build ({reached})")


CONSUMER_KEYS = {"prefix", "internal", "controller", "tag", "boxSize", "senderRadius", "ratio", "slackRange", "slack", "slackPlanted", "selfGrabDefault", "mount", "mountRot",
                 "chain", "endpoint", "homeAt", "home", "handle", "rope", "fade", "cycle", "announce", "enableDefault"}


def arg(name):
    if name not in sys.argv:
        return None
    i = sys.argv.index(name) + 1
    if i >= len(sys.argv):
        refuse(f"{name} needs a value")
    return sys.argv[i]


def consumer_config(path):
    """CONFIG with a consumer's JSON keys over it; `handle` and `rope` merge key by key."""
    with open(path, encoding="utf-8") as fh:
        user = json.load(fh)
    bad = sorted(set(user) - CONSUMER_KEYS - {"_comment"})
    if bad:
        refuse(f"{path}: unknown or non-consumer keys {bad} (rigSeed belongs to this entry's object-sync build)")
    c = dict(CONFIG)
    for k, v in user.items():
        if k in ("handle", "rope"):
            c[k] = dict(CONFIG[k], **v)
        elif k != "_comment":
            c[k] = v
    return c


def main():
    cpath = arg("--config")
    c = consumer_config(cpath) if cpath else CONFIG
    if "--check" in sys.argv:
        sys.exit(0 if check(c, os.path.join(HERE, "LeashStake.prefab")) else 1)
    if "--check-prefab" in sys.argv:
        sys.exit(0 if check(c, arg("--check-prefab"), entry=False) else 1)
    og = sync_gen()
    out = arg("--out") or (HERE if not cpath else refuse("--config needs --out: a consumer never writes into this entry"))
    text, r = document(c, og)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "controller.yaml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with open(os.path.join(out, "rig.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, indent=2)
        fh.write("\n")
    if not cpath:
        stext, f = og.document(sync_config(c, og))
        os.makedirs(os.path.dirname(SYNC_OUT), exist_ok=True)
        with open(SYNC_OUT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(stext)
    print(f"wrote {out}: controller.yaml ({c['controller']}) and rig.json"
          + ("" if cpath else ", and object-sync/controller.yaml")
          + f": {len(r['strand'])} strand bones, length {r['length']} m, handle reach {r['handle']['reach']} m, "
          f"Home {r['home']['localPosition']}")


if __name__ == "__main__":
    main()
