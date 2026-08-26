#!/usr/bin/env bash
# Configure a linked ARIA-NBV worktree without copying the runtime or data cache.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_git_dir="$(git -C "$repo_root" rev-parse --absolute-git-dir)"
shared_root="${ARIA_NBV_SHARED_ROOT:-}"
check_only=false

usage() {
  cat <<'EOF'
Usage: scripts/setup_worktree_env.sh [--check]

Links this worktree to the source checkout's Python runtime, ignored data cache,
downloaded literature PDFs, and content-addressed Graphify semantic caches,
then initializes the exact submodules recorded by this worktree.

ARIA_NBV_SHARED_ROOT must identify the worktree from which this worktree was
forked. Source .env afterwards to use the linked virtual environment.
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

[[ -n "$shared_root" ]] || fail "ARIA_NBV_SHARED_ROOT must identify the parent worktree"
[[ -d "$shared_root" ]] || fail "shared root does not exist: $shared_root"
shared_root="$(cd "$shared_root" && pwd -P)"
[[ "$shared_root" != "$repo_root" ]] || fail "shared root must be another worktree"
source_git_dir="$(git -C "$shared_root" rev-parse --absolute-git-dir 2>/dev/null)" || \
  fail "shared root is not a Git worktree; cannot seed Graphify"
source_common_dir="$(git --git-dir="$source_git_dir" --work-tree="$shared_root" \
  rev-parse --git-common-dir 2>/dev/null)" || fail "shared root Git metadata is unavailable"
destination_common_dir="$(git_in_worktree rev-parse --git-common-dir)" || \
  fail "destination Git metadata is unavailable"
[[ "$source_common_dir" = /* ]] || source_common_dir="$shared_root/$source_common_dir"
[[ "$destination_common_dir" = /* ]] || destination_common_dir="$repo_root/$destination_common_dir"
source_common_dir="$(cd "$source_common_dir" && pwd -P)"
destination_common_dir="$(cd "$destination_common_dir" && pwd -P)"
[[ "$source_common_dir" == "$destination_common_dir" ]] || \
  fail "source and destination must belong to the same Git common directory"
registered_source=false
registered_destination=false
while IFS= read -r worktree_line; do
  [[ "$worktree_line" == "worktree $shared_root" ]] && registered_source=true
  [[ "$worktree_line" == "worktree $repo_root" ]] && registered_destination=true
done < <(git --git-dir="$source_git_dir" --work-tree="$shared_root" worktree list --porcelain)
[[ "$registered_source" == true && "$registered_destination" == true ]] || \
  fail "source and destination must both be registered Git worktrees"

# Everything above is Git metadata only. Do not invoke a parent-provided
# executable or create child links until the source topology is proven.
(
  cd "$shared_root"
  python3 -I "$repo_root/scripts/check_graphify_freshness.py" --usable --quiet
) || fail "shared parent Graphify generation is not query-admissible; complete its semantic refresh first"
[[ -d "$shared_root/aria_nbv/.venv" ]] || fail "shared runtime is missing: $shared_root/aria_nbv/.venv"
shared_python="$shared_root/aria_nbv/.venv/bin/python"
[[ -x "$shared_python" ]] || fail "shared Python is not executable: $shared_python"
"$shared_python" -c 'import sys; raise SystemExit(0 if sys.executable else 1)' \
  >/dev/null 2>&1 || fail "shared Python cannot run: $shared_python"
[[ -d "$shared_root/.data" ]] || fail "shared data cache is missing: $shared_root/.data"

shared_graphify_semantic_cache="$shared_root/graphify-out/cache/semantic"
shared_graphify_semantic_deep_cache="$shared_root/graphify-out/cache/semantic-deep"

if [[ "$check_only" == false ]]; then
  "$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" \
    --prepare-cache --destination "$repo_root"
fi

shared_graphify_semantic_cache="$(realpath_portable "$shared_graphify_semantic_cache")"
shared_graphify_semantic_deep_cache="$(realpath_portable "$shared_graphify_semantic_deep_cache")"
[[ -d "$shared_graphify_semantic_cache" ]] || fail "shared Graphify semantic cache is missing: $shared_root/graphify-out/cache/semantic"
[[ -d "$shared_graphify_semantic_deep_cache" ]] || fail "shared Graphify semantic-deep cache is missing: $shared_root/graphify-out/cache/semantic-deep"

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
  mkdir -p .data docs/literature
fi

# Download manifests are tracked; every other top-level .data directory is an
# ignored cache and can be shared before rebuilding the deterministic Graphify
# projection. PDF presence participates in that projection, so link it before
# reconciliation rather than after it.
while IFS= read -r -d '' source; do
  link_or_check "$source" ".data/$(basename "$source")"
done < <(find "$shared_root/.data" -mindepth 1 -maxdepth 1 -type d \
  ! -name aria_download_urls ! -name graphify-semantic-cache -print0)

if [[ -e "$shared_root/docs/literature/pdf" ]]; then
  link_or_check "$shared_root/docs/literature/pdf" "docs/literature/pdf"
fi

# Seed durable Graphify state from a sibling Git worktree. The helper copies a
# strict allowlist and synthesizes child metadata; cache links below are the
# only shared Graphify state.
seed_args=(--source "$shared_root" --destination "$repo_root")
seed_args+=(--destination-git-dir "$repo_git_dir")
[[ "$check_only" == true ]] && seed_args+=(--check)
"$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" "${seed_args[@]}"

if [[ "$check_only" == false ]]; then
  "$shared_python" "$repo_root/scripts/reconcile_graphify_worktree.py" --root "$repo_root"
else
  "$shared_python" "$repo_root/scripts/check_graphify_freshness.py" --usable --quiet || \
    fail "seeded Graphify generation is not query-admissible"
fi

# These content-addressed semantic results are the only Graphify state shared
# between worktrees. Graphs, manifests, projections, AST state, and run state
# stay local. Clearing either cache increases future extraction cost everywhere
# but cannot make a stale graph current.
"$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" \
  --prepare-cache --destination "$repo_root" --check
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
