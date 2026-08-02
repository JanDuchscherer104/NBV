# PRD: Thin Root/Nested AGENTS Rewrite

Status: Consensus approved

Date: 2026-08-01

Requirements owner: `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`

Companion test plan: `.omx/plans/test-spec-thin-root-nested-agents-rewrite.md`

Final Architect review: `.omx/plans/thin-root-nested-agents-rewrite-architect-review.md`

Final Critic review: `.omx/plans/thin-root-nested-agents-rewrite-critic-review.md`

## Outcome

Produce one coherent root-to-leaf instruction hierarchy in which root guidance is
a compact dispatcher and every current nested `AGENTS.md` remains as a thinner
nearest-owner guide. Preserve safety, source authority, local hazards, routing,
capture, optional-tool fallback, stable identifiers, and validation outcomes.

Implementation proceeds through vertical claim slices: establish the destination
owner, update consumers, prove the candidate, and only then remove the source
copy. Internal commits may isolate slices, but the merge boundary must expose a
complete, coherent hierarchy.

## Requirements Summary

1. Root `AGENTS.md` retains only repository-wide safety, source-order and
   nearest-guide pointers, compact routing/capture, optional-tool evidence and
   exact-source fallback, and minimal verification/debrief rules
   (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:394-415`).
2. Retain and thin all current nested guides: `aria_nbv/AGENTS.md`, the four
   module guides under `aria_nbv/aria_nbv/**/AGENTS.md`, and `docs/AGENTS.md`.
   File deletion is deferred to a separate change with consumer and repeated-
   ambiguity evidence.
3. “Root plus nearest guide is sufficient” means sufficient to identify the
   exact owner, local hazard, local validation, and relevant procedural route.
   The pair does not copy the full procedure, implementation, or scientific fact.
4. Procedures stay in skills; implementation truth stays in code/tests/config;
   thesis/public truth stays in Typst/Quarto/bibliography; current state and human
   preferences stay in their existing owners. The owner ladder is
   `.agents/references/source_order.md:5-61` and capture rule is lines `69-84`.
5. Preserve optional Graphify, MemPalace, OMX, MCP, and autoresearch boundaries.
   Exact-source work remains usable without them. Do not edit the byte-identical
   upstream Graphify skill.
6. Before guidance edits, convert G002/routing evidence to candidate-independent
   owner/outcome assertions and prove that the old integrated scaffold passes.
7. Permanent CI remains deterministic. Native/model trials are disposable
   baseline/candidate evidence, not a new checked-in evaluator, dashboard, trace
   corpus, or CI dependency.
8. Destructive work on overlapping root/MemPalace/source-order/fixture/G002 paths
   requires an immutable integrated commit. A bounded dirty diff is insufficient.
9. Permanent validators protect only stable, objective recurring failures with
   positive and negative fixtures. Unrelated skill line-budget, semantic-drift,
   or warning cleanup is out of scope unless it directly blocks this candidate.
10. No acceptance target uses arbitrary line counts, aggregate bytes/LOC, exact
    prose, or exact identifiers except a proven stable compatibility interface.

## Scope

### Guidance and direct consumers

- `AGENTS.md`
- `aria_nbv/AGENTS.md`
- `aria_nbv/aria_nbv/data_handling/AGENTS.md`
- `aria_nbv/aria_nbv/rollouts/AGENTS.md`
- `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`
- `aria_nbv/aria_nbv/vin/AGENTS.md`
- `docs/AGENTS.md`
- `.agents/references/source_order.md` only where the integrated owner ladder or
  capture pointer must change to support a vertical claim slice
- `scripts/scaffold/fixtures/routing.json`
- `scripts/tests/test_agent_governance_g002.py`
- `scripts/scaffold_audit.py`, including its inline self-tests, only for rules
  directly affected by candidate-independent fixture conversion
- One rewrite closeout debrief under `.agents/memory/history/YYYY/MM/`, distinct
  from concurrent baseline debriefs already integrated before this rewrite

### Exclusions

- No nested `AGENTS.md` deletion.
- No domain-skill rename, merge, deletion, or unrelated edit.
- No `.agents/skills/graphify/**` edit or upstream-pin change.
- No MemPalace corpus/runtime redesign; preserve the integrated policy and route
  operational detail to its accepted owner.
- No package behavior, scientific contract, thesis claim, API, generated docs,
  Graphify projection, OMX lifecycle, or external-tool configuration change.
- No new checked-in native/model-evaluation runner by default.
- No cleanup of pre-existing scaffold warnings, line budgets, semantic-drift
  warnings, or fixture debt unless it prevents the candidate from passing an
  already justified gate.
- `scripts/tests/test_scaffold_audit.py` is not a touchpoint; scaffold self-tests
  live inline in `scripts/scaffold_audit.py:770-951`.

## RALPLAN-DR (Short Mode)

### Principles

1. A dispatcher points; the nearest owner defines.
2. Complete each claim slice destination-first and remove source text last.
3. Preserve observable outcomes before reducing guidance.
4. Keep permanent enforcement deterministic and smaller than the protected rule.
5. Expose only a coherent hierarchy as the merge boundary.

### Top Drivers

1. Avoid capability loss or overwrite across active MemPalace/root/test changes.
2. Reduce always-loaded duplication without hiding local hazards or procedures.
3. Replace lexical confidence with candidate-independent deterministic checks and
   bounded native outcome evidence.

### Options

#### Option A — Atomic file-batch rewrite

Rewrite root, nested guides, fixtures, and tests together.

Pros: one immediately coherent diff; no temporary internal duplication.

Cons: file-led, hard to attribute or roll back, and unsafe across overlapping
concurrent paths.

#### Option B — Vertical claim slices on one integration branch (recommended)

Freeze an immutable integrated baseline and candidate-independent evaluator, then
complete each claim family destination → consumers → proof → source removal.
Allow internal slice commits but merge only the complete hierarchy.

Pros: decision-lossless, auditable, rollback-friendly, and compatible with
composed Codex instructions.

Cons: serial integrator is a throughput constraint; temporary internal
duplication remains until each slice closes.

#### Option C — Root-only thinning

Thin root and leave nested content/tests unchanged.

Pros: smallest immediate edit.

Cons: does not satisfy the nearest-owner rewrite, retains duplication, and can
leave destinations implicit.

### Recommendation

Choose Option B. It synthesizes atomic coherence with small rollback boundaries:
vertical slices are reviewable internally, while only the completed hierarchy is
eligible to merge.

## Ephemeral Claim Ledger

Keep the ledger untracked in the execution session/PR working notes or an
execution-owned OMX evidence artifact. It is migration evidence, not a new truth
owner.

Group rows by claim family. A family row may cover claims sharing the same owner,
consumer set, disposition, and proof. Expand to individual rows whenever any of
those fields differs. Every deleted, relocated, or replaced claim requires an
individual row.

Required fields:

| Field | Requirement |
| --- | --- |
| Family / claim ID | Stable within this execution |
| Integrated source locator | Exact path/line on immutable baseline commit |
| Outcome | Observable behavior protected |
| Destination owner | One existing canonical owner |
| Consumers | Every live pointer, guide, test, or operator path |
| Disposition | retained, relocated, replaced, removed, deferred, unresolved |
| Candidate locator | Required for relocated/replaced claims |
| Deterministic proof | Static/test command and expected behavior |
| Native proof | Scenario/rubric criterion when judgment is required |

Dispositions:

- **retained:** stays in place because it is universal or materially local.
- **relocated:** same claim moves to a smaller existing owner; consumers update
  before source removal.
- **replaced:** another instruction/mechanism preserves the outcome; candidate-
  independent proof must pass first.
- **removed:** redundant/stale content with verified no-consumer evidence.
- **deferred:** valid later cleanup; current behavior stays intact.
- **unresolved:** owner, consumer, or proof is missing; destructive work is
  prohibited.

No destructive claim may merge as deferred or unresolved; leave its source text
untouched and report it.

## Stable-Identifier Exceptions

Exact identifiers are retained/tested only where an accepted owner and live
consumer prove compatibility:

| Identifier | Owner and consumer evidence | Required treatment |
| --- | --- | --- |
| `python-standards` | Accepted target state lines `44-47`; package guidance at `aria_nbv/AGENTS.md:63-67`; repository skills consume the route | Preserve the name and sole Python-contract-owner role |
| Eight-symbol `aria_nbv.rollouts.__all__` | `aria_nbv/aria_nbv/rollouts/__init__.py:24-32`; enforced by `aria_nbv/tests/rollouts/test_public_rollouts_api.py:35-50`; local hazard at `rollouts/AGENTS.md:47-49` | Retain the local compatibility warning; wording may change but exact API remains |
| Upstream Graphify skill identity/content | Accepted target state lines `97-105`; verified by `make graphify-skill-upstream-self-test` | Do not edit; retain explicit upstream-integrity proof |

Any additional exception must satisfy the same owner + live consumer +
compatibility-change test and be added to this table before implementation.

## Ordered Work Packages

### WP0 — Immutable integrated baseline

1. Wait for active MemPalace/domain-skill work to integrate.
2. Record an immutable commit SHA containing the authoritative versions of
   `AGENTS.md`, `source_order.md`, `human_owner_intent.md`, `aria-nbv-context`,
   routing fixtures, G002, and any concurrent baseline debrief(s). These are
   baseline inputs, not the rewrite closeout debrief.
3. Require overlapping paths to match that commit before destructive work. The
   worktree may contain unrelated dirty files, but no overlapping dirty patch may
   be used as a deletion/relocation baseline.
4. Refresh line anchors, consumers, status, and the grouped claim ledger from
   that SHA. Never use restoration/reset to manufacture the baseline.

Exit: immutable integrated SHA recorded; overlapping paths clean relative to it;
unrelated dirty paths inventoried and preserved.

### WP1 — Candidate-independent evaluator conversion

Complete before any guidance edit.

1. Convert G002 and routing fixtures from candidate prose/layout assertions to
   deterministic owner/outcome/interface assertions.
2. Preserve only justified stable identifiers from the exception table.
3. Keep `scaffold_audit.py` changes limited to schema/integrity behavior required
   by the conversion; do not clean unrelated warnings or semantic-drift rules.
4. Add positive/negative fixtures for each changed deterministic rule.
5. Prove the converted suite passes the old scaffold at the immutable baseline.
6. Create the untracked disposable `prompt-set-v1` artifact defined by the test
   spec, with six literal prompts and boolean rubrics; default to no checked-in
   runner or corpus.

Exit: old scaffold passes converted deterministic tests and one native baseline
trial per scenario; evaluator definitions are frozen before candidate guidance.

### WP2 — Vertical claim slices

S1-S6 are the shared final regression corpus; each destructive slice may add only
the smaller slice-local comparison required by its expanded claim rows.

The serial integrator completes each family in this order: destination owner,
consumers, pre-removal intermediate proof, source removal, then repeated
post-removal proof. Pre-removal proof validates only the destination and updated
consumers; it cannot close or merge a slice. Only the post-removal pass closes it.

#### Slice A — Source authority and nearest-guide discovery

- Destination: `source_order.md` plus materially local nested guide pointers.
- Consumers: root dispatcher, package/docs routing, evaluator assertions.
- Proof: owner-discovery and exact-source fallback scenarios.
- Removal: duplicate source-order/thesis-owner prose from root/nested files only
  after candidate proof.

#### Slice B — Universal safety and capture

- Destination: root for universal dirty-tree/safety pointers;
  `agent-behavior`/capture owners for procedure detail.
- Consumers: root capture pointer and governance checks.
- Proof: dirty-tree and instruction-capture scenarios.
- Removal: detailed exclusions/procedures duplicated in root only after proof.

#### Slice C — Optional-tool evidence and MemPalace/Graphify boundaries

- Destination: integrated `human_owner_intent.md`, `source_order.md`, and
  `aria-nbv-context`; root retains only optionality, evidence status, and fallback.
- Consumers: root pointer, routing fixtures, G002.
- Proof: optional-tools-unavailable and semantic-recall/direct-source outcomes;
  Graphify upstream self-test.
- Removal: corpus topology, client mechanics, and setup detail from root only
  after integrated owner and consumers pass.

#### Slice D — Package/module local hazards

- Destination: all current package/module guides, each thinned but retained.
- Consumers: package/module task routing and targeted validation.
- Proof: nearest-guide package scenarios plus stable API tests where applicable.
- Removal: dynamic file inventories, historical links, and duplicated generic
  procedure only after local owner/proof is explicit. Preserve the rollout
  eight-symbol compatibility rule.

#### Slice E — Docs local hazards and procedure routing

- Destination: retained `docs/AGENTS.md` for docs authority/hazards/validation;
  existing authoring skills/references for full procedures.
- Consumers: root docs pointer and docs scenario.
- Proof: advisor-facing Typst owner/citation/render scenario.
- Removal: copied command catalogs and Mermaid/Typst procedure detail only after
  the relevant route is verified.

Exit per slice: all destructive rows settled; destination and consumers pass the
intermediate proof; source copy is removed; the same proof is repeated and passes
post-removal. Only that post-removal pass closes the slice. A slice with any
safety/authority candidate failure remains open.

### WP3 — Coherent integration and closeout

1. Integrate all closed slices and ensure every current nested guide remains.
2. Run candidate native trials with the frozen prompts/rubric and minimal retry
   rule from the test spec.
3. Run deterministic final gates, including Graphify upstream integrity.
4. Compare pre/post dirty paths and enumerate rewrite-owned changes.
5. Close the ledger and write the one rewrite closeout debrief, distinct from
   concurrent baseline debrief(s), with deferred untouched claims.
6. Expose only the full coherent hierarchy to independent review/merge.

Stop: all acceptance criteria pass at exact candidate commit, destructive rows
are closed, and unrelated/concurrent work is preserved.

## Acceptance Criteria

1. WP0 records an immutable integrated commit; every overlapping destructive edit
   is derived from paths clean relative to that commit.
2. The assertion-disposition table in the test spec is implemented exactly; its
   positive/negative probes pass, and the independent `test-engineer` confirms
   the converted deterministic suite passes the old scaffold before any guidance
   edit. Executor self-assessment cannot satisfy this gate.
3. Permanent CI uses deterministic repository tests only; no native/model runner,
   trace corpus, network service, optional plugin, or disposable session is a CI
   dependency.
4. Every destructive claim has an expanded ledger row and completes destination
   → consumers → pre-removal intermediate proof → source removal → repeated
   post-removal proof; only the final pass closes the slice.
5. Root contains only universal dispatcher categories; every current nested
   `AGENTS.md` remains and contains a materially local owner, hazard, validation,
   and procedural route where needed.
6. Root plus the nearest guide identifies the exact owner, local hazard, local
   validation, and procedural route without copying the full procedure.
7. `python-standards`, the exact rollout eight-symbol API boundary, and upstream
   Graphify integrity remain protected as stable interfaces.
8. Optional tools remain non-authoritative and non-mandatory; exact-source work
   passes with Graphify/MemPalace/OMX/MCP unavailable.
9. The independent `test-engineer`, not the executor, grades the first baseline
   and candidate run and mandates exactly two additional runs for both sides only
   on rubric failure or executor-record/grader disagreement. The executor cannot
   trigger, waive, stop, or reinterpret retries. Any candidate safety/authority
   failure blocks regardless of retries.
10. The independent grader records candidate success for every boolean row in
    the untracked literal `prompt-set-v1` artifact, with exact client, model,
    reasoning, sandbox/approval, config, commit, prompt version, required
    locators/commands, and forbidden outcomes. Executor self-grading is evidence
    only and cannot satisfy acceptance.
11. `make scaffold-audit`, `make scaffold-audit-self-test`,
    `make graphify-skill-upstream-self-test`, `make check-agent-memory`, and
    `git diff --check` exit 0. Direct G002 is run only as a focused diagnostic
    because `make scaffold-audit-self-test` already includes it.
12. No unrelated skill warning/line-budget/semantic-drift cleanup, generated
    artifacts, package behavior, thesis content, or upstream Graphify content is
    included.
13. Dirty-tree comparison proves pre-existing unrelated paths were preserved and
    not counted as rewrite progress.
14. S1-S5 use read-only disposable worktrees. S6 alone uses matched disposable
    `workspace-write` fixtures with approval `never`, exact assigned guide
    `aria_nbv/aria_nbv/vin/AGENTS.md`, identical tracked/untracked unrelated
    sentinels, and an external pre/post status/hash/content plus `diff --check`
    oracle. Mutation outside the guide/evidence boundary, sentinel change/removal,
    or nonzero patch-hygiene result fails.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Concurrent overlap becomes the deletion baseline | Require immutable integrated SHA and clean overlapping paths |
| File-batch rewrite removes a source before its replacement works | Vertical claim slices; destination and consumers precede proof and removal |
| Evaluator favors candidate wording | Convert and pass old scaffold before edits; freeze prompts/rubric |
| Model trials become permanent nondeterministic CI | Disposable native sessions only; deterministic CI remains authoritative |
| One lucky/unlucky trial distorts result | One each by default; exactly two more on failure/disagreement; retain individual outcomes |
| Safety/authority regression is averaged away | Any candidate failure in those criteria blocks |
| S6 cannot prove preservation under a read-only sandbox | Run S6 only in matched disposable writable fixtures and compare externally captured status, hashes, and contents |
| Executor self-grades or chooses retries opportunistically | Independent `test-engineer` applies frozen rubric; verifier audits disagreements and retry rule |
| Stable API/name is lost during prose cleanup | Explicit exception table with owner and live-consumer evidence |
| Parallel workers conflict on shared policy | Serial integrator owns root/shared/MemPalace/test paths; parallelize only disjoint leaf guides |
| Scope absorbs pre-existing warning debt | Explicit exclusion; change only a rule that directly blocks converted evaluator/candidate |
| Internal slices leave inconsistent guidance | Merge boundary is the fully integrated coherent hierarchy |

## Verification

Baseline and final deterministic gates:

```text
git status --short
git diff --name-only
make scaffold-audit
make scaffold-audit-self-test
make graphify-skill-upstream-self-test
make check-agent-memory
git diff --check
```

The companion test spec defines read-only S1-S5 trials, the controlled writable
S6 fixture and external preservation oracle, exact invocation records,
independent rubric grading, retries, negative fixtures, and dirty-tree checks.

## ADR

### Decision

Use vertical claim slices on one branch after an immutable integrated baseline
and candidate-independent evaluator conversion. Keep native trials disposable,
CI deterministic, and the merge boundary atomic/coherent.

### Drivers

1. Active overlap makes dirty-diff deletion unsafe.
2. Codex consumes root and nested instructions as a composed interface.
3. Capability preservation needs evidence independent of candidate wording.

### Alternatives Considered

- Atomic file-batch rewrite: coherent but unsafe and hard to attribute.
- Root-only thinning: bounded but incomplete.

### Why Chosen

Vertical slices preserve the Architect's strongest atomic-coherence argument at
merge time while retaining claim-level proof and rollback during implementation.

### Consequences

- Shared-path work is serial and may take longer.
- Native trials remain review evidence rather than permanent tests.
- All nested guides remain; later deletion requires a separate decision.
- Temporary internal duplication is allowed until a slice closes.

### Follow-ups

- Consider nested-guide deletion only in a separate evidence-backed change.
- Address unrelated scaffold warning debt separately.
- If native trials reveal a distinct routing failure, isolate it as its own
  follow-up rather than widening this rewrite.

## Available Agent Types and Staffing

Relevant installed types: `explore`, `executor`, `writer`, `test-engineer`,
`verifier`, `code-reviewer`, `git-master`, `architect`, and `critic`. `worker` is
reserved for active Team runtime.

| Lane | Type | Reasoning | Ownership |
| --- | --- | --- | --- |
| Serial integrator | `executor` | medium | Root, source order, MemPalace overlaps, shared fixtures/G002, slice integration |
| Consumer inventory | `explore` | low | Read-only claim/consumer mapping |
| Leaf guide thinning | `writer` or `executor` | writer high; executor medium | One disjoint retained leaf guide per lane after WP1 |
| Native trial executor | `executor` | medium | Runs frozen prompts and records raw execution evidence; does not grade or choose retries |
| Independent rubric grader | `test-engineer` | medium | Grades executor records against frozen booleans, declares failure/disagreement and required retries |
| Final evidence | `verifier` | high | Audits grader independence/retries, S6 external oracle, exact-commit gates, ledger closure |
| Independent review | `code-reviewer` | high | Capability/ownership/scope regression |
| Integration history | `git-master` | high | Bounded internal commits and coherent merge boundary without broad staging |
| Consensus gate | `architect`, then `critic` | architect xhigh; critic high | Sequential architecture and execution-readiness approval |

Parallelism is limited to disjoint leaf guides after WP0 and WP1. Root,
`source_order.md`, `human_owner_intent.md`, `aria-nbv-context`, routing fixtures,
G002, and integration are never split across concurrent lanes.

## Goal-Mode Follow-up Suggestions

- **`$ultragoal` (recommended):** durable sequential checkpoints for WP0, WP1,
  vertical slices, and final verification.
- **`$team` + `$ultragoal`:** optional only for disjoint leaf-guide thinning;
  Ultragoal/serial integrator retains shared-path ownership.
- **`$autoresearch-goal`:** not applicable; official research is complete.
- **`$performance-goal`:** not applicable; size/LOC is not the evaluator.

## Team Launch Hint and Verification Path

After WP0/WP1:

```text
$team 3 "Thin only assigned disjoint leaf AGENTS guides under .omx/plans/prd-thin-root-nested-agents-rewrite.md; do not edit root, source-order, MemPalace/context skill, shared fixtures, G002, or integration paths."
```

The serial integrator assigns one retained leaf guide per worker, integrates
vertical slices, and runs shared tests. Each worker returns its claim rows,
changed paths, and targeted proof. The verifier then checks the exact candidate
commit, independent grader records, S6 external preservation evidence,
deterministic gates, stable identifiers, and dirty-tree preservation before Team
shutdown and Ultragoal checkpointing.

## Ralph Fallback

`$ralph` is an explicit single-owner fallback only. If selected, provide both
plan paths, immutable-baseline/evaluator gates, vertical-slice order, and exact
stop conditions. `$ultragoal` remains the durable default.

## Consensus Changelog

- Initial Planner draft (2026-08-01): claim-led thin-root/nested plan.
- Architect iteration 1 applied (2026-08-01): replaced file batches with vertical
  claim slices; required immutable integrated commit; froze candidate-independent
  evaluator before edits; defined disposable native trials and retries; retained
  all nested guides; added stable-interface table and Graphify gate; narrowed
  parallelism to leaf guides; removed nonexistent touchpoint and duplicate G002
  final gate; excluded unrelated warning cleanup.
- Architect iteration 2 applied (2026-08-01): added matched writable S6 fixtures,
  tracked/untracked sentinels and external preservation oracle; kept S1-S5
  read-only; scoped environment equality per scenario pair; assigned independent
  `test-engineer` grading and verifier-audited, non-executor retry decisions.
- Critic iteration 1 applied (2026-08-01): added bounded assertion dispositions
  and literal untracked `prompt-set-v1`; corrected evidence-directory/fixture
  setup, debrief lifecycle, review metadata, role reasoning defaults, and
  pre/post-removal proof closure; removed executor discretion from acceptance.
- Final Critic approval improvements applied (2026-08-01): captured S6
  `diff --check`, clarified shared S1-S6 versus claim-tied slice-local evidence,
  and linked the final approving Critic review.
