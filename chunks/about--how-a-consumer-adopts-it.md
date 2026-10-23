<!-- chunk: about--how-a-consumer-adopts-it | source: ABOUT.md | title: How a consumer adopts it | rules: - -->
## How a consumer adopts it

1. Copy `profiles/default.json` to `my-consumer.json`; set `name` and `version`.
2. Change the numbers that differ for you: `limits`, `budgets`, `identifiers`, `geometry`, `frame`, `buildVolume`, `keepOut`.
3. If your reader looks for particular property names or values, list them in `propertyNames` and `propertyValues`. Authors keep the
   neutral names; `python3 tools/map_properties.py in.ifc out.ifc --mapping my-consumer.json` renames them for you.
4. Make rules stricter (or switch them off) in `ruleLevels`; for example make `B-26` (room identifiers) `required`.
5. Switch on the extensions you implement: `walkability`, `luminaires`, `signboards`, `furnitureCollision`, `terrain`.
6. Validate the file against `profiles/profile.schema.json` and publish it at a stable address. Tell authors its name and version.
7. When you receive a delivery, run `check_all.py` with your profile; send findings back as they are (rule, element, fix hint).
