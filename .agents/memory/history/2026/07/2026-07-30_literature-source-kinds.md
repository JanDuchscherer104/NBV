---
id: 2026-07-30_literature_source_kinds
date: 2026-07-30
title: "Literature Source Kinds"
status: done
topics: [literature, architecture, sources]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/literature/README.md
  - docs/literature/sources.jsonl
---

## Task

Add *The Pragmatic Programmer* to the selected-source manifest and clarify how
arXiv, web, and direct-PDF sources compose without forcing one source kind into
another's fields.

## Result

The book is recorded as a metadata-only GitHub source. It has no local PDF
target, because the linked repository does not establish redistribution rights
for the third-party book. The manifest contract now describes source
capabilities: landing-page metadata, arXiv TeX acquisition, and explicit PDF
acquisition are independent field pairs.

## Verification

- Parsed every JSONL row as a JSON object.
- Regenerated the literature context index.
- Ran the literature-context fallback test and agent-memory validation.

## Canonical-State Impact

No thesis or implementation state changed. This is a literature-selection and
operator-contract update only.
