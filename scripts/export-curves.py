#!/usr/bin/env python3
"""
Export pre-computed stem curves to JSON bundles for the web prototype.

Reads every song in test_audio/songs.json that has curves on disk
(test_audio/<slug>/curves/) and writes to docs/proto/data/<slug>/:
  - curves.json  — all curves, rounded to 2dp
  - audio.wav    — copied from test_audio/<slug>/clip.wav
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_AUDIO = REPO_ROOT / "test_audio"
PROTO_DATA = REPO_ROOT / "docs" / "proto" / "data"

STEM_NAMES = ("drums", "bass", "vocals", "other", "piano", "guitar")
CURVE_NAMES = ("energy", "brightness", "onset", "warmth", "texture", "flux")


def load_stem_curves(curves_dir: Path, stem_name: str) -> dict[str, list[float]] | None:
    """Load all six .npy curves for a stem, returning rounded float lists."""
    meta_path = curves_dir / f"{stem_name}_meta.json"
    if not meta_path.exists():
        return None

    result: dict[str, list[float]] = {}
    for curve in CURVE_NAMES:
        npy_path = curves_dir / f"{stem_name}_{curve}.npy"
        if not npy_path.exists():
            print(f"  WARNING: missing {npy_path.name} for stem '{stem_name}'")
            return None
        arr = np.load(str(npy_path)).astype(np.float32)
        result[curve] = [round(float(v), 2) for v in arr]

    return result


def export_song(slug: str) -> bool:
    """Export curves and audio for a single song. Returns True on success."""
    song_dir = TEST_AUDIO / slug
    curves_dir = song_dir / "curves"
    clip_path = song_dir / "clip.wav"

    if not curves_dir.exists():
        print(f"  SKIP  {slug} — no curves directory")
        return False

    if not clip_path.exists():
        print(f"  SKIP  {slug} — no clip.wav")
        return False

    # Load the first stem's metadata for frame rate
    first_meta = None
    for stem in STEM_NAMES:
        meta_path = curves_dir / f"{stem}_meta.json"
        if meta_path.exists():
            first_meta = json.loads(meta_path.read_text())
            break

    if first_meta is None:
        print(f"  SKIP  {slug} — no stem metadata found")
        return False

    fps = int(first_meta["fps"])

    # Load all stems
    stems: dict[str, dict[str, list[float]]] = {}
    n_frames = 0
    for stem in STEM_NAMES:
        curves = load_stem_curves(curves_dir, stem)
        if curves is None:
            print(f"  SKIP  {slug} — incomplete curves (missing {stem})")
            return False
        stems[stem] = curves
        n_frames = len(next(iter(curves.values())))

    duration_s = round(n_frames / fps, 2)

    bundle = {
        "slug": slug,
        "duration_s": duration_s,
        "frame_rate": float(fps),
        "n_frames": n_frames,
        "stems": stems,
    }

    # Write output
    out_dir = PROTO_DATA / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "curves.json"
    json_path.write_text(json.dumps(bundle))
    print(f"  WROTE {json_path.relative_to(REPO_ROOT)}  ({n_frames} frames, {duration_s}s)")

    wav_dest = out_dir / "audio.wav"
    shutil.copy2(clip_path, wav_dest)
    print(f"  WROTE {wav_dest.relative_to(REPO_ROOT)}")

    return True


def main() -> None:
    songs_json = TEST_AUDIO / "songs.json"
    if not songs_json.exists():
        print(f"ERROR: {songs_json} not found")
        sys.exit(1)

    songs = json.loads(songs_json.read_text())
    print(f"Found {len(songs)} songs in songs.json\n")

    exported = 0
    skipped = 0
    for song in songs:
        slug = song["slug"]
        print(f"[{slug}]")
        if export_song(slug):
            exported += 1
        else:
            skipped += 1
        print()

    # Write index.json for the browser to discover available songs
    if exported > 0:
        PROTO_DATA.mkdir(parents=True, exist_ok=True)
        slugs = sorted(
            d.name for d in PROTO_DATA.iterdir()
            if d.is_dir() and (d / "curves.json").exists()
        )
        index_path = PROTO_DATA / "index.json"
        index_path.write_text(json.dumps(slugs))
        print(f"Wrote {index_path.relative_to(REPO_ROOT)} ({len(slugs)} songs)")

    print(f"Done: {exported} exported, {skipped} skipped")


if __name__ == "__main__":
    main()
