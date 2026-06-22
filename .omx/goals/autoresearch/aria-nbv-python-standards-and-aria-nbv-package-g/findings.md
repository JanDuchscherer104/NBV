# ARIA-NBV Python Standards and Package Guidance Audit

Date: 2026-06-21

## Verdict

The current Python/package guidance is directionally correct but not yet
operational enough. Agents still reimplement package functionality because the
binding standards, examples, generated contract index, module ownership guides,
KG routes, and archived implementation docs are not presented as one
unambiguous reuse-first workflow.

The highest ROI change is not another long standards document. It is a sharper
source-of-truth split:

- `aria_nbv/AGENTS.md`: short binding package policy and mandatory reuse
  preflight.
- `.agents/references/python_conventions.md`: long examples and explanations
  only, linked from the binding policy.
- `aria_nbv/pyproject.toml`: sole owner of Ruff, mypy, pytest, build metadata,
  scripts, and dependency extras.
- nearest `aria_nbv/aria_nbv/**/AGENTS.md`: module-specific ownership,
  boundaries, and verification.
- `aria_nbv/aria_nbv/**` source, public `__init__.py` exports, docstrings, and
  tests: exact API behavior and package contracts.
- generated context and litkg: discovery/evidence only, never canonical truth.

## Evidence Collected

Local evidence:

- Root dispatcher points package work to `aria_nbv/AGENTS.md`, but also repeats
  Python commands and verification gates.
- `.agents/references/source_order.md` already says skills are routing/evidence
  surfaces and `.agents/references` are operator aids or long-form convention
  references.
- `.agents/references/python_conventions.md` says binding short rules live in
  `aria_nbv/AGENTS.md`, but still contains binding-sounding core rules.
- `aria_nbv/AGENTS.md` is the right canonical package policy file, but it
  currently mixes rules, commands, examples, and pointers without a hard
  "search existing package surface first" workflow.
- nested package guides exist for `data_handling`, `rri_metrics`, `vin`, and
  `rollouts`; they are useful and should remain module-level authorities.
- `aria_nbv/pyproject.toml` already centralizes build metadata, dependencies,
  scripts, Ruff, mypy, and pytest settings.
- `make package-smoke` runs package format-check, lint, and smoke tests.
- `make context-contracts` successfully emits a broad package contract index.
- A quick AST scan found 180 modules with public class/function surface and 152
  modules with `__all__`; this is too large to expect agents to remember.
- code-index found 2175 matches for core package reuse terms after setting the
  project path to `/home/jd/repos/ARIA-NBV`.
- litkg search for Python standards fell back to `lexical_only` because Ollama
  was unreachable, and returned stale `docs/contents/impl/aria_nbv_*.qmd`
  paths that no longer exist in active docs.
- MCP_DOCKER `get_package_metrics` could not see the local package path from
  its container, so it is not currently a reliable package-audit path here.
- Context7 lookup for Pydantic v2 confirmed the local direction toward
  validators, `default_factory`, and structured fields, but local source and
  `pyproject.toml` remain the authority.

External best-practice evidence:

- PyPA treats `pyproject.toml` as the central packaging/tool configuration
  surface and recommends `[build-system]`, `[project]`, and tool-specific
  `[tool.*]` tables for new projects.
- PyPA's src-layout guidance supports installed-package testing and avoiding
  accidental imports from the repository root.
- Ruff uses the closest config and does not merge settings across config files,
  which supports keeping style configuration in one `pyproject.toml` owner.
- pytest recommends integration patterns that avoid import ambiguity; import
  mode should be an explicit local decision, not hidden in prose.
- mypy recommends consistent invocation/configuration, gradual rollout on
  existing code, and avoiding broad ignores where possible.
- Diataxis supports separating tutorials, how-to guides, reference, and
  explanation; this maps cleanly to AGENTS policy, long-form conventions,
  generated API reference, and thesis/docs narrative.

## Aggregated Current Standards

### Environment and commands

- Use `aria_nbv/.venv/bin/python` and package-local `uv` commands.
- Use `cd aria_nbv && uv sync --extra dev` for package environment setup.
- Format with `cd aria_nbv && uv run ruff format <path>`.
- Lint with `cd aria_nbv && uv run ruff check <path>`.
- Run targeted tests with `cd aria_nbv && uv run pytest <path>`.
- Use `make package-smoke` for the root CPU-only package smoke gate.
- Use `make context-contracts` when package contracts or reusable configs/types
  are relevant.

### Packaging and tool configuration

- `aria_nbv/pyproject.toml` owns project metadata, dependencies, extras, CLI
  scripts, build backend, Ruff, mypy, and pytest configuration.
- Ruff targets Python 3.11, line length 120, and currently selects `E`, `W`,
  `F`, `I`, `B`, `C4`, `UP`, and `N` while ignoring `E501`, `UP037`, and
  `F722`.
- mypy is configured strict with `check_untyped_defs` and
  `disallow_untyped_defs`, but global `ignore_missing_imports = true` weakens
  that promise and should be reviewed gradually.
- pytest discovers tests under `tests` with strict markers.

### Package coding rules

- Prefer existing tested `aria_nbv` modules before writing new helpers.
- Use typed public signatures and explicit containers over ad hoc dicts.
- Use modern Python types (`list[T]`, `dict[K, V]`, `T | None`) and
  `TYPE_CHECKING` imports for type-only dependencies.
- Use `Enum`, `Literal`, and `match` where they clarify a closed state space.
- Use `pathlib.Path` and `PathConfig`; avoid raw string paths.
- Use `Console` for operator-facing output instead of ad hoc `print`.
- Fail explicitly when assumptions are violated; avoid silent fallbacks that
  change scientific or data semantics.

### Config and API contracts

- Configs should be Pydantic `BaseConfig` / `TargetConfig` models.
- Prefer config-as-factory with `.setup_target()` for constructed objects.
- Use nested configs for dependency graphs; do not pass untyped dict blobs.
- Use `Field(default_factory=...)` for mutable defaults or constructed defaults.
- Prefer concise attribute docstrings in config models over duplicated verbose
  `Field(..., description=...)` prose unless schema metadata is needed.
- Public APIs should expose stable names through package/module `__init__.py`
  and tests, not through hidden lazy exports.

### Domain contracts

- Use EFM3D/ATEK/Project Aria utilities where possible.
- Use `PoseTW`, `CameraTW`, ARIA frame conventions, and existing coordinate
  wrappers instead of hand-rolled pose/camera math.
- Keep candidate generation, rendering, RRI metrics, VIN stores, rollouts, and
  Streamlit inspection inside their current package/module boundaries.
- Treat invalidity as a hard mask/reason contract, not low RRI.
- Keep actor-visible target selection distinct from oracle/evaluation assets.

### Documentation and docstrings

- Use Google-style docstrings for public modules, classes, functions, and
  methods.
- Document units, tensor shapes, coordinate frames, lifecycle semantics, and
  failure behavior for package contracts.
- Use Markdown/math docstrings compatible with Quartodoc; use raw docstrings
  when LaTeX escaping would otherwise be wrong.
- Exact API behavior belongs in source/docstrings/tests; narrative belongs in
  Quarto or Typst docs; agent activation belongs in skills.

## Redundant or Conflicting Surfaces

1. `aria_nbv/AGENTS.md` and `.agents/references/python_conventions.md`
   duplicate core package rules. The former should be binding; the latter
   should elaborate with examples.
2. Root `AGENTS.md`, `aria_nbv/AGENTS.md`, and
   `.agents/references/verification_matrix.md` all repeat basic Ruff/pytest
   command forms. This is acceptable only if root remains a dispatcher,
   package AGENTS remains authoritative for package work, and the matrix remains
   a command lookup.
3. `.agents/skills/python-docstrings/SKILL.md` duplicates docstring policy that
   belongs in `aria_nbv/AGENTS.md` plus `python_conventions.md`. The skill can
   later shrink to activation/script routing or be removed after migration.
4. `.agents/references/external_stack_contracts.md`,
   `.agents/references/python_conventions.md`, and several domain skills all
   restate `PoseTW`/`CameraTW`/external-stack reuse rules. Domain skills should
   link to owners, not restate.
5. litkg currently returns obsolete `docs/contents/impl/aria_nbv_package.qmd`
   and `docs/contents/impl/aria_nbv_overview.qmd` paths. Active docs no longer
   contain those paths; only archived copies were found. This is a drift bug.
6. generated KG literature files preserve old implementation-doc claims. They
   are useful history but should not rank above active package source,
   `aria_nbv/AGENTS.md`, `pyproject.toml`, or current docs.

## Why Agents Still Reimplement

The failure mode is not absence of standards. It is a weak preflight.

Agents are told to use the package guide, but the guide does not force a
repeatable discovery sequence:

1. locate the nearest module owner;
2. search public exports and tests;
3. consult generated contract context;
4. use code-index or `rg` for reusable symbols;
5. only then add new code.

Because the package surface is large and the generated index is optional,
agents often start from the local file they are editing. That makes writing a
new helper feel cheaper than discovering an existing type, config, renderer,
sampler, DTO, or metric utility.

The second issue is KG staleness. A retrieval path that returns historical
`docs/contents/impl` pages can make archived implementation prose look current.
That undermines the source-order model and increases drift.

The third issue is signal-to-noise. Binding rules, examples, verification
commands, docstring doctrine, and domain facts are mixed across multiple files.
When a rule appears in several places with slightly different wording, agents
cannot tell which surface is the owner.

## Ranked Streamlining Plan

### P0: Make `aria_nbv/AGENTS.md` the package preflight gate

Add a compact "reuse before implementation" section:

- read the nearest nested package `AGENTS.md` when touching a module family;
- run or inspect `make context-contracts` for configs/types/data contracts;
- search public exports with `rg "__all__|class |def " aria_nbv/aria_nbv`;
- search tests for the intended behavior before adding a new helper;
- use code-index for symbol-level lookup when available;
- cite the reused symbol or explain why none exists.

ROI: very high. Urgency: immediate. This directly attacks reimplementation.

### P0: Demote duplicated rules in `python_conventions.md`

Keep the file as examples and rationale. Change binding-sounding bullets into
elaborations that point back to `aria_nbv/AGENTS.md`.

ROI: high. Urgency: immediate. This reduces drift without deleting useful
detail.

### P0: Fix stale litkg / KG source ranking

Regenerate or patch KG ingestion so archived `docs/contents/impl/aria_nbv_*`
paths do not appear as active docs. Add a source-rank rule: active package
source, active AGENTS, active docs, then memory/history, then archive.

ROI: high. Urgency: immediate. Current KG evidence can misroute agents.

### P1: Add a package-guidance audit

Extend scaffold/source audits to warn when:

- a skill restates package rules instead of linking `aria_nbv/AGENTS.md`;
- `docs/contents/impl/aria_nbv_*` appears in generated KG as an active source;
- `python_conventions.md` contains new binding rules not mirrored in package
  AGENTS;
- package work changes source without evidence of `make context-contracts`,
  code-index, or an explicit export/test search in the debrief.

ROI: high. Urgency: near term.

### P1: Surface mypy honestly

Either document a supported mypy gate or explicitly say mypy is strict-configured
but not yet part of the default package smoke gate. Review global
`ignore_missing_imports = true` and move toward targeted per-module ignores.

ROI: medium-high. Urgency: near term.

### P1: Improve package landing docs without duplicating policy

Expand `aria_nbv/README.md` into a concise package landing page that links to:

- `aria_nbv/AGENTS.md` for development policy;
- generated API reference for public contracts;
- `make context-contracts` for local contract discovery;
- root docs for thesis narrative.

ROI: medium. Urgency: after preflight and KG repair.

### P2: Retire or slim `python-docstrings`

After docstring rules are owned by package policy and examples, shrink the skill
to activation plus a script pointer, or remove it if routing fixtures show no
lost owner.

ROI: medium. Urgency: later.

### P2: Evaluate pytest import mode

pytest's `--import-mode=importlib` guidance may help avoid import ambiguity, but
this is a behavior-affecting test configuration change. Trial it in a branch
with the package smoke suite before adopting.

ROI: medium. Urgency: later.

## Deprecation Candidates

- Active KG references to `docs/contents/impl/aria_nbv_package.qmd` and
  `docs/contents/impl/aria_nbv_overview.qmd`: deprecate as active sources and
  mark archive/history only.
- `.agents/skills/python-docstrings/SKILL.md`: later prune or remove after
  migration and fixture validation.
- Binding package rules inside `.agents/references/python_conventions.md`:
  demote to examples/rationale.
- Domain-skill restatements of generic package standards: replace with
  `canonical_sources` pointers.
- Generated historical literature memories: keep as evidence/history only, not
  routing authority.

## Proposed Source-Order Patch

For Python package work, use this local source order:

1. `aria_nbv/pyproject.toml` for package metadata, dependencies, scripts, and
   tool configuration.
2. `aria_nbv/AGENTS.md` for binding package development policy and preflight.
3. nearest `aria_nbv/aria_nbv/**/AGENTS.md` for module ownership.
4. `aria_nbv/aria_nbv/**` source, public exports, docstrings, and tests for
   exact API behavior.
5. generated contract context from `make context-contracts` for discovery.
6. `.agents/references/python_conventions.md` for examples and rationale.
7. active Quarto/Typst docs for public narrative.
8. litkg/KG/memory/history/archive for evidence, retrieval, and drift checks,
   not authoritative package truth.

## Verification Commands Run

- `git status --short`
- `make kg-route KG_TASK="Audit ARIA-NBV Python standards and aria_nbv package guidance sources of truth, redundancy, and agent reuse failures" KG_FORMAT=json`
- `make kg-search KG_QUERY="python_conventions aria_nbv AGENTS BaseConfig Console reuse existing utilities standards" KG_FORMAT=json KG_LIMIT=12`
- `make context-contracts`
- code-index `set_project_path` and advanced search for package reuse terms
- AST scan for public package surface counts
- Context7 `get-library-docs` for Pydantic v2 fields/validators
- `nl -ba Makefile | sed -n '830,855p'`

## Residual Risks

- The worktree was already dirty. This audit intentionally avoids changing
  canonical guidance files in the same pass.
- litkg fell back to lexical-only search because Ollama was unreachable, so
  semantic retrieval quality was degraded.
- MCP_DOCKER package metrics could not inspect the local package path from its
  runtime.
- This report is a research artifact; the next implementation slice should be a
  small patch to `aria_nbv/AGENTS.md`, `python_conventions.md`, and KG/source
  ranking, followed by scaffold/package guidance validation.

