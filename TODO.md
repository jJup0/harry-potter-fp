# TODO

Last reviewed: 2026-05-10

## Next

- [ ] Score remaining ~114 characters (resume ollama run or use cloud API)
- [ ] Regenerate reports/dashboard from comparative scores (after scoring complete)
- [ ] why do we still have a mega scores_comparative file
- [ ] rerun the whole "pipeline"
- [ ] remove all deprecated code

## Data Quality

- [ ] Source a better HP3 screenplay (both v1 and v2 are poor - see DATA_SOURCES.md)
- [ ] Fix Book 2 chapter detection (finds 10/18 due to inconsistent headings) - low priority

## Character Name Sanity Check

- [x] Fetch canonical character list from Wikipedia programmatically (`src/collect/fetch_wikipedia_characters.py`)
  - Stored as JSON at `data/reference/wikipedia_hp_characters.json` (142 characters)
  - Re-run to refresh: `python3 src/collect/fetch_wikipedia_characters.py`
- [x] Flag characters not on Wikipedia list (`src/collect/validate_characters.py`)
  - 110 characters flagged (mix of minor chars, dedup issues, truncated names)
  - Run: `python3 src/collect/validate_characters.py`
- [x] Scoring cache tracks aliases and invalidates on change
  - Each score file stores `meta.aliases` - the alias list active when scored
  - On resume, scores with stale aliases are re-scored automatically
  - Backfilled existing 209 scores with pre-dedup aliases (`src/scoring/backfill_aliases.py`)
- [ ] Fix truncated names in characters.yaml (parsing bug cut first chars):
  - `adma Patil` -> Padma Patil (already exists separately)
  - `arvati Patil` -> Parvati Patil (already exists separately)
  - `cy Weasley` -> Percy Weasley (already exists separately)
  - `mona Sprout` -> Pomona Sprout (already exists separately)
  - `tunia Dursley` -> Petunia Dursley (already exists separately)
  - `ter Pettigrew` -> Peter Pettigrew (already exists separately)
- [ ] Remove duplicate entries (different spellings/formats of same character):
  - `Alastor "Mad-Eye" Moody` / `Alastor Moody`
  - `Bartemius Crouch Jr` / `Bartemius Crouch Jr.`
  - `Bartemius Crouch Sr` / `Bartemius Crouch Sr.`
  - `Colin Creevey` / `Colin Creevy`
  - `Sybill Trelawney` / `Sybil Trelawney`
  - `Alicia Spinnet` / `Alicia Spinnett`
  - `Madam Rosmerta` / `Madame Rosmerta`
  - `Olympe Maxime` / `Madame Olympe Maxime`
  - `Voldemort` / `Lord Voldemort` / `Tom Riddle / Voldemort`
  - `Scabbers / Peter Pettigrew` / `Peter Pettigrew`
  - `Albus Potter` / `Albus Severus Potter`
  - `Marjorie Dursley` / `Marge Dursley`
- [ ] Fix misspellings: `Hannah Abbot` -> `Hannah Abbott`

## Validation

- [ ] Investigate Michael Corner scoring 0 - likely empty corpus
- [ ] Investigate Zacharias Smith (20) and Padma Patil (20) - data issue or legitimate?
- [ ] Check Ron Weasley v2 corpus - may be split across directories
- [ ] Check Dumbledore v2 corpus - may be split (`albus_dumbledore` vs `dumbledore`)

## Long Term

- [ ] Support multiple LLM providers (OpenAI, Anthropic, etc.) as swappable backends behind the same comparative scoring logic and prompt. Resume logic already tracks model per score.
- [ ] code style - reuseable directory paths - i.e. calc them once in a utils type model. use PathLib istead of os.path. imports? im sure they're messy. add type hints. code comments. docstrings.
