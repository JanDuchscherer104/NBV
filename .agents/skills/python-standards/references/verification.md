# Python Verification

Run from the repository root. `aria_nbv/pyproject.toml` owns Ruff, mypy,
pytest, and coverage configuration; `aria_nbv/uv.lock` pins versions; the
`Makefile` owns gates and path normalization. Point to these owners instead of
copying flags or pins into guidance.

- `make package-smoke` runs fixed Ruff/pytest smoke surfaces plus the public API
  typing contract. CI adds `make ruff-full`; `make mypy-contract` runs the public
  API typing contract alone.
- Use `make ruff-full` or `make ruff-targeted RUFF_PATHS="..."` for Ruff.
- Use `make coverage-targeted COVERAGE_TESTS="tests/<path>"` for operator-chosen
  branch coverage. No representative repository-wide threshold exists yet.
- Use `make mypy-targeted MYPY_PATHS="aria_nbv/<path> tests/<path>"` for selected
  roots. `make mypy-full` remains informational while its baseline is nonzero.
- Add `MYPY_JUNIT_XML=/tmp/mypy.xml` or `COVERAGE_JSON=/tmp/coverage.json` when
  structured output helps.

Pass repository-root paths such as `aria_nbv/aria_nbv/<path>` or
`aria_nbv/tests/<path>`; the targets normalize, validate, and deduplicate them.
Include `aria_nbv/tests/data_handling/public_api_typing_contract.py` when exports
change.

```sh
cd aria_nbv
uv run --extra dev ruff format --check <changed-paths>
uv run --extra dev ruff check <changed-paths>
uv run --extra dev pytest --import-mode=importlib <tests>
uv run --extra dev pytest --import-mode=importlib --cov <tests>
```

Targeted Ruff, pytest, coverage, and mypy results apply only to their named
surface; `package-smoke` covers its fixed list. Claim package-wide results only
after the corresponding full surface succeeds. Full mypy is currently non-gating.
