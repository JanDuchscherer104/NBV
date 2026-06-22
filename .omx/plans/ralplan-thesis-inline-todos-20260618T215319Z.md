# Ralplan Handoff - Thesis Inline TODOs

## Decision

Execute `todo-093` through a single-owner Ralph lane. Scope is every plain
`// TODO` comment returned by:

```sh
rg -n "//\\s*TODO" docs/typst/thesis/sections docs/typst/thesis/main.typ
```

The explicit `#validation_todo`, `#decision_todo`, `#research_todo`, and
related draft-marker macros remain future evidence gates unless their local
prose is also a plain TODO.

## Ralplan Reviews

- Planner: approved narrow direct cleanup of the extracted active thesis
  surfaces, with DB, grep, Mermaid, and Typst verification.
- Architect iteration: require artifact-level inventory and exact Mermaid PDF
  render targets. Incorporated in `.omx/context/thesis-inline-todos-20260618T215319Z.md`
  and `todo-093`.
- Critic iteration: require Mermaid render fallback, explicit Python path,
  agents-db resolution after verification, and required debrief. Incorporated
  in `todo-093`.

## Ralph Worklist

- `docs/typst/thesis/sections/02-02-geometric-learning.typ`
  - Add compact equations/prose for row equivariance, mask isolation, and
    local-frame geometry.
  - Expand the architecture ladder with online and continuous-policy bridge
    levels without making them thesis-core.
- `docs/typst/thesis/sections/03-01-formal-state.typ`
  - Render actor-visible and oracle-only blocks side by side in the Mermaid
    source/PDF.
  - Define `cal(S)^hist`, `cal(S)^cf0`, and `cal(S)^oracle` before the NBV
    tuple using shared equations.
- `docs/typst/thesis/sections/03-02-data-generation.typ`
  - Split target-RRI reward, finite-horizon return, endpoint gain, and log gain
    into separate explanatory paragraphs with source/adaptation caveats.
- `docs/typst/thesis/sections/03-method.typ`
  - Replace raw WIP/internal comments with visible thesis wording or marker
    surfaces.
  - Compress descriptor blocks through symbols/equations where useful.
  - Clarify directional-memory domains and semantics.
  - Document ARIA-NBV CORAL adaptations from code/seminar sources.
  - Remove the raw candidate-query diagram TODO after rendering legible labels.
- `docs/typst/thesis/figures/qh_actor_oracle_contract.mmd`
  - Preserve actor/oracle boundary while improving layout.
- `docs/typst/thesis/figures/qh_vin_gnn_architecture.mmd`
  - Increase font readability, use bold title-case labels, compress text, and
    rely more on symbols.

## Verification

1. `make agents-db AGENTS_ARGS='validate'`
2. `make agents-db`
3. `rg -n "//\\s*TODO" docs/typst/thesis/sections docs/typst/thesis/main.typ`
   must return zero matches.
4. `aria_nbv/.venv/bin/python tools/mermaid/scripts/aria_mermaid_lint.py ...`
5. Render exact PDFs with:
   `PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable npx --yes @mermaid-js/mermaid-cli ... --pdfFit`
6. `cd docs && typst compile typst/thesis/main.typ /tmp/aria-nbv-thesis-inline-todos.pdf --root .`
7. Add native debrief under `.agents/memory/history/2026/06/`.
8. Resolve `todo-093` with `make agents-db AGENTS_ARGS='resolve todo todo-093 --note "..."'`.
9. Re-run `make agents-db AGENTS_ARGS='validate'`, `make agents-db`, and
   `make check-agent-memory`.
