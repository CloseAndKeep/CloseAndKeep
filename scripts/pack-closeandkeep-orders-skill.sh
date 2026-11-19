#!/usr/bin/env bash
# Rebuild web/public/skills/closeandkeep-orders.zip with the skill folder at zip root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/skills/closeandkeep-orders"
OUT_DIR="$ROOT/web/public/skills"
OUT="$OUT_DIR/closeandkeep-orders.zip"

if [[ ! -f "$SRC/SKILL.md" ]]; then
  echo "missing $SRC/SKILL.md" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$SRC" "$TMP/closeandkeep-orders"
rm -f "$OUT"
(cd "$TMP" && zip -r -X "$OUT" closeandkeep-orders)
echo "wrote $OUT"
unzip -l "$OUT"
