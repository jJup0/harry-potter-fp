# Harry Potter Character Faithfulness

Scores how faithfully the eight Harry Potter films adapt each character from the seven books, and how
much damage the unfaithful portrayals do. Built for a video content workflow, so the output is a
shareable dashboard rather than a library.

**Dashboard: <https://jjup0.github.io/harry-potter-fp/>**

The pipeline reads the books and the film screenplays, collects every passage where each character
appears, and asks an LLM (Claude Sonnet 4.6 via kiro-cli) to compare the two bodies of material
against a fixed rubric. Every score carries per-dimension justifications citing the evidence it was
based on.

## What it measures

**FP (Fidelidad del Personaje), 0-100** - how closely a character's film portrayal matches their book
counterpart. Nothing else: not importance, not screen time, not charisma, not the actor's
performance. A character with 30 seconds of screen time can score 100 if those 30 seconds are
faithful.

```
FP = Personality & Voice (/25)
   + Narrative Role & Agency (/20)
   + Motivations & Internal Conflict (/15)
   + Character Arc (/15)
   + Key Relationships (/10)
   + Complexity & Lost Material (/15)
```

**CIDS (Character Infidelity Damage Score)** - how much cumulative damage an unfaithful portrayal
does, which is a different question from how unfaithful it is.

```
CIDS = (100 - FP) * log2(1 + WIE) * (1 + SDL/8)
```

- **100 - FP** is the infidelity score.
- **WIE** (Weighted Infidelity Exposure) sums exposure times impact weight over every damaging scene
  the LLM identifies. It is unbounded - a protagonist with 140 damaging scenes reaches WIE 435.
- **log2(1 + WIE)** dampens that, so volume of screen time cannot dominate the ranking on its own.
  Harry Potter's WIE of 435 contributes a factor of 8.77 rather than 435.
- **SDL** (Structural Damage Level, 1-5) rates how structurally important the deviations are, applied
  continuously as `1 + SDL/8` for a range of 1.125 to 1.625.

The two rankings answer different questions and disagree sharply. FP is topped by minor characters
who were adapted cleanly; CIDS is topped by characters whose flattening cost the story the most
(currently Percy Weasley at 483.6, Kreacher at 429.6, Ginny Weasley at 391.3).

The authoritative rubric is the one in the prompt, `src/scoring/prompts/scoring_prompt_3.txt`.
`data/fp_rules.md` is the original client-supplied 4-dimension spec that it supersedes.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml plotly pandas openpyxl pymupdf ebooklib
```

Scoring needs kiro-cli on PATH with access to claude-sonnet-4.6. Reporting does not.

```bash
# FP scoring - always name characters or cap with --top, a bare run re-scores everything
.venv/bin/python -u src/scoring/score.py --backend kiro --characters "Dobby" "Severus Snape"
.venv/bin/python -u src/scoring/score.py --backend kiro --top 50

# CIDS scoring, for characters that already have an FP score
.venv/bin/python -u src/scoring/cids.py --characters "Percy Weasley"

# Reports and dashboard, no LLM calls
.venv/bin/python src/reporting/generate_reports.py
.venv/bin/python src/reporting/dashboard/generate.py
```

Scores are cached per character. Delete a character's file in `output/scores/kiro/` to force a
rescore. Details in [docs/pipeline.md](docs/pipeline.md#score-caching-and-invalidation).

To deploy the dashboard, copy `output/dashboard.html` over `index.html` on the `gh-pages` branch and
push; GitHub Pages serves it. Use a worktree outside the repo rather than switching branches.

## How it works

```
books + screenplays -> parse -> dedup -> per-character corpus -> LLM scoring -> reports + dashboard
```

1. **Parse.** Books split into chapters and paragraphs, screenplays into scenes. Characters detected
   per segment by name and alias matching, then augmented by an LLM pass that catches pronoun and
   nickname references.
2. **Dedup.** Name variants folded onto canonical names via the alias map, validated against a
   Wikipedia-derived character list.
3. **Corpus.** Every scene and paragraph a character appears in, written to `output/corpus/`.
   Deleted and non-theatrical scenes are filtered out at load time.
4. **Score.** Book and film corpus go to the LLM together with the rubric. Returns per-dimension
   scores with justifications. Cached with the model, prompt version, and aliases used.
5. **Report.** Rankings, per-character markdown, and a single self-contained HTML dashboard.

[docs/pipeline.md](docs/pipeline.md) covers character detection, screenplay formats, the deleted-scene
list, cache invalidation, and the anti-hallucination rules in the prompts.

## Repository layout

```
data/                     Source data, treated as immutable
  source/books/           7 book text files
  source/screenplays*/    3 screenplay sources; screenplays_merged/ symlinks the best per film
  source/metrics/         Measured screen time and book mentions, from the client's xlsx
  reference/              Wikipedia character list for validation
  deleted_scenes.jsonc    Hand-maintained non-theatrical scene list
  film_presence_gaps.json Characters on screen but absent from screenplay text
  fp_rules.md             Original client rubric, superseded
output/                   Derived, all regenerable
  parsed/ corpus/         Intermediate pipeline output
  characters.yaml         Character registry
  scores/kiro/            FP scores, authoritative
  scores/cids/            CIDS scores
  reports/                CSV and markdown
  dashboard.html          Shareable dashboard
src/
  collect/                Parsing, registry, validation, presence checks
  scoring/                score.py, cids.py, scorer_kiro.py, prompts/
  reporting/              Reports and dashboard generators
config.yaml               Model, thresholds, output exclusions
```

## Current state

| | Count |
|---|---|
| Characters in registry | 213 |
| Scored | 202 |
| With film corpus, FP above 0 | 122 |
| No film corpus, scored 0 | 80 |
| With a CIDS score | 122 |
| In the ranking reports | 120 |
| In the dashboard | 200 |

Characters below `scoring.min_mentions` are not scored. Two entries are suppressed from all output
via `scoring.exclude_from_output`.

## Known limitations

- **Screenplay-derived film corpus.** Characters visible on screen but never named in the screenplay
  have no film material and cannot be scored. See
  [the gap analysis](docs/pipeline.md#the-screenplay-only-limitation).
- **Deleted scenes need a human.** Non-theatrical material is not detectable from screenplay text, so
  `data/deleted_scenes.jsonc` is maintained by hand and is certainly incomplete.
- **Book 2 chapter headings.** The Chamber of Secrets source file has undetectable headings for
  chapters 7-8 and 13-18 (OCR artefacts). All text is present and scoring is unaffected, since
  paragraphs are processed regardless of chapter assignment.
- **LLM judgement is not stable to the decimal.** Rescoring the same character can move the total by
  a point or two. Treat small differences as noise; the bands are meaningful, the exact numbers are
  not.

Open bugs and data-quality problems are tracked as
[GitHub issues](https://github.com/jJup0/harry-potter-fp/issues).

## Further reading

| Document | Contents |
|---|---|
| [docs/pipeline.md](docs/pipeline.md) | Corpus building, caching, prompts, dashboard internals |
| [DATA_SOURCES.md](DATA_SOURCES.md) | Per-source quality assessment and which screenplay wins per film |
| [DECISIONS.md](DECISIONS.md) | Decision log, including retired approaches |
| [AGENTS.md](AGENTS.md) | Conventions for automated agents working in this repo |
