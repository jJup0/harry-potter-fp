#!/bin/bash
set -euo pipefail

DEST="$(cd "$(dirname "$0")/../.." && pwd)/data/raw/books"
mkdir -p "$DEST"

BASE="https://raw.githubusercontent.com/bobdeng/owlreader/master/ERead/assets/books"

KEYS=(
  "1_philosophers_stone"
  "2_chamber_of_secrets"
  "3_prisoner_of_azkaban"
  "4_goblet_of_fire"
  "5_order_of_the_phoenix"
  "6_half_blood_prince"
  "7_deathly_hallows"
)
URLS=(
  "Harry%20Potter%20and%20the%20Sorcerer's%20Stone.txt"
  "Harry%20Potter%20and%20the%20Chamber%20of%20Secrets.txt"
  "Harry%20Potter%20and%20the%20Prisoner%20of%20Azkaban%20.txt"
  "Harry%20Potter%20and%20the%20Goblet%20of%20Fire.txt"
  "Harry%20Potter%20and%20the%20Order%20of%20the%20Phoenix.txt"
  "Harry%20Potter%20and%20The%20Half-Blood%20Prince.txt"
  "Harry%20Potter%20and%20the%20Deathly%20Hallows%20.txt"
)

for i in "${!KEYS[@]}"; do
  key="${KEYS[$i]}"
  url="${BASE}/${URLS[$i]}"
  dest_file="${DEST}/${key}.txt"
  if [ -f "$dest_file" ]; then
    echo "SKIP $key (already exists)"
  else
    echo "Downloading $key..."
    curl -sL "$url" -o "$dest_file"
    echo "  -> $(wc -c < "$dest_file") bytes"
  fi
done

echo "Done. Books in $DEST:"
ls -la "$DEST"
