# ARIA-NBV scaffold five-PR rebuild correction context

## Decision

Correct PR1's accepted evidence through a successor rather than editing either
earlier bundle. Both earlier generations are archived byte-identically. The
immediate predecessor is the PR1 correction bundle; commit `1a48952f527149c1f295121c2208da440a29d8f4`
is historical provenance for the older contract-v1 generation.

## Boundaries

- Each accepted predecessor SCAFF report is preserved byte-for-byte in its
  archive. The active successor report remains at the native specification
  path with privacy-normalized content and its own registered hash and size.
- The Prometheus plan clarifies the PR1/PR2 transcript boundary, LOC evidence,
  privacy threat model, CI history requirement, and shared-path ledger.
- The two pre-policy plans are represented only by a privacy-safe disposition
  record; their unredacted payloads are removed from the active tree.
- Raw transcript data, runtime state, and Graphify output are outside this
  bundle. PR1 freezes the Git/report corpus and aggregate transcript evidence;
  PR2 owns all-session transcript completeness and promotion review.

## Acceptance basis

The successor contains all six role families and a successor-specific hashed
acceptance record. The registry binds bundle, task, handoff, baseline,
immediate and transitive predecessor receipts, native path, byte count, and
SHA-256 without depending on branch-local Git topology. Because the PR base has
no registry, the independently reviewed merged tree establishes the first
mainline trust root; receipt enforcement becomes externally anchored for later
transitions. The LOC manifest owns both selection rules and sorted path-level
rows.
