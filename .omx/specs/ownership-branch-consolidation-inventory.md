# Ownership and branch-consolidation inventory (S1 complete)

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
are in the JSON companion. Deleted-source Git blobs remain auditable at receipt
commit `9c246b2cc99110d32e161371138d0378dd34f22a`.

## Disposition ledger summary

The JSON companion contains 47 source-block rows (each with stable id, source blob, heading/anchor or bullet
span), each with subject, disposition, canonical destination, destination
verification, and link action. Current disposition counts remain:

| disposition | rows |
|---|---:|
| historical (retired source retained as receipt/provenance) | 33 |
| deferred-action (follow-up only) | 4 |
| code-owned | 5 |
| test-owned | 1 |
| removed | 4 |
| total | 47 |

All 47 ledger rows now point to an exact single owner path/anchor or defining
symbol/test, and `destination_verified` is true for each row. The 33 retired
source blocks are historical receipts after owner materialization; deferred
promotion items remain explicit follow-up work.

G004 narrowed the implementation and routing receipts to exact Python, test,
Typst, setup, source-order, and CI owners. G005 retired the duplicate QMD and
memory-state files while preserving their source hashes. The ledger now records
47 verified destination pointers against the active owner graph.

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

All 8 theory pages are retained only as **deprecated** docs-owned archive,
navigation, or external-background references. Their immutable blob OIDs and content hashes are recorded
in the JSON receipt; Typst and Python owners remain authoritative. This is not
deletion approval: inbound-link and citation scans remain required, and every
candidate records a planned Typst destination with `destination_verified: true`.

## Live-consumer and provenance inventory

The repository-wide tracked-reference scan records 121 concrete path groups with
line locators: 85 dated-history, 34 resolved-provenance, and 2 migration-receipt groups.
Immutable transcript artifacts are recorded as resolved, historical, and
non-authoritative provenance; retired state paths are omitted from the consumer
ledger and remain covered only by bounded migration receipts.
Each record uses the `classification` field, names its consumer type, disposition, and
replacement owner. Executable and generated classes were classified by path;
untracked derived artifacts remain an explicit scan gap. Only dated history,
resolved provenance, and migration receipts may retain mentions.

## Python/API coverage

Five concrete coverage rows assign implementation facts to exact defining
Python/config/type symbols and focused tests; generated API remains derived from
the Makefile quartodoc targets (`Makefile:666-685`). Coverage is verified.

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

JSON is the machine-readable source for row counts and receipts; this Markdown
is its concise human view. Deletion-ready now passes with live/generic-sink
negative tests retained. Before handoff, compare both files, rerun exact-link
scans, and run `git diff --check`.
