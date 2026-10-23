<!-- chunk: g1--7-floors-roofs-ceilings-and-slab-openings | source: 01-builders-and-architects-guide.md | title: 7. Floors, roofs, ceilings and slab openings | rules: B-50,B-51,B-51a,B-52,B-53,B-54,B-55 -->
## 7. Floors, roofs, ceilings and slab openings

**B-50 · RECOMMENDED** - Model every walkable floor, including walkable roofs, as an `IfcSlab` (`FLOOR` or `ROOF`) whose top face is the finished floor. Rooms standing on a floor the consumer supplies (`baseSurfaces`) need no slab of their own. Glass floors are slabs with a glass-like colour and opacity. A consumer that checks standing points or floor contact raises this to required.

**B-51 · RECOMMENDED** - Do not duplicate a floor the consumer already provides (`baseSurfaces`); two coplanar surfaces flicker.

**B-51a · RECOMMENDED** - Omit slabs that rest directly on a consumer-supplied floor, or make them very thin.

**B-52 · RECOMMENDED** - Give slabs a realistic thickness; very thin slabs are fine only for surface layers such as paving.

**B-53 · REQUIRED** - Cut every hole in a slab (stair wells, shafts, service drops) as an `IfcOpeningElement` linked by `IfcRelVoidsElement`, not as separate floor pieces that merely leave a gap.

**B-54 · RECOMMENDED** - Model ceilings or roofs. Many consumers draw no ceiling unless there is geometry; a room with nothing above it reads as open-topped. A ceiling is the underside of a slab or an `IfcCovering`.

**B-55 · RECOMMENDED** - Keep your own structure clear of openings in surfaces the consumer supplies (`baseSurfaces`), with the margin the profile states.
