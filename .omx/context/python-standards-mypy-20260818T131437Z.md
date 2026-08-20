# Task Context

## Task

Prepare a minimal patch to `.agents/skills/python-standards/SKILL.md` that is
well integrated with the repository's `pyproject.toml`, Makefile, CI impact
routing, and existing checks, including full and targeted mypy workflows.

## Constraints

- Planning only during the current `$ralplan` turn; do not edit source files.
- Keep implementation minimal and preserve existing owners.
- Keep executable tool behavior owned by `aria_nbv/pyproject.toml`, Makefile,
  CI, source, and tests; the skill should route and explain those commands.
- Preserve the current Python skill identifier and API/docstring scope.
- Do not add a new dependency unless the existing configuration requires it.

## Live Evidence

- Worktree is clean and detached at `150e9fb1faf58875a3dbc239e513431330a7c4c2`.
- `aria_nbv/pyproject.toml` has strict mypy configuration for Python 3.11,
  Ruff, pytest, and a dev dependency on mypy.
- `Makefile` has `qh-ci`, `package-smoke`, and root `ci`; package CI currently
  runs Ruff and pytest but not mypy.
- `.github/workflows/ci.yml` routes package changes through `package-smoke`
  and uses `scripts/ci_impact.py` for affected-family selection.
- `.agents/skills/python-standards/SKILL.md` is 270 lines and currently has
  no explicit mypy verification entry.
- `make scaffold-audit` passes with zero errors but warns about the Python
  skill's hot-path size and formula detail.

## Likely Touchpoints

- `.agents/skills/python-standards/SKILL.md`
- `Makefile`
- `.github/workflows/ci.yml`
- `scripts/ci_impact.py` and `scripts/tests/test_ci_impact.py` only if routing
  behavior must change
- `aria_nbv/pyproject.toml` only if a command/configuration gap is proven

## Acceptance Shape

- Full mypy command is explicit and uses the repository's configured project.
- Targeted mypy command supports one or more package paths without inventing a
  second configuration source.
- CI runs the intended mypy gate for package-impacting changes.
- Skill guidance distinguishes formatting, linting, tests, type checking, and
  generated-doc verification.
- Existing scaffold and CI routing tests remain green.
