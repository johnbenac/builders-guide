<!-- chunk: g2--2-colour-rules | source: 02-interior-decorators-guide.md | title: 2. Colour rules | rules: D-01,D-02,D-03,D-04,D-05,D-06,D-07,D-08 -->
## 2. Colour rules

**D-01 · REQUIRED** - Give each distinct finish its own colour within an element class. The schedule keys finishes by (class, colour, opacity); two finishes with the same key are one finish. Colours that differ by less than 1/255 in every channel are the same colour.

**D-02 · REQUIRED** - Give the same finish the same colour and opacity on every element that uses it. A small drift (from re-rounding in another tool) creates a new key that has no schedule entry.

**D-03 · REQUIRED** - When you deliver a finish schedule, include an entry for every (class, colour, opacity) combination that appears in your IFC files. The checker lists them (`finishKeys`).

**D-04 · RECOMMENDED** - Use opacity below 1 only for glass and other see-through things (about 0.4 to 0.6 for glazing). Consumers treat anything with an opacity below 1 as see-through. A walkable glass floor is a slab with a glass colour and opacity.

**D-05 · RECOMMENDED** - Keep the palette small: at most `budgets.maxDistinctColours` combinations (default 50). Every combination is one more material to map, load and draw.

**D-06 · RECOMMENDED** - Treat the IFC colour as a design tint: the schedule says how strongly it is blended into the texture (0 means the texture alone, 1 the colour fully). Pick a colour near the intended look, not a code colour such as pure red.

**D-07 · RECOMMENDED** - Avoid pure black, pure white and very dark large surfaces: they clip or disappear under typical lighting. Keep large floors and walls between about 0.25 and 0.85 in mean linear luminance unless a dark look is the point.

**D-08 · RECOMMENDED** - Choose neutral tints for fabrics; strongly coloured tints shift under lighting.
