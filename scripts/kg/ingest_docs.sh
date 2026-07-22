#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(git rev-parse --show-toplevel)
TOOLKIT_ROOT="${PROJECT_ROOT}/.agents/external/litkg-rs"

if [[ ! -x "${TOOLKIT_ROOT}/scripts/kg/ingest_docs.sh" ]]; then
  echo "Missing litkg-rs Graphiti ingestion helper at ${TOOLKIT_ROOT}/scripts/kg/ingest_docs.sh" >&2
  exit 2
fi

if [[ "$#" -eq 0 ]]; then
  set -- \
    "${PROJECT_ROOT}/AGENTS.md" \
    "${PROJECT_ROOT}/.agents/AGENTS_INTERNAL_DB.md" \
    "${PROJECT_ROOT}/.agents/references/source_order.md" \
    "${PROJECT_ROOT}/docs/contents/thesis/roadmap.qmd" \
    "${PROJECT_ROOT}/docs/contents/thesis/questions.qmd" \
    "${PROJECT_ROOT}/aria_nbv/AGENTS.md" \
    "${PROJECT_ROOT}/docs/index.qmd" \
    "${PROJECT_ROOT}/docs/contents/impl/overview.qmd" \
    "${PROJECT_ROOT}/docs/contents/impl/oracle_rri_impl.qmd" \
    "${PROJECT_ROOT}/docs/contents/impl/data_pipeline_overview.qmd" \
    "${PROJECT_ROOT}/docs/contents/literature/index.qmd" \
    "${PROJECT_ROOT}/docs/contents/theory/nbv_background.qmd" \
    "${PROJECT_ROOT}/docs/typst/seminar_paper/main.typ"
fi

KG_OLLAMA_CONFIG="${PROJECT_ROOT}/.configs/litkg.toml" \
KG_DOC_REPO_ROOT="${PROJECT_ROOT}" \
GRAPHITI_GROUP_ID="${GRAPHITI_GROUP_ID:-aria-nbv-docs}" \
  "${TOOLKIT_ROOT}/scripts/kg/ingest_docs.sh" "$@"
