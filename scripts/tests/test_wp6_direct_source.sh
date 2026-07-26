#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_INTERPRETER:-python3}"

"$PYTHON_BIN" scripts/tests/test_wp6_literature_owners.py
"$PYTHON_BIN" scripts/tests/test_wp6_direct_source_claims.py
"$PYTHON_BIN" scripts/tests/test_wp6_scoped_uml.py
"$PYTHON_BIN" scripts/tests/test_wp6_retired_routes.py

make context-contracts PYTHON_INTERPRETER=python3 >/tmp/aria-wp6-contracts.txt
grep -Fq '# Data Contracts' /tmp/aria-wp6-contracts.txt
rg -n '^#{1,6} ' docs -g '*.qmd' >/tmp/aria-wp6-qmd.txt
grep -Fq 'docs/contents/' /tmp/aria-wp6-qmd.txt
rg -n '^\s*(=+ |#include\s+")' docs/typst -g '*.typ' >/tmp/aria-wp6-typst.txt
grep -Fq 'docs/typst/' /tmp/aria-wp6-typst.txt
make context-dir-tree PYTHON_INTERPRETER=python3 >/tmp/aria-wp6-package-tree.txt
grep -Fq 'aria_nbv/aria_nbv' /tmp/aria-wp6-package-tree.txt
make context-qmd-tree >/tmp/aria-wp6-docs-tree.txt
grep -Fq '.qmd' /tmp/aria-wp6-docs-tree.txt
rg -n 'finite candidate set' scripts/tests/fixtures/wp6_direct_source/source.tex >/tmp/aria-wp6-literature.txt

rm -f /tmp/aria-wp6-contracts.txt /tmp/aria-wp6-qmd.txt /tmp/aria-wp6-typst.txt \
  /tmp/aria-wp6-package-tree.txt /tmp/aria-wp6-docs-tree.txt \
  /tmp/aria-wp6-literature.txt
echo 'WP6 exact-source fallback: PASS'
