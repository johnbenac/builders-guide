#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Coincident faces: find them in a GLB, and merge them inside one product.

    python3 tools/coplanar.py MODEL.glb [MORE.glb ...] [--min-area 0.005] [--top 20] [--json]

Two triangles are coincident when they lie in the same plane, face the same way and overlap. Two nodes that share such an area fight for the same
pixels in a rasteriser (z-fighting: flicker and one surface showing through the other), and a path tracer shades them unpredictably. Faces that
point opposite ways (a skin pressed against a wall) cannot fight and are not reported. The check is an estimate: planes are matched with a normal
rounded to 0.01 and a plane offset within 2 mm, and the areas are the exact overlaps of the matched triangles seen in the plane.

For a GLB it reports the pairs of nodes (in the IFC frame, with every node transform applied) whose coincident area is at least `--min-area` square
metres, the largest first. Exit codes: 0 (the list may be empty), 2 wrong command line, 3 a file could not be read.

As a library:
    find_overlaps(tris, owner, min_area)      pairs of owners with coincident faces
    union_within(groups)                     replace the coincident, overlapping triangles of one product by the union of their polygons
    union_parts(parts)                       the same for export_glb's [(rgba, Nx3 triangle soup)]; used by `export_glb.py --coplanar union`

`union_within` is for the geometry of ONE product that is built from several boxes or solids sharing a plane (a plinth and a skirting, two coats of
one wall): on every such plane the first group (by name) keeps its area, later groups lose what it covers, and the pieces are re-triangulated. It
does not move anything: where two different products are coincident the model has to change (a few millimetres of offset, a butt joint, one
solid), which only the author can decide; `find_overlaps` names them.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
from glbkit import Failed  # noqa: E402

NORMAL_DIGITS = 2          # normals are matched to 0.01
PLANE_TOL = 0.002          # offsets are matched within 2 mm
MIN_TRIANGLE_AREA = 2e-4   # smaller triangles are slivers and are ignored


def _planes(tris):
    """(unit normals, plane offsets, areas, ok mask) of triangles (N, 3, 3)."""
    import numpy as np
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    nv = np.cross(b - a, c - a)
    ln = np.linalg.norm(nv, axis=1)
    ok = ln / 2 >= MIN_TRIANGLE_AREA
    nn = nv / np.where(ln > 0, ln, 1.0)[:, None]
    return nn, (nn * a).sum(axis=1), ln / 2, ok


def _basis(n):
    import numpy as np
    u = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0])
    u = u / np.linalg.norm(u)
    return u, np.cross(n, u)


def find_overlaps(tris, owner, min_area=0.005):
    """Pairs of owners whose same-facing coplanar triangles overlap by at least `min_area` square metres.

    tris: (N, 3, 3) float array of triangles in one frame; owner: N integers (the node or product each triangle belongs to). Triangles of one
    owner never count against each other. Returns [(owner a, owner b, area, normal, offset)] with a < b, the largest area first."""
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    tris = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    owner = np.asarray(owner)
    nn, off, area, ok = _planes(tris)
    buckets = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        key = (round(float(nn[i, 0]), NORMAL_DIGITS) + 0.0, round(float(nn[i, 1]), NORMAL_DIGITS) + 0.0, round(float(nn[i, 2]), NORMAL_DIGITS) + 0.0)
        buckets[key].append(i)
    found, where = defaultdict(float), {}
    for key, idx in buckets.items():
        if len({int(owner[i]) for i in idx}) < 2:
            continue
        by_off = defaultdict(list)
        for i in idx:
            by_off[int(np.floor(off[i] / PLANE_TOL))].append(i)
        for ok_, members in by_off.items():
            cand = members + by_off.get(ok_ + 1, [])          # a plane near a bucket border belongs to both neighbours
            members_set = set(members)                          # a pair is counted in the bucket of one of its triangles, once
            if len({int(owner[i]) for i in cand}) < 2:
                continue
            n = np.array(key, dtype=float)
            n = n / np.linalg.norm(n)
            u, v = _basis(n)
            polys, own, mine = [], [], []
            for i in cand:
                p = Polygon([(float(q @ u), float(q @ v)) for q in tris[i]])
                if p.is_valid and p.area > 1e-5:
                    polys.append(p)
                    own.append(int(owner[i]))
                    mine.append(i in members_set)
            if len(polys) < 2:
                continue
            tree = STRtree(polys)
            seen = set()
            for i, p in enumerate(polys):
                for j in tree.query(p):
                    if j <= i or own[j] == own[i] or (i, int(j)) in seen or not (mine[i] or mine[j]):
                        continue
                    seen.add((i, int(j)))
                    ov = p.intersection(polys[j]).area
                    if ov > 1e-6:
                        pair = (min(own[i], own[j]), max(own[i], own[j]))
                        found[pair] += ov
                        where.setdefault(pair, (key, float(off[cand[0]])))
    rows = [(a, b, ov, where[(a, b)][0], where[(a, b)][1]) for (a, b), ov in found.items() if ov >= min_area]
    return sorted(rows, key=lambda r: (-r[2], r[0], r[1]))


def glb_overlaps(data, min_area=0.005):
    """find_overlaps for a GLB: [(node name a, node name b, area, normal, offset)]. Node transforms are applied; the frame is the IFC frame."""
    import numpy as np
    doc, bn = glbkit.split_glb(data)
    items = glbkit.triangles_of(doc, bn)
    names, tris, owner = [], [], []
    for it in items:
        key = "/".join(it["path"])
        if key not in names:
            names.append(key)
        tris.append(it["tri"])
        owner.append(np.full(len(it["tri"]), names.index(key)))
    if not tris:
        return []
    rows = find_overlaps(np.concatenate(tris), np.concatenate(owner), min_area)
    out = []
    for a, b, ov, nrm, off in rows:
        short = lambda k: k.rsplit("/", 1)[-1]  # noqa: E731
        out.append((short(names[a]), short(names[b]), ov, nrm, off))
    return out


def union_within(groups):
    """groups: {name: (T, 3, 3) triangles of one frame}. Same-facing coplanar triangles that overlap are replaced, plane by plane, by the union of
    their polygons: the first group (sorted by name) keeps the area, later groups lose what it covers. Returns (new groups, planes resolved,
    area removed in square metres). Needs shapely 2.1 or later (constrained Delaunay triangulation)."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    if not hasattr(shapely, "constrained_delaunay_triangles"):
        raise Failed("the coplanar union needs shapely 2.1 or later (pip install -U shapely)")
    names = sorted(groups)
    tris = np.concatenate([np.asarray(groups[n], dtype=float).reshape(-1, 3, 3) for n in names]) if names else np.zeros((0, 3, 3))
    sid = np.concatenate([np.full(len(groups[n]), i) for i, n in enumerate(names)]) if names else np.zeros(0, int)
    nn, d, area, ok = _planes(tris) if len(tris) else (np.zeros((0, 3)), np.zeros(0), np.zeros(0), np.zeros(0, bool))
    ok = ok & (area > 1e-12)
    keys = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        keys[(tuple(np.round(nn[i], 3) + 0.0), round(float(d[i]), 3) + 0.0)].append(i)
    drop = np.zeros(len(tris), bool)
    new = {n: [] for n in names}
    planes, removed = 0, 0.0
    for (nk, dk), idx in sorted(keys.items()):
        if len(idx) < 2:
            continue
        n = np.array(nk, dtype=float)
        n = n / np.linalg.norm(n)
        u, v = _basis(n)
        polys = [Polygon([(float(p @ u), float(p @ v)) for p in tris[i]]) for i in idx]
        tree = STRtree(polys)
        overlap = any(jj > ii and p.intersection(polys[jj]).area > 1e-9 for ii, p in enumerate(polys) for jj in tree.query(p))
        if not overlap:
            continue
        planes += 1
        base = n * dk
        covered = None
        before = sum(p.area for p in polys)
        for s in sorted({int(sid[i]) for i in idx}):
            us = unary_union([polys[k] for k, i in enumerate(idx) if sid[i] == s])
            region = us if covered is None else us.difference(covered)
            covered = us if covered is None else covered.union(us)
            if region.is_empty:
                continue
            for poly in (region.geoms if hasattr(region, "geoms") else [region]):
                if poly.geom_type != "Polygon" or poly.area < 1e-8:
                    continue
                for t2 in shapely.constrained_delaunay_triangles(poly).geoms:
                    pts = list(t2.exterior.coords)[:3]
                    p3 = np.array([base + u * x + v * y for x, y in pts])
                    if np.dot(np.cross(p3[1] - p3[0], p3[2] - p3[0]), n) < 0:
                        p3 = p3[::-1]
                    new[names[s]].append(p3)
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
    lose all their triangles are dropped. Vertices are rounded to 6 places, as the exporter does."""
    import numpy as np
    groups = {tuple(float(x) for x in rgba): np.asarray(t, dtype=float).reshape(-1, 3, 3) for rgba, t in parts}
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
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = {}
    for p in a.glb:
        try:
            with open(p, "rb") as fh:
                out[os.path.basename(p)] = glb_overlaps(fh.read(), a.min_area)
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
