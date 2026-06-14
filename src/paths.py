"""Shared project paths. Import from here instead of computing in each script."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Source data (immutable inputs)
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "source"
BOOKS_DIR = SOURCE_DIR / "books"
SCREENPLAYS_DIR = SOURCE_DIR / "screenplays_merged"
METRICS_DIR = SOURCE_DIR / "metrics"
SCREEN_TIME_FILE = METRICS_DIR / "screen_time_v2.json"
BOOK_MENTIONS_FILE = METRICS_DIR / "book_mentions_v2.json"
ALIAS_FILE = DATA_DIR / "manual-character-alias-mapping.jsonc"

# Derived data (all regenerable)
OUTPUT_DIR = PROJECT_ROOT / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
PARSED_BOOKS_DIR = PARSED_DIR / "books"
PARSED_BOOKS_AUGMENTED_DIR = PARSED_DIR / "books_augmented"
PARSED_SCREENPLAYS_DIR = PARSED_DIR / "screenplays"
CORPUS_DIR = OUTPUT_DIR / "corpus"
CHARACTERS_FILE = OUTPUT_DIR / "characters.yaml"
SCORES_DIR = OUTPUT_DIR / "scores"
COMPARATIVE_SCORES_DIR = SCORES_DIR / "comparative"
KIRO_SCORES_DIR = SCORES_DIR / "kiro"
CIDS_DIR = SCORES_DIR / "cids"
REPORTS_DIR = OUTPUT_DIR / "reports"
DASHBOARD_FILE = OUTPUT_DIR / "dashboard.html"

# Prompts
PROMPTS_DIR = PROJECT_ROOT / "src" / "scoring" / "prompts"
