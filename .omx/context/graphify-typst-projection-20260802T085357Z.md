# Context: minimal Graphify projection for shared Typst semantics

## Task statement

Plan and implement a minimal deterministic `graphify-input/` projection for the
ARIA-NBV shared glossary, symbols, and equations, including explicit usage edges
from active Typst thesis sections, then publish the verified change as a new pull
request.

## Desired outcome

- Graphify receives stable, source-linked Markdown entities for glossary terms,
  shared symbols, and shared equations instead of file-only owner stubs.
- The projection records deterministic edges among terms, symbols, equations,
  citations, related terms, and active Typst sections that use shared notation.
- Exact Typst/YAML owners remain authoritative; generated projection and graph
  artifacts remain derived navigation.
- The byte-identical upstream Graphify skill is not modified.
- The normal artifact profile remains minimal; SVG, GraphML, wiki, Obsidian,
  call-flow, and tree exports are not made prerequisites.

## Known facts and evidence

- Base is `origin/main` at `a5b6fc3c`, which contains merged PR #45 and PR #46.
- The dedicated worktree is
  `/home/jd/repos/ARIA-NBV-graphify-typst-projection` on branch
  `codex/graphify-typst-projection`.
- `scripts/setup_worktree_env.sh --check` passes and both shared Graphify cache
  symlinks exist.
- `scripts/build_graphify_projection.py` currently creates one thesis page per
  active Typst source and populates it only with owner, citation, and explicit
  code-link relationships.
- Current projected pages for `glossary.typ`, `symbols/*.typ`, and
  `equations/*.typ` are therefore owner stubs rather than semantic entities.
- `scripts/glossary_build.py validate` reports 56 glossary terms, 64 notation
  symbols, and 58 notation equations on the live base.
- `docs/typst/shared/glossary.typ` owns term prose and semantic metadata.
- `docs/typst/shared/symbols*.typ` and `equations*.typ` own executable Typst math;
  `docs/notation.yml` owns stable portable symbol/equation keys, TeX forms, and
  descriptions.
- `.graphifyignore` excludes raw Typst and admits only the deterministic Markdown
  projection for this surface.
- ARIA freshness requires `graphify-input/index.md`,
  `graphify-out/graph.json`, and `graphify-out/cache/stat-index.json`; manifest
  state remains necessary for incremental extraction.

## Constraints

- Do not edit `.agents/skills/graphify/**`.
- Do not introduce a repository-owned Graphify schema, graph builder, semantic
  cache implementation, or provider backend.
- Do not move domain truth into Graphify, skills, generated Markdown, or graph
  artifacts.
- Keep changes reviewable and centered on the existing projection builder,
  hermetic projection tests, and only the smallest guidance/debrief updates
  required by repository policy.
- Preserve unrelated work in the primary checkout.
- Use OpenAI/Codex subscription-backed native agents if semantic ingestion needs
  host-agent extraction; do not use Claude, Gemini, or provider API keys.
- New PR targets `main`; user explicitly authorized commit, push, and PR creation.

## Unknowns and planning decisions

- Whether entity pages should be one file per entity or grouped by domain while
  retaining stable headings and links.
- The smallest deterministic method for querying glossary metadata without
  duplicating `glossary_build.py` parsing logic.
- How to validate notation usage tokens and reject unknown `#symb.*` / `#eqs.*`
  references without over-parsing arbitrary Typst.
- What bounded end-to-end evidence is sufficient to prove upstream Graphify can
  ingest the new projection with useful edges without making an LLM result a CI
  invariant.

## Likely touchpoints

- `scripts/build_graphify_projection.py`
- `scripts/tests/test_build_graphify_projection.py`
- possibly a narrow shared helper in `scripts/glossary_build.py` if reuse is
  materially simpler than another parser
- `.agents/skills/aria-nbv-context/SKILL.md` only if the operator boundary needs a
  stable clarification
- `.agents/memory/history/2026/08/` for the required non-trivial-work debrief

## Verification baseline

- `aria_nbv/.venv/bin/python scripts/glossary_build.py validate`
- `aria_nbv/.venv/bin/python -m unittest scripts.tests.test_build_graphify_projection`
- `python3 scripts/build_graphify_projection.py --check --aria-code-ref "$(git rev-parse HEAD)"`
- focused freshness/projection tests, `make check-agent-memory`, and `git diff --check`
- bounded upstream Graphify ingestion smoke with exact-source inspection of the
  resulting nodes/edges; no optional exports
