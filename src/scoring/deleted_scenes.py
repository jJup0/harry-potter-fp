"""
Deleted-scene exclusion logic.

Loads data/deleted_scenes.jsonc and provides:
- load_deleted_scenes(): returns the parsed exclusion list
- filter_deleted_scenes(scenes, character): returns (included, excluded) scene lists
- tag_deleted_scenes(scenes, character): returns scenes with 'deleted' field added
"""

import json
import os
import re

_DELETED_SCENES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "deleted_scenes.jsonc"
)

_cache = None


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
