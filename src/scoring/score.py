#!/usr/bin/env python3
"""
FP Scoring Framework - main entry point.

Scores each character on 4 dimensions (each out of 25, total 100):
  - Personality, Narrative Role, Motivations, Character Arc

Usage:
  python3 src/scoring/score.py --backend rule_based --top 20
  python3 src/scoring/score.py --backend kiro --characters "Dobby"
  python3 src/scoring/score.py --backend openai --top 10

Backends (--backend):
  - rule_based: deterministic heuristics (placeholder - scores by corpus size, NOT real FP)
  - openai: any OpenAI-compatible API (OpenAI, ollama, litellm, etc.)
  - kiro: pipes prompt to kiro-cli --no-interactive

KNOWN ISSUE: Both LLM backends (kiro, openai) currently fail with all-zero scores.
The fundamental design flaw is that the scorer sends one source at a time (just book
OR just screenplay), but FP requires comparing book vs film together.
See PLAN.md task #1.
"""
import json
import os
import sys
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "characters.yaml")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "metrics")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Add scoring dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]
BACKENDS = ['rule_based', 'openai', 'kiro']


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_characters():
    with open(CHARACTERS_FILE) as f:
        return yaml.safe_load(f)['characters']


def load_corpus(char_name):
    dirname = char_name.lower().replace(' ', '_').replace('.', '_').replace("'", '_')
    base = os.path.join(CORPUS_DIR, dirname)
    corpus = {'books': [], 'screenplays': []}
    for sub in ('books', 'screenplays'):
        path = os.path.join(base, sub, 'scenes.json')
        if os.path.exists(path):
            with open(path) as f:
                corpus[sub] = json.load(f).get('scenes', [])
    return corpus


def get_scorer(backend):
    if backend == 'rule_based':
        import scorer_rule_based
        return scorer_rule_based.score_character
    elif backend == 'openai':
        import scorer_openai
        return scorer_openai.score_character
    elif backend == 'kiro':
        import scorer_kiro
        return scorer_kiro.score_character
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose from: {BACKENDS}")


def aggregate_scores(per_source_scores):
    if not per_source_scores:
        return {d: 0 for d in DIMENSIONS}
    weights = {}
    for source, scores in per_source_scores.items():
        meta = scores.get('meta', {})
        weights[source] = max(meta.get('scenes', 0) + meta.get('paragraphs', 0), 1)
    total_weight = sum(weights.values())
    aggregated = {}
    for dim in DIMENSIONS:
        aggregated[dim] = round(
            sum(per_source_scores[src][dim] * weights[src] for src in per_source_scores) / total_weight, 1)
    aggregated['total'] = round(sum(aggregated[d] for d in DIMENSIONS), 1)
    return aggregated


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Score HP characters on faithfulness')
    parser.add_argument('--backend', choices=BACKENDS, help='Scoring backend')
    parser.add_argument('--characters', nargs='+', help='Only score these characters')
    parser.add_argument('--top', type=int, help='Only score top N characters by presence')
    args = parser.parse_args()

    config = load_config()
    scoring_config = config.get('scoring', {})
    backend = args.backend or scoring_config.get('backend', 'rule_based')

    score_fn = get_scorer(backend)
    characters = load_characters()
    min_mentions = scoring_config.get('min_mentions', 10)

    # Load metrics for filtering
    screen_time, book_mentions = {}, {}
    st_path = os.path.join(METRICS_DIR, 'screen_time.json')
    bm_path = os.path.join(METRICS_DIR, 'book_mentions.json')
    if os.path.exists(st_path):
        with open(st_path) as f:
            screen_time = json.load(f)
    if os.path.exists(bm_path):
        with open(bm_path) as f:
            book_mentions = json.load(f)

    print(f"Scoring with '{backend}' backend")
    all_scores = []
    scored = 0

    try:
        for char in characters:
            name = char['name']
            if args.characters and name not in args.characters:
                continue
            st = screen_time.get(name, {}).get('_total', 0)
            bm = book_mentions.get(name, {}).get('_total', 0)
            if st + bm < min_mentions:
                continue
            if args.top and scored >= args.top:
                break

            corpus = load_corpus(name)
            if not corpus['books'] and not corpus['screenplays']:
                continue

            print(f"  [{scored+1}] {name}...")
            per_source = score_fn(name, corpus, scoring_config)
            overall = aggregate_scores(per_source)

            all_scores.append({
                'character': name, 'overall': overall, 'per_source': per_source,
                'meta': {'screenplay_words': st, 'book_mentions': bm},
            })
            scored += 1
    finally:
        # Cleanup persistent sessions
        if backend == 'kiro':
            import scorer_kiro
            scorer_kiro.shutdown()

    all_scores.sort(key=lambda x: x['overall'].get('total', 0), reverse=True)

    out_file = f'scores_{backend}.json'
    out_path = os.path.join(OUTPUT_DIR, out_file)
    with open(out_path, 'w') as f:
        json.dump(all_scores, f, indent=2)

    print(f"\nScored {len(all_scores)} characters")
    print(f"{'Character':<30} {'Pers':>5} {'Role':>5} {'Motiv':>5} {'Arc':>5} {'TOTAL':>7}")
    print("-" * 63)
    for s in all_scores[:25]:
        o = s['overall']
        print(f"{s['character']:<30} {o['personality']:>5} {o['narrative_role']:>5} "
              f"{o['motivations']:>5} {o['character_arc']:>5} {o['total']:>7}")
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
