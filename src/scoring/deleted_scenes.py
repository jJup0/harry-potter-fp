"""
Deleted-scene exclusion logic. Two mechanisms, because our sources differ in quality.

1. data/deleted_scenes.jsonc - scenes pinned to an exact (film, scene_index) in the
   parsed corpus. Removed from the corpus outright before scoring.
   - load_deleted_scenes(): returns the parsed exclusion list
   - filter_deleted_scenes(scenes, character): returns (included, excluded) scene lists
   - tag_deleted_scenes(scenes, character): returns scenes with 'deleted' field added

2. data/deleted_scenes_reported.jsonc - scenes Aitor reported by title and film, with no
   index. Injected into the scoring prompt as "ignore this material" instructions.
   Scene segmentation is too coarse in some films to cut these safely: Chamber of Secrets
   parses as 8 blocks averaging 2400 words, so dropping the block containing Lockhart's
   deleted quiz would also drop most of his theatrical material.
   - load_reported_scenes(): returns the parsed reported list
   - reported_scenes_for(character, films): entries relevant to one character
   - deleted_scenes_prompt_block(character, films): formatted prompt section, or ""
"""

import json
import os
import re

_DELETED_SCENES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "deleted_scenes.jsonc"
)
_REPORTED_SCENES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "deleted_scenes_reported.jsonc"
)

FILM_TITLES = {
    "1_philosophers_stone": "Philosopher's Stone",
    "2_chamber_of_secrets": "Chamber of Secrets",
    "3_prisoner_of_azkaban": "Prisoner of Azkaban",
    "4_goblet_of_fire": "Goblet of Fire",
    "5_order_of_the_phoenix": "Order of the Phoenix",
    "6_half_blood_prince": "Half-Blood Prince",
    "7_deathly_hallows_p1": "Deathly Hallows Part 1",
    "8_deathly_hallows_p2": "Deathly Hallows Part 2",
}

_cache = None
_reported_cache = None


def load_deleted_scenes(path=None):
    """Load and parse the deleted_scenes.jsonc file. Strips comments."""
    global _cache
    if _cache is not None and path is None:
        return _cache

    fpath = path or _DELETED_SCENES_PATH
    with open(fpath) as f:
        text = f.read()
    # Strip single-line comments (// ...)
    text = re.sub(r"//[^\n]*", "", text)
    data = json.loads(text)
    entries = data.get("entries", [])

    # Build lookup: (film, scene_index) -> list of entries
    lookup = {}
    for entry in entries:
        key = (entry["film"], entry["scene_index"])
        lookup.setdefault(key, []).append(entry)

    result = {"entries": entries, "lookup": lookup}
    if path is None:
        _cache = result
    return result


def is_scene_deleted(scene, character, deleted_data=None):
    """Check if a scene should be excluded for a given character."""
    if deleted_data is None:
        deleted_data = load_deleted_scenes()
    lookup = deleted_data["lookup"]
    key = (scene.get("source"), scene.get("scene_index"))
    entries = lookup.get(key, [])
    for entry in entries:
        if character in entry["characters"]:
            return True
    return False


def filter_deleted_scenes(scenes, character, deleted_data=None):
    """Split scenes into (included, excluded) for a character.

    Returns:
        tuple: (included_scenes, excluded_scenes)
    """
    if deleted_data is None:
        deleted_data = load_deleted_scenes()
    included = []
    excluded = []
    for scene in scenes:
        if is_scene_deleted(scene, character, deleted_data):
            excluded.append(scene)
        else:
            included.append(scene)
    return included, excluded


def tag_deleted_scenes(scenes, character, deleted_data=None):
    """Return scenes with a 'deleted' boolean field added (non-mutating)."""
    if deleted_data is None:
        deleted_data = load_deleted_scenes()
    result = []
    for scene in scenes:
        tagged = dict(scene)
        tagged["deleted"] = is_scene_deleted(scene, character, deleted_data)
        result.append(tagged)
    return result


# --- Reported (index-less) deleted scenes: prompt injection -------------------


def load_reported_scenes(path=None):
    """Load and parse data/deleted_scenes_reported.jsonc. Strips comments."""
    global _reported_cache
    if _reported_cache is not None and path is None:
        return _reported_cache

    fpath = path or _REPORTED_SCENES_PATH
    if not os.path.exists(fpath):
        return {"entries": [], "by_character": {}}
    with open(fpath) as f:
        text = re.sub(r"//[^\n]*", "", f.read())
    entries = json.loads(text).get("entries", [])

    by_character = {}
    for entry in entries:
        for name in entry.get("characters", []):
            by_character.setdefault(name, []).append(entry)

    result = {"entries": entries, "by_character": by_character}
    if path is None:
        _reported_cache = result
    return result


def reported_scenes_for(character, films=None, reported_data=None):
    """Reported deleted scenes relevant to one character.

    Args:
        character: canonical character name
        films: optional iterable of film source keys (e.g. {"6_half_blood_prince"}).
               When given, only scenes from those films are returned, so a character
               is never told about material outside the corpus they were sent.
    """
    if reported_data is None:
        reported_data = load_reported_scenes()
    entries = reported_data["by_character"].get(character, [])
    if films is not None:
        films = set(films)
        entries = [e for e in entries if e["film"] in films]
    return sorted(entries, key=lambda e: -e["rank"])


def films_in_corpus(scenes):
    """Film source keys present in a list of corpus scenes."""
    return {s.get("source") for s in scenes if s.get("source")}


_BLOCK_HEADER = """## NON-THEATRICAL MATERIAL - EXCLUDE FROM SCORING

The FILM CORPUS above is built from screenplay sources, and screenplays contain scenes that
never reached the screen. The following scenes involving {character} were cut from the
theatrical release. Where this material appears in the FILM CORPUS, treat it as absent from
the film:

{items}

Do not credit the film with any characterisation that rests only on these scenes, and do not
cite them as film evidence. Where a book beat survives only in one of these scenes, it counts
as material lost in adaptation.
"""


def deleted_scenes_prompt_block(character, films=None, reported_data=None):
    """Prompt section listing non-theatrical scenes for a character, or "" if none."""
    entries = reported_scenes_for(character, films, reported_data)
    if not entries:
        return ""
    items = "\n".join(
        f"- [{FILM_TITLES.get(e['film'], e['film'])}] \"{e['title']}\" - {e['description']}"
        for e in entries
    )
    return _BLOCK_HEADER.format(character=character, items=items)
