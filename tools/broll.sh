#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
py="$root/tools/.venv/bin/python"

if [[ ! -x "$py" ]]; then
  python3 -m venv "$root/tools/.venv"
  "$py" -m pip install -q google-genai pillow numpy
fi

cmd="${1:-}"
shift || true
case "$cmd" in
  annotate) exec "$py" "$root/tools/broll/annotate.py" "$@" ;;
  search) exec "$py" "$root/tools/broll/search.py" "$@" ;;
  analyze-refs) exec "$py" "$root/tools/broll/analyze_ref.py" "$@" ;;
  new | autopick | storyboard | compose) exec "$py" "$root/tools/broll/build.py" "$cmd" "$@" ;;
  *)
    echo "usage: tools/broll.sh annotate|search|new|storyboard|compose ..." >&2
    exit 1
    ;;
esac
