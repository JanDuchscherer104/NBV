# ARIA-NBV documentation operations

Public setup and research pages live under [`contents/`](contents/). The
portable environment guide is [`SETUP.md`](../SETUP.md); the rendered setup
page is [`contents/setup.qmd`](contents/setup.qmd). Keep implementation
contracts in Python/configuration and their tests, and keep thesis claims in
the active Typst include graph.

## Commands and owners

Keep documentation operations local to this directory. Read
[`AGENTS.md`](AGENTS.md) for the docs owner map and use `make help` from the
repository root for the executable targets. Thesis claims belong to the active
Typst include graph.

## Thesis reader-state ledger

[`typst/thesis/development/reader-state.toml`](typst/thesis/development/reader-state.toml)
records the intended chapter-by-chapter learning journey. It is maintained by
authors and agents when a chapter's conceptual question, prerequisites,
takeaways, teaching device, or outgoing dependency changes; it is not generated
from the prose. Its Typst projection validates the record and appears only in
development renders. The existing development thesis build therefore provides
the narrow verification path; submission mode omits the ledger.
