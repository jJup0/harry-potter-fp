"""Shared project paths. Import from here instead of computing in each script.

Every path is a ``pathlib.Path``. Modules that need a string for an older API can
call ``str()`` or ``os.fspath()``, but both ``open()`` and ``os.path.join()``
accept Path objects directly, so that is rarely necessary.

The point of this module is that seventeen scripts used to derive PROJECT_ROOT
themselves with varying numbers of ``".."`` segments depending on how deeply they
were nested, which meant moving a file silently changed where it read and wrote.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_FILE = PROJECT_ROOT / "config.yaml"

# Source data (immutable inputs)
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "source"
BOOKS_DIR = SOURCE_DIR / "books"
SCREENPLAYS_DIR = SOURCE_DIR / "screenplays_merged"
METRICS_DIR = SOURCE_DIR / "metrics"
SCREEN_TIME_FILE = METRICS_DIR / "screen_time_v2.json"
BOOK_MENTIONS_FILE = METRICS_DIR / "book_mentions_v2.json"
REFERENCE_DIR = DATA_DIR / "reference"
WIKIPEDIA_CHARACTERS_FILE = REFERENCE_DIR / "wikipedia_hp_characters.json"
ALIAS_FILE = DATA_DIR / "manual-character-alias-mapping.jsonc"
DELETED_SCENES_FILE = DATA_DIR / "deleted_scenes.jsonc"
DELETED_SCENES_REPORTED_FILE = DATA_DIR / "deleted_scenes_reported.jsonc"
FILM_PRESENCE_GAPS_FILE = DATA_DIR / "film_presence_gaps.json"

# Derived data (all regenerable)
OUTPUT_DIR = PROJECT_ROOT / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
PARSED_BOOKS_DIR = PARSED_DIR / "books"
PARSED_BOOKS_AUGMENTED_DIR = PARSED_DIR / "books_augmented"
PARSED_SCREENPLAYS_DIR = PARSED_DIR / "screenplays"
CORPUS_DIR = OUTPUT_DIR / "corpus"
CHARACTERS_FILE = OUTPUT_DIR / "characters.yaml"
SCORES_DIR = OUTPUT_DIR / "scores"
KIRO_SCORES_DIR = SCORES_DIR / "kiro"
KIRO_SCORES_FILE = SCORES_DIR / "scores_kiro.json"
CIDS_DIR = SCORES_DIR / "cids"
MODEL_COMPARISON_DIR = SCORES_DIR / "model_comparison"
REPORTS_DIR = OUTPUT_DIR / "reports"
DASHBOARD_FILE = OUTPUT_DIR / "dashboard.html"
CUT_SCENES_DIR = OUTPUT_DIR / "cut_scenes"
CUT_SCENES_FILE = OUTPUT_DIR / "cut_scenes.html"
SCENE_CHAPTER_MAPPING_DIR = OUTPUT_DIR / "scene_chapter_mapping"
DELETED_SCENE_CHARACTERS_DIR = OUTPUT_DIR / "deleted_scene_characters"
SANITY_CHECKS_DIR = OUTPUT_DIR / "sanity_checks"

# Prompts
PROMPTS_DIR = PROJECT_ROOT / "src" / "scoring" / "prompts"
SCORING_PROMPT_FILE = PROMPTS_DIR / "scoring_prompt_3.txt"
CIDS_PROMPT_FILE = PROMPTS_DIR / "cids_prompt.txt"

# Scratch space for non-interactive kiro-cli calls. These must never run in the
# project directory, so they get dedicated directories under /tmp.
KIRO_SCORING_CWD = Path("/tmp/harry-potter-scoring-calls")
KIRO_SCORING_RAW_DIR = Path("/tmp/harry-potter-scoring-raw")
KIRO_CIDS_RAW_DIR = Path("/tmp/harry-potter-cids-raw")
KIRO_DELETED_SCENE_CWD = Path("/tmp/harry-potter-deleted-scene-tagging")
KIRO_SCENE_MAPPING_CWD = Path("/tmp/harry-potter-scene-mapping")
KIRO_LLM_PARSE_CWD = Path("/tmp/harry-potter-llm-parse")
KIRO_CUT_SCENES_CWD = Path("/tmp/harry-potter-cut-scenes")
KIRO_SANITY_CHECKS_CWD = Path("/tmp/harry-potter-sanity-checks")
