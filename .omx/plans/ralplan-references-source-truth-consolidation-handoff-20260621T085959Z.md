# Ralplan Consensus Handoff: References Source-Of-Truth Consolidation

Date: 2026-06-21

## Planning Artifacts

- Plan: `.omx/plans/ralplan-references-source-truth-consolidation-20260621T085959Z.md`
- Target autoresearch evidence artifact for later execution merge: `.omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md`

## Consensus Gate

`ralplan_consensus_gate.complete: true`

Review order:

1. Architect iteration 1: `ITERATE`
   - Required pinning typed inventory to `source_order.md` only.
   - Required routing downstream implementation through `refactor-016` via `agents-db`.
2. Architect iteration 2: `APPROVE`
   - Confirmed inventory ownership and refactor-016 route.
3. Critic iteration 2: `ITERATE`
   - Required merge acceptance criteria, post-merge grep, dirty-worktree preflight, `make agents-db`, and fair Option D.
4. Architect iteration 3: `APPROVE`
   - Confirmed the revised plan is architecturally sound and source-order aligned.
5. Critic iteration 3: `APPROVE`
   - Confirmed testable acceptance criteria, fair options, dirty-state guard, and concrete verification.

## Architect Approval

Final Architect verdict: `APPROVE`.

Key rationale:

- The plan pins the typed reference inventory to `source_order.md`.
- The plan routes follow-on implementation through `refactor-016` via `agents-db`.
- The `.omx/goals` findings merge is evidence/proposal only, not canonical repo truth.
- The package preflight belongs in `aria_nbv/AGENTS.md`.

## Critic Approval

Final Critic verdict: `APPROVE`.

Key rationale:

- Merge acceptance criteria are testable.
- Post-merge `rg` verification is explicit.
- Dirty-worktree preflight is present.
- Later canonical-patch verification includes `make scaffold-audit`, `make kg-status`, `make agents-db AGENTS_ARGS='validate'`, `make agents-db`, and `make check-agent-memory`.
- Option D is a fair ralplan stopping point, while Option A remains the durable cleanup path.

## Approved Follow-Up

Ralplan stops at this planning handoff. Execution requires an explicit `$ultragoal`, `$team`, or `$ralph` handoff.

Approved execution sequence:

1. Merge the addendum into `.omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md` as evidence/proposal only.
2. Verify the artifact merge with:

```bash
rg -n "References Source-Of-Truth Consolidation|evidence/proposal|ralplan-references-source-truth-consolidation" .omx/goals/autoresearch/aria-nbv-python-standards-and-aria-nbv-package-g/findings.md
```

3. Preserve dirty owner surfaces before canonical edits:

```bash
git status --short -- .agents/references/source_order.md aria_nbv/AGENTS.md .agents/references/python_conventions.md .agents/references/human_owner_intent.md .agents/refactors.toml
```

4. Implement the PR-sized canonical patch under `refactor-016` ownership:
   - add reference ownership typing to `source_order.md`;
   - add package reuse preflight to `aria_nbv/AGENTS.md`;
   - demote duplicated binding prose in `python_conventions.md`;
   - narrow quick references and `human_owner_intent.md`;
   - include `litkg_quick_reference.md` or `omx_quick_reference.md` in the dirty preflight if they are edited.

5. Verify with:

```bash
make scaffold-audit
make kg-status
make agents-db AGENTS_ARGS='validate'
make agents-db
make check-agent-memory
```
