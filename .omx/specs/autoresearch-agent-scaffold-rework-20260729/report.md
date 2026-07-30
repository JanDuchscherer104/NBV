---
kind: spec
status: current
---

# ARIA-NBV Agent Scaffold Rework: Source-Aligned Restart

## Scope And Completeness

This revision audits every source family requested for the scaffold restart:

- all user-authored messages in the reviewed private Codex parent task;
- PR #30 at audited head `2b02a3bff7ac2fccffd8118b2790ec3f3803b6e5`;
- the June 9-10 scaffold deep-interview lineage recovered from Git history;
- the dated May 6-July 12 local review corpus under
  `.agents/work/agents-scaffold/`;
- the July 11 decision record, July 14 context and plan, and July 20 context and
  successor plan named by the repository owner;
- the completed Python/package-guidance autoresearch goal metadata;
- the local `writing-great-skills` reference; and
- current upstream guidance from OpenAI, Anthropic, Agent Skills, and Graphify.

"Complete" here means that every requested source family has a disposition and
every non-trivial candidate is represented as retained, superseded, rejected,
deferred, or unresolved. It does not mean that repeated prompts, transient
execution instructions, or implementation detail are copied into the target
state. User-authored intent is primary preference evidence; historical OMX
artifacts are decision evidence; PR #30 is experimental evidence; external
guidance is comparative practice evidence, not authority over ARIA choices.

The Python/package-guidance goal's metadata and passing verdict remain, but its
referenced `findings.md` is absent. This report therefore preserves the goal and
its rubric as an evidence gap; it does not repeat the unavailable findings as
verified conclusions.

## Executive Verdict

Start again from current `main` through small, independently useful pull
requests. Do not merge, repair in place, or replay the history of PR #30.

The previous work found several useful capabilities: compact progressive
disclosure, stronger Typst ownership, measured-autoresearch, exact Graphify
traversal, native hierarchy visualization, equation numbering, source-link
macros, and visible prune evidence. It also demonstrated that aggressive
consolidation can delete operational knowledge, move complexity into custom
validators, and claim simplification without measuring what agents actually
receive or whether tasks still succeed.

The new attempt therefore follows one rule:

> One purpose, one owner, and one comparative evidence bundle per pull request.

This is an ARIA review policy, not a claimed universal best practice. A material
claim needs a baseline, candidate evidence, objective assertions, cost or
context impact, and human review; one green check is not sufficient.

This report is decision evidence. Current code, tests, configuration,
`human_owner_intent.md`, `source_order.md`, the active thesis, and exact papers
remain authoritative for their own claims.

## Durable Invariants

- Keep default context small and load detail only when needed.
- Give every durable meaning one authoritative owner.
- Keep root guidance thin and place contracts beside their nearest owner.
- Prefer upstream behavior by default; retain a local adapter or small
  implementation only when a measured gap and comparative evidence justify it.
- Treat graphs, retrieval, plans, debriefs, and agent output as evidence, never
  automatic truth.
- Preserve source, freshness/worktree, ambiguity, and extracted/inferred
  provenance for derived evidence.
- Keep optional tools optional: exact-source repository work must remain
  possible without OMX, Graphify, MemPalace, or LitKG.
- Keep primary scientific and domain facts in code, tests, the active thesis,
  and exact papers. Skills may own stable operational procedures and precise
  pointers, but must not become competing fact stores.
- Preserve privacy: raw transcripts, runtime identifiers, machine paths,
  credentials, and private retrieval corpora remain untracked.
- Prefer small owner-scoped PRs and explicit capability dispositions over
  all-at-once migration.
- Require fresh executable verification before claiming completion.
- Retire an owner only after its facts and consumers have verified destinations.
- Operational status must be literal: distinguish configured, available,
  initialized, healthy, and fresh. Never advance a freshness marker after a
  failed required stage or report a partial result as current.
- Durable guidance names capabilities and fallbacks, not client-specific MCP
  transport identifiers, developer paths, or assumed tool availability.
- Non-blocking automation may report failure without stopping unrelated work;
  it must not suppress failure and imply success.
- Approval and write-autonomy defaults are operator choices, not repository
  invariants, unless the owner explicitly adopts them for every collaborator.
- Active routing and backlog evidence exclude resolved and historical records
  unless the task explicitly requests history.
- Keep accepted plans immutable and supersede them explicitly.
- Keep Python entity contracts in source docstrings and render them through
  Quartodoc; require useful contract documentation, not narration of trivial
  private helpers.
- Keep package READMEs only for durable human subsystem orientation. Do not
  generate symbol matrices or duplicate routing policy in them.
- Keep UML an explicit, untracked, operator-only architecture aid. It is not a
  default context surface, runtime flow model, or API authority.
- Resolve literature claims from authoritative TeX/PDF sources with citation,
  exact locator, and calibrated wording. Retrieval tools may locate evidence
  but do not verify the claim.
- Give every actionable scaffold finding one disposition: reject, deduplicate,
  preserve as a protocol, or record in Agents DB.

## Goals

The target scaffold should:

- route an agent quickly to the exact owning source;
- provide a compact operator-onboarding route from global Codex guidance back
  to repository-owned policy without duplicating ARIA rules globally;
- expose detail progressively instead of loading a project handbook;
- preserve independently useful ARIA workflows without mirroring domain truth;
- measure the complete prompt-visible skill surface, not a convenient subset;
- evaluate routing and skills using realistic task outcomes and negative cases;
- use Graphify only where it improves owner or relationship discovery over
  exact search at acceptable context and maintenance cost;
- retain `measured-autoresearch` for research-only, evaluator-design, measured
  implementation, and keep-or-discard iterations;
- make every measured-autoresearch mission name its target function, safe edit
  surface, cheap and full evaluator tiers, evidence output, and keep/discard
  rule; external engines may execute packets but do not own these semantics;
- keep autoresearch and other external harnesses behind bounded adapter
  contracts: explicit budgets and stop conditions, reproducible evidence, and
  proposals rather than direct mutation of owner surfaces;
- retain Agents DB as the actionable-work owner for now;
- determine the debrief trigger from measured retrieval value and maintenance
  cost; keep debriefs historical rather than a current-state mirror;
- keep generated navigation local, reproducible, and non-authoritative;
- reduce custom scaffold implementation without deleting unique capabilities;
- preserve Git LFS ownership for versioned checkpoints and model artifacts;
- avoid restoring retired cache-migration or runtime-training APIs merely for
  compatibility; and
- make every retained skill predictable: a clear trigger, a bounded process,
  checkable completion criteria, and branch-specific detail disclosed only when
  needed;
- choose one primary work lane before activation branches multiply, while
  naming secondary owners explicitly for genuinely cross-surface changes;
- classify every prompt-visible default, system, external, and repository skill
  as retained, disabled, explicitly invoked, uncontrollable, or unresolved;
  repository-local counts alone are not the runtime surface; and
- preserve the thesis-wide shared-notation requirement. Every notation symbol
  used in Typst must resolve through the shared glossary/notation owner. The
  earlier phrase that every "equation" must be defined there is retained as an
  ambiguity: equation labels and semantic definitions belong in shared
  ownership, but copying every equation body would violate single ownership.

## Non-Goals

- No comprehensive scaffold handbook or duplicated scientific narrative.
- No repo-owned replacement for Graphify, OMX, MemPalace, or a literature
  engine when maintained upstream behavior is sufficient.
- No automatic truth, acceptance, conflict resolution, or supersession from
  similarity, timestamps, inferred links, or agent consensus.
- No fixed skill-count target without task-success evidence.
- No tracked wiki, graph, transcript corpus, or generated report as project
  truth.
- No wholesale deletion of skills, Quarto pages, state journals, LitKG routes,
  or context helpers before replacement parity is demonstrated.
- No thesis, package, or runtime behavior changes hidden in a scaffold PR.
- No replay of PR #30's commits or large custom policy engines.
- No generated symbol inventories, default global UML, or broad context
  snapshots as substitutes for exact owners.
- No numeric simplification target, skill count, graph size, or LOC result that
  can hide lost capability or new custom maintenance cost.

## Source Authority And Alignment

Use the following precedence when sources disagree:

1. Current reviewed owner intent determines scaffold preferences.
2. Current code, tests, configuration, thesis sources, and exact papers
   determine implementation and scientific truth in their respective scopes.
3. Newer user intent refines older intent only within the scope actually
   reconsidered; age alone never performs supersession.
4. Accepted OMX artifacts preserve decisions and rationale, but do not override
   current owners or prove that an implementation worked.
5. PR #30 and generated reports provide observations and candidates only.
6. External sources inform design, but ARIA-specific policies remain explicit
   owner choices.

The named July artifacts are audited at their native repository-relative paths,
not at the stale archive paths used by the previous report:

- `.omx/specs/aria-nbv-agent-scaffold-simplification-20260711/decision-record.md`
- `.omx/context/agent-scaffold-consensus-20260714T081220Z.md`
- `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714.md`
- `.omx/context/agent-scaffold-refresh-20260720T110000Z.md`
- `.omx/plans/ralplan-aria-nbv-agent-scaffold-refresh-20260720.md`
- `.omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/`

The PR #30 issue index, five-PR proposal, HTML audit, and validator result are
copied review evidence in `.agents/references/scaffold_rework/evidence/`; they
are not present at that path in the primary checkout and are not promoted to
current truth by being preserved here.

## External Practice Evidence

The restart adopts only practices supported by both the project intent and a
plausible operational benefit:

- OpenAI's [Harness Engineering](https://openai.com/index/harness-engineering/)
  reports that a short `AGENTS.md` works better as a map than as a monolithic
  manual, and that stable architecture and documentation invariants benefit
  from mechanical checks.
- Anthropic's
  [context-engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  frames context as a finite attention budget and recommends the smallest
  high-signal token set that supports the desired outcome.
- Agent Skills guidance on
  [descriptions](https://agentskills.io/skill-creation/optimizing-descriptions),
  [best practices](https://agentskills.io/skill-creation/best-practices), and
  [evaluation](https://agentskills.io/skill-creation/evaluating-skills)
  supports progressive disclosure, focused descriptions, realistic positive
  and near-miss prompts, repeated trials, and comparison with a no-skill or
  previous-skill baseline.
- Upstream [Graphify](https://github.com/Graphify-Labs/graphify) provides native
  query, path, explain, hierarchy, and extracted/inferred provenance behavior.
  These features must be evaluated before ARIA adds wrappers; inferred edges
  guide discovery but consequential claims still require exact-source checks.

These sources do not establish ARIA's optional-tool policy, immutable-plan
policy, exact source hierarchy, or PR boundaries. Those are owner preferences.
Likewise, local `disable-model-invocation` behavior is client-specific and must
be measured in the actual Codex runtime rather than treated as a portable Agent
Skills standard.

## Skill Design Contract

The local `writing-great-skills` reference contributes the following
requirements without becoming a second project-truth store:

- Predictability means a repeatable process, not identical generated output.
- A model-invoked skill spends startup context; a user-invoked skill spends
  human recall. Independent reach must justify the chosen cost, and a router is
  useful only when explicit skills exceed practical recall.
- A description states one distinct trigger per execution branch. Synonyms and
  body summaries are duplication, not coverage.
- Every procedural step ends in a checkable completion criterion; important
  criteria account for the complete touched surface and prevent premature
  completion.
- Inline what every branch needs; move branch-only reference material behind a
  precise context pointer; keep a concept's definition, rules, and caveats
  co-located.
- Split a skill only for independent invocation or when hiding later steps
  prevents premature completion. Do not split merely to shorten files.
- Prune duplicate, irrelevant, no-op, sedimentary, and ceremonial prose.
  Prefer positive target behavior; reserve negation for real guardrails.
- Admit, change, or retire a skill only against realistic activation and task
  fixtures, including adjacent negative cases and a prior/no-skill baseline.

Do not optimize only a hand-picked ARIA skill count. Inventory the actual client
catalog: discovered skill, precedence/collision, invocation eligibility,
startup description bytes, activated body, references read, and task outcome.
Where runtime telemetry is unavailable, record an evidence gap rather than a
file-based estimate presented as runtime truth.

## Historical Evidence Ledger

### June 9-10 scaffold deep interview and goal persistence

Recovered Git-history sources at commit `d24bdd18f111369762fc6f9a9a14ed241e26fe80`:

- the session-scoped `deep-interview-state.json` lifecycle record;
- `.omx/context/agent-scaffold-cleanup-20260609T205222Z.md`;
- `.omx/plans/agent-scaffold-cleanup-prd-20260609.md`; and
- `.omx/plans/prometheus-strict/agent-scaffold-goals-20260610.md`.

The state JSON is lifecycle metadata, not the interview transcript. The
substantive durable artifacts are the context, PRD, and goals plan. They were
first tracked by `56c2bc21`, restored by `d24bdd18`, and removed from the active
tree by `40febb61` as indexed OMX runtime artifacts.

Retain: repository-owned ARIA policy with pointer-only global onboarding;
strict ownership and replaceable external tools; deterministic checks rather
than fuzzy duplicate-policy gates; contract-level verification routes across
code, docs, literature, CLI, Streamlit, and visual evidence; and an
autoresearch adapter that has explicit budgets, seeds where applicable,
dry-run/stop behavior, and evidence/proposal outputs without directly mutating
policy, memory, roadmap, or active backlog.

The narrow June 9 cleanup PRD is not the complete interview result. In the same
task, the owner explicitly said that the first implementation omitted requested
operator workflows and then requested persistence of all scaffold goals. The
June 10 goals plan therefore refines the PRD for intent coverage.

Do not inherit automatically: the contemporary shortlist of LangGraph, Open
Deep Research, LlamaIndex, smolagents, CrewAI, or other harnesses; the old
`.agents/memory/state/` ownership assignment; or a requirement to build broad
automation before a bounded task and evaluator justify it. Those are historical
implementation hypotheses or later-contested ownership choices.

### May 6-July 12 local scaffold review corpus

The ignored local review corpus under `.agents/work/agents-scaffold/` spans four
different scaffold states and must be read chronologically:

- May 6 reviews evaluate PR #13-era routing and propose substantial LitKG,
  generated-context, and skill expansion.
- June 10 autoresearch reports compare then-current external engines.
- June 19 reviews focus on safety, routing overlap, tool capability, and
  empirical skill evaluation.
- July 8-12 reviews inspect external-skill integration and the implemented
  scaffold immediately before the simplification decision record.

The files are advisory snapshots, not accepted decisions, and several assess
commits or tool versions that are no longer current. Their specific tool picks,
skill counts, renames, and deletion catalogs therefore receive no standing
authority.

Retain these additional cross-report conclusions:

- Keep edits request-traceable and choose one primary lane. A secondary owner
  is a declared dependency, not a reason to activate every broad router.
- Treat tool health as layered state. Configured does not mean installed;
  installed does not mean initialized for the active worktree; ready does not
  mean fresh; and a CLI-readiness probe is not an end-to-end health check.
- Make freshness transactional and scoped to the stage or source family that
  succeeded. Failure injection must prove that a failed required stage leaves
  the previous successful marker unchanged.
- Make hook and adapter failures concise and visible. Avoid `|| true`, hidden
  mutation, and background work whose failure cannot be distinguished from a
  healthy no-op.
- Refer to optional tools by capability with an exact-source fallback. Keep
  transport names, launch commands, version mappings, and client differences in
  runtime adapters rather than durable skill contracts.
- Validate literal owner, `must_read`, test, and verification paths when a
  lightweight deterministic check can do so. Do not replace this with semantic
  drift heuristics or an exhaustive private schema.
- Keep permissive approval modes and write-enabled MCP posture out of tracked
  defaults. Apply least privilege and expose write authority explicitly.
- Do not route active work through resolved backlog, raw transcripts, archived
  guidance, or historical review documents.
- Add nested `AGENTS.md` files only after repeated ambiguity or a materially
  distinct verification contract demonstrates the need.
- Preserve one canonical client-neutral capability description where multiple
  clients are supported, but implement a manifest or doctor command only if a
  small design prevents real configuration drift. The principle does not
  justify another broad policy engine.

Retain from the autoresearch reports only the loop contract: a mission-owned
target function, bounded edit surface, cheap diagnostics before expensive
experiments, explicit metrics and artifacts, reproducibility controls, and a
keep/discard decision. Do not retain their dated recommendation of a particular
external engine or build an executor that duplicates OMX orchestration.

Reject or defer the expansion-heavy proposals: mandatory LitKG context packs,
automatic transcript ingestion, a generated agent brief, new pandas/Plotly
skills without demonstrated demand, a fixed Matt-skill allowlist, raw upstream
setup conventions, code-index retention periods, and generated client adapters.
Each may be reconsidered only as a small capability experiment against the
current baseline.

### July 11 simplification decision record

Source: `.omx/specs/aria-nbv-agent-scaffold-simplification-20260711/decision-record.md`
in the primary checkout.

Retain: one owner per meaning, thin root routing, `aria-nbv-context` as discovery
control rather than a project handbook, derived evidence as non-authoritative,
optional-tool failure isolation, operator-only UML, docstring/Quartodoc Python
entity ownership, contract-tiered documentation, selective package READMEs,
and direct-source literature verification.

Do not inherit automatically: categorical LitKG removal, exact Graphify corpus,
or fixed command and skill inventories. Those conclusions were later contested.

### July 14 simplification plan

Source: `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714.md`
in the primary checkout.

Retain: independent reach earns a skill, explicit behavior beats ambient hooks,
and deletion must be proven by owners and tests before removal.

Reject as a timeless target: an exact seven-to-nine skill count. Capability and
prompt measurements, not an arbitrary count, determine the compact portfolio.

### July 20 scaffold refresh plan

Source: `codex/agent-scaffold-refresh-v2` at
`.omx/plans/ralplan-aria-nbv-agent-scaffold-refresh-20260720.md`.

Retain: measured-autoresearch, Agents DB, current debrief policy, durable human
intent, privacy, exact-source fallback, and no tracked generated wiki.

Treat as superseded or unproven implementation hypotheses: an exact nine-skill
portfolio, one tracked graph, automatic source/graph commit pairs, a large OMX
lifecycle validator, broad external-skill closure enforcement, and simultaneous
LitKG/context/state retirement. The plan's retention of measured-autoresearch,
Agents DB, exact-source fallback, privacy, and no generated wiki remains current.

### July 26 scaffold issue index

Source:
`.agents/references/scaffold_rework/evidence/scaffold-issue-index-20260726.md`.

Preserve its observed improvements: compact ARIA skills, repaired `aria-docs`
progressive disclosure, mixed measured-autoresearch iterations, cleaner graph
hierarchy, native-shaped provenance, and local non-authoritative graph output.

Preserve its warnings: runtime prompt budgets omitted most visible skills;
routing tests measured lexical consistency rather than task outcomes; graph
link precision and scaffold/bibliography coverage were incomplete; custom
scaffold scripts grew despite headline LOC reduction; synchronous hooks and
mandatory debrief growth had unmeasured cost.

Also preserve its concrete failure candidates: vendored Graphify over-trigger,
an undocumented large tree artifact, custom adaptation growth before tests,
stale external-skill policy, copied-hook drift, transcript completeness gaps,
regressed source inspection, and live-looking references to retired systems.
These are hypotheses to reproduce against `main`, not licenses for bulk removal.

### July 26 five-PR rebuild proposal

Source:
`.agents/references/scaffold_rework/evidence/five-pr-rebuild-20260726.md`.

Retain: clean reconstruction from `main`, split ownership between intent,
memory, skills, Graphify, and integration, explicit retained/replaced/pruned
capability ledgers, and rollback boundaries.

Revise: do not mechanically execute its five PRs. The later PR #30 audit showed
that thesis salvage belongs in separate thesis PRs, Graphify and external-skill
policy require experiments first, and retirement must proceed one capability at
a time.

### July 28 PR #30 reviewability audit

Preserved evidence:
`.agents/references/scaffold_rework/evidence/pr30-reviewability-20260728.html`.
Original audited head:
`2b02a3bff7ac2fccffd8118b2790ec3f3803b6e5`.

The historical validator record is preserved in
`.agents/references/scaffold_rework/evidence/pr30-reviewability-result-20260728.json`,
but it does not cryptographically bind the preserved HTML copy. The audit
remains the strongest consolidated comparison of pre-PR, PR #30, and target
responsibilities. Its central verdict stands: PR #30 is an experimental
research branch, not a reviewable PR.

Observed working capabilities:

- Typst build, equation numbering, notation and prune audits;
- measured-autoresearch self-tests;
- exact Graphify query/path traversal and cleaner hierarchy visualization;
- compact behavior/docs routing;
- branch-aware source-link primitives.

Observed or material failures:

- 383 changed files with unrelated responsibility families;
- skill and documentation deletion without task-success parity;
- custom Graphify code growth and noisy broad retrieval;
- Graphify plan-to-implementation drift;
- an overbuilt OMX lifecycle engine;
- unresolved scientific citations and semantic-loss risks;
- stale generated PDF and lost state/thesis contracts;
- retirement claims unsupported by replacement evidence.

PR #30 remains an open draft as of this report. It must not be treated as the
new implementation baseline. At the live check on 2026-07-30 it still contained
383 changed files, +20,446/-20,486 lines, and a failing root CI check.

### Parent Codex task

The parent task contributes the strongest temporal preference evidence. Its
material sequence is:

- preserve information and capabilities before simplifying;
- prefer native/upstream implementations and progressive disclosure;
- centralize scientific truth in code, thesis, and exact papers;
- require Graphify to respect native hierarchy and link modalities, but later
  question whether Graphify was useful enough to justify its adaptation;
- reject PR #30 as overwhelming and explicitly allow partial adoption;
- replace one monster PR with small, self-contained PRs;
- build a reviewed owner-intent corpus, then reject trivial candidates and
  overengineered extraction machinery; and
- consolidate only important, generalizable, non-conflicting intent into the
  restart evidence.

Thus the earlier requests to include all candidates or make
`aria-nbv-context` contain all relevant project information are superseded by
the later requirements for selective distillation, context hygiene, single
ownership, and progressive disclosure. The July 20 fixed architecture is
evidence, not a standing command to reproduce its full target.

## Current Conflicts

Keep these open until their dedicated workpackage supplies evidence:

- exact Graphify corpus, refresh behavior, and retained outputs;
- whether a fresh Graphify graph is the default navigation route or an optional
  architecture aid used only after exact lookup becomes insufficient;
- whether LitKG still provides unique claim or retrieval value;
- whether `aria-nbv-context` is a pure router or contains compact stable
  orientation;
- exact external-skill reference, allowlist, pinning, or vendoring policy;
- which handwritten state surfaces can retire;
- whether debriefs remain required for every non-trivial task, as retained by
  the July 20 successor, or become event-triggered/episodic, as later cost and
  context concerns suggest;
- when Typst becomes the sole scientific owner rather than the target owner;
- the exact enforceable interpretation of the shared-glossary requirement for
  equation labels and definitions;
- minimum OMX registry and validator implementation. Current artifacts retain
  native OMX role paths and superseded bundles remain archived with successor
  provenance.

These earlier numeric targets are explicitly superseded as universal gates:
exactly nine ARIA skills, a fixed prompt-byte reduction, and a fixed graph-size
limit. They may be retained as historical baselines, but capability, runtime,
and maintenance evidence determines acceptance. Destructive migration still
stops on unresolved ownership, missing source/test coverage, stale material
evidence, unclassified artifacts, hidden semantic changes, or an unpaired
maintenance-cost regression.

## Clean Restart Sequence

Before implementation, freeze a small representative evaluator. It must cover:

- owner localization from code, docs, thesis, literature, and scaffold prompts;
- positive and near-miss skill activation;
- task completion with the current skill, candidate skill, and no-skill path;
- Graphify owner/path/hierarchy tasks, including code-symbol references from
  docs, thesis structure, bibliography/paper membership, stale graphs, and
  inferred-edge false links;
- exact-source fallback with optional tools absent; and
- human review cost: files changed, generated churn, custom LOC, diff size, and
  whether the result can be reviewed independently.

Record assertion-level evidence, repeated-run aggregates where stochastic
behavior matters, runtime/token cost when observable, and explicit telemetry
gaps. Do not optimize the evaluator after seeing only the candidate result.

### PR 1: Intent and authority alignment

Scope: `human_owner_intent.md`, `source_order.md`, and the smallest routing
references needed to remove contradictions. No skill deletion, Graphify,
thesis migration, or lifecycle engine.

Proof: authority examples resolve to one current owner; open choices remain
explicit.

### PR 2: Additive `aria-docs` routing

Scope: add or repair compact `aria-docs` routing while retaining old document
workflows until positive, negative, and task-outcome fixtures demonstrate
parity.

Proof: representative tasks succeed with the proposed route and do not
over-trigger on adjacent tasks.

Retain `measured-autoresearch` unchanged. Give it a separate PR only when a
demonstrated evaluator or iteration-mode gap requires modification.

### PR 3: Runtime scaffold measurement

Scope: measure complete prompt-visible skill descriptions, startup context,
real activation, and representative task outcomes. Prefer test fixtures and
existing Codex diagnostics over a policy engine.

Proof: fixed baseline and candidate measurements with no-skill or prior-skill
comparison.

### Experiment 4: Upstream Graphify usefulness

Scope: compare exact search, plain upstream Graphify, the main integration, and
PR #30's adapter on fixed owner, path, hierarchy, thesis, literature, and stale
graph tasks. Do not merge adaptation code during the experiment.

Proof: owner-at-top-k, locator/path correctness, false links, nodes inspected,
runtime, context cost, and custom LOC.

### PR 5+: One retirement at a time

Retire one redundant skill, context surface, state journal, or LitKG route only
after its own capability ledger and replacement proof are green. Keep each
retirement independently reversible.

### Separate thesis PRs

Salvage centered numbered equations using native Typst math, shared notation and
glossary coverage, branch-aware code/source links, draft markers, development
build profiles, and visible prune evidence as separate thesis changes. The
proposed folding of Quarto questions/roadmap material into Typst is a separate
semantic migration and requires statement-by-statement ownership review. Do not
use scaffold cleanup to justify Quarto deletion or generated PDF churn.

### Separate OMX design

Start from the requirement: preserve accepted evidence and explicit
supersession. Test whether existing Git history plus a compact manifest/hash
check is sufficient before adding lifecycle machinery.

## Review Contract

Every replacement PR must satisfy:

- one purpose reflected by title, body, diff, and tests;
- one owner for every moved fact;
- one comparative evidence bundle for the claimed improvement;
- explicit retained, replaced, removed, and deferred capabilities;
- no generated or binary churn unless it is the deliverable;
- exact-head hosted CI and reviewable commit history;
- rollback without depending on later PRs.

Permanent automation is admitted only for a stable, recurring, objectively
testable invariant. Every new validator or hook needs an owner, a concrete
failure mode, a useful remediation message, a positive fixture, a negative
fixture, and evidence that it does not block the valid baseline. A validator
larger or harder to maintain than the capability it protects is a design
failure unless its comparative benefit is demonstrated.

## Candidate Disposition Summary

Retain now:

- thin scoped guidance, exact-source owners, progressive disclosure, privacy,
  measured-autoresearch, Agents DB, docstrings/Quartodoc, selective READMEs,
  direct-source literature checks, optional-tool fallback, and small PRs;
- PR #30's observed useful capabilities only as salvage candidates: Typst
  equation/notation/prune checks, source-link primitives, native Graphify
  traversal/hierarchy, and repaired docs routing; and
- native OMX role paths with explicit supersession evidence, without assuming a
  registry engine is needed.

Reject now:

- PR #30 as a merge or replay unit;
- a comprehensive context skill, tracked generated wiki/graph as truth, global
  generated inventories, custom Graphify replacement, broad synchronous hooks,
  lexical-only routing tests, or automatic intent acceptance;
- arbitrary skill/LOC/byte targets used without capability evidence; and
- bulk deletion based only on apparent redundancy.

Defer to evidence:

- Graphify corpus, refresh, hooks, outputs, and adapter;
- LitKG and state-journal retirement;
- external-skill allowlisting/pinning/vendoring;
- exact debrief trigger policy and minimal OMX lifecycle machinery; and
- any generated cross-modal/NLP layer beyond upstream Graphify behavior.

Keep outside this scaffold series:

- thesis semantic consolidation, notation/equation formatting, Quarto removal,
  model/package refactors, runtime training APIs, and scientific claim changes.
- code or chat TODOs do not automatically become debrief prose. Existing source
  TODOs stay with their source owner; actionable cross-cutting findings go to
  Agents DB after review; historical failed approaches may remain in debriefs.

## Recommended First Action

Review and merge only the intent/authority report branch. Then open PR 2 as an
additive capability-preservation change. Do not begin Graphify, LitKG, state,
or broad skill retirement until the runtime measurement workpackage has a
frozen evaluator.
