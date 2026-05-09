"""
Scorer interface. All scorers implement score_character():

    def score_character(char_name, corpus, config) -> dict:
        Returns {source_name: {personality, narrative_role, motivations, character_arc, meta}, ...}

Each dimension is scored 0-25. meta contains backend-specific info.
"""

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]


def group_by_source(scenes):
    groups = {}
    for s in scenes:
        src = s.get('source', 'unknown')
        groups.setdefault(src, []).append(s)
    return groups


def fallback_scores(source_type, scene_count):
    return {
        'personality': 0, 'narrative_role': 0, 'motivations': 0, 'character_arc': 0,
        'meta': {'type': source_type,
                 'scenes': scene_count if source_type == 'screenplay' else 0,
                 'paragraphs': scene_count if source_type == 'book' else 0,
                 'error': True}
    }
