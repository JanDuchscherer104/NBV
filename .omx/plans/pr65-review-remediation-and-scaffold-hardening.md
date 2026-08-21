---
kind: plan
status: proposed
created: 2026-08-21
target: PR #65
---

# PR #65 review remediation and scaffold hardening

## Outcome

Resolve every still-valid finding in `pr65-review-gpt56pro.md`, preserve the
native-minimal skill direction, and publish one exact-head PR #65 state that is
rebased onto current `origin/main`, behaviorally checked, provenance-safe, and
accurately described.

The target architecture remains deliberately thin:

```text
root AGENTS.md
  -> universal safety and primary dispatch
nearest nested AGENTS.md
  -> local hazards, owner boundaries, focused proof
skill frontmatter
  -> name plus one high-signal activation description
selected SKILL.md
  -> invocation-wide invariants, neutral branch selectors, completion
focused reference or script
  -> branch-specific procedure, versions, examples, deterministic operations
exact owner
  -> source, tests, config, Typst, bibliography, or primary source
validation
  -> static integrity lint plus bounded fresh-agent behavior trials
```

Every durable fact has one exact owner. Other surfaces state only when and how
to reach it.

## Current evidence and constraints

- The review was written against remote PR head
  `3433ebf9fcb73d098cb2af18ebf7e780bc7f741e`; the remediation worktree is now
  at local head `c26c9fbb02baf4908fd100fad14645587e214626`, one commit ahead of the
  published branch.
- After fetching on 2026-08-21, `origin/main` is
  `3a6ff491fadb19c20af3d876ae4734e138804ee9`. The branch is 14 commits ahead and
  8 behind. A merge-tree check reports conflicts only in
  `.agents/skills/aria-nbv-context/SKILL.md` and
  `.agents/skills/typst-authoring/SKILL.md`.
- Current `main` requires new debriefs to carry
  `codex_thread: codex://threads/<thread-id>` and supplies the canonical
  `make new-debrief ... CODEX_THREAD_ID=...` route
  (`origin/main:.agents/memory/README.md:28-40`). The branch validator does not
  yet enforce that field (`scripts/validate_agent_memory.py:39-47,264-320`).
- The accepted target state explicitly distinguishes lexical routing fixtures
  from behavior evaluation and forbids a general evaluator framework,
  dashboard, transcript processor, or composite scoring engine
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:515-538,723-745`).
- Official OpenAI documentation establishes that `codex exec` supports
  ephemeral non-interactive runs, a read-only default sandbox, JSONL event
  output, and schema-constrained final output. Use those native surfaces for a
  bounded manual smoke runner rather than building an evaluation platform:
  <https://learn.chatgpt.com/docs/non-interactive-mode>.
- Graphify is currently `unusable` in this worktree because the projected index
  parent is missing or unsafe. Until the worktree bootstrap repairs that state,
  Graphify is navigation-unavailable and exact-source inspection remains the
  authority. A usable/fresh Graphify state is a publication gate, not evidence
  for any source claim.
- Preserve unrelated work. Do not broaden this scaffold PR into package-runtime
  or scientific-behavior changes. Keep `agent-behavior/SKILL.md` compact and do
  not restore the rejected sentence “Load only detail that materially improves
  the decision or proof.”

## Finding disposition

| Finding | Current verdict | Planned resolution |
|---|---|---|
| 1. New debrief contract | Valid, open | Rebase, backfill verified thread provenance for every PR-created 2026-08-21 debrief, document a date-based grandfather boundary, and enforce it with focused tests. |
| 2. Context7 hierarchy | Valid, open | Make Graphify, Context7, semantic recall, context-map lookup, local-code lookup, known-owner handoff, and failure handoff sibling selectors under one neutral branch index. |
| 3. Durable-workpackage trigger | Valid, partially repaired | Keep the restored selector label, but make the imperative explicit: “After completing a durable workpackage, or before staging…”; add a no-Git-wording behavior trial. |
| 4. Declaration-only routing suite | Valid, open | Retain static fixtures as lint and add a small manual read-only fresh-agent trial runner with prompt/rubric separation and raw evidence capture. |
| 5. Pointer validator gaps/escape | Valid, open | Replace Markdown-only extraction with one bounded repository-pointer parser and strict root containment. |
| 6. Hard-coded skill registry | Valid, open | Validate structurally discovered custom skills; retain only the explicit pinned-upstream Graphify exemption. |
| 7. Oracle owner drift | Valid, open | Replace the broad Oracle route with scorer, evidence, DTO, and orchestration leaves backed by exact source and focused tests. |
| 8. Geometry/Zarr owner collapse | Valid, open | Split pose generation, rendering geometry, VIN geometry, rollout Zarr, and immutable VIN-store routes. |
| 9. Volatile evidence in accepted spec | Valid, open | Keep the durable amendment and remove run counts, temporary paths, chronology, and environment anecdotes; dated debriefs own execution evidence. |
| 10. Historical provenance rewrite | Valid and broader than the two examples | Restore every pre-existing debrief modified only to replace retired paths; permit those paths only in byte-identical cutover records. Keep the migration receipt's explicit current-destination mapping. |
| Stale PR body | Valid, open | Rewrite against the final rebased head and actual checks; remove obsolete head, counts, source-order, Graphify, and Context7 wording. |

## Architecture decisions

### A. Keep branch selection neutral and one-hop

`aria-nbv-context/SKILL.md` keeps the owner hierarchy, conflict rule, capture
rule, one neutral branch index, and completion contract. Each branch selector
links directly to at most one focused reference or exact owner. Context7 does
not become the parent of local lookup, semantic recall, or failure routing.
Exact Context7 IDs remain solely in
`references/context7_library_ids.md`; Graphify state/provenance remains solely
in `references/graphify-aria-boundary.md`.

### B. Separate declarations, observations, and policy

- `scripts/scaffold/fixtures/routing_prompts.jsonl` becomes the single owner for
  trial IDs and raw prompt text. It contains no expected owners or answers.
- `scripts/scaffold/fixtures/routing.json` becomes the deterministic static
  rubric keyed by the same IDs: exact owner paths, expected/forbidden tools, and
  required/forbidden outcomes, but no duplicate prompt text.
- The static audit requires a one-to-one ID join between prompts and rubric.
- A manual runner invokes fresh, ephemeral, read-only Codex sessions and stores
  raw JSONL plus schema-constrained final reports under ignored
  `.agents/work/routing-trials/<head>/`.
- Automated checks validate only objective shape/event facts. An independent
  verifier compares the raw trace and final report with the frozen rubric. No
  aggregate score, optimizer, dashboard, transcript database, or CI/network
  prerequisite is introduced.

### C. Treat exact-owner pointers as integrity edges, not authority

The pointer validator checks whether explicit local pointers resolve safely and
exist. It does not turn repository links into a second source graph. Only
`references/*.md` links participate in the progressive-disclosure reachability
graph; source/config/test/Typst/directory links are integrity-checked leaves.

### D. Preserve historical records; map current owners elsewhere

Completed debriefs are immutable evidence. Restore the four pre-existing
debriefs changed by this branch to their cutover blobs:

- `.agents/memory/history/2026/06/2026-06-17_advisor_deck_source_of_truth_autoresearch.md`
- `.agents/memory/history/2026/06/2026-06-17_advisor_deck_source_of_truth_patch.md`
- `.agents/memory/history/2026/08/2026-08-01_compositional_mempalace_corpus_and_gpu_runtime.md`
- `.agents/memory/history/2026/08/2026-08-01_pr45_graphify_review_remediation.md`

Add the former source-order index to the retired-source set, but accept
it only when the current record is byte-identical to the existing retirement
cutover blob (`scripts/validate_agent_memory.py:147-186`). Do not append modern
successor links to frozen records; the current hierarchy and migration receipt
already map active ownership.

### E. Keep skill discovery structural

Every `.agents/skills/*/SKILL.md` discovered as ARIA-owned is validated. Remove
the 11-entry `APPROVED_CUSTOM_SKILL_PATHS` registry and its equality test
(`scripts/scaffold_audit.py:21-36,451-458`;
`scripts/tests/test_agent_governance_g002.py:17-26,183-185`). Graphify remains a
single named upstream exemption because its version marker and byte-identity
tests are an integrity contract, not a general membership allowlist.

## Workpackages

### WP0 — Rebase onto current `origin/main` and preserve current owners

1. Fetch `origin/main` again immediately before execution and record its exact
   SHA; rebase `codex/context-surface-reduction` onto that ref.
2. Resolve the two known content conflicts without restoring rich frontmatter:
   - in `aria-nbv-context/SKILL.md`, keep native-minimal frontmatter and the
     branch architecture in WP2 while porting main's Typst-first notation rule:
     shared `symbols.typ`/`equations.typ` bodies and metadata are authoritative;
     `docs/notation.yml` is a generated cross-format adapter;
   - in `typst-authoring/SKILL.md`, keep native-minimal progressive disclosure
     and port main's rules for `#eqs.*`, reusable symbols/equations, and local
     dummy variables.
3. Inspect every auto-merged guidance, memory, Makefile, script, and docs file;
   do not accept conflict resolutions solely because Git merged them.

Acceptance:

- `git merge-base --is-ancestor origin/main HEAD` succeeds.
- `git merge-tree --write-tree origin/main HEAD` reports no conflicts.
- Only intended files differ, and the worktree is clean before WP1.
- The rebase introduces no rich skill frontmatter and preserves current main's
  debrief/thread and Typst notation contracts.

### WP1 — Repair debrief provenance and evidence ownership

Files:

- `.agents/memory/README.md`
- `scripts/validate_agent_memory.py`
- focused validator tests under `scripts/tests/`
- the four PR-created 2026-08-21 debriefs
- the four restored pre-existing debriefs listed in Decision D
- `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`

Actions:

1. Adopt an explicit grandfather boundary: native debriefs dated before
   `2026-08-21` and `status: legacy-imported` records remain historical;
   non-legacy records dated on or after `2026-08-21` require a valid
   `codex_thread: codex://threads/<UUID>`.
2. Recover, rather than guess, the originating task IDs for:
   - `2026-08-21_pr65_review_and_graphify_0948.md`
   - `2026-08-21_source_order_pointer_retirement.md`
   - `2026-08-21_g004_native_minimal_frontmatter_rationale.md`
   - `2026-08-21_agent_behavior_invariant_restoration.md`
   Never copy one thread ID across records without provenance evidence.
3. Extend `check_history_records()` to reject missing or malformed thread URIs
   on/after the cutoff. Add tests for a grandfathered record, a valid current
   record, a missing field, a malformed/non-UUID URI, and unchanged legacy
   imports.
4. Restore the four pre-existing debriefs byte-for-byte and extend retired-path
   validation as described in Decision D. Add a regression proving an active or
   modified record cannot smuggle a retired path while an unchanged cutover
   record remains valid.
5. Edit the branch-added accepted amendment in place
   (`...target-state.md:1113-1178`): retain the durable ownership, frontmatter,
   Context7, Graphify, and progressive-disclosure decisions at
   `:1113-1131`; delete fixed counts, old heads, temporary environments,
   chronology, CUDA anecdotes, and stale check totals at `:1133-1178`. State
   only that verification belongs in dated debriefs and fresh exact-head runs.

Acceptance:

- `make check-agent-memory` passes.
- Focused debrief-thread and retired-record tests pass.
- `git diff origin/main --` shows no content change in the four restored
  historical debriefs.
- No accepted specification paragraph claims a fixed test count, temporary
  path, environment diagnosis, or “final” review state.

Commit boundary: one focused provenance/evidence commit after the checks pass.

### WP2 — Repair selectors and exact owner routing

Files:

- `.agents/skills/agent-behavior/SKILL.md`
- `.agents/skills/aria-nbv-context/SKILL.md`
- `.agents/skills/aria-nbv-context/references/context_map.md`
- `scripts/scaffold/fixtures/routing.json`
- focused governance tests

Actions:

1. Replace the separate Graphify/Context7 heading hierarchy at
   `aria-nbv-context/SKILL.md:53-86` with one neutral branch index whose sibling
   selectors are Graphify, Context7, reviewed semantic recall, derived context
   map, unknown local code lookup, already-known owner, and concrete failure.
   Keep direct links and one-hop disclosure; do not create another index file.
2. Change `agent-behavior/SKILL.md:47-50` to say:
   “After completing a durable workpackage, or before staging, committing,
   pushing, changing a pull request, publishing review comments, retargeting,
   or releasing, read `references/external-actions.md`.” Preserve all restored
   general invariants and keep the skill below its current 100-line comfort
   bound.
3. Replace the broad Oracle RRI row in `context_map.md:27` with narrow leaves
   grounded in the package's own symbol matrix
   (`aria_nbv/aria_nbv/oracle/README.md:43-106`):
   - shared scorer engine -> `oracle/_scoring.py`;
   - evidence construction -> `oracle/evidence.py`;
   - scene scorer -> `oracle/scene_rri.py`;
   - target scorer -> `oracle/target_rri.py`;
   - result DTOs -> `oracle/labels.py`;
   - generation/orchestration -> `oracle/pipelines/`;
   - rendering semantics -> rendering owners only when the prompt concerns
     rendering.
4. Split `routing.json:13,16-17` into prompt-specific owner fixtures. Every
   expected route names the defining source, nearest applicable guide, and
   focused test:
   - Oracle scorer/evidence/DTO/pipeline leaves;
   - pose/candidate generation (`pose_generation/`);
   - projection/backprojection (`rendering/`);
   - VIN candidate-frame inputs (`vin/AGENTS.md`, `vin/geometry/`);
   - rollout Zarr/Q (`rollouts/AGENTS.md`, `rollouts/zarr_store.py`, rollout
     tests; ownership contract at `rollouts/AGENTS.md:9-18,32-37`);
   - immutable VIN stores (`data_handling/AGENTS.md`, `vin_store/`, focused
     store tests; ownership contract at `data_handling/AGENTS.md:9-32`).
5. Keep `agents/openai.yaml` metadata unchanged unless the final skill
   activation description changes. Do not add UI metadata to skills that do not
   already own it.

Acceptance:

- Static fixtures contain no Oracle route that treats `labels.py` as scorer
  logic or `pipelines/` as the scorer implementation.
- No geometry fixture maps all pose, rendering, and VIN geometry to one guide.
- No storage fixture conflates rollout stores with immutable VIN datasets.
- Static governance and scaffold-audit checks pass.
- Fresh-agent trials in WP5 prove Context7 is forbidden for local lookup,
  known-owner, semantic-recall, and failure prompts, and prove workpackage
  completion activates the external-actions branch without Git vocabulary.

Commit boundary: one focused routing/owner-map commit.

### WP3 — Harden repository-pointer validation

Files:

- `scripts/scaffold_audit.py`
- `scripts/tests/test_agent_governance_g002.py`
- scaffold-audit self-tests

Actions:

1. Replace `local_markdown_pointers()` and `resolve_markdown_pointer()`
   (`scaffold_audit.py:284-334`) with a small `RepositoryPointer` parser/resolver
   used by both audit and governance tests.
2. Recognize explicit Markdown links and unambiguous backticked repository
   paths. Cover the current owner families, including `.md`, `.qmd`, `.typ`,
   `.tex`, `.bib`, `.py`, `.toml`, `.yaml`, `.yml`, `.json`, `.jsonl`, and
   `.sh` files plus explicit directories. Accept repo-root families such as
   `.agents/`, `.omx/`, `aria_nbv/`, `docs/`, `scripts/`, skill-relative
   `references/`, and explicit `./`/`../` paths.
3. Exclude URLs, `mailto:`, commands, placeholders, and glob expressions. Do not
   treat arbitrary prose tokens as paths.
4. Preserve missing explicit pointers so they fail validation. Resolve first,
   then require `resolved.is_relative_to(ROOT_RESOLVED)` before any existence or
   anchor check.
5. Validate Markdown heading anchors with the existing slug logic and Typst
   labels for explicit `path.typ#label` pointers. Do not invent unstable symbol
   anchor syntax for Python/TOML/YAML.
6. Keep progressive-disclosure reachability limited to custom-skill Markdown
   reference nodes; exact-owner leaves receive integrity checks only.
7. Add positive probes for valid directory and Typst-label pointers, and
   negative probes for missing Markdown/Typst/Python targets, missing directory,
   malformed Markdown anchor, malformed Typst label, and `../../` escape.

Acceptance:

- Every required negative probe fails for the intended reason.
- Existing valid references and the upstream Graphify boundary still pass.
- The parser has one resolution/containment path rather than file-type-specific
  escape rules.
- Scaffold self-tests, governance tests, Ruff, and `git diff --check` pass.

Commit boundary: one focused pointer-integrity commit.

### WP4 — Remove the custom-skill membership registry

Files:

- `scripts/scaffold_audit.py`
- `scripts/tests/test_agent_governance_g002.py`

Actions:

1. Delete `APPROVED_CUSTOM_SKILL_PATHS` and the discovered-equals-approved
   assertion. Continue deriving `CUSTOM_SKILLS` from structural discovery.
2. Validate every discovered ARIA-owned entrypoint for minimal frontmatter,
   directory/name parity, references, line budget, tools, and semantic leakage.
3. Retain one explicit Graphify path exemption tied to `.graphify_version` and
   existing upstream byte-identity tests; do not introduce a generic exemption
   list.
4. Add a temporary-fixture self-test showing that a newly discovered valid
   custom skill is audited without editing validator source.

Acceptance:

- Adding a structurally valid temporary skill does not require a registry edit.
- A malformed newly discovered skill fails the same checks as existing skills.
- Graphify remains byte-identical to its pinned 0.9.48 upstream bundle.
- Focused governance, upstream Graphify integrity, and scaffold-audit tests pass.

Commit boundary: one focused structural-discovery commit. WP3 and WP4 may share
one commit only if the final diff remains a single coherent audit refactor.

### WP5 — Add bounded behavioral routing trials

Files/artifacts:

- `scripts/scaffold/fixtures/routing_prompts.jsonl` (prompt-only inputs)
- a small manual runner such as `scripts/scaffold/run_routing_trials.py`
- one JSON Schema for final trial reports
- ignored `.agents/work/routing-trials/<head>/` raw evidence
- a dated debrief containing only the bounded summary and artifact paths

Actions:

1. Freeze prompts before executing them. `routing_prompts.jsonl` is the only
   owner of prompt text and contains only ID plus task; expected owners,
   forbidden routes, and grading language remain exclusively in `routing.json`
   and are never injected into the tested prompt. The two files must have
   identical unique ID sets.
2. Use `codex exec --ephemeral --sandbox read-only --json`, schema-constrained
   final output, and a detached checkout of the exact candidate head. Capture
   Codex version, model/effort, commit, loaded guides, selected skill, opened
   references, tool calls, exact owner, handoff, selected verification, outcome,
   and token/context usage.
3. Keep the runner orchestration-only: no policy inference, model tuning,
   aggregate scoring, dashboard, persistent transcript database, or normal-CI
   network dependency.
4. Cover only changed/high-risk routes:
   - Context7 external API positive route;
   - local lookup, known-owner, semantic recall, and failure Context7 negatives;
   - workpackage completion without Git vocabulary;
   - Oracle scorer/evidence/DTO/pipeline disambiguation;
   - pose versus rendering versus VIN geometry;
   - rollout Zarr versus immutable VIN-store routing.
5. For each family include the smallest useful set of explicit trigger,
   implicit trigger, near miss/forbidden route, correct handoff, and completion
   trial. Do not mechanically multiply every prompt into six cases when one
   paired trial proves multiple boundaries.
6. Have a verifier review raw JSONL against the frozen rubric after execution.
   Record pass/fail per case and exact failure evidence; do not collapse results
   into a composite score.

Acceptance:

- Prompt-only inputs contain no expected path, skill, tool, or outcome text.
- Every trial is ephemeral and read-only; the detached checkout remains clean.
- Raw JSONL and final structured reports identify the exact tested commit and
  runtime surface.
- All changed-route trials pass, or publication stops with the failing prompt
  and trace preserved.
- Normal `make scaffold-audit` and CI remain hermetic and do not invoke Codex or
  require network access.

Commit boundary: one focused smoke-runner/fixture commit. Raw run artifacts stay
ignored; the bounded dated debrief is committed after successful execution.

### WP6 — Repair Graphify bootstrap and run exact-head verification

1. Run the repository worktree bootstrap owner
   (`scripts/setup_worktree_env.sh`) first, then
   `python3 scripts/check_graphify_freshness.py --json`.
2. Require `usable: true` before eligible Graphify-backed navigation. If setup
   leaves the graph unusable, diagnose the bootstrap/projection owner and fix it
   only if the defect is in this branch; otherwise record the exact external
   blocker and do not claim Graphify verification.
3. When usable, run a bounded upstream `graphify query` for the scaffold routing
   architecture and verify every consequential result against exact files.
4. Run validation in increasing scope:
   - `python3 scripts/scaffold_audit.py --self-test`
   - focused governance, pointer, skill-discovery, memory, ownership, and
     Graphify tests
   - `make check-agent-memory`
   - `make scaffold-audit`
   - changed Python Ruff checks and `git diff --check`
   - the repository's Root Verification / `make ci` route for the exact rebased
     head, with any environment-only gap stated literally.
5. Re-run `git merge-tree --write-tree origin/main HEAD` after all changes and
   confirm the tested head remains based on current `origin/main`.

Acceptance:

- Graphify reports usable and its pinned upstream integrity checks pass.
- All changed-contract checks are green with fresh output.
- Hosted Root Verification runs against the final PR head and then-current
  `origin/main`, not an older synthetic merge.
- Worktree status is clean after each committed workpackage and at handoff.

### WP7 — Refresh PR #65 and resolve review state

1. Push the rebased branch with `--force-with-lease` only after all local exact-
   head gates pass and after rechecking the expected remote old head.
2. Rewrite the PR body to state:
   - final head and current `origin/main` base;
   - actual changed-file/commit surface;
   - native-minimal frontmatter and neutral branch architecture;
   - complete retirement of the former source-order index;
   - Graphify 0.9.48 and its verified state;
   - `@Context7` plugin ownership and Docker-MCP deprecation;
   - exact fresh static, behavioral, memory, Graphify, and hosted checks;
   - explicit remaining gaps, if any.
3. Resolve each review finding only after linking it to the final-head patch and
   evidence. Do not reuse pre-rebase counts or hosted runs.
4. Verify via GitHub that PR #65 targets `main`, its remote head equals the
   locally tested head, required checks are green, and no actionable review
   thread remains open.

Acceptance:

- The PR body describes the actual final branch; it contains no obsolete SHA,
  old Graphify version, retained-source-order claim, Docker-MCP Context7 route,
  or stale test count.
- Remote PR head equals local `HEAD`; base is `main`; merge-tree and hosted
  verification are green for that pair.
- Every valid finding has a patch/evidence response, and no unresolved comment
  is silently dismissed.

## Verification matrix

| Contract | Primary proof | Secondary proof |
|---|---|---|
| Rebase/current main | ancestor check and merge-tree | GitHub base/head identity |
| Debrief thread provenance | focused validator tests | `make check-agent-memory` |
| Historical immutability | cutover blob/hash comparison | retired-record negative tests |
| Neutral branch selection | fresh-agent forbidden/positive trials | static route/pointer lint |
| Workpackage trigger | no-Git-wording fresh-agent trial | exact selector assertion |
| Oracle/geometry/storage owners | focused paired trials | exact owner/source/test fixtures |
| Pointer safety | missing/type/anchor/escape probes | governance and audit self-tests |
| Structural skill discovery | temporary-skill probes | Graphify exemption integrity tests |
| Progressive disclosure | loaded-reference trace per trial | one-hop reference graph audit |
| Graphify availability | freshness JSON plus bounded query | exact-source verification |
| Publication | hosted Root Verification | final PR body/thread audit |

## Risks and mitigations

- **Remote drift during implementation:** fetch and record `origin/main` at WP0
  and again before publication; repeat merge-tree and hosted verification.
- **Invented debrief provenance:** stop and report a specific record if its
  originating task cannot be proven; never fabricate or bulk-copy thread IDs.
- **Pointer false positives:** restrict extraction to explicit Markdown links
  and unambiguous backticked repo-path forms; keep commands/globs/prose excluded.
- **Behavior runner becomes infrastructure:** manual-only, read-only,
  orchestration-only, no aggregate scoring, no default CI integration, and only
  changed-route prompts.
- **User configuration contaminates trials:** capture the exact runtime plugin,
  skill, model, and tool surface. Use a controlled repo-only lane for local
  routes and an explicitly recorded `@Context7`-enabled lane only for plugin
  routes.
- **Skill body regrowth:** keep `agent-behavior` compact; use one-hop references
  only for branch-specific procedure, not another shallow index.
- **Graphify treated as truth:** require freshness classification and exact-owner
  verification; never use graph output to override source/tests/config/Typst.

## Out of scope

- Package-runtime, model, rollout, or scientific behavior changes.
- New general evaluator, scoring framework, dashboard, ontology, or transcript
  service.
- New arbitrary skill-count target or replacement skill registry.
- Broad rewrites of root/nested `AGENTS.md` beyond conflict integration required
  by current `main`.
- Rewriting frozen historical debriefs to current language.
- Reintroducing the former source-order index, Docker-MCP Context7, or rich routing
  frontmatter.

## Stop condition

Stop only when the final published PR #65 head is based on then-current
`origin/main`, every valid finding above has a focused patch and evidence, the
fresh-agent trials prove the repaired routes without expected-answer leakage,
Graphify and static checks are verified, the PR body matches reality, and all
remaining gaps are explicit. If any behavioral trial, provenance check,
merge-tree check, or hosted required check fails, preserve the exact evidence
and do not mark the PR merge-ready.
