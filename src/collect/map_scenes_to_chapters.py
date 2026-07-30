#!/usr/bin/env python3
"""
Step 1: Map screenplay scenes to book chapters using an LLM.
Produces output/scene_chapter_mapping/<film>.json

One LLM call per film (8 total). Sends compact scene summaries + chapter titles.
Fully resumable - skips films with existing mapping files.

Usage:
  python3 src/collect/map_scenes_to_chapters.py
"""

import json
import os
import sys
import time

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from llm import call_kiro, extract_json

KIRO_CWD = "/tmp/harry-potter-scene-mapping"
os.makedirs(KIRO_CWD, exist_ok=True)

SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "screenplays")
BOOKS_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "books")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scene_chapter_mapping")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# DH chapter split
DH_SPLIT = {
    "7_deathly_hallows_p1": (1, 24),
    "8_deathly_hallows_p2": (25, 37),
}


def summarize_scene(i, scene):
    """One-line summary of a screenplay scene."""
    first_dir = (scene["directions"][0][:150] if scene.get("directions") else "")
    speakers = list(dict.fromkeys(d["speaker"] for d in scene.get("dialogue", [])[:6]))
    speakers_str = ", ".join(speakers[:5])
    return f"Scene {i}: {first_dir} [{speakers_str}]"


def get_chapter_list(book_data, chapter_range=None):
    chapters = book_data["chapters"]
    if chapter_range:
        lo, hi = chapter_range
        chapters = [c for c in chapters if lo <= c["chapter_number"] <= hi]
    return chapters


def build_prompt(film_name, scene_summaries, chapters):
    chapter_lines = [f"Ch{c['chapter_number']}: {c['chapter_title']}" for c in chapters]
    return f"""Map scenes from the Harry Potter film "{film_name}" to book chapters.

Below are the film's scenes in sequential order, then the book's chapter list.

Assign each scene to the book chapter it most closely corresponds to. Some scenes may be film-original (no book equivalent) - mark those as "original".

Respond ONLY with a JSON object: {{"mapping": [...]}} where the array has one entry per scene - either a chapter number (int) or "original".

FILM SCENES:
{chr(10).join(scene_summaries)}

BOOK CHAPTERS:
{chr(10).join(chapter_lines)}"""


def map_film(film_name):
    out_path = os.path.join(OUTPUT_DIR, f"{film_name}.json")
    if os.path.exists(out_path):
        print(f"  [{film_name}] cached", flush=True)
        return

    sp_path = os.path.join(SCREENPLAYS_DIR, f"{film_name}.json")
    with open(sp_path) as f:
        sp_data = json.load(f)

    book_name = FILM_BOOK_MAP[film_name]
    with open(os.path.join(BOOKS_DIR, f"{book_name}.json")) as f:
        book_data = json.load(f)

    scene_summaries = [summarize_scene(i, s) for i, s in enumerate(sp_data["scenes"])]
    chapter_range = DH_SPLIT.get(film_name)
    chapters = get_chapter_list(book_data, chapter_range)
    chapter_lines = [f"Ch{c['chapter_number']}: {c['chapter_title']}" for c in chapters]

    prompt = build_prompt(film_name, scene_summaries, chapters)
    print(f"  [{film_name}] {len(scene_summaries)} scenes, {len(chapters)} chapters, ~{len(prompt)//4} tokens", flush=True)

    t0 = time.time()
    response = call_kiro(prompt, model="claude-sonnet-4.6", agent="blank-agent",
                         cwd=KIRO_CWD)
    print(f"  [{film_name}] response in {time.time()-t0:.1f}s", flush=True)

    parsed = extract_json(response)
    if not parsed or "mapping" not in parsed:
        # Try extracting a bare array
        import re
        match = re.search(r'\[[\s\S]*?\]', response)
        if match:
            try:
                mapping = json.loads(match.group(0))
            except json.JSONDecodeError:
                # Try line-by-line: find longest valid JSON array
                text = response
                start = text.find('[')
                if start >= 0:
                    # Find matching bracket
                    depth = 0
                    for i in range(start, len(text)):
                        if text[i] == '[': depth += 1
                        elif text[i] == ']': depth -= 1
                        if depth == 0:
                            try:
                                mapping = json.loads(text[start:i+1])
                                break
                            except json.JSONDecodeError:
                                pass
                    else:
                        print(f"  [{film_name}] FAILED: could not parse array", flush=True)
                        return
                else:
                    print(f"  [{film_name}] FAILED: no array found", flush=True)
                    return
        else:
            print(f"  [{film_name}] FAILED: could not parse response", flush=True)
            print(f"  Raw: {response[:500]}", flush=True)
            return
    else:
        mapping = parsed["mapping"]

    output = {
        "film": film_name,
        "book": book_name,
        "chapter_range": chapter_range,
        "scene_count": len(sp_data["scenes"]),
        "mapping": mapping,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  [{film_name}] saved ({len(mapping)} mappings)", flush=True)


def main():
    print("Mapping screenplay scenes to book chapters...", flush=True)
    for film in FILM_BOOK_MAP:
        map_film(film)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
