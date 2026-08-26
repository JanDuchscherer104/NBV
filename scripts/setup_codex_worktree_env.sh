#!/usr/bin/env bash
# Resolve Codex's optional fork parent before running the strict setup owner.
set -euo pipefail

# Git hooks export these for their own administrative directory.  This setup
# script deliberately addresses several distinct worktrees, so inherited hook
# bindings would make every `git -C` query target the committing child instead.
unset GIT_DIR GIT_WORK_TREE

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
explicit_parent="${CODEX_SOURCE_WORKSPACE_PATH:-}"
maintain=false

for argument in "$@"; do
  case "$argument" in
    --maintain) maintain=true ;;
    --quiet) ;;
    *) ;;
  esac
done

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

validated_graphify_modes() {
  local modes
  if [[ -v ARIA_NBV_GRAPHIFY_MODES ]]; then
    modes="$ARIA_NBV_GRAPHIFY_MODES"
  else
    modes="standard"
  fi
  case "$modes" in
    standard|deep|standard,deep) printf '%s\n' "$modes" ;;
    *) fail "ARIA_NBV_GRAPHIFY_MODES must be standard, deep, or standard,deep" ;;
  esac
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

validate_canonical_cache_topology() {
  local primary="$1" primary_git_dir primary_common_dir expected_common_dir cache_path line

  [[ -n "$primary" && -d "$primary" ]] || fail "canonical primary worktree is unavailable"
  primary="$(cd "$primary" && pwd -P)"
  primary_git_dir="$(git -C "$primary" rev-parse --absolute-git-dir 2>/dev/null)" || \
    fail "canonical primary worktree is not a Git worktree"
  primary_common_dir="$(git --git-dir="$primary_git_dir" --work-tree="$primary" \
    rev-parse --git-common-dir 2>/dev/null)" || fail "canonical primary Git metadata is unavailable"
  [[ "$primary_common_dir" = /* ]] || primary_common_dir="$primary/$primary_common_dir"
  primary_common_dir="$(cd "$primary_common_dir" && pwd -P)"
  expected_common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)" || \
    fail "destination Git metadata is unavailable"
  [[ "$expected_common_dir" = /* ]] || expected_common_dir="$repo_root/$expected_common_dir"
  expected_common_dir="$(cd "$expected_common_dir" && pwd -P)"
  [[ "$primary_common_dir" == "$expected_common_dir" && -d "$primary/.git" ]] || \
    fail "canonical primary worktree does not own this repository"
  while IFS= read -r line; do
    [[ "$line" == "worktree $primary" ]] && break
  done < <(git --git-dir="$primary_git_dir" --work-tree="$primary" worktree list --porcelain)
  [[ "${line:-}" == "worktree $primary" ]] || fail "canonical primary worktree is not registered"
  for cache_path in "$primary/.data/graphify-semantic-cache" \
    "$primary/.data/graphify-semantic-cache/semantic" \
    "$primary/.data/graphify-semantic-cache/semantic-deep"; do
    [[ ! -L "$cache_path" && -d "$cache_path" ]] || \
      fail "canonical Graphify cache is missing or unsafe: $cache_path"
  done
}

maintain_graphify() {
  local primary
  primary="$(canonical_primary_worktree)"
  validate_canonical_cache_topology "$primary"
  if ! python3 "$repo_root/scripts/reconcile_graphify_worktree.py" \
    --root "$repo_root" >/dev/null 2>&1; then
    fail "Graphify admission maintenance failed; rerun Codex worktree setup"
  fi
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
validated_modes="$(validated_graphify_modes)"

if [[ "$maintain" == true ]]; then
  maintain_graphify
  exit 0
fi

shared_root="$explicit_parent"
canonical_primary="$(canonical_primary_worktree)"
validate_canonical_cache_topology "$canonical_primary"
if [[ -z "$shared_root" ]]; then
  common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)" || \
    fail "Git metadata is unavailable for Codex worktree setup"
  [[ "$common_dir" = /* ]] || common_dir="$repo_root/$common_dir"
  common_dir="$(cd "$common_dir" && pwd -P)"
  shared_root="$(parentless_worktree)"
fi

if ! setup_output="$(ARIA_NBV_SHARED_ROOT="$shared_root" \
  ARIA_NBV_CANONICAL_PRIMARY="$canonical_primary" \
  ARIA_NBV_GRAPHIFY_MODES="$validated_modes" \
  bash "$repo_root/scripts/setup_worktree_env.sh" "$@" 2>&1)"; then
  setup_error="$(printf '%s\n' "$setup_output" | sed -n 's/^error: //p' | tail -n 1)"
  fail "${setup_error:-Codex worktree setup failed; rerun setup after repairing Graphify admission}"
fi
