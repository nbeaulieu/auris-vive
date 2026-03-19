#!/bin/bash
# scripts/grab-clip.sh
# Downloads a 30-second clip from a YouTube URL starting at a given timestamp.
# Usage: ./scripts/grab-clip.sh
#
# Requires: yt-dlp, ffmpeg
#   brew install yt-dlp ffmpeg

set -e
cd "$(dirname "$0")/.."

URL="https://www.youtube.com/watch?v=ko70cExuzZM"
START="2:10"
DURATION=30
OUTDIR="test_audio"
OUTFILE="$OUTDIR/clip.wav"

mkdir -p "$OUTDIR"

echo "▸ downloading audio..."
yt-dlp \
  --extract-audio \
  --audio-format wav \
  --audio-quality 0 \
  --output "$OUTDIR/full.%(ext)s" \
  "$URL"

echo "▸ trimming to ${DURATION}s from ${START}..."
ffmpeg -y \
  -ss "$START" \
  -i "$OUTDIR/full.wav" \
  -t "$DURATION" \
  -c copy \
  "$OUTFILE"

rm "$OUTDIR/full.wav"

echo "✓ saved: $OUTFILE"
