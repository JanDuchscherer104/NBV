#!/bin/sh
set -eu

ROOT=$(git rev-parse --show-toplevel)
PYTHON_BIN=$(command -v python3)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/aria-graph-hook.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q
git -C "$TMP" config user.email graphify-test@example.invalid
git -C "$TMP" config user.name graphify-test
mkdir -p "$TMP/scripts/git_hooks" "$TMP/scripts" "$TMP/aria_nbv/aria_nbv"
cp "$ROOT/scripts/git_hooks/post-commit" "$TMP/scripts/git_hooks/post-commit"
cp "$ROOT/.graphify.toml" "$TMP/.graphify.toml"

cat >"$TMP/scripts/graphify_adapter.py" <<'EOF'
from pathlib import Path
import sys


def load_config():
    return {}


def selected_literature_dirs():
    return {"paper-a"}


def classify_path(path, config, selected):
    del config
    if path.startswith("aria_nbv/aria_nbv/") and path.endswith(".py"):
        return "code"
    if path.startswith(("docs/typst/thesis/", "docs/typst/shared/")):
        return "thesis"
    if path == "docs/literature/sources.jsonl":
        return "literature"
    if path.startswith("docs/literature/tex-src/"):
        parts = path.split("/")
        return "literature" if len(parts) > 3 and parts[3] in selected else None
    return None


if __name__ == "__main__":
    assert sys.argv[1:] == ["sync"]
    Path("dispatch.log").open("a", encoding="utf-8").write("sync\n")
EOF
printf '%s\n' '# bridge fixture' >"$TMP/scripts/graphify_bridge.py"
printf '%s\n' 'VALUE = 1' >"$TMP/aria_nbv/aria_nbv/example.py"
git -C "$TMP" add .
git -C "$TMP" commit -qm initial

run_hook() {
  (
    cd "$TMP"
    PATH=/usr/bin:/bin PYTHON_INTERPRETER="$PYTHON_BIN" scripts/git_hooks/post-commit
  )
}

dispatches() {
  if [ -f "$TMP/dispatch.log" ]; then
    wc -l <"$TMP/dispatch.log"
  else
    printf '0\n'
  fi
}

commit_change() {
  git -C "$TMP" add -A
  git -C "$TMP" commit -qm "$1"
  run_hook
}

printf '%s\n' 'VALUE = 2' >"$TMP/aria_nbv/aria_nbv/example.py"
commit_change corpus-change
test "$(dispatches)" -eq 1

printf '%s\n' '# config change' >>"$TMP/.graphify.toml"
commit_change config-change
test "$(dispatches)" -eq 2

printf '%s\n' '# adapter change' >>"$TMP/scripts/graphify_adapter.py"
commit_change adapter-change
test "$(dispatches)" -eq 3

printf '%s\n' '# bridge change' >>"$TMP/scripts/graphify_bridge.py"
commit_change bridge-change
test "$(dispatches)" -eq 4

printf '%s\n' 'operator guidance' >"$TMP/AGENTS.md"
commit_change agents-change
test "$(dispatches)" -eq 4

mkdir -p "$TMP/.agents"
printf '%s\n' 'operator state' >"$TMP/.agents/operator.md"
commit_change operator-change
test "$(dispatches)" -eq 4

mkdir -p "$TMP/graphify-out"
printf '{}\n' >"$TMP/graphify-out/graph.json"
git -C "$TMP" add -f graphify-out/graph.json
git -C "$TMP" commit -qm graph-only
run_hook
test "$(dispatches)" -eq 4
