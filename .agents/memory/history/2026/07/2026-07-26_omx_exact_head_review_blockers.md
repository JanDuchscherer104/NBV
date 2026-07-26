---
id: 2026-07-26_omx_exact_head_review_blockers
date: 2026-07-26
title: "OMX Exact-Head Review Blockers"
status: done
topics: [scaffold, omx, privacy, validation]
confidence: high
canonical_updates_needed: []
---

Resolved the exact-head PR1 lifecycle blockers without rewriting history. The
accepted bundle now uses a Git-ancestor baseline, hashed acceptance record,
path/hash/byte artifact provenance, all-status privacy scanning, and merge-base
transition validation through the production memory gate. Two unaccepted
pre-policy payloads containing machine-local paths were removed and replaced by
one privacy-safe disposition specification.

Verification covered the focused validator against the real merge base, the
integration/unit suite, the production memory gate, tracked-artifact privacy,
repository memory checks, root CI, and diff hygiene. The approved SCAFF report
remained byte-identical.
