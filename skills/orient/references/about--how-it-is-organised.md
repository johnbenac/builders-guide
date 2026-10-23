<!-- chunk: about--how-it-is-organised | source: ABOUT.md | title: How it is organised | rules: - -->
## How it is organised

The set separates **core practice** from **consumer parameters**.

* **Core** is what is good practice for any consumer: a declared unit, a stated frame, levels, rooms with real floors, doors that
  fill openings, unique identifiers, honest materials, a manifest with hashes and licences. Core rules say *what goes wrong for any
  consumer* if you ignore them.
* **Parameters** are everything numeric or consumer-specific: size and triangle limits, identifier lengths, clearance values, whether
  room identifiers are mandatory, which optional extensions apply. They live in a **profile**, a small JSON file
  (`profiles/profile.schema.json`). `profiles/default.json` has publicly defensible defaults; `profiles/example-strict.json` shows a
  constrained consumer. Rules in `rules.json` name the parameters they use.
* A **consumer profile** is simply a profile a consumer publishes. Authors and agents build to it and check against it:
  `python3 tools/check_all.py PATH --profile consumer.json --json`. Reports state which profile they used.
