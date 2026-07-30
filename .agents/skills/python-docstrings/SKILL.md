---
name: python-docstrings
description: Compatibility router for the former ARIA-NBV Python-docstring invocation.
metadata:
  mode: router
  not_when:
    - "the caller already invokes python-standards"
  evidence_required:
    - "the Python API, DTO, typing, or docstring contract being changed"
  handoff_to:
    - "python-standards for all active Python documentation and contract guidance"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "python docstrings"
    - "Python docstring"
    - "docstring guidance"
  must_read:
    - ".agents/skills/python-standards/SKILL.md"
  verification:
    - "follow python-standards verification"
  canonical_sources:
    - ".agents/skills/python-standards/SKILL.md"
---

# Python Docstrings Compatibility Router

Use `python-standards`. It is the sole active owner of ARIA-NBV Python API,
DTO, typing, shape, and docstring guidance; this router preserves existing
`$python-docstrings` invocations without duplicating those rules.
