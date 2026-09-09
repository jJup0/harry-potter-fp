#!/usr/bin/env python3
"""
Attach canonical character names to each reported deleted scene.

Aitor's CSV names the scene but not who is in it, and the prompt injection needs to
be narrow: a character should only be told to ignore scenes they could plausibly
appear in. This pass asks the LLM to name the characters in each scene, then resolves
those names through the registry's alias map and drops anything unknown.

Fully resumable - one JSON file per scene rank in output/deleted_scene_characters/,
written as each call returns. Re-run to fill in whatever is missing.

Usage:
  python3 -u src/collect/tag_deleted_scene_characters.py [--ranks 1,2,3] [--merge]

  --merge      after tagging, write the characters back into
               data/deleted_scenes_reported.jsonc
  --reresolve  re-resolve names previously dropped as unknown, no LLM calls.
               Use after changing _resolve rather than re-running the whole pass.
"""

import argparse
import glob
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from paths import (
    CHARACTERS_FILE,
    DELETED_SCENES_REPORTED_FILE,
    DELETED_SCENE_CHARACTERS_DIR,
    KIRO_DELETED_SCENE_CWD,
    PROJECT_ROOT,
)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from llm import call_kiro, extract_json
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "collect"))
from build_character_registry import build_alias_to_canonical, resolve_name

import yaml

KIRO_CWD = str(KIRO_DELETED_SCENE_CWD)
os.makedirs(KIRO_CWD, exist_ok=True)

REPORTED_PATH = DELETED_SCENES_REPORTED_FILE
REGISTRY_PATH = CHARACTERS_FILE
OUT_DIR = DELETED_SCENE_CHARACTERS_DIR

PROMPT = """You are identifying which Harry Potter characters appear in a scene that was \
deleted from the theatrical cut of the films.

SCENE
  Film: {film_name}
  Title: {title}
  Description: {description}

TASK
List every character who appears in, speaks in, or is directly involved in this scene.
Include characters who are the subject of the scene even if they only react.

RULES
- Use full canonical names as they appear in the books ("Rubeus Hagrid", not "Hagrid").
- Do not include characters who are merely mentioned in dialogue without being present.
- Be conservative: if you are unsure whether a character is in this specific scene, leave
  them out. A missing name is better than a wrong one, because this list is used to
  suppress material from that character's score.

Respond with ONLY a JSON object:
{{"rank": {rank}, "characters": ["Exact Name", ...], "reasoning": "one sentence"}}
"""

FILM_NAMES = {
    "1_philosophers_stone": "Harry Potter and the Philosopher's Stone",
    "2_chamber_of_secrets": "Harry Potter and the Chamber of Secrets",
    "3_prisoner_of_azkaban": "Harry Potter and the Prisoner of Azkaban",
    "4_goblet_of_fire": "Harry Potter and the Goblet of Fire",
    "5_order_of_the_phoenix": "Harry Potter and the Order of the Phoenix",
    "6_half_blood_prince": "Harry Potter and the Half-Blood Prince",
    "7_deathly_hallows_p1": "Harry Potter and the Deathly Hallows: Part 1",
    "8_deathly_hallows_p2": "Harry Potter and the Deathly Hallows: Part 2",
}


def load_reported():
    with open(REPORTED_PATH) as f:
        text = re.sub(r"//[^\n]*", "", f.read())
    return json.loads(text)["entries"]


def load_registry_names():
    with open(REGISTRY_PATH) as f:
        return [c["name"] for c in yaml.safe_load(f)["characters"]]


def _resolve(raw, allowed, alias_map):
    """Resolve one free-form name to a registry name, or None if unknown.

    The alias map does not carry full formal names, so the model naming Harry
    "Harry James Potter" resolved to nothing and silently dropped him from the scene.
    Falling back to first + last name recovers those without touching the global alias
    list, which would invalidate cached scores for every affected character.
    """
    canonical = resolve_name(raw, alias_map)
    if canonical in allowed:
        return canonical
    raw = re.sub(r"\bSenior\b", "Sr.", raw)
    raw = re.sub(r"\bJunior\b", "Jr.", raw)
    canonical = resolve_name(raw, alias_map)
    if canonical in allowed:
        return canonical
    parts = raw.split()
    if len(parts) > 2:
        short = f"{parts[0]} {parts[-1]}"
        canonical = resolve_name(short, alias_map)
        if canonical in allowed:
            return canonical
        # "Bartemius Crouch Senior" -> "Bartemius Crouch"
        canonical = resolve_name(" ".join(parts[:-1]), alias_map)
        if canonical in allowed:
            return canonical
    return None


def tag_one(entry, names, model):
    out_path = os.path.join(OUT_DIR, f"{entry['rank']:03d}.json")
    if os.path.exists(out_path):
        print(f"  [cached] rank {entry['rank']}: {entry['title']}", flush=True)
        with open(out_path) as f:
            return json.load(f)

    prompt = PROMPT.format(
        film_name=FILM_NAMES.get(entry["film"], entry["film"]),
        title=entry["title"],
        description=entry["description"],
        rank=entry["rank"],
    )
    print(f"  [start] rank {entry['rank']}: {entry['title']}", flush=True)
    response = call_kiro(prompt, model=model, cwd=KIRO_CWD)
    parsed = extract_json(response)
    if parsed is None:
        print(f"  [FAIL] rank {entry['rank']}: could not parse response", flush=True)
        return None

    # Resolve free-form names through the registry's alias map, then keep only
    # names that actually exist in the registry - anything else cannot be scored.
    allowed, alias_map = names
    matched, dropped = [], []
    for raw in parsed.get("characters", []):
        canonical = _resolve(raw, allowed, alias_map)
        if canonical is None:
            dropped.append(raw)
        elif canonical not in matched:
            matched.append(canonical)
    result = {
        "rank": entry["rank"],
        "title": entry["title"],
        "film": entry["film"],
        "characters": matched,
        "dropped_unknown": dropped,
        "reasoning": parsed.get("reasoning", ""),
        "model": model,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(
        f"  [done] rank {entry['rank']}: {len(matched)} characters"
        + (f" ({len(dropped)} unknown dropped)" if dropped else ""),
        flush=True,
    )
    return result


def reresolve_cached(names):
    """Re-run name resolution over cached results, no LLM calls.

    Use after changing _resolve: names previously binned as unknown get another pass,
    so a resolver fix does not mean paying for the whole tagging run again.
    """
    allowed, alias_map = names
    recovered = 0
    for path in sorted(glob.glob(os.path.join(OUT_DIR, "*.json"))):
        with open(path) as f:
            data = json.load(f)
        still_dropped = []
        for raw in data.get("dropped_unknown", []):
            canonical = _resolve(raw, allowed, alias_map)
            if canonical is None:
                still_dropped.append(raw)
            elif canonical not in data["characters"]:
                data["characters"].append(canonical)
                print(f"  rank {data['rank']}: recovered {raw!r} -> {canonical}")
                recovered += 1
        data["dropped_unknown"] = still_dropped
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    print(f"Recovered {recovered} character tags from previously dropped names")


def merge_into_reported():
    """Write tagged characters back into data/deleted_scenes_reported.jsonc."""
    with open(REPORTED_PATH) as f:
        raw = f.read()
    header = "".join(line for line in raw.splitlines(True) if line.startswith("//"))
    entries = json.loads(re.sub(r"//[^\n]*", "", raw))["entries"]

    tagged = 0
    for entry in entries:
        path = os.path.join(OUT_DIR, f"{entry['rank']:03d}.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            entry["characters"] = json.load(f)["characters"]
        tagged += 1

    with open(REPORTED_PATH, "w") as f:
        f.write(header)
        json.dump({"entries": entries}, f, indent=2)
        f.write("\n")
    print(f"Merged characters into {tagged}/{len(entries)} entries")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranks", help="comma-separated ranks to tag")
    ap.add_argument("--model", default="claude-sonnet-4.6")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--merge", action="store_true", help="merge results into the jsonc")
    ap.add_argument("--reresolve", action="store_true",
                    help="re-resolve cached dropped names after a resolver fix, no LLM calls")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    entries = load_reported()
    if args.ranks:
        wanted = {int(r) for r in args.ranks.split(",")}
        entries = [e for e in entries if e["rank"] in wanted]
    names = (set(load_registry_names()), build_alias_to_canonical())

    if args.reresolve:
        reresolve_cached(names)
        if args.merge:
            merge_into_reported()
        return 0

    print(f"Tagging {len(entries)} scenes against {len(names[0])} registry names")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(tag_one, e, names, args.model): e for e in entries}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"  [ERROR] rank {futures[future]['rank']}: {exc}", flush=True)

    if args.merge:
        merge_into_reported()
    return 0


if __name__ == "__main__":
    sys.exit(main())
