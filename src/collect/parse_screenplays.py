#!/usr/bin/env python3
"""
Parse screenplays into scenes.

Two transcript formats:
- Fandom wiki: [stage directions] and "Character Name: dialogue"
- Script-o-rama (film 3): plain dialogue blocks, no brackets

Outputs JSON per film in output/parsed/screenplays/
"""

import json
import os
import re
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCREENPLAYS_DIR = os.path.join(PROJECT_ROOT, "data", "source", "screenplays")
CHARACTERS_FILE = os.path.join(PROJECT_ROOT, "output", "characters.yaml")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "screenplays")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_character_aliases():
    """Build set of all known character name variants for detection."""
    with open(CHARACTERS_FILE) as f:
        data = yaml.safe_load(f)
    names = set()
    for c in data["characters"]:
        names.add(c["name"].lower())
        for a in c.get("aliases", []):
            names.add(a.strip().lower())
    return names


def parse_fandom_transcript(text, char_names):
    """Parse fandom wiki format: [directions] and Character: dialogue."""
    scenes = []
    current_scene = {"directions": [], "dialogue": [], "characters": set()}

    # Split into lines
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for stage direction that indicates scene change
        # Heuristic: a long [direction] mentioning a new location
        direction_match = re.match(r"^\[(.+)\]$", line)
        if direction_match:
            direction = direction_match.group(1)
            # Scene break heuristic: direction mentions location change keywords
            is_scene_break = bool(
                re.search(
                    r"\b(we see|we are now|scene changes?|cut to|later|next (?:day|morning|scene)|"
                    r"transition|meanwhile|the next|back (?:at|in|to)|now in|"
                    r"exterior|interior|outside|inside)\b",
                    direction,
                    re.IGNORECASE,
                )
            )

            if is_scene_break and (
                current_scene["dialogue"] or current_scene["directions"]
            ):
                current_scene["characters"] = sorted(current_scene["characters"])
                scenes.append(current_scene)
                current_scene = {"directions": [], "dialogue": [], "characters": set()}

            current_scene["directions"].append(direction)
            # Detect characters mentioned in directions
            for name in char_names:
                if re.search(r"\b" + re.escape(name) + r"\b", direction, re.IGNORECASE):
                    current_scene["characters"].add(name)
            continue

        # Check for dialogue: "Character Name: text"
        dialogue_match = re.match(r"^([A-Z][A-Za-z\.\' ]+?):\s*(.*)$", line)
        if dialogue_match:
            speaker = dialogue_match.group(1).strip()
            text_content = dialogue_match.group(2).strip()
            current_scene["dialogue"].append({"speaker": speaker, "text": text_content})
            current_scene["characters"].add(speaker.lower())
            continue

        # Inline directions within dialogue lines
        if line.startswith("[") or line.endswith("]"):
            current_scene["directions"].append(line.strip("[]"))
        else:
            # Continuation of previous dialogue or narration
            if current_scene["dialogue"]:
                current_scene["dialogue"][-1]["text"] += " " + line

    # Don't forget last scene
    if current_scene["dialogue"] or current_scene["directions"]:
        current_scene["characters"] = sorted(current_scene["characters"])
        scenes.append(current_scene)

    return scenes


def parse_scriptorama_transcript(text, char_names):
    """Parse script-o-rama format: plain text blocks separated by blank lines."""
    scenes = []
    current_scene = {"directions": [], "dialogue": [], "characters": set()}

    # Split into paragraphs (double newline separated)
    paragraphs = re.split(r"\n\s*\n", text)
    line_count = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        line_count += 1

        # Detect characters mentioned
        for name in char_names:
            if re.search(r"\b" + re.escape(name) + r"\b", para, re.IGNORECASE):
                current_scene["characters"].add(name)

        current_scene["dialogue"].append({"speaker": "unknown", "text": para})

        # Scene break every ~30 paragraphs as rough heuristic for this format
        if line_count % 30 == 0 and current_scene["dialogue"]:
            current_scene["characters"] = sorted(current_scene["characters"])
            scenes.append(current_scene)
            current_scene = {"directions": [], "dialogue": [], "characters": set()}

    if current_scene["dialogue"] or current_scene["directions"]:
        current_scene["characters"] = sorted(current_scene["characters"])
        scenes.append(current_scene)

    return scenes


def parse_screenplay(filepath, char_names):
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    fname = os.path.basename(filepath)
    # Film 3 uses script-o-rama format (no brackets, no "Name:" pattern)
    if "3_prisoner" in fname:
        return parse_scriptorama_transcript(text, char_names)
    return parse_fandom_transcript(text, char_names)


def main():
    char_names = load_character_aliases()
    print(f"Loaded {len(char_names)} character name variants")

    for fname in sorted(os.listdir(SCREENPLAYS_DIR)):
        if not fname.endswith(".txt"):
            continue
        filepath = os.path.join(SCREENPLAYS_DIR, fname)
        scenes = parse_screenplay(filepath, char_names)

        # Stats
        total_dialogue = sum(len(s["dialogue"]) for s in scenes)
        total_chars = set()
        for s in scenes:
            total_chars.update(s["characters"])

        print(
            f"{fname}: {len(scenes)} scenes, {total_dialogue} dialogue lines, {len(total_chars)} characters"
        )

        out_name = fname.replace(".txt", ".json")
        with open(os.path.join(OUTPUT_DIR, out_name), "w") as f:
            json.dump(
                {"film": fname.replace(".txt", ""), "scenes": scenes}, f, indent=2
            )

    print(f"\nParsed screenplays saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
