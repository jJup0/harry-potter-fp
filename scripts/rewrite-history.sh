#!/bin/bash
set -e

# Idempotent script to create a clean 'main' branch from 'dev'
# Safe to re-run - always starts fresh.

REPO_DIR="/home/jake/actual_home/programming/harry-potter-aitor"
cd "$REPO_DIR"

# Paths to strip from every commit's tree
STRIP_PATHS=(
  output/reports/
  output/dashboard.html
  corpus/
  data/parsed/
  data/raw/books_v2/
  data/characters.yaml
  data/metrics/book_mentions.json
  data/metrics/completeness.json
  data/metrics/screen_time.json
  output/scores/scores.json
  output/scores/scores_rule_based.json
  output/scores/scores_kiro.json
  PLAN.md
  debug_ollama.py
  debug_screen_time.py
  debug_xlsx.py
  unload_model.py
  notes.txt
  task-from-aitor.md
  run_scoring.sh
  questions-for-aitor.md
)

# Reset state
git checkout dev
git branch -D main 2>/dev/null || true

# Get ordered commit hashes from dev
mapfile -t COMMITS < <(git log --reverse --format=%H dev)
TOTAL=${#COMMITS[@]}
echo "=== $TOTAL commits on dev ==="

# Define groups: "end_index:message"
SQUASH_GROUPS=(
  "0:initial project structure"
  "2:add source data, pipeline, and scoring infrastructure"
  "5:comparative LLM scorer and initial scoring run"
  "6:score all characters with per-character JSON files"
  "7:remove deprecated scoring backends"
  "8:score remaining characters"
  "12:character deduplication and alias system"
  "13:backfill alias metadata into score files"
  "15:code formatting and cleanup"
  "18:fix character aliases and rescore affected characters"
  "19:reorganize data layout"
  "21:rescore characters with updated corpus"
  "24:interactive dashboard v1.0"
)

# Build clean history on orphan branch
git checkout --orphan main

for group in "${SQUASH_GROUPS[@]}"; do
  END_IDX="${group%%:*}"
  MSG="${group#*:}"
  TARGET_HASH="${COMMITS[$END_IDX]}"

  # Load the full tree from that commit into working tree and index
  git rm -rf --quiet . 2>/dev/null || true
  git checkout "$TARGET_HASH" -- .

  # Remove unwanted paths from the working tree and index
  for p in "${STRIP_PATHS[@]}"; do
    if [[ "$p" == */ ]]; then
      # Directory
      git rm -rf --quiet --ignore-unmatch "$p"
    else
      git rm -f --quiet --ignore-unmatch "$p"
      # Also glob for path-glob patterns
      git ls-files "$p" 2>/dev/null | xargs -r git rm -f --quiet --ignore-unmatch
    fi
  done

  git add -A
  # Only commit if there are changes (or it's the first commit)
  if git diff --cached --quiet 2>/dev/null && [ "$(git rev-list --count HEAD 2>/dev/null)" != "0" ]; then
    echo "  [skip] $MSG (no changes)"
  else
    git commit --allow-empty -m "$MSG"
    echo "  [$((END_IDX+1))/$TOTAL] $MSG"
  fi
done

echo ""
echo "=== Done! ==="
git log --oneline
