<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Contributing

Thank you for helping. Changes are welcome as proposals with a reason and, for a new rule, an example of the problem it prevents in
some consumer.

## What to propose

* A **rule**: state what goes wrong for which kind of consumer if it is ignored, the check (script or review), and a fix hint. Put
  anything numeric in a profile parameter, not in the rule text. New rules start `RECOMMENDED`.
* A **parameter**: add it to `profiles/profile.schema.json` with a description and to `profiles/default.json` with a defensible value.
* A **tool change**: keep `--json` output and exit codes stable (`schemas/check-report.schema.json`).
* A **correction**: wrong, unclear or out-of-date text.

## How to change things

1. Edit the guides (`01`-`05`), `tools/rules_meta.json`, profiles, schemas, templates, skills or tools. Do not edit generated files
   (`rules.json`, `06-rules-index.md`, `07-profile-parameters.md`, `chunks/`, `llms.txt`, `llms-full.txt`, `skills/*/references/`,
   `MANIFEST.json`).
2. Regenerate: `python3 tools/gen_all.py --write`.
3. Run the tests: `python3 tools/test_sync.py`, `python3 tools/selftest.py` and `python3 tools/agent_harness.py`
   (`pip install -r tools/requirements.txt` first).
4. Add a line to `CHANGELOG.md` and follow `VERSIONING.md`.

## Style

* Plain language, short sentences. Rules are one imperative sentence followed by why it matters.
* Describe requirements as what any consumer needs; refer to "the consumer" and "the profile", never to a particular product, vendor,
  project or site. Examples and fixtures use neutral content only.
* Do not cite or claim conformance to any standard, and do not claim endorsement by any body.
* Keep each skill under 400 lines and each chunk under about 1,500 tokens.

## Licence of contributions

Contributions are accepted under the licences of the set (see `LICENSE.md`): text under CC BY 4.0, code and machine-readable files
under Apache-2.0. By contributing you confirm you have the right to do so.
