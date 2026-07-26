---
name: python-docstrings
description: Write contract-first Python docstrings.
metadata:
  mode: implementation
  not_when:
    - "the implementation or public API is still changing"
    - "public narrative rather than API documentation is the output"
  handoff_to:
    - "nearest package owner for unresolved behavior, shapes, units, or lifecycle"
    - "external documentation capability for public docs beyond generated API pages"
  evidence_required:
    - "implementation, public call sites, tests, and nearest package guidance"
    - "format, lint, and Quartodoc evidence appropriate to the change"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "write or refactor Python docstrings"
    - "fix generated Python API documentation"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/python-docstrings/references/quartodoc-contract.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#code-quality"
    - "docs/AGENTS.md#commands"
    - "scripts/quarto_generate_api_docs.sh"
  verification:
    - "ruff format and ruff check for touched Python"
    - "Quartodoc generation for rendered API changes"
---

# Python Docstrings

1. Read the implementation, public call sites, tests, nearest package guide,
   and sibling docstrings.
2. Document only the enforced contract: purpose, parameters, returns, errors,
   side effects, lifecycle, and any code-owned type, shape, unit, or frame
   semantics needed for correct use.
3. Use a concise summary and Google-style sections. Put field documentation
   beside public dataclass, config, or model fields when the live renderer
   exposes them.
4. Link to the owning code or docs instead of copying equations, scientific
   rationale, schemas, or project terminology into the docstring.
5. Follow the Quartodoc reference only when generated API output is affected.

Complete when prose matches live behavior, references resolve, touched Python
passes format/lint, and affected Quartodoc output generates successfully.
