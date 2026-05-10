#!/usr/bin/env python3
"""
Build per-character corpus from parsed books and screenplays (v1 pipeline).
For each character, collect all scenes/paragraphs where they appear.

Outputs to corpus/<character_name>/books/scenes.json
         corpus/<character_name>/screenplays/scenes.json

NOTE: This builds the v1 corpus. The v2 pipeline (src/collect/build_v2_pipeline.py)
builds a separate corpus at data/v2/corpus/. The scorer currently reads from v1.
"""

import json
import os
import re
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PARSED_SCREENPLAYS = os.path.join(PROJECT_ROOT, "data", "parsed", "screenplays")
PARSED_BOOKS = os.path.join(PROJECT_ROOT, "data", "parsed", "books")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "characters.yaml")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")


def safe_dirname(name):
    """Convert character name to safe directory name."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")


def load_characters():
    with open(CHARACTERS_FILE) as f:
        data = yaml.safe_load(f)
    return data["characters"]


def build_alias_lookup(characters):
    """Map lowercase alias -> canonical name."""
    # Names that are too generic to be useful for character detection
    BLOCKLIST = {
        "you",
        "all",
        "voice",
        "hogwarts",
        "weasley",
        "ominous voice",
        "elevator voice",
        "man",
        "woman",
        "boy",
        "girl",
        "student",
        "students",
        "crowd",
        "everyone",
        "someone",
        "death eater",
        "death eaters",
        "the",
        "his",
        "her",
        "him",
    }
    lookup = {}
    for c in characters:
        canonical = c["name"]
        if canonical.lower() in BLOCKLIST:
            continue
        lookup[canonical.lower()] = canonical
        for a in c.get("aliases", []):
            clean = a.strip().replace("\n", " ").lower()
            if len(clean) >= 3 and clean not in BLOCKLIST:
                lookup[clean] = canonical
    return lookup


def build_screenplay_corpus(alias_lookup):
    """Collect screenplay scenes per character."""
    corpus = {}  # canonical_name -> list of scene entries

    for fname in sorted(os.listdir(PARSED_SCREENPLAYS)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PARSED_SCREENPLAYS, fname)) as f:
            data = json.load(f)

        film = data["film"]
        for scene_idx, scene in enumerate(data["scenes"]):
            # Find all characters in this scene
            chars_in_scene = set()
            for c in scene.get("characters", []):
                c_lower = c.lower()
                if c_lower in alias_lookup:
                    chars_in_scene.add(alias_lookup[c_lower])

            # Also check dialogue speakers
            for d in scene.get("dialogue", []):
                speaker = d["speaker"].lower()
                if speaker in alias_lookup:
                    chars_in_scene.add(alias_lookup[speaker])

            entry = {
                "source": film,
                "scene_index": scene_idx,
                "dialogue": scene.get("dialogue", []),
                "directions": scene.get("directions", []),
            }

            for char_name in chars_in_scene:
                if char_name not in corpus:
                    corpus[char_name] = []
                corpus[char_name].append(entry)

    return corpus


def build_book_corpus(alias_lookup):
    """Collect book paragraphs per character."""
    corpus = {}

    # Same blocklist as alias lookup
    blocklist = {
        "you",
        "all",
        "voice",
        "hogwarts",
        "weasley",
        "ominous voice",
        "elevator voice",
        "man",
        "woman",
        "boy",
        "girl",
        "student",
        "students",
        "crowd",
        "everyone",
        "someone",
        "death eater",
        "death eaters",
        "the",
        "his",
        "her",
        "him",
    }

    for fname in sorted(os.listdir(PARSED_BOOKS)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PARSED_BOOKS, fname)) as f:
            data = json.load(f)

        book = data["book"]
        for chapter in data["chapters"]:
            ch_title = chapter["chapter_title"]
            for scene in chapter["scenes"]:
                chars_in_scene = set()
                for c in scene.get("characters_mentioned", []):
                    if c.lower() not in blocklist:
                        chars_in_scene.add(c)
                for s in scene.get("speakers", []):
                    if s.lower() not in blocklist:
                        chars_in_scene.add(s)

                entry = {
                    "source": book,
                    "chapter": ch_title,
                    "paragraph_index": scene.get("paragraph_index", 0),
                    "text": scene["text"],
                    "has_dialogue": scene.get("has_dialogue", False),
                }

                for char_name in chars_in_scene:
                    if char_name not in corpus:
                        corpus[char_name] = []
                    corpus[char_name].append(entry)

    return corpus


def write_corpus(corpus, subdir):
    """Write corpus entries to files."""
    count = 0
    for char_name, entries in corpus.items():
        dirname = safe_dirname(char_name)
        char_dir = os.path.join(CORPUS_DIR, dirname, subdir)
        os.makedirs(char_dir, exist_ok=True)

        outpath = os.path.join(char_dir, "scenes.json")
        with open(outpath, "w") as f:
            json.dump(
                {
                    "character": char_name,
                    "total_scenes": len(entries),
                    "scenes": entries,
                },
                f,
                indent=2,
            )
        count += 1
    return count


def main():
    characters = load_characters()
    alias_lookup = build_alias_lookup(characters)
    print(f"Loaded {len(characters)} characters, {len(alias_lookup)} aliases")

    print("Building screenplay corpus...")
    sp_corpus = build_screenplay_corpus(alias_lookup)
    sp_count = write_corpus(sp_corpus, "screenplays")
    print(f"  {sp_count} characters with screenplay appearances")

    print("Building book corpus...")
    book_corpus = build_book_corpus(alias_lookup)
    book_count = write_corpus(book_corpus, "books")
    print(f"  {book_count} characters with book appearances")

    # Print top characters by scene count
    all_chars = set(list(sp_corpus.keys()) + list(book_corpus.keys()))
    stats = []
    for c in all_chars:
        sp = len(sp_corpus.get(c, []))
        bk = len(book_corpus.get(c, []))
        stats.append((c, sp, bk, sp + bk))
    stats.sort(key=lambda x: x[3], reverse=True)

    print("\nTop 20 characters by total scenes:")
    for name, sp, bk, total in stats[:20]:
        print(f"  {name}: {sp} screenplay scenes, {bk} book paragraphs ({total} total)")

    print(f"\nCorpus written to {CORPUS_DIR}")


if __name__ == "__main__":
    main()
