---
id: 2026-06-17_thesis_geometry_architecture_autoresearch
date: 2026-06-17
title: "Thesis Geometry Architecture Autoresearch"
status: done
topics: [thesis, literature, geometry, architecture, autoresearch]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/02-background.typ
  - docs/typst/thesis/sections/03-method.typ
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the thesis literature autoresearch artifact with a focused critique of
the planned architecture around QCNet-style relative descriptors, Deja View,
set encoders, geometric deep learning, and geometric invariance/equivariance.

## Method

Used repo-local routing and litkg first, then inspected local TeX sources for
QCNet/QCNeXt, Deep Sets, Set Transformer, Geometric Deep Learning,
SE(3)-Transformer, EGNN, Point Transformer/PTv3/KPConv, and Deja View.

## Findings

The thesis should dedicate a section to geometric symmetries and candidate-set
architecture. The minimum contract is candidate-row permutation equivariance,
mask-safe set processing, target/current/query-local relative pose encodings,
gravity-aware partial symmetry, and directional visibility memory on `S^2`.

Full `SE(3)` or `E(n)` equivariance is useful as an ablation, not a default
requirement. ARIA-NBV has physical gravity/up signals, camera/frustum
conventions, target support boundaries, and actor/oracle boundaries that can
make blanket invariance incorrect.

The recommended architecture ladder remains conservative: calibrated
independent scorer, DeepSets context, masked Set Transformer, QCNet-style
relative positional encodings, directional/support attention bias, residual
dueling `Q_H`, and only then recurrent Deja View-style refinement or exact
equivariant/point-backbone ablations.

## Verification

Updated the existing autoresearch report and result metadata. Follow-up checks
ran on the artifact and agent memory:

- `rg -n "Geometric Invariance|QCNet|Deja View|permutation equivariance|S\\^2" .omx/specs/autoresearch-thesis-lit-review/report.md`
- `git diff --check`
- `make check-agent-memory`
- `make kg-claim-check KG_CLAIM='ARIA-NBV candidate value models should preserve candidate-row permutation equivariance, prefer target/current/query-local relative pose encodings over raw absolute world pose, and treat exact SE(3)/E(n)-equivariant models as ablations unless simple set models fail.'` returned `unverifiable` because current literature `paper:*` nodes lack source paths.
- Fallback `make kg-search KG_QUERY='candidate permutation equivariance target local frame relative pose Set Transformer QCNet geometric invariance' KG_LIMIT=10` returned the repo-local candidate-view-dependence theory note plus SE(3)-Transformer/Point Transformer related entries.

## Canonical State Impact

The autoresearch artifact now owns the refined architecture critique. The
active thesis should later consume it into a dedicated background/method section
on geometric symmetries and candidate-set architecture.
