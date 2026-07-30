#!/usr/bin/env python3
"""
Step 2: Identify book scenes cut from the films.
For each book chapter, sends chapter text + mapped screenplay scenes to LLM.
Outputs output/cut_scenes/<book>/<chapter_N>.json

Fully resumable - skips chapters with existing output files.

Usage:
  python3 -u src/collect/find_cut_scenes.py [--book 4_goblet_of_fire] [--chapter 7]
"""

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from llm import call_kiro, extract_json

KIRO_CWD = "/tmp/harry-potter-cut-scenes"
os.makedirs(KIRO_CWD, exist_ok=True)

SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "screenplays")
BOOKS_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "books")
MAPPING_DIR = os.path.join(PROJECT_ROOT, "output", "scene_chapter_mapping")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "cut_scenes")

FILM_BOOK_MAP = {
    "1_philosophers_stone": "1_philosophers_stone",
    "2_chamber_of_secrets": "2_chamber_of_secrets",
    "3_prisoner_of_azkaban": "3_prisoner_of_azkaban",
    "4_goblet_of_fire": "4_goblet_of_fire",
    "5_order_of_the_phoenix": "5_order_of_the_phoenix",
    "6_half_blood_prince": "6_half_blood_prince",
    "7_deathly_hallows_p1": "7_deathly_hallows",
    "8_deathly_hallows_p2": "7_deathly_hallows",
}

DH_SPLIT = {
    "7_deathly_hallows_p1": (1, 24),
    "8_deathly_hallows_p2": (25, 37),
}

PROMPT = """You are analyzing which book scenes were cut from the Harry Potter film adaptation.

Below is a chapter from the book, followed by the corresponding screenplay scenes from the film.

Identify book scenes/events from this chapter that were CUT from the film - i.e. present in the book text but absent from the screenplay. A "scene" is a distinct narrative moment: a conversation, event, discovery, or setting (roughly 1-3 minutes of expected screen time if filmed).

Do NOT list:
- Minor dialogue differences or condensed conversations (if the core event is still there, it's not "cut")
- Internal thoughts (unfilmable)
- Descriptions/narration with no plot relevance

DO list:
- Entire conversations or events removed
- Characters or subplots that were cut (e.g. Peeves, S.P.E.W., Winky)
- Significant scenes that change understanding of characters or plot

Respond with JSON:
{{"cut_scenes": [
  {{"title": "Short scene title", "description": "1-2 sentence description of what happens", "characters": ["Character1", "Character2"], "significance": "low|medium|high"}}
]}}

If nothing significant was cut from this chapter, respond: {{"cut_scenes": []}}

---
BOOK CHAPTER: {chapter_title}

{chapter_text}

---
CORRESPONDING FILM SCREENPLAY SCENES:

{screenplay_text}
"""


def get_films_for_book(book_name):
    """Get which film(s) correspond to a book."""
    films = [f for f, b in FILM_BOOK_MAP.items() if b == book_name]
    return films


def get_screenplay_scenes_for_chapter(film_name, chapter_number):
    """Get screenplay scenes mapped to a specific chapter."""
    mapping_path = os.path.join(MAPPING_DIR, f"{film_name}.json")
    if not os.path.exists(mapping_path):
        return []
    with open(mapping_path) as f:
        mapping_data = json.load(f)

    sp_path = os.path.join(SCREENPLAYS_DIR, f"{film_name}.json")
    with open(sp_path) as f:
        sp_data = json.load(f)

    scenes = []
    for i, ch in enumerate(mapping_data["mapping"]):
        if ch == chapter_number and i < len(sp_data["scenes"]):
            scenes.append(sp_data["scenes"][i])
    return scenes


def format_screenplay_scenes(scenes):
    """Format screenplay scenes compactly."""
    if not scenes:
        return "(No corresponding film scenes found for this chapter)"
    parts = []
    for i, scene in enumerate(scenes):
        lines = []
        for d in scene.get("directions", []):
            lines.append(f"[{d}]")
        for dl in scene.get("dialogue", []):
            lines.append(f"{dl['speaker']}: {dl['text']}")
        parts.append(f"--- Film Scene {i+1} ---\n" + "\n".join(lines))
    return "\n\n".join(parts)


def format_chapter_text(chapter):
    """Format chapter text compactly."""
    paragraphs = [s["text"] for s in chapter["scenes"]]
    return "\n\n".join(paragraphs)


def process_chapter(book_name, chapter, film_names):
    """Process a single chapter."""
    ch_num = chapter["chapter_number"]
    book_dir = os.path.join(OUTPUT_DIR, book_name)
    os.makedirs(book_dir, exist_ok=True)
    out_path = os.path.join(book_dir, f"chapter_{ch_num}.json")

    if os.path.exists(out_path):
        return None  # cached

    # Get all screenplay scenes for this chapter across relevant films
    all_sp_scenes = []
    for film in film_names:
        # Check if this chapter is in range for this film (relevant for DH)
        ch_range = DH_SPLIT.get(film)
        if ch_range and not (ch_range[0] <= ch_num <= ch_range[1]):
            continue
        all_sp_scenes.extend(get_screenplay_scenes_for_chapter(film, ch_num))

    chapter_text = format_chapter_text(chapter)
    screenplay_text = format_screenplay_scenes(all_sp_scenes)

    # Truncate if too long (keep under ~100K chars)
    if len(chapter_text) > 60000:
        chapter_text = chapter_text[:60000] + "\n\n[...truncated...]"
    if len(screenplay_text) > 30000:
        screenplay_text = screenplay_text[:30000] + "\n\n[...truncated...]"

    prompt = PROMPT.format(
        chapter_title=chapter["chapter_title"],
        chapter_text=chapter_text,
        screenplay_text=screenplay_text,
    )

    tag = f"[{book_name}][ch{ch_num}]"
    print(f"  {tag} sending ~{len(prompt)//4} tokens...", flush=True)
    t0 = time.time()
    try:
        response = call_kiro(prompt, model="claude-sonnet-4.6", agent="blank-agent",
                             cwd=KIRO_CWD)
    except Exception as e:
        print(f"  {tag} FAILED: {e}", flush=True)
        return None

    elapsed = time.time() - t0
    parsed = extract_json(response)
    if parsed is None:
        print(f"  {tag} FAILED: no JSON ({elapsed:.1f}s)", flush=True)
        print(f"  Raw: {response[:300]}", flush=True)
        return None

    result = {
        "book": book_name,
        "chapter_number": ch_num,
        "chapter_title": chapter["chapter_title"],
        "cut_scenes": parsed.get("cut_scenes", []),
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    n = len(result["cut_scenes"])
    print(f"  {tag} {n} cut scenes found ({elapsed:.1f}s)", flush=True)
    return result


def main():
    book_filter = None
    chapter_filter = None
    workers = 3

    args = sys.argv[1:]
    while args:
        if args[0] == "--book" and len(args) > 1:
            book_filter = args[1]
            args = args[2:]
        elif args[0] == "--chapter" and len(args) > 1:
            chapter_filter = int(args[1])
            args = args[2:]
        elif args[0] == "--workers" and len(args) > 1:
            workers = int(args[1])
            args = args[2:]
        else:
            args = args[1:]

    # Check mappings exist
    missing = [f for f in FILM_BOOK_MAP if not os.path.exists(os.path.join(MAPPING_DIR, f"{f}.json"))]
    if missing:
        print(f"ERROR: Missing scene-chapter mappings for: {missing}")
        print("Run: python3 src/collect/map_scenes_to_chapters.py")
        sys.exit(1)

    books = sorted(set(FILM_BOOK_MAP.values()))
    if book_filter:
        books = [b for b in books if book_filter in b]

    tasks = []
    for book_name in books:
        book_path = os.path.join(BOOKS_DIR, f"{book_name}.json")
        with open(book_path) as f:
            book_data = json.load(f)
        film_names = get_films_for_book(book_name)
        for chapter in book_data["chapters"]:
            if chapter_filter and chapter["chapter_number"] != chapter_filter:
                continue
            tasks.append((book_name, chapter, film_names))

    # Count cached
    cached = sum(1 for b, ch, _ in tasks
                 if os.path.exists(os.path.join(OUTPUT_DIR, b, f"chapter_{ch['chapter_number']}.json")))
    print(f"Processing {len(tasks)} chapters ({cached} cached, {len(tasks)-cached} remaining)", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_chapter, b, ch, films): (b, ch["chapter_number"])
                   for b, ch, films in tasks}
        for future in as_completed(futures):
            future.result()  # propagate exceptions

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
