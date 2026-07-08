---
id: 2026-07-08_streamlit_import_cycle_fix
date: 2026-07-08
title: "Streamlit Import Cycle Fix"
status: done
topics: [streamlit, data-handling, imports]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/data_handling/__init__.py
---

## Task

Fixed the `uv run nbv-st` startup failure caused by a circular import between
`aria_nbv.data_handling` and `aria_nbv.pose_generation`.

## Changes

- Restored the intended `aria_nbv.data_handling.__init__` import order so raw
  snippet exports, including `EfmSnippetView`, are bound before offline dataset
  modules import candidate-generation contracts.
- Preserved the existing public API surface and avoided touching unrelated
  dirty `.agents` worktree changes.

## Verification

- `cd aria_nbv && uv run python -c 'import aria_nbv; import aria_nbv.streamlit_app'`
  passed.
- `cd aria_nbv && uv run pytest tests/data_handling/test_public_api_contract.py::test_public_api_smoke_imports_all_exports tests/test_streamlit_entry.py -q`
  passed with 5 tests.
- `cd aria_nbv && uv run ruff check aria_nbv/data_handling/__init__.py` passed.
- `cd aria_nbv && uv run nbv-st --server.port 8519 --server.headless true`
  reached Streamlit ready state at `http://localhost:8519`; the temporary
  server was stopped after verification.
- `graphify update .` refreshed the local AST graph after the code edit.
