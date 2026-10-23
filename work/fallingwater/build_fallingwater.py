#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A simplified, from-memory massing of a three-level house cantilevered over a stream, written with the guide set's rules.

    python3 build_fallingwater.py OUT_DIR

Writes OUT_DIR/ifc/fallingwater-master.ifc, OUT_DIR/tables/rooms.csv and OUT_DIR/tables/building.json.

The dimensions are approximate and set by the author of this script, not taken from drawings (see NOTES.md). Everything is
metres, Z up, +X forward, +Y left; the stream side of the house is the low-Y side. Levels sit at 0.0, 3.0 and 6.0 m.
The output is deterministic. Requires: pip install ifcopenshell
"""
import csv
import json
import os
import sys
import uuid

import ifcopenshell
import ifcopenshell.guid

LEVEL_OFFSET = 0.0           # default profile
NS = uuid.UUID("5f1c7a54-3a0e-5b6d-9e47-0f6f1d7c2a11")
BID = "B-FALLINGWATER"
LAYER = "permanent"

m = ifcopenshell.file(schema="IFC4")


def gid(key):
    return ifcopenshell.guid.compress(uuid.uuid5(NS, key).hex)


def pt(*c):
    return m.create_entity("IfcCartesianPoint", Coordinates=[float(x) for x in c])


def dr(*c):
    return m.create_entity("IfcDirection", DirectionRatios=[float(x) for x in c])


def ax3(origin=(0, 0, 0), z=(0, 0, 1), x=(1, 0, 0)):
    return m.create_entity("IfcAxis2Placement3D", Location=pt(*origin), Axis=dr(*z), RefDirection=dr(*x))


def place(origin=(0, 0, 0), parent=None):
    return m.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=ax3(origin))


# ------------------------------------------------------------------ project, units, context
project = m.create_entity("IfcProject", GlobalId=gid("project"), Name="Cantilevered house over a stream")
units = [m.create_entity("IfcSIUnit", UnitType=t, Name=n) for t, n in (
    ("LENGTHUNIT", "METRE"), ("AREAUNIT", "SQUARE_METRE"), ("VOLUMEUNIT", "CUBIC_METRE"), ("PLANEANGLEUNIT", "RADIAN"))]
project.UnitsInContext = m.create_entity("IfcUnitAssignment", Units=units)
ctx = m.create_entity("IfcGeometricRepresentationContext", None, "Model", 3, 1e-5, ax3())
body = m.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body", ContextType="Model",
                       ParentContext=ctx, TargetView="MODEL_VIEW")
project.RepresentationContexts = [ctx]


def prop(name, value):
    if isinstance(value, bool):
        v = m.create_entity("IfcBoolean", wrappedValue=value)
    elif isinstance(value, (int, float)):
        v = m.create_entity("IfcReal", wrappedValue=float(value))
    else:
        v = m.create_entity("IfcText", wrappedValue=str(value))
    return m.create_entity("IfcPropertySingleValue", Name=name, NominalValue=v)


def pset(obj, set_name, values):
    ps = m.create_entity("IfcPropertySet", GlobalId=gid("pset/" + obj.GlobalId + "/" + set_name), Name=set_name,
                         HasProperties=[prop(k, v) for k, v in values.items()])
    m.create_entity("IfcRelDefinesByProperties", GlobalId=gid("rel/" + obj.GlobalId + "/" + set_name),
                    RelatedObjects=[obj], RelatingPropertyDefinition=ps)


pset(project, "Pset_Declaration_Frame", {
    "FrameNote": "metres; +X forward; +Y left; +Z up; local z = 0 at the finished floor of the lowest level",
    "LevelOffsetMetres": LEVEL_OFFSET})

# ------------------------------------------------------------------ surface styles
styles = {}


def style(name, hexcol, opacity=1.0):
    if name not in styles:
        r, g, b = (int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        rend = m.create_entity("IfcSurfaceStyleRendering", SurfaceColour=m.create_entity("IfcColourRgb", Red=r, Green=g, Blue=b),
                               Transparency=round(1.0 - opacity, 6), ReflectanceMethod="NOTDEFINED")
        styles[name] = m.create_entity("IfcSurfaceStyle", Name=name, Side="BOTH", Styles=[rend])
    return styles[name]


C = {
    "stone": style("sandstone", "#a98d63"),
    "tray": style("concrete tray", "#d9cdb0"),
    "parapet": style("concrete parapet", "#e6dcc3"),
    "roof": style("concrete roof", "#c9bfa6"),
    "partition": style("plaster partition", "#efe9db"),
    "door": style("door glazed", "#8fb8b8", 0.45),
    "glass": style("window glass", "#91c8d0", 0.45),
    "frame": style("steel frame", "#a8372a"),
    "stair": style("stone stair", "#b9a584"),
    "boulder": style("boulder", "#7d776b"),
    "room": style("room volume", "#f4f1ea"),
}

# ------------------------------------------------------------------ geometry helpers (z arguments are absolute metres)
CUR = {"elev": 0.0}


def _solid(profile, z0, depth, st):
    solid = m.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=ax3((0, 0, z0 - CUR["elev"])),
                            ExtrudedDirection=dr(0, 0, 1), Depth=float(depth))
    m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
    return solid


def box(x0, y0, z0, dx, dy, dz, st):
    prof = m.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(dx), YDim=float(dy),
                           Position=m.create_entity("IfcAxis2Placement2D", Location=m.create_entity(
                               "IfcCartesianPoint", Coordinates=[x0 + dx / 2.0, y0 + dy / 2.0])))
    return _solid(prof, z0, dz, st)


def poly(points, z0, dz, st):
    """Upward extrusion of a closed polygon (plan points, counter-clockwise or not)."""
    area = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
               for i in range(len(points)))
    pts = list(points) if area > 0 else list(reversed(points))
    curve = m.create_entity("IfcPolyline", Points=[m.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y)])
                                                   for x, y in pts + [pts[0]]])
    return _solid(m.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve), z0, dz, st)


def stair_solid(start, run, width, z_low, nt, tread, riser, st):
    """Flight of nt treads (nt + 1 risers) rising from z_low along unit vector `run`, centred on `start` (plan point at the foot)."""
    up = (0.0, 0.0, 1.0)
    zv = (run[1] * up[2], -run[0] * up[2], 0.0)       # run x up: the direction the profile is extruded in
    origin = (start[0] - zv[0] * width / 2.0, start[1] - zv[1] * width / 2.0, z_low - CUR["elev"])
    pts = [(0.0, 0.0), (0.0, riser)]
    for k in range(1, nt + 1):
        pts += [(k * tread, k * riser)] if k == nt else [(k * tread, k * riser), (k * tread, (k + 1) * riser)]
    pts += [(nt * tread, (nt + 1) * riser), (nt * tread, 0.0)]
    # drop the duplicate collinear vertex at the last tread
    clean = [p for i, p in enumerate(pts) if p != pts[i - 1]]
    curve = m.create_entity("IfcPolyline", Points=[m.create_entity("IfcCartesianPoint", Coordinates=[a, b]) for a, b in clean + [clean[0]]])
    prof = m.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve)
    solid = m.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=ax3(origin, z=zv, x=(run[0], run[1], 0.0)),
                            ExtrudedDirection=dr(0, 0, 1), Depth=float(width))
    # profile Y must be world up: Position's local Y = Z x X, so choose Axis = zv, RefDirection = run  =>  Y = zv x run = up
    m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
    return solid


def shape(solids):
    rep = m.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
                          RepresentationType="SweptSolid", Items=solids)
    return m.create_entity("IfcProductDefinitionShape", Representations=[rep])


# ------------------------------------------------------------------ spatial structure
site = m.create_entity("IfcSite", GlobalId=gid("site"), Name="Wooded ravine site", ObjectPlacement=place(), CompositionType="ELEMENT")
building = m.create_entity("IfcBuilding", GlobalId=gid("building"), Name="Cantilevered house",
                           ObjectPlacement=place(parent=site.ObjectPlacement), CompositionType="ELEMENT")
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/project"), RelatingObject=project, RelatedObjects=[site])
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/site"), RelatingObject=site, RelatedObjects=[building])
pset(building, "Pset_Declaration_Building", {"BuildingId": BID, "Layer": LAYER})

ELEV = [0.0, 3.0, 6.0]
LEVEL_NAMES = ["Cantilevered house - living / +0 m", "Cantilevered house - bedrooms / +3 m", "Cantilevered house - upper / +6 m"]
storeys = []
for i, (el, nm) in enumerate(zip(ELEV, LEVEL_NAMES)):
    storeys.append(m.create_entity("IfcBuildingStorey", GlobalId=gid("storey%d" % i), Name=nm, Elevation=el,
                                   ObjectPlacement=place((0, 0, el), building.ObjectPlacement), CompositionType="ELEMENT"))
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/building"), RelatingObject=building, RelatedObjects=storeys)
contained = [[] for _ in storeys]


def at(level):
    CUR["elev"] = ELEV[level]
    CUR["level"] = level


def add(cls, key, name, solids, **kw):
    lv = CUR["level"]
    e = m.create_entity(cls, GlobalId=gid(key), Name=name, ObjectPlacement=place(parent=storeys[lv].ObjectPlacement),
                        Representation=shape(solids) if solids else None, **kw)
    contained[lv].append(e)
    return e


# ------------------------------------------------------------------ main dimensions
T = 0.35          # slab thickness
H = 2.65          # clear height: floor to underside of the slab above
WT = 0.4          # exterior wall thickness
PT = 0.2          # partition thickness
X0, X1, Y0, Y1 = 0.0, 15.0, 0.0, 10.0     # main body footprint (outer faces)
CORE = (9.0, 3.9, 12.0, 9.6)              # stone core (x0, y0, x1, y1)

# ------------------------------------------------------------------ slabs (trays)
at(0)
slab0 = add("IfcSlab", "slab/L0", "Main floor tray", [box(X0, Y0, -T, X1 - X0, Y1 - Y0, T, C["tray"])], PredefinedType="FLOOR")
add("IfcSlab", "slab/T0", "Living terrace tray", [box(3.0, -4.8, -T, 12.0, 4.8, T, C["tray"])], PredefinedType="FLOOR")

at(1)
slab1 = add("IfcSlab", "slab/L1", "Bedroom floor tray", [box(X0, Y0, ELEV[1] - T, X1 - X0, Y1 - Y0, T, C["tray"])], PredefinedType="FLOOR")
add("IfcSlab", "slab/T1", "Master terrace tray", [box(0.0, -6.2, ELEV[1] - T, 11.0, 6.2, T, C["tray"])], PredefinedType="FLOOR")

at(2)
slab2 = add("IfcSlab", "slab/L2", "Upper floor tray and roof terrace", [box(X0, Y0, ELEV[2] - T, X1 - X0, Y1 - Y0, T, C["tray"])], PredefinedType="FLOOR")
add("IfcSlab", "slab/roof", "Roof slab", [box(-0.4, 5.2, ELEV[2] + H, 9.8, 5.2, T, C["roof"])], PredefinedType="ROOF")


def opening(key, host, x0, y0, z0, dx, dy, dz):
    op = add("IfcOpeningElement", key, "Opening " + key, [box(x0, y0, z0, dx, dy, dz, C["partition"])], PredefinedType="OPENING")
    m.create_entity("IfcRelVoidsElement", GlobalId=gid("void/" + key), RelatingBuildingElement=host, RelatedOpeningElement=op)
    return op


# slab holes for stairs (B-53): hatch to the stream, stair L0 -> L1, stair L1 -> L2
at(0)
opening("hole/hatch", slab0, 3.95, 0.3, -T - 0.02, 1.3, 3.6, T + 0.04)
at(1)
opening("hole/stair1", slab1, 1.4, 8.4, ELEV[1] - T - 0.02, 3.4, 1.2, T + 0.04)
at(2)
opening("hole/stair2", slab2, 4.4, 6.0, ELEV[2] - T - 0.02, 3.3, 1.2, T + 0.04)

# ------------------------------------------------------------------ walls with openings
# an opening spec: (kind, along-wall start, width, sill, head); kind door | window
FRAME_T = 0.06


def wall(level, key, name, rect, openings, st="stone", z0=None, h=H, along="x", cls_pre=""):
    """Axis-aligned wall; rect = (x0, y0, x1, y1). openings are positioned along x (or y) in absolute plan coordinates."""
    at(level)
    z0 = ELEV[level] if z0 is None else z0
    x0, y0, x1, y1 = rect
    w = add("IfcWall", "wall/" + key, name, [box(x0, y0, z0, x1 - x0, y1 - y0, h, C[st])], PredefinedType="STANDARD")
    thick = (y1 - y0) if along == "x" else (x1 - x0)
    for i, (kind, s, width, sill, head) in enumerate(openings):
        okey = "%s/o%d" % (key, i)
        if along == "x":
            op = opening("opening/" + okey, w, s, y0 - 0.02, z0 + sill, width, thick + 0.04, head - sill)
            lx, ly, lw, ld = s, y0 + thick / 2 - FRAME_T / 2, width, FRAME_T
        else:
            op = opening("opening/" + okey, w, x0 - 0.02, s, z0 + sill, thick + 0.04, width, head - sill)
            lx, ly, lw, ld = x0 + thick / 2 - FRAME_T / 2, s, FRAME_T, width
        if kind == "door":
            e = add("IfcDoor", "door/" + okey, "Door " + okey, [box(lx, ly, z0 + sill, lw, ld, head - sill, C["door"])],
                    OverallHeight=head - sill, OverallWidth=width, PredefinedType="DOOR", OperationType="SINGLE_SWING_LEFT")
        else:
            e = add("IfcWindow", "window/" + okey, "Window " + okey, [box(lx, ly, z0 + sill, lw, ld, head - sill, C["glass"])],
                    OverallHeight=head - sill, OverallWidth=width, PredefinedType="WINDOW", PartitioningType="SINGLE_PANEL")
        m.create_entity("IfcRelFillsElement", GlobalId=gid("fill/" + okey), RelatingOpeningElement=op, RelatedBuildingElement=e)
    return w


D, W = "door", "window"
DH = 2.3

# Level 0 (living), z 0 to 2.65 -----------------------------------------------------------------
wall(0, "L0/S", "South wall L0", (X0, Y0, X1, Y0 + WT), [(D, 1.2, 1.2, 0, DH), (W, 2.8, 2.4, 0.9, 2.2), (D, 5.6, 1.2, 0, DH),
                                                         (W, 7.4, 4.2, 0.9, 2.2), (D, 12.0, 1.2, 0, DH)])
wall(0, "L0/N", "North wall L0", (X0, Y1 - WT, X1, Y1), [(W, 0.8, 3.6, 0.9, 2.2), (D, 6.0, 1.2, 0, DH), (W, 12.6, 1.4, 1.0, 2.1)])
wall(0, "L0/W", "West wall L0", (X0, Y0 + WT, X0 + WT, Y1 - WT), [(W, 2.0, 6.0, 0.9, 2.2)], along="y")
wall(0, "L0/E", "East wall L0", (X1 - WT, Y0 + WT, X1, Y1 - WT), [(W, 1.0, 2.0, 0.9, 2.2), (W, 5.5, 2.0, 0.9, 2.2)], along="y")
wall(0, "L0/kitchen", "Kitchen partition L0", (12.0, 3.9, X1 - WT, 4.1), [(D, 13.0, 1.0, 0, DH)], st="partition")

# Level 1 (bedrooms), z 3 to 5.65 --------------------------------------------------------------
wall(1, "L1/S", "South wall L1", (X0, Y0, X1, Y0 + WT), [(D, 1.5, 1.2, 0, DH), (W, 3.2, 2.2, 0.9, 2.2), (D, 5.8, 1.2, 0, DH),
                                                         (D, 10.6, 1.2, 0, DH), (W, 12.4, 1.6, 0.9, 2.2)])
wall(1, "L1/N", "North wall L1", (X0, Y1 - WT, X1, Y1), [(W, 5.0, 3.4, 0.9, 2.2), (W, 12.6, 1.4, 0.9, 2.2)])
wall(1, "L1/W", "West wall L1", (X0, Y0 + WT, X0 + WT, Y1 - WT), [(W, 1.5, 3.0, 0.9, 2.2), (W, 6.6, 1.4, 0.9, 2.2)], along="y")
wall(1, "L1/E", "East wall L1", (X1 - WT, Y0 + WT, X1, Y1 - WT), [(W, 1.2, 2.0, 0.9, 2.2), (W, 5.6, 2.4, 0.9, 2.2)], along="y")
wall(1, "L1/hall", "Hall partition L1", (X0 + WT, 5.6, 9.0, 5.8), [(D, 3.0, 1.2, 0, DH)], st="partition")
wall(1, "L1/master-east", "Master east partition L1", (8.8, Y0 + WT, 9.0, 5.6), [(D, 2.0, 1.0, 0, DH)], st="partition", along="y")
wall(1, "L1/east-room", "East room partition L1", (12.0, 3.9, X1 - WT, 4.1), [(D, 13.0, 1.0, 0, DH)], st="partition")

# Level 2 (upper), z 6 to 8.65: a smaller volume to the north-west --------------------------------
wall(2, "L2/S", "South wall L2", (X0, 5.6, 9.0, 6.0), [(D, 1.0, 1.2, 0, DH), (W, 3.2, 4.8, 0.9, 2.2)])
wall(2, "L2/N", "North wall L2", (X0, Y1 - WT, 9.0, Y1), [(W, 1.0, 7.0, 0.9, 2.2)])
wall(2, "L2/W", "West wall L2", (X0, 6.0, X0 + WT, Y1 - WT), [(W, 6.8, 2.0, 0.9, 2.2)], along="y")
wall(2, "L2/E", "East wall L2", (8.6, 6.0, 9.0, Y1 - WT), [(W, 7.0, 2.0, 0.9, 2.2)], along="y")

# the stone core, rising through the house and past the roof
for lv in (0, 1):
    wall(lv, "core/L%d" % lv, "Stone core L%d" % lv, CORE, [])
wall(2, "core/L2", "Stone chimney stack", CORE, [], h=H + 1.8)

# ------------------------------------------------------------------ parapets (walls, 1.0 m, cream concrete)
PH = 1.0
for lv, base, items in (
        (0, 0.0, [("S", (3.0, -4.8, 15.0, -4.6)), ("W", (3.0, -4.6, 3.2, 0.0)), ("E", (14.8, -4.6, 15.0, 0.0))]),
        (1, ELEV[1], [("S", (0.0, -6.2, 11.0, -6.0)), ("W", (0.0, -6.0, 0.2, 0.0)), ("E", (10.8, -6.0, 11.0, 0.0))]),
        (2, ELEV[2], [("S", (0.0, 0.0, 15.0, 0.2)), ("E", (14.8, 0.2, 15.0, 10.0)), ("N", (9.0, 9.8, 14.8, 10.0)),
                      ("W", (0.0, 0.2, 0.2, 5.6))])):
    for tag, rect in items:
        wall(lv, "parapet/L%d%s" % (lv, tag), "Parapet L%d %s" % (lv, tag), rect, [], st="parapet", z0=base, h=PH)

# ------------------------------------------------------------------ stairs (B-60, B-61)
def stair(level, key, name, start, run, width, z_low, nt, tread, riser):
    at(level)
    return add("IfcStairFlight", "stair/" + key, name, [stair_solid(start, run, width, z_low, nt, tread, riser, C["stair"])],
               NumberOfRisers=nt + 1, NumberOfTreads=nt, RiserHeight=riser, TreadLength=tread, PredefinedType="STRAIGHT")


# hatch stair from the living room down to the stream (2.6 m drop), 15 risers
stair(0, "hatch", "Hatch stair to the stream", (4.6, 0.3), (0, 1), 1.2, -2.6, 14, 0.25, 2.6 / 15)
# living room to bedroom level (3.0 m rise), 16 risers of 0.1875, then bedroom level to upper level
f1 = stair(0, "L0-L1", "Stair living to bedrooms", (0.6, 9.0), (1, 0), 1.2, 0.0, 15, 0.28, 0.1875)
f2 = stair(1, "L1-L2", "Stair bedrooms to upper", (8.6, 6.6), (-1, 0), 1.2, ELEV[1], 15, 0.28, 0.1875)
at(0)
interior = add("IfcStair", "stair/parent", "Interior stairs", None, PredefinedType="STRAIGHT_RUN_STAIR")
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/stairs"), RelatingObject=interior, RelatedObjects=[f1, f2])
contained[0].remove(f1)
contained[1].remove(f2)

# ------------------------------------------------------------------ hearth boulder (a low irregular outcrop in the living room)
at(0)
boulder = add("IfcBuildingElementProxy", "boulder/hearth", "Hearth boulder",
              [poly([(9.5, 2.9), (10.3, 2.7), (11.2, 2.9), (11.5, 3.5), (11.1, 3.9), (9.7, 3.9), (9.4, 3.4)], 0.0, 0.2, C["boulder"])],
              PredefinedType="USERDEFINED", ObjectType="Boulder")

# ------------------------------------------------------------------ rooms (IfcSpace), B-20 to B-29
ROOMS = []


def room(level, rid, name, function, outline, finish, circulation=False, height=H):
    at(level)
    sp = m.create_entity("IfcSpace", GlobalId=gid("room/" + rid), Name=name, LongName=name,
                         ObjectPlacement=place(parent=storeys[level].ObjectPlacement),
                         Representation=shape([poly(outline, ELEV[level], height, C["room"])]),
                         PredefinedType="INTERNAL", ElevationWithFlooring=0.0, CompositionType="ELEMENT")
    m.create_entity("IfcRelAggregates", GlobalId=gid("agg/" + rid), RelatingObject=storeys[level], RelatedObjects=[sp])
    area = abs(sum(outline[i][0] * outline[(i + 1) % len(outline)][1] - outline[(i + 1) % len(outline)][0] * outline[i][1]
                   for i in range(len(outline)))) / 2.0
    pset(sp, "Pset_Declaration_Room", {
        "RoomId": rid, "Occupant": "Residence", "Function": ("Circulation - " if circulation else "") + function,
        "NetAreaSquareMetres": round(area, 3), "BaseLevelMetres": ELEV[level], "ClearHeightMetres": height, "Finish": finish})
    ROOMS.append((rid, name, level, round(area, 3), height))


I = WT
room(0, "FW-L0-LIV", "Living room", "living, dining and entry", [(I, I), (14.6, I), (14.6, 3.9), (9.0, 3.9), (9.0, 9.6), (I, 9.6)],
     "flagstone floor; plaster ceiling; sandstone walls", circulation=True)
room(0, "FW-L0-KIT", "Kitchen", "kitchen", [(12.0, 4.1), (14.6, 4.1), (14.6, 9.6), (12.0, 9.6)],
     "flagstone floor; plaster walls")
room(0, "FW-L0-TER", "Living terrace", "open-air terrace over the stream", [(3.2, -4.6), (14.8, -4.6), (14.8, 0.0), (3.2, 0.0)],
     "concrete tray; cream parapet", circulation=True)
room(1, "FW-L1-HALL", "Bedroom hall", "hall and stair landing",
     [(I, 5.8), (9.0, 5.8), (9.0, 9.6), (4.8, 9.6), (4.8, 8.4), (1.4, 8.4), (1.4, 9.6), (I, 9.6)],
     "flagstone floor; plaster walls", circulation=True)
room(1, "FW-L1-MAS", "Master bedroom", "bedroom", [(I, I), (8.8, I), (8.8, 5.6), (I, 5.6)], "cork floor; plaster walls")
room(1, "FW-L1-BED2", "Second bedroom", "bedroom", [(9.0, I), (14.6, I), (14.6, 3.9), (9.0, 3.9)], "cork floor; plaster walls")
room(1, "FW-L1-DRS", "Dressing room", "dressing room and bath", [(12.0, 4.1), (14.6, 4.1), (14.6, 9.6), (12.0, 9.6)],
     "tile floor; plaster walls")
room(1, "FW-L1-TER", "Master terrace", "open-air terrace over the living terrace", [(0.2, -6.0), (10.8, -6.0), (10.8, 0.0), (0.2, 0.0)],
     "concrete tray; cream parapet", circulation=True)
room(2, "FW-L2-STU", "Upper study", "study and guest bedroom",
     [(I, 6.0), (4.4, 6.0), (4.4, 7.2), (7.7, 7.2), (7.7, 6.0), (8.6, 6.0), (8.6, 9.6), (I, 9.6)], "cork floor; plaster walls")
room(2, "FW-L2-TER", "Roof terrace", "open-air roof terrace",
     [(0.2, 0.2), (14.8, 0.2), (14.8, 9.8), (12.0, 9.8), (12.0, 3.9), (9.0, 3.9), (9.0, 5.6), (0.2, 5.6)],
     "concrete tray; cream parapet", circulation=True)

# ------------------------------------------------------------------ containment
for lv in range(3):
    m.create_entity("IfcRelContainedInSpatialStructure", GlobalId=gid("contain/storey%d" % lv), RelatingStructure=storeys[lv],
                    RelatedElements=contained[lv])


def write(out_dir):
    os.makedirs(os.path.join(out_dir, "ifc"), exist_ok=True)
    text = m.to_string()
    head, data = text.split("DATA;", 1)
    import re
    head = re.sub(r"FILE_NAME\(.*\);", "FILE_NAME('fallingwater-master.ifc','2026-10-23T00:00:00',('Author'),('Organisation'),"
                  "'ifcopenshell','ifcopenshell','');", head)
    path = os.path.join(out_dir, "ifc", "fallingwater-master.ifc")
    with open(path, "w", newline="\n") as fh:
        fh.write(head + "DATA;" + data)
    return path


def tables(out_dir):
    os.makedirs(os.path.join(out_dir, "tables"), exist_ok=True)
    with open(os.path.join(out_dir, "tables", "rooms.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["roomId", "name", "occupant", "kind", "enclosed", "level", "levelElevationMetres", "floorAreaM2",
                    "clearHeightM", "buildingId", "layer"])
        for rid, name, lv, area, h in ROOMS:
            w.writerow([rid, name, "Residence", "terrace" if rid.endswith("TER") else "room",
                        "no" if rid.endswith("TER") else "yes", LEVEL_NAMES[lv], ELEV[lv], area, h, BID, LAYER])
    meta = {"format": "building-metadata/1", "building": {"id": BID, "name": "Cantilevered house", "layer": LAYER},
            "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": LEVEL_OFFSET},
            "ifc": {"path": "ifc/fallingwater-master.ifc", "schema": "IFC4"},
            "levels": [{"name": n, "elevationMetres": e, "rooms": sum(1 for r in ROOMS if r[2] == i)}
                       for i, (n, e) in enumerate(zip(LEVEL_NAMES, ELEV))],
            "occupants": ["Residence"], "roomIdPrefix": "FW-",
            "counts": {"rooms": len(ROOMS), "walls": len(m.by_type("IfcWall")), "doors": len(m.by_type("IfcDoor")),
                       "windows": len(m.by_type("IfcWindow")), "stairFlights": len(m.by_type("IfcStairFlight"))}}
    with open(os.path.join(out_dir, "tables", "building.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fallingwater-out"
    p = write(out)
    tables(out)
    chk = ifcopenshell.open(p)
    print("wrote", p, "schema", chk.schema, "entities", len(list(chk)), "rooms", len(chk.by_type("IfcSpace")))
