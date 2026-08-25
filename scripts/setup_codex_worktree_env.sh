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

candidate_rank() {
  local candidate="$1" destination_head="$2" candidate_git_dir candidate_common_dir candidate_head distance

  [[ -n "$candidate" && "$candidate" != "$repo_root" && -d "$candidate" ]] || return 1
  candidate="$(cd "$candidate" && pwd -P)"
  candidate_git_dir="$(git -C "$candidate" rev-parse --absolute-git-dir 2>/dev/null)" || return 1
  candidate_common_dir="$(git -C "$candidate" rev-parse --git-common-dir 2>/dev/null)" || return 1
  [[ "$candidate_common_dir" = /* ]] || candidate_common_dir="$candidate/$candidate_common_dir"
  candidate_common_dir="$(cd "$candidate_common_dir" && pwd -P)" || return 1
  [[ "$candidate_common_dir" == "$common_dir" ]] || return 1
  candidate_head="$(git --git-dir="$candidate_git_dir" --work-tree="$candidate" \
    rev-parse --verify HEAD^{commit} 2>/dev/null)" || return 1
  if [[ "$candidate_head" == "$destination_head" ]]; then
    printf '0\t%s\n' "$candidate"
    return 0
  fi
  git --git-dir="$candidate_git_dir" --work-tree="$candidate" \
    merge-base --is-ancestor "$candidate_head" "$destination_head" >/dev/null 2>&1 || return 1
  distance="$(git --git-dir="$candidate_git_dir" --work-tree="$candidate" \
    rev-list --count "$candidate_head..$destination_head" 2>/dev/null)" || return 1
  [[ "$distance" =~ ^[0-9]+$ ]] || return 1
  printf '%s\t%s\n' "$distance" "$candidate"
}

candidate_usable() {
  local candidate="$1"
  (
    cd "$candidate"
    python3 -I "$repo_root/scripts/check_graphify_freshness.py" --usable --quiet
  ) >/dev/null 2>&1
}

registered_sibling_ranks() {
  local excluded="$1" destination_head line candidate="" prunable=false rank
  destination_head="$(git -C "$repo_root" rev-parse --verify HEAD^{commit})" || \
    fail "destination Git HEAD is unavailable for Codex worktree setup"

  emit_candidate() {
    [[ -n "$candidate" && "$candidate" != "$excluded" && "$prunable" == false ]] || return 0
    rank="$(candidate_rank "$candidate" "$destination_head")" || return 0
    printf '%s\n' "$rank"
  }

  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      "worktree "*)
        emit_candidate
        candidate="${line#worktree }"
        prunable=false
        ;;
      "prunable "*) prunable=true ;;
      "")
        emit_candidate
        candidate=""
        prunable=false
        ;;
    esac
  done < <(git -C "$repo_root" worktree list --porcelain)
  emit_candidate
}

parentless_worktree() {
  local primary candidates best_distance selected_count selected line distance candidate
  primary="$(canonical_primary_worktree)"
  if candidate_usable "$primary"; then
    printf '%s\n' "$primary"
    return 0
  fi

  candidates="$(registered_sibling_ranks "$primary" | LC_ALL=C sort -t $'\t' -k1,1n -k2,2)"
  [[ -n "$candidates" ]] || fail \
    "no query-admissible registered Graphify parent; refresh the canonical primary or an eligible ancestor worktree"
  best_distance=""
  selected=""
  selected_count=0
  while IFS=$'\t' read -r distance candidate; do
    [[ -n "$distance" && -n "$candidate" ]] || continue
    if [[ -n "$best_distance" && "$distance" != "$best_distance" ]]; then
      [[ "$selected_count" -eq 0 ]] || break
    fi
    if [[ -z "$best_distance" || "$distance" != "$best_distance" ]]; then
      best_distance="$distance"
      selected=""
      selected_count=0
    fi
    if candidate_usable "$candidate"; then
      selected="$candidate"
      selected_count=$((selected_count + 1))
    fi
  done <<<"$candidates"
  [[ "$selected_count" -gt 0 ]] || fail \
    "no query-admissible registered Graphify parent; refresh the canonical primary or an eligible ancestor worktree"
  [[ "$selected_count" -eq 1 ]] || fail \
    "ambiguous query-admissible Graphify parent candidates at Git distance $best_distance; set CODEX_SOURCE_WORKSPACE_PATH explicitly"
  printf '%s\n' "$selected"
}

# A non-empty Codex source is the actual fork parent and therefore always wins.
# Codex 0.149.1 may omit it for project-created worktrees; only then fall back
# to an unambiguous, query-admissible registered ancestor worktree.
# The strict setup owner validates both topology and Graphify admission.
shared_root="$explicit_parent"
if [[ -z "$shared_root" ]]; then
  common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)" || \
    fail "Git metadata is unavailable for Codex worktree setup"
  [[ "$common_dir" = /* ]] || common_dir="$repo_root/$common_dir"
  common_dir="$(cd "$common_dir" && pwd -P)"
  shared_root="$(parentless_worktree)"
fi

ARIA_NBV_SHARED_ROOT="$shared_root" \
  exec bash "$repo_root/scripts/setup_worktree_env.sh" "$@"
