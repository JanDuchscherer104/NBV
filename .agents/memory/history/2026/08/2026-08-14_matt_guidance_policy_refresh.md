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

Review `mattpocock/skills` and *The Pragmatic Programmer* for general practices
that improve ARIA-NBV guidance without creating another policy inventory.

## Method

Compared the upstream skill entry points at commit
`8b78b531ab965735c5dc74f6f7a219e1e37326df`, checked the official `skills` CLI
selection flags, mapped the book's general engineering guidance, and retained
ARIA's source-order owners for adopted behavior.

## Literature Identity

Thomas, David, and Andrew Hunt. *The Pragmatic Programmer: Your Journey to
Mastery*, 20th Anniversary Edition. Pearson Education, 2020.
ISBN-13 `978-0-13-595705-9`; ISBN-10 `0-13-595705-2`; P3.0 dated 2020-01-22.

The untracked local PDF named in the task was inspected as local evidence for
the printed-page crosswalk below. The bibliographic identity above, rather than
that machine-local path, makes the reviewed edition independently identifiable.

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
- Change-locality and reversible-learning mechanics belong to the compact
  `agent-behavior` workflow, not to unreviewed human-owner preferences.
- External `writing-for-agents` advice remains optional evidence;
  `.agents/skills/README.md` and its validator own ARIA skill-authoring rules.
- `to-spec` and `to-tickets` replace the removed `to-prd` and `to-issues`
  surfaces without replacing OMX or Agents DB ownership.
- Removed upstream skills and new Claude- or TypeScript-specific helpers do not
  become ARIA routing or truth surfaces.
- No tracked upstream-skill inventory or install command was retained. The CLI
  can select scope, agent, and skill, but those flags do not turn a mutable
  upstream source into an immutable repository policy.

## Verification

The reviewed upstream tree and official installer help were compared with the
proposed policy. Focused governance tests and repository scaffold checks were
run before publication.

## Canonical-State Impact

No external-skill inventory became repository truth. Adopted execution behavior
lives in `agent-behavior`; exact code, tests, configuration, Typst, and source
order retain their existing authority.
