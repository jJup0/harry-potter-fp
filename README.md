# Harry Potter Character Faithfulness (FP) Project

A data pipeline and scoring system that measures how faithfully Harry Potter characters are portrayed in the films compared to the books. Built for Aitor's content creation workflow.

## How It Works (Non-Technical Summary)

The system takes the 7 Harry Potter books and 8 film screenplays, finds every paragraph/scene where each character appears, and builds a per-character "corpus" of all their book material and all their film material. Then an LLM (Claude Sonnet 4.6 via kiro-cli) reads the full corpus for each character along with the FP rubric, and scores how faithfully the film version matches the book version across 6 dimensions. The AI also draws on its own pre-trained knowledge of the series to fill in context beyond the provided excerpts.

Results are cached so re-running only recalculates characters whose aliases, model, or prompt version changed. The final output is an interactive dashboard with rankings, per-dimension breakdowns, presence filters, scatter plots, and click-to-detail panels.

Of 216 characters in the registry, 209 are scored. The remaining 7 are intentionally skipped (generic entries like "Voice" or animals like Hedwig that don't fit the rubric). Characters need at least 10 book mentions to be eligible for scoring.

Dashboard: https://jjup0.github.io/harry-potter-fp/

## What is FP?

FP (Fidelidad del Personaje / Character Faithfulness) is a 0-100 score measuring one thing only: **how faithful a character's film portrayal is to their book counterpart**. It does NOT measure importance, screen time, charisma, or actor quality.

FP = Personality & Voice (0-25) + Narrative Role & Agency (0-20) + Motivations & Internal Conflict (0-15) + Character Arc (0-15) + Key Relationships (0-10) + Complexity & Lost Material (0-15)

A character with 30 seconds of screen time can score 100 if those 30 seconds are faithful.

Aitor's original rules (in Spanish, `data/fp_rules.txt` and `data/fp_rules.md`) define a 4-dimension version with each dimension out of 25. The scorer extended this to 6 dimensions to separate relationships and lost material from the broader categories, and all current scores use the 6-dimension rubric. The authoritative definition is the one in the LLM prompt: `src/scoring/prompts/scoring_prompt_3.txt`.

## Project Status

| Phase | Status | Notes |
|-------|--------|-------|
| Data collection | Done | Books, screenplays, character registry, metrics |
| Corpus building | Done | 228 characters (v1), 216 characters (v2 after dedup) |
| Metrics | Done | Screen time (actual minutes), book mentions (actual counts) |
| LLM scoring | Done | 202/216 scored via kiro-cli (claude-sonnet-4.6), 6 dimensions with justifications |
| Character validation | Done | Wikipedia cross-reference, alias tracking |
| Reports & dashboard | Done | Generated from kiro scores |

**Current state:** 202 characters have LLM-generated FP scores (6 dimensions, max 100) with per-dimension justifications via kiro-cli and claude-sonnet-4.6. 80 characters have no film corpus and score 0. Scoring cache tracks aliases and auto-invalidates when dedup rules change.

## Quick Start

```bash
# Install dependencies
pip install pyyaml plotly pandas openpyxl pymupdf ebooklib

# Fetch canonical character list from Wikipedia (updates data/reference/wikipedia_hp_characters.json)
python3 src/collect/fetch_wikipedia_characters.py

# Validate our characters against Wikipedia (flags unknowns)
python3 src/collect/validate_characters.py

# Run LLM scoring (requires kiro-cli with claude-sonnet-4.6)
python3 -u src/scoring/score.py --backend kiro --characters "Dobby" "Severus Snape"

# Run scoring for top N characters by corpus size
python3 -u src/scoring/score.py --backend kiro --top 50

# Generate reports from existing scores
python3 src/reporting/generate_reports.py
python3 src/reporting/generate_dashboard.py
```

## CIDS (Character Infidelity Damage Score)

CIDS measures the cumulative damage caused by an unfaithful film portrayal, combining how unfaithful the character is (100 - FP), how much screen time is spent on damaging deviations (WIE), and how structurally important those deviations are (SDL).

```
CIDS = (100 - FP) * log2(1 + WIE) * (1 + SDL/8)
```

- **100 - FP**: infidelity score (0-100). Higher means less faithful.
- **WIE** (Weighted Infidelity Exposure): sum of (exposure * impact_weight) across all damaging scenes identified by the LLM. Unbounded - a protagonist with 140 damaging scenes gets WIE ~435.
- **log2(1 + WIE)**: logarithmic dampening prevents protagonists from dominating the ranking purely on volume. Harry Potter's WIE of 435 becomes log2(436) = 8.77 instead of a raw 435x multiplier.
- **SDL** (Structural Damage Level, 1-5): how structurally important the character's deviations are. Applied as a continuous term (1 + SDL/8), giving a range of 1.125 to 1.625.

The previous formula (`CIDS = (100 - FP) * WIE * lookup_table[SDL]`) was unbounded in WIE, so protagonists always topped the ranking regardless of how faithful their portrayal was.

## Architecture

### Data Flow

```
Raw sources -> Parse -> Dedup -> Character corpus -> Score (LLM via kiro-cli) -> Reports/Dashboard
```

1. **Raw sources**: Book text files + screenplay text files + Aitor's xlsx metrics
2. **Parse**: Split into scenes (screenplays) and paragraphs (books), detect characters per segment
3. **Dedup**: Merge character name variants via alias map in `src/collect/build_character_registry.py` (e.g. "Sybil Trelawney" -> "Sybill Trelawney", "Madame Rosmerta" -> "Madam Rosmerta"). Validated against `data/reference/wikipedia_hp_characters.json`.
4. **Corpus**: Per-character collection of every scene/paragraph they appear in (`output/corpus/`)
5. **Score**: Feed book + film corpus together to LLM with rubric, get 4-dimension scores + justifications. Cache stores aliases used at scoring time; scores auto-invalidate when aliases change.
6. **Report**: Aggregate scores into rankings, per-character reports, interactive dashboard

### Corpus Parsing - How Characters Are Detected

The corpus for each character is built by detecting their presence in every paragraph (books) or scene (screenplays).

**Books:** Each book is split into chapters (via regex matching "CHAPTER" headings), then each chapter into paragraphs (by blank lines or indentation patterns). Long paragraphs (>500 chars) are further split at sentence boundaries. For each paragraph, the system checks if any known character name or alias (>= 3 chars) appears as a whole word (case-insensitive). If a character's name/alias is found, that paragraph is added to their book corpus.

**LLM augmentation:** After regex-based detection, each chapter is sent to Claude Sonnet 4.6 which identifies characters referenced by pronoun, nickname, or description (e.g. "He cast a spell" -> Harry Potter, "the Dark Lord" -> Lord Voldemort). The LLM outputs only a corrections dict (paragraph index -> characters to add), keeping output minimal (~500-1500 chars per chapter vs 25K+ input). Augmented results are saved in `output/parsed/books_augmented/`. This adds ~30% more character attributions.

**Context heuristic:** Adjacent paragraphs are included in a character's corpus if they pass a heuristic filter: pronoun continuations (starts with she/he/they), dialogue continuations (starts with a quote), or paragraphs with zero detected characters. This captures pronoun-referenced actions without blanket padding.

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
│   │   └── kiro/                   # Per-character score JSONs (authoritative)
│   │   └── scores_kiro.json        # Combined scores
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
│   │   ├── scorer_kiro.py          # LLM scorer (kiro-cli, book+film comparative)
│   │   └── prompts/scoring_prompt.txt  # English FP rubric for LLM
│   └── reporting/                  # Reports + dashboard generators
├── config.yaml                 # Scoring configuration (model, thresholds)
├── TODO.md                     # Remaining work
├── DECISIONS.md                # Detailed decision log
└── questions-for-aitor.md      # Open questions for client
```

### Scoring Cache & Invalidation

Each per-character score file in `output/scores/kiro/` stores metadata about the conditions under which it was scored:
- `meta.model` - LLM model used
- `meta.prompt_version` - prompt major.minor version
- `meta.aliases` - alias list active when scored

On resume, a score is re-run if:
- Model changed
- Prompt major version bumped
- Alias list for that character changed (dedup rules updated)

### Scoring Backend

The sole scoring backend is `kiro`, which pipes the book+film corpus and rubric to kiro-cli (claude-sonnet-4.6) and parses the structured JSON response. Scores are stored in `output/scores/kiro/`.

## Sample Output

Top scores from the 122 characters with film corpus:

| Character | Pers/25 | Role/20 | Motiv/15 | Arc/15 | Rels/10 | Lost/15 | Total |
|-----------|---------|---------|----------|--------|---------|---------|-------|
| Gilderoy Lockhart | 22 | 17 | 13 | 13 | 7 | 10 | 82 |
| Minerva McGonagall | 21 | 16 | 13 | 13 | 8 | 11 | 82 |
| Molly Weasley | 21 | 16 | 13 | 13 | 8 | 10 | 81 |
| Harry Potter | 20 | 17 | 12 | 11 | 7 | 9 | 76 |
| Severus Snape | 19 | 14 | 11 | 11 | 7 | 9 | 71 |
| Ginny Weasley | 13 | 11 | 9 | 8 | 5 | 7 | 53 |

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

1. **80 characters have no film corpus** - scored 0, excluded from ranking (issue #36 owns the data problem)
2. **Book 2 source file missing chapter headings** - Chapters 7-8 and 13-18 have no detectable headings (OCR artifacts: tabs, mixed case, spaced letters). All text content is present but gets lumped into preceding chapters. Does not affect character detection or scoring since all paragraphs are processed regardless of chapter assignment.
3. **Ron Weasley v2 corpus may be thin** - FIXED: was caused by 4-char alias minimum filtering out "Ron"
4. **Dumbledore v2 corpus may be split** - NOT AN ISSUE: all under albus_dumbledore/
5. **Michael Corner scored 0** - likely empty corpus, needs investigation
6. **110 characters flagged** - not on Wikipedia canonical list (mix of minor chars, truncated names, dedup issues)
7. **Screenplays may contain deleted/draft scenes** - Some screenplay sources include scenes cut from the theatrical release or present only in early drafts. Affected characters:
   - **Sir Cadogan** - only in PoA deleted scenes
   - **Vernon/Petunia/Dudley** - DH farewell is an extended scene
   - **Ernie Macmillan** - CoS scene was deleted
   - **Draco Malfoy** - DH2 screenplay contains wand-toss scene (draft) never in the theatrical cut
8. **Snape dimension distribution inverted** - Total 71 is defensible but personality (19/25) is too generous (Rickman played a fundamentally different, calmer character) and narrative_role (14/25) too harsh (spy function carried over intact). Dimensions partially cancel out to a reasonable total.
9. **LLM hallucination from pretrained knowledge** - The scorer sometimes claims scenes "are present in the film corpus" when they are not, drawing on pretrained film knowledge and misattributing it as corpus evidence. Known cases:
   - **Moaning Myrtle** - claims HBP bathroom scene is in corpus (corpus has 0 HBP scenes for her)
   - **Remus Lupin** - claims DH Grimmauld Place confrontation and Shell Cottage birth announcement are present (neither is in the DH corpus)
   Prompt updated to explicitly prohibit claiming corpus evidence for pretrained knowledge. Affected characters need rescoring.

## Questions for Aitor (Unanswered)

1. Should deleted scenes be included in the film corpus?
2. What's the intended output format for his content? (Ranked list? Per-character deep dives? Video scripts?)
3. Harry/Ron/Hermione are not in the screen time xlsx - intentional or name mismatch?
