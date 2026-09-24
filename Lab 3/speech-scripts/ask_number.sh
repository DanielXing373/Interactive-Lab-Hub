#!/usr/bin/env bash
# Ask for a zip code out loud, then record the answer.
# Run from this directory with the Lab 3 virtualenv active:
#   source ../.venv/bin/activate
#   ./ask_number.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOICES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/voices"
OUT="$SCRIPT_DIR/number_answer.wav"
MIC_CARD="$(arecord -l | awk -F'[ :]' '/^card/{print $2; exit}')"

if [[ -z "$MIC_CARD" ]]; then
  echo "No microphone found. Check the connection with: arecord -l"
  exit 1
fi

python3 -m piper \
  --model en_US-lessac-medium \
  --data-dir "$VOICES_DIR" \
  --output-raw \
  -- "What is your zip code? Please say the digits." \
  | aplay -r 22050 -f S16_LE -t raw -

echo "Recording 5 seconds... say the digits now."
arecord -D "plughw:${MIC_CARD},0" -f S16_LE -r 16000 -c 1 -d 5 "$OUT"
echo "Saved to $OUT"

python3 "$SCRIPT_DIR/transcribe.py" "$OUT" --model base.en
