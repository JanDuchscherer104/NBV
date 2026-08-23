---
kind: issue-acceptance-handoff
status: proposed
slug: online-oracle-mvp
captured: 2026-08-22
issues:
  - 74
  - 75
allowed_dispositions:
  - compatible
  - needs_issue_amendment
  - needs_follow_up_issue
issue_revisions:
  - issue: 74
    timestamp: 2026-08-19T09:37:13Z
    body_sha256: 1f91070808154c7ea2e0547359d1fda3172898f6b70144557bd40d4ee1c14f04
  - issue: 75
    timestamp: 2026-08-19T09:38:02Z
    body_sha256: ac0fab167f5a891aa9657e17ce8d57ab12f6c139bcde02d5da304461101825ef
---

# Online oracle MVP issue-acceptance handoff

This is the concrete WP0a handoff schema and current planning snapshot for
GitHub issues #74 and #75. The issue revisions recorded in frontmatter are the
source snapshot used for this handoff. A work package may not close an issue
while any row is `needs_issue_amendment` or `needs_follow_up_issue`.

Required row fields are `issue`, `acceptance_key`, `source_acceptance`,
`mvp_contract`, `disposition`, `evidence_owner`, and `closure_rule`. The three
frontmatter dispositions are the complete vocabulary.

| Issue | Acceptance key | Source acceptance | MVP contract | Disposition | Evidence owner | Closure rule |
| --- | --- | --- | --- | --- | --- | --- |
| #74 | presentation-free-environment | reusable oracle environment independent of UI | `OracleNbvEnvironment.open()` returns a bound episode facade | compatible | WP4 environment tests | dense parity and lifecycle tests pass |
| #74 | query-modes | dense, subset, and selected-only oracle queries | all three exist for evaluation; only dense-valid enters fitted Q | compatible | WP4 query tests and WP5 admission tests | sparse modes cannot enter dense learning identity |
| #74 | lifecycle-vocabulary | reset/step-style interaction | `open/prepare_decision/evaluate/commit/endpoint/close` with bound hashes | needs_issue_amendment | issue #74 owner plus WP4 ADR | live issue accepts the narrowed vocabulary or records an equivalent mapping |
| #74 | cache-and-atomicity | episode-local cache, atomic transition, endpoint | cache identities, rehash-before-use, transactional commit, independent endpoint | compatible | WP0a golden and WP4 CUDA lifecycle tests | parity, failure atomicity, and cleanup evidence pass |
| #74 | collector-boundary | collector above rather than inside environment | `OnlineQhCollector` composes environment, replay, bundle, and writer | compatible | WP5 integration test | environment has no persistence/training imports |
| #75 | finite-candidate-ranking | learned masked selector over current finite table | pipeline-local Q_H score Adapter feeds existing replay selection | compatible | WP1/WP2/WP5 tests | fresh-process ranking parity and existing selection tests pass |
| #75 | live-policy-decision | live gradient-bearing `PolicyDecision` during collection | MVP collection is inference-only and persists existing detached selection records | needs_issue_amendment | issue #75 owner and #77 gradient owner | issue accepts fitted-Q narrowing; any policy-gradient learner is separately versioned |
| #75 | detached-storage | one-way detached storage projection | reuse existing detached `CandidateScores`/step records; never persist autograd | compatible | WP5 storage-safety tests | stored rows have no graph and exact bundle identity |
| #75 | staged-learning | dense one-step, offline Q_H, then optional online | WP3 offline M5 gate precedes WP5 dense-valid round learning | compatible | WP3/WP5 reports | M5 gates and dense support admission pass |
| #75 | broader-policy-gradient | score-function update under nondifferentiable reward | deferred training-mode learner recomputes log probability from stored actor/action | needs_follow_up_issue | #77 or a new objective-specific issue | separate objective, manifest, tests, and scientific gate exist |
| #75 | matched-hard-oracle | compare under matched candidate and oracle contracts | fixed hard oracle and matched candidate/query/acquisition/endpoint budgets | compatible | WP3/WP5 held-out reports | paired held-out contract report passes |

WP0a must replace `proposed` with a live-reviewed status and record any accepted
issue edits or follow-up issue URLs. This artifact is planning evidence; it does
not itself modify or close GitHub issues.
