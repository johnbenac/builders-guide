<!-- chunk: g3--1-what-consumers-do-with-an-item | source: 03-furniture-and-fixtures-guide.md | title: 1. What consumers do with an item | rules: - -->
## 1. What consumers do with an item

An item reaches a consumer as an element inside a building's master IFC file. What happens next differs, but these things are common:

| Stage | What typically happens | Consequence for you |
|---|---|---|
| Reading | the class of the element and its geometry are read; declaration properties are read by name | use the right class (section 2) |
| Material | class, colour and opacity select a finish (guide 2) | distinct finish, distinct colour |
| Collision | furniture is approximated by a simple shape, often **one axis-aligned box** around the element, while fixed equipment may collide as exact triangles | a chair can be a solid block; do not rely on walking under a table. The profile states the mode (`extensions.furnitureCollision`) |
| Standing points | simulators keep a start point clear of furniture by a margin | leave free floor (guide 1, B-33, with the walkability extension) |
| Interaction | most consumers have no sit points, drawers or moving parts for IFC items | item data beyond the model is for placement tools |

An **item library** is a folder of single-item IFC files plus a description file per item. A building author places items into
the master file as instances (section 8).
