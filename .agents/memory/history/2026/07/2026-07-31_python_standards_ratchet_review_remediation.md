---
id: 2026-07-31_python_standards_ratchet_review_remediation
date: 2026-07-31
title: "Python Standards Ratchet Review Remediation"
status: done
topics: [python-standards, scaffold, code-review]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/python-standards/SKILL.md
  - scripts/tests/test_python_standards_ratchet.py
---

## Task

Resolve the remaining review findings on the Python documentation ratchet
without taking over the downstream causal-CI or transcript-validator layers.

## Result

The skill now states that this layer introduces the executable ratchet and that
required CI must invoke it explicitly. The active-owner regression parses
tracked and untracked paths as NUL-delimited bytes and preserves hostile
newline-bearing filenames. Commit-transcript provenance was removed from this
layer so it does not precede its downstream validator.

## Verification

- The 28 focused ratchet and ownership tests passed.
- Ruff format and lint passed for the ratchet implementation and tests.
- Strict mypy passed for the ratchet implementation and tests.

## Canonical-State Impact

No canonical project state changed. This remediation narrows layer claims and
hardens its existing regression coverage.
