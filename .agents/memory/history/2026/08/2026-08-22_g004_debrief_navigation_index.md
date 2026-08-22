---
id: 2026-08-22_g004_debrief_navigation_index
date: 2026-08-22
title: "G004 debrief navigation index"
status: done
topics: [agent-scaffold, debrief, navigation, provenance]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/memory/README.md
  - .github/workflows/ci.yml
  - AGENTS.md
  - Makefile
  - scripts/ci_impact.py
  - scripts/debrief_index.py
  - scripts/debrief_nudge.sh
  - scripts/new_debrief.py
  - scripts/validate_agent_memory.py
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_debrief_index.py
  - scripts/tests/test_validate_agent_memory_threads.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 7ee7ec7e7a5f89e2e74d346d48aa3de75d7da98f
repo_branch: codex/debrief-navigation-index
worktree_kind: linked
---

## Task
Implemented a deterministic, source-digesting navigation index and tightened
evidence-based debrief capture eligibility without introducing a truth registry.

## Method
Reused `validate_agent_memory.parse_frontmatter`, projected exactly the visible
tracked/untracked history Markdown set with canonical JSONL rendering, added
generator provenance and validator/nudge seams, and updated the scaffold
contract, source-opening safety, and existing scaffold CI path classification.

## Findings
The index is owned by `scripts/debrief_index.py`; `source_path` and
`source_sha256` detect source edits and membership changes. New records carry
Git object format, corresponding full OID, branch/detached state, and
primary/linked worktree provenance, including SHA-256 repositories.
Legacy `files_touched` is projected as stable `touched_owner_paths` without
source backfill, and every row carries a string-or-null `codex_thread`.
Generation rejects symlinked or resolved-outside history sources before reading
them. Generated titles and Git branch provenance use YAML-safe JSON string
syntax; the canonical frontmatter parser decodes those JSON string escapes
while retaining its legacy scalar fallback. Queries validate index freshness
and source containment before opening Markdown. The index remains
navigation-only and historical Markdown remains evidence.

## Verification
- `aria_nbv/.venv/bin/python -m pytest -q scripts/tests/test_debrief_index.py scripts/tests/test_validate_agent_memory_threads.py scripts/tests/test_validate_agent_memory_retired.py scripts/tests/test_agent_governance_g002.py scripts/tests/test_ownership_consolidation_contract.py scripts/tests/test_ci_impact.py` — 102 passed, 36 subtests passed.
- `make ownership-consolidation-contract PYTHON_INTERPRETER=aria_nbv/.venv/bin/python` — 20 passed.
- `make check-agent-memory scaffold-audit ci-impact-self-test PYTHON_INTERPRETER=aria_nbv/.venv/bin/python` — memory validation passed, 12 skills audited with zero errors/warnings, and 13 CI-impact tests passed.
- `aria_nbv/.venv/bin/ruff format --check ... && aria_nbv/.venv/bin/ruff check ...` — five repair Python files formatted and lint-clean.
- `aria_nbv/.venv/bin/mypy --no-incremental scripts/debrief_index.py scripts/new_debrief.py scripts/validate_agent_memory.py` — success, no issues in three files.
- `bash -n scripts/debrief_nudge.sh && git diff --check` — passed.

No commit, push, PR, or other worktree action was performed.

## Canonical Owner Impact
Canonical owners updated: `AGENTS.md`, `.agents/memory/README.md`,
`scripts/debrief_index.py`, `scripts/new_debrief.py`,
`scripts/validate_agent_memory.py`, `scripts/debrief_nudge.sh`, `Makefile`,
`scripts/ci_impact.py`, and `.github/workflows/ci.yml`; focused contracts are
owned by the three changed test modules.
