---
id: 2026-08-26_api_dependency_mermaid_contrast
date: 2026-08-26
title: "API dependency Mermaid contrast"
status: done
topics: [api-docs, mermaid, quarto, accessibility]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - scripts/quartodoc_generate_dependency_diagram.py
  - docs/reference/_package_dependencies.mmd
  - docs/reference/_package_dependencies.json
  - scripts/tests/test_quartodoc_generate_dependency_diagram.py
codex_thread: codex://threads/01a03a4a-114d-7f71-b9ec-140f32b8b20b
repo_object_format: sha1
repo_head: 73c84a89cde608b15615a9ece6e1b33c9ca068a6
repo_branch: "codex/fix-parentless-graphify-setup"
worktree_kind: linked
---

## Task
Make the generated API package-dependency Mermaid figure readable in both site
themes without changing its AST aggregation, layout, or edge-selection rules.

## Findings
The global Quarto Mermaid dark theme supplied a light default node-label color
to the generated pale package nodes. The generator now emits local base-theme
frontmatter with explicit dark primary text, line, and edge-label background
colors, and its sole package class supplies the matching label color and
semibold weight. The stale unused input/output/compute/data class definitions
were removed.

`make api-docs` regenerated the diagram and dependency JSON. Its unrelated
sidebar churn was excluded. A focused generator test locks the local styling
and preserves the LR edge-label output contract.

## Commit
- [66ea5a48d31fb1eb46664995969ac48f03339535](https://github.com/JanDuchscherer104/ARIA-NBV/commit/66ea5a48d31fb1eb46664995969ac48f03339535)
- [73c84a89cde608b15615a9ece6e1b33c9ca068a6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/73c84a89cde608b15615a9ece6e1b33c9ca068a6)

## Verification
`make api-docs`, the focused generator test, Ruff, CI-impact test,
`api-docs-self-test`, Mermaid lint, and a local Quarto API-reference render
passed. Mermaid lint reported only its generic missing-class warnings, which
are intentional because this generated figure uses no input/output/compute/data
nodes. The local Mermaid wrapper found no `mmdc`, so it skipped SVG rendering;
the successful Quarto render is the retained site-integration proof.
