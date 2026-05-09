# Decisions & Documentation

## Data Source Decisions

Two generations of data exist: v1 (scraped from the web) and v2 (Aitor's files). To avoid inconsistencies from mixing sources, we pick the single best source per data type.

| Data | Source | Location | Why |
|------|--------|----------|-----|
| Books (text) | v1 — GitHub downloads | `data/raw/books/` | Individual files per book, clean plain text, well-formatted paragraphs |
| Screenplays HP2, 6, 7.1, 7.2 | v2 — Aitor's PDFs | `data/raw/screenplays_v2/` | Actual screenplays with INT/EXT markers, proper formatting |
| Screenplays HP1, 3, 4, 5 | v1 — fandom wiki transcripts | `data/raw/screenplays/` | v2 PDFs were garbled (HP5), fan comments (HP4), incomplete (HP3), or transcript-not-screenplay (HP1) |
| Screen time | v2 — Aitor's xlsx | `data/metrics/screen_time_v2.json` | Actual measured minutes per character per film (111 characters) |
| Book mentions | v2 — Aitor's xlsx | `data/metrics/book_mentions_v2.json` | Actual counted mentions per character per book (210 characters) |
| Character registry | v2 — derived from Aitor's data | `data/v2/characters.yaml` | Canonical names from Aitor's mentions + screen time (239 characters) |
| FP scoring rules | v2 — Aitor's PDF | `data/fp_rules.txt` | The definitive scoring rubric (Spanish original, translated into prompt) |

**Rejected sources and why:**
- v2 books PDF (`harrypotter-16.pdf`): single 3623-page file, didn't split cleanly into individual books
- v2 books epub: Spanish edition ("La colección completa") — wrong language for English analysis
- v1 screen time (word count estimates): less accurate than Aitor's measured minutes
- v1 book mentions (regex-based): less accurate than Aitor's hand-counted data

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Natural fit for text processing, data analysis, and LLM integration |
| Execution model | Local, on-demand | Run scripts manually, inspect output, iterate. No server/deployment needed |
| Book segmentation | Paragraph-level | Each paragraph is a "scene" for character detection. Handles multiple book formats (double-newline, full-width indent, 4-space indent, line-wrapped) |
| Screenplay segmentation | Scene-level | v2 PDFs: INT./EXT./CUT TO: markers. v1 transcripts: `[stage direction]` heuristics |
| Character detection | Alias matching | Map all known name variants to canonical names. Blocklist for generic words |
| FP scoring | Book vs film comparison | Per Aitor's rules: score how faithfully the film portrays the book character. NOT quality, importance, or screen time |
| Scoring backends | Rule-based + LLM | Rule-based for fast iteration with placeholder heuristics. LLM (kiro-cli / OpenAI) for real evaluation using Aitor's rubric |
| LLM integration | Persistent kiro-cli tmux session | `/clear` between calls for fresh context. Avoids 37s cold-start per call. Also supports OpenAI API |
| Corpus truncation | 80K chars max per LLM call | ~20K tokens of corpus text, leaving room for prompt + response within context window |
| Visualization | Plotly (interactive HTML) | Self-contained single file, no server needed. Hover, zoom, filter |

---

## FP Scoring Rules (from Aitor)

FP measures **one thing only**: how faithful the character is in the films compared to the books.

FP does **NOT** measure: importance, screen time, charisma, actor quality, or likability.

**FP = Personality + Narrative Role + Motivations + Character Arc** (each 0–25, total 0–100)

### Scoring Bands

| Dimension | 23–25 | 18–22 | 12–17 | 6–11 | 0–5 |
|-----------|-------|-------|-------|------|-----|
| Personality | Practically identical | Minor changes | Clear changes | Altered | Unrecognizable |
| Narrative Role | Identical | Reduced but recognizable | Altered | Substituted | Eliminated |
| Motivations | Intact | Simplified but correct | Altered | Wrong | Opposite |
| Character Arc | Complete and faithful | Compressed | Incomplete | Altered | Nonexistent or false |

### Golden Rules (non-negotiable)
1. Never compare characters against each other
2. Never use subjective "looks better"
3. Never use screen time as a factor
4. Always justify with book AND film evidence
5. If there is no change → no penalty
6. Little presence ≠ little faithfulness

Full rules (Spanish original): `data/fp_rules.txt`
Translated scoring prompt: `src/scoring/prompts/scoring_prompt.txt`

---

## Pipeline Summary

### V1 (web-scraped)
- Books: 7 files from GitHub, 6.4MB total
- Screenplays: 8 wiki transcripts, 812KB total
- Character registry: 228 characters auto-extracted from dialogue patterns
- Metrics: word-count screen time, regex-based book mentions
- Corpus: 226 character directories

### V2 (Aitor's data + best-of-both)
- Books: same v1 files (best available)
- Screenplays: 4 from v2 PDFs + 4 from v1 transcripts, 616 scenes total
- Character registry: 239 characters from Aitor's xlsx data
- Metrics: actual screen time minutes + actual book mention counts
- Corpus: 224 character directories
- Pipeline: `src/collect/build_v2_pipeline.py`

### Scoring
- Rule-based: placeholder heuristics based on corpus size (for testing pipeline)
- LLM: prompt with Aitor's exact rubric, persistent kiro-cli session, JSON output parsing
- CLI: `python3 src/scoring/score.py --backend llm --characters "Dobby" --top 10`
- Output: `output/scores/scores.json` (rule-based), `output/scores/scores_llm.json` (LLM)

### Reporting
- Ranked table: `output/reports/ranking.csv` + `ranking.md`
- Per-character reports: `output/reports/characters/` (197 markdown files)
- Dashboard: `output/dashboard.html` (interactive Plotly, 6 charts)

---

## Project Structure

```
harry-potter-aitor/
├── data/
│   ├── raw/
│   │   ├── books/                  # v1: 7 individual book text files
│   │   ├── screenplays/            # v1: 8 wiki transcript text files
│   │   ├── screenplays_v2/         # v2: 8 PDF-extracted screenplay texts
│   │   └── books_v2/               # v2: PDF + epub extracted (not primary)
│   ├── parsed/                     # v1 parsed JSON (scenes, chapters)
│   ├── v2/
│   │   ├── characters.yaml         # v2 character registry
│   │   ├── parsed/                 # v2 parsed JSON
│   │   └── corpus/                 # v2 per-character corpus
│   ├── metrics/
│   │   ├── screen_time.json        # v1: word-count estimates
│   │   ├── screen_time_v2.json     # v2: Aitor's actual minutes
│   │   ├── book_mentions.json      # v1: regex-based estimates
│   │   ├── book_mentions_v2.json   # v2: Aitor's actual counts
│   │   └── completeness.json
│   ├── freind-input-data/          # Aitor's raw input files
│   ├── fp_rules.txt                # Extracted FP rules (Spanish)
│   └── characters.yaml             # v1 character registry
├── corpus/                         # v1 per-character corpus
├── src/
│   ├── collect/
│   │   ├── download_books.sh
│   │   ├── download_screenplays.py
│   │   ├── build_character_registry.py
│   │   ├── parse_screenplays.py
│   │   ├── parse_books.py
│   │   ├── process_friend_data.py  # v2 data extraction
│   │   └── build_v2_pipeline.py    # v2 unified pipeline
│   ├── corpus/
│   │   └── build_corpus.py
│   ├── metrics/
│   │   ├── compute_metrics.py
│   │   └── check_completeness.py
│   ├── scoring/
│   │   ├── score.py                # Main scorer (--backend, --characters, --top)
│   │   ├── llm_scorer.py           # LLM backend (kiro-cli + OpenAI API)
│   │   └── prompts/
│   │       └── scoring_prompt.txt  # Aitor's FP rules as LLM prompt
│   └── reporting/
│       ├── generate_reports.py     # CSV + markdown reports
│       └── generate_dashboard.py   # Interactive Plotly HTML
├── output/
│   ├── scores/
│   │   ├── scores.json             # Rule-based scores
│   │   └── scores_llm.json         # LLM scores (when available)
│   ├── reports/
│   │   ├── ranking.csv
│   │   ├── ranking.md
│   │   └── characters/             # Per-character markdown reports
│   └── dashboard.html              # Interactive visualization
├── config.yaml                     # Scoring config (backend, thresholds, LLM settings)
├── requirements.txt                # pyyaml, plotly, pandas, openpyxl, pymupdf, ebooklib
├── PLAN.md                         # Task tracking
├── DECISIONS.md                    # This file
└── questions-for-aitor.md
```

---

## Known Limitations

- **HP3 screenplay** (Prisoner of Azkaban) has poor coverage in both v1 (script-o-rama format, 1 scene detected) and v2 (only 6 pages). May need manual sourcing.
- **Book paragraph splitting** varies by format — books 2-4 use full-width space indent, book 5 uses 4-space indent, books 6-7 use double newlines, book 1 uses line-wrapping. All handled but edge cases possible.
- **Character alias matching** can produce false positives for short/common names. Blocklist mitigates but doesn't eliminate.
- **Rule-based scoring** uses placeholder heuristics (corpus size). Real scores require LLM evaluation.
- **LLM scoring** via kiro-cli persistent session needs further testing.
- **Spanish epub** from Aitor is not usable for English text analysis.
- **Book 2 chapter detection** only finds 10 of 18 chapters due to inconsistent heading formatting in the source text.
