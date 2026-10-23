#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Intake step: rename declaration properties in an IFC file between the neutral names of these guides and the
names a particular consumer reads. The mapping file is kept by the receiving party, outside this set.

    python3 map_properties.py IN.ifc OUT.ifc --mapping MAPPING.json [--reverse]

MAPPING.json: {"propertyNames": {"CanonicalName": "ConsumerName", ...}, "propertyValues": {"CanonicalName": {"value": "consumer value"}}}
A consumer profile (profiles/profile.schema.json) has exactly these two keys, so a profile file can be used as the mapping.
Only the Name (and, for properties listed in propertyValues, the text value) of IfcPropertySingleValue lines is changed; every
other byte is kept. Without --reverse the neutral
names become consumer names; with --reverse the consumer names become neutral again (the round trip is byte-identical).
Stops with an error when the mapping is not one-to-one or when a target name already exists in the file.
"""
import argparse
import json
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--mapping", required=True)
ap.add_argument("--reverse", action="store_true")
a = ap.parse_args()

with open(a.mapping, encoding="utf-8") as fh:
    doc = json.load(fh)
names = doc.get("propertyNames", {})
values = doc.get("propertyValues", {})
if len(set(names.values())) != len(names):
    sys.exit("the mapping is not one-to-one")
fnames = dict(names)
if a.reverse:
    names = {v: k for k, v in names.items()}
    values = {fnames.get(k, k): {cv: v for v, cv in m.items()} for k, m in values.items()}
else:
    values = {k: dict(m) for k, m in values.items()}
with open(a.src, "rb") as fh:
    text = fh.read().decode("latin1")
simple = re.compile(r"^(#\d+=IFCPROPERTYSINGLEVALUE\(')([^']*)(')", re.M)
textval = re.compile(r"^(#\d+=IFCPROPERTYSINGLEVALUE\(')([^']*)(',\$,IFCTEXT\(')([^']*)(')", re.M)
present = {m.group(2) for m in simple.finditer(text)}
clash = sorted(t for s, t in names.items() if s in present and t in present)
if clash:
    sys.exit("target names already present in the file: " + ", ".join(clash[:5]))
count = 0


def sub(m):
    global count
    n = names.get(m.group(2))
    if n is None:
        return m.group(0)
    count += 1
    return m.group(1) + n + m.group(3)


def subv(m):
    vmap = values.get(m.group(2))
    if not vmap or m.group(4) not in vmap:
        return m.group(0)
    return m.group(1) + m.group(2) + m.group(3) + vmap[m.group(4)] + m.group(5)


out = textval.sub(subv, text)
out = simple.sub(sub, out)
with open(a.dst, "wb") as fh:
    fh.write(out.encode("latin1"))
print("renamed %d property name(s) in %s" % (count, a.dst))
