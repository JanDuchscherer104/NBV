# PR1 evidence coverage

## Successor correction

Commit `1a48952f527149c1f295121c2208da440a29d8f4` is historical provenance for
the older contract-v1 generation. Independent review verified its twelve
registered artifacts byte-identically against the archived bundle while that
history was available. Live contract-v2 validation instead checks immediate and
transitive content receipts and does not require that branch-local commit to
remain reachable after squash or rebase.

This PR is the registry bootstrap: its base has no accepted registry against
which the imported chain can be authenticated. The exact independently reviewed
tree that merges to the mainline establishes the first trust root. Receipts
prove internal chain consistency during bootstrap and enforce immutability for
all later transitions whose merge base contains that root; they cannot by
themselves authenticate a coordinated rewrite of the bootstrap tree.

PR1's frozen evidence corpus is the 130-commit scaffold branch, its history and
path inventories, the accepted SCAFF report, and aggregate transcript-manifest
facts below. It is not an all-session assertion inventory. Normalization,
privacy review, conflict/supersession classification, and owner promotion for
all ARIA-NBV sessions remain blocking PR2 work.

## PR #28 snapshot

PR #28 was closed as superseded on 2026-07-26. Its head was
`6339bb74d8e382937d728318cc18ad07a9063eef`, its base was `main`, and CI
reported Root Verification as failure/UNSTABLE. The local raw snapshot has
SHA-256 `876e497f4136f8fa78bc1043a8aa7d9bd3b31a91ecec5181b039b1c107b3a3af`.
No raw comments are retained here.

## History reconciliation

The authoritative commands are:

```text
git rev-list --count --first-parent b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
git log --first-parent --format= --name-only b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
git diff --name-only b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
```

After blank-line removal and unique path sorting, these yield 130 commits, 391
history-touched paths, 366 final-net paths, and 25 transient paths. Counts of
392 and 26 are line-count-with-header variants of the same ledgers. Non-first-
parent `git log` diff semantics yield lower counts and are not this contract.

The two removed pre-policy plan payloads retain only privacy-safe provenance in
[`legacy-plan-disposition.md`](legacy-plan-disposition.md): historical source
commits, native paths, SHA-256 digests, byte counts, classification,
disposition, and successor links. They were not accepted six-role bundles.

## Transcript coverage

The 2026-06-22 local manifest recorded 552 candidate ARIA sessions, 47,211 raw
and 42,774 deduplicated chat messages, 12,684 raw and 3,110 deduplicated user
messages, and 3,489 candidate decisions. Its SHA-256 is
`bb889cda2c403ab7c6fa96e41a7576203daf7e75015af3406e24b7928ec345d2`.
The 2026-07-25 scaffold-distill manifest matched only four sessions and is not
a full refresh; its SHA-256 is
`69b255168b429509193e97124677b22054413a180ae59adf3fe243248ded4c9e`.

All-session normalization, privacy scanning, review, conflict/supersession
classification, and promotion remain PR2 blockers. This evidence does not claim
that all prior prompts are reconciled.

## LOC baseline

[`loc-manifest.json`](loc-manifest.json) is the single machine-readable owner of
the baseline selection rules, sorted category/path/physical-line rows, and
category summaries. Its test regenerates every row from Git blobs at
`b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c`; no production evidence generator
or second glob list is retained.

## Current owners and supporting evidence

Current ownership and existing evidence remain in
[`source_order.md`](../../../.agents/references/source_order.md),
[`human_owner_intent.md`](../../../.agents/references/human_owner_intent.md),
the accepted plan's
[Temporal Decision Ledger](../../plans/prometheus-strict/aria-nbv-scaffold-five-pr-rebuild.md#temporal-decision-ledger),
and the [SCAFF report](../autoresearch-agent-scaffold-issue-index-20260726/report.md).
Their content is not duplicated here.

## External pins

- [Graphify 0.9.26 at `66d8110a534b52df3d660b5fda5aa5461a6b667a`](https://github.com/Graphify-Labs/graphify/tree/66d8110a534b52df3d660b5fda5aa5461a6b667a)
  is [Apache-2.0](https://github.com/Graphify-Labs/graphify/blob/66d8110a534b52df3d660b5fda5aa5461a6b667a/LICENSE).
- [MemPalace v3.6.0 at `8ab251c452c43f2b07a76a28f2433e258307f571`](https://github.com/MemPalace/mempalace/tree/8ab251c452c43f2b07a76a28f2433e258307f571)
  is [MIT](https://github.com/MemPalace/mempalace/blob/8ab251c452c43f2b07a76a28f2433e258307f571/LICENSE).
  [Contradiction handling](https://mempalaceofficial.com/concepts/contradiction-detection.html)
  is incomplete/experimental, so this release is not characterized as stable.
- [Matt skills at `ed37663cc5fbef691ddfecd080dff42f7e7e350d`](https://github.com/mattpocock/skills/tree/ed37663cc5fbef691ddfecd080dff42f7e7e350d)
  is [MIT](https://github.com/mattpocock/skills/blob/ed37663cc5fbef691ddfecd080dff42f7e7e350d/LICENSE).

Only primary-source links and paraphrases are retained; upstream guidance text
is not copied.
