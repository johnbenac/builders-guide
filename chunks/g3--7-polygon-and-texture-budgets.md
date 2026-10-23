<!-- chunk: g3--7-polygon-and-texture-budgets | source: 03-furniture-and-fixtures-guide.md | title: 7. Polygon and texture budgets | rules: F-50,F-51,F-52,F-53 -->
## 7. Polygon and texture budgets

**F-50 · REQUIRED** - Stay within the profile's limits for a whole delivery: `limits.maxFileMegabytes`, `limits.maxVertices`, `limits.maxTriangles`.

**F-51 · RECOMMENDED** - Keep each item small: at most `budgets.maxItemTriangles` triangles (default 2,000), far fewer for ordinary items. Do not model hidden undersides, fasteners or text.

**F-52 · RECOMMENDED** - Do not deliver textures with an item. Items take their look from the building's finish schedule (guide 2), keyed by class and colour. If a bespoke texture set is unavoidable, deliver it as a normal texture set (guide 2, section 4) and list it in the item description.

**F-53 · RECOMMENDED** - Use one or two surface colours on an ordinary item and up to four on a feature item; every distinct colour of every item adds a material.
