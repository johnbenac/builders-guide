#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the worked-example delivery of guide 5 into an output folder.

One room (4.8 m by 3.8 m, 3.0 m clear height) with one door, one window, one table, one wall covering and one
ceiling light fixture, on one level, written as IFC4 with the library `ifcopenshell`.

    python3 make_sample.py OUT_DIR

Writes OUT_DIR/ifc/example-room-master.ifc and the companion tables. The output is deterministic: running the
script twice gives byte-identical files. Entity numbers start at 700001 and positions that the consumer reads
(light position) are written in the consumer's global frame with a level offset of 12.0 m, as guide 1 (B-71, B-92)
describes.

Requires: pip install ifcopenshell
"""
import csv
import os
import re
import sys
import uuid

import ifcopenshell
import ifcopenshell.guid

LEVEL_OFFSET = 12.0          # metres, from the (example) profile
ENTITY_START = 700001        # from the (example) profile
NS = uuid.UUID("135a3346-0b9a-5ae4-b7e1-aec9398344b6")

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
project = m.create_entity("IfcProject", GlobalId=gid("project"), Name="Example room delivery")
length = m.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
area = m.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE")
volume = m.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
angle = m.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
project.UnitsInContext = m.create_entity("IfcUnitAssignment", Units=[length, area, volume, angle])
ctx = m.create_entity("IfcGeometricRepresentationContext", None, "Model", 3, 1e-5, ax3())
body = m.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body", ContextType="Model",
                       ParentContext=ctx, TargetView="MODEL_VIEW")
project.RepresentationContexts = [ctx]

# ------------------------------------------------------------------ properties
def prop(name, value):
    if isinstance(value, bool):
        v = m.create_entity("IfcBoolean", wrappedValue=value)
    elif isinstance(value, (int, float)):
        v = m.create_entity("IfcReal", wrappedValue=float(value))
    else:
        v = m.create_entity("IfcText", wrappedValue=str(value))
    return m.create_entity("IfcPropertySingleValue", Name=name, NominalValue=v)


def pset(obj, set_name, values):
    props = [prop(k, v) for k, v in values.items()]
    ps = m.create_entity("IfcPropertySet", GlobalId=gid("pset/" + obj.GlobalId + "/" + set_name), Name=set_name,
                         HasProperties=props)
    m.create_entity("IfcRelDefinesByProperties", GlobalId=gid("rel/" + obj.GlobalId + "/" + set_name),
                    RelatedObjects=[obj], RelatingPropertyDefinition=ps)


# project-level frame note (B-12)
pset(project, "Pset_Declaration_Frame", {
    "FrameNote": "metres; +X forward; +Y left; +Z up; local z = 0 at the finished floor of the lowest level",
    "LevelOffsetMetres": LEVEL_OFFSET})

# ------------------------------------------------------------------ surface styles (colour and opacity only)
styles = {}


def style(name, hexcol, opacity=1.0):
    if name in styles:
        return styles[name]
    r, g, b = (int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    rend = m.create_entity("IfcSurfaceStyleRendering", SurfaceColour=m.create_entity("IfcColourRgb", Red=r, Green=g, Blue=b),
                           Transparency=round(1.0 - opacity, 6), ReflectanceMethod="NOTDEFINED")
    styles[name] = m.create_entity("IfcSurfaceStyle", Name=name, Side="BOTH", Styles=[rend])
    return styles[name]


# ------------------------------------------------------------------ geometry helpers
def box_solid(x0, y0, z0, dx, dy, dz, st):
    """Axis-aligned box as an upward extrusion of a rectangle profile; returns the solid."""
    prof = m.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(dx), YDim=float(dy),
                           Position=m.create_entity("IfcAxis2Placement2D", Location=m.create_entity(
                               "IfcCartesianPoint", Coordinates=[x0 + dx / 2.0, y0 + dy / 2.0])))
    solid = m.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=ax3((0, 0, z0)),
                            ExtrudedDirection=dr(0, 0, 1), Depth=float(dz))
    m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
    return solid


def shape(solids, rep_type="SweptSolid"):
    rep = m.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
                          RepresentationType=rep_type, Items=solids)
    return m.create_entity("IfcProductDefinitionShape", Representations=[rep])


# ------------------------------------------------------------------ spatial structure
site = m.create_entity("IfcSite", GlobalId=gid("site"), Name="Example site", ObjectPlacement=place(),
                       CompositionType="ELEMENT")
building = m.create_entity("IfcBuilding", GlobalId=gid("building"), Name="Example building",
                           ObjectPlacement=place(parent=site.ObjectPlacement), CompositionType="ELEMENT")
storey = m.create_entity("IfcBuildingStorey", GlobalId=gid("storey0"), Name="Example building - ground / +0 m",
                         ObjectPlacement=place((0, 0, 0), building.ObjectPlacement), CompositionType="ELEMENT",
                         Elevation=0.0)
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/project"), RelatingObject=project, RelatedObjects=[site])
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/site"), RelatingObject=site, RelatedObjects=[building])
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/building"), RelatingObject=building, RelatedObjects=[storey])
pset(building, "Pset_Declaration_Building", {"BuildingId": "B-EXAMPLE", "Layer": "interim"})

contained = []


def add(cls, key, name, solids, st_place=None, **kw):
    e = m.create_entity(cls, GlobalId=gid(key), Name=name, ObjectPlacement=st_place or place(parent=storey.ObjectPlacement),
                        Representation=shape(solids) if solids else None, **kw)
    contained.append(e)
    return e


C = {
    "wall": style("wall ivory", "#d9d2c3"),
    "floor": style("slab floor", "#c9c4b8"),
    "roof": style("slab roof", "#e8e4da"),
    "door": style("door timber", "#977353"),
    "glass": style("window glass", "#91c8d0", 0.45),
    "frame": style("window frame", "#6b7a81"),
    "table": style("table oak", "#ccbba0"),
    "cover": style("covering timber", "#8c6f4e"),
    "housing": style("luminaire housing", "#3d4348"),
    "lens": style("luminaire lens", "#fff0cf"),
}

W, D, T, H = 5.2, 4.2, 0.2, 3.0   # outer width, outer depth, wall thickness, clear height

# ------------------------------------------------------------------ floor and roof slabs
floor = add("IfcSlab", "slab/floor", "Floor slab", [box_solid(0, 0, -0.3, W, D, 0.3, C["floor"])], PredefinedType="FLOOR")
roof = add("IfcSlab", "slab/roof", "Roof slab", [box_solid(0, 0, H, W, D, 0.3, C["roof"])], PredefinedType="ROOF")

# ------------------------------------------------------------------ walls (south, north, west, east)
walls = {
    "south": add("IfcWall", "wall/south", "South wall", [box_solid(0, 0, 0, W, T, H, C["wall"])], PredefinedType="STANDARD"),
    "north": add("IfcWall", "wall/north", "North wall", [box_solid(0, D - T, 0, W, T, H, C["wall"])], PredefinedType="STANDARD"),
    "west": add("IfcWall", "wall/west", "West wall", [box_solid(0, T, 0, T, D - 2 * T, H, C["wall"])], PredefinedType="STANDARD"),
    "east": add("IfcWall", "wall/east", "East wall", [box_solid(W - T, T, 0, T, D - 2 * T, H, C["wall"])], PredefinedType="STANDARD"),
}


def opening(key, wall, x0, y0, z0, dx, dy, dz):
    """An opening element that voids a wall (B-41, B-44)."""
    op = add("IfcOpeningElement", key, "Opening " + key, [box_solid(x0, y0, z0, dx, dy, dz, C["wall"])],
             PredefinedType="OPENING")
    m.create_entity("IfcRelVoidsElement", GlobalId=gid("void/" + key), RelatingBuildingElement=wall, RelatedOpeningElement=op)
    return op


# door: 1.2 m wide, 2.3 m high, in the south wall; the doorway stays open (no threshold, no bar)
door_op = opening("opening/door", walls["south"], 0.8, -0.02, 0.0, 1.2, T + 0.04, 2.3)
door = add("IfcDoor", "door/entrance", "Entrance door", [box_solid(0.8, 0.08, 0.0, 1.2, 0.04, 2.3, C["door"])],
           OverallHeight=2.3, OverallWidth=1.2, PredefinedType="DOOR", OperationType="SINGLE_SWING_LEFT")
m.create_entity("IfcRelFillsElement", GlobalId=gid("fill/door"), RelatingOpeningElement=door_op, RelatedBuildingElement=door)

# window: 1.5 m wide, 1.2 m high, sill at 0.9 m, in the north wall
win_op = opening("opening/window", walls["north"], 2.0, D - T - 0.02, 0.9, 1.5, T + 0.04, 1.2)
window = add("IfcWindow", "window/north", "North window",
             [box_solid(2.0, D - T / 2 - 0.01, 0.9, 1.5, 0.02, 1.2, C["glass"])],
             OverallHeight=1.2, OverallWidth=1.5, PredefinedType="WINDOW", PartitioningType="SINGLE_PANEL")
m.create_entity("IfcRelFillsElement", GlobalId=gid("fill/window"), RelatingOpeningElement=win_op, RelatedBuildingElement=window)

# ------------------------------------------------------------------ the room (an IfcSpace), D-10, B-20 to B-25
room = add("IfcSpace", "room/main", "Example work room", [box_solid(T, T, 0, W - 2 * T, D - 2 * T, H, C["wall"])],
           PredefinedType="INTERNAL", ElevationWithFlooring=0.0, CompositionType="ELEMENT",
           LongName="Example work room")
contained.remove(room)     # a room belongs to its level by aggregation, not containment
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/room"), RelatingObject=storey, RelatedObjects=[room])
area_m2 = round((W - 2 * T) * (D - 2 * T), 3)
pset(room, "Pset_Declaration_Room", {
    "RoomId": "EX-001", "Occupant": "Example Occupant", "Function": "Work room",
    "NetAreaSquareMetres": area_m2, "BaseLevelMetres": 0.0, "ClearHeightMetres": H,
    "Finish": "oak plank floor; ivory plaster walls; timber wall covering on the west wall"})

# ------------------------------------------------------------------ the table: a mapped item (F-61), pivot at the floor
tbl_origin = (2.6, 2.1)
tbl_geom = box_solid(-0.8, -0.4, 0.0, 1.6, 0.8, 0.74, C["table"])
tbl_rep = m.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
                          RepresentationType="SweptSolid", Items=[tbl_geom])
tbl_map = m.create_entity("IfcRepresentationMap", MappingOrigin=ax3(), MappedRepresentation=tbl_rep)
tbl_item = m.create_entity("IfcMappedItem", MappingSource=tbl_map, MappingTarget=m.create_entity(
    "IfcCartesianTransformationOperator3D", LocalOrigin=pt(0, 0, 0)))
tbl_shape = m.create_entity("IfcProductDefinitionShape", Representations=[m.create_entity(
    "IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="MappedRepresentation",
    Items=[tbl_item])])
table = m.create_entity("IfcFurnishingElement", GlobalId=gid("furniture/table"), Name="Work table, 1.6 m",
                        ObjectType="table", ObjectPlacement=place((tbl_origin[0], tbl_origin[1], 0.0), storey.ObjectPlacement),
                        Representation=tbl_shape)
contained.append(table)
pset(table, "Pset_Declaration_Item", {"ItemId": "table.work.1600", "ItemVersion": "1.0.0", "Role": "work table"})

# ------------------------------------------------------------------ the wall covering (D-31): a 10 mm shell on the west wall
cover = add("IfcCovering", "covering/west", "West wall timber covering",
            [box_solid(T, 0.6, 0.1, 0.01, 3.0, 2.4, C["cover"])], PredefinedType="CLADDING")

# ------------------------------------------------------------------ the luminaire: assembly + housing + lens (B-90, B-91)
lx, ly = tbl_origin
asm = add("IfcElementAssembly", "lum/assembly", "Example work room luminaire 1", None, PredefinedType="USERDEFINED",
          ObjectType="Luminaire")
housing = m.create_entity("IfcLightFixture", GlobalId=gid("lum/housing"), Name="Example work room luminaire 1 housing",
                          ObjectType="Luminaire housing", ObjectPlacement=place(parent=storey.ObjectPlacement),
                          Representation=shape([box_solid(lx - 0.15, ly - 0.15, H - 0.1, 0.3, 0.3, 0.1, C["housing"])]),
                          PredefinedType="USERDEFINED")
lens = m.create_entity("IfcLightFixture", GlobalId=gid("lum/lens"), Name="Example work room luminaire 1 lens",
                       ObjectType="Luminaire lens", ObjectPlacement=place(parent=storey.ObjectPlacement),
                       Representation=shape([box_solid(lx - 0.12, ly - 0.12, H - 0.12, 0.24, 0.24, 0.02, C["lens"])]),
                       PredefinedType="USERDEFINED")
m.create_entity("IfcRelAggregates", GlobalId=gid("agg/lum"), RelatingObject=asm, RelatedObjects=[housing, lens])
lens_z_local = H - 0.12 + 0.01     # centre of the lens part
pset(asm, "Pset_Declaration_Luminaire", {
    "LuminaireId": "UL-EX-01", "LuminaireMount": "ceiling", "LuminaireTarget": "EX-001",
    "LightType": "spot", "LightEnergy": 6.0, "LightRangeM": 8.0, "LightSpotDeg": 78.0,
    "LightColor": "1,0.87,0.7",
    "LightPositionLocal": "%g,%g,%g" % (lx, ly, lens_z_local),
    "LightPosition": "%g,%g,%g" % (lx, ly, round(lens_z_local + LEVEL_OFFSET, 6)),
    "LightAim": "0,0,-1", "LightFadeBeginM": 40.0, "LightFadeLengthM": 20.0})

# ------------------------------------------------------------------ containment in the level
m.create_entity("IfcRelContainedInSpatialStructure", GlobalId=gid("contain/storey0"), RelatingStructure=storey,
                RelatedElements=contained)

# ------------------------------------------------------------------ write, renumber from the assigned start, verify
def write(out_dir):
    os.makedirs(os.path.join(out_dir, "ifc"), exist_ok=True)
    text = m.to_string()
    # the example keeps '#' out of every quoted string, so a plain renumbering is safe
    head, data = text.split("DATA;", 1)
    # fixed header so that two runs give byte-identical files
    head = re.sub(r"FILE_NAME\(.*\);", "FILE_NAME('example-room-master.ifc','2026-10-22T00:00:00',('Example author'),"
                  "('Example organisation'),'ifcopenshell','ifcopenshell','');", head)
    assert "#" not in re.sub(r"#\d+", "", data), "unexpected '#' in a string"
    offset = ENTITY_START - 1
    data = re.sub(r"#(\d+)", lambda g: "#%d" % (int(g.group(1)) + offset), data)
    path = os.path.join(out_dir, "ifc", "example-room-master.ifc")
    with open(path, "w", newline="\n") as fh:
        fh.write(head + "DATA;" + data)
    return path


def tables(out_dir):
    os.makedirs(os.path.join(out_dir, "tables"), exist_ok=True)
    with open(os.path.join(out_dir, "tables", "rooms.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["roomId", "name", "occupant", "kind", "enclosed", "level", "levelElevationMetres", "floorAreaM2",
                    "clearHeightM", "buildingId", "layer"])
        w.writerow(["EX-001", "Example work room", "Example Occupant", "room", "yes", "Example building - ground / +0 m",
                    0.0, area_m2, H, "B-EXAMPLE", "interim"])


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample-out"
    p = write(out)
    tables(out)
    chk = ifcopenshell.open(p)
    print("wrote", p)
    print("schema", chk.schema, "entities", len(list(chk)),
          "first id", min(e.id() for e in chk), "rooms", len(chk.by_type("IfcSpace")))
