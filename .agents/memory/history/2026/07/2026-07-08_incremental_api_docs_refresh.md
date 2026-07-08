---
id: 2026-07-08_incremental_api_docs_refresh
date: 2026-07-08
title: "Incremental API Docs Refresh"
status: done
topics: [docs, quarto, quartodoc, api-reference]
confidence: high
canonical_updates_needed: []
files_touched:
  - Makefile
  - scripts/quarto_generate_api_docs.sh
  - scripts/quarto_refresh_api_docs.sh
---

## Task

Add local automation for refreshing only the ARIA-NBV API docs needed during
docstring iteration, without changing the full publish-safe `make api-docs`
regeneration path.

## Method

Extended `scripts/quarto_generate_api_docs.sh` with opt-in environment
controls for Quartodoc filtering, watching, and incremental mode. Added
`scripts/quarto_refresh_api_docs.sh` to regenerate matching Quartodoc pages,
detect changed generated reference pages by content hash, and render only the
requested or changed API pages with Quarto `--no-clean --no-execute`.

Added local Make targets:

- `make api-docs-filter API_FILTER='data_handling*'`
- `make api-docs-watch API_FILTER='data_handling*'`
- `make api-docs-refresh API_FILTER='data_handling*' API_PAGES='reference/data_handling.qmd'`

## Verification

- `bash -n scripts/quarto_generate_api_docs.sh`
- `bash -n scripts/quarto_refresh_api_docs.sh`
- `make -n api-docs-filter API_FILTER='data_handling*'`
- `make -n api-docs-refresh API_FILTER='data_handling*' API_PAGES='reference/data_handling.qmd'`
- `make api-docs-refresh API_FILTER='data_handling*' API_PAGES='reference/data_handling.qmd'`
- `cd docs && quarto render reference/data_handling.qmd --no-clean --no-execute`
- HTML assertion for `data_handling.html` role links
- `make check-agent-memory`

## Canonical State Impact

No canonical memory-state update is needed. The durable command surface is the
Makefile and docs build scripts; CI and publish behavior remain full
regeneration.
