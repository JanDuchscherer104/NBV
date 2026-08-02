#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../../../../" && pwd)"

OUT="${1:-${ROOT_DIR}/docs/_generated/context/source_index.md}"
if [[ "$OUT" != /* ]]; then
  OUT="${ROOT_DIR}/${OUT}"
fi

mkdir -p "$(dirname "$OUT")"

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
tmp="$(mktemp)"

relpath() {
  sed "s#^${ROOT_DIR}/##"
}

has_rg() {
  command -v rg >/dev/null 2>&1
}

list_files() {
  local pattern="$1"
  local root="$2"
  if [[ ! -d "$root" ]]; then
    return 0
  fi
  if has_rg; then
    rg --files -g "$pattern" "$root" 2>/dev/null || true
  else
    find "$root" -type f -name "$pattern" 2>/dev/null || true
  fi
}

count_files() {
  local pattern="$1"
  local root="$2"
  list_files "$pattern" "$root" | wc -l | tr -d ' '
}

count_immediate_dirs() {
  local root="$1"
  if [[ ! -d "$root" ]]; then
    echo 0
    return
  fi
  find "$root" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' '
}

qmd_count="$(count_files '*.qmd' "${ROOT_DIR}/docs")"
typst_thesis_count="$(count_files '*.typ' "${ROOT_DIR}/docs/typst/thesis")"
typst_paper_count="$(count_files '*.typ' "${ROOT_DIR}/docs/typst/seminar_paper")"
typst_slides_count="$(( $(count_files '*.typ' "${ROOT_DIR}/docs/typst/seminar_slides") + $(count_files '*.typ' "${ROOT_DIR}/docs/typst/thesis_slides") ))"
typst_shared_count="$(count_files '*.typ' "${ROOT_DIR}/docs/typst/shared")"
lit_root="${ROOT_DIR}/docs/literature"
lit_tex_count="$(count_files '*.tex' "${lit_root}")"
lit_bib_count="$(count_files '*.bib' "${lit_root}")"
lit_family_count="$(count_immediate_dirs "${lit_root}/tex-src")"
py_count="$(count_files '*.py' "${ROOT_DIR}/aria_nbv/aria_nbv")"
ref_count="$(count_files '*.md' "${ROOT_DIR}/.agents/references")"
memory_state_count="$(count_files '*.md' "${ROOT_DIR}/.agents/memory/state")"
memory_history_count="$(count_files '*.md' "${ROOT_DIR}/.agents/memory/history")"

{
  echo "# Context Sources Index"
  echo
  echo "- Generated: ${timestamp}"
  echo "- Repo: ${ROOT_DIR}"
  echo
  echo "## Retrieval ladder"
  echo "1. Source order and conflict rule: .agents/references/source_order.md"
  echo "2. Current thesis direction: docs/contents/thesis/{roadmap,questions}.qmd plus .agents/memory/state/{PROJECT_STATE,DECISIONS,OPEN_QUESTIONS,GOTCHAS}.md"
  echo "3. Active thesis prose and hierarchy: docs/typst/thesis/main.typ plus recursive includes"
  echo "4. Shared scientific language: docs/typst/shared/{glossary,symbols,equations}.typ plus docs/notation.yml"
  echo "5. Seminar evidence: docs/typst/seminar_paper/main.typ for historical implemented evidence only"
  echo "6. Idea archive: docs/contents/ideas.qmd for read-only scratch/history"
  echo "7. On-demand references: .agents/references/ and .agents/skills/aria-nbv-context/references/{context_map,context7_library_ids}.md"
  echo "8. Lightweight refresh: make context"
  echo "9. Heavyweight fallback: make context-heavy"
  echo
  echo "## Core owner map"
  echo "- .agents/references/source_order.md"
  echo "- docs/contents/thesis/roadmap.qmd"
  echo "- docs/contents/thesis/questions.qmd"
  echo "- docs/typst/shared/glossary.typ"
  echo "- docs/typst/shared/symbols.typ"
  echo "- docs/typst/shared/equations.typ"
  echo "- docs/notation.yml"
  echo "- docs/contents/glossary.qmd"
  echo "- docs/typst/thesis/main.typ  # active thesis"
  echo "- docs/typst/seminar_paper/main.typ  # only for seminar evidence"
  echo "- docs/contents/ideas.qmd  # read-only archive/scratch"
  echo "- .agents/memory/state/PROJECT_STATE.md"
  echo "- .agents/memory/state/DECISIONS.md"
  echo "- .agents/memory/state/OPEN_QUESTIONS.md"
  echo "- .agents/memory/state/GOTCHAS.md"
  echo
  echo "## Lightweight refresh"
  echo "- \`make context\` refreshes \`source_index.md\`, \`literature_index.md\`, and \`data_contracts.md\`."
  echo "- Prefer \`make context-contracts\` or \`scripts/nbv_get_context.sh contracts\` before opening \`docs/_generated/context/data_contracts.md\`."
  echo "- Use \`make context-heavy\` only for bundled heavy fallback artifacts."
  echo
  echo "## Source families"
  echo "| Family | Count | Use when | First reveal |"
  echo "|---|---:|---|---|"
  echo "| Canonical state | ${memory_state_count} docs | You need current truth, conventions, or decisions | Open the relevant doc in \`.agents/memory/state/\` |"
  echo "| Agent history | ${memory_history_count} docs | The task is historical, comparative, or evidence-driven | \`rg -n \"<term>\" .agents/memory/history\` |"
  echo "| Agent references | ${ref_count} docs | You need authority, human-preference, or external-doc routing | Open the smallest named reference |"
  echo "| Quarto docs | ${qmd_count} files | You need implementation narrative, roadmap, or explainer docs | \`scripts/nbv_qmd_outline.sh --compact\` |"
  echo "| Typst active thesis | ${typst_thesis_count} files | You need current thesis prose or section ownership | \`scripts/nbv_typst_includes.py --thesis --mode outline\` |"
  echo "| Typst shared language | ${typst_shared_count} files | You need glossary, symbol, equation, or notation ownership | Open the matching shared facade, then its domain module |"
  echo "| Typst seminar paper | ${typst_paper_count} files | You need historical implemented evidence or seminar wording | \`scripts/nbv_typst_includes.py --seminar --mode outline\` |"
  echo "| Typst slides | ${typst_slides_count} files | The task explicitly touches slides | \`scripts/nbv_typst_includes.py --thesis --with-slides --mode outline\` |"
  echo "| Literature | ${lit_family_count} families, ${lit_tex_count} .tex, ${lit_bib_count} .bib | You need related-work or source-paper context | \`scripts/nbv_literature_index.sh\` |"
  echo "| Python source | ${py_count} files | You need contracts, module ownership, or symbols | \`scripts/nbv_get_context.sh contracts\`, \`modules\`, or \`match <term>\` |"
  echo
  echo "## Curated documentation families"
  echo "| Topic | Primary paths | Use when |"
  echo "|---|---|---|"
  echo "| Project hub | \`docs/index.qmd\` | You need the docs landing page or high-level navigation. |"
  echo "| Current thesis | \`docs/contents/thesis/roadmap.qmd\`, \`docs/contents/thesis/questions.qmd\`, \`.agents/memory/state/\` | You need current milestones, direction, or open research questions. |"
  echo "| Active thesis prose | \`docs/typst/thesis/main.typ\` and its includes | You need current thesis wording, hierarchy, or claim placement. |"
  echo "| Shared scientific language | \`docs/typst/shared/glossary.typ\`, \`symbols.typ\`, \`equations.typ\`, \`docs/notation.yml\` | You need a durable term, symbol, equation, or printed notation entry. |"
  echo "| Setup and resources | \`docs/contents/setup.qmd\`, \`resources.qmd\` | You need environment/bootstrap help or external resource links. |"
  echo "| Findings and glossary | \`docs/contents/experiments/findings.qmd\`, \`docs/contents/glossary.qmd\`, \`docs/typst/shared/glossary.typ\` | You need prior experiment outcomes or project terminology. |"
  echo "| Idea archive | \`docs/contents/ideas.qmd\` | You need read-only scratch/history, not current direction. |"
  echo "| Implementation contracts | \`docs/reference/index.qmd\`, package docstrings | You need package architecture or oracle/RRI computation details. |"
  echo "| External stack owners | \`data_handling/\`, \`rendering/\`, \`vin/\`, and vendored source under \`external/\` | You need ATEK, EFM3D, EVL, or Project Aria tooling contracts. |"
  echo
  echo "## Secondary/on-demand references"
  echo "- .agents/skills/aria-nbv-context/references/context_map.md"
  echo "- .agents/skills/aria-nbv-context/references/context7_library_ids.md"
  echo "- .agents/memory/README.md"
  echo "- docs/index.qmd"
  echo "- .agents/archive/docs/todos.qmd  # historical archive only"
  echo
  echo "## Preferred reveal commands"
  echo '- scripts/nbv_qmd_outline.sh --compact'
  echo '- scripts/nbv_typst_includes.py --thesis --mode outline'
  echo '- scripts/nbv_typst_includes.py --seminar --mode outline  # historical only'
  echo '- scripts/nbv_literature_index.sh'
  echo '- make context-contracts'
  echo '- scripts/nbv_get_context.sh contracts'
  echo '- scripts/nbv_get_context.sh modules'
  echo '- scripts/nbv_get_context.sh match <term>'
  echo '- make context    # refresh lightweight routing artifacts'
  echo
  echo "## Heavy fallback only"
  echo "- Prefer specific targets when possible: \`make context-uml\`, \`make context-docstrings\`, \`make context-tree\`."
  echo "- Bundled fallback: \`make context-heavy\`."
  echo "- Heavy artifacts: \`context_snapshot.md\`, \`aria_nbv_uml.mmd\`, \`aria_nbv_filtered_uml.mmd\`, \`aria_nbv_class_docstrings.md\`, \`aria_nbv_tree.md\`."
  echo
  echo "## Search recipes (rg)"
  echo 'rg -n "<term>" .agents/memory/state'
  echo 'rg -n "<term>" .agents/memory/history'
  echo 'rg -n "<term>" .agents/references'
  echo 'rg -n "<term>" docs/**/*.qmd'
  echo 'rg -n "<term>" docs/typst/**/*.typ'
  echo 'rg -n "<term>" docs/literature/**/*.{tex,bib,sty}'
  echo 'rg -n "<term>" aria_nbv/aria_nbv'
  echo 'rg -n "VinPrediction|EfmSnippetView|BaseConfig" docs/_generated/context/data_contracts.md'
} > "$tmp"

mv "$tmp" "$OUT"
echo "Wrote context sources index to $OUT"
