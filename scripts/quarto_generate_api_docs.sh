#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCS_DIR="${REPO_ROOT}/docs"
REFERENCE_DIR="${DOCS_DIR}/reference"
PYTHON_BIN=""
TMP_LOG="$(mktemp)"
TMP_CONFIG=""
QUARTODOC_ARGS=()

# PEP 660 editable finders may point the shared environment at a different
# checkout. Put this worktree's package root on Python's startup path; adding
# Quartodoc's source_dir later is too late to override an installed finder.
export PYTHONPATH="${REPO_ROOT}/aria_nbv${PYTHONPATH:+:${PYTHONPATH}}"

cd "${DOCS_DIR}"
mkdir -p reference

cleanup() {
  rm -f "${TMP_LOG}"
  if [[ -n "${TMP_CONFIG}" ]]; then
    rm -f "${TMP_CONFIG}"
  fi
}
trap cleanup EXIT

if [[ -n "${QUARTO_PYTHON:-}" && -x "${QUARTO_PYTHON}" ]]; then
  PYTHON_BIN="${QUARTO_PYTHON}"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -x "${REPO_ROOT}/aria_nbv/.venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/aria_nbv/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Could not find a Python executable for docs generation." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -m quartodoc --help >/dev/null 2>&1; then
  if command -v uvx >/dev/null 2>&1; then
    echo "Using uvx fallback for quartodoc; local Python ${PYTHON_BIN} has no quartodoc."
    UVX_QUARTODOC="1"
  else
    echo "quartodoc is required to build docs/reference. Install quartodoc in ${PYTHON_BIN} or uvx." >&2
    exit 1
  fi
fi

TMP_CONFIG="$(mktemp "${DOCS_DIR}/.quartodoc-expanded.XXXXXX.yml")"
"${PYTHON_BIN}" "${SCRIPT_DIR}/quartodoc_expand_config.py" \
  --config "${DOCS_DIR}/_quarto.yml" \
  --output "${TMP_CONFIG}"

QUARTODOC_ARGS=(build --config "${TMP_CONFIG}")

if [[ -n "${QUARTODOC_FILTER:-}" ]]; then
  QUARTODOC_ARGS+=(--filter "${QUARTODOC_FILTER}")
fi

if [[ "${QUARTODOC_WATCH:-0}" == "1" ]]; then
  QUARTODOC_ARGS+=(--watch)
fi

clean_reference_render_artifacts() {
  find "${REFERENCE_DIR}" -maxdepth 1 -type f -name "*.html" -delete
  find "${REFERENCE_DIR}" -maxdepth 1 -type d -name "*_files" -exec rm -rf {} +
  if [[ -d "${DOCS_DIR}/.quarto/idx/reference" ]]; then
    find "${DOCS_DIR}/.quarto/idx/reference" -maxdepth 1 -type f -name "*.json" -delete
  fi
}

clean_reference_pages() {
  find "${REFERENCE_DIR}" -maxdepth 1 -type f -name "*.qmd" ! -name "_*.qmd" ! -name "index.qmd" -delete
  clean_reference_render_artifacts
}

run_quartodoc_interlinks() {
  local interlinks_args=(interlinks --fast "${TMP_CONFIG}")

  if [[ "${UVX_QUARTODOC:-0}" == "1" ]]; then
    uv run --project "${REPO_ROOT}/aria_nbv" --directory "${DOCS_DIR}" --frozen --with quartodoc quartodoc "${interlinks_args[@]}"
  else
    "${PYTHON_BIN}" -m quartodoc "${interlinks_args[@]}"
  fi
}

refresh_interlinks() {
  local mode="${QUARTODOC_INTERLINKS:-auto}"
  local inventory_dir="${DOCS_DIR}/_inv"
  local source

  case "${mode}" in
    0)
      echo "Skipping Quartodoc interlinks (QUARTODOC_INTERLINKS=0)."
      return
      ;;
    1)
      ;;
    auto)
      for source in python torch lightning torchmetrics; do
        if [[ ! -f "${inventory_dir}/${source}_objects.txt" ]]; then
          run_quartodoc_interlinks
          return
        fi
      done
      echo "Using cached Quartodoc interlink inventories. Set QUARTODOC_INTERLINKS=1 to refresh."
      return
      ;;
    *)
      echo "QUARTODOC_INTERLINKS must be 0, 1, or auto (got ${mode})." >&2
      exit 2
      ;;
  esac

  run_quartodoc_interlinks
}

run_quartodoc() {
  set +e
  if [[ "${UVX_QUARTODOC:-0}" == "1" ]]; then
    uv run --project "${REPO_ROOT}/aria_nbv" --directory "${DOCS_DIR}" --frozen --with quartodoc quartodoc "${QUARTODOC_ARGS[@]}" 2>&1 | tee "${TMP_LOG}"
  else
    "${PYTHON_BIN}" -m quartodoc "${QUARTODOC_ARGS[@]}" 2>&1 | tee "${TMP_LOG}"
  fi
  BUILD_STATUS=${PIPESTATUS[0]}
  set -e
}

extract_missing_aliases() {
  sed -n "s/.*Could not resolve alias \\([A-Za-z0-9_\\.]*\\) pointing at.*/\\1/p" "${TMP_LOG}" \
    | sort -u
}

remove_stale_reference_pages() {
  local removed=0
  local symbol
  for symbol in "$@"; do
    [[ -z "${symbol}" ]] && continue
    if [[ -f "${REFERENCE_DIR}/${symbol}.qmd" ]]; then
      rm -f "${REFERENCE_DIR}/${symbol}.qmd"
      echo "Pruned stale symbol page: ${REFERENCE_DIR}/${symbol}.qmd"
      removed=1
    fi
  done
  if [[ "${removed}" -eq 1 ]]; then
    return 0
  fi
  return 1
}

if [[ "${QUARTODOC_INCREMENTAL:-0}" == "1" ]]; then
  echo "Running incremental quartodoc build; existing generated reference pages are preserved."
else
  clean_reference_pages
fi
run_quartodoc

if [[ "${BUILD_STATUS}" -ne 0 ]]; then
  if grep -Eq "AliasResolutionError|KeyError: '" "${TMP_LOG}"; then
    echo "quartodoc reported alias/lookup errors. Running resilient regeneration." >&2
    mapfile -t MISSING_SYMBOLS < <(extract_missing_aliases)
    if remove_stale_reference_pages "${MISSING_SYMBOLS[@]}"; then
      run_quartodoc
    else
      echo "Unable to identify stale symbol pages from alias failures; retrying would be a guess." >&2
      run_quartodoc
    fi
    if [[ "${BUILD_STATUS}" -ne 0 ]]; then
      echo "quartodoc build failed after resilience retry (exit ${BUILD_STATUS})." >&2
      exit "${BUILD_STATUS}"
    fi
    echo "Recovered from stale-symbol alias failures during regeneration."
  else
    echo "quartodoc build failed (exit ${BUILD_STATUS})." >&2
    exit "${BUILD_STATUS}"
  fi
fi

clean_reference_render_artifacts
README_GUIDE_ARGS=()
if [[ -n "${QUARTODOC_FILTER:-}" ]]; then
  README_GUIDE_ARGS+=(--filter "${QUARTODOC_FILTER}")
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/quartodoc_inject_package_readmes.py" "${README_GUIDE_ARGS[@]}"
"${PYTHON_BIN}" "${SCRIPT_DIR}/quartodoc_generate_dependency_diagram.py"
refresh_interlinks
"${PYTHON_BIN}" "${SCRIPT_DIR}/quartodoc_nest_sidebar.py" "${REFERENCE_DIR}/_sidebar.yml"

if grep -Eq "^WARNING:" "${TMP_LOG}"; then
  echo "quartodoc finished with non-blocking warnings. Review them before release."
fi
