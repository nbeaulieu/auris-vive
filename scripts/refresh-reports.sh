#!/bin/bash
# scripts/refresh-reports.sh
# Regenerate report.txt for all songs that have stems, without re-running separation.
# Reads existing stems from disk, recomputes analysis + BPM, rewrites reports.
# Usage: ./scripts/refresh-reports.sh

set -e
cd "$(dirname "$0")/.."

source .venv-ml/bin/activate

echo "▸ refreshing reports..."
echo ""

python3 - << 'EOF'
import json
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path
from datetime import datetime

SONGS_FILE = Path("test_audio/songs.json")
SR = 44100
STEM_NAMES = ["drums", "bass", "vocals", "other", "piano", "guitar"]

if not SONGS_FILE.exists():
    print("✗ test_audio/songs.json not found")
    exit(1)

songs = json.loads(SONGS_FILE.read_text())

for song in songs:
    slug      = song["slug"]
    clip_path = Path(f"test_audio/{slug}/clip.wav")
    stems_dir = Path(f"test_audio/{slug}/stems")
    report    = Path(f"test_audio/{slug}/report.txt")

    if not clip_path.exists():
        print(f"  {slug:20s}  ✗ no clip")
        continue

    if not stems_dir.exists():
        print(f"  {slug:20s}  ✗ no stems")
        continue

    # Load clip for BPM
    mono, _ = librosa.load(str(clip_path), sr=SR, mono=True)
    tempo, _ = librosa.beat.beat_track(y=mono, sr=SR)
    bpm = float(np.asarray(tempo).item())
    duration = len(mono) / SR

    # Load mix for isolation score baseline
    mix, _ = sf.read(str(clip_path), always_2d=True)
    mix = mix.T.astype(np.float32)  # (2, N)
    mix_rms = float(np.sqrt(np.mean(mix ** 2)))

    def analyse(stem: np.ndarray) -> dict:
        peak      = float(np.max(np.abs(stem)))
        rms       = float(np.sqrt(np.mean(stem ** 2)))
        isolation = rms / mix_rms if mix_rms > 0 else 0.0
        return {
            "peak":      round(peak, 4),
            "rms":       round(rms, 4),
            "isolation": round(isolation, 4),
            "silent":    peak < 0.01,
        }

    def note(stats: dict) -> str:
        if stats["silent"]:           return "silent"
        if stats["isolation"] > 0.3:  return "strong"
        if stats["isolation"] > 0.05: return "present"
        return "weak"

    lines = [
        f"Auris Vive — Stem Analysis Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Track:     {song['name']}",
        f"Source:    {clip_path}",
        f"Duration:  {duration:.2f}s",
        f"BPM:       {bpm:.1f}",
        f"",
        f"{'stem':10s}  {'peak':>8s}  {'rms':>8s}  {'isolation':>10s}  note",
        "-" * 62,
    ]

    for stem_name in STEM_NAMES:
        npy_path  = stems_dir / f"{stem_name}.npy"
        flac_path = stems_dir / f"{stem_name}.flac"
        if npy_path.exists():
            stem = np.load(str(npy_path))   # (2, N) float32 — instant
        elif flac_path.exists():
            data, _ = sf.read(str(flac_path), always_2d=True)
            stem = data.T.astype(np.float32)
        else:
            lines.append(f"{stem_name:10s}  {'—':>8s}  {'—':>8s}  {'—':>10s}  missing")
            continue
        stats = analyse(stem)
        lines.append(
            f"{stem_name:10s}  {stats['peak']:>8.4f}  "
            f"{stats['rms']:>8.4f}  {stats['isolation']:>10.4f}  {note(stats)}"
        )

    report.write_text("\n".join(lines) + "\n")
    print(f"  {slug:20s}  ✓ BPM={bpm:.1f}  →  {report}")

print("\n✓ all reports refreshed")
EOF
