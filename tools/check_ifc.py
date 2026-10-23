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

Requires: pip install ifcopenshell numpy
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

import report as rpt
import terrain_lib

TOOL_VERSION = "2.0.0"

DECLARED_BASE = {"RoomId", "Occupant", "Function", "ZoneId", "ZoneClass", "Requirement", "NetAreaSquareMetres", "BaseLevelMetres"}
TERRAIN_PROPS = ["Role", "PackageName", "PackageVersion", "PackageSha256", "PatchSha256", "PatchLevel", "PixelSizeMetres",
                 "ErrorBoundMetres", "Frame", "VerticalDatum"]
SITE_PROPS = ["SeaLevelMetres", "FootprintInWater", "DistanceToShoreMetres", "FloorHeightAboveSeaMetres"]
NOT_SOLID = {"IFCDOOR", "IFCOPENINGELEMENT", "IFCSPACE", "IFCSPATIALZONE", "IFCLIGHTFIXTURE", "IFCELEMENTASSEMBLY", "IFCGEOGRAPHICELEMENT"}
SOLID_NOT_GLASS = {"IfcWall", "IfcWallStandardCase", "IfcFurnishingElement", "IfcStairFlight", "IfcCovering"}


class Report:
    def __init__(self):
        self.findings = []
        self.file = None

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


def footprint_points(model, geo, storeys, cap=500):
    """Plan points (file frame) of the slabs and walls of the lowest level: where the building touches the ground."""
    low = min(storeys, key=lambda s: s.Elevation if s.Elevation is not None else 0.0)
    pts = [geo[e.id()]["v"][:, :2] for e in list(model.by_type("IfcSlab")) + list(model.by_type("IfcWall"))
           if e.id() in geo and container_of(e) == low]
    if not pts:
        return low, np.zeros((0, 2))
    u = np.unique(np.round(np.vstack(pts), 3), axis=0)
    if len(u) > cap:
        u = u[np.linspace(0, len(u) - 1, cap).astype(int)]
    return low, u


def check_terrain(R, model, tcfg, geo, P, storeys, terrains, args):
    """Terrain context (B-130 to B-140): one derived, read-only terrain element, its georeference and its relation to the building."""
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
    tri = V[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    plan_area = n[:, 2] / 2.0
    bad_tri = int(np.sum(plan_area <= 1e-9))
    key = np.unique(np.round(V, 6), axis=0, return_inverse=True)[1].reshape(-1)
    fk = key[F]
    edges = np.sort(np.concatenate([fk[:, [0, 1]], fk[:, [1, 2]], fk[:, [2, 0]]]), axis=1)
    _, ecount = np.unique(edges, axis=0, return_counts=True)
    lo, hi = V[:, :2].min(0), V[:, :2].max(0)
    rect = float((hi[0] - lo[0]) * (hi[1] - lo[1]))
    covered = float(plan_area[plan_area > 0].sum())
    msgs = []
    if bad_tri:
        msgs.append("%d triangle(s) do not face up or have no area" % bad_tri)
    if (ecount > 2).any():
        msgs.append("%d edge(s) belong to more than two triangles" % int((ecount > 2).sum()))
    if abs(covered - rect) > 1e-6 * max(rect, 1.0):
        msgs.append("the triangles cover %.3f m2 of a %.3f m2 patch rectangle (overlap or hole)" % (covered, rect))
    if msgs:
        R.fail("B-131", "terrain is not a valid heightfield: " + "; ".join(msgs), t.GlobalId)
    else:
        R.ok("B-131", "terrain is a heightfield of %d triangles covering %.1f m2 once" % (len(F), rect))

    low, fp = footprint_points(model, geo, storeys)
    margin = float(tcfg["footprintMarginMetres"])
    if len(fp):
        short = int(np.sum(np.any(fp - margin < lo - 1e-9, axis=1) | np.any(fp + margin > hi + 1e-9, axis=1)))
        if short:
            R.fail("B-132", "%d footprint point(s) of the lowest level are less than %g m from the edge of the terrain patch" % (short, margin), t.GlobalId)
        else:
            R.ok("B-132", "the patch extends at least %g m beyond the footprint" % margin)

    convs = model.by_type("IfcMapConversion")
    prof = rpt.profile()
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
        if abs((c.XAxisAbscissa if c.XAxisAbscissa is not None else 1.0) - 1.0) > 1e-9 or abs(c.XAxisOrdinate or 0.0) > 1e-9:
            probs.append("the local X axis does not point east")
        if abs((c.Scale if c.Scale is not None else 1.0) - 1.0) > 1e-9:
            probs.append("the scale is not 1")
        if c.OrthogonalHeight is None:
            probs.append("OrthogonalHeight (floor height above sea level) is missing")
        else:
            ortho = float(c.OrthogonalHeight)
        if abs(args.level_offset) > 1e-12:
            probs.append("frame.levelOffsetMetres is %g; it must be 0 because the floor height is carried by OrthogonalHeight" % args.level_offset)
        if probs:
            R.fail("B-133", "georeference: " + "; ".join(probs), c.GlobalId if hasattr(c, "GlobalId") else None)
        else:
            R.ok("B-133", "georeference to %s, floor %.3f m above sea level" % (crs.Name, ortho))

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
        zt = terrain_lib.heights_at(V, F, fp)
        have = ~np.isnan(zt)
        sea = float(tcfg["seaLevelMetres"])
        flag = bool(P[site.id()].get("FootprintInWater")) if site is not None else False
        wet = int(np.sum(zt[have] + ortho < sea - 1e-9))
        if wet or flag:
            R.fail("B-135", "the building stands in water: %d footprint point(s) are on terrain below sea level (%g m)%s" % (
                wet, sea, "; FootprintInWater is true" if flag else ""), site.GlobalId if site is not None else None)
        else:
            R.ok("B-135", "every footprint point is at or above sea level")
        if have.any():
            gap = float(low.Elevation or 0.0) - zt[have]
            ft, bt = float(tcfg["floatToleranceMetres"]), float(tcfg["buryToleranceMetres"])
            if gap.min() > ft:
                R.fail("B-136", "the building floats: the lowest floor is %.2f to %.2f m above the terrain at every footprint point" % (gap.min(), gap.max()))
            elif gap.max() < -bt:
                R.fail("B-136", "the building is buried: the lowest floor is %.2f to %.2f m below the terrain at every footprint point" % (-gap.max(), -gap.min()))
            else:
                R.ok("B-136", "floor %.2f m above to %.2f m below the terrain across the footprint (estimate)" % (gap.max(), -gap.min()))

    tp = P[t.id()]
    miss = [k for k in TERRAIN_PROPS if k not in tp]
    probs = []
    if miss:
        probs.append("lacks " + ", ".join(miss))
    else:
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
    for sp in (rooms_all if walk["enabled"] else []):
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
    for sp in (rooms_all if lum_cfg["enabled"] else []):
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
                          extra={"finishKeys": finish_keys, "file": os.path.basename(path), "sha256": sha}, error=error)
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
