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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from paths import CIDS_DIR, CORPUS_DIR

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


# Full film titles, which the model uses about as often as the abbreviations.
# Matched anywhere in the string rather than only at the start.
FILM_TITLE_TO_SOURCE = [
    (r"philosopher'?s stone|sorcerer'?s stone", "1_philosophers_stone"),
    (r"chamber of secrets", "2_chamber_of_secrets"),
    (r"prisoner of azkaban", "3_prisoner_of_azkaban"),
    (r"goblet of fire", "4_goblet_of_fire"),
    (r"order of the phoenix", "5_order_of_the_phoenix"),
    (r"half-?blood prince", "6_half_blood_prince"),
    (r"deathly hallows,? part 1|deathly hallows part i\b|dh part 1", "7_deathly_hallows_p1"),
    (r"deathly hallows,? part 2|deathly hallows part ii\b|dh part 2", "8_deathly_hallows_p2"),
    (r"deathly hallows", None),  # ambiguous, expands to both parts
]

DH_BOTH = ["7_deathly_hallows_p1", "8_deathly_hallows_p2"]

# A bare "Film Scene 4 - ..." with no film named. These come from the
# split-by-book path, where each call is given exactly one film's corpus, so the
# model has no reason to name it. They are not verifiable from the string alone,
# but they are also the entries least at risk of citing the wrong film: the model
# could only cite what was in front of it. Counted separately rather than as
# parser failures. Scores written after book tagging was added carry the film
# explicitly and skip this path.
UNATTRIBUTED_RE = re.compile(
    r"^(film\s+(corpus\s+)?)?scenes?\s+\d+|^film\s+(corpus\s+)?scene\b", re.I
)


def extract_film_prefix(scene_str):
    """Extract the film abbreviation from a scene string like 'CoS Film - ...'"""
    # Patterns: "CoS Film - ...", "CoS Film Scene 7 ...", "HBP Film ...", "DH1 Film ..."
    # Also: "All films ...", "Across multiple films ..."
    scene_lower = scene_str.lower().strip()

    # Skip entries that reference multiple/all films
    if scene_lower.startswith("all films") or scene_lower.startswith("across"):
        return ["ALL"]
    if scene_lower.startswith("films ") or scene_lower.startswith("multiple films"):
        return ["ALL"]

    # Match film abbreviation at start
    m = re.match(r'^(ps/ss|ps|ss|cos|poa|gof|ootp|hbp|dh[12]?)\s*film', scene_lower)
    if m:
        prefix = m.group(1)
        if prefix == "dh":
            return list(DH_BOTH)
        return [FILM_PREFIX_TO_SOURCE[prefix]]

    # Also try without "Film" keyword - some entries like "CoS Scene 7..."
    m = re.match(r'^(ps/ss|ps|ss|cos|poa|gof|ootp|hbp|dh[12]?)\s', scene_lower)
    if m:
        prefix = m.group(1)
        if prefix == "dh":
            return list(DH_BOTH)
        return [FILM_PREFIX_TO_SOURCE[prefix]]

    # Reversed order, e.g. "Film GoF - ..." or "Film DH - ..."
    m = re.match(r'^film\s+[(\[]?(ps/ss|ps|ss|cos|poa|gof|ootp|hbp|dh[12]?)\b', scene_lower)
    if m:
        prefix = m.group(1)
        if prefix == "dh":
            return list(DH_BOTH)
        return [FILM_PREFIX_TO_SOURCE[prefix]]

    # Slash-separated abbreviations anywhere, e.g. "OotP/HBP", "PS/CoS"
    slash = re.match(r'^(ps|ss|cos|poa|gof|ootp|hbp|dh1|dh2)(/(?:ps|ss|cos|poa|gof|ootp|hbp|dh1|dh2))+', scene_lower)
    if slash:
        parts = re.split(r"/", slash.group(0))
        sources = [FILM_PREFIX_TO_SOURCE[p] for p in parts if FILM_PREFIX_TO_SOURCE.get(p)]
        if sources:
            return sources

    # Spelled-out film titles, anywhere in the string
    for pattern, source in FILM_TITLE_TO_SOURCE:
        if re.search(pattern, scene_lower):
            return list(DH_BOTH) if source is None else [source]

    # Bare scene number with no film named - from the split path, see above
    if UNATTRIBUTED_RE.match(scene_lower):
        return ["UNATTRIBUTED"]

    # Entries about material being absent from the films name no scene because
    # there is no scene. Percy Weasley's "GoF Film - Absent entirely" is the
    # canonical case. These are deliberate, not fabricated, and verifying a film
    # reference against the corpus is meaningless for them.
    if re.search(
        r"\babsent\b|\babsence\b|no equivalent|never (appears|shown)|not (in|present)\b"
        r"|^film\s*[-—–]\s*no\b|\bcut entirely\b|\bomitted\b",
        scene_lower,
    ):
        return ["ABSENCE_CLAIM"]

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
    stats = {"total_scenes": 0, "verified_ok": 0, "mismatched": 0, "unparseable": 0,
             "multi_film": 0, "unattributed_split": 0, "absence_claims": 0}

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

            # Scores written after book tagging record the film directly, which
            # beats guessing it from free text.
            tagged = scene.get("book")
            if tagged:
                expected_sources = DH_BOTH if "deathly_hallows" in tagged else [tagged]
            else:
                expected_sources = extract_film_prefix(scene_str)
            if expected_sources is None:
                stats["unparseable"] += 1
                continue
            if expected_sources == ["ALL"]:
                stats["multi_film"] += 1
                continue
            if expected_sources == ["UNATTRIBUTED"]:
                stats["unattributed_split"] += 1
                continue
            if expected_sources == ["ABSENCE_CLAIM"]:
                stats["absence_claims"] += 1
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
    print(f"  Unattributed (split path):     {stats['unattributed_split']}")
    print(f"  Absence claims (no scene):     {stats['absence_claims']}")
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
