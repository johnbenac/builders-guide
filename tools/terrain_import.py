#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add the derived, read-only terrain context to a master IFC file (guide 1, section 16).

    python3 terrain_import.py PATCH.tif SIDECAR.json MASTER.ifc --request site-request.json --out MASTER-WITH-TERRAIN.ifc
                              [--profile PROFILE.json] [--error-bound METRES]

Reads the height patch the terrain source delivered (GeoTIFF, one float32 band, metres) with its sidecar, reduces the samples to a
triangulated network that stays within the error bound of every sample, converts it to the file frame and writes into a copy of the
master file:

* one IfcGeographicElement TERRAIN (an IfcTriangulatedFaceSet) on the IfcSite, with Pset_Declaration_Terrain (source version, hashes,
  pixel size, error bound, frame, vertical datum);
* an IfcMapConversion to an IfcProjectedCRS named as the sidecar says (a custom frame, not a registry code), whose OrthogonalHeight
  is the height of the lowest finished floor above sea level and whose X axis is the building azimuth from the request;
* IfcSite.RefElevation (terrain height at the building origin above sea level) and Pset_Declaration_Site (sea level, whether the
  footprint is in water, distance to shore when the source gives it, floor height above sea level).

It never edits the heights and never cuts a pad. Exit codes: 0 written, 2 wrong command line, 3 an input is unusable (the message
says which, for example a hash that does not match the sidecar).

Requires: pip install ifcopenshell numpy pillow scipy shapely jsonschema
"""
import argparse
import json
import math
import os
import re
import sys
import uuid

import numpy as np
import ifcopenshell
import ifcopenshell.guid

import report as rpt
import terrain_lib as tl

NS = uuid.UUID("0f1d3c52-7a41-5c0e-8b26-4d9e6a1f3b77")
FILE_FRAME = ("file frame: z up; x and y are the site frame (x east, y north) shifted by the building origin and turned by the "
              "building azimuth (IfcMapConversion), z is measured from the lowest finished floor")


def fail(msg):
    print("terrain_import: " + msg, file=sys.stderr)
    sys.exit(3)


def load_json(path, schema_rel):
    try:
        import jsonschema
    except ImportError:
        fail("the Python package jsonschema is needed to validate %s: pip install -r tools/requirements.txt" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        fail("cannot read %s: %s" % (path, exc))
    with open(os.path.join(rpt.ROOT, schema_rel), encoding="utf-8") as fh:
        schema = json.load(fh)
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        fail("%s does not match %s: %s: %s" % (path, schema_rel, "/".join(map(str, errs[0].path)) or "(top)", errs[0].message[:160]))
    return doc


def gid(key):
    return ifcopenshell.guid.compress(uuid.uuid5(NS, key).hex)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch")
    ap.add_argument("sidecar")
    ap.add_argument("master")
    ap.add_argument("--request", required=True, help="the site request the patch answers (tools/site_request.py)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile")
    ap.add_argument("--error-bound", type=float, default=None, help="largest vertical difference from any sample, metres (default: the profile's)")
    a = ap.parse_args()
    prof = rpt.load_profile(a.profile)
    cfg = prof["extensions"]["terrain"]

    side = load_json(a.sidecar, "schemas/terrain-patch.schema.json")
    req = load_json(a.request, "schemas/site-request.schema.json")
    for p in (a.patch, a.master):
        if not os.path.isfile(p):
            fail("no such file: " + p)
    if os.path.abspath(a.out) == os.path.abspath(a.master) or (os.path.exists(a.out) and os.path.samefile(a.out, a.master)):
        fail("--out must not be the master file; write a new file")

    # pins: the patch is the one the sidecar describes, and the request was made for this master
    if tl.sha256_file(a.patch) != side["patch"]["sha256"]:
        fail("the patch hash differs from the sidecar's (%s); the sidecar describes another file" % side["patch"]["sha256"][:12])
    if side["patch"]["file"] != os.path.basename(a.patch):
        fail("the sidecar describes the file %r, not %r" % (side["patch"]["file"], os.path.basename(a.patch)))
    if tl.sha256_file(a.master) != req["master"]["sha256"]:
        fail("the site request was made for another version of the master file; run site_request.py again")
    if side["frame"] != req["frame"]:
        fail("the sidecar's frame (%r) is not the request's (%r)" % (side["frame"], req["frame"]))
    if abs(side["verticalDatum"]["seaLevelMetres"] - cfg["seaLevelMetres"]) > 1e-9:
        fail("the sidecar puts sea level at %g m, the profile at %g m" % (side["verticalDatum"]["seaLevelMetres"], cfg["seaLevelMetres"]))
    if cfg["crsName"] and side["crs"]["name"] != cfg["crsName"]:
        fail("the sidecar's CRS is named %r, the profile expects %r" % (side["crs"]["name"], cfg["crsName"]))
    bound = cfg["maxErrorBoundMetres"] if a.error_bound is None else a.error_bound
    if not bound > 0:
        fail("the error bound must be greater than 0 (got %g)" % bound)
    if bound > cfg["maxErrorBoundMetres"] + 1e-12:
        fail("error bound %g m is above the profile's %g m" % (bound, cfg["maxErrorBoundMetres"]))
    if abs(prof["frame"].get("levelOffsetMetres", 0.0)) > 1e-12:
        fail("the profile's frame.levelOffsetMetres must be 0 with the terrain extension; the floor height is carried by the georeference")
    pm = side["patch"]
    if pm["width"] * pm["height"] > cfg["maxPatchSamples"]:
        fail("the patch has %d x %d samples, more than the profile's limit of %d; cut a smaller patch or use a coarser level" % (
            pm["width"], pm["height"], cfg["maxPatchSamples"]))

    try:
        z, info = tl.read_patch(a.patch, cfg["maxPatchSamples"])
    except tl.PatchError as exc:
        fail(str(exc))
    ps, origin = pm["pixelSizeMetres"], (pm["origin"]["x"], pm["origin"]["y"])
    if z.shape != (pm["height"], pm["width"]):
        fail("the patch is %d x %d samples, the sidecar says %d x %d" % (z.shape[1], z.shape[0], pm["width"], pm["height"]))
    if abs(info["pixelSize"] - ps) > 1e-9 * max(1.0, ps) or abs(info["origin"][0] - origin[0]) > 1e-6 or abs(info["origin"][1] - origin[1]) > 1e-6:
        fail("the georeferencing tags of the GeoTIFF disagree with the sidecar (pixel size %g vs %g, origin %s vs %s)" % (
            info["pixelSize"], ps, info["origin"], origin))
    e0, n0, floor = req["buildingOrigin"]["x"], req["buildingOrigin"]["y"], req["finishedFloorElevationMetres"]
    (bx0, by0), (bx1, by1) = req["patch"]["bounds"]["min"], req["patch"]["bounds"]["max"]
    xmin, ymin, xmax, ymax = tl.patch_extent(z.shape, origin, ps)
    if bx0 < xmin - 1e-6 or by0 < ymin - 1e-6 or bx1 > xmax + 1e-6 or by1 > ymax + 1e-6:
        fail("the patch (sample centres %.3f, %.3f to %.3f, %.3f) does not cover the area the request asked for (%.3f, %.3f to %.3f, %.3f)" % (
            xmin, ymin, xmax, ymax, bx0, by0, bx1, by1))
    azimuth = float(req["buildingAzimuthDegrees"])
    ca, sa = math.cos(math.radians(azimuth)), math.sin(math.radians(azimuth))
    try:
        verts_idx, tris, worst = tl.decimate(z, bound, max_triangles=cfg["maxTriangles"])
    except (tl.PatchError, ValueError) as exc:
        fail(str(exc))
    sx = origin[0] + (verts_idx[:, 0] + 0.5) * ps
    sy = origin[1] - (verts_idx[:, 1] + 0.5) * ps
    sz = z[verts_idx[:, 1], verts_idx[:, 0]]
    dx, dy = sx - e0, sy - n0                                   # site frame to file frame: shift, then turn by minus the azimuth
    fx, fy, fz = ca * dx + sa * dy, -sa * dx + ca * dy, sz - floor
    tris = tl.faces_up(np.column_stack([fx, fy]), tris)

    # the site elevation is the height of the network that is written (what the checker reads), not of the raster
    ground_tin = tl.heights_at(np.column_stack([fx, fy, fz]), tris, np.array([[0.0, 0.0]]))[0]
    if np.isnan(ground_tin):
        fail("the patch does not cover the building origin")
    ground_origin = float(ground_tin) + floor
    try:
        ground_raster = tl.bilinear(z, origin, ps, e0, n0)
    except ValueError:
        fail("the patch does not cover the building origin")
    if abs(ground_origin - ground_raster) > cfg["siteElevationToleranceMetres"]:
        print("terrain_import: warning: the network is %.3f m from the raster at the building origin (the error bound holds at sample "
              "positions only); the site elevation follows the network" % abs(ground_origin - ground_raster), file=sys.stderr)
    sea = cfg["seaLevelMetres"]
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    foot = unary_union([Polygon(r) for r in req["footprint"]["polygons"]]).buffer(0)
    try:
        in_water = any(tl.bilinear(z, origin, ps, x, y) < sea for x, y in tl.sample_polygon(foot, spacing=1.0))
    except ValueError:
        fail("the patch does not cover the whole footprint")

    # ------------------------------------------------------------------ write
    with open(a.master, "rb") as fh:
        raw = fh.read().decode("latin1")
    model = ifcopenshell.open(a.master)
    if model.by_type("IfcMapConversion") or any(g.PredefinedType == "TERRAIN" for g in model.by_type("IfcGeographicElement")):
        fail("the master file already has a georeference or a terrain element")
    sites = model.by_type("IfcSite")
    ctxs = [c for c in model.by_type("IfcGeometricRepresentationContext") if not c.is_a("IfcGeometricRepresentationSubContext")]
    bodies = [c for c in model.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"]
    if not (sites and ctxs and bodies):
        fail("the master file needs an IfcSite and a model context with a Body sub-context")
    site, ctx, body = sites[0], ctxs[0], bodies[0]
    if any(getattr(r.RelatingPropertyDefinition, "Name", None) == "Pset_Declaration_Site" for r in site.IsDefinedBy or []):
        fail("the site already has a Pset_Declaration_Site; remove it or write the terrain by hand")
    metres = [u for ua in model.by_type("IfcUnitAssignment") for u in ua.Units if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT"]
    if not metres:
        fail("the master file declares no SI length unit (B-02)")
    metre = metres[0]

    def prop(name, value):
        if isinstance(value, bool):
            v = model.create_entity("IfcBoolean", wrappedValue=value)
        elif isinstance(value, (int, float)):
            v = model.create_entity("IfcReal", wrappedValue=float(value))
        else:
            v = model.create_entity("IfcText", wrappedValue=str(value))
        return model.create_entity("IfcPropertySingleValue", Name=name, NominalValue=v)

    def pset(obj, name, values):
        ps_ = model.create_entity("IfcPropertySet", GlobalId=gid("pset/" + obj.GlobalId + "/" + name), Name=name,
                                  HasProperties=[prop(k, v) for k, v in values.items()])
        model.create_entity("IfcRelDefinesByProperties", GlobalId=gid("rel/" + obj.GlobalId + "/" + name), RelatedObjects=[obj],
                            RelatingPropertyDefinition=ps_)

    crs = model.create_entity("IfcProjectedCRS", Name=side["crs"]["name"], Description=side["crs"]["definition"],
                              GeodeticDatum=side["crs"].get("geodeticDatum"), VerticalDatum=side["verticalDatum"]["name"],
                              MapProjection=side["crs"].get("mapProjection"), MapUnit=metre)
    model.create_entity("IfcMapConversion", SourceCRS=ctx, TargetCRS=crs, Eastings=float(e0), Northings=float(n0),
                        OrthogonalHeight=float(floor), XAxisAbscissa=ca, XAxisOrdinate=sa, Scale=1.0)
    site.RefElevation = float(ground_origin)

    plist = model.create_entity("IfcCartesianPointList3D", CoordList=[tuple(map(float, p)) for p in zip(fx, fy, fz)])
    tfs = model.create_entity("IfcTriangulatedFaceSet", Coordinates=plist, Closed=False,
                              CoordIndex=[tuple(int(i) + 1 for i in t) for t in tris])
    rep = model.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
                              RepresentationType="Tessellation", Items=[tfs])
    place = model.create_entity("IfcLocalPlacement", PlacementRelTo=site.ObjectPlacement, RelativePlacement=model.create_entity(
        "IfcAxis2Placement3D", Location=model.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])))
    terrain = model.create_entity("IfcGeographicElement", GlobalId=gid("terrain/" + pm["sha256"]), Name="Terrain",
                                  ObjectPlacement=place, Representation=model.create_entity("IfcProductDefinitionShape", Representations=[rep]),
                                  PredefinedType="TERRAIN")
    model.create_entity("IfcRelContainedInSpatialStructure", GlobalId=gid("contain/terrain/" + pm["sha256"]), RelatingStructure=site,
                        RelatedElements=[terrain])
    pset(terrain, "Pset_Declaration_Terrain", {
        "Role": "derived-context", "PackageName": side["package"]["name"], "PackageVersion": side["package"]["version"],
        "PackageSha256": side["package"]["sha256"], "PatchSha256": pm["sha256"], "PatchLevel": pm["level"],
        "PixelSizeMetres": ps, "ErrorBoundMetres": bound, "MeasuredMaxErrorMetres": round(worst, 6),
        "Frame": FILE_FRAME, "VerticalDatum": "%s; sea level at %g m in the site frame" % (side["verticalDatum"]["name"], sea)})
    site_props = {"SeaLevelMetres": sea, "FootprintInWater": bool(in_water), "FloorHeightAboveSeaMetres": float(floor),
                  "TerrainHeightAtOriginMetres": round(float(ground_origin), 6)}
    dist = (side.get("water") or {}).get("distanceToShoreMetres")
    if dist is not None:
        site_props["DistanceToShoreMetres"] = float(dist)
    pset(site, "Pset_Declaration_Site", site_props)

    text = model.to_string()
    old_name = re.search(r"FILE_NAME\(.*?\);", raw, re.S)
    if old_name:
        text = re.sub(r"FILE_NAME\(.*?\);", lambda _m: old_name.group(0), text, count=1, flags=re.S)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="\n") as fh:
        fh.write(text)
    print("wrote %s: %d samples reduced to %d vertices and %d triangles (max error %.4f m at the samples, bound %g m); site elevation %.3f m; "
          "floor %.3f m above sea level; footprint in water: %s" % (a.out, z.size, len(fx), len(tris), worst, bound, ground_origin, floor,
                                                                     "yes" if in_water else "no"))


if __name__ == "__main__":
    main()
