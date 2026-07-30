---
kind: deep-interview-spec
status: proposed
slug: aria-nbv-agent-scaffold-target-state
profile: standard
context_type: brownfield
final_ambiguity: 0.12
threshold: 0.20
---

# ARIA-NBV Agent Scaffold Target-State Specification

## Authority And Use

This document is the proposed requirements source of truth for the next
ARIA-NBV agent-scaffold attempt. It consolidates reviewed human intent,
historical OMX decisions, PR #30 evidence, local scaffold reviews, and trusted
external practice research.

It becomes authoritative only after explicit human acceptance. Until then,
`.agents/references/human_owner_intent.md` remains the reviewed preference owner
and exact code, tests, configuration, thesis sources, and papers remain
authoritative in their respective domains.

After acceptance:

- this specification owns the scaffold-rework target state and planning bounds;
- `.agents/references/human_owner_intent.md` owns only general human preferences
  outside this target state and may point here rather than duplicate it;
- later `.omx/plans/` own implementation sequencing, not requirements;
- historical reports and artifacts remain evidence with the dispositions below;
- changes to this target state require explicit supersession, not silent edits.

The specification is semantically lossless: every distinct material conclusion
from the reviewed corpus is retained, refined, rejected, deferred, or kept open.
Losslessness does not require copying repeated prose or historical implementation
detail.

## Intent

Build an agent scaffold that helps agents find the correct owner, load only the
context needed for the task, preserve valuable ARIA workflows, and verify work
from exact evidence. The scaffold must remain understandable and maintainable by
humans and must not become a second implementation of upstream orchestration,
retrieval, graph, memory, or documentation systems.

The immediate motivation is to restart after PR #30. That branch combined too
many concerns, added custom machinery before proving utility, removed useful
content, and became too large to review. The next attempt must salvage proven
capabilities without replaying the branch or repeating its migration shape.

## Desired Outcome

- Agents reach the exact owning source quickly and can explain why it is the
  owner.
- Default context is small; detail appears progressively and only when needed.
- Every durable meaning has one owner and every derived representation points
  back to it.
- Optional tools improve navigation or execution without becoming hidden
  dependencies.
- Skills remain compact procedural front doors and preserve independently useful
  capabilities.
- Scaffold changes are measured against realistic tasks and shipped as small,
  independently reviewable pull requests.
- Scientific, implementation, evidence, guidance, intent, planning, runtime,
  and historical surfaces remain distinguishable.
- Custom scaffold code and policy exist only where a measured local gap
  justifies their maintenance cost.

## Ubiquitous Language

Use these terms consistently in scaffold work:

- **Owner:** the source responsible for maintaining one class of durable
  information.
- **Authority:** an owner allowed to settle a disputed claim in its scope.
- **Evidence:** material that supports or challenges a claim but cannot settle
  it by itself.
- **Derived view:** a reproducible navigation or presentation artifact generated
  from owners, with provenance and freshness.
- **Router:** guidance that locates an owner or workflow without copying its
  durable contents.
- **Runtime state:** transient execution state used to resume or coordinate a
  tool; it is not repository truth.
- **Human intent:** an explicitly reviewed human preference or target-state
  requirement.
- **Decision record:** rationale for an accepted, consequential trade-off; it is
  not a task queue, implementation spec, state mirror, or proof of execution.
- **Plan:** a proposed implementation sequence derived from accepted
  requirements; it is not current implementation truth.
- **Capability:** a user-visible task outcome independent of the skill, script,
  tool, or upstream dependency that currently provides it.
- **Supersession:** explicit replacement of an earlier requirement or decision
  within a named scope, with predecessor and successor provenance.

Avoid unqualified uses of `context`, `memory`, `truth`, `canonical`, `artifact`,
`skill`, or `graph` when the precise category above is intended.

## Governing Principles

- **Context hygiene:** keep startup and default context small; retrieve detail
  only while it materially improves correctness or verification.
- **Single ownership:** one durable meaning has one authoritative owner. Links
  and views do not become competing stores.
- **Progressive disclosure:** root guidance is a thin map; local contracts and
  verification live near their owners; branch-specific workflow detail loads on
  demand.
- **Upstream first:** use maintained native behavior before local adaptation.
  Add a local adapter only for a demonstrated gap and keep it minimal.
- **Evidence before assertion:** exact source and fresh executable verification
  establish current facts; retrieval and agent confidence guide discovery.
- **Qualified provenance:** derived evidence records source, active worktree or
  revision, freshness, ambiguity, and extracted versus inferred status.
- **Reviewability:** one purpose, one owner, and one comparative evidence bundle
  define the pull-request unit.
- **Capability preservation:** simplify by preserving outcomes, not by retaining
  every current file or deleting every apparent duplicate.
- **Least privilege:** write authority, hooks, MCP tools, and automation are
  explicit and task-scoped rather than permissive tracked defaults.
- **Literal operational status:** configured, installed, initialized, healthy,
  and fresh are distinct states and must be reported accurately.
- **Stable language:** terminology conflicts are surfaced before design; resolved
  terms are captured in their existing owner.
- **Sparse durable decisions:** record only choices that are costly to reverse,
  surprising without rationale, and based on genuine alternatives.

## Source And Ownership Model

- Code, tests, and active configuration own executable behavior and contracts.
- Exact papers own external scientific claims and retain precise locators.
- The active Typst thesis is the target owner for scientific narrative,
  notation, and research direction. Until that migration is reviewed,
  `.agents/references/source_order.md` resolves current authority.
- Immutable manifests and evidence bundles own measurements. Reports and thesis
  prose interpret them.
- Root and nearest `AGENTS.md` files own universal and local repository
  invariants, hazards, and verification routes.
- Skills own repeatable procedures, activation, handoffs, and verification; they
  do not own scientific facts or package encyclopedias.
- `.agents/references/human_owner_intent.md` owns reviewed general human scaffold
  preferences outside this accepted target-state specification.
- Agents DB TOMLs own actionable issues, TODOs, and refactors.
- Debriefs own concise historical diagnoses, failed approaches, measurements,
  and handoffs when those are not durable elsewhere.
- OMX context, specifications, plans, handoffs, and goal ledgers own their
  workflow artifacts, not implementation or scientific truth.
- Graphs, indexes, reports, transcripts, retrieval results, and model memory are
  evidence or derived views only.

Newer intent refines older intent only within the scope actually reconsidered.
Age, similarity, inferred links, or agent consensus never performs automatic
acceptance or supersession.

## Guidance And Progressive Disclosure

- Keep root `AGENTS.md` concise: universal safety, source-order pointer, compact
  routing, instruction-capture rules, and minimal verification expectations.
- Put package hazards and local verification in the nearest `AGENTS.md` only
  after a materially distinct contract or repeated routing ambiguity justifies
  the file.
- Do not create a comprehensive root handbook, generated agent brief, or default
  all-in-one context snapshot.
- Keep package READMEs only for durable human subsystem orientation. Do not put
  agent routing, generated symbol matrices, or transient refactor inventories
  in them.
- Keep `aria-nbv-context` focused on deterministic discovery, owner location,
  provenance, and handoff. Whether it contains a small stable orientation layer
  remains open.
- Exact search and direct source reading remain the universal fallback.
- Durable guidance names capabilities and fallbacks, not developer paths,
  transient transport identifiers, or assumed optional-tool availability.

## Skill Model

- A skill must have independent procedural value, a clear trigger, a bounded
  default path, explicit exclusions, checkable completion criteria, and evidence
  that it improves task performance or predictability.
- Keep the entrypoint compact. Inline universal steps and disclose specialized
  branches through precise references.
- Split a skill only when it has an independently invocable task branch or when
  hiding later steps prevents premature completion.
- Preserve meaningful helper scripts, tests, handoffs, and failure knowledge
  during consolidation.
- Choose one primary work lane before activation branches multiply; declare
  secondary owners only for genuine cross-surface dependencies.
- Classify the actual prompt-visible runtime surface, including system,
  external, and repository skills. A repository directory count is not the
  runtime skill surface.
- Evaluate positive prompts, near misses, forbidden routes, handoffs, and task
  outcomes. Lexical consistency alone is insufficient.
- Keep `measured-autoresearch` and `agents-db` unless dedicated evidence supports
  a later change. Do not enforce an arbitrary skill-count target.
- Skills may contain operational domain procedures and precise owner pointers,
  but scientific and implementation facts remain with thesis, papers, code,
  tests, and configuration.

## Optional Tools And External Capabilities

- OMX, Graphify, MemPalace, LitKG, MCP servers, external skills, and similar
  systems remain optional evidence, navigation, or orchestration tools.
- Normal repository work and CI must remain possible from exact sources without
  these tools.
- Prefer capability descriptions over client-specific transport or launch
  details in durable guidance.
- Do not vendor or reimplement maintained external capabilities without a
  measured gap, an explicit owner, and a smaller justified maintenance surface.
- Optional automation may fail without blocking unrelated work, but it must
  report failure and must not imply that a partial result is healthy or fresh.
- Repository defaults must not silently grant broad write authority or
  permissive approval modes.
- Any external-skill pin, allowlist, vendoring policy, or recursive integrity
  check requires a dedicated decision and evidence package.

## Graphify Contract

- Graphify is a navigation accelerator, not a knowledge authority.
- Preserve native source hierarchy and `EXTRACTED`, `INFERRED`, and `AMBIGUOUS`
  provenance where Graphify proves useful.
- Consequential inferred links require exact-source verification.
- Wrong-root or materially stale graph evidence cannot establish current state.
- Benchmark unmodified current upstream Graphify before retaining hooks,
  adapters, custom parsers, old pins, or tracked outputs.
- Compare exact search, upstream Graphify, the current integration, and PR #30's
  adapter on fixed owner, path, hierarchy, thesis, literature, stale-graph, and
  false-link tasks.
- Measure locator correctness, owner-at-k, source-verification rate, runtime,
  context cost, generated size, and custom LOC.
- Do not track a graph, generated wiki, or report as project truth merely because
  upstream can generate it.
- The exact corpus, refresh model, hooks, default routing, and retained outputs
  remain open pending the comparative experiment.

## Memory, Debriefs, Conversations, And Agents DB

- Keep raw transcripts, runtime identifiers, machine paths, credentials, and
  private retrieval corpora untracked.
- Publish only reviewed distillations; do not infer truth or acceptance from
  transcript mining.
- Keep Agents DB as the actionable-work owner for now. Exclude resolved and
  historical records from active routing unless history is explicitly requested.
- Keep debriefs concise and historical rather than a default current-state
  mirror. Their exact trigger policy remains open pending retrieval-value and
  maintenance-cost evidence.
- Retire a handwritten state or history surface only after every live claim has
  a verified destination and every consumer has migrated.
- Code or chat TODOs do not automatically become debrief prose. Source-local
  TODOs stay with their owner; reviewed cross-cutting work enters Agents DB.
- MemPalace or other conversation tools may improve recall checks, but they do
  not accept, merge, or supersede requirements.

## OMX Artifact Contract

- Use native `.omx/context`, `.omx/specs`, `.omx/plans`, and handoff/goal paths
  for their documented roles.
- Accepted specifications and plans are immutable decision evidence. Changes use
  explicit successors with predecessor provenance rather than in-place rewriting.
- Keep drafts, runtime state, logs, and raw interview material ignored unless a
  separate accepted policy says otherwise.
- Preserve accepted evidence and supersession while first testing whether Git
  history and compact hashes are sufficient.
- Do not build a broad artifact registry, lifecycle engine, or natural-language
  acceptance system without a demonstrated failure that native paths and Git
  cannot solve.
- A validator or agent review supplies evidence; explicit human acceptance
  promotes this target-state specification.
- Plans derived from this specification must not silently narrow its scope,
  settle open decisions, or claim that planned work is implemented.

## Measured Autoresearch Contract

- Preserve `measured-autoresearch` as the ARIA sidecar for measurement-gated
  research and improvement loops.
- Support research-only, evaluator-design, measured implementation, and
  keep-or-discard iterations rather than forcing code changes every iteration.
- Every mission names its target function, allowed edit surface, budget, cheap
  evaluator tier, full evaluator tier, evidence outputs, reproducibility
  controls, keep/discard rule, and stop conditions.
- OMX may own orchestration and persistence; the repository-owned mission owns
  ARIA target-function and evaluator semantics.
- External engines may execute bounded packets but do not directly mutate
  policy, owner intent, roadmap, memory, or active backlog.
- Prefer cheap diagnostics before expensive experiments and record telemetry
  gaps rather than inventing measurements.
- Do not preserve dated framework recommendations as requirements.

## Documentation, Thesis, And Literature

- Keep current public documentation renderable and distinguish current thesis
  direction from historical implementation evidence.
- Source docstrings and Quartodoc own Python module and public-entity contracts,
  including non-obvious fields, shapes, units, lifecycle, and failures. Do not
  narrate trivial private helpers.
- Keep `python-docstrings` as the procedural style owner unless measured evidence
  supports a change.
- Keep scientific language, notation, equation labels, bibliography, draft
  markers, build profiles, and source links in shared Typst ownership.
- Every Typst notation symbol must resolve through the shared glossary/notation
  owner; the exact enforceable scope for equation definitions remains open.
- Cross-modal links should resolve to real code symbols, thesis sections, or
  exact literature sources and remain removable navigation rather than truth.
- Literature claims require citation resolution, authoritative TeX/PDF
  inspection, an exact locator, and calibrated wording.
- Retrieval and generated literature graphs may locate evidence but do not
  verify scientific claims.
- Thesis consolidation, Quarto retirement, equation formatting, and source-link
  changes belong in separate thesis PRs, not scaffold migration PRs.

## Operational And Security Invariants

- Distinguish configured, installed, initialized, available, healthy, and fresh.
- A failed required stage leaves the previous successful freshness marker
  unchanged.
- Non-blocking hooks and adapters report concise failures and do not hide them
  behind successful no-ops.
- Permanent validators protect stable, recurring, objectively testable failures;
  each needs an owner, positive and negative fixtures, and useful remediation.
- A validator larger or harder to maintain than the protected capability is a
  design failure unless comparative evidence proves its value.
- Validate literal owner, read-first, test, and verification paths when a small
  deterministic check prevents recurring drift.
- Avoid broad semantic policy validators and environment-specific tracked
  defaults.
- Manage intentionally versioned model checkpoints and artifacts through Git
  LFS.
- Do not restore retired cache-migration or runtime-training APIs solely for
  compatibility.

## Evaluation And Review Contract

Before destructive consolidation, freeze a representative evaluator covering:

- owner localization across code, docs, thesis, literature, and scaffold;
- positive, near-miss, and negative skill activation;
- task completion with current, candidate, and no-skill paths;
- optional-tool absence and exact-source fallback;
- stale, wrong-root, and inferred Graphify evidence;
- terminology and authority conflicts;
- retained capability regression;
- runtime/token cost, references read, and telemetry gaps; and
- human review cost, custom LOC, generated churn, files changed, and rollback.

Use executable end-state assertions as primary evidence. Use transcript or trace
review to explain failures and costs. Repeat stochastic trials and aggregate
results where necessary. Do not tune the evaluator only after seeing the
candidate result.

Every replacement pull request requires:

- one self-contained concern reflected in title, body, diff, and tests;
- one owner for every moved fact;
- one baseline-versus-candidate evidence bundle;
- explicit retained, replaced, removed, deferred, and open capabilities;
- no unrelated package, thesis, generated, or binary churn;
- a green repository and exact-head hosted CI where applicable; and
- an independent rollback boundary.

Refactors and behavior changes are separate review units unless separation would
make either change invalid.

## Goals

- Align current owner intent, source order, and routing without duplicating them.
- Preserve or repair independently useful documentation and operational skills.
- Measure the complete runtime scaffold surface and representative outcomes.
- Determine Graphify's useful role through an upstream-first comparative test.
- Retire one redundant capability implementation at a time only after parity.
- Reduce custom scaffold code and maintenance burden without deleting unique
  capability.
- Preserve useful PR #30 candidates for isolated re-evaluation: progressive
  skill disclosure, repaired documentation routing, measured-autoresearch tests,
  Graphify provenance/hierarchy, and thesis notation/linkage checks.
- Make every actionable scaffold finding receive a reviewed disposition or an
  Agents DB owner.

## Non-Goals

- No replay, merge-in-place repair, or wholesale cherry-pick of PR #30.
- No one-shot migration of skills, Graphify, LitKG, memory, OMX lifecycle,
  thesis, and generated artifacts.
- No comprehensive scaffold handbook or project encyclopedia in a skill.
- No repository-owned replacement for maintained external systems without a
  measured local gap.
- No graph, wiki, transcript corpus, generated report, debrief, or agent memory
  as authoritative project truth.
- No tracked generated graph/wiki/context merely for convenience.
- No fixed skill count, prompt-byte reduction, graph-size limit, LOC target, or
  generated-artifact count as a proxy for capability.
- No automatic truth, acceptance, conflict resolution, or supersession from
  timestamps, similarity, inferred links, or agent consensus.
- No custom natural-language intent extractor, ontology, conflict resolver, or
  broad artifact lifecycle engine.
- No generated symbol inventories, default global UML, or broad context
  snapshots as substitutes for exact owners.
- No mandatory semantic validator for terminology or preferences.
- No bulk deletion based only on apparent redundancy or file non-use.
- No thesis, package, model, metric, or runtime-training behavior hidden inside
  a scaffold PR.
- No permanent compatibility layer for retired internal APIs without an active
  supported consumer.

## Explicitly Rejected Or Superseded Proposals

- An exact seven-, eight-, or nine-skill target.
- Fixed prompt-byte, graph-size, or scaffold-LOC gates as universal acceptance
  criteria.
- A comprehensive `aria-nbv-context` handbook.
- A tracked generated wiki or graph as canonical knowledge.
- Mandatory source/graph commit pairs and automatic graph refresh before every
  query.
- A custom Graphify replacement or large parser/adapter layer before upstream
  comparison.
- Categorical LitKG removal or retention without capability evidence.
- Automatic transcript ingestion, generated agent briefs, or transcript-derived
  accepted intent.
- Mandatory generated context suites, AST inventories, symbol matrices, and
  global UML in routine routing.
- Broad synchronous hooks and hidden background mutation.
- A fixed Matt/external-skill allowlist or vendoring policy without runtime and
  maintenance evidence.
- Expansion into new generic pandas/Plotly or other skills without demonstrated
  independent demand.
- Permissive tracked write/approval defaults for every collaborator.
- Treating historical review recommendations or framework shortlists as current
  architecture.

## Open Decisions

These remain unresolved and block only their affected workpackage:

- Exact Graphify corpus, refresh behavior, retained outputs, hooks, and whether
  it is default navigation or an optional architecture aid.
- Whether LitKG provides unique claim, retrieval, or literature value after
  exact-source alternatives are verified.
- Whether `aria-nbv-context` is a pure router or contains compact stable
  orientation.
- Exact external-skill reference, allowlist, pinning, vendoring, and integrity
  policy.
- Which handwritten state surfaces can retire after owner/consumer migration.
- Whether debriefs remain required for broad non-trivial work or become strictly
  event-triggered and episodic.
- When Typst becomes the sole scientific owner and the exact enforceable shared
  glossary/equation contract.
- Minimum OMX accepted-artifact retention, archive, supersession, registry, and
  validation mechanism.
- Which PR #30 Graphify, docs, Typst, and source-link capabilities are
  non-inferior when isolated against the current baseline.

No implementation plan may silently resolve these choices.

## Decision Boundaries

After acceptance, planning agents may without further confirmation:

- deduplicate wording while preserving requirements and source pointers;
- group requirements into small workpackages and experiments;
- order non-destructive packages by dependency and evidence needs;
- define tests and measurements directly implied by this specification;
- recommend rejection of a package whose capability or owner cannot be proven;
  and
- keep unresolved choices scoped to dedicated experiments or user decisions.

Planning or execution must ask before:

- changing, weakening, or broadening an accepted invariant;
- resolving an open decision without the specified evidence or human choice;
- deleting the only known owner or implementation of a capability;
- making optional tools required for normal work or CI;
- introducing a new dependency, tracked generated corpus, broad hook, or
  permissive write authority;
- combining thesis/package semantics with scaffold work; or
- superseding this specification.

## Assumptions And Resolutions

- **Assumption:** all earlier user requests should be copied. **Resolution:**
  repeated and superseded wording is omitted, but each distinct conclusion has
  a disposition and a source pointer.
- **Assumption:** one authoritative document should contain every implementation
  fact. **Resolution:** this document owns target-state requirements only and
  points to domain owners.
- **Assumption:** PR #30 improvements should be retained because they existed.
  **Resolution:** retain them as candidates until isolated tests prove value.
- **Assumption:** upstream-first forbids local code. **Resolution:** measured,
  minimal adapters remain allowed for demonstrated gaps.
- **Assumption:** an agent review can accept this document. **Resolution:** agent
  review is evidence; explicit human acceptance is required.
- **Assumption:** standardized OMX JSON includes a generic source registry.
  **Resolution:** installed OMX provides mode-specific result and handoff JSON,
  not a generic artifact-reference registry; source pointers stay in this spec.

## Scenario Pressure Tests

- If Graphify says module A owns a symbol but current code defines it in module
  B, exact code wins and the graph is marked stale or incorrect.
- If a global instruction conflicts with the nearest `AGENTS.md`, the nearest
  applicable owner governs within its allowed scope; universal safety remains
  global.
- If a skill repeats a package invariant, the package guide keeps the invariant
  and the skill points to it.
- If an accepted old plan conflicts with newer reviewed owner intent, neither
  timestamp nor plan status resolves the conflict automatically; scope-specific
  human intent and exact owners determine the successor.
- If an optional tool is unavailable, exact-source work continues and the
  missing capability is reported rather than silently approximated.
- If a deletion removes a named file but no evaluator covers its capability,
  the retirement is blocked.
- If a hook fails after partial work, it reports the failed stage and does not
  advance freshness or imply success.
- If a historical resolved issue appears in retrieval, it remains historical
  unless explicitly reopened into Agents DB.

## Acceptance Criteria For This Specification

- Every tracked aggregation artifact in `.agents/references/scaffold_rework/`
  and both current autoresearch reports appears in the source ledger.
- June deep-interview, July decision/plan, local review corpus, and PR #30
  evidence have explicit retained/rejected/deferred/open dispositions.
- The specification separates principles, invariants, goals, non-goals,
  preferences, open decisions, and historical hypotheses.
- No unresolved decision is presented as accepted policy.
- No raw transcript, runtime identifier, credential, machine path, or private
  corpus content is tracked.
- No new source registry, graph, ontology, ADR hierarchy, or lifecycle engine is
  introduced.
- `git diff --check` passes and the committed diff contains only requirements
  artifacts and necessary index pointers.
- The human owner reviews the complete document and explicitly accepts or
  revises it before its status changes from `proposed`.
- `$plan` consumes this specification directly without repeating broad
  requirements discovery or treating historical reports as implementation
  instructions.

## Source Coverage Ledger

### Current reviewed owners and syntheses

- `.agents/references/human_owner_intent.md`
  - Role: current reviewed human preferences.
  - Disposition: incorporated throughout; remains authoritative until this spec
    is explicitly accepted.
- `.omx/specs/autoresearch-agent-scaffold-rework-20260729/report.md`
  - Role: source-aligned restart synthesis and historical disposition ledger.
  - Disposition: incorporated; implementation sequence remains advisory for the
    later planning phase.
- `.omx/specs/autoresearch-agent-scaffold-external-best-practices-20260730/report.md`
  - Role: trusted external practice research and domain-modeling adaptation.
  - Disposition: principles and limits incorporated; external advice does not
    override ARIA owner decisions.
- `.agents/references/scaffold_rework/README.md`
  - Role: evidence index and authority warning.
  - Disposition: incorporated as the evidence boundary.

### Preserved PR #30 evidence

- `.agents/references/scaffold_rework/evidence/scaffold-issue-index-20260726.md`
  - Role: measured improvements, regressions, and unresolved scaffold issues.
  - Disposition: useful capabilities retained as isolated candidates; broad
    implementation recommendations require current reproduction.
- `.agents/references/scaffold_rework/evidence/five-pr-rebuild-20260726.md`
  - Role: historical clean-room decomposition.
  - Disposition: small-PR principle retained; exact five-PR sequence deferred to
    planning against this specification.
- `.agents/references/scaffold_rework/evidence/pr30-reviewability-20260728.html`
  - Role: visual PR #30 audit.
  - Disposition: reviewability findings retained; the HTML is evidence only.
- `.agents/references/scaffold_rework/evidence/pr30-reviewability-result-20260728.json`
  - Role: historical validator record.
  - Disposition: retained as provenance, not a current digest or approval.

### Historical Git evidence

- Git commit `d24bdd18`
  - Sources: June scaffold cleanup context, cleanup PRD, deep-interview lifecycle
    record, and scaffold-goals plan.
  - Disposition: optional/replaceable-tool, bounded-adapter, operator-onboarding,
    and measured-autoresearch intent retained; dated framework choices and old
    state ownership rejected or deferred.
- Git commit `2fda4412`
  - Sources: archived July 11/14 simplification bundle and July 20 refresh
    context, plan, reviews, test spec, and handoff.
  - Disposition: durable ownership, progressive-disclosure, privacy,
    measured-autoresearch, Agents DB, direct-source, docstring, and reviewability
    decisions retained; fixed skill/graph/validator targets and categorical
    retirements rejected or deferred.
- Git commit `2b02a3bf`
  - Source: audited PR #30 experimental implementation.
  - Disposition: not a merge or migration base; isolated capabilities and
    observed failure modes are retained as experiment candidates.
- `.agents/work/agents-scaffold/` review corpus as summarized in the current
  restart report
  - Role: May 6-July 12 advisory snapshots across changing scaffold states.
  - Disposition: cross-report safety, status, routing, least-privilege, and
    autoresearch-loop principles retained; dated tool picks and expansion-heavy
    proposals rejected or deferred.

### External practice evidence

The external report contains exact links and limits for OpenAI, Anthropic,
Agent Skills, AGENTS.md, Google review guidance, GitHub customization, MCP
security, SWE-agent, and Graphify. This specification incorporates the stable
overlap: scoped instructions, finite context, focused skills, simple interfaces,
outcome evaluations, least privilege, provenance, and small changes. The source
URLs remain owned by that report to avoid duplicating a bibliography here.

## Brownfield Evidence Versus Inference

Confirmed from current artifacts:

- Current owner intent, both autoresearch reports, and the four preserved PR #30
  evidence artifacts exist in this worktree.
- The current branch is a small evidence/intent branch rather than PR #30.
- Installed OMX recognizes `.omx/specs/deep-interview-*.md` as a requirements
  artifact for planning handoff.
- Installed OMX uses mode-specific JSON contracts; no generic `omx artifact`
  source-reference registry is available.

Still requiring implementation-time verification:

- Actual prompt-visible skill inventory and context cost.
- Current Graphify behavior and comparative utility.
- Current LitKG consumers and replacement parity.
- Current state/debrief consumers and retrieval value.
- Exact client-specific skill, hook, MCP, and permission surfaces.

## Planning Handoff

After explicit human acceptance, hand this file to:

```text
$plan --direct .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
```

The plan should produce concrete, independently green workpackages and PRs. Use
consensus review only for packages with genuine architectural alternatives or
destructive retirement risk. Planning must preserve every invariant, non-goal,
open-decision boundary, and acceptance criterion in this specification.

Do not begin implementation from this artifact directly.
