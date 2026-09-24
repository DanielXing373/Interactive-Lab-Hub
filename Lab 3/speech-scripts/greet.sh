#!/usr/bin/env bash
# Greet Daniel with the Piper neural voice.
# Run from this directory with the Lab 3 virtualenv active:
#   source ../.venv/bin/activate
#   ./greet.sh

set -euo pipefail
VOICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"

python3 -m piper \
  --model en_US-lessac-medium \
  --data-dir "$VOICES_DIR" \
  --output-raw \
  -- "Good morning, Daniel. How are you doing today?" \
  | aplay -r 22050 -f S16_LE -t raw -
