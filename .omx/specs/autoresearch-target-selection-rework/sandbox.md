# Autoresearch Sandbox: Target Selection Rework

## Scope

Read-only research plus artifact creation. No production Python, thesis, Quarto,
or canonical memory state files were edited during this iteration.

## Sources Inspected

- `/home/jd/.codex/sessions/2026/06/17/rollout-2026-06-17T11-12-21-019ed4da-5d8f-7740-a68e-e2ee800d7bee.jsonl`
- `.omx/goals/autoresearch/aria-nbv-current-target-selection-methodology-au/`
- `.agents/memory/transcripts/distilled/2026-06-18/{candidate_decisions.jsonl,reviewed_decisions.jsonl,manifest.json}`
- `.agents/work/target-selection-sampling/current-target-selection-audit-2026-06-17.md`
- `.agents/work/target-selection-sampling/01-review-gpt55pro.md`
- `.agents/work/target-selection-sampling/02-review-gpt55pro.md`
- `docs/typst/thesis/sections/03-method.typ`
- `docs/contents/theory/candidate_sampling_target_selection.qmd`
- `docs/contents/thesis/questions.qmd`
- `.agents/memory/state/DECISIONS.md`
- `.agents/memory/state/OPEN_QUESTIONS.md`
- `.agents/issues.toml`
- `.agents/todos.toml`
- `aria_nbv/aria_nbv/data_handling/_target_selection.py`
- `aria_nbv/tests/data_handling/test_target_selection.py`
- `aria_nbv/aria_nbv/rollouts/dataset_writer.py`
- `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/app/panels/target_audit.py`
- `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py`
- `aria_nbv/aria_nbv/pose_generation/positional_sampling.py`
- `.configs/build_rollouts_v1_realistic.toml`

## Local Commands Used

- `make kg-status`
- `make kg-route KG_TASK="Aggregate evidence for reworking ARIA-NBV V1 target selection into actor-visible labelable target-pool sampling with stratified support visibility distance class and hard-turn bins"`
- `rg` / `sed` / targeted Python transcript parsing for local evidence extraction.

## Known Limitations

- `make kg-search` was observed in lexical-only mode because the local embedding
  backend was unreachable; `make kg-status` itself passed.
- The prior transcript mission artifact for
  `019ed4da-5d8f-7740-a68e-e2ee800d7bee` ended in a blocked reconciliation
  state, but its target-selection audit evidence and professor-critic synthesis
  were still available and usable.
