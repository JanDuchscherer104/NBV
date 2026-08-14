---
id: 2026-08-14_matt_guidance_policy_refresh
date: 2026-08-14
title: "Matt Guidance Policy Refresh"
status: done
topics: [agent-scaffold, mattpocock-skills, pragmatic-programmer, guidance, policy]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/references/human_owner_intent.md
  - .agents/references/mattpocock_skills_manifest.toml
  - scripts/tests/test_agent_governance_g002.py
---

## Task

Refresh ARIA-NBV's tracked policy for `mattpocock/skills` without importing
generic programming principles into hot-path repository guidance.

## Method

Compared the tracked manifest with all 35 skill entry points at upstream commit
`8b78b531ab965735c5dc74f6f7a219e1e37326df`, checked the operator-local Codex
installation, mapped the general engineering guidance in
`docs/literature/pdf/the-pragmatic-programmer-20th-anniversary-edition_P3.0.pdf`,
and retained ARIA's source-order owners for durable meaning.

## Pragmatic Programmer Invariants

Page references below are printed book pages in the P3.0 PDF.

- Topics 2-5 (pages 3-12) reinforce responsibility, bounded quality, and
  resisting software entropy. ARIA captures these through predictable process,
  reviewability, surgical changes, and literal verification.
- Topics 8-11 and 28 (pages 28-49 and 130-136) connect ease of change, DRY
  knowledge, orthogonality, reversibility, and decoupling. ARIA keeps one owner
  per durable meaning and now states changeability and locality explicitly;
  `aria-grill` routes interface work to `codebase-design`.
- Topics 12-13 (pages 50-58) distinguish retained tracer code from disposable
  learning prototypes. ARIA now records reversible learning explicitly and
  keeps prototype artifacts evidential until an owning source adopts the result.
- Topics 23-27 (pages 104-127) reinforce contracts, early failure, assertions,
  resource balance, and short planning horizons. Source, tests, and active
  configuration own executable contracts; `agent-behavior` owns bounded work and
  fresh verification; `python-standards` documents settled Python API contracts.
- Topics 40-44 (pages 209-242) reinforce continuous refactoring, testing through
  interfaces, property checks, safety, and naming. ARIA routes cleanup through
  `simplification`, verification through nearest package owners, and domain
  language through its glossary and source owners.

These are ownership and execution invariants, not a second engineering handbook.
The PDF remains literature evidence; canonical ARIA owners state the adopted
preferences and procedures.

## Findings

- `codebase-design` remains an explicit capability routed through `aria-grill`.
- `human_owner_intent.md` now records changeability/locality and reversible
  learning without duplicating package contracts or skill procedures.
- `writing-for-agents` replaces `writing-great-skills` and is reference-only;
  `.agents/references/source_order.md` remains the local guidance owner.
- `to-spec` and `to-tickets` replace the removed `to-prd` and `to-issues`
  surfaces without replacing OMX or Agents DB ownership.
- Removed upstream skills and new Claude- or TypeScript-specific helpers do not
  become ARIA routing or truth surfaces.
- The operator-local Codex installation already matched the selected current
  skills, so no repository copy or wrapper was added.

## Verification

The manifest inventory and every `upstream_path` were compared with the pinned
upstream tree. Focused governance tests and repository scaffold checks were run
before publication.

## Canonical-State Impact

The tracked external-skill policy is current at the reviewed commit. Human-owner
intent now owns the two newly explicit cross-task preferences. Exact code, tests,
configuration, Typst, and source order retain their existing authority.
