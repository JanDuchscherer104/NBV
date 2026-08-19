# Context7 Library IDs And Query Seeds

Use this fallback only when no narrower skill owns the external API question.
Open the local owner and installed call site first. Use a supplied exact ID
directly; otherwise resolve the library, then issue one focused query per
concept. Each backticked list below is a seed menu, not one broad query: select
only the API or behavior needed for the current decision. Verify consequential
answers against the installed version, local source/tests, and exact ARIA
owner.

## Navigation And Publication

- `/graphify-labs/graphify`
  - `query, path, and explain command selection and output contracts`
  - `post-commit and post-checkout hook installation behavior`
  - `incremental code refresh versus semantic invalidation for changed docs`
- `/websites/typst_app` — `labels, references, imports, context, show rules, and
  compile behavior for the exact Typst construct in use`.
- `/typst-community/glossarium` — `term registration, short forms, references,
  grouping, and glossary printing`.
- `/cetz-package/cetz` — `canvas coordinates, projections, transforms, anchors,
  and drawing primitives for the selected figure`.
- `/jollywatt/typst-fletcher` — `diagram nodes, edges, labels, layouts, and CeTZ
  integration`.
- `/touying-typ/touying` — `slide composition, sections, counters, pauses, and
  reveal behavior`.
- `/websites/quarto` — `cross-references, project navigation, filters, metadata,
  and render behavior for the selected output format`.
- `/mermaid-js/mermaid` — `syntax and renderer behavior for the selected diagram
  type and installed Mermaid version`.

## Aria, Data, Geometry, And Learning

- `/facebookresearch/atek` — `ASE snippet schema, field semantics, dataset
  loading, and vendor-aligned sample conventions`.
- `/websites/facebookresearch_github_io_projectaria_tools` — `camera calibration,
  trajectories, coordinate frames, VRS access, and pose transforms`.
- `/facebookresearch/efm3d` — `Aria snippet structures, tensor wrappers, camera
  conventions, and EFM3D backbone outputs`.
- `/pytorch/pytorch` — `tensor, DataLoader, serialization, device, dtype, and
  execution semantics for the exact installed API`.
- `/facebookresearch/pytorch3d` — `PerspectiveCameras, transforms, rasterization,
  depth conventions, and camera coordinate systems`.
- `/mikedh/trimesh` — `mesh loading, scene transforms, simplification, proximity,
  and geometric query behavior`.
- `/dfki-ric/pytransform3d` — `transform composition, inversion, quaternion or
  matrix conversion, and frame conventions`.
- `/isl-org/open3d` — `point-cloud, mesh, visualization, and geometry inspection
  APIs`.
- `/e3nn/e3nn` — `irreducible representations, spherical harmonics, equivariant
  tensor products, and normalization conventions`.
- `/farama-foundation/gymnasium` — `Env reset/step contracts, termination versus
  truncation, spaces, wrappers, and environment checking`.
- `/dlr-rm/stable-baselines3` — `PPO, Dict observations, MultiInputPolicy,
  check_env, callbacks, save/load, and evaluation`.
- `/dlr-rm/rl-baselines3-zoo` — `SB3 training recipes, evaluation protocol, and
  hyperparameter conventions for the selected algorithm`.

## Configuration, Storage, Training, And UI

- `/websites/hydra_cc` — `configuration composition, defaults lists, overrides,
  working directories, and multirun behavior`.
- `/omry/omegaconf` — `structured configs, interpolation, merging, missing values,
  and container conversion`.
- `/pydantic/pydantic` — `BaseModel validation, Field constraints, serializers,
  model validators, and settings for the installed major version`.
- `/websites/jcristharif_msgspec` — `Struct definitions, JSON encoding/decoding,
  tagged unions, validation, and schema evolution`.
- `/websites/zarr_readthedocs_io_en_stable` — `array creation, chunking, codecs,
  groups, stores, metadata, append/resize, and concurrency`.
- `/websites/astral_sh_uv` — `workspace sync, lock files, tool installation,
  dependency groups, environments, and command execution`.
- `/lightning-ai/pytorch-lightning` — `Trainer and LightningModule lifecycle,
  hooks, checkpointing, validation, callbacks, and distributed behavior`.
- `/wandb/wandb` — `run lifecycle, metric logging, artifacts, resume, sweeps, and
  Lightning integration`.
- `/websites/optuna_readthedocs_io_en_stable` — `study and trial lifecycle,
  samplers, pruners, storage, conditional search spaces, and distributed runs`.
- `/plotly/plotly.py` — `figure traces, subplots, callbacks, serialization, and
  interactive rendering`.
- `/websites/streamlit_io` — `session state, caching, reruns, widgets, fragments,
  and app execution semantics`.
- `/rerun-io/rerun` — `recording streams, entity paths, timelines, transforms,
  blueprints, sinks, and saved RRD artifacts`.
- `/websites/mojolang` — `Python interop, importable Mojo modules, FFI, GPU
  kernels, ownership, and packaging`.

## Local-First Exceptions

For EFM3D, ATEK, and Project Aria tools, inspect `external/`, the nearest
package source/tests, and its `AGENTS.md` before Context7. External docs explain
the dependency; they do not own ARIA's wrapper behavior or scientific meaning.
