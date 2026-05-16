# TODO

Last reviewed: 2026-05-16

## Bugs

- [ ] Dashboard: mobile detection for default chart count not working in Brave responsive simulator

## Next

- [ ] Remove mega `scores_comparative.json` or regenerate it from individual score files
- [ ] Remove deprecated code (old backends, dead scripts)

## Data Quality

- [ ] Source a better HP3 screenplay (both v1 and v2 are poor)
- [ ] Fix Book 2 chapter detection (finds 10/18 due to inconsistent headings) - low priority

## Validation

- [ ] Investigate Michael Corner scoring 0 - likely empty corpus
- [ ] Investigate Zacharias Smith (20) and Padma Patil (20) - data issue or legitimate?
- [ ] Check Ron Weasley corpus - may be split across directories
- [ ] Check Dumbledore corpus - may be split (`albus_dumbledore` vs `dumbledore`)

## Long Term

- [ ] Support multiple LLM providers (OpenAI, Anthropic, etc.) as swappable backends
- [ ] Code style - reusable directory paths (calc once in utils, use pathlib instead of os.path), clean imports, type hints, code comments, docstrings
