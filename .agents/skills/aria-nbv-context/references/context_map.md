# Aria NBV Context Map

Use this map to pick the smallest relevant set of files before broad search.

## Concept-to-source matrix

Only the non-obvious cross-surface routes live here. Obvious file-name or heading matches should be handled by `source_index.md`, outlines, or direct `rg`.

| Topic | Canonical state | References | Paper | Quarto docs | Literature | Code | First reveal command |
|---|---|---|---|---|---|---|---|
| Coordinate frames and conventions | `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md`, `.agents/references/external_stack_contracts.md` | `docs/typst/seminar_paper/sections/05-coordinate-conventions.typ`, `docs/typst/seminar_paper/sections/12f-appendix-pose-frames.typ` | `docs/contents/glossary.qmd`, `docs/contents/literature/efm3d.qmd` | `literature/tex-src/arXiv-project-aria/definitions.tex` | `aria_nbv/aria_nbv/pose_generation`, `aria_nbv/aria_nbv/rendering` | `scripts/nbv_typst_includes.py --paper --mode outline` |
| Oracle RRI computation | `.agents/memory/state/PROJECT_STATE.md`, `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/05-oracle-rri.typ`, `docs/typst/seminar_paper/sections/12c-appendix-oracle-rri-labeler.typ` | `docs/reference/index.qmd`, `docs/contents/theory/rri_theory.qmd` | `literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | `aria_nbv/aria_nbv/pipelines/oracle_rri_labeler.py`, `aria_nbv/aria_nbv/rendering/candidate_depth_renderer.py` | `scripts/nbv_get_context.sh match OracleRriLabeler` |
| Candidate generation and pose sampling | `.agents/memory/state/PROJECT_STATE.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/08-system-pipeline.typ` | `docs/reference/index.qmd`, `docs/contents/thesis/questions.qmd#rq3-candidates` | `literature/tex-src/arXiv-GenNBV/3-Method.tex` | `aria_nbv/aria_nbv/pose_generation/` | `scripts/nbv_get_context.sh match candidate` |
| Data contracts and typed containers | `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/06-architecture.typ` | `docs/reference/index.qmd` | — | `aria_nbv/aria_nbv/data_handling/efm_views.py`, `aria_nbv/aria_nbv/vin/types.py`, `aria_nbv/aria_nbv/utils/base_config.py` | `scripts/nbv_get_context.sh contracts` |
| VIN architecture and predictors | `.agents/memory/state/PROJECT_STATE.md`, `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/06-architecture.typ`, `docs/typst/seminar_paper/sections/12g-appendix-vin-v3-streamline.typ` | `docs/reference/index.qmd`, `docs/contents/thesis/roadmap.qmd#roadmap-m2` | `literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex`, `literature/tex-src/arXiv-EFM3D/method.tex` | `aria_nbv/aria_nbv/vin/` | `scripts/nbv_get_context.sh match VinModel` |
| Training objective and configs | `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/OPEN_QUESTIONS.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/07-training-objective.typ`, `docs/typst/seminar_paper/sections/07a-binning.typ`, `docs/typst/seminar_paper/sections/07b-training-config.typ` | `docs/reference/index.qmd` | `literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex` | `aria_nbv/aria_nbv/vin/`, `aria_nbv/aria_nbv/configs/optuna_config.py` | `scripts/nbv_get_context.sh match train` |
| VIN offline stores and dataset splits | `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/GOTCHAS.md` | `.agents/references/python_conventions.md` | `docs/typst/seminar_paper/sections/12h-appendix-offline-cache.typ` | `docs/reference/index.qmd`, `docs/contents/setup.qmd` | `literature/tex-src/arXiv-EFM3D/dataset.tex` | `aria_nbv/aria_nbv/data_handling/_offline_dataset.py`, `aria_nbv/aria_nbv/data_handling/_offline_store.py`, `aria_nbv/aria_nbv/data_handling/_offline_writer.py` | `scripts/nbv_get_context.sh match VinOffline` |

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
