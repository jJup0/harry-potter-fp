"""Corpus-derived presence metrics for the reports and dashboard.

The presence columns used to come straight out of each score file's meta, and both
of them printed 0 in cases where there was plenty of material:

`screenplay_words` counts only words the character speaks, so every character who
never speaks scored 0 no matter how much film material they have. Fang has 15 film
scenes and 2.5 minutes of screen time and still showed 0. Presenting that next to
an FP of 82 invites the reaction that the data is broken.

`book_mentions` and `screen_time_minutes` come from Aitor's measured xlsx, which is
authoritative where it has a row but is missing rows for several characters -
Fawkes has no book-mentions row despite 133 paragraphs in the book corpus, and
Harry, Ron and Hermione have no screen-time rows at all.

So: report scene and paragraph counts derived from the corpus, which is the same
material the scorer was actually shown, and fall back to those counts wherever the
measured metrics have no row. `measured` flags tell the caller which is which.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import CORPUS_DIR

_cache = {}


def _safe_name(char_name):
    return re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")


def corpus_counts(char_name):
    """Scene and paragraph counts for a character, straight from the corpus."""
    if char_name in _cache:
        return _cache[char_name]
    base = CORPUS_DIR / _safe_name(char_name)
    counts = {"film_scenes": 0, "book_paragraphs": 0}
    for sub, key in (("screenplays", "film_scenes"), ("books", "book_paragraphs")):
        path = base / sub / "scenes.json"
        if path.exists():
            with open(path) as f:
                counts[key] = len(json.load(f).get("scenes", []))
    _cache[char_name] = counts
    return counts


def presence(score_record):
    """Presence metrics for one score record, measured where available.

    Returns film_scenes and book_paragraphs (always corpus-derived), plus
    screen_time_minutes and book_mentions taken from the measured metrics when
    they have a row and from the corpus otherwise. The *_measured booleans say
    which source won, so output can mark the difference instead of hiding it.
    """
    meta = score_record.get("meta", {})
    counts = corpus_counts(score_record["character"])

    screen_time = meta.get("screen_time_minutes", 0) or 0
    book_mentions = meta.get("book_mentions", 0) or 0

    return {
        "film_scenes": counts["film_scenes"],
        "book_paragraphs": counts["book_paragraphs"],
        "screen_time_minutes": screen_time,
        "screen_time_measured": screen_time > 0,
        "book_mentions": book_mentions if book_mentions else counts["book_paragraphs"],
        "book_mentions_measured": book_mentions > 0,
        # Kept so nothing silently loses access to it, but never used as a
        # presence measure - see the module docstring.
        "spoken_words": meta.get("screenplay_words", 0) or 0,
    }
