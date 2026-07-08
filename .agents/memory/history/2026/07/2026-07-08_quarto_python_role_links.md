---
id: 2026-07-08_quarto_python_role_links
date: 2026-07-08
title: "Quarto Python Role Links"
status: done
topics: [docs, quarto, quartodoc, python-docstrings]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/_quarto.yml
  - docs/_extensions/aria-python-roles/aria-python-roles.lua
---

## Task

Make ARIA-NBV generated package docs resolve VS Code-friendly Sphinx/Python
roles such as `:mod:`, `:class:`, `:func:`, `:meth:`, and `:attr:` in Quarto
HTML instead of rendering the role prefix literally.

## Method

Added a local Quarto Lua filter that resolves local ARIA-NBV Python-domain
roles against Quartodoc's generated `docs/objects.json`. The filter supports
Sphinx shorthand roles and explicit `:py:*:` forms, maps methods to
Quartodoc's `function` inventory role, maps constants/data to `attribute`, and
uses the current generated API page header as local module/class context before
falling back to unambiguous short-name resolution.

Updated `docs/_quarto.yml` to run the filter. The `python-docstrings` skill
already records the verified Sphinx/Python-domain role contract for local API
symbols, so no additional guidance-surface edit was needed.

## Verification

- `cd docs && quarto render reference/data_handling.qmd --no-clean`
- `cd docs && quarto render reference/rri_metrics.oracle_rri.qmd --no-clean`
- `cd docs && quarto render reference --no-clean`
- HTML assertion for `data_handling.html` verified links for
  `aria_nbv.data_handling`, `EfmSnippetView`, `VinSnippetView`, and
  `VinOracleBatch`, with no literal role prefixes in prose.
- Temporary role-family smoke render verified `:mod:`, `:py:mod:`, `:class:`,
  `:func:`, `:meth:`, `:attr:`, `:py:meth:`, and `:py:attr:`.
- `make qmd-frontmatter-check`
- `make check-agent-memory`
- `python3 /home/jd/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/python-docstrings`
- `git diff --check` on touched files

## Canonical State Impact

No `.agents/memory/state` update is needed. The durable workflow preference is
captured in the `python-docstrings` skill and its references, which own
docstring-relevant conventions.
