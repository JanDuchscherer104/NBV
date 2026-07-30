#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../../../../" && pwd)"
LIT_DIR="${ROOT_DIR}/docs/literature"
TEX_SRC_DIR="${LIT_DIR}/tex-src"
OUT="${1:-${ROOT_DIR}/docs/_generated/context/literature_index.md}"

if [[ "$OUT" != /* ]]; then
  OUT="${ROOT_DIR}/${OUT}"
fi

mkdir -p "$(dirname "$OUT")"
tmp="$(mktemp)"
timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

relpath() {
  sed "s#^${ROOT_DIR}/##"
}

{
  echo "# Literature Source Index"
  echo
  echo "- Generated: ${timestamp}"
  echo "- Repo: ${ROOT_DIR}"
  echo
  echo "## How to use"
  echo "1. Pick the paper family here."
  echo "2. Run scripts/nbv_literature_search.sh \"<term>\" within that family or globally."
  echo "3. Open only the matching section files after the family is known."
  echo
  if [[ -d "$TEX_SRC_DIR" ]]; then
    echo "## Local TeX Paper Families"
    while IFS= read -r family; do
      rel_family="$(printf '%s\n' "$family" | relpath)"
      family_name="$(basename "$family")"
      main_tex=""
      if [[ -f "$family/main.tex" ]]; then
        main_tex="$(printf '%s\n' "$family/main.tex" | relpath)"
      fi
      mapfile -t bibs < <(find "$family" -maxdepth 2 -type f -name '*.bib' | sort)
      mapfile -t texs < <(find "$family" -type f -name '*.tex' ! -name 'main.tex' | sort)
      echo "### ${family_name}"
      echo "- Root: ${rel_family}"
      if [[ -n "$main_tex" ]]; then
        echo "- Main: ${main_tex}"
      fi
      if [[ ${#bibs[@]} -gt 0 ]]; then
        echo "- Bibliography:"
        for bib in "${bibs[@]}"; do
          printf '  - %s\n' "$(printf '%s\n' "$bib" | relpath)"
        done
      fi
      if [[ ${#texs[@]} -gt 0 ]]; then
        echo "- Sections:"
        for tex in "${texs[@]}"; do
          printf '  - %s\n' "$(printf '%s\n' "$tex" | relpath)"
        done
      fi
      echo
    done < <(find "$TEX_SRC_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
  else
    echo "## Paper families"
    echo "- No literature/tex-src directory found."
  fi
  echo "## Search recipes"
  echo 'scripts/nbv_literature_search.sh "VIN-NBV"'
  echo 'scripts/nbv_literature_search.sh "Relative Reconstruction Improvement"'
  echo 'scripts/nbv_literature_search.sh "Aria Synthetic Environments"'
} > "$tmp"

mv "$tmp" "$OUT"
echo "Wrote literature index to $OUT"
