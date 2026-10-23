<!-- chunk: readme--how-rules-are-written | source: README.md | title: How rules are written | rules: B-12,B-90 -->
## How rules are written

> **B-12 · REQUIRED** - The statement.
>
> **B-90 · REQUIRED · luminaires** - A statement that applies only in the named extension.

* **REQUIRED** means that without it a consumer is likely to refuse the file, lose the element, or read it wrongly, or (guide 4) that
  the delivery process requires it. A delivery that breaks a REQUIRED rule is sent back.
* **RECOMMENDED** means good practice that prevents a defect often seen or keeps work portable. A delivery that ignores it is accepted if
  everything REQUIRED passes, but the reviewer may ask for revision.
* The level shown is the **default**. A profile can raise, lower or switch off any rule (`ruleLevels`); `rules.json` and the checkers use
  the profile's level.
* Numbers are never in a rule's text as a requirement: they are profile parameters, written in `backticks` (`limits.maxTriangles`).

Identifier letters: **B** builders and architects, **D** decorators, **F** furniture and fixtures, **X** delivery and acceptance.
Numbers are never reused; a retired rule keeps its number.
