# SPDX-License-Identifier: Apache-2.0
"""A small authoring kit for IFC4 buildings that follow the guide set's rules.

It holds the plumbing every building needs, so a project writes only its programme: levels, slabs, walls with openings, stairs
with correctly sized wells, pitched roofs, battered walls, rooms (internal and open-air) and their declaration properties.
Everything is deterministic: the same script writes the same bytes. z arguments are absolute metres; the kit stores them
relative to the level the element belongs to (`at(level)` chooses it).

    from ifc_author import Builder
    b = Builder("my-namespace", "Project", "Site", "Building", "B-ID")
    ground = b.level("Building - ground / +0 m", 0.0)
    b.at(ground)
    b.slab("slab/floor", "Floor", [b.box(0, 0, -0.3, 6, 5, 0.3, b.style("slab", "#c9c4b8"))])
    ...
    b.write("out", "master.ifc")

See tools/make_fixtures.py for three complete examples. Requires: pip install ifcopenshell
"""
import csv
import json
import math
import os
import re
import uuid

import ifcopenshell
import ifcopenshell.guid

FRAME_NOTE = "metres; +X forward; +Y left; +Z up; local z = 0 at the finished floor of the lowest level"


def _area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2.0


class Builder:
    def __init__(self, namespace, project, site, building, building_id, layer="permanent", level_offset=0.0, schema="IFC4",
                 occupant="Residence"):
        self.ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
        self.m = m = ifcopenshell.file(schema=schema)
        self.building_id, self.layer, self.level_offset, self.occupant = building_id, layer, level_offset, occupant
        self.levels, self.contained, self.rooms = [], [], []
        self.cur = {"elev": 0.0, "level": 0}
        self._styles = {}
        self.project = m.create_entity("IfcProject", GlobalId=self.gid("project"), Name=project)
        units = [m.create_entity("IfcSIUnit", UnitType=t, Name=n) for t, n in (
            ("LENGTHUNIT", "METRE"), ("AREAUNIT", "SQUARE_METRE"), ("VOLUMEUNIT", "CUBIC_METRE"), ("PLANEANGLEUNIT", "RADIAN"))]
        self.project.UnitsInContext = m.create_entity("IfcUnitAssignment", Units=units)
        ctx = m.create_entity("IfcGeometricRepresentationContext", None, "Model", 3, 1e-5, self._ax3())
        self.body = m.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body", ContextType="Model",
                                    ParentContext=ctx, TargetView="MODEL_VIEW")
        self.project.RepresentationContexts = [ctx]
        self.pset(self.project, "Pset_Declaration_Frame", {"FrameNote": FRAME_NOTE, "LevelOffsetMetres": level_offset})
        self.site = m.create_entity("IfcSite", GlobalId=self.gid("site"), Name=site, ObjectPlacement=self._place(), CompositionType="ELEMENT")
        self.building = m.create_entity("IfcBuilding", GlobalId=self.gid("building"), Name=building,
                                        ObjectPlacement=self._place(parent=self.site.ObjectPlacement), CompositionType="ELEMENT")
        m.create_entity("IfcRelAggregates", GlobalId=self.gid("agg/project"), RelatingObject=self.project, RelatedObjects=[self.site])
        m.create_entity("IfcRelAggregates", GlobalId=self.gid("agg/site"), RelatingObject=self.site, RelatedObjects=[self.building])
        self.pset(self.building, "Pset_Declaration_Building", {"BuildingId": building_id, "Layer": layer})

    # ------------------------------------------------------------------ identity and properties
    def gid(self, key):
        return ifcopenshell.guid.compress(uuid.uuid5(self.ns, key).hex)

    def _pt(self, *c):
        return self.m.create_entity("IfcCartesianPoint", Coordinates=[float(x) for x in c])

    def _dr(self, *c):
        return self.m.create_entity("IfcDirection", DirectionRatios=[float(x) for x in c])

    def _ax3(self, origin=(0, 0, 0), z=(0, 0, 1), x=(1, 0, 0)):
        return self.m.create_entity("IfcAxis2Placement3D", Location=self._pt(*origin), Axis=self._dr(*z), RefDirection=self._dr(*x))

    def _place(self, origin=(0, 0, 0), parent=None):
        return self.m.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=self._ax3(origin))

    def prop(self, name, value):
        m = self.m
        if isinstance(value, bool):
            v = m.create_entity("IfcBoolean", wrappedValue=value)
        elif isinstance(value, (int, float)):
            v = m.create_entity("IfcReal", wrappedValue=float(value))
        else:
            v = m.create_entity("IfcText", wrappedValue=str(value))
        return m.create_entity("IfcPropertySingleValue", Name=name, NominalValue=v)

    def pset(self, obj, set_name, values):
        ps = self.m.create_entity("IfcPropertySet", GlobalId=self.gid("pset/" + obj.GlobalId + "/" + set_name), Name=set_name,
                                  HasProperties=[self.prop(k, v) for k, v in values.items()])
        self.m.create_entity("IfcRelDefinesByProperties", GlobalId=self.gid("rel/" + obj.GlobalId + "/" + set_name),
                             RelatedObjects=[obj], RelatingPropertyDefinition=ps)

    def style(self, name, hexcol, opacity=1.0):
        if name not in self._styles:
            r, g, b = (int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
            rend = self.m.create_entity("IfcSurfaceStyleRendering", SurfaceColour=self.m.create_entity("IfcColourRgb", Red=r, Green=g, Blue=b),
                                        Transparency=round(1.0 - opacity, 6), ReflectanceMethod="NOTDEFINED")
            self._styles[name] = self.m.create_entity("IfcSurfaceStyle", Name=name, Side="BOTH", Styles=[rend])
        return self._styles[name]

    # ------------------------------------------------------------------ levels
    def level(self, name, elevation, ground_contact=False):
        """Add a level (IfcBuildingStorey) at `elevation` metres; `ground_contact` declares that it touches the terrain (B-141)."""
        i = len(self.levels)
        st = self.m.create_entity("IfcBuildingStorey", GlobalId=self.gid("storey%d" % i), Name=name, Elevation=float(elevation),
                                  ObjectPlacement=self._place((0, 0, elevation), self.building.ObjectPlacement), CompositionType="ELEMENT")
        self.levels.append(st)
        self.contained.append([])
        if ground_contact:
            self.pset(st, "Pset_Declaration_Level", {"GroundContact": True})
        return i

    def at(self, level):
        self.cur = {"elev": float(self.levels[level].Elevation), "level": level}

    # ------------------------------------------------------------------ solids (z absolute)
    def _solid(self, profile, z0, depth, st, position=None):
        solid = self.m.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, ExtrudedDirection=self._dr(0, 0, 1),
                                     Position=position or self._ax3((0, 0, z0 - self.cur["elev"])), Depth=float(depth))
        self.m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
        return solid

    def box(self, x0, y0, z0, dx, dy, dz, st):
        prof = self.m.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(dx), YDim=float(dy),
                                    Position=self.m.create_entity("IfcAxis2Placement2D", Location=self.m.create_entity(
                                        "IfcCartesianPoint", Coordinates=[x0 + dx / 2.0, y0 + dy / 2.0])))
        return self._solid(prof, z0, dz, st)

    def poly(self, points, z0, dz, st):
        """Upward extrusion of a plan polygon."""
        pts = list(points) if _area(points) > 0 else list(reversed(points))
        curve = self.m.create_entity("IfcPolyline", Points=[self.m.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y)])
                                                            for x, y in pts + [pts[0]]])
        return self._solid(self.m.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve), z0, dz, st)

    def prism(self, axis, points, start, length, st):
        """A section (u, z) swept along +x (axis 'x', u is y) or along +y (axis 'y', u is x), starting at `start`, `length` long.
        For roof slabs that follow a pitch, and for walls whose faces lean (battered walls)."""
        e = self.cur["elev"]
        pts = [(u, z - e) for u, z in points]
        if axis == "y":
            pts = [(-u, z) for u, z in pts]
        pts = pts if _area(pts) > 0 else list(reversed(pts))
        curve = self.m.create_entity("IfcPolyline", Points=[self.m.create_entity("IfcCartesianPoint", Coordinates=[float(u), float(z)])
                                                            for u, z in pts + [pts[0]]])
        prof = self.m.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve)
        if axis == "x":
            pos = self._ax3((start, 0, 0), z=(1, 0, 0), x=(0, 1, 0))
        else:
            pos = self._ax3((0, start, 0), z=(0, 1, 0), x=(-1, 0, 0))
        solid = self.m.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=pos, ExtrudedDirection=self._dr(0, 0, 1), Depth=float(length))
        self.m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
        return solid

    def _shape(self, solids):
        rep = self.m.create_entity("IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body",
                                   RepresentationType="SweptSolid", Items=solids)
        return self.m.create_entity("IfcProductDefinitionShape", Representations=[rep])

    # ------------------------------------------------------------------ elements
    def add(self, cls, key, name, solids, **kw):
        lv = self.cur["level"]
        e = self.m.create_entity(cls, GlobalId=self.gid(key), Name=name, ObjectPlacement=self._place(parent=self.levels[lv].ObjectPlacement),
                                 Representation=self._shape(solids) if solids else None, **kw)
        self.contained[lv].append(e)
        return e

    def slab(self, key, name, solids, kind="FLOOR"):
        return self.add("IfcSlab", key, name, solids, PredefinedType=kind)

    def footing(self, key, name, solids, kind="PAD_FOOTING"):
        return self.add("IfcFooting", key, name, solids, PredefinedType=kind)

    def opening(self, key, host, x0, y0, z0, dx, dy, dz, st):
        op = self.add("IfcOpeningElement", key, "Opening " + key, [self.box(x0, y0, z0, dx, dy, dz, st)], PredefinedType="OPENING")
        self.m.create_entity("IfcRelVoidsElement", GlobalId=self.gid("void/" + key), RelatingBuildingElement=host, RelatedOpeningElement=op)
        return op

    def _fill(self, wall, key, along, span, z0, openings, st_open, st_door, st_glass, leaf=0.06):
        """Cut and fill openings: (kind, start along the wall, width, sill, head) with kind 'door' or 'window'."""
        lo, hi = span
        for i, (kind, s, width, sill, head) in enumerate(openings):
            okey = "%s/o%d" % (key, i)
            mid = (lo + hi) / 2.0 - leaf / 2.0
            if along == "x":
                op = self.opening("opening/" + okey, wall, s, lo - 0.02, z0 + sill, width, hi - lo + 0.04, head - sill, st_open)
                lx, ly, lw, ld = s, mid, width, leaf
            else:
                op = self.opening("opening/" + okey, wall, lo - 0.02, s, z0 + sill, hi - lo + 0.04, width, head - sill, st_open)
                lx, ly, lw, ld = mid, s, leaf, width
            if kind == "door":
                e = self.add("IfcDoor", "door/" + okey, "Door " + okey, [self.box(lx, ly, z0 + sill, lw, ld, head - sill, st_door)],
                             OverallHeight=head - sill, OverallWidth=width, PredefinedType="DOOR", OperationType="SINGLE_SWING_LEFT")
            else:
                e = self.add("IfcWindow", "window/" + okey, "Window " + okey, [self.box(lx, ly, z0 + sill, lw, ld, head - sill, st_glass)],
                             OverallHeight=head - sill, OverallWidth=width, PredefinedType="WINDOW", PartitioningType="SINGLE_PANEL")
            self.m.create_entity("IfcRelFillsElement", GlobalId=self.gid("fill/" + okey), RelatingOpeningElement=op, RelatedBuildingElement=e)

    def wall(self, key, name, rect, height, style, openings=(), along="x", z0=None, opening_styles=None, object_type=None):
        """Axis-aligned wall from rect = (x0, y0, x1, y1), `height` high from z0 (default: the level's floor); `along` is the run axis
        used to position the openings. opening_styles = (opening, door, glass) surface styles."""
        z0 = self.cur["elev"] if z0 is None else z0
        x0, y0, x1, y1 = rect
        kw = {"ObjectType": object_type} if object_type else {}
        w = self.add("IfcWall", "wall/" + key, name, [self.box(x0, y0, z0, x1 - x0, y1 - y0, height, style)], PredefinedType="STANDARD", **kw)
        if openings:
            self._fill(w, key, along, (y0, y1) if along == "x" else (x0, x1), z0, openings, *opening_styles)
        return w

    def wall_prism(self, key, name, axis, section, start, length, style, openings=(), z0=None, opening_styles=None):
        """A wall whose cross-section is `section` (u, z) points, swept along `axis` from `start` for `length`: a battered wall
        (thick at the foot, thinner at the head) or a gable end. `z0` is only used to place openings."""
        w = self.add("IfcWall", "wall/" + key, name, [self.prism(axis, section, start, length, style)], PredefinedType="STANDARD")
        if openings:
            us = [u for u, _ in section]
            self._fill(w, key, "x" if axis == "x" else "y", (min(us), max(us)), self.cur["elev"] if z0 is None else z0, openings, *opening_styles)
        return w

    def gable_roof(self, key, name, rect, z_eave, rise, ridge_axis, style, thickness=0.25, overhang=0.4):
        """Two sloped roof slabs (IfcSlab ROOF) meeting at a central ridge that runs along `ridge_axis`; the underside is at z_eave above
        the walls (the rect faces) and `rise` higher at the ridge; the overhang continues the slope down. Returns the two slabs."""
        x0, y0, x1, y1 = rect
        out = []
        if ridge_axis == "x":
            lo, hi, mid, a, b = y0 - overhang, y1 + overhang, (y0 + y1) / 2.0, x0 - overhang, x1 + overhang
        else:
            lo, hi, mid, a, b = x0 - overhang, x1 + overhang, (x0 + x1) / 2.0, y0 - overhang, y1 + overhang
        half = mid - (y0 if ridge_axis == "x" else x0)         # half width between the walls
        zr = z_eave + rise
        z_lo = zr - rise * (mid - lo) / half
        z_hi = zr - rise * (hi - mid) / half
        for tag, (u0, z0_, u1, z1_) in (("a", (lo, z_lo, mid, zr)), ("b", (mid, zr, hi, z_hi))):
            sect = [(u0, z0_), (u1, z1_), (u1, z1_ + thickness), (u0, z0_ + thickness)]
            out.append(self.slab("%s/%s" % (key, tag), "%s %s" % (name, tag), [self.prism(ridge_axis, sect, a, b - a, style)], kind="ROOF"))
        return out

    # ------------------------------------------------------------------ stairs
    def _stair_solid(self, start, run, width, z_low, nt, tread, riser, st):
        up = (0.0, 0.0, 1.0)
        zv = (run[1] * up[2], -run[0] * up[2], 0.0)
        origin = (start[0] - zv[0] * width / 2.0, start[1] - zv[1] * width / 2.0, z_low - self.cur["elev"])
        pts = [(0.0, 0.0), (0.0, riser)]
        for k in range(1, nt + 1):
            pts += [(k * tread, k * riser)] if k == nt else [(k * tread, k * riser), (k * tread, (k + 1) * riser)]
        pts += [(nt * tread, (nt + 1) * riser), (nt * tread, 0.0)]
        clean = [p for i, p in enumerate(pts) if p != pts[i - 1]]
        curve = self.m.create_entity("IfcPolyline", Points=[self.m.create_entity("IfcCartesianPoint", Coordinates=[a, b]) for a, b in clean + [clean[0]]])
        prof = self.m.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve)
        solid = self.m.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=self._ax3(origin, z=zv, x=(run[0], run[1], 0.0)),
                                     ExtrudedDirection=self._dr(0, 0, 1), Depth=float(width))
        self.m.create_entity("IfcStyledItem", Item=solid, Styles=[st])
        return solid

    def stair_plan(self, rise, tread=0.28, max_riser=0.19):
        """(treads, riser) for a flight that climbs `rise` with risers no higher than `max_riser` (the profile's
        geometry.stairRiserLimitMetres); the last riser leads onto the upper floor."""
        n = int(math.ceil(rise / max_riser - 1e-9))
        return n - 1, rise / n

    def stair(self, key, name, start, run, width, z_low, rise, st, tread=0.28, max_riser=0.19):
        """A straight IfcStairFlight whose foot is the plan point `start`, running along the unit vector `run`; returns the flight."""
        nt, riser = self.stair_plan(rise, tread, max_riser)
        return self.add("IfcStairFlight", "stair/" + key, name, [self._stair_solid(start, run, width, z_low, nt, tread, riser, st)],
                        NumberOfRisers=nt + 1, NumberOfTreads=nt, RiserHeight=riser, TreadLength=tread, PredefinedType="STRAIGHT")

    def stair_well(self, start, run, width, z_low, rise, ceiling_z, tread=0.28, max_riser=0.19, headroom=2.0):
        """The plan rectangle (x0, y0, x1, y1) a slab must be cut away over a flight, from the first tread that has less than
        `headroom` (the profile's geometry.stairHeadroomMetres) under the slab underside `ceiling_z` up to the top of the flight."""
        nt, riser = self.stair_plan(rise, tread, max_riser)
        k0 = next((k for k in range(1, nt + 1) if z_low + k * riser + headroom > ceiling_z), nt + 1)
        s0, s1 = (k0 - 1) * tread, nt * tread
        a = (start[0] + run[0] * s0, start[1] + run[1] * s0)
        b = (start[0] + run[0] * s1, start[1] + run[1] * s1)
        hw = width / 2.0
        xs = [a[0] - abs(run[1]) * hw, a[0] + abs(run[1]) * hw, b[0] - abs(run[1]) * hw, b[0] + abs(run[1]) * hw]
        ys = [a[1] - abs(run[0]) * hw, a[1] + abs(run[0]) * hw, b[1] - abs(run[0]) * hw, b[1] + abs(run[0]) * hw]
        return min(xs), min(ys), max(xs), max(ys)

    # ------------------------------------------------------------------ rooms
    def room(self, rid, name, function, outline, finish, style, circulation=False, height=2.65, external=False, notes=None):
        """A room (IfcSpace) over a plan outline from the level's floor up `height`. `external` makes an open-air room (terrace,
        courtyard, deck): PredefinedType EXTERNAL and Enclosed false (B-143)."""
        lv, e = self.cur["level"], self.cur["elev"]
        sp = self.m.create_entity("IfcSpace", GlobalId=self.gid("room/" + rid), Name=name, LongName=name,
                                  ObjectPlacement=self._place(parent=self.levels[lv].ObjectPlacement),
                                  Representation=self._shape([self.poly(outline, e, height, style)]),
                                  PredefinedType="EXTERNAL" if external else "INTERNAL", ElevationWithFlooring=0.0, CompositionType="ELEMENT")
        self.m.create_entity("IfcRelAggregates", GlobalId=self.gid("agg/" + rid), RelatingObject=self.levels[lv], RelatedObjects=[sp])
        area = round(abs(_area(outline)), 3)
        props = {"RoomId": rid, "Occupant": self.occupant,
                 "Function": ("Circulation - " if circulation else "") + function, "NetAreaSquareMetres": area,
                 "BaseLevelMetres": e, "ClearHeightMetres": height, "Enclosed": not external, "Finish": finish}
        if notes:
            props["Notes"] = notes
        self.pset(sp, "Pset_Declaration_Room", props)
        self.rooms.append({"id": rid, "name": name, "level": lv, "area": area, "height": height, "external": external,
                           "occupant": props["Occupant"]})
        return sp

    # ------------------------------------------------------------------ output
    def finish(self):
        self.m.create_entity("IfcRelAggregates", GlobalId=self.gid("agg/building"), RelatingObject=self.building, RelatedObjects=self.levels)
        for lv, items in enumerate(self.contained):
            if items:
                self.m.create_entity("IfcRelContainedInSpatialStructure", GlobalId=self.gid("contain/storey%d" % lv),
                                     RelatingStructure=self.levels[lv], RelatedElements=items)

    def write(self, out_dir, filename, author="Author", organisation="Organisation", stamp="2026-01-01T00:00:00", entity_start=None):
        self.finish()
        os.makedirs(os.path.join(out_dir, "ifc"), exist_ok=True)
        text = self.m.to_string()
        head, data = text.split("DATA;", 1)
        head = re.sub(r"FILE_NAME\(.*\);", "FILE_NAME('%s','%s',('%s'),('%s'),'ifcopenshell','ifcopenshell','');" % (
            filename, stamp, author, organisation), head)
        if entity_start:
            assert "#" not in re.sub(r"#\d+", "", data), "unexpected '#' in a string"
            data = re.sub(r"#(\d+)", lambda g: "#%d" % (int(g.group(1)) + entity_start - 1), data)
        path = os.path.join(out_dir, "ifc", filename)
        with open(path, "w", newline="\n") as fh:
            fh.write(head + "DATA;" + data)
        return path

    def tables(self, out_dir, ifc_path="ifc/master.ifc"):
        """tables/rooms.csv and tables/building.json (guide 4)."""
        os.makedirs(os.path.join(out_dir, "tables"), exist_ok=True)
        names = [s.Name for s in self.levels]
        with open(os.path.join(out_dir, "tables", "rooms.csv"), "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["roomId", "name", "occupant", "kind", "enclosed", "level", "levelElevationMetres", "floorAreaM2", "clearHeightM",
                        "buildingId", "layer"])
            for r in self.rooms:
                w.writerow([r["id"], r["name"], r["occupant"], "open" if r["external"] else "room", "no" if r["external"] else "yes",
                            names[r["level"]], float(self.levels[r["level"]].Elevation), r["area"], r["height"], self.building_id, self.layer])
        meta = {"format": "building-metadata/1", "building": {"id": self.building_id, "name": self.building.Name, "layer": self.layer},
                "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": self.level_offset},
                "ifc": {"path": ifc_path, "schema": "IFC4"},
                "levels": [{"name": s.Name, "elevationMetres": float(s.Elevation), "rooms": sum(1 for r in self.rooms if r["level"] == i)}
                           for i, s in enumerate(self.levels)],
                "occupants": sorted({r["occupant"] for r in self.rooms}),
                "counts": {"rooms": len(self.rooms), "walls": len(self.m.by_type("IfcWall")), "doors": len(self.m.by_type("IfcDoor")),
                           "windows": len(self.m.by_type("IfcWindow")), "stairFlights": len(self.m.by_type("IfcStairFlight"))}}
        with open(os.path.join(out_dir, "tables", "building.json"), "w") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")
