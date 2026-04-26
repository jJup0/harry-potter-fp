#!/usr/bin/env python3
"""
LLM-based scoring backend.

Sends character corpus (per source) to an LLM with the scoring prompt,
parses structured JSON output, and returns per-source scores.

For kiro-cli: uses a persistent tmux session via interactive_runner,
with /clear between scoring calls for fresh context.
Also supports OpenAI-compatible APIs.
"""
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request

PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "scoring_prompt.txt")
MAX_CORPUS_CHARS = 80000  # ~20k tokens
ANSI_RE = re.compile(r'\x1b[\[\(][0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]|\x1b\[\?[0-9]*[a-zA-Z]')
KIRO_SESSION = "hp-scorer"
READY_RE = re.compile(r'\[.*\]\s+\d+%\s*>')
CREDITS_RE = re.compile(r'▸ Credits:')


def load_system_prompt():
    with open(PROMPT_FILE) as f:
        return f.read()


def prepare_corpus_text(scenes, source_type):
    parts = []
    total_chars = 0
    for i, scene in enumerate(scenes):
        if source_type == 'screenplay':
            lines = []
            for d in scene.get('directions', []):
                lines.append(f"[{d}]")
            for d in scene.get('dialogue', []):
                lines.append(f"{d['speaker']}: {d['text']}")
            text = '\n'.join(lines)
        else:
            text = scene.get('text', '')
        if total_chars + len(text) > MAX_CORPUS_CHARS:
            parts.append(f"\n[... {len(scenes) - i} more scenes truncated for length ...]")
            break
        parts.append(f"--- Scene {i+1} ---\n{text}")
        total_chars += len(text)
    return '\n\n'.join(parts)


# --- Persistent kiro-cli session management ---

def _runner(cmd, *args):
    result = subprocess.run(
        ["interactive_runner", KIRO_SESSION, cmd, *args],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip()


def _tmux_buffer():
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", KIRO_SESSION, "-p", "-S", "-1000"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout


def _session_alive():
    r = subprocess.run(["tmux", "has-session", "-t", KIRO_SESSION],
                       capture_output=True, timeout=5)
    return r.returncode == 0


def _wait_ready(timeout=60):
    """Wait for kiro-cli to show the ready prompt."""
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(1)
        buf = ANSI_RE.sub('', _tmux_buffer())
        lines = buf.strip().split('\n')
        # Check last few lines for ready prompt
        for line in lines[-5:]:
            if READY_RE.search(line.strip()):
                return True
    return False


def ensure_kiro_session():
    """Start a persistent kiro-cli session if not already running."""
    if _session_alive():
        return
    print(f"    Starting kiro-cli session '{KIRO_SESSION}'...")
    _runner("start", "kiro-cli chat --classic --trust-tools= --wrap never")
    if not _wait_ready(timeout=45):
        raise RuntimeError("kiro-cli session did not become ready in time")
    print(f"    Session ready.")


def clear_kiro_session():
    """Send /clear to reset context, confirm with 'y'."""
    _runner("send", "/clear")
    time.sleep(1)
    # /clear prompts [y/n]
    _runner("send", "y")
    _wait_ready(timeout=15)


def send_to_kiro(prompt, timeout=120):
    """Send a prompt to the persistent kiro-cli session and wait for response."""
    # Snapshot buffer position before sending
    before = _tmux_buffer()
    before_len = len(before)

    # Use tmux load-buffer for large prompts
    if len(prompt) > 800:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix='hp-score-') as f:
            f.write(prompt)
            tmpfile = f.name
        try:
            subprocess.run(["tmux", "load-buffer", "-b", "hp-paste", tmpfile], check=True, timeout=5)
            subprocess.run(["tmux", "paste-buffer", "-b", "hp-paste", "-t", KIRO_SESSION], check=True, timeout=5)
            time.sleep(0.5)
            subprocess.run(["tmux", "send-keys", "-t", KIRO_SESSION, "Enter"], check=True, timeout=5)
        finally:
            os.unlink(tmpfile)
    else:
        _runner("send", prompt)

    # Wait for response
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        full = _tmux_buffer()
        new_content = full[before_len:] if len(full) > before_len else full
        clean = ANSI_RE.sub('', new_content)
        if CREDITS_RE.search(clean) and READY_RE.search(clean.split("Credits:")[-1]):
            return _extract_response(new_content)

    # Timeout — return whatever we have
    full = _tmux_buffer()
    new_content = full[before_len:] if len(full) > before_len else full
    return _extract_response(new_content)


def _extract_response(raw):
    """Extract the assistant response text from kiro-cli output."""
    clean = ANSI_RE.sub('', raw).strip()
    lines = clean.split('\n')
    response_lines = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if '▸ Credits:' in stripped:
            capturing = False
            continue
        if READY_RE.match(stripped):
            continue
        if re.match(r'^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s', stripped):
            continue
        if stripped.startswith('> '):
            capturing = True
            response_lines.append(stripped[2:])
        elif capturing:
            response_lines.append(stripped if stripped else '')
    return '\n'.join(response_lines).strip()


# --- LLM call routing ---

def call_llm(messages, config):
    model = config.get('model', 'kiro-cli')
    if model == 'kiro-cli':
        return call_kiro_cli_persistent(messages, config)
    return call_openai_api(messages, config)


def call_kiro_cli_persistent(messages, config):
    """Send prompt to persistent kiro-cli session."""
    ensure_kiro_session()
    clear_kiro_session()

    prompt = '\n\n'.join(m.get('content', '') for m in messages)
    timeout = config.get('timeout', 120)

    response = send_to_kiro(prompt, timeout=timeout)
    if not response:
        raise ValueError("Empty response from kiro-cli")
    return response


def call_openai_api(messages, config):
    api_base = config.get('api_base', 'http://localhost:11434/v1')
    api_key = config.get('api_key', os.environ.get('OPENAI_API_KEY', 'ollama'))
    model = config.get('model', 'llama3')
    temperature = config.get('temperature', 0.3)
    max_tokens = config.get('max_tokens', 2000)
    timeout = config.get('timeout', 60)

    if api_key.startswith('$'):
        api_key = os.environ.get(api_key[1:], api_key)

    payload = json.dumps({
        'model': model, 'messages': messages,
        'temperature': temperature, 'max_tokens': max_tokens,
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{api_base}/chat/completions', data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST'
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    if not raw:
        raise ValueError("Empty response from LLM API")
    result = json.loads(raw)
    content = result['choices'][0]['message']['content']
    if not content:
        raise ValueError("Empty content in LLM response")
    return content


# --- Response parsing ---

def parse_llm_response(response_text):
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try markdown code block
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    # Try finding a JSON object with "scores" key
    json_match = re.search(r'(\{[^{}]*"scores"\s*:\s*\{[^}]+\}.*?\})', response_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    # Last resort
    return json.loads(response_text)


# --- Scoring ---

def score_character_source(char_name, source_name, scenes, source_type, config):
    system_prompt = load_system_prompt()
    corpus_text = prepare_corpus_text(scenes, source_type)

    user_message = (
        f"{system_prompt}\n\n---\n\n"
        f"## Character: {char_name}\n"
        f"## Source: {source_name} ({source_type})\n"
        f"## Total scenes in corpus: {len(scenes)}\n\n"
        f"## Corpus:\n\n{corpus_text}\n\n---\n\n"
        f"Now score this character. Respond with ONLY the JSON object as specified above. No other text."
    )

    messages = [{'role': 'user', 'content': user_message}]
    response = call_llm(messages, config)
    parsed = parse_llm_response(response)

    scores = parsed.get('scores', {})
    return {
        'personality': scores.get('personality', 0),
        'narrative_role': scores.get('narrative_role', 0),
        'motivations': scores.get('motivations', 0),
        'character_arc': scores.get('character_arc', 0),
        'justification': parsed.get('justification', {}),
        'key_observations': parsed.get('key_observations', ''),
        'meta': {
            'type': source_type,
            'scenes': len(scenes) if source_type == 'screenplay' else 0,
            'paragraphs': len(scenes) if source_type == 'book' else 0,
            'corpus_chars_sent': len(corpus_text),
        }
    }


def score_llm_based(char_name, corpus, config):
    llm_config = config.get('llm', {})
    per_source = {}

    sp_groups = {}
    for s in corpus.get('screenplays', []):
        src = s.get('source', 'unknown')
        sp_groups.setdefault(src, []).append(s)

    bk_groups = {}
    for s in corpus.get('books', []):
        src = s.get('source', 'unknown')
        bk_groups.setdefault(src, []).append(s)

    for source, scenes in sp_groups.items():
        print(f"    LLM scoring {char_name} / {source} (screenplay, {len(scenes)} scenes)...")
        try:
            per_source[source] = score_character_source(char_name, source, scenes, 'screenplay', llm_config)
        except Exception as e:
            print(f"    ERROR: {e}")
            per_source[source] = _fallback_scores('screenplay', len(scenes))
        time.sleep(llm_config.get('delay_seconds', 1))

    for source, scenes in bk_groups.items():
        print(f"    LLM scoring {char_name} / {source} (book, {len(scenes)} paragraphs)...")
        try:
            per_source[source] = score_character_source(char_name, source, scenes, 'book', llm_config)
        except Exception as e:
            print(f"    ERROR: {e}")
            per_source[source] = _fallback_scores('book', len(scenes))
        time.sleep(llm_config.get('delay_seconds', 1))

    return per_source


def _fallback_scores(source_type, scene_count):
    return {
        'personality': 0, 'narrative_role': 0, 'motivations': 0, 'character_arc': 0,
        'justification': {'error': 'LLM call failed'},
        'key_observations': 'Scoring failed — using fallback.',
        'meta': {
            'type': source_type,
            'scenes': scene_count if source_type == 'screenplay' else 0,
            'paragraphs': scene_count if source_type == 'book' else 0,
            'error': True,
        }
    }


def shutdown_kiro_session():
    """Kill the persistent kiro-cli session."""
    if _session_alive():
        subprocess.run(["tmux", "kill-session", "-t", KIRO_SESSION], capture_output=True, timeout=5)
        print(f"    Killed kiro-cli session '{KIRO_SESSION}'")
