#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
model="$root/tools/models/ggml-base.en.bin"

if [[ $# -lt 1 ]]; then
  echo "usage: tools/transcribe.sh <media-file>" >&2
  exit 1
fi
src="$1"
if [[ ! -f "$src" ]]; then
  echo "not a file: $src" >&2
  exit 1
fi
if [[ ! -f "$model" ]]; then
  echo "missing whisper model: $model" >&2
  exit 1
fi

stem="${src%.*}"
wav="$(mktemp -t aieditor-XXXX).wav"
cleanup() { rm -f "$wav"; }
trap cleanup EXIT

ffmpeg -y -i "$src" -ar 16000 -ac 1 -c:a pcm_s16le "$wav" -hide_banner -loglevel error
whisper-cli \
  --model "$model" \
  --file "$wav" \
  --output-json \
  --output-json-full \
  --split-on-word \
  --max-len 1 \
  --output-file "$stem"
echo "wrote ${stem}.json"
