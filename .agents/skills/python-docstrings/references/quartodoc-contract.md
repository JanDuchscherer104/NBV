# Quartodoc Validation

Use this branch only when docstrings affect generated API pages.

1. Read the live Quartodoc configuration in `docs/_quarto.yml` and documentation
   commands in `docs/AGENTS.md`; do not copy parser or inventory settings here.
2. Generate API pages with `./scripts/quarto_generate_api_docs.sh`.
3. Inspect the touched generated page and any reference warnings. Use syntax
   supported by the live configuration and verify links rather than assuming
   an external inventory exists.
4. For a substantial rendered change, run the narrow Quarto check or render
   required by `docs/AGENTS.md`.

Quartodoc validates presentation. Package code, tests, and the nearest
`AGENTS.md` remain the owners of API behavior and domain contracts.
