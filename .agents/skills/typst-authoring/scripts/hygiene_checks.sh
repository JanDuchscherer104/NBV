#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: hygiene_checks.sh [--strict|--examples] [paths...]

Modes:
  default     Advisory checks for real documents; exits zero.
  --strict    Fail if suspicious matches are found in real documents.
  --examples  Include skill fixtures/examples; exits zero.

Examples:
  .agents/skills/typst-authoring/scripts/hygiene_checks.sh docs/typst/thesis
  .agents/skills/typst-authoring/scripts/hygiene_checks.sh --strict docs/typst/thesis/sections
  .agents/skills/typst-authoring/scripts/hygiene_checks.sh --examples .agents/skills/typst-authoring
EOF
}

mode="soft"
targets=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      mode="strict"
      shift
      ;;
    --examples)
      mode="examples"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      targets+=("$1")
      shift
      ;;
  esac
done

if [[ ${#targets[@]} -eq 0 ]]; then
  if [[ "$mode" == "examples" ]]; then
    targets=(.agents/skills/typst-authoring)
  else
    targets=(docs/typst/thesis)
  fi
fi

echo "== Typst authoring hygiene checks =="
echo "Mode: $mode"
echo "Targets: ${targets[*]}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
authoring_test="$repo_root/scripts/tests/test_typst_authoring_hygiene.py"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) not available; skipping pattern checks" >&2
  exit 0
fi

if [[ "$mode" == "strict" && -f "$authoring_test" ]]; then
  python3 "$authoring_test" --scan "${targets[@]}"
fi

exclude_args=()
if [[ "$mode" != "examples" ]]; then
  exclude_args+=(
    --glob '!**/assets/fixtures/**'
    --glob '!**/assets/templates/**'
    --glob '!**/issues.md'
    --glob '!**/references/math-attachments.md'
    --glob '!**/references/notation-migration.md'
    --glob '!**/*.generated.typ'
    --glob '!**/*.mmd'
    --glob '!**/*.svg'
    --glob '!**/*.png'
    --glob '!**/*.pdf'
  )
else
  exclude_args+=(
    --glob '!**/references/packages/**'
    --glob '!**/scripts/**'
  )
fi

found_any=0
found_blocking=0

run_check() {
  local title="$1"
  local pattern="$2"
  local severity="${3:-blocking}"
  local status=0

  echo
  echo "-- $title [$severity] --"
  if rg -n "${exclude_args[@]}" "$pattern" "${targets[@]}"; then
    found_any=1
    if [[ "$severity" == "blocking" ]]; then
      found_blocking=1
    fi
  else
    status=$?
    if [[ $status -eq 1 ]]; then
      echo "no matches"
    else
      echo "rg failed with status $status" >&2
      exit "$status"
    fi
  fi
}

run_check "Typst operator attachment followed immediately by arguments" \
  'op\("[^"]+"\)_[^[:space:]]+\('

run_check "Accidental double bolding" \
  'bold\(bold'

run_check "Locked ARIA-NBV notation convention violations" \
  'bold\(cal\(|bold\(Q\)_t|bold\(s\)_t\^"(obs|cf0|cf\+|oracle)"|bold\(q\)_\(t,|S O\(2\)|cal\(A\)_t\^e|cal\(C\)_t\^e'

run_check "Raw LaTeX leakage" \
  '\\(mathbf|mathcal|mathrm|operatorname|textbf)|cal\{' \
  advisory

run_check "Temporary citation placeholders" \
  '\[CITATION NEEDED|TODO citation|citation needed|TODO: cite|FIXME citation'

run_check "Stale global skill paths inside repo-local guidance" \
  '[.]codex/skills/typst-authoring'

run_check "Recurring proposal notation that should use shared modules when edited" \
  'bold\(z\)_e|Q_\(H,theta\)|Delta_t\^e|J_e\^\(H\)|G_t\^\(H\)|bold\(F\)_t\^"EVL"|bold\(O\)_t\^"pred"' \
  advisory

run_check "Image includes without same-line width argument" \
  'image\("[^"]+"\)' \
  advisory

run_check "Unprefixed Typst labels" \
  '<[[:alpha:]][[:alnum:]_-]*>' \
  advisory

echo
if [[ "$mode" == "strict" && "$found_blocking" -ne 0 ]]; then
  echo "Strict hygiene failed. Review blocking matches above; do not suppress real document issues silently." >&2
  exit 1
fi

echo "Done. Advisory matches are review prompts; strict mode fails only on blocking checks."
