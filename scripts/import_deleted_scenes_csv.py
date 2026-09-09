#!/usr/bin/env python3
"""
Import Aitor's reported deleted-scene CSV into data/deleted_scenes_reported.jsonc.

The CSV carries a scene title, film and description but no scene index - these are
scenes Aitor knows were cut from the theatrical release, not positions in our parsed
corpus. They are consumed as prompt instructions rather than corpus surgery, so no
index is needed. See src/scoring/deleted_scenes.py.

Existing `characters` lists in the output file are preserved on re-import, so the
LLM tagging pass (src/collect/tag_deleted_scene_characters.py) is not undone by
re-running this.

Usage:
    python3 scripts/import_deleted_scenes_csv.py <csv_path>
"""

import csv
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(PROJECT_ROOT, "data", "deleted_scenes_reported.jsonc")

# Aitor's film_code column -> the "source" key used throughout our corpus
FILM_CODE_MAP = {
    "PS": "1_philosophers_stone",
    "COS": "2_chamber_of_secrets",
    "POA": "3_prisoner_of_azkaban",
    "GOF": "4_goblet_of_fire",
    "OOTP": "5_order_of_the_phoenix",
    "HBP": "6_half_blood_prince",
    "DH1": "7_deathly_hallows_p1",
    "DH2": "8_deathly_hallows_p2",
}

HEADER = """\
// Deleted / non-theatrical scenes as reported by Aitor.
//
// Source: data/hp_deleted_scenes_EN.csv, imported by scripts/import_deleted_scenes_csv.py.
// Unlike data/deleted_scenes.jsonc these entries carry no scene_index - they name a
// scene the client knows was cut, without saying where it sits in our parsed corpus.
// They are injected into the FP and CIDS prompts as "ignore this material" instructions
// rather than removing scenes, because our scene segmentation is far too coarse in some
// films (Chamber of Secrets parses as 8 blocks) to cut safely.
//
// Fields:
//   rank        - Aitor's ordering, 1 = most significant omission
//   title       - scene title as reported
//   film        - matches the "source" field in corpus scenes.json
//   film_code   - Aitor's abbreviation, kept for round-tripping to his sheet
//   description - Aitor's description of what the scene contains
//   confidence  - Aitor's confidence that the scene is non-theatrical
//   characters  - canonical names, filled in by
//                 src/collect/tag_deleted_scene_characters.py and hand-correctable
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    csv_path = sys.argv[1]

    existing = {}
    if os.path.exists(OUT_PATH):
        import re

        with open(OUT_PATH) as f:
            text = re.sub(r"//[^\n]*", "", f.read())
        for entry in json.loads(text).get("entries", []):
            existing[entry["rank"]] = entry.get("characters", [])

    entries = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            code = row["film_code"]
            if code not in FILM_CODE_MAP:
                print(f"  WARN: unknown film_code {code!r}, skipping rank {row['rank']}")
                continue
            rank = int(row["rank"])
            entries.append(
                {
                    "rank": rank,
                    "title": row["scene_title_en"],
                    "film": FILM_CODE_MAP[code],
                    "film_code": code,
                    "description": row["description_en"],
                    "confidence": row["confidence"],
                    "characters": existing.get(rank, []),
                }
            )

    entries.sort(key=lambda e: -e["rank"])
    with open(OUT_PATH, "w") as f:
        f.write(HEADER)
        json.dump({"entries": entries}, f, indent=2)
        f.write("\n")

    tagged = sum(1 for e in entries if e["characters"])
    print(f"Wrote {len(entries)} entries to {OUT_PATH} ({tagged} with characters)")
    by_film = {}
    for e in entries:
        by_film[e["film"]] = by_film.get(e["film"], 0) + 1
    for film, n in sorted(by_film.items()):
        print(f"  {film:24} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
