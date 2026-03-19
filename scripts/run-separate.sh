#!/bin/bash
# scripts/run-separate.sh
# Run a real audio file through ingest + separation and report per-stem output.
# Usage: ./scripts/run-separate.sh [path/to/audio.wav]
#        defaults to test_audio/clip.wav
#
# Device is selected via AURIS_DEVICE env var (auto | cpu | mps | cuda).
# Defaults to mps on Apple Silicon, cuda in production, cpu as fallback.
# First run downloads model weights (~400MB) — subsequent runs use cache.

set -e
cd "$(dirname "$0")/.."

FILE="${1:-test_audio/clip.wav}"

if [ ! -f "$FILE" ]; then
  echo "✗ file not found: $FILE"
  echo "  run ./scripts/grab-clip.sh first, or pass a path as argument"
  exit 1
fi

source .venv-ml/bin/activate

echo "▸ device: ${AURIS_DEVICE:-auto}"
echo "▸ file:   $FILE"
echo ""

AURIS_DEVICE="${AURIS_DEVICE:-auto}" python3 - "$FILE" << 'EOF'
import sys
import time
from src.pipeline.ingest import load
from src.pipeline.separate import separate, select_device

path = sys.argv[1]

print("▸ ingesting...")
audio = load(path)
print(f"  {audio.shape}  {audio.dtype}  {audio.shape[1]/44100:.1f}s")

print("▸ selecting device...")
device = select_device()
print(f"  {device}")

print("▸ separating (first run downloads weights ~400MB, please wait)...")
start = time.time()

def on_ready(stems):
    elapsed = time.time() - start
    print(f"  [{elapsed:.1f}s] stems ready: {list(stems.keys())}")

stems = separate(audio, device=device, on_stems_ready=on_ready)
elapsed = time.time() - start

print(f"\n✓ separation complete in {elapsed:.1f}s")
print(f"{'stem':10s}  {'shape':18s}  {'peak':>8s}")
print("-" * 42)
for name, stem in stems.items():
    peak = float(abs(stem).max())
    print(f"{name:10s}  {str(stem.shape):18s}  {peak:8.4f}")
EOF
