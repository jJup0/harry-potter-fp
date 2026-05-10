#!/usr/bin/env python3
"""
FP Scoring Framework - main entry point.

Scores each character on 4 dimensions (each out of 25, total 100):
  - Personality, Narrative Role, Motivations, Character Arc

Usage:
  python3 -u src/scoring/score.py --backend comparative --top 216
  python3 -u src/scoring/score.py --backend comparative --characters "Dobby" "Severus Snape"

Resume logic:
  Writes individual JSON files per character to output/scores/<backend>/.
  On resume, skips characters that already have a score file with the same
  model AND prompt major version. Changing the model or bumping the prompt
  major version (e.g. 1.x -> 2.x) triggers a rescore. Minor version bumps
  (e.g. 1.0 -> 1.1) do NOT trigger a rescore.

  Prompt version is read from the first line of src/scoring/prompts/scoring_prompt.txt:
    # version: <major>.<minor>
"""
import json
import os
import sys
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "data", "v2", "corpus")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "v2", "characters.yaml")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "metrics")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]
BACKENDS = ['comparative']

SKIP_CHARACTERS = {
    'You', 'All', 'Voice', 'Hogwarts', 'Weasley', 'Everyone', 'Someone',
    'Crowd', 'Boy', 'Man', 'Woman', 'Girl', 'Student', 'Students',
    'Death Eater', 'Death Eaters', 'Guard', 'Wizard', 'Wizards',
    'Gang', 'Class', 'Muggle', 'Goblin', 'Snatcher', 'Radio',
    'Howler', 'Pixie', 'Hedwig', 'Buckbeak',
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_characters():
    with open(CHARACTERS_FILE) as f:
        return yaml.safe_load(f)['characters']


def get_character_aliases(char_name):
    """Get the current alias list for a character from the registry."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "collect"))
    from build_character_registry import KNOWN_CHARACTERS
    for canonical, aliases in KNOWN_CHARACTERS.items():
        if canonical == char_name:
            return sorted(aliases)
        if char_name in aliases:
            return sorted(aliases)
    return []


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


def char_score_path(backend, char_name):
    """Path to individual character score file."""
    safe = char_name.lower().replace(' ', '_').replace('.', '_').replace("'", '_')
    d = os.path.join(OUTPUT_DIR, backend)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{safe}.json')


def get_scorer(backend):
    if backend == 'comparative':
        import scorer_comparative
        return scorer_comparative.score_character
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

    # Determine current model and prompt major version for resume checks
    current_model = scoring_config.get('llm', {}).get('model', '')
    prompt_version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'scoring', 'prompts', 'scoring_prompt.txt')
    # Try reading from the prompt file directly
    prompt_file = os.path.join(PROJECT_ROOT, 'src', 'scoring', 'prompts', 'scoring_prompt.txt')
    current_prompt_major = '0'
    if os.path.exists(prompt_file):
        with open(prompt_file) as f:
            first_line = f.readline().strip()
        if first_line.startswith('# version:'):
            ver = first_line.split(':', 1)[1].strip()
            current_prompt_major = ver.split('.')[0]

    # Resume: check which characters already have individual score files
    # Skip only if same model AND same prompt major version AND same aliases
    already_scored = set()
    alias_mismatch = set()
    score_dir = os.path.join(OUTPUT_DIR, backend)
    if os.path.isdir(score_dir):
        for fname in os.listdir(score_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(score_dir, fname)
            with open(fpath) as f:
                data = json.load(f)
            meta = data.get('per_source', {}).get('comparative', {}).get('meta', {})
            scored_model = meta.get('model')
            scored_prompt_ver = meta.get('prompt_version', '0.0')
            scored_major = scored_prompt_ver.split('.')[0]
            if scored_model == current_model and scored_major == current_prompt_major:
                # Check aliases match
                char_name = data.get('character', '')
                scored_aliases = meta.get('aliases')
                if scored_aliases is not None:
                    current_aliases = get_character_aliases(char_name)
                    if scored_aliases != current_aliases:
                        alias_mismatch.add(fname[:-5])
                        continue
                already_scored.add(fname[:-5])
    if already_scored:
        print(f"  Resuming: {len(already_scored)} characters already scored (model={current_model}, prompt v{current_prompt_major}.x)")
    if alias_mismatch:
        print(f"  Re-scoring: {len(alias_mismatch)} characters with changed aliases")

    scored = 0
    try:
        for char in characters:
            name = char['name']
            if args.characters and name not in args.characters:
                continue
            if name in SKIP_CHARACTERS:
                continue
            # Check if already scored by filename
            safe = name.lower().replace(' ', '_').replace('.', '_').replace("'", '_')
            if safe in already_scored:
                continue
            corpus = load_corpus(name)
            if not corpus['books'] and not corpus['screenplays']:
                st_val = screen_time.get(name, {}).get('_total', 0)
                bm_val = book_mentions.get(name, {}).get('_total', 0)
                if st_val + bm_val < min_mentions:
                    continue
            if args.top and scored >= args.top:
                break

            print(f"  [{len(already_scored) + scored + 1}] {name}...")
            per_source = score_fn(name, corpus, scoring_config)
            overall = aggregate_scores(per_source)

            # Store current aliases in meta for cache invalidation
            current_aliases = get_character_aliases(name)
            for src_data in per_source.values():
                if isinstance(src_data, dict) and 'meta' in src_data:
                    src_data['meta']['aliases'] = current_aliases

            result = {
                'character': name, 'overall': overall, 'per_source': per_source,
                'meta': {
                    'screenplay_words': screen_time.get(name, {}).get('_total', 0),
                    'book_mentions': book_mentions.get(name, {}).get('_total', 0),
                },
            }

            # Write individual file
            with open(char_score_path(backend, name), 'w') as f:
                json.dump(result, f, indent=2)

            scored += 1
    finally:
        pass

    # Collect all individual scores into combined file
    all_scores = []
    score_dir = os.path.join(OUTPUT_DIR, backend)
    if os.path.isdir(score_dir):
        for fname in sorted(os.listdir(score_dir)):
            if fname.endswith('.json'):
                with open(os.path.join(score_dir, fname)) as f:
                    all_scores.append(json.load(f))
    all_scores.sort(key=lambda x: x['overall'].get('total', 0), reverse=True)

    combined_path = os.path.join(OUTPUT_DIR, f'scores_{backend}.json')
    with open(combined_path, 'w') as f:
        json.dump(all_scores, f, indent=2)

    print(f"\nScored {len(all_scores)} characters total ({scored} new)")
    print(f"{'Character':<30} {'Pers':>5} {'Role':>5} {'Motiv':>5} {'Arc':>5} {'TOTAL':>7}")
    print("-" * 63)
    for s in all_scores[:25]:
        o = s['overall']
        print(f"{s['character']:<30} {o['personality']:>5} {o['narrative_role']:>5} "
              f"{o['motivations']:>5} {o['character_arc']:>5} {o['total']:>7}")
    print(f"\nSaved to {combined_path}")


if __name__ == '__main__':
    main()
