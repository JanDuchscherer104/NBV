#!/bin/sh
set -eu

ROOT=$(git rev-parse --show-toplevel)
PYTHON_BIN=$(command -v python3)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/aria-graph-hook.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q
git -C "$TMP" config user.email graphify-test@example.invalid
git -C "$TMP" config user.name graphify-test
mkdir -p "$TMP/scripts/git_hooks" "$TMP/aria_nbv/aria_nbv"
cp "$ROOT/scripts/git_hooks/post-commit" "$TMP/scripts/git_hooks/post-commit"

cat >"$TMP/scripts/graphify_refresh.py" <<'EOF'
from pathlib import Path
Path("dispatch.log").open("a", encoding="utf-8").write("graphify\n")
EOF

touch "$TMP/aria_nbv/aria_nbv/example.py"
git -C "$TMP" add .
git -C "$TMP" commit -qm initial
printf '# change\n' >>"$TMP/aria_nbv/aria_nbv/example.py"
git -C "$TMP" add .
git -C "$TMP" commit -qm code-change
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" GRAPHIFY_SYNC_HOOK=1 scripts/git_hooks/post-commit
)

test "$(grep -c '^graphify$' "$TMP/dispatch.log")" -eq 1
