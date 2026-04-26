#!/usr/bin/env python3
"""
Estimate screen time (words spoken per character per film) and
book presence (name mentions per character per book).
Outputs data/metrics/screen_time.json and data/metrics/book_mentions.json
"""
import json
import os
import re
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PARSED_SCREENPLAYS = os.path.join(PROJECT_ROOT, "data", "parsed", "screenplays")
PARSED_BOOKS = os.path.join(PROJECT_ROOT, "data", "parsed", "books")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "data", "characters.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "metrics")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BLOCKLIST = {'you', 'all', 'voice', 'hogwarts', 'weasley', 'ominous voice',
             'elevator voice', 'man', 'woman', 'boy', 'girl', 'student',
             'students', 'crowd', 'everyone', 'someone', 'wizard'}


def load_alias_map():
    with open(CHARACTERS_FILE) as f:
        data = yaml.safe_load(f)
    alias_map = {}
    for c in data['characters']:
        canonical = c['name']
        if canonical.lower() in BLOCKLIST:
            continue
        alias_map[canonical.lower()] = canonical
        for a in c.get('aliases', []):
            clean = a.strip().replace('\n', ' ').lower()
            if len(clean) >= 3 and clean not in BLOCKLIST:
                alias_map[clean] = canonical
    return alias_map


def compute_screen_time(alias_map):
    """Count words spoken per character per film."""
    # {canonical_name: {film: word_count}}
    screen_time = {}

    for fname in sorted(os.listdir(PARSED_SCREENPLAYS)):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(PARSED_SCREENPLAYS, fname)) as f:
            data = json.load(f)

        film = data['film']
        for scene in data['scenes']:
            for d in scene.get('dialogue', []):
                speaker = d['speaker'].strip().lower()
                canonical = alias_map.get(speaker)
                if not canonical:
                    # Try stripping title
                    stripped = re.sub(r'^(professor|mr\.?|mrs\.?|uncle|aunt)\s+', '', speaker).strip()
                    canonical = alias_map.get(stripped)
                if not canonical:
                    continue

                words = len(d.get('text', '').split())
                if canonical not in screen_time:
                    screen_time[canonical] = {}
                screen_time[canonical][film] = screen_time[canonical].get(film, 0) + words

    # Add totals
    for char, films in screen_time.items():
        films['_total'] = sum(v for k, v in films.items() if k != '_total')

    return screen_time


def compute_book_mentions(alias_map):
    """Count name mentions per character per book."""
    # Collect all names to search for, grouped by canonical
    canonical_to_names = {}
    for alias, canonical in alias_map.items():
        if canonical not in canonical_to_names:
            canonical_to_names[canonical] = set()
        canonical_to_names[canonical].add(alias)

    mentions = {}

    for fname in sorted(os.listdir(PARSED_BOOKS)):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(PARSED_BOOKS, fname)) as f:
            data = json.load(f)

        book = data['book']

        # Reconstruct full book text for counting
        full_text = ''
        for chapter in data['chapters']:
            for scene in chapter['scenes']:
                full_text += scene['text'] + '\n'

        full_lower = full_text.lower()

        for canonical, names in canonical_to_names.items():
            count = 0
            for name in names:
                if len(name) < 3:
                    continue
                count += len(re.findall(r'\b' + re.escape(name) + r'\b', full_lower))
            if count > 0:
                if canonical not in mentions:
                    mentions[canonical] = {}
                mentions[canonical][book] = count

    # Add totals
    for char, books in mentions.items():
        books['_total'] = sum(v for k, v in books.items() if k != '_total')

    return mentions


def main():
    alias_map = load_alias_map()
    print(f"Loaded {len(alias_map)} aliases")

    print("Computing screen time (words spoken per film)...")
    screen_time = compute_screen_time(alias_map)
    # Sort by total
    screen_time = dict(sorted(screen_time.items(), key=lambda x: x[1].get('_total', 0), reverse=True))
    with open(os.path.join(OUTPUT_DIR, 'screen_time.json'), 'w') as f:
        json.dump(screen_time, f, indent=2)
    print(f"  {len(screen_time)} characters with dialogue")
    print("  Top 10:")
    for name, films in list(screen_time.items())[:10]:
        print(f"    {name}: {films['_total']} words across {len(films)-1} films")

    print("\nComputing book mentions...")
    mentions = compute_book_mentions(alias_map)
    mentions = dict(sorted(mentions.items(), key=lambda x: x[1].get('_total', 0), reverse=True))
    with open(os.path.join(OUTPUT_DIR, 'book_mentions.json'), 'w') as f:
        json.dump(mentions, f, indent=2)
    print(f"  {len(mentions)} characters mentioned")
    print("  Top 10:")
    for name, books in list(mentions.items())[:10]:
        print(f"    {name}: {books['_total']} mentions across {len(books)-1} books")

    print(f"\nMetrics saved to {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
