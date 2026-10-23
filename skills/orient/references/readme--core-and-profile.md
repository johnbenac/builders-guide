<!-- chunk: readme--core-and-profile | source: README.md | title: Core and profile | rules: - -->
## Core and profile

* **Core rules** say what is good practice for any consumer and what goes wrong for any consumer if you ignore it.
* **Profile parameters** hold everything numeric or consumer-specific: size and triangle limits, identifier lengths, clearances,
  property names, whether room identifiers are mandatory, and which optional extensions apply. See
  [07-profile-parameters.md](07-profile-parameters.md).
* **Extensions** (`walkability`, `luminaires`, `signboards`, `furnitureCollision`, `terrain`) are optional rule groups a profile switches on.

Check anything against a profile: `python3 tools/check_all.py PATH --profile consumer.json --json`. Reports name the profile used.
