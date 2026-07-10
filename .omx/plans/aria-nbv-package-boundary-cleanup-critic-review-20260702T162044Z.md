# Critic Review

Initial verdict: ITERATE

Confidence: high

## Critical findings

- Validation was not concrete enough for execution. The plan's broad `rg`
  check would hit historical/archive/memory references, not just active stale
  imports.
- The validation list omitted touched surfaces proven by current imports:
  `aria_nbv/aria_nbv/rl/counterfactual_env.py`,
  `aria_nbv/tests/rl/test_counterfactual_env.py`,
  `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`, and
  `aria_nbv/tests/data_handling/test_public_api_contract.py`.
- The plan omitted required lint/format checks despite `rollouts/AGENTS.md`
  requiring `ruff format` and `ruff check` for touched rollout files.

## Plan risks

- The root `pose_generation.__init__` exports are currently used by tests and
  app helpers; the handoff should explicitly say these are intentionally moved
  to direct `aria_nbv.rollouts` imports, not preserved by a facade.
- Docs references include `docs/_quarto.yml`, `docs/reference/_sidebar.yml`,
  and thesis code references; these need an explicit active-docs update or
  deliberate archive exception.
- Option A is otherwise consistent and does not smuggle target descriptors,
  target-conditioned scoring, Q_H, scene-memory, or broad app/data
  restructuring.

## Required changes before implementation

- Update the execution handoff and validation with exact added checks:
  `uv run pytest tests/rl/test_counterfactual_env.py`,
  `uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py`,
  `uv run pytest tests/data_handling/test_public_api_contract.py`, plus
  `ruff format --check` and `ruff check` on touched files.
- Replace the stale-reference `rg` with a scoped active-surface command that
  excludes `.agents/archive/**`, transcript/history dumps, and generated/site
  output, or explicitly classifies allowed historical hits.
- Add current live import/doc sites to Option A's handoff list so the executor
  does not guess the migration surface.

## Consensus gate

HOLD until the required changes are applied.

## Resolution applied

The ralplan was updated with known live migration surfaces, explicit
formatter/linter/test checks, direct-import intent for moved root exports, and
a scoped active-surface reference scan.

## Final re-review

Verdict: APPROVE

Confidence: high

Critical findings: none.

Plan risks:

- `tests/rl/test_counterfactual_env.py` is dependency-gated, so a skip must be
  reported with the exact missing dependency if it cannot run.
- Docs/API navigation changes may require regenerated reference output later,
  but the active source files are now named in the handoff.

Required changes before implementation: none.

Consensus gate: PASS

Rationale: the iteration directly closed the prior HOLD items. Option A now
names the live migration surface, states the intended root-export move without
a compatibility facade by default, adds the missing RL/app/public-API tests,
adds `ruff format --check` and `ruff check`, and replaces the noisy broad
stale-reference scan with an active-surface scan plus historical/archive
classification. The plan remains bounded to PR #15 cleanup and does not
smuggle target descriptors, target-conditioned scoring, Q_H, scene-memory,
online RL core, or broad app/data restructuring.
