# Harry Potter Character Faithfulness (FP) Project

A data pipeline and scoring system that measures how faithfully Harry Potter characters are portrayed in the films compared to the books. Built for Aitor's content creation workflow.

## What is FP?

FP (Fidelidad del Personaje / Character Faithfulness) is a 0–100 score measuring one thing only: **how faithful a character's film portrayal is to their book counterpart**. It does NOT measure importance, screen time, charisma, or actor quality.

FP = Personality (0–25) + Narrative Role (0–25) + Motivations (0–25) + Character Arc (0–25)

A character with 30 seconds of screen time can score 100 if those 30 seconds are faithful. The full scoring rubric (in Spanish) is in `data/fp_rules.txt`, and the English LLM prompt translation is in `src/scoring/prompts/scoring_prompt.txt`.

## Project Status

| Phase | Status | Notes |
|-------|--------|-------|
| Data collection | ✅ Done | Books, screenplays, character registry, metrics |
| Corpus building | ✅ Done | 224 characters (v2), 226 characters (v1) |
| Metrics | ✅ Done | Screen time (actual minutes), book mentions (actual counts) |
| Rule-based scoring | ✅ Done | Placeholder heuristics only — not real FP scores |
| LLM scoring | ❌ Broken | Both kiro and OpenAI backends fail (all scores = 0, `"error": true`) |
| Reports & dashboard | ✅ Done | But based on rule-based placeholder scores, not real FP |

**The critical blocker is LLM scoring.** The rule-based scorer is just a placeholder that scores based on corpus size (more text = higher score), which is meaningless for FP. Real scoring requires an LLM to read the corpus and evaluate faithfulness per Aitor's rubric.

## Quick Start

```bash
# Install dependencies
pip install pyyaml plotly pandas openpyxl pymupdf ebooklib

# Run rule-based scoring (placeholder)
python3 src/scoring/score.py --backend rule_based --top 20

# Run kiro-cli scoring (currently broken)
python3 src/scoring/score.py --backend kiro --characters "Dobby"

# Generate reports from existing scores
python3 src/reporting/generate_reports.py
python3 src/reporting/generate_dashboard.py
```

## Architecture

### Data Flow

```
Raw sources → Parse → Character corpus → Score (LLM) → Reports/Dashboard
```

1. **Raw sources**: Book text files + screenplay text files + Aitor's xlsx metrics
2. **Parse**: Split into scenes (screenplays) and paragraphs (books), detect characters per segment
3. **Corpus**: Per-character collection of every scene/paragraph they appear in
4. **Score**: Feed corpus + rubric to LLM, get 4-dimension scores per character per source
5. **Report**: Aggregate scores into rankings, per-character reports, interactive dashboard

### Data Versions

There are two generations of data (v1 and v2). The project uses the best source per data type:

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
│   ├── v2/corpus/              # Per-character corpus (v2)
│   ├── metrics/                # Screen time + book mentions (v1 and v2)
│   ├── freind-input-data/      # Aitor's raw input files
│   └── fp_rules.txt            # FP scoring rules (Spanish)
├── corpus/                     # Per-character corpus (v1)
├── src/
│   ├── collect/                # Data ingestion scripts
│   ├── corpus/build_corpus.py  # Corpus builder
│   ├── metrics/                # Metrics computation
│   ├── scoring/                # FP scoring framework
│   └── reporting/              # Reports + dashboard
├── output/
│   ├── scores/                 # Score JSON files
│   ├── reports/                # CSV + markdown reports
│   └── dashboard.html          # Interactive Plotly dashboard
├── config.yaml                 # Scoring configuration
└── DECISIONS.md                # Detailed decision log
```

### Scoring Backends

| Backend | How it works | Status |
|---------|-------------|--------|
| `rule_based` | Placeholder: scores based on corpus size | Works, but scores are meaningless |
| `kiro` | Pipes prompt to `kiro-cli --no-interactive` | Fails — all responses error out |
| `openai` | Standard OpenAI chat completions API | Needs API key configured |

## Known Issues

1. **LLM scoring completely broken**: Both `scores_kiro.json` and `scores_llm.json` show all zeros with `"error": true` for every source. The kiro scorer's ANSI stripping / response parsing may be the issue, or the prompt may be too large.

2. **HP3 screenplay coverage is poor**: Prisoner of Azkaban has only 1 scene detected (v1) or 6 pages (v2). This film's characters will have weak screenplay corpus data.

3. **Duplicate character directories in corpus**: Some characters appear under multiple names (e.g., `colin_creevey` and `colin_creevy`, `sybil_trelawney` and `sybill_trelawney`, `madame_poppy_pomfrey` and `poppy_pomfrey`). The alias system should collapse these but the v1 corpus has duplicates.

4. **Generic "characters" pollute corpus**: Entries like `all`, `you`, `everyone`, `boy`, `man`, `crowd`, `hogwarts`, `voice` have huge corpus files (the `you` corpus is 3.5MB). The blocklist exists but doesn't cover all cases, and the v1 corpus was built before the blocklist was complete.

5. **v2 corpus vs v1 corpus confusion**: Two separate corpus directories exist (`corpus/` for v1, `data/v2/corpus/` for v2). The scorer reads from `corpus/` (v1). It's unclear if the v2 corpus was ever fully built or if the scorer should be pointed at it.

6. **Book 2 chapter detection**: Only finds 10 of 18 chapters due to inconsistent heading formatting.

7. **Dashboard and reports use rule-based scores**: Since LLM scoring never succeeded, all output artifacts reflect the placeholder heuristic scores.

8. **Screen time = 0 for Harry, Ron, Hermione in v2 characters.yaml**: The three main characters show `screen_time_minutes: 0` in the registry. Either the xlsx didn't have their data or the extraction missed them.

## Questions / Unclear Areas

1. **Which corpus does the scorer actually use?** `score.py` reads from `corpus/` (v1), but the v2 pipeline writes to `data/v2/corpus/`. Are the v2 corpus files complete? Should the scorer be switched to v2?

2. **What broke the kiro scorer?** The `scores_kiro.json` shows every source errored. Was this a kiro-cli version issue, prompt size issue, or parsing issue? The debug files in `/tmp/hp_kiro_debug_*` might have clues if they still exist.

3. **Per-source vs per-character scoring**: The current design scores each character per-source (per book, per film) then aggregates. But FP is about book-vs-film comparison. Should the scorer receive BOTH the book corpus AND film corpus for a character and compare them, rather than scoring each source independently?

4. **Aggregation logic**: `aggregate_scores()` weights by scene/paragraph count. A character with 1000 book paragraphs and 5 screenplay scenes will have their score dominated by the book score. Is that the intent?

5. **What does Aitor want to do with the scores?** The DECISIONS.md mentions Instagram/TikTok/YouTube content. Is the goal a ranked list? Per-character deep dives? Comparison videos? This affects what the output format should be.

6. **Deleted scenes**: Aitor mentioned having deleted scenes but couldn't think of how to separate them. Should they be included in the film corpus or excluded?

7. **"Compares these corpus"**: Still unanswered from the original questions. What exactly is being compared?
