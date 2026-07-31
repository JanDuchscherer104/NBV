---
id: 2026-07-30_commit_transcript_provenance
date: 2026-07-30
title: "Commit-linked Codex transcript provenance"
status: done
topics: [codex, provenance, git-hooks, ci]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/DECISIONS.md
---

## Task

Add privacy-bounded conversation provenance for explicitly Codex-authored
commits without making transcripts a repository truth owner or changing plain
human commit behavior.

## Method

Added an explicit commit wrapper, exact-session redacted capture, hash-bound
trailer validation, worktree-relative source hooks, and a Git-only CI range
validator. The existing batch extractor supplies exact-session parsing
primitives; commit capture never runs its global gather path.

## Findings

- Codex authorship is explicit (`ARIA_CODEX_COMMIT=1` plus
  `ARIA_CODEX_THREAD_ID`), never inferred from author identity or ambient state.
- Capture requires an explicit UTC `CODEX_TRANSCRIPT_SCOPE_START`; messages
  before that commit-relevant boundary are excluded even when they belong to
  the same repository and session. Canonical selection metadata participates
  in snapshot identity and payload validation.
- Raw/full sessions remain local. A committed slice contains only filtered
  same-repository user/assistant text, pattern-redaction metadata, and integrity
  hashes, and remains non-authoritative. The sanitizer covers enumerated
  credential, identifier, email, and machine-path shapes; it makes no arbitrary
  semantic-PII claim.
- Control-plane records contribute only to the snapshot hash. Balanced runtime
  wrappers are stripped from eligible conversation text before sanitization;
  malformed tagged messages are excluded, and residual artifact tags fail.
- The existing legacy transcript corpus is grandfathered historical evidence;
  new commit slices use the isolated `transcripts/commits/` namespace.
- Transcript-only evidence changes select no conditional CI tier, while the
  always-run impact job still validates every commit in the range.
- A cryptographic invocation nonce prevents stale hook state reuse. Wrapper
  failure removes only the generated artifact and restores amend state without
  disturbing unrelated staging.
- Parent and non-transcript-tree binding rejects replay after rebase,
  cherry-pick, squash, or content changes. Descriptor-relative no-follow
  artifact operations prevent symlink and parent-swap escapes.
- Merge commits can inherit only unchanged parent artifacts. Squashed histories
  must be recaptured as one single-parent provenance artifact rather than
  combining multiple commit slices; active merges fail before capture mutation.

## Verification

Focused temporary-repository tests cover exact-session absence and repository
identity, filtering/redaction, retry/amend, staging isolation, pointer and hash
integrity, root/single-parent/merge range validation, orphan/modify/delete
rejection, hook drift, Graphify separation, and transcript-only CI routing.
Ruff and strict mypy passed; 53 provenance tests,
the end-to-end hook shell test, 24 CI-impact tests, 9 legacy extractor tests,
and governance/documentation validation passed. The scientific tier passed 266
tests. Full local CI reached a pre-existing package-smoke environment failure:
the renderer selected CUDA while the installed PyTorch3D extension lacked GPU
support. The Graphify integration gate was separately blocked because the
workspace has Graphify 0.9.26 while the repository pins 0.9.20.

## Canonical State Impact

Updated `DECISIONS.md` with the narrow successor policy. Human preference and
memory policy now distinguish local raw/full sessions from redacted
commit-scoped provenance slices.
