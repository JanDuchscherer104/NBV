# Mypy configuration and green CI rollout

Status: approved execution plan for Ultragoal. Start from `origin/main`, not the detached historical checkout.

## Goal

Configure mypy through the existing Python-project owner, add reproducible targeted/full commands, gate CI on a passing bounded contract, and publish a branch whose required CI is green and whose PR reports mergeable against current `main`.

## Research basis

Official mypy guidance for existing codebases recommends standardizing the version, configuration, targets, and CI command; starting with a passing subset; and expanding coverage incrementally. Strict mode is a useful end state, but legacy codebases should enable checks progressively. Configuration belongs in the project `pyproject.toml`, with per-module overrides for exceptions.

Sources:

- [Existing codebases](https://mypy.readthedocs.io/en/stable/existing_code.html)
- [Configuration file reference](https://mypy.readthedocs.io/en/stable/config_file.html)
- [Running mypy and missing imports](https://mypy.readthedocs.io/en/stable/running_mypy.html)
- [Error codes](https://mypy.readthedocs.io/en/stable/error_codes.html)

## Live repository facts

- `aria_nbv/pyproject.toml` is the existing Python project owner.
- The dev extra currently permits mypy; `aria_nbv/uv.lock` resolves mypy 2.1.0.
- `[tool.mypy]` currently targets Python 3.11, enables strict mode, and has global missing-import suppression plus two overrides.
- The public contract `aria_nbv/tests/data_handling/public_api_typing_contract.py` passes targeted checking.
- Full `mypy aria_nbv` currently exits nonzero with 1,187 diagnostics across 133 files and remains informational during this rollout.
- `Makefile` `package-smoke` currently runs Ruff and pytest; package-impact routing already selects package validation for package/config changes.
- The checkout is detached at `150e9fb1fa`; `origin/main` is `406b11f48f`. Create a new `codex/mypy-config-ci` branch from `origin/main` before editing.

## Decisions

1. Use `aria_nbv/pyproject.toml` as the single mypy configuration owner. Do not add a second config file.
2. Pin the dev dependency to the currently locked mypy version, `mypy==2.1.0`, and validate the lock.
3. Add `files = ["aria_nbv"]` under `[tool.mypy]` so bare mypy means full package validation from the package root.
4. Add explicit `warn_unused_configs = true`; run CI/configuration validation with `--no-incremental`.
5. Remove global `ignore_missing_imports`. Retain only dependency-specific overrides proven necessary by fresh diagnostics; do not add broad suppressions.
6. Add Make targets for targeted, contract, and full runs. The contract target is the initial CI gate; the full target remains non-gating until its baseline is clean.
7. Update the Python standards skill with the canonical Make commands and targeted/full claim boundaries.

## Implementation steps

1. Create `codex/mypy-config-ci` from `origin/main` while preserving unrelated work and the existing planning artifacts.
2. Update `aria_nbv/pyproject.toml` and `aria_nbv/uv.lock` with the decisions above. Validate whether the existing `atek.*` and `plotly.graph_objects.*` overrides are still required; keep only evidence-backed overrides.
3. Add minimal Make targets:

   ```text
   make mypy-contract
   make mypy-targeted MYPY_PATHS="aria_nbv/<module> tests/<test>"
   make mypy-full
   ```

   Targeted execution must reject an empty path list, run from `aria_nbv/`, normalize repository-root paths, and use `--warn-unused-configs --no-incremental` for deterministic validation.

4. Make `mypy-contract` a dependency of `package-smoke`. Do not make the known full-package baseline a required CI gate.
5. Update `.agents/skills/python-standards/SKILL.md` to route users to the Make targets and explain that targeted success is surface-limited.
6. Run local validation, commit only intended files, push the branch, open or update the PR, and wait for hosted CI. Repair failures, conflicts, or mergeability blockers before completion.

## Acceptance criteria

- Exactly one active mypy configuration owner exists: `aria_nbv/pyproject.toml`.
- `pyproject.toml`, `uv.lock`, and `uv run --extra dev mypy --version` agree on mypy 2.1.0.
- Bare mypy from `aria_nbv/` resolves the package default; explicit targeted paths remain supported.
- Global missing-import suppression is absent; any retained suppression is module-specific and diagnostic-backed.
- `warn_unused_configs` is active and deterministic validation reports no stale overrides.
- `make mypy-contract` passes.
- `make mypy-targeted MYPY_PATHS=...` handles valid normalized paths and rejects empty/unrelated input.
- `make mypy-full` remains available and reports the nonzero baseline without being falsely described as green.
- `make package-smoke PYTEST_ARGS=` passes with the contract gate.
- Scaffold, ownership, CI-impact, Ruff, pytest, and `git diff --check` validation pass.
- The branch is based on current `origin/main`, the PR has no merge conflicts, required hosted checks are successful, and GitHub reports it mergeable.

## Verification matrix

```text
uv lock --check
cd aria_nbv && uv run --extra dev mypy --version
cd aria_nbv && uv run --extra dev mypy --warn-unused-configs --no-incremental tests/data_handling/public_api_typing_contract.py
make mypy-contract
make mypy-targeted MYPY_PATHS="aria_nbv/tests/data_handling/public_api_typing_contract.py"
make mypy-full
make package-smoke PYTEST_ARGS=
make ci-impact-self-test
make agents-db-validate check-agent-memory scaffold-audit scaffold-audit-self-test
make ownership-consolidation-contract
git diff --check
```

For hosted completion, verify the PR head/base SHAs, required checks, review state, merge state, and absence of conflicts with `gh pr view`/`gh pr checks` or the connected GitHub surface. A green local run is insufficient evidence of mergeability.

## Risks and mitigations

- Removing global import suppression may expose genuine dependency or local typing errors. Classify each diagnostic; add only narrow, documented module overrides or fix the source.
- Changing bare mypy semantics may surprise developers. Document the package default and preserve explicit targeted invocation.
- A full strict check cannot be made green within this bounded change. Keep it measurable and non-gating; do not hide diagnostics with broad ignores.
- The current checkout has linked-worktree metadata warnings. Use explicit worktree Git metadata or a valid new branch/worktree and verify the exact branch head before publishing.
- External PR publication changes remote state. Only publish the focused branch and verify the resulting PR/check state before claiming completion.

## Staffing and follow-up

- Ultragoal leader: owns `.omx/ultragoal/goals.json`, checkpoints, and final evidence.
- Executor, medium: implements the configuration, Make targets, and skill update.
- Test-engineer, medium: validates targeted/full command behavior and CI gate coverage.
- Verifier, high: runs the complete local matrix and checks claims against artifacts.
- Code-reviewer, high plus architect, xhigh: perform independent final review before the terminal goal checkpoint.
- Git-master, high: handles focused commit, push, PR metadata, and mergeability evidence.

Use Team only if the implementation splits into disjoint lanes; otherwise keep one executor followed by verifier and Git-master. `$ultragoal` is the default durable follow-up; `$ralph` is only a deliberate persistent single-owner fallback.

## ADR

**Decision:** strengthen the existing project configuration and add a bounded CI gate, while retaining a non-gating full-package diagnostic.

**Drivers:** official staged-rollout guidance; reproducible mypy 2.1.0 behavior; current package-wide baseline; requirement for green CI and mergeable delivery.

**Alternatives considered:** skill-only guidance; a separate mypy config file; immediate full-package CI gating.

**Why chosen:** this keeps configuration single-owned, makes the passing contract enforceable, and avoids pretending the known full baseline is clean.

**Consequences:** package CI gains one bounded static check; future modules must be added deliberately; full strict cleanup remains follow-up work.

**Follow-ups:** expand the CI target set as modules become clean; revisit full-package gating after the diagnostic baseline reaches zero.
