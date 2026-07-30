#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <pattern> [rg flags...]" >&2
  exit 1
fi

pattern="$1"
shift

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../../../../" && pwd)"
LIT_DIR="${ROOT_DIR}/docs/literature"

if [[ ! -d "$LIT_DIR" ]]; then
  echo "error: literature directory not found: $LIT_DIR" >&2
  exit 2
fi

if command -v rg >/dev/null 2>&1; then
  rg -n "$pattern" "$LIT_DIR" --glob "**/*.tex" --glob "**/*.bib" --glob "**/*.sty" "$@"
else
  grep -R -n -E "$pattern" "$LIT_DIR" --include="*.tex" --include="*.bib" --include="*.sty"
fi
