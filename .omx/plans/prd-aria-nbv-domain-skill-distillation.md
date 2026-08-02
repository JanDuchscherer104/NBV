---
kind: ralplan-prd
status: approved
slug: aria-nbv-domain-skill-distillation
mode: deliberate-consensus
amended: 2026-08-01
requirements_owner: .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
context: .omx/context/aria-nbv-domain-skill-distillation-20260801T083021Z.md
---

# PRD: ARIA-NBV domain-skill distillation

## Outcome

Determine, through bounded comparisons, which of the nine scoped skill
identifiers still earn independent invocation. Every scoped skill has three
possible survival dispositions: retain a separately distilled minimal skill,
merge into a minimal adjacent procedure, or route the branch through existing
guidance/procedure and prune the skill. The planning hypothesis is that all nine
remain useful as thin procedural front doors, but retention is an evidence-gated
disposition rather than a fixed outcome. Remove the obsolete
`python-docstrings` compatibility router and move every domain/scientific/
implementation claim out of skill bodies and skill references according to the
claim-type-to-owner matrix below.

The target is not a smaller skill count. The target is predictable invocation,
small loaded context, one owner per meaning, and capability-preserving deletion.

## Requirements summary

1. Treat the accepted scaffold specification as the requirements authority and
   this plan as sequencing only
   (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:14-30`).
2. Keep skills procedural: activation, owner localization, ordered work,
   handoff, evidence, verification, and a checkable completion condition. Keep
   scientific and implementation facts in exact owners
   (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:169-210`).
3. Apply the `writing-great-skills` model:
   - the description is the model-facing invocation pointer;
   - one trigger per genuine branch, without synonym lists;
   - universal steps stay inline;
   - branch-only reference loads through a precise pointer;
   - split or merge only when invocation or sequence proves the boundary;
   - run relevance, no-op, duplication, sediment, and sprawl checks.
4. Preserve every independently useful outcome before deleting a compatibility
   route, nested reference, metadata field, or validator behavior
   (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:572-604`).
5. Respect the existing dirty worktree. The staged deletion of
   `.agents/skills/python-docstrings/SKILL.md` is pre-existing user-owned work;
   execution must isolate it into its own review unit or preserve it untouched.

## Scope

### In scope

- The nine named `SKILL.md` entrypoints and their existing `agents/openai.yaml`
  files.
- The staged retirement of `python-docstrings` and its live routing consumers.
- The Rerun skill's four nested reference files.
- Owner migration needed to make skill deletion/distillation truthful.
- The custom skill metadata/style/audit surface needed to remove duplicated
  trigger and authority metadata.
- A tiny shared routing/capability smoke set plus workpackage-local comparisons.

### Out of scope

- Python runtime behavior changes, scientific-method changes, new experiments,
  or thesis-claim changes beyond relocating already accepted current meaning.
- Broad mega-skill consolidation. Bounded pairwise merger hypotheses and their
  candidate descriptions/branch maps are in scope; an implementation merge is a
  later destructive workpackage only if its comparison passes.
- General cleanup of `python-standards`, `typst-authoring`, `agent-behavior`,
  `aria-nbv-context`, or unrelated skills.
- Rewriting historical transcripts, debriefs, resolved records, or archived
  evidence merely because they mention a retired skill.
- A general routing evaluator, dashboard, ontology, transcript processor, or
  semantic scoring framework.
- Resolving the accepted specification's open Graphify or external-skill-policy
  decisions.

## RALPLAN-DR

### Principles

1. **One meaning, one owner.** A skill points to a fact; it never settles the
   fact.
2. **Invocation earns identity.** Retain a skill only when its trigger and work
   path are independently useful.
3. **Progressive disclosure follows branches.** Load universal procedure now;
   load specialist detail only when that branch is actually taken.
4. **Capability before deletion.** Freeze positive, near-miss, handoff, and
   optional-tool-absent behavior before removing an owner or route.
5. **One concern, one proof.** Every workpackage has one responsibility shift,
   a focused baseline/candidate comparison, and a rollback boundary.

### Decision drivers

1. Eliminate domain-truth drift between skills and current thesis/code owners.
2. Reduce prompt/context and maintenance load without degrading invocation or
   handoff behavior.
3. Keep the cleanup reviewable in a dirty brownfield repository.

### Viable options

#### Option A — body-only distillation under the current custom metadata schema

Keep all custom fields (`triggers`, `canonical_sources`, `tool_refs`, and so on),
move domain prose out of bodies, and leave `scaffold_audit.py` structurally
unchanged.

Pros:

- smallest immediate diff;
- preserves current lexical fixtures and generated metadata consumers;
- low migration risk.

Cons:

- retains 46-57 frontmatter lines per scoped skill;
- keeps descriptions, trigger lists, body `When To Use`, and UI prompts as
  competing invocation statements;
- retains a 994-line custom validator whose size and semantic heuristics conflict
  with the accepted tiny-smoke-set direction;
- leaves `canonical_sources` and `must_read` as overlapping owner inventories.

#### Option B — native-first metadata plus owner-first procedural distillation

Make `name` and a tight `description` the scoped skill frontmatter. Put only the
ordered procedure, exact owner pointers needed on every run, branch-specific
context pointers, handoffs, verification, and completion criterion in the body.
Update existing UI metadata only when the visible trigger changes. Reduce the
custom audit to structural/path checks and retain routing behavior as a tiny
baseline/candidate smoke set rather than lexical scoring.

Pros:

- matches the actual Codex skill discovery surface and `writing-great-skills`;
- removes duplicated trigger and authority inventories;
- makes each loaded skill legible and branch-driven;
- exposes missing owners instead of hiding them behind skill references;
- creates a path to delete most custom audit machinery.

Cons:

- requires a schema/audit transition before individual skills can land green;
- demands focused behavioral evidence because lexical fixtures no longer stand
  in for invocation quality;
- owner gaps, especially Rerun, must be filled first.

#### Option C — adjacent pairwise mergers

Test the strongest plausible pairwise mergers rather than a straw-man mega-skill:

| Pair | Strongest merged candidate | Tension to test | Planning assessment |
| --- | --- | --- | --- |
| Review + diagnosis | “Investigate ARIA changes or failures and return evidence-ranked findings” with diff and symptom branches | A diff review can finish without reproduction; causal diagnosis must reproduce before mutation | Separate is likely more predictable; merge only if both positive and near-miss prompts preserve their different completion criteria |
| Target-RRI + rollout | “Validate target-conditioned gain semantics and finite-candidate multi-step evaluation” | Label/visibility meaning is upstream of rollout budgets/policies | Separate with an explicit handoff is likely safer; merge risks loading rollout policy for local label work |
| Dataset + Zarr | “Operate or change ARIA persisted stores” with operation and storage-implementation branches | Existing-store health versus writer/API/layout change | Plausible merger, but it must distinguish rebuild/manifest operations from codec/concurrency/API work in every trial |
| Geometry + Rerun | “Validate or visualize ARIA spatial contracts” with semantic and observer branches | Geometry changes settle frame meaning; Rerun should only observe it | Separate is likely required to keep display-only transformations from becoming semantic changes |

`docs-curator` versus `typst-authoring` is a required boundary/handoff comparison,
not a merger candidate. `typst-authoring` is outside this cleanup scope and has
no paired destructive workpackage; WP7 may narrow `docs-curator` and prove the
handoff but may not modify, merge, or retire `typst-authoring`.

Pros:

- can remove descriptions only where adjacent branches truly share one leading
  word and completion criterion;
- tests the strongest realistic consolidation candidates.

Cons:

- each merger expands the loaded branch surface;
- combined rollback affects two currently independent task outcomes;
- a successful description match may still hide premature completion or wrong
  owner selection inside the merged body.

#### Option D — route-only fallback and pruning

Remove a scoped skill when truth removal leaves only pointers or handoffs and
the same branch can be reached predictably through the nearest `AGENTS.md`,
module README, code structure/Graphify navigation, or an existing procedural
skill.

Pros:

- removes a model-visible description that no longer buys independent procedure;
- avoids turning skills into a parallel routing index;
- lets repository structure and owning guidance perform normal localization.

Cons:

- can weaken autonomous reach if the replacement route is implicit or broad;
- requires the same exact-consumer and rollback proof as a merger.

### Decision

Choose a **staged Option B** as the target and test Options C and D in WP0.
The current planning recommendation is to retain the nine identifiers because
their leading words, owners, and completion criteria differ, but each retention
must be confirmed by a symmetric comparison of a separately distilled minimal
candidate, a minimal merged candidate where applicable, and a route-only/prune
candidate. The legacy body is frozen as evidence only; it cannot be the sole
separate-skill candidate. A merger or prune is viable only when it preserves
every branch and near miss with no broader owner load; inconclusive evidence
retains the separately distilled skill. Use Option A as the rollback state if the
dual-schema/native-first transition cannot preserve current behavior.

## Target skill contract

Each retained scoped skill should have:

1. `name` and one concise model-facing `description` with one trigger per genuine
   branch.
2. Owner-localization behavior that starts from repository structure, the
   nearest `AGENTS.md`/module README, and the exact code or Typst owner for the
   active branch. Keep an unconditional pointer only when every branch needs it;
   otherwise place it beside the branch that uses it.
3. One ordered procedural path whose steps end in observable criteria.
4. A small branch map only where tasks genuinely diverge.
5. Adjacent handoffs stated at the decision point, not repeated in metadata,
   overview, and conclusion.
6. The narrowest verification route and a checkable completion condition.
7. No formulas, version values, schema tables, roadmap gates, comprehensive
   command inventories, or domain invariants that can drift independently of
   code/docs. Minimal stable commands required to execute or verify the
   procedure may remain; CLI options and semantics, schemas, versions, defaults,
   and command catalogues stay with CLI help, Make, code, README, or `AGENTS.md`.
8. No skill-local file presented as a source of domain authority.

`agents/openai.yaml` remains optional UI metadata. Existing files are updated to
match changed trigger scope; missing files are not created merely for symmetry.
A skill that becomes only pointers or handoffs after truth removal has no
independent procedural value and must be compared against route-only/prune.

## Skill dispositions

The table below records provisional retention candidates, not predetermined
survivors. WP0 must assign every one of the nine scoped skills exactly one final
disposition: `retain`, `merge`, or `route-only/prune`. A route-only candidate
must identify the nearest existing guidance or procedure that preserves the
branch and must pass the same consumer, invocation, completion, and rollback
checks as a merger. `python-docstrings` remains the already-decided prune outside
that nine-skill comparison.

| Skill | Disposition | Independent invocation | Distill or move | Exact owner family |
| --- | --- | --- | --- | --- |
| `code-review-aria-nbv` | Keep and distill | Concrete ARIA diff/review-feedback evaluation with owner-grounded severity findings | Remove generic harness, GitHub lifecycle, repeated trigger list, severity duplication, and domain encyclopedia; keep establish-surface → read owner → validate finding → report | Root/nearest `AGENTS.md`; exact diff/tests; root review contract (`AGENTS.md` routing and review rules) |
| `counterfactual-rollout-planner` | Keep and distill | Finite-candidate rollout/Q_H evidence and comparison planning | Move M/RQ gates, complexity, sampling-policy facts, trace schema, and actor/oracle semantics; keep budget/evidence checklist and handoffs | `docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ`, `04-05-finite-candidate-value-model.typ`, `05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ`; `aria_nbv/aria_nbv/rollouts/{AGENTS.md,README.md,replay/,trace.py,zarr_store.py}` |
| `dataset-cache-ops` | Keep and distill | Operating/validating downloads, shards, immutable stores, and rebuild decisions | Move current class/config names, dataset version, manifest schema, migration mechanics, exact command catalogue; keep inspect → validate → choose rebuild/mutation branch → verify | `aria_nbv/aria_nbv/data_handling/{AGENTS.md,README.md,vin_store/}` and CLI help/source docstrings |
| `diagnose-aria` | Keep and distill | Symptom-driven ARIA causal loop | Remove Streamlit/data/docs command catalogue and repeated domain list; keep reproduce → minimize → rank falsifiable hypotheses → vary one factor → regression proof → remove probes | Root/nearest `AGENTS.md`, exact failing code/test/CLI, and owning module README/docstrings |
| `docs-curator` | Keep but narrow | Quarto, bibliography, navigation, and public/internal boundary curation | Remove Typst authoring trigger and Typst compile recipes; hand off Typst narrative/notation/rendering to `typst-authoring`; keep source-role check, boundary, render, completion | `docs/AGENTS.md`, `docs/typst/thesis/sections/`, and bibliography owner; exact public docs source |
| `entity-aware-rri` | Keep and distill | Target/entity selection and target-specific RRI evidence boundary | Move V0/V1, OBS-SEL/PRED-Q/GT-EVAL, invalidity, formula, and roadmap meaning; keep identify owner → classify actor/oracle/eval evidence → validate target support → verify | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`, `04-method/04-03-candidate-and-replay-contract.typ`; `aria_nbv/aria_nbv/rri_metrics/{AGENTS.md,README.md,returns.py}` and target/oracle code |
| `nbv-geometry-contracts` | Keep and distill | Cross-module pose/camera/frame/shape/unit contract verification | Move frame meanings, CW90 behavior, camera-resolution conventions, and diagnostic assertions; keep evidence tuple and focused test selection | `aria_nbv/AGENTS.md`, exact geometry/rendering/data-view source docstrings, and `docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ` |
| `rerun-nbv-inspector` | Keep after owner migration; aggressively distill | Rerun-specific observer/logging artifact workflow | Move `nbv-inspector-contract.md` domain contract into package README/nearest guide/docstrings; delete fixed entity trees and API fact tables from skill references; retain current-official-doc lookup only as a conditional step | New `aria_nbv/aria_nbv/rerun_inspector/README.md` and, if repeated local hazards justify it, nested `AGENTS.md`; public code docstrings/tests; geometry/data owners |
| `zarr-python` | Keep and distill | Zarr API/layout/codec/store/concurrency changes, distinct from store operation | Move local responsibilities, helper names, schema/layout facts, and implemented migration semantics; keep localize owner → consult current official docs if nontrivial → smallest change → round trip | `aria_nbv/pyproject.toml`; `aria_nbv/aria_nbv/{data_handling,rollouts}/{AGENTS.md,README.md}`; `zarr_store.py` and VIN-store source/docstrings/tests |
| `python-docstrings` | Prune | None beyond forwarding to `python-standards` | Preserve the already-staged deletion; verify no live consumer and keep `python-standards` as the active procedure | `python-standards`, `aria_nbv/AGENTS.md`, and public code docstrings |

## Invocation and leading-word dispositions

`writing-great-skills` is an external operator reference for predictable skill
design, not repository authority. Before metadata conversion or merger, WP0 must
freeze this disposition for each scoped skill:

| Skill | Invocation mode | Evidence autonomous reach is required | Leading word | Independent description branches |
| --- | --- | --- | --- | --- |
| `code-review-aria-nbv` | Model-invoked | Root review routing and review-feedback tasks must select it without `$code-review-aria-nbv`; it hands off only when reproduction is needed | Review | working-tree/PR diff; follow-up finding validation |
| `counterfactual-rollout-planner` | Model-invoked | Rollout/Q_H work is routed from task content and entity-RRI handoffs | Plan | counterfactual rollout; finite-candidate Q_H comparison |
| `dataset-cache-ops` | Model-invoked | Dataset/store operation prompts and Zarr handoffs must reach it autonomously | Operate | downloads/shards/meshes; store validation/rebuild; manifests/storage smoke |
| `diagnose-aria` | Model-invoked | Root symptom/failure routing and review handoffs must enter the causal loop without an explicit skill name | Diagnose | failing command/metric/UI/docs/data symptom |
| `docs-curator` | Model-invoked | Root docs routing must distinguish Quarto/navigation/public-boundary work from Typst authoring | Curate | Quarto/navigation; bibliography; public/internal boundary |
| `entity-aware-rri` | Model-invoked | Target/entity task content and rollout/geometry handoffs must localize target semantics autonomously | Target | entity selection; target-specific labels/diagnostics |
| `nbv-geometry-contracts` | Model-invoked | Pose/camera/frame/shape changes and Rerun/target handoffs must reach semantic verification | Geometry | pose/frame; projection/backprojection; shapes/units |
| `rerun-nbv-inspector` | Model-invoked | Rerun artifact and rollout-inspection requests must select the observer path without explicit invocation | Inspect | offline sample; rollout-Zarr; entities/sinks; frame display |
| `zarr-python` | Model-invoked | API/layout/codec/store/concurrency changes must be distinguished autonomously from operating an existing store | Change Zarr | API/store; layout/chunk/codec; concurrency/migration |

Model-invoked means autonomous and explicit user reach are both preserved. A
skill may become user-invoked only through a separately reviewed scope change
with evidence that neither repo routing nor another skill needs autonomous reach;
this plan proposes none. For each passing merger, the WP0 comparison must also
prove that the survivor identifier and description retain a discoverable leading
word for every absorbed branch. Explicit review, target-RRI, Zarr, or Rerun
prompts becoming less discoverable fails the merger; do not add compatibility
aliases merely to make a candidate pass.

## Owner-preparation requirements

### Claim-type-to-owner matrix

| Claim type | Allowed authoritative owner |
| --- | --- |
| Scientific definitions, formulas, and interpretation | Shared or thesis Typst, or the exact external primary source |
| Executable behavior, types, shapes, schemas, versions, and defaults | Code, active configuration, public docstrings, and tests |
| Durable subsystem orientation and usage | The owning module README |
| Invariants, hazards, routing, and verification | The nearest `AGENTS.md` |
| Repeatable procedure | The smallest skill that demonstrably improves predictability |

README and `AGENTS.md` are not generic sinks for scientific definitions or
implementation truth. Owner migration must classify the claim first, then use
the narrowest row above.

Skill edits must not create an ownership vacuum. Before removing a fact from a
skill, classify it as one of:

- **already owned** — link to the exact current Typst/code/README/AGENTS owner;
- **move** — add and verify the fact in the smallest allowed owner in a
  prerequisite owner-only review unit; remove it from the skill only after that
  prerequisite lands;
- **derived procedure** — rewrite it as an action/evidence/completion step;
- **stale** — delete it with exact-source evidence;
- **open** — leave the skill edit blocked and record the owner gap through Agents
  DB rather than inventing authority.

Required gaps to resolve first:

1. Create a durable Rerun subsystem owner under
   `aria_nbv/aria_nbv/rerun_inspector/` before deleting
   `references/nbv-inspector-contract.md`.
2. Move implemented rollout-Zarr meaning out of the draft
   `aria_nbv/aria_nbv/rollouts/zarr_contract.md` into `zarr_store.py` docstrings
   and `rollouts/README.md`; move planned scientific meaning into Typst or delete
   stale draft content.
3. Replace Quarto roadmap/theory owner pointers in counterfactual and entity-RRI
   skills with active Typst-section and code owners. Missing current content is a
   thesis-owner migration, not permission to leave the skill authoritative.
4. Ensure exact diagnostic and operational commands are discoverable in nearest
   `AGENTS.md`, module README, CLI `--help`, or Make targets before deleting them
   from skills.

Each destructive skill workpackage also carries an ephemeral procedural-
capability disposition:

```text
skill + branch | retained | replaced | removed | deferred | open | comparison evidence
```

This table covers every branch removed from descriptions, bodies, references, or
metadata. It is PR evidence, not a new tracked authority registry. At minimum,
Rerun accounts for offline samples, rollout-Zarr inspection, candidates/frusta
and validity, RGB/depth/cameras, OBB/mesh/trajectory logging, sink modes, current
official-API lookup, and geometry handoff. Dataset operations account for
downloads, shards/meshes, immutable-store validation, version/rebuild decisions,
split/manifests, storage estimates, and smoke checks.

## Metadata and audit distillation

### Target

- Make `description` the sole model-invocation statement.
- Remove duplicated `metadata.triggers` and body `When To Use` lists.
- Remove custom authority/tool registries from scoped skill frontmatter.
- Put exact owner pointers and branch conditions next to the step that uses them.
- Keep UI metadata human-facing and non-authoritative.

This is a repository-wide target, not permission for this scoped plan to weaken
unconverted skills.

### Transition

1. Introduce two explicit profiles:
   - `legacy-structured`: current metadata remains fully validated whenever it is
     present;
   - `native-minimal`: `name`/`description` frontmatter plus body owner pointers,
     handoffs, evidence, verification, and completion.
2. Update the direct consumer and live policy owners for that transition
   together:
   `.agents/references/source_order.md`, `.agents/skills/README.md`, root routing
   where necessary, `scripts/scaffold_audit.py`,
   `scripts/tests/test_agent_governance_g002.py`, and the fixture schema. Preserve
   Make/CI as callers and verification gates; edit them only if fresh evidence
   shows their command contract must change.
   `scripts/quarto_generate_agent_docs.py` is a verified non-consumer and remains
   unchanged unless fresh exact-source evidence proves otherwise.
3. Add one temporary audit-owned discriminator,
   `NATIVE_MINIMAL_SKILLS`, containing only explicitly converted skill
   identifiers. Absence of legacy metadata does not imply conversion. A skill
   outside this set must satisfy the complete legacy schema; partial or absent
   legacy metadata fails. A skill inside the set must satisfy the native-minimal
   contract and is not required to reconstruct removed custom fields.
4. Update `NATIVE_MINIMAL_SKILLS` and one converted skill atomically in each
   one-skill workpackage. Its rollback reverts both changes. The set is a
   temporary scaffold-migration mechanism, not a domain registry or authority
   surface, and is deleted with the legacy schema only after full migration.
5. Make `description` the sole activation statement immediately for converted
   skills. Retire lexical trigger scoring only for those skills; do not weaken
   unrelated legacy validation.
6. Keep `scripts/scaffold/fixtures/routing.json` as the tiny human-readable smoke
   specification and execute predefined baseline/candidate native Codex probes
   per destructive workpackage.
7. Delete the remaining global custom metadata machinery only in a later plan
   after all skills and consumers transition. This scoped work must not claim
   repository-wide metadata retirement.

## Workpackages and pull-request boundaries

### Execution preflight — clean baseline gate

Before WP0, freeze or track the approved PRD, test specification, handoff, and
approving amendment reviews at a selected revision. Create or select a clean,
dedicated worktree at that revision; record its branch/head and classify every
unrelated dirty path before proceeding. The preflight passes only when the
dedicated baseline is clean and `make scaffold-audit`,
`make scaffold-audit-self-test`, and `make check-agent-memory` all exit zero.
Graphify freshness is recorded, but stale Graphify routes discovery to exact
sources rather than invalidating an otherwise clean baseline. No WP0 evidence
may be collected from the current dirty primary worktree.

### WP0 — Freeze behavior and evaluate pairwise mergers

Owner: scaffold verification.

- Add missing positive/near-miss fixtures for counterfactual rollout,
  dataset-cache operation, and both offline and rollout-Zarr Rerun inspection.
- Record the invocation-mode/leading-word matrix above, including autonomous
  reach evidence, description branches, and survivor-name discoverability.
- Retain the existing `python-docstring-contract` expectation of
  `python-standards`.
- Freeze one legacy observation lane, then draft separately distilled minimal
  candidates, minimal merged candidates for the four Option C pairs, and
  route-only/prune candidates for every scoped skill. Compare those candidates
  symmetrically in the disposable probe setup without editing the primary
  worktree. Separately prove the docs-curator/Typst handoff boundary.
- Keep the shared smoke set to owner discovery, progressive disclosure,
  diagnostic routing, and exact-source fallback. Run the remaining positive,
  near-miss, and handoff probes only for the skill or pair whose identity is at
  stake. Use repeated trials only when stochastic invocation materially decides
  retain/merge/prune; declare that reason and count before inspecting results.
- Retain a separate pair only when the merger has any wrong primary owner,
  forbidden activation, broader must-read set, or weakened completion criterion.
- If a pair passes every fixed comparison, replace the two corresponding
  single-skill workpackages below with one merged-pair workpackage that preserves
  both branch contracts and has one independent rollback. If it fails any
  comparison, retain both identifiers and execute their two single-skill
  workpackages unless a route-only/prune candidate independently passes for one
  of them. A passing route-only/prune candidate suppresses that one-skill
  distillation package and replaces it with an atomic consumer/routing removal
  package with independent rollback. An inconclusive result defaults to retaining
  the separately distilled skill. No skill may execute more than one disposition.
- Materialize each passing merger from this fixed substitution matrix; it is
  execution evidence attached to WP0, not a new authority registry:

| Pair | Survivor and retired identifier | Required prerequisites retained | Suppressed individual packages | Atomic conversion and rollback | Required comparison coverage |
| --- | --- | --- | --- | --- | --- |
| Review + diagnosis | Keep `diagnose-aria`; retire `code-review-aria-nbv` | WP2 | WP5 and WP6 | Add only `diagnose-aria` to `NATIVE_MINIMAL_SKILLS`, replace its body, retire the peer, and rewrite the consumer bundle below; rollback restores both legacy skills/consumers and removes the survivor from the set | U1-U5b, I1-I2, I5, positive prompts 1/4 and review/diagnosis near misses |
| Target-RRI + rollout | Keep `counterfactual-rollout-planner`; retire `entity-aware-rri` | WP2, WP4A, WP4B | WP8 and WP9 | Add only the survivor to `NATIVE_MINIMAL_SKILLS`, consume both verified fact-owner prerequisites, retire the peer, and rewrite its consumer bundle atomically; rollback restores both legacy skills/consumers and removes the survivor from the set | U1-U4/U5b/U6b, I1-I5, positive prompts 2/6 and target/rollout near misses |
| Dataset + Zarr | Keep `dataset-cache-ops`; retire `zarr-python` | WP2 and WP3 | WP10 and WP11 | Add only the survivor to `NATIVE_MINIMAL_SKILLS`, preserve dataset and rollout storage handoffs, retire the peer, and rewrite its consumer bundle atomically; rollback restores both legacy skills/consumers and removes the survivor from the set | U1-U5b/U6, I1-I3/I5, positive prompts 3/10 and dataset/Zarr near misses |
| Geometry + Rerun | Keep `nbv-geometry-contracts`; retire `rerun-nbv-inspector` | WP2, WP3, WP4 | WP12 and WP13 | Add only the survivor to `NATIVE_MINIMAL_SKILLS`, consume verified Rerun/read-model owners, delete/demote references, retire the peer, and rewrite its consumer bundle atomically; rollback restores both legacy skills/references/consumers and removes the survivor from the set | U1-U6, I1-I3/I5, both Rerun positives, geometry positive, and geometry/Rerun near misses |

  A passing merged package remains skill-only except for its atomic audit
  discriminator and live routing/UI/backlog consumers. It consumes owner
  prerequisites; it never edits Typst, package code, README, or AGENTS truth
  owners except a routing-only `AGENTS.md` reference required to replace the
  retired identifier.

  The current consumer bundles to inventory again at the exact execution head
  are:

  - review/diagnosis: root `AGENTS.md`, `aria-grill`, `diagnose-aria`, the
    Matt Pocock adapter manifest, routing fixtures, and survivor UI metadata;
  - target-RRI/rollout: `code-review-aria-nbv`,
    `counterfactual-rollout-planner`, `nbv-geometry-contracts`, routing/audit
    fixtures, current `.agents/issues.toml`/`.agents/todos.toml` references, and
    survivor UI metadata;
  - dataset/Zarr: `dataset-cache-ops`, routing fixtures, and survivor UI metadata;
    `/zarr-developers/zarr-python` remains an external library identifier, not a
    skill consumer;
  - geometry/Rerun: `code-review-aria-nbv`, `dataset-cache-ops`, `diagnose-aria`,
    `nbv-geometry-contracts`, the conditional Typst visualization handoff,
    routing fixtures, current `.agents/todos.toml` references, and survivor UI
    metadata.

  The exact-head inventory classifies each match as `atomic consumer`,
  `retired self-subtree`, `historical evidence`, or `domain/library homonym`.
  Atomic consumers are patched in the candidate and merged workpackage;
  self-subtrees retire with the peer; historical evidence and genuine homonyms
  remain with a written rationale. Backlog changes use `agents-db`. The merged
  workpackage must reach zero live skill-identifier/path consumers after those
  justified exclusions and must revert the entire consumer bundle together.
- No live skill or owner edits.

#### Disposable native candidate-probe protocol

1. Record the baseline SHA, model, Codex version/config profile, primary-worktree
   status, complete model-visible skill/tool catalog, digest of the baseline
   `.agents/skills` inventory, and every pre-existing path from
   `git worktree list --porcelain`.
2. Create a detached temporary worktree at that SHA at the explicit child
   `<new-mktemp-parent>/probe`. Resolve the parent and resolve the not-yet-created
   child with `realpath -m` (or an equivalent parent-relative comparison); require
   the probe path to be a strict child of the newly created parent and unequal to
   every pre-existing worktree before adding or modifying it.
   Reproduce only intentional baseline skill-state differences needed by WP0;
   do not copy unrelated dirty files from the primary worktree.
3. Keep the legacy pair unchanged only in the observation lane. Build separate
   candidate lanes for the two separately distilled minimal skills, the fixed
   minimal merger, and each applicable route-only/prune fallback. Candidate lanes
   update the temporary audit discriminator/fixtures and every exact live
   routing/UI/current-backlog consumer required by their disposition. Require a
   scoped tracked-reference search to return zero unexplained live consumers of
   every retired identifier/path. Store candidate patches, output schema, JSONL,
   and last messages outside both worktrees as ephemeral comparison evidence.
4. Launch each prompt in a new process with no resume state, using the same model
   and config in both lanes. The executable shape is:

   ```text
   codex --ask-for-approval never exec --ephemeral --ignore-user-config \
     -m <recorded-model> \
     --json --output-schema <probe-schema.json> \
     -o <last-message.json> -C <detached-probe-worktree> \
     --sandbox read-only <prompt> > <events.jsonl>
   ```

   The output schema requires selected primary, branch, first owner opened,
   handoff, completion evidence, false activations, and the selected skill source
   path. Ignoring user config holds configured MCP/plugin differences constant
   while the detached repository still supplies its local guidance/skills; it
   does not claim to eliminate built-in tools or every user-global skill. Record
   and compare the complete effective catalog/tool namespaces in every lane. For
   the optional-tool-absent case, require the relevant external documentation
   namespaces to be absent and Graphify to be recorded stale/unavailable in both
   lanes; otherwise the trial is blocked rather than relabeled.
5. Run one fresh deterministic process for the tiny shared smoke and each
   affected pair-local case. Repeat only a predeclared identity-decisive
   stochastic invocation case. Do not tune candidate text, prompts, schema,
   model, trial count, or pass bars after seeing output.
6. Treat observed JSONL/tool events as authoritative over the final-response
   self-report. Require the event stream to show the actual skill and owner paths
   opened beneath the disposable worktree. A reported path outside the probe,
   an unobserved claimed open, or any mismatch between structured/final output
   and observed events fails the trial. Also prove every retired identifier is
   absent from that worktree's model-visible inventory.
7. Confirm and capture that the temporary worktree diff contains only the
   candidate disposition, its temporary discriminator/fixture changes, and its exact
   classified atomic consumer bundle. Revalidate the exact strict-child target,
   then dispose only that known dirty target with:

   ```text
   git worktree remove --force -- <validated-probe-worktree>
   test ! -e <validated-probe-worktree>
   rmdir -- <validated-empty-mktemp-parent>
   ```

   Do not run repository-wide `git worktree prune`. Re-list worktrees and prove
   every pre-existing path remains. The primary worktree status/digest must match
   its baseline.

Exit evidence includes commands, exit status, structured outputs, exact temporary
diff, disposal proof, and baseline-versus-candidate comparison. It is not copied
into a tracked truth surface.

#### Combined passing-set and rollback gate

If two or more pairwise mergers pass, WP0 must not approve them independently
until their actual combined state passes this bounded gate:

1. Build an ephemeral consumer-dependency graph whose nodes are only the passing
   mergers and whose edges mean their patches touch the same live consumer file
   or one survivor consumes the other's retired identifier. Fix application
   order by owner prerequisites first and substitution-table order for ties.
2. In one disposable candidate, instantiate all passing substitutions and their
   classified consumer bundles in that order. Run the complete positive,
   near-miss, handoff, optional-tool, catalog, and zero-unexplained-reference
   checks against the combined state.
3. Represent each substitution as its own temporary commit using repository-local
   throwaway Git author settings, not operator-global identity. For each passing
   merger, create a separate validated strict-child rollback-probe worktree at
   the combined commit and run `git revert --no-commit <that-merger-commit>` while
   every other merger remains applied. Re-run the affected full branches and
   consumer search. The reverted pair uses its separate-skill expected primaries,
   while every other pair keeps its merged expectations. The restored legacy
   skill/consumers must coexist with every still-retired identifier and must not
   overwrite another merger's changes.
4. Dispose each rollback probe with the same narrow forced-removal protocol. Do
   not reset or restore the primary worktree and do not run global prune.
5. If the combined state or any individual rollback fails, record the implicated
   component or component union, reject every merger in it, and retain those
   separate skills. Non-overlapping passing components may proceed. Rebuild and
   re-run the final accepted combined set once; an inconclusive rerun retains the
   implicated component union.

This tests only the selected passing set plus at most one rollback per selected
merger (four), not every theoretical subset. The graph, application order,
temporary commits, and results are ephemeral WP0 evidence, not repository truth.

Exit: each retain/merge/route-only-prune disposition has bounded symmetric
comparison evidence;
the baseline fails when an expected route, branch, handoff, or fallback is lost;
the candidate fails when its survivor name/description weakens any absorbed
branch's autonomous reach; and the accepted combined set proves independent
rollback while the other accepted mergers remain applied.

### WP1 — Retire `python-docstrings`

Owner: Python guidance routing.

- Isolate the existing staged deletion into a one-file review unit.
- Prove no live dispatcher, skill, hook, Make target, guide, config, or generated
  UI metadata points to it.
- Verify the docstring prompt routes to `python-standards` in every predeclared
  trial.
- Leave historical evidence untouched.

Exit: deletion is consumer-complete and independently reversible.

### WP2 — Add the dual-schema compatibility bridge

Owner: skill scaffold mechanics.

- Update the direct consumer and policy owners named in the metadata section;
  preserve Make/CI callers unless their command contract actually changes.
- Continue strict legacy validation when metadata is present; add the
  `native-minimal` path only for identifiers explicitly named in the temporary
  `NATIVE_MINIMAL_SKILLS` set.
- Do not convert the nine live skills in this PR.
- Preserve `make scaffold-audit`, `make scaffold-audit-self-test`, and CI as
  meaningful gates without inventing a new semantic evaluator.

Exit: minimal and legacy fixtures both pass; invalid YAML, name/path mismatch,
missing description, broken declared pointer, malformed fixture, an unlisted
metadata-absent skill, partial legacy metadata, legacy metadata regression, and
retired live identifier fail; an explicitly allowlisted native-minimal fixture
passes.

### WP3 — Prepare rollout/Zarr ownership

Owner: `aria_nbv.rollouts`.

- Disposition `zarr_contract.md` claim by claim into implemented code/docstrings,
  `rollouts/README.md`/`AGENTS.md`, active scoped Typst, stale, or open.
- Audit `rollouts.read_model` against direct interpretation in
  `rerun_inspector/_rollout_zarr.py`.
- Complete any interpretation migration only as a separately approved package
  behavior change; otherwise record it open and keep owner prose literal.
- Add focused read-model/rollout-inspection tests for the actual current boundary.
- No skill edits.

Exit: implemented versus planned rollout meaning has exact owners, and the
read-model/Rerun seam is either proven complete or explicitly open.

### WP4 — Prepare the Rerun subsystem owner

Owner: `aria_nbv.rerun_inspector`.

- Create/update module `README.md`, nearest `AGENTS.md` only if local hazards
  justify it, and public code docstrings/tests for both offline-sample and
  rollout-Zarr inspection.
- Map all former `nbv-inspector-contract.md` facts and all procedural branches.
- Do not delete skill references or distill the skill yet.

Exit: non-skill owners cover retained offline and rollout inspection contracts
without claiming closure of an open read-model seam.

### WP4A — Prepare counterfactual-rollout fact owners

Owner: active thesis sections and `aria_nbv.rollouts`.

- Disposition every roadmap, formula, trace, sampling, actor/oracle, and
  comparison fact currently held only by `counterfactual-rollout-planner`.
- Add and verify missing current scientific meaning in the smallest active Typst
  section; executable meaning in rollout code/config/docstrings/tests; durable
  subsystem orientation/usage in the module README; and invariants, hazards,
  routing, or verification in the nearest `AGENTS.md`.
- Record stale or open claims literally; do not edit the skill in this package.

Exit: every fact later removed by WP8 already has a verified allowed owner, is
stale with evidence, or remains open and therefore blocks its removal.

### WP4B — Prepare entity-RRI fact owners

Owner: active thesis sections and target/RRI package code.

- Disposition every target/entity, actor/oracle/evaluation, invalidity, formula,
  and roadmap fact currently held only by `entity-aware-rri`.
- Add and verify missing current scientific meaning in the smallest active Typst
  section; executable meaning in target/RRI code/config/docstrings/tests; durable
  subsystem orientation/usage in the module README; and invariants, hazards,
  routing, or verification in the nearest `AGENTS.md`.
- Record stale or open claims literally; do not edit the skill in this package.

Exit: every fact later removed by WP9 already has a verified allowed owner, is
stale with evidence, or remains open and therefore blocks its removal.

### WP5 — Distill `code-review-aria-nbv`

Owner: ARIA review procedure.

- Remove duplicated generic harness/GitHub mechanics and domain catalogue.
- Preserve concrete diff establishment, exact-owner grounding, finding
  validation, severity ordering, output shape, and review/diagnosis handoff.

Exit: all review branches and near misses pass every predeclared trial; one-skill
rollback.

### WP6 — Distill `diagnose-aria`

Owner: ARIA diagnostic procedure.

- Remove the domain/command catalogue after owner discoverability is proven.
- Preserve reproduce, minimize, falsifiable hypotheses, one-variable probes,
  regression evidence, cleanup, and review handoff.

Exit: all diagnostic branches and near misses pass every predeclared trial;
one-skill rollback.

### WP7 — Narrow `docs-curator`

Owner: docs curation procedure.

- Restrict to Quarto/bibliography/navigation/public-boundary work.
- Route Typst authoring/render QA to `typst-authoring`.
- Remove duplicated QMD taxonomy and commands already owned by `docs/AGENTS.md`.

Exit: Quarto and Typst prompts choose the correct primary in all trials; one-skill rollback.

### WP8 — Distill `counterfactual-rollout-planner`

Owner: finite-candidate rollout procedure.

- Depend on WP4A and consume its verified owner dispositions; do not modify
  thesis, code, README, or AGENTS truth owners in this workpackage.
- Remove or rewrite only facts whose prerequisite disposition permits it.
- Preserve budgets/evidence comparison, target-RRI handoff, and rollout completion
  criteria without retaining roadmap/formula truth.

Exit: rollout branches/near misses pass; one-skill rollback.

### WP9 — Distill `entity-aware-rri`

Owner: target-RRI procedure.

- Depend on WP4B and consume its verified owner dispositions; do not modify
  thesis, code, README, or AGENTS truth owners in this workpackage.
- Remove or rewrite only facts whose prerequisite disposition permits it.
- Preserve actor/oracle/evaluation classification, target support/invalidity
  evidence, geometry and rollout handoffs, and focused proof.

Exit: target branches/near misses pass; one-skill rollback.

### WP10 — Distill `dataset-cache-ops`

Owner: dataset/store operation procedure.

- Remove implementation/version/schema facts after exact owner proof.
- Preserve downloads, shards/meshes, store validation, version/rebuild decision,
  manifest/split/storage estimates, smoke checks, and Zarr handoff.

Exit: every procedural branch is retained/replaced/removed explicitly and passes its comparison; one-skill rollback.

### WP11 — Distill `zarr-python`

Owner: storage implementation procedure.

- Remove local schema/helper/API facts after WP3 owner proof.
- Preserve local owner discovery, conditional current official-doc evidence,
  smallest change, round trip, and dataset/rollout handoffs.

Exit: API/layout positives and operation near misses pass; one-skill rollback.

### WP12 — Distill `nbv-geometry-contracts`

Owner: geometry verification procedure.

- Move/remove frame and camera facts only after exact AGENTS/code/Typst proof.
- Preserve frame/direction/shape/unit evidence, focused verification, and Rerun/
  target/rollout handoffs.

Exit: semantic geometry and display-only near misses pass; one-skill rollback.

### WP13 — Distill `rerun-nbv-inspector`

Owner: Rerun observer procedure.

- Depend on WP3 and WP4.
- Delete or demote all four skill-local references according to factual and
  procedural capability dispositions.
- Preserve offline samples, rollout-Zarr, candidate/validity, RGB/depth/camera,
  OBB/mesh/trajectory, sink modes, official-API lookup, and geometry handoff.

Exit: every Rerun branch and near miss passes every predeclared trial; no
skill-local domain
authority; one-skill rollback.

### WP14 — Final cross-surface reconciliation

Owner: scaffold integration.

- Run the complete smoke set and all local comparisons.
- Verify merged workpackages already changed and can independently revert every
  required dispatcher/UI/backlog consumer. Repair of a required retired-skill
  consumer is not deferred to WP14; reopen the originating workpackage instead.
- Update only genuinely deferred, non-atomic follow-up whose state changed and
  is not required for a skill deletion/merger to be live-consumer complete.
- Leave historical evidence intact and record unresolved owner gaps explicitly.
- Scope owner assertions to facts removed from these skills; do not resolve the
  broader Typst/Quarto open decision.

Exit: all acceptance criteria and verification gates pass at the exact PR head.

## Acceptance criteria

1. Every one of the nine skill identifiers has exactly one recorded
   retain/merge/route-only-prune disposition from a symmetric comparison of
   separately distilled minimal, minimal merged where applicable, and route-only
   candidates. A retained identifier maps to a distinct procedural branch; a
   merger or prune preserves every branch, near miss, owner load, and completion
   criterion in the predeclared trials. Legacy bodies are observation baselines,
   not the separate candidate.
2. `python-docstrings/SKILL.md` is absent and no live tracked consumer outside
   history/archive/runtime artifacts references its identifier or path.
3. Every surviving retained or merged scoped skill has minimal valid frontmatter,
   one concise description, bounded ordered procedure, branch-local owner
   localization, focused verification, and a checkable completion condition. A
   route-only/pruned skill instead passes the absence and replacement-route gates.
4. No scoped skill or skill-local reference is presented as authority for a
   scientific fact, implementation contract, formula, version, schema, roadmap
   gate, or domain invariant.
5. Every removed factual sentence has an explicit `already owned`, `move`,
   `stale`, or `open` disposition with a resolvable allowed owner.
6. `docs-curator` no longer claims general Typst authoring; dataset-cache versus
   Zarr, geometry versus Rerun, entity-RRI versus rollout, and review versus
   diagnosis remain distinguishable by positive and near-miss probes.
7. The Rerun package has a non-skill contract owner before the authoritative
   skill reference is deleted.
8. The dual-schema audit strictly validates unconverted legacy metadata and the
   native-minimal contract only for explicitly allowlisted converted skills.
   Metadata absence never selects the native profile. It adds no replacement
   semantic evaluator; routing/capability behavior is demonstrated by the
   bounded smoke set rather than lexical overlap scores.
9. No new dependency, top-level skill, reference handbook, generated truth
   surface, or general evaluator is added.
10. Each workpackage passes its focused tests, `make check-agent-memory`, reduced
    scaffold checks, `git diff --check`, and exact-head CI where applicable.
11. Each PR records retained, replaced, removed, deferred, and open capabilities
    and can be reverted independently.
12. Any merged workpackage includes its exact live routing/UI/current-backlog
    consumer bundle, reaches zero unexplained live references to the retired
    skill identifier/path, and restores the full bundle on rollback.
13. When multiple mergers pass pairwise, their selected combined state and one
    rollback per selected merger pass the full affected smoke/consumer checks;
    a failed interaction conservatively retains its connected component.
14. Execution begins only from a frozen clean dedicated baseline with tracked
    approved planning artifacts and green scaffold audit, scaffold self-test,
    and agent-memory validation.

## Pre-mortem

### Failure 1 — a skill looks cleaner because its only surviving owner was deleted

Early signal: a removed sentence can be found only in Git history or a skill-local
reference; a new pointer names a nonexistent or draft owner.

Mitigation: claim-level owner disposition before skill edits; block the edit when
the replacement owner cannot be opened and verified.

### Failure 2 — metadata removal silently degrades invocation/handoffs

Early signal: positive prompts select generic or adjacent skills; near-miss prompts
activate both data/storage or geometry/Rerun branches; UI defaults describe the old
scope.

Mitigation: freeze native baseline outputs in WP0; change one boundary at a time;
run positive, near-miss, handoff, and tool-absent probes before and after.

### Failure 3 — cleanup recreates the overgrown validator in another form

Early signal: new token scorers, tool registries, synonym lists, fixture engines,
or dashboards appear; validation LOC grows while tested behavior remains lexical.

Mitigation: cap the validator's responsibility, not its score; use existing native
runs and focused tests; reject machinery without a demonstrated recurring stable
failure.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Existing dirty/staged work is folded into a broad commit | Path-scoped status/diff before every workpackage; WP1 owns only the existing deletion |
| Typst/Quarto source-order conflict | Accepted spec and current Typst include graph govern current thesis; unresolved gaps remain explicit |
| Fixed commands removed before discoverability exists | Confirm nearest AGENTS/README/CLI/Make owner first; otherwise retain a precise procedural pointer temporarily |
| Rerun API guidance stales | Query current official docs only on API-change branches; keep local invariant in code/README/tests |
| Mixed old/new metadata confuses audit | WP2 explicitly supports the transition and lands before scoped skill conversions |
| PRs become too broad | Split any workpackage whose diff crosses an independent owner or rollback boundary |

## ADR

### Decision

Treat retention of all nine scoped domain skills as the leading hypothesis, test
separately distilled minimal skills against the four strongest in-scope pairwise
mergers and route-only/prune fallbacks plus the docs/Typst handoff, retire
`python-docstrings`, migrate domain
truth to exact owners before deletion, and transition converted skills through a
dual-schema bridge to native-first descriptions plus bounded bodies and tiny
behavioral evidence.

### Drivers

- accepted single-ownership and progressive-disclosure requirements;
- distinct invocation value across the nine skills;
- high maintenance/context cost and semantic drift in current metadata/bodies;
- destructive-cleanup risk in a dirty brownfield repository.

### Alternatives considered

- Body-only pruning under current metadata: safe but retains the core duplication.
- Adjacent pairwise merging: fewer descriptions where two branches can genuinely
  share owner load and completion criteria, but unsafe when either route broadens.

### Why chosen

Pairwise evidence keeps the identity decision fair. Native-first distillation
then removes the duplicated index for retained/merged candidates, while
owner-first sequencing prevents a shorter skill from becoming a deletion of
knowledge.

### Consequences

- More initial work is spent proving owners and routing behavior.
- The skill count is determined by bounded pairwise evidence and is expected,
  but not required, to remain largely unchanged.
- Scoped skill bodies and metadata become substantially smaller.
- Some current nested references are deleted; legacy validator logic remains
  until its consumers transition, while converted paths stop depending on it.
- Owner gaps become explicit package/thesis work rather than skill prose.
- Pointer-only survivors are removed when repository structure, nearest guidance,
  or an existing procedure preserves the branch with equal predictability.

### Follow-ups

- Apply the same native-first audit to remaining skills only after this scoped
  set demonstrates preserved behavior.
- Consider broader module README symbol-matrix cleanup separately; do not attach
  it to skill distillation.
- Record unresolved owner gaps through Agents DB.

## Available agent types and staffing guidance

Available relevant roles: `explore`, `analyst`, `planner`, `architect`, `critic`,
`executor`, `writer`, `test-engineer`, `verifier`, `code-reviewer`,
`code-simplifier`, and `git-master`.

Recommended execution staffing:

- Leader / Ultragoal owner: `planner` or main leader, medium/high reasoning, owns
  dependency order and checkpoint ledger.
- Owner migration lanes: two `executor` agents, medium reasoning, split strictly
  between docs/Typst owners and package/code owners.
- Skill distillation lane: one `writer` or `executor`, high reasoning, owns only
  scoped skill files and UI metadata.
- Verification lane: one `test-engineer`, medium reasoning, owns fixtures and
  focused checks.
- Independent gate: one `verifier` or `code-reviewer`, high reasoning, validates
  each completed workpackage against owner/capability evidence.
- Final cleanup: optional `code-simplifier`, high reasoning, only after behavior
  is green and only on the changed scaffold code.

## Goal-mode follow-up suggestions

- Default: `$ultragoal` with this PRD and its test specification as the durable
  sequential ledger.
- Parallel delivery: combine `$ultragoal` with `$team` after WP0/WP2 establish
  stable boundaries; Team supplies checkpoint-ready evidence, Ultragoal owns
  completion state.
- `$ralph` is an explicit fallback only for one persistent single-owner
  workpackage such as WP2 or WP7; it is not the default for the multi-owner plan.
- `$autoresearch-goal` and `$performance-goal` do not fit this implementation
  plan because the deliverable is neither research evidence nor performance
  optimization.

## Team launch hints and verification path

After explicit execution approval:

```text
$ultragoal .omx/plans/prd-aria-nbv-domain-skill-distillation.md
$team 3:executor "Implement the next dependency-ready workpackages from .omx/plans/prd-aria-nbv-domain-skill-distillation.md using .omx/plans/test-spec-aria-nbv-domain-skill-distillation.md; preserve unrelated work and return exact owner/test evidence."
```

Team proves the workpackage-local owner migration, focused behavior comparison,
changed-skill validation, and clean scoped diff before stopping. Ultragoal records
those outputs as durable checkpoints and does not close until the independent
final verifier confirms the complete acceptance criteria at the exact head.

## Applied review improvements

- Iteration 1 Architect: changed the native-first migration to a dual-schema
  compatibility bridge that preserves strict validation for unconverted skills.
- Iteration 1 Architect: added credible adjacent pairwise merger hypotheses and
  predefined comparison evidence before final keep/merge dispositions.
- Iteration 1 Architect: split owner preparation from every one-skill rollback
  unit.
- Iteration 1 Architect: added the `rollouts.read_model` / Rerun interpretation
  seam, offline plus rollout-Zarr owner preparation, and explicit Rerun branches.
- Iteration 1 Architect: added ephemeral procedural-capability dispositions and
  three-trial routing comparisons.
- Iteration 1 Architect: scoped Typst-only assertions to facts removed from these
  skills without resolving the accepted global Typst/Quarto open decision.
- Iteration 2 Architect: made native-minimal conversion explicit through a
  temporary audit-owned identifier set with atomic per-skill rollback and
  negative fixtures for absent or partial legacy metadata.
- Iteration 2 Architect: made counterfactual and entity-RRI truth migration
  owner-only prerequisites and made WP0 suppress either the merged-pair package
  or its two individual packages according to fixed comparison evidence.
- Iteration 3 Architect: kept docs/Typst handoff-only and added a fixed per-pair
  substitution matrix with inherited owner prerequisites, survivor/retirement
  identifiers, atomic discriminator rollback, tests, and inconclusive-retain
  behavior.
- Iteration 4 Architect: made the final smoke oracle branch-conditioned so a
  passing merger must preserve retired-skill capabilities through its fixed
  survivor rather than fail an identifier-only expectation.
- Critic iteration 1: corrected the metadata-consumer inventory, added explicit
  model-invocation/leading-word dispositions, and made WP0 candidate comparisons
  executable through isolated ephemeral Codex runs in a detached worktree.
- Critic iteration 2: made live routing/UI/current-backlog consumer rewrites part
  of each candidate, merged workpackage, and rollback; WP14 now verifies atomic
  completeness instead of repairing a broken retired-skill dispatch surface.
- Consensus loop 3 Architect: added a bounded combined passing-set gate and one
  isolated rollback probe per selected merger so overlapping handoff consumers
  cannot invalidate independent rollback.
- Final Critic: approved the exact-head consumer bundles, zero-unexplained-
  reference gate, combined passing-set interaction test, independent rollback
  probes, owner-first sequencing, and complete verification/staffing handoff.
- 2026-08-01 amendment: added retain/merge/route-only-prune dispositions,
  symmetric minimal-candidate comparison, claim-type ownership, branch-local
  localization, stable-command bounds, event-authoritative probe evidence, a
  tiny shared smoke policy, and the clean-baseline execution preflight.
- 2026-08-01 Architect/Critic amendment gate: approved after making the handoff
  consensus state sequential and pending until the Critic verdict; implementation
  remains `NO-GO` until the clean-baseline gate passes.
