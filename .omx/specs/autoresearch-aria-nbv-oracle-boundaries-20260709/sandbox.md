# Sandbox

This autoresearch pass is planning/review only.

Allowed writes:

- `.omx/specs/autoresearch-aria-nbv-oracle-boundaries-20260709/**`
- `.omx/state/autoresearch-aria-nbv-oracle-boundaries-20260709/**`
- `.agents/memory/history/2026/07/**` debrief only if needed

Read sources:

- Current code under `aria_nbv/aria_nbv/{rri_metrics,rollouts,pipelines,data_handling}`
- Previous OMX plans/specs under `.omx/plans` and `.omx/specs`
- Repo guidance from `AGENTS.md` and nearest package guides
- Graphify navigation output when available

Validation:

- Independent architect-style approval must be recorded in `completion.json`.
- Local artifact checks must pass: non-empty report, JSON-valid completion/state, `git diff --check`, and `make check-agent-memory` if a debrief is written.

