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
- `.agents/references/human_owner_intent.md` continues to own general cross-task
  human preferences and points here for requirements scoped to this rework;
- later `.omx/plans/` own implementation sequencing, not requirements;
- historical reports and artifacts remain evidence with the dispositions below;
- changes to this target state require explicit supersession, not silent edits.

The specification is decision-lossless: it retains accepted current intent,
unresolved conflicts, and capabilities at risk from destructive cleanup.
Superseded implementation hypotheses may be summarized by source family rather
than copied or individually registered.

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
- Omx stays the domain agnostic orchestration harness.
- Skills remain compact procedural front doors and preserve independently useful
  capabilities.
- Scaffold changes are measured against realistic tasks and shipped as small,
  independently reviewable pull requests.
- Scientific, implementation, evidence, guidance, intent, planning, runtime,
  and historical surfaces remain distinguishable.
- Custom scaffold code and policy exist only where a measured local gap
  justifies their maintenance cost.

## Domain Ubiquitous Language And Scaffold Vocabulary

ARIA-NBV's domain ubiquitous language has one source family:

- `docs/typst/shared/glossary.typ` owns domain terms, definitions, aliases,
  relationships, citation keys, and references to notation and equations;
- `docs/typst/shared/symbols.typ` and `docs/typst/shared/symbols/*.typ` own domain
  symbols and their stable keys; and
- `docs/typst/shared/equations.typ` and `docs/typst/shared/equations/*.typ` own
  named equations and their stable keys.

`docs/typst/shared/notation.typ`, generated glossary/notation files, rendered
glossaries, Quarto pages, skills, graphs, and agent guidance are consumers or
derived views. They must not redefine a term, symbol, or equation independently.
When code or prose needs new domain language, update the appropriate shared
Typst owner first and reference its stable key from the consuming surface.

The following terms are narrower scaffold-governance vocabulary for this
specification. They do not compete with the domain glossary:

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
- **Upstream first:** use maintained native behavior (omx, graphify, mattpocock/skills, ...) before local adaptation.
  Add a local adapter only for a demonstrated gap and keep it minimal.
- **Evidence before assertion:** exact source and fresh executable verification
  establish current facts; retrieval and agent confidence guide discovery.
- **Qualified provenance:** derived evidence records source, active worktree or
  revision, freshness, ambiguity, and extracted versus inferred status.
- **Reviewability:** one purpose, one owner, and one comparative evidence bundle
  define the pull-request unit.
- **Capability preservation:** simplify by preserving outcomes, not by retaining
  every current file or deleting every apparent duplicate.
- **Literal operational status:** configured, installed, initialized, healthy,
  and fresh are distinct states and must be reported accurately.
- **Stable language:** terminology conflicts are surfaced before design; resolved
  domain terms, symbols, and equations are captured in the shared Typst owners
  named above; scaffold-governance terms remain scoped to this specification.
- **Rich source-owned linkage:** connect thesis prose, glossary entries,
  equations, symbols, code contracts, tests, measurements, and exact literature
  through stable owner-defined identifiers and resolvable links. Links improve
  traversal without copying the linked fact into another authority.
- **Sparse durable decisions:** record only choices that are costly to reverse,
  surprising without rationale, and based on genuine alternatives.

## Source And Ownership Model

The principal repository owners are:

- `aria_nbv/aria_nbv/` owns Python implementation and runtime behavior. Public
  module, class, function, DTO, shape, unit, lifecycle, and failure contracts
  live in source signatures, types, and docstrings; `aria_nbv/tests/` proves
  executable behavior; active TOML and Python configuration owns selected
  runtime parameters. Generated Quartodoc pages render source contracts but do
  not own them.
- `docs/typst/thesis/main.typ` and its includes under
  `docs/typst/thesis/sections/` own the active thesis narrative, research
  questions, method, evaluation interpretation, limitations, and submission
  claims.
- `docs/typst/shared/glossary.typ`, `docs/typst/shared/symbols.typ`,
  `docs/typst/shared/symbols/*.typ`, `docs/typst/shared/equations.typ`, and
  `docs/typst/shared/equations/*.typ` own domain ubiquitous language, notation,
  and named mathematical definitions.
- `docs/contents/literature/*.qmd` owns curated repository literature synthesis,
  while `docs/literature/sources.jsonl` records the local source catalog,
  `docs/references.bib` and `docs/references-qh.bib` own citation identities,
  and exact papers or their authoritative TeX/PDF sources own external
  scientific claims and locators.
- Root and nearest nested `AGENTS.md` files own repository-wide and local
  invariants, hazards, and verification routes. `.agents/references/source_order.md`
  resolves current conflicts while this proposed target state is being reviewed.
- `.agents/references/human_owner_intent.md` owns reviewed general human
  preferences. After acceptance, this specification owns only the requirements
  scoped to the scaffold rework.
- `.agents/issues.toml`, `.agents/todos.toml`, `.agents/refactors.toml`, and
  `.agents/resolved.toml` own actionable and resolved maintenance work through
  Agents DB.
- Immutable manifests and evidence bundles own measurements. Reports and thesis
  prose interpret them.
- Skills own repeatable procedures, activation, handoffs, and verification; they
  do not own scientific facts or package encyclopedias.
- Debriefs own concise historical diagnoses, failed approaches, measurements,
  and handoffs when those are not durable elsewhere.
- OMX context, specifications, plans, handoffs, and goal ledgers own their
  workflow artifacts, not implementation or scientific truth.
- Graphs, indexes, reports, transcripts, retrieval results, and model memory are
  evidence or derived views only.

Newer intent refines older intent only within the scope actually reconsidered.
Age, similarity, inferred links, or agent consensus never performs automatic
acceptance or supersession.

## `.agents/references` Target State

`.agents/references` is not a general documentation shelf. In the accepted
target state it contains only small, human-maintained, cross-cutting maps that
have no more local owner:

```text
.agents/references/
  README.md                 # index and scope boundary only
  human_owner_intent.md     # reviewed general human preferences
  source_order.md           # concise authority and conflict-resolution map
```

The index lists these owners and points to package, documentation, tool, OMX,
and test surfaces without restating their content. Files do not remain in this
directory merely because agents may find them useful. Before moving or deleting
one, preserve each still-current rule in its closest source owner and prove that
its active consumers use that owner. Git history preserves superseded policy;
it is not necessary to keep a second active copy for provenance.

The current files have these target dispositions:

- `README.md`: add this new compact index only after the migration. It lists
  the two substantive references, states what does not belong in the directory,
  and points outward without copying owner content.
- `agent_memory_templates.md`: move the surviving debrief schema and examples
  beside the debrief implementation, preferably `.agents/memory/README.md` or
  the script/template that validates them. Delete it if debriefs retire.
  > Not sure, would merge memory and debrief instructions into [$mempalace-aria-nbv:agents-db](/home/jd/repos/ARIA-NBV/.agents/skills/agents-db/SKILL.md)
- `alignment_tools_contract.md`: fold its universal rule, optional tools produce
  evidence rather than truth, into root guidance and this specification. Move
  tool-specific behavior beside each retained tool, then delete the aggregate.
- `context7_library_ids.md`: keep contents, integrate in new aria-nbv context routing skill;
- `external_stack_contracts.md`: move live ATEK, EFM3D, EVL, and Project Aria
  contracts to the nearest `data_handling`, rendering, or package owner,
  including source docstrings and tests. Delete package-docstring TODO lists or
  move actionable items to Agents DB.
- `human_owner_intent.md`: retain, but keep only reviewed general preferences.
  Scaffold-rework requirements move to this specification after acceptance.
- `source_order.md`: retain and rewrite as the concise current authority map.
  Remove stale QMD, generated-context, handwritten-state, or tool routes as
  their owners change; do not turn it into a project encyclopedia.
- `litkg_quick_reference.md`: while LitKG remains undecided, treat this as
  migration input. If LitKG is retained, put only ARIA-specific operations
  beside its configuration or vendored tool documentation and rely on upstream
  docs for generic usage. If LitKG retires, delete the file after replacement
  checks pass.
- `omx_artifact_policy.md`: if a repository OMX lifecycle is retained, move its
  minimal tracked-artifact contract to `.omx/README.md` and enforce it with the
  smallest existing validator. Otherwise rely on upstream OMX behavior and
  delete the local policy.
- `omx_quick_reference.md`: delete the generic command guide and link to pinned
  upstream OMX documentation. Preserve only proven ARIA-specific deviations
  beside `.omx/` or in the optional-operator section of root guidance.
- `operator_quick_reference.md`: retire the mixed grab bag. Move environment
  recovery to package setup documentation; tool health to the retained tool;
  frame notation to the Typst glossary and geometry package; EFM views to
  `data_handling`; and dirty-worktree invariants to root guidance.
- `python_conventions.md`: move durable cross-package Python contracts to
  `aria_nbv/AGENTS.md`, source docstrings, formatter/type configuration, and
  executable tests. Do not maintain a prose duplicate of configured rules.
  <!-- Not sure, maabe make our python standards a skill? -->
- `rollout_zarr_q_invalidity_contract.md`: move this domain contract beside
  `aria_nbv.rollouts`, its schema/codecs, tests, and corresponding Typst
  definitions. The package `AGENTS.md` may summarize hazards and routes but may
  not duplicate the complete schema.
- `skill_style_guide.md`: move the minimal skill authoring contract to
  `.agents/skills/README.md` and its validator. Generic authoring advice should
  come from the upstream skill-authoring capability rather than an ARIA copy.
- `thesis_code_links.md`: move the durable link convention into the contract
  documentation of `docs/typst/shared/style.typ`, with a short route in
  `docs/AGENTS.md`. Compile-time behavior remains owned and tested by the Typst
  implementation.
- `verification_matrix.md`: distribute commands to the nearest `AGENTS.md`,
  package/test owner, Make target help, or retained tool documentation. Root
  guidance keeps only universal verification expectations; delete the central
  matrix after every active route has a local owner.
- `scaffold_routing_fixtures.json`: it is executable test data, not a reference.
  Replace it with the smallest accepted smoke scenarios under the scaffold
  test owner, or delete it if the current skill-name-specific fixture no longer
  tests a retained outcome.
- `scaffold_rework/README.md` and `scaffold_rework/evidence/*`: retain them only
  through review and acceptance of this specification. After acceptance, the
  specification's decision-lossless dispositions, frozen PR/commit references,
  and Git history are the durable record; remove this temporary evidence tree
  from the active scaffold rather than creating another archive hierarchy.

Migration is content-led, not file-led. Each workpackage inventories distinct
current claims, assigns each claim to one owner, updates consumers, validates
the replacement, and only then removes the old file. Copying a whole reference
file to a new directory without reducing overlap does not satisfy this target.

## Cross-Modal Linkage Contract

Rich linkage is a repository requirement, not a Graphify-specific feature:

- Glossary entries use their structured `internal_links`, `citations`,
  `symbol_refs`, and `equation_refs` fields to connect domain language to thesis
  sections, bibliography entries, symbols, and equations.
- Thesis sections use glossary terms, shared `symb` and `eqs` keys, citations,
  and the source-link macros in `docs/typst/shared/style.typ` to connect claims
  to their definitions, evidence, and implementation anchors.
- The contract documentation and implementation in
  `docs/typst/shared/style.typ` own the final versus draft code-link convention:
  final-worthy links use `gh`, drafting links use `gh-wip` or `gh-symbol`, and
  submission builds disable draft-only navigation. During migration,
  `.agents/references/thesis_code_links.md` is an input to that owner, not a
  permanent parallel contract.
- Public code docstrings link to the relevant thesis section, glossary key,
  equation key, evidence contract, or paper when that relationship is necessary
  to understand semantics. They do not copy thesis prose or mathematical
  definitions into Python documentation.
- Literature syntheses resolve citation keys to `docs/references.bib` or
  `docs/references-qh.bib` and preserve exact source locators. Thesis claims link
  to those citations rather than treating a graph or synthesis page as proof.
- Tests and immutable measurement manifests link to the implementation contract
  they verify; thesis results link to the exact evidence bundle they interpret.
- Durable links use repository-relative paths, stable glossary/symbol/equation
  keys, citation keys, code symbols, commit or release identifiers, and stable
  evidence IDs. Machine paths, runtime IDs, generated graph-node IDs, and
  search-result positions are not durable identifiers.

Link validation must check that touched targets resolve, that final thesis links
are pinned appropriately, that draft-only links disappear in submission mode,
and that no derived navigation surface becomes the only representation of a
relationship. Graphify may discover, index, or validate these links, but the
source-owned links must remain usable when Graphify is absent.

## Guidance And Progressive Disclosure

- Keep root `AGENTS.md` concise: universal safety, source-order pointer, compact
  routing, instruction-capture rules, and minimal verification expectations.
- Put package hazards and local verification in the nearest `AGENTS.md` only
  after a materially distinct contract or repeated routing ambiguity justifies
  the file.
- Do not create a comprehensive root handbook, generated agent brief, or default
  all-in-one context snapshot.
- Code documentation should live in doc-strings.
- Keep package READMEs only for durable human and agent subsystem orientation, domain specific usage information, sometimes domain specific architecture and implementation details. Do not put
  agent routing, generated symbol matrices, or transient refactor inventories
  in them.
- Preserve deterministic discovery, owner location, provenance, and handoff as
  an outcome without freezing the current router or its file layout.
- Exact search and direct source reading remain the universal fallback.
- Durable guidance names capabilities and fallbacks, not developer paths,
  transient transport identifiers, or assumed optional-tool availability.
- Global Codex guidance remains pointer-only for ARIA-NBV; repository guidance
  owns ARIA policy, routing, and verification.
- Scoped UML generation remains an explicit, untracked operator aid. It is not a
  default context surface, runtime-flow model, or API authority.

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
- Report repository-controlled and complete runtime surfaces separately. Skill
  counts, description bytes, and LOC are maintenance/context costs, not evidence
  that a capability was preserved.
- Evaluate positive prompts, near misses, forbidden routes, handoffs, and task
  outcomes. Lexical consistency fixtures are lint, not routing or capability
  evaluation.
- Keep `measured-autoresearch` and `agents-db` unless dedicated evidence supports
  a later change. Do not enforce an arbitrary skill-count target.
- Do not blindly drop any of our established preferences, invariants in skills like [$mempalace-aria-nbv:typst-authoring](.agents/skills/typst-authoring/SKILL.md).
- Skills may contain operational domain procedures and precise owner pointers,
  but scientific and implementation facts remain with thesis, papers, code,
  tests, and configuration.

Cleanup preserves outcome contracts rather than current skill names or file
layouts:

- agents locate the exact owner, respect dirty-worktree boundaries, choose one
  primary lane, and verify the result;
- Typst, Quarto, bibliography, rendering, and source-link tasks reach complete
  progressively disclosed authoring guidance;
- diagnostic prompts reach one usable workflow or an exact-source fallback; and
- removing or consolidating a named skill is allowed when these outcomes remain
  covered by the shared smoke set or a workpackage-local comparison.

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
- First decouple Graphify from mandatory routing, hooks, freshness gates, CI
  requirements, and ordinary task completion. Preserve the existing integration
  dormant long enough to remain a reproducible comparison candidate.
- Compare exact-source routing, the dormant current integration, and unmodified
  current upstream Graphify on fixed owner, path, hierarchy, thesis, literature,
  active-bibliography, stale-graph, false-link, broad-query, and exact-file
  negative-routing tasks.
- Measure locator correctness, owner-at-k, source-verification rate, runtime,
  context cost, generated size, and custom LOC.
- Keep generated graph, report, and wiki output local, reproducible, and
  non-authoritative.
- After the comparison, the human owner selects complete deletion, optional
  unmodified upstream use, or upstream plus one proven thin adapter. A planning
  agent must not infer that choice from a composite score.
- The exact optional corpus, refresh model, and retained local outputs remain
  open until that selection. Graphify does not return to required routing or CI.

The frozen PR #30 evidence establishes a narrower historical result: exact
`path`/`explain` traversal and native hierarchy were useful when the symbol or
file was already known. Broad natural-language retrieval was noisy; inferred
link precision, scaffold-corpus coverage, and agent-productivity benefit were
not established; and the custom adapter grew while suppressing native report
and visualization outputs. These findings define comparison cases, not a reason
to retain that adapter.

## Memory, Debriefs, Conversations, And Agents DB

- Keep raw transcripts, runtime identifiers, machine paths, credentials, and
  private retrieval corpora untracked.
- Publish only reviewed distillations; do not infer truth or acceptance from
  transcript mining.
- Keep Agents DB as the actionable-work owner for now. Exclude resolved and
  historical records from active routing unless history is explicitly requested.
- Historical ledgers, debriefs, and resolved records must be visibly historical;
  references to retired tools must not appear as current routes or owners.
- Keep debriefs concise and historical rather than a default current-state
  mirror. Retain the current non-trivial-work trigger policy; a later measured
  package may propose narrowing it from retrieval-value and maintenance-cost
  evidence.
- Retire a handwritten state or history surface only after every live claim has
  a verified destination and every consumer has migrated.
- Code or chat TODOs do not automatically become debrief prose. Source-local
  TODOs stay with their owner; reviewed cross-cutting work enters Agents DB.
- MemPalace or other conversation tools may improve recall checks, but they do
  not accept, merge, or supersede requirements.

## OMX Artifact Contract

- Use native `.omx/context`, `.omx/interviews`, `.omx/specs`, and `.omx/plans`
  paths for selected current review, decision, report, plan, and handoff
  artifacts. Tracking is independent of acceptance; proposed material may be
  versioned for review.
- Keep drafts, runtime state, goals, logs, team data, caches, temporary files,
  and routine autoresearch mission/sandbox/result sidecars ignored. Track a
  sidecar exceptionally only when it is unique durable evidence.
- The working tree contains current review or accepted artifacts and final
  evidence that remains useful. When an artifact is superseded, remove it and
  identify its former path and Git commit from the successor when provenance is
  material. Git history is the archive.
- After this specification is accepted, retain it and the current evidence
  index. Remove its context and interview once their decisions are represented
  or assigned, unless either contains unique unresolved evidence.
- Do not add an `.omx/archive`, artifact registry, byte-identical bundle copies,
  tombstones, seed recovery, purge simulation, rollback journal, or
  natural-language acceptance system without a separately demonstrated failure
  that native paths and Git cannot solve.
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
- Source docstrings own Python module and public-entity contracts, including
  non-obvious fields, shapes, units, lifecycle, and failures. Quartodoc renders
  those contracts as generated human-facing documentation. Do not narrate
  trivial private helpers.
- Preserve contract-focused Python docstring authoring and Quartodoc
  compatibility as outcomes; the current procedural skill may be consolidated
  when those outcomes remain covered.
- Keep scientific language, notation, equation labels, bibliography, draft
  markers, build profiles, and source links in shared Typst ownership.
- Every Typst notation symbol must resolve through the shared glossary/notation
  owner; the exact enforceable scope for equation definitions remains open.
- Typst owns visible thesis structure, citations, and code-reference anchors;
  code and docstrings own implementation symbols; BibTeX and exact papers own
  citation identity and scientific evidence.
- Cross-modal links must resolve through those source owners and remain useful
  without Graphify. Graphify may index or enrich them as qualified derived
  evidence but may not become their sole representation.
- Literature claims require citation resolution, authoritative TeX/PDF
  inspection, an exact locator, and calibrated wording.
- Retrieval and generated literature graphs may locate evidence but do not
  verify scientific claims.
- Thesis consolidation, Quarto retirement, equation formatting, and source-link
  changes belong in separate thesis PRs, not scaffold migration PRs.
- Native Typst and BibTeX extraction by upstream Graphify remains unproven for
  this repository. Any ARIA adapter requires a measured gap and an isolated
  experiment after the clean scaffold baseline exists.

## Operational And Security Invariants

- A failed required stage leaves the previous successful freshness marker
  unchanged.
- Non-blocking hooks and adapters report concise failures and do not hide them
  behind successful no-ops.
- Tracked hook/configuration changes and installed operator state must not drift
  silently. Heavy synchronous post-commit work requires measured latency and an
  explicit failure policy; it is not a default scaffold mechanism.
- Permanent validators protect stable, recurring, objectively testable failures;
  each needs an owner, positive and negative fixtures, and useful remediation.
- A validator larger or harder to maintain than the protected capability is a
  design failure unless comparative evidence proves its value.
- Validate literal owner, read-first, test, and verification paths when a small
  deterministic check prevents recurring drift.
- Avoid broad semantic policy validators and environment-specific tracked
  defaults.
- Narrow scaffold validators should be hermetic where practical and must not
  require unrelated network access, Git LFS objects, or a full-repository clone
  merely to validate a local planning or routing contract.
- Manage intentionally versioned model checkpoints and artifacts through Git
  LFS.
- Do not restore retired cache-migration or runtime-training APIs solely for
  compatibility.

## Evaluation And Review Contract

Before destructive consolidation, freeze one tiny shared smoke set covering
owner discovery, progressive disclosure, diagnostic routing, and exact-source
work when optional tools are absent. Each destructive workpackage adds only the
bounded comparison needed for the capability it removes or replaces.

Prefer native Codex runs, existing tests, and shell checks. Use executable
end-state assertions as primary evidence and transcript or trace review only to
explain failures and costs. Repeat stochastic trials only where necessary. Do
not create a general evaluator framework, dashboard, ontology, transcript
processor, or scoring engine, and do not tune checks after seeing the candidate
result.

Accounting reports distinguish repository-controlled versus observed runtime
surfaces and production, test, generated, and upstream code. No combined byte
or LOC total may be presented as task-success or retained-capability evidence.

Graphify's dedicated comparison additionally covers owner and path discovery,
native hierarchy, thesis-code-literature relationships, stale or wrong-root
evidence, false inferred links, optional-tool fallback, runtime, context cost,
generated size, and custom LOC. These dimensions remain disaggregated evidence
for the human decision rather than inputs to an automatic composite score.

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
- Make scaffold measurements literal and disaggregated so cost reductions are
  not reported as capability or productivity gains.
- Determine Graphify's useful role through an upstream-first comparative test.
- Retire one redundant capability implementation at a time only after parity.
- Reduce custom scaffold code and maintenance burden without deleting unique
  capability.
- Preserve useful PR #30 candidates for isolated re-evaluation: progressive
  skill disclosure, preflight discipline, repaired authoring and diagnostic
  routing, measured-autoresearch tests, Graphify provenance/hierarchy, source
  links, and the thesis-only notation and prune audits.
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
- The PR #30 OMX registry, archive copies, tombstones, seed recovery, purge
  simulation, rollback machinery, and pinned lifecycle subsystem.
- The custom HTML intent reviewer and its extraction/validation machinery as a
  maintained scaffold subsystem.
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

- Which optional Graphify role, if any, the human owner selects after the
  exact-source/current-integration/unmodified-upstream comparison, followed by
  the exact corpus, refresh behavior, and retained local outputs for that role.
- Whether LitKG provides unique claim, retrieval, or literature value after
  exact-source alternatives are verified.
- Exact external-skill reference, allowlist, pinning, vendoring, and integrity
  policy.
- Which handwritten state surfaces can retire after owner/consumer migration.
- When Typst becomes the sole scientific owner and the exact enforceable shared
  glossary/equation contract.

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
  repeated and superseded wording is omitted. Accepted current requirements,
  unresolved conflicts, and capabilities exposed to destructive cleanup remain
  decision-lossless; historical implementation hypotheses may be summarized by
  source family.
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
- If Graphify is absent, agents still follow Typst-to-code links, resolve
  bibliography citations to exact papers, and complete ordinary repository work.
- If the Graphify comparison has mixed results, no aggregate score selects its
  role; the human owner reviews the disaggregated evidence and chooses.
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
  evidence have source-family dispositions, while every accepted current
  requirement, unresolved conflict, and capability at risk from destructive
  cleanup is retained explicitly.
- The specification separates principles, invariants, goals, non-goals,
  preferences, open decisions, and historical hypotheses.
- No unresolved decision is presented as accepted policy.
- No raw transcript, runtime identifier, credential, machine path, or private
  corpus content is tracked.
- No new source registry, graph, ontology, ADR hierarchy, or lifecycle engine is
  introduced.
- The final `.agents/references` tree contains only its index,
  `human_owner_intent.md`, and `source_order.md`; every removed file has a
  claim-level owner/disposition and no live consumer of the obsolete path.
- `git diff --check` passes and the committed diff contains only requirements
  artifacts and necessary index pointers.
- The human owner reviews the complete document and explicitly accepts or
  revises it before its status changes from `proposed`.
- Acceptance is a separate atomic follow-up that changes the specification
  status, updates the evidence-index pointer, and removes scoped duplication
  from `human_owner_intent.md`. Context and interview records are then removed
  once fully represented or assigned, unless they retain unique unresolved
  evidence.
- `$plan` consumes this specification directly without repeating broad
  requirements discovery or treating historical reports as implementation
  instructions.

## Source Coverage Ledger

### Current reviewed owners and syntheses

- `.agents/references/human_owner_intent.md`
  - Role: current reviewed human preferences.
  - Disposition: incorporated throughout; remains authoritative until this spec
    is explicitly accepted and continues to own general cross-task preferences
    afterward.
- `.omx/specs/autoresearch-agent-scaffold-rework-20260729/report.md`
  - Role: source-aligned restart synthesis and historical disposition ledger,
    including the reviewed `.agents/work/agents-scaffold/` corpus.
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
  - Disposition: compact skill/docs routing, measured autoresearch, owner
    localization, and native-shaped graph hierarchy/provenance remain isolated
    candidates. Scoped prompt budgets, lexical routing fixtures, structural
    graph tests, headline LOC, corpus omissions, inferred-link errors, hook
    drift, and historical-record leakage become explicit measurement and
    replacement constraints. Exact workpackages require current reproduction.
- `.agents/references/scaffold_rework/evidence/five-pr-rebuild-20260726.md`
  - Role: historical clean-room decomposition.
  - Disposition: clean baseline, serial small PRs, one owner, one proof,
    explicit capability dispositions, stop conditions, and rollback boundaries
    retained. Its exact five-PR sequence, tool choices, fixed path inventories,
    transcript/graph machinery, and migration ledgers are not requirements.
- `.agents/references/scaffold_rework/evidence/pr30-reviewability-20260728.html`
  - Role: visual PR #30 audit.
  - Disposition: exact Graphify traversal and hierarchy, measured-autoresearch,
    progressive disclosure, authoring restoration, and preflight discipline are
    candidate capabilities. Noisy broad retrieval, incomplete graph coverage,
    custom-code growth, suppressed upstream outputs, red CI, hidden scope,
    binary/generated churn, and unproven deletion parity are failure evidence.
    RQ5, Quarto/Typst parity, bibliography/glossary, and PDF findings remain with
    thesis/documentation owners and outside scaffold PRs.
- `.agents/references/scaffold_rework/evidence/pr30-reviewability-result-20260728.json`
  - Role: historical validator record.
  - Disposition: proves only that the HTML passed its stated historical review
    prompt; it is provenance, not approval of PR #30, this specification, or a
    current implementation.

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

Still requiring implementation-time verification against the active baseline:

- Actual prompt-visible skill inventory and context cost.
- Current Graphify behavior and comparative utility; frozen PR #30 observations
  remain historical evidence rather than current-state claims.
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
