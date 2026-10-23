#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write the request a building sends to its terrain source (guide 1, section 16).

    python3 site_request.py MASTER.ifc --floor-elevation H --origin E N [--profile PROFILE.json] [--out site-request.json]

The request holds the footprint polygon of the lowest level (slabs and walls seen from above), the finished floor elevation, the
grading rule and the clearing margin from the profile, and the smallest patch the source should cut. Coordinates are in the site
frame (x east, y north, metres): the file's x and y plus the building origin given with --origin. Heights are above sea level.

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


def lowest_level_elements(model):
    storeys = model.by_type("IfcBuildingStorey")
    if not storeys:
        return None, []
    low = min(storeys, key=lambda s: s.Elevation if s.Elevation is not None else 0.0)
    out = []
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        if rel.RelatingStructure == low:
            out += [e for e in rel.RelatedElements if e.is_a("IfcSlab") or e.is_a("IfcWall")]
    return low, out


def footprint(model):
    """Plan footprint (shapely geometry, file frame) of the slabs and walls of the lowest level."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    low, elems = lowest_level_elements(model)
    parts = []
    for e in elems:
        if not getattr(e, "Representation", None):
            continue
        sh = ifcopenshell.geom.create_shape(settings, e)
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        f = np.array(sh.geometry.faces).reshape(-1, 3)
        for tri in v[f][:, :, :2]:
            p = Polygon(tri)
            if p.area > 1e-9:
                parts.append(p)
    if not parts:
        return low, None
    return low, unary_union(parts).buffer(0)


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ifc")
    ap.add_argument("--floor-elevation", type=float, required=True, help="height above sea level of the lowest finished floor, metres")
    ap.add_argument("--origin", type=float, nargs=2, required=True, metavar=("E", "N"), help="site-frame position of the file origin, metres")
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
    low, geom = footprint(model)
    if geom is None or geom.is_empty:
        print("no slabs or walls on the lowest level of %s: nothing to take a footprint from" % a.ifc, file=sys.stderr)
        sys.exit(3)
    method = "hull" if a.hull else "union"
    polys = polygons_of(geom, method)
    e0, n0 = a.origin
    polys = [[[x + e0, y + n0] for x, y in ring] for ring in polys]
    allp = np.array([pt for ring in polys for pt in ring])
    margin = float(cfg["footprintMarginMetres"])
    req = {
        "format": "site-request/1",
        "frame": SITE_FRAME,
        "master": {"file": os.path.basename(a.ifc), "sha256": sha256_file(a.ifc)},
        "buildingOrigin": {"x": e0, "y": n0},
        "finishedFloorElevationMetres": a.floor_elevation,
        "footprint": {"method": method, "polygons": polys},
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
    print("wrote %s: %d polygon(s) from level %s, floor %.3f m above sea level, patch bounds %s to %s" % (
        a.out, len(polys), low.Name, a.floor_elevation, req["patch"]["bounds"]["min"], req["patch"]["bounds"]["max"]))


if __name__ == "__main__":
    main()
