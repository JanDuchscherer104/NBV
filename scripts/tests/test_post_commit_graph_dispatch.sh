#!/bin/sh
set -eu

ROOT=$(git rev-parse --show-toplevel)
PYTHON_BIN=$(command -v python3)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/aria-graph-hook.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q
git -C "$TMP" config user.email graphify-test@example.invalid
git -C "$TMP" config user.name graphify-test
mkdir -p "$TMP/scripts/git_hooks" "$TMP/scripts/kg" "$TMP/scripts" "$TMP/aria_nbv/aria_nbv" "$TMP/graphify-out"
cp "$ROOT/scripts/git_hooks/post-commit" "$TMP/scripts/git_hooks/post-commit"

cat >"$TMP/scripts/kg/auto_refresh.sh" <<'EOF'
#!/bin/sh
printf 'kg\n' >> dispatch.log
EOF
chmod +x "$TMP/scripts/kg/auto_refresh.sh"
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

test "$(grep -c '^kg$' "$TMP/dispatch.log")" -eq 1
test "$(grep -c '^graphify --mode structural$' "$TMP/dispatch.log")" -eq 1

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
