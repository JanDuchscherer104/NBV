# Ralplan: References Source-Of-Truth Consolidation Addendum

Date: 2026-06-21

## Purpose

Merge the valid findings from the follow-up best-practice research into the Python/package guidance autoresearch thread without changing canonical guidance files during ralplan. Direct writes to `.omx/goals/autoresearch/*` are blocked while ralplan is active, so this file is the merge-ready planning addendum.

Target autoresearch artifact for the later execution handoff:

- `.omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md`

## Validated Direct Recommendation

Do not merge all `.agents/references/*` content into skills. That would bloat skills and turn activation files into duplicate manuals.

Use this ownership model:

- root and nested `AGENTS.md`: dispatch and binding rules;
- `.agents/skills/*/SKILL.md`: activation, routing, evidence, verification;
- `.agents/references/*`: long-form references, tool cards, templates, and operator aids;
- `aria_nbv/**`: Python package truth and implementation contracts;
- `docs/**` and Typst thesis sources: public and thesis truth.

The fix is reference ownership typing, not wholesale merging.

## File-Level Dispositions

| File | Verdict | Action |
| --- | --- | --- |
| `source_order.md` | Keep as spine | Make it the typed index for reference roles and conflict resolution. |
| `skill_style_guide.md` | Keep | Normative skill schema/style owner; skills link to it instead of inlining. |
| `scaffold_routing_fixtures.json` | Keep | Machine fixture surface under audit, not prose. |
| `verification_matrix.md` | Keep, slim | Own cross-surface command gates; remove local/runtime-only requirements. |
| `alignment_tools_contract.md` | Keep, slim | Owner for replaceable OMX/MCP/KG/tool boundary policy. |
| `human_owner_intent.md` | Keep, narrow | Human preferences only; move duplicated capture policy back to `source_order.md`. |
| `agent_memory_templates.md` | Keep or move near memory | Template owner for debriefs; link from `agents-db`, not every skill. |
| `worktree_policy.md` | Keep | Operational policy for parallel sessions and dirty worktrees; link from root guidance only. |
| `context7_library_ids.md` | Keep as tool lookup | Skills should use `metadata.context7_refs` rather than duplicating lookup tables. |
| `litkg_quick_reference.md` | Keep, shorten | Quick commands only; full trust/schema policy belongs in litkg docs/config. |
| `omx_quick_reference.md` | Keep, shorten | Operator how-to only; do not make OMX repo truth. |
| `operator_quick_reference.md` | Split | Keep machine/operator recovery there; move package/domain facts elsewhere. |
| `python_conventions.md` | Rehome or demote | Package standards should be package-owned; this can remain examples/rationale. |
| `external_stack_contracts.md` | Move closer to package/domain | Treat as package annex or module reference, not generic scaffold guidance. |
| `rollout_zarr_q_invalidity_contract.md` | Move | Domain contract should live with rollout package/docs ownership. |
| `skill_prune_merge_verdict.md` | Deprecate/archive | Dated verdict; convert durable decisions into owners or backlog. |

## Redundancies To Carry Forward

1. Instruction capture is duplicated. `source_order.md` owns capture rules, while `human_owner_intent.md` repeats capture-policy structure. Keep the table only in `source_order.md`.
2. Tool boundary policy repeats across `source_order.md`, `alignment_tools_contract.md`, `litkg_quick_reference.md`, `omx_quick_reference.md`, and backlog records. Make `alignment_tools_contract.md` the policy owner; quick refs should be command-only.
3. Python standards are split across `aria_nbv/AGENTS.md` and `.agents/references/python_conventions.md`. Move binding package rules toward `aria_nbv/AGENTS.md`, nested module `AGENTS.md`, `pyproject.toml`, public docstrings, and generated API docs.
4. Large domain contracts in generic references create drift. `rollout_zarr_q_invalidity_contract.md` should move under rollout package or docs/theory ownership.

## Action Items

P0:

- Add a typed inventory to `source_order.md` that classifies every reference file by owner role: conflict resolver, normative style/schema, command quick reference, operator recovery, package annex, domain contract, template, historical verdict, or machine fixture.
- Add a binding pre-implementation rule to `aria_nbv/AGENTS.md`: before adding a new helper, class, config, CLI, or data container, search `aria_nbv/`, inspect the nearest nested `AGENTS.md`, prefer extending the existing public API, and document why reuse is impossible when adding a new abstraction.
- Re-scope `human_owner_intent.md` to human preferences only.
- Re-scope `litkg_quick_reference.md` and `omx_quick_reference.md` to commands and fallback usage only.

P1:

- Move or rehome `rollout_zarr_q_invalidity_contract.md` to rollout package/docs ownership, then leave only a pointer from `.agents/references`.
- Move `external_stack_contracts.md` closer to package/domain ownership, or mark it explicitly as a package annex.
- Add `metadata.context7_refs`, `metadata.literature_refs`, and `metadata.tool_refs` to relevant skills instead of duplicating lookup prose in skill bodies.
- Convert durable decisions from `skill_prune_merge_verdict.md` into `source_order.md`, `skill_style_guide.md`, or backlog records, then archive the dated verdict.

P2:

- Add audit checks for stale generic-reference domain contracts, quick refs that contain policy, and skills that duplicate reference lookup tables.
- Keep `agent_memory_templates.md` linked mainly from `agents-db` and memory workflows, not from every skill.

## RALPLAN-DR Summary

Principles:

- Keep skills small and activation-oriented.
- Make each durable truth have exactly one owner.
- Treat tools, KG, and OMX as evidence producers, not truth owners.
- Prefer package-owned Python standards over generic scaffold references.
- Preserve machine-readable fixtures and audit gates as separate surfaces.

Decision drivers:

- Drift reduction has higher ROI than reducing file count.
- Agents need a forced reuse-discovery workflow more than more prose.
- Domain contracts should sit near the code/docs they govern.

Viable options:

- Option A: typed inventory plus scoped moves. Preferred because it preserves useful references while clarifying ownership.
- Option B: merge references into skills. Rejected because it bloats skills and duplicates manuals.
- Option C: leave references as-is and rely on audit warnings. Rejected because current warnings identify drift but do not clarify ownership enough for future agents.
- Option D: merge the addendum into the autoresearch artifact only and defer canonical guidance changes. Viable as a stopping point under ralplan constraints, but incomplete as the final cleanup because it leaves known source-owner drift in place.

ADR:

- Decision: use reference ownership typing and PR-sized scoped moves.
- Why chosen: it matches the repo source-order model, external documentation architecture practice, and the observed reimplementation failure mode.
- Consequences: first implementation should touch reference ownership and package preflight, not domain behavior.
- Follow-up lane: explicit `$ultragoal`, `$team`, or `$ralph` handoff can merge this addendum into the target autoresearch artifact as evidence/proposal only, then implement the source-order/package-guidance changes through `refactor-016` via `agents-db`.

## Validated Repo Evidence

- `make kg-status` returned `kg-status: ok`.
- `make scaffold-audit` returned `skills=19 errors=0 warnings=16`.
- `refactor-016` already owns human-intent narrowing, litkg quick-reference slimming, alignment-tool boundaries, skill metadata cleanup, and quick-reference simplification.
- `source_order.md` already says `.agents/references/` are operator aids and long conventions, while skills own activation/routing/evidence loops.
- `alignment_tools_contract.md` already says optional tools produce evidence/proposals/diagnostics and do not own ARIA-NBV truth.

## External Best-Practice Support

- Diataxis supports separating tutorials, how-to guides, reference, and explanation, which maps to keeping routing skills, quick refs, durable contracts, and docs narrative separate.
- Write the Docs "Docs as Code" supports versioned, reviewed, tested reference surfaces rather than hidden runtime/tool state.
- Google developer documentation style gives project-specific style precedence over general style references.
- PEP 8 gives project-specific Python style precedence and emphasizes consistency within a project.
- PEP 257 defines docstring conventions and attribute docstrings, supporting the package's config-field docstring convention.

## Merge Acceptance Criteria

After ralplan reaches a terminal planning state and an explicit execution lane is activated, the target autoresearch findings file must contain:

- a dated heading named `References Source-Of-Truth Consolidation Addendum`;
- the source plan path `.omx/plans/ralplan-references-source-truth-consolidation-20260621T085959Z.md`;
- explicit wording that the merged addendum is `evidence/proposal only`, not canonical repo truth;
- the validated repo evidence: `make kg-status` OK, `make scaffold-audit` with 0 errors and 16 warnings, and `refactor-016` as implementation owner;
- the P0/P1/P2 action items from this plan without promoting them to completed changes.

Post-merge verification:

```bash
rg -n "References Source-Of-Truth Consolidation|evidence/proposal|ralplan-references-source-truth-consolidation" .omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md
```

## Dirty-Worktree Preflight

Before the later canonical patch, capture and preserve pre-existing edits on the expected owner surfaces:

```bash
git status --short -- .agents/references/source_order.md aria_nbv/AGENTS.md .agents/references/python_conventions.md .agents/references/human_owner_intent.md .agents/refactors.toml
```

If any of those files contain unrelated user or agent edits, read and work with them instead of overwriting or reverting them.

## Execution Handoff

When an explicit execution lane is activated, merge this addendum into:

- `.omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md` as evidence/proposal only

Then apply the first PR-sized canonical patch under existing `refactor-016` ownership via `agents-db`, avoiding a parallel backlog queue:

1. add reference ownership typing to `source_order.md`;
2. add the package reuse preflight to `aria_nbv/AGENTS.md`;
3. demote duplicated binding prose in `python_conventions.md`;
4. narrow quick references and `human_owner_intent.md`;
5. verify with `make scaffold-audit`, `make kg-status`, `make agents-db AGENTS_ARGS='validate'`, `make agents-db`, and `make check-agent-memory`.
