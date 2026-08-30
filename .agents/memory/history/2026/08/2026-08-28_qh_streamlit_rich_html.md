---
id: 2026-08-28_qh_streamlit_rich_html
date: 2026-08-28
title: "QH Streamlit Rich HTML Rendering"
status: done
topics: [qh, streamlit, rich, diagnostics]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/utils/rich_summary.py
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
codex_thread: codex://threads/01a0487a-9939-7902-a5fc-49e691659d3e
repo_object_format: sha1
repo_head: 45dac6f1ebdb95c1d2d0c2263bc756ad1686e20f
repo_branch: codex/qh-streamlit-rich-html
worktree_kind: primary
---

## Task

Preserve Rich styling when displaying the Q_H item and collated batch in Streamlit.

## Method

Added a focused `capture_tree_html` adapter using Rich's recorded HTML export with a transparent, inherited-color `<pre>` wrapper. The Q_H panel now caches both plain text and HTML renderings in a typed `TypedDict`, displays HTML via Streamlit 1.57's `st.html`, and retains plain text for evidence JSON.

## Findings

The existing `st.code` path intentionally discarded Rich styles. ANSI output is unsuitable for the browser; Rich HTML preserves field/value coloring without adding a custom component or dependency.

## Verification

- Ruff passed on the touched runtime and test files.
- Mypy passed for the Rich summary and Streamlit panel.
- 39 focused Rich-summary, Streamlit-panel, and dataset-bundle tests passed.
- `st.html` smoke test passed under the installed Streamlit 1.57.0.
- `git diff --check` passed.

## Canonical-State Impact

The shared Rich summary adapter remains the sole styling owner; the Q_H panel only chooses the browser representation. No additional canonical update is needed.

## Commits

- [45dac6f1ebdb95c1d2d0c2263bc756ad1686e20f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/45dac6f1ebdb95c1d2d0c2263bc756ad1686e20f) — preserve Rich styles in the Q_H Streamlit preview.
