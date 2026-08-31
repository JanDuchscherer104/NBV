# Recent Human-Intent Mining Report

## Conceptual TL;DR

The two-week prompt corpus supports five additions to the durable human-intent
owner: parsimony, explicit upstream traceability, orthogonal or explicitly
stacked pull requests with explanatory descriptions, preservation of useful
scientific target-state reasoning with clear status labels, and a bounded
scientific taste for active perception, geometry, self-consistency, and
elegance. The proposed owner edit records those preferences without promoting
task-local implementation requests, scientific claims, runtime instructions,
or workflow mechanics.

## Corpus and method

The mining window was 2026-08-17 through 2026-08-31, inclusive. Its staged
count ledger is:

| Branch | Stage | Count |
| --- | --- | ---: |
| Broad diagnostic | Dated JSONL session fragments scanned by the repository extractor | 1,755 |
| Broad diagnostic | Fragments with extractor-level ARIA-NBV project evidence | 1,215 |
| Human-provenance sieve | Root-session fragments selected from all 1,755 scanned fragments | 564 |
| Human-provenance sieve | Root fragments with extractor-level ARIA-NBV evidence | 308 |
| Human-provenance sieve | Deduplicated `user` records emitted from those root fragments | 1,554 |
| Human-provenance sieve | Prompt records remaining after wrapper and injection exclusion | 504 |
| Human-provenance sieve | Distinct root sessions represented by those records | 69 |
| Human-provenance sieve | Structured plan answers reviewed alongside the prompts | 12 |
| Semantic review | Direct preference-cue records manually shortlisted | 33 |

The recipe used the dated session directories as explicit inputs to
`scripts/codex_transcript_extract.py`, with the repository root supplied as
`--project-root` and a temporary output root outside the repository. A session
was admitted as a root only when its `session_meta.payload.parent_thread_id`
was null or absent and `session_meta.payload.source` was a scalar rather than a
delegated-agent metadata object. The repository extractor then required either
a working directory under the project root or ARIA-NBV marker context, while
rejecting records whose working directory identified another repository.

The final injection sieve rejected empty text. For XML-like wrappers it matched
the opening tag name before either whitespace or `>`—equivalently,
`^<tag(?:\s|>)`—so wrappers with attributes were excluded too. The tag families
and literal prose prefixes were:

```text
tag families: skill, recommended_plugins, subagent_notification,
codex_delegation, codex_internal_context, turn_aborted,
in-app-browser-context, environment_context, INSTRUCTIONS

literal prefixes: # AGENTS.md instructions, # Context from my IDE setup:,
You are, Your task is
```

The 33-record preference-cue count is a manual review shortlist, not another
machine classifier. Because JSONL `user` records can contain delegated agent
assignments and injected bootstrap material, the extractor's lexical labels
were treated only as discovery aids. All 504 remaining records were reviewed
semantically against the live owner and the owner's Git history during the
same window.

Promotion followed this model:

1. A prompt is evidence, not policy.
2. Repetition or unusually direct wording makes a preference a candidate.
3. A candidate is rejected if it is task-local, contradicted, stale, private,
   already meaningfully owned, or actually a workflow or implementation rule.
4. Only a reusable cross-task preference absent from the canonical owner is
   promoted, in concise public-safe language.

Raw prompts, session identifiers, machine paths, credentials, and private
transcript material are intentionally absent from this report. Date and
truncated content-hash locators provide local auditability without publishing
the underlying conversation corpus.

## Accepted candidates

| Candidate | Bounded evidence | Why it belongs in human intent |
| --- | --- | --- |
| Parsimony | 2026-08-18 `cb560d979b07`; 2026-08-25 `ecdc78b7b5d7`; 2026-08-28 `34d7064af526` | Repeated requests for the simplest adequate solution and welcomed simplification express a cross-task design preference. The existing owner favored minimal adapters, but did not state the general preference clearly. |
| Upstream traceability | 2026-08-24 `4ba4098a52f9`; 2026-08-26 `1a884e1ab287` | Repeated requests require externally grounded local guidance to retain provenance and one explicit, opt-in refresh route. Concrete update commands remain workflow-owned. |
| Orthogonal or explicit stacked PRs, with explanatory PR bodies | 2026-08-26 `682a3c07ab5c`, `9b742e96de4c`; 2026-08-27 `c1f988cefefb`; 2026-08-29 `ba798f3fb7f`, `da2a2e4ee3c`; 2026-08-31 `812537e8c478`, `7568f974880e` | Review unit shape and the desired reviewer-facing explanation recur across unrelated work. Exact Git operations remain workflow-owned; the durable preference is small orthogonal units, explicit dependency stacks, a conceptual TL;DR, educational theory, and rendered decision-relevant figures. |
| Preserve scientific status distinctions | 2026-08-31 `b8ee2e509661`, `3f45d2b1fd4c` | The user repeatedly asks not to erase useful conceptual targets while requiring implemented, target, and speculative states to remain distinct. This governs cross-document reasoning rather than one thesis passage. |
| Bounded scientific taste | 2026-08-26 `308bb319b4ab` | The prompt explicitly identifies active perception, geometric reasoning, self-consistency, parsimony, and elegance as preferences while warning against overfitting to them. Recording the qualifier keeps this a lens, not a scientific claim or hard constraint. |

## Already captured or routed elsewhere

| Theme | Disposition |
| --- | --- |
| Keep thesis prose and implementation synchronized | Already owned by the agent-behavior workflow and exact source hierarchy. |
| Publish review comments, close resolved threads, and verify exact PR heads | Already owned by external-action and PR verification guidance; these are procedures, not human intent. |
| Graphify readiness, worktree setup, and degraded routing | Already captured in the human-intent scaffold preferences and the Graphify/context workflow. |
| Theory-rich Python docstrings | Already owned by Python standards and its focused reference. |
| Reader-centred scientific exposition that states objects positively through their structure, role, and justification | Already owned by academic-writing guidance and its reader-centred exposition reference. |
| Figure-gallery proposal and selection loops | A repeatable Typst-authoring workflow candidate, not a general owner preference. |
| Development-only Typst styling and individual visualization choices | Owned by the affected Typst source, authoring guidance, and tests. |
| Candidate-generation, dataset, loss, masking, and geometry choices | Task-specific scientific or implementation decisions; route to their code, tests, evidence, issue, or thesis owner. |
| Contradictory operational instructions | Rejected as session-scoped and unsuitable for durable promotion. |

## Canonical edit

The owner update is deliberately limited to:

- two new core principles for parsimony and upstream traceability;
- a sharper reviewability principle for orthogonal PRs and necessary stacks;
- a PR-exposition principle covering conceptual TL;DRs, theory, and rendered
  decision-relevant figures; and
- two scientific-collaboration principles covering status distinctions and the
  user's explicitly qualified scientific taste.

No executable behavior, scientific claim, backlog item, or external-system
state is changed.

## Limitations and residual risk

The local extractor is conservative about text matching but not sufficient to
prove human authorship from role labels alone. The root-session and injection
sieve reduces that risk, and manual semantic comparison provides the promotion
decision, but the aggregate counts should not be interpreted as a complete
measurement of every user preference. Content hashes are audit locators, not
authority or acceptance signals.

The report evaluates only the stated two-week window. Older preferences remain
subject to the canonical owner's reviewed supersession rules.
