#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Can a body of a given radius walk to every room? A 3D voxel walk through the whole-model GLB.

    python3 tools/walkcheck.py MODEL.glb --start X,Y,Z [--radius 0.30 0.45 ...] [--doors open|solid] [--waypoint NAME=X,Y,Z ...]
                               [--res 0.05] [--step H] [--riser H] [--body-height 1.75] [--require RADIUS] [--profile PROFILE.json]
                               [--max-memory-mb 4096] [--out REPORT.json] [--json]

The GLB is what a consumer sees, so the walk is measured on it (every node transform applied, coordinates converted back to the IFC frame, metres):

  1. every triangle is sampled onto a voxel grid (`--res` metres in plan and in height); the voxels they touch are solid. Door leaves are left out
     with `--doors open` (the default: a door is a way through) and solid with `--doors solid`; windows, furniture, fixtures and planting are solid;
  2. a standing place is a voxel that holds an upward-facing surface of the building (floor, slab, covering, tread, terrain; never furniture or
     planting) with a free cylinder of the body radius from `--riser` to `--body-height` above it, and free feet (a cylinder of 2.5 cm) from 5 cm up
     to the largest riser `--step`: a walker steps over a riser of that height but not through a chair leg or a basket;
  3. two neighbouring standing places are joined when they are 8-neighbours in plan (or two cells out across a step) and differ in height by at
     most `--step`;
  4. from `--start` the connected set is grown at each body radius; each room of the GLB (`extras.rooms`, footprint and level) is reported with the
     area that can be reached, and every `--waypoint` with the component it is in. A route that survives a body radius of 0.45 m has a clear
     width of at least 0.90 m everywhere along it.

Stairs. `--step` is the largest riser a walker steps over: it defaults to the profile's `geometry.stairRiserLimitMetres` (B-61, 0.19 m in the default
profile; `--profile` names another), taken up to the next grid cell, so every stair that keeps the guide's riser limit can be climbed. The wide
part of the body (the radius) must be clear from `--riser` above the surface, so that the next tread of a stair, which is a riser higher, is not
inside the body: `--riser` defaults to the step height plus one grid cell (0.25 m at the defaults) and cannot be lower than the step height. A riser
above `--step` cuts the stair off, which is the answer when the stair does not keep the limit. (The profile's
`extensions.walkability.stepHeightMetres` is the height of a step taken without noticing, a different number.)

Report (`walk-report/1`, `schemas/walk-report.schema.json`): per radius (keyed by the radius with two decimals, with more digits when it has more) the
standing places, the components, whether the start was found, per room the walkable and reachable areas and the share of the walkable area that is
reachable, per waypoint its component.

Size and time. The grid covers the whole model (taken from its triangles, not from what the file says about its size) at `--res`. It needs about
20 bytes per cell and 200 bytes per standing place, so a 20 x 20 x 7 m building at 0.05 m is 22 million cells and about 0.5 GB, and 40 x 30 x 10 m is 96 million and about 2 GB.
The tool computes the cells and the number of surface samples (about 2 million samples per second) before it allocates anything, and stops with
an error and a suggestion (a coarser `--res`) when the cells need more than `--max-memory-mb` (default 4096) or the samples exceed
200 million. Terrain that reaches far from the building counts: a 100 x 100 m patch is 40 million cells per metre of height at 0.05 m.

Exit codes: 0 done, 1 the start is not on a standing place at some radius, or with `--require RADIUS` some non-external room has no reachable
standing place at that radius, 2 wrong command line, 3 the GLB could not be read or is malformed, the size budget was exceeded, or scipy is missing.
Requires numpy, scipy and shapely (tools/requirements.txt). A negative first coordinate is written `--start=-8,7,0`.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
import report as rpt  # noqa: E402
from glbkit import Failed  # noqa: E402

VERSION = "2.4.0"
SUPPORT_KINDS = {"structure", "covering", "terrain"}
FEET_LO = 0.05            # the feet occupy 5 cm to `step` above the surface
FEET_RADIUS = 0.025
DEFAULT_STEP = 0.19       # when the profile does not state geometry.stairRiserLimitMetres
BYTES_PER_CELL = 20       # measured 16 to 18 bytes per cell of the grid, with the arrays of one radius
BYTES_PER_PLACE = 200     # the links between standing places (12 neighbours, two 4-byte indices each, and the sparse matrix built from them)
DEFAULT_MAX_MB = 4096
MAX_SAMPLES = 200_000_000 # surface samples, about 2 million per second
MAX_SUB = 160             # a triangle edge is cut into pieces of at most this many sample steps, so no piece needs more than a few MB


def sample_count(tri, spacing):
    """How many surface samples sample_triangles() makes for these triangles (N, 3, 3), without making them."""
    import numpy as np
    e = np.maximum(np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1), np.linalg.norm(tri[:, 2] - tri[:, 0], axis=1))
    m = np.maximum(1, np.ceil(e / spacing)).astype(np.int64)
    return int(((m + 1) * (m + 2) // 2).sum())


def _subdivide(tri, k):
    """One triangle (3, 3) cut into k * k triangles (k * k, 3, 3)."""
    import numpy as np
    pts = {}
    a, b, c = tri
    for i in range(k + 1):
        for j in range(k + 1 - i):
            pts[(i, j)] = a + (b - a) * (i / k) + (c - a) * (j / k)
    out = []
    for i in range(k):
        for j in range(k - i):
            out.append((pts[(i, j)], pts[(i + 1, j)], pts[(i, j + 1)]))
            if i + j < k - 1:
                out.append((pts[(i + 1, j)], pts[(i + 1, j + 1)], pts[(i, j + 1)]))
    return np.array(out)


def sample_triangles(tri, spacing):
    """Points on the surface of every triangle (barycentric lattice finer than `spacing`), in batches of about two million points at most: a
    generator of (points (M, 3), triangle index (M,)). A triangle with an edge of more than MAX_SUB steps is cut into smaller ones first, so that one
    large triangle (a terrain quad) never needs a lattice of hundreds of megabytes."""
    import numpy as np
    e = np.maximum(np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1), np.linalg.norm(tri[:, 2] - tri[:, 0], axis=1))
    big = np.flatnonzero(e / spacing > MAX_SUB)
    parent = np.arange(len(tri))
    if len(big):
        keep = np.ones(len(tri), bool)
        keep[big] = False
        pieces, owners = [tri[keep]], [parent[keep]]
        for b in big:
            k = int(math.ceil(e[b] / spacing / MAX_SUB))
            sub = _subdivide(tri[b], k)
            pieces.append(sub)
            owners.append(np.full(len(sub), b))
        tri, parent = np.concatenate(pieces), np.concatenate(owners)
    v0 = tri[:, 0]
    e1 = tri[:, 1] - v0
    e2 = tri[:, 2] - v0
    m = np.maximum(1, np.ceil(np.maximum(np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1)) / spacing).astype(int))
    for mv in np.unique(m):
        sel = np.flatnonzero(m == mv)
        i, j = np.meshgrid(np.arange(mv + 1), np.arange(mv + 1), indexing="ij")
        ok = (i + j) <= mv
        u = (i[ok] / mv)[None, :, None]
        w = (j[ok] / mv)[None, :, None]
        step = max(1, int(2_000_000 // max(1, ok.sum())))
        for a in range(0, len(sel), step):
            s = sel[a:a + step]
            p = v0[s][:, None, :] + u * e1[s][:, None, :] + w * e2[s][:, None, :]
            yield p.reshape(-1, 3), np.repeat(parent[s], ok.sum())


def _finite_numbers(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)


class World:
    """The triangles of a model GLB in the IFC frame, with which of them are solid and which can be stood on."""

    def __init__(self, data, doors="open"):
        import numpy as np
        self.doc, bn = glbkit.split_glb(data)
        if not isinstance(self.doc, dict):
            raise Failed("the GLB's JSON chunk is not an object")
        ex = self.doc.get("extras") if isinstance(self.doc.get("extras"), dict) else {}
        self.rooms = ex.get("rooms") or []
        if not isinstance(self.rooms, list):
            raise Failed("extras.rooms must be a list")
        for i, r in enumerate(self.rooms):
            fp = r.get("footprint") if isinstance(r, dict) else None
            if not (isinstance(r, dict) and isinstance(r.get("id"), str) and isinstance(fp, list) and len(fp) >= 3 and all(_finite_numbers(q, 2) for q in fp)):
                raise Failed("extras.rooms[%d] needs an id and a footprint of at least 3 [x, y] points" % i)
            if r.get("min") is not None and not _finite_numbers(r["min"], 3):
                raise Failed("extras.rooms[%d].min must be 3 finite numbers" % i)
        levels = ex.get("levels") or []
        if not (isinstance(levels, list) and all(isinstance(lv, dict) and isinstance(lv.get("name"), str) and isinstance(lv.get("elevation"), (int, float)) and
                                                  not isinstance(lv.get("elevation"), bool) and math.isfinite(lv["elevation"]) for lv in levels)):
            raise Failed("extras.levels must be a list of {name, elevation} with finite elevations")
        self.levels = {lv["name"]: lv["elevation"] for lv in levels}
        tris, support = [], []
        try:
            items = glbkit.triangles_of(self.doc, bn)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            raise Failed("the GLB cannot be read as triangles (%s: %s)" % (type(exc).__name__, str(exc)[:100]))
        for it in items:
            exn = it.get("extras") if isinstance(it.get("extras"), dict) else {}
            kind = exn.get("kind", "")
            category = exn.get("category") or ""
            if kind == "door" and doors == "open":
                continue
            tris.append(it["tri"])
            support.append(np.full(len(it["tri"]), kind in SUPPORT_KINDS and "planting" not in str(category)))
        if not tris:
            raise Failed("the GLB holds no geometry")
        self.tri = np.concatenate(tris)
        if not np.isfinite(self.tri).all():
            raise Failed("the GLB holds a non-finite coordinate")
        self.is_support = np.concatenate(support)
        # the grid is sized from the triangles themselves: a stated size that is smaller than the geometry would silently cut it, one that is not
        # a number would crash
        self.lo, self.hi = self.tri.reshape(-1, 3).min(axis=0), self.tri.reshape(-1, 3).max(axis=0)


class Grid:
    def __init__(self, world, res, body_height, step, riser_clear, max_mb=DEFAULT_MAX_MB):
        import numpy as np
        self.w, self.res, self.zres = world, res, res
        self.body_height, self.step, self.riser_clear, self.max_mb = body_height, step, riser_clear, max_mb
        pad = 0.2
        self.x0, self.y0, self.z0 = world.lo[0] - pad, world.lo[1] - pad, world.lo[2] - 0.075
        self.nx = int(math.ceil((world.hi[0] + pad - self.x0) / res))
        self.ny = int(math.ceil((world.hi[1] + pad - self.y0) / res))
        self.nz = int(math.ceil((world.hi[2] + 0.1 - self.z0) / self.zres))
        cells = self.nx * self.ny * self.nz
        self.estimated_mb = cells * BYTES_PER_CELL / 1e6
        if self.estimated_mb > max_mb:
            raise Failed("the grid would have %d x %d x %d = %.0f million cells, about %.0f MB (the limit is %d MB, --max-memory-mb); use a coarser --res (now %g m)"
                         % (self.nx, self.ny, self.nz, cells / 1e6, self.estimated_mb, max_mb, res))
        self.samples = sample_count(world.tri, res * 0.45)
        if self.samples > MAX_SAMPLES:
            raise Failed("the surfaces need %d million samples (the limit is %d million); use a coarser --res (now %g m)" % (self.samples // 1_000_000, MAX_SAMPLES // 1_000_000, res))
        self.blocked = np.zeros((self.nx, self.ny, self.nz), bool)
        self.sup = np.zeros((self.nx, self.ny, self.nz), bool)
        self._voxelize()
        self._distances()

    def _voxelize(self):
        import numpy as np
        w, res = self.w, self.res
        tri = w.tri
        lo, hi = tri.min(axis=1), tri.max(axis=1)
        zmax = self.z0 + self.nz * self.zres
        inside = (hi[:, 2] > self.z0) & (lo[:, 2] < zmax)
        idx = np.flatnonzero(inside)
        n = np.cross(tri[idx, 1] - tri[idx, 0], tri[idx, 2] - tri[idx, 0])
        ln = np.linalg.norm(n, axis=1)
        good = ln > 1e-12
        idx, n, ln = idx[good], n[good], ln[good]
        up = (n[:, 2] / ln > 0.7) & w.is_support[idx]
        for c0 in range(0, len(idx), 4000):
            sl = slice(c0, c0 + 4000)
            for pts, tid in sample_triangles(tri[idx[sl]], res * 0.45):
                ix = np.floor((pts[:, 0] - self.x0) / res).astype(np.int32)
                iy = np.floor((pts[:, 1] - self.y0) / res).astype(np.int32)
                iz = np.floor((pts[:, 2] - self.z0) / self.zres).astype(np.int32)
                ok = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny) & (iz >= 0) & (iz < self.nz)
                ix, iy, iz, tid = ix[ok], iy[ok], iz[ok], tid[ok]
                self.blocked[ix, iy, iz] = True
                u = up[sl][tid]
                self.sup[ix[u], iy[u], iz[u]] = True
        # a floor finish lies on its slab: surfaces within 5 cm are one walking surface, the upper one is the one walked on
        for off in range(1, max(1, int(round(0.05 / self.zres))) + 1):
            dup = np.zeros_like(self.sup)
            dup[:, :, :-off] = self.sup[:, :, off:]
            self.sup &= ~dup

    def _distances(self):
        """Per height slice: distance (in cells) from every free cell to the nearest solid cell."""
        import numpy as np
        from scipy import ndimage
        self.dist = np.empty((self.nx, self.ny, self.nz), np.float32)
        for k in range(self.nz):
            b = self.blocked[:, :, k]
            self.dist[:, :, k] = ndimage.distance_transform_edt(~b) if b.any() else 1e4

    def standing_places(self, radius):
        """(ix, iy, iz, key) of the standing places of a body of this radius, sorted by plan cell then height."""
        import numpy as np
        res, zres = self.res, self.zres
        rc = radius / res
        rf = max(FEET_RADIUS / res, 1.0)
        lo_u, hi = int(round(self.riser_clear / zres)), int(round(self.body_height / zres))
        lo_f = max(1, int(round(FEET_LO / zres)))                  # never the surface voxel itself (at --res 0.1 the rounding gave 0)
        hi_f = max(self.step_cells(), lo_f + 1)
        k = np.arange(self.nz)

        def free_between(thr, a, b):
            bad = (self.dist < thr).astype(np.int16)
            cs = np.cumsum(bad, axis=2, dtype=np.int16)
            kb = np.minimum(k + b, self.nz - 1)
            ka = np.minimum(k + a - 1, self.nz - 1)
            return (cs[:, :, kb] - cs[:, :, ka]) == 0
        walk = self.sup & free_between(rc, lo_u, hi) & free_between(rf, lo_f, hi_f)
        ixs, iys, izs = np.nonzero(walk)
        key = ixs.astype(np.int64) * self.ny + iys
        order = np.lexsort((izs, key))
        return ixs[order], iys[order], izs[order], key[order]

    def step_cells(self):
        """The largest riser in cells: two surfaces `step` apart can be this many cells apart."""
        return int(math.ceil(self.step / self.zres - 1e-9))

    def components(self, radius):
        import numpy as np
        from scipy.sparse import coo_matrix, csgraph
        ixs, iys, izs, key = self.standing_places(radius)
        n = len(ixs)
        need = self.estimated_mb + n * BYTES_PER_PLACE / 1e6
        if need > self.max_mb:
            raise Failed("the grid and the %d standing places at radius %g would need about %.0f MB (the limit is %d MB, --max-memory-mb); use a coarser --res (now %g m)"
                         % (n, radius, need, self.max_mb, self.res))
        rows, cols = [], []
        kmax = self.step_cells()
        uk, first, cnt = np.unique(key, return_index=True, return_counts=True)
        maxc = int(cnt.max()) if n else 0
        # the 8 neighbours at any permitted height difference; the ring two cells out only across a step (a riser between two treads leaves a gap
        # of a cell or two between the last cell with free feet below it and the first on the tread above)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if (dx, dy) <= (0, 0):
                    continue                         # a link is symmetric: half of the neighbours find all of them
                ring2 = max(abs(dx), abs(dy)) == 2
                nk = key + dx * self.ny + dy
                pos = np.minimum(np.searchsorted(uk, nk), max(len(uk) - 1, 0))
                found = (uk[pos] == nk) if len(uk) else np.zeros(n, bool)
                for s in range(maxc):
                    ok = found & (s < cnt[pos])
                    j = np.where(ok, first[pos] + s, 0)
                    dkk = np.abs(izs[j] - izs)
                    ok &= dkk <= kmax
                    if ring2:
                        ok &= dkk >= 3
                    a = np.flatnonzero(ok)
                    rows.append(a.astype(np.int32))
                    cols.append(j[a].astype(np.int32))
        r = np.concatenate(rows) if rows else np.zeros(0, np.int32)
        c = np.concatenate(cols) if cols else np.zeros(0, np.int32)
        g = coo_matrix((np.ones(len(r), np.int8), (r, c)), shape=(n, n)).tocsr()
        ncomp, lab = csgraph.connected_components(g, directed=False)
        return dict(ixs=ixs, iys=iys, izs=izs, key=key, uk=uk, first=first, cnt=cnt, lab=lab, ncomp=int(ncomp), radius=radius)

    def cell(self, comp, x, y, z, search=0.35):
        """Index of the standing place nearest to (x, y) at height about z, or None."""
        import numpy as np
        ix = int(math.floor((x - self.x0) / self.res))
        iy = int(math.floor((y - self.y0) / self.res))
        iz = (z - self.z0) / self.zres
        rr = int(round(search / self.res))
        best, bd = None, 1e9
        for dx in range(-rr, rr + 1):
            for dy in range(-rr, rr + 1):
                kq = (ix + dx) * self.ny + (iy + dy)
                p = np.searchsorted(comp["uk"], kq)
                if p < len(comp["uk"]) and comp["uk"][p] == kq:
                    for s in range(comp["cnt"][p]):
                        j = comp["first"][p] + s
                        dz = abs(comp["izs"][j] - iz) * self.zres
                        if dz > 0.30:
                            continue
                        d = math.hypot(dx, dy) * self.res + dz
                        if d < bd:
                            best, bd = j, d
        return best


def room_stats(grid, comp, start_idx):
    """Per room of the GLB: walkable and reachable area of standing places inside its footprint at its level."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    reach = comp["lab"] == comp["lab"][start_idx]
    xs = grid.x0 + (comp["ixs"] + 0.5) * grid.res
    ys = grid.y0 + (comp["iys"] + 0.5) * grid.res
    zs = grid.z0 + (comp["izs"] + 0.5) * grid.zres
    out = []
    for r in grid.w.rooms:
        poly = Polygon(r["footprint"])
        elev = grid.w.levels.get(r.get("level"), r["min"][2] if r.get("min") else 0.0)
        inpoly = shapely.contains_xy(poly, xs, ys) & (np.abs(zs - elev) < 0.35)
        n_in, n_reach = int(inpoly.sum()), int((inpoly & reach).sum())
        cell = grid.res * grid.res
        out.append({"id": r["id"], "level": r.get("level"), "external": bool(r.get("external")), "footprintAreaM2": round(poly.area, 2),
                    "walkableAreaM2": round(n_in * cell, 2), "reachableAreaM2": round(n_reach * cell, 2),
                    "reachable": n_reach > 0, "reachableShareOfWalkable": round(n_reach / n_in, 3) if n_in else 0.0})
    return out


def radius_key(rad):
    """The key of a radius in the report: two decimals ("0.30"), more digits only when the radius has more, so two radii never share a key."""
    k = "%.2f" % rad
    return k if abs(float(k) - rad) < 1e-9 else repr(float(rad))


def check_options(radii, res, body_height, step, riser_clear, start=None, waypoints=None):
    """ValueError with the reason when a number cannot be used: radii, resolution and heights must be finite and above zero, the body must be taller
    than the step, the wide part of the body cannot start below the step."""
    def pos(name, v):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError("%s must be a finite number above 0, not %r" % (name, v))
    for rad in radii:
        pos("--radius", rad)
    pos("--res", res)
    pos("--body-height", body_height)
    pos("--step", step)
    pos("--riser", riser_clear)
    if res > 0.5:
        raise ValueError("--res %g is too coarse to see a wall; use 0.5 m or less" % res)
    if riser_clear < step - 1e-9:
        raise ValueError("--riser (%g) cannot be below --step (%g): the body would have to pass through the step it steps over" % (riser_clear, step))
    if body_height <= riser_clear:
        raise ValueError("--body-height (%g) must be above --riser (%g)" % (body_height, riser_clear))
    for name, v in ([("--start", start)] if start is not None else []) + sorted((waypoints or {}).items()):
        if not _finite_numbers(list(v), 3):
            raise ValueError("%s must be three finite numbers" % name)


def walk(data, start, radii, waypoints=None, doors="open", res=0.05, body_height=1.75, step=None, riser_clear=None, max_mb=DEFAULT_MAX_MB):
    """The walk report (a dict) for a model GLB. step defaults to the profile's stair riser limit; riser_clear to the step plus one grid cell.
    Failed when the input cannot be used or the size budget is exceeded; ValueError for numbers that make no sense."""
    try:
        import scipy  # noqa: F401
    except ImportError:
        raise Failed("walkcheck needs scipy (pip install -r tools/requirements.txt)")
    step = rpt.param("geometry.stairRiserLimitMetres", DEFAULT_STEP) if step is None else step
    if riser_clear is None:
        riser_clear = math.ceil(step / res - 1e-9) * res + res if isinstance(res, (int, float)) and res > 0 else None
    radii = sorted({round(r, 9) for r in radii if isinstance(r, (int, float))} | {r for r in radii if not isinstance(r, (int, float))})
    check_options(radii, res, body_height, step, riser_clear, start, waypoints)
    world = World(data, doors)
    grid = Grid(world, res, body_height, step, riser_clear, max_mb)
    rep = {"format": "walk-report/1", "tool": {"name": "walkcheck.py", "version": VERSION},
           "grid": {"planResolutionMetres": res, "cells": [grid.nx, grid.ny, grid.nz], "bodyHeightMetres": body_height,
                    "feetHeightRangeMetres": [FEET_LO, round(grid.step_cells() * grid.zres, 6)],
                    "upperBodyFromMetres": round(riser_clear, 6), "maxRiserMetres": step, "estimatedMegabytes": round(grid.estimated_mb), "surfaceSamples": grid.samples},
           "doors": doors, "start": list(start), "radii": {}}
    for rad in radii:
        comp = grid.components(rad)
        entry = {"standingPlaces": int(len(comp["ixs"])), "components": comp["ncomp"]}
        si = grid.cell(comp, *start)
        entry["startFound"] = si is not None
        if si is not None:
            entry["startComponent"] = int(comp["lab"][si])
            entry["rooms"] = room_stats(grid, comp, si)
            wp = {}
            for name, (x, y, z) in (waypoints or {}).items():
                j = grid.cell(comp, x, y, z, search=0.12)
                wp[name] = None if j is None else int(comp["lab"][j])
            entry["waypoints"] = {k: {"component": v, "connectedToStart": v is not None and v == entry["startComponent"]} for k, v in wp.items()}
        rep["radii"][radius_key(rad)] = entry
    return rep


def _xyz(text):
    try:
        v = [float(x) for x in text.split(",")]
        assert len(v) == 3 and all(math.isfinite(x) for x in v)
        return v
    except (ValueError, AssertionError):
        raise argparse.ArgumentTypeError("expected X,Y,Z in metres (finite numbers), got %r" % text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glb")
    ap.add_argument("--start", type=_xyz, required=True, help="where the walk starts (X,Y,Z in the IFC frame, metres); must be on a standing place; write a negative first number as --start=-8,7,0")
    ap.add_argument("--radius", type=float, nargs="+", default=[0.30], help="body radii in metres, above 0 (default 0.30; 0.45 is a 0.9 m route)")
    ap.add_argument("--waypoint", action="append", default=[], metavar="NAME=X,Y,Z", help="report whether this place is connected to the start")
    ap.add_argument("--doors", choices=["open", "solid"], default="open")
    ap.add_argument("--res", type=float, default=0.05, help="grid cell in metres (default 0.05)")
    ap.add_argument("--step", type=float, default=None, help="largest riser a walker steps over (default: the profile's geometry.stairRiserLimitMetres, 0.19)")
    ap.add_argument("--riser", type=float, default=None, help="height above the surface from which the full body radius must be clear (default: --step plus one cell; not below --step)")
    ap.add_argument("--body-height", type=float, default=1.75)
    ap.add_argument("--profile", help="consumer profile (its geometry.stairRiserLimitMetres is the default of --step)")
    ap.add_argument("--max-memory-mb", type=int, default=DEFAULT_MAX_MB, help="refuse a grid that needs more than this (default %d)" % DEFAULT_MAX_MB)
    ap.add_argument("--require", type=float, help="exit 1 if a non-external room has no reachable standing place at this radius")
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    wps = {}
    for w in a.waypoint:
        name, _, xyz = w.partition("=")
        try:
            wps[name] = _xyz(xyz)
        except argparse.ArgumentTypeError as exc:
            print("ERROR --waypoint %s: %s" % (w, exc), file=sys.stderr)
            sys.exit(2)
    if a.max_memory_mb <= 0:
        print("ERROR --max-memory-mb must be above 0", file=sys.stderr)
        sys.exit(2)
    try:
        rpt.load_profile(a.profile)
    except (OSError, ValueError) as exc:
        print("ERROR --profile: %s" % exc, file=sys.stderr)
        sys.exit(2)
    radii = sorted(set(a.radius) | ({a.require} if a.require is not None else set()))
    try:
        step = rpt.param("geometry.stairRiserLimitMetres", DEFAULT_STEP) if a.step is None else a.step
        riser = a.riser
        if riser is None and isinstance(a.res, float) and math.isfinite(a.res) and a.res > 0 and isinstance(step, (int, float)) and math.isfinite(step) and step > 0:
            riser = math.ceil(step / a.res - 1e-9) * a.res + a.res
        check_options(radii, a.res, a.body_height, step, riser, a.start, wps)
    except ValueError as exc:
        print("ERROR %s" % exc, file=sys.stderr)
        sys.exit(2)
    try:
        with open(a.glb, "rb") as fh:
            data = fh.read()
        rep = walk(data, a.start, radii, wps, a.doors, a.res, a.body_height, a.step, a.riser, a.max_memory_mb)
    except (OSError, Failed) as exc:
        print("ERROR %s" % exc, file=sys.stderr)
        sys.exit(3)
    except MemoryError:
        print("ERROR out of memory; use a coarser --res or a smaller model", file=sys.stderr)
        sys.exit(3)
    code = 0
    missing = [k for k, e in rep["radii"].items() if not e["startFound"]]
    if missing:
        code = 1
    if a.require is not None:
        e = rep["radii"][radius_key(a.require)]
        if not e["startFound"] or any(not r["reachable"] for r in e["rooms"] if not r["external"]):
            code = 1
    rep["exitCode"] = code
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rep, fh, indent=1)
            fh.write("\n")
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        g = rep["grid"]
        print("grid %d x %d x %d cells of %.3f m (about %d MB); doors %s; steps up to %g m" % (*g["cells"], g["planResolutionMetres"], g["estimatedMegabytes"], rep["doors"], g["maxRiserMetres"]))
        for k, e in rep["radii"].items():
            if not e["startFound"]:
                print("radius %s: the start is not on a standing place of this body (%d standing places in all)" % (k, e["standingPlaces"]))
                continue
            print("radius %s: %d standing places, %d component(s); reachable from the start:" % (k, e["standingPlaces"], e["components"]))
            for r in e["rooms"]:
                print("   %-28s %6.1f of %6.1f m2 walkable (%3d%%)%s" % (r["id"], r["reachableAreaM2"], r["walkableAreaM2"], round(100 * r["reachableShareOfWalkable"]),
                                                                     "" if r["reachable"] else "   NOT REACHABLE"))
            for n, v in e["waypoints"].items():
                print("   waypoint %-20s %s" % (n, "connected" if v["connectedToStart"] else ("not on a standing place" if v["component"] is None else "cut off")))
        if missing:
            print("ERROR the start %s is not on a standing place at radius %s" % (",".join("%g" % x for x in a.start), ", ".join(missing)), file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
