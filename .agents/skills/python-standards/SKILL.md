---
name: python-standards
description: Use for ARIA-NBV Python typing, configuration, DTO, docstring, and API-contract guidance after the owning package is known.
metadata:
  mode: implementation
  not_when:
    - "public Typst or Quarto narrative without Python API changes"
    - "an unstable API redesign before its package contract is settled"
  handoff_to:
    - "docs-curator for public narrative or generated-documentation navigation"
    - "nbv-geometry-contracts for frame, unit, or camera semantics"
    - "simplification for behavior-preserving API cleanup"
  evidence_required:
    - "owning package guidance and public API contract"
    - "targeted format, lint, and test evidence for touched Python"
  applies_to:
    - "aria_nbv/**/*.py"
  triggers:
    - "Python standards"
    - "typing"
    - "config model"
    - "DTO"
    - "docstring"
    - "API contract"
  must_read:
    - "aria_nbv/AGENTS.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#core-rules"
    - "aria_nbv/pyproject.toml"
  context7_refs:
    - "/pydantic/pydantic"
    - "/pytorch/pytorch"
  verification:
    - "ruff format <file>"
    - "ruff check <file>"
    - "cd aria_nbv && uv run pytest <path>"
---

# Python Standards

Use this skill after localizing the package owner. It provides generic Python
practice; ARIA-NBV data, geometry, model, and rollout semantics remain in
package guidance, source contracts, tests, and the Typst owners.

## Workflow

1. Read `aria_nbv/AGENTS.md` and the nearest package guide.
2. Inspect existing public symbols before adding a helper, DTO, config, or API.
3. Open only the reference needed by the change:
   - `references/general_conventions.md` for typing, paths, runtime setup, and logging;
   - `references/config-datamodel-fields.md` for Pydantic/config and DTO fields;
   - `references/tensor-shapes.md` for tensors and shapes;
   - `references/theory-rich-docstrings.md`, `quartodoc-contract.md`, and
     `cross-references.md` for public documentation.
4. Keep behavior, types, and documentation aligned; do not reproduce package
   semantics in generic guidance.
5. Run format, lint, and focused tests.

## Rules

- Prefer typed public interfaces, explicit typed containers, `Path`, and
  existing package/config seams over ad-hoc dictionaries or factories.
- Let formatter, linter, type configuration, source signatures, and tests own
  executable requirements. This skill explains their use; it does not duplicate
  their complete rule sets.
- Document public contracts when units, shapes, mutation, ownership, lifecycle,
  or failure semantics are not obvious. Do not turn simple helpers into essays.
- Add an abstraction only when it has a real reusable owner; otherwise extend
  the existing local seam.

## Completion

Report the package owner, the reference branch used, and focused verification.
