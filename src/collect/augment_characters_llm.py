#!/usr/bin/env python3
"""
LLM-augmented character detection. Takes regex-parsed chapters and asks
the LLM to add missing character attributions (pronouns, nicknames, etc).

Outputs corrections only - minimal LLM output tokens.

Usage:
  python3 src/collect/augment_characters_llm.py [--book 1_philosophers_stone] [--chapter 1]
"""

import json
import os
import re
import subprocess
import sys
import time

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PARSED_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "books")
AUGMENTED_DIR = os.path.join(PROJECT_ROOT, "output", "parsed", "books_augmented")
KIRO_CWD = "/tmp/harry-potter-llm-parse"
os.makedirs(AUGMENTED_DIR, exist_ok=True)
os.makedirs(KIRO_CWD, exist_ok=True)

SYSTEM_PROMPT = """You are augmenting character detection for Harry Potter book paragraphs. You will receive numbered paragraphs with their currently detected characters (from regex matching). Your job is to identify MISSING characters - those referenced by pronoun, nickname, or description but not listed.

Rules:
- Only add characters who are clearly the subject/object of the paragraph (speaking, acting, being described)
- Resolve pronouns from context (e.g. if paragraph 5 mentions "Harry" and paragraph 6 says "He cast a spell", add "Harry Potter" to paragraph 6)
- Resolve nicknames/descriptions ("the boy who lived" = Harry Potter, "the Dark Lord" = Lord Voldemort, "Padfoot" = Sirius Black, "Moony" = Remus Lupin, "Wormtail" = Peter Pettigrew, "Prongs" = James Potter)
- Use canonical full names
- Do NOT remove any existing detections, only ADD missing ones

Output ONLY a JSON object mapping paragraph index to array of characters to ADD:
{"3": ["Harry Potter"], "7": ["Ron Weasley", "Hermione Granger"], "12": ["Albus Dumbledore"]}

If no corrections needed, output: {}
Output ONLY the JSON object, nothing else."""


def augment_chapter(chapter_data, book_tag=""):
    """Send chapter paragraphs to LLM for character augmentation."""
    scenes = chapter_data["scenes"]
    # Build compact representation: index, text snippet, current characters
    lines = []
    for i, s in enumerate(scenes):
        chars = ", ".join(s.get("characters_mentioned", [])) or "(none)"
        lines.append(f"[{i}] [{chars}] {s['text']}")

    user_msg = "\n".join(lines)
    prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{user_msg}"

    print(f"  {book_tag} Sending {len(user_msg):,} chars ({len(scenes)} paras)...", flush=True)
    start = time.time()
    result = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--model", "claude-sonnet-4.6", "--agent", "blank-agent"],
        input=prompt,
        capture_output=True,
        text=True,
        cwd=KIRO_CWD,
    )
    elapsed = time.time() - start

    # Strip ANSI
    output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]*[a-zA-Z]', '', result.stdout).strip()
    print(f"  {book_tag} Response: {len(output)} chars ({elapsed:.1f}s)", flush=True)

    if result.returncode != 0:
        print(f"  {book_tag} STDERR: {result.stderr[:300]}", flush=True)
        return {}

    # Extract JSON object
    json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
    if not json_match:
        # Try multiline
        json_match = re.search(r'\{[\s\S]*\}', output)
    if not json_match:
        print(f"  {book_tag} FAILED: no JSON found", flush=True)
        print(f"  {book_tag} Raw (first 300): {output[:300]}", flush=True)
        return {}

    try:
        corrections = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"  {book_tag} FAILED: JSON parse error: {e}", flush=True)
        print(f"  {book_tag} Match (first 300): {json_match.group()[:300]}", flush=True)
        return {}

    added = sum(len(v) for v in corrections.values())
    print(f"  {book_tag} OK: {len(corrections)} paras corrected, {added} chars added", flush=True)
    return corrections


def main():
    book = "1_philosophers_stone"
    chapter_filter = None
    args = sys.argv[1:]
    while args:
        if args[0] == "--book" and len(args) > 1:
            book = args[1]
            args = args[2:]
        elif args[0] == "--chapter" and len(args) > 1:
            chapter_filter = int(args[1])
            args = args[2:]
        elif args[0] == "--all":
            run_all_books()
            return
        else:
            args = args[1:]

    run_book(book, chapter_filter)


BOOKS = [
    "1_philosophers_stone",
    "2_chamber_of_secrets",
    "3_prisoner_of_azkaban",
    "4_goblet_of_fire",
    "5_order_of_the_phoenix",
    "6_half_blood_prince",
    "7_deathly_hallows",
]


def run_all_books():
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=7) as pool:
        futures = {pool.submit(run_book, book, None): book for book in BOOKS}
        for future in as_completed(futures):
            book = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  ERROR on {book}: {e}", flush=True)


def run_book(book, chapter_filter=None):
    parsed_path = os.path.join(PARSED_DIR, f"{book}.json")
    if not os.path.exists(parsed_path):
        print(f"Not found: {parsed_path}")
        return

    with open(parsed_path) as f:
        data = json.load(f)

    print(f"Augmenting {book} ({len(data['chapters'])} chapters)", flush=True)

    # Load existing progress if any
    out_path = os.path.join(AUGMENTED_DIR, f"{book}.json")
    done_chapters = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        for ch in existing["chapters"]:
            if ch.get("augmented"):
                done_chapters.add(ch["chapter_number"])
                # Copy augmented data into current
                for target_ch in data["chapters"]:
                    if target_ch["chapter_number"] == ch["chapter_number"]:
                        target_ch["scenes"] = ch["scenes"]
                        target_ch["augmented"] = True
        if done_chapters:
            print(f"  Resuming: {len(done_chapters)} chapters already done", flush=True)

    for ch in data["chapters"]:
        ch_num = ch["chapter_number"]
        if chapter_filter and ch_num != chapter_filter:
            continue
        if ch_num in done_chapters:
            continue
        tag = f"[{book}][{ch_num}/{len(data['chapters'])}]"
        print(f"  {tag} {ch['chapter_title']}", flush=True)

        corrections = augment_chapter(ch, tag)

        # Apply corrections
        for idx_str, chars_to_add in corrections.items():
            idx = int(idx_str)
            if 0 <= idx < len(ch["scenes"]):
                existing = set(ch["scenes"][idx].get("characters_mentioned", []))
                existing.update(chars_to_add)
                ch["scenes"][idx]["characters_mentioned"] = sorted(existing)

        ch["augmented"] = True

        # Save after each chapter
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

    print(f"\nSaved: {out_path}", flush=True)


if __name__ == "__main__":
    main()
