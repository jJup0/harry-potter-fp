#!/usr/bin/env python3
"""
Validate project characters against the Wikipedia canonical list.
Flags any character in our registry that doesn't appear on Wikipedia.

Usage:
  python3 src/collect/validate_characters.py
"""

import json
import os
import re

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "output", "characters.yaml")
WIKIPEDIA_FILE = os.path.join(
    PROJECT_ROOT, "data", "reference", "wikipedia_hp_characters.json"
)

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


SCORES_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "kiro")

# Words that mark a registry entry as a role or crowd label rather than a person.
ROLE_WORDS = {
    "boy", "girl", "man", "woman", "student", "students", "guard", "wizard",
    "wizards", "witch", "goblin", "snatcher", "crowd", "everyone", "someone",
    "voice", "gang", "class", "muggle", "portrait", "waiter", "conductor",
    "minister", "announcer", "driver", "bartender", "villager", "prefect",
}


def _scored_totals():
    """FP totals by character name, for entries that have a score file."""
    totals = {}
    if not os.path.isdir(SCORES_DIR):
        return totals
    for fname in os.listdir(SCORES_DIR):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        with open(os.path.join(SCORES_DIR, fname)) as f:
            data = json.load(f)
        totals[data.get("character", "")] = data.get("overall", {}).get("total") or 0
    return totals


def classify_flag(name, wiki_names, registry_names):
    """Guess why a registry entry is not on the Wikipedia list.

    The flags mix three unrelated things, which is why the raw count has never
    been actionable. Only malformed names and dedup misses are defects; a genuinely
    minor character that Wikipedia omits is fine.
    """
    lower = name.lower()
    tokens = name.split()

    # Malformed: role labels, and names that do not start with a capital, which is
    # what parser truncations and sentence fragments look like.
    if any(t.lower() in ROLE_WORDS for t in tokens):
        return "malformed", "contains a role or crowd word"
    if name[:1].islower():
        return "malformed", "does not start with a capital"

    # Dedup miss: another registry entry, itself on Wikipedia, differs only by an
    # honorific or generational suffix, or is a strict prefix of this name.
    stripped = re.sub(r"\s+(sr\.?|jr\.?|senior|junior|i{1,3})$", "", lower).strip()
    for other in registry_names:
        other_lower = other.lower()
        if other_lower == lower:
            continue
        if other_lower not in wiki_names:
            continue
        if stripped == other_lower:
            return "dedup-miss", f"suffix variant of '{other}', which is on Wikipedia"
        if len(tokens) > 1 and other_lower == tokens[-1].lower():
            return "dedup-miss", f"surname matches '{other}', which is on Wikipedia"

    return "minor", "not listed by Wikipedia, no defect detected"


def report_by_cause(not_on_wiki, wiki_names):
    """Split the flagged list by likely cause, and by whether it reaches output."""
    registry_names = load_our_characters()
    totals = _scored_totals()

    buckets = {"malformed": [], "dedup-miss": [], "minor": []}
    for name in sorted(not_on_wiki):
        cause, why = classify_flag(name, wiki_names, registry_names)
        buckets[cause].append((name, why, totals.get(name)))

    print("=" * 78)
    print("FLAGGED BY LIKELY CAUSE")
    print("=" * 78)
    print(
        "Only malformed names and dedup misses are defects. A minor character that\n"
        "Wikipedia omits is not a problem. Entries with no FP score never reach any\n"
        "output, so they are noise regardless of cause.\n"
    )
    for cause in ("malformed", "dedup-miss", "minor"):
        rows = buckets[cause]
        scored = [r for r in rows if r[2]]
        print(f"{cause}: {len(rows)} flagged, {len(scored)} of them scored")
        for name, why, total in rows:
            mark = f"FP {total}" if total else "unscored"
            print(f"    {name:<32} [{mark:>9}]  {why}")
        print()

    actionable = [
        (n, w, t)
        for c in ("malformed", "dedup-miss")
        for n, w, t in buckets[c]
        if t
    ]
    print("-" * 78)
    print(f"ACTIONABLE: {len(actionable)} flagged entries are a likely defect AND scored")
    for name, why, total in actionable:
        print(f"    {name:<32} FP {total:<6} {why}")


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
            if name.lower() == canonical.lower() or name.lower() in [
                a.lower() for a in aliases
            ]:
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
    report_by_cause(not_on_wiki, wiki_names)

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
