#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Coincident faces: find them in a GLB, and merge them inside one product.

    python3 tools/coplanar.py MODEL.glb [MORE.glb ...] [--min-area 0.005] [--top 20] [--json]

Two triangles are coincident when they lie in the same plane, face the same way and overlap. Two nodes that share such an area fight for the same
pixels in a rasteriser (z-fighting: flicker and one surface showing through the other), and a path tracer shades them unpredictably. Faces that
point opposite ways (a skin pressed against a wall) cannot fight and are not reported. The check is an estimate: triangles are matched to a plane when all three
corners are within 2 mm of it and the normal is within about 0.6 degrees (cells of 0.01 per normal component and their neighbours find the candidates,
so a pair on the border of two cells is not missed), and the areas are the exact overlaps of the matched triangles seen in the plane. Fine tessellation
counts like coarse: only degenerate triangles are ignored. A model with more than --max-triangles (300000) triangles that share a plane with another
node, or a search that takes longer than --seconds (60), is an error, never a clean result.

For a GLB it reports the pairs of nodes (in the IFC frame, with every node transform applied) whose coincident area is at least `--min-area` square
metres, the largest first. Exit codes: 0 (the list may be empty), 2 wrong command line, 3 a file could not be read or the budget was used up.

As a library:
    find_overlaps(tris, owner, min_area)      pairs of owners with coincident faces
    union_within(groups)                     replace the coincident, overlapping triangles of one product by the union of their polygons
    union_parts(parts)                       the same for export_glb's [(rgba, Nx3 triangle soup)]; used by `export_glb.py --coplanar union`

`union_within` is for the geometry of ONE product that is built from several boxes or solids sharing a plane (a plinth and a skirting, two coats of
one wall): on every such plane the first group (by name) keeps its area, later groups lose what it covers, and the pieces are re-triangulated (onto
the reference plane of the group, at most 2 mm from where they were). It does not move products: where two different products are coincident the model has to change (a few millimetres of offset, a butt joint, one
solid), which only the author can decide; `find_overlaps` names them.
"""
import argparse
import itertools
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
from glbkit import Failed  # noqa: E402

NORMAL_CELL = 0.01         # candidate planes are looked for in cells of 0.01 per normal component and PLANE_TOL of offset, and in the cells next to them
PLANE_TOL = 0.002          # a triangle belongs to a plane when all its corners are within 2 mm of it
COS_SAME = 0.99995         # ... and its normal is within about 0.6 degrees of the plane's
MIN_TRIANGLE_AREA = 1e-8   # only degenerate triangles are ignored; a fine tessellation counts like a coarse one
MAX_PASSES = 8             # planes taken one after the other out of a cluster of near planes
MAX_TRIANGLES = 300000     # triangles that share a plane with another product: more than this and the check says it was skipped
MAX_SECONDS = 60.0         # ... and so does a check that runs longer than this


def _planes(tris):
    """(unit normals, plane offsets, areas, ok mask) of triangles (N, 3, 3)."""
    import numpy as np
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    nv = np.cross(b - a, c - a)
    ln = np.linalg.norm(nv, axis=1)
    ok = (ln / 2 >= MIN_TRIANGLE_AREA) & np.isfinite(ln)
    nn = nv / np.where(ln > 0, ln, 1.0)[:, None]
    return nn, (nn * a).sum(axis=1), ln / 2, ok


def _basis(n):
    import numpy as np
    u = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0])
    u = u / np.linalg.norm(u)
    return u, np.cross(n, u)


_NEIGHBOURS = [d for d in itertools.product((-1, 0, 1), repeat=4) if d > (0, 0, 0, 0)]


def plane_groups(tris, nn, off, area, ok, owner=None, deadline=None):
    """Groups of triangles that lie in one plane and face the same way: [(indices, unit normal, a point of the plane)].

    One routine for the finder and for the union, so they agree on what "the same plane" means. Triangles are put in cells of their normal (0.01 per
    component) and offset (2 mm); cells that touch each other form a cluster, so a pair of planes that straddles a cell border is still compared. In a
    cluster the largest triangle names a reference plane, the triangles whose three corners are within PLANE_TOL of it and whose normal is within
    about 0.6 degrees of it form a group, and the rest are tried against the next reference (at most MAX_PASSES times). Only groups of two or more
    triangles are returned and, when `owner` is given, only those with at least two owners. Triangles are never taken from one plane to another."""
    import numpy as np
    cells = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        cells[(int(np.floor(nn[i, 0] / NORMAL_CELL)), int(np.floor(nn[i, 1] / NORMAL_CELL)), int(np.floor(nn[i, 2] / NORMAL_CELL)),
               int(np.floor(off[i] / PLANE_TOL)))].append(int(i))
    parent = {k: k for k in cells}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for k in cells:
        for d in _NEIGHBOURS:
            k2 = (k[0] + d[0], k[1] + d[1], k[2] + d[2], k[3] + d[3])
            if k2 in cells:
                r1, r2 = find(k), find(k2)
                if r1 != r2:
                    parent[max(r1, r2)] = min(r1, r2)
    clusters = defaultdict(list)
    for k, members in cells.items():
        clusters[find(k)].extend(members)
    out = []
    for root in sorted(clusters):
        members = np.array(sorted(clusters[root]), dtype=int)
        if len(members) < 2 or (owner is not None and len(set(owner[members].tolist())) < 2):
            continue
        rem = members[np.lexsort((members, -area[members]))]            # the largest triangle first, ties by index
        for _ in range(MAX_PASSES):
            if len(rem) < 2:
                break
            if deadline is not None and time.monotonic() > deadline:
                raise Failed("the coincident-face check ran out of time")
            ref = rem[0]
            dist = np.abs(np.einsum("j,nkj->nk", nn[ref], tris[rem] - tris[ref, 0])).max(axis=1)
            same = (nn[rem] @ nn[ref] >= COS_SAME) & (dist <= PLANE_TOL)
            group, rem = rem[same], rem[~same]
            if len(group) >= 2 and (owner is None or len(set(owner[group].tolist())) >= 2):
                out.append((np.sort(group), nn[ref], tris[ref, 0]))
    return out


def _polygons(tris, idx, n, p0):
    """Shapely polygons of triangles seen in the plane through p0 with normal n."""
    import numpy as np
    import shapely
    u, v = _basis(n)
    q = tris[idx] - p0
    xy = np.stack([q @ u, q @ v], axis=-1)                                # (m, 3, 2)
    return shapely.polygons(xy), u, v


def _overlapping_pairs(polys, owner=None):
    """(i, j, area) of every pair i < j of polygons that overlap in area (and have different owners when `owner` is given)."""
    import numpy as np
    import shapely
    tree = shapely.STRtree(polys)
    a, b = tree.query(polys, predicate="intersects")
    keep = a < b
    if owner is not None:
        keep &= owner[a] != owner[b]
    a, b = a[keep], b[keep]
    if not len(a):
        return a, b, np.zeros(0)
    ov = shapely.area(shapely.intersection(polys[a], polys[b]))
    return a, b, ov


def find_overlaps(tris, owner, min_area=0.005, max_triangles=MAX_TRIANGLES, seconds=MAX_SECONDS):
    """Pairs of owners whose same-facing coplanar triangles overlap by at least `min_area` square metres.

    tris: (N, 3, 3) float array of triangles in one frame; owner: N integers (the node or product each triangle belongs to). Triangles of one
    owner never count against each other. Returns [(owner a, owner b, area, normal, offset)] with a < b, the largest area first. Failed when more than
    `max_triangles` triangles share a plane with another owner's, or the check takes longer than `seconds`: it says so, it never reports a clean
    result for work it did not do."""
    import numpy as np
    deadline = time.monotonic() + seconds
    tris = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    owner = np.asarray(owner)
    nn, off, area, ok = _planes(tris)
    groups = plane_groups(tris, nn, off, area, ok, owner, deadline)
    total = sum(len(g[0]) for g in groups)
    if total > max_triangles:
        raise Failed("%d triangles share a plane with another product's (the budget is %d); the coincident-face check was not run" % (total, max_triangles))
    found, where = defaultdict(float), {}
    for idx, n, p0 in groups:
        if time.monotonic() > deadline:
            raise Failed("the coincident-face check ran out of time (%g s)" % seconds)
        polys, _u, _v = _polygons(tris, idx, n, p0)
        valid = np.asarray(__import__("shapely").is_valid(polys))
        own = owner[idx]
        if not valid.all():
            polys, own = polys[valid], own[valid]
        a, b, ov = _overlapping_pairs(polys, own)
        for i, j, o in zip(a.tolist(), b.tolist(), ov.tolist()):
            if o > 1e-6:
                pair = (int(min(own[i], own[j])), int(max(own[i], own[j])))
                found[pair] += o
                where.setdefault(pair, (tuple(round(float(x), 2) + 0.0 for x in n), float(n @ p0)))
    rows = [(a, b, ov, where[(a, b)][0], where[(a, b)][1]) for (a, b), ov in found.items() if ov >= min_area]
    return sorted(rows, key=lambda r: (-r[2], r[0], r[1]))


def glb_overlaps(data, min_area=0.005, **budget):
    """find_overlaps for a GLB: [(node name a, node name b, area, normal, offset)]. Node transforms are applied; the frame is the IFC frame.
    Failed when the file cannot be read, or the budget of find_overlaps is used up."""
    import numpy as np
    doc, bn = glbkit.split_glb(data)
    try:
        items = glbkit.triangles_of(doc, bn)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        raise Failed("the GLB cannot be read as triangles (%s: %s)" % (type(exc).__name__, str(exc)[:100]))
    names, index, tris, owner = [], {}, [], []
    for it in items:
        key = "/".join(it["path"])
        if key not in index:
            index[key] = len(names)
            names.append(key)
        tris.append(it["tri"])
        owner.append(np.full(len(it["tri"]), index[key]))
    if not tris:
        return []
    rows = find_overlaps(np.concatenate(tris), np.concatenate(owner), min_area, **budget)
    short = lambda k: k.rsplit("/", 1)[-1]  # noqa: E731
    return [(short(names[a]), short(names[b]), ov, nrm, off) for a, b, ov, nrm, off in rows]


def union_within(groups, max_triangles=MAX_TRIANGLES, seconds=MAX_SECONDS):
    """groups: {name: (T, 3, 3) triangles of one frame}. Same-facing coplanar triangles that overlap are replaced, plane by plane, by the union of
    their polygons: the first group (sorted by name) keeps the area, later groups lose what it covers. "The same plane" is what find_overlaps means by
    it (plane_groups: within 2 mm and about 0.6 degrees of a reference plane), so after the union find_overlaps finds nothing left in these planes;
    triangles of a plane group move onto its reference plane (by at most 2 mm). Returns (new groups, planes resolved, area removed in square metres).
    Needs shapely 2.1 or later (constrained Delaunay triangulation). Re-triangulated regions get corners that a neighbouring face of the product, which
    shares an edge with them, does not have: a T-junction, invisible in a rasteriser unless the product is exported with its vertices indexed and
    welded elsewhere."""
    import numpy as np
    import shapely
    from shapely.ops import unary_union
    if not hasattr(shapely, "constrained_delaunay_triangles"):
        raise Failed("the coplanar union needs shapely 2.1 or later (pip install -U shapely)")
    deadline = time.monotonic() + seconds
    names = sorted(groups)
    tris = np.concatenate([np.asarray(groups[n], dtype=float).reshape(-1, 3, 3) for n in names]) if names else np.zeros((0, 3, 3))
    sid = np.concatenate([np.full(len(groups[n]), i) for i, n in enumerate(names)]) if names else np.zeros(0, int)
    if len(tris) > max_triangles:
        raise Failed("%d triangles in one product (the budget of the coplanar union is %d)" % (len(tris), max_triangles))
    nn, d, area, ok = _planes(tris) if len(tris) else (np.zeros((0, 3)), np.zeros(0), np.zeros(0), np.zeros(0, bool))
    drop = np.zeros(len(tris), bool)
    new = {n: [] for n in names}
    planes, removed = 0, 0.0
    for idx, n, p0 in plane_groups(tris, nn, d, area, ok, None, deadline):
        polys, u, v = _polygons(tris, idx, n, p0)
        _a, _b, ov = _overlapping_pairs(polys)
        if not (ov > 1e-9).any():
            continue
        planes += 1
        covered = None
        before = float(shapely.area(polys).sum())
        for s_ in sorted({int(sid[i]) for i in idx}):
            us = unary_union([polys[k] for k, i in enumerate(idx) if sid[i] == s_])
            region = us if covered is None else us.difference(covered)
            covered = us if covered is None else covered.union(us)
            if region.is_empty:
                continue
            for poly in (region.geoms if hasattr(region, "geoms") else [region]):
                if poly.geom_type != "Polygon" or poly.area < 1e-8:
                    continue
                for t2 in shapely.constrained_delaunay_triangles(poly).geoms:
                    pts = list(t2.exterior.coords)[:3]
                    p3 = np.array([p0 + u * x + v * y for x, y in pts])
                    if np.dot(np.cross(p3[1] - p3[0], p3[2] - p3[0]), n) < 0:
                        p3 = p3[::-1]
                    new[names[s_]].append(p3)
        removed += before - covered.area
        drop[idx] = True
    out = {}
    for i, n in enumerate(names):
        keep = tris[(sid == i) & ~drop]
        extra = np.array(new[n]).reshape(-1, 3, 3) if new[n] else np.zeros((0, 3, 3))
        out[n] = np.concatenate([keep, extra]) if len(extra) else keep
    return out, planes, removed


def union_parts(parts):
    """union_within for [(rgba, Nx3 triangle soup)] (export_glb's parts of one product). Returns (parts, planes resolved, area removed). Parts that
    lose all their triangles are dropped. Vertices are rounded to 6 places, as the exporter does. Parts of one colour are one group (none of their
    triangles is lost); between colours the part with the lowest (r, g, b, a) keeps a shared area, which is the order the exporter lists the parts in,
    so the result does not depend on anything but the geometry and the colours."""
    import numpy as np
    by_colour = defaultdict(list)
    for rgba, t in parts:
        by_colour[tuple(float(x) for x in rgba)].append(np.asarray(t, dtype=float).reshape(-1, 3, 3))
    groups = {k: np.concatenate(v) for k, v in by_colour.items()}
    keys = sorted(groups)
    new, planes, removed = union_within({"%06d" % i: groups[k] for i, k in enumerate(keys)})
    out = []
    for i, k in enumerate(keys):
        t = new["%06d" % i]
        if len(t):
            out.append((k, np.round(t.reshape(-1, 3), 6) + 0.0))
    return sorted(out, key=lambda p: p[0]), planes, removed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glb", nargs="+")
    ap.add_argument("--min-area", type=float, default=0.005, help="smallest coincident area of a pair, in square metres (default 0.005)")
    ap.add_argument("--top", type=int, default=20, help="pairs to print (default 20; --json lists all)")
    ap.add_argument("--max-triangles", type=int, default=MAX_TRIANGLES, help="most triangles that share a plane with another node (default %d); more is an error" % MAX_TRIANGLES)
    ap.add_argument("--seconds", type=float, default=MAX_SECONDS, help="longest the search may take (default %g); longer is an error" % MAX_SECONDS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not (a.min_area >= 0 and a.max_triangles > 0 and a.seconds > 0 and a.top >= 0):
        print("ERROR --min-area and --top must be zero or more, --max-triangles and --seconds above zero", file=sys.stderr)
        sys.exit(2)
    out = {}
    for p in a.glb:
        try:
            with open(p, "rb") as fh:
                out[os.path.basename(p)] = glb_overlaps(fh.read(), a.min_area, max_triangles=a.max_triangles, seconds=a.seconds)
        except (OSError, Failed) as exc:
            print("ERROR %s: %s" % (p, exc), file=sys.stderr)
            sys.exit(3)
    if a.json:
        print(json.dumps({k: [{"a": x, "b": y, "areaM2": round(ov, 4), "normal": list(n), "offset": round(o, 4)} for x, y, ov, n, o in v] for k, v in out.items()}, indent=1))
        return
    for k, v in out.items():
        print("%s: %d pair(s) of nodes with coincident faces over %g m2, %.2f m2 in all" % (k, len(v), a.min_area, sum(r[2] for r in v)))
        for x, y, ov, n, o in v[:a.top]:
            print("  %7.3f m2  %s  |  %s  (normal %s, offset %.3f)" % (ov, x, y, n, o))


if __name__ == "__main__":
    main()
