---
id: 2026-08-26_quartodoc_package_readme_projection
date: 2026-08-26
title: "Quartodoc package README projection"
status: done
topics: [docs, quartodoc, readme]
confidence: high
canonical_updates_needed:
  - scripts/quarto_generate_api_docs.sh
  - scripts/quartodoc_inject_package_readmes.py
  - aria_nbv/aria_nbv/vin/README.md
  - tools/mermaid/references/aria_mermaid_style.md
  - .agents/skills/aria-nbv-mermaid/SKILL.md
touched_owner_paths:
  - scripts/quarto_generate_api_docs.sh
  - scripts/quartodoc_inject_package_readmes.py
  - scripts/tests/test_quarto_generate_api_docs.sh
  - scripts/tests/test_quartodoc_inject_package_readmes.py
  - aria_nbv/aria_nbv/vin/README.md
  - aria_nbv/aria_nbv/lightning/README.md
  - docs/figures/diagrams
  - tools/mermaid
  - .agents/skills/aria-nbv-mermaid/SKILL.md
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: c24f7f103ab00f602896c8dda3bf55a9dda96d1b
repo_branch: "codex/quartodoc-package-readmes"
worktree_kind: linked
---

## Task
Render each README on the existing public Quartodoc package surface beside its
package ``__init__.py`` documentation without hand-maintaining reference pages.

## Method
Added an idempotent Quartodoc postprocessor that discovers the same package tree
as the existing configuration, strips only each README's duplicate H1, rewrites
README-local documentation and package-guide links for the reference-page
location, then inserts a marker-bounded guide before generated API inventories.
The generator forwards ``QUARTODOC_FILTER`` so targeted refreshes modify and
render only the requested package page.

## Findings
The README and package docstring remain their respective authored sources;
``docs/reference`` remains generated. The VIN-only refresh rendered the guide,
Mermaid architecture diagram, and generated inventory in one page. All eleven
current public package READMEs project successfully. The app and Rerun README
packages remain outside the existing public Quartodoc surface.

## Commits
- [f59874e95cb25aa3de2731111432b1c0a0d33de3](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f59874e95cb25aa3de2731111432b1c0a0d33de3)
- [1479bcdc2b5b4434104bb8ecef2ce753e7861202](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1479bcdc2b5b4434104bb8ecef2ce753e7861202)
- [ed570aa5e4ef0a78a800c8dc00339e775ae331a8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ed570aa5e4ef0a78a800c8dc00339e775ae331a8)
- [359cd9ef15a02957ccff31d383c633f311d69c86](https://github.com/JanDuchscherer104/ARIA-NBV/commit/359cd9ef15a02957ccff31d383c633f311d69c86)
- [c24f7f103ab00f602896c8dda3bf55a9dda96d1b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c24f7f103ab00f602896c8dda3bf55a9dda96d1b)

## Verification
- Five focused generator/injection tests passed.
- Focused Ruff format and lint checks passed.
- `make api-docs-self-test` passed.
- `make api-docs-refresh API_FILTER=vin API_PAGES=reference/vin.qmd` completed;
  expected existing Quartodoc docstring warnings and missing-target warnings
  remain when rendering a single page without the rest of the generated graph.
- The generated VIN page returned HTTP 200 from a localhost tmux-hosted preview.
- Its Mermaid graph now has an explicit dark text color in every semantic node
  class, preserving legibility against its light semantic fills under Quarto's
  configured dark Mermaid theme.
- The same contrast contract now covers all tracked semantic Mermaid sources,
  package README diagrams, templates, examples, and the generated API
  dependency graph; a focused regression test guards the contract.

## Canonical Owner Impact
Updated the API-generation seam, focused tests, shared Mermaid style/lint
owners, and user-facing package/Quarto diagrams. No Typst or package runtime
contract changed.
