---
id: 2026-07-25_shared_notation_and_marker_linkage
date: 2026-07-25
title: "Shared Notation And Marker Linkage"
status: done
topics: [thesis, typst, notation, draft-markers, measured-autoresearch]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation
  - docs/typst/thesis/sections/04-method
  - docs/typst/thesis/sections/05-experimental-design
  - docs/typst/thesis/sections/07-discussion.typ
  - aria_nbv/aria_nbv/data_handling/offline/inventory.py
---

# Shared Notation And Marker Linkage

## Outcome

G008 moved the reconstruction-metric formulas from the foundations section to
shared Typst equation owners and retained only three durable new symbols:
reference geometry, reference samples, and tolerance. Six development-diary
action markers now carry exact agents-DB locators in their existing `source`
field. The locator is navigation evidence; the agents DB remains authoritative
for work status and acceptance criteria.

## Measurement

The first frozen evaluator was rejected as measurement evidence after it was
shown to parse zero `docs/notation.yml` keys and to count canonical shared
definitions as section-local violations. Its discarded runs remain in
`.omx/goals/autoresearch/scaffold-notation-ownership-20260725/`.

The corrected successor mission is
`.omx/goals/autoresearch/scaffold-notation-ownership-v2-20260725/`. Its retained
iteration reduced ownership violations from 449 to 431, section-local symbolic
math fragments from 241 to 229, and unowned action markers from 13 to 7.
Unregistered shared references remained 195. Counted non-test LOC changed from
14399 to 14461, within the frozen allowance. Every hard gate passed.

## TODO Disposition

| Surface | Disposition |
| --- | --- |
| Active thesis plain `TODO`/`FIXME`/`HACK` comments | Zero; the fail-closed typed marker system remains the action mechanism. |
| Six development-diary markers | Linked to `todo-053`, `todo-026`, `todo-037`, `todo-089`, `todo-038`, and `todo-060`; intentionally unresolved. |
| Seven other active typed action markers | Retained for the next G008 linkage and notation slice. |
| Active Python inline TODOs | Concentrated in `data_handling/offline/inventory.py`; deferred to its owning cleanup instead of being silently changed during thesis work. |
| Data-handling README TODO | Deferred with the same owner; it is not thesis evidence. |
| Historical seminar/archive TODOs | Historical evidence only; not promoted into active thesis truth. |
| Prompt and transcript TODO ideas | Evidence only. They require temporal discount, deduplication, and an agents-DB owner before action. |

## Verification

- `python3 scripts/glossary_build.py validate`
- development-profile `typst compile` with dependency output
- submission status-marker compile succeeds
- submission actionable-marker fixture fails with the expected panic
- successor measured-autoresearch `validate` and `report`
- exact agents-DB locator existence checks
- `make check-agent-memory`
- `git diff --check`
