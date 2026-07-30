#!/usr/bin/env bash
# Configure a linked ARIA-NBV worktree without copying the runtime or data cache.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shared_root="${ARIA_NBV_SHARED_ROOT:-$(git -C "$repo_root" worktree list --porcelain | awk '/^worktree / { print substr($0, 10); exit }')}"
check_only=false

usage() {
  cat <<'EOF'
Usage: scripts/setup_worktree_env.sh [--check]

Links this worktree to the primary checkout's Python runtime and generated data
cache, then initializes the exact submodules recorded by this worktree.

Set ARIA_NBV_SHARED_ROOT to use a primary checkout other than Git's first
registered worktree. Source .env afterwards to use aria_nbv_run.
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
  "$shared_root/aria_nbv/.venv/bin/python" -c \
    'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

[[ -d "$shared_root/aria_nbv/.venv" ]] || fail "shared runtime is missing: $shared_root/aria_nbv/.venv"
[[ -d "$shared_root/.data" ]] || fail "shared data cache is missing: $shared_root/.data"
[[ "$shared_root" != "$repo_root" ]] || fail "shared root must be another worktree"

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

if [[ "$check_only" == false ]]; then
  mkdir -p .data
fi

for cache_dir in ase_efm ase_meshes ase_meshes_processed offline_cache worktree_migrations; do
  source="$shared_root/.data/$cache_dir"
  [[ -e "$source" ]] || continue
  link_or_check "$source" ".data/$cache_dir"
done

if [[ "$check_only" == false ]]; then
  git submodule update --init --recursive
  if [[ ! -e .env ]]; then
    ln -s .env.example .env
  fi
else
  [[ -e .env ]] || fail ".env is missing; run scripts/setup_worktree_env.sh before checking"
fi

if git submodule status --recursive | awk '/^[-+U]/ { exit 1 }'; then
  printf 'ARIA-NBV worktree environment is ready. Source .env from %s.\n' "$repo_root"
else
  fail "one or more submodules are not at the recorded commit"
fi
