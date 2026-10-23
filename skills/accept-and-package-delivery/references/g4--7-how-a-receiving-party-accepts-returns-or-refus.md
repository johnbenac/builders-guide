<!-- chunk: g4--7-how-a-receiving-party-accepts-returns-or-refus | source: 04-delivery-and-acceptance-guide.md | title: 7. How a receiving party accepts, returns or refuses | rules: X-60 -->
## 7. How a receiving party accepts, returns or refuses

### 7.1 Outcomes

| Outcome | When | What the sender receives |
|---|---|---|
| **Accepted** | every check in section 5 passes and review finds nothing to change | a confirmation naming the delivery id, version and the master file's hash |
| **Accepted with notes** | every REQUIRED rule passes, and the reviewer lists RECOMMENDED rules or defects worth fixing later | the same confirmation plus a findings list |
| **Revision needed** | one or more REQUIRED rules fail, or a defect makes the work unusable, but the delivery is otherwise sound | a findings list (section 7.3); the sender sends a new version |
| **Rejected** | the package cannot be used as it stands: a hash does not match, the file cannot be read, the schema or units are wrong, a hard limit is exceeded, the licence is missing or does not allow use, or the work was built to the wrong profile | the reason, and what to do before sending anything again |

### 7.2 Steps

1. **Intake.** Package checks (hashes, layout, manifest, provenance, licence). A failure here is a rejection or an immediate return, because nothing else can be trusted.
2. **Reading and identity.** The master file is read; units, limits, identifiers.
3. **Rule data.** For any new `Occupant` string or room-id prefix in the room table, the receiving party adds its classification rules, and renames declaration properties to its own names with `tools/map_properties.py` and a mapping file it keeps itself (a profile's `propertyNames` and `propertyValues` are exactly that mapping). The sender's file stays neutral.
4. **Build and check.** The receiving party builds from the files and runs the checks of section 5.2.
5. **Review.** A person looks at finishes and wrap, signs, lighting, furniture clearances, and anything the scripts only estimate.
6. **Outcome.** One of the four outcomes above.

### 7.3 Findings and revision

The receiving party sends findings in the shape of section 5.1: the rule, its level, the product's `GlobalId`, and what was measured against what was expected. The sender answers each REQUIRED finding with a fix or a reason.

**X-60 · RECOMMENDED** - When you send a revision, change only what the findings and your own notes name, bump the version (section 4), list what changed in `notes/changes.md`, and keep every unchanged identifier. A revision that renames identifiers without being asked is a MAJOR change and is reviewed again from the start.

### 7.4 After acceptance

An accepted version is held by its hashes. If you later replace a building, deliver a new version of the master file that keeps the identifiers of everything that stays; references the receiving party holds (which room is a start room, which sign belongs to which building) then keep working. Nothing in an accepted version is edited by the receiving party: if it needs a change, it asks for a new version.
