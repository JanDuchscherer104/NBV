# Prometheus Strict Plan

### Target Result

- Refactor the active ARIA-NBV thesis seed so `docs/typst/thesis/main.typ` exposes the full chapter/appendix structure and the section source tree matches the current RQ spine.

### Clarified Requirements (Metis)

- Keep `main.typ` as the active thesis source of truth.
- Preserve source order: roadmap/questions/memory and active thesis sections outrank historical seminar/proposal/advisor artifacts.
- Use external HM/TUM thesis guidance for structure and reader expectations, not for technical claim ownership.
- Do not strengthen scientific claims while moving prose.
- Keep draft/open-work material in the appendix with `dashy-todo` markers.
- Validate through Typst compile, outline/include inspection, diff hygiene, and claim checks only where claims change.

### Critique Resolved (Momus)

- Hidden appendix inclusion makes `main.typ` look incomplete -> make appendix ownership explicit in the root or through a visible template parameter.
- `03-method.typ` is too large and mixes problem formulation, data generation, encodings, replay, and `Q_H` -> split by scientific ownership.
- Generic thesis structures could distort ARIA-NBV -> use a CS thesis spine, not blind IMRAD.
- Large file moves are review-risky -> do a mechanical move first, then prose polish in follow-up patches.

### Oracle Execution Plan

1. Create chapter index files for foundations, problem formulation, oracle/data generation, method, and experimental design.
2. Move existing section content mechanically into the new chapter tree without changing claims.
3. Make appendix inclusion visible from the root thesis source, either by a template parameter or an explicit root include compatible with the template.
4. Add a compact RQ placement section using `docs/contents/thesis/questions.qmd` as the current wording owner.
5. Move schedule/open-work/seminar-detail material to appendix files and preserve `dashy-todo` markers.
6. Compile and inspect `typst/thesis/main.typ`; run stale include and claim-hygiene scans.

### Verification Matrix

| Claim | Required evidence | Owner/lane |
| --- | --- | --- |
| `main.typ` exposes all top-level chapters and appendix ownership | `rg -n "#include|appendix/index" docs/typst/thesis/main.typ docs/typst/thesis/template/layout/thesis_template.typ` | executor |
| Every section file is reachable exactly once | include-graph scan and compiled TOC inspection | executor |
| Typst still compiles | `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-structure.pdf` | executor |
| RQs match current thesis truth | manual comparison with `roadmap.qmd` and `questions.qmd` | reviewer |
| No new unsupported advisor-facing claim | `make kg-claim-check KG_CLAIM="<new claim>"` when prose is strengthened | reviewer |
| Repo hygiene holds | `git diff --check`; `make check-agent-memory` only if guidance/memory changes | executor |

### Artifact

- Durable plan path: `.omx/plans/prometheus-strict/thesis-structure-and-main-include-graph.md`
- Research artifact: `.omx/specs/autoresearch-thesis-structure/report.md`

### Handoff

- Recommended next workflow: direct execution for source-file refactor; `$ultragoal` only if bundling prose rewrites and RQ polishing.
- Stop condition: thesis compiles, source files are reachable exactly once, and the new outline follows the RQ spine without claim-strength drift.

### Clean-Room Credit

Inspired by OMO Prometheus (`code-yeongyu/oh-my-openagent`), reimplemented from concept under MIT.
