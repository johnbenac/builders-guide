#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Three generic worked fixtures for sites and forms the one-room example does not cover, built with tools/ifc_author.py.

    python3 make_fixtures.py OUT_DIR

Writes OUT_DIR/<name>/ifc/master.ifc and tables for each of

    tray-house       two levels of cantilevered trays over a watercourse: stacked slabs, a stone core, open-air terraces,
                     a stair through a slab well, a parapet
    hillside-block   a block stepped up a steep slope and turned 30 degrees from east: two ground-contact levels, footings,
                     a retaining wall, a gable roof, a stair that arrives on a roof terrace
    courtyard        four wings round an open courtyard on one level: battered (leaning) outer walls, flat roofs with a
                     courtyard opening, parapets, open-air circulation

Each build returns the placement used for the terrain test (floor elevation, building origin, azimuth, ground slope). The
output is deterministic. Requires: pip install ifcopenshell
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ifc_author import Builder  # noqa: E402

def kit(name, building_id, occupant):
    b = Builder("fixtures/" + name, name, "Fixture site", name, building_id, occupant=occupant)
    C = {k: b.style(n, h, o) for k, (n, h, o) in {
        "stone": ("stone", "#a98d63", 1.0), "tray": ("concrete", "#d9cdb0", 1.0), "light": ("plaster", "#efe9db", 1.0),
        "roof": ("roof", "#8c5a4a", 1.0), "door": ("door glazed", "#8fb8b8", 0.45), "glass": ("window glass", "#91c8d0", 0.45),
        "stair": ("stair", "#b9a584", 1.0), "footing": ("footing", "#888888", 1.0), "room": ("room volume", "#f4f1ea", 1.0)}.items()}
    return b, C, (C["light"], C["door"], C["glass"])


def tray_house():
    b, C, ops = kit("tray-house", "B-TRAY", "Residence")
    T, H = 0.35, 2.65
    g, up = b.level("Tray house - living / +0 m", 0.0), b.level("Tray house - bedroom / +3 m", 3.0)
    b.at(g)
    slab0 = b.slab("slab/0", "Living floor", [b.box(0, 0, -T, 12, 8, T, C["tray"])])
    b.slab("slab/t0", "Living terrace", [b.box(3, -4, -T, 9, 4, T, C["tray"])])
    b.at(up)
    slab1 = b.slab("slab/1", "Bedroom floor", [b.box(0, 0, 3 - T, 12, 8, T, C["tray"])])
    b.slab("slab/t1", "Bedroom terrace", [b.box(0, -5.5, 3 - T, 9, 5.5, T, C["tray"])])
    b.slab("slab/roof", "Roof", [b.box(-0.4, -0.4, 6.0, 12.8, 8.8, T, C["roof"])], kind="ROOF")
    foot, run = (1.0, 7.15), (1, 0)
    b.at(g)
    b.stair("0-1", "Stair up", foot, (1, 0), 1.1, 0.0, 3.0, C["stair"])
    x0, y0, x1, y1 = b.stair_well(foot, run, 1.1, 0.0, 3.0, 3 - T)
    b.at(up)
    b.opening("hole/stair", slab1, x0, y0, 3 - T - 0.02, x1 - x0, y1 - y0, T + 0.04, C["light"])
    for lv, d0, d1 in ((g, 2.0, 9.0), (up, 1.5, 6.0)):        # the doors of the upper level open onto its terrace
        b.at(lv)
        d = (("door", d0, 1.2, 0, 2.3), ("window", 3.6, 1.6, 0.9, 2.2), ("door", d1, 1.2, 0, 2.3))
        b.wall("S%d" % lv, "South wall", (0, 0, 12, 0.3), H, C["stone"], d, opening_styles=ops)
        b.wall("N%d" % lv, "North wall", (0, 7.7, 12, 8), H, C["stone"], [("window", 3.0, 4.0, 0.9, 2.2)], opening_styles=ops)
        b.wall("W%d" % lv, "West wall", (0, 0.3, 0.3, 7.7), H, C["stone"], [], along="y", opening_styles=ops)
        b.wall("E%d" % lv, "East wall", (11.7, 0.3, 12, 7.7), H, C["stone"], [("window", 3.0, 2.0, 0.9, 2.2)], along="y", opening_styles=ops)
    b.at(g)
    b.wall("parapet0", "Parapet", (3, -4, 12, -3.8), 1.0, C["tray"])
    b.at(up)
    b.wall("parapet1", "Parapet", (0, -5.5, 9, -5.3), 1.0, C["tray"], z0=3.0)
    b.at(g)
    b.room("TH-L0-LIV", "Living room", "living room", [(0.3, 0.3), (11.7, 0.3), (11.7, 7.7), (0.3, 7.7)], "flagstone", C["room"], circulation=True)
    b.room("TH-L0-TER", "Living terrace", "open-air terrace over the watercourse", [(3.2, -3.8), (12, -3.8), (12, 0), (3.2, 0)], "concrete", C["room"],
           circulation=True, external=True)
    b.at(up)
    b.room("TH-L1-BED", "Bedroom", "bedroom",
           [(0.3, 0.3), (11.7, 0.3), (11.7, 7.7), (x1, 7.7), (x1, y0), (x0, y0), (x0, 7.7), (0.3, 7.7)],
           "cork", C["room"])
    b.room("TH-L1-TER", "Bedroom terrace", "open-air terrace over the living terrace", [(0.2, -5.3), (9, -5.3), (9, 0), (0.2, 0)], "concrete", C["room"],
           circulation=True, external=True)
    return b, {"floor": 412.0, "origin": (0.0, 0.0), "azimuth": 0.0, "height_at_origin": 411.0, "slope_x": 0.0, "slope_y": 0.1}


def hillside_block():
    b, C, ops = kit("hillside-block", "B-HILL", "Chalet")
    T, H = 0.35, 2.65
    low, up = b.level("Hillside block - lower / +0 m", 0.0, ground_contact=True), b.level("Hillside block - upper / +3 m", 3.0, ground_contact=True)
    b.at(low)
    b.slab("slab/0", "Lower floor", [b.box(0, 0, -T, 10, 6, T, C["tray"])])
    b.footing("footing", "Strip footing", [b.box(0, 0, -0.9, 10, 6, 0.55, C["footing"])])
    b.at(up)
    slab1 = b.slab("slab/1", "Upper floor and roof terrace", [b.box(0, 0, 3 - T, 10, 12, T, C["tray"])])
    b.at(low)
    foot = (5.2, 1.8)
    b.stair("0-1", "Stair to the upper level", foot, (0, 1), 1.0, 0.0, 3.0, C["stair"])
    x0, y0, x1, y1 = b.stair_well(foot, (0, 1), 1.0, 0.0, 3.0, 3 - T)
    b.at(up)
    b.opening("hole/stair", slab1, x0, y0, 3 - T - 0.02, x1 - x0, y1 - y0, T + 0.04, C["light"])
    b.at(low)
    b.wall("S0", "South wall", (0, 0, 10, 0.3), H, C["stone"], [("door", 5.4, 1.2, 0, 2.3), ("window", 1.5, 2.0, 0.9, 2.2)], opening_styles=ops)
    b.wall("N0", "North wall", (0, 5.7, 10, 6.0), H, C["stone"], [], opening_styles=ops)
    b.wall("W0", "West wall", (0, 0.3, 0.3, 5.7), H, C["stone"], [("window", 2.0, 2.0, 0.9, 2.2)], along="y", opening_styles=ops)
    b.wall("E0", "East wall", (9.7, 0.3, 10, 5.7), H, C["stone"], [("window", 2.0, 2.0, 0.9, 2.2)], along="y", opening_styles=ops)
    b.wall("P0", "Partition", (4.0, 0.3, 4.2, 5.7), H, C["light"], [("door", 2.0, 1.0, 0, 2.3)], along="y", opening_styles=ops)
    b.at(up)
    wall_h = H
    b.wall("S1", "South wall", (0, 6.0, 10, 6.2), wall_h, C["light"], [("door", 4.7, 1.0, 0, 2.3)], opening_styles=ops)
    b.wall("N1", "North wall", (0, 11.7, 10, 12.0), wall_h, C["stone"], [("window", 3.0, 3.0, 0.9, 2.2)], opening_styles=ops)
    b.wall("W1", "West wall", (0, 6.2, 0.3, 11.7), wall_h, C["stone"], [("window", 8.0, 2.0, 0.9, 2.2)], along="y", opening_styles=ops)
    b.wall("E1", "East wall", (9.7, 6.2, 10, 11.7), wall_h, C["stone"], [("window", 8.0, 2.0, 0.9, 2.2)], along="y", opening_styles=ops)
    b.wall("R1", "Retaining wall", (-2.5, 11.7, 0, 12.0), 3.0, C["stone"], [], z0=1.5, object_type="retaining")
    eave = 3.0 + wall_h
    b.wall_prism("gable-w", "Gable end west", "x", [(6.0, eave), (12.0, eave), (9.0, eave + 1.5)], 0.0, 0.3, C["stone"])
    b.wall_prism("gable-e", "Gable end east", "x", [(6.0, eave), (12.0, eave), (9.0, eave + 1.5)], 9.7, 0.3, C["stone"])
    b.gable_roof("roof", "Gable roof", (0, 6, 10, 12), eave, 1.5, "x", C["roof"])
    b.at(low)
    b.room("HB-L0-WRK", "Workshop", "workshop", [(0.3, 0.3), (4.0, 0.3), (4.0, 5.7), (0.3, 5.7)], "concrete", C["room"])
    b.room("HB-L0-HALL", "Entry hall", "entry hall and stair", [(4.2, 0.3), (9.7, 0.3), (9.7, 5.7), (4.2, 5.7)], "slate", C["room"], circulation=True)
    b.at(up)
    b.room("HB-L1-TER", "Roof terrace", "open-air terrace on the lower roof",
           [(0.3, 0.3), (9.7, 0.3), (9.7, 5.7), (x1, 5.7), (x1, y0), (x0, y0), (x0, 5.7), (0.3, 5.7)], "slate", C["room"], circulation=True, external=True)
    b.room("HB-L1-LIV", "Living room", "living room", [(0.3, 6.2), (9.7, 6.2), (9.7, 11.7), (0.3, 11.7)], "timber", C["room"])
    # the terrain rises 0.5 m per metre of the building's +Y axis; it is 1.5 m below the lower floor at y = 0
    return b, {"floor": 1200.0, "origin": (500.0, 200.0), "azimuth": 30.0, "height_at_origin": 1198.5,
               "slope_x": -0.25, "slope_y": 0.4330127}


def courtyard():
    b, C, ops = kit("courtyard", "B-COURT", "Community")
    T, H = 0.35, 3.0
    g = b.level("Courtyard building - ground / +0 m", 0.0, ground_contact=True)
    b.at(g)
    b.slab("slab/0", "Floor", [b.box(0, 0, -T, 20, 20, T, C["tray"])])
    # four roof pieces round the open courtyard
    for k, (x0, y0, dx, dy) in {"s": (0, 0, 20, 6.2), "n": (0, 13.8, 20, 6.2), "w": (0, 6.2, 6.2, 7.6), "e": (13.8, 6.2, 6.2, 7.6)}.items():
        b.slab("roof/" + k, "Roof " + k, [b.box(x0, y0, H, dx, dy, T, C["roof"])], kind="ROOF")
    # outer walls lean inwards: thick at the foot, thinner at the head
    b.wall_prism("outer-s", "South outer wall", "x", [(0, 0), (0.8, 0), (0.8, H), (0.3, H)], 0.0, 20.0, C["stone"],
                 [("door", 9.3, 1.4, 0, 2.4), ("window", 3.0, 1.2, 1.2, 2.2), ("window", 15.0, 1.2, 1.2, 2.2)], opening_styles=ops)
    b.wall_prism("outer-n", "North outer wall", "x", [(19.2, 0), (20, 0), (19.7, H), (19.2, H)], 0.0, 20.0, C["stone"],
                 [("window", 3.0, 1.2, 1.2, 2.2), ("window", 15.0, 1.2, 1.2, 2.2)], opening_styles=ops)
    b.wall_prism("outer-w", "West outer wall", "y", [(0, 0), (0.8, 0), (0.8, H), (0.3, H)], 0.8, 18.4, C["stone"],
                 [("window", 9.4, 1.2, 1.2, 2.2)], opening_styles=ops)
    b.wall_prism("outer-e", "East outer wall", "y", [(19.2, 0), (20, 0), (19.7, H), (19.2, H)], 0.8, 18.4, C["stone"],
                 [("window", 9.4, 1.2, 1.2, 2.2)], opening_styles=ops)
    # the wall of the courtyard, with a door into each wing, also divides the wings
    b.wall("c-s", "Courtyard wall south", (0.8, 5.8, 19.2, 6.2), H, C["light"], [("door", 9.0, 1.2, 0, 2.3)], opening_styles=ops)
    b.wall("c-n", "Courtyard wall north", (0.8, 13.8, 19.2, 14.2), H, C["light"], [("door", 9.0, 1.2, 0, 2.3)], opening_styles=ops)
    b.wall("c-w", "Courtyard wall west", (5.8, 6.2, 6.2, 13.8), H, C["light"], [("door", 9.0, 1.2, 0, 2.3)], along="y", opening_styles=ops)
    b.wall("c-e", "Courtyard wall east", (13.8, 6.2, 14.2, 13.8), H, C["light"], [("door", 9.0, 1.2, 0, 2.3)], along="y", opening_styles=ops)
    for k, rect in {"s": (0.3, 0.3, 19.7, 0.6), "n": (0.3, 19.4, 19.7, 19.7), "w": (0.3, 0.6, 0.6, 19.4), "e": (19.4, 0.6, 19.7, 19.4)}.items():
        b.wall("parapet-" + k, "Parapet " + k, rect, 0.8, C["stone"], z0=H + T)
    r = C["room"]
    b.room("CY-SOUTH", "South wing", "hall of the south wing", [(0.8, 0.8), (19.2, 0.8), (19.2, 5.8), (0.8, 5.8)], "packed earth", r, height=H)
    b.room("CY-NORTH", "North wing", "hall of the north wing", [(0.8, 14.2), (19.2, 14.2), (19.2, 19.2), (0.8, 19.2)], "packed earth", r, height=H)
    b.room("CY-WEST", "West wing", "cells of the west wing", [(0.8, 6.2), (5.8, 6.2), (5.8, 13.8), (0.8, 13.8)], "packed earth", r, height=H)
    b.room("CY-EAST", "East wing", "cells of the east wing", [(14.2, 6.2), (19.2, 6.2), (19.2, 13.8), (14.2, 13.8)], "packed earth", r, height=H)
    b.room("CY-YARD", "Courtyard", "open-air courtyard", [(6.2, 6.2), (13.8, 6.2), (13.8, 13.8), (6.2, 13.8)], "paving", r, circulation=True, external=True, height=H)
    return b, {"floor": 3650.0, "origin": (0.0, 0.0), "azimuth": 0.0, "height_at_origin": 3650.0, "slope_x": 0.02, "slope_y": 0.03}


FIXTURES = {"tray-house": tray_house, "hillside-block": hillside_block, "courtyard": courtyard}


def build(name, out_dir):
    """Build one fixture into OUT_DIR/<name>; returns (path of the master file, placement dict)."""
    b, place = FIXTURES[name]()
    d = os.path.join(out_dir, name)
    path = b.write(d, "master.ifc")
    b.tables(d, "ifc/master.ifc")
    return path, place


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fixtures-out"
    for n in FIXTURES:
        print("wrote", build(n, out)[0])
