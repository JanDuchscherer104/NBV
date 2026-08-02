# Context7 Library IDs

This is the fallback inventory for external library documentation. Prefer the
localized domain skill's smaller `metadata.context7_refs` list; use this file
only when no retained skill owns the external API question.

## Use order

1. Open the local package/docs owner and installed call site first.
2. Select one exact ID from the owning skill metadata or this inventory.
3. Request the smallest topic-specific official-doc slice.
4. Re-resolve the ID before consequential API or dependency changes; Context7
   availability and rankings can change.
5. Verify the answer against the installed version, local source, and focused
   tests. Context7 evidence never replaces ARIA behavior or scientific owners.

## Typst publication packages

- `/websites/typst_app` - Typst language and standard-library documentation.
- `/typst-community/glossarium` - Glossarium term registration, references, and
  printing behavior used by the shared glossary.
- `/cetz-package/cetz` - CeTZ canvas, coordinates, projections, and drawing APIs.
- `/jollywatt/typst-fletcher` - Fletcher diagrams, nodes, edges, and CeTZ
  integration.
- `/touying-typ/touying` - Touying slide composition and reveal behavior.
- `/websites/quarto` - Quarto documentation and publishing behavior.

## Package, data, geometry, and operations

- `/facebookresearch/atek` - Aria Training and Evaluation Kit. Used for raw ASE/ATEK snippet semantics, dataset field conventions, and vendor-aligned loader behavior.
- `/websites/facebookresearch_github_io_projectaria_tools` - Project Aria Tools docs. Used for Aria calibration, trajectory, and VRS/pose tooling behavior that surfaces through our data and rendering stacks.
- `/facebookresearch/efm3d` - Egocentric Foundation Models for 3D understanding. Used for the vendored EFM3D backbone, tensor wrappers, and Aria snippet structures that our training/data pipeline builds on.
- `/websites/hydra_cc` - Hydra configuration composition and runtime behavior.
- `/omry/omegaconf` - OmegaConf containers, interpolation, merging, and structured configuration behavior used beneath Hydra.
- `/websites/mojolang` - Mojo language docs from Modular. Used for official guidance on Python interop, Python-importable Mojo modules, FFI, and GPU kernel primitives when evaluating targeted acceleration work for `aria_nbv`.
- `/lightning-ai/pytorch-lightning` - PyTorch Lightning. Used for trainer/datamodule behavior, callback integration, and fit/validation loop semantics in the VIN training stack.
- `/mikedh/trimesh` - Mesh processing and analysis. Used for processed ASE mesh loading, simplification, and geometric utilities in mesh-cache and rendering helpers.
- `/wandb/wandb` - Weights & Biases. Used for experiment tracking, logging, and sweep integration in Lightning training workflows.
- `/websites/optuna_readthedocs_io_en_stable` - Optuna. Used for hyperparameter search and trial orchestration around the Lightning training entrypoints.
- `/pytorch/pytorch` - PyTorch. Used for tensor semantics, dataset/dataloader behavior, serialization compatibility, and model execution throughout the package.
- `/facebookresearch/pytorch3d` - PyTorch3D. Used for candidate depth rendering, camera representations, and geometric transforms in oracle labeling and diagnostics.
- `/plotly/plotly.py` - Plotly. Used for interactive diagnostics and visualization in app/reporting surfaces.
- `/dfki-ric/pytransform3d` - pytransform3d. Used for transform conversions and pose utilities where projectaria/EFM wrappers are not sufficient.
- `/isl-org/open3d` - Open3D. Used for point-cloud visualization and geometry inspection utilities.
- `/farama-foundation/gymnasium` - Gymnasium. Used for custom RL environment interfaces, reset/step contracts, and observation/action-space definitions for sequential counterfactual pose selection.
- `/dlr-rm/stable-baselines3` - Stable Baselines3. Used for PPO-ready training, environment validation (`check_env`), and Dict-observation `MultiInputPolicy` baselines over counterfactual candidate shells.
- `/dlr-rm/rl-baselines3-zoo` - RL Baselines3 Zoo. Used as a reference surface for practical SB3 training/evaluation recipes and hyperparameter conventions when the repo adds larger RL experiments.
- `/pydantic/pydantic` - Pydantic. Used for strongly typed configs, validation, and config-as-factory patterns across the runtime.
- `/websites/jcristharif_msgspec` - msgspec. Used for typed manifest/index serialization and safe structured payload encoding in the new offline data stack.
- `/websites/streamlit_io` - Streamlit. Used for the interactive dashboard/app surfaces that inspect cache, VIN, and attribution outputs.
- `/rerun-io/rerun` - Rerun. Used for viewer/logging APIs, entity paths, timelines, frame transforms, and saved `.rrd` inspector artifacts.
- `/mermaid-js/mermaid` - Mermaid. Used for diagram syntax and renderer behavior when local lint/render checks need external syntax confirmation.
- `/websites/astral_sh_uv` - uv. Used for environment synchronization, dependency locking, and local command execution conventions in the Python workspace.
- `/websites/zarr_readthedocs_io_en_stable` - Zarr Python. Used for dense numeric shard storage in the immutable VIN offline dataset format.
- `/e3nn/e3nn` - e3nn. Used only when a plan explicitly touches equivariant or spherical-harmonic feature work.

## Project-specific note

For EFM3D, ATEK, and Project Aria tools, prefer the vendored source under
`external/` and the owning package source, tests, and `AGENTS.md` before broad
external lookup.
