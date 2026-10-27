#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

ok() { printf '  ok    %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1"; fail=1; }

echo "AI Video Editor — tool check"
echo

if command -v ffmpeg >/dev/null; then
  ok "ffmpeg $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"
else
  bad "ffmpeg missing"
fi

if command -v yt-dlp >/dev/null; then
  ok "yt-dlp $(yt-dlp --version)"
else
  bad "yt-dlp missing"
fi

if command -v whisper-cli >/dev/null && [[ -f "$root/tools/models/ggml-base.en.bin" ]]; then
  ok "whisper.cpp $(whisper-cli --version 2>&1 | head -1) + base.en model"
else
  bad "whisper-cli or tools/models/ggml-base.en.bin missing"
fi

if (cd "$root" && npx --yes hyperframes@0.8.192 --version >/dev/null); then
  ok "hyperframes $(cd "$root" && npx --yes hyperframes@0.8.192 --version 2>/dev/null | head -1)"
else
  bad "hyperframes CLI missing"
fi

if (cd "$root" && npx remotion versions >/dev/null); then
  ok "remotion $(cd "$root" && npx remotion --version 2>/dev/null | head -1)"
else
  bad "remotion missing"
fi

echo
if [[ "$fail" -ne 0 ]]; then
  echo "One or more tools failed."
  exit 1
fi
echo "Ready. Open this folder in Cursor, then learn a style or drop footage."
