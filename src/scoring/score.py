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
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "output", "characters.yaml")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "metrics")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIMENSIONS = ["personality_voice", "narrative_role_agency", "motivations_internal_conflict", "character_arc", "key_relationships", "complexity_nuance_lost_material"]
BACKENDS = ["comparative", "kiro"]

SKIP_CHARACTERS = {
    "You",
    "All",
    "Voice",
    "Hogwarts",
    "Weasley",
    "Everyone",
    "Someone",
    "Crowd",
    "Boy",
    "Man",
    "Woman",
    "Girl",
    "Student",
    "Students",
    "Death Eater",
    "Death Eaters",
    "Guard",
    "Wizard",
    "Wizards",
    "Gang",
    "Class",
    "Muggle",
    "Goblin",
    "Snatcher",
    "Radio",
    "Howler",
    "Pixie",
    "Hedwig",
    "Buckbeak",
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_characters():
    with open(CHARACTERS_FILE) as f:
        return yaml.safe_load(f)["characters"]


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
    dirname = char_name.lower().replace(" ", "_").replace(".", "_").replace("'", "_")
    base = os.path.join(CORPUS_DIR, dirname)
    corpus = {"books": [], "screenplays": []}
    for sub in ("books", "screenplays"):
        path = os.path.join(base, sub, "scenes.json")
        if os.path.exists(path):
            with open(path) as f:
                corpus[sub] = json.load(f).get("scenes", [])
    return corpus


def corpus_hash(corpus):
    """Short hash of corpus content for cache invalidation."""
    import hashlib
    h = hashlib.md5()
    for sub in ("books", "screenplays"):
        for s in corpus.get(sub, []):
            h.update(json.dumps(s, sort_keys=True).encode()[:200])
    return h.hexdigest()[:12]


def char_score_path(backend, char_name):
    """Path to individual character score file."""
    safe = char_name.lower().replace(" ", "_").replace(".", "_").replace("'", "_")
    d = os.path.join(OUTPUT_DIR, backend)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{safe}.json")


def get_scorer(backend):
    if backend == "comparative":
        import scorer_comparative

        return scorer_comparative.score_character
    elif backend == "kiro":
        import scorer_kiro

        return scorer_kiro.score_character
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose from: {BACKENDS}")


def aggregate_scores(per_source_scores):
    if not per_source_scores:
        return {d: 0 for d in DIMENSIONS}
    weights = {}
    for source, scores in per_source_scores.items():
        meta = scores.get("meta", {})
        weights[source] = max(meta.get("scenes", 0) + meta.get("paragraphs", 0), 1)
    total_weight = sum(weights.values())
    aggregated = {}
    for dim in DIMENSIONS:
        aggregated[dim] = round(
            sum(per_source_scores[src][dim] * weights[src] for src in per_source_scores)
            / total_weight,
            1,
        )
    aggregated["total"] = round(sum(aggregated[d] for d in DIMENSIONS), 1)
    return aggregated


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Score HP characters on faithfulness")
    parser.add_argument("--backend", choices=BACKENDS, help="Scoring backend")
    parser.add_argument("--characters", nargs="+", help="Only score these characters")
    parser.add_argument(
        "--top", type=int, help="Only score top N characters by presence"
    )
    args = parser.parse_args()

    config = load_config()
    scoring_config = config.get("scoring", {})
    backend = args.backend or scoring_config.get("backend", "rule_based")

    score_fn = get_scorer(backend)
    characters = load_characters()
    min_mentions = scoring_config.get("min_mentions", 10)

    # Load metrics for filtering
    screen_time, book_mentions = {}, {}
    st_path = os.path.join(METRICS_DIR, "screen_time_v2.json")
    bm_path = os.path.join(METRICS_DIR, "book_mentions_v2.json")
    if os.path.exists(st_path):
        with open(st_path) as f:
            screen_time = json.load(f)
    if os.path.exists(bm_path):
        with open(bm_path) as f:
            book_mentions = json.load(f)

    print(f"Scoring with '{backend}' backend")

    # Determine current model and prompt major version for resume checks
    current_model = scoring_config.get("llm", {}).get("model", "")
    prompt_version_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "src",
        "scoring",
        "prompts",
        "scoring_prompt.txt",
    )
    # Try reading from the prompt file directly
    prompt_file = os.path.join(
        PROJECT_ROOT, "src", "scoring", "prompts", "scoring_prompt.txt"
    )
    current_prompt_major = "0"
    if os.path.exists(prompt_file):
        with open(prompt_file) as f:
            first_line = f.readline().strip()
        if first_line.startswith("# version:"):
            ver = first_line.split(":", 1)[1].strip()
            current_prompt_major = ver.split(".")[0]

    # Resume: check which characters already have individual score files
    # Skip only if same model AND same prompt major version AND same aliases
    already_scored = set()
    alias_mismatch = set()
    corpus_mismatch = set()
    score_dir = os.path.join(OUTPUT_DIR, backend)
    if os.path.isdir(score_dir):
        for fname in os.listdir(score_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(score_dir, fname)
            with open(fpath) as f:
                data = json.load(f)
            meta = data.get("per_source", {}).get("comparative", {}).get("meta", {})
            scored_model = meta.get("model")
            scored_prompt_ver = meta.get("prompt_version", "0.0")
            scored_major = scored_prompt_ver.split(".")[0]
            if scored_model == current_model and scored_major == current_prompt_major:
                char_name = data.get("character", "")
                # Check aliases
                scored_aliases = meta.get("aliases")
                if scored_aliases is not None:
                    current_aliases = get_character_aliases(char_name)
                    if scored_aliases != current_aliases:
                        alias_mismatch.add(fname[:-5])
                        continue
                # Check corpus hash
                scored_hash = meta.get("corpus_hash")
                if scored_hash is not None:
                    corpus = load_corpus(char_name)
                    if corpus_hash(corpus) != scored_hash:
                        corpus_mismatch.add(fname[:-5])
                        continue
                already_scored.add(fname[:-5])
    if already_scored:
        print(
            f"  Resuming: {len(already_scored)} characters already scored (model={current_model}, prompt v{current_prompt_major}.x)"
        )
    if alias_mismatch:
        print(f"  Re-scoring: {len(alias_mismatch)} characters with changed aliases")
    if corpus_mismatch:
        print(f"  Re-scoring: {len(corpus_mismatch)} characters with changed corpus")

    scored = 0
    to_score = []
    for char in characters:
        name = char["name"]
        if args.characters and name not in args.characters:
            continue
        if name in SKIP_CHARACTERS:
            continue
        safe = name.lower().replace(" ", "_").replace(".", "_").replace("'", "_")
        if safe in already_scored:
            continue
        corpus = load_corpus(name)
        if not corpus["books"] and not corpus["screenplays"]:
            st_val = screen_time.get(name, {}).get("_total", 0)
            bm_val = book_mentions.get(name, {}).get("_total", 0)
            if st_val + bm_val < min_mentions:
                continue
        if args.top and len(to_score) >= args.top:
            break
        to_score.append((name, corpus))

    print(f"  Scoring {len(to_score)} characters with {scoring_config.get('parallel', 10)} workers")

    def score_one(item):
        name, corpus = item
        # Characters with no film scenes get deterministic zero
        if not corpus.get("screenplays"):
            print(f"  [skip] {name}: no film scenes", flush=True)
            book_words = sum(len(s.get("text", "").split()) for s in corpus.get("books", []))
            result = {
                "character": name,
                "overall": {"personality_voice": 0, "narrative_role_agency": 0, "motivations_internal_conflict": 0, "character_arc": 0, "key_relationships": 0, "complexity_nuance_lost_material": 0, "total": 0},
                "per_source": {"not_in_films": "Character does not appear in the film screenplay corpus. Score set to 0."},
                "meta": {
                    "screen_time_minutes": screen_time.get(name, {}).get("_total", 0),
                    "book_mentions": book_mentions.get(name, {}).get("_total", 0),
                    "screenplay_words": 0,
                    "book_words": book_words,
                },
            }
            with open(char_score_path(backend, name), "w") as f:
                json.dump(result, f, indent=2)
            return result
        print(f"  [start] {name}...", flush=True)
        per_source = score_fn(name, corpus, scoring_config)
        overall = aggregate_scores(per_source)
        current_aliases = get_character_aliases(name)
        c_hash = corpus_hash(corpus)
        for src_data in per_source.values():
            if isinstance(src_data, dict) and "meta" in src_data:
                src_data["meta"]["aliases"] = current_aliases
                src_data["meta"]["corpus_hash"] = c_hash
        # Compute corpus word counts
        film_words = 0
        char_aliases = {a.lower() for a in get_character_aliases(name)} | {name.lower()}
        for s in corpus.get("screenplays", []):
            for d in s.get("dialogue", []):
                speaker = d.get("speaker", "").lower()
                if any(alias in speaker or speaker in alias for alias in char_aliases if len(alias) >= 3):
                    film_words += len(d.get("text", "").split())
        book_words = sum(len(s.get("text", "").split()) for s in corpus.get("books", []))
        result = {
            "character": name,
            "overall": overall,
            "per_source": per_source,
            "meta": {
                "screen_time_minutes": screen_time.get(name, {}).get("_total", 0),
                "book_mentions": book_mentions.get(name, {}).get("_total", 0),
                "screenplay_words": film_words,
                "book_words": book_words,
            },
        }
        with open(char_score_path(backend, name), "w") as f:
            json.dump(result, f, indent=2)
        print(f"  [done] {name}: {overall.get('total', '?')}", flush=True)
        return result

    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = scoring_config.get("parallel", 10)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(score_one, item): item[0] for item in to_score}
        for future in as_completed(futures):
            try:
                future.result()
                scored += 1
            except Exception as e:
                print(f"  ERROR {futures[future]}: {e}", flush=True)

    # Collect all individual scores into combined file
    all_scores = []
    score_dir = os.path.join(OUTPUT_DIR, backend)
    if os.path.isdir(score_dir):
        for fname in sorted(os.listdir(score_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(score_dir, fname)) as f:
                    all_scores.append(json.load(f))
    all_scores.sort(key=lambda x: x["overall"].get("total", 0), reverse=True)

    combined_path = os.path.join(OUTPUT_DIR, f"scores_{backend}.json")
    with open(combined_path, "w") as f:
        json.dump(all_scores, f, indent=2)

    print(f"\nScored {len(all_scores)} characters total ({scored} new)")
    print(
        f"{'Character':<30} {'TOTAL':>7}"
    )
    print("-" * 40)
    for s in all_scores[:25]:
        o = s["overall"]
        print(
            f"{s['character']:<30} {o['total']:>7}"
        )
    print(f"\nSaved to {combined_path}")


if __name__ == "__main__":
    main()
