---
id: 2026-06-17_thesis_architecture_iteration8_sampler_sensitivity
date: 2026-06-17
title: "Thesis Architecture Iteration 8 Sampler Sensitivity"
status: done
topics: [thesis, literature, candidate-sampling, target-selection, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing the candidate sampler and
target-selection protocol as experimental variables for oracle headroom and
learned `Q_H` claims.

## Findings

Candidate distribution must be reported as part of every headroom and `Q_H`
result. Realistic local ARIA candidate profiles, relaxed local profiles, and
free-shell upper bounds answer different questions and should not be mixed into
one performance claim.

The main V1 candidate profile should remain a local egocentric motion prior with
target-aware finite candidates. Hestia contributes target-then-pose and
future-return caution, GenNBV contributes state/history diversity ideas, PB-NBV
contributes cheap candidate prefiltering ideas, and Instance-NBV contributes
object-centric support diagnostics. None of those papers replace target-RRI with
coverage or make free-space continuous control the thesis-core objective.

Target selection should keep OBS-SEL, PRED-Q, and GT-EVAL distinct. Unmatched,
unsupported, or ambiguous targets are target-invalid protocol cases, not
low-RRI valid samples.

## Canonical State Impact

The autoresearch report now requires profile-indexed claims for `D1`
`v1_realistic_3family`, `D2` `v1_relaxed_3family`, and `D3`
`upper_bound_free_shell`, plus profile-specific validity, invalidity,
support, target-gain, selected-family, and oracle-headroom reports.

Follow-up thesis edits should add method and evaluation tables for candidate
profiles and target-selection sensitivity. Follow-up implementation checks
should verify whether the current generator and rollout writer persist
`position_id`, family provenance, invalid-reason fields, and non-forward
target-aware valid-count summaries.

## Verification

- Local scans covered `docs/contents/theory/candidate_sampling_target_selection.qmd`,
  `docs/contents/thesis/questions.qmd`, `docs/contents/thesis/roadmap.qmd`,
  `.agents/work/target-selection-sampling`, `.agents/work/rollout-scale-readiness`,
  and local Hestia, GenNBV, PB-NBV, and Instance-NBV TeX sources.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
