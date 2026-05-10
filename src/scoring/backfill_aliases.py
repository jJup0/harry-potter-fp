#!/usr/bin/env python3
"""
Backfill existing score cache files with the aliases that were active
when they were originally scored (pre-dedup commit aliases).

This ensures the cache invalidation logic works correctly: scores that
were generated with the old alias set won't be needlessly re-scored.
"""

import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCORE_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "comparative")

# These are the aliases as they existed BEFORE the dedup commit (HEAD~1).
# Used to backfill the cache so existing scores are recognized as valid
# for their original alias set.
PRE_DEDUP_ALIASES = {
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
    "Lord Voldemort": [
        "Voldemort",
        "You-Know-Who",
        "He-Who-Must-Not-Be-Named",
        "The Dark Lord",
        "Tom Riddle",
        "Tom",
        "Riddle",
    ],
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


def get_pre_dedup_aliases(char_name):
    """Get the pre-dedup alias list for a character."""
    for canonical, aliases in PRE_DEDUP_ALIASES.items():
        if canonical == char_name:
            return sorted(aliases)
    return []


def main():
    if not os.path.isdir(SCORE_DIR):
        print("No score directory found.")
        return

    updated = 0
    skipped = 0
    for fname in sorted(os.listdir(SCORE_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(SCORE_DIR, fname)
        with open(fpath) as f:
            data = json.load(f)

        meta = data.get("per_source", {}).get("comparative", {}).get("meta", {})
        if "aliases" in meta:
            skipped += 1
            continue

        char_name = data.get("character", "")
        aliases = get_pre_dedup_aliases(char_name)
        meta["aliases"] = aliases
        data["per_source"]["comparative"]["meta"] = meta

        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)
        updated += 1

    print(
        f"Backfilled {updated} score files with pre-dedup aliases ({skipped} already had aliases)"
    )


if __name__ == "__main__":
    main()
