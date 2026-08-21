---
id: 2026-08-21_streamlit_guidance_strategy_research
date: 2026-08-21
title: "Streamlit guidance strategy research"
status: done
topics: [streamlit, agent-guidance, progressive-disclosure, app-architecture]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/specs/autoresearch-streamlit-guidance/report.md
  - .omx/specs/autoresearch-streamlit-guidance/result.json
---

## Task

Decide whether ARIA-NBV should adopt externally maintained Streamlit skills,
where local Streamlit preferences should live, and which prior debrief/session
requirements should constrain future app work.

## Method

- Queried the existing Graphify projection, then verified exact app sources and
  focused tests in the split-repair worktree.
- Inspected the resolved Streamlit 1.57 environment and its bundled application
  skill.
- Compared the official application skill with the two framework-maintainer
  skills named by the user, official public docs, release/install behavior, and
  licensing.
- Mined Streamlit debriefs and the exact source session for explicit user
  requirements.
- Passed the report through an independent architect review and repaired two
  P1 wording/contract mismatches before approval.

## Findings

- The correct external baseline is Streamlit's version-matched
  `developing-with-streamlit` application skill, not the framework-monorepo
  debugging or architecture skills.
- In the current 1.57 environment, agents can consult the bundled source but
  cannot invoke `streamlit skills`; a global invokable meta-skill should follow
  only after a separately verified upgrade to Streamlit 1.58 or later.
- `aria_nbv/aria_nbv/app/AGENTS.md` should own ARIA-specific implementation,
  state/cache, laziness, scientific-presentation, Rerun, and verification rules.
- `aria_nbv/aria_nbv/app/README.md` should own human launch, navigation, and
  troubleshooting guidance.
- Default-visible bounded diagnostics are compatible with laziness; full-store
  aggregates, deep Q_H reads, and unbounded evidence require explicit dispatch.

## Verification

- Autoresearch completion artifact records independent architect approval with
  no remaining P0-P2 findings.
- State and result JSON parse successfully.
- Local report links and Markdown diff checks pass.

## Canonical-state impact

This task produced an approved research recommendation but did not change
current app behavior or guidance. The app `AGENTS.md` and README remain explicit
follow-up owners rather than being silently created during research.
