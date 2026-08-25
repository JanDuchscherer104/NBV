---
id: 2026-08-25_hm_thesis_declaration_compliance
date: 2026-08-25
title: "HM thesis declaration compliance"
status: done
topics: [thesis, hm, typst, compliance]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/main.pdf
  - docs/typst/thesis/template/layout/disclaimer.typ
  - docs/typst/thesis/tests/declaration.typ
  - scripts/tests/test_thesis_marker_contract.py
codex_thread: codex://threads/01a03839-e87c-7160-a79d-7cc1e8c6d588
repo_object_format: sha1
repo_head: 3475e30d7c0229e626302f5378de706c0d6e60f1
repo_branch: "codex/hm-thesis-declaration"
worktree_kind: linked
---

## Task
Complete the HM/FK07 thesis declaration and lock its required clauses in rendered output.

## Method
Compared the active declaration with HM ASPO §26(7) and the current FK07 thesis page, changed only the declaration owner, and added a Typst fixture plus PDF-text regression check.

## Findings
`docs/typst/thesis/template/layout/disclaimer.typ` now states independent authorship, no prior examination submission, exclusive use of declared sources/aids, and identification of verbatim or paraphrased quotations. The test compiles the real declaration component and checks those four clauses in extracted PDF text.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/3475e30d7c0229e626302f5378de706c0d6e60f1
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/7062be72063cf280e0c3c9df7d694eaca5047c5a

## Verification
- `make thesis-marker-contract typst-authoring-contract thesis-pdf-ci PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python CI_RENDER_DIR=/tmp/aria-hm-declaration-render` — passed.
- Extracted declaration page 128 contained all four clauses; visual inspection found no overflow or clipping.
- Independent review of staged diff `914aa73082411e123f2555dc4cd1b0da121779bd96b4b472215273844202fb5a` — approved.
- Independent review of tracked-PDF follow-up `88b8633c94ea4915ec19655ae2f179afbe3dcbdc8f10bbc8f88eff1d5539a28d` — approved; extracted tracked and fresh-render text hashes matched and all four clauses were present.
- `git diff --check` — passed.

## Canonical Owner Impact
Updated the active Typst declaration and its executable rendered-text contract; no submission state or signature rule was inferred.
