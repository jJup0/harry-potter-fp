#!/usr/bin/env python3
"""
Post-hoc verifier for CIDS damaging_scenes entries.

For each character's CIDS output, checks that the film cited in each
damaging_scenes[].scene field actually appears in that character's film corpus.
Reports mismatches without modifying anything.
"""

import json
import os
import re
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CIDS_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "cids")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")

# Map scene-field film prefixes to corpus source identifiers
FILM_PREFIX_TO_SOURCE = {
    "ps": "1_philosophers_stone",
    "ss": "1_philosophers_stone",
    "ps/ss": "1_philosophers_stone",
    "cos": "2_chamber_of_secrets",
    "poa": "3_prisoner_of_azkaban",
    "gof": "4_goblet_of_fire",
    "ootp": "5_order_of_the_phoenix",
    "hbp": "6_half_blood_prince",
    "dh1": "7_deathly_hallows_p1",
    "dh2": "8_deathly_hallows_p2",
    "dh": None,  # ambiguous - could be p1 or p2, check both
}


def extract_film_prefix(scene_str):
    """Extract the film abbreviation from a scene string like 'CoS Film - ...'"""
    # Patterns: "CoS Film - ...", "CoS Film Scene 7 ...", "HBP Film ...", "DH1 Film ..."
    # Also: "All films ...", "Across multiple films ..."
    scene_lower = scene_str.lower().strip()

    # Skip entries that reference multiple/all films
    if scene_lower.startswith("all films") or scene_lower.startswith("across"):
        return ["ALL"]

    # Match film abbreviation at start
    m = re.match(r'^(ps/ss|ps|ss|cos|poa|gof|ootp|hbp|dh[12]?)\s*film', scene_lower)
    if m:
        prefix = m.group(1)
        if prefix == "dh":
            return ["7_deathly_hallows_p1", "8_deathly_hallows_p2"]
        return [FILM_PREFIX_TO_SOURCE[prefix]]

    # Also try without "Film" keyword - some entries like "CoS Scene 7..."
    m = re.match(r'^(ps/ss|ps|ss|cos|poa|gof|ootp|hbp|dh[12]?)\s', scene_lower)
    if m:
        prefix = m.group(1)
        if prefix == "dh":
            return ["7_deathly_hallows_p1", "8_deathly_hallows_p2"]
        return [FILM_PREFIX_TO_SOURCE[prefix]]

    return None  # Could not determine film


def get_corpus_sources(char_name):
    """Get set of film sources present in a character's screenplay corpus."""
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    path = os.path.join(CORPUS_DIR, safe, "screenplays", "scenes.json")
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        data = json.load(f)
    return set(s.get("source", "") for s in data.get("scenes", []))


def verify_all():
    mismatches = []
    stats = {"total_scenes": 0, "verified_ok": 0, "mismatched": 0, "unparseable": 0, "multi_film": 0}

    cids_files = sorted(f for f in os.listdir(CIDS_DIR) if f.endswith(".json") and not f.startswith("_"))
    print(f"Verifying {len(cids_files)} CIDS files...")

    for fname in cids_files:
        with open(os.path.join(CIDS_DIR, fname)) as f:
            data = json.load(f)

        char_name = data.get("character", fname.replace(".json", ""))
        corpus_sources = get_corpus_sources(char_name)
        scenes = data.get("damaging_scenes", [])

        for i, scene in enumerate(scenes):
            scene_str = scene.get("scene", "")
            stats["total_scenes"] += 1

            expected_sources = extract_film_prefix(scene_str)
            if expected_sources is None:
                stats["unparseable"] += 1
                continue
            if expected_sources == ["ALL"]:
                stats["multi_film"] += 1
                continue

            # Check if at least one expected source is in corpus
            if any(s in corpus_sources for s in expected_sources):
                stats["verified_ok"] += 1
            else:
                stats["mismatched"] += 1
                mismatches.append({
                    "character": char_name,
                    "scene_index": i,
                    "scene": scene_str,
                    "cited_film": expected_sources,
                    "corpus_has": sorted(corpus_sources),
                })

    return mismatches, stats


def main():
    mismatches, stats = verify_all()

    print(f"\nStats:")
    print(f"  Total damaging_scenes entries: {stats['total_scenes']}")
    print(f"  Verified OK (film in corpus):  {stats['verified_ok']}")
    print(f"  MISMATCHED (film NOT in corpus): {stats['mismatched']}")
    print(f"  Multi/all films (skipped):     {stats['multi_film']}")
    print(f"  Unparseable film prefix:       {stats['unparseable']}")

    if mismatches:
        print(f"\n{'='*80}")
        print(f"MISMATCHES ({len(mismatches)} entries across {len(set(m['character'] for m in mismatches))} characters):")
        print(f"{'='*80}")
        current_char = None
        for m in sorted(mismatches, key=lambda x: x["character"]):
            if m["character"] != current_char:
                current_char = m["character"]
                print(f"\n  {current_char} (corpus has: {', '.join(m['corpus_has']) or 'NONE'})")
            print(f"    [{m['scene_index']}] {m['scene']}")
            print(f"        cited: {m['cited_film']}")
    else:
        print("\nNo mismatches found!")

    # Save results
    out_path = os.path.join(CIDS_DIR, "_verification.json")
    with open(out_path, "w") as f:
        json.dump({"stats": stats, "mismatches": mismatches}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
