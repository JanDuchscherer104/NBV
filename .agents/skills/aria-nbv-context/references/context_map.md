# ARIA-NBV Derived Context Route Index

Use this derived index only for non-obvious cross-surface and literature route
labels. The owner hierarchy in `../SKILL.md#owner-hierarchy` resolves authority;
this file provides first-reveal commands and never owns the facts it locates.

## Active thesis and shared scientific language

Use this lane before historical papers whenever the question is thesis-facing.
Generated files are projections; open the human-edited owner named below.

| Intent | Current owner | Supporting surface | First reveal |
|---|---|---|---|
| Active thesis prose and section hierarchy | `docs/typst/thesis/main.typ` and its recursive includes | `docs/typst/thesis/development/roadmap.typ`, `docs/typst/thesis/sections/01-research-questions.typ` | `scripts/nbv_typst_includes.py --thesis --mode outline` |
| Durable term or glossary anchor | `docs/typst/shared/glossary.typ` | `docs/contents/glossary.qmd` is generated public output | `rg -n 'key:|short:|long:|anchor:' docs/typst/shared/glossary.typ` |
| Reusable Typst symbol body and metadata | `docs/typst/shared/symbols.typ` and `docs/typst/shared/symbols/*.typ` | `docs/notation.yml` is a generated cross-format adapter | `rg -n '<term>|#let' docs/typst/shared/symbols*.typ docs/typst/shared/symbols` |
| Reusable equation body and metadata | `docs/typst/shared/equations.typ` and `docs/typst/shared/equations/*.typ` | `docs/notation.yml` is a generated cross-format adapter | `rg -n '<term>|#let' docs/typst/shared/equations*.typ docs/typst/shared/equations` |
| Printed thesis symbol list | shared symbol/equation facade metadata | `docs/typst/shared/notation.typ`; `notation.generated.typ` is generated | `rg -n '<term>|thesis_list' docs/typst/shared/{symbols,equations}.typ` |

## Concept-to-source matrix

Only the non-obvious cross-surface routes live here. Obvious file-name or heading matches should be handled by `source_index.md`, outlines, or direct `rg`.

| Topic | Current owner | References | Historical seminar evidence | Quarto docs | Literature | Code | First reveal command |
|---|---|---|---|---|---|---|---|
| Coordinate frames and conventions | `aria_nbv/aria_nbv/pose_generation`, `aria_nbv/aria_nbv/rendering` | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/05-coordinate-conventions.typ`, `docs/typst/seminar_paper/sections/12f-appendix-pose-frames.typ` | `docs/contents/glossary.qmd`, `docs/contents/literature/efm3d.qmd` | `docs/literature/tex-src/arXiv-project-aria/definitions.tex` | `aria_nbv/aria_nbv/pose_generation`, `aria_nbv/aria_nbv/rendering` | `scripts/nbv_typst_includes.py --seminar --mode outline` |
| Oracle evidence and private scoring engine | `aria_nbv/aria_nbv/oracle/evidence.py`, `aria_nbv/aria_nbv/oracle/_scoring.py` | `aria_nbv/aria_nbv/oracle/README.md`, `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/05-oracle-rri.typ`, `docs/typst/seminar_paper/sections/12c-appendix-oracle-rri-labeler.typ` | `docs/reference/index.qmd`, `docs/contents/theory/rri_theory.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/oracle/evidence.py`, `aria_nbv/aria_nbv/oracle/_scoring.py` | `scripts/nbv_get_context.sh match PreparedRriScorer` |
| Scene-RRI scoring | `aria_nbv/aria_nbv/oracle/scene_rri.py` | `aria_nbv/aria_nbv/oracle/README.md`, `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/05-oracle-rri.typ` | `docs/reference/index.qmd`, `docs/contents/theory/rri_theory.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/oracle/scene_rri.py` | `scripts/nbv_get_context.sh match SceneRriScorer` |
| Target-RRI scoring | `aria_nbv/aria_nbv/oracle/target_rri.py` | `aria_nbv/aria_nbv/oracle/README.md`, `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/05-oracle-rri.typ` | `docs/reference/index.qmd`, `docs/contents/theory/rri_theory.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/oracle/target_rri.py` | `scripts/nbv_get_context.sh match TargetRriScorer` |
| Oracle label DTOs and retained evidence | `aria_nbv/aria_nbv/oracle/labels.py` | `aria_nbv/aria_nbv/oracle/README.md`, `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/12c-appendix-oracle-rri-labeler.typ` | `docs/reference/index.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/oracle/labels.py` | `scripts/nbv_get_context.sh match OracleCandidateLabels` |
| Oracle label-generation pipelines | `aria_nbv/aria_nbv/oracle/pipelines/` | `aria_nbv/aria_nbv/oracle/README.md`, `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/12c-appendix-oracle-rri-labeler.typ` | `docs/reference/index.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/oracle/pipelines/`, `aria_nbv/aria_nbv/rendering/candidate_depth_renderer.py` | `scripts/nbv_get_context.sh match OracleRriLabeler` |
| Candidate generation and pose sampling | `aria_nbv/aria_nbv/pose_generation/` | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/08-system-pipeline.typ` | `docs/reference/index.qmd`, `docs/typst/thesis/sections/01-research-questions.typ#ssec:rq4` | `docs/literature/tex-src/arXiv-GenNBV/3-Method.tex` | `aria_nbv/aria_nbv/pose_generation/` | `scripts/nbv_get_context.sh match candidate` |
| Data contracts and typed containers | `aria_nbv/aria_nbv/data_handling/ase_efm/views.py`, `aria_nbv/aria_nbv/vin/types/`, `aria_nbv/aria_nbv/utils/base_config.py` | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/06-architecture.typ` | `docs/reference/index.qmd` | — | `aria_nbv/aria_nbv/data_handling/ase_efm/views.py`, `aria_nbv/aria_nbv/vin/types/`, `aria_nbv/aria_nbv/utils/base_config.py` | `scripts/nbv_get_context.sh contracts` |
| VIN architecture and predictors | `aria_nbv/aria_nbv/vin/` | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/06-architecture.typ`, `docs/typst/seminar_paper/sections/12g-appendix-vin-v3-streamline.typ` | `docs/reference/index.qmd`, `docs/typst/thesis/development/roadmap.typ#ssec:milestones` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex`, `docs/literature/tex-src/arXiv-EFM3D/method.tex` | `aria_nbv/aria_nbv/vin/` | `scripts/nbv_get_context.sh match VinModel` |
| Training objective and configs | `aria_nbv/aria_nbv/vin/`, `aria_nbv/aria_nbv/configs/optuna_config.py`, focused tests | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/07-training-objective.typ`, `docs/typst/seminar_paper/sections/07a-binning.typ`, `docs/typst/seminar_paper/sections/07b-training-config.typ` | `docs/reference/index.qmd` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex` | `aria_nbv/aria_nbv/vin/`, `aria_nbv/aria_nbv/configs/optuna_config.py` | `scripts/nbv_get_context.sh match train` |
| VIN offline stores and dataset splits | `aria_nbv/aria_nbv/data_handling/vin_store/dataset.py`, `aria_nbv/aria_nbv/data_handling/vin_store/store.py`, `aria_nbv/aria_nbv/data_handling/vin_store/writer.py`, setup docs | `aria_nbv/AGENTS.md` | `docs/typst/seminar_paper/sections/12h-appendix-offline-cache.typ` | `docs/reference/index.qmd`, `docs/contents/setup.qmd` | `docs/literature/tex-src/arXiv-EFM3D/dataset.tex` | `aria_nbv/aria_nbv/data_handling/vin_store/dataset.py`, `aria_nbv/aria_nbv/data_handling/vin_store/store.py`, `aria_nbv/aria_nbv/data_handling/vin_store/writer.py` | `scripts/nbv_get_context.sh match VinOffline` |

## Literature evidence routing

These rows are routing handles, not paper summaries. Use them to reveal the
owning literature page, citation keys, and local source mirrors before writing
advisor-facing claims.

| Concept route | Quarto owner | Representative citation keys | Local source mirrors | First reveal command |
|---|---|---|---|---|
| `quality-driven-rri` | `docs/contents/literature/vin_nbv.qmd` | `VIN-NBV-frahm2025` | `docs/literature/tex-src/arXiv-VIN-NBV/` | `scripts/nbv_literature_search.sh RRI` |
| `egocentric-aria-substrate` | `docs/contents/literature/project_aria.qmd`, `docs/contents/literature/efm3d.qmd` | `projectaria-engel2023`, `ProjectAria-ASE-2025`, `EFM3D-straub2024`, `EVL-Doc-2025` | `docs/literature/tex-src/arXiv-project-aria/`, `docs/literature/tex-src/arXiv-EFM3D/` | `scripts/nbv_literature_search.sh EFM3D` |
| `finite-candidate-rl` | `docs/contents/literature/rl_planning.qmd` | `DoubleDQN-vanHasselt2015`, `DuelingDQN-wang2016`, `IQL-kostrikov2021`, `CQL-kumar2020`, `BCQ-fujimoto2019` | `docs/literature/tex-src/arXiv-DQN/`, `docs/literature/tex-src/arXiv-Double-DQN/`, `docs/literature/tex-src/arXiv-CQL/`, `docs/literature/tex-src/arXiv-BCQ/` | `scripts/nbv_literature_search.sh Double` |
| `continuous-nbv-bridge` | `docs/contents/literature/gen_nbv.qmd`, `docs/contents/literature/hestia.qmd`, `docs/contents/literature/pb_nbv.qmd` | `GenNBV-chen2024`, `Hestia-lu2026`, `PB-NBV-jia2025` | `docs/literature/tex-src/arXiv-GenNBV/`, `docs/literature/tex-src/arXiv-Hestia/`, `docs/literature/tex-src/arXiv-PB-NBV/` | `scripts/nbv_literature_search.sh PPO` |
| `radiance-field-nbv-bridge` | `docs/contents/literature/active_3dgs_nbv.qmd`, `docs/contents/literature/scone_fisherrf.qmd` | `ActiveNeRF-pan2022`, `FisherRF-jiang2024`, `ObjectCentricNBV-jeong2026`, `li2025bestviewselectionssemantic`, `FOVHPE-bae2025` | `docs/literature/tex-src/arXiv-FisherRF/`, `docs/literature/tex-src/arXiv-Instance-NBV/`, `docs/literature/tex-src/arXiv-Dynamic-3DGS/` | `scripts/nbv_literature_search.sh FisherRF` |
| `semantic-scene-memory-bridge` | `docs/contents/literature/scene_script.qmd` | `SceneScript-avetisyan2024` | `docs/literature/tex-src/arXiv-scene-script/` | `scripts/nbv_literature_search.sh SceneScript` |
