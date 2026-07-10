---
scope: package
applies_to: aria_nbv/**
summary: Package-specific implementation, validation, and design guidance for the aria_nbv Python workspace.
---

# Package Guidance

Apply this file when working under `aria_nbv/`.

## Commands
- Python: `aria_nbv/.venv/bin/python`
- Environment recovery: `cd aria_nbv && uv sync --all-extras`
- Format: `ruff format <file>`
- Lint: `ruff check <file>`
- Tests: `uv run pytest <path>` or `aria_nbv/.venv/bin/python -m pytest <path>`
- Contracts: `make context-contracts`

## Core Rules
- Use `pathlib.Path` for filesystem paths.
- Use `PoseTW` and `CameraTW` instead of raw matrices.
- Use `Console` from `aria_nbv.utils` for structured logging.
- Prefer existing implementations (i.e. from `pytorch3d`, `efm3d`, `atek`, and `projectaria_tools`) over reimplementation.
- Use ARIA constants from `efm3d.aria.aria_constants` for dataset keys.
- Follow EFM3D / ATEK coordinate conventions and document tensor shapes plus coordinate frames where they are not obvious.
- Never let package behavior fail silently; raise actionable errors or log explicit failure context.

## Progressive Disclosure
- Stay at this file for shared Python, config-as-factory, and verification rules across `aria_nbv/`.
- Open one deeper module guide only after the touched contract is clear:
  - `aria_nbv/aria_nbv/data_handling/AGENTS.md` for raw snippets, cache flows, datasets, and cache contracts
  - `aria_nbv/aria_nbv/rollouts/AGENTS.md` for multi-step rollout traces, rollout Zarr/Q stores, and rollout generation CLIs
  - `aria_nbv/aria_nbv/rri_metrics/AGENTS.md` for oracle labels, binning, ordinal loss, and reported metric semantics
  - `aria_nbv/aria_nbv/vin/AGENTS.md` for scorer, candidate-context, training batch, and VIN model contracts
- If a task spans multiple modules, start with the owner of the main contract, then open adjacent guides only for crossed boundaries.
- New raw-snippet, dataset, or offline-store work should target
  `aria_nbv.data_handling` and the immutable `VinOfflineDataset` path.
- Do not restore legacy cache migration helpers or runtime training APIs. If old
  cache data is missing, rebuild available immutable stores with
  `VinOfflineWriter` rather than reviving removed cache datasets/providers.
- Keep canonical package roots clean. Add compatibility wrappers only when a
  task explicitly requires them and the public contract is still active.

## Config-As-Factory
- Config classes should inherit `BaseConfig` and remain the main construction surface for runtime objects.
- Instantiate runtime objects through config `.setup_target()` methods rather than loose dicts or long argument lists.
- Nested configs should compose subcomponents when that improves clarity; do not bypass nested configs that already exist.
- Use `setup_target(...)` for late-bound runtime inputs such as `params`, `trainer`, or `split`.
- Prefer `Field(default_factory=...)` for computed defaults and nested config defaults.
- Use `field_validator`, `model_validator`, and `setup_target()` together for validation, default wiring, and runtime instantiation logic.
- Canonical examples: `aria_nbv/aria_nbv/utils/base_config.py` and `aria_nbv/aria_nbv/lightning/aria_nbv_experiment.py`.

## Anti-Patterns
- Do not instantiate internal runtime objects from raw `dict[str, Any]` blobs when a dedicated config model should exist.
- Do not bypass a nested config object to construct one of its targets manually.
- Do not add compatibility wrappers or silent fallbacks when removing obsolete internal interfaces unless the task explicitly asks for compatibility.
- Do not extract shared helpers into new modules without ensuring the new helper files are tracked and included in the same change.

## Code Quality
- All interfaces must be fully typed and use modern builtins such as `list[str]` and `dict[str, Any]`.
- Use `TYPE_CHECKING` guards for type-only imports.
- Use `Literal` for constrained string values.
- Public methods, functions, classes, modules, config models, dataclasses, and
  typed payload fields must follow the `python-docstrings` skill. That skill
  owns Google-style sections, Quartodoc behavior, Jaxtyping shape display,
  equations, references, and field-docstring rules.
- See `.agents/references/python_conventions.md` for non-docstring Python
  typing, runtime, and config conventions.


## Verification
- For package changes, run format -> lint -> targeted pytest on the changed surface.
- Every new feature or behavior change must come with targeted pytest coverage.
- Prefer real-data or integration-style tests when feasible.
- Prefer tracer-bullet TDD for risky behavior changes: one failing
  public-interface behavior test, minimal implementation, repeat.
- Tests should verify observable contracts through public package interfaces
  rather than private helper shape whenever a public seam exists.
- Treat public package interfaces, config `.setup_target()` surfaces, CLIs, and
  Streamlit dispatcher imports as the preferred test seams before private
  helper tests.
- Update docs when behavior or user-facing workflows change.
- Keep public signatures typed and public methods documented.
- Work in a test-driven manner when possible - start by planning interfaces and writing tests before implementation.

## Completion Criteria
- Changed Python files are formatted and lint-clean.
- Targeted pytest coverage was run for the changed surface.
- Docs were updated when behavior or user-facing workflows changed.
- No temporary placeholders, stale paths, or undocumented public API changes remain.
