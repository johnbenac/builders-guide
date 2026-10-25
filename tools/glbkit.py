# SPDX-License-Identifier: Apache-2.0
"""Shared geometry code of ingest.py, export_glb.py, validate_glb.py and render.py: IFC products to triangles, triangles to GLB, GLB back
to triangles. Not a command-line tool.

Conventions of every GLB this set writes (guide 4, section 8; `08-submissions-and-ingest.md`):
  * units are metres;
  * the IFC frame is Z up, glTF is Y up: a point is converted by (x, y, z) -> (x, z, -y), and back by (x, y, z) -> (x, -z, y);
  * geometry is a triangle soup with one flat normal per triangle; colours become PBR metallic-roughness materials (base colour factor,
    metallic 0, roughness 0.9, double sided, BLEND when the IFC colour is translucent);
  * nothing in the file depends on the machine, the user or the time: the same IFC bytes always give the same GLB bytes.
`GLB_GENERATOR` is frozen on purpose: a component's identity is the hash of its GLB bytes, so the string is not changed by releases.
"""
import hashlib
import json
import re
import struct

GLB_GENERATOR = "authoring-guide-set ingest 2.2.0"
AXIS_NOTE = "(x,y,z) -> (x,z,-y) from the IFC frame (Z up) to glTF (Y up)"
MAX_TRIANGLES = 2000000          # per component
FURNITURE = {"IfcFurnishingElement", "IfcFurniture", "IfcSystemFurnitureElement"}
FIXTURE = {"IfcLightFixture", "IfcLamp", "IfcSanitaryTerminal", "IfcElectricAppliance", "IfcFlowTerminal", "IfcAlarm", "IfcOutlet",
           "IfcSwitchingDevice", "IfcAudioVisualAppliance", "IfcCommunicationsAppliance", "IfcSensor", "IfcWasteTerminal"}
HARDWARE = {"IfcDiscreteAccessory", "IfcMechanicalFastener", "IfcFastener", "IfcRailing"}
KIND_OF = {"IfcCovering": "covering", "IfcDoor": "door", "IfcWindow": "window"}
COVERING_CATEGORY = {"FLOORING": "floor-covering", "CEILING": "ceiling-covering", "CLADDING": "wall-covering", "WRAPPING": "wall-covering",
                     "MEMBRANE": "covering", "INSULATION": "covering", "SLEEVING": "covering", "MOLDING": "covering", "SKIRTINGBOARD": "covering"}
SKIP_CLASSES = {"IfcOpeningElement", "IfcVirtualElement", "IfcSpace", "IfcAnnotation", "IfcGrid", "IfcGeographicElement"}
# Volumes that state a requirement or a room, not a thing: a consumer must not draw or collide with them. `exclusion_reason` names them, an
# export in `volumes="exclude"` mode leaves them out and lists them (`extras.excluded` of the whole-model GLB), and the validator accepts
# a missing node only for a product that is on that list and of one of these kinds.
VOLUME_REASONS = {"zone": "IfcSpatialZone", "reservation": "IfcBuildingElementProxy PROVISIONFORSPACE"}


class Failed(Exception):
    """A limit, a read error or an internal check failed."""


class NullLimits:
    """Stands in for ingest.Limits when there is no time limit."""

    def tick(self):
        pass


def slugify(text, default="item"):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:60] or default


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def r6(x):
    v = round(float(x), 6)
    return 0.0 if v == 0 else v


def rl(seq):
    return [r6(x) for x in seq]


# ---------------------------------------------------------------- GLB writing
def _soup_arrays(rgba_tri):
    import numpy as np
    out = []
    for rgba, tri in sorted(rgba_tri, key=lambda p: tuple(p[0])):
        v = np.array(tri, dtype=np.float64).reshape(-1, 3)
        v = np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1)                  # Z up -> Y up
        t = v.reshape(-1, 3, 3)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ln = np.linalg.norm(n, axis=1)
        n = n / np.where(ln > 1e-12, ln, 1.0)[:, None]
        out.append((rgba, v.astype("<f4"), np.repeat(n, 3, axis=0).astype("<f4")))
    return out


def _indexed_arrays(parts):
    """Like _soup_arrays, but vertices that agree in position and normal are shared: [(rgba, positions Mx3 float32, normals Mx3 float32, indices uint32)].
    The vertex order is the order of first use, so the same shape always gives the same bytes."""
    import numpy as np
    out = []
    for rgba, pv, nv in _soup_arrays(parts):
        key = np.concatenate([pv, nv], axis=1)
        uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        order = np.argsort(first, kind="stable")
        rank = np.empty_like(order)
        rank[order] = np.arange(len(order))
        idx = rank[inv.reshape(-1)].astype("<u4")
        uniq = uniq[order]
        out.append((rgba, np.ascontiguousarray(uniq[:, :3], dtype="<f4"), np.ascontiguousarray(uniq[:, 3:], dtype="<f4"), idx))
    return out


def quaternion_of(r):
    """Unit quaternion (x, y, z, w) of a 3x3 rotation matrix, with w >= 0 and rounded to 9 places (stable bytes); None when r is not a proper rotation."""
    import numpy as np
    r = np.asarray(r, dtype=float)
    if not (np.allclose(r @ r.T, np.eye(3), atol=1e-6) and np.linalg.det(r) > 0):
        return None
    t = np.trace(r)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = [(r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s, 0.25 * s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2
        q = [0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s, (r[2, 1] - r[1, 2]) / s]
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2
        q = [(r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s, (r[0, 2] - r[2, 0]) / s]
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2
        q = [(r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s, (r[1, 0] - r[0, 1]) / s]
    q = np.array(q) / np.linalg.norm(q)
    if q[3] < 0 or (q[3] == 0 and q[np.nonzero(q)[0][0]] < 0):
        q = -q
    return [round(float(x), 9) + 0.0 for x in q]


def _pack(doc, bin_chunks):
    js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    js += b" " * (-len(js) % 4)
    bn = b"".join(bin_chunks)
    bn += b"\0" * (-len(bn) % 4)
    total = 12 + 8 + len(js) + 8 + len(bn)
    return b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bn), b"BIN\0") + bn


def _material(rgba, name=None):
    m = {"pbrMetallicRoughness": {"baseColorFactor": [float(x) for x in rgba], "metallicFactor": 0.0, "roughnessFactor": 0.9},
         "alphaMode": "BLEND" if rgba[3] < 0.999 else "OPAQUE", "doubleSided": True}
    if name:
        m["name"] = name
    return m


def write_glb(parts):
    """One mesh, one node. parts: list of (rgba tuple, Nx3 float array of triangle-soup vertices, Z up). Returns the GLB bytes.
    Byte-stable across releases (component identity depends on it)."""
    bin_chunks, views, accs, prims, mats = [], [], [], [], []
    off = 0
    for rgba, pv, nv in _soup_arrays(parts):
        for arr in (pv, nv):
            b = arr.tobytes()
            views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b), "target": 34962})
            bin_chunks.append(b)
            off += len(b)
        accs.append({"bufferView": len(views) - 2, "componentType": 5126, "count": int(len(pv)), "type": "VEC3",
                     "min": [float(x) for x in pv.min(axis=0)], "max": [float(x) for x in pv.max(axis=0)]})
        accs.append({"bufferView": len(views) - 1, "componentType": 5126, "count": int(len(nv)), "type": "VEC3"})
        mats.append(_material(rgba))
        prims.append({"attributes": {"POSITION": len(accs) - 2, "NORMAL": len(accs) - 1}, "material": len(mats) - 1, "mode": 4})
    doc = {"asset": {"version": "2.0", "generator": GLB_GENERATOR},
           "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}], "meshes": [{"primitives": prims}],
           "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": off}],
           "extras": {"units": "metres", "axisConversion": AXIS_NOTE}}
    return _pack(doc, bin_chunks)


def write_scene_glb(name, levels, loose, extras, indexed=False):
    """A whole model as a scene graph: root node `model`, one child per level (`level:<name>`), one child per component below it.

    levels: list of {"name", "components": [component]}; loose: components without a level (placed under the root);
    component: {"name": node name, "extras": dict, "parts": [(rgba, Nx3 triangle soup, Z up)]} and, for a node with its own pivot,
    "node": {"translation": [x, y, z] in glTF axes, "rotation": [x, y, z, w] or None}: then `parts` are in the node's own frame (Z up, before the
    axis conversion) and components whose parts are identical share one mesh (instancing). Without "node" the parts are world coordinates and
    nothing is shared. Each component dict gets "mesh" (the mesh index) and "instanceOf" (the name of the first node that uses that mesh, else None).
    indexed: vertices that agree in position and normal are shared and the primitives carry indices.
    extras: dict stored as the document's extras (units and the axis note are added). Materials are shared by colour and named by it."""
    bin_chunks, views, accs, meshes, nodes, mats, mat_index = [], [], [], [], [{"name": name, "children": []}], [], {}
    off = [0]
    shared = {}

    def add_view(arr, target=34962):
        pad = -off[0] % 4
        if pad:
            bin_chunks.append(b"\0" * pad)
            off[0] += pad
        b = arr.tobytes()
        views.append({"buffer": 0, "byteOffset": off[0], "byteLength": len(b), "target": target})
        bin_chunks.append(b)
        off[0] += len(b)
        return len(views) - 1

    def mat_of(rgba):
        key = tuple(float(x) for x in rgba)
        if key not in mat_index:
            hexcol = "".join("%02x" % int(round(x * 255)) for x in key)
            mats.append(_material(key, "colour-" + hexcol))
            mat_index[key] = len(mats) - 1
        return mat_index[key]

    def add_component(c, parent):
        arrays = _indexed_arrays(c["parts"]) if indexed else [(r, p, n, None) for r, p, n in _soup_arrays(c["parts"])]
        own = c.get("node")
        fp = None
        if own is not None:
            h = hashlib.sha256()
            for rgba, pv, nv, ix in arrays:
                h.update(repr(tuple(rgba)).encode() + pv.tobytes() + nv.tobytes() + (ix.tobytes() if ix is not None else b""))
            fp = h.hexdigest()
        if fp is not None and fp in shared:
            mesh_index, c["instanceOf"] = shared[fp]
        else:
            prims = []
            for rgba, pv, nv, ix in arrays:
                va, vb = add_view(pv), add_view(nv)
                accs.append({"bufferView": va, "componentType": 5126, "count": int(len(pv)), "type": "VEC3",
                             "min": [float(x) for x in pv.min(axis=0)], "max": [float(x) for x in pv.max(axis=0)]})
                accs.append({"bufferView": vb, "componentType": 5126, "count": int(len(nv)), "type": "VEC3"})
                pr = {"attributes": {"POSITION": len(accs) - 2, "NORMAL": len(accs) - 1}, "material": mat_of(rgba), "mode": 4}
                if ix is not None:
                    small = len(pv) < 65536
                    vi = add_view(ix.astype("<u2" if small else "<u4"), 34963)
                    accs.append({"bufferView": vi, "componentType": 5123 if small else 5125, "count": int(len(ix)), "type": "SCALAR"})
                    pr["indices"] = len(accs) - 1
                prims.append(pr)
            meshes.append({"name": c["name"], "primitives": prims})
            mesh_index = len(meshes) - 1
            c["instanceOf"] = None
            if fp is not None:
                shared[fp] = (mesh_index, c["name"])
        c["mesh"] = mesh_index
        node = {"name": c["name"], "mesh": mesh_index, "extras": c["extras"]}
        if own is not None:
            if own.get("translation") and any(abs(v) > 0 for v in own["translation"]):
                node["translation"] = [r6(v) for v in own["translation"]]
            if own.get("rotation"):
                node["rotation"] = list(own["rotation"])
        nodes.append(node)
        nodes[parent]["children"].append(len(nodes) - 1)

    for lv in levels:
        nodes.append({"name": "level:" + lv["name"], "children": [], "extras": lv.get("extras", {})})
        nodes[0]["children"].append(len(nodes) - 1)
        me = len(nodes) - 1
        for c in lv["components"]:
            add_component(c, me)
    for c in loose:
        add_component(c, 0)
    for n in nodes:
        if not n.get("children"):
            n.pop("children", None)
    ex = {"units": "metres", "axisConversion": AXIS_NOTE}
    ex.update(extras)
    pad = -off[0] % 4
    if pad:
        bin_chunks.append(b"\0" * pad)
        off[0] += pad
    doc = {"asset": {"version": "2.0", "generator": GLB_GENERATOR}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes,
           "meshes": meshes, "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": off[0]}], "extras": ex}
    return _pack(doc, bin_chunks)


def write_swatch_glb(name, tile_metres, images, extras):
    """A flat swatch of a texture set: a square of 2 x 2 tiles lying in the horizontal plane, +Y up, with POSITION, NORMAL, TANGENT and
    TEXCOORD_0, and the set's PNG maps embedded. images: {"albedo": bytes, "normal": bytes or None, "orm": bytes or None}."""
    import numpy as np
    h = float(tile_metres)                 # half side = one tile, so the swatch shows 2 x 2 tiles
    pos = np.array([[-h, 0, h], [h, 0, h], [h, 0, -h], [-h, 0, -h]], dtype="<f4")
    nor = np.tile(np.array([0, 1, 0], dtype="<f4"), (4, 1))
    tan = np.tile(np.array([1, 0, 0, 1], dtype="<f4"), (4, 1))
    uv = np.array([[0, 2], [2, 2], [2, 0], [0, 0]], dtype="<f4")
    idx = np.array([0, 1, 2, 0, 2, 3], dtype="<u2")
    chunks, views, accs = [], [], []
    off = 0

    def view(b, target=None):
        nonlocal off
        pad = -off % 4
        if pad:
            chunks.append(b"\0" * pad)
            off += pad
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(b)}
        if target:
            v["target"] = target
        views.append(v)
        chunks.append(b)
        off += len(b)
        return len(views) - 1
    vi = [view(pos.tobytes(), 34962), view(nor.tobytes(), 34962), view(tan.tobytes(), 34962), view(uv.tobytes(), 34962), view(idx.tobytes(), 34963)]
    accs += [{"bufferView": vi[0], "componentType": 5126, "count": 4, "type": "VEC3", "min": [float(x) for x in pos.min(0)], "max": [float(x) for x in pos.max(0)]},
             {"bufferView": vi[1], "componentType": 5126, "count": 4, "type": "VEC3"},
             {"bufferView": vi[2], "componentType": 5126, "count": 4, "type": "VEC4"},
             {"bufferView": vi[3], "componentType": 5126, "count": 4, "type": "VEC2"},
             {"bufferView": vi[4], "componentType": 5123, "count": 6, "type": "SCALAR"}]
    imgs, texs, tex_of = [], [], {}
    for key in ("albedo", "normal", "orm"):
        data = images.get(key)
        if data:
            imgs.append({"bufferView": view(data), "mimeType": "image/png", "name": key})
            texs.append({"sampler": 0, "source": len(imgs) - 1})
            tex_of[key] = len(texs) - 1
    pbr = {"metallicFactor": 1.0, "roughnessFactor": 1.0, "baseColorFactor": [1.0, 1.0, 1.0, 1.0]}
    mat = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": True}
    if "albedo" in tex_of:
        pbr["baseColorTexture"] = {"index": tex_of["albedo"]}
    if "orm" in tex_of:
        pbr["metallicRoughnessTexture"] = {"index": tex_of["orm"]}
        mat["occlusionTexture"] = {"index": tex_of["orm"]}
    if "normal" in tex_of:
        mat["normalTexture"] = {"index": tex_of["normal"]}
    doc = {"asset": {"version": "2.0", "generator": GLB_GENERATOR}, "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"name": "material:" + name, "mesh": 0}],
           "meshes": [{"name": "material:" + name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TANGENT": 2, "TEXCOORD_0": 3},
                                                                     "indices": 4, "material": 0, "mode": 4}]}],
           "materials": [mat], "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
           "images": imgs, "textures": texs, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": off}],
           "extras": dict({"units": "metres", "axisConversion": AXIS_NOTE, "swatchTiles": 2, "tileMetres": float(tile_metres)}, **extras)}
    return _pack(doc, chunks)


# ---------------------------------------------------------------- GLB reading
def split_glb(data):
    """(json document, BIN bytes) of a GLB; Failed when the container is malformed."""
    if len(data) < 20 or data[:4] != b"glTF":
        raise Failed("not a GLB file")
    ver, total = struct.unpack("<II", data[4:12])
    if ver != 2 or total != len(data):
        raise Failed("GLB header: version %d, length %d of %d" % (ver, total, len(data)))
    jl, jt = struct.unpack("<I4s", data[12:20])
    if jt != b"JSON" or 20 + jl > len(data):
        raise Failed("GLB has no JSON chunk")
    try:
        doc = json.loads(data[20:20 + jl].decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Failed("the JSON chunk is not valid JSON")
    bn = b""
    if 28 + jl <= len(data):
        bl, bt = struct.unpack("<I4s", data[20 + jl:28 + jl])
        if bt != b"BIN\0" or 28 + jl + bl != len(data):
            raise Failed("GLB has no BIN chunk of the stated length")
        bn = data[28 + jl:28 + jl + bl]
    return doc, bn


def read_glb(data):
    """Parse and validate a GLB written by write_glb (also any plain triangle GLB). Returns {'triangles', 'min', 'max', 'primitives'} in glTF axes."""
    import numpy as np
    if len(data) < 28 or data[:4] != b"glTF":
        raise Failed("not a GLB file")
    doc, bn = split_glb(data)
    bl = len(bn)
    if doc["buffers"][0]["byteLength"] > len(bn):
        raise Failed("GLB buffer is shorter than declared")
    tris, lo, hi = 0, None, None
    for pr in doc["meshes"][0]["primitives"]:
        acc = doc["accessors"][pr["attributes"]["POSITION"]]
        bv = doc["bufferViews"][acc["bufferView"]]
        if acc["componentType"] != 5126 or acc["type"] != "VEC3" or bv["byteOffset"] + acc["count"] * 12 > bl or acc["count"] % 3:
            raise Failed("GLB position accessor is malformed")
        arr = np.frombuffer(bn, dtype="<f4", count=acc["count"] * 3, offset=bv["byteOffset"]).reshape(-1, 3)
        if not np.isfinite(arr).all():
            raise Failed("GLB holds a non-finite coordinate")
        if not (np.allclose(arr.min(axis=0), acc["min"]) and np.allclose(arr.max(axis=0), acc["max"])):
            raise Failed("GLB accessor bounds differ from the data")
        nacc = doc["accessors"][pr["attributes"]["NORMAL"]]
        if nacc["count"] != acc["count"]:
            raise Failed("GLB normals and positions differ in number")
        tris += acc["count"] // 3
        lo = arr.min(axis=0) if lo is None else np.minimum(lo, arr.min(axis=0))
        hi = arr.max(axis=0) if hi is None else np.maximum(hi, arr.max(axis=0))
    return {"triangles": tris, "min": [float(x) for x in lo], "max": [float(x) for x in hi], "primitives": len(doc["meshes"][0]["primitives"])}


_COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def accessor_array(doc, bn, index):
    """The data of accessor `index` as a float64 / int array of shape (count, components). Handles byteStride; sparse accessors are not supported."""
    import numpy as np
    acc = doc["accessors"][index]
    code, size = _COMP[acc["componentType"]]
    n = _NCOMP[acc["type"]]
    count = acc["count"]
    if "bufferView" not in acc:
        return np.zeros((count, n))
    bv = doc["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * size
    if stride == n * size:
        arr = np.frombuffer(bn, dtype="<" + code, count=count * n, offset=start).reshape(count, n)
    else:
        raw = np.frombuffer(bn, dtype=np.uint8, count=(count - 1) * stride + n * size, offset=start)
        arr = np.lib.stride_tricks.as_strided(raw, shape=(count, n * size), strides=(stride, 1)).copy().view("<" + code).reshape(count, n)
    return arr


def node_matrix(node):
    import numpy as np
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    q = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = q
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * np.array(s)[None, :]
    m[:3, 3] = t
    return m


def triangles_of(doc, bn):
    """Every mesh primitive of the default scene as a draw item, in world coordinates converted back to the IFC frame (Z up).

    Returns a list of dicts: node (name), path (names from the root), extras (of the node), tri (Nx3x3 float64), uv (Nx3x2 or None),
    material (the glTF material dict, {} when none), images (decoded PNG bytes by slot) are resolved by the caller from `doc`."""
    import numpy as np
    out = []
    scene = doc["scenes"][doc.get("scene", 0)]

    def walk(i, parent, path):
        node = doc["nodes"][i]
        m = parent @ node_matrix(node)
        p = path + [node.get("name", "")]
        if "mesh" in node:
            for pr in doc["meshes"][node["mesh"]]["primitives"]:
                if pr.get("mode", 4) != 4:
                    continue
                pos = accessor_array(doc, bn, pr["attributes"]["POSITION"]).astype(np.float64)
                if "indices" in pr:
                    idx = accessor_array(doc, bn, pr["indices"]).reshape(-1).astype(np.int64)
                    pos = pos[idx]
                    uv = accessor_array(doc, bn, pr["attributes"]["TEXCOORD_0"]).astype(np.float64)[idx] if "TEXCOORD_0" in pr["attributes"] else None
                else:
                    uv = accessor_array(doc, bn, pr["attributes"]["TEXCOORD_0"]).astype(np.float64) if "TEXCOORD_0" in pr["attributes"] else None
                w = pos @ m[:3, :3].T + m[:3, 3]
                ifc = np.stack([w[:, 0], -w[:, 2], w[:, 1]], axis=1)                 # Y up -> Z up
                mat = doc.get("materials", [])[pr["material"]] if "material" in pr else {}
                out.append({"node": node.get("name", ""), "path": p, "extras": node.get("extras", {}), "tri": ifc.reshape(-1, 3, 3),
                            "uv": uv.reshape(-1, 3, 2) if uv is not None else None, "material": mat})
        for c in node.get("children", []):
            walk(c, m, p)
    for n in scene.get("nodes", []):
        walk(n, np.eye(4), [])
    return out


# ---------------------------------------------------------------- IFC geometry
def part_products(root):
    """The geometry-carrying products of a component root: the root itself, or all parts of an assembly (recursively)."""
    out = []

    def walk(e):
        if getattr(e, "Representation", None) and not e.is_a("IfcElementAssembly") and e.is_a() not in SKIP_CLASSES:
            out.append(e)
        for rel in getattr(e, "IsDecomposedBy", None) or []:
            for c in rel.RelatedObjects:
                walk(c)
    walk(root)
    return out


def shape_parts(model, root, limits):
    """[(rgba, triangle soup Nx3 in the root's own frame)] for a component root, and the root's world matrix (4x4)."""
    import numpy as np
    import ifcopenshell.geom
    import ifcopenshell.util.placement as pl
    settings = ifcopenshell.geom.settings()
    m_root = pl.get_local_placement(root.ObjectPlacement) if root.ObjectPlacement else np.eye(4)
    inv = np.linalg.inv(m_root)
    groups = {}
    ntri = 0
    for p in part_products(root):
        limits.tick()
        try:
            sh = ifcopenshell.geom.create_shape(settings, p)
        except Exception as exc:
            raise Failed("%s %s (%s): geometry could not be built: %s" % (p.is_a(), p.Name, p.GlobalId, str(exc)[:120]))
        g = sh.geometry
        v = np.array(g.verts, dtype=float).reshape(-1, 3)
        f = np.array(g.faces, dtype=int).reshape(-1, 3)
        if not len(f):
            raise Failed("%s %s (%s) has no triangles" % (p.is_a(), p.Name, p.GlobalId))
        m_part = pl.get_local_placement(p.ObjectPlacement) if p.ObjectPlacement else np.eye(4)
        m = inv @ m_part
        v = v @ m[:3, :3].T + m[:3, 3]
        mid = np.array(g.material_ids, dtype=int)
        cols = []
        for mt in g.materials:
            try:
                c = mt.diffuse.components if hasattr(mt.diffuse, "components") else mt.diffuse
                cols.append((r6(min(1.0, max(0.0, c[0]))), r6(min(1.0, max(0.0, c[1]))), r6(min(1.0, max(0.0, c[2]))),
                             r6(1.0 - float(mt.transparency or 0.0))))
            except Exception:
                cols.append((0.8, 0.8, 0.8, 1.0))
        for i in range(len(f)):
            col = cols[mid[i]] if 0 <= mid[i] < len(cols) else (0.8, 0.8, 0.8, 1.0)
            groups.setdefault(col, []).append(v[f[i]])
        ntri += len(f)
        if ntri > MAX_TRIANGLES:
            raise Failed("component %s has more than %d triangles" % (root.Name, MAX_TRIANGLES))
    return [(c, np.array(t, dtype=float).reshape(-1, 3)) for c, t in sorted(groups.items())], m_root


def bounds_info(parts, recentre):
    import numpy as np
    allv = np.concatenate([t for _, t in parts])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    shift = np.zeros(3)
    if recentre:
        shift = np.array([(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2]])
    return lo, hi, shift


def component_geometry(model, root, limits, recentre):
    """The geometry of one component root: dict(parts, lo, hi, shift, m_root, triangles, glb, info). Parts are in the (possibly recentred)
    component frame and rounded to the precision the GLB stores, so the same shape always gives the same bytes."""
    import numpy as np
    parts, m_root = shape_parts(model, root, limits)
    lo, hi, shift = bounds_info(parts, recentre)
    parts = [(c, np.round(t - shift, 6) + 0.0) for c, t in parts]
    lo, hi = lo - shift, hi - shift
    glb = write_glb(parts)
    info = read_glb(glb)
    ntri = sum(len(t) // 3 for _, t in parts)
    if info["triangles"] != ntri:
        raise Failed("GLB check: %d triangles written, %d expected" % (info["triangles"], ntri))
    return {"parts": parts, "lo": lo, "hi": hi, "shift": shift, "m_root": m_root, "triangles": ntri, "glb": glb, "info": info}


def kind_of_class(cls):
    if cls in FURNITURE:
        return "furniture"
    if cls in FIXTURE:
        return "fixture"
    if cls in HARDWARE:
        return "hardware"
    return KIND_OF.get(cls)


def kind_and_category(e, parts):
    cls = e.is_a()
    ot = slugify(getattr(e, "ObjectType", None), "")
    if cls == "IfcElementAssembly":
        kinds = {kind_of_class(p.is_a()) for p in parts}
        kinds.discard(None)
        if len(kinds) != 1:
            return None, None
        k = kinds.pop()
        return k, ot or ("luminaire" if k == "fixture" else k)
    k = kind_of_class(cls)
    if k is None:
        return None, None
    if cls == "IfcCovering":
        return k, COVERING_CATEGORY.get(str(getattr(e, "PredefinedType", "") or ""), "covering")
    return k, ot or slugify(cls[3:])


def master_roots(model):
    """[(root product, geometry products, kind, category)] for every furniture element, covering, fixture or luminaire assembly, hardware
    piece, door and window of an IFC file, in GlobalId order (the components ingest takes from a master file)."""
    out, seen = [], set()
    for e in sorted(model.by_type("IfcProduct"), key=lambda x: x.GlobalId):
        if e.is_a() in SKIP_CLASSES or e.id() in seen:
            continue
        if any(r.RelatingObject.is_a("IfcElementAssembly") for r in (getattr(e, "Decomposes", None) or [])):
            continue                                    # taken as part of its assembly
        parts = part_products(e)
        if not parts:
            continue
        kind, cat = kind_and_category(e, parts)
        if not kind:
            continue
        for p in parts:
            seen.add(p.id())
        out.append((e, parts, kind, cat))
    return out


def exclusion_reason(e):
    """Why a product is a volume and not scenery: "zone" (IfcSpatialZone), "reservation" (IfcBuildingElementProxy of type PROVISIONFORSPACE), or None."""
    if e.is_a("IfcSpatialZone"):
        return "zone"
    if e.is_a("IfcBuildingElementProxy") and str(getattr(e, "PredefinedType", "") or "") == "PROVISIONFORSPACE":
        return "reservation"
    return None


def excluded_volumes(model):
    """The exclusion report: [{globalId, ifcClass, name, predefinedType, reason}] of every volume with a representation, in GlobalId order."""
    out = []
    for e in sorted(model.by_type("IfcProduct"), key=lambda x: x.GlobalId):
        why = exclusion_reason(e)
        if why and getattr(e, "Representation", None):
            out.append({"globalId": e.GlobalId, "ifcClass": e.is_a(), "name": str(e.Name or ""), "predefinedType": str(getattr(e, "PredefinedType", "") or ""), "reason": why})
    return out


def level_of(e):
    """The building storey that holds a product (directly, or through the assembly it is part of), or None."""
    seen = 0
    while e is not None and seen < 20:
        for rel in getattr(e, "ContainedInStructure", None) or []:
            return rel.RelatingStructure
        nxt = None
        for rel in getattr(e, "Decomposes", None) or []:
            if rel.RelatingObject.is_a("IfcBuildingStorey"):
                return rel.RelatingObject
            nxt = rel.RelatingObject
        e, seen = nxt, seen + 1
    return None


def item_root(model, label):
    """The one top-level product of an item IFC file (guide 3); Failed when there is not exactly one."""
    roots = [e for e in model.by_type("IfcProduct") if e.is_a() not in SKIP_CLASSES and getattr(e, "Representation", None)
             and not any(r.RelatingObject.is_a("IfcElementAssembly") for r in (getattr(e, "Decomposes", None) or []))]
    if len(roots) != 1:
        raise Failed("%s must hold exactly one top-level product (found %d)" % (label, len(roots)))
    return roots[0]
