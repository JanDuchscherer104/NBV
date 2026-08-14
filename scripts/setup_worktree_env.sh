#!/usr/bin/env bash
# Configure a linked ARIA-NBV worktree without copying the runtime or data cache.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_git_dir="$(git -C "$repo_root" rev-parse --absolute-git-dir)"
shared_root="${ARIA_NBV_SHARED_ROOT:-$(git --git-dir="$repo_git_dir" worktree list --porcelain | awk '/^worktree / { print substr($0, 10); exit }')}"
check_only=false

usage() {
  cat <<'EOF'
Usage: scripts/setup_worktree_env.sh [--check]

Links this worktree to the source checkout's Python runtime, ignored data cache,
downloaded literature PDFs, and content-addressed Graphify semantic caches,
then initializes the exact submodules recorded by this worktree.

Set ARIA_NBV_SHARED_ROOT to use a primary checkout other than Git's first
registered worktree. Source .env afterwards to use the linked virtual
environment.
EOF
}

if [[ "${1:-}" == "--check" ]]; then
  check_only=true
elif [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

realpath_portable() {
  "$shared_python" -c \
    'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

git_in_worktree() {
  git --git-dir="$repo_git_dir" --work-tree="$repo_root" "$@"
}

[[ -d "$shared_root/aria_nbv/.venv" ]] || fail "shared runtime is missing: $shared_root/aria_nbv/.venv"
shared_python="$shared_root/aria_nbv/.venv/bin/python"
[[ -x "$shared_python" ]] || fail "shared Python is not executable: $shared_python"
"$shared_python" -c 'import sys; raise SystemExit(0 if sys.executable else 1)' \
  >/dev/null 2>&1 || fail "shared Python cannot run: $shared_python"
[[ -d "$shared_root/.data" ]] || fail "shared data cache is missing: $shared_root/.data"
[[ "$shared_root" != "$repo_root" ]] || fail "shared root must be another worktree"

shared_graphify_cache_root="$shared_root/.data/graphify-semantic-cache"
shared_graphify_semantic_cache="$shared_graphify_cache_root/semantic"
shared_graphify_semantic_deep_cache="$shared_graphify_cache_root/semantic-deep"

if [[ "$check_only" == false ]]; then
  mkdir -p "$shared_graphify_semantic_cache" "$shared_graphify_semantic_deep_cache"
else
  [[ -d "$shared_graphify_semantic_cache" ]] || fail "shared Graphify semantic cache is missing: $shared_graphify_semantic_cache"
  [[ -d "$shared_graphify_semantic_deep_cache" ]] || fail "shared Graphify semantic-deep cache is missing: $shared_graphify_semantic_deep_cache"
fi

link_or_check() {
  local source="$1"
  local target="$2"

  if [[ -L "$target" ]]; then
    [[ "$(realpath_portable "$target")" == "$(realpath_portable "$source")" ]] || fail "$target points somewhere else"
    return
  fi

  if [[ "$check_only" == true ]]; then
    fail "$target is not linked to $source"
  fi
  [[ ! -e "$target" ]] || fail "$target already exists; preserve it or replace it manually"
  ln -s "$source" "$target"
}

cd "$repo_root"
link_or_check "$shared_root/aria_nbv/.venv" "aria_nbv/.venv"
"$repo_root/aria_nbv/.venv/bin/python" \
  -c 'import sys; raise SystemExit(0 if sys.executable else 1)' \
  >/dev/null 2>&1 || fail "linked Python cannot run: $repo_root/aria_nbv/.venv/bin/python"

if [[ "$check_only" == false ]]; then
  mkdir -p .data docs/literature graphify-out/cache
fi

# Download manifests are tracked; every other top-level .data directory is an
# ignored cache and can be shared without copying it into each worktree. The
# Graphify semantic cache is intentionally excluded: only its two content-
# addressed namespaces are linked under graphify-out/cache below.
while IFS= read -r -d '' source; do
  link_or_check "$source" ".data/$(basename "$source")"
done < <(find "$shared_root/.data" -mindepth 1 -maxdepth 1 -type d \
  ! -name aria_download_urls ! -name graphify-semantic-cache -print0)

# TeX and bibliography sources are tracked and Git checks them out normally.
# PDFs are ignored downloads, so retain one shared read-only cache for them.
if [[ -e "$shared_root/docs/literature/pdf" ]]; then
  link_or_check "$shared_root/docs/literature/pdf" "docs/literature/pdf"
fi

# These content-addressed semantic results are the only Graphify state shared
# between worktrees. Graphs, manifests, projections, AST state, and run state
# stay local. Clearing either cache increases future extraction cost everywhere
# but cannot make a stale graph current.
link_or_check "$shared_graphify_semantic_cache" "graphify-out/cache/semantic"
link_or_check "$shared_graphify_semantic_deep_cache" "graphify-out/cache/semantic-deep"

if [[ "$check_only" == false ]]; then
  git_in_worktree submodule update --init --recursive
  if [[ ! -e .env ]]; then
    ln -s .env.example .env
  fi
else
  [[ -e .env ]] || fail ".env is missing; run scripts/setup_worktree_env.sh before checking"
fi

if git_in_worktree submodule status --recursive | awk '/^[-+U]/ { exit 1 }'; then
  printf 'ARIA-NBV worktree environment is ready. Source .env from %s.\n' "$repo_root"
else
  fail "one or more submodules are not at the recorded commit"
fi
