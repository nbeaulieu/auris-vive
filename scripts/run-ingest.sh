#!/bin/bash
# scripts/run-ingest.sh
# Run a real audio file through the ingest stage and report the output contract.
# Usage: ./scripts/run-ingest.sh [path/to/audio.wav]
#        defaults to test_audio/clip.wav

set -e
cd "$(dirname "$0")/.."

FILE="${1:-test_audio/clip.wav}"

if [ ! -f "$FILE" ]; then
  echo "✗ file not found: $FILE"
  echo "  run ./scripts/grab-clip.sh first, or pass a path as argument"
  exit 1
fi

source .venv-ml/bin/activate

echo "▸ ingesting: $FILE"
python3 - "$FILE" << 'EOF'
import sys
from src.pipeline.ingest import load

path = sys.argv[1]
audio = load(path)

print(f"  shape:    {audio.shape}")
print(f"  dtype:    {audio.dtype}")
print(f"  duration: {audio.shape[1] / 44100:.2f}s")
print(f"  peak:     {float(abs(audio).max()):.4f}")
print("✓ ingest passed")
EOF
