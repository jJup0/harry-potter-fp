#!/usr/bin/env python3
"""
Generate output reports from scores.
- Ranked table (CSV + markdown)
- Per-character detailed report (markdown)

Data source: output/scores/kiro/ (6-dimension schema from kiro-cli/claude-sonnet-4.6)
"""

import csv
import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCORES_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "kiro")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DIMENSIONS = [
    "personality_voice",
    "narrative_role_agency",
    "motivations_internal_conflict",
    "character_arc",
    "key_relationships",
    "complexity_nuance_lost_material",
]
DIM_LABELS = {
    "personality_voice": "Personality & Voice",
    "narrative_role_agency": "Narrative Role & Agency",
    "motivations_internal_conflict": "Motivations & Internal Conflict",
    "character_arc": "Character Arc",
    "key_relationships": "Key Relationships",
    "complexity_nuance_lost_material": "Complexity & Lost Material",
}
DIM_MAX = {
    "personality_voice": 25,
    "narrative_role_agency": 20,
    "motivations_internal_conflict": 15,
    "character_arc": 15,
    "key_relationships": 10,
    "complexity_nuance_lost_material": 15,
}


def load_scores():
    """Load all individual score files from kiro directory."""
    scores = []
    for fname in sorted(os.listdir(SCORES_DIR)):
        if not fname.endswith(".json"):
            continue
        # Skip split directories that might appear as files
        fpath = os.path.join(SCORES_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath) as f:
            scores.append(json.load(f))
    return scores


def generate_ranking_table(scored, unscored):
    """Generate ranked table as CSV and markdown."""
    csv_path = os.path.join(OUTPUT_DIR, "ranking.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["Rank", "Character"]
            + [DIM_LABELS[d] for d in DIMENSIONS]
            + ["Total FP", "Screenplay Words", "Book Mentions"]
        )
        for i, s in enumerate(scored, 1):
            o = s["overall"]
            m = s.get("meta", {})
            w.writerow(
                [i, s["character"]]
                + [o.get(d, 0) for d in DIMENSIONS]
                + [o["total"], m.get("screenplay_words", 0), m.get("book_mentions", 0)]
            )

    # Markdown
    md_path = os.path.join(OUTPUT_DIR, "ranking.md")
    with open(md_path, "w") as f:
        f.write("# Character Faithfulness Rankings\n\n")
        f.write(f"Scored characters: {len(scored)}\n\n")
        f.write(
            "| Rank | Character | Pers | Role | Motiv | Arc | Rels | Lost | **Total** | Words | Mentions |\n"
        )
        f.write(
            "|------|-----------|------|------|-------|-----|------|------|-----------|-------|----------|\n"
        )
        for i, s in enumerate(scored, 1):
            o = s["overall"]
            m = s.get("meta", {})
            f.write(
                f"| {i} | {s['character']} | {o.get('personality_voice', 0)} | "
                f"{o.get('narrative_role_agency', 0)} | {o.get('motivations_internal_conflict', 0)} | "
                f"{o.get('character_arc', 0)} | {o.get('key_relationships', 0)} | "
                f"{o.get('complexity_nuance_lost_material', 0)} | **{o['total']}** | "
                f"{m.get('screenplay_words', 0)} | {m.get('book_mentions', 0)} |\n"
            )

        if unscored:
            f.write(f"\n\n## No Film Corpus ({len(unscored)} characters)\n\n")
            f.write(
                "These characters have book material but no screenplay corpus, so they cannot be scored for film faithfulness.\n\n"
            )
            f.write("| Character | Book Mentions |\n")
            f.write("|-----------|---------------|\n")
            for s in sorted(unscored, key=lambda x: x.get("meta", {}).get("book_mentions", 0), reverse=True):
                m = s.get("meta", {})
                f.write(f"| {s['character']} | {m.get('book_mentions', 0)} |\n")

    return csv_path, md_path


def generate_character_reports(scored):
    """Generate a detailed markdown report per character."""
    reports_dir = os.path.join(OUTPUT_DIR, "characters")
    os.makedirs(reports_dir, exist_ok=True)

    for rank, s in enumerate(scored, 1):
        name = s["character"]
        o = s["overall"]
        safe_name = name.lower().replace(" ", "_").replace(".", "").replace("'", "")

        with open(os.path.join(reports_dir, f"{safe_name}.md"), "w") as f:
            f.write(f"# {name}\n\n")
            f.write(f"**Rank:** #{rank} of {len(scored)}\n\n")

            # Overall scores
            f.write("## Overall Scores\n\n")
            f.write("| Dimension | Score |\n")
            f.write("|-----------|-------|\n")
            for dim in DIMENSIONS:
                f.write(f"| {DIM_LABELS[dim]} | {o.get(dim, 0)}/{DIM_MAX[dim]} |\n")
            f.write(f'| **Total FP** | **{o["total"]}/100** |\n\n')

            # Justifications from per_source.comparative
            per_source = s.get("per_source", {})
            comparative = per_source.get("comparative", {})
            justification = comparative.get("justification", {})
            if justification:
                f.write("## Per-Dimension Analysis\n\n")
                for dim in DIMENSIONS:
                    j = justification.get(dim, "")
                    if j:
                        f.write(f"### {DIM_LABELS[dim]} ({o.get(dim, 0)}/{DIM_MAX[dim]})\n\n")
                        f.write(f"{j}\n\n")

            # Key observations
            key_obs = comparative.get("key_observations", "")
            if key_obs:
                f.write(f"## Key Observations\n\n{key_obs}\n\n")

            # Lost material
            lost = comparative.get("lost_or_transferred_material", [])
            if lost:
                f.write("## Lost or Transferred Material\n\n")
                for item in lost:
                    f.write(f"- {item}\n")
                f.write("\n")

            # Metadata
            m = s.get("meta", {})
            f.write("## Presence Metrics\n\n")
            f.write(f'- Screenplay words: {m.get("screenplay_words", 0):,}\n')
            f.write(f'- Book mentions: {m.get("book_mentions", 0):,}\n')

    return reports_dir


def main():
    all_scores = load_scores()
    print(f"Loaded {len(all_scores)} score files from {SCORES_DIR}")

    # Separate scored (total > 0) from unscored (no film corpus)
    scored = [s for s in all_scores if s["overall"].get("total", 0) > 0]
    unscored = [s for s in all_scores if s["overall"].get("total", 0) == 0]

    scored.sort(key=lambda x: x["overall"]["total"], reverse=True)
    print(f"  Scored: {len(scored)}, No film corpus: {len(unscored)}")

    csv_path, md_path = generate_ranking_table(scored, unscored)
    print(f"  Ranking table: {csv_path}")
    print(f"  Ranking markdown: {md_path}")

    reports_dir = generate_character_reports(scored)
    print(f"  Character reports: {reports_dir}/ ({len(scored)} files)")

    print("\nDone.")


if __name__ == "__main__":
    main()
