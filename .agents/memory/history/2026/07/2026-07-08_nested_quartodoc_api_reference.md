---
id: 2026-07-08_nested_quartodoc_api_reference
date: 2026-07-08
title: "Nested Quartodoc API Reference"
status: done
topics: [docs, quarto, quartodoc, api-reference, vin]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/_quarto.yml
  - docs/reference/_api_index.md
  - docs/reference/_sidebar.yml
  - docs/reference/index.qmd
  - scripts/quarto_generate_api_docs.sh
  - scripts/quartodoc_expand_config.py
  - scripts/quartodoc_nest_sidebar.py
---

# Nested Quartodoc API Reference

## Summary

Implemented generated Quartodoc API discovery for the public `aria_nbv`
package surface. The docs config now owns one `Stable Package Surface` section,
while `scripts/quartodoc_expand_config.py` discovers importable package modules
and excludes app, data-cache, UI, private, and experimental roots. The generated
sidebar is post-processed into a nested package tree so `vin` follows the
current module topology.

## Changed Surfaces

- `docs/_quarto.yml`
- `docs/reference/_api_index.md`
- `docs/reference/_sidebar.yml`
- `docs/reference/index.qmd`
- `scripts/quarto_generate_api_docs.sh`
- `scripts/quartodoc_expand_config.py`
- `scripts/quartodoc_nest_sidebar.py`
- VIN API links in Quarto thesis/literature pages and glossary source.

## Validation

- `bash -n scripts/quarto_generate_api_docs.sh`
- `bash -n scripts/quarto_refresh_api_docs.sh`
- `make api-docs`
- `cd docs && quarto render reference/lightning.qmd --no-clean --no-execute`
- `cd docs && quarto render reference/index.qmd --no-clean --no-execute`
- `quarto render docs --no-execute`
- Targeted re-render of former stale-link pages after updating `vin.model_v3`
  links to `vin.models.scene_myopic`.
- `make qmd-frontmatter-check`
- `make check-agent-memory`
- `git diff --check`
- `graphify update .`

## Notes

The local project environment has package dependencies but not Quartodoc. The
API generator now falls back to `uv run --project aria_nbv --with quartodoc`
instead of plain `uvx`, so Griffe can resolve project imports without trying to
rebuild heavy dependencies such as PyTorch3D in the tool environment.
