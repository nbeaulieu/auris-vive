#!/bin/bash
# scripts/grab-clip.sh
# Downloads a 30-second clip from a YouTube URL starting at a given timestamp.
# Usage: ./scripts/grab-clip.sh <url> <name> [start] [duration]
#
# Examples:
#   ./scripts/grab-clip.sh "https://youtube.com/watch?v=..." tswift "2:10" 30
#   ./scripts/grab-clip.sh "https://youtube.com/watch?v=..." finger11 "1:00" 30
#
# Output: test_audio/<name>/clip.wav
#
# Requires: yt-dlp, ffmpeg
#   brew install yt-dlp ffmpeg

set -e
cd "$(dirname "$0")/.."

URL="${1:?usage: grab-clip.sh <url> <name> [start] [duration]}"
NAME="${2:?usage: grab-clip.sh <url> <name> [start] [duration]}"
START="${3:-0:00}"
DURATION="${4:-30}"
OUTDIR="test_audio/$NAME"
OUTFILE="$OUTDIR/clip.wav"

mkdir -p "$OUTDIR"

echo "▸ downloading: $NAME"
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
