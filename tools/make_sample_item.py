#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the worked-example item (guide 3): a 1.6 m work table as a stand-alone library item.

    python3 make_sample_item.py OUT_DIR

Writes OUT_DIR/items/table.work.1600/table.work.1600.ifc and table.work.1600.item.json. The item sits at the origin
with its lowest point on z = 0 and its pivot at the centre of its footprint. Deterministic.

Requires: pip install ifcopenshell
"""
import json
import os
import re
import sys
import uuid

import ifcopenshell
import ifcopenshell.guid

NS = uuid.UUID("cd93845e-524b-5f8c-8303-620aae92d05b")
m = ifcopenshell.file(schema="IFC4")


def gid(k):
    return ifcopenshell.guid.compress(uuid.uuid5(NS, k).hex)


def pt(*c):
    return m.create_entity("IfcCartesianPoint", Coordinates=[float(x) for x in c])


def dr(*c):
    return m.create_entity("IfcDirection", DirectionRatios=[float(x) for x in c])


def ax3(o=(0, 0, 0)):
    return m.create_entity("IfcAxis2Placement3D", Location=pt(*o), Axis=dr(0, 0, 1), RefDirection=dr(1, 0, 0))


project = m.create_entity("IfcProject", GlobalId=gid("project"), Name="Item library: table.work.1600")
units = [m.create_entity("IfcSIUnit", UnitType=u, Name=n) for u, n in (
    ("LENGTHUNIT", "METRE"), ("AREAUNIT", "SQUARE_METRE"), ("VOLUMEUNIT", "CUBIC_METRE"), ("PLANEANGLEUNIT", "RADIAN"))]
project.UnitsInContext = m.create_entity("IfcUnitAssignment", Units=units)
ctx = m.create_entity("IfcGeometricRepresentationContext", None, "Model", 3, 1e-5, ax3())
body = m.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body", ContextType="Model", ParentContext=ctx,
                       TargetView="MODEL_VIEW")
project.RepresentationContexts = [ctx]

r, g, b = (int(c, 16) / 255.0 for c in ("cc", "bb", "a0"))
st = m.create_entity("IfcSurfaceStyle", Name="table oak", Side="BOTH", Styles=[m.create_entity(
    "IfcSurfaceStyleRendering", SurfaceColour=m.create_entity("IfcColourRgb", Red=r, Green=g, Blue=b), Transparency=0.0,
    ReflectanceMethod="NOTDEFINED")])
prof = m.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=1.6, YDim=0.8,
                       Position=m.create_entity("IfcAxis2Placement2D", Location=m.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0])))
solid = m.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=ax3(), ExtrudedDirection=dr(0, 0, 1), Depth=0.74)
m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
shape = m.create_entity("IfcProductDefinitionShape", Representations=[m.create_entity(
    "IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])])
item = m.create_entity("IfcFurnishingElement", GlobalId=gid("item"), Name="Work table, 1.6 m", ObjectType="table",
                       ObjectPlacement=m.create_entity("IfcLocalPlacement", RelativePlacement=ax3()), Representation=shape)
props = [m.create_entity("IfcPropertySingleValue", Name=k, NominalValue=m.create_entity("IfcText", wrappedValue=v))
         for k, v in (("ItemId", "table.work.1600"), ("ItemVersion", "1.0.0"), ("Role", "work table"))]
ps = m.create_entity("IfcPropertySet", GlobalId=gid("pset"), Name="Pset_Declaration_Item", HasProperties=props)
m.create_entity("IfcRelDefinesByProperties", GlobalId=gid("rel"), RelatedObjects=[item], RelatingPropertyDefinition=ps)

out = sys.argv[1] if len(sys.argv) > 1 else "sample-out"
d = os.path.join(out, "items", "table.work.1600")
os.makedirs(d, exist_ok=True)
text = m.to_string()
text = re.sub(r"FILE_NAME\(.*\);", "FILE_NAME('table.work.1600.ifc','2026-10-22T00:00:00',('Example author'),"
              "('Example organisation'),'ifcopenshell','ifcopenshell','');", text, count=1)
with open(os.path.join(d, "table.work.1600.ifc"), "w", newline="\n") as fh:
    fh.write(text)
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "..", "templates", "item.template.json"), encoding="utf-8") as fh:
    desc = json.load(fh)
desc["provenance"] = {"author": "Example organisation", "licence": "Free to reuse (example)", "source": "original"}
with open(os.path.join(d, "table.work.1600.item.json"), "w", newline="\n") as fh:
    json.dump(desc, fh, indent=2)
    fh.write("\n")
print("wrote", d)
