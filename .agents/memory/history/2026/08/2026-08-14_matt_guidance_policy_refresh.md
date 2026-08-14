---
id: 2026-08-14_matt_guidance_policy_refresh
date: 2026-08-14
title: "Matt Guidance Policy Refresh"
status: done
topics: [agent-scaffold, mattpocock-skills, guidance, policy]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/references/mattpocock_skills_manifest.toml
  - scripts/tests/test_agent_governance_g002.py
---

## Task

Refresh ARIA-NBV's tracked policy for `mattpocock/skills` without importing
generic programming principles into hot-path repository guidance.

## Method

Compared the tracked manifest with all 35 skill entry points at upstream commit
`8b78b531ab965735c5dc74f6f7a219e1e37326df`, checked the operator-local Codex
installation, and retained ARIA's source-order owners for durable meaning.

## Findings

- `codebase-design` remains an explicit capability routed through `aria-grill`.
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

The tracked external-skill policy is current at the reviewed commit. Exact code,
tests, configuration, Typst, source order, and human-owner intent retain their
existing authority.
