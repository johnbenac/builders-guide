---
name: decorate-interior
description: Define finishes for IFC buildings (wall coverings, floors, ceilings, accents, trims, glass) and deliver a reusable material library of texture sets and a finish schedule that any consumer can map to its own materials. Use when choosing colours for IFC elements, writing a finish schedule, authoring or checking texture sets (albedo, normal, orm), or when a check reports a D-rule finding.
license: CC-BY-4.0
metadata:
  version: "2.0.0"
  rules: "D-01 to D-85"
---

# Decorate an interior

Consumers differ in how they read surfaces, so the portable method is: give each finish its own colour and opacity in the IFC
(class, colour, opacity is the key), describe what each key means in a finish schedule, and deliver texture sets separately. Do not
rely on textures inside the IFC.

## Inputs

* The IFC master file (or the plan for one), and the `finishKeys` of its check report (every class, colour, opacity).
* The profile (`textures.*` values: map names, sizes, density, normal convention, tint modes) and any finishes the consumer already has.
* Python with `numpy` and `pillow` for the texture checker.

## Procedure

1. **Colour plan.** One distinct 8-bit colour per finish within a class; the same colour everywhere that finish is used (D-01, D-02).
   Treat the colour as a design tint (D-06). Keep the palette small (D-05). Opacity below 1 only for glass (D-04).
2. **Get the keys.** Run `check_ifc.py` and read `finishKeys` from the JSON report.
3. **Finish schedule.** Start from `templates/finish-schedule.template.json`. One `materials[]` entry per key; slabs and stairs use
   `top`, `side`, `bottom`; most classes use `all`. Add `floors[]` rules so every room floor is covered (D-10). Mark emissive parts
   `keep` (D-62). Validate against `schemas/finish-schedule.schema.json`.
4. **Texture sets.** A folder per set with the maps the profile lists, normally `albedo.png`, `normal.png`, `orm.png`, and `set.json`
   (D-40, D-41, D-43). Fixture: `python3 tools/make_sample_texture_set.py work/` writes a valid seamless set. 8-bit RGB PNG; albedo
   sRGB; normal tangent basis with the profile's green-channel convention; orm linear (R occlusion, G roughness, B metalness); square
   power-of-two size from `textures.sizesPixels`; tile size so density is inside `textures.densityPixelsPerMetre` (D-44, D-45).
5. **Check.** Each set: `python3 tools/check_texture_set.py SET_DIR --profile PROFILE.json --preview wrap.png --json`. Look at
   `wrap.png` (D-42).
6. **Library file.** Write `finishes/library.json` (`schemas/material-library.schema.json`) listing sets and the schedule.
7. **Provenance.** `finishes/SOURCES.csv` with asset, type, source, licence, notes for every set (D-80).
8. **Check all.** `python3 tools/check_all.py FINISHES_DIR --profile PROFILE.json --json`; repair per `REPAIR-LOOP.md`.

## Commands

```
python3 tools/check_all.py finishes/ --profile PROFILE.json --json --out report.json
python3 tools/check_texture_set.py finishes/textures/plaster_fine --preview wrap.png --json
python3 tools/check_ifc.py MASTER.ifc --finish-schedule finishes/finish-schedule.json --json
```

## Reading the report

D-03 `fail`: a (class, colour, opacity) has no schedule entry; the message names it. D-40, D-41, D-43 `fail`: a map is missing, has
the wrong encoding, or `tileMetres` is absent. D-42, D-44 to D-47 `warn`: quality advice with a fix hint.

## Stop conditions

* A needed finish does not exist and you cannot make it: say which key lacks a finish; do not reuse a wrong one.
* The licence of a source image is unknown: do not include it (D-80).
* Same finding after three runs: report it.

## Definition of done

`check_all.py` on the finishes folder and on the IFC with the schedule exits 0; the wrap preview was looked at; sources and licences
written.

## References (load on demand)

| Topic | File |
|---|---|
| all rules of this skill with fix hints | `references/rules.md` |
| how consumers read colour and class | `references/g2--1-how-consumers-decide-what-a-surface-looks-like.md` |
| colour rules | `references/g2--2-colour-rules.md` |
| floors, ceilings, coverings, trims, glass | `references/g2--3-floors-ceilings-wall-coverings-accents-and-tri.md` |
| texture set format | `references/g2--4-texture-sets.md` |
| finish schedule | `references/g2--5-the-finish-schedule.md` |
| palettes, libraries, defects | `references/g2--6-palettes.md`, `references/g2--7-delivering-a-reusable-material-library.md`, `references/g2--8-defects-commonly-seen.md` |
