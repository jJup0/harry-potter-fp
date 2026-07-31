#!/usr/bin/env python3
"""Dry-run verification for film presence gap analysis (issue #36).

Verifies the claims in data/film_presence_gaps.json against actual repo data.
Does NOT modify any corpus, parsed output, or scores.
"""
import json
import os
import sys
import yaml

WORKTREE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS_DIR = os.path.join(WORKTREE, "output/corpus")
PARSED_DIR = os.path.join(WORKTREE, "output/parsed/screenplays")
CHARS_FILE = os.path.join(WORKTREE, "output/characters.yaml")
GAPS_FILE = os.path.join(WORKTREE, "data/film_presence_gaps.json")
SCORES_DIR = os.path.join(WORKTREE, "output/scores/kiro")
SCREENPLAYS_DIRS = [
    os.path.join(WORKTREE, "data/source/screenplays"),
    os.path.join(WORKTREE, "data/source/screenplays_v2"),
    os.path.join(WORKTREE, "data/source/screenplays_v3"),
    os.path.join(WORKTREE, "data/source/screenplays_merged"),
]


def to_slug(name):
    """Match the corpus builder's slug logic (hyphens become underscores)."""
    return name.lower().replace(" ", "_").replace(".", "").replace("'", "").replace('"', '').replace("-", "_")


def name_in_screenplays(name):
    """Check if a name appears in any screenplay source."""
    surname = name.split()[-1].lower()
    for sp_dir in SCREENPLAYS_DIRS:
        if not os.path.isdir(sp_dir):
            continue
        for fname in os.listdir(sp_dir):
            if not fname.endswith('.txt'):
                continue
            with open(os.path.join(sp_dir, fname)) as f:
                text = f.read().lower()
            if surname in text:
                return True
    return False


def main():
    with open(CHARS_FILE) as f:
        chars = {c['name']: c for c in yaml.safe_load(f)['characters']}

    with open(GAPS_FILE) as f:
        gaps = json.load(f)

    errors = []

    # 1. Verify screenplay_only_gaps
    print("=== Verifying screenplay_only_gaps ===")
    for entry in gaps["screenplay_only_gaps"]["characters"]:
        name = entry["name"]
        char = chars.get(name)
        if not char:
            errors.append(f"{name}: not in characters.yaml")
            continue

        st = char.get("screen_time_minutes", 0) or 0
        if st != entry["screen_time_minutes"]:
            errors.append(f"{name}: screen time mismatch {st} vs {entry['screen_time_minutes']}")

        # Verify absent from all screenplays
        if name_in_screenplays(name):
            errors.append(f"{name}: FOUND in screenplay source (should be absent)")
        else:
            print(f"  OK: {name} - absent from all screenplay sources, {st} min screen time")

        # Verify empty corpus
        slug = to_slug(name)
        scenes_file = os.path.join(CORPUS_DIR, slug, "screenplays", "scenes.json")
        if os.path.exists(scenes_file):
            with open(scenes_file) as f:
                data = json.load(f)
            if data.get("total_scenes", 0) > 0:
                errors.append(f"{name}: has {data['total_scenes']} corpus scenes (expected 0)")
            else:
                print(f"  OK: {name} - empty corpus confirmed")
        else:
            print(f"  OK: {name} - no corpus dir")

    # 2. Verify stale_scores
    print("\n=== Verifying stale_scores ===")
    stale_ok = 0
    for name in gaps["stale_scores"]["characters"]:
        slug = to_slug(name)
        scenes_file = os.path.join(CORPUS_DIR, slug, "screenplays", "scenes.json")
        score_file = os.path.join(SCORES_DIR, f"{slug}.json")

        has_corpus = False
        if os.path.exists(scenes_file):
            with open(scenes_file) as f:
                data = json.load(f)
            if data.get("total_scenes", 0) > 0:
                has_corpus = True

        if not has_corpus:
            errors.append(f"{name}: claimed stale but has NO corpus")
            continue

        if os.path.exists(score_file):
            with open(score_file) as f:
                score = json.load(f)
            total = score.get("overall", {}).get("total", -1)
            if total != 0:
                errors.append(f"{name}: score is {total}, not 0 (not actually stale?)")
            else:
                stale_ok += 1
        else:
            errors.append(f"{name}: no score file")
    print(f"  OK: {stale_ok}/{len(gaps['stale_scores']['characters'])} confirmed (have corpus, score 0)")

    # 3. Verify needs_client_confirmation
    print("\n=== Verifying needs_client_confirmation ===")
    confirmed = 0
    for name in gaps["needs_client_confirmation"]["full_list"]:
        char = chars.get(name)
        if not char:
            errors.append(f"{name}: not in characters.yaml")
            continue
        st = char.get("screen_time_minutes", 0) or 0
        if st > 0:
            errors.append(f"{name}: HAS screen time ({st} min) - should not need confirmation")
            continue

        slug = to_slug(name)
        scenes_file = os.path.join(CORPUS_DIR, slug, "screenplays", "scenes.json")
        if os.path.exists(scenes_file):
            with open(scenes_file) as f:
                data = json.load(f)
            if data.get("total_scenes", 0) > 0:
                errors.append(f"{name}: has {data['total_scenes']} corpus scenes (not truly empty)")
                continue
        confirmed += 1
    print(f"  OK: {confirmed}/{len(gaps['needs_client_confirmation']['full_list'])} confirmed (no screen time, empty corpus)")

    # 4. No-mutation check
    print("\n=== Verifying no corpus mutation ===")
    print(f"  output/corpus is symlink: {os.path.islink(os.path.join(WORKTREE, 'output/corpus'))}")
    print(f"  output/parsed is symlink: {os.path.islink(os.path.join(WORKTREE, 'output/parsed'))}")

    # 5. Rescoring needs
    print("\n=== Characters needing action ===")
    print("  Rescoring needed (stale scores with corpus available):")
    for name in gaps["stale_scores"]["characters"]:
        print(f"    {name}")
    print(f"\n  Screenplay-only gaps (will remain unscored):")
    for entry in gaps["screenplay_only_gaps"]["characters"]:
        print(f"    {entry['name']}")
    print(f"\n  Awaiting client confirmation: {gaps['needs_client_confirmation']['count']} characters")

    # Summary
    print(f"\n=== RESULT ===")
    if errors:
        print(f"  FAILED - {len(errors)} errors:")
        for e in errors:
            print(f"    {e}")
        return 1
    else:
        print("  ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
