# Autoresearch Sandbox

## Scope

Read-only verification over local ARIA-NBV repository sources. Runtime artifacts
are written only under `.omx/specs/autoresearch-source-of-truth-conflicts/` and
`.omx/state/autoresearch-source-of-truth-conflicts/`.

## Primary Inputs

- `.agents/work/source-of-truth-conflicts.md`
- `AGENTS.md`
- `docs/AGENTS.md`
- `.agents/references/source_order.md`
- `.agents/references/alignment_tools_contract.md`
- `docs/contents/thesis/questions.qmd`
- `docs/contents/thesis/roadmap.qmd`
- `.agents/memory/state/*.md`
- advisor/proposal/slides/README/nav/backlog/code surfaces cited in the report

## Verification Commands

```sh
rg -n "^## (C[0-9]+|R[0-9]+)|^# " .agents/work/source-of-truth-conflicts.md
rg -n "highest-level project ground truth|seminar paper|current thesis direction" AGENTS.md docs/AGENTS.md docs/index.qmd .agents/references/source_order.md
rg -n "RQ1|RQ2|RQ3|RQ4|RQ5|RQ6" docs/contents/thesis/questions.qmd docs/contents/thesis/roadmap.qmd docs/typst/thesis/advisor_meeting_2026_05_22.typ docs/contents/thesis/advisor_meeting_2026_05_22_questions.md .agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md
rg -n "root-normalized|state-relative|target_error|gamma|discount|clipping|near-solved" docs/contents/thesis/questions.qmd docs/contents/thesis/roadmap.qmd docs/typst/thesis/advisor_distillation.typ docs/typst/thesis/sections/proposal docs/typst/shared .agents/memory/state/*.md
rg -n "vin_offline\\.counterfactuals|rollouts\\.zarr|OFFLINE_DATASET_VERSION|counterfactuals" docs .agents aria_nbv README.md
rg -n "Gymnasium|SB3|PPO|online RL|M6|bridge|stretch" AGENTS.md docs/contents/thesis/questions.qmd docs/contents/thesis/roadmap.qmd docs/typst/thesis_slides/slides_thesis_outlook.typ aria_nbv/aria_nbv/rl .agents/memory/state/*.md
rg -n "MSc Slides 01|m1_contract_report|advisor_distillation|Typst slides" docs/_quarto.yml docs/AGENTS.md .agents/references/source_order.md docs/contents/thesis/m1_contract_report.qmd .agents/todos.toml
rg -n "TARGET_POINT|RADIAL_AWAY|RADIAL_TOWARDS|FORWARD_RIG|UNIFORM_SPHERE|FORWARD_POWERSPHERICAL|forward_local|target_bearing_local|lateral_target_bypass" aria_nbv/aria_nbv/pose_generation docs/contents/thesis/questions.qmd .agents/memory/state/DECISIONS.md .agents/todos.toml
python3 - <<'PY'
from pathlib import Path
report = Path(".omx/specs/autoresearch-source-of-truth-conflicts/report.md").read_text()
missing = [f"C{i}" for i in range(1, 17) if f"### C{i}" not in report]
missing += [f"R{i}" for i in range(1, 5) if f"### R{i}" not in report]
if missing:
    raise SystemExit(f"missing report items: {missing}")
required = [
    "docs/index.qmd:47",
    "docs/contents/thesis/questions.qmd:119",
    "docs/typst/thesis/advisor_meeting_2026_05_22.typ:142",
    "docs/typst/thesis/advisor_distillation.typ:282",
    "docs/contents/thesis/m1_contract_report.qmd:43",
    "aria_nbv/aria_nbv/data_handling/_offline_store.py:33",
]
for token in required:
    if token not in report:
        raise SystemExit(f"missing required evidence token: {token}")
print("source-of-truth conflict report validates")
PY
```
