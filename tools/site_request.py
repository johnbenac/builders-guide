#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write the request a building sends to its terrain source (guide 1, section 16).

    python3 site_request.py MASTER.ifc --floor-elevation H --origin E N [--azimuth DEG] [--profile PROFILE.json] [--out site-request.json]

The request holds the footprint polygon of the ground-contact levels (slabs and walls seen from above), the finished floor
elevation of each, the grading rule and the clearing margin from the profile, and the smallest patch the source should cut.
Ground-contact levels are those declared with GroundContact true in Pset_Declaration_Level (B-141); with no declaration it is the
lowest level. Coordinates are in the site frame (x east, y north, metres): the file's x and y turned by the building azimuth
(--azimuth, degrees counter-clockwise from east to the file's +X axis; default 0) and shifted by the building origin given with
--origin. Heights are above sea level.

--floor-elevation and --origin come from whoever places the building; they are not guessed. Exit codes: 0 written, 2 wrong
command line, 3 the IFC file cannot be read.

Requires: pip install ifcopenshell numpy shapely
"""
import argparse
import json
import os
import sys

import numpy as np
import ifcopenshell
import ifcopenshell.geom

import report as rpt
from terrain_lib import sha256_file

SITE_FRAME = "site: x east, y north, z up, metres; heights above mean sea level"


def ground_levels(model):
    """The levels that touch the ground: those declared with GroundContact true (B-141), else the lowest level."""
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
    return sorted(flagged or [min(storeys, key=lambda x: x.Elevation if x.Elevation is not None else 0.0)],
                  key=lambda x: x.Elevation or 0.0)


def level_elements(model, storey):
    out = []
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        if rel.RelatingStructure == storey:
            out += [e for e in rel.RelatedElements if e.is_a("IfcSlab") or e.is_a("IfcWall")]
    return out


def footprint(model, storey):
    """Plan footprint (shapely geometry, file frame) of the slabs and walls of one level; None when it has none."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    parts = []
    for e in level_elements(model, storey):
        if not getattr(e, "Representation", None):
            continue
        sh = ifcopenshell.geom.create_shape(settings, e)
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        f = np.array(sh.geometry.faces).reshape(-1, 3)
        for tri in v[f][:, :, :2]:
            p = Polygon(tri)
            if p.area > 1e-9:
                parts.append(p)
    return unary_union(parts).buffer(0) if parts else None


def polygons_of(geom, method):
    from shapely.geometry import MultiPolygon
    if method == "hull":
        geom = geom.convex_hull
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for p in polys:
        p = p.simplify(0.001, preserve_topology=True)
        ring = list(p.exterior.coords)[:-1]
        out.append([[round(x, 3), round(y, 3)] for x, y in ring])
    return out


def to_site(rings, e0, n0, azimuth_degrees):
    c, sn = np.cos(np.radians(azimuth_degrees)), np.sin(np.radians(azimuth_degrees))
    return [[[round(e0 + c * x - sn * y, 3), round(n0 + sn * x + c * y, 3)] for x, y in ring] for ring in rings]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ifc")
    ap.add_argument("--floor-elevation", type=float, required=True, help="height above sea level of the lowest finished floor, metres")
    ap.add_argument("--origin", type=float, nargs=2, required=True, metavar=("E", "N"), help="site-frame position of the file origin, metres")
    ap.add_argument("--azimuth", type=float, default=0.0, help="angle from east, counter-clockwise, to the file's +X axis, degrees")
    ap.add_argument("--profile")
    ap.add_argument("--hull", action="store_true", help="send the convex hull instead of the exact footprint")
    ap.add_argument("--out", default="site-request.json")
    a = ap.parse_args()
    prof = rpt.load_profile(a.profile)
    cfg = prof["extensions"]["terrain"]
    try:
        model = ifcopenshell.open(a.ifc)
    except Exception as exc:
        print("cannot read %s: %s" % (a.ifc, exc), file=sys.stderr)
        sys.exit(3)
    from shapely.ops import unary_union
    method = "hull" if a.hull else "union"
    e0, n0 = a.origin
    levels, geoms = [], []
    for st in ground_levels(model):
        g = footprint(model, st)
        if g is None or g.is_empty:
            continue
        geoms.append(g)
        el = float(st.Elevation or 0.0)
        levels.append({"name": st.Name, "elevationMetres": el, "finishedFloorElevationMetres": a.floor_elevation + el,
                       "footprint": {"method": method, "polygons": to_site(polygons_of(g, method), e0, n0, a.azimuth)}})
    if not levels:
        print("no slabs or walls on the ground-contact level(s) of %s: nothing to take a footprint from" % a.ifc, file=sys.stderr)
        sys.exit(3)
    polys = to_site(polygons_of(unary_union(geoms).buffer(0), method), e0, n0, a.azimuth)
    allp = np.array([pt for ring in polys for pt in ring])
    margin = float(cfg["footprintMarginMetres"])
    req = {
        "format": "site-request/1",
        "frame": SITE_FRAME,
        "master": {"file": os.path.basename(a.ifc), "sha256": sha256_file(a.ifc)},
        "buildingOrigin": {"x": e0, "y": n0},
        "buildingAzimuthDegrees": a.azimuth,
        "finishedFloorElevationMetres": a.floor_elevation,
        "footprint": {"method": method, "polygons": polys},
        "levels": levels,
        "grading": {"maxCutFillSlope": cfg["grading"]["maxCutFillSlope"]},
        "clearing": {"marginMetres": float(cfg["clearingMarginMetres"])},
        "patch": {"minMarginMetres": margin,
                  "bounds": {"min": [round(float(allp[:, 0].min()) - margin, 3), round(float(allp[:, 1].min()) - margin, 3)],
                             "max": [round(float(allp[:, 0].max()) + margin, 3), round(float(allp[:, 1].max()) + margin, 3)]}},
        "profile": {"name": rpt.profile_info()["name"], "version": rpt.profile_info()["version"]},
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(req, fh, indent=2)
        fh.write("\n")
    print("wrote %s: %d ground-contact level(s), floor %.3f m above sea level, azimuth %g degrees, patch bounds %s to %s" % (
        a.out, len(levels), a.floor_elevation, a.azimuth, req["patch"]["bounds"]["min"], req["patch"]["bounds"]["max"]))


if __name__ == "__main__":
    main()
