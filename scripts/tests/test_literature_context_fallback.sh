#!/bin/sh
set -eu

root=$(git rev-parse --show-toplevel)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aria-literature-context.XXXXXX")
trap 'rm -rf "$tmp"' EXIT

index="$tmp/literature-index.md"
"$root/.agents/skills/aria-nbv-context/scripts/nbv_literature_index.sh" "$index"

test -s "$index"
grep -q '^## Local TeX Paper Families$' "$index"
! grep -qi 'litkg\|semantic scholar' "$index"

"$root/.agents/skills/aria-nbv-context/scripts/nbv_literature_search.sh" \
  'VIN-NBV' >"$tmp/search.txt"
test -s "$tmp/search.txt"
