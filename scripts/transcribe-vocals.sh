#!/bin/bash
# scripts/transcribe-vocals.sh
# Run Whisper on the vocal stem for a song, producing timestamped transcript JSON.
# Usage: ./scripts/transcribe-vocals.sh <slug>
# Requires: pip install openai-whisper (in .venv-ml)
# Output: test_audio/<slug>/transcript.json

set -e
cd "$(dirname "$0")/.."

SLUG="${1:?usage: transcribe-vocals.sh <slug>}"
VOCALS_PATH="test_audio/$SLUG/stems/vocals.flac"

if [ ! -f "$VOCALS_PATH" ]; then
  echo "✗ vocals not found: $VOCALS_PATH — run stems first"
  exit 1
fi

source .venv-ml/bin/activate

echo "▸ transcribing vocals for $SLUG..."

python3 - "$SLUG" "$VOCALS_PATH" << 'EOF'
import sys
import json
from pathlib import Path

import whisper

slug = sys.argv[1]
vocals_path = sys.argv[2]

model = whisper.load_model("base")
result = model.transcribe(vocals_path, word_timestamps=True)

words = []
for segment in result["segments"]:
    for word in segment.get("words", []):
        words.append({
            "word":  word["word"].strip(),
            "start": round(word["start"], 3),
            "end":   round(word["end"], 3),
        })

output = {"slug": slug, "language": result["language"], "words": words}
out_path = Path(f"test_audio/{slug}/transcript.json")
out_path.write_text(json.dumps(output, indent=2))
print(f"✓ {len(words)} words → {out_path}")
EOF
