# Test specification: shared-Typst Graphify projection

## Test objective

Prove that the projection deterministically exposes canonical glossary,
symbol, and equation identities plus active-thesis usage relations, while
preserving all pre-existing projection safety and provenance contracts.

## Unit and hermetic contract tests

Extend `scripts/tests/test_build_graphify_projection.py` and its fixture with a
minimal canonical glossary, notation YAML, symbol/equation modules, active uses,
inactive uses, comments, raw blocks, and punctuation-bound references.

Required cases:

1. `test_shared_typst_entities_render_stable_pages`
   - two identical builds produce byte-identical term/symbol/equation pages;
   - identities are `glossary-term:*`, `symbol:*`, and `equation:*`.
2. `test_term_relations_link_known_entities`
   - parent taxonomy labels render as `parent_label`; related, citation, symbol,
     and equation references resolve through relative Markdown links;
   - missing related or notation metadata references fail with the offending term/key.
3. `test_active_sources_record_notation_usage_multiplicity`
   - repeated uses record exact count;
   - the active source links to term, symbol, and equation pages.
4. `test_usage_scanner_ignores_comments_raw_imports_and_inactive_sources`
   - no edge is emitted from excluded lexical regions or files outside the
     compiled include closure;
   - the thesis root and non-section shared owners never emit usage edges.
5. `test_usage_scanner_stops_before_typst_punctuation`
   - `#symb.rl.qh.` resolves to `rl.qh`;
   - commas, parentheses, brackets, and sentence punctuation are covered.
6. `test_unknown_active_notation_reference_fails_closed`
   - unknown `symb` and `eqs` keys and unknown `@...:short` references report
     source path and line;
   - glossary/bibliography ID collisions fail as ambiguous.
7. `test_entity_owner_links_distinguish_metadata_and_typst_implementation`
   - notation pages link to `docs/notation.yml` and the exact shared domain
     module resolved from the validated Typst expression;
   - malformed expressions, missing modules, missing members, and multiple
     declarations fail with the notation key and candidate paths.
8. `test_projection_index_includes_registry_owners_and_families`
   - owner digests include glossary, notation, and implementation modules;
   - family counts match fixture entities.
9. All existing tests remain unchanged or are updated only for intentional new
   Typst query calls and entity counts.
10. `test_rebuild_removes_obsolete_entity_pages`
    - deleting a canonical fixture entity removes its generated page after the
      next non-check build.

## Repository integration checks

Run in order:

```bash
aria_nbv/.venv/bin/python scripts/glossary_build.py validate
aria_nbv/.venv/bin/python -m unittest scripts.tests.test_build_graphify_projection
aria_nbv/.venv/bin/python -m unittest scripts.tests.test_graphify_freshness
python3 scripts/build_graphify_projection.py --check --aria-code-ref "$(git rev-parse HEAD)"
git diff --check
make check-agent-memory
```

If repository policy or changed guidance expands the affected check surface, run
the narrow matching scaffold/projection tests before the aggregate memory check.

## Bounded upstream Graphify ingestion smoke

This is local evidence, not a CI assertion:

1. Build the projection at the current source commit.
2. Copy a closed representative subset into a fresh temporary corpus containing:
   - one glossary term with symbol/equation refs;
   - its symbol page;
   - its equation page;
   - one thesis source page with usage links.
3. Point Graphify at fresh temporary output and cache directories that do not
   share state with the repository caches.
4. Run upstream Graphify semantic extraction through Codex native host agents and
   the ChatGPT subscription. Do not use Claude, Gemini, or provider API keys.
5. Require successful coverage of every dispatched file and no nodes sourced
   outside the dispatched subset.
6. Inspect the extraction/graph JSON for the representative identities and at
   least one usage/reference path connecting the thesis source to the notation
   entity and glossary term.
7. Record command, subset, coverage, node/edge evidence, and limitations in the
   debrief. Do not commit `graphify-input/`, `graphify-out/`, or cache files.

If the upstream LLM extraction does not reproduce a specific edge, report that
as advisory ingestion variance; do not weaken the deterministic projection
contract or add a custom graph builder to force the result.

## Negative and invariant checks

```bash
git diff --name-only origin/main...HEAD -- .agents/skills/graphify
git diff --cached --name-only
git status --short
```

- first command must be empty;
- intended staged files only;
- no generated projection, graph, cache, SVG, GraphML, wiki, Obsidian, tree, or
  call-flow artifact may enter the commit;
- source-order ownership remains explicit in rendered pages and documentation.

## Review-blocker regression additions (2026-08-02)

- Reject an output path that overlaps a resolved shared symbol or equation
  implementation owner before any install operation.
- Consume dotted notation tokens as one lexical token, so sentence punctuation
  is accepted but `#symb.rl.qh.extra` and `#eqs.rl.q_h.extra` fail closed.
- Accept only the exact glossary invocation suffix `:short`; reject known-term
  alternatives such as `:shorter` and unknown `:short` IDs.
- Validate `parent` as taxonomy metadata and `related` as canonical glossary
  entity references; render the former as `parent_label` and the latter as a
  generated identity edge.

## Final quality gate

After implementation verification:

1. run `ai-slop-cleaner` on changed implementation/test files and record a
   passed/no-op result;
2. rerun the focused checks above;
3. independently obtain `code-reviewer: APPROVE` and `architect: CLEAR`;
4. prove the architecture invariants from the PRD against implementation, tests,
   and both reviews;
5. only then complete the aggregate Codex goal, checkpoint Ultragoal, commit,
   push, and open the draft PR.
