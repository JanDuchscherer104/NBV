---
id: 2026-08-27_s2_report_snapshot_streamlit_seam
date: 2026-08-27
title: "S2 report snapshot Streamlit seam"
status: done
topics: [streamlit, reporting, rollouts, s2, architecture]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/app/config.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/s2_directions.py
  - aria_nbv/aria_nbv/app/panels/report_results.py
  - aria_nbv/aria_nbv/reporting/config.py
  - aria_nbv/aria_nbv/reporting/_rollouts.py
  - aria_nbv/aria_nbv/rollouts/s2_analysis.py
  - aria_nbv/aria_nbv/rollouts/s2_plotting.py
  - .configs/streamlit_app.toml
  - .configs/reports/s2-thesis-pilot.toml
  - docs/typst/thesis/data/s2-rollout-pilot/report.json
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: f1ac98a690358bef301122966e8534840fcea77c
repo_branch: "codex/pr160-review-remediation"
worktree_kind: linked
---

## Task
Resolve PR 160 against current main and remove S2 data loading, reduction, and
plot construction from the Streamlit application boundary.

## Method
Merged current main, separated rollout-owned acquisition and plotting, routed
both app previews through the immutable scientific-report transaction, nested
the reducer config inside the shared TOML recipe, regenerated the pilot bundle
and API topology, and added boundary and multi-store ordering regressions.

## Findings
- `rollouts/s2_analysis.py` now owns validated binning, strict store reads,
  canonical payload digests, and evidence DTOs; `rollouts/s2_plotting.py` owns
  deterministic Plotly construction.
- `_stored_rollouts/s2_directions.py` now owns only widgets, explicit dispatch,
  session-state invalidation, support messaging, and rendering of a sealed
  `ReportSnapshot`; shared reconstruction lives in `app/panels/report_results.py`.
- `.configs/streamlit_app.toml` selects the report recipe and section. The
  report recipe remains the sole owner of analysis parameters, channels,
  theme, and evidence status; active-store previews replace only source paths.
- S2 store slots are sorted by manifest identity rather than input path, and
  addressed reducer exclusions are retained as `s2.table.issues`.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f1ac98a690358bef301122966e8534840fcea77c

## Verification
- `make ruff-full`: passed.
- Focused mypy over 17 touched source files: passed.
- Reporting, Streamlit, campaign, rollout-inspection, and S2 tests: 275 passed.
- Pilot `nbv-report build`, `make thesis-report-data-contract`, and
  `make thesis-pdf-ci`: passed.
- `make api-docs` and focused affected-page Quarto renders: passed; existing
  non-blocking Quartodoc docstring warnings remained outside this workpackage.
- Extracted app ownership Mermaid lint: zero errors and warnings; local render
  skipped because no Mermaid CLI is installed.

## Canonical Owner Impact
Python/configuration owners, public package READMEs, generated API topology, and
the immutable thesis pilot report bundle were updated. No scientific estimand,
notation definition, or thesis prose changed.
