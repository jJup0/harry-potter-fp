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


def score_character(char_name, corpus, config):
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "claude-sonnet-4.6")
    try:
        book_text = _prepare_corpus(corpus.get("books", []), "book")
        film_text = _prepare_corpus(corpus.get("screenplays", []), "screenplay")

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

        for attempt in range(1, MAX_RETRIES + 1):
            print(f"    attempt {attempt}/{MAX_RETRIES}: calling kiro-cli ({model})...")
            t0 = time.time()
            response = _call_kiro(user_msg, model)
            print(f"    kiro-cli took {time.time() - t0:.1f}s, got {len(response)} chars back")
            raw_file = os.path.join(
                RAW_DIR, f"{char_name.lower().replace(' ', '_')}_attempt{attempt}.txt"
            )
            with open(raw_file, "w") as rf:
                rf.write(response)
            parsed = _extract_json(response)
            if parsed is None:
                print(f"    parse failed, raw: {response[:200]}")
                time.sleep(2)
                continue
            error = _validate_response(parsed)
            if error:
                print(f"    schema invalid - {error}")
                time.sleep(2)
                continue
            scores = parsed["scores"]
            return {
                "comparative": {
                    **{k: scores[k] for k in DIMENSIONS},
                    "justification": parsed.get("justification", {}),
                    "confidence": parsed.get("confidence", {}),
                    "lost_or_transferred_material": parsed.get("lost_or_transferred_material", []),
                    "score_caps_applied": parsed.get("score_caps_applied", []),
                    "key_observations": parsed.get("key_observations", ""),
                    "meta": {
                        "type": "comparative",
                        "model": model,
                        "prompt_version": _get_prompt_version(),
                        "book_chars_sent": len(book_text),
                        "film_chars_sent": len(film_text),
                    },
                }
            }

        print(f"    FAILED after {MAX_RETRIES} attempts")
        return _fallback(char_name)
    except Exception as e:
        print(f"    ERROR: {e}")
        return _fallback(char_name)


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
