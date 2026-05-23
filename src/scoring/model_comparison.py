#!/usr/bin/env python3
"""
Model comparison experiment: score Ginny 3x with opus, sonnet, haiku,
then blind-review all 9 scores with a separate opus call.

Usage:
  python3 src/scoring/model_comparison.py
"""

import json
import os
import re
import subprocess
import sys
import time

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "scoring_prompt_3.txt")
CORPUS_DIR = os.path.join(PROJECT_ROOT, "output", "corpus", "ginny_weasley")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "model_comparison")
KIRO_CWD = "/tmp/harry-potter-scoring-calls"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(KIRO_CWD, exist_ok=True)

MODELS = ["claude-opus-4.6", "claude-sonnet-4.6", "claude-haiku-4.5"]
RUNS = 3
CHARACTER = "Ginny Weasley"


def load_corpus():
    book_path = os.path.join(CORPUS_DIR, "books", "scenes.json")
    film_path = os.path.join(CORPUS_DIR, "screenplays", "scenes.json")
    with open(book_path) as f:
        books = json.load(f)["scenes"]
    with open(film_path) as f:
        films = json.load(f)["scenes"]
    return books, films


def prepare_corpus(scenes, source_type):
    if source_type == "screenplay":
        by_source = {}
        for s in scenes:
            by_source.setdefault(s.get("source", "unknown"), []).append(s)
        parts = []
        for source, group in by_source.items():
            parts.append(f"## {source}")
            for s in group:
                lines = [f"[{d}]" for d in s.get("directions", [])]
                lines += [f"{d['speaker']}: {d['text']}" for d in s.get("dialogue", [])]
                lines = _trim_scene_lines(lines, CHARACTER)
                parts.append("\n".join(lines))
            parts.append("")
        return "\n---\n".join(parts)
    else:
        by_chapter = {}
        for s in scenes:
            key = (s.get("source", ""), s.get("chapter", ""))
            by_chapter.setdefault(key, []).append(s.get("text", ""))
        parts = []
        for (source, chapter), texts in by_chapter.items():
            parts.append(f"## {source}\n### {chapter}")
            parts.append("\n---\n".join(texts))
        return "\n\n".join(parts)


def _trim_scene_lines(lines, character, max_untrimmed=5000):
    """Trim large scenes to lines around character mentions."""
    # Strip formatting noise
    lines = [l for l in lines if not re.match(
        r'^\s*(CONTINUED|CUT TO|FADE|Rev\.|HARRY POTTER.*Rev\.|\d+\.?\s*$)', l, re.IGNORECASE
    )]

    char_lower = character.lower()
    first_name = char_lower.split()[0]
    char_lines = [i for i, l in enumerate(lines) if char_lower in l.lower() or first_name in l.lower()]

    # Adaptive: if character barely appears, trim even small scenes
    threshold = max_untrimmed if len(char_lines) > 2 else 1500

    full = "\n".join(lines)
    if len(full) <= threshold:
        return lines

    # Adaptive context: 1 if character barely appears, 2 otherwise
    context = 1 if len(char_lines) <= 2 else 2

    relevant = set()
    for i in char_lines:
        for j in range(max(0, i - context), min(len(lines), i + context + 1)):
            relevant.add(j)

    if not relevant:
        return lines[:2]

    trimmed = []
    last_included = -1
    for i in sorted(relevant):
        if last_included >= 0 and i > last_included + 1:
            trimmed.append("[...]")
        trimmed.append(lines[i])
        last_included = i
    return trimmed


def build_scoring_prompt(book_text, film_text):
    with open(PROMPT_FILE) as f:
        system_prompt = f.read()
    return (
        f"{system_prompt}\n\n---\n\n"
        f"## Character: {CHARACTER}\n\n"
        f"## BOOK CORPUS\n\n{book_text}\n\n"
        f"## FILM CORPUS\n\n{film_text}\n\n---\n\n"
        f"Score how faithfully the FILM portrays {CHARACTER} compared to the BOOKS.\n\n"
        f"Respond with ONLY a JSON object with these exact keys:\n"
        f'{{"character": "{CHARACTER}", '
        f'"scores": {{"personality_voice": <0-25>, "narrative_role_agency": <0-20>, '
        f'"motivations_internal_conflict": <0-15>, "character_arc": <0-15>, '
        f'"key_relationships": <0-10>, "complexity_nuance_lost_material": <0-15>}}, '
        f'"total": <sum 0-100>, '
        f'"justification": {{...per dimension with book_baseline, film_portrayal, difference...}}, '
        f'"key_observations": "..."}}'
    )


def call_kiro(prompt, model):
    result = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--model", model, "--agent", "blank-agent"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=KIRO_CWD,
    )
    output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]*[a-zA-Z]', '', result.stdout).strip()
    return output


def extract_json(text):
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def score_once(prompt, model, run_id):
    """Score and return parsed result."""
    out_file = os.path.join(OUTPUT_DIR, f"{model}_run{run_id}.json")
    if os.path.exists(out_file):
        print(f"  [{model}][run {run_id}] cached", flush=True)
        with open(out_file) as f:
            return json.load(f)

    print(f"  [{model}][run {run_id}] scoring...", flush=True)
    start = time.time()
    raw = call_kiro(prompt, model)
    elapsed = time.time() - start
    print(f"  [{model}][run {run_id}] {len(raw)} chars ({elapsed:.1f}s)", flush=True)

    parsed = extract_json(raw)
    if not parsed:
        print(f"  [{model}][run {run_id}] FAILED to parse JSON", flush=True)
        print(f"  Raw (first 300): {raw[:300]}", flush=True)
        return None

    parsed["_meta"] = {"model": model, "run": run_id, "elapsed": elapsed}
    with open(out_file, "w") as f:
        json.dump(parsed, f, indent=2)
    total = parsed.get("total", sum(parsed.get("scores", {}).values()))
    print(f"  [{model}][run {run_id}] total={total}", flush=True)
    return parsed


def blind_review(scores, book_text, film_text):
    """Have opus review all 9 scores without knowing which model produced them."""
    review_file = os.path.join(OUTPUT_DIR, "blind_review.json")
    if os.path.exists(review_file):
        print("  Blind review cached", flush=True)
        with open(review_file) as f:
            return json.load(f)

    # Shuffle and anonymize
    import random
    random.seed(42)
    indexed = list(enumerate(scores))
    random.shuffle(indexed)

    entries = []
    for label_idx, (orig_idx, s) in enumerate(indexed):
        entry = {
            "id": chr(65 + label_idx),  # A, B, C...
            "scores": s.get("scores", {}),
            "total": s.get("total"),
            "justification": s.get("justification", {}),
            "key_observations": s.get("key_observations", ""),
        }
        entries.append(entry)

    prompt = (
        f"You are reviewing 9 different FP (character faithfulness) scores for Ginny Weasley. "
        f"Each was produced by an anonymous scorer. Your job is to read the corpus below, then "
        f"rate each score's quality from 1-10 based on:\n"
        f"- Accuracy: do the scores match what the corpus shows?\n"
        f"- Justification quality: are the explanations specific and evidence-based?\n"
        f"- Calibration: are scores appropriately harsh/generous given the evidence?\n\n"
        f"## BOOK CORPUS (abbreviated)\n\n{book_text[:50000]}\n\n"
        f"## FILM CORPUS (abbreviated)\n\n{film_text[:20000]}\n\n"
        f"## SCORES TO REVIEW\n\n{json.dumps(entries, indent=2)}\n\n"
        f"Respond with ONLY a JSON object:\n"
        f'{{"reviews": [{{"id": "A", "quality": <1-10>, "reasoning": "..."}}, ...]}}'
    )

    print("  Running blind review with opus...", flush=True)
    start = time.time()
    raw = call_kiro(prompt, "claude-opus-4.6")
    elapsed = time.time() - start
    print(f"  Blind review done ({elapsed:.1f}s)", flush=True)

    parsed = extract_json(raw)
    if not parsed:
        print(f"  FAILED to parse review", flush=True)
        print(f"  Raw (first 500): {raw[:500]}", flush=True)
        return None

    # Map back to original indices
    id_to_orig = {chr(65 + i): orig_idx for i, (orig_idx, _) in enumerate(indexed)}
    for review in parsed.get("reviews", []):
        review["_original_index"] = id_to_orig.get(review["id"])
        orig_idx = id_to_orig.get(review["id"])
        if orig_idx is not None:
            review["_model"] = scores[orig_idx]["_meta"]["model"]
            review["_run"] = scores[orig_idx]["_meta"]["run"]

    with open(review_file, "w") as f:
        json.dump(parsed, f, indent=2)
    return parsed


def main():
    books, films = load_corpus()
    book_text = prepare_corpus(books, "book")
    film_text = prepare_corpus(films, "screenplay")
    prompt = build_scoring_prompt(book_text, film_text)
    print(f"Prompt: {len(prompt):,} chars", flush=True)

    # Score 3x per model
    all_scores = []
    for model in MODELS:
        for run in range(1, RUNS + 1):
            result = score_once(prompt, model, run)
            if result:
                all_scores.append(result)

    print(f"\n{len(all_scores)}/9 scores collected", flush=True)
    if len(all_scores) < 9:
        print("Some scores failed, continuing with what we have", flush=True)

    # Summary
    print("\n--- SCORES ---", flush=True)
    for s in all_scores:
        m = s["_meta"]
        print(f"  {m['model']} run{m['run']}: {s.get('total', '?')}", flush=True)

    # Blind review
    review = blind_review(all_scores, book_text, film_text)
    if review:
        print("\n--- BLIND REVIEW ---", flush=True)
        for r in review.get("reviews", []):
            print(f"  {r.get('_model', '?')} run{r.get('_run', '?')}: quality={r.get('quality')}", flush=True)
            print(f"    {r.get('reasoning', '')[:120]}", flush=True)


if __name__ == "__main__":
    main()
