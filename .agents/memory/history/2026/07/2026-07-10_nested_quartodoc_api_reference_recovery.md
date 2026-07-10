---
id: 2026-07-10_nested_quartodoc_api_reference_recovery
date: 2026-07-10
title: "Recover Nested Quartodoc API Reference"
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

Recovered the scoped nested Quartodoc API-reference implementation from the
previous worktree stash without applying its unrelated application, model, test,
or docstring changes. Quartodoc now receives a temporary standard configuration
generated from the importable package tree, excluding non-public roots and
private path components. The generated sidebar is reshaped to mirror dotted
module paths below one `Stable Package Surface` section.

The API generator retains the local incremental controls and uses the project
environment when Quartodoc is supplied through `uv`. This keeps API generation
compatible with package dependencies while avoiding a full local environment
rebuild.
