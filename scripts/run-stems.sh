#!/bin/bash
# scripts/run-stems.sh
# Run a file through ingest + separation and write each stem as FLAC + NPY.
# Usage: ./scripts/run-stems.sh <path/to/clip.wav> [output_name] [--force]
#
# Flags:
#   --force   Re-run separation even if stems already exist
#
# Output:
#   test_audio/<n>/stems/{drums,bass,vocals,other,piano,guitar}.flac  (listen)
#   test_audio/<n>/stems/{drums,bass,vocals,other,piano,guitar}.npy   (pipeline cache)
#   test_audio/<n>/report.txt

set -e
cd "$(dirname "$0")/.."

FILE="${1:?usage: run-stems.sh <path/to/clip.wav> [output_name] [--force]}"
NAME="${2:-$(basename $(dirname "$FILE"))}"
FORCE="${3:-}"

if [ ! -f "$FILE" ]; then
  echo "✗ file not found: $FILE"
  exit 1
fi

# Skip if stems already exist and --force not set
STEMS_DIR="test_audio/$NAME/stems"
if [ -d "$STEMS_DIR" ] && [ -f "$STEMS_DIR/drums.npy" ] && [ "$FORCE" != "--force" ]; then
  echo "✓ stems already exist for $NAME — skipping (use --force to re-run)"
  exit 0
fi

source .venv-ml/bin/activate

echo "▸ device: ${AURIS_DEVICE:-auto}"
echo "▸ file:   $FILE"
echo "▸ output: $STEMS_DIR/"
echo ""

AURIS_DEVICE="${AURIS_DEVICE:-auto}" python3 - "$FILE" "$NAME" << 'EOF'
import sys
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import soundfile as sf
import librosa
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

# BPM detection on mono mix
mono = audio.mean(axis=0)
tempo, _ = librosa.beat.beat_track(y=mono, sr=sr)
bpm = float(np.asarray(tempo).item())
print(f"  BPM: {bpm:.1f}")

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
        # FLAC — for listening
        sf.write(str(out_dir / f"{stem_name}.flac"), stem.T, sr, subtype="PCM_24")
        # NPY — for pipeline reuse (float32, shape (2,N), loads in ~10ms)
        np.save(str(out_dir / f"{stem_name}.npy"), stem)
        print(f"  ✓ {stem_name}")
    all_stems.update(stems)

stems = separate(audio, device=device, on_stems_ready=on_ready)
all_stems.update(stems)
elapsed = time.time() - start

# ── Analysis ──────────────────────────────────────────────────────────────────

def analyse(stem, mix):
    peak      = float(np.max(np.abs(stem)))
    rms       = float(np.sqrt(np.mean(stem ** 2)))
    mix_rms   = float(np.sqrt(np.mean(mix ** 2)))
    isolation = rms / mix_rms if mix_rms > 0 else 0.0
    return {
        "peak":      round(peak, 4),
        "rms":       round(rms, 4),
        "isolation": round(isolation, 4),
        "silent":    peak < 0.01,
    }

def note(stats):
    if stats["silent"]:           return "silent"
    if stats["isolation"] > 0.3:  return "strong"
    if stats["isolation"] > 0.05: return "present"
    return "weak"

print(f"\n✓ separation complete in {elapsed:.1f}s")
print()
print(f"  {'stem':10s}  {'peak':>8s}  {'rms':>8s}  {'isolation':>10s}  note")
print("  " + "-" * 58)

report_lines = [
    f"Auris Vive — Stem Analysis Report",
    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"Track:     {name}",
    f"Source:    {path}",
    f"Duration:  {duration:.2f}s",
    f"BPM:       {bpm:.1f}",
    f"Device:    {device}",
    f"Time:      {elapsed:.1f}s",
    f"",
    f"{'stem':10s}  {'peak':>8s}  {'rms':>8s}  {'isolation':>10s}  note",
    "-" * 62,
]

for stem_name, stem in sorted(all_stems.items()):
    stats = analyse(stem, audio)
    n     = note(stats)
    print(f"  {stem_name:10s}  {stats['peak']:>8.4f}  {stats['rms']:>8.4f}  {stats['isolation']:>10.4f}  {n:>12s}")
    report_lines.append(f"{stem_name:10s}  {stats['peak']:>8.4f}  {stats['rms']:>8.4f}  {stats['isolation']:>10.4f}  {n}")

report_path = Path(f"test_audio/{name}/report.txt")
report_path.write_text("\n".join(report_lines) + "\n")
print(f"\n  report: {report_path}")
print(f"  stems:  test_audio/{name}/stems/")
for f in sorted(out_dir.glob("*.flac")):
    size_kb = f.stat().st_size // 1024
    print(f"    {f.name:20s}  {size_kb:>6d} KB")

# ── Curve extraction ─────────────────────────────────────────────────────────

from src.pipeline.analyse.analyse import analyse as analyse_curves
from src.pipeline.analyse.disk import DiskCurvesSource

curves_dir = Path(f"test_audio/{name}/curves")
source = DiskCurvesSource(curves_dir)

print(f"\n▸ extracting visualisation curves...")
stem_curves = analyse_curves(all_stems)
for sc_name, sc in stem_curves.items():
    source.save(sc_name, sc)
    print(f"  ✓ curves: {sc_name}")
print(f"  curves: {curves_dir}/")
EOF
