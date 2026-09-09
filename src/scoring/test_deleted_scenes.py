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
from deleted_scenes import (
    FILM_TITLES,
    deleted_scenes_prompt_block,
    filter_deleted_scenes,
    films_in_corpus,
    load_deleted_scenes,
    load_reported_scenes,
    reported_scenes_for,
)

# Bootstrap: src/ must be importable before paths.py can be imported.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from paths import PROJECT_ROOT
from score import SKIP_CHARACTERS
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

    # --- Reported (index-less) scenes: prompt injection ---------------------
    reported = load_reported_scenes()
    print("\n" + "=" * 60)
    print("REPORTED DELETED SCENES - PROMPT INJECTION DRY RUN")
    print("=" * 60)
    print(f"{len(reported['entries'])} reported scenes, "
          f"{len(reported['by_character'])} characters tagged")

    untagged = [e for e in reported["entries"] if not e.get("characters")]
    if untagged:
        print(f"\nWARNING: {len(untagged)} scenes have no characters tagged yet - "
              f"run src/collect/tag_deleted_scene_characters.py --merge")
        for e in untagged[:10]:
            print(f"  - rank {e['rank']}: {e['title']}")

    injected = []
    for char in sorted(reported["by_character"]):
        # Films of the corpus the scorer actually sees, i.e. after index-based cuts.
        # Characters left with no film corpus are scored as a deterministic zero and
        # never reach the prompt.
        kept, _ = filter_deleted_scenes(load_film_scenes(char), char, deleted_data)
        relevant = reported_scenes_for(char, films_in_corpus(kept), reported)
        tagged_total = len(reported["by_character"][char])
        if not relevant:
            print(f"\n{char}: 0/{tagged_total} scenes injected "
                  f"(none of those films are in their corpus)")
            continue
        print(f"\n{char}: {len(relevant)}/{tagged_total} scenes injected")
        for e in relevant:
            print(f"    - [{FILM_TITLES.get(e['film'], e['film'])}] {e['title']}")
        injected.append(char)

    # --- Write trivia report ------------------------------------------------
    report_path = os.path.join(PROJECT_ROOT, "output", "reports", "deleted_scenes_trivia.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Deleted / Non-Theatrical Scenes - Trivia Material\n\n")
        f.write("Scenes that were not in the theatrical release. Useful as trivia for videos.\n\n")

        f.write("## Reported by Aitor\n\n")
        f.write("Ranked by Aitor, 1 = most significant omission. These are excluded from FP and\n")
        f.write("CIDS by instructing the scorer to ignore them, not by cutting the corpus.\n\n")
        f.write("| Rank | Scene | Film | Description | Characters |\n")
        f.write("|------|-------|------|-------------|------------|\n")
        for e in sorted(reported["entries"], key=lambda e: e["rank"]):
            chars = ", ".join(e.get("characters", [])) or "-"
            film = FILM_TITLES.get(e["film"], e["film"])
            f.write(f"| {e['rank']} | {e['title']} | {film} | {e['description']} | {chars} |\n")

        f.write("\n## Cut from the parsed corpus\n\n")
        f.write("Pinned to an exact scene index and removed before scoring.\n\n")
        f.write("| Character | Film | Scene | Type | Note |\n")
        f.write("|-----------|------|-------|------|------|\n")
        for t in trivia_lines:
            f.write(f"| {t['character']} | {t['film']} | {t['scene_index']} | {t['reason']} | {t['note']} |\n")
    print(f"\nTrivia report written to: {report_path}")

    # --- Characters needing rescore -----------------------------------------
    print("\n" + "=" * 60)
    print("CHARACTERS NEEDING RESCORE:")
    print("=" * 60)
    needs_rescore = []
    for char in sorted(characters):
        if char in SKIP_CHARACTERS:
            continue
        scenes = load_film_scenes(char)
        _, excluded = filter_deleted_scenes(scenes, char, deleted_data)
        if excluded:
            remaining = len(scenes) - len(excluded)
            if remaining == 0:
                print(f"  - {char}: SKIP (empty film corpus)")
            else:
                print(f"  - {char}: corpus cut ({remaining} scenes remain)")
                needs_rescore.append(char)
    for char in injected:
        if char in SKIP_CHARACTERS:
            continue
        if char not in needs_rescore:
            print(f"  - {char}: prompt injection")
            needs_rescore.append(char)

    skipped = sorted(set(characters) & SKIP_CHARACTERS)
    if skipped:
        print(f"\n  ({len(skipped)} tagged characters omitted, score.py skips them: {', '.join(skipped)})")

    print(f"\n{len(needs_rescore)} characters to rescore. Pass to score.py as:")
    print("  --characters " + " ".join(f'"{c}"' for c in sorted(needs_rescore)))
    list_path = os.path.join(PROJECT_ROOT, "output", "reports", "deleted_scenes_rescore_list.txt")
    with open(list_path, "w") as f:
        f.write("\n".join(sorted(needs_rescore)) + "\n")
    print(f"Rescore list written to: {list_path}")


if __name__ == "__main__":
    main()
