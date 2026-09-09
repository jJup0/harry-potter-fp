#!/usr/bin/env python3
"""
FP Scoring Framework - main entry point.

Scores each character on 6 dimensions (total 100):
  - Personality & Voice (0-25), Narrative Role & Agency (0-20),
    Motivations & Internal Conflict (0-15), Character Arc (0-15),
    Key Relationships (0-10), Complexity & Lost Material (0-15)

Usage:
  python3 -u src/scoring/score.py --backend kiro --top 216
  python3 -u src/scoring/score.py --backend kiro --characters "Dobby" "Severus Snape"

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
import re
import sys
import yaml

from deleted_scenes import filter_deleted_scenes

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "output", "characters.yaml")
METRICS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "metrics")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIMENSIONS = ["personality_voice", "narrative_role_agency", "motivations_internal_conflict", "character_arc", "key_relationships", "complexity_nuance_lost_material"]
BACKENDS = ["kiro"]

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
    dirname = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    base = os.path.join(CORPUS_DIR, dirname)
    corpus = {"books": [], "screenplays": []}
    for sub in ("books", "screenplays"):
        path = os.path.join(base, sub, "scenes.json")
        if os.path.exists(path):
            with open(path) as f:
                corpus[sub] = json.load(f).get("scenes", [])
    return corpus


def film_corpus_empty(char_name):
    """True if the character has no film scenes left after deleted-scene cuts.

    This is what the deterministic zero score means, so it is also the only
    condition under which a cached zero stays valid. Corpora change as parsing
    and the deleted-scene list change, in both directions.
    """
    corpus = load_corpus(char_name)
    kept, _ = filter_deleted_scenes(corpus.get("screenplays", []), char_name)
    return not kept


def char_score_path(backend, char_name):
    """Path to individual character score file."""
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    d = os.path.join(OUTPUT_DIR, backend)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{safe}.json")


def get_scorer(backend):
    if backend == "kiro":
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
    backend = args.backend or scoring_config.get("backend", "kiro")

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

    # Determine current model and prompt major version for resume checks.
    # Read it from the scorer itself so this can never drift from the prompt the
    # scorer actually sends - it previously read scoring_prompt.txt while the
    # scorer used scoring_prompt_3.txt, so a major bump would have been ignored.
    current_model = scoring_config.get("llm", {}).get("model", "")
    from scorer_kiro import _get_prompt_version

    current_prompt_major = _get_prompt_version().split(".")[0]

    # Resume: check which characters already have individual score files
    # Skip only if same model AND same prompt major version AND same aliases AND same corpus version
    already_scored = set()
    alias_mismatch = set()
    corpus_version_mismatch = set()
    corpus_gained = set()
    corpus_emptied = set()
    current_corpus_version = str(scoring_config.get("corpus_version", 1))
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
            char_name = data.get("character", "")
            scored_total = data.get("overall", {}).get("total", 0)
            if scored_model is None and scored_total == 0:
                # Written by the deterministic zero path, which fires when the film
                # corpus is empty. Valid only while that is still true - characters
                # whose corpus later gained scenes were otherwise pinned at 0 forever.
                if film_corpus_empty(char_name):
                    already_scored.add(fname[:-5])
                else:
                    print(f"    {char_name}: zero score but film corpus is no longer empty")
                    corpus_gained.add(fname[:-5])
                continue
            if scored_total == 0 and meta.get("film_chars_sent", 0) == 0:
                # An LLM zero, but the scorer sent it no film text. Older scorer
                # versions did that even when the corpus had scenes, so the zero
                # reflects a broken call rather than a judgement. Gate on the
                # recorded byte count so a rescore cannot loop: once the model has
                # actually seen film text, its verdict stands.
                if film_corpus_empty(char_name):
                    already_scored.add(fname[:-5])
                else:
                    print(f"    {char_name}: scored 0 from an empty film corpus, but {len(load_corpus(char_name)['screenplays'])} film scenes exist")
                    corpus_gained.add(fname[:-5])
                continue
            if scored_total and film_corpus_empty(char_name):
                # The inverse: a real score whose film corpus has since emptied,
                # usually through the deleted-scene list. Sir Cadogan sat at 78
                # with nothing left in the films.
                print(f"    {char_name}: scored {scored_total} but film corpus is now empty")
                corpus_emptied.add(fname[:-5])
                continue
            if scored_model != current_model:
                print(f"    {char_name}: model mismatch ({scored_model} != {current_model})")
                continue
            if scored_major != current_prompt_major:
                print(f"    {char_name}: prompt version mismatch (v{scored_major}.x != v{current_prompt_major}.x)")
                continue
            # Check aliases
            scored_aliases = meta.get("aliases")
            if scored_aliases is not None:
                current_aliases = get_character_aliases(char_name)
                if scored_aliases != current_aliases:
                    print(f"    {char_name}: alias mismatch ({scored_aliases} != {current_aliases})")
                    alias_mismatch.add(fname[:-5])
                    continue
            # Check corpus version
            scored_corpus_ver = str(meta.get("corpus_version", 1))
            if scored_corpus_ver != current_corpus_version:
                print(f"    {char_name}: corpus version mismatch (v{scored_corpus_ver} != v{current_corpus_version})")
                corpus_version_mismatch.add(fname[:-5])
                continue
            already_scored.add(fname[:-5])
    if already_scored:
        print(
            f"  Cached: {len(already_scored)} characters (model={current_model}, prompt v{current_prompt_major}.x, corpus v{current_corpus_version})"
        )
    if alias_mismatch:
        print(f"  Re-scoring: {len(alias_mismatch)} characters with changed aliases")
    if corpus_version_mismatch:
        print(f"  Re-scoring: {len(corpus_version_mismatch)} characters with bumped corpus version")
    if corpus_gained:
        print(f"  Re-scoring: {len(corpus_gained)} characters pinned at 0 whose film corpus is no longer empty")
    if corpus_emptied:
        print(f"  Re-scoring: {len(corpus_emptied)} characters with a stale score and an empty film corpus")

    # Clear split caches for characters that need rescoring
    import shutil
    for safe in alias_mismatch | corpus_version_mismatch | corpus_gained | corpus_emptied:
        split_dir = os.path.join(score_dir, f"{safe}_split")
        if os.path.isdir(split_dir):
            shutil.rmtree(split_dir)

    scored = 0
    to_score = []
    for char in characters:
        name = char["name"]
        if args.characters and name not in args.characters:
            continue
        if name in SKIP_CHARACTERS:
            continue
        safe = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
        if safe in already_scored:
            continue
        corpus = load_corpus(name)
        # Exclude deleted/non-theatrical scenes from film corpus
        corpus["screenplays"], _ = filter_deleted_scenes(
            corpus["screenplays"], name
        )
        if not corpus["books"] and not corpus["screenplays"]:
            st_val = screen_time.get(name, {}).get("_total", 0)
            bm_val = book_mentions.get(name, {}).get("_total", 0)
            if st_val + bm_val < min_mentions:
                continue
        if args.top and len(to_score) >= args.top:
            break
        to_score.append((name, corpus))

    print(f"  Scoring {len(to_score)} characters with {scoring_config.get('parallel', 10)} workers")

    failures = []

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
        if not per_source:
            # No score file is written, so the next run retries this character.
            # Writing zeros here used to silently overwrite real scores and then
            # look identical to "absent from the films" in every report.
            failures.append(name)
            return None
        overall = aggregate_scores(per_source)
        current_aliases = get_character_aliases(name)
        for src_data in per_source.values():
            if isinstance(src_data, dict) and "meta" in src_data:
                src_data["meta"]["aliases"] = current_aliases
                src_data["meta"]["corpus_version"] = current_corpus_version
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
            name = futures[future]
            try:
                if future.result() is not None:
                    scored += 1
            except Exception as e:
                print(f"  ERROR {name}: {e}", flush=True)
                failures.append(name)

    if failures:
        errors_path = os.path.join(OUTPUT_DIR, backend, "_errors.json")
        with open(errors_path, "w") as f:
            json.dump({"failed": sorted(set(failures))}, f, indent=2)
        print(f"\n{len(set(failures))} characters failed and were left unscored, listed in {errors_path}")

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

    # A run where everything failed is an operational failure, not a result.
    # Five characters silently timing out used to look like a table of zeros.
    if to_score and scored == 0:
        print("ERROR: every character in this run failed to score", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
