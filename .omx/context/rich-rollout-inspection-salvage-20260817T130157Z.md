# Rich rollout inspection salvage context

## Task statement

Plan a selective salvage of useful stored-rollout inspection and plotting behavior from historical PR #32 (`70fc7fcbe5969927de322cf42a5cff782de80687`) and PR #38 (`a8ff3d6bd134f500badc515959400185a4cf8fba`) onto the current generation branch (`823a945da19852e4ac2b6ac8750ca9c5abfe0263`).

## Desired outcome

Produce an implementation-ready PRD and test specification for a separate, read-only rich inspection PR. Restore useful missing scientific and training-readiness views while retaining current target/candidate/temporal/query/Rerun functionality and avoiding obsolete generation, collection, or service architecture.

## Known facts and evidence

- PR #62 is the generation-side PR. Its explicit boundary assigns scheduling, CUDA execution, status, validation, and promoted artifact records to generation; inspection consumes validated paths read-only.
- Both historical PRs contain the modular `_stored_rollouts/` UI package plus inspection/read-model/scientific-audit work. PR #38 adds `rollouts/reporting.py` and stronger scientific contracts; PR #32 contains some richer exploratory plot variants.
- Current inspection already owns discovery, inventory, target and candidate audits, temporal summaries, paired comparisons, selected-rank/regret, root-relative geometry, failure triage, evidence bundle export, query workbench, and post-hoc Rerun in:
  - `aria_nbv/aria_nbv/rollouts/inspection.py`
  - `aria_nbv/aria_nbv/rollouts/reporting.py`
  - `aria_nbv/aria_nbv/rollouts/read_model.py`
  - `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py`
- Current Q_H loading and admission truth is owned by `aria_nbv/aria_nbv/rollouts/qh_reader.py`; UI must delegate to that owner rather than recreate masks or loader semantics.
- High-value missing or partial capabilities identified by the exact-ref audit are:
  1. header metrics, reference coverage, and per-source storage footprint;
  2. reconstruction trajectory and declared discounted-return views;
  3. oracle headroom with explicit denominators, exclusions, and cohort identities;
  4. candidate component composition, proposal calibration, conditional collision/support, and scientifically valid macro aggregation;
  5. Q_H stage admission, loader/datamodule provenance, and explicit opt-in single-chain materialization;
  6. physical Zarr topology where it materially aids debugging.
- Current strengths to preserve include paired matched-cohort comparisons, deterministic bootstrap intervals, target and action-support diagnostics, query workbench, `ScientificExplanation`, exports, and Rerun handoff.
- Historical `rollouts.collection`, broad scientific-audit sealing machinery, generic session/service architecture, generation controls, automatic polling, and kill/delete controls are not required for the requested salvage.
- Graphify state is `usable-stale` at graph revision `915489422ca20522801becf9c6f91780bc2a3ef1`; exact source/ref verification is required for all consequential plan claims.

## Constraints

- Planning only in this Ralplan turn; no source implementation.
- Preserve the two-PR boundary. Do not merge, rebase, or cherry-pick either historical PR wholesale.
- Base implementation on a fresh inspection worktree after PR #62 is merged, or explicitly stack it on PR #62 if implementation must begin earlier.
- Read only validated promoted stores; do not mutate rollout stores or schemas.
- Keep `read_model.py` and `rollouts.inspection` presentation-free; Streamlit and Plotly remain clients.
- Reuse the current ordered typed grouping vocabulary and candidate audit projection; unsupported grouping keys fail closed.
- Preserve V0/V1 readers, `TargetLineage`, target arrays, Zarr schema, campaign binding, and Rerun as post-hoc inspection only.
- No generic inspection service, reader protocol, plotting framework, new dependency, automatic polling, monitoring daemon, campaign control, or historical collection abstraction.
- Heavy Q_H materialization and full candidate scans must be explicit opt-in actions with bounded reads and visible provenance.
- Preserve unrelated dirty and runtime state in the current worktree.

## Open questions resolved by planning assumptions

- “Missing functionality” means the useful missing/partial capabilities above, not every historical implementation detail.
- Confirmatory sealed scientific-audit infrastructure is deferred until a concrete confirmatory thesis/export requirement exists; ordinary evidence exports remain included.
- The preferred delivery is one separate inspection PR with owner-disjoint commits and staged feature gates, not a wholesale branch transplant.

## Likely code and test touchpoints

- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/rollouts/reporting.py`
- `aria_nbv/aria_nbv/rollouts/read_model.py`
- `aria_nbv/aria_nbv/rollouts/qh_reader.py`
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py`
- a small `_stored_rollouts/` presentation package only if extraction reduces the current page without introducing a second data-access owner
- `aria_nbv/tests/rollouts/test_inspection.py`
- `aria_nbv/tests/rollouts/test_reporting.py`
- `aria_nbv/tests/rollouts/test_qh_reader.py`
- `aria_nbv/tests/app/panels/test_stored_rollouts_panel.py`
- focused new panel tests for reconstruction, headroom, candidate evidence, and Q_H admission

## Verification expectations

- Exact behavior-level comparison against both historical refs.
- Hand-calculated reducer fixtures for denominators, exclusions, returns, headroom, and macro weighting.
- V0/V1 and schema byte-identity regressions.
- Fail-closed malformed, ambiguous, stale, tampered, and unsupported-evidence tests.
- Lazy/opt-in tests proving page load does not materialize Q_H or scan all candidate rows.
- Focused Streamlit rendering and lineage/Rerun handoff tests.
- Ruff format/check, focused pytest suites, compileall, `git diff --check`, independent code review, and architect review.
