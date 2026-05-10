#!/usr/bin/env python3
"""Find characters in characters.yaml that haven't been handled by KNOWN_CHARACTERS yet."""
import yaml
import sys

sys.path.insert(0, "src/collect")
from build_character_registry import KNOWN_CHARACTERS

with open("output/characters.yaml") as f:
    chars = yaml.safe_load(f)["characters"]

# All canonical names (lowercased)
canonical_set = set(k.lower() for k in KNOWN_CHARACTERS.keys())

# All alias targets (names that get merged into a canonical)
alias_targets = set()
for aliases in KNOWN_CHARACTERS.values():
    for a in aliases:
        alias_targets.add(a.lower())

print("Characters in characters.yaml NOT yet handled by KNOWN_CHARACTERS:")
print("(Need to be assigned as alias of something, or added as canonical)\n")

unhandled = []
for c in chars:
    name = c["name"]
    nl = name.lower()
    if nl not in canonical_set and nl not in alias_targets:
        unhandled.append(name)

for n in sorted(unhandled):
    print(f"  {n}")
print(f"\nTotal: {len(unhandled)}")
