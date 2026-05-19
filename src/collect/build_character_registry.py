#!/usr/bin/env python3
"""
Extract character names from screenplays and books to build a character registry.
Outputs output/characters.yaml
"""

import os
import re
import yaml
from collections import Counter

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "screenplays_merged")
BOOKS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "books")
OUTPUT = os.path.join(PROJECT_ROOT, "output", "characters.yaml")

# Canonical name -> list of aliases that should merge into it
# This also serves as the "full name" registry
ALIAS_FILE = os.path.join(PROJECT_ROOT, "data", "manual-character-alias-mapping.jsonc")


def _load_jsonc(path):
    """Load a JSONC file (JSON with comments and trailing commas)."""
    import json

    with open(path) as f:
        text = f.read()
    # Strip // comments
    text = re.sub(r"//[^\n]*", "", text)
    # Strip trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


KNOWN_CHARACTERS = _load_jsonc(ALIAS_FILE)["characters"]


def extract_screenplay_speakers():
    speakers = Counter()
    pattern = re.compile(r"^([A-Z][A-Za-z\.\' ]+?):\s", re.MULTILINE)
    for fname in sorted(os.listdir(SCREENPLAYS_DIR)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(SCREENPLAYS_DIR, fname), encoding="utf-8") as f:
            text = f.read()
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if len(name) < 2 or len(name) > 40:
                continue
            if name.lower() in (
                "note",
                "cut to",
                "ext",
                "int",
                "scene",
                "fade",
                "continued",
                "the end",
                "title",
                "subtitle",
            ):
                continue
            speakers[name] += 1
    return speakers


def extract_book_dialogue_speakers():
    speakers = Counter()
    pattern = re.compile(
        r"(?:said|asked|whispered|shouted|yelled|muttered|called|cried|screamed|"
        r"snapped|snarled|growled|replied|answered|exclaimed|demanded|roared|"
        r"squealed|gasped|stammered|bellowed|hissed|moaned|groaned|sobbed|"
        r"sighed|laughed|chuckled|giggled|sneered|barked|spat|wailed|whimpered)"
        r"\s+((?:(?:Mr|Mrs|Ms|Professor|Sir|Lord|Lady|Madam|Madame|Uncle|Aunt)\.?\s+)?"
        r"[A-Z][a-z]+(?:[A-Z][a-z]+)*(?:\s[A-Z][a-z]+(?:[A-Z][a-z]+)*)?)",
        re.MULTILINE,
    )
    for fname in sorted(os.listdir(BOOKS_DIR)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(BOOKS_DIR, fname), encoding="utf-8") as f:
            text = f.read()
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if len(name) < 2:
                continue
            speakers[name] += 1
    return speakers


def build_alias_to_canonical():
    """Build reverse map: alias -> canonical name."""
    alias_map = {}
    for canonical, aliases in KNOWN_CHARACTERS.items():
        alias_map[canonical] = canonical
        alias_map[canonical.lower()] = canonical
        for alias in aliases:
            alias_map[alias] = canonical
            alias_map[alias.lower()] = canonical
    return alias_map


def resolve_name(name, alias_map):
    """Try to resolve a name to its canonical form."""
    # Try exact match first (handles "Mrs. Longbottom" -> Augusta)
    if name in alias_map:
        return alias_map[name]
    if name.lower() in alias_map:
        return alias_map[name.lower()]
    # Try stripping title only if no exact match
    stripped = re.sub(
        r"^(Professor|Mr\.?|Mrs\.?|Ms\.?|Sir|Lord|Lady|Madam|Madame|Uncle|Aunt)\s+",
        "",
        name,
    ).strip()
    if stripped != name:
        if stripped in alias_map:
            return alias_map[stripped]
        if stripped.lower() in alias_map:
            return alias_map[stripped.lower()]
    return name  # fallback: keep original


def build_registry():
    print("Extracting screenplay speakers...")
    screenplay_speakers = extract_screenplay_speakers()
    print(f"  Found {len(screenplay_speakers)} unique speaker names")

    print("Extracting book dialogue speakers...")
    book_speakers = extract_book_dialogue_speakers()
    print(f"  Found {len(book_speakers)} unique speaker names")

    alias_map = build_alias_to_canonical()

    # Merge into canonical names
    characters = {}

    def ensure_entry(canonical):
        if canonical not in characters:
            characters[canonical] = {
                "aliases": set(),
                "screenplay_lines": 0,
                "book_attributions": 0,
            }

    for name, count in screenplay_speakers.most_common():
        canonical = resolve_name(name, alias_map)
        ensure_entry(canonical)
        characters[canonical]["aliases"].add(name)
        characters[canonical]["screenplay_lines"] += count

    for name, count in book_speakers.most_common():
        canonical = resolve_name(name, alias_map)
        ensure_entry(canonical)
        characters[canonical]["aliases"].add(name)
        characters[canonical]["book_attributions"] += count

    # Build output
    output = []
    for name, data in sorted(
        characters.items(),
        key=lambda x: x[1]["screenplay_lines"] + x[1]["book_attributions"],
        reverse=True,
    ):
        total = data["screenplay_lines"] + data["book_attributions"]
        if total < 2:
            continue
        # Clean aliases: remove canonical name itself, sort
        aliases = sorted(a for a in data["aliases"] if a != name)
        entry = {"name": name}
        if aliases:
            entry["aliases"] = aliases
        entry["screenplay_lines"] = data["screenplay_lines"]
        entry["book_attributions"] = data["book_attributions"]
        output.append(entry)

    print(f"\nTotal characters (>=2 mentions): {len(output)}")
    print("Top 20:")
    for c in output[:20]:
        aliases_str = (
            f" (aka {', '.join(c.get('aliases', [])[:3])})" if c.get("aliases") else ""
        )
        print(
            f"  {c['name']}{aliases_str}: {c['screenplay_lines']} screenplay, {c['book_attributions']} book"
        )

    with open(OUTPUT, "w") as f:
        yaml.dump(
            {"characters": output},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    build_registry()
