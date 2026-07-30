---
name: code-review-aria-nbv
description: Use when reviewing ARIA-NBV working-tree or PR diffs, following up external/model review findings, or supplying ARIA-NBV domain context to the oh-my-codex code-review harness with severity-ranked file and line findings.
metadata:
  mode: review
  not_when:
    - "pure implementation without a review request"
    - "architecture brainstorming without concrete diffs"
    - "GitHub review-thread state matters but gh-address-comments is unavailable"
    - "generic cross-repo code review with no ARIA-NBV domain surface"
  handoff_to:
    - "external code-review workflow capability for independent code-reviewer plus architect lanes, merge gating, and final review synthesis"
    - "GitHub review-thread capability for unresolved PR review threads, inline anchors, or resolution state"
    - "simplification for behavior-preserving AI-slop, dead-code, wrapper, or duplication cleanup"
    - "python-docstrings for Python API-contract docstring findings"
    - "docs-curator or typst-authoring for public docs, thesis prose, citations, or Typst standards"
    - "plan-grill for architecture decisions without concrete diffs"
    - "diagnose-aria when a finding needs reproduction"
  evidence_required:
    - "review surface from git diff, PR diff, or named files"
    - "external review artifact or GitHub review-thread dump when addressing received feedback"
    - "nearest owner guidance for touched surfaces"
    - "OMX code-review lane outputs when reporting merge-ready status"
    - "line-referenced findings or explicit no-findings statement"
  applies_to:
    - "**"
  triggers:
    - "review"
    - "PR review"
    - "working tree review"
    - "requested changes"
    - "external review"
    - "research model review"
    - "AI slop review"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
    - ".agents/references/verification_matrix.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - ".agents/references/verification_matrix.md"
    - ".agents/skills/README.md"
    - "scripts/scaffold/fixtures/routing.json"
  context7_refs:
    - "/pytorch/pytorch"
    - "/facebookresearch/pytorch3d"
    - "/websites/quarto"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/references.bib"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "surface-specific checks for reviewed changes"
---

# Code Review For ARIA-NBV

## Role Split

- The external code-review workflow capability owns the generic review harness:
  independent `code-reviewer` and `architect` lanes, `CLEAR` / `WATCH` / `BLOCK`
  architecture status, deterministic merge gating, and final synthesis. Do not
  replace either required lane with this skill, the authoring agent, or an
  external model report.
- The GitHub review-thread capability owns PR review-thread mechanics:
  resolving the PR, fetching unresolved/outdated/line-anchored review threads,
  clustering actionable comments, and preserving write safety. Use it whenever
  inline anchors or resolution state matter.
- This skill is the ARIA-NBV sidecar. It supplies local owner guidance,
  research/domain invariants, severity mapping, domain-specific handoffs, and
  focused verification choices for ARIA review or review-follow-up work; use
  `references/upstream-mattpocock.md` only as optional generic review framing.
- External research/model reviews are advisory inputs. Accept, reject, or
  reproduce each finding from repo evidence before implementing it or feeding it
  into an OMX merge-ready verdict.

## When To Use

Use this skill when the task is to:

- review the current working tree before commit or branch promotion
- review a GitHub pull request diff or requested-review state
- triage and address a received external model, human, or GitHub review
- review agent-memory, docs, data-contract, RRI, VIN, or Streamlit changes
- aggregate accepted review feedback into follow-up edits or agents DB records

## Grounding

Before reviewing substantial ARIA changes, read `AGENTS.md`, the nearest nested
`AGENTS.md` for the touched surface, `.agents/references/source_order.md`, and
`.agents/references/verification_matrix.md`. For docs-heavy reviews, include
`docs/AGENTS.md`; for package-contract reviews, refresh `make context-contracts`
only when generated contract context is needed.

## Domain Handoffs

Route validated findings to the smallest owner named by metadata or the nearest
`AGENTS.md`. Common handoffs: `simplification` for behavior-preserving cleanup,
`python-docstrings` for API docs, `docs-curator` / `typst-authoring` for public
docs and thesis prose, `nbv-geometry-contracts` for frames, `entity-aware-rri`
for target semantics, `counterfactual-rollout-planner` for rollout/Q_H,
`dataset-cache-ops` / `rerun-nbv-inspector` for data and visual diagnostics,
and `aria-litkg-memory` / `agents-db` for claim checks or durable records.

## Review Standard

Default to a code-review mindset:

- findings first
- order by severity
- focus on correctness, behavioral regressions, determinism drift, missing validation, repo-boundary leaks, frame/pose mistakes, stale documentation, and operator-facing contract breaks
- include tight file and line references whenever the location is clear
- if there are no findings, say that explicitly and call out residual risk or missing tests
- prefer tests that exercise public contracts and user-visible behavior

Severity: `P0` data loss/security/merge-blocking failure; `P1` correctness or
contract break; `P2` maintainability, observability, or test gap; `P3` polish.
Map these to external workflow severities as `CRITICAL`, `HIGH`, `MEDIUM`,
`LOW`. Use `REQUEST CHANGES` for unresolved `P0`/`P1`; treat unresolved
ownership or source-order conflict as architecture `WATCH`/`BLOCK`.

## External Review Follow-Up

When following up external or GitHub feedback, preserve the raw artifact or
thread id, establish the current diff first, classify each item as accepted,
rejected with evidence, needs reproduction, duplicate, already addressed, or
deferred, then route accepted items through the domain handoffs above. Implement
fixes only when asked to address feedback, and verify with the narrowest
surface-specific command.

## Working Tree Review

Establish the review surface with `git status --short`, `git diff --stat`, and
the relevant diff or PR metadata. Narrow large trees by subsystem, review tests
and docs alongside contract changes, and run only the validations needed to
confirm or falsify likely findings. Use GitHub review-thread tooling whenever
unresolved inline anchors or resolution state matter.

## Output Shape

1. `Findings`
2. `Open Questions / Assumptions`
3. `Change Summary` or `Residual Risk`

For OMX merge-gated review, also include code-reviewer recommendation,
architect status, and deterministic final recommendation. When there are no
findings, say what was validated and what remains unvalidated.
