# SPDX-License-Identifier: Apache-2.0
"""Shared terrain helpers: read a height patch (GeoTIFF, one float32 band, metres), reduce it to a triangulated network with a
stated error bound, and look heights up in a network.

Used by terrain_import.py, make_sample_terrain.py and check_ifc.py. Frames: the site frame is x east, y north, z up, metres, with
heights above sea level; the file frame is the site frame shifted by the building origin (x, y) and by the floor height (z).

Requires: pip install numpy pillow scipy
"""
import hashlib
import math

import numpy as np
from PIL import Image

TAG_PIXEL_SCALE, TAG_TIEPOINT, TAG_NODATA = 33550, 33922, 42113


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PatchError(Exception):
    """The height patch cannot be used; the message says why."""


def read_patch(path):
    """Read a GeoTIFF height patch. Returns (z, info): z is a float64 array (rows north to south, columns west to east) and info
    has the georeferencing found in the file (`pixelSize`, `origin` = outer north-west corner, or None when the tags are absent)."""
    try:
        im = Image.open(path)
        im.load()
    except Exception as exc:                                     # not a readable image
        raise PatchError("cannot read %s: %s" % (path, exc))
    if im.mode != "F":
        raise PatchError("%s is %s, not a single band of 32-bit floats" % (path, im.mode))
    z = np.array(im, dtype=np.float64)
    tags = getattr(im, "tag_v2", {})
    nodata = tags.get(TAG_NODATA)
    if nodata is not None:
        try:
            if np.any(z == float(str(nodata).strip("\x00 "))):
                raise PatchError("%s has no-data samples; the terrain source must deliver a complete patch" % path)
        except ValueError:
            pass
    if not np.all(np.isfinite(z)):
        raise PatchError("%s has samples that are not finite numbers" % path)
    info = {"pixelSize": None, "origin": None}
    scale, tie = tags.get(TAG_PIXEL_SCALE), tags.get(TAG_TIEPOINT)
    if scale and tie and len(scale) >= 2 and len(tie) >= 6:
        info["pixelSize"] = (float(scale[0]), float(scale[1]))
        info["origin"] = (float(tie[3]) - float(tie[0]) * float(scale[0]), float(tie[4]) + float(tie[1]) * float(scale[1]))
    return z, info


def write_patch(path, z, origin, pixel_size, nodata=-9999.0):
    """Write a float32 GeoTIFF with the pixel scale and tie point tags (origin = outer north-west corner)."""
    from PIL import TiffImagePlugin
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[TAG_PIXEL_SCALE] = (float(pixel_size), float(pixel_size), 0.0)
    ifd.tagtype[TAG_PIXEL_SCALE] = 12
    ifd[TAG_TIEPOINT] = (0.0, 0.0, 0.0, float(origin[0]), float(origin[1]), 0.0)
    ifd.tagtype[TAG_TIEPOINT] = 12
    ifd[TAG_NODATA] = str(nodata)
    Image.fromarray(np.asarray(z, dtype=np.float32), mode="F").save(path, tiffinfo=ifd, compression="tiff_adobe_deflate")


def sample_grid(z, origin, pixel_size):
    """Sample positions of a patch in the site frame: the pixel centres. Returns X, Y arrays shaped like z."""
    h, w = z.shape
    xs = origin[0] + (np.arange(w) + 0.5) * pixel_size
    ys = origin[1] - (np.arange(h) + 0.5) * pixel_size
    return np.meshgrid(xs, ys)


def bilinear(z, origin, pixel_size, x, y):
    """Height of the raster at one site-frame point, bilinear between sample centres (clamped to the patch)."""
    h, w = z.shape
    c = min(max((x - origin[0]) / pixel_size - 0.5, 0.0), w - 1.0)
    r = min(max((origin[1] - y) / pixel_size - 0.5, 0.0), h - 1.0)
    c0, r0 = int(math.floor(c)), int(math.floor(r))
    c1, r1 = min(c0 + 1, w - 1), min(r0 + 1, h - 1)
    fc, fr = c - c0, r - r0
    return float((z[r0, c0] * (1 - fc) + z[r0, c1] * fc) * (1 - fr) + (z[r1, c0] * (1 - fc) + z[r1, c1] * fc) * fr)


def decimate(z, eps):
    """Reduce a height grid to a triangulated network whose height differs from every sample by at most `eps`.

    Starts from the four corners and adds, round by round, the worst sample of every triangle that still exceeds `eps`, with a
    Delaunay triangulation of the plan positions, so the result is a heightfield over the whole rectangle. Returns
    (vertices, triangles, max_error): vertices are (column, row) index pairs, triangles are index triples into them in no
    particular winding (use faces_up once the vertices have plan coordinates), max_error is the largest difference at any
    sample. The bound holds at the sample positions; between samples the network is a straight interpolation."""
    from scipy.spatial import Delaunay
    h, w = z.shape
    if h < 2 or w < 2:
        raise PatchError("a patch needs at least 2 by 2 samples")
    rr, cc = np.mgrid[0:h, 0:w]
    samples = np.column_stack([cc.ravel(), rr.ravel()]).astype(float)
    zf = z.ravel()
    chosen = {(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)}
    while True:
        verts = np.array(sorted(chosen), dtype=float)
        tri = Delaunay(verts)
        simplex = tri.find_simplex(samples)
        simplex[simplex < 0] = 0                                  # a sample on the hull edge: any adjacent triangle
        t = tri.transform[simplex]
        b = np.einsum("nij,nj->ni", t[:, :2], samples - t[:, 2])
        wts = np.column_stack([b, 1.0 - b.sum(axis=1)])
        vz = z[verts[:, 1].astype(int), verts[:, 0].astype(int)]
        zhat = np.einsum("ni,ni->n", wts, vz[tri.simplices[simplex]])
        err = np.abs(zf - zhat)
        worst = float(err.max())
        if worst <= eps:
            break
        cand = np.where(err > eps)[0]
        order = np.lexsort((-err[cand], simplex[cand]))
        cand, sid = cand[order], simplex[cand][order]
        _, first = np.unique(sid, return_index=True)
        for i in cand[first]:
            chosen.add((int(samples[i, 0]), int(samples[i, 1])))
    return verts.astype(int), tri.simplices.copy(), worst


def faces_up(xy, tris):
    """Reorder every triangle so that it faces up in a frame where x runs east and y runs north."""
    a, b, c = xy[tris[:, 0]], xy[tris[:, 1]], xy[tris[:, 2]]
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    out = tris.copy()
    flip = cross < 0
    out[flip] = tris[flip][:, [0, 2, 1]]
    return out


def heights_at(verts, tris, points, chunk=64):
    """Height of a triangulated network at plan points. verts is (n, 3), tris is (m, 3) zero-based, points is (k, 2).
    Returns an array of k heights with NaN where no triangle contains the point."""
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    v0, v1 = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    ok = np.abs(den) > 1e-12
    den = np.where(ok, den, 1.0)
    lo = np.minimum(np.minimum(a[:, :2], b[:, :2]), c[:, :2]) - 1e-9
    hi = np.maximum(np.maximum(a[:, :2], b[:, :2]), c[:, :2]) + 1e-9
    out = np.full(len(points), np.nan)
    for i, p in enumerate(points):
        near = np.where(ok & (p[0] >= lo[:, 0]) & (p[0] <= hi[:, 0]) & (p[1] >= lo[:, 1]) & (p[1] <= hi[:, 1]))[0]
        if not len(near):
            continue
        d = p - a[near, :2]
        u = (d[:, 0] * v1[near, 1] - v1[near, 0] * d[:, 1]) / den[near]
        v = (v0[near, 0] * d[:, 1] - d[:, 0] * v0[near, 1]) / den[near]
        inside = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
        if inside.any():
            j = int(np.argmax(inside))
            k = near[j]
            out[i] = a[k, 2] + u[j] * (b[k, 2] - a[k, 2]) + v[j] * (c[k, 2] - a[k, 2])
    return out
