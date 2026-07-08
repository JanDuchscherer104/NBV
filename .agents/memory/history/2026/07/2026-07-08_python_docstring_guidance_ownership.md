---
id: 2026-07-08_python_docstring_guidance_ownership
date: 2026-07-08
title: "Python Docstring Guidance Ownership"
status: done
topics: [python, docstrings, quartodoc, skills]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/python-docstrings/SKILL.md
  - .agents/skills/python-docstrings/references/
  - .agents/references/python_conventions.md
  - aria_nbv/AGENTS.md
---

## Task

Move ARIA-NBV Python docstring preferences out of the general Python
conventions reference and into the `python-docstrings` skill as the sole
owner.

## Method

Read the root/package guidance, `source_order.md`, the existing
`python-docstrings` skill references, `python_conventions.md`, and the local
Quartodoc configuration. Implemented the ownership move by expanding the skill
with focused references for Jaxtyping shape style, theory-rich docstrings,
datamodel field docs, and Quartodoc rendering. A follow-up moved general style
and canonical examples into the top-level `SKILL.md` and removed the separate
`general-style.md` and `examples.md` references.
Another follow-up replaced non-ARIA examples with ARIA-NBV examples and
verified the current role behavior with a temporary Quartodoc/Quarto render.
A later follow-up clarified that external symbols use the same Quartodoc
inventory role model as internal symbols once their inventories are configured.

## Outputs

- `python-docstrings` now owns Google-style sections, theory/equation
  expectations, per-field docs, Jaxtyping-facing shape display, examples,
  cross-references, and Quartodoc caveats.
- General style rules and canonical examples are now covered directly in
  `SKILL.md`.
- All examples in the `python-docstrings` skill surfaces are ARIA-NBV-specific.
- Cross-reference guidance now records that the current `docs/_quarto.yml`
  does not enable Quartodoc interlinks, so `:class:`-style roles render
  literally. If interlinks are enabled later, local inventory roles should be
  `class`, `function`, `module`, `attribute`, and only `data` when present in
  the generated inventory.
- External API symbols can use the same role syntax when their inventory source
  is configured; for example, TorchMetrics classes should use an external
  inventory role such as:

```text
:external+torchmetrics:py:class:`torchmetrics.regression.SpearmanCorrCoef`
```

- `python_conventions.md` now keeps non-docstring typing, runtime, and config
  conventions only.
- `aria_nbv/AGENTS.md` routes Python API docstring details to the skill instead
  of duplicating the detailed rules.

## Verification

- `python3 /home/jd/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/python-docstrings`
- `git diff --check -- .agents/skills/python-docstrings .agents/references/python_conventions.md aria_nbv/AGENTS.md`
- `make check-agent-memory`
- `make scaffold-audit` was run and failed on a pre-existing unrelated missing
  canonical source in `.agents/skills/nbv-geometry-contracts/SKILL.md`. It also
  warns that `python-docstrings/SKILL.md` is over the normal hot-path line
  budget and contains formula-detail; those warnings are an intentional
  consequence of keeping style and examples in the top-level skill.
- Temporary Quartodoc build and Quarto render for
  `aria_nbv.rri_metrics.oracle_rri.OracleRRI` showed `:class:`RriResult`` is
  preserved literally in qmd/html under the current config. The temporary
  `objects.json` emitted roles `class`, `function`, `module`, and `attribute`.

## Canonical State Impact

No `.agents/memory/state/` update is needed. The canonical preference moved to
the owning skill surface itself.
