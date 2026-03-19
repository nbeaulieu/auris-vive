#!/bin/bash
# scripts/run-stems.sh
# Run a file through ingest + separation and write each stem as a FLAC file.
# Usage: ./scripts/run-stems.sh <path/to/clip.wav> [output_name]
#
# Examples:
#   ./scripts/run-stems.sh test_audio/tswift/clip.wav tswift
#   ./scripts/run-stems.sh test_audio/piano-man/clip.wav piano-man
#
# Output:
#   test_audio/<name>/stems/{drums,bass,vocals,other,piano,guitar}.flac
#   test_audio/<name>/report.txt

set -e
cd "$(dirname "$0")/.."

FILE="${1:?usage: run-stems.sh <path/to/clip.wav> [output_name]}"
NAME="${2:-$(basename $(dirname "$FILE"))}"

if [ ! -f "$FILE" ]; then
  echo "✗ file not found: $FILE"
  exit 1
fi

source .venv-ml/bin/activate

echo "▸ device: ${AURIS_DEVICE:-auto}"
echo "▸ file:   $FILE"
echo "▸ output: test_audio/$NAME/stems/"
echo ""

AURIS_DEVICE="${AURIS_DEVICE:-auto}" python3 - "$FILE" "$NAME" << 'EOF'
import sys
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import soundfile as sf
from src.pipeline.ingest import load
from src.pipeline.separate import separate, select_device

path    = sys.argv[1]
name    = sys.argv[2]
out_dir = Path(f"test_audio/{name}/stems")
out_dir.mkdir(parents=True, exist_ok=True)

print("▸ ingesting...")
audio = load(path)
sr = 44100
duration = audio.shape[1] / sr
print(f"  {audio.shape}  {audio.dtype}  {duration:.1f}s")

print("▸ selecting device...")
device = select_device()
print(f"  {device}")

print("▸ separating...")
start = time.time()
all_stems = {}

def on_ready(stems):
    elapsed = time.time() - start
    print(f"  [{elapsed:.1f}s] stems ready: {list(stems.keys())}")
    for stem_name, stem in stems.items():
        out_path = out_dir / f"{stem_name}.flac"
        sf.write(str(out_path), stem.T, sr, subtype="PCM_24")
        print(f"  ✓ written: {out_path}")
    all_stems.update(stems)

stems = separate(audio, device=device, on_stems_ready=on_ready)
all_stems.update(stems)
elapsed = time.time() - start

# ── Analysis ──────────────────────────────────────────────────────────────────

def analyse(stem: np.ndarray, mix: np.ndarray) -> dict:
    peak      = float(np.max(np.abs(stem)))
    rms       = float(np.sqrt(np.mean(stem ** 2)))
    mix_rms   = float(np.sqrt(np.mean(mix ** 2)))
    isolation = rms / mix_rms if mix_rms > 0 else 0.0
    silence   = peak < 0.01
    return {
        "peak":      round(peak, 4),
        "rms":       round(rms, 4),
        "isolation": round(isolation, 4),   # fraction of mix energy in this stem
        "silent":    silence,
    }

print(f"\n✓ separation complete in {elapsed:.1f}s")
print()
print(f"  {'stem':10s}  {'peak':>8s}  {'rms':>8s}  {'isolation':>10s}  {'note':>12s}")
print("  " + "-" * 58)

report_lines = [
    f"Auris Vive — Stem Analysis Report",
    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"Source:    {path}",
    f"Duration:  {duration:.2f}s",
    f"Device:    {device}",
    f"Time:      {elapsed:.1f}s",
    f"",
    f"{'stem':10s}  {'peak':>8s}  {'rms':>8s}  {'isolation':>10s}  note",
    "-" * 62,
]

for stem_name, stem in sorted(all_stems.items()):
    stats = analyse(stem, audio)
    note  = "silent" if stats["silent"] else (
            "strong" if stats["isolation"] > 0.3 else
            "present" if stats["isolation"] > 0.05 else
            "weak"
    )
    line = f"  {stem_name:10s}  {stats['peak']:>8.4f}  {stats['rms']:>8.4f}  {stats['isolation']:>10.4f}  {note:>12s}"
    print(line)
    report_lines.append(f"{stem_name:10s}  {stats['peak']:>8.4f}  {stats['rms']:>8.4f}  {stats['isolation']:>10.4f}  {note}")

# ── Write report ──────────────────────────────────────────────────────────────

report_path = Path(f"test_audio/{name}/report.txt")
report_path.write_text("\n".join(report_lines) + "\n")
print(f"\n  report written: {report_path}")

print(f"\n  stems location: test_audio/{name}/stems/")
for f in sorted(out_dir.glob("*.flac")):
    size_kb = f.stat().st_size // 1024
    print(f"  {f.name:20s}  {size_kb:>6d} KB")
EOF
