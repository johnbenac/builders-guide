#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate a small, seamless, procedural texture set for the worked example (guide 5).

    python3 make_sample_texture_set.py OUT_DIR

Writes OUT_DIR/finishes/textures/plaster_example/{albedo.png,normal.png,orm.png,set.json} (1024 by 1024 pixels,
2 m per tile, tintMode multiply). Deterministic: the same seed gives the same bytes. The set is original work made
by this script and is free to reuse.

Requires: pip install numpy pillow
"""
import json
import os
import sys

import numpy as np
from PIL import Image

SIZE = 1024
rng = np.random.default_rng(7)


def periodic_noise(cells, octaves=5, gain=0.5):
    """Seamless fractal noise: random grids upsampled with periodic cubic smoothing."""
    out = np.zeros((SIZE, SIZE), np.float32)
    amp = 1.0
    for o in range(octaves):
        n = cells * 2 ** o
        g = rng.random((n, n)).astype(np.float32)
        xs = np.arange(SIZE) / SIZE * n
        i0 = np.floor(xs).astype(int) % n
        i1 = (i0 + 1) % n
        f = xs - np.floor(xs)
        f = f * f * (3 - 2 * f)
        row = g[:, i0] * (1 - f) + g[:, i1] * f            # interpolate along x
        col = row[i0, :] * (1 - f)[:, None] + row[i1, :] * f[:, None]
        out += amp * col
        amp *= gain
    out -= out.min()
    return out / out.max()


def to_srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


h = 0.6 * periodic_noise(6) + 0.4 * periodic_noise(40, 3)
albedo_lin = (0.80 + 0.12 * (h - 0.5))[..., None] * np.array([1.0, 0.99, 0.96], np.float32)   # near-neutral light map (tinted by the consumer)
dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
nx, ny, nz = -dx * 6.0, dy * 6.0, np.ones_like(h)                                     # tangent basis, +Y up
inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
normal = np.stack([nx * inv, ny * inv, nz * inv], -1)
ao = np.clip(0.92 + 0.08 * h, 0, 1)
rough = np.clip(0.85 + 0.08 * (h - 0.5), 0, 1)
metal = np.zeros_like(h)

out = sys.argv[1] if len(sys.argv) > 1 else "sample-out"
d = os.path.join(out, "finishes", "textures", "plaster_example")
os.makedirs(d, exist_ok=True)
Image.fromarray((to_srgb(albedo_lin) * 255 + 0.5).astype(np.uint8)).save(os.path.join(d, "albedo.png"), optimize=True)
Image.fromarray(((normal * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(os.path.join(d, "normal.png"), optimize=True)
Image.fromarray((np.stack([ao, rough, metal], -1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(d, "orm.png"), optimize=True)
with open(os.path.join(d, "set.json"), "w", newline="\n") as fh:
    json.dump({"name": "plaster_example", "version": "1.0.0", "sizePixels": SIZE, "tileMetres": 2.0, "tintMode": "multiply",
               "direction": "none", "description": "fine plaster with low relief, near-neutral light albedo",
               "maps": {"albedo": "albedo.png", "normal": "normal.png", "orm": "orm.png"},
               "generator": "tools/make_sample_texture_set.py, seed 7"}, fh, indent=2)
    fh.write("\n")
print("wrote", d)
