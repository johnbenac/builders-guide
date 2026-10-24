<!-- chunk: readme--for-agents | source: README.md | title: For agents | rules: - -->
## For agents

The set is also written to be read and run by software agents of any kind. Static files only; no service is needed.

| File | Use |
|---|---|
| [AGENTS.md](AGENTS.md) | short entry point: what the set is, commands, working rules |
| `llms.txt`, `llms-full.txt` | index of the set, and all content in marked chunks |
| `skills/` | six skills (orient, author-building, decorate-interior, author-furniture-library, accept-and-package-delivery, submit-delivery), each with a short `SKILL.md` and on-demand `references/` |
| `rules.json` | all rules with level, applies_to, parameters, extension, how to check, fix hint, examples |
| [REPAIR-LOOP.md](REPAIR-LOOP.md) | run, read findings, fix, rerun until no REQUIRED finding remains |
| `profiles/` | the profile schema, the default profile, and an example of a strict consumer profile |
| `chunks/`, `MANIFEST.json` | the guides in pieces of about 1,500 tokens or less; every file with purpose and tags |
| `schemas/` | JSON Schemas: profile, rules, checker report, delivery manifest, submission block, proof manifest, catalogue, material library, furniture item, building summary, finish schedule |
