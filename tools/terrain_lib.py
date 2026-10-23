# SPDX-License-Identifier: Apache-2.0
"""Shared terrain helpers: read a height patch (GeoTIFF, one float32 band, metres) with strict checks, reduce it to a triangulated
network with a stated error bound, look heights up in a network, and find a building's ground-contact levels and footprints.

Used by terrain_import.py, site_request.py, make_sample_terrain.py and check_ifc.py. Frames: the site frame is x east, y north,
z up, metres, with heights above sea level; the file frame is the site frame shifted by the building origin, turned by the building
azimuth and shifted down by the floor height.

Requires: pip install numpy (pillow to read or write a patch, scipy to reduce one, shapely for footprints)
"""
import hashlib
import math
import warnings

import numpy as np

TAG_PIXEL_SCALE, TAG_TIEPOINT, TAG_NODATA, TAG_GEOKEYS, TAG_TRANSFORMATION = 33550, 33922, 42113, 34735, 34264
KEY_RASTER_TYPE, RASTER_PIXEL_IS_AREA = 1025, 1
MAX_SAMPLES = 25000000          # most samples read from one patch (the profile's extensions.terrain.maxPatchSamples)
MAX_ABS_HEIGHT = 20000.0        # metres; anything beyond is not terrain
SENTINELS = (-9999.0, -32768.0)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PatchError(Exception):
    """The height patch cannot be used; the message says why."""


def read_patch(path, max_samples=MAX_SAMPLES):
    """Read a GeoTIFF height patch. Returns (z, info): z is a float64 array (rows north to south, columns west to east) and info has
    `pixelSize` (one number: square pixels are required) and `origin` (the outer north-west corner). The file must carry the pixel
    scale and tie point tags, state pixel-is-area, hold no no-data samples or sentinel values, and stay within `max_samples`."""
    from PIL import Image
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            Image.MAX_IMAGE_PIXELS = max_samples
            im = Image.open(path)
            if im.size[0] * im.size[1] > max_samples:
                raise PatchError("%s has %d x %d samples, more than the limit of %d" % (path, im.size[0], im.size[1], max_samples))
            im.load()
    except PatchError:
        raise
    except Exception as exc:                                     # not a readable image, or too large
        raise PatchError("cannot read %s: %s" % (path, exc))
    if im.mode != "F":
        raise PatchError("%s is %s, not a single band of 32-bit floats" % (path, im.mode))
    z = np.array(im, dtype=np.float64)
    tags = getattr(im, "tag_v2", {})
    if TAG_TRANSFORMATION in tags:
        raise PatchError("%s carries a ModelTransformation tag (a rotated or sheared raster); only the pixel scale and tie point form is accepted" % path)
    scale, tie = tags.get(TAG_PIXEL_SCALE), tags.get(TAG_TIEPOINT)
    if not (scale and tie and len(scale) >= 2 and len(tie) >= 6):
        raise PatchError("%s lacks the GeoTIFF pixel scale and tie point tags; the terrain source must write them" % path)
    sx, sy = float(scale[0]), float(scale[1])
    if sx <= 0 or abs(sx - sy) > 1e-9 * max(sx, sy):
        raise PatchError("%s has pixels of %g by %g m; square pixels are required" % (path, sx, sy))
    keys = tags.get(TAG_GEOKEYS)
    if keys and len(keys) >= 4:
        for i in range(int(keys[3])):
            k = keys[4 + 4 * i:8 + 4 * i]
            if len(k) == 4 and k[0] == KEY_RASTER_TYPE and k[3] != RASTER_PIXEL_IS_AREA:
                raise PatchError("%s is not pixel-is-area (GeoKey 1025 = %d); the tie point must be the outer corner of the first pixel" % (path, k[3]))
    nodata = tags.get(TAG_NODATA)
    if nodata is not None:
        try:
            nd = float(str(nodata).strip("\x00 "))
        except ValueError:
            raise PatchError("%s has a no-data tag %r that is not a number" % (path, nodata))
        if np.any(z == nd):
            raise PatchError("%s has no-data samples; the terrain source must deliver a complete patch" % path)
    if not np.all(np.isfinite(z)):
        raise PatchError("%s has samples that are not finite numbers" % path)
    if np.any(np.isin(z, SENTINELS)) or float(np.abs(z).max()) > MAX_ABS_HEIGHT:
        raise PatchError("%s has heights that look like no-data sentinels or are not terrain (limit %g m)" % (path, MAX_ABS_HEIGHT))
    return z, {"pixelSize": sx, "origin": (float(tie[3]) - float(tie[0]) * sx, float(tie[4]) + float(tie[1]) * sy)}


def write_patch(path, z, origin, pixel_size, nodata=-9999.0):
    """Write a float32 GeoTIFF with the pixel scale, tie point and pixel-is-area tags (origin = outer north-west corner)."""
    from PIL import Image, TiffImagePlugin
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[TAG_PIXEL_SCALE] = (float(pixel_size), float(pixel_size), 0.0)
    ifd.tagtype[TAG_PIXEL_SCALE] = 12
    ifd[TAG_TIEPOINT] = (0.0, 0.0, 0.0, float(origin[0]), float(origin[1]), 0.0)
    ifd.tagtype[TAG_TIEPOINT] = 12
    ifd[TAG_GEOKEYS] = (1, 1, 0, 1, KEY_RASTER_TYPE, 0, 1, RASTER_PIXEL_IS_AREA)
    ifd.tagtype[TAG_GEOKEYS] = 3
    ifd[TAG_NODATA] = str(nodata)
    Image.fromarray(np.asarray(z, dtype=np.float32), mode="F").save(path, tiffinfo=ifd, compression="tiff_adobe_deflate")


def sample_grid(z, origin, pixel_size):
    """Sample positions of a patch in the site frame: the pixel centres. Returns X, Y arrays shaped like z."""
    h, w = z.shape
    xs = origin[0] + (np.arange(w) + 0.5) * pixel_size
    ys = origin[1] - (np.arange(h) + 0.5) * pixel_size
    return np.meshgrid(xs, ys)


def patch_extent(shape, origin, pixel_size):
    """(xmin, ymin, xmax, ymax) between the first and last sample centres of a patch, in the site frame."""
    h, w = shape
    return (origin[0] + 0.5 * pixel_size, origin[1] - (h - 0.5) * pixel_size, origin[0] + (w - 0.5) * pixel_size, origin[1] - 0.5 * pixel_size)


def bilinear(z, origin, pixel_size, x, y):
    """Height of the raster at one site-frame point, bilinear between sample centres. A point outside the sample centres is an error:
    nothing is clamped."""
    h, w = z.shape
    xmin, ymin, xmax, ymax = patch_extent(z.shape, origin, pixel_size)
    eps = 1e-9 * max(1.0, pixel_size)
    if not (xmin - eps <= x <= xmax + eps and ymin - eps <= y <= ymax + eps):
        raise ValueError("the point (%g, %g) is outside the patch" % (x, y))
    c = min(max((x - origin[0]) / pixel_size - 0.5, 0.0), w - 1.0)
    r = min(max((origin[1] - y) / pixel_size - 0.5, 0.0), h - 1.0)
    c0, r0 = int(math.floor(c)), int(math.floor(r))
    c1, r1 = min(c0 + 1, w - 1), min(r0 + 1, h - 1)
    fc, fr = c - c0, r - r0
    return float((z[r0, c0] * (1 - fc) + z[r0, c1] * fc) * (1 - fr) + (z[r1, c0] * (1 - fc) + z[r1, c1] * fc) * fr)


def decimate(z, eps, max_triangles=None, max_rounds=60):
    """Reduce a height grid to a triangulated network whose height differs from every sample by at most `eps` (> 0).

    Starts from the four corners and adds, round by round, the worst sample of every triangle that still exceeds `eps`, with a
    Delaunay triangulation of the plan positions, so the result is a heightfield over the whole rectangle. Returns
    (vertices, triangles, max_error): vertices are (column, row) index pairs, triangles are index triples into them in no
    particular winding (use faces_up once the vertices have plan coordinates), max_error is the largest difference at any
    sample. The bound holds at the sample positions only; between samples the network is a straight interpolation.
    Raises PatchError when the network would need more than `max_triangles` or more than `max_rounds` rounds."""
    from scipy.spatial import Delaunay
    if not eps > 0:
        raise ValueError("the error bound must be greater than 0")
    h, w = z.shape
    if h < 2 or w < 2:
        raise PatchError("a patch needs at least 2 by 2 samples")
    rr, cc = np.mgrid[0:h, 0:w]
    samples = np.column_stack([cc.ravel(), rr.ravel()]).astype(float)
    zf = z.ravel()
    chosen = {(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)}
    for _ in range(max_rounds):
        verts = np.array(sorted(chosen), dtype=float)
        tri = Delaunay(verts)
        if max_triangles is not None and len(tri.simplices) > max_triangles:
            raise PatchError("staying within %g m needs more than %d triangles; raise the error bound (within the profile's limit), coarsen "
                             "the patch or cut a smaller one" % (eps, max_triangles))
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
            return verts.astype(int), tri.simplices.copy(), worst
        cand = np.where(err > eps)[0]
        order = np.lexsort((-err[cand], simplex[cand]))
        cand, sid = cand[order], simplex[cand][order]
        _, first = np.unique(sid, return_index=True)
        for i in cand[first]:
            chosen.add((int(samples[i, 0]), int(samples[i, 1])))
    raise PatchError("the reduction did not reach %g m in %d rounds; the patch is too rough for that bound (raise it or coarsen the patch)" % (eps, max_rounds))


def faces_up(xy, tris):
    """Reorder every triangle so that it faces up in a frame where x runs east and y runs north."""
    a, b, c = xy[tris[:, 0]], xy[tris[:, 1]], xy[tris[:, 2]]
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    out = tris.copy()
    flip = cross < 0
    out[flip] = tris[flip][:, [0, 2, 1]]
    return out


def heights_at(verts, tris, points):
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


# ------------------------------------------------------------------ ground-contact levels and footprints (shared by the request and the checker)
def ground_levels(model):
    """The levels that touch the ground: those declared with GroundContact true in Pset_Declaration_Level (B-141), else the lowest
    level. Sorted by elevation."""
    storeys = model.by_type("IfcBuildingStorey")
    if not storeys:
        return []
    flagged = []
    for st in storeys:
        for rel in st.IsDefinedBy or []:
            ps = getattr(rel, "RelatingPropertyDefinition", None)
            if ps is not None and ps.is_a("IfcPropertySet") and ps.Name == "Pset_Declaration_Level":
                for p in ps.HasProperties or []:
                    if p.Name == "GroundContact" and p.NominalValue is not None and p.NominalValue.wrappedValue is True:
                        flagged.append(st)
    return sorted(flagged or [min(storeys, key=lambda x: x.Elevation if x.Elevation is not None else 0.0)], key=lambda x: x.Elevation or 0.0)


def level_elements(model, storey):
    """The slabs and walls contained in one level."""
    out = []
    for rel in storey.ContainsElements or []:
        out += [e for e in rel.RelatedElements if e.is_a("IfcSlab") or e.is_a("IfcWall")]
    return out


def footprint_polygon(model, storey, mesh_of):
    """Plan footprint (a shapely geometry, in the frame of the meshes) of the slabs and walls of one level, or None.
    `mesh_of(element)` returns (vertices (n, 3), faces (m, 3)) in that frame, or None for an element without geometry."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    parts = []
    for e in level_elements(model, storey):
        mesh = mesh_of(e)
        if mesh is None:
            continue
        v, f = mesh
        for tri in v[f][:, :, :2]:
            p = Polygon(tri)
            if p.area > 1e-9:
                parts.append(p)
    return unary_union(parts).buffer(0) if parts else None


def sample_polygon(geom, spacing=2.0, cap=1500):
    """Points that stand for a footprint: every ring vertex, points along every ring edge at most `spacing` apart, and a grid of
    `spacing` inside. Over `cap` points the convex hull vertices and the extremes in four directions are kept, plus an even share of
    the rest. Returns an (n, 2) array."""
    import shapely
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    pts = []
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            c = np.array(ring.coords)[:-1]
            for a, b in zip(c, np.roll(c, -1, axis=0)):
                n = max(1, int(math.ceil(np.hypot(*(b - a)) / spacing)))
                pts.append(a + (b - a) * (np.arange(n)[:, None] / n))
        x0, y0, x1, y1 = p.bounds
        gx, gy = np.meshgrid(np.arange(x0, x1 + spacing, spacing), np.arange(y0, y1 + spacing, spacing))
        g = np.column_stack([gx.ravel(), gy.ravel()])
        pts.append(g[shapely.contains_xy(p, g[:, 0], g[:, 1])])
    u = np.unique(np.round(np.vstack(pts), 3), axis=0) if pts else np.zeros((0, 2))
    if len(u) <= cap:
        return u
    hull = np.array(geom.convex_hull.exterior.coords)[:-1] if geom.convex_hull.geom_type == "Polygon" else np.zeros((0, 2))
    keep = [hull] + [u[[np.argmin(k), np.argmax(k)]] for k in (u[:, 0], u[:, 1], u[:, 0] + u[:, 1], u[:, 0] - u[:, 1])]
    rest = u[np.linspace(0, len(u) - 1, max(1, cap - sum(len(k) for k in keep))).astype(int)]
    return np.unique(np.round(np.vstack(keep + [rest]), 3), axis=0)
