---
id: 2026-08-21_g001_routing_trial_adjudication
date: 2026-08-21
title: "G001 routing-trial adjudication"
status: done
topics: [agent-scaffold, routing, verification]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a025fe-787d-7460-930b-2eaf2e3cf7cd
---

## Task

Make hidden-rubric routing trials fail closed when their separate adjudication
is missing, malformed, mismatched, timed out, semantically failing, or not
grounded in complete raw event evidence from attested evaluator fixtures.

## Method

The clean runner HEAD is the evaluator/rubric commit and `--head` is the tested
commit. Before execution, the harness compares the prompt and rubric Git blobs
at both commits and rejects any byte difference; prompt/rubric parsing uses the
attested evaluator blobs rather than mutable worktree files. Both full commit
identities are recorded in trial and aggregate reports.

The trial receives only its rubric-blind task in normal harness flow. A separate
schema-constrained verifier receives the evaluator rubric, bounded untrusted
trial response, and deterministic raw-event projection. This is prompt hiding
and evaluator-only flow, not a security boundary against a malicious trial
agent that deliberately reads the tracked rubric from its checkout.

The event projection retains bounded event/item identity, command and tool
identity/arguments, paths, status, exit codes, and errors while omitting usage,
reasoning, messages, and command/tool output. Missing, malformed, unreadable,
truncated, or dropped evidence is host-rejected before verification. Verdict
evidence must reference unique in-range event indices and repeat the referenced
event/item identities exactly. Aggregate success requires every trial process
to succeed cleanly with complete raw evidence and an adjudicated `pass`.

## Findings

Raw trial and verifier artifacts remain in the existing ignored routing-trials
tree. Per-field, item-count, total event-evidence, and trial-response bounds are
explicit. Malformed event lines are counted and make evidence incomplete.
Invalid UTF-8, read failures, malformed verdict JSON, identity mismatch, invalid
event references, and incomplete event evidence cannot produce a pass. Recognized
execution events without type-appropriate identity are counted as invalid
projection items, so mixed valid and identity-free streams remain incomplete;
valid non-execution noise remains ignored.

Hosted scaffold CI runs only the deterministic routing unit tests. It never
invokes live Codex/model trials.

## Verification

Focused `pytest` passed with 25 routing tests and 13 CI-impact tests with 41
subtests (38 total). Agent-memory validation, Ruff on all changed Python files,
and `git diff --check` passed.

## Canonical-State Impact

The runner, verifier schema, focused tests, existing scaffold CI step/path
filters, and explicit scaffold CI-impact classification changed. No new CI
family or live hosted model execution was introduced.
