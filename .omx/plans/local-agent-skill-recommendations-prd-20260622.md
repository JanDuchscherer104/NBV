# PRD: Local Scientific Agent Skill Adapters

## Requirements Summary
Integrate the extracted K-Dense scientific-agent-skills recommendations into ARIA-NBV as controlled scaffold work:
- keep the complete upstream collection outside `.agents/skills/`;
- expose only small ARIA-owned adapter skills under `.agents/skills/`;
- preserve the source-order contract that skills are activation/evidence sidecars, not durable thesis-truth owners;
- add provenance, update, and audit surfaces for the external source;
- update routing fixtures so new adapters do not collide with existing `typst-authoring`, `docs-curator`, `aria-litkg-memory`, `aria-nbv-context`, `code-review-aria-nbv`, or domain skills.

## RALPLAN-DR Summary

### Principles
1. Keep upstream skill collections as evidence inputs, not activated local authority.
2. Put durable thesis, bibliography, experiment, and figure truth in existing owner surfaces.
3. Prefer six compact adapter skills over broad imports or duplicated routers.
4. Make every external-skill update auditable, pinned, and non-automatic.
5. Preserve normal Codex/AGENTS usability without requiring OMX, KG, Zotero, or K-Dense tooling.

### Decision Drivers
1. Routing safety: avoid accidental activation of large upstream skills, name collisions, or external tool namespaces.
2. Scientific usefulness: improve writing, literature synthesis, methodology review, figure semantics, experiment design, and citation hygiene.
3. Maintainability: keep hot-path skills compact and validated by existing scaffold checks.

### Viable Options

#### Option A: Pin upstream under `.agents/external/` plus six local adapters
Pros: matches `.agents/external/litkg-rs`; allows reviewed updates without activating the catalog; gives adapters local ownership; keeps `sync_claude_skills.sh` simple.
Cons: adds one external source and a small update/audit tool; requires careful frontmatter and fixture work.

#### Option B: Vendor selected upstream skill bodies into `.agents/skills/`
Pros: fastest initial implementation; no submodule update tooling.
Cons: imports large opinionated bodies; risks biomedical/generated-image/network defaults in hot-path routing; makes upstream comparison harder.

#### Option C: Merge only a few recommendations into existing skills
Pros: minimal file count; no new external source boundary.
Cons: loses repeatable workflows for literature/review/methodology/citation/figures; overloads adjacent owners; no update provenance.

### Favored Option
Choose Option A. It is the only option that satisfies routing safety, scientific usefulness, and maintainability without surrendering local source ownership.

## Scope

### Phase 0: Inventory And Boundary Lock
- Verify upstream URL, license, and target commit.
- Record the current dirty `.agents/external/litkg-rs` baseline with `git status --short .agents/external/litkg-rs` so K-Dense submodule work is not conflated with existing submodule drift.
- Confirm `.agents/external/litkg-rs` remains the correct precedent.
- Confirm `scripts/sync_claude_skills.sh` only exposes direct `.agents/skills/*/SKILL.md` children.
- Record external source policy in `.configs/external_skills.toml`.
- Add a lock/provenance format for selected K-Dense skills.

### Phase 1: External Source Boundary
- Add `.agents/external/scientific-agent-skills` as a pinned git submodule.
- Add `.configs/external_skills.toml` with upstream path, URL, pinned ref, license, update policy, disabled default policy, integration rows, and script/network policy.
- Add `scripts/external_skills.py` with `status`, `diff`, `audit`, and `update` subcommands.
- Extend scaffold/audit checks only as needed to ensure the external source is not discovered as a local skill and selected upstream paths/adapters exist.

### Phase 2: Writing, Literature, And Citation Adapters
- Add `scientific-writing` for verified claim/evidence to prose.
- Add `literature-review` for question, query plan, screening ledger, contradictory evidence, thematic synthesis, and handoff to writing.
- Add `citation-management` for BibTeX integrity, metadata validation, duplicate/missing/unused citation reports, and explicit citation-key diffs.
- Add `references/upstream-adaptation.md` for each adapter.
- Update root/docs routing and scaffold fixtures.

### Phase 3: Review And Methodology Adapters
- Add `scientific-review`, merging useful review concepts from upstream `peer-review`, `scholar-evaluation`, and `scientific-critical-thinking` while rejecting false-precision scoring and biomedical defaults.
- Add `experiment-design` for experimental unit, scene split, pairing, budget, uncertainty, leakage, and effect-size decisions.
- Add ARIA-specific checks for V0/V1 evidence, target-vs-scene RRI, oracle-vs-actor-visible inputs, budget parity, invalidity masks, and scene/root bootstrap semantics.

### Phase 4: Visualization And Existing Owner Merges
- Add `scientific-visualization` for figure semantics, provenance, uncertainty, aggregation level, accessibility, and thesis/advisor-facing data figure review.
- Merge selected slide guidance into `.agents/skills/typst-authoring/references/slides.md` only after a fixture or dry-exercise result shows the merge improves routing or review quality.
- Merge selected Mermaid readability/accessibility guidance into `aria-nbv-mermaid` only after a fixture or dry-exercise result shows the merge improves local rules.
- Merge falsifiability, alternatives, boundary cases, and failure-scenario prompts into `plan-grill` references only when a fixture or dry exercise shows the existing skill misses that planning behavior.

### Phase 5: Evaluation And Pruning
- Test every adapter against positive and negative activation fixtures.
- Run one real-path dry exercise per adapter: thesis prose outline, literature synthesis, bibliography integrity report, scientific review, experiment comparison design, and figure semantics/provenance review.
- Remove or defer any adapter that does not measurably improve routing quality, evidence quality, or review reliability.

## Non-Goals
- Do not install the full K-Dense catalog directly under `.agents/skills/`.
- Do not add external literature/research systems such as `parallel-web`, `exa-search`, Paperzilla, Open Notebook, or duplicate vector/notebook stores.
- Do not activate AI-generated schematic/image skills for normal thesis work.
- Do not add biomedical, genomics, chemistry, clinical, laboratory, geospatial, materials, astronomy, or unrelated package-specific skills.
- Do not make `pyzotero` canonical until Zotero/Better BibTeX is accepted.
- Do not use K-Dense or OMX artifacts as public thesis truth.

## Acceptance Criteria
- `.agents/external/scientific-agent-skills` is pinned and not discovered by local skill sync or scaffold routing as an activated skill.
- `.configs/external_skills.toml` records selected integrations and disables all unlisted upstream skills by default.
- `scripts/external_skills.py status`, `diff --source kdense`, `audit --source kdense`, and `update --source kdense --ref <sha-or-tag>` have documented behavior and tests or smoke checks.
- The six adapter skills match `.agents/references/skill_style_guide.md` frontmatter requirements.
- Every adapter includes `references/upstream-adaptation.md` with adopted, rejected, ARIA overrides, reviewed commit, reviewed date, and license.
- Root and docs guidance route scientific prose, literature synthesis, scientific review, final/advisor-facing data figures, experiment/statistical evidence, and citation metadata to the right adapters without duplicating long policy.
- `scaffold_routing_fixtures.json` includes positive and negative examples for the new adapters and adjacent skills.
- Adjacent skills remain clearly owned: `typst-authoring`, `docs-curator`, `aria-litkg-memory`, `aria-nbv-context`, and `code-review-aria-nbv`.
- `make scaffold-audit`, `make scaffold-audit-self-test`, `make check-agent-memory`, and `make claude-skills` pass or exact environment blockers are recorded.

## Risks And Mitigations
- Imported upstream prose could turn local skills into manuals. Mitigate by keeping `SKILL.md` compact, moving detail to references, and running scaffold audits.
- New adapters could collide with docs/Typst routing. Mitigate with negative fixtures and explicit `not_when` handoffs.
- Submodule update drift could silently change recommendations. Mitigate with pinned refs, reviewed commits, selected-skill diffs, and no automatic adapter rewrites.
- Citation-management could mutate bibliography too freely. Mitigate with explicit diffs before citation-key/BibTeX changes and `docs/references.bib` ownership.
- Literature-review could duplicate KG/LitKG. Mitigate by routing retrieval through existing source policy and using the adapter for protocol/screening/synthesis.
- Scientific-review could overlap with code-review. Mitigate by limiting it to evidence, narrative, and methodology critique.

## Verification Steps
1. Static scaffold checks: `make scaffold-audit`, `make scaffold-audit-self-test`, `make check-agent-memory`, `make claude-skills`.
2. External source checks: `python3 scripts/external_skills.py status`, `python3 scripts/external_skills.py diff --source kdense`, `python3 scripts/external_skills.py audit --source kdense`.
3. Routing fixtures: positive examples activate each adapter; negative examples keep adjacent work on existing owners.
4. Guidance inspection: `rg -n "scientific-writing|literature-review|scientific-review|scientific-visualization|experiment-design|citation-management" AGENTS.md docs/AGENTS.md .agents/references`.
5. Real-path dry exercises for all six adapters.

## ADR

### Decision
Integrate the extracted K-Dense recommendations by pinning the upstream repository under `.agents/external/` and adding six compact ARIA-owned adapter skills under `.agents/skills/`.

### Drivers
Avoid accidental activation of the full upstream catalog; improve scientific writing/review/methodology/visualization/literature/citation workflows; keep external scaffolds replaceable, reviewable, and non-authoritative.

### Alternatives Considered
- Directly install or copy upstream skills into `.agents/skills/`: rejected because it imports broad defaults, external tool assumptions, and routing ambiguity.
- Only merge scattered guidance into existing skills: rejected because it hides repeatable workflows inside adjacent owners and loses provenance.

### Why Chosen
The pinned-external-plus-adapters model gives upstream freshness and local control. It matches the existing external-source pattern, keeps skills compact, and creates a clean audit path for future upstream changes.

### Consequences
Adds one external source, one small update/audit tool, six adapter skills, and routing fixtures. Requires discipline that adapters route durable truth to existing owners.

### Follow-Ups
Use a git submodule for the first implementation unless execution discovers a concrete repo-policy blocker; add a mocked or dry-run smoke for `scripts/external_skills.py update --source kdense --ref <sha-or-tag>` so non-rewrite behavior is directly testable; record the existing `.agents/external/litkg-rs` dirty baseline before adding K-Dense; revisit Zotero/Better BibTeX only after bibliography workflow ownership is accepted; delete/defer any adapter that fails dry exercises.

## Available Agent Types Roster
`explore`, `researcher`, `dependency-expert`, `planner`, `architect`, `critic`, `executor`, `test-engineer`, `verifier`, `writer`, `code-reviewer`.

## Follow-Up Staffing Guidance

### Recommended `$ultragoal` Path
Use `$ultragoal` as the default durable follow-up. Suggested sequential goals: external source boundary and audit tool; writing/literature/citation adapters; review/methodology adapters; visualization and existing-owner merges; evaluation, pruning, debrief, and PR cleanup.

### Recommended `$team` Path
Use `$team` after phase 1 if implementing phases 2-4 in parallel:
- Lane A, `executor` + `writer`: scientific-writing, literature-review, citation-management.
- Lane B, `executor` + `writer`: scientific-review and experiment-design.
- Lane C, `executor` + `writer`: scientific-visualization plus `typst-authoring`, `aria-nbv-mermaid`, and `plan-grill` reference merges.
- Lane D, `test-engineer`: fixtures, external skill audit tests, validation scripts.
- Lane E, `verifier` or `code-reviewer`: integration review after lanes merge.

### `$team` Launch Hints
```text
$team "Implement .omx/plans/local-agent-skill-recommendations-prd-20260622.md. Phase 1 must complete first. Then split adapter implementation into disjoint lanes A-D, preserve dirty worktree changes, and return checkpoint-ready evidence for Ultragoal."
```

```bash
omx team "Implement .omx/plans/local-agent-skill-recommendations-prd-20260622.md with phase 1 first, then parallel adapter/test lanes"
```

### Team Verification Path
Before shutdown, each lane reports changed files, fixtures, and commands; static and external-source checks pass; one verifier inspects that upstream text was adapted rather than copied into hot-path bodies. Ultragoal checkpoints only after team evidence proves phase acceptance criteria.

### Ralph Fallback
Use `$ralph` only if the user intentionally wants a single-owner persistent verification loop. It is not the default because this work benefits from durable goal tracking and can be parallelized after phase 1.

## Goal-Mode Follow-Up Suggestions
- `$ultragoal`: recommended default for durable execution and checkpointing.
- `$team`: recommended alongside Ultragoal after phase 1 for parallel adapter lanes.
- `$autoresearch-goal`: not default; use only if the follow-up becomes a research project about upstream skill catalogs.
- `$performance-goal`: not applicable.

## Applied Reviewer Improvements
- Architect approved the pinned external plus local adapter boundary.
- Phase 1 now names a pinned git submodule instead of leaving storage ambiguous.
- Phase 4 merges into `typst-authoring`, `aria-nbv-mermaid`, or `plan-grill` only after fixture or dry-exercise evidence shows a benefit.
- The test spec now includes explicit nearest-neighbor collision fixtures for scientific writing versus Typst authoring, and scientific visualization versus Mermaid diagram work.
- Critic approved the plan and requested final execution-readiness details.
- Phase 0 now records the existing dirty `.agents/external/litkg-rs` baseline before K-Dense work.
- The follow-up list now requires a mocked or dry-run update smoke for `scripts/external_skills.py update`.
- The test spec now gives stable fixture IDs matching the existing scaffold fixture schema.
