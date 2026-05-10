#!/usr/bin/env python3
"""
Fetch the list of Harry Potter characters from Wikipedia and store as JSON.
Source: https://en.wikipedia.org/wiki/List_of_Harry_Potter_characters

Output: data/reference/wikipedia_hp_characters.json
"""
import json
import os
import re
import urllib.request
import datetime

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUTPUT = os.path.join(PROJECT_ROOT, "data", "reference", "wikipedia_hp_characters.json")
URL = "https://en.wikipedia.org/w/index.php?title=List_of_Harry_Potter_characters&action=raw"


def fetch_wikitext():
    print(f"Fetching {URL}...")
    req = urllib.request.Request(URL, headers={"User-Agent": "HPCharacterFaithfulness/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        wikitext = resp.read().decode("utf-8")
    print(f"  Got {len(wikitext)} chars of wikitext")
    return wikitext


def extract_name_from_line(line, section):
    """Extract character name from a wikitext bullet line."""
    entry = line.lstrip("* ").strip()
    if not entry:
        return None, []

    display_name = None
    anchor_name = None
    alt_names = []

    # {{Visible anchor|...|text=...}} (with or without extra anchors between)
    va_text = re.match(r'\{\{[Vv]isible anchor\|([^}|]+?)(?:\|[^}]*?)*\|text=\s*([^}]+?)\s*\}\}', entry)
    if va_text:
        anchor_name = va_text.group(1).strip()
        display_name = va_text.group(2).strip()
    elif re.match(r'\{\{[Vv]isible anchor\|', entry):
        # {{Visible anchor|Name|AltName}} or {{Visible anchor|Name}}
        inner = re.match(r'\{\{[Vv]isible anchor\|([^}]+)\}\}', entry)
        if inner:
            parts = [p.strip() for p in inner.group(1).split("|")]
            anchor_name = parts[0]
            display_name = parts[0]
            for p in parts[1:]:
                if p and not p.startswith("text="):
                    alt_names.append(p)
    elif re.match(r'\[\[', entry):
        # [[Link|Display]] or [[Link]]
        link_match = re.match(r'\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]', entry)
        if link_match:
            anchor_name = link_match.group(1).strip()
            display_name = (link_match.group(2) or link_match.group(1)).strip()
    else:
        # Plain text before dash
        dash_match = re.match(r'([^–\n]+?)(?:\s*–|\s*$)', entry)
        if dash_match:
            display_name = dash_match.group(1).strip()
            display_name = re.sub(r'<ref[^>]*>.*?</ref>', '', display_name)
            display_name = re.sub(r'<ref[^>]*/?>', '', display_name)

    if not display_name:
        return None, []

    # Clean stray brackets/punctuation from Wikipedia typos
    display_name = display_name.strip("][ ")

    # Convert "Surname, Firstname" to "Firstname Surname" for by_surname section
    if section == "by_surname" and ", " in display_name:
        parts = display_name.split(", ", 1)
        canonical = f"{parts[1].strip()} {parts[0].strip()}"
    else:
        canonical = display_name

    # If anchor_name differs meaningfully, add as alt
    if anchor_name:
        clean_anchor = anchor_name.strip("][ ")
        if clean_anchor != canonical and clean_anchor != display_name:
            alt_names.append(clean_anchor)

    # Check for parenthetical alt names
    paren_match = re.search(r'\(([^)]+)\)', canonical)
    if paren_match:
        alt = paren_match.group(1).strip()
        canonical = canonical[:paren_match.start()].strip()
        if alt and not alt.startswith("née") and not alt.startswith("born"):
            alt_names.append(alt)

    return canonical, alt_names


def parse_characters(wikitext):
    lines = wikitext.split("\n")
    characters = []
    section = None

    for line in lines:
        # Track which section we're in
        if line.strip() == "==Characters by surname==":
            section = "by_surname"
            continue
        elif line.strip() == "==Characters with no surname==":
            section = "no_surname"
            continue
        elif line.startswith("==") and not line.startswith("==="):
            if section is not None:
                # We've left the character sections
                break
            continue

        # Skip sub-headers (=== A ===)
        if line.startswith("==="):
            continue

        if section is None:
            continue

        # Only process bullet lines
        if not line.startswith("*"):
            continue

        canonical, alt_names = extract_name_from_line(line, section)
        if canonical and len(canonical) >= 2:
            characters.append({
                "name": canonical,
                "alt_names": alt_names,
                "section": section,
            })

    return characters


def main():
    wikitext = fetch_wikitext()
    characters = parse_characters(wikitext)
    print(f"\nExtracted {len(characters)} characters")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    output_data = {
        "source": "https://en.wikipedia.org/wiki/List_of_Harry_Potter_characters",
        "retrieved": datetime.datetime.now().strftime("%Y-%m-%d"),
        "characters": characters,
    }
    with open(OUTPUT, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"Saved to {OUTPUT}")
    print("\nFirst 30:")
    for c in characters[:30]:
        alt = f" (aka {', '.join(c['alt_names'])})" if c["alt_names"] else ""
        print(f"  {c['name']}{alt}")


if __name__ == "__main__":
    main()
