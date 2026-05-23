"""
Comparative FP scorer. Sends BOTH book and film corpus in one LLM call
so the model can compare how faithfully the film portrays the book character.

Uses JSON schema validation and retries to handle flaky model outputs.
"""

import json
import os
import re
import time
import urllib.request

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
RAW_DIR = "/tmp/fp_raw_responses"
os.makedirs(RAW_DIR, exist_ok=True)


def _get_prompt_version():
    """Read version from first line of prompt file. Format: '# version: major.minor'"""
    with open(PROMPT_FILE) as f:
        first_line = f.readline().strip()
    if first_line.startswith("# version:"):
        return first_line.split(":", 1)[1].strip()
    return "0.0"


def _validate_response(parsed):
    """Validate the parsed JSON matches our expected schema. Returns error string or None."""
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
    try:
        book_text = _prepare_corpus(corpus.get("books", []), "book")
        film_text = _prepare_corpus(corpus.get("screenplays", []), "screenplay")

        user_msg = (
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
            print(
                f"    attempt {attempt}/{MAX_RETRIES}: calling {llm_config.get('model')}..."
            )
            response = _call_api(user_msg, llm_config)
            print(f"    got {len(response)} chars back")
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
                        "model": llm_config.get("model"),
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


def _call_api(user_msg, config):
    api_base = config["api_base"].rstrip("/")
    api_key = config.get("api_key", "")
    if api_key.startswith("$"):
        api_key = os.environ.get(api_key[1:], api_key)

    with open(PROMPT_FILE) as f:
        system_prompt = f.read()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    # Use ollama native API to set num_ctx
    if "localhost:11434" in api_base:
        payload = json.dumps(
            {
                "model": config["model"],
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": config.get("temperature", 0.3),
                    "num_ctx": config.get("num_ctx", 65536),
                },
            }
        ).encode("utf-8")
        url = api_base.replace("/v1", "") + "/api/chat"
    else:
        payload = json.dumps(
            {
                "model": config["model"],
                "messages": messages,
                "temperature": config.get("temperature", 0.3),
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        url = f"{api_base}/chat/completions"

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=config.get("timeout", 300)) as resp:
        raw = resp.read().decode("utf-8")
    print(f"    API took {time.time() - t0:.1f}s")
    if not raw:
        raise ValueError("Empty API response")
    data = json.loads(raw)
    if "message" in data:
        return data["message"]["content"]
    return data["choices"][0]["message"]["content"]


def _extract_json(response_text):
    """Try to extract a JSON object from the response, stripping markdown fences."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None
