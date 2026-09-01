#!/usr/bin/env bash
# Configure a linked ARIA-NBV worktree without copying the runtime or data cache.
set -euo pipefail

# See the public Codex boundary: hook-provided bindings are valid only for the
# hook's administrative directory, not for the independent parent and primary
# worktree topology checks below.
unset GIT_DIR GIT_WORK_TREE

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

git_dir_for_worktree() {
  local worktree="$1" marker gitdir
  marker="$worktree/.git"
  if [[ -d "$marker" ]]; then
    printf '%s\n' "$marker"
    return 0
  fi
  [[ -f "$marker" ]] || return 1
  IFS= read -r gitdir <"$marker" || return 1
  [[ "$gitdir" == "gitdir: "* ]] || return 1
  gitdir="${gitdir#gitdir: }"
  [[ "$gitdir" = /* ]] || gitdir="$worktree/$gitdir"
  cd "$gitdir" && pwd -P
}

repo_git_dir="$(git_dir_for_worktree "$repo_root")" || {
  printf 'error: destination Git metadata is unavailable\n' >&2
  exit 1
}
shared_root="${ARIA_NBV_SHARED_ROOT:-}"
canonical_primary="${ARIA_NBV_CANONICAL_PRIMARY:-}"
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
  git -c core.worktree="$repo_root" --git-dir="$repo_git_dir" --work-tree="$repo_root" "$@"
}

[[ -n "$shared_root" ]] || fail "ARIA_NBV_SHARED_ROOT must identify the parent worktree"
[[ -d "$shared_root" ]] || fail "shared root does not exist: $shared_root"
shared_root="$(cd "$shared_root" && pwd -P)"
[[ "$shared_root" != "$repo_root" ]] || fail "shared root must be another worktree"
source_git_dir="$(git_dir_for_worktree "$shared_root")" || \
  fail "shared root is not a Git worktree; cannot seed Graphify"
source_common_dir="$(git -c core.worktree="$shared_root" --git-dir="$source_git_dir" --work-tree="$shared_root" \
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
done < <(git -c core.worktree="$shared_root" --git-dir="$source_git_dir" --work-tree="$shared_root" worktree list --porcelain)
[[ "$registered_source" == true && "$registered_destination" == true ]] || \
  fail "source and destination must both be registered Git worktrees"

# Cache identity belongs to the registered primary checkout, not to whichever
# sibling was selected to provide inherited Graphify artifacts.  Authenticate
# it before invoking a parent runtime or mutating the destination.
[[ -n "$canonical_primary" && -d "$canonical_primary" ]] || \
  fail "canonical primary worktree is unavailable"
canonical_primary="$(cd "$canonical_primary" && pwd -P)"
canonical_git_dir="$(git_dir_for_worktree "$canonical_primary")" || \
  fail "canonical primary worktree is not a Git worktree"
canonical_common_dir="$(git -c core.worktree="$canonical_primary" --git-dir="$canonical_git_dir" --work-tree="$canonical_primary" \
  rev-parse --git-common-dir 2>/dev/null)" || fail "canonical primary Git metadata is unavailable"
[[ "$canonical_common_dir" = /* ]] || canonical_common_dir="$canonical_primary/$canonical_common_dir"
canonical_common_dir="$(cd "$canonical_common_dir" && pwd -P)"
[[ "$canonical_common_dir" == "$destination_common_dir" && -d "$canonical_primary/.git" ]] || \
  fail "canonical primary worktree does not own this repository"
registered_primary=false
while IFS= read -r worktree_line; do
  [[ "$worktree_line" == "worktree $canonical_primary" ]] && registered_primary=true
done < <(git -c core.worktree="$canonical_primary" --git-dir="$canonical_git_dir" --work-tree="$canonical_primary" worktree list --porcelain)
[[ "$registered_primary" == true ]] || fail "canonical primary worktree is not registered"
canonical_cache_root="$canonical_primary/.data/graphify-semantic-cache"
for cache_path in "$canonical_primary/.data" "$canonical_cache_root" \
  "$canonical_cache_root/semantic" "$canonical_cache_root/semantic-deep"; do
  if [[ "$check_only" == true || -e "$cache_path" || -L "$cache_path" ]]; then
    [[ ! -L "$cache_path" && -d "$cache_path" ]] || \
      fail "canonical Graphify cache is missing or unsafe: $cache_path"
  fi
done
if [[ "$check_only" == false ]]; then
  mkdir -p "$canonical_cache_root/semantic" "$canonical_cache_root/semantic-deep"
fi

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

shared_graphify_semantic_cache="$canonical_cache_root/semantic"
shared_graphify_semantic_deep_cache="$canonical_cache_root/semantic-deep"

if [[ "$check_only" == false ]]; then
  "$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" \
    --prepare-cache --destination "$repo_root" \
    --canonical-cache-root "$canonical_cache_root"
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

# A tracked paper must remain an exact local checkout input. Older revisions
# ignored this directory wholesale and could share it as one cache symlink;
# mixed tracked/untracked directories cannot safely be replaced that way.
tracked_pdf_inputs="$(git_in_worktree ls-files -- docs/literature/pdf)"
if [[ -n "$tracked_pdf_inputs" ]]; then
  [[ -d docs/literature/pdf && ! -L docs/literature/pdf ]] || \
    fail "tracked PDF inputs require a local docs/literature/pdf directory"
elif [[ -e "$shared_root/docs/literature/pdf" ]]; then
  link_or_check "$shared_root/docs/literature/pdf" "docs/literature/pdf"
fi

# Seed durable Graphify state from a sibling Git worktree. The helper copies a
# strict allowlist and synthesizes child metadata; cache links below are the
# only shared Graphify state.
seed_args=(--source "$shared_root" --destination "$repo_root")
seed_args+=(--destination-git-dir "$repo_git_dir")
seed_args+=(--canonical-cache-root "$canonical_cache_root")
[[ "$check_only" == true ]] && seed_args+=(--check)
"$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" "${seed_args[@]}"

if [[ "$check_only" == false ]]; then
  # Worktree creation is a deterministic bootstrap.  Retain a valid inherited
  # graph when only its semantic namespaces are stale; Codex-owned maintenance
  # performs the upstream semantic refresh after the session starts.
  "$shared_python" "$repo_root/scripts/reconcile_graphify_worktree.py" \
    --root "$repo_root" --prepare-only
  "$shared_python" "$repo_root/scripts/check_graphify_freshness.py" --usable --quiet || \
    fail "seeded Graphify generation is not query-admissible"
else
  "$shared_python" "$repo_root/scripts/check_graphify_freshness.py" --usable --quiet || \
    fail "seeded Graphify generation is not query-admissible"
fi

# These content-addressed semantic results are the only Graphify state shared
# between worktrees. Graphs, manifests, projections, AST state, and run state
# stay local. Clearing either cache increases future extraction cost everywhere
# but cannot make a stale graph current.
"$shared_python" "$repo_root/scripts/graphify_worktree_seed.py" \
  --prepare-cache --destination "$repo_root" \
  --canonical-cache-root "$canonical_cache_root" --check
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
