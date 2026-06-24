#!/usr/bin/env python3
"""Generate an interactive HTML page showing all book scenes cut from the films."""

import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
CUT_SCENES_DIR = os.path.join(PROJECT_ROOT, "output", "cut_scenes")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "output", "cut_scenes.html")
PAGE_DIR = os.path.dirname(os.path.abspath(__file__))

BOOK_NAMES = {
    "1_philosophers_stone": "Philosopher's Stone",
    "2_chamber_of_secrets": "Chamber of Secrets",
    "3_prisoner_of_azkaban": "Prisoner of Azkaban",
    "4_goblet_of_fire": "Goblet of Fire",
    "5_order_of_the_phoenix": "Order of the Phoenix",
    "6_half_blood_prince": "Half-Blood Prince",
    "7_deathly_hallows": "Deathly Hallows",
}


def load_cut_scenes():
    """Load all cut scene data, organized by book."""
    data = {}
    for book_dir in sorted(os.listdir(CUT_SCENES_DIR)):
        book_path = os.path.join(CUT_SCENES_DIR, book_dir)
        if not os.path.isdir(book_path):
            continue
        chapters = []
        for fname in sorted(os.listdir(book_path), key=lambda f: int(f.split("_")[1].split(".")[0])):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(book_path, fname)) as f:
                chapters.append(json.load(f))
        data[book_dir] = chapters
    return data


def main():
    data = load_cut_scenes()

    # Stats
    total_scenes = sum(len(ch["cut_scenes"]) for chs in data.values() for ch in chs)
    high = sum(1 for chs in data.values() for ch in chs for s in ch["cut_scenes"] if s["significance"] == "high")
    medium = sum(1 for chs in data.values() for ch in chs for s in ch["cut_scenes"] if s["significance"] == "medium")
    low = sum(1 for chs in data.values() for ch in chs for s in ch["cut_scenes"] if s["significance"] == "low")

    with open(os.path.join(PAGE_DIR, "template.html")) as f:
        template = f.read()
    with open(os.path.join(PAGE_DIR, "style.css")) as f:
        css = f.read()
    with open(os.path.join(PAGE_DIR, "cut_scenes.js")) as f:
        js = f.read()

    html = template.replace("{{CSS}}", css)
    html = html.replace("{{JS}}", js)
    html = html.replace("{{CUT_SCENES_JSON}}", json.dumps(data))
    html = html.replace("{{TOTAL_SCENES}}", str(total_scenes))
    html = html.replace("{{HIGH_COUNT}}", str(high))
    html = html.replace("{{MEDIUM_COUNT}}", str(medium))
    html = html.replace("{{LOW_COUNT}}", str(low))

    # Book names for JS
    html = html.replace("{{BOOK_NAMES_JSON}}", json.dumps(BOOK_NAMES))

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"Cut scenes page: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
