#!/bin/bash
# scripts/run-analyse.sh
# Run the analyse stage on existing stem .npy files and write curves to disk.
# Does NOT re-run separation — reads stems that are already on disk.
# Usage: ./scripts/run-analyse.sh [slug]
#        with no argument, processes all songs in songs.json that have stems

set -e
cd "$(dirname "$0")/.."

source .venv-ml/bin/activate

SLUG="${1:-}"

python3 - "$SLUG" << 'EOF'
import sys
import json
import time
import numpy as np
from pathlib import Path

slug_filter = sys.argv[1]  # empty string = all songs

SONGS_FILE = Path("test_audio/songs.json")
SR         = 44_100
STEM_NAMES = ["drums", "bass", "vocals", "other", "piano", "guitar"]

if not SONGS_FILE.exists():
    print("✗ test_audio/songs.json not found")
    sys.exit(1)

songs = json.loads(SONGS_FILE.read_text())

from src.pipeline.analyse.analyse import analyse
from src.pipeline.analyse.disk import DiskCurvesSource

processed = 0
skipped   = 0

for song in songs:
    slug = song["slug"]

    if slug_filter and slug != slug_filter:
        continue

    stems_dir  = Path(f"test_audio/{slug}/stems")
    curves_dir = Path(f"test_audio/{slug}/curves")

    # Check stems exist as .npy
    npy_files = list(stems_dir.glob("*.npy")) if stems_dir.exists() else []
    if not npy_files:
        print(f"  {slug:20s}  · no stems — run stems first")
        skipped += 1
        continue

    print(f"  {slug:20s}  ▸ analysing...")
    start = time.time()

    # Load stems from .npy (fast — no re-separation)
    stems = {}
    for npy_path in sorted(npy_files):
        stem_name = npy_path.stem  # e.g. "drums"
        if stem_name in STEM_NAMES:
            stems[stem_name] = np.load(str(npy_path))

    if not stems:
        print(f"  {slug:20s}  · no valid stem files found")
        skipped += 1
        continue

    # Run analyse stage
    try:
        curves = analyse(stems)
    except Exception as exc:
        print(f"  {slug:20s}  ✗ analysis failed: {exc}")
        skipped += 1
        continue

    # Write to disk
    source = DiskCurvesSource(curves_dir)
    for stem_name, stem_curves in curves.items():
        source.save(stem_name, stem_curves)

    elapsed = time.time() - start
    print(f"  {slug:20s}  ✓ {len(curves)} stems analysed in {elapsed:.1f}s  →  {curves_dir}")
    processed += 1

print(f"\n✓ done — {processed} processed, {skipped} skipped")
EOF
