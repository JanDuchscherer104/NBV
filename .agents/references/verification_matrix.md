# ARIA-NBV Verification Matrix

Use the narrowest command that proves the claim for the touched surface. Workflow
routing lives in root `AGENTS.md` and the active skill; this file is only a
compact command index.

## Agent Scaffold, Skills, Memory

- Skill validation:
  `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/<skill-dir>`
- Scaffold audit:
  `make scaffold-audit`
  `make scaffold-audit-self-test`
- Final scaffold budgets and tracked-output policy:
  `make wp7-integration-check`
- Pinned Matt closure, isolation, routing, rollback, and prompt budget:
  `make matt-policy-self-test`
- Agent memory:
  `make check-agent-memory`
  Covers repo-owned scaffold alignment checks, required debrief frontmatter,
  and forbidden tracked runtime state.
- Registered OMX planning evidence:
  `make omx-artifacts-check`
  Runs lifecycle fixtures plus live registry, hash, placement, history, and
  unregistered-path validation.
- Agents DB:
  `make agents-db AGENTS_ARGS='validate'`
  `make agents-db`
- Optional tool boundary smoke:
  `rg -n "alignment_tools_contract|operator-local|evidence producers" AGENTS.md .agents/references .agents/issues.toml .agents/todos.toml .agents/refactors.toml`
- Forbidden repo-runtime references:
  keep unregistered OMX drafts/runtime state, user-local Codex guidance, and
  transient pointer markers out of tracked repo guidance.

## Streamlit, Rerun, Offline, And Rollouts

- Streamlit app:
  `cd aria_nbv && uv run nbv-st --server.port <port>`
- Streamlit smoke and panel tests:
  `cd aria_nbv && uv run pytest tests/test_streamlit_entry.py tests/app`
- Live UI symptoms:
  use the selected diagnostic workflow's interactive app inspection when browser tools are
  available.
- Rerun launch helper tests:
  `cd aria_nbv && uv run pytest tests/app/test_rerun_launch.py`
- Offline store inspection:
  `make offline-info`
  `make offline-tree`
  `make offline-samples`
  `make offline-sample-rerun-random`
- Rollout store inspection:
  `make rollouts-info`
  `make rollouts-stats`
  `make rollouts-rerun-random`
- Direct Rerun inspector:
  `cd aria_nbv && uv run nbv-rerun-inspect --config-path ../.configs/rerun_offline.toml ...`

## Exact-Source And Optional Tooling

- Graphify integration and corpus policy:
  `make graphify-ci`
- Local Graphify navigation freshness:
  `python3 scripts/check_graphify_freshness.py`
- Advisor-facing claim checks:
  follow `.agents/references/direct_source_claim_checklist.md`
- Exact-source fallback:
  `make wp6-direct-source-check`
- Autoresearch adapter contract evidence:
  `rg -n "Autoresearch Adapter|typed config|checkpoint evaluation|raw shell|proposal" .agents/references/alignment_tools_contract.md AGENTS.md`
- External framework adoption smoke:
  `rg -n "langgraph|llama_index|open_deep_research|ai-scientist|karpathy/autoresearch" aria_nbv/pyproject.toml aria_nbv/uv.lock scripts aria_nbv`

## Public Docs

- Frontmatter:
  `make qmd-frontmatter-check`
- Focused Quarto render:
  `cd docs && quarto render <page.qmd>`
- Focused Typst render:
  `cd docs && typst compile typst/seminar_paper/main.typ --root .`
  or `cd docs && typst compile typst/thesis/main.typ --root .`

## Python Package

- Format:
  `ruff format <file>`
- Lint:
  `ruff check <file>`
- Targeted tests:
  `cd aria_nbv && uv run pytest <path>`

## Research Contract Examples

- Data handling/offline store:
  `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py`
- RRI:
  `cd aria_nbv && uv run pytest tests/rri_metrics`
- Rollouts:
  `cd aria_nbv && uv run pytest tests/pose_generation/test_counterfactuals.py`
- Rerun inspector:
  run the focused inspector tests or smoke command named by
  `rerun-nbv-inspector`.
