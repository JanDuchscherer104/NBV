---
id: 2026-07-18_thesis_artifact_driven_reporting_and_pruning
date: 2026-07-18
title: "Artifact-Driven Thesis Reporting and Pruning"
status: done
topics: [thesis, typst, rollouts, reporting, scientific-writing, reproducibility]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/reporting.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/info_cli.py
  - aria_nbv/tests/rollouts/test_reporting.py
  - docs/typst/thesis/experiment_data.typ
  - docs/typst/thesis/data/report-bundle-fixture.json
  - docs/typst/thesis/data/report-bundle-invalid-missing-facts.json
  - docs/typst/thesis/tests/report_data_smoke.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/metadata.typ
  - docs/typst/thesis/appendix/index.typ
  - docs/typst/thesis/sections/
  - docs/typst/thesis/template/layout/disclaimer.typ
  - docs/typst/thesis/template/layout/thesis_template.typ
  - docs/typst/thesis/template/layout/titlepage.typ
artifacts:
  - .omx/plans/thesis-artifact-driven-reporting-and-pruning-20260717.md
  - .omx/ultragoal/goals.json
  - .omx/ultragoal/ledger.jsonl
assumptions:
  - "The rich research diary remains development-only; submission mode contains only evidence-backed narrative and the reproducibility appendix."
  - "Pilot fixtures test the reporting interface and are not scientific evidence."
---

## Task

Replace hand-copied thesis numbers with a small artifact-driven reporting seam,
correct the manuscript to the implemented oracle and rollout contracts, and
prune boilerplate across every active thesis chapter without fabricating
results. The work covered the Python reporting interface, the Typst loader and
fixtures, Chapters 01--08, the appendix, front matter, and the development
diary.

## Implementation

`aria_nbv.rollouts.reporting` now projects validated rollout stores, resolved
manifests, and caller-selected sidecars into deterministic pandas DataFrames
and a strict JSON bundle. The tables reuse the row and statistic builders in
`aria_nbv.rollouts.inspection`; CLI statistics and preflight output therefore
share the same numerical definitions as Streamlit-facing inspection and the
thesis export. Facts carry units, denominators, aggregation, provenance, and an
explicit `pilot` or `confirmatory` status. Typed long-form parameter and
sidecar rows preserve missing values, and serialization is byte-stable under
input reordering.

`nbv-rollouts-info` exposes that seam through `--thesis-bundle-output`, an
explicit `--thesis-evidence-status`, and repeated `--thesis-sidecar` inputs.
Text and JSON output report the output path, `aria-nbv-thesis-report-v1`
schema, top-level `evidence` role, and digest. Analysis code can promote result
facts through the typed `aria-nbv-analysis-facts-v1` contract. Promoted facts
must name a known store, match the export status, include value, unit,
denominator, aggregation, and provenance, and not collide with store-derived
facts. Logical names and content-addressed identifiers retain portable sidecar
provenance while excluding machine-local absolute paths.

`docs/typst/thesis/experiment_data.typ` is intentionally small: one JSON
loader, schema and required-fact assertions, evidence-status checks, and one
null-aware formatter. The in-project positive fixture exercises all 15 report
tables; the invalid fixture and status-mismatch compile paths prove that
missing or misclassified evidence is rejected. Fixture numbers are identified
as synthetic interface data and are not rendered as thesis findings.
Submission now fails closed unless the operator supplies an explicit
confirmatory bundle whose top-level role is `evidence`; Typst inputs cannot
relabel the bundled development fixture as publication evidence.

All active thesis sections were rewritten. Chapter 03 now describes the
implemented sampling of finite, positive-volume GT OBB tasks rather than a
proposal-to-GT IoU matcher, treats GT pose and extent as privileged V0 task
instruction, separates hard geometry invalidity from oracle-label failure, and
does not interpret projected-area or support placeholders as measurements.
Chapters 01, 02, and 04 retain the research questions, essential ASE/EFM3D,
VIN, and RRI context, finite-candidate masks and replay contracts, and the
explicitly unimplemented finite-horizon value model while removing speculative
architecture and migration prose. Chapters 05--08 define a frozen
scene-disjoint population, paired per-scene endpoint estimand, denominators,
valid-store gates, failure strata, and evidence availability instead of empty
result slots. The tracked thesis diff removed 1,107 lines and added 333 lines;
the chapter-specific reductions recorded during execution were 472 to 314 LOC
for Chapter 03, 254 to 102 LOC for Chapters 01--02, 572 to 136 LOC for Chapter
04, 227 to 181 LOC for Chapter 05, and 68 to 56 LOC for Chapters 06--08.

The reproducibility appendix is present in development and submission modes.
It renders bundle provenance and renders resolved parameter rows only for a
confirmatory bundle. The marked research diary remains development-only and
contains decisions, failures, rejected scope, and next evidence gates rather
than submission claims. English and German abstracts now state the current
evidence boundary directly.

The confirmatory Results surface is deliberately compact. A result family is
available only when the bundle is confirmatory, every included store validates,
and every store supplies the exact required facts; one valid store cannot mask
an incomplete peer. Population, candidate-support, paired-effect, and resource
facts render per stable store/profile label without cross-profile aggregation
in Typst. The appendix uses the same labels to attribute each selected resolved
parameter to its source store and leaves full identifiers and hashes in the
machine-readable bundle.

## Final Review Remediation

The first aggregate final review, G007, correctly blocked completion. The
reporting adapter lacked a supported CLI export path and could not promote the
analysis facts required by Results; submission could silently consume the
development fixture, the appendix caption overstated confirmatory provenance,
owner metadata TODOs remained visible, parameter rows lacked store attribution,
and sidecars leaked machine-local paths. The architecture review also found
that population and paired-effect availability did not require every included
store to validate.

G008 resolved those findings with the CLI export,
`aria-nbv-analysis-facts-v1` promotion, portable content-addressed sidecars,
the explicit `evidence` role, fail-closed submission inputs, conditional
omission of unknown owner metadata, per-store appendix parameters, and
all-store Results gates. Unknown second-examiner and date fields are empty or
`none` and disappear from the title and declaration layouts rather than being
shown as TODOs or replaced by invented values. A second changed-files
anti-slop pass found no masking fallback or justified Python deletion; it made
only a small appendix UI cleanup, collapsing redundant evidence-class wording
to `Confirmatory evidence`.

## Scientific Blockers Preserved

No confirmatory held-out, population-level rollout bundle currently supplies
the frozen scene and target population, exclusions, paired policy endpoints,
uncertainty, headroom gate, and matched runtime/storage evidence required by
the experimental design. The current train-only and CUDA-out-of-memory rollout
attempts establish implementation readiness and a rendering scale gate only;
they do not establish throughput, dataset volume, generalization, or policy
quality. The learned finite-horizon value model is not implemented, so no
learned-policy superiority is claimed.

The second examiner, registered start date, submission date, and formatted
submission-date text in `docs/typst/thesis/metadata.typ` remain external
owner-supplied metadata. They are omitted from rendered surfaces until supplied
rather than displayed as placeholders or guessed.

## Verification

Reporting verification covered CLI parity, Streamlit/inspection-row parity,
typed missingness, provenance, stable sidecar identity, byte-stable bundle
serialization, failure projection, and fail-fast manifest and group contracts.
The implementation pass recorded 26 passing reporting tests; an independent
verification rerun recorded Ruff clean and 17 passing focused tests. After the
G008 remediation, the exact reporting and CLI suite passed all 32 tests with
Ruff formatting and checks clean. Repeated CLI exports were byte-identical and
their SHA-256 digests matched CLI metadata; text and JSON modes reported the
bundle contract, all 14 Results keys were available from store-derived and
promoted facts, unknown-store promotion failed without writing output, and no
machine-local sidecar path appeared in the exported bundle.

Typst verification compiled the positive loader smoke document and the full
75-page development thesis. Submission without explicit data, fixture data
masquerading as confirmatory, and malformed report data each failed as
intended. A realistic-shaped two-store confirmatory evidence bundle compiled a
75-page submission document and exercised both profiles, all-store gates,
compact Results rows, appendix provenance, and 20 per-store parameter rows.
That artifact proves structure and layout only; it is not thesis-level
scientific evidence. Render inspection found readable Results and appendix
tables, clean title and declaration omission of unknown metadata, and no diary
or TODO leakage in submission mode. The second cleanup reran all 32 focused
tests, both positive Typst builds, the negative publication gates, and
`make check-agent-memory`; all expected outcomes passed. `git diff --check`
also passed.

## Worktree Isolation

Pre-existing rollout-pilot changes under `.configs/`, rollout generation and
sharding, the PyTorch3D renderer, their tests, pilot sidecars, and the
2026-07-17 paired-source debrief were preserved. This thesis task neither
reverted nor claimed those changes. The archived rollout-bandwidth Ultragoal
and its artifacts also remained untouched while this separate thesis plan ran.

## Canonical State Impact

No canonical state update is required. The changes implement the existing
actor/oracle, invalidity, finite-candidate, evidence-status, and public-doc
boundaries; they do not establish new experimental truth. Confirmatory results
must enter through a validated frozen report bundle before any later canonical
claim update.
