#!/bin/sh
set -eu

ROOT=$(git rev-parse --show-toplevel)
PYTHON_BIN=$(command -v python3)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/aria-graph-hook.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q
git -C "$TMP" config user.email graphify-test@example.invalid
git -C "$TMP" config user.name graphify-test
mkdir -p "$TMP/scripts/git_hooks" "$TMP/scripts" "$TMP/aria_nbv/aria_nbv" "$TMP/graphify-out"
mkdir -p "$TMP/docs/literature"
cp "$ROOT/scripts/git_hooks/post-commit" "$TMP/scripts/git_hooks/post-commit"
cp "$ROOT/scripts/graphify_contract.py" "$TMP/scripts/graphify_contract.py"
cp "$ROOT/.graphify.toml" "$TMP/.graphify.toml"
cp "$ROOT/.graphifyignore" "$TMP/.graphifyignore"
printf '%s\n' '{"tex_dir":"arXiv-selected"}' >"$TMP/docs/literature/sources.jsonl"

cat >"$TMP/scripts/graphify_refresh.py" <<'EOF'
from pathlib import Path
import sys
Path("dispatch.log").open("a", encoding="utf-8").write("graphify " + " ".join(sys.argv[1:]) + "\n")
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

test "$(grep -c '^graphify --mode structural$' "$TMP/dispatch.log")" -eq 1

mkdir -p "$TMP/.agents/skills/demo"
printf '%s\n' '---' 'name: demo' 'description: fixture' '---' >"$TMP/.agents/skills/demo/SKILL.md"
git -C "$TMP" add .
git -C "$TMP" commit -qm skill-change
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" GRAPHIFY_SYNC_HOOK=1 scripts/git_hooks/post-commit
)
test "$(grep -c '^graphify --mode structural$' "$TMP/dispatch.log")" -eq 2

mkdir -p "$TMP/docs/literature/tex-src/arXiv-selected"
printf 'selected\n' >"$TMP/docs/literature/tex-src/arXiv-selected/main.tex"
git -C "$TMP" add .
git -C "$TMP" commit -qm selected-literature
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" GRAPHIFY_SYNC_HOOK=1 scripts/git_hooks/post-commit
)
test "$(grep -c '^graphify --mode structural$' "$TMP/dispatch.log")" -eq 3

mkdir -p "$TMP/docs/literature/tex-src/arXiv-unselected"
printf 'unselected\n' >"$TMP/docs/literature/tex-src/arXiv-unselected/main.tex"
git -C "$TMP" add .
git -C "$TMP" commit -qm unselected-literature
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" GRAPHIFY_SYNC_HOOK=1 scripts/git_hooks/post-commit
)
test "$(grep -c '^graphify --mode structural$' "$TMP/dispatch.log")" -eq 3

printf '{}\n' >"$TMP/graphify-out/graph.json"
git -C "$TMP" add -f graphify-out/graph.json
git -C "$TMP" commit -qm graph-only
before=$(wc -l <"$TMP/dispatch.log")
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" GRAPHIFY_SYNC_HOOK=1 scripts/git_hooks/post-commit
)
after=$(wc -l <"$TMP/dispatch.log")
test "$before" -eq "$after"

printf '[broken\n' >"$TMP/.graphify.toml"
git -C "$TMP" add .graphify.toml
git -C "$TMP" commit -qm malformed-graphify-config
(
  cd "$TMP"
  PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" \
    GRAPHIFY_REFRESH_LOG="$TMP/preflight.log" GRAPHIFY_SYNC_HOOK=1 \
    scripts/git_hooks/post-commit
)
grep -q 'Graphify preflight failed: corpus classification error' "$TMP/preflight.log"
