---
kind: spec
status: current
---

# ARIA-NBV Agent Scaffold Rework: Consolidated Evidence

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

> One purpose, one owner, and one executable proof per pull request.

This report is decision evidence. Current code, tests, configuration,
`human_owner_intent.md`, `source_order.md`, the active thesis, and exact papers
remain authoritative for their own claims.

## Durable Invariants

- Keep default context small and load detail only when needed.
- Give every durable meaning one authoritative owner.
- Keep root guidance thin and place contracts beside their nearest owner.
- Prefer upstream behavior; retain only minimal adapters for measured gaps.
- Treat graphs, retrieval, plans, debriefs, and agent output as evidence, never
  automatic truth.
- Preserve source, freshness/worktree, ambiguity, and extracted/inferred
  provenance for derived evidence.
- Keep optional tools optional: exact-source repository work must remain
  possible without OMX, Graphify, MemPalace, or LitKG.
- Keep scientific/domain knowledge in code, tests, the active thesis, and exact
  papers rather than skills.
- Preserve privacy: raw transcripts, runtime identifiers, machine paths,
  credentials, and private retrieval corpora remain untracked.
- Prefer small owner-scoped PRs and explicit capability dispositions over
  all-at-once migration.
- Require fresh executable verification before claiming completion.
- Retire an owner only after its facts and consumers have verified destinations.
- Keep accepted plans immutable and supersede them explicitly.

## Goals

The target scaffold should:

- route an agent quickly to the exact owning source;
- expose detail progressively instead of loading a project handbook;
- preserve independently useful ARIA workflows without mirroring domain truth;
- measure the complete prompt-visible skill surface, not a convenient subset;
- evaluate routing and skills using realistic task outcomes and negative cases;
- use Graphify only where it improves owner or relationship discovery over
  exact search at acceptable context and maintenance cost;
- retain `measured-autoresearch` for research-only, evaluator-design, measured
  implementation, and keep-or-discard iterations;
- retain Agents DB as the actionable-work owner for now;
- keep debriefs episodic and useful rather than a current-state mirror;
- keep generated navigation local, reproducible, and non-authoritative;
- reduce custom scaffold implementation without deleting unique capabilities.

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

## Historical Evidence Ledger

### July 11 simplification decision record

Source: `codex/scaffold-distill-upstream-graphify` at
`.omx/archive/accepted-bundles/aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f/specs/aria-nbv-agent-scaffold-simplification-20260711/decision-record.md`.

Retain: one owner per meaning, thin root routing, `aria-nbv-context` as discovery
control rather than a project handbook, derived evidence as non-authoritative,
and optional-tool failure isolation.

Do not inherit automatically: categorical LitKG removal, exact Graphify corpus,
or fixed command and skill inventories. Those conclusions were later contested.

### July 14 simplification plan

Source: the same accepted bundle at
`plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714.md`.

Retain: independent reach earns a skill, explicit behavior beats ambient hooks,
and deletion must be proven by owners and tests before removal.

Reject as a timeless target: an exact seven-to-nine skill count. Capability and
prompt measurements, not an arbitrary count, determine the compact portfolio.

### July 20 scaffold refresh plan

Source: `codex/agent-scaffold-refresh-v2` at
`.omx/plans/ralplan-aria-nbv-agent-scaffold-refresh-20260720.md`.

Retain: measured-autoresearch, Agents DB, current debrief policy, durable human
intent, privacy, exact-source fallback, and no tracked generated wiki.

Treat as disproven implementation hypotheses: one tracked graph, automatic
source/graph commit pairs, a large OMX lifecycle validator, broad external-skill
closure enforcement, and simultaneous LitKG/context/state retirement.

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
new implementation baseline.

## Current Conflicts

Keep these open until their dedicated workpackage supplies evidence:

- exact Graphify corpus, refresh behavior, and retained outputs;
- whether LitKG still provides unique claim or retrieval value;
- whether `aria-nbv-context` is a pure router or contains compact stable
  orientation;
- exact external-skill reference, allowlist, pinning, or vendoring policy;
- which handwritten state surfaces can retire;
- when Typst becomes the sole scientific owner rather than the target owner;
- minimum OMX registry and validator implementation. Current artifacts retain
  native OMX role paths and superseded bundles remain archived with successor
  provenance.

## Clean Restart Sequence

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

Salvage numbered equations, source links, and visible prune markers as separate
thesis changes. Do not use scaffold cleanup to justify thesis semantic changes,
Quarto deletion, or generated PDF churn.

### Separate OMX design

Start from the requirement: preserve accepted evidence and explicit
supersession. Test whether existing Git history plus a compact manifest/hash
check is sufficient before adding lifecycle machinery.

## Review Contract

Every replacement PR must satisfy:

- one purpose reflected by title, body, diff, and tests;
- one owner for every moved fact;
- one executable proof for the claimed improvement;
- explicit retained, replaced, removed, and deferred capabilities;
- no generated or binary churn unless it is the deliverable;
- exact-head hosted CI and reviewable commit history;
- rollback without depending on later PRs.

## Recommended First Action

Review and merge only the intent/authority report branch. Then open PR 2 as an
additive capability-preservation change. Do not begin Graphify, LitKG, state,
or broad skill retirement until the runtime measurement workpackage has a
frozen evaluator.
