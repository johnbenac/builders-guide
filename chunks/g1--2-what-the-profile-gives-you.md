<!-- chunk: g1--2-what-the-profile-gives-you | source: 01-builders-and-architects-guide.md | title: 2. What the profile gives you | rules: - -->
## 2. What the profile gives you

Before you start, get the profile of the consumer you build for. If you have none, use `profiles/default.json` and say so in
your delivery notes. If a number your work depends on is missing, ask the consumer; do not guess.

| Profile item | What it tells you | Parameters |
|---|---|---|
| frame | which way +X and +Y point, the height of your local z = 0 in the consumer's frame, whether the file is placed as authored | `frame.horizontalAxes`, `frame.levelOffsetMetres`, `frame.placement` |
| limits and budgets | hard caps and recommended sizes | `limits.*`, `budgets.*` |
| identifiers | room identifier length and pattern, assigned entity-number range, allowed occupants | `identifiers.*`, `propertyNames` |
| geometry | doorway, stair and ramp values | `geometry.*` |
| volumes | the region to stay inside, regions to keep out, floors the consumer supplies | `buildVolume`, `keepOut`, `baseSurfaces` |
| extensions | whether it walks people through rooms, turns fixtures into lights, generates signs, simplifies furniture, supplies terrain | `extensions.*` |
| rule levels | rules it makes stricter or switches off | `ruleLevels` |
