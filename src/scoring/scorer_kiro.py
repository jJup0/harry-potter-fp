"""
Kiro-CLI scorer. Uses kiro-cli --no-interactive with stdin piping.
Each scoring call is a fresh kiro-cli invocation (~30-40s startup overhead).

STATUS: BROKEN - all calls return errors (scores_kiro.json shows all zeros).
Likely causes:
  1. Response parsing assumes '> ' prefix which may not match kiro-cli output format
  2. 80K char prompts may exceed kiro-cli input limits
  3. ANSI stripping regex may miss some escape sequences
  4. FUNDAMENTAL: sends one source at a time, but FP needs book+film comparison

Debug files are written to /tmp/hp_kiro_debug_*.txt on each call.
"""
import json
import os
import re
import subprocess
import time

from scorer_base import group_by_source, fallback_scores

PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "scoring_prompt.txt")
MAX_CORPUS_CHARS = 80000
ANSI_RE = re.compile(r'\x1b[\[\(][0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]|\x1b\[\?[0-9]*[a-zA-Z]')


def _call_kiro(prompt, timeout=120):
    """Call kiro-cli --no-interactive, pass prompt via temp file, return response."""
    import tempfile
    # Write prompt to file, pipe via cat to avoid stdin line-splitting
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix='hp-kiro-') as f:
        f.write(prompt)
        tmpfile = f.name
    try:
        result = subprocess.run(
            f'cat {tmpfile} | kiro-cli chat --no-interactive --trust-tools=',
            shell=True, capture_output=True, text=True, timeout=timeout,
        )
    finally:
        os.unlink(tmpfile)

    raw = result.stdout
    clean = ANSI_RE.sub('', raw)
    lines = clean.split('\n')
    response_lines = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if '▸ Credits:' in stripped:
            break
        if re.match(r'^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s', stripped):
            continue
        if stripped.startswith('> '):
            capturing = True
            response_lines.append(stripped[2:])
        elif capturing:
            response_lines.append(stripped)
    return '\n'.join(response_lines).strip()


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
        prompt = (
            f"{system_prompt}\n\n---\n\n"
            f"## Character: {char_name}\n## Source: {source_name} ({source_type})\n"
            f"## Total scenes: {len(scenes)}\n\n## Corpus:\n\n{corpus_text}\n\n---\n\n"
            f"Score this character now. Include 'Score: N/25' for each dimension."
        )
        timeout = llm_config.get('timeout', 180)
        response = _call_kiro(prompt, timeout=timeout)
        if not response:
            raise ValueError("Empty response from kiro-cli")
        # Debug dump
        debug_file = f"/tmp/hp_kiro_debug_{source_name}_{source_type}.txt"
        with open(debug_file, 'w') as df:
            df.write(response)
        return _parse_response(response, source_type, len(scenes), len(corpus_text))
    except Exception as e:
        print(f"    ERROR: {e}")
        return fallback_scores(source_type, len(scenes))


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
    # Try JSON
    try:
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
            return _build(parsed.get('scores', {}), parsed, source_type, scene_count, corpus_chars)
        m = re.search(r'(\{[^{}]*"scores"\s*:\s*\{[^}]+\}.*?\})', response_text, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
            return _build(parsed.get('scores', {}), parsed, source_type, scene_count, corpus_chars)
    except (json.JSONDecodeError, KeyError):
        pass
    # Fallback: markdown "Score: N/25"
    scores = {}
    for pat, dim in [
        (r'PERSONALITY.*?(?:Score:|:)\s*(\d+)/25', 'personality'),
        (r'NARRATIVE.?ROLE.*?(?:Score:|:)\s*(\d+)/25', 'narrative_role'),
        (r'MOTIVATIONS.*?(?:Score:|:)\s*(\d+)/25', 'motivations'),
        (r'CHARACTER.?ARC.*?(?:Score:|:)\s*(\d+)/25', 'character_arc'),
    ]:
        m = re.search(pat, response_text, re.IGNORECASE | re.DOTALL)
        if m:
            scores[dim] = int(m.group(1))
    if scores:
        return _build(scores, {}, source_type, scene_count, corpus_chars)
    raise ValueError(f"Could not parse scores from response ({len(response_text)} chars)")


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


def shutdown():
    pass  # No persistent session to clean up
