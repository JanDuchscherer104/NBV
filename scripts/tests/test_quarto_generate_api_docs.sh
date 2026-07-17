#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
SANDBOX="$(mktemp -d)"
trap 'rm -rf "${SANDBOX}"' EXIT

mkdir -p "${SANDBOX}/scripts" "${SANDBOX}/docs/reference"
cp "${REPO_ROOT}/scripts/quarto_generate_api_docs.sh" "${SANDBOX}/scripts/"
touch "${SANDBOX}/docs/_quarto.yml"
touch "${SANDBOX}/docs/reference/stale.symbol.qmd"

FAKE_PYTHON="${SANDBOX}/fake-python"
cat >"${FAKE_PYTHON}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-m" && "${2:-}" == "quartodoc" && "${3:-}" == "--help" ]]; then
  exit 0
fi

if [[ "${1:-}" == *"quartodoc_expand_config.py" ]]; then
  while [[ "$#" -gt 0 ]]; do
    if [[ "$1" == "--output" ]]; then
      : >"$2"
      exit 0
    fi
    shift
  done
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "quartodoc" && "${3:-}" == "build" ]]; then
  count=0
  if [[ -f "${QUARTODOC_TEST_COUNT}" ]]; then
    count="$(<"${QUARTODOC_TEST_COUNT}")"
  fi
  count=$((count + 1))
  printf '%s\n' "${count}" >"${QUARTODOC_TEST_COUNT}"
  if [[ "${count}" -eq 1 ]]; then
    echo "AliasResolutionError: Could not resolve alias stale.symbol pointing at aria_nbv.missing.Symbol" >&2
    exit 1
  fi
  exit 0
fi

exit 0
EOF
chmod +x "${FAKE_PYTHON}"

COUNT_FILE="${SANDBOX}/quartodoc-build-count"
OUTPUT="$({
  QUARTO_PYTHON="${FAKE_PYTHON}" \
    QUARTODOC_TEST_COUNT="${COUNT_FILE}" \
    QUARTODOC_INCREMENTAL=1 \
    QUARTODOC_INTERLINKS=0 \
    bash "${SANDBOX}/scripts/quarto_generate_api_docs.sh"
} 2>&1)"

[[ "$(<"${COUNT_FILE}")" == "2" ]]
[[ ! -e "${SANDBOX}/docs/reference/stale.symbol.qmd" ]]
grep -Fq "Pruned stale symbol page:" <<<"${OUTPUT}"
grep -Fq "Recovered from stale-symbol alias failures during regeneration." <<<"${OUTPUT}"
if grep -Fq "retrying would be a guess" <<<"${OUTPUT}"; then
  echo "stale alias recovery incorrectly reported that no page was removed" >&2
  exit 1
fi

echo "Quartodoc stale-alias recovery: PASS"
