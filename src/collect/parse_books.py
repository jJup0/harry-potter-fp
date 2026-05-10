#!/usr/bin/env python3
"""
Parse books into chapters and paragraph-level scenes.
Detects character presence per paragraph.
Outputs JSON per book in data/parsed/books/
"""

import json
import os
import re
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
BOOKS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "books")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "characters.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "parsed", "books")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_character_names():
    """Load all character name variants, return dict of lowercase_name -> canonical_name."""
    with open(CHARACTERS_FILE) as f:
        data = yaml.safe_load(f)
    name_map = {}
    for c in data["characters"]:
        canonical = c["name"]
        name_map[canonical.lower()] = canonical
        for a in c.get("aliases", []):
            clean = a.strip().replace("\n", " ")
            if len(clean) >= 2:
                name_map[clean.lower()] = canonical
    return name_map


def split_chapters(text):
    """Split book text into chapters."""
    # Match various chapter heading formats:
    # "CHAPTER ONE", "- CHAPTER ONE -", "Chapter 1: Title", "CHAPTER TWo", "CHAPTER F I v E"
    pattern = re.compile(
        r"^\s*-?\s*[Cc][Hh][Aa][Pp][Tt][Ee][Rr]\s+[A-Za-z0-9 \t\-:vI]+", re.MULTILINE
    )
    splits = list(pattern.finditer(text))

    if not splits:
        return [{"title": "FULL TEXT", "body": text}]

    chapters = []
    for i, match in enumerate(splits):
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        title = match.group(0).strip().strip("-").strip()
        body = text[match.end() : end].strip()
        chapters.append({"title": title, "body": body})

    return chapters


def detect_characters(text, name_map):
    """Find all characters mentioned in a text block."""
    found = set()
    text_lower = text.lower()
    for name, canonical in name_map.items():
        # Skip very short names that cause false positives
        if len(name) <= 2:
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", text_lower):
            found.add(canonical)
    return sorted(found)


def detect_dialogue_speakers(text, name_map):
    """Detect who speaks in a paragraph from dialogue attribution."""
    speakers = set()
    # "said Harry", "Harry said", etc.
    pattern = re.compile(
        r"(?:said|asked|whispered|shouted|yelled|muttered|called|cried|screamed|"
        r"snapped|snarled|growled|replied|answered|exclaimed|demanded|roared|"
        r"squealed|gasped|stammered|bellowed|hissed|moaned|groaned|sobbed|"
        r"sighed|laughed|sneered|barked|spat|wailed|whimpered)"
        r"\s+((?:(?:Mr|Mrs|Ms|Professor|Sir|Lord|Lady|Madam|Uncle|Aunt)\.?\s+)?"
        r"[A-Z][a-z]+(?:[A-Z][a-z]+)*(?:\s[A-Z][a-z]+)*)",
    )
    for match in pattern.finditer(text):
        name = match.group(1).strip().lower()
        if name in name_map:
            speakers.add(name_map[name])
        # Try stripping title
        stripped = re.sub(
            r"^(professor|mr\.?|mrs\.?|ms\.?|sir|lord|lady|madam|uncle|aunt)\s+",
            "",
            name,
        ).strip()
        if stripped in name_map:
            speakers.add(name_map[stripped])
    return speakers


def parse_book(filepath, name_map):
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    chapters = split_chapters(text)
    parsed_chapters = []

    for ch_idx, chapter in enumerate(chapters):
        # Split into paragraphs - handle multiple formats:
        # 1. Double newline separated (book 6, 7)
        # 2. Lines starting with full-width spaces or tabs (books 2-5)
        # 3. Single newline line-wrapped text (book 1) - use blank lines or dialogue quotes
        body = chapter["body"]

        if "\u3000" in body:
            # Full-width space indented (books 2-4)
            paragraphs = re.split(r"\n(?=[\u3000\t　])", body)
        elif re.search(r"\n    [A-Z\'\"]", body):
            # 4-space indented paragraphs (book 5)
            paragraphs = re.split(r"\n(?=    [A-Z'\"\u2018\u201c])", body)
        elif "\n\n" in body:
            # Double newline separated (books 6, 7)
            paragraphs = re.split(r"\n\s*\n", body)
        else:
            # Line-wrapped text (book 1): split on lines starting with "
            # or lines after a short line (dialogue), or page numbers
            lines = body.split("\n")
            paragraphs = []
            current = []
            for line in lines:
                stripped = line.strip()
                # Page numbers or blank lines signal paragraph breaks
                if not stripped or re.match(r"^\d+$", stripped):
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    continue
                # New paragraph if line starts with " (dialogue) and we have content
                if stripped.startswith('"') and current:
                    paragraphs.append(" ".join(current))
                    current = [stripped]
                else:
                    current.append(stripped)
            if current:
                paragraphs.append(" ".join(current))

        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        scenes = []
        for p_idx, para in enumerate(paragraphs):
            if len(para) < 10:
                continue
            characters_mentioned = detect_characters(para, name_map)
            speakers = detect_dialogue_speakers(para, name_map)
            has_dialogue = '"' in para or "\u201c" in para

            scenes.append(
                {
                    "paragraph_index": p_idx,
                    "text": para,
                    "characters_mentioned": characters_mentioned,
                    "speakers": sorted(speakers),
                    "has_dialogue": has_dialogue,
                }
            )

        parsed_chapters.append(
            {
                "chapter_number": ch_idx + 1,
                "chapter_title": chapter["title"],
                "scenes": scenes,
            }
        )

    return parsed_chapters


def main():
    name_map = load_character_names()
    print(f"Loaded {len(name_map)} character name variants")

    for fname in sorted(os.listdir(BOOKS_DIR)):
        if not fname.endswith(".txt"):
            continue
        filepath = os.path.join(BOOKS_DIR, fname)
        chapters = parse_book(filepath, name_map)

        total_scenes = sum(len(ch["scenes"]) for ch in chapters)
        all_chars = set()
        for ch in chapters:
            for s in ch["scenes"]:
                all_chars.update(s["characters_mentioned"])

        print(
            f"{fname}: {len(chapters)} chapters, {total_scenes} paragraphs, {len(all_chars)} characters"
        )

        out_name = fname.replace(".txt", ".json")
        with open(os.path.join(OUTPUT_DIR, out_name), "w") as f:
            json.dump(
                {"book": fname.replace(".txt", ""), "chapters": chapters}, f, indent=2
            )

    print(f"\nParsed books saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
