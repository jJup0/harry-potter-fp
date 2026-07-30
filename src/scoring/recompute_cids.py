"""
One-off script to recompute CIDS scores in place using the new log-dampened formula.
No LLM calls - uses stored WIE and SDL values.

New formula: CIDS = (100 - FP) * log2(1 + WIE) * (1 + SDL/8)
Old formula: CIDS = (100 - FP) * WIE * STRUCTURAL_MULTIPLIERS[SDL]

Preserves old values as cids_v1 / adjusted_cids_v1. Idempotent: won't overwrite
cids_v1 if it already exists (i.e. safe to re-run).
"""

import json
import math
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CIDS_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "cids")


def recompute_file(path):
    with open(path) as f:
        data = json.load(f)

    wie = data["weighted_infidelity_exposure"]
    sdl = data["structural_damage_level"]
    fp = data["fp_score"]
    infidelity = 100 - fp

    # Preserve old values (only if not already preserved)
    if "cids_v1" not in data:
        data["cids_v1"] = data["cids"]
        data["adjusted_cids_v1"] = data["adjusted_cids"]

    # New formula
    cids = infidelity * math.log2(1 + wie) * (1 + sdl / 8)
    data["cids"] = round(cids, 1)
    data["adjusted_cids"] = round(cids, 1)

    # Update damage_per_exposure
    total_exposure = sum(s.get("exposure", 0) for s in data.get("damaging_scenes", []))
    data["damage_per_exposure"] = round(cids / total_exposure, 1) if total_exposure > 0 else 0

    # Remove obsolete field
    data.pop("structural_damage_multiplier", None)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return data["character"], cids


def regenerate_summary():
    results = []
    for fname in sorted(os.listdir(CIDS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        with open(os.path.join(CIDS_DIR, fname)) as f:
            data = json.load(f)
        results.append(data)
    results.sort(key=lambda x: x.get("cids", 0), reverse=True)

    summary = [{
        "character": r["character"],
        "fp_score": r["fp_score"],
        "cids": r["cids"],
        "adjusted_cids": r["adjusted_cids"],
        "structural_damage_level": r["structural_damage_level"],
    } for r in results]

    summary_path = os.path.join(CIDS_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary ({len(summary)} characters) to {summary_path}")
    return results


def main():
    files = [f for f in os.listdir(CIDS_DIR) if f.endswith(".json") and not f.startswith("_")]
    print(f"Recomputing CIDS for {len(files)} characters...")

    scores = []
    for fname in sorted(files):
        path = os.path.join(CIDS_DIR, fname)
        name, cids = recompute_file(path)
        scores.append((name, cids))

    scores.sort(key=lambda x: x[1], reverse=True)
    print(f"\nTop 15 by new CIDS:")
    print(f"{'Character':<30} {'CIDS':>8}")
    print("-" * 40)
    for name, cids in scores[:15]:
        print(f"{name:<30} {cids:>8.1f}")

    print()
    regenerate_summary()


if __name__ == "__main__":
    main()
