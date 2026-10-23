<!-- chunk: g1--6-walls-doors-windows-and-openings | source: 01-builders-and-architects-guide.md | title: 6. Walls, doors, windows and openings | rules: B-40,B-40a,B-41,B-42,B-43,B-44,B-45,B-46,B-47,B-48 -->
## 6. Walls, doors, windows and openings

**B-40 · REQUIRED** - Model walls as `IfcWall` (`IfcWallStandardCase` is also read), not as generic proxies; consumers select, colour and count by class.

**B-40a · RECOMMENDED** - Use one element per maximal straight run rather than one per room edge.

**B-41 · REQUIRED** - Model every door as an `IfcDoor` that fills an `IfcOpeningElement` in the wall, linked with `IfcRelVoidsElement` (wall to opening) and `IfcRelFillsElement` (opening to door). Tools find doorways, count them and work out which rooms they connect from the opening; a door with no opening is a picture on a solid wall.

**B-42 · REQUIRED** - Keep every doorway passable: its clear height is at least `geometry.doorMinClearHeightMetres`, and nothing solid (a sill, a bar, a glazed panel, furniture) crosses the opening centre line at the heights in `geometry.doorwayProbeHeightsMetres`. A door leaf may stand open or closed in the model, but do not rely on it to block movement.

**B-43 · RECOMMENDED** - Make doorways at least `geometry.doorMinClearWidthMetres` wide.

**B-44 · REQUIRED** - Model every window as an `IfcWindow` in an `IfcOpeningElement` linked with the voids and fills relations, so the wall is cut where the window is.

**B-45 · RECOMMENDED** - Give glass a surface style with opacity below 1 (about 0.4 to 0.6), so that every consumer shows it as see-through.

**B-46 · RECOMMENDED** - Give walls their real thickness; zero-thickness walls and double walls confuse area, collision and rendering.

**B-47 · RECOMMENDED** - Make every room reachable through a doorway, an open edge or a stair from a circulation room.

**B-48 · RECOMMENDED** - Do not put a door in a floor or roof; floor apertures are slab openings (B-53).
