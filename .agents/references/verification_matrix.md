# ARIA-NBV Verification Matrix

Use this matrix after choosing the lane from root `AGENTS.md` or an active
skill. Use the narrowest loop that can prove the claim. If the task is
explanatory, diagnostic, review, planning, or backlog-only, route to the
matching workflow before running broad checks.

## Lane Selection And Debug Pointers

- Read-only explanation or cross-file causality:
  `$oh-my-codex:analyze`; output evidence, inference, unknowns, and the next
  discriminating read-only probe.
- Concrete failure, regression, or suspicious output:
  `diagnose-aria`; capture the exact command, traceback/metric/bad output,
  smallest failing loop, 3-5 falsifiable hypotheses, and passing loop after a
  fix.
- Concrete diff review:
  `code-review`; include severity-ranked findings and file/line evidence.
- Broad scaffold, thesis, or advisor-facing decision:
  `plan-grill`; include success criteria, in/out of scope, assumptions, and
  deferred decisions.
- Backlog, debrief, or memory maintenance:
  `agents-db`; validate active TOML and memory surfaces after edits.

## Agent Scaffold, Skills, Memory

- Skill validation:
  `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/<skill-dir>`
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
  run the task-specific smoke from the cleanup plan and keep ignored OMX plans,
  user-local Codex guidance, and transient pointer markers out of tracked repo
  guidance.

## litkg Guidance Or KG Config

- `make kg-capabilities KG_FORMAT=json`
- `make kg-route KG_TASK="<task>" KG_FORMAT=json`
- `make kg-claim-check KG_CLAIM="<claim>"` for advisor-facing claims

## Autoresearch Adapter Contracts

- Adapter contract evidence:
  `rg -n "Autoresearch Adapter|typed config|checkpoint evaluation|raw shell|proposal" .agents/references/alignment_tools_contract.md AGENTS.md`
- External framework selection remains dependency-free until a later gate:
  `rg -n "langgraph|llama_index|open_deep_research|ai-scientist|karpathy/autoresearch" aria_nbv/pyproject.toml aria_nbv/uv.lock .configs scripts aria_nbv`

## CLI, Streamlit, Rerun, And Visual Gates

- CLI evidence gates must name the exact command, config, output artifact, and
  pass/fail condition in the owning work item before broad automation is added.
- Streamlit and visual gates are contract-only until a work item explicitly adds
  automation. First-wave checks should verify the contract text and expected
  evidence paths, not require screenshots.
- Rerun gates should cite the relevant inspector skill or smoke artifact and
  keep `.rrd` outputs generated unless a task intentionally versions a sample.

## Public Docs

- Frontmatter:
  `make qmd-frontmatter-check`
- Focused Quarto render:
  `cd docs && quarto render <page.qmd>`
- Focused Typst render:
  `cd docs && typst compile typst/seminar_paper/main.typ --root .`
  or `cd docs && typst compile typst/thesis/proposal.typ --root .`

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
