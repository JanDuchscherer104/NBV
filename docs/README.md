# ARIA-NBV documentation operations

Public setup and research pages live under [`contents/`](contents/). The
portable environment guide is [`SETUP.md`](../SETUP.md); the rendered setup
page is [`contents/setup.qmd`](contents/setup.qmd). Keep implementation
contracts in Python/configuration and their tests, and keep thesis claims in
the active Typst include graph.

## Commands and evidence

Run commands from the repository root unless a command changes directory. The
Makefile and CI workflow are the executable owners; this page is only a stable
route for the command/evidence ledger.

| Surface | Command | Evidence |
| --- | --- | --- |
| Agent guidance and memory | `make check-agent-memory scaffold-audit scaffold-audit-self-test` | validator output and the task receipt for the run |
| CI routing | `make ci-impact-self-test` | path-family routing self-test output |
| Quarto and Typst docs | `make qmd-frontmatter-check docs-render-core` | render/check output and generated CI artifacts |
| Package contracts | `make package-smoke` | focused CPU smoke/test output |
| Worktree bootstrap | `bash scripts/tests/test_setup_worktree_env.sh` | setup contract test output |
| Graphify navigation | `python3 scripts/check_graphify_freshness.py --json` | freshness JSON; exact sources remain authoritative |

For a narrower proof, use the nearest `AGENTS.md` or package skill and record
the exact command and result in the task receipt. Do not copy state,
thesis prose, or Python contract text into this routing page.

## Verification

The root CI contract is exposed as `make ci`; its families and path routing are
defined by `.github/workflows/ci.yml` and `scripts/ci_impact.py`. Documentation
changes should at minimum run `make qmd-frontmatter-check docs-render-core`
and `git diff --check`.
