#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Can a body of a given radius walk to every room? A 3D voxel walk through the whole-model GLB.

    python3 tools/walkcheck.py MODEL.glb --start X,Y,Z [--radius 0.30 0.45 ...] [--doors open|solid] [--waypoint NAME=X,Y,Z ...]
                               [--res 0.05] [--step 0.2] [--body-height 1.75] [--require RADIUS] [--out REPORT.json] [--json]

The GLB is what a consumer sees, so the walk is measured on it (every node transform applied, coordinates converted back to the IFC frame, metres):

  1. every triangle is sampled onto a voxel grid (`--res` metres in plan and in height); the voxels they touch are solid. Door leaves are left out
     with `--doors open` (the default: a door is a way through) and solid with `--doors solid`; windows, furniture, fixtures and planting are solid;
  2. a standing place is a voxel that holds an upward-facing surface of the building (floor, slab, covering, tread, terrain; never furniture or
     planting) with a free cylinder of the body radius from `--riser` (0.22 m) to `--body-height` above it, and free feet (one cell) from 0.05 m up to
     the largest riser `--step` (default 0.2 m; the profile's `extensions.walkability.stepHeightMetres` is the height of a step taken without
     noticing, a different number): a walker steps over a riser of that height but not through a chair leg or a basket;
  3. two neighbouring standing places are joined when they are 8-neighbours in plan (or two cells out across a step) and differ in height by at
     most `--step`;
  4. from `--start` the connected set is grown at each body radius; each room of the GLB (`extras.rooms`, footprint and level) is reported with the
     area that can be reached, and every `--waypoint` with the component it is in. A route that survives a body radius of 0.45 m has a clear
     width of at least 0.90 m everywhere along it.

Report (`walk-report/1`, `schemas/walk-report.schema.json`): per radius the standing places, the components, whether the start was found, per room
the walkable and reachable areas and the share of the walkable area that is reachable, per waypoint its component. Memory is about 10 bytes per
voxel: a 20 x 20 x 4 m building at 0.05 m needs about 130 MB; `--res` 0.1 for large plots.

Exit codes: 0 done, 1 with `--require RADIUS` some non-external room has no reachable standing place at that radius, 2 wrong command line, 3 the
GLB could not be read. Requires numpy, scipy and shapely (tools/requirements-terrain.txt).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
from glbkit import Failed  # noqa: E402

VERSION = "2.3.0"
SUPPORT_KINDS = {"structure", "covering", "terrain"}
FEET_LO = 0.05            # the feet occupy 5 cm to `step` above the surface
FEET_RADIUS = 0.025
DEFAULT_STEP = 0.20
DEFAULT_RISER_CLEAR = 0.22
MAX_CELLS = 400_000_000


def sample_triangles(tri, spacing):
    """Points on the surface of every triangle (barycentric lattice finer than `spacing`). Returns (points (M, 3), triangle index (M,))."""
    import numpy as np
    v0 = tri[:, 0]
    e1 = tri[:, 1] - v0
    e2 = tri[:, 2] - v0
    m = np.maximum(1, np.ceil(np.maximum(np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1)) / spacing).astype(int))
    pts, ids = [], []
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
            pts.append(p.reshape(-1, 3))
            ids.append(np.repeat(s, ok.sum()))
    return np.concatenate(pts), np.concatenate(ids)


class World:
    """The triangles of a model GLB in the IFC frame, with which of them are solid and which can be stood on."""

    def __init__(self, data, doors="open"):
        import numpy as np
        self.doc, bn = glbkit.split_glb(data)
        ex = self.doc.get("extras") or {}
        self.rooms = ex.get("rooms") or []
        self.levels = {lv["name"]: lv["elevation"] for lv in ex.get("levels") or []}
        tris, support = [], []
        for it in glbkit.triangles_of(self.doc, bn):
            kind = (it.get("extras") or {}).get("kind", "")
            category = (it.get("extras") or {}).get("category") or ""
            if kind == "door" and doors == "open":
                continue
            tris.append(it["tri"])
            support.append(np.full(len(it["tri"]), kind in SUPPORT_KINDS and "planting" not in category))
        if not tris:
            raise Failed("the GLB holds no geometry")
        self.tri = np.concatenate(tris)
        self.is_support = np.concatenate(support)
        b = ex.get("bounds")
        if b:
            lo, hi = np.array(b["min"], float), np.array(b["max"], float)
        else:
            lo, hi = self.tri.reshape(-1, 3).min(axis=0), self.tri.reshape(-1, 3).max(axis=0)
        self.lo, self.hi = lo, hi


class Grid:
    def __init__(self, world, res, body_height, step, riser_clear):
        import numpy as np
        self.w, self.res, self.zres = world, res, res
        self.body_height, self.step, self.riser_clear = body_height, step, riser_clear
        pad = 0.2
        self.x0, self.y0, self.z0 = world.lo[0] - pad, world.lo[1] - pad, world.lo[2] - 0.075
        self.nx = int(math.ceil((world.hi[0] + pad - self.x0) / res))
        self.ny = int(math.ceil((world.hi[1] + pad - self.y0) / res))
        self.nz = int(math.ceil((min(world.hi[2], world.lo[2] + 12.0) + 0.1 - self.z0) / self.zres))
        if self.nx * self.ny * self.nz > MAX_CELLS:
            raise Failed("the grid would have %d x %d x %d cells; use a coarser --res" % (self.nx, self.ny, self.nz))
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
            pts, tid = sample_triangles(tri[idx[sl]], res * 0.45)
            ix = np.floor((pts[:, 0] - self.x0) / res).astype(int)
            iy = np.floor((pts[:, 1] - self.y0) / res).astype(int)
            iz = np.floor((pts[:, 2] - self.z0) / self.zres).astype(int)
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
        lo_f, hi_f = int(round(FEET_LO / zres)), max(int(round(self.step / zres)), int(round(FEET_LO / zres)) + 1)
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

    def components(self, radius):
        import numpy as np
        from scipy.sparse import coo_matrix, csgraph
        ixs, iys, izs, key = self.standing_places(radius)
        n = len(ixs)
        rows, cols = [], []
        kmax = int(round(self.step / self.zres))
        uk, first, cnt = np.unique(key, return_index=True, return_counts=True)
        maxc = int(cnt.max()) if n else 0
        # the 8 neighbours at any permitted height difference; the ring two cells out only across a step (a riser between two treads leaves a gap
        # of a cell or two between the last cell with free feet below it and the first on the tread above)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx == 0 and dy == 0:
                    continue
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
                    rows.append(a)
                    cols.append(j[a])
        r = np.concatenate(rows) if rows else np.zeros(0, int)
        c = np.concatenate(cols) if cols else np.zeros(0, int)
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


def walk(data, start, radii, waypoints=None, doors="open", res=0.05, body_height=1.75, step=None, riser_clear=DEFAULT_RISER_CLEAR):
    """The walk report (a dict) for a model GLB."""
    world = World(data, doors)
    step = DEFAULT_STEP if step is None else step
    grid = Grid(world, res, body_height, step, riser_clear)
    rep = {"format": "walk-report/1", "tool": {"name": "walkcheck.py", "version": VERSION},
           "grid": {"planResolutionMetres": res, "cells": [grid.nx, grid.ny, grid.nz], "bodyHeightMetres": body_height, "feetHeightRangeMetres": [FEET_LO, step],
                    "upperBodyFromMetres": riser_clear, "maxRiserMetres": step},
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
        rep["radii"]["%.2f" % rad] = entry
    return rep


def _xyz(text):
    try:
        v = [float(x) for x in text.split(",")]
        assert len(v) == 3
        return v
    except (ValueError, AssertionError):
        raise argparse.ArgumentTypeError("expected X,Y,Z in metres, got %r" % text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glb")
    ap.add_argument("--start", type=_xyz, required=True, help="where the walk starts (X,Y,Z in the IFC frame, metres); must be on a standing place; write a negative first number as --start=-8,7,0")
    ap.add_argument("--radius", type=float, nargs="+", default=[0.30], help="body radii in metres (default 0.30; 0.45 is a 0.9 m route)")
    ap.add_argument("--waypoint", action="append", default=[], metavar="NAME=X,Y,Z", help="report whether this place is connected to the start")
    ap.add_argument("--doors", choices=["open", "solid"], default="open")
    ap.add_argument("--res", type=float, default=0.05, help="grid cell in metres (default 0.05)")
    ap.add_argument("--step", type=float, default=None, help="largest riser a walker steps over (default 0.2)")
    ap.add_argument("--body-height", type=float, default=1.75)
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
    try:
        with open(a.glb, "rb") as fh:
            data = fh.read()
        radii = sorted(set(a.radius) | ({a.require} if a.require else set()))
        rep = walk(data, a.start, radii, wps, a.doors, a.res, a.body_height, a.step)
    except (OSError, Failed) as exc:
        print("ERROR %s" % exc, file=sys.stderr)
        sys.exit(3)
    code = 0
    if a.require:
        e = rep["radii"]["%.2f" % a.require]
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
        print("grid %d x %d x %d cells of %.3f m; doors %s" % (*g["cells"], g["planResolutionMetres"], rep["doors"]))
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
    sys.exit(code)


if __name__ == "__main__":
    main()
