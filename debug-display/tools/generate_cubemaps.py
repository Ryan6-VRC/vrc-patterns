#!/usr/bin/env python3
"""Generate the two owned reflection spheremaps for debug-display's shell pass.

Replaces the Poiyomi cubemaps (`T_Shine_CM`, `T_iridescent_CM`) the ancestor materials
referenced out of `com.poiyomi.toon`. That dependency failed QUIETLY rather than loudly: the shader
is self-contained and only the texture slot pointed into the package, so a consumer without Poiyomi
got a null cubemap and a silently wrong reflection, never a pink material. Owning them removes the
dependency and the quiet failure together.

Procedural rather than image-generated, for three reasons: the content is gradients, so a model buys
nothing; a generator script is reproducible where a generated image is not (CLAUDE.md rule 3); and it
keeps a public repo free of a second provenance question.

512 squared is sized off measurement, not taste. The ancestor's `T_Shine_CM` was 2048 squared carrying
58 KiB of actual gradient detail, `T_iridescent_CM` was natively 420 squared, and the shell samples
heavily mipped (the reference material lands near mip 2.2) -- so 512 already exceeds what survives
sampling.

Stdlib only (zlib + struct write the PNG). PIL would be shorter but adds a dependency the next person
may not have, and the whole point of committing a generator is that it still runs.

Import settings the shader depends on -- assert them on the committed .meta, do not eyeball them:
    textureShape: TextureCube      generateCubemap: Auto (a 1:1 source reads as a spheremap)
A wrong textureShape silently samples a flat 2D texture instead of a cube, which is the same class of
quiet failure this script exists to remove.

Usage:  python generate_cubemaps.py [output_dir]
Default output_dir is ../assets relative to this script.
"""

import math
import os
import struct
import sys
import zlib

SIZE = 512


def write_png(path, rows):
    """Write 8-bit RGB PNG. `rows` is a list of bytearrays, each SIZE*3 long."""
    raw = b"".join(b"\x00" + bytes(r) for r in rows)  # filter byte 0 (None) per scanline

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)  # bit depth 8, colour type 2 (RGB)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def sphere_direction(u, v):
    """Decode a spheremap texel to the world direction it reflects.

    A spheremap stores the sphere of directions in its inscribed disc: the texel at (u,v) in [-1,1]
    carries the normal N = (u, v, sqrt(1 - r^2)), and the direction sampled through it is the view
    vector (0,0,1) reflected about N. Colouring by that direction rather than by (u,v) is what makes
    the gradients coherent ON THE SPHERE -- a flat 2D gradient would visibly swim as the camera moves,
    which is exactly the artifact a reflection cubemap must not have.

    Returns None outside the disc; those texels are unused by the sampler and get the rim value.
    """
    r2 = u * u + v * v
    if r2 > 1.0:
        return None
    nz = math.sqrt(1.0 - r2)
    # R = 2*(N.V)*N - V, with V = (0,0,1) and N.V = nz
    return (2.0 * nz * u, 2.0 * nz * v, 2.0 * nz * nz - 1.0)


def clamp8(x):
    return 0 if x < 0 else (255 if x > 255 else int(x))


def glass(d):
    """Neutral glass/specular environment: a sky-to-ground luminance ramp plus two soft highlights.

    This is what reads as glass once the shell blurs it: broad vertical energy separation with a couple
    of specular blobs to catch the eye as the surface turns. Deliberately low-saturation so the text
    palette, not the shell, carries colour.
    """
    x, y, z = d
    # Sky/ground ramp on elevation, smoothstepped so the horizon is soft rather than a hard line.
    t = (y + 1.0) * 0.5
    t = t * t * (3.0 - 2.0 * t)
    base = 26.0 + 150.0 * t
    # Slight cool tint upward, warm downward -- reads as sky over a neutral floor.
    rr, gg, bb = base * 0.94, base * 0.97, base * 1.06
    if y < 0.0:
        warm = -y
        rr += 16.0 * warm
        gg += 10.0 * warm

    # Two specular highlights, placed off-axis so the shell never looks symmetric (which reads as CG).
    for hx, hy, hz, power, gain in ((0.45, 0.72, -0.53, 220.0, 210.0),
                                    (-0.62, 0.35, 0.70, 90.0, 90.0)):
        dot = x * hx + y * hy + z * hz
        if dot > 0.0:
            spec = dot ** power
            rr += gain * spec
            gg += gain * spec
            bb += gain * spec
    return clamp8(rr), clamp8(gg), clamp8(bb)


def iridescent(d):
    """Hue sweeps with view direction, so a turning surface shifts colour.

    The finding wants this one for AXIS LEGIBILITY -- a display whose shell shifts hue as it rotates
    reads its orientation at a glance. Hue tracks azimuth (a full wrap around the sphere) with a
    secondary shift on elevation, so both axes are legible rather than just the horizontal one.
    """
    x, y, z = d
    azimuth = math.atan2(x, z) / (2.0 * math.pi) + 0.5   # 0..1 around the sphere
    # The wrap count MUST be an integer. atan2's branch cut (x = 0, z < 0) makes azimuth jump 0.5 -> 1.0
    # there, so only an integer multiplier lands both sides on the same hue; a fractional one (1.5 was
    # tried) leaves a hard colour seam down the vertical centre line, inside the sampled disc.
    hue = (azimuth * 2.0 + y * 0.28) % 1.0
    sat = 0.48 + 0.22 * (1.0 - abs(y))                   # richest at the equator
    val = 0.34 + 0.42 * ((y + 1.0) * 0.5)                # still brighter up than down

    # HSV -> RGB, inline (six-sector form) to keep this stdlib-only and dependency-free.
    i = int(hue * 6.0) % 6
    f = hue * 6.0 - int(hue * 6.0)
    p, q, t = val * (1.0 - sat), val * (1.0 - sat * f), val * (1.0 - sat * (1.0 - f))
    rr, gg, bb = ((val, t, p), (q, val, p), (p, val, t),
                  (p, q, val), (t, p, val), (val, p, q))[i]
    return clamp8(rr * 255.0), clamp8(gg * 255.0), clamp8(bb * 255.0)


def generate(shade):
    rows = []
    for py in range(SIZE):
        # +v is up: image row 0 is the top, so flip.
        v = 1.0 - 2.0 * (py + 0.5) / SIZE
        row = bytearray()
        for px in range(SIZE):
            u = 2.0 * (px + 0.5) / SIZE - 1.0
            d = sphere_direction(u, v)
            if d is None:
                # Outside the disc the sampler never reads; clamp to the nearest rim direction so the
                # corners cannot bleed a hard edge in under bilinear filtering at low mips.
                r = math.sqrt(u * u + v * v)
                d = sphere_direction(u / r * 0.999, v / r * 0.999)
            row += bytes(shade(d))
        rows.append(row)
    return rows


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    for name, shade in (("Cube_Glass.png", glass), ("Cube_Iridescent.png", iridescent)):
        path = os.path.join(out_dir, name)
        write_png(path, generate(shade))
        print("wrote %s (%d x %d, %d bytes)" % (path, SIZE, SIZE, os.path.getsize(path)))


if __name__ == "__main__":
    main()
