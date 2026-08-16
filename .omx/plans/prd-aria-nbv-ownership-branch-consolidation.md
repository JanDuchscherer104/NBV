---
kind: plan
status: accepted
---

# PRD: ARIA-NBV Ownership and Branch Consolidation

**Status:** consensus-approved plan; execution is gated by S0

**Planning date:** 2026-08-14

**Execution owner:** root leader/orchestrator

**Recommended execution mode:** `$ultragoal` for durable checkpoints plus `$team` for owner-disjoint waves

**Current checkout policy:** read-only for execution; preserve its existing dirty state

## 1. Outcome

### Human-approved review reconciliation (2026-08-16)

Human review explicitly approves one intentional PR (#59) for this ownership
consolidation. Focused commits remain rollback boundaries; the follow-up
transcript-access work is excluded from this PR. The active RQ owner uses six
tiered questions: RQ1--RQ4 are the evaluated core, RQ5 is a conditional online
bridge, and RQ6 is a lower-priority continuous/simulator escalation. This
supersedes the earlier four-question extraction scope without copying its
unreviewed QMD roadmap material into the active owner.

Consolidate scientific and implementation authority without replaying stale pull
request stacks:

- the active Typst include graph rooted at
  `docs/typst/thesis/main.typ` owns ARIA-NBV theory, the exact research
  questions, scientific definitions, hypotheses, method narrative,
  interpretation, and claims;
- Python source, configuration, types, and concise contract-focused docstrings
  own implementation behavior and implementation details; tests prove those
  contracts;
- Quarto retains only role-disjoint public material: generated API reference,
  setup and command entry points, literature source dossiers, external
  background, and navigation that does not restate ARIA-NBV theory or Python
  contracts;
- the entire `.agents/memory/state/` current-truth layer is retired. Valid unique
  content from `PROJECT_STATE.md`, `DECISIONS.md`, `GOTCHAS.md`, and
  `OPEN_QUESTIONS.md` moves to its canonical Typst, Python/docstring/test,
  configuration/setup, or agent-guidance owner before all four files are
  deleted; the agents DB may track work by pointer but does not inherit their
  narrative content;
- `.omx/**` records coordination, decisions, receipts, and verification only. It
  never becomes a scientific or implementation truth owner;
- open branches and pull requests are reconciled against the new owner map after
  the ownership migration, rather than merged because their CI is green.

This is a two-stage program. Stage A classifies branches and PRs and freezes a
safe baseline. Stage B performs the ownership migration in isolated worktrees,
then re-evaluates salvageable branch content against the consolidated baseline.

## 2. Requirements Summary

### 2.1 Authority requirements

1. Keep the current Typst thesis as the only owner of thesis-facing theory. The
   active root and include chain are visible at
   `docs/typst/thesis/main.typ:72-82`.
2. Extract the four current RQs from
   `docs/typst/thesis/sections/01-introduction.typ:15-25` into
   `docs/typst/thesis/sections/01-research-questions.typ`, then include that file
   from the introduction at the same narrative position. Do not import obsolete
   QMD RQ5/RQ6 material as active questions.
3. Absorb and then delete these three QMDs atomically after destination proof:
   - `docs/contents/thesis/questions.qmd` ->
     `docs/typst/thesis/sections/01-research-questions.typ`;
   - `docs/contents/thesis/roadmap.qmd` ->
     `docs/typst/thesis/development/roadmap.typ`;
   - `docs/contents/thesis/m1_contract_report.qmd` ->
     `docs/typst/thesis/development/m1-contract-report.typ`.
4. Rewrite, do not transliterate, the roadmap and M1 report. They may contain
   development status, evidence pointers, gates, and concise promotion entries;
   they must not duplicate scientific theory or Python-owned contracts.
5. Update `.agents/references/source_order.md` so its role split links directly
   to the three new `.typ` files and no longer assigns current direction to the
   deleted QMDs. The conflicting current text is at
   `.agents/references/source_order.md:7-24`.
6. Keep literature reviews as exhaustive source dossiers. Typst owns the
   selected synthesis and all current ARIA-NBV scientific claims.
7. Classify every `docs/contents/theory/*.qmd` page as `keep`, `thin`, or
   `delete`:
   - `keep` only for cited external background, evidence, or examples without
     normative ARIA-NBV theory or implementation contracts;
   - `thin` when a stable URL or navigation role remains useful;
   - `delete` when no unique role-disjoint content remains.
   The RRI and RL theory pages are expected to be `thin` or `delete` after
   verified Typst promotion, not preserved by default.
8. Reduce handwritten implementation documentation to minimal setup and command
   entry points. Generated API reference must derive from Python and docstrings;
   the existing generation targets are at `Makefile:666-685`.
9. Absorb and delete all four `.agents/memory/state/*.md` files after a complete
   paragraph/bullet-level disposition pass:
   - `PROJECT_STATE.md` currently mixes the core claim, thesis direction,
     implementation status, priorities, blockers, and stale QMD pointers
     (`:12-74`);
   - `DECISIONS.md` contains repo workflow rules, thesis theory, notation,
     implementation contracts, storage schemas, and experiment policy
     (`:12-321`);
   - `GOTCHAS.md` restates environment, training, storage, frame, EVL, and
     Pydantic behavior (`:12-42`);
   - `OPEN_QUESTIONS.md` mixes advisor decisions, scientific questions,
     implementation choices, backlog items, and already locked decisions
     (`:12-50`).
10. Route each validated unique item to exactly one owner:
    - theory, RQs, hypotheses, scientific decisions, interpretation, and open
      scientific choices -> the active Typst thesis; development-only choices
      use the guarded roadmap or promotion queue;
    - Python behavior, lifecycle, shapes, frames, schemas, failure modes, and
      implementation caveats -> the defining source docstring/type/config and a
      focused test where the contract needs proof;
    - setup/environment commands that are not Python API contracts -> the
      minimal role-disjoint setup owner, without restating implementation
      behavior;
    - agent workflow/routing invariants -> the smallest existing `AGENTS.md`,
      skill, or source-order owner only when the rule is still valid and not
      already present;
    - actionable work -> an agents-DB record containing only compact context,
      owner pointers, acceptance, and gates. The record is action tracking, not
      a canonical destination, and may be created only after any valid source
      content has been materialized and verified at that destination;
    - obsolete, duplicate, or purely historical material -> deletion, with Git
      history and dated debriefs as provenance.
11. Remove the canonical-state mechanism and all live consumers of the four
    files or `.agents/memory/state/` directory:
    - update `.agents/memory/README.md:3-22` and
      `.agents/AGENTS_INTERNAL_DB.md:10-17` so history is episodic evidence and
      current truth always resolves to Typst/code/config/tests/guidance;
    - keep `canonical_updates_needed` as an owner-path list in debrief metadata,
      but update `.agents/memory/README.md:24-66` and `scripts/new_debrief.py` so
      examples point directly to canonical Typst/Python/guidance owners rather
      than `memory/state`;
    - remove the fixed `DECISIONS.md` promotion target from
      `scripts/codex_transcript_extract.py:658,726-773` and its tests. Candidate
      distillates remain non-authoritative until ordinary review assigns an
      exact canonical owner or agents-DB record;
    - remove all four state `DocSpec` entries and any empty canonical-state
      navigation from `scripts/quarto_generate_agent_docs.py:84-121`;
    - update source order, `aria-grill`, `agents-db`, context maps/indexes,
      Graphify inclusion, active backlog references, and generated context;
    - preserve dated history, resolved-backlog references, and migration receipts
      as provenance.
12. Do not create replacement `STATE.md`, `CONTEXT.md`, decision registry,
    canonical-memory summary, or automatic transcript-promotion sink. Routing
    surfaces point to canonical owners; they do not summarize their contents.

### 2.2 Typst state and marker requirements

Extend `docs/typst/thesis/draft_markers.typ`, preserving its existing mode check
at lines 3-10, submission-fatal typed TODOs at lines 12-37, and
submission-valid `thesis_status` at lines 59-107.

Required contracts:

```typst
#let development_only(body) = if thesis_mode == "development" { body } else { none }
```

- Development mode returns the body.
- Submission mode returns no rendered content.
- The macro must be the single guard used for roadmap, M1 report, draft-open-work,
  and promotion-queue content.

```typst
#let promotion_entry(
  summary,
  source:,
  target-section:,
  gate:,
  disposition:,
) = ...
```

- It is development-only.
- All named fields are required and non-empty.
- `disposition` is one of `candidate`, `blocked`, `deferred`, or `rejected`.
- Promoted content leaves the queue; `promoted` is intentionally not a live
  queue disposition.
- The body is a concise pointer, not a second copy of theory or a Python
  contract.

`thesis_status` remains a descriptive epistemic marker that is legal in
submission mode. Typed TODO markers remain visible in development and fatal in
submission. The raw development guard currently used for draft-open-work at
`docs/typst/thesis/appendix/index.typ:108-110` must be replaced by
`development_only(...)`.

### 2.3 Quarto requirements

1. Keep one `docs/_quarto.yml`.
2. Preserve the `contents/**/*.qmd` wildcard at `docs/_quarto.yml:4-8`.
3. Keep local and published Quarto behavior equivalent. Do not add an internal
   profile, quarantine directory, render allowlist, or hidden advisor site.
4. Remove all navbar/sidebar entries for the deleted thesis QMDs. Current links
   occur at `docs/_quarto.yml:78-87` and `docs/_quarto.yml:135-139`.
5. Update or remove inbound QMD links before deletion. Rendering must not leave
   a broken route or silently omit an intended public page.
6. Maintain an explicit expected-page manifest test because the wildcard alone
   cannot prove that a deliberately retained page is still rendered.

### 2.4 Branch and PR requirements

The following is a planning snapshot, not authorization for a GitHub mutation.
Refresh exact heads, bases, review threads, checks, and diffs at S0.

| PR | Planned disposition | Merge condition |
|---|---|---|
| #50 thin routing rewrite | Independent predecessor; out of scope for this task | Consume only its final exact handoff. Do not review, edit, merge, retarget, or close it here. |
| #49 Graphify freshness | Expected superseded by final #50 | Salvage only unique valid hunks absent from the pinned #50 tree. Otherwise close as superseded after authorization. |
| #47 MemPalace recall | Optional post-baseline lane | Rebase/adapt only after the owner map lands; it must remain optional and exact-source-first. |
| #44, #42, #38, #32, #30, #25 | Do not merge as-is | Disposition-only. #42 may supply bounded generated-API checks; #30 is historical idea salvage only. |

Stage A must not rebuild the stale PR stack. For every open PR and unmerged local
or remote branch, record `merge`, `salvage`, `superseded`, `close`, `defer`, or
`unknown`, with exact head/base/tree evidence and the reason.

### 2.5 Worktree and external-action requirements

- Do not modify the current dirty checkout.
- Ordinary Git commands in this checkout currently resolve
  `core.worktree=/var/tmp/aria-g006-gate-0CVnjn` from `.git/config`. Treat this
  as a hard preflight ambiguity: do not stage, commit, create a branch, or derive
  a baseline from this checkout until the intended Git/worktree relationship is
  proven. Do not silently rewrite the local Git configuration.
- Create all implementation branches from the S0 pinned integration baseline in
  clean, owner-disjoint worktrees.
- The repository currently has a large registered-worktree set; preview and
  classify stale registrations, but do not prune or delete any branch/worktree
  as part of consolidation without a separate exact-target authorization.
- Pushes, PR comments, PR closes, retargets, merges, branch deletion, and
  worktree deletion require fresh explicit authorization.

## 3. Acceptance Criteria

### 3.1 Ownership and content

- [ ] The active Typst include graph contains exactly one canonical six-tier
      statement in `sections/01-research-questions.typ`: RQ1--RQ4 evaluated
      core, RQ5 conditional online bridge, and RQ6 lower-priority escalation.
- [ ] `01-introduction.typ` includes the RQ file and no longer embeds a second
      copy.
- [ ] Roadmap and M1 content render only in development mode from their dedicated
      `.typ` files.
- [ ] The three deprecated QMDs no longer exist.
- [ ] `PROJECT_STATE.md`, `DECISIONS.md`, `GOTCHAS.md`, and
      `OPEN_QUESTIONS.md` no longer exist; `.agents/memory/state/` is absent or
      empty and has not been replaced by a renamed state/decision/context
      summary.
- [ ] A paragraph-level migration ledger gives every substantive block in the
      three deleted QMDs and four deleted memory-state files a canonical
      destination or an explicit `removed`, `historical`, `code-owned`,
      `test-owned`, `literature-owned`, or `deferred-action`
      disposition. Before either deletion commit, unique-content rows contain
      zero `unresolved` dispositions; every non-removed unique row records
      `destination_verified: true` plus an existing owner path and exact
      section/symbol; every `deferred-action` row names an active backlog ID,
      owner, and gate only for follow-up work after that canonical content is
      materialized; and every `removed` row records redundancy or obsolescence
      evidence.
- [ ] Every migrated scientific item appears once in the active Typst include
      graph; every migrated implementation item appears in its defining
      Python/config/type docstring and focused test rather than a handwritten
      implementation summary.
- [ ] Every valid unique-content row has a non-agents-DB
      `canonical_destination`, including setup and agent-guidance items.
      `deferred-action` means only that follow-up work is tracked; it names the
      already-materialized canonical-owner pointer plus backlog ID, owner,
      acceptance, and gate. It cannot substitute for content migration.
- [ ] Migrated agents-DB records contain only problem/why-now, canonical owner
      references, acceptance, and gates. They contain no copied theory,
      decisions, formulas, schemas, implementation contracts, or replacement
      narrative summaries.
- [ ] A file-level keep/thin/delete matrix covers every theory QMD and records
      unique retained value, canonical destination, inbound links, and citation
      disposition.
- [ ] No `.omx`, Quarto, skill, agent guidance, memory, or generated surface
      restates current RQs, equations, scientific definitions, or Python
      implementation contracts as authoritative truth.
- [ ] `.agents/references/source_order.md` links the three new Typst files and
      states the role-disjoint Quarto/Python ownership split without assigning
      any current-truth role to `.agents/memory/state/` or a replacement memory
      layer.
- [ ] A repository-wide reference classifier finds no live pointer to
      `.agents/memory/state/` or any of its four retired files, including
      guidance, skills, context maps/indexes, templates, transcript promotion,
      active backlog records, generated-doc specifications, and generated
      context/Graphify artifacts. Only dated history, resolved provenance, and
      explicit migration receipts may mention them.

### 3.2 Marker behavior

- [ ] `development_only` is visible in development and empty in submission.
- [ ] `promotion_entry` rejects missing/empty required fields and unknown
      dispositions.
- [ ] `promotion_entry` is absent from submission output.
- [ ] `thesis_status` remains legal in submission mode.
- [ ] Every typed TODO still aborts submission compilation.
- [ ] Development-only includes are reachable and cycle-free.

### 3.3 Documentation and API

- [ ] Quarto renders successfully with the existing wildcard.
- [ ] The expected-page manifest passes and excludes all three removed thesis
      pages.
- [ ] No internal link or navigation entry targets a removed page.
- [ ] Literature dossiers retain source-level coverage while thesis synthesis is
      removed or replaced by direct Typst pointers.
- [ ] Generated API reference is fresh against Python owners and public
      docstrings satisfy the repository's contract-focused docstring standard.
- [ ] Handwritten command/setup pages contain no duplicated implementation
      details.
- [ ] Internal generated-agent-doc configuration no longer produces canonical
      state, decisions, gotchas, or open-question mirrors, and contains no empty
      navigation section left by their removal.
- [ ] `docs/_generated/context/source_index.md`, `context_snapshot.md`, and every
      other live generated context artifact contain no retired memory-state
      reference.
- [ ] Graphify's graph, manifest, stats/detection metadata, and semantic chunk
      inventory contain no live source from `.agents/memory/state/`, and the
      imported #50 freshness gate passes without destructively purging shared
      content-addressed caches.
- [ ] Transcript distillation has no generic canonical-memory promotion target;
      tests prove candidate records remain non-authoritative until assigned an
      exact canonical owner or agents-DB target through ordinary review.
- [ ] Debrief documentation/templates may name exact canonical owner paths but do
      not assume a canonical memory-state update lane.

### 3.4 Branch and integration

- [ ] S0 records the final #50 commit SHA, tree SHA, base, released paths/hunks,
      check state, unresolved-thread state, exact validation commands, and
      reusable artifacts.
- [ ] Every worker begins from the recorded baseline or an integrated checkpoint
      named by the leader.
- [ ] Every lane touches only reserved paths, produces one focused commit, and
      returns the commit SHA plus validation output.
- [ ] The leader integrates in the declared order and runs the full final gate.
- [ ] PR/branch dispositions are refreshed after consolidation; no external
      action occurs without explicit authorization.

## 4. RALPLAN-DR Decision Summary

### Principles

1. One meaning, one owner.
2. Preserve information through an explicit disposition, then prune duplicates.
3. Pin immutable baselines and report exact evidence before parallel work.
4. Parallelize owner-disjoint leaves; serialize shared seams under the leader.
5. `.omx` coordinates work but never owns scientific or implementation truth.

### Top three decision drivers

1. Eliminate QMD/Typst/Python authority conflicts without losing unique evidence.
2. Integrate safely around the independent PR #50 task and the dirty current
   checkout.
3. Make destructive migration deterministic, reviewable, reversible, and
   testable.

### Options considered

#### A. Dependency spine plus owner-disjoint leaves — selected

Pin #50, freeze the owner map and tests, establish shared Typst marker contracts,
then execute isolated leaf lanes and integrate them serially. This minimizes
shared-file races and makes each deletion depend on destination proof.

**Invalidation condition:** if the final #50 handoff cannot provide an immutable
baseline and released-path receipt, execution stops before creating worktrees.

#### B. One atomic consolidation PR — rejected

This simplifies dependency ordering but combines theory migration, API cleanup,
navigation, and branch reconciliation into an unreviewable destructive diff.

**Would reconsider only if:** all parallel tooling is unavailable and a single
clean-room owner can still produce independently reviewable commits with the same
gates.

#### C. Independent parallel PRs without a shared spine — rejected

This maximizes concurrency but races on `main.typ`, `draft_markers.typ`,
`source_order.md`, `_quarto.yml`, citations, and deletion/link updates. It also
permits workers to start from incompatible branch histories.

**Would reconsider only if:** the shared seams are extracted and frozen first,
which effectively becomes option A.

#### D. Keep dual Typst/Quarto scientific ownership — invalidated

The user explicitly selected strict Typst ownership. Keeping both would preserve
the present drift mechanism and violate the requested consolidation.

#### E. Retain a narrower canonical memory-state layer — invalidated

The user explicitly selected deprecation of all four state files. Even a reduced
decision/gotcha/question layer would remain a manually synchronized cache of
Typst, Python, configuration, tests, and guidance.

## 5. Architecture Decision Record

### Decision

Use the active Typst include graph as the single scientific narrative owner;
use Python/config/types/docstrings plus tests as the single implementation owner;
retain Quarto only for role-disjoint public documentation; and retire the entire
four-file `.agents/memory/state/` current-truth layer rather than maintaining a
parallel decision/gotcha/question cache. Execute the migration on a pinned
post-#50 dependency spine, with leader-owned shared seams and owner-disjoint
worker leaves.

### Drivers

- Existing drift is concrete: Typst contains four current RQs at
  `sections/01-introduction.typ:15-25`, while `questions.qmd:32-58` and
  `questions.qmd:80-120` describe a larger roadmap and obsolete RQ5/RQ6
  escalation.
- The roadmap contains substantial scientific/model detail beginning at
  `roadmap.qmd:118`, which competes with Typst rather than serving navigation.
- The M1 report copies Python contract maps and operational evidence beginning at
  `m1_contract_report.qmd:19`, rather than remaining a thin status view.
- The current Quarto navbar and sidebar expose all three conflicting pages at
  `docs/_quarto.yml:78-87` and `docs/_quarto.yml:135-155`.
- The current source-order document assigns current direction to the QMDs at
  `.agents/references/source_order.md:11-14`.
- The four memory-state files duplicate the same authority across 487 lines:
  `PROJECT_STATE.md` calls six RQs canonical and points direction back to QMDs;
  `DECISIONS.md` embeds thesis theory and detailed live schemas;
  `GOTCHAS.md` restates discoverable implementation contracts; and
  `OPEN_QUESTIONS.md` includes already locked decisions.
- Git history shows reactive manual maintenance rather than a freshness
  contract: 26 commits from 2026-03-25 through 2026-07-30, with updates mixed
  into memory/scaffold, feature/refactor, and generic `dirty add .` commits.
  `scripts/validate_agent_memory.py:153-225` validates history structure and
  tracked runtime paths, not memory-state semantic freshness.

### Alternatives

See options B-E above.

### Why this decision

It removes competing truth surfaces while preserving distinct public and
development needs. A guarded Typst development appendix lets roadmap and
evidence status remain near the thesis without entering submission output.
Generated API reference keeps implementation documentation close to code. The
pinned-spine execution model isolates this work from PR #50 and the user's dirty
checkout.

### Consequences

Positive:

- scientific changes have one review surface and one submission rendering path;
- implementation contract changes flow through code, docstrings, generated API,
  and tests;
- Quarto becomes smaller and less likely to publish stale thesis state;
- agent routing no longer amplifies a manually maintained cross-domain cache;
- branch salvage can be judged against explicit owners rather than age or CI.

Costs:

- useful paragraphs must be mapped before deletion;
- all seven retired narrative sources require exhaustive disposition before
  deletion, and valid unique content may require surgical Typst/docstring/test
  additions;
- transcript/debrief workflows and backlog references must be retargeted without
  creating a generic replacement promotion sink;
- stable QMD URLs may need thin replacement routes only when they have a proven
  public role;
- Typst tests must distinguish development and submission modes;
- PR #47/#49 reconciliation waits for the consolidated baseline.

### Follow-ups

- Add the explicit human supersession as a compact ownership-only successor spec
  under `.omx/specs/`; do not copy scientific content into it.
- Refresh `source_order.md` in the integration commit.
- Remove the complete canonical-state mechanism and all live consumers; refresh
  derived Graphify/context outputs after the four source deletions.
- Record a non-authoritative migration/deletion ledger and final verification
  receipt under `.omx/`.
- After validation, request separate authorization for any GitHub or worktree
  cleanup actions.

## 6. Prior Plan Conflict and Missing-Information Audit

The historical handoff
`.omx/state/ralplan-agents-routing-scaffold-thesis-patches-handoff.json` is
retained unchanged as provenance. It was approved against observed head
`ecd54fcc...` (`:8-12`) but explicitly blocked execution (`:54-70`). Its
assumptions are superseded as follows:

| Historical assumption | Current decision |
|---|---|
| Graphify was optional measurement-only (`:90-96`) | Do not re-decide Graphify here. Import the final mandatory routing/freshness contract from PR #50's exact handoff. |
| Thesis QMDs could remain available through Quarto quarantine/profile work | Delete the three named QMDs after verified migration; keep one equivalent Quarto site with the existing wildcard. |
| `.agents/memory/state/` could remain a narrower canonical truth layer | Retire all four state files. Route theory to Typst, implementation facts to code/docstrings/tests, setup and workflow rules to their smallest existing owners, active work to pointer-only agents-DB records, and history to debriefs/Git. |
| Human accepted-spec supersession was missing (`:83-88`) | The current user instruction explicitly selects Typst/Python ownership. Persist the ownership-only supersession before source edits. |
| G006/predecessor state blocked execution (`:72-81`) | Replace this stale blocker with the final PR #50 handoff gate. Do not infer release from the old state file. |
| PR #30 supplied an implementation candidate | Preserve only idea-level salvage; do not replay its oversized branch or current QMD ownership model. |

Missing information that S0 must acquire:

- final #50 head/base/tree and completion receipt from task
  `019fff32-f2c3-7120-ae67-1ec7c42168de`;
- final #50 unresolved-review and CI state;
- exact paths/hunks released by that task;
- current open PR and unmerged branch heads after #50 settles;
- the intended relationship between `/home/jd/repos/ARIA-NBV`, its Git directory,
  and the configured `/var/tmp/aria-g006-gate-0CVnjn` worktree;
- exact inbound links, citations, promotion targets, and generated references to
  the three QMDs and all four memory-state files;
- exact expected Quarto page set;
- paragraph/bullet-level migration dispositions for all seven retired narrative
  sources and the theory-page unique-content matrix;
- an allowlist distinguishing historical/resolved memory-state provenance and
  migration receipts from every other repository reference that must be removed;
- Python/docstring/API coverage gaps that remain after refreshing generated docs;
- an approved exact target list before any worktree or branch cleanup.

Until the first four items are recorded, the plan is **approved but blocked at
S0**. No consolidation worktree should be created.

## 7. Implementation Plan

### Stage A — baseline and disposition

#### S0. Import the independent PR #50 completion receipt

Owner: leader/orchestrator. No worker delegation.

1. Wait for the independent PR #50 task to finish.
2. Record commit SHA, tree SHA, base SHA, changed paths, released paths/hunks,
   checks, unresolved threads, exact validation commands, and artifact locations.
3. Verify the receipt against local Git objects and GitHub state without editing
   or commenting on #50.
4. Verify which filesystem tree ordinary Git commands inspect. Use an explicit
   clean worktree created through the repository's valid Git common directory;
   never use the current redirected `core.worktree` as implicit baseline proof.
5. Create a clean integration worktree from the pinned SHA only after the receipt
   and Git/worktree relationship are complete.
6. Import #50's exact Graphify/scaffold validation commands verbatim into the
   successor test specification. Missing commands or artifacts block S1.

Stop condition: one immutable baseline receipt is complete and locally
verifiable.

#### S1. Create the ownership and migration inventories

Owner: leader, assisted by read-only `explore` agents where useful.

Produce under `.omx/`:

1. Paragraph/bullet-level disposition ledger for the three thesis QMDs and all
   four `.agents/memory/state/*.md` files. Record source path, heading/anchor or
   line span, Git blob ID, concise subject, destination owner, target
   path/section/symbol, link/citation action, and disposition.
2. File-level keep/thin/delete matrix for every theory QMD.
3. Inbound-link, navigation, skill, generator, Graphify, and context-index
   inventory for all seven retired sources and every theory page. Classify each
   repository-wide memory-state mention as live, dated history, resolved
   provenance, or migration receipt; templates, transcript promotion, and active
   backlog records count as live. Inspect executable/configured consumers and
   deserialize relevant generated artifacts rather than relying only on textual
   matches in source files.
4. Canonical-destination coverage inventory proving each valid unique state item
   already exists at its Typst/Python/config/test/setup/guidance owner. Record
   `destination_verified: true` only after the exact owner path and
   section/symbol exist and pass the relevant focused check; a planned or
   nonexistent destination fails coverage. Before migration, an item may be
   assigned to an owner-disjoint lane, but that assignment never satisfies the
   S4 deletion gate. Agents-DB IDs are recorded in a separate optional
   `tracking_record` field and never satisfy `canonical_destination`.
5. Python/docstring/generated-API coverage inventory.
6. Exact-diff inventories for PR #49 and #47 against the pinned tree.
7. Open PR, local branch, remote branch, and registered-worktree ledger.

The ledgers contain references and decisions, not copied theory or contracts.

Stop condition: every source block and branch/PR has an explicit disposition,
every valid unique state item has exactly one existing, verified canonical
destination, and every
live memory-state consumer has a recorded removal or exact-owner replacement.
Inventory work may record a temporary `unresolved` row only while assigning its
owner; S4 cannot begin until unique-content rows contain zero unresolved entries
and every non-removed unique row has `destination_verified: true`; an independent
reviewer must also confirm that no agents-DB record became a narrative truth
owner.

#### S2. Freeze shared contracts and lane reservations

Owner: leader.

1. Persist a compact successor ownership spec under `.omx/specs/`.
2. Persist a test specification under `.omx/plans/` derived from section 9.
3. Freeze the expected Quarto page manifest.
4. Freeze the Typst marker state machine and promotion disposition enum.
5. Reserve all shared paths to the leader.
6. Record the baseline SHA/tree and planned lane bases in the execution ledger.

Stop condition: no worker owns or may edit a shared seam.

### Stage B — owner migration and reconciliation

#### S3. Leader foundation commit

Leader-owned paths:

- `docs/typst/thesis/draft_markers.typ`;
- the Typst marker fixtures/test harness;
- the initial development include wiring needed by workers;
- the expected-page manifest harness;
- `.omx/**` execution receipts.

Implement `development_only` and `promotion_entry`, normalize the existing raw
development guard, and prove the macro contracts before worker launch. Do not
delete QMDs or edit shared navigation yet.

Stop condition: focused foundation tests pass and the leader records the
foundation commit SHA.

#### Wave A. Five owner-disjoint leaf lanes

Create each branch/worktree from the leader foundation SHA:

| Lane | Branch | Suggested worktree | Owned surface | Deliverable |
|---|---|---|---|---|
| RQ | `codex/consolidation-rq` | `/home/jd/.codex/worktrees/aria-consolidation-rq` | `sections/01-research-questions.typ` and the reserved RQ portion of `01-introduction.typ` | Canonical four-RQ extraction plus source-block disposition evidence. |
| Roadmap | `codex/consolidation-roadmap` | `/home/jd/.codex/worktrees/aria-consolidation-roadmap` | `development/roadmap.typ` | Development-only schedule/gate/status view with promotion pointers; no duplicated theory. |
| M1 | `codex/consolidation-m1` | `/home/jd/.codex/worktrees/aria-consolidation-m1` | `development/m1-contract-report.typ` | Development-only evidence/status view linking code/tests/artifacts; no copied implementation contracts. |
| Typst theory | `codex/consolidation-typst-theory` | `/home/jd/.codex/worktrees/aria-consolidation-typst-theory` | Leader-assigned, disjoint thesis section files only | Promote selected unique scientific content and citations into canonical thesis sections. |
| API | `codex/consolidation-api` | `/home/jd/.codex/worktrees/aria-consolidation-api` | Python/docstrings, focused tests, generated API config/tests only | Close contract-doc gaps and prove generated API freshness. |

State-ledger rows are assigned to these destination-owning lanes: scientific
rows to RQ/roadmap/Typst-theory, implementation rows to API, and minimal setup
rows to Wave B command docs. Agent-workflow rows remain leader-owned. There is no
memory-state worker because the deleted sources do not own their destinations.

Worker contract:

- do not edit `.omx/**`, `main.typ`, `draft_markers.typ`, `appendix/index.typ`,
  `source_order.md`, any `AGENTS.md`, `docs/_quarto.yml`, shared notation,
  bibliography, Makefile/CI, or another lane's files;
- do not delete a source QMD;
- produce one focused local commit;
- return commit SHA, changed paths, disposition rows closed, tests run, and
  remaining blockers;
- do not push or mutate GitHub.

Leader cherry-pick order:

1. RQ;
2. roadmap;
3. M1;
4. Typst theory;
5. API.

Run the relevant focused checks after every cherry-pick and record an integrated
checkpoint SHA after Wave A.

#### Wave B. Two role-disjoint cleanup lanes

Create both lanes from the Wave A integrated checkpoint:

| Lane | Branch | Owned surface | Deliverable |
|---|---|---|---|
| Theory Quarto | `codex/consolidation-theory-quarto` | leader-assigned `docs/contents/theory/*.qmd` files only | Apply the frozen keep/thin/delete matrix without editing navigation or shared thesis files. |
| Command docs | `codex/consolidation-command-docs` | leader-assigned setup/command QMD files only | Remove copied implementation detail while preserving minimal executable entry points. |

Each worker follows the same one-commit/no-push evidence contract. The leader
integrates and validates each commit separately.

#### S4. Leader integration and atomic source retirement

Leader-only shared surfaces:

- `.omx/**`;
- `docs/typst/thesis/main.typ` and the shared include graph;
- `docs/typst/thesis/draft_markers.typ`;
- `docs/typst/thesis/appendix/index.typ`;
- `.agents/references/source_order.md`;
- all four `.agents/memory/state/*.md` files and the state directory contract;
- `.agents/memory/README.md`, `.agents/AGENTS_INTERNAL_DB.md`, debrief templates,
  transcript extraction/promotion code and tests;
- `.agents/skills/aria-grill/SKILL.md` and the ARIA context routing/index files;
- `scripts/quarto_generate_agent_docs.py`;
- repository-wide live memory-state consumers, including active backlog records;
- root/docs/nested agent guidance;
- `docs/_quarto.yml` and navigation;
- shared notation, glossary, bibliography, and generated integration files;
- Makefile/CI and cross-surface tests.

Integration order:

1. Validate all destination Typst content in development mode.
2. Validate the submission projection and marker behavior.
3. Validate disposition-ledger completeness for the three QMDs and four
   memory-state files; require zero unresolved unique-content rows, fully
   qualified `deferred-action` rows, evidence-backed removals, and exactly one canonical
   destination for each migrated item.
4. Update include wiring, direct source-order links, navigation, and inbound
   links.
5. Delete the three QMDs in the same focused integration commit as their final
   navigation/link removal.
6. In a second focused integration commit, delete all four memory-state files
   and retire the directory contract together with every repository-wide live
   consumer: source-order, skills, memory policy, internal DB guidance,
   context-map/index, debrief templates, transcript promotion, active backlog
   records, generated-doc specifications, generated context, and Graphify live
   reachability. Preserve dated history, resolved provenance, and migration
   receipts.
7. Render Typst and Quarto, regenerate/check all context projections, refresh or
   incrementally update Graphify according to the imported #50 contract, and run
   the repository-wide active-reference classifier from the post-deletion tree.
   Remove live reachability from graph/manifest/stats/detection/chunk inventories
   without purging shared content-addressed caches.
8. Record both deletion commit SHAs and rollback instructions.

Do not leave stubs for the three deprecated QMDs or four memory-state files. Git
history and the migration ledger preserve provenance. Do not create a renamed
state/decision/context summary or generic transcript-promotion sink; narrow owner
pointers belong in `source_order.md` and the applicable skills.

#### S5. Reconcile branches and PRs

Only after S4 passes:

1. Re-diff #49 against the integrated tree and salvage only unique valid hunks.
2. Re-diff #47 and produce an optional-lane adaptation plan that preserves
   exact-source and mandatory Graphify authority.
3. Mark #44/#42/#38/#32/#30/#25 with evidence-backed dispositions; extract only
   bounded tests or ideas explicitly named in the ledger.
4. Refresh all open/unmerged branch dispositions.
5. Present the proposed merge/close/delete batch to the user for external-action
   authorization.

No GitHub action is part of this plan's automatic execution.

## 8. Parallel Execution and OMX Handoff

### Available agent-type roster

| Role | Model/effort | Use in this program |
|---|---|---|
| root leader/orchestrator | `gpt-5.6-luna`, high | Baseline, reservations, shared seams, integration, stop/escalate calls. |
| `architect` | `gpt-5.6-sol`, xhigh | Boundary review if execution uncovers a new cross-owner design choice. |
| `critic` | `gpt-5.6-luna`, high | Adversarial plan/change review; already used for this plan. |
| `team-executor` | `gpt-5.6-luna`, medium | Wave A/B implementation lanes under explicit path ownership. |
| `writer` | `gpt-5.6-luna`, high | Typst/Quarto prose migration where no Python work is involved. |
| `test-engineer` | `gpt-5.6-luna`, medium | Fixture and expected-manifest implementation if separated from production paths. |
| `verifier` | `gpt-5.6-luna`, high | Independent post-integration evidence audit. |
| `code-reviewer` | `gpt-5.6-luna`, high | Final source diff review after verification. |
| `git-master` | `gpt-5.6-luna`, high | Read-only branch topology and safe integration advice. |
| `explore` | `gpt-5.6-luna`, low | Fast read-only link, owner, symbol, and branch mapping. |

Apply `python-standards` in the API lane. Apply `typst-authoring` in Typst lanes.
All workers remain under the nearest `AGENTS.md` and must not revert concurrent
edits.

### Staffing recommendation

- One high-reasoning leader owns S0-S4 and all shared files.
- Wave A uses five medium-reasoning `team-executor` workers because the lanes are
  path-disjoint after the foundation commit.
- Wave B uses two medium-reasoning `team-executor` workers.
- One high-reasoning `verifier` audits the integrated tree without authoring the
  changes.
- One high-reasoning `code-reviewer` performs the final diff review.
- Use `architect` only if a newly discovered dependency changes the owner map;
  do not reopen settled theory decisions for stylistic preference.

### Launch hints

OMX Team requires an attached tmux runtime. From a clean integration worktree:

```sh
tmux new-session -s aria-consolidation
cd /absolute/path/to/clean/integration-worktree
omx team 5:team-executor "Execute Wave A from .omx/plans/prd-aria-nbv-ownership-branch-consolidation.md; obey path reservations and return local commit SHAs plus validation evidence."
```

After Wave A integration and checkpointing:

```sh
omx team 2:team-executor "Execute Wave B from .omx/plans/prd-aria-nbv-ownership-branch-consolidation.md at the recorded Wave A checkpoint; obey path reservations and return local commit SHAs plus validation evidence."
```

Use `$ultragoal` with this plan path as the durable execution owner. Team is a
bounded parallel subroutine: it does not own sequencing, shared files, final
verification, or external actions.

### Team verification path

1. Leader records baseline/foundation/checkpoint SHAs before launch.
2. Each worker reports changed paths and one commit SHA.
3. Leader rejects any commit touching unreserved/shared paths.
4. Leader cherry-picks in the declared order and runs focused checks after each.
5. Team state is terminal only when all lane receipts exist; a worker summary is
   not proof of integration.
6. Independent verifier checks the final integrated tree, not worker worktrees.
7. Ultragoal records final checks, disposition coverage, unresolved items, and
   the external-action boundary.

## 9. Verification Plan

### 9.1 Unit/fixture checks

- Positive and negative fixtures for `development_only`.
- `promotion_entry` fixtures for every allowed disposition, every missing field,
  empty fields, and an unknown disposition.
- Submission-valid `thesis_status` fixture.
- Submission-fatal fixture for each typed TODO alias.
- Include reachability and cycle check for all new Typst files.
- Migration-ledger schema and disposition coverage check.
- Migration-ledger materialization check rejecting nonexistent, merely planned,
  or unverified canonical paths/sections/symbols; every non-removed unique row
  must have `destination_verified: true`, including `deferred-action` rows.
- Repository-wide active-reference classifier/fixture that fails when any live
  guidance, skill, context map/index, template, active backlog record,
  transcript promotion target, generated-doc spec, generated context artifact,
  or Graphify source names `.agents/memory/state/` or any retired state file;
  explicitly allow only dated history, resolved provenance, and migration
  receipts. Exercise executable/configured consumers and deserialize the
  relevant generated Graphify/context artifacts so binary or structured
  metadata cannot evade a source-text-only scan.
- Canonical-destination uniqueness check for every valid item from all four
  memory-state files, including setup and agent-guidance destinations; agents-DB
  paths fail this field.
- Agents-DB narrative-non-ownership fixture/review gate: migrated records expose
  only problem/why-now, canonical owner references, acceptance, and gates, and
  reject copied theory, decisions, formulas, schemas, or implementation
  contracts.
- Transcript-distillation fixtures proving candidates have no generic canonical
  memory target and require explicit reviewed owner assignment.
- Debrief-policy fixtures proving `canonical_updates_needed` accepts exact
  canonical owner paths without depending on a memory-state directory.
- Theory-page matrix schema and coverage check.
- Expected Quarto page manifest check.
- Generated API freshness and stale-alias self-test (`Makefile:255-256`).

### 9.2 Integration checks

Typst development projection:

- four canonical RQs render once;
- roadmap, M1 status, draft-open-work, and promotion queue render;
- direct source and target pointers resolve.

Typst submission projection:

- four canonical RQs render once;
- roadmap, M1 status, draft-open-work, and promotion queue are absent;
- `thesis_status` compiles;
- typed TODO fixtures fail;
- the full submission build fails unless its existing confirmatory-evidence gate
  is satisfied.

Quarto:

- `contents/**/*.qmd` remains configured;
- the full site renders;
- expected pages exist;
- removed thesis routes do not exist;
- no link, nav entry, or citation points to a deleted/renamed target.

Agent routing and memory:

- all four state files are absent and `.agents/memory/state/` is absent or empty;
- `source_order.md`, memory policy, internal DB guidance, and agent skills no
  longer assign any current-truth role to `.agents/memory/state/`;
- `aria-grill`, the context map/index, and generated-agent-doc configuration do
  not route through a retired state file;
- no generated state/decision/gotcha/open-question mirror or empty navigation
  group is produced;
- debrief templates and active agents-DB records do not request or cite
  memory-state files as current owners;
- transcript distillation does not promote into `DECISIONS.md` or another generic
  sink;
- all live generated context artifacts omit the state directory and four files;
- `make check-agent-memory` passes, but is supplemented by the active-reference
  fixture because the current validator does not prove semantic freshness;
- refreshed Graphify graph, manifest, stats/detection metadata, and semantic
  chunk inventory contain no live source or reachability for
  `.agents/memory/state/` or any retired file; shared content-addressed caches
  remain intact.

Python/API:

- generated reference is fresh;
- focused docstring/type/config tests pass;
- implementation behavior is unchanged unless a separately accepted code fix is
  required and covered by tests.

### 9.3 End-to-end gates

Import and run the exact PR #50 Graphify/scaffold commands from S0. At minimum,
the current repository exposes:

```sh
make scaffold-audit
make scaffold-audit-self-test
make check-agent-memory
make api-docs-self-test
make quarto-docs-ci
make thesis-pdf
git diff --check
make ci
```

The named targets are currently defined at `Makefile:228-259`,
`Makefile:666-725`, and `Makefile:737`. If PR #50 changes them, the pinned
handoff commands take precedence and this plan's test spec must be updated before
execution.

### 9.4 Observability and receipts

The `.omx` execution ledger records:

- baseline commit/tree and PR #50 receipt;
- lane reservations, bases, commit SHAs, and changed paths;
- paragraph/file disposition and live-consumer coverage;
- focused and integrated validation commands with exit status and artifact path;
- final unresolved items;
- proposed external actions and whether authorization was granted.

Generated PDFs, sites, API pages, screenshots, graphs, and logs are evidence, not
truth owners.

## 10. Pre-mortem, Mitigations, and Rollback

### Failure scenario 1: PR #50 changes or releases an incomplete baseline

**Early signs:** missing tree SHA, changed head after receipt, undocumented shared
paths, unresolved threads, or unavailable validation artifacts.

**Mitigation:** block before worktree creation; re-import and re-verify one exact
receipt. Never guess released paths from a local diff.

**Rollback:** none required because no source mutation has begun.

### Failure scenario 2: content is lost or merely duplicated in Typst

**Early signs:** uncovered ledger rows, two RQ render occurrences, theory text in
roadmap/M1, a renamed state/decision/context summary, a generic transcript
promotion sink, broken citations, or a deletion commit without destination
proof.

**Mitigation:** fail the coverage and render gates; require explicit dispositions;
integrate leaf commits before the atomic deletion commit.

**Rollback:** the first boundary reverts the three-QMD/navigation deletion
commit; the second independently reverts the four-file memory-state mechanism
retirement commit. Rehearse the second boundary in a temporary worktree:

1. revert the retirement commit;
2. prove the four files and live consumers match the recorded pre-retirement
   checkpoint and the legacy baseline checks pass; the new absence/reference
   gates are expected to fail in this temporary reverted state;
3. reapply the retirement commit;
4. prove the new transcript/debrief, active-reference, context, Graphify, and
   agents-DB non-ownership gates pass.

Revert only the offending leaf or integration commit; do not rewrite history.

### Failure scenario 3: development-only content leaks or scaffold/Graphify gates regress

**Early signs:** submission PDF contains roadmap/M1/promotion content, typed TODOs
compile, or imported #50 checks fail after integration.

**Mitigation:** stop integration, identify the first failing cherry-pick, and
repair or revert that focused commit before continuing.

**Rollback:** revert the affected focused commit and return to the last recorded
integrated checkpoint.

## 11. Architect/Critic Review Changelog

The planning pass used sequential Architect then Critic review. The final Critic
verdict was **APPROVE** after the following changes were incorporated:

- added an immutable PR #50 commit/tree receipt and made its absence a hard S0
  blocker;
- separated the independent PR #50 task from this plan's scope;
- made the three QMD deletions atomic with destination, link, citation, and render
  proof;
- replaced an informal draft flag with explicit `development_only`,
  `promotion_entry`, `thesis_status`, and typed-TODO state contracts;
- kept `.omx` non-authoritative and prevented planning ledgers from copying
  theory or code contracts;
- changed parallel execution to owner-disjoint worktrees with leader-owned shared
  surfaces and ordered cherry-picks;
- added expected-page, migration-coverage, include-reachability, generated-API,
  and exact-PR50 verification gates;
- preserved the old handoff as historical evidence and enumerated superseded
  assumptions instead of overwriting it;
- delayed PR #47/#49 reconciliation until the new ownership baseline exists;
- added pre-mortem, rollback, observability, staffing, and Team verification
  sections for the destructive migration.
- added the user-requested `PROJECT_STATE.md` retirement: paragraph-level
  disposition, live-consumer removal, separate reversible deletion commit,
  Graphify/context cleanup, and a freshness/reference regression gate.
- strengthened that amendment after Architect review with a bounded role audit
  of the three retained state files, zero-unresolved deletion gates,
  repository-wide reference classification, exact generated/Graphify
  postconditions, and two-commit rollback rehearsal.
- completed the required sequential re-review; Architect and Critic both
  returned `APPROVE` with no remaining blocker.
- superseded the partial-retention amendment after the user explicitly required
  deprecation of `DECISIONS.md`, `GOTCHAS.md`, and `OPEN_QUESTIONS.md` as well;
  the plan now retires all four memory-state files, migrates validated unique
  content to exact Typst/docstring/test/config/guidance owners, and removes the
  generic transcript/debrief/current-truth mechanism.
- prohibited agents DB from becoming a terminal content owner, extended
  canonical-destination coverage to setup/guidance, and defined inverse/forward
  expectations for the temporary-worktree rollback rehearsal.
- closed the final Critic-identified deletion loophole: `deferred-action` may
  track only post-migration follow-up, every non-removed unique row requires an
  existing exact destination with `destination_verified: true`, and fixtures
  reject merely planned destinations while inspecting configured/generated
  consumers.

- completed the required sequential re-review of the full seven-source
  retirement amendment: Architect and Critic both returned `APPROVE` with no
  remaining blocker. Execution remains blocked only on the explicit S0 evidence
  gate.

## 12. Goal-Mode Follow-up Suggestions

1. **Recommended:** launch `$ultragoal` with this PRD as the durable multi-stage
   execution contract. It should own S0-S5, receipts, checkpoints, and the final
   authorization boundary.
2. **Recommended parallel path:** let Ultragoal invoke OMX `$team` for Wave A and
   Wave B only after their prerequisites and reservations are recorded.
3. **Not applicable:** `$autoresearch-goal`; this is an ownership migration, not
   evaluator-gated empirical research.
4. **Not applicable:** `$performance-goal`; no performance objective is being
   optimized.
5. **Fallback only by explicit user choice:** `$ralph` as a persistent
   single-owner execution loop if Team/tmux is unavailable. Do not silently
   substitute it for the requested parallel plan.

## 13. Completion and Handoff

The consolidation is complete only when:

- all acceptance criteria are checked with fresh evidence;
- the final integrated commit/tree and rollback points are recorded;
- the independent verifier and final code reviewer report no blocking findings;
- no unique-content disposition remains unresolved and
  `deferred-action`/`removed` rows satisfy their evidence contracts;
- all four memory-state files, their directory contract, generated mirrors,
  promotion sinks, and live routing references are absent while historical and
  resolved provenance remains available;
- proposed PR/branch/worktree actions are presented separately and remain
  unexecuted until authorized.

The final handoff must lead with the resulting owner map, changed files, deleted
surfaces, exact validation evidence, remaining risks, and the external actions
that still require user approval.
