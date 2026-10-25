#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks for one texture set folder (guide 2, section 4).

    python3 check_texture_set.py SET_DIR [--preview wrap.png] [--report report.json]

Looks for albedo.png, normal.png, orm.png and set.json. Exits 1 when a REQUIRED rule fails.

Requires: pip install numpy pillow
"""
import argparse
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

import report as rpt

VERSION = "2.4.0"

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")
rows = []


def add(rule, level, ok, msg):
    lvl = rpt.level_of(rule)          # the profile may change a rule's level
    if lvl == "OFF":
        return
    rows.append({"rule": rule, "level": lvl, "status": "pass" if ok else ("fail" if lvl == "REQUIRED" else "warn"), "message": msg})


def png_header(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h, depth, ctype = struct.unpack(">IIBB", head[16:26])
    return w, h, depth, ctype


def from_srgb(s):
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def seam_ratio(a):
    a = a.astype(np.float32)
    inner_x = np.abs(a[:, 1:] - a[:, :-1]).mean()
    seam_x = np.abs(a[:, 0] - a[:, -1]).mean()
    inner_y = np.abs(a[1:] - a[:-1]).mean()
    seam_y = np.abs(a[0] - a[-1]).mean()
    return float(max(seam_x / (inner_x + 1e-6), seam_y / (inner_y + 1e-6)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set_dir")
    ap.add_argument("--profile", default=None, help="consumer profile; default profiles/default.json")
    ap.add_argument("--preview", default=None, help="write a three-by-three wrap preview of the albedo map")
    ap.add_argument("--report", default=None, help="also write the JSON report to this file")
    ap.add_argument("--json", action="store_true", help="print the JSON report (schema check-report/1) instead of text")
    a = ap.parse_args()
    tx = rpt.load_profile(a.profile)["textures"]
    d = a.set_dir
    if not os.path.isdir(d):
        rep = rpt.make_report("check_texture_set.py", VERSION, {"path": d}, [], error="input not found: %s" % d)
        print(json.dumps(rep, indent=1) if a.json else "ERROR input not found: %s" % d)
        sys.exit(rep["exitCode"])
    imgs = {}
    for name in tx["maps"]:
        p = os.path.join(d, name + ".png")
        if not os.path.exists(p):
            add("D-40", "REQUIRED", False, "missing %s.png" % name)
            continue
        hd = png_header(p)
        if hd is None:
            add("D-41", "REQUIRED", False, "%s.png is not a PNG file" % name)
            continue
        w, h, depth, ctype = hd
        if depth != 8 or ctype != 2:
            add("D-41", "REQUIRED", False, "%s.png must be 8-bit RGB without alpha (found bit depth %d, colour type %d)" % (name, depth, ctype))
            continue
        imgs[name] = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0
        add("D-41", "REQUIRED", True, "%s.png is 8-bit RGB, %d by %d" % (name, w, h))
    meta = None
    mp = os.path.join(d, "set.json")
    if not os.path.exists(mp):
        add("D-40", "REQUIRED", False, "missing set.json")
    else:
        with open(mp, encoding="utf-8") as fh:
            meta = json.load(fh)
        tm = meta.get("tileMetres")
        if not isinstance(tm, (int, float)) or tm <= 0:
            add("D-43", "REQUIRED", False, "set.json needs tileMetres greater than 0")
        else:
            add("D-43", "REQUIRED", True, "tileMetres %g" % tm)
        if meta.get("tintMode") not in tx["tintModes"]:
            add("D-47", "RECOMMENDED", False, "set.json tintMode should be one of %s" % ", ".join(tx["tintModes"]))
        if meta.get("normalConvention") and meta["normalConvention"] != tx["normalConvention"]:
            add("D-41", "REQUIRED", False, "set.json declares normalConvention %s; the profile reads %s" % (meta["normalConvention"], tx["normalConvention"]))
        if not SEMVER.match(str(meta.get("version", ""))):
            add("D-83", "RECOMMENDED", False, "set.json version should be a SemVer string")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(meta.get("name", ""))):
            add("D-83", "RECOMMENDED", False, "set name should be lower case with underscores")
    if imgs:
        sizes = {k: v.shape[:2] for k, v in imgs.items()}
        same = len(set(sizes.values())) == 1
        add("D-44", "RECOMMENDED", same, "all maps have the same size" if same else "maps differ in size: %s" % sizes)
        h, w = next(iter(sizes.values()))
        sq = h == w and (h & (h - 1)) == 0 and h in tx["sizesPixels"]
        add("D-44", "RECOMMENDED", sq, "square, power of two (%d)" % h if sq else "%d by %d is not a square power of two among %s" % (w, h, tx["sizesPixels"]))
        if meta and isinstance(meta.get("tileMetres"), (int, float)) and meta["tileMetres"] > 0:
            ppm = h / meta["tileMetres"]
            lo_d, hi_d = tx["densityPixelsPerMetre"]
            add("D-45", "RECOMMENDED", lo_d <= ppm <= hi_d, "%.0f pixels per metre" % ppm if lo_d <= ppm <= hi_d else
                "%.0f pixels per metre is outside the profile's %g to %g" % (ppm, lo_d, hi_d))
        if "albedo" in imgs:
            lin = from_srgb(imgs["albedo"])
            luma = float((lin * np.array([0.2126, 0.7152, 0.0722])).sum(-1).mean())
            mode = (meta or {}).get("tintMode")
            lo, hi = (0.3, 0.97) if mode == "multiply" else (0.02, 0.85)
            add("D-07", "RECOMMENDED", lo <= luma <= hi, "mean linear luminance %.3f" % luma if lo <= luma <= hi else
                "mean linear luminance %.3f is outside %.2f to %.2f for tintMode %s" % (luma, lo, hi, mode))
            add("D-42", "RECOMMENDED", seam_ratio(imgs["albedo"]) < 3.0, "albedo wrap seam ratio %.2f (about 1 is invisible; look at the preview)" % seam_ratio(imgs["albedo"]))
            if a.preview:
                t = (imgs["albedo"] * 255 + 0.5).astype(np.uint8)
                Image.fromarray(np.tile(t, (3, 3, 1))).resize((1536, 1536), Image.LANCZOS).save(a.preview)
        if "normal" in imgs:
            v = imgs["normal"] * 2 - 1
            ln = float(np.sqrt((v ** 2).sum(-1)).mean())
            mz = float(v[..., 2].mean())
            ok = 0.9 < ln < 1.1 and mz > 0.8 and abs(float(v[..., 0].mean())) < 0.1 and abs(float(v[..., 1].mean())) < 0.1
            add("D-41", "REQUIRED", ok, "normal map: mean length %.2f, mean z %.2f" % (ln, mz) if ok else
                "normal map does not look like tangent-basis data (mean length %.2f, mean z %.2f, mean xy %.2f, %.2f)" % (
                    ln, mz, float(v[..., 0].mean()), float(v[..., 1].mean())))
        if "orm" in imgs:
            o = imgs["orm"]
            add("D-41", "REQUIRED", float(o[..., 0].mean()) > 0.4 and float(o[..., 1].mean()) > 0.02,
                "orm map: occlusion mean %.2f, roughness mean %.2f, metalness mean %.2f" % tuple(float(o[..., i].mean()) for i in range(3)))
    name = os.path.basename(os.path.abspath(d))
    rep = rpt.make_report("check_texture_set.py", VERSION, {"path": name}, rpt.from_rows(rows, name), extra={"set": name})
    if a.report:
        rpt.write(rep, a.report)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        print("%s: %s (%d REQUIRED failure(s))" % (name, rep["result"].upper(), rep["summary"]["requiredFailures"]))
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
