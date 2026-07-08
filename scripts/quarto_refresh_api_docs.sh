#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCS_DIR="${REPO_ROOT}/docs"
REFERENCE_DIR="${DOCS_DIR}/reference"
TMP_DIR="$(mktemp -d)"
BEFORE="${TMP_DIR}/before.sha256"
AFTER="${TMP_DIR}/after.sha256"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

snapshot_reference_pages() {
  if [[ ! -d "${REFERENCE_DIR}" ]]; then
    return
  fi

  find "${REFERENCE_DIR}" -maxdepth 1 -type f \
    \( -name "*.qmd" -o -name "_api_index.md" -o -name "_sidebar.yml" \) -print0 \
    | sort -z \
    | xargs -0 --no-run-if-empty sha256sum \
    | sed "s#  ${REPO_ROOT}/##"
}

changed_reference_pages() {
  comm -13 <(sort "${BEFORE}") <(sort "${AFTER}") \
    | awk '{ print $2 }'
}

render_pages() {
  local pages=("$@")
  if [[ "${#pages[@]}" -eq 0 ]]; then
    echo "No changed API reference pages to render."
    return
  fi

  (
    cd "${DOCS_DIR}"
    quarto render "${pages[@]}" --no-clean --no-execute
  )
}

mkdir -p "${REFERENCE_DIR}"
snapshot_reference_pages > "${BEFORE}"

QUARTODOC_FILTER="${API_FILTER:-${QUARTODOC_FILTER:-}}" \
QUARTODOC_INCREMENTAL=1 \
"${SCRIPT_DIR}/quarto_generate_api_docs.sh"

snapshot_reference_pages > "${AFTER}"

if [[ -n "${API_PAGES:-}" ]]; then
  # shellcheck disable=SC2206
  PAGES=(${API_PAGES})
else
  PAGES=()
  mapfile -t CHANGED_PAGES < <(changed_reference_pages)
  for page in "${CHANGED_PAGES[@]}"; do
    case "${page}" in
      docs/reference/_api_index.md|docs/reference/_sidebar.yml)
        PAGES+=("docs/reference/index.qmd")
        ;;
      *.qmd)
        PAGES+=("${page}")
        ;;
    esac
  done
fi

RELATIVE_PAGES=()
declare -A SEEN_PAGES=()
for page in "${PAGES[@]}"; do
  page="${page#${DOCS_DIR}/}"
  page="${page#docs/}"
  if [[ -n "${SEEN_PAGES[${page}]:-}" ]]; then
    continue
  fi
  SEEN_PAGES["${page}"]=1
  RELATIVE_PAGES+=("${page}")
done

render_pages "${RELATIVE_PAGES[@]}"
