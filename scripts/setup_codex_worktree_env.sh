#!/usr/bin/env bash
# Resolve Codex's optional fork parent before running the strict setup owner.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
explicit_parent="${CODEX_SOURCE_WORKSPACE_PATH:-}"

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

canonical_primary_worktree() {
  local common_dir candidate candidate_git_dir candidate_common_dir line

  common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)" || \
    fail "Git metadata is unavailable for Codex worktree setup"
  [[ "$common_dir" = /* ]] || common_dir="$repo_root/$common_dir"
  common_dir="$(cd "$common_dir" && pwd -P)"
  candidate="$(cd "$(dirname "$common_dir")" && pwd -P)"
  candidate_git_dir="$(git -C "$candidate" rev-parse --absolute-git-dir 2>/dev/null)" || \
    fail "Git's canonical primary worktree is unavailable"
  candidate_common_dir="$(git -C "$candidate" rev-parse --git-common-dir 2>/dev/null)" || \
    fail "Git's canonical primary worktree is unavailable"
  [[ "$candidate_common_dir" = /* ]] || candidate_common_dir="$candidate/$candidate_common_dir"
  candidate_common_dir="$(cd "$candidate_common_dir" && pwd -P)"
  [[ "$candidate_git_dir" == "$common_dir" && "$candidate_common_dir" == "$common_dir" ]] || \
    fail "Git's canonical primary worktree does not own this repository"
  [[ -d "$candidate/.git" ]] || \
    fail "Git's canonical primary worktree is not a primary checkout"

  while IFS= read -r line; do
    [[ "$line" == "worktree $candidate" ]] && {
      printf '%s\n' "$candidate"
      return 0
    }
  done < <(git -C "$repo_root" worktree list --porcelain)
  fail "Git's canonical primary worktree is not registered"
}

# A non-empty Codex source is the actual fork parent and therefore always wins.
# Codex 0.149.1 may omit it for project-created worktrees; only then fall back
# to Git's canonical primary checkout, never an arbitrary registered worktree.
# The strict setup owner validates both topology and Graphify admission.
shared_root="$explicit_parent"
if [[ -z "$shared_root" ]]; then
  shared_root="$(canonical_primary_worktree)"
fi

ARIA_NBV_SHARED_ROOT="$shared_root" \
  exec bash "$repo_root/scripts/setup_worktree_env.sh" "$@"
