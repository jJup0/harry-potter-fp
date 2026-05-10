"""Find score files that don't correspond to a current canonical character."""
import os
import sys

sys.path.insert(0, "src/collect")
from build_character_registry import KNOWN_CHARACTERS
import re

SCORE_DIR = "output/scores/comparative"

def safe_dirname(name):
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")

canonical_dirs = set(safe_dirname(k) for k in KNOWN_CHARACTERS.keys())

stale = []
for fname in sorted(os.listdir(SCORE_DIR)):
    if not fname.endswith(".json"):
        continue
    stem = fname[:-5]
    if stem not in canonical_dirs:
        stale.append(fname)

print(f"Stale score files (no longer canonical): {len(stale)}")
for f in stale:
    print(f"  {f}")
