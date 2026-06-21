---
id: 2026-06-18_codex_transcript_chat_export
date: 2026-06-18
title: "Codex Transcript Chat Export"
status: done
topics: [codex, transcripts, memory]
confidence: high
canonical_updates_needed: []
---

## Task
Update `make codex-transcripts` so the default invocation writes dated transcript
artifacts, including chat-only user/assistant records under
`.agents/memory/transcripts/raw/<date>/chat_messages.jsonl`.

## Method
Extended `scripts/codex_transcript_extract.py` to collect chat-message records
from Codex session JSONL without tool calls, tool outputs, bootstrap dumps, or
environment context. Kept existing user-message, plan-mode answer, and
distillate outputs intact. Updated the Make target help text and focused tests
for chat extraction, default writes, manifest paths, and filtering.

## Findings
- `scripts/codex_transcript_extract.py` now writes `raw/<date>/chat_messages.jsonl`
  by default and exposes `--dry-run` for count-only checks.
- `aria_nbv/tests/agent_memory/test_codex_transcript_extract.py` covers assistant
  chat extraction, duplicate user event/response filtering, and default manifest
  output.
- `Makefile` documents the new default write behavior for `codex-transcripts`.

## Verification
- Passed: `aria_nbv/.venv/bin/python -m pytest aria_nbv/tests/agent_memory/test_codex_transcript_extract.py`
- Passed: `aria_nbv/.venv/bin/ruff check scripts/codex_transcript_extract.py aria_nbv/tests/agent_memory/test_codex_transcript_extract.py`
- Passed without touching dirty repo transcript batches:
  `make codex-transcripts CODEX_TRANSCRIPT_ARGS="--sessions-root /tmp/no-such-codex-sessions --output-root <tmp>"`

## Canonical State Impact
None. Existing canonical transcript policy already allows lower-authority raw
transcript artifacts under `.agents/memory/transcripts/raw/`.
