"""
Kiro CLI scoring backend. Pipes prompts to kiro-cli chat --no-interactive
and parses the JSON response.
"""

import json
import os
import re
import subprocess
import time

PROMPT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "prompts", "scoring_prompt_3.txt"
)
MAX_RETRIES = 3
DIMENSIONS = {
    "personality_voice": 25,
    "narrative_role_agency": 20,
    "motivations_internal_conflict": 15,
    "character_arc": 15,
    "key_relationships": 10,
    "complexity_nuance_lost_material": 15,
}
KIRO_CWD = "/tmp/harry-potter-scoring-calls"
RAW_DIR = "/tmp/harry-potter-scoring-raw"
os.makedirs(KIRO_CWD, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def _get_prompt_version():
    with open(PROMPT_FILE) as f:
        first_line = f.readline().strip()
    if first_line.startswith("# version:"):
        return first_line.split(":", 1)[1].strip()
    return "0.0"


def _validate_response(parsed):
    if not isinstance(parsed, dict):
        return "Response is not a JSON object"
    scores = parsed.get("scores")
    if not isinstance(scores, dict):
        return "Missing or invalid 'scores' object"
    for key, max_val in DIMENSIONS.items():
        val = scores.get(key)
        if not isinstance(val, (int, float)):
            return f"scores.{key} missing or not a number"
        if val < 0 or val > max_val:
            return f"scores.{key}={val} out of range 0-{max_val}"
    return None


SPLIT_THRESHOLD = int(os.environ.get("SPLIT_THRESHOLD", 500_000))


def score_character(char_name, corpus, config):
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "claude-sonnet-4.6")

    book_scenes = corpus.get("books", [])
    film_scenes = corpus.get("screenplays", [])
    total_book_chars = sum(len(s.get("text", "")) for s in book_scenes)

    if total_book_chars > SPLIT_THRESHOLD:
        return _score_split_by_book(char_name, book_scenes, film_scenes, model)
    else:
        return _score_single(char_name, book_scenes, film_scenes, model)


def _score_split_by_book(char_name, book_scenes, film_scenes, model):
    """Score per-book (parallel + cached) then merge via LLM."""
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed
    by_book = defaultdict(list)
    for s in book_scenes:
        by_book[s.get("source", "unknown")].append(s)

    # Split film scenes by matching source
    by_film = defaultdict(list)
    for s in film_scenes:
        by_film[s.get("source", "unknown")].append(s)

    # Map book -> matching film(s)
    # Book 7 maps to both deathly_hallows_p1 and p2
    def get_film_scenes(book_name):
        # Direct match first
        if book_name in by_film:
            return by_film[book_name]
        # Book 7 -> films 7+8
        if "deathly_hallows" in book_name:
            return by_film.get("7_deathly_hallows_p1", []) + by_film.get("8_deathly_hallows_p2", [])
        # Try matching by number prefix
        prefix = book_name.split("_")[0]
        for film_name, scenes in by_film.items():
            if film_name.startswith(prefix + "_"):
                return scenes
        return []

    # Cache dir for per-book scores
    safe_name = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "output", "scores", "kiro", f"{safe_name}_split")
    os.makedirs(cache_dir, exist_ok=True)

    def score_book(book_name, scenes):
        cache_file = os.path.join(cache_dir, f"{book_name}.json")
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                print(f"    [{char_name}][{book_name}] cached", flush=True)
                return json.load(f)
        matching_film = get_film_scenes(book_name)
        if not matching_film:
            print(f"    [{char_name}][{book_name}] no matching film, skipping", flush=True)
            return None
        print(f"    [{char_name}][{book_name}] {len(scenes)} paragraphs, {len(matching_film)} film scenes", flush=True)
        book_text = _prepare_corpus(scenes, "book")
        film_text = _prepare_corpus(matching_film, "screenplay")
        result = _score_call(char_name, book_text, film_text, model, tag=book_name)
        if result:
            result["book"] = book_name
            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)
        return result

    all_scores = []
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = {pool.submit(score_book, bk, sc): bk for bk, sc in sorted(by_book.items())}
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_scores.append(result)

    if not all_scores:
        return _fallback(char_name)

    # Merge via LLM
    print(f"    [{char_name}][merge] synthesizing {len(all_scores)} book scores...", flush=True)
    merged = _merge_scores(char_name, all_scores, model)
    if not merged:
        avg = {}
        for key in DIMENSIONS:
            avg[key] = round(sum(s[key] for s in all_scores) / len(all_scores), 1)
        merged = avg

    return {
        "comparative": {
            **{k: merged[k] for k in DIMENSIONS},
            "justification": merged.get("justification", {}),
            "confidence": merged.get("confidence", {}),
            "lost_or_transferred_material": merged.get("lost_or_transferred_material", []),
            "score_caps_applied": merged.get("score_caps_applied", []),
            "key_observations": merged.get("key_observations", ""),
            "meta": {
                "type": "comparative",
                "model": model,
                "prompt_version": _get_prompt_version(),
                "book_chars_sent": sum(len(s.get("text", "")) for s in book_scenes),
                "film_chars_sent": sum(len(s.get("text", "")) for s in film_scenes if "text" in s),
                "split_books": len(all_scores),
            },
        }
    }


def _merge_scores(char_name, per_book_scores, model):
    """LLM call to merge per-book scores into a single final score."""
    scores_summary = json.dumps([{
        "book": s["book"],
        "scores": {k: s[k] for k in DIMENSIONS},
        "justification": s.get("justification", {}),
        "key_observations": s.get("key_observations", ""),
    } for s in per_book_scores], indent=2)

    prompt = (
        f"You scored {char_name}'s film faithfulness separately for each book. "
        f"Now synthesize these into ONE final score.\n\n"
        f"Per-book scores:\n{scores_summary}\n\n"
        f"Consider: which books are most important for this character's arc? "
        f"Where are the biggest faithfulness failures? Weight accordingly.\n\n"
        f"Respond with ONLY a JSON object with the same schema:\n"
        f'{{"scores": {{"personality_voice": <0-25>, "narrative_role_agency": <0-20>, '
        f'"motivations_internal_conflict": <0-15>, "character_arc": <0-15>, '
        f'"key_relationships": <0-10>, "complexity_nuance_lost_material": <0-15>}}, '
        f'"total": <sum 0-100>, '
        f'"confidence": {{"global": "High/Medium/Low"}}, '
        f'"justification": {{...per dimension...}}, '
        f'"lost_or_transferred_material": [...], '
        f'"score_caps_applied": [...], '
        f'"key_observations": "..."}}'
    )

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"    [{char_name}][merge] attempt {attempt}/{MAX_RETRIES}...")
        response = _call_kiro(prompt, model)
        parsed = _extract_json(response)
        if parsed is None:
            continue
        scores = parsed.get("scores")
        if not scores:
            continue
        error = _validate_response(parsed)
        if error:
            print(f"    [{char_name}][merge] schema invalid - {error}")
            continue
        return {**scores, "justification": parsed.get("justification", {}),
                "confidence": parsed.get("confidence", {}),
                "lost_or_transferred_material": parsed.get("lost_or_transferred_material", []),
                "score_caps_applied": parsed.get("score_caps_applied", []),
                "key_observations": parsed.get("key_observations", "")}

    print(f"    [{char_name}][merge] FAILED, falling back to average")
    return None


def _score_single(char_name, book_scenes, film_scenes, model):
    book_text = _prepare_corpus(book_scenes, "book")
    film_text = _prepare_corpus(film_scenes, "screenplay")
    result = _score_call(char_name, book_text, film_text, model)
    if not result:
        return _fallback(char_name)
    return {
        "comparative": {
            **{k: result[k] for k in DIMENSIONS},
            "justification": result.get("justification", {}),
            "confidence": result.get("confidence", {}),
            "lost_or_transferred_material": result.get("lost_or_transferred_material", []),
            "score_caps_applied": result.get("score_caps_applied", []),
            "key_observations": result.get("key_observations", ""),
            "meta": {
                "type": "comparative",
                "model": model,
                "prompt_version": _get_prompt_version(),
                "book_chars_sent": len(book_text),
                "film_chars_sent": len(film_text),
            },
        }
    }


def _score_call(char_name, book_text, film_text, model, tag=None):
    """Single scoring call. Returns parsed scores dict or None."""
    try:
        with open(PROMPT_FILE) as f:
            system_prompt = f.read()

        user_msg = (
            f"{system_prompt}\n\n---\n\n"
            f"## Character: {char_name}\n\n"
            f"## BOOK CORPUS (scenes where {char_name} appears in the books)\n\n{book_text}\n\n"
            f"## FILM CORPUS (scenes where {char_name} appears in the screenplays)\n\n{film_text}\n\n---\n\n"
            f"Score how faithfully the FILM portrays {char_name} compared to the BOOKS.\n\n"
            f"Respond with ONLY a JSON object with these exact keys:\n"
            f'{{"character": "{char_name}", '
            f'"scores": {{"personality_voice": <0-25>, "narrative_role_agency": <0-20>, '
            f'"motivations_internal_conflict": <0-15>, "character_arc": <0-15>, '
            f'"key_relationships": <0-10>, "complexity_nuance_lost_material": <0-15>}}, '
            f'"total": <sum 0-100>, '
            f'"confidence": {{"global": "High/Medium/Low", ...per dimension...}}, '
            f'"justification": {{...per dimension with book_baseline, film_portrayal, difference, penalty_logic, evidence_status...}}, '
            f'"lost_or_transferred_material": [...], '
            f'"score_caps_applied": [...], '
            f'"key_observations": "..."}}'
        )

        prefix = f"[{char_name}][{tag}] " if tag else f"[{char_name}] "
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"    {prefix}attempt {attempt}/{MAX_RETRIES}: calling kiro-cli ({model})...")
            t0 = time.time()
            response = _call_kiro(user_msg, model)
            print(f"    {prefix}kiro-cli took {time.time() - t0:.1f}s, got {len(response)} chars back")
            raw_file = os.path.join(
                RAW_DIR, f"{char_name.lower().replace(' ', '_')}{'_' + tag if tag else ''}_attempt{attempt}.txt"
            )
            with open(raw_file, "w") as rf:
                rf.write(response)
            parsed = _extract_json(response)
            if parsed is None:
                print(f"    {prefix}parse failed, raw: {response[:200]}")
                time.sleep(2)
                continue
            error = _validate_response(parsed)
            if error:
                print(f"    {prefix}schema invalid - {error}")
                time.sleep(2)
                continue
            scores = parsed["scores"]
            return {**scores, "justification": parsed.get("justification", {}),
                    "confidence": parsed.get("confidence", {}),
                    "lost_or_transferred_material": parsed.get("lost_or_transferred_material", []),
                    "score_caps_applied": parsed.get("score_caps_applied", []),
                    "key_observations": parsed.get("key_observations", "")}

        print(f"    {prefix}FAILED after {MAX_RETRIES} attempts")
        return None
    except Exception as e:
        print(f"    {prefix}ERROR: {e}")
        return None


def _fallback(char_name):
    return {
        "comparative": {
            **{k: 0 for k in DIMENSIONS},
            "meta": {
                "type": "comparative",
                "model": None,
                "prompt_version": _get_prompt_version(),
                "book_chars_sent": 0,
                "film_chars_sent": 0,
                "error": True,
            },
        }
    }


def _prepare_corpus(scenes, source_type):
    parts = []
    for i, scene in enumerate(scenes):
        if source_type == "screenplay":
            lines = [f"[{d}]" for d in scene.get("directions", [])]
            lines += [f"{d['speaker']}: {d['text']}" for d in scene.get("dialogue", [])]
            text = "\n".join(lines)
        else:
            text = scene.get("text", "")
        parts.append(f"--- Scene {i+1} ---\n{text}")
    return "\n\n".join(parts)


def _call_kiro(prompt, model):
    result = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--model", model, "--trust-tools="],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=KIRO_CWD,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kiro-cli failed (exit {result.returncode}): {result.stderr[:200]}")
    return result.stdout


def _extract_json(response_text):
    """Extract JSON from kiro-cli output which may contain markdown formatting."""
    # Try to find a JSON block in markdown fences
    # Strip ANSI escape codes
    response_text = re.sub(r"\x1b\[[0-9;]*m", "", response_text)
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try to find raw JSON object
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
