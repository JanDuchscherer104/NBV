---
name: python-docstrings
description: Use for concise contract docstrings on ARIA-NBV Python modules, public APIs, config models, DTOs, wrappers, and streaming or session interfaces.
metadata:
  mode: implementation
  not_when:
    - "Quarto, Typst, or public narrative is the primary output"
    - "implementation behavior or API design is still changing"
  handoff_to:
    - "aria-docs for Quarto, Typst, or thesis documentation"
    - "nearest package owner for unresolved frame, unit, shape, or lifecycle semantics"
    - "external codebase-design capability before documenting an unstable API"
  evidence_required:
    - "stable public contract and nearest package owner"
    - "implementation and call-site evidence for shapes, units, frames, and lifecycle"
    - "ruff and targeted docs generation when affected"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "Python docstring"
    - "generated API documentation"
    - "shape, unit, frame, or lifecycle docs"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/python-docstrings/references/type-shape-jaxtyping.md"
    - ".agents/skills/python-docstrings/references/config-datamodel-fields.md"
    - ".agents/skills/python-docstrings/references/quartodoc-contract.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#completion-criteria"
    - ".agents/skills/python-docstrings/references/type-shape-jaxtyping.md"
    - ".agents/skills/python-docstrings/references/theory-rich-docstrings.md"
    - ".agents/skills/python-docstrings/references/config-datamodel-fields.md"
    - ".agents/skills/python-docstrings/references/quartodoc-contract.md"
    - ".agents/skills/python-docstrings/references/cross-references.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/pydantic/pydantic"
  literature_refs:
    - "docs/typst/thesis/main.typ"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "ruff format <file> and ruff check <file>"
    - "./scripts/quarto_generate_api_docs.sh when generated API docs change"
---

# Python Docstrings

Inspect the implementation, public call sites, nearest package guide, and
existing sibling style before writing. Document the contract the API actually
enforces: purpose, parameters, returns, raised errors, shapes, dtypes, units,
coordinate frames, side effects, lifecycle, and ownership boundary.

Use the linked references only for the branch that applies. Prefer a concise
summary plus Google-style sections. Put field docs on config/data-model fields
where Quartodoc can render them. Keep formulas and scientific rationale in the
owning theory or thesis source and link there; do not copy them into docstrings.

Complete when the docstring matches code and tests, cross-references resolve,
and touched Python passes formatting and lint.
