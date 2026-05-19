# Harry Potter Character Faithfulness (FP) Project

A data pipeline and scoring system that measures how faithfully Harry Potter characters are portrayed in the films compared to the books. Built for Aitor's content creation workflow.

## How It Works (Non-Technical Summary)

The system takes the 7 Harry Potter books and 8 film screenplays, finds every paragraph/scene where each character appears, and builds a per-character "corpus" of all their book material and all their film material. Then a local AI model (Gemma 4) reads both sides - up to ~15,000 characters of book text and ~15,000 of film text per character - along with Aitor's FP rubric, and scores how faithfully the film version matches the book version across 4 dimensions. The AI also draws on its own pre-trained knowledge of the series to fill in context beyond the provided excerpts. For major characters with huge corpora, the AI sees a representative sample rather than every single mention.

Results are cached so re-running only recalculates characters whose aliases, model, or prompt version changed. The final output is an interactive dashboard with rankings, per-dimension breakdowns, presence filters, scatter plots, and click-to-detail panels.

Of 216 characters in the registry, 209 are scored. The remaining 7 are intentionally skipped (generic entries like "Voice" or animals like Hedwig that don't fit the rubric). Characters need at least 10 book mentions to be eligible for scoring.

Dashboard: https://jjup0.github.io/harry-potter-fp/

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

### Corpus Parsing - How Characters Are Detected

The corpus for each character is built by detecting their presence in every paragraph (books) or scene (screenplays).

**Books:** Each book is split into chapters (via regex matching "CHAPTER" headings), then each chapter into paragraphs (by blank lines or indentation patterns). For each paragraph, the system checks if any known character name or alias appears as a whole word (case-insensitive, minimum 4 characters to avoid false positives). If a character's name/alias is found, that paragraph is added to their book corpus.

**Screenplays (v1 - wiki transcripts):** Parsed by detecting `Speaker: dialogue` patterns and `[stage directions]` in brackets. Scene breaks are detected by keywords in directions (e.g. "cut to", "meanwhile", "later"). A character is included in a scene if they speak (their name appears as a speaker) or their name/alias appears in a stage direction.

**Screenplays (v2/v3 - proper format):** Parsed by detecting `INT./EXT.` scene headers and ALL-CAPS speaker names. A character is included if they speak or their name appears in the character list for that scene.

**Alias resolution:** All character names are mapped through `KNOWN_CHARACTERS` in `build_character_registry.py`, which maps variants (e.g. "Sybil Trelawney", "Professor Trelawney", "Trelawney") to a single canonical name. The alias map is built as lowercase -> canonical for matching.

**Minimum threshold:** Characters need at least 10 combined book mentions + screen time to be eligible for scoring.

### Data Sources

| Data | Source | Why |
|------|--------|-----|
| Book texts | v1 (GitHub) | Clean per-book text files |
| Screenplays | screenplays_merged/ (symlinks) | Best source per film: v1 fan transcripts, v2 Aitor PDFs, or v3 Script Slug |
| Screen time | v2 (Aitor's xlsx) | Actual measured minutes per character per film |
| Book mentions | v2 (Aitor's xlsx) | Actual counted mentions per character per book |
| Character registry | v2 (from Aitor's data) | 239 canonical characters |
| Wikipedia characters | Fetched programmatically | 142 canonical characters for validation |

### Directory Structure

```
├── data/                           # SOURCE DATA (immutable inputs)
│   ├── source/
│   │   ├── books/                  # 7 book text files
│   │   ├── screenplays/            # 8 wiki transcripts (v1, fan-curated dialogue)
│   │   ├── screenplays_v2/         # 8 PDF-extracted screenplays (from Aitor's PDFs)
│   │   ├── screenplays_v3/         # 8 Script Slug PDFs + extracted text
│   │   ├── screenplays_merged/     # Symlinks to best source per film (see SOURCE.md inside)
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

## Dashboard Features

The interactive dashboard (`output/dashboard.html`) provides:

- **Stacked bar charts** - Top and bottom characters ranked by FP score, broken down by dimension. Dropdown to control how many characters are visible (5/10/20/50/100/All).
- **Scatter plot** - Book mentions vs screenplay words, colored by FP score. Shows which characters have the most material in each medium.
- **Score distribution histogram** - How FP scores are distributed across all characters.
- **Presence filters** - Sliders to filter by minimum book mentions and minimum screenplay words. Updates all charts and the character list in real-time.
- **Character search** - Text search to find specific characters in the all-characters list.
- **Click-to-detail panel** - Click any character in a chart or the list to open a side panel with per-dimension scores and full justifications.
- **URL hash linking** - Direct links to specific characters via `#character=Name` in the URL.
- **Mobile responsive** - Detail panel becomes a bottom sheet on small screens.

Dashboard: https://jjup0.github.io/harry-potter-fp/

## Known Issues

1. **Reports/dashboard use rule-based scores** - need regeneration from comparative scores
2. **HP3 screenplay coverage** - RESOLVED: now using Steve Kloves Full Tan Draft from Script Slug (v3)
3. **Ron Weasley v2 corpus may be thin** - check if data split across directories
4. **Dumbledore v2 corpus may be split** - check `albus_dumbledore` vs `dumbledore`
5. **Michael Corner scored 0** - likely empty corpus, needs investigation
6. **110 characters flagged** - not on Wikipedia canonical list (mix of minor chars, truncated names, dedup issues)

## Questions for Aitor (Unanswered)

1. Should deleted scenes be included in the film corpus?
2. What's the intended output format for his content? (Ranked list? Per-character deep dives? Video scripts?)
3. Harry/Ron/Hermione are not in the screen time xlsx - intentional or name mismatch?
