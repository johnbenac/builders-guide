#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Acceptance checks for a delivered IFC master file (guide 4, section 5).

    python3 check_ifc.py FILE.ifc [--level-offset 12.0] [--min-entity-id 700001] [--base-floor-z 0.0]
                         [--occupants occupants.txt] [--volume volume.json]
                         [--finish-schedule finish-schedule.json] [--density 1090]
                         [--property-prefix PREFIX] [--report report.json]

Every finding carries a rule id from the guides and its level (REQUIRED or RECOMMENDED). The exit status is 1 when
any REQUIRED rule fails, 0 otherwise. Rules that a script can only approximate are marked "estimate" in the
message; a person confirms them.

Requires: pip install ifcopenshell numpy shapely (scipy and pillow only for the terrain tools)
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.unit

try:
    import shapely  # noqa: F401
except ImportError:
    shapely = None

import report as rpt
import terrain_lib

TOOL_VERSION = "2.2.0"

DECLARED_BASE = {"RoomId", "Occupant", "Function", "ZoneId", "ZoneClass", "Requirement", "NetAreaSquareMetres", "BaseLevelMetres", "Enclosed",
                 "GroundContact"}
TERRAIN_PROPS = ["Role", "PackageName", "PackageVersion", "PackageSha256", "PatchSha256", "PatchLevel", "PixelSizeMetres",
                 "ErrorBoundMetres", "Frame", "VerticalDatum"]
SITE_PROPS = ["SeaLevelMetres", "FootprintInWater", "DistanceToShoreMetres", "FloorHeightAboveSeaMetres"]
NOT_SOLID = {"IFCDOOR", "IFCOPENINGELEMENT", "IFCSPACE", "IFCSPATIALZONE", "IFCLIGHTFIXTURE", "IFCELEMENTASSEMBLY", "IFCGEOGRAPHICELEMENT"}
SOLID_NOT_GLASS = {"IfcWall", "IfcWallStandardCase", "IfcFurnishingElement", "IfcStairFlight", "IfcCovering"}


class Report:
    def __init__(self):
        self.findings = []
        self.file = None
        self.terrain = None             # the terrain source pins found in the file, for the report (X-23)

    def add(self, rule, status, message, element=None, **extra):
        f = rpt.finding(rule, status, message, element=element, file=self.file, **extra)
        if f:                       # None when the profile switches the rule off
            self.findings.append(f)

    def fail(self, rule, message, element=None, **kw):
        # a failed RECOMMENDED rule is only a warning
        self.add(rule, "fail" if rpt.level_of(rule) == "REQUIRED" else "warn", message, element, **kw)

    def ok(self, rule, message):
        self.add(rule, "pass", message)

    def info(self, rule, message, **kw):
        self.add(rule, "info", message, **kw)

    @property
    def failed(self):
        return any(f["status"] == "fail" for f in self.findings)


def vec3(text):
    try:
        v = [float(x) for x in str(text).split(",")]
    except ValueError:
        return None
    return v if len(v) == 3 and all(math.isfinite(x) for x in v) else None


def own_props(prefix):
    """Declaration properties: single values in property sets linked by IfcRelDefinesByProperties on the product itself;
    the first value read for a name wins. Names are translated to the canonical names of the guides through the profile's
    propertyNames (consumer name -> canonical name); `prefix` is a shortcut for a plain name prefix."""
    inverse = {v: k for k, v in rpt.profile().get("propertyNames", {}).items()}
    values = rpt.profile().get("propertyValues", {})

    def read(e):
        out, ignored = {}, []
        for rel in getattr(e, "IsDefinedBy", None) or []:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            ps = rel.RelatingPropertyDefinition
            if not ps.is_a("IfcPropertySet"):
                continue
            for p in ps.HasProperties or []:
                name = p.Name[len(prefix):] if prefix and p.Name.startswith(prefix) else p.Name
                name = inverse.get(name, name)
                if p.is_a("IfcPropertySingleValue"):
                    v = p.NominalValue.wrappedValue if p.NominalValue is not None else None
                    back = {cv: k for k, cv in values.get(name, {}).items()}
                    out.setdefault(name, back.get(v, v))
                else:
                    ignored.append(name)
        return out, ignored
    return read


REFERENCED = {}


def container_of(e):
    """The level (IfcBuildingStorey) that holds an element, through containment, references or aggregation."""
    seen = 0
    while e is not None and seen < 10:
        for rel in getattr(e, "ContainedInStructure", None) or []:
            return rel.RelatingStructure
        if e.id() in REFERENCED:
            return REFERENCED[e.id()]
        parent = None
        for rel in getattr(e, "Decomposes", None) or []:
            parent = rel.RelatingObject
        if parent is not None and parent.is_a("IfcBuildingStorey"):
            return parent
        e = parent
        seen += 1
    return None


def point_in_tri(p, a, b, c):
    d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
    d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def segment_hits(tris, p0, p1):
    """True when the segment p0-p1 crosses any triangle of the (n,3,3) array."""
    with np.errstate(all="ignore"):
        d = p1 - p0
        e1 = tris[:, 1] - tris[:, 0]
        e2 = tris[:, 2] - tris[:, 0]
        h = np.cross(d, e2)
        a = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(a) > 1e-12
        f = 1.0 / a
        s = p0 - tris[:, 0]
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * (q @ d)
        t = f * np.einsum("ij,ij->i", e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)
    return bool(hit.any())


def turn(xy, theta):
    """Rotate plan points counter-clockwise by theta (file frame to the site's axis directions)."""
    c, s = math.cos(theta), math.sin(theta)
    return np.column_stack([c * xy[:, 0] - s * xy[:, 1], s * xy[:, 0] + c * xy[:, 1]])


def file_mesh(geo):
    """mesh_of for terrain_lib.footprint_polygon: the meshes the checker already built, in the file frame."""
    def mesh_of(e):
        g = geo.get(e.id())
        return None if g is None else (g["v"], g["f"])
    return mesh_of


def check_terrain(R, model, tcfg, geo, P, storeys, terrains, args):
    """Terrain context (B-130 to B-141): one derived, read-only terrain element, its georeference and its relation to the building."""
    if len(terrains) != 1:
        R.fail("B-130", "the file has %d terrain elements; exactly one IfcGeographicElement TERRAIN is required" % len(terrains))
        return
    t = terrains[0]
    items = [i for r in (t.Representation.Representations if t.Representation else []) for i in r.Items]
    problems = []
    cont = container_of(t)
    if cont is None or not cont.is_a("IfcSite"):
        problems.append("it is not contained in the IfcSite")
    if len(items) != 1 or not items[0].is_a("IfcTriangulatedFaceSet"):
        problems.append("its body is not one IfcTriangulatedFaceSet")
    if problems:
        R.fail("B-130", "terrain: " + "; ".join(problems), t.GlobalId)
    else:
        R.ok("B-130", "one terrain element on the site, a triangulated face set")
    g = geo.get(t.id())
    if g is None or not len(g["f"]):
        R.fail("B-131", "the terrain yields no triangles", t.GlobalId)
        return
    V, F = g["v"], g["f"]
    convs = model.by_type("IfcMapConversion")
    theta = 0.0
    if len(convs) == 1:
        theta = math.atan2(convs[0].XAxisOrdinate or 0.0, convs[0].XAxisAbscissa if convs[0].XAxisAbscissa is not None else 1.0)

    # B-131: the triangles are a consistently oriented, upward-facing disc whose outline is the patch rectangle and whose plan area is
    # that rectangle's. Overlaps and holes cannot cancel: a directed edge used twice means two triangles lie over each other.
    uniq, inv = np.unique(np.round(V, 6), axis=0, return_inverse=True)
    fk = inv.reshape(-1)[F]
    directed = np.concatenate([fk[:, [0, 1]], fk[:, [1, 2]], fk[:, [2, 0]]])
    _, dcount = np.unique(directed, axis=0, return_counts=True)
    uedges, ucount = np.unique(np.sort(directed, axis=1), axis=0, return_counts=True)
    us = turn(uniq[:, :2], theta)                                # the patch is a rectangle in the site's axis directions
    lo, hi = us.min(0), us.max(0)
    tol = 1e-6 * max(1.0, float(np.abs(us).max()))

    def on_side(p, q):
        return any(abs(p[k] - e) < tol and abs(q[k] - e) < tol for k in (0, 1) for e in (lo[k], hi[k]))
    ragged = sum(1 for e in uedges[ucount == 1] if not on_side(us[e[0]], us[e[1]]))
    tri = V[F]
    plan_area = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])[:, 2] / 2.0
    rect = float((hi[0] - lo[0]) * (hi[1] - lo[1]))
    covered = float(plan_area[plan_area > 0].sum())
    msgs = []
    if int(np.sum(plan_area <= 1e-9)):
        msgs.append("%d triangle(s) do not face up or have no area" % int(np.sum(plan_area <= 1e-9)))
    if (dcount > 1).any():
        msgs.append("%d edge(s) are used twice in the same direction (triangles lie over each other, or one is flipped)" % int((dcount > 1).sum()))
    if (ucount > 2).any():
        msgs.append("%d edge(s) belong to more than two triangles" % int((ucount > 2).sum()))
    if ragged:
        msgs.append("%d outline edge(s) are not on the patch rectangle (a hole or a ragged edge)" % ragged)
    if abs(covered - rect) > 1e-6 * max(rect, 1.0):
        msgs.append("the triangles cover %.3f m2 of a %.3f m2 patch rectangle" % (covered, rect))
    if msgs:
        R.fail("B-131", "terrain is not a valid heightfield: " + "; ".join(msgs), t.GlobalId)
    else:
        R.ok("B-131", "terrain is a heightfield of %d triangles covering %.1f m2 once" % (len(F), rect))

    grounds = terrain_lib.ground_levels(model)
    mesh_of = file_mesh(geo)

    def level_points(st):
        poly = terrain_lib.footprint_polygon(model, st, mesh_of)
        return terrain_lib.sample_polygon(poly) if poly is not None else np.zeros((0, 2))
    level_pts = [(st, level_points(st)) for st in grounds]
    fp = np.vstack([p for _, p in level_pts]) if any(len(p) for _, p in level_pts) else np.zeros((0, 2))
    margin = float(tcfg["footprintMarginMetres"])
    if len(fp):
        fs = turn(fp, theta)
        short = int(np.sum(np.any(fs - margin < lo - 1e-9, axis=1) | np.any(fs + margin > hi + 1e-9, axis=1)))
        if short:
            R.fail("B-132", "%d footprint point(s) of the ground-contact level(s) are less than %g m from the edge of the terrain patch" % (short, margin), t.GlobalId)
        else:
            R.ok("B-132", "the patch extends at least %g m beyond the footprint (%d points)" % (margin, len(fp)))

    ortho = None
    if len(convs) != 1:
        R.fail("B-133", "the file has %d IfcMapConversion; exactly one is required" % len(convs))
    else:
        c = convs[0]
        crs = c.TargetCRS
        probs = []
        if not crs.is_a("IfcProjectedCRS") or not (crs.Name or "").strip():
            probs.append("the target is not an IfcProjectedCRS with a name")
        elif tcfg["crsName"] and crs.Name != tcfg["crsName"]:
            probs.append("the CRS is named %r, the profile expects %r" % (crs.Name, tcfg["crsName"]))
        if crs.is_a("IfcProjectedCRS") and not (crs.MapUnit is not None and crs.MapUnit.is_a("IfcSIUnit") and crs.MapUnit.Name == "METRE"
                                                and crs.MapUnit.Prefix is None):
            probs.append("the map unit is not plain metres")
        ax, ay = (c.XAxisAbscissa if c.XAxisAbscissa is not None else 1.0), (c.XAxisOrdinate or 0.0)
        if abs(math.hypot(ax, ay) - 1.0) > 1e-6:
            probs.append("the X axis (%g, %g) is not a unit vector" % (ax, ay))
        if abs((c.Scale if c.Scale is not None else 1.0) - 1.0) > 1e-9:
            probs.append("the scale is not 1")
        if c.OrthogonalHeight is None:
            probs.append("OrthogonalHeight (floor height above sea level) is missing")
        else:
            ortho = float(c.OrthogonalHeight)
        if storeys and abs(min(float(st.Elevation or 0.0) for st in storeys)) > 1e-6:
            probs.append("the lowest level is at %g m; its finished floor must be local z = 0 so that OrthogonalHeight is its height above sea level" % min(
                float(st.Elevation or 0.0) for st in storeys))
        if abs(args.level_offset) > 1e-12:
            probs.append("frame.levelOffsetMetres is %g; it must be 0 because the floor height is carried by OrthogonalHeight" % args.level_offset)
        if probs:
            R.fail("B-133", "georeference: " + "; ".join(probs), c.GlobalId if hasattr(c, "GlobalId") else None)
        else:
            R.ok("B-133", "georeference to %s, floor %.3f m above sea level, azimuth %.1f degrees" % (crs.Name, ortho, math.degrees(theta)))

    site = (model.by_type("IfcSite") or [None])[0]
    zt0 = terrain_lib.heights_at(V, F, np.array([[0.0, 0.0]]))[0]
    if site is not None and ortho is not None:
        if site.RefElevation is None:
            R.fail("B-134", "IfcSite.RefElevation is not set", site.GlobalId)
        elif np.isnan(zt0):
            R.fail("B-134", "the terrain does not cover the building origin", site.GlobalId)
        elif abs(site.RefElevation - (zt0 + ortho)) > tcfg["siteElevationToleranceMetres"]:
            R.fail("B-134", "IfcSite.RefElevation is %.3f m but the terrain at the building origin is %.3f m above sea level" % (
                site.RefElevation, zt0 + ortho), site.GlobalId)
        else:
            R.ok("B-134", "site elevation %.3f m matches the terrain at the origin" % site.RefElevation)

    if len(fp) and ortho is not None:
        sea = float(tcfg["seaLevelMetres"])
        flag = bool(P[site.id()].get("FootprintInWater")) if site is not None else False
        ft, bt = float(tcfg["floatToleranceMetres"]), float(tcfg["buryToleranceMetres"])
        wet = 0
        verdicts = []
        for st, pts in level_pts:
            if not len(pts):
                continue
            zt = terrain_lib.heights_at(V, F, pts)
            have = ~np.isnan(zt)
            wet += int(np.sum(zt[have] + ortho < sea - 1e-9))
            if have.any():
                gap = float(st.Elevation or 0.0) - zt[have]
                if gap.min() > ft:
                    verdicts.append("the building floats: level %s is %.2f to %.2f m above the terrain at every footprint point" % (st.Name, gap.min(), gap.max()))
                elif gap.max() < -bt:
                    verdicts.append("the building is buried: level %s is %.2f to %.2f m below the terrain at every footprint point" % (st.Name, -gap.max(), -gap.min()))
        if wet or flag:
            R.fail("B-135", "the building stands in water: %d footprint point(s) are on terrain below sea level (%g m)%s" % (
                wet, sea, "; FootprintInWater is true" if flag else ""), site.GlobalId if site is not None else None)
        else:
            R.ok("B-135", "every sampled footprint point is at or above sea level")
        if verdicts:
            R.fail("B-136", verdicts[0] + ("" if len(verdicts) == 1 else " (and %d more level(s))" % (len(verdicts) - 1)))
        else:
            R.ok("B-136", "no ground-contact level floats or is buried (estimate, %d level(s))" % len(level_pts))
        # B-141: a level that is not declared but sits on the ground everywhere
        undeclared = []
        for st in storeys:
            if st in grounds:
                continue
            pts = level_points(st)
            if not len(pts):
                continue
            zt = terrain_lib.heights_at(V, F, pts)
            have = ~np.isnan(zt)
            if have.sum() >= 3 and np.mean(np.abs(float(st.Elevation or 0.0) - zt[have]) <= min(ft, bt)) > 0.5:
                undeclared.append(st.Name)
        if undeclared:
            R.fail("B-141", "level(s) %s sit on the terrain but are not declared GroundContact true" % ", ".join(undeclared[:3]))
        else:
            R.ok("B-141", "ground-contact level(s): %s" % ", ".join(st.Name for st in grounds))

    tp = P[t.id()]
    miss = [k for k in TERRAIN_PROPS if k not in tp]
    probs = []
    if miss:
        probs.append("lacks " + ", ".join(miss))
    else:
        R.terrain = {k: tp[k] for k in ("PackageName", "PackageVersion", "PackageSha256", "PatchSha256")}
        if len(convs) == 1 and ortho is not None:               # where the file puts the building, for the package to compare with the request
            R.terrain.update({"FloorHeightAboveSeaMetres": ortho, "AzimuthDegrees": round(math.degrees(theta), 9),
                              "EastingMetres": float(convs[0].Eastings or 0.0), "NorthingMetres": float(convs[0].Northings or 0.0)})
        if tp["Role"] != "derived-context":
            probs.append("Role is %r, not 'derived-context'" % tp["Role"])
        try:
            if float(tp["ErrorBoundMetres"]) > tcfg["maxErrorBoundMetres"] + 1e-12:
                probs.append("ErrorBoundMetres %g is above the profile's %g" % (float(tp["ErrorBoundMetres"]), tcfg["maxErrorBoundMetres"]))
        except (TypeError, ValueError):
            probs.append("ErrorBoundMetres is not a number")
    if probs:
        R.fail("B-137", "Pset_Declaration_Terrain: " + "; ".join(probs), t.GlobalId)
    else:
        R.ok("B-137", "source pinned: %s %s" % (tp["PackageName"], tp["PackageVersion"]))
    if len(F) > tcfg["maxTriangles"]:
        R.fail("B-138", "the terrain has %d triangles; the profile allows at most %d" % (len(F), tcfg["maxTriangles"]), t.GlobalId)
    else:
        R.ok("B-138", "the terrain has %d triangles, within the profile's %d" % (len(F), tcfg["maxTriangles"]))
    sp = P[site.id()] if site is not None else {}
    missing_site = [k for k in ("SeaLevelMetres", "FootprintInWater") if k not in sp]
    if missing_site:
        R.fail("B-139", "Pset_Declaration_Site lacks " + ", ".join(missing_site), site.GlobalId if site is not None else None)
    else:
        R.ok("B-139", "water declared as metadata on the site")
    frame = str(tp.get("Frame", "")).lower()
    if "east" not in frame or "north" not in frame:
        R.fail("B-140", "Pset_Declaration_Terrain.Frame does not state the frame (x east, y north, z up)", t.GlobalId)
    else:
        R.ok("B-140", "the frame of the terrain numbers is stated")


def is_external(sp, props):
    """An open-air room: PredefinedType EXTERNAL or Enclosed declared false (B-143)."""
    return (getattr(sp, "PredefinedType", None) == "EXTERNAL") or props.get("Enclosed") is False


def room_polygons(model, geo, room_floor):
    """Plan polygon (shapely) and floor height of every room that has a floor: {id: (polygon, zfloor)}."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    out = {}
    for sp in model.by_type("IfcSpace"):
        if sp.id() not in room_floor:
            continue
        ft, zmin, _ = room_floor[sp.id()]
        parts = [Polygon(t[:, :2]) for t in ft]
        parts = [q for q in parts if q.area > 1e-9]
        if parts:
            out[sp.id()] = (unary_union(parts).buffer(0), float(zmin))
    return out


NOT_A_CEILING = {"FLOORING", "CLADDING", "WRAPPING", "MOLDING", "SKIRTINGBOARD", "INSULATION", "MEMBRANE"}


def thin_axis(v):
    """Unit plan direction in which a mesh is thinnest, and its extent along it (a door leaf's normal and its thickness)."""
    xy = v[:, :2] - v[:, :2].mean(0)
    if len(xy) < 3:
        return np.array([1.0, 0.0]), 0.0
    vals, vecs = np.linalg.eigh(np.cov(xy.T))
    n = vecs[:, 0]
    proj = xy @ n
    return n, float(proj.max() - proj.min())


def check_room_geometry(R, model, geo, P, room_floor, flights, doors, prof, tris_of):
    """Estimates that need the whole model: rooms overlapping (B-30), something over every enclosed room (B-54), every room reachable
    from a circulation room (B-47) and stair head-room (B-61)."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from shapely.prepared import prep
    from shapely.strtree import STRtree
    polys = room_polygons(model, geo, room_floor)
    rooms = {sp.id(): sp for sp in model.by_type("IfcSpace")}
    ids = sorted(polys)
    level_key = {}
    for i in ids:
        lv = container_of(rooms[i])
        level_key[i] = lv.id() if lv is not None else None
    buf = {i: polys[i][0].buffer(1e-6) for i in ids}
    prepared = {i: prep(buf[i]) for i in ids}
    tree = STRtree([buf[i] for i in ids]) if ids else None

    def label(i):
        return P[i].get("RoomId") or rooms[i].Name

    def rooms_at(x, y, level=None, z=None, tol_z=0.5):
        pt = Point(x, y)
        out = []
        for k in (tree.query(pt, predicate="intersects") if tree is not None else []):
            i = ids[k]
            if (level is None or level_key[i] == level) and (z is None or abs(polys[i][1] - z) <= tol_z) and prepared[i].intersects(pt):
                out.append(i)
        return out

    # B-30: rooms on one level overlap by no more than the tolerance (a wall thickness)
    tol = float(prof["geometry"]["roomOverlapToleranceMetres"])
    bad = []
    for i in ids:
        for k in (tree.query(polys[i][0], predicate="intersects") if tree is not None else []):
            j = ids[k]
            if j <= i or level_key[i] != level_key[j] or abs(polys[i][1] - polys[j][1]) > 0.05:
                continue
            inter = polys[i][0].intersection(polys[j][0])
            if inter.area > 1e-6 and not inter.buffer(-tol / 2.0).is_empty:
                bad.append((i, j, inter.area))
    if bad:
        i, j, ar = bad[0]
        R.fail("B-30", "%d pair(s) of rooms on one level overlap by more than %g m, first %s and %s (%.2f m2)" % (
            len(bad), tol, label(i), label(j), ar), rooms[i].GlobalId)
    elif len(ids) > 1:
        R.ok("B-30", "no rooms overlap by more than %g m" % tol)

    # B-54: something over every enclosed room. Vertical rays at a 3 by 3 grid of points (and two more) in the room; a slab or ceiling
    # must lie within the room's height plus half a metre, a roof slab within a roof's rise; a floor finish does not count.
    def tris_of_class(pred):
        arr = [tris_of(e) for e in model.by_type("IfcProduct") if e.id() in geo and pred(e)]
        return np.vstack(arr) if arr else np.zeros((0, 3, 3))
    near_cover = tris_of_class(lambda e: (e.is_a("IfcSlab") and e.PredefinedType != "ROOF") or
                               (e.is_a("IfcCovering") and getattr(e, "PredefinedType", None) not in NOT_A_CEILING))
    roof_cover = tris_of_class(lambda e: (e.is_a("IfcSlab") and e.PredefinedType == "ROOF") or e.is_a("IfcRoof"))
    open_rooms = []
    for i in ids:
        if is_external(rooms[i], P[i]):
            continue
        poly, z = polys[i]
        height = float(geo[i]["v"][:, 2].max() - z)
        x0, y0, x1, y1 = poly.bounds
        pts = [(x0 + (a + 0.5) / 3.0 * (x1 - x0), y0 + (b + 0.5) / 3.0 * (y1 - y0)) for a in range(3) for b in range(3)]
        pts += [(p.x, p.y) for p in (poly.representative_point(), poly.centroid)]
        pts = [q for q in pts if prepared[i].contains(Point(q))] or [(poly.representative_point().x, poly.representative_point().y)]
        hit = 0
        for q in pts:
            p0 = np.array([q[0], q[1], z + 0.05])
            if (len(near_cover) and segment_hits(near_cover, p0, p0 + np.array([0, 0, height + 0.45]))) or \
                    (len(roof_cover) and segment_hits(roof_cover, p0, p0 + np.array([0, 0, height + 12.0]))):
                hit += 1
        if hit / float(len(pts)) < 0.5:
            open_rooms.append((i, hit, len(pts)))
    if open_rooms:
        i, hit, n = open_rooms[0]
        R.fail("B-54", "%d enclosed room(s) lack a slab, roof or ceiling over most of their floor (estimate), first %s: %d of %d sample points covered" % (
            len(open_rooms), label(i), hit, n), rooms[i].GlobalId)
    elif ids:
        R.ok("B-54", "every enclosed room has a slab, roof or ceiling over most of its floor (estimate)")

    # B-47: rooms reachable from a circulation room through doors, stairs and open edges (estimate)
    prefix = (prof["identifiers"].get("circulationPrefix") or "Circulation").lower()
    circ = {i for i in ids if str(P[i].get("Function", "")).lower().startswith(prefix)}
    edges = {i: set() for i in ids}

    def join(a_list, b_list):
        for i in a_list:
            for j in b_list:
                if i != j:
                    edges[i].add(j)
                    edges[j].add(i)
    for d in doors:
        g = geo.get(d.id())
        if g is None:
            continue
        n, thick = thin_axis(g["v"])                          # the leaf is thin: its normal is the wall's; the opening is as thick as the wall
        for rel in getattr(d, "FillsVoids", None) or []:
            og = geo.get(rel.RelatingOpeningElement.id())
            if og is not None and len(og["v"]):
                proj = og["v"][:, :2] @ n
                thick = float(proj.max() - proj.min())
        lo, hi = g["v"].min(0), g["v"].max(0)
        c = (lo[:2] + hi[:2]) / 2.0
        dist = thick / 2.0 + 0.3
        lv = container_of(d)
        lv = lv.id() if lv is not None else None
        join(rooms_at(c[0] + n[0] * dist, c[1] + n[1] * dist, level=lv), rooms_at(c[0] - n[0] * dist, c[1] - n[1] * dist, level=lv))
    for op in model.by_type("IfcOpeningElement"):               # a through-opening in a wall with nothing in it (an archway) joins the rooms on both sides
        og = geo.get(op.id())
        if og is None or not len(og["v"]) or getattr(op, "HasFillings", None):
            continue
        hosts = [r.RelatingBuildingElement for r in (getattr(op, "VoidsElements", None) or []) if r.RelatingBuildingElement.is_a("IfcWall")]
        if not hosts:
            continue
        wg = geo.get(hosts[0].id())
        n, thick = thin_axis((wg or og)["v"])
        lo, hi = og["v"].min(0), og["v"].max(0)
        c = (lo[:2] + hi[:2]) / 2.0
        dist = thick / 2.0 + 0.3
        lv = container_of(hosts[0])
        lv = lv.id() if lv is not None else None
        join([i for i in rooms_at(c[0] + n[0] * dist, c[1] + n[1] * dist, level=lv, z=lo[2], tol_z=0.7)],
             [i for i in rooms_at(c[0] - n[0] * dist, c[1] - n[1] * dist, level=lv, z=lo[2], tol_z=0.7)])
    for f in flights:
        g = geo.get(f.id())
        if g is None:
            continue
        v = g["v"]
        lo, hi = v.min(0), v.max(0)
        ax = 0 if (hi[0] - lo[0]) >= (hi[1] - lo[1]) else 1
        end_lo, end_hi = lo[ax], hi[ax]
        up_hi = v[v[:, ax] >= end_hi - 0.3][:, 2].mean() >= v[v[:, ax] <= end_lo + 0.3][:, 2].mean()
        foot_end, head_end = (end_lo, end_hi) if up_hi else (end_hi, end_lo)
        sign = 1.0 if foot_end < head_end else -1.0
        mid = (lo + hi) / 2.0
        p_foot, p_head = mid.copy(), mid.copy()
        p_foot[ax] = foot_end + sign * 0.15
        p_head[ax] = head_end + sign * 0.3
        join(rooms_at(p_foot[0], p_foot[1], z=lo[2]), rooms_at(p_head[0], p_head[1], z=hi[2]))
    walls_fp = {}

    def wall_footprint(level):
        if level not in walls_fp:
            from shapely.geometry import Polygon
            parts = []
            for w in model.by_type("IfcWall"):
                lw = container_of(w)
                if w.id() in geo and lw is not None and lw.id() == level:
                    t = tris_of(w)
                    up = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])[:, 2] > 1e-9
                    parts += [Polygon(x[:, :2]) for x in t[up] if Polygon(x[:, :2]).area > 1e-9]
            walls_fp[level] = unary_union(parts).buffer(0.02) if parts else None
        return walls_fp[level]
    for i in ids:                                                 # rooms that touch with no wall between them are joined by an open edge
        for k in (tree.query(polys[i][0].buffer(0.02), predicate="intersects") if tree is not None else []):
            j = ids[k]
            if j <= i or level_key[i] != level_key[j] or abs(polys[i][1] - polys[j][1]) > 0.05 or polys[i][0].distance(polys[j][0]) > 0.02:
                continue
            shared = polys[i][0].boundary.intersection(polys[j][0].buffer(0.03))
            line = max(shared.geoms, key=lambda s: s.length) if hasattr(shared, "geoms") and len(shared.geoms) else shared
            if line.is_empty or line.length < 0.9 or line.geom_type != "LineString":
                continue
            wf = wall_footprint(level_key[i])
            if any(wf is None or not wf.contains(line.interpolate(f, normalized=True)) for f in (0.1, 0.3, 0.5, 0.7, 0.9)):
                join([i], [j])
    if not circ:
        R.info("B-47", "no room declares a Function starting %r; reachability was not checked" % prefix)
    elif ids:
        seen, todo = set(circ), list(circ)
        while todo:
            for j in edges[todo.pop()]:
                if j not in seen:
                    seen.add(j)
                    todo.append(j)
        lost = [i for i in ids if i not in seen]
        if lost:
            R.fail("B-47", "%d room(s) cannot be reached from a circulation room through a doorway, stair or open edge (estimate), first %s" % (
                len(lost), label(lost[0])), rooms[lost[0]].GlobalId)
        else:
            R.ok("B-47", "every room is reachable from a circulation room (estimate)")
        groups, left = 0, set(circ)
        while left:
            groups += 1
            todo = [left.pop()]
            while todo:
                for j in edges[todo.pop()]:
                    if j in left:
                        left.discard(j)
                        todo.append(j)
        if groups > 1:
            R.info("B-47", "the %d circulation rooms form %d separate groups; each room is reachable from its own group only" % (len(circ), groups))

    # B-61: head-room above every tread, against slabs, roofs, ceilings, beams, walls and the other flights and ramps
    head = float(prof["geometry"]["stairHeadroomMetres"])
    owners, arrs = [], []
    for e in model.by_type("IfcProduct"):
        if e.id() in geo and (e.is_a("IfcSlab") or e.is_a("IfcRoof") or e.is_a("IfcBeam") or e.is_a("IfcWall") or e.is_a("IfcStairFlight")
                              or e.is_a("IfcRampFlight") or (e.is_a("IfcCovering") and getattr(e, "PredefinedType", None) not in NOT_A_CEILING)):
            t = tris_of(e)
            arrs.append(t)
            owners.append(np.full(len(t), e.id()))
    blk_all = np.vstack(arrs) if arrs else np.zeros((0, 3, 3))
    owner = np.concatenate(owners) if owners else np.zeros(0, int)
    treads, failed = 0, False
    for f in flights:
        t = tris_of(f)
        if t is None or not len(blk_all):
            continue
        blk = blk_all[owner != f.id()]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
        cent = np.unique(np.round(t[n[:, 2] > 0.99].mean(1), 3), axis=0)
        for c in cent:
            treads += 1
            if segment_hits(blk, c + np.array([0, 0, 0.03]), c + np.array([0, 0, head - 0.03])):
                R.fail("B-61", "stair flight %s has less than %g m of head-room above the tread at %.2f, %.2f, %.2f" % (f.Name, head, *c), f.GlobalId)
                failed = True
                break
    if flights and not failed:
        R.ok("B-61", "%g m of head-room above %d tread surfaces of %d flight(s) (estimate)" % (head, treads, len(flights)))



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ifc")
    ap.add_argument("--profile", default=None, help="consumer profile (profiles/profile.schema.json); default profiles/default.json")
    ap.add_argument("--level-offset", type=float, default=None, help="override the profile's frame.levelOffsetMetres")
    ap.add_argument("--finish-schedule", default=None)
    ap.add_argument("--property-prefix", default="", help="shortcut: read declaration properties that carry this name prefix")
    ap.add_argument("--known-room-ids", default=None, help="text file of room identifiers already used elsewhere")
    ap.add_argument("--report", default=None, help="also write the JSON report to this file")
    ap.add_argument("--json", action="store_true", help="print the JSON report (schema check-report/1) instead of text")
    args = ap.parse_args()
    if shapely is None:
        print("check_ifc.py needs the Python package shapely: pip install -r tools/requirements.txt", file=sys.stderr)
        sys.exit(3)
    prof = rpt.load_profile(args.profile)
    if args.level_offset is None:
        args.level_offset = float(prof["frame"].get("levelOffsetMetres", 0.0))
    args.min_entity_id = prof["identifiers"].get("entityNumberStart")
    args.base_floor_z = float(prof["baseSurfaces"][0].get("localZ", 0.0)) if prof.get("baseSurfaces") else None
    brief_occupants = prof["identifiers"].get("occupants")
    brief_volume = None
    if prof.get("buildVolume"):
        brief_volume = dict(prof["buildVolume"])
        brief_volume["keepOut"] = prof.get("keepOut", [])
    args.occupants = None
    args.volume = None

    R = Report()
    path = args.ifc
    R.file = os.path.basename(path)
    if not os.path.isfile(path):
        R.fail("B-01", "the file does not exist: %s" % path)
        finish(R, path, "", {}, [], args, error="input not found: %s" % path)
    with open(path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()

    # ---------------------------------------------------------------- text form (B-04, B-08), size (B-05, B-09)
    nonascii = sum(1 for b in raw if b > 127)
    if nonascii:
        R.fail("B-04", "%d non-ASCII bytes; encode them with the format's escapes" % nonascii)
    else:
        R.ok("B-04", "ASCII only")
    text = raw.decode("latin1")
    data = text.split("DATA;", 1)[1].split("ENDSEC;", 1)[0] if "DATA;" in text else ""
    bad_lines = [i for i, ln in enumerate(data.split("\n")) if ln.strip() and not (ln.startswith("#") and ln.rstrip().endswith(";"))]
    if bad_lines:
        R.fail("B-08", "%d line(s) in the data section are not a complete one-line entity (first at data line %d)" % (len(bad_lines), bad_lines[0] + 1))
    elif data:
        R.ok("B-08", "every entity is on one line")
    mb = len(raw) / 1048576.0
    lim, rec = prof["limits"]["maxFileMegabytes"], prof["budgets"]["recommendedFileMegabytes"]
    if mb > lim:
        R.fail("B-05", "file is %.1f MB, the profile's limit is %g MB" % (mb, lim))
    elif mb > rec:
        R.fail("B-09", "file is %.1f MB; the profile recommends at most %g MB" % (mb, rec))
    else:
        R.ok("B-05", "file size %.1f MB" % mb)

    try:
        model = ifcopenshell.open(path)
    except Exception as exc:  # unreadable file
        R.fail("B-01", "the file cannot be opened: %s" % exc)
        finish(R, path, sha, {}, [], args, error="the file cannot be opened: %s" % exc)
        return
    allowed_schemas = prof["schema"]["allowed"]
    if model.schema not in allowed_schemas:
        R.fail("B-01", "schema is %s; the profile accepts %s" % (model.schema, ", ".join(allowed_schemas)))
    else:
        R.ok("B-01", "schema %s" % model.schema)

    # ---------------------------------------------------------------- units (B-02)
    units = model.by_type("IfcUnitAssignment")
    length = None
    for ua in units:
        for u in ua.Units or []:
            if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT":
                length = u
            if u.is_a("IfcConversionBasedUnit") and u.UnitType == "LENGTHUNIT":
                length = u
    if length is None:
        R.fail("B-02", "no length unit is declared")
    else:
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        if abs(scale - 1.0) > 1e-9:
            R.fail("B-02", "the length unit resolves to %g metres, not 1" % scale)
        elif length.is_a("IfcSIUnit") and length.Prefix is None:
            R.ok("B-02", "length unit is metre")
        else:
            R.fail("B-02a", "the length unit resolves to metres but is written with a prefix or conversion; plain metres are preferred")

    # ---------------------------------------------------------------- identifiers (B-70, B-71)
    gids = collections.Counter()
    for e in model.by_type("IfcRoot"):
        gids[e.GlobalId] += 1
    dup = [g for g, n in gids.items() if n > 1]
    badlen = [g for g in gids if not re.fullmatch(r"[0-9A-Za-z_$]{22}", g or "")]
    if dup:
        R.fail("B-70", "%d duplicate GlobalId value(s), first %s" % (len(dup), dup[0]))
    if badlen:
        R.fail("B-70", "%d GlobalId value(s) are not 22 characters of the IFC alphabet, first %s" % (len(badlen), badlen[0]))
    if not dup and not badlen:
        R.ok("B-70", "%d GlobalId values, unique, 22 characters" % len(gids))
    low = min(e.id() for e in model)
    if args.min_entity_id is not None:
        if low < args.min_entity_id:
            R.fail("B-71", "lowest entity number is #%d, the profile's assigned start is #%d" % (low, args.min_entity_id))
        else:
            R.ok("B-71", "entity numbers start at #%d" % low)
    else:
        R.info("B-71", "lowest entity number is #%d (the profile assigns no start)" % low)

    for rel in model.by_type("IfcRelReferencedInSpatialStructure"):
        for el in rel.RelatedElements or []:
            REFERENCED[el.id()] = rel.RelatingStructure
    read = own_props(args.property_prefix)
    lum_cfg, sign_cfg = prof["extensions"]["luminaires"], prof["extensions"]["signboards"]
    declared = DECLARED_BASE | set(lum_cfg["requiredProperties"]) | set(sign_cfg["requiredProperties"]) | set(TERRAIN_PROPS) | set(SITE_PROPS)
    products = [e for e in model.by_type("IfcProduct")]
    P = {}
    ignored_declared = []
    for e in products:
        props, ignored = read(e)
        P[e.id()] = props
        for n in ignored:
            if n in declared:
                ignored_declared.append((e.GlobalId, n))
    if ignored_declared:
        R.fail("B-72", "%d declaration propert(ies) are not single values and will not be read, first %s on %s" % (
            len(ignored_declared), ignored_declared[0][1], ignored_declared[0][0]))
    else:
        R.ok("B-72", "all declaration properties are single values")

    # ---------------------------------------------------------------- levels (B-13), project note (B-12), hierarchy (B-14)
    storeys = model.by_type("IfcBuildingStorey")
    if not storeys:
        R.fail("B-13", "no IfcBuildingStorey")
    else:
        no_elev = [s.Name for s in storeys if s.Elevation is None]
        if no_elev:
            R.fail("B-13", "level(s) without an Elevation: %s" % ", ".join(map(str, no_elev[:5])))
        loose = []
        for e in products:
            if e.is_a("IfcSite") or e.is_a("IfcBuilding") or e.is_a("IfcBuildingStorey") or e.is_a("IfcOpeningElement"):
                continue      # an opening follows the element it voids
            if container_of(e) is None:
                loose.append(e)
        if loose:
            R.fail("B-13", "%d element(s) belong to no level, first %s (%s)" % (len(loose), loose[0].GlobalId, loose[0].is_a()), loose[0].GlobalId)
        else:
            R.ok("B-13", "%d level(s); every element belongs to a level" % len(storeys))
    pj = model.by_type("IfcProject")
    pj_props = read(pj[0])[0] if pj else {}
    if "FrameNote" not in pj_props:
        R.fail("B-12", "no FrameNote property on the IfcProject")
    if not (model.by_type("IfcSite") and model.by_type("IfcBuilding")):
        R.fail("B-14", "the Project > Site > Building > Level hierarchy is incomplete")

    # ---------------------------------------------------------------- geometry (B-05, B-06)
    settings = ifcopenshell.geom.settings()
    geo = {}
    verts_total = tris_total = 0
    it = ifcopenshell.geom.iterator(settings, model, max(1, os.cpu_count() or 1))
    if it.initialize():
        while True:
            sh = it.get()
            g = sh.geometry
            v = np.array(g.verts, dtype=float).reshape(-1, 3)
            mat = ifcopenshell.util.placement.get_local_placement(model.by_id(sh.id).ObjectPlacement)
            v = v @ mat[:3, :3].T + mat[:3, 3]      # to the file frame
            f = np.array(g.faces, dtype=int).reshape(-1, 3)
            mats = []
            for mt in g.materials:
                try:
                    c = mt.diffuse.components if hasattr(mt.diffuse, "components") else mt.diffuse
                    col = "#%02x%02x%02x" % tuple(int(round(min(1.0, max(0.0, x)) * 255)) for x in c[:3])
                    mats.append((col, round(1.0 - float(mt.transparency or 0.0), 3)))
                except Exception:
                    mats.append(("#cccccc", 1.0))
            geo[sh.id] = {"v": v, "f": f, "mats": mats, "mid": np.array(g.material_ids, dtype=int)}
            verts_total += len(v)
            tris_total += len(f)
            if not it.next():
                break
    missing = [e for e in products if getattr(e, "Representation", None) and e.Representation.Representations and e.id() not in geo
               and not e.is_a("IfcElementAssembly")]
    if missing:
        R.fail("B-06", "%d product(s) have a representation but no triangles, first %s (%s)" % (
            len(missing), missing[0].GlobalId, missing[0].is_a()), missing[0].GlobalId)
    else:
        R.ok("B-06", "every represented product yields triangles")
    if verts_total > prof["limits"]["maxVertices"] or tris_total > prof["limits"]["maxTriangles"]:
        R.fail("B-05", "%d vertices and %d triangles exceed the profile's limits of %d and %d" % (
            verts_total, tris_total, prof["limits"]["maxVertices"], prof["limits"]["maxTriangles"]))
    terrain_ids = {e.id() for e in model.by_type("IfcGeographicElement") if getattr(e, "PredefinedType", None) == "TERRAIN"}
    budget_tris = tris_total - sum(len(geo[i]["f"]) for i in terrain_ids if i in geo)      # terrain has its own cap (B-138)
    if budget_tris > prof["budgets"]["recommendedTriangles"]:
        R.fail("B-120", "%d triangles; the profile recommends at most %d" % (budget_tris, prof["budgets"]["recommendedTriangles"]))
    else:
        R.ok("B-05", "%d vertices, %d triangles" % (verts_total, tris_total))

    def tris_of(e):
        g = geo.get(e.id())
        return None if g is None else g["v"][g["f"]]

    def bbox_of(e):
        g = geo.get(e.id())
        return None if g is None or not len(g["v"]) else (g["v"].min(0), g["v"].max(0))

    # ---------------------------------------------------------------- rooms (B-20 to B-26, B-50)
    rooms_all = model.by_type("IfcSpace")
    known = set()
    if args.known_room_ids and os.path.exists(args.known_room_ids):
        known = {ln.strip() for ln in open(args.known_room_ids) if ln.strip()}
    allowed = set(brief_occupants) if brief_occupants else None
    room_ids = collections.Counter()
    slabs = [e for e in model.by_type("IfcSlab")]
    slab_up = []
    for s in slabs:
        t = tris_of(s)
        if t is None:
            continue
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        up = n[:, 2] > 1e-9
        for tri in t[up]:
            slab_up.append(tri)
    slab_up = np.array(slab_up) if slab_up else np.zeros((0, 3, 3))
    room_floor = {}
    for sp in rooms_all:
        pr = P[sp.id()]
        g = geo.get(sp.id())
        if g is None or not len(g["f"]):
            R.fail("B-21", "room %s (%s) has no geometry" % (pr.get("RoomId", sp.Name), sp.GlobalId), sp.GlobalId)
            continue
        t = g["v"][g["f"]]
        zmin = t[:, :, 2].min()
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        on_floor = (np.abs(t[:, :, 2] - zmin).max(1) < 0.02) & (n[:, 2] < -1e-9)
        if not on_floor.any():
            R.fail("B-20", "room %s: no downward-facing floor triangles on the lowest plane" % pr.get("RoomId", sp.Name), sp.GlobalId)
            continue
        ft = t[on_floor]
        area = float(np.abs(n[on_floor][:, 2]).sum() / 2.0)
        room_floor[sp.id()] = (ft, zmin, area)
        rid = pr.get("RoomId")
        if not rid:
            R.fail("B-26", "room %s has no RoomId (the profile reads it as %s)" % (sp.Name, prof["propertyNames"].get("RoomId", "RoomId")), sp.GlobalId)
        else:
            room_ids[rid] += 1
            if len(str(rid)) > prof["identifiers"]["roomIdMaxLength"] or not re.fullmatch(prof["identifiers"]["roomIdPattern"], str(rid)):
                R.fail("B-23", "RoomId %r must be at most %d characters and match %s" % (
                    rid, prof["identifiers"]["roomIdMaxLength"], prof["identifiers"]["roomIdPattern"]), sp.GlobalId)
            if rid in known:
                R.fail("B-22", "RoomId %r is already used elsewhere" % rid, sp.GlobalId)
        occ = pr.get("Occupant")
        if not occ:
            R.fail("B-24", "room %s has no Occupant" % (rid or sp.Name), sp.GlobalId)
        elif allowed is not None and occ not in allowed:
            R.fail("B-24", "Occupant %r of room %s is not in the profile's list" % (occ, rid), sp.GlobalId)
        if not pr.get("Function"):
            R.fail("B-25", "room %s has no Function" % (rid or sp.Name), sp.GlobalId)
        net = pr.get("NetAreaSquareMetres")
        if net is not None and abs(float(net) - area) > max(0.5, 0.05 * area):
            R.info("B-20", "room %s: NetAreaSquareMetres %.2f differs from the floor area %.2f" % (rid, float(net), area))
        # a slab under the room (B-50): up-facing slab triangle within 0.4 m of the floor, over the floor's centre
        cx = ft[:, :, :2].mean((0, 1))
        found = args.base_floor_z is not None and abs(zmin - args.base_floor_z) < 0.05
        for tri in slab_up:
            if abs(tri[:, 2].mean() - zmin) < 0.4 and point_in_tri(cx, tri[0], tri[1], tri[2]):
                found = True
                break
        if not found:
            # the room's centre may lie outside an L-shaped floor: try the centre of the largest floor triangle
            big = ft[np.argmax(np.abs(np.cross(ft[:, 1] - ft[:, 0], ft[:, 2] - ft[:, 0])[:, 2]))]
            c2 = big[:, :2].mean(0)
            for tri in slab_up:
                if abs(tri[:, 2].mean() - zmin) < 0.4 and point_in_tri(c2, tri[0], tri[1], tri[2]):
                    found = True
                    break
        if not found:
            R.fail("B-50", "room %s: no slab top within 0.4 m of the floor under the room" % (rid or sp.Name), sp.GlobalId)
    dups = [r for r, n in room_ids.items() if n > 1]
    if dups:
        R.fail("B-22", "duplicate RoomId value(s): %s" % ", ".join(dups[:8]))
    elif rooms_all:
        R.ok("B-22", "%d room(s), RoomId values unique in this file" % len(rooms_all))
    if not rooms_all:
        R.fail("B-20", "the file contains no IfcSpace (no rooms)")

    # standing point (B-33, walkability extension), estimate: free floor outside furniture footprints grown by the profile's clearance
    walk = prof["extensions"]["walkability"]
    clr = float(walk["standingClearanceMetres"])
    if not walk["enabled"]:
        R.info("B-33", "walkability extension not enabled by the profile; standing points were not checked")
    obstacles = [e for e in products if e.is_a() in ("IfcFurnishingElement", "IfcBuildingElementProxy", "IfcRailing", "IfcTransportElement")
                 and not (e.is_a("IfcBuildingElementProxy") and getattr(e, "PredefinedType", None) == "PROVISIONFORSPACE")]
    for sp in ([r for r in rooms_all if not is_external(r, P[r.id()])] if walk["enabled"] else []):
        if sp.id() not in room_floor:
            continue
        ft, zmin, area = room_floor[sp.id()]
        lo = ft[:, :, :2].reshape(-1, 2).min(0)
        hi = ft[:, :, :2].reshape(-1, 2).max(0)
        rects = []
        for o in obstacles:
            b = bbox_of(o)
            if b and b[0][2] < zmin + 1.6 and b[1][2] > zmin + 0.1:
                rects.append((b[0][0] - clr, b[0][1] - clr, b[1][0] + clr, b[1][1] + clr))
        free = False
        for x in lo[0] + (hi[0] - lo[0]) * np.arange(24) / 23.0:
            for y in lo[1] + (hi[1] - lo[1]) * np.arange(24) / 23.0:
                if any(point_in_tri((x, y), tri[0], tri[1], tri[2]) for tri in ft[:200]) and not any(
                        r[0] < x < r[2] and r[1] < y < r[3] for r in rects):
                    free = True
                    break
            if free:
                break
        if not free:
            R.fail("B-33", "room %s: no standing point outside furniture grown by %g m (estimate)" % (P[sp.id()].get("RoomId") or sp.Name, clr), sp.GlobalId)

    # ---------------------------------------------------------------- doors and windows (B-41, B-42, B-44)
    solid_prods = []
    for e in products:
        if e.is_a().upper() in NOT_SOLID or e.is_a() in walk["nonSolidClasses"]:
            continue
        if e.is_a("IfcBuildingElementProxy") and getattr(e, "PredefinedType", None) == "PROVISIONFORSPACE":
            continue
        if bbox_of(e) is not None:
            solid_prods.append(e)

    def opening_of(e):
        for rel in getattr(e, "FillsVoids", None) or []:
            op = rel.RelatingOpeningElement
            for v in getattr(op, "VoidsElements", None) or []:
                return op, v.RelatingBuildingElement
            return op, None
        return None, None

    doors = model.by_type("IfcDoor")
    for kind, rule in (("IfcDoor", "B-41"), ("IfcWindow", "B-44")):
        for e in model.by_type(kind):
            op, wall = opening_of(e)
            if op is None or wall is None:
                R.fail(rule, "%s %s is not linked to an opening in a wall (IfcRelFillsElement and IfcRelVoidsElement)" % (kind, e.Name), e.GlobalId)
    if doors and not any(f["rule"] == "B-41" and f["status"] == "fail" for f in R.findings):
        R.ok("B-41", "%d door(s), each fills an opening that voids a wall" % len(doors))
    for e in doors:
        op, wall = opening_of(e)
        if op is None:
            continue
        g = geo.get(op.id())
        if g is None:
            continue
        v = g["v"]
        c = v.mean(0)
        xy = v[:, :2] - c[:2]
        w_, vec = np.linalg.eigh(np.cov(xy.T) if len(xy) > 2 else np.eye(2))
        major = vec[:, 1]
        normal = np.array([-major[1], major[0]])
        z0 = v[:, 2].min()
        height = v[:, 2].max() - z0
        width = 2 * np.abs(xy @ major).max()
        gm = prof["geometry"]
        if height < gm["doorMinClearHeightMetres"]:
            R.fail("B-42", "doorway %s is %.2f m high; the profile needs at least %g m" % (e.Name, height, gm["doorMinClearHeightMetres"]), e.GlobalId)
        if width < gm["doorMinClearWidthMetres"]:
            R.fail("B-43", "doorway %s is %.2f m wide; the profile recommends at least %g m" % (e.Name, width, gm["doorMinClearWidthMetres"]), e.GlobalId)
        near = [o for o in solid_prods if o.id() != op.id() and bbox_of(o) is not None
                and np.all(bbox_of(o)[0] < c + 1.5) and np.all(bbox_of(o)[1] > c - 1.5)]
        blocked = []
        for h in gm["doorwayProbeHeightsMetres"]:
            p0 = np.array([c[0] - normal[0] * 0.55, c[1] - normal[1] * 0.55, z0 + h])
            p1 = np.array([c[0] + normal[0] * 0.55, c[1] + normal[1] * 0.55, z0 + h])
            for o in near:
                if o.is_a("IfcFurnishingElement"):
                    lo, hi = bbox_of(o)
                    # slab test of the segment against the box
                    d = p1 - p0
                    tmin, tmax = 0.0, 1.0
                    for ax in range(3):
                        if abs(d[ax]) < 1e-12:
                            if p0[ax] < lo[ax] or p0[ax] > hi[ax]:
                                tmin, tmax = 1, 0
                                break
                        else:
                            t1, t2 = (lo[ax] - p0[ax]) / d[ax], (hi[ax] - p0[ax]) / d[ax]
                            tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
                    if tmin <= tmax:
                        blocked.append((h, o.Name))
                else:
                    if segment_hits(tris_of(o), p0, p1):
                        blocked.append((h, o.Name))
        if blocked:
            R.fail("B-42", "doorway %s is blocked at %.1f m by %s" % (e.Name, blocked[0][0], blocked[0][1]), e.GlobalId)

    # ---------------------------------------------------------------- stairs (B-61, B-62)
    flights = model.by_type("IfcStairFlight")
    for fl in flights:
        t = tris_of(fl)
        if t is None:
            continue
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
        tops = sorted({round(float(tr[:, 2].mean()), 3) for tr, nn in zip(t, n) if nn[2] > 0.99})
        if len(tops) > 2:
            risers = np.diff(tops)
            risers = risers[risers > 0.02]
            if len(risers) and risers.max() > prof["geometry"]["stairRiserLimitMetres"]:
                R.fail("B-61", "stair flight %s has a riser of %.3f m; the profile allows at most %g m" % (
                    fl.Name, risers.max(), prof["geometry"]["stairRiserLimitMetres"]), fl.GlobalId)
    for b in model.by_type("IfcBuilding"):
        levels = [s for s in storeys if any(r.RelatingObject == b for r in (s.Decomposes or []))]
        if len(levels) > 1:
            has = False
            for f in list(flights) + list(model.by_type("IfcStair")):
                st = container_of(f)
                if st is not None and st in levels:
                    has = True
                    break
            if not has:
                R.fail("B-62", "building %s has %d levels but no stair" % (b.Name, len(levels)), b.GlobalId)

    check_room_geometry(R, model, geo, P, room_floor, flights, doors, prof, tris_of)

    # ---------------------------------------------------------------- below the lowest floor (B-142)
    if storeys:
        floor0 = min(float(st.Elevation or 0.0) for st in storeys)
        allowed_below = ("IfcSlab", "IfcFooting", "IfcPile", "IfcWall", "IfcStairFlight", "IfcStair", "IfcRamp", "IfcRampFlight",
                         "IfcOpeningElement", "IfcGeographicElement", "IfcSite", "IfcBuilding", "IfcBuildingStorey")
        low = [e for e in products if e.id() in geo and not any(e.is_a(c) for c in allowed_below)
               and not (e.is_a("IfcBuildingElementProxy") and getattr(e, "PredefinedType", None) == "PROVISIONFORSPACE")
               and geo[e.id()]["v"][:, 2].min() < floor0 - 0.05]
        if low:
            R.fail("B-142", "%d element(s) reach below the lowest finished floor (z %.2f), first %s (%s); only slabs, footings, piles, walls, stairs, ramps, openings, terrain and reservation volumes may" % (
                len(low), floor0, low[0].GlobalId, low[0].is_a()), low[0].GlobalId)
        else:
            R.ok("B-142", "nothing but foundations, walls, stairs, ramps, openings, terrain and reservation volumes reaches below the lowest floor")

    # ---------------------------------------------------------------- open-air rooms (B-143)
    odd = [sp for sp in rooms_all if ((getattr(sp, "PredefinedType", None) == "EXTERNAL") != (P[sp.id()].get("Enclosed") is False))
           and ("Enclosed" in P[sp.id()] or getattr(sp, "PredefinedType", None) == "EXTERNAL")]
    if odd:
        R.fail("B-143", "room %s: PredefinedType EXTERNAL and Enclosed false must go together" % (P[odd[0].id()].get("RoomId") or odd[0].Name), odd[0].GlobalId)
    elif any(is_external(sp, P[sp.id()]) for sp in rooms_all):
        R.ok("B-143", "open-air rooms are EXTERNAL with Enclosed false")

    # ---------------------------------------------------------------- reserved volumes and zones (B-80, B-81)
    prov_text = len(re.findall(r"^#\d+=IFCBUILDINGELEMENTPROXY\(.*\.PROVISIONFORSPACE\.\);\s*$", text, re.M))
    prov_model = sum(1 for e in model.by_type("IfcBuildingElementProxy") if e.PredefinedType == "PROVISIONFORSPACE")
    if prov_text != prov_model:
        R.fail("B-80", "%d reservation proxies are not recognised by a line scan (the predefined type must be the last argument)" % (prov_model - prov_text))
    elif prov_model:
        R.ok("B-80", "%d reservation proxies recognised" % prov_model)
    zids = collections.Counter()
    for z in model.by_type("IfcSpatialZone"):
        zids[P[z.id()].get("ZoneId") or z.Name] += 1
        if z.id() not in geo:
            R.fail("B-81", "zone %s has no geometry" % z.Name, z.GlobalId)
    d = [k for k, n in zids.items() if n > 1]
    if d:
        R.fail("B-81", "duplicate zone id(s): %s" % ", ".join(map(str, d[:5])))

    # ---------------------------------------------------------------- luminaires (extension; B-90 to B-95)
    lum_ids = collections.Counter()
    targets = set()
    if not lum_cfg["enabled"]:
        R.info("B-90", "luminaires extension not enabled by the profile; fixtures were not checked")
    suffix, tol = lum_cfg["lensNameSuffix"], lum_cfg["positionToleranceMetres"]
    for a in (model.by_type("IfcElementAssembly") if lum_cfg["enabled"] else []):
        pr = P[a.id()]
        if "LuminaireId" not in pr and not any(k.startswith("Light") for k in pr):
            continue
        name = pr.get("LuminaireId", a.Name)
        lum_ids[name] += 1
        miss = [k for k in lum_cfg["requiredProperties"] if k not in pr]
        if miss:
            R.fail("B-91", "luminaire %s lacks: %s" % (name, ", ".join(miss)), a.GlobalId)
            continue
        parts = []
        for rel in a.IsDecomposedBy or []:
            parts += [p for p in rel.RelatedObjects if p.is_a("IfcLightFixture")]
        lens = [p for p in parts if (p.Name or "").endswith(suffix)]
        if len(parts) != 2 or len(lens) != 1:
            R.fail("B-90", "luminaire %s must have two IfcLightFixture parts, one whose name ends in %r (found %d parts, %d emissive)" % (name, suffix, len(parts), len(lens)), a.GlobalId)
        if pr.get("LightType") not in lum_cfg["lightTypes"]:
            R.fail("B-91", "luminaire %s: LightType must be one of %s" % (name, ", ".join(lum_cfg["lightTypes"])), a.GlobalId)
        pos, aim, col = vec3(pr.get("LightPosition")), vec3(pr.get("LightAim")), vec3(pr.get("LightColor"))
        if pos is None or aim is None or col is None:
            R.fail("B-91", "luminaire %s: LightPosition, LightAim and LightColor must be text 'x,y,z'" % name, a.GlobalId)
            continue
        if abs(math.sqrt(sum(x * x for x in aim)) - 1.0) > 1e-6:
            R.fail("B-93", "luminaire %s: LightAim is not a unit vector" % name, a.GlobalId)
        if not all(0.0 <= x <= 1.0 for x in col):
            R.fail("B-91", "luminaire %s: LightColor values must be between 0 and 1" % name, a.GlobalId)
        if lens:
            b = bbox_of(lens[0])
            if b is not None:
                ctr = (b[0] + b[1]) / 2.0
                dist = math.dist([ctr[0], ctr[1], ctr[2] + args.level_offset], pos)
                if dist >= tol:
                    R.fail("B-92", "luminaire %s: the emissive part's centre plus the level offset is %.3f m from LightPosition (limit %g m)" % (name, dist, tol), a.GlobalId)
        if pr.get("LuminaireTarget"):
            targets.add(pr["LuminaireTarget"])
    dl = [k for k, n in lum_ids.items() if n > 1]
    if dl:
        R.fail("B-91", "duplicate LuminaireId: %s" % ", ".join(dl[:5]))
    if lum_ids and not any(f["rule"] in ("B-90", "B-91", "B-92", "B-93") and f["status"] == "fail" for f in R.findings):
        R.ok("B-91", "%d luminaire(s) complete; positions match their emissive part within %g m" % (len(lum_ids), tol))
    for sp in ([r for r in rooms_all if not is_external(r, P[r.id()])] if lum_cfg["enabled"] else []):
        rid = P[sp.id()].get("RoomId")
        if rid and rid not in targets:
            R.fail("B-94", "room %s has no authored fixture targeting it" % rid, sp.GlobalId)

    # ---------------------------------------------------------------- signs (extension; B-100 to B-102)
    if not sign_cfg["enabled"]:
        R.info("B-100", "signboards extension not enabled by the profile; boards were not checked")
    dens, mincap, rd = sign_cfg["displayPixelsPerRadian"], sign_cfg["minCapitalPixels"]["primary"], sign_cfg["readingDistanceMetres"]
    for a in (model.by_type("IfcElementAssembly") if sign_cfg["enabled"] else []):
        pr = P[a.id()]
        if "SignboardId" not in pr and not any(k.startswith("Signboard") for k in pr):
            continue
        name = pr.get("SignboardId", a.Name)
        miss = [k for k in sign_cfg["requiredProperties"] if k not in pr]
        if miss:
            R.fail("B-100", "sign %s lacks: %s" % (name, ", ".join(miss)), a.GlobalId)
            continue
        if pr["SignboardKind"] not in sign_cfg["kinds"]:
            R.fail("B-100", "sign %s: kind %r is not one of %s" % (name, pr["SignboardKind"], sign_cfg["kinds"]), a.GlobalId)
        pos, nrm = vec3(pr["SignboardPosition"]), vec3(pr["SignboardNormal"])
        if pos is None or nrm is None:
            R.fail("B-100", "sign %s: position and normal must be text 'x,y,z'" % name, a.GlobalId)
            continue
        read_m, w, h = float(pr["SignboardReadM"]), float(pr["SignboardWidthM"]), float(pr["SignboardHeightM"])
        fit = (w - 0.24 * h) / (0.55 * max(1, len(str(pr["SignboardText"]))))
        if fit < 0.05:
            R.fail("B-101", "sign %s: the text cannot fit the board at a capital height of 0.05 m (estimate)" % name, a.GlobalId)
        cap = min(0.5 * h, fit)
        supported = cap * dens / mincap
        if read_m > supported + 1e-9:
            R.fail("B-102", "sign %s: the letters support about %.1f m (estimate), not the declared %.0f m" % (name, supported, read_m), a.GlobalId)
        if not rd[0] <= read_m <= rd[1]:
            R.fail("B-102", "sign %s: reading distance %.0f m is outside the profile's %g to %g m" % (name, read_m, rd[0], rd[1]), a.GlobalId)

    # ---------------------------------------------------------------- build volume (B-110)
    if args.volume or brief_volume:
        vol = brief_volume if not args.volume else json.load(open(args.volume))
        bad = 0
        first = None
        for e in products:
            if e.is_a().upper() in ("IFCSPACE", "IFCSPATIALZONE", "IFCOPENINGELEMENT") or e.id() not in geo or e.id() in terrain_ids:
                continue
            v = geo[e.id()]["v"] + np.array([0, 0, args.level_offset])
            inside = np.ones(len(v), bool)
            if "box" in vol:
                inside &= np.all((v >= vol["box"]["min"]) & (v <= vol["box"]["max"]), axis=1)
            if "ellipse" in vol:
                el = vol["ellipse"]
                inside &= (v[:, 0] / el["a"]) ** 2 + (v[:, 1] / el["b"]) ** 2 <= 1.0
                inside &= (v[:, 2] >= el["zmin"]) & (v[:, 2] <= el["zmax"])
            for k in vol.get("keepOut", []):
                inside &= ~np.all((v >= k["min"]) & (v <= k["max"]), axis=1)
            if not inside.all():
                bad += 1
                first = first or e
        if bad:
            R.fail("B-110", "%d product(s) have vertices outside the build volume or inside a keep-out volume, first %s (%s)" % (bad, first.GlobalId, first.is_a()), first.GlobalId)
        else:
            R.ok("B-110", "all geometry is inside the build volume")
    else:
        R.info("B-110", "the profile gives no build volume; it was not checked")

    # ---------------------------------------------------------------- terrain context (extension; B-130 to B-140)
    tcfg = prof["extensions"]["terrain"]
    if not tcfg["enabled"]:
        R.info("B-130", "terrain extension not enabled by the profile; terrain context was not checked")
        if terrain_ids:
            R.fail("B-115", "the file has a terrain element but the profile does not enable the terrain extension")
    else:
        check_terrain(R, model, tcfg, geo, P, storeys, [model.by_id(i) for i in sorted(terrain_ids)], args)

    # ---------------------------------------------------------------- finish keys (D-03 to D-05)
    keys = collections.Counter()
    for e in products:
        g = geo.get(e.id())
        if g is None or e.is_a().upper() in ("IFCSPACE", "IFCSPATIALZONE", "IFCOPENINGELEMENT") or e.id() in terrain_ids:
            continue
        used = set(g["mid"].tolist()) if len(g["mid"]) else set()
        for i in used:
            if 0 <= i < len(g["mats"]):
                col, op = g["mats"][i]
                keys[(e.is_a(), col, op)] += 1
    for (cls, col, op), n in sorted(keys.items()):
        if op < 0.99 and cls in SOLID_NOT_GLASS:
            R.fail("D-04", "%s with colour %s has opacity %.2f and may be treated as glass by consumers" % (cls, col, op))
    finish_keys = [{"class": c, "colour": col, "opacity": op, "elements": n} for (c, col, op), n in sorted(keys.items())]
    if len(keys) > prof["budgets"]["maxDistinctColours"]:
        R.fail("D-05", "%d distinct (class, colour, opacity) combinations; the profile recommends at most %d" % (len(keys), prof["budgets"]["maxDistinctColours"]))
    if args.finish_schedule:
        sched = json.load(open(args.finish_schedule))
        have = {(m["key"]["class"], m["key"]["colour"].lower(), round(float(m["key"].get("opacity", 1.0)), 2)) for m in sched.get("materials", [])}
        lacking = [k for k in keys if (k[0], k[1], round(k[2], 2)) not in have]
        if lacking:
            R.fail("D-03", "%d combination(s) have no entry in the finish schedule, first %s" % (len(lacking), lacking[0]))
        else:
            R.ok("D-03", "every combination is in the finish schedule")
    else:
        R.info("D-03", "%d (class, colour, opacity) combinations found; give --finish-schedule to check coverage" % len(keys))

    counts = {"levels": len(storeys), "rooms": len(rooms_all), "doors": len(doors), "windows": len(model.by_type("IfcWindow")),
              "luminaires": len(lum_ids), "triangles": tris_total, "vertices": verts_total,
              "furniture": len(model.by_type("IfcFurnishingElement")), "finishKeys": len(keys)}
    finish(R, path, sha, counts, finish_keys, args)


def finish(R, path, sha, counts, finish_keys, args, error=None):
    rep = rpt.make_report("check_ifc.py", TOOL_VERSION, {"path": os.path.basename(path), "sha256": sha}, R.findings, counts,
                          extra=dict({"finishKeys": finish_keys, "file": os.path.basename(path), "sha256": sha},
                                     **({"terrain": R.terrain} if R.terrain else {})), error=error)
    if args.report:
        rpt.write(rep, args.report)
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        s = rep["summary"]
        print("result: %s (%d REQUIRED failure(s), %d RECOMMENDED warning(s)); %s" % (rep["result"].upper(), s["requiredFailures"],
              s["recommendedWarnings"], ", ".join("%s %s" % (v, k) for k, v in counts.items())))
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
