"""
Deterministic rule-based scorer.
PLACEHOLDER ONLY - scores based on corpus size (dialogue count, scene count),
which has nothing to do with actual character faithfulness.
Useful only for testing the pipeline end-to-end.
Real FP scoring requires an LLM to read and compare book vs film corpus.
"""
from scorer_base import group_by_source


def score_character(char_name, corpus, config):
    rules = config.get('rules', {})
    per_source = {}

    for source, scenes in group_by_source(corpus['screenplays']).items():
        dialogue_count = sum(len(s.get('dialogue', [])) for s in scenes)
        per_source[source] = {
            'personality': _placeholder(dialogue_count, 50),
            'narrative_role': _placeholder(len(scenes), 10),
            'motivations': _placeholder(dialogue_count, 30),
            'character_arc': _placeholder(len(scenes), 15),
            'meta': {'type': 'screenplay', 'scenes': len(scenes),
                     'dialogue_lines': dialogue_count,
                     'directions': sum(len(s.get('directions', [])) for s in scenes)},
        }

    for source, scenes in group_by_source(corpus['books']).items():
        dialogue_count = sum(1 for s in scenes if s.get('has_dialogue'))
        per_source[source] = {
            'personality': _placeholder(dialogue_count, 50),
            'narrative_role': _placeholder(len(scenes), 100),
            'motivations': _placeholder(dialogue_count, 30),
            'character_arc': _placeholder(len(scenes), 150),
            'meta': {'type': 'book', 'paragraphs': len(scenes),
                     'dialogue_paragraphs': dialogue_count,
                     'total_words': sum(len(s.get('text', '').split()) for s in scenes)},
        }

    return per_source


def _placeholder(value, threshold):
    return round(min(25, (value / max(threshold, 1)) * 25), 1)
