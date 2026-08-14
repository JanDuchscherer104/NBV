# Ownership and branch-consolidation inventory (S1 provisional)

Generated 2026-08-14 from the clean `codex/ownership-branch-consolidation`
worktree. This is a receipt and pointer ledger, not a replacement owner: it
does not copy theory, formulas, implementation contracts, or state narratives.

## Immutable baseline receipt

The immutable merged PR50 baseline is commit
`4748c4dd01e77bae5bdb2ff6932e8980a9416b4c` (tree
`7b297ffaf2a114d2184051737001090bfc4ada50`, parents
`4d216d1c1d402a3cc10a232cd8a6d1ed44dbc286` and
`f54ecbaae42ad81fadc4a3ba6ef860894388df96`). Root Verification CI is
**SUCCESS**, all 16/16 review threads are resolved, and no formal reviewDecision
is recorded. Commit `d6a3082f3ea03a8cdf14fa2673f21ed4e3f1ea9f` / tree
`112cc32e9f4a2a796aca7eda9e6cade5807c559b` is retained only as historical
pre-merge candidate evidence.

Source blob receipts cover 7 files / 2,063 lines: roadmap 751, questions 665,
M1 report 160, and state files 487. SHA-256 values and all row-level pointers
are in the JSON companion.

## Disposition ledger summary

The JSON companion contains 47 source-block rows (each with stable id, source blob, heading/anchor or bullet
span), each with subject, disposition, canonical destination, destination
verification, and link action. Current disposition counts remain:

| disposition | rows |
|---|---:|
| unresolved (migration not yet materialized) | 33 |
| deferred-action (follow-up only) | 4 |
| code-owned | 5 |
| test-owned | 1 |
| removed | 4 |
| total | 47 |

`destination_verified` is intentionally false for planned Typst/Python/setup
owners; every row now carries a destination locator. No row is eligible for deletion-gate closure until its exact owner
path and section/symbol exist and focused verification passes. Deferred action
never substitutes for migration; it records a pointer plus a pending backlog
gate.

G003 materialized and verified 30 destination pointers (including the two
deferred promotion-queue rows) against the active Typst owner graph; unresolved
rows remain intentionally open where the destination is code/setup-owned or
requires a later evidence gate.

The three former DB-shaped destinations are now non-DB canonical owners:
`retired-008-roadmap-risks` -> `development/roadmap.typ#risks`,
`retired-028-m1-blockers` -> `development/m1-contract-report.typ#blockers`,
and `retired-032-issues-blockers` -> `development/roadmap.typ#issues-and-blockers`.
Any agents-DB tracking ID remains metadata-only in `tracking_record`.

Source coverage is paragraph/bullet-oriented by stable heading anchors and
line spans: roadmap (10 rows), questions (13), M1 (6), PROJECT_STATE (5),
DECISIONS (4), GOTCHAS (3), and OPEN_QUESTIONS (6). Any later split of a span must
retain the source path and blob hash.

## Theory-QMD matrix

All 8 theory pages are classified. `rl_planning.qmd` and `rri_theory.qmd` are
**thin** candidates after Typst promotion; the remaining six are **keep**
candidates for external background/evidence. This is not deletion approval:
inbound-link and citation scans remain required, and every candidate records a
planned Typst destination with `destination_verified: false`.

## Live-consumer and provenance inventory

The repository-wide tracked-reference scan records 123 concrete path groups with
line locators: 84 dated-history, 1 resolved-provenance, 2 migration-receipt, and
36 live-reference groups. Each record uses the `classification` field, names its consumer type, disposition, and
replacement owner. Executable and generated classes were classified by path;
untracked derived artifacts remain an explicit scan gap. Only dated history,
resolved provenance, and migration receipts may retain mentions.

## Python/API coverage

Five concrete coverage rows assign implementation facts to defining
Python/config/type docstrings and focused tests; generated API remains derived
from the Makefile quartodoc targets (`Makefile:666-685`). Coverage is pending
destination materialization and must not be satisfied by this ledger or an
agents-DB record.

## PR, branch, and worktree dispositions

- #50: independent predecessor; consume exact merged handoff only. Hosted and
  local merge/tree evidence is present; no mutation is authorized here.
- #49 GitHub head `c63e95c3...` (matching local `codex/pr49-upstream-canonical-graph`):
  salvage-review against the pinned merged tree; 96 files, 2,794 insertions,
  6,990 deletions.
- #47 GitHub head `f71a8fb0...` on `codex/mempalace-compositional-integration`:
  defer until the owner map lands; 81 files, 2,480 insertions, 5,366 deletions.
  Local `codex/mempalace-agent-scaffold` at `e99303a5...` is stale and must not
  be conflated with the GitHub PR head.
- #44/#42/#38/#32/#30/#25: disposition-only; do not merge as-is.

Registered worktrees include prunable entries. They are preview-only; no branch
or worktree deletion is authorized. The redirected `core.worktree` ambiguity
in the main checkout is recorded as a hard baseline risk.

## Gate status

This inventory is intentionally provisional. JSON is the machine-readable
source for row counts and receipts; this Markdown is its concise human view.
Before S1 handoff, compare both files, run exact-link/consumer scans,
materialize canonical destinations, and run `git diff --check`.
