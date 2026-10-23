<!-- chunk: params--extensions | source: 07-profile-parameters.md | title: Extensions | rules: - -->
## Extensions

An extension is an optional group of rules. It applies only when `extensions.<name>.enabled` is true: `walkability` (for consumers that place people or agents in rooms), `luminaires` (fixtures become lights), `signboards` (signs are generated from declared boards), `furnitureCollision` (furniture is approximated by a simple collider). Rules that belong to an extension carry its name after the level, for example `B-90 REQUIRED luminaires`, and `rules.json` lists it in `extension`.
