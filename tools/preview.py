#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Draw what is in a master IFC file, so that an author (or an agent) can see its own work: one plan per level and one
isometric view.

    python3 preview.py MASTER.ifc OUT_DIR [--no-iso] [--strict]

Plans cut at 1.2 m above each level's floor: walls and columns that span that height are dark, slabs light, doors and windows
coloured, stairs hatched, rooms outlined and labelled with their RoomId (open-air rooms dashed). The isometric view draws every
solid and, when the file has one, the terrain as a faint surface (an even share of its triangles when there are more than 20,000;
the message says so). Elements whose geometry cannot be built are left out of the pictures and listed; with --strict that is an
error. Writes OUT_DIR/plan-<n>-<level>.png and OUT_DIR/iso.png.
Exit codes: 0 written, 3 the file cannot be read, matplotlib is missing, or --strict and something was left out.

Requires: pip install -r tools/requirements-preview.txt
"""
import argparse
import os
import re
import sys

import numpy as np
import ifcopenshell
from shapely.geometry import Polygon
from shapely.ops import unary_union
import ifcopenshell.geom

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except ImportError:
    plt = None

ISO_COLOURS = {"IfcSlab": "#d9cdb0", "IfcWall": "#a98d63", "IfcStairFlight": "#6b8e9b", "IfcBuildingElementProxy": "#777777",
               "IfcWindow": "#4aa3c8", "IfcDoor": "#2a7f7f", "IfcFooting": "#888888", "IfcCovering": "#c9b79a", "IfcRoof": "#b07a5a"}


def meshes(model, skipped):
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    out = {}
    for e in model.by_type("IfcProduct"):
        if not getattr(e, "Representation", None) or e.is_a("IfcOpeningElement"):
            continue
        try:
            sh = ifcopenshell.geom.create_shape(settings, e)
        except Exception as exc:
            skipped.append("%s %s (%s)" % (e.is_a(), e.GlobalId, str(exc).splitlines()[0][:80] if str(exc) else "no geometry"))
            continue
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        f = np.array(sh.geometry.faces).reshape(-1, 3)
        if len(f):
            out[e.id()] = (v, f)
    return out


def level_of(e):
    for rel in getattr(e, "ContainedInStructure", None) or []:
        return rel.RelatingStructure
    for rel in getattr(e, "Decomposes", None) or []:
        if rel.RelatingObject.is_a("IfcBuildingStorey"):
            return rel.RelatingObject
    return None


def room_id(model, sp):
    for rel in sp.IsDefinedBy or []:
        ps = getattr(rel, "RelatingPropertyDefinition", None)
        if ps is not None and ps.is_a("IfcPropertySet"):
            for p in ps.HasProperties or []:
                if p.Name == "RoomId" and p.NominalValue is not None:
                    return str(p.NominalValue.wrappedValue)
    return sp.Name or ""


def up_faces(v, f, zmax=None):
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    keep = n[:, 2] > 1e-9
    return tri[keep][:, :, :2]


def plan(model, geo, storey, path, cut=1.2):
    fig, ax = plt.subplots(figsize=(10, 8))
    el = float(storey.Elevation or 0.0)
    shown = 0
    for e in model.by_type("IfcProduct"):
        if e.id() not in geo or level_of(e) != storey:
            continue
        v, f = geo[e.id()]
        zmin, zmax = v[:, 2].min(), v[:, 2].max()
        cls = e.is_a()
        tris = up_faces(v, f)
        if not len(tris):
            continue
        if cls == "IfcSpace":
            continue
        if cls == "IfcSlab" and not (zmax <= el + 0.05):
            continue
        if cls == "IfcSlab":
            colour, alpha, z = "#e6dfcc", 0.9, 1
        elif cls in ("IfcWall", "IfcColumn") and zmin <= el + cut <= zmax:
            colour, alpha, z = "#3a3a3a", 1.0, 3
        elif cls == "IfcStairFlight":
            ax.add_collection(PolyCollection(tris, facecolors="#c5d6dc", edgecolors="#4d6f7c", hatch="////", linewidths=0.3, zorder=2))
            shown += 1
            continue
        elif cls in ("IfcWindow", "IfcDoor"):
            colour, alpha, z = ("#4aa3c8" if cls == "IfcWindow" else "#c0622d"), 1.0, 4
        elif cls in ("IfcFooting", "IfcBuildingElementProxy", "IfcFurnishingElement") and zmin <= el + cut:
            colour, alpha, z = "#9a9a9a", 0.8, 2
        else:
            continue
        ax.add_collection(PolyCollection(tris, facecolors=colour, edgecolors="none", alpha=alpha, zorder=z))
        shown += 1
    for sp in model.by_type("IfcSpace"):
        if sp.id() not in geo or level_of(sp) != storey:
            continue
        v, f = geo[sp.id()]
        low = v[:, 2].min()
        tris = [t for t in v[f] if np.allclose(t[:, 2], low, atol=1e-6)]
        if not tris:
            continue
        pts = np.vstack(tris)[:, :2]
        ext = (sp.PredefinedType or "") == "EXTERNAL"
        outline = unary_union([Polygon(t[:, :2]) for t in tris if Polygon(t[:, :2]).area > 1e-9]).buffer(0)
        for g in (list(outline.geoms) if hasattr(outline, "geoms") else [outline]):
            xs, ys = g.exterior.xy
            ax.plot(xs, ys, color="#2a6f2a" if ext else "#1f4e9c", linestyle="--" if ext else "-", linewidth=0.9, zorder=5)
        c = np.array(outline.centroid.coords[0])
        ax.text(c[0], c[1], room_id(model, sp), ha="center", va="center", fontsize=7, zorder=6)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_title("%s (floor %.2f m, cut at %.1f m)" % (storey.Name, el, el + cut), fontsize=9)
    ax.grid(True, linewidth=0.2)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return shown


def iso(model, geo, path, notes):
    fig = plt.figure(figsize=(12, 6))
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for k, (el, az) in enumerate(((28, -60), (28, -120))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        for e in model.by_type("IfcProduct"):
            if e.id() not in geo or e.is_a("IfcSpace") or e.is_a("IfcSpatialZone"):
                continue
            v, f = geo[e.id()]
            terrain = e.is_a("IfcGeographicElement")
            if terrain and len(f) > 20000:
                notes.append("terrain: %d triangles, drawing every %dth" % (len(f), -(-len(f) // 20000)))
                f = f[::-(-len(f) // 20000)]
            col = "#9bb37a" if terrain else ISO_COLOURS.get(e.is_a(), "#bbbbbb")
            ax.add_collection3d(Poly3DCollection(v[f], facecolor=col, edgecolor="none" if terrain else "#00000022", linewidths=0.2,
                                                 alpha=0.25 if terrain else (0.55 if e.is_a() in ("IfcWindow", "IfcDoor") else 0.95)))
            if not terrain:
                lo, hi = np.minimum(lo, v.min(0)), np.maximum(hi, v.max(0))
        if np.isfinite(lo).all():
            pad = 0.15 * (hi - lo)
            ax.set_xlim(lo[0] - pad[0], hi[0] + pad[0])
            ax.set_ylim(lo[1] - pad[1], hi[1] + pad[1])
            ax.set_zlim(lo[2] - pad[2], hi[2] + pad[2])
            ax.set_box_aspect(tuple(np.maximum(hi - lo + 2 * pad, 1e-3)))
        ax.view_init(el, az)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ifc")
    ap.add_argument("out_dir")
    ap.add_argument("--no-iso", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 3 when an element had to be left out of the pictures")
    a = ap.parse_args()
    if plt is None:
        print("matplotlib is not installed: pip install matplotlib", file=sys.stderr)
        sys.exit(3)
    try:
        model = ifcopenshell.open(a.ifc)
    except Exception as exc:
        print("cannot read %s: %s" % (a.ifc, exc), file=sys.stderr)
        sys.exit(3)
    os.makedirs(a.out_dir, exist_ok=True)
    skipped, notes = [], []
    geo = meshes(model, skipped)
    for i, st in enumerate(sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation or 0.0)):
        slug = re.sub(r"[^a-z0-9]+", "-", (st.Name or "level").lower()).strip("-")[:40]
        p = os.path.join(a.out_dir, "plan-%d-%s.png" % (i, slug))
        n = plan(model, geo, st, p)
        print("wrote %s (%d elements)" % (p, n))
    if not a.no_iso:
        p = os.path.join(a.out_dir, "iso.png")
        iso(model, geo, p, notes)
        print("wrote " + p)
    for n in sorted(set(notes)):
        print("note: " + n)
    if skipped:
        print("left out of the pictures: %d element(s) whose geometry could not be built, first %s" % (len(skipped), "; ".join(skipped[:3])), file=sys.stderr)
        if a.strict:
            sys.exit(3)


if __name__ == "__main__":
    main()
