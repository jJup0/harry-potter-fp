#!/usr/bin/env python3
"""
Generate output reports from scores.
- Ranked table (CSV + markdown)
- Per-character detailed report (markdown)
"""
import csv
import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCORES_FILE = os.path.join(PROJECT_ROOT, "output", "scores", "scores_comparative.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]
DIM_LABELS = {"personality": "Personality", "narrative_role": "Narrative Role",
              "motivations": "Motivations", "character_arc": "Character Arc"}


def generate_ranking_table(scores):
    """Generate ranked table as CSV and markdown."""
    # CSV
    csv_path = os.path.join(OUTPUT_DIR, 'ranking.csv')
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Rank', 'Character', 'Personality', 'Narrative Role',
                     'Motivations', 'Character Arc', 'Total FP',
                     'Screenplay Words', 'Book Mentions'])
        for i, s in enumerate(scores, 1):
            o = s['overall']
            m = s.get('meta', {})
            w.writerow([i, s['character'], o['personality'], o['narrative_role'],
                        o['motivations'], o['character_arc'], o['total'],
                        m.get('screenplay_words', 0), m.get('book_mentions', 0)])

    # Markdown
    md_path = os.path.join(OUTPUT_DIR, 'ranking.md')
    with open(md_path, 'w') as f:
        f.write('# Character Faithfulness Rankings\n\n')
        f.write(f'Total characters scored: {len(scores)}\n\n')
        f.write('| Rank | Character | Pers | Role | Motiv | Arc | **Total** | Words | Mentions |\n')
        f.write('|------|-----------|------|------|-------|-----|-----------|-------|----------|\n')
        for i, s in enumerate(scores, 1):
            o = s['overall']
            m = s.get('meta', {})
            f.write(f"| {i} | {s['character']} | {o['personality']} | {o['narrative_role']} | "
                    f"{o['motivations']} | {o['character_arc']} | **{o['total']}** | "
                    f"{m.get('screenplay_words', 0)} | {m.get('book_mentions', 0)} |\n")

    return csv_path, md_path


def generate_character_reports(scores):
    """Generate a detailed markdown report per character."""
    reports_dir = os.path.join(OUTPUT_DIR, 'characters')
    os.makedirs(reports_dir, exist_ok=True)

    for rank, s in enumerate(scores, 1):
        name = s['character']
        o = s['overall']
        safe_name = name.lower().replace(' ', '_').replace('.', '').replace("'", '')

        with open(os.path.join(reports_dir, f'{safe_name}.md'), 'w') as f:
            f.write(f'# {name}\n\n')
            f.write(f'**Rank:** #{rank} of {len(scores)}\n\n')

            # Overall scores
            f.write('## Overall Scores\n\n')
            f.write(f'| Dimension | Score (/25) |\n')
            f.write(f'|-----------|-------------|\n')
            for dim in DIMENSIONS:
                f.write(f'| {DIM_LABELS[dim]} | {o[dim]} |\n')
            f.write(f'| **Total FP** | **{o["total"]}** |\n\n')

            # Per-source breakdown
            f.write('## Per-Source Breakdown\n\n')
            for source, src_scores in s.get('per_source', {}).items():
                meta = src_scores.get('meta', {})
                src_type = meta.get('type', 'unknown')
                f.write(f'### {source} ({src_type})\n\n')

                if src_type == 'screenplay':
                    f.write(f'- Scenes: {meta.get("scenes", 0)}\n')
                    f.write(f'- Dialogue lines: {meta.get("dialogue_lines", 0)}\n')
                elif src_type == 'book':
                    f.write(f'- Paragraphs: {meta.get("paragraphs", 0)}\n')
                    f.write(f'- Dialogue paragraphs: {meta.get("dialogue_paragraphs", 0)}\n')
                    f.write(f'- Total words: {meta.get("total_words", 0):,}\n')
                elif src_type == 'comparative':
                    f.write(f'- Book chars sent: {meta.get("book_chars_sent", 0):,}\n')
                    f.write(f'- Film chars sent: {meta.get("film_chars_sent", 0):,}\n')

                f.write(f'\n| Dimension | Score |\n|-----------|-------|\n')
                for dim in DIMENSIONS:
                    f.write(f'| {DIM_LABELS[dim]} | {src_scores.get(dim, 0)} |\n')
                f.write('\n')

                # Justifications (comparative scorer)
                justification = src_scores.get('justification', {})
                if justification:
                    f.write('#### Justifications\n\n')
                    for dim in DIMENSIONS:
                        j = justification.get(dim, '')
                        if j:
                            f.write(f'**{DIM_LABELS[dim]}:** {j}\n\n')

                key_obs = src_scores.get('key_observations', '')
                if key_obs:
                    f.write(f'**Key observations:** {key_obs}\n\n')

            # Metadata
            m = s.get('meta', {})
            f.write('## Presence Metrics\n\n')
            f.write(f'- Screenplay words spoken: {m.get("screenplay_words", 0):,}\n')
            f.write(f'- Book mentions: {m.get("book_mentions", 0):,}\n')

    return reports_dir


def main():
    with open(SCORES_FILE) as f:
        scores = json.load(f)

    print(f"Generating reports for {len(scores)} characters...")

    csv_path, md_path = generate_ranking_table(scores)
    print(f"  Ranking table: {csv_path}")
    print(f"  Ranking markdown: {md_path}")

    reports_dir = generate_character_reports(scores)
    print(f"  Character reports: {reports_dir}/ ({len(scores)} files)")

    print("\nDone.")


if __name__ == '__main__':
    main()
