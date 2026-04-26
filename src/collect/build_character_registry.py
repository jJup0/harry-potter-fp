#!/usr/bin/env python3
"""
Extract character names from screenplays and books to build a character registry.
Outputs data/characters.yaml
"""
import os
import re
import yaml
from collections import Counter

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "screenplays")
BOOKS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "books")
OUTPUT = os.path.join(PROJECT_ROOT, "data", "characters.yaml")

# Canonical name -> list of aliases that should merge into it
# This also serves as the "full name" registry
KNOWN_CHARACTERS = {
    "Harry Potter": ["Harry", "Potter"],
    "Ron Weasley": ["Ron", "Ronald Weasley", "Ronald"],
    "Hermione Granger": ["Hermione"],
    "Albus Dumbledore": ["Dumbledore", "Professor Dumbledore"],
    "Rubeus Hagrid": ["Hagrid"],
    "Severus Snape": ["Snape", "Professor Snape"],
    "Minerva McGonagall": ["McGonagall", "Professor McGonagall"],
    "Draco Malfoy": ["Draco", "Malfoy"],
    "Lucius Malfoy": ["Lucius"],
    "Narcissa Malfoy": ["Narcissa"],
    "Lord Voldemort": ["Voldemort", "You-Know-Who", "He-Who-Must-Not-Be-Named",
                       "The Dark Lord", "Tom Riddle", "Tom", "Riddle"],
    "Neville Longbottom": ["Neville", "Longbottom"],
    "Augusta Longbottom": ["Mrs. Longbottom", "Mrs Longbottom"],
    "Ginny Weasley": ["Ginny"],
    "Fred Weasley": ["Fred"],
    "George Weasley": ["George"],
    "Arthur Weasley": ["Mr. Weasley", "Mr Weasley", "Arthur"],
    "Molly Weasley": ["Mrs. Weasley", "Mrs Weasley", "Molly"],
    "Percy Weasley": ["Percy"],
    "Bill Weasley": ["Bill"],
    "Charlie Weasley": ["Charlie"],
    "Remus Lupin": ["Lupin", "Professor Lupin", "Remus"],
    "Sirius Black": ["Sirius", "Black"],
    "Dolores Umbridge": ["Umbridge", "Professor Umbridge"],
    "Horace Slughorn": ["Slughorn", "Professor Slughorn"],
    "Cornelius Fudge": ["Fudge", "Cornelius"],
    "Vernon Dursley": ["Vernon", "Uncle Vernon", "Mr. Dursley"],
    "Petunia Dursley": ["Petunia", "Aunt Petunia", "Mrs. Dursley"],
    "Dudley Dursley": ["Dudley"],
    "Bellatrix Lestrange": ["Bellatrix"],
    "Nymphadora Tonks": ["Tonks", "Nymphadora"],
    "Alastor Moody": ["Moody", "Mad-Eye", "Mad-Eye Moody"],
    "Cedric Diggory": ["Cedric", "Diggory"],
    "Cho Chang": ["Cho"],
    "Luna Lovegood": ["Luna", "Lovegood"],
    "Dobby": [],
    "Kreacher": [],
    "Gilderoy Lockhart": ["Lockhart", "Professor Lockhart", "Gilderoy"],
    "Quirinus Quirrell": ["Quirrell", "Professor Quirrell"],
    "Sybill Trelawney": ["Trelawney", "Professor Trelawney"],
    "Pomona Sprout": ["Sprout", "Professor Sprout"],
    "Filius Flitwick": ["Flitwick", "Professor Flitwick"],
    "Rubeus Hagrid": ["Hagrid"],
    "Argus Filch": ["Filch"],
    "Poppy Pomfrey": ["Pomfrey", "Madam Pomfrey"],
    "Rolanda Hooch": ["Hooch", "Madam Hooch"],
    "Peter Pettigrew": ["Pettigrew", "Wormtail", "Peter"],
    "Barty Crouch Sr.": ["Crouch", "Barty Crouch"],
    "Barty Crouch Jr.": [],
    "Rufus Scrimgeour": ["Scrimgeour"],
    "Kingsley Shacklebolt": ["Kingsley", "Shacklebolt"],
    "Seamus Finnigan": ["Seamus", "Finnigan"],
    "Dean Thomas": ["Dean"],
    "Lavender Brown": ["Lavender"],
    "Parvati Patil": ["Parvati"],
    "Padma Patil": ["Padma"],
    "Oliver Wood": ["Oliver", "Wood"],
    "Katie Bell": ["Katie"],
    "Angelina Johnson": ["Angelina"],
    "Lee Jordan": ["Lee"],
    "Colin Creevey": ["Colin", "Creevey"],
    "Dennis Creevey": ["Dennis"],
    "Ernie Macmillan": ["Ernie"],
    "Hannah Abbott": ["Hannah"],
    "Justin Finch-Fletchley": ["Justin"],
    "Susan Bones": ["Susan"],
    "Pansy Parkinson": ["Pansy"],
    "Blaise Zabini": ["Blaise", "Zabini"],
    "Vincent Crabbe": ["Crabbe"],
    "Gregory Goyle": ["Goyle"],
    "Marcus Flint": ["Flint"],
    "Cormac McLaggen": ["McLaggen", "Cormac"],
    "Romilda Vane": ["Romilda"],
    "Fenrir Greyback": ["Greyback", "Fenrir"],
    "Mundungus Fletcher": ["Mundungus"],
    "Aberforth Dumbledore": ["Aberforth"],
    "Gellert Grindelwald": ["Grindelwald"],
    "Rita Skeeter": ["Rita"],
    "Olympe Maxime": ["Maxime", "Madame Maxime"],
    "Igor Karkaroff": ["Karkaroff"],
    "Viktor Krum": ["Krum", "Viktor"],
    "Fleur Delacour": ["Fleur"],
    "Gabrielle Delacour": ["Gabrielle"],
    "Xenophilius Lovegood": ["Xenophilius"],
    "Bathilda Bagshot": ["Bathilda"],
    "Garrick Ollivander": ["Ollivander"],
    "Griphook": [],
    "Firenze": [],
    "Peeves": [],
    "Nearly Headless Nick": ["Nick", "Nearly Headless Nick"],
    "Moaning Myrtle": ["Myrtle"],
    "The Sorting Hat": ["Sorting Hat"],
    "The Fat Lady": ["Fat Lady"],
    "Hedwig": [],
    "Fawkes": [],
    "Buckbeak": [],
    "Nagini": [],
    "Norbert": ["Norberta"],
    "Aragog": [],
    "Scabbers": [],
    "Crookshanks": [],
    "Pigwidgeon": [],
    "Errol": [],
}


def extract_screenplay_speakers():
    speakers = Counter()
    pattern = re.compile(r'^([A-Z][A-Za-z\.\' ]+?):\s', re.MULTILINE)
    for fname in sorted(os.listdir(SCREENPLAYS_DIR)):
        if not fname.endswith('.txt'):
            continue
        with open(os.path.join(SCREENPLAYS_DIR, fname), encoding='utf-8') as f:
            text = f.read()
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if len(name) < 2 or len(name) > 40:
                continue
            if name.lower() in ('note', 'cut to', 'ext', 'int', 'scene', 'fade',
                                'continued', 'the end', 'title', 'subtitle'):
                continue
            speakers[name] += 1
    return speakers


def extract_book_dialogue_speakers():
    speakers = Counter()
    pattern = re.compile(
        r'(?:said|asked|whispered|shouted|yelled|muttered|called|cried|screamed|'
        r'snapped|snarled|growled|replied|answered|exclaimed|demanded|roared|'
        r'squealed|gasped|stammered|bellowed|hissed|moaned|groaned|sobbed|'
        r'sighed|laughed|chuckled|giggled|sneered|barked|spat|wailed|whimpered)'
        r'\s+((?:(?:Mr|Mrs|Ms|Professor|Sir|Lord|Lady|Madam|Madame|Uncle|Aunt)\.?\s+)?'
        r'[A-Z][a-z]+(?:[A-Z][a-z]+)*(?:\s[A-Z][a-z]+(?:[A-Z][a-z]+)*)?)',
        re.MULTILINE
    )
    for fname in sorted(os.listdir(BOOKS_DIR)):
        if not fname.endswith('.txt'):
            continue
        with open(os.path.join(BOOKS_DIR, fname), encoding='utf-8') as f:
            text = f.read()
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if len(name) < 2:
                continue
            speakers[name] += 1
    return speakers


def build_alias_to_canonical():
    """Build reverse map: alias -> canonical name."""
    alias_map = {}
    for canonical, aliases in KNOWN_CHARACTERS.items():
        alias_map[canonical] = canonical
        alias_map[canonical.lower()] = canonical
        for alias in aliases:
            alias_map[alias] = canonical
            alias_map[alias.lower()] = canonical
    return alias_map


def resolve_name(name, alias_map):
    """Try to resolve a name to its canonical form."""
    # Try exact match first (handles "Mrs. Longbottom" -> Augusta)
    if name in alias_map:
        return alias_map[name]
    if name.lower() in alias_map:
        return alias_map[name.lower()]
    # Try stripping title only if no exact match
    stripped = re.sub(r'^(Professor|Mr\.?|Mrs\.?|Ms\.?|Sir|Lord|Lady|Madam|Madame|Uncle|Aunt)\s+', '', name).strip()
    if stripped != name:
        if stripped in alias_map:
            return alias_map[stripped]
        if stripped.lower() in alias_map:
            return alias_map[stripped.lower()]
    return name  # fallback: keep original


def build_registry():
    print("Extracting screenplay speakers...")
    screenplay_speakers = extract_screenplay_speakers()
    print(f"  Found {len(screenplay_speakers)} unique speaker names")

    print("Extracting book dialogue speakers...")
    book_speakers = extract_book_dialogue_speakers()
    print(f"  Found {len(book_speakers)} unique speaker names")

    alias_map = build_alias_to_canonical()

    # Merge into canonical names
    characters = {}

    def ensure_entry(canonical):
        if canonical not in characters:
            characters[canonical] = {'aliases': set(), 'screenplay_lines': 0, 'book_attributions': 0}

    for name, count in screenplay_speakers.most_common():
        canonical = resolve_name(name, alias_map)
        ensure_entry(canonical)
        characters[canonical]['aliases'].add(name)
        characters[canonical]['screenplay_lines'] += count

    for name, count in book_speakers.most_common():
        canonical = resolve_name(name, alias_map)
        ensure_entry(canonical)
        characters[canonical]['aliases'].add(name)
        characters[canonical]['book_attributions'] += count

    # Build output
    output = []
    for name, data in sorted(characters.items(),
                              key=lambda x: x[1]['screenplay_lines'] + x[1]['book_attributions'],
                              reverse=True):
        total = data['screenplay_lines'] + data['book_attributions']
        if total < 2:
            continue
        # Clean aliases: remove canonical name itself, sort
        aliases = sorted(a for a in data['aliases'] if a != name)
        entry = {'name': name}
        if aliases:
            entry['aliases'] = aliases
        entry['screenplay_lines'] = data['screenplay_lines']
        entry['book_attributions'] = data['book_attributions']
        output.append(entry)

    print(f"\nTotal characters (>=2 mentions): {len(output)}")
    print("Top 20:")
    for c in output[:20]:
        aliases_str = f" (aka {', '.join(c.get('aliases', [])[:3])})" if c.get('aliases') else ""
        print(f"  {c['name']}{aliases_str}: {c['screenplay_lines']} screenplay, {c['book_attributions']} book")

    with open(OUTPUT, 'w') as f:
        yaml.dump({'characters': output}, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\nSaved to {OUTPUT}")


if __name__ == '__main__':
    build_registry()
