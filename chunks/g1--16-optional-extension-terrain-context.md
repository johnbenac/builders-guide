<!-- chunk: g1--16-optional-extension-terrain-context | source: 01-builders-and-architects-guide.md | title: 16. Optional extension: terrain context | rules: - -->
## 16. Optional extension: terrain context

Some consumers place a building in a world whose ground comes from their own terrain source. There the terrain stays authoritative in
the source. In IFC it is **derived, read-only context**: a terrain element built from a patch the source gives you, used for
placement, clash and "is the building floating or buried" checks. The extension applies when `extensions.terrain.enabled` is true;
its numbers are in `extensions.terrain.*`.

The work flows like this:

1. **Send** the source three things: the building footprint polygon, the finished floor elevation (height above sea level of the lowest
   finished floor) and a grading rule (`extensions.terrain.grading`, for example cut and fill slopes no steeper than 1:2). `tools/site_request.py` writes them from the master file.
2. **Receive** a height patch: a GeoTIFF with one float32 band in metres, cut round the building with a margin, at one source level
   (one pixel size), and a JSON sidecar (`schemas/terrain-patch.schema.json`) with the source package version and hash, origin, pixel size, CRS
   definition, vertical datum and licence. The source grades the pad and clears vegetation inside the footprint plus a margin
   (`extensions.terrain.clearingMarginMetres`). Its baseline ground is natural, with no built features; the building is an overlay
   layer and never part of the terrain.
3. **Import** with `tools/terrain_import.py`: it reduces the samples to a triangulated network within a stated error bound, converts
   to the file frame and writes the elements the rules below describe.
4. **Check** with `check_ifc.py` and a profile that enables the extension.

Say which frame each number is in:

| Where | Frame |
|---|---|
| sidecar and site request | site frame: x east, y north, z up, metres, centred on the site; heights above mean sea level, with sea level exactly 0 |
| IFC file | file frame: x east, y north (the site frame shifted by the building origin), z measured from the lowest finished floor |
| the consumer's own runtime | whatever it uses (for example x east, y up, z south); the consumer converts, you never write it |

The site frame is a custom azimuthal frame on a sphere, not a registry code. `IfcProjectedCRS.Name` carries the profile's name for it
(`extensions.terrain.crsName`) and `Description` carries the definition from the sidecar.
