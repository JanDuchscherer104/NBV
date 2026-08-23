# Agent Memory

This directory stores episodic evidence and migration indexes. Current truth
lives with the smallest source-order owner: active Typst, Python/configuration,
tests, setup, or agent guidance. The agents DB stores actionable follow-up
metadata; it is not a narrative owner.

## Layout
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes

## What Happened To The Old `.codex/*` Debriefs
- Dated or clearly episodic notes were imported into `history/YYYY/MM/` with YAML frontmatter.
- Ambiguous or undated legacy notes were archived under `archive/codex-legacy/flat/`.
- Previous canonical-input documents such as the old `AGENTS.md` and `AGENTS_INTERNAL_DB.md` were archived under `archive/codex-legacy/canonical-inputs/`.
- The migration inventory is recorded in `index/codex_migration_manifest.md`.

## Current Policy
- Capture only reusable evidence, durable decisions, failed approaches,
  consequential verification, or canonical-owner impact. Task length alone
  does not make work eligible for a debrief.
- Eligible tasks should leave a debrief in `history/YYYY/MM/`.
- If a task changes current truth, update its exact canonical owner selected by
  `.agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy`.
- Architect and critic review outputs remain session-local. Capture only their
  accepted durable decisions in the relevant Typst, code/config/test, setup, or
  guidance owner; put actionable work in the agents DB and a bounded task
  summary in `history/`.
- If a task does not change current truth, say so explicitly in the debrief instead of silently relying on chat history.

## Debrief Contract

Native debriefs use absolute ISO dates and include `id`, `date`, `title`,
`status`, `topics`, `confidence`, `canonical_updates_needed`, and the
stable `touched_owner_paths` list. The originating Codex thread is recorded as
`codex_thread: codex://threads/<thread-id>`; this field is required for native
records dated on or after 2026-08-21. Use `make new-debrief TITLE="..."
CODEX_THREAD_ID="<thread-id>"` to create the canonical frontmatter and body.
Earlier historical records are grandfathered.
Native records dated on or after 2026-08-22 also include portable checkout
provenance: `repo_object_format` (`sha1` or `sha256`), the corresponding full
`repo_head`, attached `repo_branch` or `detached`, and `worktree_kind`
(`primary` or `linked`). The recorded object format makes OID validation
portable across checkouts. Earlier and legacy-imported records are
grandfathered; provenance is never backfilled.
Keep the body to task, method, findings, verification, and canonical-state
impact. Add `files_touched`, `source_legacy_path`, `artifacts`, or assumptions
only when they make the record materially easier to audit.

Existing records with `status: legacy-imported` are grandfathered archive
evidence and do not need backfilling unless a task explicitly requests it.
Use absolute ISO dates (`2026-05-08`) in frontmatter and prose; debriefs outlive
the session that wrote them.

### No Canonical Updates

```yaml
---
id: 2026-03-25_example_debrief
date: 2026-03-25
title: "Example Debrief"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed: []
touched_owner_paths: []
codex_thread: codex://threads/<thread-id>
---
```

### With Canonical Updates

```yaml
---
id: 2026-03-25_example_with_state_updates
date: 2026-03-25
title: "Example Debrief With State Updates"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/development/roadmap.typ
  - aria_nbv/aria_nbv/<owner>.py
touched_owner_paths: []
codex_thread: codex://threads/<thread-id>
---
```

When it materially clarifies the work, note staged or commit scope in a dirty
worktree and whether compatibility was deliberately preserved or removed.
For a reviewed-intent proposal, put the existing target owner path in
`canonical_updates_needed`; the body must contain the exact five-field
`## Human Intent Proposal` template below. The jq query is only a first-stage
candidate listing: open each source and confirm the exact five fields with
`Disposition: proposed` before treating it as pending. Legacy target-path rows
without that body are not proposals. The candidates can be listed with:

```sh
jq -r 'select(.canonical_update_paths | index(".agents/references/human_owner_intent.md")) | .source_path' \
  .agents/memory/index/debriefs.jsonl
```

```md
## Human Intent Proposal
- Proposed statement: <reusable statement>
- Evidence: <exact user statement or bounded evidence>
- Current owner or conflict: <reviewed policy or unresolved conflict>
- Scope and target owner: <scope and exact owner path>
- Disposition: proposed
```

The proposal is only evidence until the `agents-db` `proposal-review` mode
assigns exactly one disposition. That mode owns the lifecycle: `accept` and
`narrow` require an ordinary edit to the smallest policy owner; `reject`
resolves the existing record with a reason while policy bytes stay unchanged;
`defer` leaves policy unchanged and keeps the record active. TOML records the
lifecycle but never installs policy automatically.
The JSONL file at `index/debriefs.jsonl` is a derived navigation index only.
It contains no findings, rankings, authority scores, or current-truth claims.
Every row exposes `touched_owner_paths` and `codex_thread`. Older
`files_touched` metadata is normalized without backfilling historical
Markdown; missing legacy owner paths become an empty list and a missing legacy
thread becomes `null`.
Regenerate it with `make debrief-index`; `make check-agent-memory` rejects
added, edited, deleted, renamed, or malformed visible history sources until it
matches. Open each indexed `source_path` before consequential historical use.

### Filter, Then Open

Use the index to narrow candidates; use the source opener for evidence:

```sh
jq -r 'select(.topics | index("scaffold")) | [.date, .status, .source_path] | @tsv' \
  .agents/memory/index/debriefs.jsonl
jq -r 'select(.date >= "2026-08-01" and .status == "done") | .source_path' \
  .agents/memory/index/debriefs.jsonl
source_path=$(jq -r 'select(.topics | index("scaffold")) | .source_path' \
  .agents/memory/index/debriefs.jsonl | head -n 1)
test -n "$source_path"
python3 scripts/debrief_index.py --query "$source_path"
```
