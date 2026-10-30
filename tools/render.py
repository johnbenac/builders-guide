#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Headless, deterministic renders of GLB files: the standard proof set of a delivery.

    python3 tools/render.py GLB_DIR --out OUT_DIR [--index INDEX.json] [--scale 1.0] [--json]
    python3 tools/render.py MODEL.glb --out OUT_DIR           (plans, interiors and exteriors of one whole-model GLB)

GLB_DIR is the folder tools/export_glb.py wrote (model.glb, components/, materials/). For `model.glb` it renders
  plan-<n>-<level>.png        orthographic plan of each level, looking straight down, everything above 1.2 m over the floor cut away
  room-<id>-<k>.png           `proofs.interiorViewsPerRoom` perspective views per room (at most `proofs.maxRoomsPerKind` rooms of each room
                              kind, where kind is the room's Function property): camera 1.6 m above the floor (at most 60 % of the room
                              height) at the point of the room's footprint nearest each corner of its bounding box, looking at the
                              footprint's centre at 1.0 m
  exterior-<k>.png            `proofs.exteriorViews` orthographic views from evenly spaced directions, 28 degrees above the horizon
and for every other GLB a contact sheet sheet-<glb name>.png of `proofs.turntableFrames` orthographic turntable frames (a texture swatch
gets four fixed frames), 320 x 320 pixels each, 4 per row.

Why this renderer: it is a plain software rasteriser written with numpy (about 400 lines, in this file). It needs no GPU, display, browser
or system library, so it behaves the same on a laptop, a build server and a GitHub-hosted runner; on one toolchain the same GLB gives the
same bytes. It draws flat-shaded triangles with a z-buffer, 2 x 2 supersampled; it applies base colour factors and the base colour texture
(bilinear, repeating); it does not draw normal maps, metal or roughness, shadows or reflections. See guide 4, section 8.1.

Conventions (recorded for every picture in proofs/manifest.json): world frame Z up (the GLB is converted back from Y up); +X right and
+Y up on plans; light: key from the direction (0.35, -0.5, 0.8) and fill from (-0.6, 0.4, 0.3), both normalised, with
shade = 0.30 + 0.12 * (0.5 + 0.5 * n_z) + 0.55 * max(0, n . key) + 0.20 * max(0, n . fill), at most 1, and the normal turned towards the
viewer; colours are used as stored (no gamma); in plans the inside of a cut solid (its back faces) is filled dark grey (a section); translucent surfaces are blended over the opaque picture, back to front; background (236, 238,
240) for views and white for plans. A picture holds only image chunks (no text, no time, no profile). Sizes: plans 1280 x 960, views 1280 x 720,
sheets 1280 wide, all multiplied by --scale (the profile's proofs.minRenderWidth and maxRenderPixels bound them).

Exit codes: 0 written, 2 wrong command line, 3 an input could not be read. Requires numpy, Pillow and shapely (tools/requirements.txt).
"""
import argparse
import io
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
import report as rpt  # noqa: E402

VERSION = "2.5.0"
BACKEND = "numpy-rasteriser/1"
SS = 2
KEY = np.array([0.35, -0.5, 0.8]) / np.linalg.norm([0.35, -0.5, 0.8])
FILL = np.array([-0.6, 0.4, 0.3]) / np.linalg.norm([-0.6, 0.4, 0.3])
LIGHT = {"model": "flat-lambert/1", "keyDirection": [round(float(x), 6) for x in KEY], "fillDirection": [round(float(x), 6) for x in FILL],
         "shade": "0.30 + 0.12*(0.5+0.5*nz) + 0.55*max(0,n.key) + 0.20*max(0,n.fill), at most 1"}
BG_VIEW, BG_PLAN = (236, 238, 240), (255, 255, 255)
SECTION = (0.16, 0.16, 0.18)
PLAN_SIZE, VIEW_SIZE, CELL = (1280, 960), (1280, 720), 320
CUT_HEIGHT = 1.2
SWATCH_FRAMES = [(0, 90), (0, 35), (120, 35), (240, 35)]


# ---------------------------------------------------------------- scene
class Scene:
    """All triangles of a GLB in the IFC frame (Z up), one row per triangle."""

    def __init__(self, data):
        doc, bn = glbkit.split_glb(data)
        self.doc, self.extras = doc, doc.get("extras", {}) if isinstance(doc.get("extras"), dict) else {}
        items = glbkit.triangles_of(doc, bn)
        self.textures = []
        tex_index = {}
        P, UV, COL, TEX, LV, KIND = [], [], [], [], [], []
        for it in items:
            t = it["tri"]
            m = it["material"] or {}
            pbr = m.get("pbrMetallicRoughness", {})
            col = list(pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1.0]))
            tex = -1
            bt = pbr.get("baseColorTexture")
            if bt is not None and it["uv"] is not None:
                ti = bt["index"]
                if ti not in tex_index:
                    tex_index[ti] = len(self.textures)
                    self.textures.append(self._decode(doc, bn, ti))
                tex = tex_index[ti]
            n = len(t)
            P.append(t)
            UV.append(it["uv"] if it["uv"] is not None else np.zeros((n, 3, 2)))
            COL.append(np.tile(np.array(col, dtype=np.float64), (n, 1)))
            TEX.append(np.full(n, tex, dtype=np.int64))
            ex = it["extras"] if isinstance(it["extras"], dict) else {}
            path = it["path"]
            LV.append(np.full(n, next((p[6:] for p in path if p.startswith("level:")), ""), dtype=object))
            KIND.append(np.full(n, ex.get("kind", ""), dtype=object))
        if not P:
            raise glbkit.Failed("the GLB holds no triangles")
        self.P, self.UV, self.COL = np.concatenate(P), np.concatenate(UV), np.concatenate(COL)
        self.TEX, self.LV, self.KIND = np.concatenate(TEX), np.concatenate(LV), np.concatenate(KIND)
        e1, e2 = self.P[:, 1] - self.P[:, 0], self.P[:, 2] - self.P[:, 0]
        n = np.cross(e1, e2)
        ln = np.linalg.norm(n, axis=1)
        self.N = n / np.where(ln > 1e-15, ln, 1.0)[:, None]
        self.valid = ln > 1e-15

    @staticmethod
    def _decode(doc, bn, ti):
        from PIL import Image
        im = doc["images"][doc["textures"][ti]["source"]]
        v = doc["bufferViews"][im["bufferView"]]
        raw = bn[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
        with Image.open(io.BytesIO(raw)) as pil:
            return np.asarray(pil.convert("RGB"), dtype=np.float64) / 255.0

    def bounds(self, mask=None):
        P = self.P if mask is None else self.P[mask]
        return P.reshape(-1, 3).min(axis=0), P.reshape(-1, 3).max(axis=0)


# ---------------------------------------------------------------- geometry
def clip_tris(V, D):
    """Clip triangles to the half-space D >= 0. V: (N,3,K) vertex attributes, D: (N,3) signed distances. Returns (V', parent index)."""
    inside = D >= 0
    cnt = inside.sum(axis=1)
    outs, par = [V[cnt == 3]], [np.nonzero(cnt == 3)[0]]
    m = cnt == 1
    if m.any():
        Vm, Dm, Im, ix = V[m], D[m], inside[m], np.nonzero(m)[0]
        rot = (Im.argmax(axis=1)[:, None] + np.arange(3)) % 3
        Vr = np.take_along_axis(Vm, rot[:, :, None], 1)
        Dr = np.take_along_axis(Dm, rot, 1)
        t1 = (Dr[:, 0] / (Dr[:, 0] - Dr[:, 1]))[:, None]
        t2 = (Dr[:, 0] / (Dr[:, 0] - Dr[:, 2]))[:, None]
        outs.append(np.stack([Vr[:, 0], Vr[:, 0] + (Vr[:, 1] - Vr[:, 0]) * t1, Vr[:, 0] + (Vr[:, 2] - Vr[:, 0]) * t2], axis=1))
        par.append(ix)
    m = cnt == 2
    if m.any():
        Vm, Dm, Im, ix = V[m], D[m], inside[m], np.nonzero(m)[0]
        rot = ((~Im).argmax(axis=1)[:, None] + np.arange(3)) % 3
        Vr = np.take_along_axis(Vm, rot[:, :, None], 1)
        Dr = np.take_along_axis(Dm, rot, 1)
        c, a, b = Vr[:, 0], Vr[:, 1], Vr[:, 2]
        ta = (Dr[:, 0] / (Dr[:, 0] - Dr[:, 1]))[:, None]
        tb = (Dr[:, 0] / (Dr[:, 0] - Dr[:, 2]))[:, None]
        ca, cb = c + (a - c) * ta, c + (b - c) * tb
        outs += [np.stack([a, b, cb], axis=1), np.stack([a, cb, ca], axis=1)]
        par += [ix, ix]
    return np.concatenate(outs), np.concatenate(par)


def look_at(eye, target, up=(0.0, 0.0, 1.0)):
    eye, target, up = (np.asarray(x, dtype=np.float64) for x in (eye, target, up))
    f = target - eye
    f = f / np.linalg.norm(f)
    r = np.cross(f, up)
    if np.linalg.norm(r) < 1e-9:                       # looking straight up or down: use +Y as the up direction on screen
        r = np.cross(f, np.array([0.0, 1.0, 0.0]))
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, f, r, u


def sample_texture(tex, uv):
    h, w = tex.shape[:2]
    x = (uv[:, 0] % 1.0) * w - 0.5
    y = (uv[:, 1] % 1.0) * h - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, x1, y0, y1 = x0 % w, (x0 + 1) % w, y0 % h, (y0 + 1) % h
    return (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x1] * fx * (1 - fy) + tex[y1, x0] * (1 - fx) * fy + tex[y1, x1] * fx * fy)


def draw(scene, mask, cam, size, background, clip_z=None, section=False):
    """Draw the triangles selected by `mask` and return an (H, W, 3) uint8 picture. cam: dict(projection, eye, target, up, halfHeight | fov)."""
    W, H = size
    w2, h2 = W * SS, H * SS
    idx = np.nonzero(mask & scene.valid)[0]
    eye, f, r, u = look_at(cam["eye"], cam["target"], cam.get("up", (0, 0, 1)))
    P = scene.P[idx]
    UV = scene.UV[idx]
    N = scene.N[idx]
    parent = idx
    V = np.concatenate([P, UV], axis=2)                       # (N,3,5): world xyz, uv
    if clip_z is not None:
        V, p = clip_tris(V, clip_z - V[:, :, 2])
        parent = parent[p]
        N = N[p]
    rel = V[:, :, :3] - eye
    cx, cy, cd = rel @ r, rel @ u, rel @ f
    persp = cam["projection"] == "perspective"
    if persp:
        near = cam.get("near", 0.05)
        C = np.stack([cx, cy, cd, V[:, :, 3], V[:, :, 4]], axis=2)
        C, p = clip_tris(C, cd - near)
        parent, N = parent[p], N[p]
        cx, cy, cd = C[:, :, 0], C[:, :, 1], C[:, :, 2]
        UVc = C[:, :, 3:5]
        fpx = (h2 / 2.0) / math.tan(math.radians(cam["fov"]) / 2.0)
        sx = cx / cd * fpx + w2 / 2.0
        sy = h2 / 2.0 - cy / cd * fpx
        invd = 1.0 / cd
    else:
        UVc = V[:, :, 3:5]
        k = (h2 / 2.0) / cam["halfHeight"]
        sx = cx * k + w2 / 2.0
        sy = h2 / 2.0 - cy * k
        invd = None
    depth = cd
    # shading from the geometric normal turned towards the viewer
    cen = eye + (cx.mean(axis=1)[:, None] * r + cy.mean(axis=1)[:, None] * u + cd.mean(axis=1)[:, None] * f)
    towards = (eye - cen) if persp else -f[None, :]
    flip = (N * towards).sum(axis=1) < 0
    Ns = np.where(flip[:, None], -N, N)
    shade = 0.30 + 0.12 * (0.5 + 0.5 * Ns[:, 2]) + 0.55 * np.maximum(0, Ns @ KEY) + 0.20 * np.maximum(0, Ns @ FILL)
    shade = np.minimum(shade, 1.0)
    col = scene.COL[parent].copy()
    tex = scene.TEX[parent].copy()
    if section:                # looking into a solid that was cut open shows its back faces: fill them with the section colour, a little nearer
        back = flip
        col[back, :3] = SECTION
        col[back, 3] = 1.0
        shade[back] = 1.0
        tex[back] = -1
        depth = depth.copy()
        depth[back] -= 0.002
    # cull what is off screen or has no area
    minx, maxx, miny, maxy = sx.min(1), sx.max(1), sy.min(1), sy.max(1)
    area = (sx[:, 1] - sx[:, 0]) * (sy[:, 2] - sy[:, 0]) - (sx[:, 2] - sx[:, 0]) * (sy[:, 1] - sy[:, 0])
    ok = (maxx >= 0) & (minx <= w2) & (maxy >= 0) & (miny <= h2) & (np.abs(area) > 1e-9)
    order = np.nonzero(ok)[0]
    zbuf = np.full((h2, w2), np.inf)
    img = np.empty((h2, w2, 3))
    img[:] = np.array(background, dtype=np.float64) / 255.0
    opaque = [i for i in order if col[i, 3] >= 0.999]
    trans = [i for i in order if col[i, 3] < 0.999]
    trans.sort(key=lambda i: -float(depth[i].mean()))

    def raster(i, blend):
        x0, x1, x2 = sx[i]
        y0, y1, y2 = sy[i]
        ix0, ix1 = max(int(math.ceil(min(x0, x1, x2) - 0.5)), 0), min(int(math.floor(max(x0, x1, x2) - 0.5)), w2 - 1)
        iy0, iy1 = max(int(math.ceil(min(y0, y1, y2) - 0.5)), 0), min(int(math.floor(max(y0, y1, y2) - 0.5)), h2 - 1)
        if ix1 < ix0 or iy1 < iy0:
            return
        px = (np.arange(ix0, ix1 + 1) + 0.5)[None, :]
        py = (np.arange(iy0, iy1 + 1) + 0.5)[:, None]
        a = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        l0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / a
        l1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / a
        l2 = 1.0 - l0 - l1
        inside = (l0 >= -1e-9) & (l1 >= -1e-9) & (l2 >= -1e-9)
        if not inside.any():
            return
        if persp:
            iv = l0 * invd[i, 0] + l1 * invd[i, 1] + l2 * invd[i, 2]
            z = 1.0 / iv
        else:
            z = l0 * depth[i, 0] + l1 * depth[i, 1] + l2 * depth[i, 2]
        zc = zbuf[iy0:iy1 + 1, ix0:ix1 + 1]
        vis = inside & (z < zc)
        if not vis.any():
            return
        base = np.broadcast_to(col[i, :3], (int(vis.sum()), 3)).astype(np.float64)
        if tex[i] >= 0:
            if persp:
                uvp = (l0[..., None] * UVc[i, 0] * invd[i, 0] + l1[..., None] * UVc[i, 1] * invd[i, 1] + l2[..., None] * UVc[i, 2] * invd[i, 2]) / iv[..., None]
            else:
                uvp = l0[..., None] * UVc[i, 0] + l1[..., None] * UVc[i, 1] + l2[..., None] * UVc[i, 2]
            base = base * sample_texture(scene.textures[tex[i]], uvp[vis])
        rgb = base * shade[i]
        dst = img[iy0:iy1 + 1, ix0:ix1 + 1]
        if blend:
            al = col[i, 3]
            dst[vis] = rgb * al + dst[vis] * (1 - al)
        else:
            dst[vis] = rgb
            zc[vis] = z[vis]
    for i in opaque:
        raster(i, False)
    for i in trans:
        raster(i, True)
    small = img.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    return np.clip(np.floor(small * 255.0 + 0.5), 0, 255).astype(np.uint8)


def png_bytes(arr):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="PNG", compress_level=9, optimize=False)
    return buf.getvalue()


def fit_ortho(scene, mask, eye_dir, up, size, margin=1.06):
    """An orthographic camera looking along -eye_dir at the centre of the selected triangles' box, fitting it."""
    lo, hi = scene.bounds(mask)
    c = (lo + hi) / 2.0
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    d = np.asarray(eye_dir, dtype=np.float64)
    d = d / np.linalg.norm(d)
    radius = np.linalg.norm(hi - lo) / 2.0
    eye, f, r, u = look_at(c + d * (radius * 3.0 + 1.0), c, up)
    pr, pu = (corners - c) @ r, (corners - c) @ u
    aspect = size[0] / size[1]
    half = max(np.abs(pu).max(), np.abs(pr).max() / aspect, 0.05) * margin
    return {"projection": "orthographic", "eye": eye, "target": c, "up": up, "halfHeight": float(half)}


def cam_record(cam):
    rec = {"projection": cam["projection"], "eye": [round(float(x), 4) for x in cam["eye"]], "target": [round(float(x), 4) for x in cam["target"]],
           "up": [float(x) for x in cam.get("up", (0, 0, 1))]}
    if cam["projection"] == "orthographic":
        rec["halfHeightMetres"] = round(cam["halfHeight"], 4)
    else:
        rec["verticalFovDegrees"] = cam["fov"]
        rec["nearMetres"] = cam.get("near", 0.05)
    return rec


def slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:n] or "x"


# ---------------------------------------------------------------- the standard set
def render_model(data, scale, out, glb_sha, glb_rel, params):
    """Plans, interiors and exteriors of a whole-model GLB. Appends records (dicts with `png` bytes) to `out`."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points
    sc = Scene(data)
    ex = sc.extras
    plan_size = (int(round(PLAN_SIZE[0] * scale)), int(round(PLAN_SIZE[1] * scale)))
    view_size = (int(round(VIEW_SIZE[0] * scale)), int(round(VIEW_SIZE[1] * scale)))
    levels = ex.get("levels", [])
    outdoor = np.isin(sc.KIND, ["terrain"])
    for n, lv in enumerate(levels):
        mask = (sc.LV == lv["name"]) | ((sc.LV == "") & ~outdoor)
        if not mask.any():
            continue
        cut = lv["elevation"] + CUT_HEIGHT
        mask &= sc.P[:, :, 2].min(axis=1) <= cut
        if not mask.any():
            continue
        cam = fit_ortho(sc, mask, (0, 0, 1), (0, 1, 0), plan_size, 1.04)
        img = draw(sc, mask, cam, plan_size, BG_PLAN, clip_z=cut, section=True)
        out.append({"name": "plan-%d-%s.png" % (n, slug(lv["name"])), "png": png_bytes(img), "size": plan_size, "kind": "plan",
                    "subject": {"type": "level", "id": lv["name"], "name": lv["name"], "elevationMetres": lv["elevation"]},
                    "camera": cam_record(cam), "cutHeightMetres": round(cut, 4), "background": list(BG_PLAN)})
    # interiors: up to maxRoomsPerKind rooms of each kind
    per_kind, picked = {}, []
    for room in sorted(ex.get("rooms", []), key=lambda r: (r["function"], r["id"])):
        if per_kind.get(room["function"], 0) < params["maxRoomsPerKind"]:
            per_kind[room["function"]] = per_kind.get(room["function"], 0) + 1
            picked.append(room)
    everything = np.ones(len(sc.P), dtype=bool)
    for room in picked:
        poly = Polygon(room["footprint"]).buffer(0)
        if poly.is_empty:
            continue
        lo, hi = np.array(room["min"]), np.array(room["max"])
        inset = poly.buffer(-min(0.3, 0.12 * min(hi[0] - lo[0], hi[1] - lo[1])))
        inset = inset if (not inset.is_empty and inset.area > 0) else poly
        cen = poly.centroid if poly.contains(poly.centroid) else poly.representative_point()
        eye_h = lo[2] + min(1.6, 0.6 * (hi[2] - lo[2]))
        corners = [(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]
        for k in range(params["interiorViewsPerRoom"]):
            eye_pt = nearest_points(inset, Point(corners[k % 4]))[0]
            tgt_pt = cen
            if eye_pt.distance(tgt_pt) < 0.5:
                tgt_pt = nearest_points(inset, Point(corners[(k + 2) % 4]))[0]
            cam = {"projection": "perspective", "eye": np.array([eye_pt.x, eye_pt.y, eye_h]), "target": np.array([tgt_pt.x, tgt_pt.y, lo[2] + 1.0]),
                   "up": (0, 0, 1), "fov": 60.0, "near": 0.05}
            img = draw(sc, everything & ~outdoor, cam, view_size, BG_VIEW)
            out.append({"name": "room-%s-%d.png" % (slug(room["id"]), k), "png": png_bytes(img), "size": view_size, "kind": "interior",
                        "subject": {"type": "room", "id": room["id"], "name": room["name"], "roomKind": room["function"], "level": room["level"]},
                        "camera": cam_record(cam), "background": list(BG_VIEW)})
    n_ext = params["exteriorViews"]
    for k in range(n_ext):
        az = math.radians(45.0 + 360.0 * k / n_ext)
        el = math.radians(28.0)
        d = (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))
        cam = fit_ortho(sc, everything, d, (0, 0, 1), view_size)
        img = draw(sc, everything, cam, view_size, BG_VIEW)
        out.append({"name": "exterior-%d.png" % k, "png": png_bytes(img), "size": view_size, "kind": "exterior",
                    "subject": {"type": "model", "id": "model", "name": "whole model"}, "camera": cam_record(cam),
                    "azimuthDegrees": round(math.degrees(az), 4), "elevationDegrees": 28.0, "background": list(BG_VIEW)})


def render_sheet(data, scale, out, name, subject, material, params):
    sc = Scene(data)
    cell = int(round(CELL * scale))
    frames = SWATCH_FRAMES if material else [(360.0 * k / params["turntableFrames"], 20) for k in range(params["turntableFrames"])]
    everything = np.ones(len(sc.P), dtype=bool)
    lo, hi = sc.bounds()
    c = (lo + hi) / 2.0
    radius = max(np.linalg.norm(hi - lo) / 2.0, 0.05)
    cols = 4
    rows = -(-len(frames) // cols)
    sheet = np.empty((rows * cell, cols * cell, 3), dtype=np.uint8)
    sheet[:] = BG_VIEW
    recs = []
    for i, (az_d, el_d) in enumerate(frames):
        az, el = math.radians(az_d), math.radians(el_d)
        d = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
        eye, f, r, u = look_at(c + d * (radius * 3.0 + 1.0), c, (0, 0, 1))
        cam = {"projection": "orthographic", "eye": eye, "target": c, "up": (0, 0, 1), "halfHeight": float(radius * 1.12)}
        tile = draw(sc, everything, cam, (cell, cell), BG_VIEW)
        y, x = (i // cols) * cell, (i % cols) * cell
        sheet[y:y + cell, x:x + cell] = tile
        recs.append({"index": i, "azimuthDegrees": round(az_d, 4), "elevationDegrees": float(el_d)})
        sheet[y:y + cell, x:x + 1] = 200                      # one-pixel grey rules between the frames
        sheet[y:y + 1, x:x + cell] = 200
    cam = {"projection": "orthographic", "eye": c, "target": c, "up": (0, 0, 1), "halfHeight": float(radius * 1.12)}
    rec_cam = cam_record(cam)
    rec_cam.pop("eye")
    out.append({"name": name, "png": png_bytes(sheet), "size": (cols * cell, rows * cell), "kind": "sheet", "subject": subject, "camera": rec_cam,
                "frames": recs, "cellPixels": [cell, cell], "columns": cols, "background": list(BG_VIEW)})


def render_set(glb_files, scale=1.0, params=None):
    """glb_files: list of dicts {path (file), rel (path used in names), role (model|component|material), subject (for sheets)}.
    Returns the list of records, each with `png` bytes, `name`, `glbSha256`, `glb` (the rel path)."""
    params = params or {k: rpt.param("proofs." + k) for k in ("interiorViewsPerRoom", "maxRoomsPerKind", "exteriorViews", "turntableFrames")}
    out = []
    for g in glb_files:
        with open(g["path"], "rb") as fh:
            data = fh.read()
        sha = glbkit.sha256_bytes(data)
        before = len(out)
        if g["role"] == "model":
            render_model(data, scale, out, sha, g["rel"], params)
        else:
            base = os.path.splitext(os.path.basename(g["rel"]))[0]
            render_sheet(data, scale, out, "sheet-%s.png" % base, g.get("subject") or {"type": "component", "id": base, "name": base},
                         g["role"] == "material", params)
        for rec in out[before:]:
            rec["glb"], rec["glbSha256"] = g["rel"], sha
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a folder written by export_glb.py, or one .glb file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--index", help="write the list of pictures with hashes and camera parameters as JSON")
    ap.add_argument("--scale", type=float, default=1.0, help="multiplies every picture size (default 1)")
    ap.add_argument("--profile")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    files = []
    if os.path.isfile(a.path):
        files.append({"path": a.path, "rel": os.path.basename(a.path), "role": "model"})
    elif os.path.isdir(a.path):
        for base, dirs, names in os.walk(a.path):
            dirs.sort()
            for n in sorted(names):
                if n.endswith(".glb"):
                    full = os.path.join(base, n)
                    rel = os.path.relpath(full, a.path).replace(os.sep, "/")
                    role = "model" if rel.startswith("model") else ("material" if rel.startswith("materials/") else "component")
                    files.append({"path": full, "rel": rel, "role": role})
    else:
        print("ERROR not found: %s" % a.path, file=sys.stderr)
        sys.exit(3)
    try:
        recs = render_set(files, a.scale)
    except (glbkit.Failed, KeyError, ValueError) as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        sys.exit(3)
    os.makedirs(a.out, exist_ok=True)
    index = []
    for r in recs:
        with open(os.path.join(a.out, r["name"]), "wb") as fh:
            fh.write(r["png"])
        index.append({k: v for k, v in r.items() if k != "png"} | {"sha256": glbkit.sha256_bytes(r["png"]), "bytes": len(r["png"])})
    if a.index:
        with open(a.index, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(index, fh, indent=1)
            fh.write("\n")
    for r in index:
        if a.json:
            continue
        print("%s  %s  %dx%d" % (r["sha256"], r["name"], r["size"][0], r["size"][1]))
    if a.json:
        print(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
