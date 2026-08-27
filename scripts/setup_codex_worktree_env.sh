#!/usr/bin/env bash
# Resolve Codex's optional fork parent before running the strict setup owner.
set -euo pipefail

# Git hooks export these for their own administrative directory.  This setup
# script deliberately addresses several distinct worktrees, so inherited hook
# bindings would make topology queries target the committing child instead.
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

git_at() {
  local git_dir="$1" worktree="$2"
  shift 2
  git -c core.worktree="$worktree" --git-dir="$git_dir" --work-tree="$worktree" "$@"
}

repo_git_dir="$(git_dir_for_worktree "$repo_root")" || {
  printf 'error: destination Git metadata is unavailable for Codex worktree setup\n' >&2
  exit 1
}

explicit_parent="${CODEX_SOURCE_WORKSPACE_PATH:-}"
maintain=false
check_only=false

for argument in "$@"; do
  case "$argument" in
    --maintain) maintain=true ;;
    --check) check_only=true ;;
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

  common_dir="$(git_at "$repo_git_dir" "$repo_root" rev-parse --git-common-dir)" || \
    fail "Git metadata is unavailable for Codex worktree setup"
  [[ "$common_dir" = /* ]] || common_dir="$repo_root/$common_dir"
  common_dir="$(cd "$common_dir" && pwd -P)"
  candidate="$(cd "$(dirname "$common_dir")" && pwd -P)"
  candidate_git_dir="$(git_dir_for_worktree "$candidate")" || \
    fail "Git's canonical primary worktree is unavailable"
  candidate_common_dir="$(git_at "$candidate_git_dir" "$candidate" rev-parse --git-common-dir 2>/dev/null)" || \
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
  done < <(git_at "$repo_git_dir" "$repo_root" worktree list --porcelain)
  fail "Git's canonical primary worktree is not registered"
}

validate_canonical_cache_topology() {
  local primary="$1" allow_missing="$2" primary_git_dir primary_common_dir expected_common_dir cache_path line

  [[ -n "$primary" && -d "$primary" ]] || fail "canonical primary worktree is unavailable"
  primary="$(cd "$primary" && pwd -P)"
  primary_git_dir="$(git_dir_for_worktree "$primary")" || \
    fail "canonical primary worktree is not a Git worktree"
  primary_common_dir="$(git_at "$primary_git_dir" "$primary" \
    rev-parse --git-common-dir 2>/dev/null)" || fail "canonical primary Git metadata is unavailable"
  [[ "$primary_common_dir" = /* ]] || primary_common_dir="$primary/$primary_common_dir"
  primary_common_dir="$(cd "$primary_common_dir" && pwd -P)"
  expected_common_dir="$(git_at "$repo_git_dir" "$repo_root" rev-parse --git-common-dir)" || \
    fail "destination Git metadata is unavailable"
  [[ "$expected_common_dir" = /* ]] || expected_common_dir="$repo_root/$expected_common_dir"
  expected_common_dir="$(cd "$expected_common_dir" && pwd -P)"
  [[ "$primary_common_dir" == "$expected_common_dir" && -d "$primary/.git" ]] || \
    fail "canonical primary worktree does not own this repository"
  while IFS= read -r line; do
    [[ "$line" == "worktree $primary" ]] && break
  done < <(git_at "$primary_git_dir" "$primary" worktree list --porcelain)
  [[ "${line:-}" == "worktree $primary" ]] || fail "canonical primary worktree is not registered"
  for cache_path in "$primary/.data/graphify-semantic-cache" \
    "$primary/.data/graphify-semantic-cache/semantic" \
    "$primary/.data/graphify-semantic-cache/semantic-deep"; do
    [[ "$allow_missing" == true && ! -e "$cache_path" && ! -L "$cache_path" ]] && continue
    [[ ! -L "$cache_path" && -d "$cache_path" ]] || \
      fail "canonical Graphify cache is missing or unsafe: $cache_path"
  done
}

prepare_canonical_cache() {
  local primary="$1"
  validate_canonical_cache_topology "$primary" true
  [[ ! -e "$primary/.data" || ( ! -L "$primary/.data" && -d "$primary/.data" ) ]] || \
    fail "canonical Graphify cache is missing or unsafe: $primary/.data"
  mkdir -p "$primary/.data/graphify-semantic-cache/semantic" \
    "$primary/.data/graphify-semantic-cache/semantic-deep"
  validate_canonical_cache_topology "$primary" false
}

maintain_graphify() {
  local primary
  primary="$(canonical_primary_worktree)"
  prepare_canonical_cache "$primary"
  if [[ "$repo_root" != "$primary" ]]; then
    python3 "$repo_root/scripts/graphify_worktree_seed.py" --check-owned \
      --destination "$repo_root" --destination-git-dir "$repo_git_dir" \
      --canonical-cache-root "$primary/.data/graphify-semantic-cache" \
      >/dev/null 2>&1 || \
      fail "linked worktree Graphify seed is invalid; rerun Codex worktree setup"
  fi
  if ! python3 "$repo_root/scripts/reconcile_graphify_worktree.py" \
    --root "$repo_root" >/dev/null 2>&1; then
    fail "Graphify admission maintenance failed; rerun Codex worktree setup"
  fi
}

candidate_rank() {
  local candidate="$1" destination_head="$2" candidate_git_dir candidate_common_dir candidate_head distance

  [[ -n "$candidate" && "$candidate" != "$repo_root" && -d "$candidate" ]] || return 1
  candidate="$(cd "$candidate" && pwd -P)"
  candidate_git_dir="$(git_dir_for_worktree "$candidate")" || return 1
  candidate_common_dir="$(git_at "$candidate_git_dir" "$candidate" rev-parse --git-common-dir)" || return 1
  [[ "$candidate_common_dir" = /* ]] || candidate_common_dir="$candidate/$candidate_common_dir"
  candidate_common_dir="$(cd "$candidate_common_dir" && pwd -P)" || return 1
  [[ "$candidate_common_dir" == "$common_dir" ]] || return 1
  candidate_head="$(git_at "$candidate_git_dir" "$candidate" \
    rev-parse --verify HEAD^{commit} 2>/dev/null)" || return 1
  if [[ "$candidate_head" == "$destination_head" ]]; then
    printf '0\t%s\n' "$candidate"
    return 0
  fi
  git_at "$candidate_git_dir" "$candidate" \
    merge-base --is-ancestor "$candidate_head" "$destination_head" >/dev/null 2>&1 || return 1
  distance="$(git_at "$candidate_git_dir" "$candidate" \
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
  destination_head="$(git_at "$repo_git_dir" "$repo_root" rev-parse --verify HEAD^{commit})" || \
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
  done < <(git_at "$repo_git_dir" "$repo_root" worktree list --porcelain)
  emit_candidate
}

parentless_worktree() {
  local primary candidates distance candidate
  primary="$(canonical_primary_worktree)"
  if candidate_usable "$primary"; then
    printf '%s\n' "$primary"
    return 0
  fi

  candidates="$(registered_sibling_ranks "$primary" | LC_ALL=C sort -t $'\t' -k1,1n -k2,2)"
  [[ -n "$candidates" ]] || fail \
    "no query-admissible registered Graphify parent; refresh the canonical primary or an eligible ancestor worktree"
  while IFS=$'\t' read -r distance candidate; do
    [[ -n "$distance" && -n "$candidate" ]] || continue
    if candidate_usable "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done <<<"$candidates"
  fail "no query-admissible registered Graphify parent; refresh the canonical primary or an eligible ancestor worktree"
}

# A non-empty Codex source is the actual fork parent and therefore always wins.
# Codex 0.149.1 may omit it for project-created worktrees; only then fall back
# to the nearest query-admissible registered ancestor worktree. Equally near
# candidates use the stable worktree-path ordering established above.
# The strict setup owner validates both topology and Graphify admission.
validated_modes="$(validated_graphify_modes)"

if [[ "$maintain" == true ]]; then
  maintain_graphify
  exit 0
fi

shared_root="$explicit_parent"
canonical_primary="$(canonical_primary_worktree)"
cache_may_be_missing=false
[[ "$check_only" == false ]] && cache_may_be_missing=true
validate_canonical_cache_topology "$canonical_primary" "$cache_may_be_missing"
if [[ -z "$shared_root" ]]; then
  common_dir="$(git_at "$repo_git_dir" "$repo_root" rev-parse --git-common-dir)" || \
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
