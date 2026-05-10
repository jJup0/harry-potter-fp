"""
OpenAI API scorer. Works with any OpenAI-compatible endpoint
(OpenAI, Anthropic via litellm, ollama, etc.)

STATUS: Untested/broken - scores_llm.json shows all zeros with errors.
Requires api_base and api_key configured in config.yaml under scoring.llm.
Same fundamental design flaw as kiro scorer: sends one source at a time
instead of comparing book vs film together.
"""
import json
import os
import re
import time
import urllib.request

from scorer_base import group_by_source, fallback_scores

PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "scoring_prompt.txt")
MAX_CORPUS_CHARS = 80000


def score_character(char_name, corpus, config):
    llm_config = config.get('llm', {})
    per_source = {}

    for source, scenes in group_by_source(corpus['screenplays']).items():
        print(f"    {char_name} / {source} (screenplay, {len(scenes)} scenes)...")
        per_source[source] = _score_source(char_name, source, scenes, 'screenplay', llm_config)
        time.sleep(llm_config.get('delay_seconds', 1))

    for source, scenes in group_by_source(corpus['books']).items():
        print(f"    {char_name} / {source} (book, {len(scenes)} paragraphs)...")
        per_source[source] = _score_source(char_name, source, scenes, 'book', llm_config)
        time.sleep(llm_config.get('delay_seconds', 1))

    return per_source


def _score_source(char_name, source_name, scenes, source_type, llm_config):
    try:
        with open(PROMPT_FILE) as f:
            system_prompt = f.read()
        corpus_text = _prepare_corpus(scenes, source_type)
        user_msg = (
            f"## Character: {char_name}\n## Source: {source_name} ({source_type})\n"
            f"## Total scenes: {len(scenes)}\n\n## Corpus:\n\n{corpus_text}\n\n---\n\n"
            f"Now score this character. Respond with ONLY the JSON object. No other text."
        )
        response = _call_api(system_prompt, user_msg, llm_config)
        return _parse_response(response, source_type, len(scenes), len(corpus_text))
    except Exception as e:
        print(f"    ERROR: {e}")
        return fallback_scores(source_type, len(scenes))


def _call_api(system_prompt, user_msg, config):
    api_base = config['api_base']
    api_key = config.get('api_key', '')
    if api_key.startswith('$'):
        api_key = os.environ.get(api_key[1:], api_key)

    payload = json.dumps({
        'model': config['model'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_msg},
        ],
        'temperature': config.get('temperature', 0.3),
        'max_tokens': config.get('max_tokens', 2000),
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{api_base}/chat/completions', data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=config.get('timeout', 60)) as resp:
        raw = resp.read().decode('utf-8')
    if not raw:
        raise ValueError("Empty API response")
    return json.loads(raw)['choices'][0]['message']['content']


def _prepare_corpus(scenes, source_type):
    parts = []
    total = 0
    for i, scene in enumerate(scenes):
        if source_type == 'screenplay':
            lines = [f"[{d}]" for d in scene.get('directions', [])]
            lines += [f"{d['speaker']}: {d['text']}" for d in scene.get('dialogue', [])]
            text = '\n'.join(lines)
        else:
            text = scene.get('text', '')
        if total + len(text) > MAX_CORPUS_CHARS:
            parts.append(f"\n[... {len(scenes) - i} more scenes truncated ...]")
            break
        parts.append(f"--- Scene {i+1} ---\n{text}")
        total += len(text)
    return '\n\n'.join(parts)


def _parse_response(response_text, source_type, scene_count, corpus_chars):
    # Try JSON first
    try:
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
            s = parsed.get('scores', {})
            return _build(s, parsed, source_type, scene_count, corpus_chars)
        m = re.search(r'(\{[^{}]*"scores"\s*:\s*\{[^}]+\}.*?\})', response_text, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
            s = parsed.get('scores', {})
            return _build(s, parsed, source_type, scene_count, corpus_chars)
    except (json.JSONDecodeError, KeyError):
        pass
    # Fallback: markdown "Score: N/25"
    scores = {}
    for pat, dim in [
        (r'PERSONALITY.*?Score:\s*(\d+)/25', 'personality'),
        (r'NARRATIVE.?ROLE.*?Score:\s*(\d+)/25', 'narrative_role'),
        (r'MOTIVATIONS.*?Score:\s*(\d+)/25', 'motivations'),
        (r'CHARACTER.?ARC.*?Score:\s*(\d+)/25', 'character_arc'),
    ]:
        m = re.search(pat, response_text, re.IGNORECASE | re.DOTALL)
        if m:
            scores[dim] = int(m.group(1))
    if scores:
        return _build(scores, {}, source_type, scene_count, corpus_chars)
    raise ValueError(f"Could not parse scores ({len(response_text)} chars)")


def _build(scores, parsed, source_type, scene_count, corpus_chars):
    return {
        'personality': scores.get('personality', 0),
        'narrative_role': scores.get('narrative_role', 0),
        'motivations': scores.get('motivations', 0),
        'character_arc': scores.get('character_arc', 0),
        'justification': parsed.get('justification', {}),
        'key_observations': parsed.get('key_observations', ''),
        'meta': {'type': source_type,
                 'scenes': scene_count if source_type == 'screenplay' else 0,
                 'paragraphs': scene_count if source_type == 'book' else 0,
                 'corpus_chars_sent': corpus_chars},
    }
