# SPDX-License-Identifier: Apache-2.0
"""The one list of files that make up the set, shared by gen_all.py (MANIFEST.json, MANIFEST.sha256), build_dist.py (the zip) and
test_sync.py, so that they cannot disagree.

The set is every file under the top folder except version-control and cache folders, any folder whose name starts with a dot
(virtual environments, tool caches), `work/` (scratch output, git-ignored), `dist/` (hand-over files, listed separately) and
compiled Python. `MANIFEST.sha256` is the checksum list itself and is not in it.
"""
import hashlib
import os

EXCLUDE_DIRS = {"__pycache__", "dist", "work", "node_modules"}
CHECKSUM_FILE = "MANIFEST.sha256"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def set_files(root):
    """Relative paths (forward slashes, sorted) of every file of the set except MANIFEST.sha256."""
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("."))
        for n in names:
            rel = os.path.relpath(os.path.join(base, n), root).replace(os.sep, "/")
            if rel != CHECKSUM_FILE and not rel.endswith(".pyc"):
                out.append(rel)
    return sorted(out)


def dist_files(root):
    """The hand-over documents in dist/ that MANIFEST.sha256 also covers."""
    d = os.path.join(root, "dist")
    if not os.path.isdir(d):
        return []
    return sorted("dist/" + n for n in os.listdir(d) if n.endswith((".html", ".pdf")))


def checksum_text(root):
    """The content of MANIFEST.sha256: the hash of every file of the set and of the hand-over documents."""
    return "".join("%s  %s\n" % (sha256_file(os.path.join(root, rel)), rel) for rel in set_files(root) + dist_files(root))
