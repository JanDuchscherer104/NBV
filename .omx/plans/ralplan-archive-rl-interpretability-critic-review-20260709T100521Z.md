# Critic Review: Archive RL and Interpretability

VERDICT: APPROVE

Justification:
- No blocking issues found.
- The plan is planning-only and has a durable handoff shape across context, plan, and test-spec artifacts.
- Graphify and `rg` identify the same active Streamlit/test contact surface.

Gate checks:
- Clarity: pass. The chosen option is hard archive plus active-surface removal, and compatibility shims are explicitly rejected.
- Verifiability: pass. Acceptance criteria and checks cover archive paths, active imports, Streamlit navigation, tests, dependencies, lint, `git diff --check`, and `graphify update .`.
- Completeness: pass. Live search confirms the plan's active contacts: `app/config.py`, `app/app.py`, `app/panels.py`, `app/panels/__init__.py`, `app/panels/rl.py`, `app/panels/testing_attribution.py`, plus the listed focused tests.
- Big picture: pass. Optional dependency and docs/backlog cleanup are bounded, not silently forced into the archive change.
- Principle/option consistency: pass. Option A matches hard archive; compatibility shims and page hiding alone are rejected.
- Alternatives depth: pass for this scope.
- Risk/verification rigor: pass. Dirty worktree risk is real, including dirty `testing_attribution.py`, but the plan requires focused status/diff inspection before edits.

Representative simulations:
- Removing Streamlit app edges before moving modules prevents import-time breakage from `app/config.py`, `app/app.py`, and panel re-exports.
- Updating/deleting the named tests removes `RlPageConfig`, `CounterfactualRLEnvConfig`, RL panel, and attribution imports from active tests.
- `streamlit_app.py` is not an extra blocking edge; it imports `NbvStreamlitApp` and config from `aria_nbv.app`, so the planned app/config edits cover it.

Agent:
- `019f4672-65f0-7d32-b4f0-02ea32e436bc`
