#!/usr/bin/env python3
"""Rebuild scores_comparative.json from individual score files."""

import json
import os

SCORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output", "scores", "comparative")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "..", "output", "scores", "scores_comparative.json")

all_scores = []
for fname in sorted(os.listdir(SCORE_DIR)):
    if fname.endswith(".json"):
        with open(os.path.join(SCORE_DIR, fname)) as f:
            all_scores.append(json.load(f))

all_scores.sort(key=lambda x: x["overall"].get("total", 0), reverse=True)

with open(OUTPUT, "w") as f:
    json.dump(all_scores, f, indent=2)

print(f"Rebuilt {OUTPUT} with {len(all_scores)} characters")
