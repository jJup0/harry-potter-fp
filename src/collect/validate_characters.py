#!/usr/bin/env python3
"""
Validate project characters against the Wikipedia canonical list.
Flags any character in our registry that doesn't appear on Wikipedia.

Usage:
  python3 src/collect/validate_characters.py
"""
import json
import os
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "v2", "characters.yaml")
WIKIPEDIA_FILE = os.path.join(PROJECT_ROOT, "data", "reference", "wikipedia_hp_characters.json")

# Import alias map from registry
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_character_registry import KNOWN_CHARACTERS


def load_wikipedia_names():
    """Load all canonical + alt names from Wikipedia JSON."""
    with open(WIKIPEDIA_FILE) as f:
        data = json.load(f)
    names = set()
    for char in data["characters"]:
        names.add(char["name"].lower())
        for alt in char.get("alt_names", []):
            names.add(alt.lower())
    return names


def load_our_characters():
    """Load character names from our registry."""
    with open(CHARACTERS_FILE) as f:
        data = yaml.safe_load(f)
    return [c["name"] for c in data["characters"]]


def build_known_names_set():
    """Build set of all known canonical names + aliases (lowercased)."""
    names = set()
    for canonical, aliases in KNOWN_CHARACTERS.items():
        names.add(canonical.lower())
        for a in aliases:
            names.add(a.lower())
    return names


def main():
    wiki_names = load_wikipedia_names()
    our_chars = load_our_characters()
    known = build_known_names_set()

    print(f"Wikipedia characters: {len(wiki_names)} names (including alts)")
    print(f"Our characters: {len(our_chars)}")
    print()

    # Flag characters not on Wikipedia
    not_on_wiki = []
    for name in our_chars:
        if name.lower() in wiki_names:
            continue
        # Check if any known canonical maps to a wiki name
        found = False
        for canonical, aliases in KNOWN_CHARACTERS.items():
            if name.lower() == canonical.lower() or name.lower() in [a.lower() for a in aliases]:
                if canonical.lower() in wiki_names:
                    found = True
                    break
        if not found:
            not_on_wiki.append(name)

    if not_on_wiki:
        print(f"FLAGGED: {len(not_on_wiki)} characters NOT on Wikipedia list:")
        for name in sorted(not_on_wiki):
            print(f"  - {name}")
    else:
        print("All characters match Wikipedia list.")

    print()

    # Also show Wikipedia characters we DON'T have
    our_lower = {n.lower() for n in our_chars}
    our_lower.update(known)
    missing_from_us = []
    with open(WIKIPEDIA_FILE) as f:
        wiki_data = json.load(f)
    for char in wiki_data["characters"]:
        name = char["name"]
        if name.lower() not in our_lower:
            # Check alt names too
            found = False
            for alt in char.get("alt_names", []):
                if alt.lower() in our_lower:
                    found = True
                    break
            if not found:
                missing_from_us.append(name)

    if missing_from_us:
        print(f"INFO: {len(missing_from_us)} Wikipedia characters not in our registry:")
        for name in sorted(missing_from_us):
            print(f"  + {name}")


if __name__ == "__main__":
    main()
