#!/usr/bin/env python3
"""
Dry-run: report which scenes would be tagged as deleted per character.
Also generates the deleted-scene trivia report.

Usage:
    python3 src/scoring/test_deleted_scenes.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scoring"))
from deleted_scenes import load_deleted_scenes, filter_deleted_scenes

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")


def load_film_scenes(char_name):
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    path = os.path.join(CORPUS_DIR, safe, "screenplays", "scenes.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("scenes", [])


def main():
    deleted_data = load_deleted_scenes()

    # Collect all affected characters
    characters = set()
    for entry in deleted_data["entries"]:
        characters.update(entry["characters"])

    print("=" * 60)
    print("DELETED SCENE EXCLUSION - DRY RUN REPORT")
    print("=" * 60)

    all_ok = True
    trivia_lines = []

    for char in sorted(characters):
        scenes = load_film_scenes(char)
        included, excluded = filter_deleted_scenes(scenes, char, deleted_data)
        total = len(scenes)
        n_exc = len(excluded)

        print(f"\n{char}:")
        print(f"  Total film scenes: {total}")
        print(f"  Excluded (deleted): {n_exc}")
        print(f"  Remaining: {total - n_exc}")

        if total - n_exc == 0:
            print(f"  -> EMPTY FILM CORPUS (absent from theatrical films)")

        for s in excluded:
            film = s.get("source", "?")
            idx = s.get("scene_index", "?")
            # Find matching entry for note
            entry_key = (film, idx)
            entries = deleted_data["lookup"].get(entry_key, [])
            note = ""
            reason = ""
            for e in entries:
                if char in e["characters"]:
                    note = e.get("note", "")
                    reason = e.get("reason", "")
                    break
            print(f"    - {film} scene {idx} [{reason}]: {note}")
            trivia_lines.append({
                "character": char,
                "film": film,
                "scene_index": idx,
                "reason": reason,
                "note": note,
            })

    # Verify Sir Cadogan has empty film corpus
    cadogan_scenes = load_film_scenes("Sir Cadogan")
    included, excluded = filter_deleted_scenes(cadogan_scenes, "Sir Cadogan", deleted_data)
    assert len(included) == 0, f"Sir Cadogan should have empty film corpus, got {len(included)} scenes"
    print("\n" + "=" * 60)
    print("VERIFICATION: Sir Cadogan has EMPTY film corpus after exclusion. OK.")
    print("=" * 60)

    # Write trivia report
    report_path = os.path.join(PROJECT_ROOT, "output", "reports", "deleted_scenes_trivia.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Deleted / Non-Theatrical Scenes - Trivia Material\n\n")
        f.write("These scenes appear in our screenplay sources but were not in the\n")
        f.write("theatrical release. Useful as trivia for videos.\n\n")
        f.write("| Character | Film | Scene | Type | Note |\n")
        f.write("|-----------|------|-------|------|------|\n")
        for t in trivia_lines:
            f.write(f"| {t['character']} | {t['film']} | {t['scene_index']} | {t['reason']} | {t['note']} |\n")
    print(f"\nTrivia report written to: {report_path}")

    # Characters needing rescore
    print("\n" + "=" * 60)
    print("CHARACTERS NEEDING RESCORE:")
    print("=" * 60)
    for char in sorted(characters):
        scenes = load_film_scenes(char)
        _, excluded = filter_deleted_scenes(scenes, char, deleted_data)
        if excluded:
            remaining = len(scenes) - len(excluded)
            status = "SKIP (empty film corpus)" if remaining == 0 else f"RESCORE ({remaining} scenes remain)"
            print(f"  - {char}: {status}")


if __name__ == "__main__":
    main()
