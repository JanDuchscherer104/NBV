---
id: 2026-08-21_require_codex_thread_links_in_debriefs
date: 2026-08-21
title: "Require Codex Thread Links In Debriefs"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a0235f-e433-7832-9712-7f44babaf4a1
---

## Task
Require future native debriefs to identify the originating Codex task with a
`codex://threads/<thread-id>` deeplink.

## Method
Inspected `.agents/memory/README.md`, `scripts/new_debrief.py`, and the
`make new-debrief` target; updated the canonical contract and scaffold.

## Findings
New debrief scaffolding requires `--thread-id` or `CODEX_THREAD_ID` and emits a
`codex_thread` frontmatter field. The current task is recorded at
`codex://threads/01a0235f-e433-7832-9712-7f44babaf4a1`.

## Verification
`python3 -m py_compile scripts/new_debrief.py scripts/validate_agent_memory.py`
passed; missing-thread invocation failed as intended; `make check-agent-memory`
passed.

## Canonical Owner Impact
Updated `.agents/memory/README.md`, `scripts/new_debrief.py`, and the Makefile
scaffold. No current scientific or product truth changed.
