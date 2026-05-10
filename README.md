# Harry Potter Character Faithfulness (FP) Project

A data pipeline and scoring system that measures how faithfully Harry Potter characters are portrayed in the films compared to the books. Built for Aitor's content creation workflow.

## What is FP?

FP (Fidelidad del Personaje / Character Faithfulness) is a 0-100 score measuring one thing only: **how faithful a character's film portrayal is to their book counterpart**. It does NOT measure importance, screen time, charisma, or actor quality.

FP = Personality (0-25) + Narrative Role (0-25) + Motivations (0-25) + Character Arc (0-25)

A character with 30 seconds of screen time can score 100 if those 30 seconds are faithful. The full scoring rubric (in Spanish) is in `data/fp_rules.txt`, and the English LLM prompt translation is in `src/scoring/prompts/scoring_prompt.txt`.

## Project Status

| Phase | Status | Notes |
|-------|--------|-------|
| Data collection | Done | Books, screenplays, character registry, metrics |
| Corpus building | Done | 228 characters (v1), 216 characters (v2 after dedup) |
| Metrics | Done | Screen time (actual minutes), book mentions (actual counts) |
| LLM comparative scoring | Working | 209/216 scored via ollama (gemma4:e4b), with justifications |
| Character validation | Done | Wikipedia cross-reference, alias tracking |
| Reports & dashboard | Done | Generated from comparative scores |

**Current state:** The comparative scorer works end-to-end with local ollama. 209 characters have real LLM-generated FP scores with per-dimension justifications. Scoring cache tracks aliases and auto-invalidates when dedup rules change.

## Quick Start

```bash
# Install dependencies
pip install pyyaml plotly pandas openpyxl pymupdf ebooklib

# Fetch canonical character list from Wikipedia (updates data/reference/wikipedia_hp_characters.json)
python3 src/collect/fetch_wikipedia_characters.py

# Validate our characters against Wikipedia (flags unknowns)
python3 src/collect/validate_characters.py

# Run comparative LLM scoring (requires ollama with gemma4:e4b or config change)
python3 -u src/scoring/score.py --backend comparative --characters "Dobby" "Severus Snape"

# Run comparative scoring for top N characters by corpus size
python3 -u src/scoring/score.py --backend comparative --top 50

# Generate reports from existing scores
python3 src/reporting/generate_reports.py
python3 src/reporting/generate_dashboard.py
```

## Architecture

### Data Flow

```
Raw sources -> Parse -> Dedup -> Character corpus -> Score (LLM comparative) -> Reports/Dashboard
```

1. **Raw sources**: Book text files + screenplay text files + Aitor's xlsx metrics
2. **Parse**: Split into scenes (screenplays) and paragraphs (books), detect characters per segment
3. **Dedup**: Merge character name variants via alias map in `src/collect/build_character_registry.py` (e.g. "Sybil Trelawney" -> "Sybill Trelawney", "Madame Rosmerta" -> "Madam Rosmerta"). Validated against `data/reference/wikipedia_hp_characters.json`.
4. **Corpus**: Per-character collection of every scene/paragraph they appear in (`output/corpus/`)
5. **Score**: Feed book + film corpus together to LLM with rubric, get 4-dimension scores + justifications. Cache stores aliases used at scoring time; scores auto-invalidate when aliases change.
6. **Report**: Aggregate scores into rankings, per-character reports, interactive dashboard

### Data Sources

| Data | Source | Why |
|------|--------|-----|
| Book texts | v1 (GitHub) | Clean per-book text files |
| Screenplays HP2,6,7.1,7.2 | v2 (Aitor's PDFs) | Actual screenplays with INT/EXT markers |
| Screenplays HP1,3,4,5 | v1 (fandom wiki) | v2 PDFs were garbled/incomplete for these |
| Screen time | v2 (Aitor's xlsx) | Actual measured minutes per character per film |
| Book mentions | v2 (Aitor's xlsx) | Actual counted mentions per character per book |
| Character registry | v2 (from Aitor's data) | 239 canonical characters |
| Wikipedia characters | Fetched programmatically | 142 canonical characters for validation |

### Directory Structure

```
├── data/                           # SOURCE DATA (immutable inputs)
│   ├── source/
│   │   ├── books/                  # 7 book text files
│   │   ├── screenplays/            # 8 wiki transcripts (fallback for HP1,3,4,5)
│   │   ├── screenplays_v2/         # 8 PDF-extracted screenplays (primary for HP2,6,7.1,7.2)
│   │   ├── aitor/                  # Aitor's raw input files (xlsx, pdf, epub)
│   │   └── metrics/                # Screen time + book mentions (from Aitor's xlsx)
│   ├── reference/                  # External reference data
│   │   ├── wikipedia_hp_characters.json  # Fetched canonical list (142 chars)
│   │   └── wikipedia_hp_characters.md    # Manual reference
│   ├── fp_rules.txt                # FP scoring rules (Spanish)
│   ├── fp_rules.md                 # FP scoring rules (markdown)
│   └── manual-character-alias-mapping.jsonc  # Hand-curated alias map
├── output/                         # DERIVED DATA (all regenerable)
│   ├── parsed/                     # Parsed JSON (books + screenplays)
│   ├── corpus/                     # Per-character corpus
│   ├── characters.yaml             # Character registry (built from Aitor's data)
│   ├── scores/
│   │   ├── comparative/            # Per-character score JSONs (with alias tracking)
│   │   └── scores_comparative.json # Combined scores
│   ├── reports/                    # CSV + markdown reports
│   └── dashboard.html              # Interactive Plotly dashboard
├── src/
│   ├── collect/
│   │   ├── build_v2_pipeline.py    # Main pipeline (parse + corpus)
│   │   ├── build_character_registry.py   # Alias map + registry builder
│   │   ├── fetch_wikipedia_characters.py # Fetch Wikipedia character list
│   │   └── validate_characters.py        # Cross-reference validation
│   ├── corpus/build_corpus.py      # Corpus builder (legacy)
│   ├── metrics/                    # Metrics computation
│   ├── scoring/
│   │   ├── score.py                # Main CLI (--backend, --characters, --top)
│   │   ├── scorer_comparative.py   # LLM scorer (book+film in one call)
│   │   └── prompts/scoring_prompt.txt  # English FP rubric for LLM
│   └── reporting/                  # Reports + dashboard generators
├── config.yaml                 # Scoring configuration (model, thresholds)
├── TODO.md                     # Remaining work
├── DECISIONS.md                # Detailed decision log
└── questions-for-aitor.md      # Open questions for client
```

### Scoring Cache & Invalidation

Each per-character score file in `output/scores/comparative/` stores metadata about the conditions under which it was scored:
- `meta.model` - LLM model used
- `meta.prompt_version` - prompt major.minor version
- `meta.aliases` - alias list active when scored

On resume, a score is re-run if:
- Model changed
- Prompt major version bumped
- Alias list for that character changed (dedup rules updated)

### Scoring Backends

| Backend | How it works | Status |
|---------|-------------|--------|
| `comparative` | Sends book+film corpus together to LLM, gets comparative FP scores | Working (209/216 chars scored) |
| `rule_based` | Placeholder: scores based on corpus size | Removed |
| `openai` | Standard OpenAI chat completions API | Legacy, superseded |
| `kiro` | Pipes prompt to kiro-cli | Legacy, superseded |

## Sample Output (Comparative Scorer)

Top scores from the 209 characters scored so far:

| Character | Pers | Role | Motiv | Arc | Total |
|-----------|------|------|-------|-----|-------|
| Madam Rosmerta | 25 | 25 | 25 | 25 | 100 |
| Bill Weasley | 25 | 25 | 25 | 24 | 99 |
| Garrick Ollivander | 25 | 25 | 24 | 24 | 98 |
| Harry Potter | 22 | 24 | 23 | 22 | 91 |
| Severus Snape | 18 | 22 | 20 | 15 | 75 |
| Ginny Weasley | 15 | 18 | 14 | 12 | 59 |

Each score includes per-dimension justifications citing specific book/film evidence.

## Known Issues

1. **Reports/dashboard use rule-based scores** - need regeneration from comparative scores
2. **HP3 screenplay coverage** - Prisoner of Azkaban has poor data in both v1 and v2
3. **Ron Weasley v2 corpus may be thin** - check if data split across directories
4. **Dumbledore v2 corpus may be split** - check `albus_dumbledore` vs `dumbledore`
5. **Michael Corner scored 0** - likely empty corpus, needs investigation
6. **110 characters flagged** - not on Wikipedia canonical list (mix of minor chars, truncated names, dedup issues)

## Questions for Aitor (Unanswered)

1. Should deleted scenes be included in the film corpus?
2. What's the intended output format for his content? (Ranked list? Per-character deep dives? Video scripts?)
3. Harry/Ron/Hermione are not in the screen time xlsx - intentional or name mismatch?
