# TODO - What Still Needs to Be Done

Last reviewed: 2026-05-09

## Current State Summary

The data pipeline works end-to-end: books and screenplays are parsed, character corpus is built (228 characters in v1, 216 in v2 after dedup), metrics are extracted from Aitor's xlsx files, and reports/dashboard can be generated. The **comparative scorer** (`--backend comparative`) is now implemented and ready to use with any OpenAI-compatible API.

## Completed (this session)

- [x] Added Harry/Ron/Hermione to screen_time_v2.json (estimated values, noted as such)
- [x] Removed 14 duplicate v2 corpus directories (typos/truncations)
- [x] Switched scorer to use v2 corpus and v2 characters.yaml
- [x] Added SKIP_CHARACTERS set to skip generic words during scoring
- [x] Created `scorer_comparative.py` - sends both book+film corpus in one LLM call
- [x] Added 'comparative' backend to score.py
- [x] Added inline documentation/comments to all source files
- [x] Created this TODO.md

## Ollama Scoring Setup (2026-05-09)

Got the comparative scorer working end-to-end with local ollama. Key findings:

**What works:**

- Model: `gemma4:e4b` via ollama native API (`/api/chat`)
- ~20s per character, valid 4-dimension scores with justifications
- One-shot prompting (example assistant response) to anchor the output schema
- `format: json` in ollama API to force JSON output
- JSON schema validation + 3 retries on invalid responses
- Raw responses saved to `/tmp/fp_raw_responses/` for debugging

**Struggles / lessons learned:**

- `gemma4:e4b` kept inventing its own score keys (e.g. `emotional_depth`, `actions`, `dialogue`) instead of using the required `personality`, `narrative_role`, `motivations`, `character_arc`. Fixed by combining one-shot example + `format: json` + explicit schema in user message.
- `gemma4:31b` timed out (>5min) even with 600s timeout - too slow for this workload with 32k context.
- Ollama's OpenAI-compatible `/v1` endpoint defaults to 4096 context, which silently truncates the prompt. The model then says "the provided text does not contain this character". Fix: use the native `/api/chat` endpoint with `options.num_ctx: 32768`.
- `response_format: {type: json_object}` on the `/v1` endpoint did NOT help the model follow the schema - it still returned JSON but with wrong keys.
- The system prompt (full scoring rubric) was too long and got ignored by smaller models. Moved the rubric inline into the user message and kept the system prompt short.
- Python output buffering hid all progress when running via tmux. Fix: `python3 -u`.
- After loading 31b with 32k context, switching to e4b gave HTTP 500 until the 31b model was explicitly unloaded (`keep_alive: 0`).

## Remaining Work

### 1. Configure an LLM backend and run real scoring (NEXT STEP)

The comparative scorer is ready but needs an API endpoint. Configure one of these in `config.yaml` under `scoring.llm`:

```yaml
scoring:
  llm:
    # Option A: OpenAI
    model: gpt-4o
    api_base: https://api.openai.com/v1
    api_key: $OPENAI_API_KEY
    temperature: 0.3
    max_tokens: 2000
    timeout: 120

    # Option B: Local ollama (needs large context model)
    # model: llama3:70b
    # api_base: http://localhost:11434/v1
    # api_key: ollama

    # Option C: Anthropic via litellm proxy
    # model: claude-sonnet-4-20250514
    # api_base: http://localhost:4000/v1
    # api_key: $ANTHROPIC_API_KEY
```

Then run:

```bash
python3 src/scoring/score.py --backend comparative --characters "Dobby" "Severus Snape"
```

### 2. Fix Ron Weasley's v2 corpus

Ron scored 2.1 in the rule-based test, meaning his v2 corpus directory is nearly empty. Check if his data ended up under a different directory name (e.g. `ron` vs `ron_weasley`) or if the alias resolution missed him.

```bash
ls data/v2/corpus/ | grep -i ron
du -sh data/v2/corpus/ron_weasley/
```

### 3. Fix Dumbledore's v2 corpus

Dumbledore scored 17.1 (low for a major character). Same issue - check if his corpus is split across `albus_dumbledore` and `dumbledore` or similar.

### 4. Regenerate reports with real scores

Once comparative scoring works:

```bash
python3 src/scoring/score.py --backend comparative --top 50
python3 src/reporting/generate_reports.py
python3 src/reporting/generate_dashboard.py
```

### 5. HP3 screenplay coverage

Prisoner of Azkaban has terrible screenplay data in both v1 (1 scene) and v2 (6 pages). May need to source a better transcript manually.

### 6. Book 2 chapter detection

Only finds 10 of 18 chapters due to inconsistent heading formatting. Low priority since paragraphs are still captured.

### 7. Translate FP to english markdown

Just for future reference for myself.

## Questions for Aitor (still unanswered)

1. Should deleted scenes be included in the film corpus or excluded?
2. What's the intended output format? Ranked list? Per-character deep dives? Video scripts?
3. Harry/Ron/Hermione are not in the screen time xlsx at all - was this intentional? Should we estimate or leave them out of screen-time-based filtering?

## File Quick Reference

| What | Where |
|------|-------|
| Run scoring | `python3 src/scoring/score.py --backend comparative --top N` |
| Scoring config | `config.yaml` |
| FP rules (Spanish) | `data/fp_rules.txt` |
| FP rules (English prompt) | `src/scoring/prompts/scoring_prompt.txt` |
| Comparative scorer (NEW) | `src/scoring/scorer_comparative.py` |
| v2 corpus (active) | `data/v2/corpus/` |
| v2 characters | `data/v2/characters.yaml` |
| Score output | `output/scores/scores_<backend>.json` |
| Dashboard | `output/dashboard.html` |
| Decision log | `DECISIONS.md` |
