#!/usr/bin/env python3
"""Sanity-check FP scores against web knowledge via kiro-cli with web search."""
import json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCORES_DIR = os.path.join(PROJECT, "output", "scores", "kiro")
RESULTS_DIR = os.path.join(PROJECT, "output", "sanity_checks")
MODEL = "claude-sonnet-4.6"
WORKERS = int(os.environ.get("WORKERS", "5"))


def result_path(char_name):
    safe = re.sub(r"[^a-z0-9_]", "_", char_name.lower()).strip("_")
    return os.path.join(RESULTS_DIR, f"{safe}.json")


def call_kiro(prompt):
    result = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--model", MODEL, "--trust-tools=web_search"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kiro-cli failed: {result.stderr[:200]}")
    return result.stdout


def check_one(score_file):
    with open(score_file) as f:
        data = json.load(f)

    name = data["character"]
    total = data["overall"]["total"]

    # Skip if already checked
    rpath = result_path(name)
    if os.path.exists(rpath):
        with open(rpath) as f:
            return json.load(f)

    if total == 0:
        r = {"character": name, "score": total, "consistency": 10, "reason": "Score is 0 (not in films) - no check needed"}
        with open(rpath, "w") as f:
            json.dump(r, f, indent=2)
        return r

    # Get justification summary
    per_source = data.get("per_source", {})
    just = ""
    for src_data in per_source.values():
        if isinstance(src_data, dict) and "justification" in src_data:
            j = src_data["justification"]
            if isinstance(j, dict):
                for dim, val in j.items():
                    if isinstance(val, dict):
                        just += f"{dim}: {val.get('difference', val.get('penalty_logic', ''))}\n"
                    elif isinstance(val, str):
                        just += f"{dim}: {val}\n"
            break

    prompt = f"""I need you to fact-check this Harry Potter character faithfulness score. Search the web for information about how {name} was portrayed in the Harry Potter films vs books.

Character: {name}
FP Score (faithfulness of film to book): {total}/100
Breakdown: personality={data['overall'].get('personality_voice',0)}/25, narrative_role={data['overall'].get('narrative_role_agency',0)}/25, motivations={data['overall'].get('motivations_internal_conflict',0)}/25, arc={data['overall'].get('character_arc',0)}/25

Key justifications from our scorer:
{just[:1500]}

Based on your web research, rate the CONSISTENCY of this score on a scale of 1-10:
- 10 = score and reasoning perfectly match what fans/critics say about this character's film adaptation
- 5 = score is in the right ballpark but some claims are questionable
- 1 = score is clearly wrong or justifications contain factual errors

Respond with ONLY a JSON object: {{"consistency": <1-10>, "reason": "<brief explanation>"}}"""

    response = call_kiro(prompt)

    # Write raw response
    raw_path = rpath.replace(".json", "_raw.txt")
    with open(raw_path, "w") as f:
        f.write(response)

    # Extract JSON
    match = re.search(r'\{[^{}]*"consistency"[^{}]*\}', response)
    if match:
        r = {"character": name, "score": total, **json.loads(match.group())}
    else:
        r = {"character": name, "score": total, "consistency": -1, "reason": f"Failed to parse: {response[:200]}"}

    with open(rpath, "w") as f:
        json.dump(r, f, indent=2)
    return r


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--characters", nargs="+", help="Specific characters to check")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    files = sorted([
        os.path.join(SCORES_DIR, f)
        for f in os.listdir(SCORES_DIR)
        if f.endswith(".json") and os.path.isfile(os.path.join(SCORES_DIR, f))
    ])

    scored = []
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        if d["overall"]["total"] == 0:
            continue
        if args.characters and d["character"] not in args.characters:
            continue
        scored.append(f)

    print(f"Checking {len(scored)} scored characters with {WORKERS} workers...")
    results = []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(check_one, f): f for f in scored}
        for future in as_completed(futures):
            try:
                r = future.result()
                results.append(r)
                icon = "✓" if r["consistency"] >= 7 else "⚠" if r["consistency"] >= 4 else "✗"
                print(f"  {icon} [{r['consistency']}/10] {r['character']} (FP={r['score']}): {r.get('reason','')[:80]}", flush=True)
            except Exception as e:
                fname = os.path.basename(futures[future])
                print(f"  ✗ ERROR {fname}: {e}", flush=True)
                results.append({"character": fname, "score": -1, "consistency": -1, "reason": str(e)})

    results.sort(key=lambda r: r.get("consistency", -1))

    # Write aggregate
    agg_path = os.path.join(RESULTS_DIR, "_summary.json")
    with open(agg_path, "w") as f:
        json.dump(results, f, indent=2)

    valid = [r for r in results if r["consistency"] > 0]
    avg = sum(r["consistency"] for r in valid) / max(1, len(valid))
    print(f"\nDone. Average consistency: {avg:.1f}/10")
    print(f"Results saved to {RESULTS_DIR}/")
    flagged = [r for r in results if 0 < r["consistency"] < 5]
    if flagged:
        print(f"\nFlagged ({len(flagged)} characters with consistency < 5):")
        for r in flagged:
            print(f"  [{r['consistency']}/10] {r['character']} (FP={r['score']}): {r['reason']}")


if __name__ == "__main__":
    main()
