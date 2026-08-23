---
name: python-standards
description: Apply ARIA-NBV Python conventions and write contract-focused docstrings; use for typing, configuration, helper ownership, DTOs, shapes, lifecycles, cross-references, and Python API contracts.
---

# Python Standards

## Codex Verification Loop

Inspect the changed surface, run the narrowest Ruff, pytest, coverage, and mypy proof,
then report command, scope, result, and baseline gaps. Targeted success never proves
package-wide correctness.

## General Python Conventions

Read [references/general_conventions.md](./references/general_conventions.md) for
typing, paths, config-as-factory behavior, runtime setup, helper locality,
logging, and project wrapper conventions. Executable requirements remain owned
by source, tests, formatter, linter, and type configuration; domain semantics
remain with the package owner.

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
reference for the active contract. For module, theory-rich function,
config/datamodel, or sequencing examples, load the matching section in
[references/canonical-examples.md](./references/canonical-examples.md).

## Docstring Workflow

1. Read the package owner and this skill before editing Python docstrings.
2. Identify the public API surface. Cover public modules, public classes,
   public functions, public methods, and meaningful typed fields or properties
   that form an external or cross-module contract.
3. Choose sections deliberately. Default to a summary line plus only the
   sections that add information: `Args:`, `Returns:`, `Yields:`,
   `Attributes:`, `Examples:`, `Notes:` or `Theory:`.
4. Write behavioral contracts. Document semantics, invariants, side effects,
   units, shapes, coordinate frames, ownership, lifecycle, theory, and boundary
   expectations. Do not restate obvious type hints.
5. Cross-reference symbols and sources with the local Quartodoc role contract
   or Quarto-compatible Markdown. See
   [references/cross-references.md](./references/cross-references.md).
6. For tensors, use ordinary framework annotations and add the shape-style token
   when shape or dtype matters: `points ``Tensor["N 3", float32]``: ...`. See
   [references/tensor-shapes.md](./references/tensor-shapes.md).
7. Trim boilerplate. Remove empty sections and filler prose. Avoid `Raises:`
   unless callers genuinely need to rely on or handle the failure contract.
8. Optionally run [scripts/audit_docstrings.py](./scripts/audit_docstrings.py)
   before or after a refactor.

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
  resolves them against the generated `objects.json` inventory (see cross-references reference).
- Keep private-helper docs concise unless their invariant or failure mode is
  needed by callers. Avoid boilerplate and long theory blocks for simple APIs.

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
- Equations or theory: read [theory-rich docstrings](./references/theory-rich-docstrings.md).
- Quartodoc or local API cross-references: read [the Quartodoc contract](./references/quartodoc-contract.md) and [cross-references](./references/cross-references.md).
- Verification selection: read [verification](./references/verification.md).
