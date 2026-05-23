"""
CIDS (Character Infidelity Damage Score) scorer.
Reuses kiro-cli backend from scorer_kiro.py.
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorer_kiro import _call_kiro, _prepare_corpus, _extract_json

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus")
SCORES_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "kiro")
CIDS_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "cids")
PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "cids_prompt.txt")
RAW_DIR = "/tmp/harry-potter-cids-raw"

os.makedirs(CIDS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

STRUCTURAL_MULTIPLIERS = {1: 1.0, 2: 1.1, 3: 1.25, 4: 1.5, 5: 2.0}
MAX_RETRIES = 3


def load_prompt():
    with open(PROMPT_FILE) as f:
        return f.read()


def load_fp_score(char_name):
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    path = os.path.join(SCORES_DIR, f"{safe}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    return data.get("overall", {}).get("total")


def load_corpus(char_name):
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    base = os.path.join(CORPUS_DIR, safe)
    corpus = {"books": [], "screenplays": []}
    for sub in ("books", "screenplays"):
        path = os.path.join(base, sub, "scenes.json")
        if os.path.exists(path):
            with open(path) as f:
                corpus[sub] = json.load(f).get("scenes", [])
    return corpus


SPLIT_THRESHOLD = 400_000  # chars, triggers per-book splitting


def score_cids(char_name, fp_score, corpus, model):
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    out_path = os.path.join(CIDS_DIR, f"{safe}.json")
    if os.path.exists(out_path):
        print(f"  [cached] {char_name}", flush=True)
        return json.load(open(out_path))

    book_text = _prepare_corpus(corpus["books"], "book")
    film_text = _prepare_corpus(corpus["screenplays"], "screenplay")

    if not film_text.strip():
        print(f"  [skip] {char_name}: no film corpus", flush=True)
        return None

    total_chars = len(book_text) + len(film_text)
    if total_chars > SPLIT_THRESHOLD:
        return _score_cids_split(char_name, fp_score, corpus, model, safe, out_path)

    prompt_template = load_prompt()
    prompt = prompt_template.format(
        character=char_name,
        fp_score=fp_score,
        book_corpus=book_text,
        film_corpus=film_text,
    )

    print(f"  [{char_name}] calling kiro-cli ({model})...", flush=True)
    try:
        response = _call_kiro(prompt, model)
    except Exception as e:
        print(f"  [{char_name}] error: {e}", flush=True)
        return None

    # Save raw
    raw_path = os.path.join(RAW_DIR, f"{safe}_raw.txt")
    with open(raw_path, "w") as f:
        f.write(response)

    parsed = _extract_json(response)
    if parsed is None:
        print(f"  [{char_name}] failed to parse JSON", flush=True)
        return None

    if "damaging_scenes" not in parsed:
        print(f"  [{char_name}] missing damaging_scenes", flush=True)
        return None

    # Compute CIDS
    infidelity = 100 - fp_score
    wie = sum(
        s.get("exposure", 0) * s.get("impact_weight", 0)
        for s in parsed["damaging_scenes"]
    )
    cids = infidelity * wie
    sdl = parsed.get("structural_damage_level", 1)
    multiplier = STRUCTURAL_MULTIPLIERS.get(sdl, 1.0)

    total_exposure = sum(s.get("exposure", 0) for s in parsed["damaging_scenes"])

    result = {
        "character": char_name,
        "fp_score": fp_score,
        "infidelity_score": infidelity,
        "weighted_infidelity_exposure": wie,
        "cids": cids,
        "damage_per_exposure": round(cids / total_exposure, 1) if total_exposure > 0 else 0,
        "structural_damage_level": sdl,
        "structural_damage_multiplier": multiplier,
        "adjusted_cids": round(cids * multiplier, 1),
        "main_damage_causes": parsed.get("main_damage_causes", []),
        "damaging_scenes": parsed["damaging_scenes"],
        "confidence": parsed.get("confidence", {}),
        "meta": {"model": model},
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  [done] {char_name}: CIDS={cids:.0f}, adjusted={result['adjusted_cids']:.0f}", flush=True)
    return result


def _score_cids_split(char_name, fp_score, corpus, model, safe, out_path):
    """Score CIDS per-book then merge damaging scenes."""
    from collections import defaultdict

    by_book = defaultdict(list)
    for s in corpus["books"]:
        by_book[s.get("source", "unknown")].append(s)
    by_film = defaultdict(list)
    for s in corpus["screenplays"]:
        by_film[s.get("source", "unknown")].append(s)

    def get_film_scenes(book_name):
        if book_name in by_film:
            return by_film[book_name]
        if "deathly_hallows" in book_name:
            return by_film.get("7_deathly_hallows_p1", []) + by_film.get("8_deathly_hallows_p2", [])
        prefix = book_name.split("_")[0]
        for film_name, scenes in by_film.items():
            if film_name.startswith(prefix + "_"):
                return scenes
        return []

    prompt_template = load_prompt()
    all_scenes = []
    all_causes = []
    max_sdl = 1

    for book_name in sorted(by_book.keys()):
        book_scenes = by_book[book_name]
        film_scenes = get_film_scenes(book_name)
        if not film_scenes:
            continue
        book_text = _prepare_corpus(book_scenes, "book")
        film_text = _prepare_corpus(film_scenes, "screenplay")
        prompt = prompt_template.format(
            character=char_name,
            fp_score=fp_score,
            book_corpus=book_text,
            film_corpus=film_text,
        )
        print(f"  [{char_name}][{book_name}] calling kiro-cli ({model})...", flush=True)
        try:
            response = _call_kiro(prompt, model)
        except Exception as e:
            print(f"  [{char_name}][{book_name}] error: {e}", flush=True)
            continue

        raw_path = os.path.join(RAW_DIR, f"{safe}_{book_name}_raw.txt")
        with open(raw_path, "w") as f:
            f.write(response)

        parsed = _extract_json(response)
        if not parsed or "damaging_scenes" not in parsed:
            print(f"  [{char_name}][{book_name}] failed to parse", flush=True)
            continue

        all_scenes.extend(parsed["damaging_scenes"])
        all_causes.extend(parsed.get("main_damage_causes", []))
        max_sdl = max(max_sdl, parsed.get("structural_damage_level", 1))
        print(f"  [{char_name}][{book_name}] {len(parsed['damaging_scenes'])} damaging scenes", flush=True)

    if not all_scenes:
        print(f"  [{char_name}] no damaging scenes found across all books", flush=True)
        return None

    # Compute final CIDS
    infidelity = 100 - fp_score
    wie = sum(s.get("exposure", 0) * s.get("impact_weight", 0) for s in all_scenes)
    cids = infidelity * wie
    total_exposure = sum(s.get("exposure", 0) for s in all_scenes)
    multiplier = STRUCTURAL_MULTIPLIERS.get(max_sdl, 1.0)

    # Deduplicate causes, keep top 3
    seen = set()
    unique_causes = []
    for c in all_causes:
        if c not in seen:
            seen.add(c)
            unique_causes.append(c)

    result = {
        "character": char_name,
        "fp_score": fp_score,
        "infidelity_score": infidelity,
        "weighted_infidelity_exposure": wie,
        "cids": cids,
        "damage_per_exposure": round(cids / total_exposure, 1) if total_exposure > 0 else 0,
        "structural_damage_level": max_sdl,
        "structural_damage_multiplier": multiplier,
        "adjusted_cids": round(cids * multiplier, 1),
        "main_damage_causes": unique_causes[:5],
        "damaging_scenes": all_scenes,
        "confidence": {"global": "Medium", "exposure_estimate": "Medium", "impact_assessment": "Medium"},
        "meta": {"model": model, "split": True},
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  [done] {char_name}: CIDS={cids:.0f}, adjusted={result['adjusted_cids']:.0f} (split)", flush=True)
    return result


def main():
    import yaml

    parser = argparse.ArgumentParser(description="Score CIDS for characters")
    parser.add_argument("--characters", nargs="+", help="Specific characters to score")
    parser.add_argument("--top", type=int, help="Score top N by FP infidelity")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    with open(os.path.join(PROJECT_ROOT, "config.yaml")) as f:
        config = yaml.safe_load(f)
    model = config.get("scoring", {}).get("llm", {}).get("model", "claude-sonnet-4.6")

    # Load all FP scores
    characters = []
    for fname in os.listdir(SCORES_DIR):
        if not fname.endswith(".json") or "_split" in fname:
            continue
        with open(os.path.join(SCORES_DIR, fname)) as f:
            data = json.load(f)
        name = data.get("character", "")
        total = data.get("overall", {}).get("total", 0)
        if total > 0 and name:
            characters.append((name, total))

    if args.characters:
        characters = [(n, t) for n, t in characters if n in args.characters]
    else:
        # Sort by infidelity (lowest FP first = most unfaithful)
        characters.sort(key=lambda x: x[1])
        if args.top:
            characters = characters[:args.top]

    print(f"Scoring CIDS for {len(characters)} characters with {args.workers} workers")

    def do_score(name, fp):
        corpus = load_corpus(name)
        return score_cids(name, fp, corpus, model)

    results = []
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(do_score, n, fp): (n, fp) for n, fp in characters}
        for future in as_completed(futures):
            name, fp = futures[future]
            r = future.result()
            if r:
                results.append(r)
            else:
                failed.append((name, fp))

    # Retry failures (queued to back)
    for retry_round in range(1, MAX_RETRIES):
        if not failed:
            break
        print(f"\n  Retry round {retry_round}: {len(failed)} characters", flush=True)
        still_failed = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(do_score, n, fp): (n, fp) for n, fp in failed}
            for future in as_completed(futures):
                name, fp = futures[future]
                r = future.result()
                if r:
                    results.append(r)
                else:
                    still_failed.append((name, fp))
        failed = still_failed

    if failed:
        print(f"\n  FAILED after all retries: {[n for n, _ in failed]}")

    results.sort(key=lambda x: x["cids"], reverse=True)
    print(f"\nCIDS Rankings (top 25):")
    print(f"{'Character':<30} {'FP':>4} {'CIDS':>7} {'Adj':>7} {'SDL':>4}")
    print("-" * 56)
    for r in results[:25]:
        print(f"{r['character']:<30} {r['fp_score']:>4} {r['cids']:>7.0f} {r['adjusted_cids']:>7.0f} {r['structural_damage_level']:>4}")

    # Save summary
    summary_path = os.path.join(CIDS_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump([{
            "character": r["character"],
            "fp_score": r["fp_score"],
            "cids": r["cids"],
            "adjusted_cids": r["adjusted_cids"],
            "structural_damage_level": r["structural_damage_level"],
        } for r in results], f, indent=2)
    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()
