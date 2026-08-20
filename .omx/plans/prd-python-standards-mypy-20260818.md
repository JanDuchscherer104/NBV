# Python standards mypy guidance

Status: consensus-approved plan; source execution intentionally not started in this planning turn.

## Outcome

Patch only `.agents/skills/python-standards/SKILL.md` so the skill gives a compact, reproducible workflow for targeted and package-wide mypy while preserving repository ownership boundaries. The patch must not change `aria_nbv/pyproject.toml`, `Makefile`, CI workflows, dependencies, or tests.

## RALPLAN-DR

### Principles

- Configuration and executable behavior remain owned by `aria_nbv/pyproject.toml`, package sources, tests, Make targets, and CI.
- The skill owns activation, path normalization, handoffs, evidence, and verification procedure.
- Targeted checks prove only the requested surface; package-wide cleanliness is claimable only after a successful full run.
- Prefer deletion and compression over new abstractions; keep the skill at most 149 lines.

### Decision

Use a single skill-file patch. Remove the complete `Canonical Examples` section without relocating it, rename `Workflow` to `Docstring Workflow`, compress retained prose, and add a `Type-checking Workflow` section containing these exact commands:

```text
cd aria_nbv && uv run --extra dev mypy <changed-paths>
cd aria_nbv && uv run --extra dev mypy aria_nbv
```

Accept only repository-root Python inputs under `aria_nbv/aria_nbv/` or `aria_nbv/tests/`. After changing into `aria_nbv`, normalize by removing the leading repository directory:

```text
aria_nbv/aria_nbv/<path> -> aria_nbv/<path>
aria_nbv/tests/<path> -> tests/<path>
```

Reject unrelated paths and deduplicate normalized arguments. When a covered public data-handling export or exposed contract is affected, append `tests/data_handling/public_api_typing_contract.py`; do not append it for unrelated internal edits.

The skill must explicitly say that the full command is non-gating and that no package-wide cleanliness claim follows from a failed run. The current same-HEAD evidence is part of this handoff, not durable skill prose: the public export fixture passes, while the package-wide command exits nonzero with 1,187 diagnostics across 133 files.

### Rejected alternatives

- Adding a package-smoke mypy gate now: the current package-wide baseline is non-clean, so CI would fail immediately and the change would broaden the requested scope.
- Adding Make aliases or changing `pyproject.toml`: the existing dev extra and strict mypy configuration already provide the command owner.
- Retaining or relocating the long examples: they duplicate source/reference ownership and keep the hot-path skill above its budget.

## Implementation steps

1. Edit only `.agents/skills/python-standards/SKILL.md`.
2. Remove the long examples and the existing prohibited legacy annotation-library reference; replace the latter with dependency-neutral guidance.
3. Compress the remaining metadata and prose to at most 149 lines.
4. Add the targeted/full mypy workflow, normalization rules, conditional public-contract mapping, claim boundaries, and CI boundary.
5. Preserve the existing references and source-order ownership model.

## Test and acceptance specification

- Tracked source diff contains exactly `.agents/skills/python-standards/SKILL.md`; preserve the pre-existing untracked planning context artifact.
- The edited skill is at most 149 lines.
- A negative content search confirms the prohibited legacy reference is absent.
- Required headings and both exact mypy commands occur once.
- Targeted inputs accept only normalized package-source/test paths, reject unrelated paths, deduplicate arguments, and include the public contract only when its covered export is affected.
- The full-run result is recorded honestly; package-wide cleanliness is asserted only if the command exits successfully.
- The `.agents/` path selects `scaffold` only through `scripts/ci_impact.py`; mypy is not described as an existing CI gate.
- `git diff --check` passes.

### Validation matrix

Run the smallest applicable checks, then the full CI-equivalent scaffold route:

```text
make ci-impact-self-test
make agents-db-validate check-agent-memory scaffold-audit scaffold-audit-self-test
python3 scripts/tests/test_agent_governance_g002.py
python3 scripts/tests/test_graphify_worktree_seed.py
bash scripts/tests/test_setup_worktree_env.sh
python3 scripts/tests/test_graphify_freshness.py
python3 scripts/tests/test_graphify_upstream_skill.py
make ownership-consolidation-contract
cd aria_nbv && uv run --extra dev mypy tests/data_handling/public_api_typing_contract.py
cd aria_nbv && uv run --extra dev mypy aria_nbv
git diff --check
```

`make scaffold-check` is not the CI-equivalent command because it additionally runs `graphify-state-check`. Package validation remains the existing Ruff format/check plus pytest `package-smoke` route and is not selected by this `.agents/` change.

## Pre-mortem

| Failure | Early signal | Mitigation |
|---|---|---|
| Root paths are passed after `cd aria_nbv` | mypy reports missing paths | Normalize and deduplicate before invocation; test both mappings. |
| Guidance implies CI gates mypy | Review finds a package-smoke or CI claim | State explicit/non-gating behavior and current baseline. |
| Compression leaves excess lines or stale content | line count or negative search fails | Delete examples, reserve space for the new workflow, and rerun both checks. |

## ADR

Single-file, sub-150-line workflow guidance is the minimal compatible design. Existing strict configuration and dev tooling are reused. A future CI gate is a separate change after package-wide baseline cleanup.

## Execution handoff

Use one executor for the single-file edit, followed by one verifier for the matrix above. Do not broaden the write set. The planning artifacts are complete, but the local consensus gate remains:

```text
ralplan_consensus_gate.complete: false
blocked_reason: documented_host_consensus_receipt_unavailable
```

No source execution or commit is authorized by this planning artifact alone.
