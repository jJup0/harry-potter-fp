#!/usr/bin/env python3
"""
Check corpus completeness: compare corpus scene counts against
book mentions and screen time to flag potential gaps.
Outputs data/source/metrics/completeness.json
"""

import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "metrics")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")


def count_corpus_scenes(char_dir):
    """Count scenes in a character's corpus."""
    counts = {"books": 0, "screenplays": 0}
    for subdir in ("books", "screenplays"):
        path = os.path.join(char_dir, subdir, "scenes.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            counts[subdir] = data.get("total_scenes", 0)
    return counts


def main():
    with open(os.path.join(METRICS_DIR, "screen_time_v2.json")) as f:
        screen_time = json.load(f)
    with open(os.path.join(METRICS_DIR, "book_mentions_v2.json")) as f:
        book_mentions = json.load(f)

    # All characters from either source
    all_chars = set(list(screen_time.keys()) + list(book_mentions.keys()))

    results = []
    for char in sorted(all_chars):
        st = screen_time.get(char, {})
        bm = book_mentions.get(char, {})
        total_words = st.get("_total", 0)
        total_mentions = bm.get("_total", 0)

        # Find corpus dir
        dirname = char.lower().replace(" ", "_").replace(".", "_").replace("'", "_")
        # Try to find matching dir
        corpus_scenes = {"books": 0, "screenplays": 0}
        for d in os.listdir(CORPUS_DIR):
            check_path = os.path.join(CORPUS_DIR, d)
            if not os.path.isdir(check_path):
                continue
            # Check if this dir's scenes.json matches this character
            for sub in ("books", "screenplays"):
                spath = os.path.join(check_path, sub, "scenes.json")
                if os.path.exists(spath):
                    with open(spath) as f:
                        data = json.load(f)
                    if data.get("character") == char:
                        corpus_scenes[sub] = data.get("total_scenes", 0)

        # Completeness heuristic:
        # If character has mentions but 0 corpus scenes, flag as incomplete
        has_book_corpus = corpus_scenes["books"] > 0
        has_screenplay_corpus = corpus_scenes["screenplays"] > 0
        book_expected = total_mentions > 0
        screenplay_expected = total_words > 0

        status = "complete"
        if book_expected and not has_book_corpus:
            status = "missing_book_corpus"
        elif screenplay_expected and not has_screenplay_corpus:
            status = "missing_screenplay_corpus"
        elif (
            book_expected
            and not has_book_corpus
            and screenplay_expected
            and not has_screenplay_corpus
        ):
            status = "missing_both"

        results.append(
            {
                "character": char,
                "screenplay_words": total_words,
                "book_mentions": total_mentions,
                "corpus_screenplay_scenes": corpus_scenes["screenplays"],
                "corpus_book_paragraphs": corpus_scenes["books"],
                "status": status,
            }
        )

    results.sort(key=lambda x: x["screenplay_words"] + x["book_mentions"], reverse=True)

    # Summary
    complete = sum(1 for r in results if r["status"] == "complete")
    missing = [r for r in results if r["status"] != "complete"]

    print(f"Total characters: {len(results)}")
    print(f"Complete: {complete}")
    print(f"Missing corpus data: {len(missing)}")
    if missing:
        print("\nCharacters with gaps:")
        for r in missing[:20]:
            print(
                f"  {r['character']}: {r['status']} "
                f"(words={r['screenplay_words']}, mentions={r['book_mentions']}, "
                f"sp_scenes={r['corpus_screenplay_scenes']}, bk_paras={r['corpus_book_paragraphs']})"
            )

    with open(os.path.join(METRICS_DIR, "completeness.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved to {os.path.join(METRICS_DIR, 'completeness.json')}")


if __name__ == "__main__":
    main()
