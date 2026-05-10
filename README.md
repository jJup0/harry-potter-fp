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
| Rule-based scoring | Done | Placeholder heuristics only - not real FP scores |
| LLM comparative scoring | Working | 102 characters scored via ollama (gemma4:e4b), with justifications |
| Reports & dashboard | Done | Currently based on rule-based scores; needs regeneration from comparative |

**Current state:** The comparative scorer works end-to-end with local ollama. 102 characters have real LLM-generated FP scores with per-dimension justifications. The remaining ~114 characters need scoring (either extend the ollama run or use a cloud API).

## Quick Start

```bash
# Install dependencies
pip install pyyaml plotly pandas openpyxl pymupdf ebooklib

# Run comparative LLM scoring (requires ollama with gemma4:e4b or config change)
python3 -u src/scoring/score.py --backend comparative --characters "Dobby" "Severus Snape"

# Run comparative scoring for top N characters by corpus size
python3 -u src/scoring/score.py --backend comparative --top 50

# Run rule-based scoring (placeholder, for pipeline testing only)
python3 src/scoring/score.py --backend rule_based --top 20

# Generate reports from existing scores
python3 src/reporting/generate_reports.py
python3 src/reporting/generate_dashboard.py
```

## Architecture

### Data Flow

```
Raw sources -> Parse -> Character corpus -> Score (LLM comparative) -> Reports/Dashboard
```

1. **Raw sources**: Book text files + screenplay text files + Aitor's xlsx metrics
2. **Parse**: Split into scenes (screenplays) and paragraphs (books), detect characters per segment
3. **Corpus**: Per-character collection of every scene/paragraph they appear in (v2, `data/v2/corpus/`)
4. **Score**: Feed book + film corpus together to LLM with rubric, get 4-dimension scores + justifications
5. **Report**: Aggregate scores into rankings, per-character reports, interactive dashboard

### Data Sources

| Data | Source | Why |
|------|--------|-----|
| Book texts | v1 (GitHub) | Clean per-book text files |
| Screenplays HP2,6,7.1,7.2 | v2 (Aitor's PDFs) | Actual screenplays with INT/EXT markers |
| Screenplays HP1,3,4,5 | v1 (fandom wiki) | v2 PDFs were garbled/incomplete for these |
| Screen time | v2 (Aitor's xlsx) | Actual measured minutes per character per film |
| Book mentions | v2 (Aitor's xlsx) | Actual counted mentions per character per book |
| Character registry | v2 (from Aitor's data) | 239 canonical characters |

### Directory Structure

```
├── data/
│   ├── raw/books/              # 7 book text files (v1)
│   ├── raw/screenplays/        # 8 wiki transcripts (v1)
│   ├── raw/screenplays_v2/     # 8 PDF-extracted screenplays (v2)
│   ├── v2/characters.yaml      # Character registry (239 chars)
│   ├── v2/parsed/              # Parsed JSON (v2 pipeline)
│   ├── v2/corpus/              # Per-character corpus (v2) - ACTIVE
│   ├── metrics/                # Screen time + book mentions
│   ├── freind-input-data/      # Aitor's raw input files
│   └── fp_rules.txt            # FP scoring rules (Spanish)
├── corpus/                     # Per-character corpus (v1, legacy)
├── src/
│   ├── collect/                # Data ingestion scripts
│   ├── corpus/build_corpus.py  # Corpus builder
│   ├── metrics/                # Metrics computation
│   ├── scoring/
│   │   ├── score.py            # Main CLI (--backend, --characters, --top)
│   │   ├── scorer_comparative.py  # LLM scorer (book+film in one call)
│   │   ├── scorer_rule_based.py   # Placeholder heuristic scorer
│   │   ├── scorer_openai.py       # OpenAI API backend (legacy)
│   │   ├── scorer_kiro.py         # kiro-cli backend (legacy, broken)
│   │   └── prompts/scoring_prompt.txt  # English FP rubric for LLM
│   └── reporting/              # Reports + dashboard generators
├── output/
│   ├── scores/
│   │   ├── scores_comparative.json  # 102 real LLM scores with justifications
│   │   ├── scores_rule_based.json   # Placeholder scores (all characters)
│   │   └── scores.json              # Legacy
│   ├── reports/                # CSV + markdown reports
│   └── dashboard.html          # Interactive Plotly dashboard
├── config.yaml                 # Scoring configuration (model, thresholds)
├── TODO.md                     # Remaining work
├── DECISIONS.md                # Detailed decision log
└── questions-for-aitor.md      # Open questions for client
```

### Scoring Backends

| Backend | How it works | Status |
|---------|-------------|--------|
| `comparative` | Sends book+film corpus together to LLM, gets comparative FP scores | Working (102/216 chars scored) |
| `rule_based` | Placeholder: scores based on corpus size | Works, scores are meaningless |
| `openai` | Standard OpenAI chat completions API | Needs API key; superseded by comparative |
| `kiro` | Pipes prompt to kiro-cli | Broken, superseded by comparative |

## Sample Output (Comparative Scorer)

Top scores from the 102 characters scored so far:

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

1. **102/216 characters scored** - need to complete the remaining ~114 characters
2. **Reports/dashboard use rule-based scores** - need regeneration from comparative scores
3. **HP3 screenplay coverage** - Prisoner of Azkaban has poor data in both v1 and v2
4. **Ron Weasley v2 corpus may be thin** - check if data split across directories
5. **Dumbledore v2 corpus may be split** - check `albus_dumbledore` vs `dumbledore`
6. **Michael Corner scored 0** - likely empty corpus, needs investigation

## Questions for Aitor (Unanswered)

1. Should deleted scenes be included in the film corpus?
2. What's the intended output format for his content? (Ranked list? Per-character deep dives? Video scripts?)
3. Harry/Ron/Hermione are not in the screen time xlsx - intentional or name mismatch?
