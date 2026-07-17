---
id: 2026-07-11_quartodoc_interlinks_dependency_map
date: 2026-07-11
title: "Quartodoc interlinks and generated API dependency map"
status: done
topics: [docs, quarto, quartodoc, api-reference, mermaid]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/_quarto.yml
  - docs/reference/index.qmd
  - scripts/quarto_generate_api_docs.sh
  - scripts/quartodoc_generate_dependency_diagram.py
assumptions:
  - "Package-landing docstring enrichment remains deferred while package refactors are active."
---

Implemented standard Quartodoc interlinks for Python, PyTorch, Lightning,
TorchMetrics, and jaxtyping inventories. The local role filter now converts
explicit external roles and configured bare external package roles into the
Markdown form expected by the upstream filter, preserving VS Code-readable
source roles.

Added a generated Mermaid diagram to the API index. It collapses static imports
to the public top-level packages, limits output to the strongest fifteen edges,
and labels itself as a navigation aid rather than a runtime/data-flow graph.

`make api-docs`, targeted Quarto renders, Mermaid lint, agents-db validation,
and Ruff checks passed. A full `quarto render docs --no-execute` was stopped
after confirming the upstream filter reparses external inventories per generated
page; this is a performance risk for the 949-page reference and should be
measured in CI before treating a full render as routine local verification.
