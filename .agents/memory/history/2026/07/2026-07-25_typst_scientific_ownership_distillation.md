---
id: 2026-07-25_typst_scientific_ownership_distillation
date: 2026-07-25
title: "Typst Scientific Ownership Distillation"
status: done
topics: [thesis, typst, source-ownership, distillation]
confidence: high
canonical_updates_needed: []
---

# Typst Scientific Ownership Distillation

## Outcome

G003 collapsed QMD-owned scientific direction into the active Typst thesis.
Code and tests remain authoritative for executable behavior, immutable evidence
bundles for measurements and validity, and exact papers for attributed
literature claims. The Development Diary and its invariant and QMD migration
ledgers are development-only evidence surfaces, not submission or scientific
authorities. Prompt and debrief text was not blindly promoted.

## Review

Independent review found and prompted fixes for raw TODO leakage and remaining
QMD authority leaks. Its diary-orphan claim was rejected by the exact include
chain: `main.typ` supplies `appendix/index.typ`; the appendix includes
`06-draft-open-work.typ` in development mode; and that file includes
`06-draft-invariant-trees.typ`. The 122-page development render contains
*B Development Diary* on page 81, *B.5 Draft Invariant Trees* on page 84, and
*B.5.6 QMD Migration Ledger* on page 89.

## TODO Disposition

| Actionable item | Disposition |
| --- | --- |
| Six plain active Typst TODO comments | Resolved in G003; no free-floating action comments remain. |
| Shared notation and every-symbol requirement | Assigned to Ultragoal G008. |
| Draft-marker and cross-modal linkage improvement | Assigned to G008 and the G004/G005 Graphify adapter work. |
| Upstream-first Graphify and progressive hierarchy | Assigned to G004/G005. |
| Measured-autoresearch mixed iteration types and scaffold rating | Assigned to G006. |
| Prompt/debrief temporal distillation and final stale-owner audit | Assigned to G007; prompts remain evidence and require current-owner and supersession checks before promotion. |

## Validation

Evidence comprised the 122-page development compile, fail-closed submission
marker check, 12 focused QMD pages (11 collapsed pages plus `docs/index.qmd`),
and scaffold audit. Canonical owners were updated in the same workpackage, so
no follow-up canonical update is required.
