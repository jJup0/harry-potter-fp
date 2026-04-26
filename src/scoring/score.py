#!/usr/bin/env python3
"""
FP Scoring Framework.

Scores each character on 4 dimensions (each out of 25, total 100):
  - Personality
  - Narrative Role
  - Motivations
  - Character Arc

Supports two backends:
  - rule-based: deterministic scoring from configurable rules (TODO: plug in Aitor's rules)
  - llm-based: sends character corpus to an LLM for scoring

Scores per-film/book, then aggregates.
Outputs to output/scores/
"""
import json
import os
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "characters.yaml")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "metrics")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_characters():
    with open(CHARACTERS_FILE) as f:
        return yaml.safe_load(f)['characters']


def load_corpus(char_name):
    """Load a character's full corpus (books + screenplays)."""
    dirname = char_name.lower().replace(' ', '_').replace('.', '_').replace("'", '_')
    base = os.path.join(CORPUS_DIR, dirname)
    corpus = {'books': [], 'screenplays': []}
    for sub in ('books', 'screenplays'):
        path = os.path.join(base, sub, 'scenes.json')
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            corpus[sub] = data.get('scenes', [])
    return corpus


def group_by_source(scenes):
    """Group scenes by their source (film/book name)."""
    groups = {}
    for s in scenes:
        src = s.get('source', 'unknown')
        if src not in groups:
            groups[src] = []
        groups[src].append(s)
    return groups


# --- Rule-based backend (placeholder) ---

def score_rule_based(char_name, corpus, rules):
    """
    Score a character using deterministic rules.
    `rules` is a dict loaded from config.yaml with scoring criteria.

    TODO: Implement when Aitor provides the rules document.
    Currently returns placeholder scores based on corpus size heuristics.
    """
    per_source = {}

    # Score screenplays
    sp_groups = group_by_source(corpus['screenplays'])
    for source, scenes in sp_groups.items():
        dialogue_count = sum(len(s.get('dialogue', [])) for s in scenes)
        direction_count = sum(len(s.get('directions', [])) for s in scenes)
        presence = min(25, len(scenes))  # crude placeholder

        per_source[source] = {
            'personality': _placeholder_score(dialogue_count, 50),
            'narrative_role': _placeholder_score(len(scenes), 10),
            'motivations': _placeholder_score(dialogue_count, 30),
            'character_arc': _placeholder_score(len(scenes), 15),
            'meta': {
                'type': 'screenplay',
                'scenes': len(scenes),
                'dialogue_lines': dialogue_count,
                'directions': direction_count,
            }
        }

    # Score books
    bk_groups = group_by_source(corpus['books'])
    for source, scenes in bk_groups.items():
        dialogue_count = sum(1 for s in scenes if s.get('has_dialogue'))
        total_words = sum(len(s.get('text', '').split()) for s in scenes)

        per_source[source] = {
            'personality': _placeholder_score(dialogue_count, 50),
            'narrative_role': _placeholder_score(len(scenes), 100),
            'motivations': _placeholder_score(dialogue_count, 30),
            'character_arc': _placeholder_score(len(scenes), 150),
            'meta': {
                'type': 'book',
                'paragraphs': len(scenes),
                'dialogue_paragraphs': dialogue_count,
                'total_words': total_words,
            }
        }

    return per_source


def _placeholder_score(value, threshold):
    """Placeholder: scale value to 0-25 based on threshold. Replace with real rules."""
    return round(min(25, (value / max(threshold, 1)) * 25), 1)


# --- LLM-based backend ---

# Import from llm_scorer module (same directory)
from llm_scorer import score_llm_based


# --- Aggregation ---

def aggregate_scores(per_source_scores):
    """Aggregate per-source scores into overall character score."""
    if not per_source_scores:
        return {d: 0 for d in DIMENSIONS}

    # Weighted average: weight by number of scenes/paragraphs
    weights = {}
    for source, scores in per_source_scores.items():
        meta = scores.get('meta', {})
        w = meta.get('scenes', 0) + meta.get('paragraphs', 0)
        weights[source] = max(w, 1)

    total_weight = sum(weights.values())
    aggregated = {}
    for dim in DIMENSIONS:
        weighted_sum = sum(
            per_source_scores[src][dim] * weights[src]
            for src in per_source_scores
        )
        aggregated[dim] = round(weighted_sum / total_weight, 1)

    aggregated['total'] = round(sum(aggregated[d] for d in DIMENSIONS), 1)
    return aggregated


# --- Main ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Score HP characters on faithfulness')
    parser.add_argument('--backend', choices=['rule_based', 'llm'], help='Override scoring backend')
    parser.add_argument('--characters', nargs='+', help='Only score these characters (by name)')
    parser.add_argument('--top', type=int, default=None, help='Only score top N characters by presence')
    args = parser.parse_args()

    config = load_config()
    scoring_config = config.get('scoring', {})
    backend = args.backend or scoring_config.get('backend', 'rule_based')
    min_mentions = scoring_config.get('min_mentions', 10)
    rules = scoring_config.get('rules', {})

    characters = load_characters()
    print(f"Scoring {len(characters)} characters using '{backend}' backend")

    # Load metrics for filtering
    screen_time_path = os.path.join(METRICS_DIR, 'screen_time.json')
    book_mentions_path = os.path.join(METRICS_DIR, 'book_mentions.json')
    screen_time = {}
    book_mentions = {}
    if os.path.exists(screen_time_path):
        with open(screen_time_path) as f:
            screen_time = json.load(f)
    if os.path.exists(book_mentions_path):
        with open(book_mentions_path) as f:
            book_mentions = json.load(f)

    all_scores = []
    scored = 0

    for char in characters:
        name = char['name']

        # CLI filters
        if args.characters and name not in args.characters:
            continue

        # Filter: only score characters with enough presence
        st = screen_time.get(name, {}).get('_total', 0)
        bm = book_mentions.get(name, {}).get('_total', 0)
        if st + bm < min_mentions:
            continue

        if args.top and scored >= args.top:
            break

        corpus = load_corpus(name)
        if not corpus['books'] and not corpus['screenplays']:
            continue

        print(f"  Scoring {name}...")
        if backend == 'rule_based':
            per_source = score_rule_based(name, corpus, rules)
        elif backend == 'llm':
            per_source = score_llm_based(name, corpus, scoring_config)
        else:
            raise ValueError(f"Unknown backend: {backend}")

        overall = aggregate_scores(per_source)

        result = {
            'character': name,
            'overall': overall,
            'per_source': per_source,
            'meta': {
                'screenplay_words': st,
                'book_mentions': bm,
            }
        }
        all_scores.append(result)
        scored += 1

    # Sort by total score
    all_scores.sort(key=lambda x: x['overall'].get('total', 0), reverse=True)

    # Save full results
    out_filename = f'scores_{backend}.json' if backend == 'llm' else 'scores.json'
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    with open(out_path, 'w') as f:
        json.dump(all_scores, f, indent=2)

    # Print summary
    print(f"\nScored {len(all_scores)} characters")
    print(f"{'Character':<30} {'Pers':>5} {'Role':>5} {'Motiv':>5} {'Arc':>5} {'TOTAL':>7}")
    print("-" * 63)
    for s in all_scores[:25]:
        o = s['overall']
        print(f"{s['character']:<30} {o['personality']:>5} {o['narrative_role']:>5} "
              f"{o['motivations']:>5} {o['character_arc']:>5} {o['total']:>7}")

    print(f"\nFull scores saved to {out_path}")


if __name__ == '__main__':
    main()
