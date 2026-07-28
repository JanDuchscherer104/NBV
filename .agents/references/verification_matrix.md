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
- Agent memory:
  `make check-agent-memory`
  Covers repo-owned scaffold alignment checks, required debrief frontmatter,
  and forbidden tracked runtime state.
- Agents DB:
  `make agents-db AGENTS_ARGS='validate'`
  `make agents-db`
- Optional tool boundary smoke:
  `rg -n "alignment_tools_contract|operator-local|evidence producers" AGENTS.md .agents/references .agents/issues.toml .agents/todos.toml .agents/refactors.toml`
- Forbidden repo-runtime references:
  keep ignored OMX plans, user-local Codex guidance, and transient pointer
  markers out of tracked repo guidance.

## Streamlit, Rerun, Offline, And Rollouts

- Streamlit app:
  `cd aria_nbv && uv run nbv-st --server.port <port>`
- Streamlit smoke and panel tests:
  `cd aria_nbv && uv run pytest tests/test_streamlit_entry.py tests/app`
- Live UI symptoms:
  use `diagnose-aria` interactive app inspection when browser tools are
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
  `cd aria_nbv && uv run nbv-rerun-inspect --config-path ../.configs/inspection/rerun/rerun_offline.toml ...`

## KG And Optional Tooling

- Graphify integration and corpus policy:
  `make graphify-integration-self-test`
- Local Graphify navigation freshness:
  `python3 scripts/check_graphify_freshness.py`
- Fast KG health probe:
  `make kg-status`
- KG capabilities and routing:
  `make kg-capabilities KG_FORMAT=json`
  `make kg-route KG_TASK="<task>" KG_FORMAT=json`
- Advisor-facing claim checks:
  `make kg-claim-check KG_CLAIM="<claim>"`
- Autoresearch adapter contract evidence:
  `rg -n "Autoresearch Adapter|typed config|checkpoint evaluation|raw shell|proposal" .agents/references/alignment_tools_contract.md AGENTS.md`
- External framework adoption smoke:
  `rg -n "langgraph|llama_index|open_deep_research|ai-scientist|karpathy/autoresearch" aria_nbv/pyproject.toml aria_nbv/uv.lock .configs scripts aria_nbv`

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
