# Sandbox

- Mission root: `.omx/specs/autoresearch-rollout-candidate-diversity-pilot-20260824`
- Validation mode: `prompt-architect-artifact`
- Output artifact: `report.md`
- Completion artifact: `result.json`
- Lifecycle state: `.omx/state/autoresearch-rollout-candidate-diversity-pilot-20260824/autoresearch-state.json`
- Allowed writes: this mission root, its lifecycle state, and ignored derived
  Graphify projection/navigation state required by the repository's freshness
  gate.
- Read-only evidence: pilot rollouts, repository source/config/tests/docs,
  Graphify navigation, Git history, live GitHub issues, and external sources.
- Forbidden mutations: package/config/docs changes, rollout regeneration,
  artifact rewrites, Git state changes, and GitHub comments/edits.
- Unrelated pre-existing worktree changes must remain untouched.
