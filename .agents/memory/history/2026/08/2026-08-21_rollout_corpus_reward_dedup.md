---
id: 2026-08-21_rollout_corpus_reward_dedup
date: 2026-08-21
title: "Rollout corpus reward deduplication"
status: done
topics: [rollout-inspection, streamlit, corpus-reporting]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Show reward and reconstruction evidence once over all validated selected rollout stores, without repeating active-store plots below the corpus view.

## Method
The UI now renders one plot per primary metric over all validated selected stores, retaining incompatible persisted contracts as separate traces instead of pooling them. Active-store scientific plots moved to the explicit Diagnose surface, and endpoint distributions now carry the same exact contract identity.

## Findings
The earlier repeated headings were distinct persisted candidate contracts, each backed by five selected shards, followed by a separate active-store evidence section. Opaque `unknown` profile labels now fall back to the campaign profile hash, candidate hashes are labeled explicitly, and no quality card pools incompatible generators.

## Verification
Reporting tests passed 30/30 and the focused Streamlit panel suite passed 76/76. Ruff format/check, module compilation, and `git diff --check` passed.

## Canonical Owner Impact
`rollouts.reporting` owns exact corpus aggregation. The stored-rollout reconstruction panel owns the deduplicated presentation and keeps incompatible contracts visible without pooling their traces. No schema, generation, training, or Rerun contract changed.
