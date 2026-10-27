#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$root/references"

if [[ $# -lt 1 ]]; then
  echo "usage: tools/download-ref.sh <url> [more urls]" >&2
  exit 1
fi

mkdir -p "$dest"
n="$(find "$dest" -maxdepth 1 -name 'ref-*.mp4' | wc -l | tr -d ' ')"

for url in "$@"; do
  n=$((n + 1))
  printf -v prefix "ref-%02d" "$n"
  yt-dlp \
    --no-playlist \
    --merge-output-format mp4 \
    -o "$dest/${prefix}-%(title).80s.%(ext)s" \
    "$url"
done
