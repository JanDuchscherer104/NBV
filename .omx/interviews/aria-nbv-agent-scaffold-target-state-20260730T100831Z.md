# Interview Summary: ARIA-NBV Agent Scaffold Target State

## Profile

- Profile: standard, crystallization from prior interviews and accepted user
  corrections
- Context type: brownfield
- New user-facing rounds: none
- Final ambiguity: 0.12
- Threshold: 0.20
- Closure status: ready to crystallize; unresolved choices are explicit planning
  or experiment gates

## Intent

Replace the scattered and partly contradictory scaffold planning corpus with one
reviewable statement of what the next scaffold attempt must preserve, avoid, and
prove. Prevent another PR #30-sized migration from turning derived evidence,
plans, or tooling into competing sources of truth.

## Resolved Boundaries

- Requirements consolidation now; implementation planning later.
- Decision-lossless coverage of accepted current intent, unresolved conflicts,
  and capabilities at risk from destructive cleanup; no transcript reproduction.
- Existing exact sources remain authoritative in their domains.
- The target-state specification becomes authoritative for this scaffold rework
  only after explicit human acceptance.
- `human_owner_intent.md` continues to own general cross-task preferences after
  acceptance; the specification owns only this scoped target state.
- Historical reports, plans, conversations, graphs, and debriefs remain evidence.
- No new generic artifact registry or source-reference schema is introduced.
- Track selected current artifacts at native OMX role paths independently of
  acceptance status; proposed review material may be versioned.
- Keep runtime state and generated sidecars local. Remove superseded artifacts
  from the working tree and recover them from Git history rather than copying
  them into an OMX archive.
- Source docstrings own Python contracts; Quartodoc renders them for humans.
- Preserve outcome contracts rather than current skill names or file layouts,
  except for the explicitly retained `measured-autoresearch` and Agents DB
  capabilities.
- Retain the current non-trivial-work debrief policy pending a separate measured
  proposal.
- Decouple Graphify from required routing before comparing exact-source,
  current-integration, and unmodified-upstream behavior. Its final role requires
  explicit human selection.
- `docs/typst/shared/glossary.typ`, the shared symbol modules, and the shared
  equation modules own ARIA-NBV's domain ubiquitous language. Generated
  notation/glossary views consume those owners rather than redefining them.
- Typst sections, code/docstrings, BibTeX, evidence manifests, and exact papers
  own durable cross-modal links through stable keys and resolvable source
  anchors; Graphify may index them but must not become their sole
  representation.
- Retire the custom HTML intent reviewer and extraction machinery as maintained
  scaffold capabilities.
- Use one tiny shared smoke set plus bounded workpackage-local comparisons rather
  than a comprehensive evaluator framework.
- Measure the complete prompt-visible runtime separately from the subset the
  repository controls; description-byte and LOC reductions are cost evidence,
  not capability evidence.
- Treat lexical routing fixtures as lint. Destructive routing changes require
  representative activation and task-outcome evidence, including negative and
  optional-tool-absent cases.
- Keep historical records visibly historical, and keep narrow scaffold checks
  independent of unrelated network, Git LFS, or full-repository state.

## Preserved Evidence Conclusions

- The issue index supports retaining compact progressive skill disclosure,
  repaired documentation routing, measured autoresearch, source ownership, and
  Graphify's native-shaped hierarchy/provenance as candidates. It also shows
  that scoped prompt budgets, lexical routing fixtures, structural graph tests,
  and headline LOC do not establish runtime usefulness or capability parity.
- The five-PR rebuild contributes the clean-baseline, serial small-PR,
  one-owner, one-proof, explicit-disposition, and rollback-boundary principles.
  Its exact five-PR sequence, tool choices, fixed inventories, and broad
  migration ledgers are historical proposals, not target-state requirements.
- The PR #30 audit establishes that exact Graphify path/explain and native tree
  hierarchy worked at audited commit `2b02a3bf`, while broad queries were noisy,
  inferred-link precision and agent productivity were unproven, corpus coverage
  was incomplete, and custom integration LOC diverged from upstream minimalism.
- The audit's RQ5, Quarto-to-Typst parity, bibliography, glossary, generated PDF,
  and other thesis findings remain actionable evidence for thesis owners. They
  must not be hidden inside scaffold PRs or misrepresented as scaffold fixes.
- The JSON validator record proves only that the historical HTML audit passed
  its stated review prompt; it does not approve PR #30 or this specification.

## Pressure Pass

Earlier proposals treated simplicity as deletion, single ownership as broad
consolidation, and Graphify or OMX lifecycle machinery as architecture. PR #30
showed that these interpretations can reduce reviewability and remove valuable
capabilities. The resolved interpretation is capability-preserving
simplification: small owner-scoped changes, exact-source fallback, measured
replacement, and explicit retained/rejected/deferred/open dispositions.

## Unresolved Decisions Preserved

- Which optional Graphify role, if any, the human owner selects after the
  exact-source/current-integration/unmodified-upstream comparison and, if it is
  retained, its exact corpus, refresh policy, and local outputs.
- LitKG's remaining unique value.
- External-skill referencing, allowlisting, pinning, or vendoring.
- Handwritten state retirement after owner and consumer migration.
- Typst sole-ownership migration and exact glossary enforcement.

## Handoff

Review `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`.
After explicit acceptance, use it as the requirements input to `$plan`; do not
repeat broad requirements discovery or begin implementation from the historical
reports.
