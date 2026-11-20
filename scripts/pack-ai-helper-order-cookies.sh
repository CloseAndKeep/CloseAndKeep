#!/usr/bin/env bash
# Publish ai-helper-order-cookies/INSTRUCTIONS.md as a downloadable .txt on the site.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/ai-helper-order-cookies/INSTRUCTIONS.md"
OUT_DIR="$ROOT/web/public/ai-helper-order-cookies"
OUT="$OUT_DIR/INSTRUCTIONS.txt"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
# Strip a leading markdown H1 for a cleaner paste-into-Claude text file; keep the rest.
{
  echo "AI Helper: Order Cookies"
  echo ""
  # Drop the first '# ...' heading line if present
  awk 'NR==1 && /^# / { next } { print }' "$SRC"
} > "$OUT"

echo "wrote $OUT"
wc -l "$OUT"
