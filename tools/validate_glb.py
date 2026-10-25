#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate GLB (binary glTF 2) files: the glTF structure, and the conventions this set asks of every delivered GLB (rule X-80).

    python3 tools/validate_glb.py PATH [PATH ...] [--profile PROFILE.json] [--ifc MASTER.ifc] [--role auto|model|component|material]
                                  [--khronos auto|on|off] [--json] [--out REPORT.json]

PATH is a GLB file, or a folder searched for *.glb (for a delivery, give deliveries/<slug>/proofs/glb). The structure checks below are
pure Python (numpy, Pillow) and need no network; none is skipped. When the
Khronos glTF Validator (Apache-2.0, npm package `gltf-validator`, pinned in tools/khronos/package-lock.json, install with
`npm ci --prefix tools/khronos`) is present it is run as well and its errors count as REQUIRED failures; `--khronos on` makes its absence an
error, `--khronos off` skips it.

Structure: container (header, chunk order, padding), top-level shape, every index in range, accessors (type, alignment, bounds against the
buffer view, min and max against the data, finite numbers, index range), buffer views, images (embedded PNG or JPEG that decodes),
textures, materials, scene graph (no cycles, one parent, reachable), and nothing unused (buffer, buffer view, accessor, mesh, material,
texture, image, sampler).
Conventions: no `uri` anywhere (external or embedded); `extras.units` is "metres" and the axis conversion is stated; the generator is the
set's; a size along any axis within `proofs.maxExtentMetres`; unit-length normals, unit tangents with w = 1 or -1; node count
(`proofs.maxGlbNodes`), triangle count (`limits.maxTriangles`, and `budgets.recommendedTriangles` as a warning) and file size
(`submission.maxFileBytes`) from the profile; texture sizes in `textures.sizesPixels`; for a whole model: the scene-graph naming
(`model` > `level:<name>` > `<kind>:<name>#<GlobalId>`), the stated bounds equal the data, and with --ifc every product's bounding box equals
the one computed from the IFC file (tolerance 1 mm) in the converted frame, and every product with geometry has a node unless the model's
`extras.excluded` (the exclusion report that `export_glb.py --volumes exclude` writes) lists it; only zones (IfcSpatialZone) and reservation
volumes (IfcBuildingElementProxy of type PROVISIONFORSPACE) may be listed, and a listed product must not have a node.

The report is `check-report/1`; every finding has rule X-80, a `code`, a `location` and a `fix_hint`. Exit codes as in report.py:
0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 nothing could be read.
"""
import argparse
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
import report as rpt  # noqa: E402
from glbkit import Failed  # noqa: E402

VERSION = "2.3.0"
RULE = "X-80"
TOP_KEYS = {"asset", "scene", "scenes", "nodes", "meshes", "materials", "accessors", "bufferViews", "buffers", "images", "textures",
            "samplers", "extras", "extensionsUsed", "extensionsRequired", "extensions", "cameras", "animations", "skins"}
ALLOWED_EXT = {"KHR_texture_transform", "KHR_materials_emissive_strength", "KHR_materials_unlit"}
COMP_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
LEAF_NAME = re.compile(r"^(furniture|covering|fixture|hardware|door|window|structure|terrain|other):[A-Za-z0-9 ._,()+-]{1,80}#[A-Za-z0-9_$]{1,40}$")
GENERATOR = re.compile(r"^authoring-guide-set [a-z0-9 ./-]{1,40}$")
KHRONOS_DIR = os.path.join(HERE, "khronos")


class File:
    """Findings of one GLB."""

    def __init__(self, label, tight=True):
        self.label, self.items, self.codes = label, [], set()

    def bad(self, code, msg, hint, pointer=None, level=None):
        self.codes.add(code)
        status = "fail" if (level or rpt.level_of(RULE)) == "REQUIRED" else "warn"
        if level == "RECOMMENDED":
            status = "warn"
        f = rpt.finding(RULE, status, "%s: %s" % (self.label, msg), element=pointer, file=self.label, level=level, code=code, fix_hint=hint)
        if f:
            self.items.append(f)


def rng(f, doc, name, idx, where, hint="Re-export the file with tools/export_glb.py."):
    arr = doc.get(name)
    if not isinstance(idx, int) or isinstance(idx, bool) or not isinstance(arr, list) or not 0 <= idx < len(arr):
        f.bad("GLB-INDEX", "%s refers to %s[%r], which does not exist" % (where, name, idx), hint, where)
        return False
    return True


def validate_one(data, label, role, item, tex_sizes, params):
    """Validate one GLB. Returns (File, info dict). `params` carries the profile numbers."""
    import numpy as np
    f = File(label)
    info = {"triangles": 0, "nodes": 0, "bounds": None, "role": role}
    # ---- container
    try:
        doc, bn = glbkit.split_glb(data)
    except Failed as exc:
        f.bad("GLB-CONTAINER", str(exc), "A GLB starts with 'glTF', version 2, its own length, a JSON chunk and an optional BIN chunk. Re-export it.")
        return f, info
    jl = struct.unpack("<I", data[12:16])[0]
    if jl % 4 or len(bn) % 4:
        f.bad("GLB-PADDING", "chunk lengths must be multiples of 4 (JSON %d, BIN %d)" % (jl, len(bn)), "Pad the JSON chunk with spaces and the BIN chunk with zeros.")
    if not isinstance(doc, dict):
        f.bad("GLB-JSON", "the JSON chunk is not an object", "Re-export the file.")
        return f, info
    for k in doc:
        if k not in TOP_KEYS:
            f.bad("GLB-TOPLEVEL", "unknown top-level property %r" % k, "Remove it; only glTF 2 properties are allowed.", "/" + k)
    asset = doc.get("asset") if isinstance(doc.get("asset"), dict) else {}
    if asset.get("version") != "2.0":
        f.bad("GLB-VERSION", "asset.version is %r, not '2.0'" % asset.get("version"), "Write glTF 2.0.", "/asset/version")
    gen = asset.get("generator")
    if not isinstance(gen, str) or not GENERATOR.match(gen):
        f.bad("GLB-GENERATOR", "asset.generator %r is not one of the set's tools" % gen, "Export with tools/export_glb.py; a generator string must not name a machine, a user or a path.", "/asset/generator")
    for k in ("scenes", "nodes", "meshes", "materials", "accessors", "bufferViews", "buffers", "images", "textures", "samplers"):
        if k in doc and not (isinstance(doc[k], list) and all(isinstance(x, dict) for x in doc[k])):
            f.bad("GLB-TYPE", "%s must be a list of objects" % k, "Re-export the file.", "/" + k)
            return f, info
    for k in ("extensionsRequired", "extensionsUsed"):
        for x in doc.get(k, []) or []:
            if k == "extensionsRequired":
                f.bad("GLB-EXTENSION", "extension %r is required; a consumer that does not know it cannot open the file" % x, "Remove the extension.", "/extensionsRequired")
            elif x not in ALLOWED_EXT:
                f.bad("GLB-EXTENSION", "extension %r is not one this set allows (%s)" % (x, ", ".join(sorted(ALLOWED_EXT))), "Remove the extension.", "/extensionsUsed")
    # ---- URIs and strings: nothing may point outside the file
    uris = []

    def find_uri(o, p):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "uri":
                    uris.append(p + "/uri")
                find_uri(v, p + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                find_uri(v, "%s/%d" % (p, i))
    find_uri(doc, "")
    for p in uris[:3]:
        f.bad("GLB-URI", "%s: an external or embedded URI; everything must be inside the GLB" % p, "Embed images in the BIN chunk (bufferView + mimeType) and use only the GLB's own buffer.", p)
    # ---- buffers and buffer views
    buffers, views, accs = doc.get("buffers", []), doc.get("bufferViews", []), doc.get("accessors", [])
    if len(buffers) != 1 and (views or accs):
        f.bad("GLB-BUFFER", "expected exactly one buffer (the BIN chunk), found %d" % len(buffers), "Write one buffer.", "/buffers")
    if buffers:
        bl = buffers[0].get("byteLength")
        if not isinstance(bl, int) or bl > len(bn) or len(bn) - bl > 3:
            f.bad("GLB-BUFFER", "buffer 0 byteLength %r does not match the BIN chunk (%d bytes)" % (bl, len(bn)), "Set byteLength to the BIN data length (rounded up to 4 at most).", "/buffers/0/byteLength")
    used_views, used_accs, used_meshes, used_mats, used_tex, used_img, used_samp = set(), set(), set(), set(), set(), set(), set()
    for i, v in enumerate(views):
        w = "/bufferViews/%d" % i
        if v.get("buffer") != 0 or not isinstance(v.get("byteLength"), int) or v["byteLength"] <= 0:
            f.bad("GLB-VIEW", "%s has no valid buffer or byteLength" % w, "Re-export the file.", w)
            continue
        off = v.get("byteOffset", 0)
        if not isinstance(off, int) or off < 0 or off + v["byteLength"] > len(bn):
            f.bad("GLB-VIEW", "%s runs past the end of the buffer" % w, "Re-export the file.", w)
        if "byteStride" in v and (not isinstance(v["byteStride"], int) or not 4 <= v["byteStride"] <= 252 or v["byteStride"] % 4):
            f.bad("GLB-VIEW", "%s byteStride must be a multiple of 4 from 4 to 252" % w, "Fix the stride.", w)
        if v.get("target") not in (None, 34962, 34963):
            f.bad("GLB-VIEW", "%s target %r is not ARRAY_BUFFER or ELEMENT_ARRAY_BUFFER" % (w, v.get("target")), "Fix the target.", w)
    # ---- accessors
    arrays = {}
    for i, a in enumerate(accs):
        w = "/accessors/%d" % i
        ct, tp, cnt = a.get("componentType"), a.get("type"), a.get("count")
        if ct not in COMP_SIZE or tp not in NCOMP or not isinstance(cnt, int) or cnt < 1:
            f.bad("GLB-ACCESSOR", "%s has an invalid componentType, type or count" % w, "Re-export the file.", w)
            continue
        if "sparse" in a:
            f.bad("GLB-ACCESSOR", "%s is sparse; sparse accessors are not allowed" % w, "Write plain accessors.", w)
            continue
        if "bufferView" not in a or not rng(f, doc, "bufferViews", a["bufferView"], w + "/bufferView"):
            f.bad("GLB-ACCESSOR", "%s has no buffer view" % w, "Re-export the file.", w)
            continue
        used_views.add(a["bufferView"])
        v = views[a["bufferView"]]
        size = COMP_SIZE[ct] * NCOMP[tp]
        stride = v.get("byteStride") or size
        start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        if (a.get("byteOffset", 0)) % COMP_SIZE[ct] or start % COMP_SIZE[ct]:
            f.bad("GLB-ACCESSOR", "%s is not aligned to its component size" % w, "Align accessor offsets to 4 bytes.", w)
        end = start + (cnt - 1) * stride + size
        if end > v.get("byteOffset", 0) + v["byteLength"] or end > len(bn):
            f.bad("GLB-ACCESSOR", "%s reads past the end of its buffer view" % w, "Re-export the file.", w)
            continue
        try:
            arr = glbkit.accessor_array(doc, bn, i)
        except Exception:
            f.bad("GLB-ACCESSOR", "%s cannot be read" % w, "Re-export the file.", w)
            continue
        arrays[i] = arr
        if ct == 5126:
            if not np.isfinite(arr).all():
                f.bad("GLB-NONFINITE", "%s holds a NaN or infinite number" % w, "Remove degenerate vertices before export.", w)
        if "min" in a or "max" in a:
            try:
                if not (np.allclose(arr.min(axis=0), a["min"], atol=1e-6) and np.allclose(arr.max(axis=0), a["max"], atol=1e-6)):
                    f.bad("GLB-MINMAX", "%s min/max differ from its data" % w, "Recompute min and max from the data.", w)
            except (KeyError, TypeError, ValueError):
                f.bad("GLB-MINMAX", "%s has a malformed min or max" % w, "Write min and max arrays of the component count.", w)
    # ---- images, textures, samplers, materials
    images, textures, samplers, mats = doc.get("images", []), doc.get("textures", []), doc.get("samplers", []), doc.get("materials", [])
    img_dims = {}
    for i, im in enumerate(images):
        w = "/images/%d" % i
        if not rng(f, doc, "bufferViews", im.get("bufferView"), w + "/bufferView"):
            continue
        used_views.add(im["bufferView"])
        if im.get("mimeType") not in ("image/png", "image/jpeg"):
            f.bad("GLB-IMAGE", "%s mimeType %r is not image/png or image/jpeg" % (w, im.get("mimeType")), "Embed PNG or JPEG only.", w)
            continue
        v = views[im["bufferView"]]
        raw = bn[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
        sig_ok = raw[:8] == b"\x89PNG\r\n\x1a\n" if im["mimeType"] == "image/png" else raw[:3] == b"\xff\xd8\xff"
        if not sig_ok:
            f.bad("GLB-IMAGE", "%s is not what its mimeType says" % w, "Embed a real PNG or JPEG.", w)
            continue
        try:
            import io

            from PIL import Image
            with Image.open(io.BytesIO(raw)) as pil:
                pil.load()
                img_dims[i] = pil.size
        except Exception:
            f.bad("GLB-IMAGE", "%s does not decode" % w, "Embed an image that opens.", w)
            continue
        if len(raw) > params["maxFileBytes"]:
            f.bad("GLB-IMAGE", "%s is %d bytes (limit %d)" % (w, len(raw), params["maxFileBytes"]), "Use a smaller image.", w)
        wd, ht = img_dims[i]
        if tex_sizes and (wd not in tex_sizes or ht not in tex_sizes):
            f.bad("GLB-IMAGE-SIZE", "%s is %d x %d pixels; the profile lists %s" % (w, wd, ht, ", ".join(map(str, tex_sizes))),
                  "Use a texture size from textures.sizesPixels.", w, level="RECOMMENDED")
    for i, t in enumerate(textures):
        w = "/textures/%d" % i
        if rng(f, doc, "images", t.get("source"), w + "/source"):
            used_img.add(t["source"])
        if "sampler" in t and rng(f, doc, "samplers", t["sampler"], w + "/sampler"):
            used_samp.add(t["sampler"])
    for i, s in enumerate(samplers):
        for k, ok in (("magFilter", (9728, 9729)), ("minFilter", (9728, 9729, 9984, 9985, 9986, 9987)), ("wrapS", (33071, 33648, 10497)), ("wrapT", (33071, 33648, 10497))):
            if k in s and s[k] not in ok:
                f.bad("GLB-SAMPLER", "/samplers/%d/%s has the invalid value %r" % (i, k, s[k]), "Use a glTF enum value.", "/samplers/%d" % i)

    def tex_ref(ti, w):
        if isinstance(ti, dict) and rng(f, doc, "textures", ti.get("index"), w + "/index"):
            used_tex.add(ti["index"])
            return ti.get("texCoord", 0)
        return None
    mat_texcoords = {}
    for i, m in enumerate(mats):
        w = "/materials/%d" % i
        pbr = m.get("pbrMetallicRoughness", {})
        if not isinstance(pbr, dict):
            f.bad("GLB-MATERIAL", "%s/pbrMetallicRoughness must be an object" % w, "Re-export the file.", w)
            continue
        for k in ("metallicFactor", "roughnessFactor"):
            if k in pbr and not (isinstance(pbr[k], (int, float)) and 0 <= pbr[k] <= 1):
                f.bad("GLB-MATERIAL", "%s %s must be a number from 0 to 1" % (w, k), "Use 0 to 1.", w)
        bc = pbr.get("baseColorFactor")
        if bc is not None and not (isinstance(bc, list) and len(bc) == 4 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in bc)):
            f.bad("GLB-MATERIAL", "%s baseColorFactor must be four numbers from 0 to 1" % w, "Use RGBA in 0 to 1.", w)
        if m.get("alphaMode", "OPAQUE") not in ("OPAQUE", "MASK", "BLEND"):
            f.bad("GLB-MATERIAL", "%s alphaMode %r is invalid" % (w, m.get("alphaMode")), "Use OPAQUE, MASK or BLEND.", w)
        tcs = []
        for key, ti in (("pbrMetallicRoughness/baseColorTexture", pbr.get("baseColorTexture")), ("pbrMetallicRoughness/metallicRoughnessTexture", pbr.get("metallicRoughnessTexture")),
                        ("normalTexture", m.get("normalTexture")), ("occlusionTexture", m.get("occlusionTexture")), ("emissiveTexture", m.get("emissiveTexture"))):
            if ti is not None:
                tc = tex_ref(ti, "%s/%s" % (w, key))
                if tc is not None:
                    tcs.append((key, tc))
        mat_texcoords[i] = tcs
    # ---- meshes
    meshes = doc.get("meshes", [])
    tri_total, lo, hi = 0, None, None
    prim_by_mesh, mesh_pos = {}, {}
    for mi, mesh in enumerate(meshes):
        for pi, pr in enumerate(mesh.get("primitives", []) or []):
            w = "/meshes/%d/primitives/%d" % (mi, pi)
            if pr.get("mode", 4) != 4:
                f.bad("GLB-PRIMITIVE", "%s mode %r: only triangles (4) are allowed" % (w, pr.get("mode")), "Triangulate.", w)
                continue
            at = pr.get("attributes") or {}
            if "POSITION" not in at or not rng(f, doc, "accessors", at["POSITION"], w + "/attributes/POSITION"):
                f.bad("GLB-PRIMITIVE", "%s has no POSITION" % w, "Write positions.", w)
                continue
            used_accs.add(at["POSITION"])
            pa = accs[at["POSITION"]]
            if pa.get("type") != "VEC3" or pa.get("componentType") != 5126 or "min" not in pa or "max" not in pa:
                f.bad("GLB-PRIMITIVE", "%s POSITION must be float VEC3 with min and max" % w, "Write float positions with min and max.", w)
                continue
            pos = arrays.get(at["POSITION"])
            if pos is None:
                continue
            idx = None
            if "indices" in pr:
                if rng(f, doc, "accessors", pr["indices"], w + "/indices"):
                    used_accs.add(pr["indices"])
                    ia = accs[pr["indices"]]
                    if ia.get("type") != "SCALAR" or ia.get("componentType") not in (5121, 5123, 5125):
                        f.bad("GLB-PRIMITIVE", "%s indices must be unsigned SCALAR" % w, "Use unsigned byte, short or int.", w)
                    else:
                        idx = arrays[pr["indices"]].reshape(-1).astype(np.int64) if pr["indices"] in arrays else None
                        if idx is not None and idx.size and idx.max() >= len(pos):
                            f.bad("GLB-PRIMITIVE", "%s has an index past the last vertex" % w, "Fix the index data.", w)
                            idx = None
            n_ind = idx.size if idx is not None else len(pos)
            if n_ind % 3:
                f.bad("GLB-PRIMITIVE", "%s has %d vertices or indices, not a multiple of 3" % (w, n_ind), "Triangles need 3 each.", w)
                continue
            ntri = n_ind // 3
            tri_total += ntri
            lo = pos.min(axis=0) if lo is None else np.minimum(lo, pos.min(axis=0))
            hi = pos.max(axis=0) if hi is None else np.maximum(hi, pos.max(axis=0))
            mesh_pos.setdefault(mi, []).append(pos)
            # attributes
            for name, acc_i in at.items():
                if not rng(f, doc, "accessors", acc_i, "%s/attributes/%s" % (w, name)):
                    continue
                used_accs.add(acc_i)
                if accs[acc_i].get("count") != len(pos):
                    f.bad("GLB-ATTRIBUTE", "%s attribute %s has %d entries, POSITION has %d" % (w, name, accs[acc_i].get("count"), len(pos)), "All attributes need one entry per vertex.", w)
                if not (name in ("POSITION", "NORMAL", "TANGENT", "COLOR_0", "JOINTS_0", "WEIGHTS_0") or re.fullmatch(r"TEXCOORD_\d", name)):
                    f.bad("GLB-ATTRIBUTE", "%s attribute %s is not one this set uses" % (w, name), "Remove it.", w, level="RECOMMENDED")
            tri = (pos[idx] if idx is not None else pos).reshape(-1, 3, 3)
            geo_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            area2 = np.linalg.norm(geo_n, axis=1)
            degenerate = int((area2 < 1e-12).sum())
            if degenerate:
                f.bad("GLB-DEGENERATE", "%s has %d zero-area triangle(s) of %d" % (w, degenerate, ntri), "Remove zero-area triangles before export.", w,
                      level="RECOMMENDED" if degenerate <= max(1, ntri // 100) else None)
            if "NORMAL" in at and at["NORMAL"] in arrays:
                nrm = arrays[at["NORMAL"]].astype(np.float64)
                if accs[at["NORMAL"]].get("type") != "VEC3" or accs[at["NORMAL"]].get("componentType") != 5126:
                    f.bad("GLB-NORMAL", "%s NORMAL must be float VEC3" % w, "Write float normals.", w)
                else:
                    ln = np.linalg.norm(nrm, axis=1)
                    off = int((np.abs(ln - 1.0) > 1e-3).sum())
                    if off:
                        f.bad("GLB-NORMAL", "%s has %d normal(s) that are not unit length" % (w, off), "Normalise the normals.", w)
                    vn = nrm[idx] if idx is not None else nrm
                    vn = vn.reshape(-1, 3, 3).mean(axis=1)
                    ok_area = area2 >= 1e-12
                    dots = (vn[ok_area] * geo_n[ok_area]).sum(axis=1)
                    flipped = int((dots < 0).sum())
                    if ok_area.any() and flipped > 0.01 * ok_area.sum():
                        f.bad("GLB-NORMAL-FACING", "%s: %d of %d triangles have a normal that points against their winding" % (w, flipped, int(ok_area.sum())),
                              "Make the winding counter-clockwise seen from the normal side.", w)
            mat = pr.get("material")
            if mat is not None and rng(f, doc, "materials", mat, w + "/material"):
                used_mats.add(mat)
                for key, tc in mat_texcoords.get(mat, []):
                    if "TEXCOORD_%d" % tc not in at:
                        f.bad("GLB-TEXCOORD", "%s: material %d uses a texture (%s) but the primitive has no TEXCOORD_%d" % (w, mat, key, tc), "Write UV coordinates.", w)
                if mats[mat].get("normalTexture") is not None:
                    if "TANGENT" not in at:
                        f.bad("GLB-TANGENT", "%s: a normal map is used but there is no TANGENT" % w, "Write tangents so every consumer shades the map the same way.", w,
                              level="RECOMMENDED")
                    elif at["TANGENT"] in arrays:
                        tg = arrays[at["TANGENT"]].astype(np.float64)
                        if accs[at["TANGENT"]].get("type") != "VEC4" or accs[at["TANGENT"]].get("componentType") != 5126:
                            f.bad("GLB-TANGENT", "%s TANGENT must be float VEC4" % w, "Write float tangents.", w)
                        else:
                            if (np.abs(np.linalg.norm(tg[:, :3], axis=1) - 1.0) > 1e-3).any() or (np.abs(np.abs(tg[:, 3]) - 1.0) > 1e-6).any():
                                f.bad("GLB-TANGENT", "%s has tangents that are not unit length or whose w is not 1 or -1" % w, "Normalise tangents; w is the handedness.", w)
                            if "NORMAL" in at and at["NORMAL"] in arrays:
                                dd = np.abs((tg[:, :3] * arrays[at["NORMAL"]]).sum(axis=1))
                                if (dd > 0.05).any():
                                    f.bad("GLB-TANGENT", "%s has tangents that are not perpendicular to their normals" % w, "Orthogonalise tangents against normals.", w)
            else:
                f.bad("GLB-MATERIAL", "%s has no material; consumers would use their own default" % w, "Give every primitive a material.", w, level="RECOMMENDED")
        prim_by_mesh[mi] = len(mesh.get("primitives", []) or [])
        if not mesh.get("primitives"):
            f.bad("GLB-MESH", "/meshes/%d has no primitives" % mi, "Remove the mesh.", "/meshes/%d" % mi)
    info["triangles"] = tri_total
    if lo is not None:
        info["bounds"] = {"min": [float(x) for x in lo], "max": [float(x) for x in hi]}      # glTF axes
    # ---- scene graph
    nodes, scenes = doc.get("nodes", []), doc.get("scenes", [])
    info["nodes"] = len(nodes)
    sc = doc.get("scene")
    if sc is None or not rng(f, doc, "scenes", sc, "/scene"):
        f.bad("GLB-SCENE", "no default scene", "Set `scene` to 0.", "/scene")
        sc_nodes = []
    else:
        sc_nodes = scenes[sc].get("nodes", [])
    parent = {}
    for ni, n in enumerate(nodes):
        w = "/nodes/%d" % ni
        if "mesh" in n and rng(f, doc, "meshes", n["mesh"], w + "/mesh"):
            used_meshes.add(n["mesh"])
        for c in n.get("children", []) or []:
            if rng(f, doc, "nodes", c, w + "/children"):
                if c in parent:
                    f.bad("GLB-NODE", "node %d has two parents" % c, "Each node has at most one parent.", w)
                parent[c] = ni
        if "matrix" in n and ("translation" in n or "rotation" in n or "scale" in n):
            f.bad("GLB-NODE", "%s has both a matrix and translation/rotation/scale" % w, "Use one or the other.", w)
        if "rotation" in n:
            q = n["rotation"]
            if not (isinstance(q, list) and len(q) == 4 and abs(math.sqrt(sum(float(x) ** 2 for x in q)) - 1.0) < 1e-3):
                f.bad("GLB-NODE", "%s rotation is not a unit quaternion" % w, "Normalise the quaternion.", w)
        if "scale" in n and (not isinstance(n["scale"], list) or any(not isinstance(x, (int, float)) or x <= 0 for x in n["scale"])):
            f.bad("GLB-NODE", "%s scale must be positive" % w, "Mirroring and zero scale are not allowed; bake them into the vertices.", w)
    # cycles / reachability
    reach, stack = set(), list(sc_nodes)
    while stack:
        x = stack.pop()
        if not isinstance(x, int) or x in reach or not 0 <= x < len(nodes):
            continue
        reach.add(x)
        stack += [c for c in nodes[x].get("children", []) or [] if isinstance(c, int)]
    for ni in range(len(nodes)):
        seen_up, x = set(), ni
        while x in parent:
            if x in seen_up:
                f.bad("GLB-NODE", "the node graph has a cycle at node %d" % ni, "Remove the cycle.", "/nodes/%d" % ni)
                break
            seen_up.add(x)
            x = parent[x]
    for ni in range(len(nodes)):
        if ni not in reach and not any(ni == r for r in sc_nodes):
            f.bad("GLB-UNUSED", "node %d is not reachable from the scene" % ni, "Remove unused nodes.", "/nodes/%d" % ni)
    for kind, count, used in (("mesh", len(meshes), used_meshes), ("material", len(mats), used_mats), ("texture", len(textures), used_tex),
                              ("image", len(images), used_img), ("sampler", len(samplers), used_samp), ("accessor", len(accs), used_accs),
                              ("bufferView", len(views), used_views)):
        un = sorted(set(range(count)) - used)
        if un:
            f.bad("GLB-UNUSED", "%s %s is not used by anything" % (kind, ", ".join(map(str, un[:5]))), "Remove unused %ss; the file may hold nothing that is not shown." % kind, "/%ss" % kind)
    # ---- the extent and the bounds are those of the scene: every node's transform applied to the mesh it holds
    wb = world_bounds(doc, nodes, sc_nodes, mesh_pos)
    if wb is not None:
        lo, hi = wb
        info["bounds"] = {"min": [float(x) for x in lo], "max": [float(x) for x in hi]}
    # ---- conventions
    ex = doc.get("extras") if isinstance(doc.get("extras"), dict) else {}
    if ex.get("units") != "metres":
        f.bad("GLB-UNITS", "extras.units is %r, not 'metres'" % ex.get("units"), "Export in metres (tools/export_glb.py does).", "/extras/units")
    if "(x,y,z)" not in str(ex.get("axisConversion", "")):
        f.bad("GLB-AXES", "extras.axisConversion does not state the axis conversion", "State the IFC Z-up to glTF Y-up conversion, as export_glb.py does.", "/extras/axisConversion")
    if lo is not None:
        ext = hi - lo
        if (ext > params["maxExtentMetres"]).any() or not np.isfinite(ext).all():
            f.bad("GLB-EXTENT", "the model is %.1f x %.1f x %.1f m; the limit is %d m along any axis (wrong unit?)" % (ext[0], ext[1], ext[2], params["maxExtentMetres"]),
                  "Check that the IFC file is in metres and that nothing stray is far from the building.", "/accessors")
    if len(data) > params["maxFileBytes"]:
        f.bad("GLB-SIZE", "%d bytes (limit %d)" % (len(data), params["maxFileBytes"]), "Reduce geometry or texture size.", None)
    if len(nodes) > params["maxGlbNodes"]:
        f.bad("GLB-NODES", "%d nodes (limit proofs.maxGlbNodes %d)" % (len(nodes), params["maxGlbNodes"]), "Merge small parts.", "/nodes")
    if tri_total > params["maxTriangles"]:
        f.bad("GLB-TRIANGLES", "%d triangles (limit limits.maxTriangles %d)" % (tri_total, params["maxTriangles"]), "Reduce the geometry.", "/meshes")
    elif role != "material" and tri_total > params["recommendedTriangles"]:
        f.bad("GLB-TRIANGLES", "%d triangles (recommended at most %d)" % (tri_total, params["recommendedTriangles"]), "Reduce the geometry.", "/meshes", level="RECOMMENDED")
    if item and tri_total > params["maxItemTriangles"]:
        f.bad("GLB-ITEM-TRIANGLES", "%d triangles for an item (recommended at most budgets.maxItemTriangles = %d)" % (tri_total, params["maxItemTriangles"]),
              "Simplify the item.", "/meshes", level="RECOMMENDED")
    # ---- scene-graph naming (whole models and swatches)
    if role == "model":
        names = [n.get("name") for n in nodes]
        if not sc_nodes or len(sc_nodes) != 1 or nodes[sc_nodes[0]].get("name") != "model":
            f.bad("GLB-NAMES", "the scene must have one root node named 'model'", "Export with tools/export_glb.py.", "/scenes/0")
        else:
            for li in nodes[sc_nodes[0]].get("children", []) or []:
                ln = nodes[li].get("name", "")
                if "mesh" in nodes[li]:
                    if not LEAF_NAME.match(ln or ""):
                        f.bad("GLB-NAMES", "node %r is not named <kind>:<name>#<GlobalId>" % (ln,), "Name leaf nodes as export_glb.py does.", "/nodes/%d" % li)
                    continue
                if not re.match(r"^level:[A-Za-z0-9 ._,()+-]{1,80}$", ln or ""):
                    f.bad("GLB-NAMES", "node %r is not named level:<name>" % (ln,), "Name level nodes level:<name>.", "/nodes/%d" % li)
                for ci in nodes[li].get("children", []) or []:
                    cn = nodes[ci].get("name", "")
                    if not LEAF_NAME.match(cn or "") or "mesh" not in nodes[ci]:
                        f.bad("GLB-NAMES", "node %r is not a mesh node named <kind>:<name>#<GlobalId>" % (cn,), "Name leaf nodes as export_glb.py does.", "/nodes/%d" % ci)
        gids = {}
        for ni, n in enumerate(nodes):
            nm = n.get("name") or ""
            if "mesh" not in n or "#" not in nm or not LEAF_NAME.match(nm):
                continue
            gid_name = nm.rsplit("#", 1)[1]
            ex_n = n.get("extras") if isinstance(n.get("extras"), dict) else {}
            if ex_n.get("globalId") != gid_name:
                f.bad("GLB-IDENT", "node %r: extras.globalId is %r, the GlobalId in its name is %r" % (nm, ex_n.get("globalId"), gid_name),
                      "Write the product's GlobalId into the node name and into extras.globalId.", "/nodes/%d" % ni, level="RECOMMENDED")
            gids.setdefault(gid_name, []).append(nm)
        for gid_name, lst in sorted(gids.items()):
            if len(lst) > 1:
                f.bad("GLB-IDENT", "GlobalId %s is on %d nodes (%s ...)" % (gid_name, len(lst), lst[0]), "One node per product.", "/nodes", level="RECOMMENDED")
        dup = {x for x in names if x and names.count(x) > 1}
        if dup:
            f.bad("GLB-NAMES", "node name %r is used more than once" % sorted(dup)[0], "Names include the GlobalId, so they are unique.", "/nodes")
        if "excluded" in ex:
            lst = ex["excluded"]
            if not (isinstance(lst, list) and all(isinstance(x, dict) and isinstance(x.get("globalId"), str) and x.get("reason") in glbkit.VOLUME_REASONS for x in lst)):
                f.bad("GLB-EXTRAS", "extras.excluded must be a list of {globalId, ifcClass, name, predefinedType, reason} with reason zone or reservation",
                      "Export with tools/export_glb.py --volumes exclude.", "/extras/excluded")
            elif len({x["globalId"] for x in lst}) != len(lst):
                f.bad("GLB-EXTRAS", "extras.excluded lists a GlobalId twice", "Export with tools/export_glb.py --volumes exclude.", "/extras/excluded")
        for k in ("levels", "rooms", "bounds", "source"):
            if k not in ex:
                f.bad("GLB-EXTRAS", "extras.%s is missing; the render tools and the checks need it" % k, "Export with tools/export_glb.py.", "/extras/" + k)
        if lo is not None and isinstance(ex.get("bounds"), dict):
            ifc_lo = [float(lo[0]), float(-hi[2]), float(lo[1])]
            ifc_hi = [float(hi[0]), float(-lo[2]), float(hi[1])]
            if not (np.allclose(ifc_lo, ex["bounds"].get("min", []), atol=1e-4) and np.allclose(ifc_hi, ex["bounds"].get("max", []), atol=1e-4)):
                f.bad("GLB-BOUNDS", "extras.bounds differ from the geometry after the axis conversion", "Re-export; the bounds are computed from the data.", "/extras/bounds")
    elif role == "material":
        if not images:
            f.bad("GLB-NAMES", "a material swatch holds no images", "Export with tools/export_glb.py.", "/images")
        if not (len(nodes) == 1 and re.match(r"^material:[A-Za-z0-9 ._,()+-]{1,60}$", nodes[0].get("name", ""))):
            f.bad("GLB-NAMES", "a material swatch has one node named material:<name>", "Export with tools/export_glb.py.", "/nodes")
    return f, info


def world_bounds(doc, nodes, sc_nodes, mesh_pos):
    """(min, max) in glTF axes of everything the default scene draws, with the transform of every node on the path applied (translation, rotation, scale
    or matrix) to the vertices of its mesh. A mesh used by several nodes counts once for each. None when the graph or a transform cannot be read
    (the other checks name that), or when no node draws anything."""
    import numpy as np
    lo = hi = None
    seen = set()
    stack = [(i, np.eye(4)) for i in sc_nodes if isinstance(i, int) and 0 <= i < len(nodes)]
    try:
        while stack:
            i, parent = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            node = nodes[i]
            m = parent @ glbkit.node_matrix(node)
            for pos in mesh_pos.get(node.get("mesh"), []) if isinstance(node.get("mesh"), int) else []:
                w = pos @ m[:3, :3].T + m[:3, 3]
                lo = w.min(axis=0) if lo is None else np.minimum(lo, w.min(axis=0))
                hi = w.max(axis=0) if hi is None else np.maximum(hi, w.max(axis=0))
            for c in node.get("children", []) or []:
                if isinstance(c, int) and 0 <= c < len(nodes):
                    stack.append((c, m))
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    return None if lo is None else (lo, hi)


def ifc_bounds_problems(glb_data, ifc_path):
    """Compare the bounding box of every product node with the one computed from the IFC file (world coordinates). Returns [message]."""
    import numpy as np
    import ifcopenshell
    import ifcopenshell.geom
    doc, bn = glbkit.split_glb(glb_data)
    model = ifcopenshell.open(ifc_path)
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    items = {}
    excluded = excluded_of(doc)
    for it in glbkit.triangles_of(doc, bn):
        gid = (it.get("extras") or {}).get("globalId")
        if gid:
            t = it["tri"].reshape(-1, 3)
            lo, hi = t.min(axis=0), t.max(axis=0)
            if gid in items:
                lo, hi = np.minimum(lo, items[gid][0]), np.maximum(hi, items[gid][1])
            items[gid] = (lo, hi)
    msgs, checked = [], 0
    for gid, x in sorted(excluded.items()):
        e = model.by_guid(gid)
        if e is None:
            msgs.append("excluded product %s is not a product of the IFC file" % gid)
        elif glbkit.exclusion_reason(e) is None:
            msgs.append("%s %s is listed as excluded, but only a zone or a reservation volume (PROVISIONFORSPACE) may be left out" % (e.is_a(), gid))
        elif glbkit.exclusion_reason(e) != x.get("reason"):
            msgs.append("excluded product %s is a %s volume, the list says %r" % (gid, glbkit.exclusion_reason(e), x.get("reason")))
        if gid in items:
            msgs.append("%s is listed as excluded but has a node in the GLB" % gid)
    for gid, (glo, ghi) in sorted(items.items()):
        e = model.by_guid(gid) if gid else None
        if e is None:
            msgs.append("node %s is not a product of the IFC file" % gid)
            continue
        los, his = [], []
        prods = glbkit.part_products(e) if e.is_a() != "IfcGeographicElement" else [e]
        for p in prods:
            try:
                g = ifcopenshell.geom.create_shape(st, p).geometry
            except Exception:
                msgs.append("%s: geometry of the IFC product could not be built" % gid)
                break
            v = np.array(g.verts, dtype=float).reshape(-1, 3)
            los.append(v.min(axis=0))
            his.append(v.max(axis=0))
        else:
            ilo, ihi = np.min(los, axis=0), np.max(his, axis=0)
            checked += 1
            if not (np.allclose(ilo, glo, atol=1e-3) and np.allclose(ihi, ghi, atol=1e-3)):
                msgs.append("%s: GLB box %s..%s differs from IFC box %s..%s" % (gid, np.round(glo, 3).tolist(), np.round(ghi, 3).tolist(),
                                                                           np.round(ilo, 3).tolist(), np.round(ihi, 3).tolist()))
    ids = {e.GlobalId for e in model.by_type("IfcProduct") if getattr(e, "Representation", None) and e.is_a() not in glbkit.SKIP_CLASSES and
           not any(r.RelatingObject.is_a("IfcElementAssembly") for r in (getattr(e, "Decomposes", None) or []))}
    missing = sorted(i for i in ids - set(items) - set(excluded))
    for gid in missing[:3]:
        msgs.append("%s is a product of the IFC file with geometry but has no node in the GLB (and is not on extras.excluded)" % gid)
    if len(missing) > 3:
        msgs.append("%d more products of the IFC file with geometry have no node in the GLB" % (len(missing) - 3))
    return msgs, checked


def excluded_of(doc):
    """{GlobalId: entry} of the exclusion report in extras.excluded of a whole-model GLB ({} when there is none)."""
    ex = doc.get("extras") if isinstance(doc.get("extras"), dict) else {}
    lst = ex.get("excluded")
    if not isinstance(lst, list):
        return {}
    return {x["globalId"]: x for x in lst if isinstance(x, dict) and isinstance(x.get("globalId"), str)}


def khronos(paths):
    """Run the Khronos validator on files; returns (version or None, {path: report}) ; (None, {}) when it is not installed."""
    node = shutil.which("node")
    if not node or not os.path.isdir(os.path.join(KHRONOS_DIR, "node_modules", "gltf-validator")):
        return None, {}
    p = subprocess.run([node, os.path.join(KHRONOS_DIR, "validate.mjs"), *paths], capture_output=True, text=True, timeout=600)
    if p.returncode:
        return None, {}
    res = json.loads(p.stdout)
    return (res[0]["version"] if res else None), {r["file"]: r for r in res}


def profile_params():
    return {"maxFileBytes": rpt.param("submission.maxFileBytes", 26214400), "maxGlbNodes": rpt.param("proofs.maxGlbNodes", 20000),
            "maxExtentMetres": rpt.param("proofs.maxExtentMetres", 5000), "maxTriangles": rpt.param("limits.maxTriangles", 5000000),
            "recommendedTriangles": rpt.param("budgets.recommendedTriangles", 1000000), "maxItemTriangles": rpt.param("budgets.maxItemTriangles", 2000)}


def validate_files(specs, ifc=None, use_khronos="auto"):
    """specs: list of dicts {path, label, role (auto|model|component|material), item (bool), ifc (path or None)}.
    Returns the check-report/1 dict (no timestamps, no absolute paths)."""
    params, sizes = profile_params(), rpt.param("textures.sizesPixels", [])
    findings, files = [], []
    kv, kreports = (None, {})
    if use_khronos != "off":
        kv, kreports = khronos([s["path"] for s in specs])
        if use_khronos == "on" and kv is None:
            return rpt.make_report("validate_glb.py", VERSION, {"path": "glb"}, [], error="--khronos on, but the Khronos validator is not installed (npm ci --prefix tools/khronos)")
    for s in specs:
        with open(s["path"], "rb") as fh:
            data = fh.read()
        role = s.get("role", "auto")
        if role == "auto":
            try:
                ex = glbkit.split_glb(data)[0].get("extras", {})
            except Failed:
                ex = {}
            role = "model" if "levels" in ex else ("material" if "swatchTiles" in ex else "component")
        f, info = validate_one(data, s["label"], role, bool(s.get("item")), sizes, params)
        entry = {"path": s["label"], "role": role, "sha256": glbkit.sha256_bytes(data), "bytes": len(data), "triangles": info["triangles"], "nodes": info["nodes"]}
        if info["bounds"]:
            lo, hi = info["bounds"]["min"], info["bounds"]["max"]
            entry["boundsIfcFrame"] = {"min": [round(lo[0], 6), round(-hi[2], 6), round(lo[1], 6)], "max": [round(hi[0], 6), round(-lo[2], 6), round(hi[1], 6)]}
        ifc_path = s.get("ifc") or (ifc if role == "model" else None)
        if ifc_path and role == "model" and not f.codes & {"GLB-CONTAINER"}:
            try:
                msgs, checked = ifc_bounds_problems(data, ifc_path)
            except Exception as exc:
                msgs, checked = ["could not compare with the IFC file: %s" % str(exc)[:120]], 0
            for m in msgs[:5]:
                f.bad("GLB-BBOX-IFC", m, "Re-export from the delivered IFC file with tools/export_glb.py.")
            entry["ifcBoundsCompared"] = checked
            n_excl = len(excluded_of(glbkit.split_glb(data)[0]))
            if n_excl:
                entry["ifcExcluded"] = n_excl
        if kv is not None:
            kr = kreports.get(s["path"])
            if kr:
                entry["khronos"] = {"errors": kr["errors"], "warnings": kr["warnings"], "infos": kr["infos"], "hints": kr["hints"]}
                for m in kr["messages"]:
                    if m["severity"] == 0:
                        f.bad("KHRONOS-" + m["code"], "Khronos validator: %s at %s" % (m["message"], m["pointer"] or "/"), "Fix what the Khronos validator names; see its message code.", m["pointer"] or None)
                    elif m["severity"] == 1:
                        f.bad("KHRONOS-" + m["code"], "Khronos validator warning: %s at %s" % (m["message"], m["pointer"] or "/"), "Fix what the Khronos validator names.", m["pointer"] or None, level="RECOMMENDED")
        if not f.items:
            findings.append(rpt.finding(RULE, "pass", "%s: valid %s GLB (%d triangles, %d nodes)" % (s["label"], role, info["triangles"], info["nodes"]), file=s["label"]))
        findings += f.items
        files.append(entry)
    extra = {"files": files, "khronos": {"used": kv is not None, "version": kv} if kv is not None else {"used": False}}
    return rpt.make_report("validate_glb.py", VERSION, {"path": "glb"}, findings, counts={"files": len(files)}, extra=extra)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--profile")
    ap.add_argument("--ifc", help="master IFC file to compare the whole model's bounding boxes with")
    ap.add_argument("--role", default="auto", choices=["auto", "model", "component", "material"])
    ap.add_argument("--khronos", default="auto", choices=["auto", "on", "off"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    specs = []
    for p in a.paths:
        if os.path.isdir(p):
            for base, dirs, names in os.walk(p):
                dirs.sort()
                for n in sorted(names):
                    if n.endswith(".glb"):
                        full = os.path.join(base, n)
                        specs.append({"path": full, "label": os.path.relpath(full, p).replace(os.sep, "/"), "role": a.role})
        elif os.path.isfile(p):
            specs.append({"path": p, "label": os.path.basename(p), "role": a.role})
        else:
            print("ERROR not found: %s" % p, file=sys.stderr)
            sys.exit(3)
    if not specs:
        rep = rpt.make_report("validate_glb.py", VERSION, {"path": a.paths[0]}, [], error="no .glb files found")
    else:
        rep = validate_files(specs, a.ifc, a.khronos)
    if a.out:
        rpt.write(rep, a.out)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        s = rep["summary"]
        print("glb: %s (%d file(s), %d REQUIRED failure(s), %d RECOMMENDED warning(s))" % (rep["result"].upper(), len(rep.get("files", [])), s["requiredFailures"], s["recommendedWarnings"]))
        if rep.get("error"):
            print("ERROR " + rep["error"])
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
