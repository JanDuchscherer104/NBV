---
name: counterfactual-rollout-planner
description: Use when ARIA-NBV work touches ASE counterfactual rollouts, non-myopic planning evaluation, invalid-action handling, stochastic branches, finite-candidate candidate-query Transformer Q_H, or the roadmap value/RL gate. Gymnasium/SB3 is post-M6 bridge work only.
metadata:
  mode: implementation
  not_when:
    - "one-step VIN scoring with no rollout, Q_H, or non-myopic evaluation surface"
    - "generic geometry, data-cache, or Streamlit debugging without rollout semantics"
  handoff_to:
    - "diagnose-aria for concrete rollout failures or suspicious metrics"
    - "nbv-geometry-contracts for pose, camera, projection, or frame-contract issues"
    - "entity-aware-rri for target-crop or target-specific RRI ownership"
    - "plan-grill for thesis-scope planning before changing roadmap claims"
  evidence_required:
    - "horizon, branch/beam width, candidate budget, and acquisition budget"
    - "validity mask and invalid-reason treatment for selected actions"
    - "oracle-evaluated cumulative target gain or explicit reason it is unavailable"
  applies_to:
    - "aria_nbv/aria_nbv/pose_generation/**"
    - "aria_nbv/aria_nbv/rl/**"
    - "docs/contents/thesis/**"
    - ".agents/references/rollout_zarr_q_invalidity_contract.md"
  triggers:
    - "counterfactual rollout"
    - "bounded lookahead"
    - "Q_H"
    - "invalid action"
  must_read:
    - "docs/contents/thesis/roadmap.qmd#roadmap-m5"
    - "docs/contents/thesis/questions.qmd#rq2-offline-qh"
    - ".agents/memory/state/PROJECT_STATE.md"
    - ".agents/references/rollout_zarr_q_invalidity_contract.md"
  canonical_sources:
    - "docs/contents/thesis/roadmap.qmd#roadmap-m5"
    - "docs/contents/thesis/questions.qmd#rq2-offline-qh"
    - "docs/contents/theory/rl_planning.qmd#q-h-training-contract"
    - ".agents/references/rollout_zarr_q_invalidity_contract.md#mask-semantics"
    - "aria_nbv/aria_nbv/rollouts/AGENTS.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/farama-foundation/gymnasium"
    - "/dlr-rm/stable-baselines3"
  literature_refs:
    - "finite-candidate-rl"
    - "continuous-nbv-bridge"
    - "DoubleDQN-vanHasselt2015"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.get_library_docs"
  verification:
    - "cd aria_nbv && uv run pytest tests/pose_generation/test_counterfactuals.py"
    - "cd aria_nbv && uv run pytest tests/rl/test_counterfactual_env.py"
---

# Counterfactual Rollout Planner

## OMX Integration

OMX owns planning and execution gates; this skill supplies ARIA rollout and Q_H
semantics for those gates. Return exact rollout budgets, evidence artifacts,
and focused verification loops rather than a standalone workflow.

## When To Use

Use this skill for:

- deterministic oracle, greedy, stochastic, beam, model-scored, or oracle
  rollouts over ASE finite candidate sets
- cumulative RRI, path cost, invalid action rate, and runtime metrics
- finite-candidate candidate-query Transformer `Q_H` training and evaluation
- M5 planning/value decisions and M6 bridge boundaries

Do not use it for one-step VIN scoring unless the output drives rollout
selection or evaluation.

Use Gymnasium/SB3 only when the task explicitly targets the post-M6 online
simulator bridge after the ASE rollout and Q_H path is stable.

## Read First

1. `docs/contents/thesis/roadmap.qmd` sections M5 and M6
2. `docs/contents/thesis/questions.qmd` sections RQ4, RQ5, and the shared
   evidence protocol
3. `aria_nbv/AGENTS.md`
4. `.agents/memory/state/PROJECT_STATE.md`
5. Relevant `pose_generation` and `rl` tests

## Rules

- Keep horizons, branch factors, and beam widths explicit.
- Treat `beam_width` as the number of sampled rollout chains retained per step,
  not as unbounded tree branching. The default bounded cost model is
  `O(B * L * N)` for beam width `B`, horizon `L`, and candidates per state `N`.
- For stochastic planning, score all valid candidates, sample with explicit
  softmax temperature for the first `Q_H` rollout-diversity source, and use
  Gumbel-Top-k when distinct sampled roots or chains are required later.
- Score all candidates but materialize expensive counterfactual modalities only
  for selected actions or retained chains.
- Report cumulative target or scene RRI together with acquisition cost,
  invalid action rate, and runtime.
- Treat online discrete `Q_H` over finite candidates as the RQ5 bridge after
  stable offline `Q_H` evidence; full continuous control and generic
  simulator-backed RL remain RQ6/stretch until the roadmap evidence gate
  passes.
- Keep actor-visible, critic-visible, and oracle-only signals separate.
- Mask invalid candidates before selection and preserve explicit invalid reason
  summaries.
- Oracle-evaluate selected learned rollouts before using them for claims.
- Log equal acquisition budget and candidate-budget parity for comparisons.
- Rollout traces should record scene/snippet, horizon step, chain id, selected
  candidate id, score source, predicted RRI, oracle RRI when available,
  cumulative RRI, path cost, validity mask summary, invalid reason summary, and
  runtime.

## Verification

- `cd aria_nbv && uv run pytest tests/pose_generation/test_counterfactuals.py`
- `cd aria_nbv && uv run pytest tests/rl/test_counterfactual_env.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_rl_panel.py`
- `cd docs && quarto render contents/thesis/roadmap.qmd contents/thesis/questions.qmd` when claims or roadmap text change
