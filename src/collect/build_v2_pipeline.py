#!/usr/bin/env python3
"""
V2 unified pipeline - builds everything from best available data sources.

Run this to regenerate all derived data:
  python3 src/collect/build_v2_pipeline.py

Steps:
  1. Build character registry from Aitor's xlsx data -> output/characters.yaml
  2. Load alias map for character detection
  3. Parse screenplays (from screenplays_merged/) -> output/parsed/screenplays/
  4. Parse books (v1 text files) -> output/parsed/books/
  5. Build per-character corpus -> output/corpus/

Data source selection per film is handled by screenplays_merged/ symlinks.
See data/source/screenplays_merged/SOURCE.md for details.

KNOWN ISSUES:
  - v2 corpus has duplicate dirs for same character (alias resolution bugs)
  - Blocklist for generic words is incomplete, some non-characters get corpus dirs
"""

import json
import os
import re
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

# Source paths
BOOKS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "books")
SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "screenplays_merged")
SCREEN_TIME_FILE = os.path.join(PROJECT_ROOT, "data", "source", "metrics", "screen_time_v2.json")
BOOK_MENTIONS_FILE = os.path.join(
    PROJECT_ROOT, "data", "source", "metrics", "book_mentions_v2.json"
)

# Output paths
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PARSED_DIR = os.path.join(OUTPUT_DIR, "parsed")
CORPUS_DIR = os.path.join(OUTPUT_DIR, "corpus")
CHARACTERS_FILE = os.path.join(OUTPUT_DIR, "characters.yaml")
os.makedirs(os.path.join(PARSED_DIR, "screenplays"), exist_ok=True)
os.makedirs(os.path.join(PARSED_DIR, "books"), exist_ok=True)

FILMS = [
    "1_philosophers_stone",
    "2_chamber_of_secrets",
    "3_prisoner_of_azkaban",
    "4_goblet_of_fire",
    "5_order_of_the_phoenix",
    "6_half_blood_prince",
    "7_deathly_hallows_p1",
    "8_deathly_hallows_p2",
]
BOOKS = [
    "1_philosophers_stone",
    "2_chamber_of_secrets",
    "3_prisoner_of_azkaban",
    "4_goblet_of_fire",
    "5_order_of_the_phoenix",
    "6_half_blood_prince",
    "7_deathly_hallows",
]


import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_character_registry import KNOWN_CHARACTERS


# --- Step 1: Character registry from Aitor's data ---


def build_character_registry():
    """Build character registry from Aitor's book mentions (canonical names)."""
    print("Step 1: Building character registry from Aitor's data...")
    with open(BOOK_MENTIONS_FILE) as f:
        mentions = json.load(f)
    with open(SCREEN_TIME_FILE) as f:
        screen_time = json.load(f)

    # Aitor's data has canonical names. Merge both sources.
    all_names = set(mentions.keys()) | set(screen_time.keys())

    # Validate: every name must be in KNOWN_CHARACTERS (as canonical or alias)
    known_canonical = set(KNOWN_CHARACTERS.keys())
    known_aliases = set()
    for aliases in KNOWN_CHARACTERS.values():
        known_aliases.update(aliases)
    all_known = known_canonical | known_aliases

    unknown = []
    for name in sorted(all_names):
        if name not in all_known:
            unknown.append(name)
    if unknown:
        raise ValueError(
            f"{len(unknown)} characters from Aitor's data not in alias mapping:\n"
            + "\n".join(f"  - {n}" for n in unknown)
        )

    characters = []
    for name in sorted(all_names):
        bm = mentions.get(name, {}).get("_total", 0)
        st = screen_time.get(name, {}).get("_total", 0)
        # Resolve to canonical
        if name in known_canonical:
            canonical = name
        else:
            # Find which canonical this is an alias of
            canonical = None
            for c, aliases in KNOWN_CHARACTERS.items():
                if name in aliases:
                    canonical = c
                    break
        entry = {
            "name": canonical,
            "book_mentions": bm,
            "screen_time_minutes": st,
        }
        characters.append(entry)

    # Merge duplicates (multiple source names -> same canonical)
    merged = {}
    for entry in characters:
        name = entry["name"]
        if name in merged:
            merged[name]["book_mentions"] += entry["book_mentions"]
            merged[name]["screen_time_minutes"] += entry["screen_time_minutes"]
        else:
            merged[name] = entry

    characters = sorted(
        merged.values(),
        key=lambda x: x["book_mentions"] + x["screen_time_minutes"],
        reverse=True,
    )

    with open(CHARACTERS_FILE, "w") as f:
        yaml.dump(
            {"characters": characters},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(f"  {len(characters)} characters -> {CHARACTERS_FILE}")
    return characters


def load_alias_map():
    """Build lowercase alias -> canonical name map from KNOWN_CHARACTERS."""
    alias_map = {}
    for canonical, aliases in KNOWN_CHARACTERS.items():
        alias_map[canonical.lower()] = canonical
        for a in aliases:
            alias_map[a.lower()] = canonical
    return alias_map


# --- Step 2: Pick best screenplay source per film ---


def get_screenplay_path(film_key):
    """Return screenplay path from merged directory."""
    path = os.path.join(SCREENPLAYS_DIR, f"{film_key}.txt")
    if os.path.exists(path):
        # Resolve symlink to determine source
        real = os.path.realpath(path)
        if "screenplays_v3" in real:
            return path, "v3_scriptslug"
        elif "screenplays_v2" in real:
            return path, "v2_pdf"
        else:
            return path, "v1_transcript"
    return None, None


# --- Step 3: Parse screenplays ---


def parse_v2_screenplay(text, alias_map):
    """Parse proper screenplay format (CHARACTER NAME in caps, INT./EXT.)."""
    scenes = []
    current_scene = {"directions": [], "dialogue": [], "characters": set()}
    # Scene headers: INT., EXT., or CUT TO:
    scene_break_re = re.compile(r"^(INT\.|EXT\.|CUT TO:|FADE|DISSOLVE)", re.MULTILINE)
    # Character speaking: name alone on a line, all caps, possibly with (CONT'D)
    speaker_re = re.compile(r"^\s*([A-Z][A-Z '.]{1,30}?)\s*(?:\(CONT'?D?\))?\s*$")

    lines = text.split("\n")
    current_speaker = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Scene break
        if scene_break_re.match(stripped):
            if current_scene["dialogue"] or current_scene["directions"]:
                current_scene["characters"] = sorted(current_scene["characters"])
                scenes.append(current_scene)
                current_scene = {"directions": [], "dialogue": [], "characters": set()}
            current_scene["directions"].append(stripped)
            current_speaker = None
            continue

        # Speaker line (centered, all caps)
        speaker_match = speaker_re.match(line)
        if speaker_match:
            name = speaker_match.group(1).strip()
            # Filter out non-character lines
            if name not in (
                "CONTINUED",
                "CUT TO",
                "FADE IN",
                "FADE OUT",
                "THE END",
                "MORE",
                "CONT",
                "DISSOLVE TO",
            ):
                current_speaker = name
                current_scene["characters"].add(name.lower())
                # Try to resolve to canonical name
                for alias, canonical in alias_map.items():
                    if alias in name.lower():
                        current_scene["characters"].add(canonical.lower())
            continue

        # Dialogue (text after a speaker, before next speaker/scene break)
        if current_speaker and stripped:
            current_scene["dialogue"].append(
                {
                    "speaker": current_speaker.title(),
                    "text": stripped,
                }
            )
            continue

        # Stage direction / action
        if stripped:
            current_scene["directions"].append(stripped)

    if current_scene["dialogue"] or current_scene["directions"]:
        current_scene["characters"] = sorted(current_scene["characters"])
        scenes.append(current_scene)

    return scenes


def parse_v1_screenplay(text, alias_map):
    """Parse v1 wiki transcript format (Character Name: dialogue, [directions])."""
    scenes = []
    current_scene = {"directions": [], "dialogue": [], "characters": set()}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        direction_match = re.match(r"^\[(.+)\]$", line)
        if direction_match:
            direction = direction_match.group(1)
            is_break = bool(
                re.search(
                    r"\b(we see|scene changes?|cut to|later|meanwhile|back (?:at|in|to)|now in)\b",
                    direction,
                    re.IGNORECASE,
                )
            )
            if is_break and (current_scene["dialogue"] or current_scene["directions"]):
                current_scene["characters"] = sorted(current_scene["characters"])
                scenes.append(current_scene)
                current_scene = {"directions": [], "dialogue": [], "characters": set()}
            current_scene["directions"].append(direction)
            for alias, canonical in alias_map.items():
                if len(alias) >= 4 and re.search(
                    r"\b" + re.escape(alias) + r"\b", direction, re.IGNORECASE
                ):
                    current_scene["characters"].add(canonical.lower())
            continue

        dialogue_match = re.match(r"^([A-Z][A-Za-z\.\' ]+?):\s*(.*)$", line)
        if dialogue_match:
            speaker = dialogue_match.group(1).strip()
            text_content = dialogue_match.group(2).strip()
            current_scene["dialogue"].append({"speaker": speaker, "text": text_content})
            current_scene["characters"].add(speaker.lower())

    if current_scene["dialogue"] or current_scene["directions"]:
        current_scene["characters"] = sorted(current_scene["characters"])
        scenes.append(current_scene)

    return scenes


def parse_all_screenplays(alias_map):
    """Parse all screenplays using best available source."""
    print("\nStep 3: Parsing screenplays...")
    for film in FILMS:
        path, source = get_screenplay_path(film)
        if not path:
            print(f"  {film}: NO SOURCE FOUND")
            continue

        with open(path, encoding="utf-8") as f:
            text = f.read()

        if source == "v2_pdf":
            scenes = parse_v2_screenplay(text, alias_map)
        else:
            scenes = parse_v1_screenplay(text, alias_map)

        total_dialogue = sum(len(s["dialogue"]) for s in scenes)
        print(
            f"  {film}: {len(scenes)} scenes, {total_dialogue} dialogue lines ({source})"
        )

        out_path = os.path.join(PARSED_DIR, "screenplays", f"{film}.json")
        with open(out_path, "w") as f:
            json.dump({"film": film, "source": source, "scenes": scenes}, f, indent=2)


# --- Step 4: Parse books (reuse v1 logic) ---


def parse_all_books(alias_map):
    """Parse all books from v1 text files."""
    print("\nStep 4: Parsing books...")
    for book in BOOKS:
        path = os.path.join(BOOKS_DIR, f"{book}.txt")
        if not os.path.exists(path):
            print(f"  {book}: NOT FOUND")
            continue

        with open(path, encoding="utf-8") as f:
            text = f.read()

        chapters = split_chapters(text)
        parsed_chapters = []
        for ch_idx, chapter in enumerate(chapters):
            paragraphs = split_paragraphs(chapter["body"])
            scenes = []
            for p_idx, para in enumerate(paragraphs):
                if len(para) < 10:
                    continue
                chars = detect_characters(para, alias_map)
                scenes.append(
                    {
                        "paragraph_index": p_idx,
                        "text": para,
                        "characters_mentioned": chars,
                        "has_dialogue": '"' in para or "\u201c" in para,
                    }
                )
            parsed_chapters.append(
                {
                    "chapter_number": ch_idx + 1,
                    "chapter_title": chapter["title"],
                    "scenes": scenes,
                }
            )

        total_paras = sum(len(ch["scenes"]) for ch in parsed_chapters)
        print(f"  {book}: {len(parsed_chapters)} chapters, {total_paras} paragraphs")

        out_path = os.path.join(PARSED_DIR, "books", f"{book}.json")
        with open(out_path, "w") as f:
            json.dump({"book": book, "chapters": parsed_chapters}, f, indent=2)


def split_chapters(text):
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


def split_paragraphs(body):
    if "\u3000" in body:
        paragraphs = re.split(r"\n(?=[\u3000\t　])", body)
    elif re.search(r"\n    [A-Z\'\"\u2018\u201c]", body):
        paragraphs = re.split(r"\n(?=    [A-Z'\"\u2018\u201c])", body)
    elif "\n\n" in body:
        paragraphs = re.split(r"\n\s*\n", body)
    else:
        lines = body.split("\n")
        paragraphs = []
        current = []
        for line in lines:
            stripped = line.strip()
            if not stripped or re.match(r"^\d+$", stripped):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                continue
            if stripped.startswith('"') and current:
                paragraphs.append(" ".join(current))
                current = [stripped]
            else:
                current.append(stripped)
        if current:
            paragraphs.append(" ".join(current))
    return [p.strip() for p in paragraphs if p.strip()]


def detect_characters(text, alias_map):
    found = set()
    text_lower = text.lower()
    for alias, canonical in alias_map.items():
        if len(alias) < 4:
            continue
        if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
            found.add(canonical)
    return sorted(found)


# --- Step 5: Build corpus ---


def build_corpus(alias_map):
    """Build per-character corpus from parsed data."""
    print("\nStep 5: Building character corpus...")
    corpus = (
        {}
    )  # canonical -> {screenplays: {source: [scenes]}, books: {source: [scenes]}}

    # Screenplays
    sp_dir = os.path.join(PARSED_DIR, "screenplays")
    for fname in sorted(os.listdir(sp_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(sp_dir, fname)) as f:
            data = json.load(f)
        film = data["film"]
        for scene_idx, scene in enumerate(data["scenes"]):
            chars_in_scene = set()
            for c in scene.get("characters", []):
                if c in alias_map:
                    chars_in_scene.add(alias_map[c])
            for d in scene.get("dialogue", []):
                speaker = d["speaker"].lower()
                if speaker in alias_map:
                    chars_in_scene.add(alias_map[speaker])

            entry = {
                "source": film,
                "scene_index": scene_idx,
                "dialogue": scene.get("dialogue", []),
                "directions": scene.get("directions", []),
            }

            for char in chars_in_scene:
                corpus.setdefault(char, {"screenplays": {}, "books": {}})
                corpus[char]["screenplays"].setdefault(film, []).append(entry)

    # Books
    bk_dir = os.path.join(PARSED_DIR, "books")
    for fname in sorted(os.listdir(bk_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(bk_dir, fname)) as f:
            data = json.load(f)
        book = data["book"]
        for chapter in data["chapters"]:
            for scene in chapter["scenes"]:
                for char in scene.get("characters_mentioned", []):
                    corpus.setdefault(char, {"screenplays": {}, "books": {}})
                    corpus[char]["books"].setdefault(book, []).append(
                        {
                            "source": book,
                            "chapter": chapter["chapter_title"],
                            "text": scene["text"],
                            "has_dialogue": scene.get("has_dialogue", False),
                        }
                    )

    # Write corpus
    for char, data in corpus.items():
        dirname = re.sub(r"[^a-z0-9_]", "_", char.lower()).strip("_")
        char_dir = os.path.join(CORPUS_DIR, dirname)
        for sub in ("screenplays", "books"):
            sub_dir = os.path.join(char_dir, sub)
            os.makedirs(sub_dir, exist_ok=True)
            all_scenes = []
            for source, scenes in data[sub].items():
                all_scenes.extend(scenes)
            with open(os.path.join(sub_dir, "scenes.json"), "w") as f:
                json.dump(
                    {
                        "character": char,
                        "total_scenes": len(all_scenes),
                        "scenes": all_scenes,
                    },
                    f,
                    indent=2,
                )

    # Stats
    top = sorted(
        corpus.items(),
        key=lambda x: sum(len(s) for s in x[1]["screenplays"].values())
        + sum(len(s) for s in x[1]["books"].values()),
        reverse=True,
    )
    print(f"  {len(corpus)} characters with corpus data")
    print("  Top 10:")
    for char, data in top[:10]:
        sp = sum(len(s) for s in data["screenplays"].values())
        bk = sum(len(s) for s in data["books"].values())
        print(f"    {char}: {sp} screenplay scenes, {bk} book paragraphs")


# --- Main ---


def main():
    characters = build_character_registry()
    alias_map = load_alias_map()
    print(f"  {len(alias_map)} aliases loaded")

    parse_all_screenplays(alias_map)
    parse_all_books(alias_map)
    build_corpus(alias_map)

    print(f"\nPipeline complete. Output in {OUTPUT_DIR}")
    print("Data sources used:")
    for film in FILMS:
        _, source = get_screenplay_path(film)
        print(f"  {film}: {source}")
    print("  Books: v1 (individual text files)")
    print("  Screen time: v2 (Aitor's xlsx)")
    print("  Book mentions: v2 (Aitor's xlsx)")


if __name__ == "__main__":
    main()
