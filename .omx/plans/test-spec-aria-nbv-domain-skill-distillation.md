---
kind: ralplan-test-spec
status: approved
slug: aria-nbv-domain-skill-distillation
prd: .omx/plans/prd-aria-nbv-domain-skill-distillation.md
mode: deliberate-consensus
amended: 2026-08-01
---

# Test specification: ARIA-NBV domain-skill distillation

## Purpose

Prove that the cleanup removes duplicate authority and context without losing
invocation, exact-owner discovery, handoffs, completion discipline, or operation
when optional tools are absent. LOC and description bytes are reported only as
maintenance evidence; they are not success criteria.

## Test strategy

1. Pass the clean-baseline preflight before freezing destructive-edit evidence.
2. Validate the smallest unit that can prove each moved contract.
3. Compare baseline and candidate on positive prompts, near misses, handoffs, and
   exact-source fallback.
4. Run owner-specific package/docs tests when a fact moves.
5. Finish with exact-head cross-surface validation and independent review.

The shared routing smoke set is intentionally tiny and human-readable. The
remaining cases are skill- or pair-local and run only when their disposition is
under decision. It must not grow
into a general evaluator or a lexical score optimized after candidate output is
seen.

## Execution preflight

Before WP0:

- freeze or track the approved PRD, test specification, handoff, and approving
  amendment reviews at one selected revision;
- create or select a clean dedicated worktree at that revision and record
  branch, head, and worktree list;
- classify every unrelated dirty path in the primary checkout and prove none is
  copied into the baseline;
- require exit zero from `make scaffold-audit`,
  `make scaffold-audit-self-test`, and `make check-agent-memory` in the dedicated
  baseline.

Expected: the baseline is clean, the approved plan is reproducible from its
revision, and all three gates are green. Stale Graphify is recorded and causes
exact-source fallback; it is not repaired as part of this plan. A failed preflight
is an implementation `NO-GO`, not WP0 evidence.

## Baseline capture

Before WP1 or WP2:

- record branch, head, and `git status --short`;
- archive the nine current descriptions and scoped skill inventories in the PR
  evidence, not as a new repository truth surface;
- run current `make scaffold-audit` and `make scaffold-audit-self-test`;
- run the tiny shared smoke plus only the affected skill/pair-local native prompts
  below in fresh, minimally primed contexts and record selected skill, owner
  opened, handoff, and completion evidence;
- capture current exact-source behavior with Graphify/tooling absent or stale;
- hash or otherwise record unrelated dirty paths so the workpackage can prove it
  did not mutate them.

Also record, for every scoped skill, its proposed invocation mode, exact evidence
that repo routing or another skill needs autonomous reach, leading word, and
independent description branches. `writing-great-skills` is an external design
reference for this evidence, not a repository truth owner.

## Unit tests

### U1 — native skill structure

For every changed skill:

- directory name equals frontmatter `name`;
- YAML parses;
- `name` and a non-empty single-sentence `description` exist;
- the description names genuine invocation branches without synonym duplication;
- any declared repository-relative owner pointer resolves;
- any referenced branch file exists and is directly linked from `SKILL.md`;
- existing `agents/openai.yaml`, if retained, parses and names the same skill.

Command:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  .agents/skills/<changed-skill>
```

Expected: success for every changed skill. If the external validator is absent,
the reduced repo mechanical gate covers equivalent stable structure and reports
the validation gap.

For `route-only/prune`, replace this structure test with absence plus exact live-
consumer, replacement-route, completion-preservation, and rollback checks. Do
not create a pointer-only skill merely to satisfy U1.

### U2 — no duplicate invocation owners

Inspect each changed skill and UI default:

- description is the sole model trigger statement;
- no `metadata.triggers` synonym list survives on converted scoped skills;
- no body `When To Use` section repeats the description;
- adjacent exclusions/handoffs appear only at the decision point that needs them.

Expected: one maintained activation meaning per skill.

### U2b — invocation mode and survivor-name discoverability

For every scoped skill, verify the PRD invocation matrix against root/nearest
routing and actual adjacent-skill handoffs. For every merged candidate, exercise
each absorbed branch using prompts that contain its natural leading word but not
the survivor identifier.

Expected: the baseline records current autonomous-routing evidence for all nine;
it does not predetermine survival. A retained minimal skill or passing merger
preserves autonomous reach for every branch it owns. A route-only/prune candidate
must prove the replacement guidance or existing procedure preserves that reach
without a model-visible compatibility alias. Each surviving description contains
one trigger per genuine branch; a candidate fails if explicit review, target-RRI,
Zarr, or Rerun wording becomes less discoverable through its selected route.

### U3 — no skill-owned domain truth

For each removed or rewritten factual sentence, review a claim-disposition row:

```text
skill path + line | claim | disposition | exact owner path + symbol/section | proof
```

Expected:

- every row is `already owned`, `move`, `stale`, or `open`;
- `already owned` and `move` paths exist under allowed Typst/code/README/AGENTS
  owners;
- `open` blocks deletion of that sentence;
- no row points to another skill or skill-local reference as authority.

Each row must first classify its claim type and use the matching owner:
scientific definition/formula/interpretation -> shared or thesis Typst or exact
external source; executable behavior/type/shape/schema/version/default -> code,
config, docstring, or test; durable subsystem orientation/usage -> module README;
invariant/hazard/routing/verification -> nearest `AGENTS.md`; repeatable
procedure -> skill. README and `AGENTS.md` fail review when used as generic sinks
for scientific or implementation truth.

This is a review artifact attached to the workpackage, not a permanent registry.

### U3b — procedural-capability preservation

For every changed skill, record each description/body/reference branch as
`retained`, `replaced`, `removed`, `deferred`, or `open`, with its focused
comparison. An `open` branch blocks deletion. Rerun and dataset coverage must
include every branch enumerated in the PRD, not only the default smoke command.

Expected: every removed procedural branch has replacement evidence or an explicit
removal rationale; no capability disappears because it was mistaken for domain
truth.

If truth removal leaves only pointers/handoffs, compare that survivor against
route-only/prune through the nearest guidance or an existing procedure. Keeping a
pointer-only skill fails unless the probe demonstrates independent procedural
value unavailable from the replacement route.

### U4 — dual-schema audit contract

Focused negative fixtures must fail for:

- malformed YAML;
- directory/frontmatter name mismatch;
- missing/empty description;
- broken explicitly declared repository pointer;
- malformed routing-fixture JSON or nonexistent expected skill;
- an unconverted skill with no legacy metadata;
- an unconverted skill with only part of the required legacy metadata;
- an allowlisted native-minimal skill that retains only part of the retired
  legacy trigger/authority metadata;
- an allowlisted native-minimal skill that retains the complete retired legacy
  trigger/authority schema (U2's one-activation-owner rule is enforced here);
- a live current-surface reference to retired `python-docstrings`.

Focused positive fixtures must pass for:

- minimal `name`/`description` frontmatter for an identifier explicitly present
  in the temporary audit-owned `NATIVE_MINIMAL_SKILLS` set;
- an explicitly allowlisted compact body with a direct owner pointer;
- a complete current legacy-metadata skill whose syntax/path/handoff/tool/owner
  checks remain strict;
- a valid tiny routing fixture.

Expected: allowlisted native-minimal skills do not require reconstructed custom
metadata; absence of metadata never implies conversion; unlisted skills require
the complete legacy contract and partial legacy metadata fails. Each one-skill
conversion and rollback changes both its entry and `NATIVE_MINIMAL_SKILLS`.
Legacy-structured skills keep every current deterministic check. The bridge adds
no new semantic keyword scanner, synonym-token scorer, or general evaluator.

### U5 — Python-docstrings retirement

```bash
test ! -e .agents/skills/python-docstrings/SKILL.md
git grep -n -I -e 'python-docstrings' -e '.agents/skills/python-docstrings' -- \
  . ':(exclude).agents/memory/**' ':(exclude).agents/archive/**' \
  ':(exclude).omx/**'
```

Expected: the file is absent and the scoped live search returns no consumer.
Historical evidence is allowed.

### U5b — merged-peer consumer atomicity

For each prospective retired peer, inventory exact-head tracked matches and
classify them as `atomic consumer`, `retired self-subtree`, `historical evidence`,
or `domain/library homonym`. Include routing/nearest guides, skill handoffs, UI
metadata, adapter manifests, audit/routing fixtures, and current backlog records.

Expected:

- the candidate probe and final merged workpackage patch every atomic consumer;
- a scoped live search returns zero unexplained identifier/path references after
  excluding the retired subtree, historical records, generated derivative text,
  and documented genuine homonyms such as `/zarr-developers/zarr-python`;
- backlog mutations use `agents-db` and historical/resolved evidence is not
  rewritten;
- rollback restores the retired skill, its peer, discriminator, fixtures, UI,
  routing/handoffs, manifests, and current backlog references together.

### U6 — rollout/read-model and Rerun owner migration

Inspect the new/updated package owner and public symbols against former
`nbv-inspector-contract.md` claims:

- observer/read-only responsibility;
- required input boundary;
- candidate-prefix/all-invalid behavior;
- frame/display-only behavior;
- CLI/output modes;
- preferred test seams.

Also compare `aria_nbv.rollouts.read_model` with
`aria_nbv.rerun_inspector._rollout_zarr` for direct array decoding, mask
reconstruction, selected transitions, and presentation DTO ownership.

Expected: every retained contract has an allowed package/code owner and focused
test; the seam is proven complete or explicitly open; no README claims a migration
that current code has not completed; the skill reference can be deleted only when
both offline and rollout inspection ownership is sufficient.

### U6b — owner-only prerequisites for counterfactual and entity-RRI

Before either skill changes, inspect the WP4A/WP4B claim dispositions and exact
owners.

Expected:

- every counterfactual fact removed in WP8 is already present and verified in an
  active Typst section or rollout package owner, stale with evidence, or open and
  therefore retained;
- every entity-RRI fact removed in WP9 is already present and verified in an
  active Typst section or target/RRI package owner, stale with evidence, or open
  and therefore retained;
- WP8 and WP9 diffs contain no Typst, package code, README, or AGENTS truth-owner
  edits; owner migration and skill distillation remain independently reversible.

### U7 — docs-curator/Typst boundary

Static review:

- `docs-curator` description/body names Quarto, bibliography, navigation, and
  public/internal boundary;
- general Typst authoring/rendering is absent and handed to `typst-authoring`;
- current docs taxonomy and commands remain in `docs/AGENTS.md`.

Expected: no duplicated authoring procedure.

## Integration tests

### I1 — metadata/audit/CI integration

Run:

```bash
make scaffold-audit
make scaffold-audit-self-test
make check-agent-memory
aria_nbv/.venv/bin/python -m pytest -q scripts/tests/test_agent_governance_g002.py
```

Expected: all pass with the minimal skill contract. If the exact pytest path is
not executable as a module in the environment, run its repository-supported
equivalent and record the gap literally.

### I2 — exact metadata-consumer integration

Confirm the transition changes only the live consumer chain:

- `scripts/scaffold_audit.py` directly reads custom skill metadata and
  `scripts/scaffold/fixtures/routing.json`;
- `scripts/tests/test_agent_governance_g002.py` protects the routing fixture;
- Make targets and CI invoke the audit/self-test;
- `.agents/skills/README.md` and `.agents/references/source_order.md` state the
  policy.

Inspect `scripts/quarto_generate_agent_docs.py` and confirm its fixed `DOC_SPECS`
do not read scoped skills or custom metadata.

Expected: actual consumers/policy owners support both schemas; the verified
non-consumer remains unchanged; no generated-doc churn or fabricated owner
surface is introduced.

### I3 — package owner verification

Run only the suites implicated by actual owner moves:

```bash
cd aria_nbv
uv run pytest tests/rollouts -q
uv run pytest tests/data_handling/test_vin_offline_store.py \
  tests/data_handling/test_public_api_contract.py -q
uv run pytest tests/rri_metrics -q
uv run pytest tests/rendering/test_depth_backprojection_conventions.py \
  tests/rendering/test_candidate_renderer_integration.py -q
uv run pytest tests/rerun_inspector \
  tests/data_handling/test_offline_visual_inventory.py -q
```

Expected: focused owners remain green. Do not run unrelated broad package suites
as a substitute for the direct contract test.

### I4 — thesis owner verification

When current scientific meaning moves into Typst:

```bash
cd docs
typst compile typst/thesis/main.typ /tmp/aria-nbv-domain-skill-distillation.pdf \
  --root .
```

Inspect affected pages for target/RRI, candidate/replay, finite-candidate value,
and policy-comparison changes.

Expected: compile succeeds, current claim strength is unchanged, and each fact
removed from the nine scoped skills has an allowed active Typst/code owner. This
test does not assert global Quarto retirement or resolve the accepted Typst/Quarto
open decision.

### I5 — adjacent-boundary handoffs

For each pair, run one prompt on either side and one ambiguous prompt:

| Boundary | Side A | Side B | Ambiguous prompt must do |
| --- | --- | --- | --- |
| Review / diagnosis | concrete diff review | failing symptom reproduction | choose symptom owner first when no trustworthy diff finding exists |
| Docs curator / Typst | Quarto navigation/bibliography | Typst prose/render | state primary owner and hand off only crossed surface |
| Target RRI / rollout | target-label semantics | multi-step Q_H evaluation | localize target semantics before rollout evaluation |
| Dataset / Zarr | operate existing store | change API/layout/codec | choose Zarr only when storage implementation changes |
| Geometry / Rerun | change frame/projection contract | log/inspect observer artifact | geometry owns semantic change; Rerun owns observer output |

Expected: exactly one primary route, with an explicit adjacent handoff only when
the prompt crosses both contracts.

## End-to-end behavioral smoke set

The shared smoke contains only: positive prompt 4 for diagnostic routing,
positive prompt 7 for exact owner discovery/progressive disclosure, near miss 7
for direct exact-source routing, and the applicable optional-tool-absent fallback.
All other prompts below are a pair-local catalog and run only for the skill or
boundary being changed.

Run each selected case once in a fresh, minimally primed Codex process before and
after the relevant workpackage. Repeat only when stochastic invocation materially
decides retain/merge/route-only-prune; record that rationale and fixed trial count
before candidate inspection. Record selected skill(s), observed skill and owner
paths, optional tool use, handoff, completion evidence, and any false activation.
Passing requires every predeclared trial to select the correct primary and no
trial to select a forbidden primary.

### Positive prompts

1. `Review this ARIA-NBV working-tree diff and report severity-ranked findings.`
   Expected primary: `code-review-aria-nbv`.
2. `Plan a finite-candidate counterfactual rollout comparison for Q_H with equal
   acquisition budgets.` Expected primary: `counterfactual-rollout-planner`.
3. `Validate this existing immutable VIN offline store and explain whether it
   needs a rebuild.` Expected primary: `dataset-cache-ops`.
4. `Diagnose this failing ARIA-NBV command from its traceback.` Expected primary:
   `diagnose-aria`.
5. `Reorganize Quarto navigation and bibliography without exposing internal agent
   pages.` Expected primary: `docs-curator`.
6. `Change target-specific RRI labels and preserve invalid-target reasons.`
   Expected primary: `entity-aware-rri`.
7. `Change CameraTW backprojection and prove the frame/shape/unit contract.`
   Expected primary: `nbv-geometry-contracts`.
8. `Save a one-sample Rerun .rrd inspection artifact for candidate frusta and
   validity.` Expected primary: `rerun-nbv-inspector`.
9. `Inspect selected transitions and target validity in an existing rollout-Zarr
   store through Rerun.` Expected primary: `rerun-nbv-inspector`; shared typed
   interpretation must come from `rollouts.read_model` where implemented.
10. `Change rollout Zarr v3 chunking and codec behavior with a round-trip test.`
   Expected primary: `zarr-python`.
11. `Refactor public Python docstrings for a DTO.` Expected primary:
    `python-standards`; `python-docstrings` must not be required.

The expectations above are the baseline and separate-skill oracle. When WP0
selects a passing merger, final verification changes only these expected
primaries while preserving the same branch, first owner, handoff, and completion
criterion:

| Passing merger | Retired-skill prompts | Merged-branch expected primary |
| --- | --- | --- |
| Review + diagnosis | Prompt 1 | `diagnose-aria`, taking its diff-review branch; prompt 4 remains `diagnose-aria` on the symptom branch |
| Target-RRI + rollout | Prompt 6 | `counterfactual-rollout-planner`, taking its target-RRI branch; prompt 2 remains its rollout branch |
| Dataset + Zarr | Prompt 10 | `dataset-cache-ops`, taking its storage-implementation branch; prompt 3 remains its existing-store operation branch |
| Geometry + Rerun | Prompts 8 and 9 | `nbv-geometry-contracts`, taking its observer/Rerun branch; prompt 7 remains its semantic-geometry branch |

No other expected primary changes. A retired identifier must be absent from the
final live surface, while every invocation branch formerly routed through it
must pass every predeclared trial through the named survivor.

### Symmetric survival comparison

For every scoped skill, compare a separately distilled minimal candidate against
a route-only/prune fallback. For each of the four in-scope Option C pairs, also
compare both separately distilled minimal skills against one minimal merged
candidate description and branch map. The unchanged legacy bodies are an
observation baseline only and cannot win identity by being compared solely with
a cleaner merger. Run the tiny shared smoke and only that skill/pair's positives,
near misses, and ambiguous handoffs. Test docs-curator/Typst only as a handoff
boundary; `typst-authoring` is not a merger candidate or editable surface.

A merger is viable only when it achieves:

- every predeclared trial has the correct primary branch and first owner;
- no predeclared trial has a forbidden primary branch;
- no additional universal owner/reference load;
- no weaker completion criterion;
- one coherent leading word and an independent rollback plan.

Any failure or inconclusive result retains the separately distilled skill. A
passing merger must instantiate the PRD's fixed substitution-matrix row,
including its owner prerequisites, survivor/retired identifier, allowlist
mutation, tests, and rollback. A passing route-only/prune result must remove the
identifier and atomically update the exact consumer bundle, replacement route,
fixtures/UI/backlog surfaces, and rollback. Do not tune prompts, trial counts, or
pass bars after seeing candidate results.

Execute the comparison in the PRD's disposable detached-worktree protocol. Every
trial is a new Codex process using `--ask-for-approval never`, `exec --ephemeral`,
and `--ignore-user-config` with the same recorded model, output schema, and
read-only policy; redirect JSON events to the external JSONL evidence path.
Candidate output is admissible only when the probe diff contains exactly the
candidate skill disposition, temporary discriminator/fixture changes, and
classified atomic consumer bundle; a scoped search has zero unexplained live
retired-skill consumers; and narrowly forced disposal restores the primary
status/digest without pruning or changing any pre-existing worktree. Observed
JSONL/tool events are authoritative over structured output and final-response
self-report: they must show every claimed opened skill/owner path beneath the
probe worktree. An outside path, an unobserved claimed open, or a mismatch fails
the trial. The retired identifier must also be absent from the probe catalog.

### Combined passing-set and independent rollback

When at least two pairwise candidates pass, construct the PRD's ephemeral
consumer-dependency graph and apply all passing substitutions as ordered separate
temporary commits in one disposable candidate. Run the complete smoke, catalog,
and zero-unexplained-reference checks against that combined commit.

For each selected merger, create a separate validated rollback-probe worktree at
the combined commit, run `git revert --no-commit` for only that merger's temporary
commit, and re-run every affected positive, near miss, handoff, and consumer
check while the other mergers remain applied. Use repository-local throwaway Git
author settings for the temporary commits. The reverted pair uses the
separate-skill primary oracle; other pairs retain their merged-primary oracle.

Expected:

- the combined candidate preserves all scoped invocation branches and contains
  zero unexplained consumers of every retired identifier/path;
- each isolated rollback applies without conflict, restores the merger's two
  legacy skill/consumer surfaces, leaves other merger changes intact, and stays
  green against identifiers those other mergers still retire;
- each rollback probe is narrowly disposed without reset/restore/global prune;
- a failing or inconclusive connected consumer component retains all its
  separate skills; a cross-component failure records and retains the implicated
  component union, while non-overlapping passing components may proceed;
- the final accepted combined set is rebuilt and passes once.

Bound: one combined run plus at most four individual rollback probes; no
exhaustive subset search.

### Near misses and forbidden routes

1. One-step VIN scoring with no rollout semantics must not select the
   counterfactual skill. If target-RRI/rollout merged, the survivor must still
   remain inactive unless the prompt crosses target/entity or rollout scope.
2. Store smoke/manifest validation with no Zarr implementation change must not
   select `zarr-python` as primary. If dataset/Zarr merged, it must take the
   `dataset-cache-ops` operation branch without loading storage-implementation
   owners.
3. Geometry semantics already proven, with only Rerun layout/color changes, must
   select `rerun-nbv-inspector` in the separate branch. If the geometry/Rerun
   merger passed, it selects the `nbv-geometry-contracts` observer branch but
   must not reopen or change semantic geometry.
4. Typst thesis prose/rendering must not select `docs-curator` as primary.
5. Concrete diff review must not enter the causal diagnosis loop unless a finding
   needs reproduction. If review/diagnosis merged, `diagnose-aria` must take the
   diff-review branch and preserve review completion without forced reproduction.
6. Scene-level RRI with no entity/target contract must not select
   `entity-aware-rri`; after a target-RRI/rollout merger it must not select the
   survivor merely because generic RRI text is present.
7. A known exact owner must open directly without Graphify, Context7, or semantic
   recall.

Expected: no forbidden primary route; adjacent skill may appear only as an
explicit handoff justified by crossed scope.

### Optional-tool-absent scenario

Run one geometry, one Rerun, and one Zarr prompt with Graphify stale and external
documentation tooling unavailable.

Expected: the agent opens exact local owners, reports unavailable external
evidence literally, and completes local-only work or stops at the precise API
evidence blocker. It never treats optional tooling as authority.

## Observability and evidence

Each workpackage records a compact evidence table in its PR/debrief:

| Field | Required value |
| --- | --- |
| Baseline revision | exact SHA |
| Candidate revision | exact SHA |
| Changed owner paths | explicit list |
| Positive/near-miss cases | pass/fail and selected primary route |
| Observed probe paths | JSONL/tool-event skill and owner paths beneath the probe worktree; mismatches fail |
| Owner dispositions | counts plus unresolved rows |
| Focused commands | command and exit status |
| Optional-tool state | absent/configured/healthy/fresh, stated literally |
| Invocation disposition | mode, autonomous-reach evidence, leading word, branches |
| Probe isolation | validated strict-child target, worktree/catalog diff, fresh-process command, JSONL plus structured output, narrow forced-disposal proof |
| Retired-skill consumers | classified exact-head inventory, zero unexplained live references, atomic rollback bundle |
| Merger interaction | consumer-dependency graph, fixed application order, combined result, one rollback result per selected merger |
| Unrelated dirty paths | unchanged proof |
| Retained/replaced/removed/deferred/open | explicit list |

Do not publish a composite quality score. Report dimensions separately.

## Final verification sequence

1. Confirm the exact worktree/branch/head and scoped diff.
2. Run `quick_validate.py` for every changed skill.
3. Run reduced `make scaffold-audit` and `make scaffold-audit-self-test`.
4. Run `make check-agent-memory` and Agents DB validation if backlog state changed.
5. Run owner-specific package tests and Typst compile only for moved meaning.
6. Execute the tiny shared smoke plus every affected skill/pair-local positive,
   near-miss, handoff, and tool-absent case.
7. Run `git diff --check` and verify unrelated dirty paths are unchanged.
8. Obtain an independent reviewer verdict that all removed facts have owners and
   all scoped invocation branches remain usable, whether routed through separate
   identifiers or an approved survivor.
9. Verify exact-head hosted CI where applicable.

## Stop conditions

Stop and keep the affected workpackage unmerged when:

- any removed fact has no allowed live owner;
- a positive route disappears or a near miss becomes ambiguous;
- a validator passes only by reintroducing semantic keyword machinery;
- owner migration changes scientific meaning rather than relocating it;
- the diff captures unrelated user/agent work;
- Rerun contract references are deleted before package ownership and focused
  tests are present.
- the clean-baseline preflight is red or the approved plan/reviews are not frozen
  at the selected revision.
