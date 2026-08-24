---
name: python-standards
description: Apply ARIA-NBV Python conventions and write concise, contract-focused docstrings for modules, public classes, functions, methods, protocols, config models, DTOs, wrappers, and streaming or session APIs; use for typing, configuration, DTO, docstring, shape, lifecycle, cross-reference, and Python API-contract work.
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

For current external dependency API or version uncertainty, route through
[`aria-nbv-context`](../aria-nbv-context/SKILL.md) and its
[`Context7 registry`](../aria-nbv-context/references/context7_library_ids.md);
keep this skill focused on ARIA's local contracts.

## Docstring Overview

Write or refactor Python docstrings as API contracts. Prefer concise,
high-information docstrings that explain behavior, invariants, units, shapes,
ownership, sequencing, theory, and boundary semantics instead of paraphrasing
type hints. This skill owns field docs, shape display, examples,
cross-references, equations, and Quartodoc constraints. Load only the focused
reference for the active contract. Read [docstring
sections](./references/docstring-sections.md) to choose and write sections; for
module, theory-rich function, config/datamodel, or sequencing examples, load
the matching section in [canonical
examples](./references/canonical-examples.md).

## Docstring Workflow

1. Read the package owner and this skill before editing Python docstrings.
2. Identify the public API surface: public modules, classes, functions,
   methods, and typed fields or properties that form an external or cross-module
   contract.
3. Read [docstring sections](./references/docstring-sections.md), then only the
   focused references needed for the contract.
4. Optionally run [scripts/audit_docstrings.py](./scripts/audit_docstrings.py)
   before or after a refactor.

## Verification Commands

Read [references/verification.md](./references/verification.md) for the narrowest
Ruff, pytest, coverage, mypy, and generated-doc proof. Report exact scope;
targeted success never proves package-wide correctness.

## Focused references

- Generic typing, runtime, configuration, and logging: read
  [general conventions](./references/general_conventions.md).
- Module, theory-rich, config/datamodel, or sequencing examples: read the
  matching section in [canonical examples](./references/canonical-examples.md).
- Tensor shape or dtype contracts: read [tensor shapes](./references/tensor-shapes.md).
- Field documentation: read [config/datamodel fields](./references/config-datamodel-fields.md).
- Section selection and writing rules: read [docstring sections](./references/docstring-sections.md).
- Equations or theory: read [theory-rich docstrings](./references/theory-rich-docstrings.md).
- Quartodoc or local API cross-references: read [the Quartodoc contract](./references/quartodoc-contract.md) and [cross-references](./references/cross-references.md).
- Verification selection: read [verification](./references/verification.md).
