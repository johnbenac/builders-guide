#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export IFC to binary glTF (GLB): the whole model, and every component on its own.

    python3 tools/export_glb.py DELIVERY_DIR --out OUT_DIR [--index INDEX.json] [--json] [--profile PROFILE.json] [--volumes mesh|exclude]
                                [--pivots world|placement|footprint] [--pivot-file PIVOTS.json] [--indexed] [--coplanar off|union]
    python3 tools/export_glb.py MODEL.ifc --out OUT_DIR

DELIVERY_DIR is a delivery folder (deliveries/<slug>/, or any package with ifc/, items/ and finishes/). Writes below OUT_DIR:
    model.glb                      the whole master IFC as a scene graph: root `model`, one `level:<name>` node per building storey,
                                   one node per product below it, named `<kind>:<name>#<GlobalId>`
    components/<kind>-<name>-<hash>.glb   one GLB per furniture item (items/), and per furniture element, covering, fixture or
                                   luminaire assembly, hardware piece, door and window of the master file: exactly the GLB
                                   tools/ingest.py stores for that component
    materials/<set>.glb            one swatch per texture set: a 2 x 2 tile square with the set's maps embedded
Every GLB is deterministic (the same IFC bytes give the same GLB bytes, on the same library versions), and carries no path, time, user or
host. The SHA-256 of each file is printed (and written to the index and the proof manifest).

Conventions (also in `extras` of every GLB): units metres; IFC is Z up, glTF is Y up, converted by (x, y, z) -> (x, z, -y); PBR
metallic-roughness materials with one base colour per IFC surface colour (metallic 0, roughness 0.9, BLEND for translucent colours);
flat per-triangle normals; no textures except in the material swatches. Component GLBs of items keep the item's declared pivot;
those of master-file elements are moved so the pivot is the centre of the footprint at the lowest point (as ingest does).

Volumes (`--volumes`, profile `proofs.glbVolumes`, default `mesh`): zones (IfcSpatialZone) and reservation volumes (IfcBuildingElementProxy of type
PROVISIONFORSPACE) state a requirement, not a thing. With `exclude` they get no mesh and no node (also when they are parts of an assembly: the
assembly's node is built without them, and an assembly of volumes only has no node), and the whole-model GLB lists them in
`extras.excluded` (GlobalId, class, name, type, reason), which `validate_glb.py --ifc` reads: a product with geometry that has no node is
accepted only when it is on that list and is one of these two kinds. With `mesh` (the default of 2.x) they are exported like any product.

Pivots (`--pivots`, profile `proofs.glbPivots`, default `world`): `world` bakes every vertex into world coordinates, so every node's origin is the
model origin (the 2.x behaviour). `placement` gives each product of the whole-model GLB its own origin, the origin of its IFC placement: the
geometry is in that local frame, the placement is the node's translation and rotation, so a chair turns about its own centre, a door leaf about its
hinge when the author put the placement there, and identical shapes (every product with the same geometry) share one mesh. `footprint` puts the
origin at the centre of the footprint at the lowest point, without rotation (as the component GLB files do). `--pivot-file` is a JSON object
`{GlobalId: [x, y] or [x, y, z]}` in IFC world coordinates (metres) that overrides the origin of single products, for example the foot of a
hinge line (z defaults to the lowest point). A product whose placement is not a proper rotation (a mirror, a scale) falls back to `footprint`.
Every export with `placement` or `footprint` also writes `model.placements.json` (beside model.glb; format `placements/1`): per node the product, the origin in the IFC
frame, the turn of the node about the vertical (null when the node is tilted or inverted: its quaternion in the GLB is exact), the 4 x 4 IFC
placement of the product (null for terrain; for `footprint` and `override` nodes the geometry is already turned into world orientation, so that is
the product's placement and not the node's), the mesh and which node it is an instance of. Terrain stays in world coordinates (pivot `world`).
`--pivot-file` entries that match no node that takes a pivot (a mistyped GlobalId, a volume left out, a part of an assembly, terrain) are an error, and
the applied ones are recorded in `extras.pivotOverrides`. `--indexed` shares vertices that agree in position and normal (indexed primitives): flat
normals make a vertex shared only between coplanar triangles, so it saves roughly 15 to 25 percent of the bytes of box-like geometry; the large saving
of a model with many repeated products comes from sharing identical shapes (`--pivots placement`). `proofs.glbIndexed` sets the default and
`--no-indexed` overrides it. The component GLB files and the swatches are not changed by any of these options.

Coincident faces (`--coplanar`, profile `proofs.glbCoplanar`, default `off`): `union` replaces, inside each product of the whole-model GLB, the
coplanar same-facing triangles that overlap (two boxes of one element sharing a plane, drawn in two colours) by the union of their polygons, so the
element no longer fights with itself; the first colour keeps the shared area. Faces of different products that coincide are not changed (the
model has to change; `tools/coplanar.py` lists them, and `validate_glb.py` warns). The result is recorded in `extras.coplanarUnion`.
Needs shapely 2.1 or later.

Exit codes: 0 written, 2 wrong command line, 3 an input could not be read or built. Requires tools/requirements.txt.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coplanar  # noqa: E402
import glbkit  # noqa: E402
import report as rpt  # noqa: E402
from glbkit import Failed, r6, rl, sha256_bytes, slugify  # noqa: E402

VERSION = "2.5.0"
STRUCTURE = {"IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcRoof", "IfcStair", "IfcStairFlight", "IfcRamp", "IfcRampFlight", "IfcColumn",
             "IfcBeam", "IfcMember", "IfcPlate", "IfcFooting", "IfcCurtainWall", "IfcBuildingElementProxy", "IfcCovering"}
NODE_KINDS = ("furniture", "covering", "fixture", "hardware", "door", "window", "structure", "terrain", "other")
SAFE = re.compile(r"[^A-Za-z0-9 ._,()+-]+")


def safe_name(text, n=80):
    return SAFE.sub("-", str(text or "")).strip(" -")[:n] or "unnamed"


def sha_file(path):
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def find_masters(delivery):
    """Relative paths of the master IFC files of a delivery folder."""
    man = os.path.join(delivery, "delivery.json")
    if not os.path.exists(man):
        man = os.path.join(delivery, "manifest.json")
    if os.path.exists(man):
        try:
            with open(man, encoding="utf-8") as fh:
                found = sorted(f["path"] for f in json.load(fh).get("files", []) if f.get("role") == "master-ifc")
            if found:
                return found
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return sorted(os.path.relpath(p, delivery).replace(os.sep, "/") for p in glob.glob(os.path.join(delivery, "ifc", "*.ifc")))


def prop(entity, pset_name, prop_name):
    for rel in getattr(entity, "IsDefinedBy", None) or []:
        ps = getattr(rel, "RelatingPropertyDefinition", None)
        if ps is not None and ps.is_a("IfcPropertySet") and (pset_name is None or ps.Name == pset_name):
            for p in ps.HasProperties or []:
                if p.Name == prop_name and getattr(p, "NominalValue", None) is not None:
                    return str(p.NominalValue.wrappedValue)
    return None


def room_records(model):
    """Rooms (IfcSpace) with identifier, name, function (the room kind), level, bounds and footprint, in the IFC frame."""
    import numpy as np
    import ifcopenshell.geom
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    out = []
    for sp in sorted(model.by_type("IfcSpace"), key=lambda e: e.GlobalId):
        if not getattr(sp, "Representation", None):
            continue
        try:
            g = ifcopenshell.geom.create_shape(st, sp).geometry
        except Exception as exc:
            raise Failed("room %s (%s): geometry could not be built: %s" % (sp.Name, sp.GlobalId, str(exc)[:100]))
        v = np.array(g.verts, dtype=float).reshape(-1, 3)
        f = np.array(g.faces, dtype=int).reshape(-1, 3)
        if not len(f):
            continue
        low = v[:, 2].min()
        polys = [Polygon(t[:, :2]) for t in v[f] if np.allclose(t[:, 2], low, atol=1e-6) and Polygon(t[:, :2]).area > 1e-9]
        if not polys:
            continue
        outline = unary_union(polys).buffer(0)
        geoms = list(outline.geoms) if hasattr(outline, "geoms") else [outline]
        big = max(geoms, key=lambda x: x.area)
        ring = [[r6(x), r6(y)] for x, y in list(big.exterior.coords)[:-1]]
        lv = glbkit.level_of(sp)
        rid = prop(sp, None, "RoomId") or sp.Name or sp.GlobalId
        out.append({"id": safe_name(rid, 64), "name": safe_name(sp.LongName or sp.Name, 80), "function": safe_name(prop(sp, None, "Function") or "unspecified", 80),
                    "level": safe_name(lv.Name, 80) if lv is not None else None, "external": str(sp.PredefinedType or "") == "EXTERNAL",
                    "min": rl(v.min(axis=0)), "max": rl(v.max(axis=0)), "footprint": ring})
    return out


VOLUME_MODES = ("mesh", "exclude")


def volumes_mode(volumes=None):
    """`volumes` as given, else the profile's proofs.glbVolumes, else "mesh"."""
    mode = volumes or rpt.param("proofs.glbVolumes", "mesh")
    if mode not in VOLUME_MODES:
        raise Failed("volumes must be one of %s, not %r" % (", ".join(VOLUME_MODES), mode))
    return mode


PIVOT_MODES = ("world", "placement", "footprint")
COPLANAR_MODES = ("off", "union")


def coplanar_mode(mode=None):
    mode = mode or rpt.param("proofs.glbCoplanar", "off")
    if mode not in COPLANAR_MODES:
        raise Failed("coplanar must be one of %s, not %r" % (", ".join(COPLANAR_MODES), mode))
    return mode



def pivots_mode(pivots=None):
    mode = pivots or rpt.param("proofs.glbPivots", "world")
    if mode not in PIVOT_MODES:
        raise Failed("pivots must be one of %s, not %r" % (", ".join(PIVOT_MODES), mode))
    return mode


def is_indexed(indexed=None):
    return bool(rpt.param("proofs.glbIndexed", False) if indexed is None else indexed)


def to_gltf_matrix(m):
    """A 4 x 4 placement of the IFC frame (Z up) as the same placement in the glTF frame (Y up): C m C^-1 with C the axis conversion."""
    import numpy as np
    c = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
    return c @ m @ np.linalg.inv(c)


def pivot_node(m_root, parts, world, mode, override):
    """The local geometry and the node transform of one product. m_root: its 4x4 placement (IFC frame); parts: its geometry in that frame;
    world: the same in world coordinates (from m_root). Returns (local parts, node dict or None, pivot origin in the IFC frame, rotation about Z in
    degrees, or None when the node's rotation is not a turn about the vertical, pivot kind). node is None for `world`."""
    import numpy as np
    if mode == "world":
        return world, None, (0.0, 0.0, 0.0), 0.0, "world"
    allv = np.concatenate([t for _, t in world])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    proper = override is None and mode == "placement" and glbkit.quaternion_of(m_root[:3, :3]) is not None
    if proper:
        local = [(c, np.round(t, 6) + 0.0) for c, t in parts]
        g = to_gltf_matrix(m_root)
        q = glbkit.quaternion_of(g[:3, :3])
        node = {"translation": [float(g[0, 3]), float(g[1, 3]), float(g[2, 3])], "rotation": q if not np.allclose(q, [0, 0, 0, 1], atol=1e-9) else None}
        upright = abs(m_root[2, 2] - 1.0) < 1e-9 and abs(m_root[0, 2]) < 1e-9 and abs(m_root[1, 2]) < 1e-9 and abs(m_root[2, 0]) < 1e-9 and abs(m_root[2, 1]) < 1e-9
        yaw = float(np.degrees(np.arctan2(m_root[1, 0], m_root[0, 0]))) if upright else None      # None: tilted or inverted, the quaternion of the node says how
        return local, node, tuple(float(v) for v in m_root[:3, 3]), yaw, "placement"
    if override is not None:
        o = np.array([override[0], override[1], override[2] if len(override) > 2 else lo[2]], dtype=float)
        kind = "override"
    else:
        o = np.array([(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2]])
        kind = "footprint"
    o = np.round(o, 6) + 0.0
    local = [(c, np.round(t - o, 6) + 0.0) for c, t in world]
    return local, {"translation": [float(o[0]), float(o[2]), float(-o[1])], "rotation": None}, tuple(float(v) for v in o), 0.0, kind


def model_roots(model, volumes="mesh"):
    """[(root, geometry products, kind, category)] for everything the whole-model GLB holds: every product with geometry that is not an opening,
    space, annotation or grid and not part of an assembly (an assembly is one root), terrain included. In GlobalId order. With volumes="exclude"
    zones and reservation volumes are left out too (`glbkit.excluded_volumes` lists them)."""
    out, seen = [], set()
    skip = glbkit.exclusion_reason if volumes == "exclude" else None       # also drops a volume that is a part of an assembly
    for e in sorted(model.by_type("IfcProduct"), key=lambda x: x.GlobalId):
        cls = e.is_a()
        if (cls in glbkit.SKIP_CLASSES and cls != "IfcGeographicElement") or e.id() in seen or cls == "IfcBuildingStorey":
            continue
        if skip is not None and skip(e):
            continue
        if any(r.RelatingObject.is_a("IfcElementAssembly") for r in (getattr(e, "Decomposes", None) or [])):
            continue
        parts_p = [e] if (cls == "IfcGeographicElement" and getattr(e, "Representation", None)) else ([] if cls == "IfcGeographicElement" else glbkit.part_products(e, skip))
        if not parts_p:
            continue
        for p in parts_p:
            seen.add(p.id())
        kind, cat = glbkit.kind_and_category(e, parts_p)
        if cls == "IfcGeographicElement":
            kind, cat = "terrain", "terrain"
        elif not kind:
            kind = "structure" if cls in STRUCTURE else "other"
            cat = slugify(cls[3:])
        out.append((e, parts_p, kind, cat))
    return out


def expected_levels_and_rooms(path, volumes=None):
    """(level names that hold at least one exported product, [(room id, room kind, level name)]) of an IFC file, without building geometry."""
    import ifcopenshell
    model = ifcopenshell.open(path)
    levels = set()
    for e, _p, _k, _c in model_roots(model, volumes_mode(volumes)):
        lv = glbkit.level_of(e)
        if lv is not None:
            levels.add(safe_name(lv.Name, 80))
    rooms = []
    for sp in sorted(model.by_type("IfcSpace"), key=lambda e: e.GlobalId):
        if getattr(sp, "Representation", None):
            lv = glbkit.level_of(sp)
            rooms.append((safe_name(prop(sp, None, "RoomId") or sp.Name or sp.GlobalId, 64), safe_name(prop(sp, None, "Function") or "unspecified", 80),
                          safe_name(lv.Name, 80) if lv is not None else None))
    return levels, rooms


def model_glb(path, rel, ifc_sha, limits=None, volumes=None, pivots=None, indexed=None, overrides=None, coplanar_union=None, check_overrides=True):
    """The whole-model GLB of one IFC file. Returns dict(glb, sha256, triangles, nodes, bounds, rooms, levels, counts, excluded, placements).
    pivots: world, placement or footprint (see the module doc); overrides: {GlobalId: [x, y(, z)]} pivot points in IFC world coordinates; an
    entry that no node uses is an error unless check_overrides is false (a delivery with several master files checks the union itself)."""
    import numpy as np
    import ifcopenshell
    limits = limits or glbkit.NullLimits()
    volumes = volumes_mode(volumes)
    pivots = pivots_mode(pivots)
    indexed = is_indexed(indexed)
    union = coplanar_mode(coplanar_union) == "union"
    union_stats = [0, 0.0]
    overrides = overrides or {}
    used_overrides = set()
    placements = []
    skip_volume = glbkit.exclusion_reason if volumes == "exclude" else None
    model = ifcopenshell.open(path)
    storeys = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: (float(s.Elevation or 0.0), s.GlobalId))
    by_level = {s.id(): [] for s in storeys}
    loose = []
    lo_all, hi_all, ntri, nnodes, counts = None, None, 0, 0, {}
    for e, parts_p, kind, cat in model_roots(model, volumes):
        cls = e.is_a()
        if cls == "IfcGeographicElement":
            import ifcopenshell.geom
            st = ifcopenshell.geom.settings()
            st.set("use-world-coords", True)
            g = ifcopenshell.geom.create_shape(st, e).geometry
            v = np.array(g.verts, dtype=float).reshape(-1, 3)
            f = np.array(g.faces, dtype=int).reshape(-1, 3)
            parts = [((0.6, 0.7, 0.45, 1.0), v[f].reshape(-1, 3))]
            world = [(c, np.round(t, 6) + 0.0) for c, t in parts]
            local, own, origin, yaw, pk = world, None, (0.0, 0.0, 0.0), 0.0, "world"
        else:
            parts, m_root = glbkit.shape_parts(model, e, limits, skip_volume)
            if union:
                parts, n_planes, area = coplanar.union_parts(parts)
                union_stats[0] += n_planes
                union_stats[1] += area
            world = [(c, np.round(t @ m_root[:3, :3].T + m_root[:3, 3], 6) + 0.0) for c, t in parts]
            local, own, origin, yaw, pk = pivot_node(m_root, parts, world, pivots, overrides.get(e.GlobalId))
            if own is not None and e.GlobalId in overrides:
                used_overrides.add(e.GlobalId)
        allv = np.concatenate([t for _, t in world])
        lo_all = allv.min(axis=0) if lo_all is None else np.minimum(lo_all, allv.min(axis=0))
        hi_all = allv.max(axis=0) if hi_all is None else np.maximum(hi_all, allv.max(axis=0))
        ntri += sum(len(t) // 3 for _, t in world)
        lv = glbkit.level_of(e)
        node = {"name": "%s:%s#%s" % (kind, safe_name(e.Name or cat), e.GlobalId),
                "extras": {"globalId": e.GlobalId, "ifcClass": cls, "kind": kind, "category": cat, "level": safe_name(lv.Name, 80) if lv is not None else None},
                "parts": local}
        if own is not None:
            node["node"] = own
        if pivots != "world":                  # one row per node; terrain stays in world coordinates (pivot "world", no placement)
            placements.append((node, e, kind, cat, origin, yaw, pk, None if cls == "IfcGeographicElement" else m_root, sum(len(t) // 3 for _, t in world)))
        counts[kind] = counts.get(kind, 0) + 1
        nnodes += 1
        (by_level[lv.id()] if lv is not None and lv.id() in by_level else loose).append(node)
    if lo_all is None:
        raise Failed("%s holds no geometry to export" % rel)
    unused = sorted(set(overrides) - used_overrides)
    if unused and check_overrides:
        raise Failed("pivot file: %d entr%s match no product node that takes a pivot (a wrong GlobalId, a volume left out, a part of an assembly, terrain), for example %s"
                     % (len(unused), "y" if len(unused) == 1 else "ies", ", ".join(unused[:3])))
    levels = [{"name": safe_name(s.Name, 80), "extras": {"elevation": r6(float(s.Elevation or 0.0))}, "components": by_level[s.id()]} for s in storeys]
    levels = [lv for lv in levels if lv["components"]] + [lv for lv in levels if not lv["components"]]
    rooms = room_records(model)
    extras = {"source": {"ifcPath": rel, "ifcSha256": ifc_sha},
              "levels": [{"name": lv["name"], "elevation": lv["extras"]["elevation"]} for lv in levels],
              "rooms": rooms, "bounds": {"min": rl(lo_all), "max": rl(hi_all)}, "counts": dict(sorted(counts.items()))}
    excluded = []
    if volumes == "exclude":
        excluded = [dict(x, name=safe_name(x["name"], 80)) for x in glbkit.excluded_volumes(model)]
        extras["excluded"] = excluded
    if pivots != "world":
        extras["nodePivots"] = pivots
    if used_overrides:
        extras["pivotOverrides"] = sorted(used_overrides)
    if indexed:
        extras["indexed"] = True
    if union:
        extras["coplanarUnion"] = {"planesResolved": union_stats[0], "areaRemovedM2": round(union_stats[1], 4)}
    glb = glbkit.write_scene_glb("model", levels, loose, extras, indexed)
    table = None
    if pivots != "world":
        rows = []
        for node, e, kind, cat, origin, yaw, pk, m_root, ntr in placements:
            rows.append({"node": node["name"], "globalId": e.GlobalId, "ifcClass": e.is_a(), "kind": kind, "category": cat, "level": node["extras"]["level"],
                         "pivot": pk, "originIfc": rl(origin), "rotationZDegrees": None if yaw is None else round(yaw, 4) + 0.0, "mesh": node["mesh"], "instanceOf": node["instanceOf"],
                         "triangles": ntr, "placementIfc": [rl(r) for r in m_root] if m_root is not None else None})
        rows.sort(key=lambda r: r["node"])
        table = {"format": "placements/1", "model": rel, "ifcSha256": ifc_sha, "modelSha256": sha256_bytes(glb), "nodePivots": pivots,
                 "meshes": len({r["mesh"] for r in rows}), "nodes": rows}
    return {"glb": glb, "sha256": sha256_bytes(glb), "triangles": ntri, "nodes": nnodes + len(levels) + 1,
            "bounds": extras["bounds"], "rooms": rooms, "levels": extras["levels"], "counts": extras["counts"], "excluded": excluded, "placements": table, "usedOverrides": sorted(used_overrides)}


def component_list(delivery, limits=None):
    """Every component of a delivery as a GLB: [{key, kind, category, name, source, glb, sha256, triangles, bounds, dimensions}].
    The order is fixed: items by id, then master-file elements by file and GlobalId, then material sets by name. Duplicates (identical GLB
    bytes) are kept; export_delivery() merges them."""
    import ifcopenshell
    limits = limits or glbkit.NullLimits()
    out = []
    base = os.path.join(delivery, "items")
    if os.path.isdir(base):
        for iid in sorted(os.listdir(base)):
            d = os.path.join(base, iid)
            ifc_rel, js_rel = "items/%s/%s.ifc" % (iid, iid), "items/%s/%s.item.json" % (iid, iid)
            if not (os.path.isdir(d) and os.path.exists(os.path.join(delivery, ifc_rel))):
                continue
            jd = {}
            if os.path.exists(os.path.join(delivery, js_rel)):
                with open(os.path.join(delivery, js_rel), encoding="utf-8") as fh:
                    jd = json.load(fh)
            model = ifcopenshell.open(os.path.join(delivery, ifc_rel))
            root = glbkit.item_root(model, ifc_rel)
            geo = glbkit.component_geometry(model, root, limits, False)
            kind = glbkit.kind_of_class(jd.get("class", "")) or glbkit.kind_of_class(root.is_a()) or "furniture"
            out.append(_entry("item:" + iid, kind, slugify(jd.get("category"), "item"), str(jd.get("name") or root.Name or iid), ifc_rel,
                              sha_file(os.path.join(delivery, ifc_rel)), geo))
    for rel in find_masters(delivery):
        model = ifcopenshell.open(os.path.join(delivery, rel))
        ifc_sha = sha_file(os.path.join(delivery, rel))
        for root, _parts, kind, cat in glbkit.master_roots(model):
            geo = glbkit.component_geometry(model, root, limits, True)
            out.append(_entry("ifc:%s#%s" % (rel, root.GlobalId), kind, cat, str(root.Name or cat), rel, ifc_sha, geo))
    return out


def _entry(key, kind, category, name, rel, ifc_sha, geo):
    return {"key": key, "kind": kind, "category": category, "name": safe_name(name, 120), "source": {"path": rel, "sha256": ifc_sha},
            "glb": geo["glb"], "sha256": sha256_bytes(geo["glb"]), "triangles": geo["triangles"],
            "bounds": {"min": rl(geo["lo"]), "max": rl(geo["hi"])}}


def material_list(delivery):
    out = []
    base = os.path.join(delivery, "finishes", "textures")
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        sp = os.path.join(d, "set.json")
        if not (os.path.isdir(d) and os.path.exists(sp)):
            continue
        with open(sp, "rb") as fh:
            sdata = fh.read()
        sj = json.loads(sdata.decode("utf-8"))
        imgs = {}
        for k in ("albedo", "normal", "orm"):
            fn = (sj.get("maps") or {}).get(k)
            if fn and os.path.exists(os.path.join(d, fn)):
                with open(os.path.join(d, fn), "rb") as fh:
                    imgs[k] = fh.read()
        if "albedo" not in imgs:
            raise Failed("texture set %s has no albedo map to export" % name)
        glb = glbkit.write_swatch_glb(safe_name(name, 60), float(sj.get("tileMetres") or 1.0), imgs,
                                      {"source": {"setPath": "finishes/textures/" + name, "setSha256": sha256_bytes(sdata)}})
        out.append({"key": "material:" + name, "kind": "material-set", "category": "material-set", "name": safe_name(name, 60),
                    "source": {"path": "finishes/textures/%s/set.json" % name, "sha256": sha256_bytes(sdata)},
                    "glb": glb, "sha256": sha256_bytes(glb), "triangles": 2, "bounds": None})
    return out


def export_delivery(delivery, limits=None, volumes=None, pivots=None, indexed=None, overrides=None, coplanar_union=None):
    """Everything export_glb writes, in memory: {"models": [...], "components": [...], "materials": [...]}. Components with identical GLB
    bytes are merged into one entry listing all their keys and names; every entry has `rel`, the path below the output folder."""
    models, used_all = [], set()
    masters = find_masters(delivery)
    for rel in masters:
        p = os.path.join(delivery, rel)
        m = model_glb(p, rel, sha_file(p), limits, volumes, pivots, indexed, overrides, coplanar_union, check_overrides=False)
        used_all.update(m["usedOverrides"])
        m["source"] = {"path": rel, "sha256": sha_file(p)}
        m["keys"], m["kind"], m["category"], m["names"] = ["model:" + rel], "model", "model", ["whole model"]
        m["rel"] = "model.glb" if len(masters) == 1 else "model-%s.glb" % slugify(os.path.splitext(os.path.basename(rel))[0])
        models.append(m)
    unused = sorted(set(overrides or {}) - used_all)
    if unused:
        raise Failed("pivot file: %d entr%s match no product node of any master file that takes a pivot (a wrong GlobalId, a volume left out, a part of an assembly, "
                     "terrain), for example %s" % (len(unused), "y" if len(unused) == 1 else "ies", ", ".join(unused[:3])))
    merged, order = {}, []
    for c in component_list(delivery, limits) + material_list(delivery):
        if c["sha256"] in merged:
            e = merged[c["sha256"]]
            e["keys"].append(c["key"])
            e["names"].append(c["name"])
            continue
        c["keys"], c["names"] = [c["key"]], [c["name"]]
        merged[c["sha256"]] = c
        order.append(c)
    comps, mats = [], []
    for c in order:
        folder = "materials" if c["kind"] == "material-set" else "components"
        c["rel"] = "%s/%s-%s-%s.glb" % (folder, c["kind"], slugify(c["name"], 40), sha256_bytes(c["keys"][0].encode("utf-8"))[:8]) \
            if folder == "components" else "materials/%s.glb" % slugify(c["name"], 60)
        (mats if folder == "materials" else comps).append(c)
    if len({c["rel"] for c in comps + mats + models}) != len(comps) + len(mats) + len(models):
        raise Failed("two exported files would have the same name; rename a texture set or an item")
    return {"models": models, "components": comps, "materials": mats}


def expected_keys(delivery):
    """The keys a complete export of a delivery has, found without building any geometry: {key: kind}. A key is `model:<ifc path>`,
    `item:<itemId>`, `ifc:<ifc path>#<GlobalId>` or `material:<set>`. Used by check_proofs.py to see whether anything is missing."""
    import ifcopenshell
    out = {}
    for rel in find_masters(delivery):
        out["model:" + rel] = "model"
        model = ifcopenshell.open(os.path.join(delivery, rel))
        for root, _parts, kind, _cat in glbkit.master_roots(model):
            out["ifc:%s#%s" % (rel, root.GlobalId)] = kind
    base = os.path.join(delivery, "items")
    if os.path.isdir(base):
        for iid in sorted(os.listdir(base)):
            if os.path.exists(os.path.join(base, iid, iid + ".ifc")):
                out["item:" + iid] = "item"
    base = os.path.join(delivery, "finishes", "textures")
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            if os.path.exists(os.path.join(base, name, "set.json")):
                out["material:" + name] = "material-set"
    return out


def write_all(result, out_dir):
    """Write an export_delivery() result below out_dir and return the index [{path, sha256, bytes, role, ...}]."""
    index = []
    for role, key in (("model", "models"), ("component", "components"), ("material", "materials")):
        for e in result[key]:
            path = os.path.join(out_dir, e["rel"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(e["glb"])
            index.append({"path": e["rel"], "role": role, "sha256": e["sha256"], "bytes": len(e["glb"])})
            if e.get("placements"):                       # beside the model; not a GLB, so not in the index or the proof manifest
                with open(os.path.splitext(path)[0] + ".placements.json", "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(e["placements"], fh, indent=1)
                    fh.write("\n")
    return index


def parse_pivot_file(obj):
    """{GlobalId: [x, y, z or None]} from the JSON of a pivot file; ValueError with the reason when it is not {GlobalId: [x, y] or [x, y, z]} of finite numbers."""
    import math
    if not isinstance(obj, dict) or not obj:
        raise ValueError("must be a JSON object {GlobalId: [x, y] or [x, y, z]} with at least one entry")
    out = {}
    for gid, v in obj.items():
        if not (isinstance(gid, str) and re.fullmatch(r"[0-9A-Za-z_$]{22}", gid)):
            raise ValueError("%r is not a GlobalId (22 characters)" % (gid,))
        if not (isinstance(v, list) and len(v) in (2, 3)):
            raise ValueError("%s: expected [x, y] or [x, y, z]" % gid)
        for x in v:
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError("%s: %r is not a finite number" % (gid, x))
        out[gid] = [float(x) for x in v]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a delivery folder, or one .ifc file")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--index", help="also write the list of files with their SHA-256 as JSON")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--profile", help="consumer profile (its proofs.glbVolumes sets the default of --volumes)")
    ap.add_argument("--pivots", choices=PIVOT_MODES, help="world (default): vertices baked into world coordinates; placement: each product has its own origin and the model GLB "
                    "shares identical shapes; footprint: origin at the centre of the footprint at the lowest point")
    ap.add_argument("--pivot-file", help="JSON {GlobalId: [x, y(, z)]} of pivot points in IFC world coordinates (for example door hinges)")
    ap.add_argument("--indexed", action=argparse.BooleanOptionalAction, default=None, help="share vertices that agree in position and normal (--no-indexed overrides a profile that sets proofs.glbIndexed)")
    ap.add_argument("--coplanar", choices=COPLANAR_MODES, help="union: merge overlapping coplanar same-facing triangles inside each product (needs shapely 2.1)")
    ap.add_argument("--volumes", choices=VOLUME_MODES, help="mesh: zones and reservation volumes are exported like any product; exclude: left out and listed in extras.excluded")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    if not os.path.exists(a.path):
        print("ERROR not found: %s" % a.path, file=sys.stderr)
        sys.exit(3)
    overrides = None
    if a.pivot_file:
        if pivots_mode(a.pivots) == "world":
            print("ERROR --pivot-file needs --pivots placement or footprint (with world pivots every origin is the model origin and the file would do nothing)", file=sys.stderr)
            sys.exit(2)
        try:
            with open(a.pivot_file, encoding="utf-8") as fh:
                overrides = parse_pivot_file(json.load(fh))
        except (OSError, ValueError) as exc:
            print("ERROR --pivot-file %s: %s" % (a.pivot_file, exc), file=sys.stderr)
            sys.exit(2)
    try:
        if os.path.isfile(a.path):
            m = model_glb(a.path, os.path.basename(a.path), sha_file(a.path), volumes=a.volumes, pivots=a.pivots, indexed=a.indexed, overrides=overrides, coplanar_union=a.coplanar)
            res = {"models": [dict(m, rel="model.glb", source={"path": os.path.basename(a.path), "sha256": sha_file(a.path)})], "components": [], "materials": []}
        else:
            res = export_delivery(os.path.abspath(a.path), volumes=a.volumes, pivots=a.pivots, indexed=a.indexed, overrides=overrides, coplanar_union=a.coplanar)
        index = write_all(res, a.out)
    except Failed as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        sys.exit(3)
    except Exception as exc:                                  # an unreadable IFC file
        print("FAILED: %s: %s" % (type(exc).__name__, str(exc)[:200]), file=sys.stderr)
        sys.exit(3)
    if a.index:
        with open(a.index, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(index, fh, indent=1)
            fh.write("\n")
    if a.json:
        print(json.dumps(index, indent=1))
    else:
        for e in index:
            print("%s  %s  (%d bytes)" % (e["sha256"], e["path"], e["bytes"]))


if __name__ == "__main__":
    main()
