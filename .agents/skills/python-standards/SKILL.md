---
name: python-standards
description: Apply ARIA-NBV Python conventions and write concise, contract-focused docstrings for modules, public classes, functions, methods, protocols, config models, DTOs, wrappers, and streaming or session APIs. Use for typing, configuration, DTO, docstring, shape, lifecycle, cross-reference, and Python API-contract work.
metadata:
  mode: implementation
  not_when:
    - "public docs, Quarto, or Typst prose not generated from Python APIs"
    - "implementation behavior changes where Python standards are incidental"
    - "large API redesign before the target interface is stable"
  handoff_to:
    - "aria-grill for unsettled module, interface, or domain-model decisions before implementation"
    - "nearest docs guide for public narrative, Quarto, or Typst documentation"
    - "nearest package guide for frame, unit, or tensor-shape semantics"
    - "simplification for behavior-preserving API cleanup before documentation"
  evidence_required:
    - "public API or cross-module contract being changed or documented"
    - "local package owner and any needed generated-doc cross-reference"
    - "targeted format, lint, test, or generated-doc evidence"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "Python standards"
    - "typing"
    - "config model"
    - "DTO"
    - "docstring"
    - "API docs"
    - "shape docs"
    - "contract docs"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/python-standards/references/general_conventions.md"
    - ".agents/skills/python-standards/references/tensor-shapes.md"
    - ".agents/skills/python-standards/references/theory-rich-docstrings.md"
    - ".agents/skills/python-standards/references/config-datamodel-fields.md"
    - ".agents/skills/python-standards/references/quartodoc-contract.md"
    - ".agents/skills/python-standards/references/cross-references.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#completion-criteria"
    - "aria_nbv/pyproject.toml"
    - ".agents/skills/python-standards/references/general_conventions.md"
    - ".agents/skills/python-standards/references/tensor-shapes.md"
    - ".agents/skills/python-standards/references/theory-rich-docstrings.md"
    - ".agents/skills/python-standards/references/config-datamodel-fields.md"
    - ".agents/skills/python-standards/references/quartodoc-contract.md"
    - ".agents/skills/python-standards/references/cross-references.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/pydantic/pydantic"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "ruff format <file>"
    - "ruff check <file>"
    - "cd aria_nbv && uv run pytest <path>"
    - "make mypy-contract; make mypy-targeted MYPY_PATHS=\"...\"; make mypy-full"
    - "./scripts/quarto_generate_api_docs.sh when generated API docs are affected"
---

# Python Standards

## Codex Verification Loop

Inspect the changed surface, run the narrowest Ruff, pytest, coverage, and mypy proof,
then report command, scope, result, and baseline gaps. Targeted success never proves
package-wide correctness.

## General Python Conventions

Read [references/general_conventions.md](./references/general_conventions.md) for
typing, paths, config-as-factory behavior, runtime setup, logging, and project
wrapper conventions. Executable requirements remain owned by source, tests,
formatter, linter, and type configuration; domain semantics remain with the package owner.

## Docstring Overview

Write or refactor Python docstrings as API contracts. Prefer concise, high-information
explanations of behavior, invariants, units, shapes, ownership, sequencing, theory,
and boundaries. This skill owns field docs, tensor-shape display, examples,
cross-references, equations, and Quartodoc rendering constraints.

## Docstring Workflow

1. Read the package owner and this skill before editing Python docstrings.
2. Identify public modules, classes, functions, methods, and typed fields forming an external or cross-module contract.
3. Choose only useful Google-style sections: `Args:`, `Returns:`, `Yields:`, `Attributes:`, `Examples:`, `Notes:`, or `Theory:`.
4. Document semantics, invariants, side effects, units, shapes, frames, ownership, lifecycle, theory, and boundaries; do not restate type hints.
5. Cross-reference with the local Quartodoc role contract or Quarto Markdown; see [references/cross-references.md](./references/cross-references.md).
6. For shaped tensors, include `points ``Tensor["N 3", float32]``: ...` and
   see [references/tensor-shapes.md](./references/tensor-shapes.md).
7. Trim boilerplate and empty sections; avoid `Raises:` unless it is a caller
   contract. Optionally run `scripts/audit_docstrings.py`.

## Writing Rules

- Start with a concise summary line that describes behavior, not the symbol name.
- Use Google-style sections only when they add information. Explain purpose,
  role, behavior, invariants, units, shapes, frames, ownership, mutation,
  lifecycle, and sequencing rather than restating names or type hints.
- Use `Attributes:` for contract-bearing state. Public dataclasses, Pydantic
  models, DTOs, configs, and typed payloads need meaningful field docs.
- Use standard Python and framework annotations (`Tensor`, `ndarray`, and
  project types); record shapes, frames, units, and support semantics in prose.
- Use `aria-grill` before documenting a genuinely unsettled boundary; this
  skill records the resulting source-level contract without duplicating design.
- Use `Yields:` for streaming APIs, `Examples:` for easy-to-misuse APIs, and
  `Notes:` or `Theory:` when they materially improve correct usage. Link complex
  definitions to the thesis owner instead of copying them.
- Use Markdown math (`$...$`, `$$...$$`) for Quarto equations and raw Python
  docstrings (`r"""..."""`) when LaTeX backslashes appear.
- Use Sphinx/Python-domain roles (`:mod:`, `:class:`, `:func:`, `:meth:`,
  `:attr:` and `:py:*:` forms) for local API symbols; the Quarto role filter
  resolves them against `docs/objects.json` (see cross-references reference).
- Keep private-helper docs concise unless their invariant or failure mode is
  needed by callers. Avoid boilerplate and long theory blocks for simple APIs.

## Verification Commands

Run from the repository root. `aria_nbv/pyproject.toml` owns Ruff/mypy/pytest/coverage
configuration, `aria_nbv/uv.lock` pins versions, and `Makefile` owns gates/path
normalization. Point to these sources, not copied flags or pins.

- `make package-smoke` runs fixed Ruff/pytest smoke surfaces plus the public API
  typing contract; CI adds `make ruff-full` for the complete stable Ruff surface;
  `make mypy-contract` runs that contract alone.
- `make ruff-full` or `make ruff-targeted RUFF_PATHS="..."` runs stable Ruff
  gates; `make coverage-targeted COVERAGE_TESTS="tests/<path>"` reports branch
  coverage. Add `MYPY_JUNIT_XML=/tmp/mypy.xml` or
  `COVERAGE_JSON=/tmp/coverage.json` for structured output.
- `make mypy-targeted MYPY_PATHS="aria_nbv/<path> tests/<path>"` checks selected roots;
  `make mypy-full` remains informational while its baseline is nonzero.
- `coverage-targeted` is intentionally operator-selected rather than a CI gate;
  it has no representative repository-wide threshold yet.

Pass repository-root paths such as `aria_nbv/aria_nbv/<path>` or `aria_nbv/tests/<path>`;
the target normalizes, validates, and deduplicates them. Targeted success is surface-limited.
Include `aria_nbv/tests/data_handling/public_api_typing_contract.py` for affected exports.

```sh
cd aria_nbv
uv run --extra dev ruff format --check <changed-paths> && uv run --extra dev ruff check <changed-paths>
uv run --extra dev pytest --import-mode=importlib <tests> && uv run --extra dev pytest --import-mode=importlib --cov <tests>
```

Targeted Ruff, pytest, coverage, and mypy results apply only to the named surface;
package-smoke covers its fixed list. Claim package-wide results only after the corresponding
full surface succeeds; full mypy is currently non-gating.

## References

- [General Python conventions](./references/general_conventions.md); [Tensor and NumPy shapes](./references/tensor-shapes.md); [Theory-rich docstrings](./references/theory-rich-docstrings.md); [Config and datamodel fields](./references/config-datamodel-fields.md); [Quartodoc contract](./references/quartodoc-contract.md); [Cross-references](./references/cross-references.md)
