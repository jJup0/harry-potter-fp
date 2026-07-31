# Pipeline Internals

Reference for how the corpus is built and how scores are cached. See the README for the
overview and the commands.

## Character detection

The corpus for each character is every passage they appear in. Detection runs in four passes.

**1. Regex matching.** Books are split into chapters (regex on "CHAPTER" headings), chapters into
paragraphs (blank lines or indentation), and paragraphs over 500 characters are split again at
sentence boundaries. Each paragraph is tested for every known character name and alias of 3 or more
characters, matched case-insensitively on word boundaries.

**2. LLM augmentation.** Each chapter is sent to Claude Sonnet 4.6, which identifies characters
referenced by pronoun, nickname, or description ("He cast a spell" to Harry Potter, "the Dark Lord"
to Lord Voldemort). The model returns only a corrections dict of paragraph index to characters to
add, keeping output at roughly 500-1500 characters per chapter against a 25K+ character input.
Results land in `output/parsed/books_augmented/`. This adds about 30% more attributions.

**3. Context heuristic.** An adjacent paragraph joins a character's corpus if it starts with a
pronoun (she/he/they), starts with a quotation mark, or has no detected characters at all. This
catches pronoun-referenced action without padding every entry with its neighbours.

**4. Alias resolution.** Every name is mapped through `KNOWN_CHARACTERS` in
`src/collect/build_character_registry.py`, which folds variants onto one canonical name ("Sybil
Trelawney", "Professor Trelawney", "Trelawney" to Sybill Trelawney). Validated against
`data/reference/wikipedia_hp_characters.json`. Hand-curated additions live in
`data/manual-character-alias-mapping.jsonc`.

Characters need 10 combined book mentions plus screen time to be eligible for scoring
(`scoring.min_mentions`).

## Screenplay parsing

Two formats, because the sources differ:

- **v1, wiki transcripts.** `Speaker: dialogue` patterns plus `[stage directions]` in brackets.
  Scene breaks inferred from keywords in directions ("cut to", "meanwhile", "later" - the full list
  is `segmentation.scene_break_keywords` in config.yaml). A character is in a scene if they speak or
  are named in a stage direction.
- **v2 and v3, proper screenplay format.** `INT.`/`EXT.` scene headers and ALL-CAPS speaker names.
  A character is in a scene if they speak or appear in that scene's character list.

`data/source/screenplays_merged/` symlinks the best source per film; see `SOURCE.md` inside it and
`DATA_SOURCES.md` for the per-film quality assessment.

### The screenplay-only limitation

The film corpus is derived entirely from screenplay text, so a character who appears on screen
without dialogue and without being named in a stage direction has an empty film corpus even though
they are plainly visible in the film. Screenplays do not name background actors.

Ernie Prang is the clean example: 1.0 minute of measured screen time in Prisoner of Azkaban as the
Knight Bus driver, and the string "prang" appears in none of the screenplay sources. He is not
scorable either, since a silent appearance offers no material against which faithfulness could be
judged.

`data/film_presence_gaps.json` holds the gap analysis and
`src/collect/verify_film_presence_gaps.py` reproduces it from repo data. The analysis separates three
groups: characters proven on screen but absent from every screenplay, characters whose zero score is
a stale-cache artefact rather than a presence problem, and characters our data simply cannot decide,
which need the client to confirm on-screen presence.

## Deleted and non-theatrical scenes

Some screenplay sources contain material that never reached the theatrical cut - deleted scenes,
extended-edition scenes, and draft-only scenes. This cannot be detected from screenplay text, so
`data/deleted_scenes.jsonc` is a hand-maintained list keyed by film and scene index, carrying the
affected characters and a reason.

`src/scoring/deleted_scenes.py` applies it at corpus-load time in both scorers, so adding an entry
requires no corpus rebuild. Scenes can be filtered out of scoring or merely tagged, the latter
keeping the material available for trivia output (`output/reports/deleted_scenes_trivia.md`).

Known entries: Sir Cadogan's three PoA scenes (all deleted, leaving him no film corpus at all), the
Dursleys' Deathly Hallows farewell (extended edition), Ernie Macmillan's Chamber of Secrets scene,
and Draco Malfoy's Deathly Hallows Part 2 wand toss (draft only).

## Score caching and invalidation

Each file in `output/scores/kiro/` records the conditions it was produced under:

| Field | Purpose |
|---|---|
| `meta.model` | LLM used |
| `meta.prompt_version` | major.minor of the prompt file |
| `meta.aliases` | alias list active at scoring time |

A cached FP score is re-run when the model changes, the prompt major version is bumped, or the
character's alias list changes because dedup rules moved. CIDS applies the same prompt-version check
via `_get_prompt_version()`.

Practical notes:

- To force a rescore of one character, delete their score file. Both scorers skip any character that
  already has a valid cached file.
- `scoring.corpus_version` in config.yaml exists to invalidate everything after a corpus change, but
  a zero-score file has `meta.model` of null and the resume logic currently treats that as
  intentionally unscored, so zero-scored characters are never revisited. This is a known bug.
- The CIDS prompt is at version 2.0 while most cached CIDS files predate it, so running
  `src/scoring/cids.py` with no `--characters` filter will re-score every character with a film
  corpus. Always pass `--characters` unless a full re-run is the intent.

## Scoring prompts

| File | Used by |
|---|---|
| `src/scoring/prompts/scoring_prompt_3.txt` | FP, authoritative 6-dimension rubric |
| `src/scoring/prompts/cids_prompt.txt` | CIDS, version 2.0 |

Both prompts forbid the model from presenting pretrained film knowledge as corpus evidence: it may
use that knowledge to interpret what the corpus contains, but every cited scene must rest on
material physically present in the supplied text, and a thin corpus should produce fewer findings at
lower confidence rather than invented ones. This rule exists because earlier scores cited scenes that
were not in the corpus at all, such as a Half-Blood Prince bathroom scene for Moaning Myrtle whose
corpus contains no Half-Blood Prince material.

`src/scoring/verify_cids.py` checks cited scenes against corpus contents without spending tokens,
writing results to `output/scores/cids/_verification.json`. It parses the film identifier out of each
cited scene string, so it only covers entries that lead with one - a partial net, not a full audit.

## Dashboard

`src/reporting/dashboard/generate.py` renders `template.html` with inlined Plotly into a single
self-contained file. Features: stacked per-dimension bar charts with a count selector, a book
mentions against screenplay words scatter coloured by FP, a score histogram, presence-filter
sliders, character search, click-to-detail panels with per-dimension justifications, `#character=Name`
URL linking, and a mobile bottom-sheet layout.

Characters listed under `scoring.exclude_from_output` in config.yaml are dropped from the dashboard,
the CSV, and the markdown reports.
