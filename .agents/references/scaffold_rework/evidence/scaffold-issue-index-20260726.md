# ARIA-NBV Agent Scaffold Issue Index

## Executive Verdict

The current scaffold is directionally better than the previous state at
`origin/main`: scientific ownership is clearer, the active ARIA skill set is
smaller, domain truth has moved out of skills, Graphify exposes a cleaner
code/thesis/literature hierarchy, and stale current-state journals are gone.
Those gains should be preserved.

The main remaining problem is that the scaffold measures and validates a
narrower system than agents actually receive and use. The final WP7 gate reports
`21 -> 10` ARIA skills and `1470 <= 1511` scoped ARIA-plus-Matt description
bytes, while a fresh `codex debug prompt-input` contains 67 skill descriptions
totaling 10,866 bytes across all repository, plugin, system, and user/global
sources. The scoped arithmetic is correct, but it does not measure the user's
broader concern about the complete startup catalog. Likewise, Graphify's
structural tests pass even though the graph
cannot answer scaffold-routing questions, omits the active bibliographies, and
contains demonstrably false inferred symbol links. The repository also reduced
headline scaffold LOC partly by deleting prose and skills while increasing a
comparable set of custom scaffold scripts from 3,428 to 8,753 lines and adding
3,930 lines of script tests.

The next work should therefore improve the truthfulness of measurements and
remove custom mechanisms, not introduce another scaffold layer. The highest
priority is to evaluate the system agents actually see: complete prompt cost,
real skill activation and task outcomes, Graphify retrieval coverage, and
sampled link precision.

## Scope And Method

This is a research-only comparison of:

- current scaffold: `5bc48d461eb6679a28d45fc0f2bf7fc6a1222121` on
  `codex/scaffold-distill-upstream-graphify`;
- previous scaffold: `origin/main` at
  `b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c`;
- the frozen WP0 reference state at
  `57457ec31e0d3b56da7cb6ebdbb9fde6166de434` where relevant.

Evidence came from exact Git blobs, current source, fresh `codex debug
prompt-input`, native Graphify commands, graph JSON inspection, scaffold checks,
and independent repository/research/verifier passes. "Observed" means directly
reproduced from source or a command. "Inferred risk" means a plausible failure
mode not yet demonstrated by an end-to-end task failure.

External comparison uses:

- [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/):
  repository guidance should act as a concise map into versioned sources, with
  mechanical checks for freshness and consistency;
- [Agent Skills: optimizing descriptions](https://agentskills.io/skill-creation/optimizing-descriptions):
  descriptions are the prompt-visible activation surface and should be tested
  for both under-triggering and over-triggering;
- [Agent Skills: evaluating skills](https://agentskills.io/skill-creation/evaluating-skills):
  use realistic prompts, objective assertions, repeated runs, and comparisons
  against no-skill or previous-skill baselines;
- [Anthropic, Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
  attention is finite, so context should be minimal, high-signal, and loaded
  just in time;
- [Graphify at the repository-pinned commit](https://github.com/Graphify-Labs/graphify/tree/66d8110a534b52df3d660b5fda5aa5461a6b667a):
  native query/path/explain traversal and explicit `EXTRACTED` versus
  `INFERRED` provenance are the intended primitives.

These references do not override ARIA-specific preferences. In particular, the
project's single-owner rule, thesis authority, dirty-worktree discipline,
accepted OMX evidence, and debrief policy are explicit repository decisions.

## Improvements To Preserve

| Improvement | Current evidence | Previous-state contrast |
| --- | --- | --- |
| Scientific truth has one explicit owner | `AGENTS.md:6-12` and `.agents/references/source_order.md:5-24` make active Typst the sole scientific narrative owner; Quarto is navigation. | Previous `AGENTS.md:9-11` split current thesis direction across roadmap/questions and canonical memory. |
| Skill consolidation reduced duplicated domain primers | Ten ARIA skills remain; current skills are 38-74 lines each. Package `AGENTS.md`, code, tests, docstrings, and Typst own durable contracts. | `origin/main` had 21 ARIA skills, including separate geometry, entity-RRI, rollout-planning, diagnosis, Mermaid, LitKG, and simplification skills. |
| `aria-docs` recovered progressive disclosure | `.agents/skills/aria-docs/SKILL.md:55-74` routes six document task families into bounded references instead of one monolithic body. | Earlier consolidation temporarily lost substantial Typst guidance; the current reference split repairs that regression. |
| Measured autoresearch preserves mixed iteration types | `.agents/skills/measured-autoresearch/SKILL.md:42-56` explicitly alternates research/inspiration and implementation/measurement iterations. | The compacted first draft had lost this Karpathy-style distinction. |
| Graph hierarchy is substantially cleaner | `scripts/tests/test_graphify_retrieval.py:67-92` proves only `aria_nbv` and `docs` appear at the tree root; the fresh graph has 5,404 code, 1,285 thesis, and 3,110 literature nodes. | The prior graph exposed many source files at top level and did not preserve the desired source hierarchy reliably. |
| Graph provenance and schema are native-shaped | The fresh graph has 17,595 `EXTRACTED` and 656 `INFERRED` links; retrieval tests check canonical schema, no dangling links, communities, and selected cross-modal links. | Previous integration mixed more repo-owned freshness/report behavior and weaker topology guarantees. |
| Generated graph/wiki are not truth surfaces | `.agents/references/graphify_contract.md:14-20` keeps graph JSON, HTML, reports, and wiki ignored local state. | This avoids the proposed tracked wiki and its duplicate-maintenance surface. |
| Stale state journals no longer claim current authority | `.agents/memory/README.md:17-24` routes durable facts to exact owners and treats transcript/debrief material as evidence. | Previous `.agents/memory/state/{DECISIONS,GOTCHAS,OPEN_QUESTIONS,PROJECT_STATE}.md` created a competing current-truth layer. |
| OMX accepted evidence has an explicit lifecycle | `.agents/references/omx_artifact_policy.md:7-31` defines current and superseded immutable bundles with registry links. | Previously `.omx` evidence was largely ignored or tracked inconsistently. |

## Ranked Issue Index

### P0: Measurements Do Not Represent The Runtime System

#### SCAFF-001 - The prompt budget excludes most prompt-visible skills

- **Kind:** observed defect; critical; high confidence.
- **Affected owner:** `scripts/scaffold/check_wp7_integration.py` and the WP0/WP7
  prompt accounting contract.
- **Current evidence:** `scripts/scaffold/check_wp7_integration.py:171-191` counts
  only repository ARIA skills and selected Matt skills. Its passing result is
  `description_crosscheck=462+1008=1470<=1511`. A fresh
  `codex debug prompt-input "Locate target-conditioned rollout scoring
  ownership."` exposes 67 skill descriptions totaling 10,866 description bytes
  and 18,301 full-entry bytes after names and absolute skill paths are included.
  Eleven MemPalace/ARIA-plus-Graphify descriptions consume 817 bytes and 29 OMX
  descriptions consume 2,650 bytes. Total captured prompt text was 54,588 bytes.
- **Previous evidence:** WP0 measured 21 ARIA descriptions totaling 3,778 bytes.
  The current ARIA-only reduction is real, but the original concern included
  active system/plugin/global skills, not only `.agents/skills`.
- **Why it matters:** the scoped gate can pass while leaving the complete startup
  catalog, including the system/plugin surfaces the user originally questioned,
  unmeasured. The 1,511-byte ceiling is valid only for its explicitly declared
  ARIA-plus-selected-Matt scope and must not be presented as an end-to-end prompt
  ceiling.
- **Smallest remedy:** replace the ARIA-plus-Matt budget with two separately
  reported metrics: repository-controlled bytes and actual clean-session total
  catalog bytes, grouped by owner. Do not claim control over system/plugin
  entries that the repo cannot disable.
- **Measurable check:** retain a sanitized `codex debug prompt-input` summary
  with entry count and bytes by source root; compare current against baseline on
  the same Codex/plugin installation.

#### SCAFF-002 - Routing fixtures validate lexical self-consistency, not routing

- **Kind:** observed defect; critical; high confidence.
- **Affected owner:** `scripts/scaffold_audit.py` and
  `.agents/references/scaffold_routing_fixtures.json`.
- **Current evidence:** `scripts/scaffold_audit.py:675-817` checks fixture schema,
  known names, and token overlap between task text and skill metadata. It never
  invokes Codex skill selection and never measures whether the selected skill
  improves task output. Thirteen fixtures therefore prove that fixture words
  resemble description words, not that routing works.
- **Previous evidence:** previous routing was mostly prose and had even less
  mechanical coverage. The fixtures are an improvement in contract hygiene but
  not an activation evaluator.
- **Best-practice conflict:** Agent Skills recommends realistic positive and
  negative prompts, repeated runs, and with-skill versus without/previous-skill
  output comparisons.
- **Smallest remedy:** keep lexical checks as cheap lint, rename them accordingly,
  and add a small held-out runtime suite covering positive triggers, near-miss
  negatives, ambiguous handoffs, and task-level output assertions.
- **Measurable check:** report precision/recall for activation and pass rate for
  task assertions over repeated runs, compared with `origin/main` or no skill.

#### SCAFF-003 - Graph link correctness is not measured

- **Kind:** observed defect; critical; high confidence.
- **Affected owner:** `scripts/tests/test_graphify_retrieval.py`,
  `scripts/graphify_adapter.py`, `scripts/graphify_bridge.py`, and upstream
  Graphify resolution behavior.
- **Current evidence:** `scripts/tests/test_graphify_retrieval.py:20-112` checks
  schema, communities, five golden links, tree roots, one explain route, and a
  benchmark command. It has no sampled precision, recall, ambiguity, or
  confidence-stratified assertions. A concrete false link exists: the lambda
  parameter `message` in `aria_nbv/aria_nbv/app/app.py:101` is linked as an
  `INFERRED indirect_call` to
  `OracleInvalidity.message` in
  `aria_nbv/aria_nbv/oracle/pipelines/evaluated_rollout.py:36`. These symbols are
  unrelated.
- **Previous evidence:** the prior graph had weaker hierarchy/schema guarantees;
  the current graph is structurally better, but correctness was not established
  in either version.
- **Why it matters:** cross-modal and code-symbol navigation can look precise
  while directing agents to the wrong owner. `INFERRED` provenance reduces, but
  does not remove, this risk.
- **Smallest remedy:** add a manually reviewed sample of extracted and inferred
  links, stratified by relation type and modality. Keep upstream confidence
  labels and avoid a second custom scoring system.
- **Measurable check:** track sampled precision, false-link examples, and
  resolution rate for an unchanged set of code, thesis, citation, and literature
  queries.

### P1: Graphify Coverage And Progressive Disclosure Are Inconsistent

#### SCAFF-004 - The graph cannot navigate the scaffold that routes agents

- **Kind:** observed defect; high severity; high confidence.
- **Affected owner:** `.graphify.toml`, `.agents/references/graphify_contract.md`,
  and the root `AGENTS.md` Graphify route.
- **Current evidence:** `.graphify.toml:4-11` admits code, Typst/shared thesis,
  and selected literature only. The fresh graph has 9,799 nodes and zero nodes
  from `.agents`, root `AGENTS.md`, or scaffold scripts. `graphify explain
  agent-behavior` returns no node. Querying `agent scaffold routing progressive
  disclosure skill ownership` starts from an unrelated VIN model "Scaffold"
  and expands to 77 mostly domain/thesis nodes.
- **Previous evidence:** `origin/main:.graphifyignore:34-51` admitted selected
  `.agents` references, backlogs, and state files. This proves broader corpus
  admission, not successful retrieval: no retained previous graph/query artifact
  was found that proves those concepts ranked correctly.
- **Conflict:** root guidance routes unknown ownership and architecture questions
  to Graphify (`AGENTS.md:123-130`), while the corpus silently excludes the
  scaffold itself.
- **Smallest remedy:** choose one honest boundary. Preferred: admit only the
  concise root/source-order/skill-frontmatter/scaffold-contract sources needed
  for routing, not history, OMX payloads, transcripts, or tests. Alternative:
  explicitly state Graphify is code/thesis/literature-only and route scaffold
  questions directly to exact sources.
- **Measurable check:** a fixed query set must retrieve the correct owner for
  routing, source order, OMX lifecycle, debrief policy, and Graphify itself
  within the first five results.

#### SCAFF-005 - Active bibliographies disappeared from the graph corpus

- **Kind:** observed regression; high severity; high confidence.
- **Affected owner:** `.graphify.toml`, `scripts/graphify_adapter.py`, and
  `scripts/graphify_bridge.py`.
- **Current evidence:** `.graphify.toml` does not include
  `docs/references.bib` or `docs/references-qh.bib`, although
  `docs/typst/thesis/template/layout/thesis_template.typ:159` imports both and
  `.agents/references/graphify_contract.md:3-11` names bibliography structure as
  an authoritative input handled by the adapter.
- **Previous evidence:** `origin/main:.graphifyignore:32` explicitly admitted
  `docs/references.bib`.
- **Why it matters:** thesis-to-paper navigation and citation resolution are
  incomplete despite literature TeX ingestion.
- **Smallest remedy:** add the two active bibliography files to the thesis or
  literature partition through the existing adapter; do not create a new
  bibliography index.
- **Measurable check:** every cited key in active Typst resolves to one Bib node,
  and representative Bib entries link to the selected local paper source when
  available.

#### SCAFF-006 - The vendored Graphify skill creates an unmeasured over-trigger risk

- **Kind:** observed size/contract conflict plus inferred activation risk; high
  severity; high confidence in the conflict, medium confidence in runtime harm.
- **Affected owner:** `.codex/skills/graphify/SKILL.md` as the vendored upstream
  surface and the narrower root `AGENTS.md` route.
- **Current evidence:** `.codex/skills/graphify/SKILL.md` is 770 lines and 40,759
  bytes, plus 522 reference lines. Its prompt-visible description says to use it
  for "any question about a codebase" and to treat project questions as
  Graphify-first. Root `AGENTS.md:123-125` intentionally narrows Graphify to
  unknown ownership, hierarchy, architecture, impact, or cross-modal work.
- **Previous evidence:** the same vendored skill exception existed, but current
  routing gives Graphify a more central role, increasing the cost of over-triggering.
- **Inference:** the broad description can load a 40 KB body for routine
  exact-file work and defeat progressive disclosure. No retained activation run
  yet demonstrates that over-trigger, so this remains a testable risk rather
  than an observed routing failure.
- **Smallest remedy:** keep upstream tooling and references intact, but expose a
  tiny ARIA routing skill or upstream-compatible override with the narrow root
  trigger. Avoid embedding ARIA-specific edits throughout the vendored upstream
  body.
- **Measurable check:** negative prompts naming exact files must not load the
  Graphify body; unknown-ownership and cross-modal prompts must load it and find
  the owner.

#### SCAFF-007 - `graphify tree --root .` creates an undocumented large artifact

- **Kind:** observed operational defect; medium severity; high confidence.
- **Affected owner:** the root `AGENTS.md` Graphify command documentation.
- **Current evidence:** the root command at `AGENTS.md:126-129` writes
  `graphify-out/GRAPH_TREE.html` by default; the observed file was 785,457 bytes.
  It is ignored and therefore does not corrupt tracked truth, but a read-only
  navigation instruction has a substantial filesystem side effect.
- **Previous evidence:** the previous root pointed agents first to query/path/
  explain and optionally to generated wiki/report artifacts.
- **Smallest remedy:** document an explicit temporary `--output` path or provide
  the exact native command with output under `/tmp`; do not wrap Graphify.
- **Measurable check:** the documented hierarchy command leaves the worktree and
  `graphify-out` unchanged.

### P1: Simplification Metrics Hide New Maintenance Cost

#### SCAFF-008 - Net scaffold LOC masks growth in custom executable machinery

- **Kind:** observed accounting defect; high severity; high confidence.
- **Affected owner:** `.agents/baselines/scaffold_wp0_baseline.json` and
  `scripts/scaffold/check_wp7_integration.py`.
- **Current evidence:** WP7 correctly reports total counted scaffold production
  LOC as `21034 < 27550`, but its baseline explicitly excludes tests and accepted
  OMX evidence. A comparable set of repo-owned scaffold/Graphify/memory scripts
  grew from 3,428 lines at `origin/main` to 8,753 lines at HEAD. Script tests grew
  from 534 to 3,930 lines. The largest current files are
  `validate_omx_artifacts.py` (2,120), `scaffold_audit.py` (1,145),
  `codex_transcript_extract.py` (1,006), `matt_skills_policy.py` (856), and
  `validate_scaffold_wp0_baseline.py` (747).
- **Reproduction inventory:** the 3,428-line previous set is
  `agents_db.py`, `check_graphify_freshness.py`,
  `check_graphify_integration.py`, `codex_transcript_extract.py`,
  `graphify_refresh.py`, `new_debrief.py`, `scaffold_audit.py`, and
  `validate_agent_memory.py`. The 8,753-line current set is `agents_db.py`,
  `codex_transcript_extract.py`, `graphify_adapter.py`, `graphify_bridge.py`,
  `new_debrief.py`, all five current `scripts/scaffold/*.py` files,
  `scaffold_audit.py`, `validate_agent_memory.py`, and
  `validate_scaffold_wp0_baseline.py`. Counts use
  `git ls-tree -r --name-only <ref> -- scripts`, then
  `git show <ref>:<path>` with `bytes.splitlines()`. The 534 and 3,930 test-line
  totals apply the same operation to every `scripts/tests/**` blob at each ref.
- **Previous evidence:** previous behavior was distributed across too many prose
  owners and skills, so raw total LOC was legitimately higher. The regression is
  not total size; it is migration of complexity into custom code excluded from
  the headline interpretation.
- **Smallest remedy:** keep the total LOC gate but add separate budgets for
  repo-owned executable scaffold LOC, tests, generated evidence, and installed
  upstream code. Require an explicit complexity justification for each custom
  script over a modest threshold.
- **Measurable check:** report all four categories and their deltas in one table;
  no category may be omitted from the narrative verdict.

#### SCAFF-009 - Custom Graphify adaptation doubled before tests

- **Kind:** observed maintenance regression; high severity; high confidence.
- **Affected owner:** `scripts/graphify_adapter.py`,
  `scripts/graphify_bridge.py`, and their focused tests.
- **Current evidence:** current `graphify_adapter.py` and `graphify_bridge.py`
  total 1,139 lines, with 950 lines of focused tests. The previous custom
  freshness/integration/refresh scripts totaled 571 lines. Current behavior is
  more correct and source hierarchy is better, but it is not minimal by LOC.
- **Previous evidence:** previous scripts relied more directly on root
  `graphify update .` and had known semantic/hierarchy defects.
- **Inference:** some adapter complexity is necessary because upstream does not
  parse all Typst/TeX/Bib structures. It has not been shown that all 1,139 lines
  are necessary.
- **Smallest remedy:** inventory each adapter responsibility as upstream gap,
  invariant, or convenience. Delete conveniences; submit generally useful
  parsing upstream where feasible; retain only temporary corpus construction and
  ARIA-specific explicit bridge extraction.
- **Measurable check:** adapter production LOC decreases while the same hierarchy,
  freshness, citation, Typst include, and sampled-link tests remain green.

#### SCAFF-010 - OMX retention is overfit to a destructive purge scenario

- **Kind:** observed redundancy and inferred maintenance risk; high severity;
  medium-high confidence.
- **Affected owner:** `.agents/references/omx_artifact_policy.md`,
  `.agents/omx_artifacts.toml`, and
  `scripts/scaffold/validate_omx_artifacts.py`.
- **Current evidence:** OMX lifecycle implementation and its main test total
  3,447 lines. Purge recovery is specified in root `AGENTS.md:40-45`, the
  104-line artifact policy, and native-acceptance fixtures. The policy pins exact
  OMX package integrity and implements transaction journals, deterministic seed
  archives, rollback, symlink/path checks, and disposable-clone purge recovery.
  `make omx-artifacts-check` passes 38 tests with one skipped native gate.
- **Previous evidence:** prior `.omx` retention was too weak and accepted plans
  were easily lost. Registry-backed immutable bundles are a real improvement.
- **Inference:** the purge-specific machinery and root-level detail impose a
  larger maintenance burden than ordinary accepted-bundle retention requires,
  especially as OMX versions change.
- **Smallest remedy:** preserve the registry, immutable current/archive bundles,
  hash verification, and transition validation. Move the destructive purge
  fixture out of default root guidance and evaluate whether a documented manual
  backup/restore procedure can replace custom interception and package-integrity
  coupling.
- **Measurable check:** accepted bundles survive supported OMX operations and a
  documented recovery drill, while lifecycle production LOC and duplicated
  policy text decrease.

### P1: Routing Has Specific Gaps And Contradictions

#### SCAFF-011 - Diagnostic routing names no usable workflow

- **Kind:** observed regression; high severity; high confidence.
- **Affected owner:** root `AGENTS.md` routing and
  `.agents/skills/aria-docs/SKILL.md` handoffs.
- **Current evidence:** `AGENTS.md:29-30` says to use "the selected diagnostic
  workflow" but names neither a retained ARIA skill nor the intended generic
  skill/plugin route. `aria-docs` similarly hands off to a "specialized
  diagnostic capability" without an ID.
- **Previous evidence:** `origin/main:AGENTS.md:30-31` explicitly routed failures
  to `diagnose-aria`; the old context skill also named that handoff.
- **Smallest remedy:** name one installed generic diagnostic workflow and retain
  ARIA-specific reproduction/verification constraints in root or nearest owner.
  Do not restore a large domain skill unless runtime evals show the generic route
  is insufficient.
- **Measurable check:** realistic package, docs-build, metric, and Streamlit
  failure prompts activate the intended route and produce owner plus reproducer
  evidence.

#### SCAFF-012 - Matt policy prose drifted from executable truth

- **Kind:** observed documentation defect; medium severity; high confidence.
- **Affected owner:** the historical Matt policy prose.
- **Current evidence:** its hand-maintained prompt-byte totals disagreed with the
  executable WP7 result. Static validation read the manifest/current skills, so
  it remained green while the prose was stale.
- **Previous evidence:** the Matt allowlist and closure hashing did not exist in
  the earlier scaffold; this is new policy drift, not inherited debt.
- **Smallest remedy:** remove mutable byte totals from prose. Render them only in
  command output or generated test evidence; keep the policy's invariant and
  calculation method in the reference.
- **Measurable check:** no hand-maintained count in references duplicates an
  executable measurement.

#### SCAFF-013 - Operator-local Matt configuration is not verified in normal use

- **Kind:** inferred integration risk; medium severity; medium confidence.
- **Affected owner:** `scripts/scaffold/matt_skills_policy.py`,
  `scripts/scaffold/bootstrap_matt_skills.py`, and `.codex/config.example.toml`.
- **Current evidence:** `.codex/config.toml` is intentionally absent and ignored;
  only an example and bootstrap/validation machinery are tracked. The actual
  fresh prompt contains many global/system/plugin skills outside the Matt
  allowlist.
- **Previous evidence:** the previous scaffold had no reliable project-local Matt
  isolation contract.
- **Smallest remedy:** report Matt isolation as optional operator setup, not as a
  complete project skill-catalog constraint. Add one non-destructive doctor
  command that reports active/missing/drifted state without rewriting config.
- **Measurable check:** clean-home, configured-home, and unconfigured-home probes
  produce distinct, accurate status and do not imply that unrelated global skills
  were disabled.

### P2: Hooks, Memory, And Historical Evidence Need Better Cost Control

#### SCAFF-014 - Copied hooks can silently become stale

- **Kind:** observed design risk; medium severity; high confidence.
- **Affected owner:** the `Makefile` hook installer and
  `scripts/git_hooks/post-commit`.
- **Current evidence:** `Makefile:181-194` copies repository hooks into the Git
  hook directory. Editing `scripts/git_hooks/post-commit` does not update an
  already installed copy until `make install-git-hooks` is rerun.
- **Previous evidence:** the previous scaffold used a more direct linked/dispatch
  arrangement, reducing copy drift but with less portability.
- **Smallest remedy:** install a tiny stable dispatcher that executes the tracked
  hook, or add a digest check to the normal scaffold doctor. Avoid copying the
  full evolving hook body.
- **Measurable check:** changing the tracked hook causes either immediate use or
  a deterministic stale-hook failure before commit-dependent behavior matters.

#### SCAFF-015 - Graph refresh runs synchronously in `post-commit`

- **Kind:** inferred operator-risk tradeoff; medium severity; medium confidence.
- **Affected owner:** `scripts/git_hooks/post-commit` and the Graphify freshness
  policy.
- **Current evidence:** `scripts/git_hooks/post-commit:1-44` uses `set -eu` and
  runs a full `graphify_adapter.py sync` synchronously for any classified corpus
  change. A missing/broken Graphify environment can turn every relevant commit
  into a slow or noisy operation after Git has already created the commit.
- **Previous evidence:** prior refresh behavior separated cheap structural update
  from semantic staleness and was more best-effort/asynchronous, but allowed stale
  graph state.
- **Smallest remedy:** measure actual hook latency and failure rate first. Keep a
  cheap content-digest stale marker in the hook; move expensive sync to an
  explicit command or background path only if measurements justify it.
- **Measurable check:** p50/p95 hook latency, refresh failure rate, and stale-graph
  duration across code, thesis, and literature commits.

#### SCAFF-016 - Debrief growth is mandatory but usefulness is unmeasured

- **Kind:** observed cost and inferred retrieval risk; medium severity; high
  confidence for cost, medium for harm.
- **Affected owner:** root debrief guidance, `.agents/memory/README.md`, and
  `.agents/references/agent_memory_templates.md`.
- **Current evidence:** `.agents/memory/history` contains 576 files and 28,936
  lines, 21 files more than `origin/main`. Root guidance requires a debrief for
  every non-trivial task. Source order correctly marks debriefs as supporting
  evidence, not truth.
- **Previous evidence:** the same debrief paradigm existed and the user has
  explicitly chosen to retain it over event-trigger-only debriefs.
- **Smallest remedy:** do not remove the policy. Measure retrieval value and
  enforce concise debrief structure: result, evidence, failures, exact canonical
  updates, and linked backlog IDs. Archive/indexing is acceptable; promotion to
  truth is not.
- **Measurable check:** for a fixed set of historical questions, record whether
  agents find the relevant debrief, time/tokens to answer, and whether it changes
  the correct source-backed conclusion.

#### SCAFF-017 - Transcript distillation has no completeness benchmark

- **Kind:** observed validation gap; medium severity; high confidence.
- **Affected owner:** `scripts/codex_transcript_extract.py`,
  `.agents/references/human_owner_intent.md`, and source-order/backlog promotion
  routes.
- **Current evidence:** `scripts/codex_transcript_extract.py` remains 1,006 lines.
  It conservatively marks candidate snippets as evidence-only, already reflected,
  needing owner review, or backlog review and does not auto-promote them. That is
  a sound authority boundary. There is no benchmark proving that important user
  invariants are extracted, assigned to the right owner, and eventually resolved.
- **Previous evidence:** the prior script was 1,002 lines and similarly relied on
  heuristic extraction. The current owner taxonomy improved, but recall is still
  unknown.
- **Smallest remedy:** create a small hand-labeled, temporally stratified sample
  of user messages with expected category, owner, and disposition. Evaluate the
  current extractor; do not feed agent-generated inferences into Graphify as
  source truth.
- **Measurable check:** precision/recall for important invariant extraction,
  owner assignment accuracy, unresolved-review age, and duplicate rate.

#### SCAFF-018 - Migration ledgers preserve stale owner wording

- **Kind:** observed historical ambiguity; low-medium severity; high confidence.
- **Affected owner:** immutable `.agents/baselines/scaffold_wp4_state_salvage.csv`
  evidence and the active `.agents/references/source_order.md` interpretation.
- **Current evidence:** `.agents/baselines/scaffold_wp4_state_salvage.csv` still
  labels `docs/contents/thesis/questions.qmd` and `roadmap.qmd` as active owners
  for multiple migrated rows, while `.agents/references/source_order.md:11-14`
  now declares them navigation-only. The ledger is historical baseline evidence,
  not current truth, but readers can mistake its wording for a live owner map.
- **Previous evidence:** at the frozen WP0 state those QMD files were considered
  active owners, so the rows were accurate when created.
- **Smallest remedy:** keep immutable historical bytes; add one surrounding note
  that destinations describe migration-time ownership and must be resolved
  through current source order. Do not rewrite accepted/baseline evidence.
- **Measurable check:** stale-owner scans distinguish immutable historical
  evidence from active references and report no ambiguous live route.

#### SCAFF-019 - Narrow source-inspection coverage regressed without an outcome test

- **Kind:** observed capability reduction and inferred risk; low-medium severity;
  medium confidence.
- **Affected owner:** `.agents/skills/aria-nbv-context/SKILL.md` and the narrow
  source-inspection commands documented by root guidance.
- **Current evidence:** current `aria-nbv-context` is a clean 39-line
  Graphify/`rg` router. The previous skill explicitly offered QMD outlines, Typst
  include topology, literature indexing, contract matching, and a structured
  zoom-out result. Current root retains `make context-contracts`, directory-tree
  and scoped UML helpers elsewhere, but no equivalent direct Typst-include
  inspection route is named.
- **Previous evidence:** the old helpers added custom code and generated context
  surfaces that the user explicitly wanted removed. Restoring them wholesale
  would be a regression.
- **Smallest remedy:** benchmark representative document-structure localization
  tasks using native Graphify plus direct Typst/Quarto tools. Restore only a
  missing native command or tiny stdout helper that demonstrably improves the
  outcome.
- **Measurable check:** owner/topology accuracy, files opened, time, and tokens for
  thesis include, QMD navigation, package contract, and paper-source tasks against
  the previous helper set.

#### SCAFF-020 - Resolved history contains live-looking references to retired LitKG

- **Kind:** observed historical-noise risk; low severity; high confidence.
- **Affected owner:** the agents-DB resolved-history schema and presentation,
  not the retired LitKG implementation.
- **Current evidence:** resolved agents-DB history retains paths and commands for
  the removed LitKG subsystem. Active routing and source order no longer use
  LitKG, and current checks pass because resolved history is not treated as a live
  route.
- **Previous evidence:** these references were operational when the subsystem was
  active.
- **Smallest remedy:** keep historical records immutable but render or query them
  with an explicit `historical/retired` status. Do not delete provenance merely
  to make stale-path scans empty.
- **Measurable check:** active-route scans exclude retired records by schema, while
  history queries visibly identify the retirement state.

## False Positives And Reversions To Avoid

The following are not recommended fixes:

1. **Do not restore the 21-skill domain catalog.** The current compact skills and
   nearest-owner model are better. Repair specific activation gaps with runtime
   evidence.
2. **Do not restore `.agents/memory/state` as a current-truth layer.** Exact code,
   tests, Typst, evidence bundles, bibliography/papers, and backlog owners are
   clearer.
3. **Do not revive LitKG or broad generated `make context` snapshots.** Direct
   source checks and a bounded navigation graph better match the single-owner
   rule.
4. **Do not track Graphify graph/report/wiki output.** Generated navigation is not
   an authority. An on-demand ignored tree/report is sufficient when it has an
   explicit output path.
5. **Do not ingest transcripts, debrief interpretations, or agent answers as
   canonical Graphify facts.** They may be searchable evidence, but exact owners
   must remain authoritative.
6. **Do not remove accepted OMX bundle retention merely because its implementation
   is too large.** Simplify around the durable registry and immutable current/
   archive contract.
7. **Do not judge Graphify only by LOC.** The current hierarchy and schema are
   materially better; simplify only with retrieval and correctness gates intact.

## Recommended Workpackages

These are deliberately small, measurable packages rather than another scaffold
rewrite.

### WP-A - Runtime Measurement Truth

Addresses SCAFF-001, SCAFF-002, SCAFF-012, and SCAFF-013.

- Add a read-only prompt catalog measurement grouped by repository, plugin,
  system, and user/global source.
- Relabel lexical fixtures as lint.
- Add a held-out runtime routing and task-outcome suite with positive, negative,
  and ambiguous prompts.
- Remove mutable byte totals from policy prose.

**Stop condition:** reports match a fresh prompt exactly and distinguish what the
repository controls from what it merely observes.

### WP-B - Graph Coverage And Correctness

Addresses SCAFF-003 through SCAFF-007.

- Resolve the scaffold-corpus boundary explicitly.
- Restore both active bibliographies through the existing adapter.
- Add sampled link precision and stable retrieval tasks.
- Narrow Graphify skill activation without forking upstream behavior further.
- Give native `tree` an explicit temporary output path.

**Stop condition:** representative owner/citation/code/thesis queries succeed,
sampled inferred-link precision is reported, and exact-file negative prompts do
not load the large Graphify skill.

### WP-C - Custom-Code Reduction

Addresses SCAFF-008 through SCAFF-010.

- Publish disaggregated LOC and maintenance budgets.
- Classify every adapter/bridge and OMX-validator responsibility as necessary
  invariant, upstream gap, or convenience.
- Delete convenience code first; preserve accepted-bundle integrity and Graphify
  retrieval behavior.

**Stop condition:** repo-owned executable scaffold LOC decreases with no loss in
the runtime, retrieval, source-ownership, or accepted-evidence gates established
by WP-A and WP-B.

### WP-D - Routing And Operator Reliability

Addresses SCAFF-011, SCAFF-014, and SCAFF-015.

- Name the actual diagnostic route.
- Make installed-hook freshness observable.
- Measure post-commit Graphify latency and choose synchronous versus stale-marker
  behavior from evidence.

**Stop condition:** diagnostic prompts route correctly, tracked hook changes
cannot silently diverge from installed behavior, and hook latency/failure policy
is explicit.

### WP-E - Memory Utility Evaluation

Addresses SCAFF-016 through SCAFF-020.

- Evaluate debrief retrieval value and transcript extraction precision/recall.
- Mark historical ledgers and resolved records visibly historical without
  rewriting immutable evidence.
- Benchmark narrow source-inspection tasks before restoring any removed helper.

**Stop condition:** retained memory surfaces demonstrate measurable retrieval
value, unresolved transcript candidates have owners, and no historical record is
mistaken for a current route.

## Validation Matrix

| Surface | Current gate | What it proves | Missing measurement |
| --- | --- | --- | --- |
| Skill source hygiene | `make scaffold-audit` passes: 10 skills, 0 errors, 0 warnings | Frontmatter, declared owners, lexical fixtures, semantic-drift heuristics | Runtime activation precision/recall and output quality |
| Memory | `make check-agent-memory` passes | Tracked memory/reference schema and active-reference consistency | Debrief utility; transcript extraction recall and closure |
| WP7 budgets | `check_wp7_integration.py` passes | Frozen ARIA skill count, selected Matt bytes, counted production LOC | Full prompt catalog and disaggregated custom/test LOC |
| Graph structure | `test_graphify_retrieval.py` passes | Native schema, no dangling links, communities, selected golden routes, two root nodes | Corpus completeness, retrieval quality, sampled link precision |
| Graph freshness | `make graphify-freshness` passes | Local graph matches selected corpus/config digests | Omitted sources such as Bib/scaffold; hook reliability and latency |
| OMX | `make omx-artifacts-check` passes 38 tests, 1 skipped | Registry integrity, transitions, rollback fixtures | Mandatory native acceptance in this run; maintenance proportionality |
| Source authority | root and source-order documents agree | Clear owner ladder and conflict rule | Whether all runtime routes actually reach those owners |

## Recommended Priority

1. **WP-A: Runtime Measurement Truth.** Without it, later simplification cannot
   tell whether routing or context improved.
2. **WP-B: Graph Coverage And Correctness.** Graphify is now central enough that
   missing corpus families and false links directly affect agent navigation.
3. **WP-D: Routing And Operator Reliability.** Fix the concrete diagnostic gap
   and establish hook evidence.
4. **WP-C: Custom-Code Reduction.** Simplify only after behavior is measured.
5. **WP-E: Memory Utility Evaluation.** Preserve the chosen debrief paradigm but
   prove that its ongoing cost helps agents.

The scaffold does not need another wholesale redesign. It needs honest runtime
measurements, a small number of repaired routes, and deletion driven by those
measurements.
