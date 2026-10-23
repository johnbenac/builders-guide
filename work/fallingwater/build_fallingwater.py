#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A simplified massing of a three-level house cantilevered over a stream, written with tools/ifc_author.py.

    python3 build_fallingwater.py OUT_DIR

Writes OUT_DIR/ifc/fallingwater-master.ifc, OUT_DIR/tables/rooms.csv and OUT_DIR/tables/building.json. The dimensions are
approximate and set by the author of this script (see NOTES.md). Metres, Z up, +X forward, +Y left; the stream side is low Y.
Levels sit at 0, 3 and 6 m. The output is deterministic.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from ifc_author import Builder  # noqa: E402

b = Builder("fallingwater-massing", "Cantilevered house over a stream", "Wooded ravine site", "Cantilevered house", "B-FALLINGWATER")
L = [b.level("Cantilevered house - living / +0 m", 0.0), b.level("Cantilevered house - bedrooms / +3 m", 3.0),
     b.level("Cantilevered house - upper / +6 m", 6.0)]
ELEV = [0.0, 3.0, 6.0]
T, H, WT, PT = 0.35, 2.65, 0.4, 0.2          # slab thickness, clear height, exterior wall thickness, partition thickness
X0, X1, Y0, Y1 = 0.0, 15.0, 0.0, 10.0        # main body footprint
CORE = (9.0, 3.9, 12.0, 9.6)                 # stone core

C = {k: b.style(n, h, o) for k, (n, h, o) in {
    "stone": ("sandstone", "#a98d63", 1.0), "tray": ("concrete tray", "#d9cdb0", 1.0), "parapet": ("concrete parapet", "#e6dcc3", 1.0),
    "roof": ("concrete roof", "#c9bfa6", 1.0), "partition": ("plaster partition", "#efe9db", 1.0), "door": ("door glazed", "#8fb8b8", 0.45),
    "glass": ("window glass", "#91c8d0", 0.45), "stair": ("stone stair", "#b9a584", 1.0), "boulder": ("boulder", "#7d776b", 1.0),
    "room": ("room volume", "#f4f1ea", 1.0)}.items()}
OPS = (C["partition"], C["door"], C["glass"])
D, W, DH = "door", "window", 2.3

# ------------------------------------------------------------------ trays
b.at(L[0])
slab0 = b.slab("slab/L0", "Main floor tray", [b.box(X0, Y0, -T, X1 - X0, Y1 - Y0, T, C["tray"])])
b.slab("slab/T0", "Living terrace tray", [b.box(3.0, -4.8, -T, 12.0, 4.8, T, C["tray"])])
b.at(L[1])
slab1 = b.slab("slab/L1", "Bedroom floor tray", [b.box(X0, Y0, 3.0 - T, X1 - X0, Y1 - Y0, T, C["tray"])])
b.slab("slab/T1", "Master terrace tray", [b.box(0.0, -6.2, 3.0 - T, 11.0, 6.2, T, C["tray"])])
b.at(L[2])
slab2 = b.slab("slab/L2", "Upper floor tray and roof terrace", [b.box(X0, Y0, 6.0 - T, X1 - X0, Y1 - Y0, T, C["tray"])])
b.slab("slab/roof", "Roof slab", [b.box(-0.4, 5.2, 6.0 + H, 9.8, 5.2, T, C["roof"])], kind="ROOF")

# ------------------------------------------------------------------ stairs and their wells (headroom 2.0 m under the slab above)
STAIRS = [  # level of the foot, key, name, foot point, run, foot z, host slab for the well, level of that slab, ceiling under it
    (0, "hatch", "Hatch stair to the stream", (4.6, 0.3), (0, 1), -2.6, 2.6, None, None),
    (0, "L0-L1", "Stair living to bedrooms", (0.6, 9.0), (1, 0), 0.0, 3.0, slab1, 1),
    (1, "L1-L2", "Stair bedrooms to upper", (8.6, 6.6), (-1, 0), 3.0, 3.0, slab2, 2)]
for lv, key, name, foot, run, zlow, rise, host, host_lv in STAIRS:
    b.at(lv)
    b.stair(key, name, foot, run, 1.2, zlow, rise, C["stair"], tread=0.25 if key == "hatch" else 0.28)
    if host is not None:
        ceiling = ELEV[host_lv] - T
        x0, y0, x1, y1 = b.stair_well(foot, run, 1.2, zlow, rise, ceiling, tread=0.28)
        b.at(host_lv)
        b.opening("hole/" + key, host, x0, y0, ELEV[host_lv] - T - 0.02, x1 - x0, y1 - y0, T + 0.04, C["partition"])
b.at(0)
b.opening("hole/hatch", slab0, 3.95, 0.3, -T - 0.02, 1.3, 3.6, T + 0.04, C["partition"])

# ------------------------------------------------------------------ walls with openings
b.at(0)
b.wall("L0/S", "South wall L0", (X0, Y0, X1, Y0 + WT), H, C["stone"], [(D, 1.2, 1.2, 0, DH), (W, 2.8, 2.4, 0.9, 2.2), (D, 5.6, 1.2, 0, DH),
       (W, 7.4, 4.2, 0.9, 2.2), (D, 12.0, 1.2, 0, DH)], opening_styles=OPS)
b.wall("L0/N", "North wall L0", (X0, Y1 - WT, X1, Y1), H, C["stone"], [(W, 0.8, 3.6, 0.9, 2.2), (D, 6.0, 1.2, 0, DH), (W, 12.6, 1.4, 1.0, 2.1)], opening_styles=OPS)
b.wall("L0/W", "West wall L0", (X0, Y0 + WT, X0 + WT, Y1 - WT), H, C["stone"], [(W, 2.0, 6.0, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("L0/E", "East wall L0", (X1 - WT, Y0 + WT, X1, Y1 - WT), H, C["stone"], [(W, 1.0, 2.0, 0.9, 2.2), (W, 5.5, 2.0, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("L0/kitchen", "Kitchen partition L0", (12.0, 3.9, X1 - WT, 4.1), H, C["partition"], [(D, 13.0, 1.0, 0, DH)], opening_styles=OPS)
b.wall("core/L0", "Stone core L0", CORE, H, C["stone"])
b.at(1)
b.wall("L1/S", "South wall L1", (X0, Y0, X1, Y0 + WT), H, C["stone"], [(D, 1.5, 1.2, 0, DH), (W, 3.2, 2.2, 0.9, 2.2), (D, 5.8, 1.2, 0, DH), (D, 10.6, 1.2, 0, DH),
       (W, 12.4, 1.6, 0.9, 2.2)], opening_styles=OPS)
b.wall("L1/N", "North wall L1", (X0, Y1 - WT, X1, Y1), H, C["stone"], [(W, 5.0, 3.4, 0.9, 2.2), (W, 12.6, 1.4, 0.9, 2.2)], opening_styles=OPS)
b.wall("L1/W", "West wall L1", (X0, Y0 + WT, X0 + WT, Y1 - WT), H, C["stone"], [(W, 1.5, 3.0, 0.9, 2.2), (W, 6.6, 1.4, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("L1/E", "East wall L1", (X1 - WT, Y0 + WT, X1, Y1 - WT), H, C["stone"], [(W, 1.2, 2.0, 0.9, 2.2), (W, 5.6, 2.4, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("L1/hall", "Hall partition L1", (X0 + WT, 5.6, 9.0, 5.8), H, C["partition"], [(D, 3.0, 1.2, 0, DH)], opening_styles=OPS)
b.wall("L1/master-east", "Master east partition L1", (8.8, Y0 + WT, 9.0, 5.6), H, C["partition"], [(D, 2.0, 1.0, 0, DH)], along="y", opening_styles=OPS)
b.wall("L1/east-room", "East room partition L1", (12.0, 3.9, X1 - WT, 4.1), H, C["partition"], [(D, 13.0, 1.0, 0, DH)], opening_styles=OPS)
b.wall("core/L1", "Stone core L1", CORE, H, C["stone"])
b.at(2)
b.wall("L2/S", "South wall L2", (X0, 5.6, 9.0, 6.0), H, C["stone"], [(D, 1.0, 1.2, 0, DH), (W, 3.2, 4.8, 0.9, 2.2)], opening_styles=OPS)
b.wall("L2/N", "North wall L2", (X0, Y1 - WT, 9.0, Y1), H, C["stone"], [(W, 1.0, 7.0, 0.9, 2.2)], opening_styles=OPS)
b.wall("L2/W", "West wall L2", (X0, 6.0, X0 + WT, Y1 - WT), H, C["stone"], [(W, 6.8, 2.0, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("L2/E", "East wall L2", (8.6, 6.0, 9.0, Y1 - WT), H, C["stone"], [(W, 7.0, 2.0, 0.9, 2.2)], along="y", opening_styles=OPS)
b.wall("core/L2", "Stone chimney stack", CORE, H + 1.8, C["stone"])

# parapets, 1.0 m, cream concrete
for lv, base, items in ((0, 0.0, [("S", (3.0, -4.8, 15.0, -4.6)), ("W", (3.0, -4.6, 3.2, 0.0)), ("E", (14.8, -4.6, 15.0, 0.0))]),
                        (1, 3.0, [("S", (0.0, -6.2, 11.0, -6.0)), ("W", (0.0, -6.0, 0.2, 0.0)), ("E", (10.8, -6.0, 11.0, 0.0))]),
                        (2, 6.0, [("S", (0.0, 0.0, 15.0, 0.2)), ("E", (14.8, 0.2, 15.0, 10.0)), ("N", (9.0, 9.8, 14.8, 10.0)), ("W", (0.0, 0.2, 0.2, 5.6))])):
    b.at(lv)
    for tag, rect in items:
        b.wall("parapet/L%d%s" % (lv, tag), "Parapet L%d %s" % (lv, tag), rect, 1.0, C["parapet"], z0=base)

# hearth boulder, a low irregular outcrop in the living room
b.at(0)
b.add("IfcBuildingElementProxy", "boulder/hearth", "Hearth boulder",
      [b.poly([(9.5, 2.9), (10.3, 2.7), (11.2, 2.9), (11.5, 3.5), (11.1, 3.9), (9.7, 3.9), (9.4, 3.4)], 0.0, 0.2, C["boulder"])],
      PredefinedType="USERDEFINED", ObjectType="Boulder")

# ------------------------------------------------------------------ rooms
I = WT
R = C["room"]
b.at(0)
b.room("FW-L0-LIV", "Living room", "living, dining and entry", [(I, I), (14.6, I), (14.6, 3.9), (9.0, 3.9), (9.0, 9.6), (I, 9.6)],
       "flagstone floor; plaster ceiling; sandstone walls", R, circulation=True)
b.room("FW-L0-KIT", "Kitchen", "kitchen", [(12.0, 4.1), (14.6, 4.1), (14.6, 9.6), (12.0, 9.6)], "flagstone floor; plaster walls", R)
b.room("FW-L0-TER", "Living terrace", "open-air terrace over the stream", [(3.2, -4.6), (14.8, -4.6), (14.8, 0.0), (3.2, 0.0)],
       "concrete tray; cream parapet", R, circulation=True, external=True)
b.at(1)
b.room("FW-L1-HALL", "Bedroom hall", "hall and stair landing",
       [(I, 5.8), (9.0, 5.8), (9.0, 9.6), (4.8, 9.6), (4.8, 8.4), (1.4, 8.4), (1.4, 9.6), (I, 9.6)], "flagstone floor; plaster walls", R, circulation=True)
b.room("FW-L1-MAS", "Master bedroom", "bedroom", [(I, I), (8.8, I), (8.8, 5.6), (I, 5.6)], "cork floor; plaster walls", R)
b.room("FW-L1-BED2", "Second bedroom", "bedroom", [(9.0, I), (14.6, I), (14.6, 3.9), (9.0, 3.9)], "cork floor; plaster walls", R)
b.room("FW-L1-DRS", "Dressing room", "dressing room and bath", [(12.0, 4.1), (14.6, 4.1), (14.6, 9.6), (12.0, 9.6)], "tile floor; plaster walls", R)
b.room("FW-L1-TER", "Master terrace", "open-air terrace over the living terrace", [(0.2, -6.0), (10.8, -6.0), (10.8, 0.0), (0.2, 0.0)],
       "concrete tray; cream parapet", R, circulation=True, external=True)
b.at(2)
b.room("FW-L2-STU", "Upper study", "study and guest bedroom",
       [(I, 6.0), (4.4, 6.0), (4.4, 7.2), (7.7, 7.2), (7.7, 6.0), (8.6, 6.0), (8.6, 9.6), (I, 9.6)], "cork floor; plaster walls", R)
b.room("FW-L2-TER", "Roof terrace", "open-air roof terrace",
       [(0.2, 0.2), (14.8, 0.2), (14.8, 9.8), (12.0, 9.8), (12.0, 3.9), (9.0, 3.9), (9.0, 5.6), (0.2, 5.6)], "concrete tray; cream parapet", R,
       circulation=True, external=True)

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fallingwater-out"
    path = b.write(out, "fallingwater-master.ifc")
    b.tables(out, "ifc/fallingwater-master.ifc")
    print("wrote", path)
