# Streamlit guidance strategy for ARIA-NBV

## Executive decision

Adopt Streamlit's official, application-facing
[`developing-with-streamlit`](https://github.com/streamlit/streamlit/blob/8c5983bac5f8abcad21b15aa61025ab106bbd7ec/lib/streamlit/.agents/skills/developing-with-streamlit/SKILL.md)
skill as the generic framework baseline, but do **not** vendor its contents and
do **not** adopt the two framework-maintainer skills named in the request.
For the current 1.57 environment this means consulting the bundled source, not
invoking a registered skill; the invokable global meta-skill follows only after
a separately verified upgrade to Streamlit 1.58 or later.

Complete the stack with two small ARIA-owned surfaces:

1. `aria_nbv/aria_nbv/app/AGENTS.md` for implementation invariants and focused
   verification;
2. `aria_nbv/aria_nbv/app/README.md` for human launch, navigation, and debugging
   instructions.

Do not create a large custom Streamlit skill. The official skill already owns
generic Streamlit API, layout, state, caching, performance, and component
guidance. ARIA's local guide should contain only rules that upstream cannot
know: scientific ownership, expensive-store laziness, cache identity, Rerun
boundaries, and the project's progressive-disclosure preferences.

## Why this is the smallest correct stack

The current app is large enough to justify a nearest-scope guide, with several
page and concern modules above 700 lines. Yet the architecture already has
meaningful seams:

- [`app.py`](../../../aria_nbv/aria_nbv/app/app.py) owns grouped navigation,
  exception containment, and lazy page imports;
- [`streamlit_app.py`](../../../aria_nbv/aria_nbv/streamlit_app.py) is the
  import-light CLI entrypoint and disables the file watcher by default;
- [`state_types.py`](../../../aria_nbv/aria_nbv/app/state_types.py) owns
  Streamlit-free typed state and cache-key semantics;
- [`controller.py`](../../../aria_nbv/aria_nbv/app/controller.py) owns the
  single-step compute/cache pipeline;
- [`panels/__init__.py`](../../../aria_nbv/aria_nbv/app/panels/__init__.py)
  lazily exposes page renderers;
- stored rollouts and VIN diagnostics already decompose large pages into
  private concern modules.

The package-level [`aria_nbv/AGENTS.md`](../../../aria_nbv/AGENTS.md) is too
general to protect these app-specific seams. Conversely, copying all of
Streamlit's generic recommendations into an app guide would duplicate an
actively maintained upstream owner.

## External-skill assessment

| Candidate | Decision | Reason |
| --- | --- | --- |
| Official bundled [`developing-with-streamlit`](https://github.com/streamlit/streamlit/blob/8c5983bac5f8abcad21b15aa61025ab106bbd7ec/lib/streamlit/.agents/skills/developing-with-streamlit/SKILL.md) | **Consult now; adopt as an invokable global meta-skill after verified >=1.58 upgrade** | It is specifically for application development and routes to version-matched references for layout, dashboards, data display, multipage apps, state, caching, performance, design, themes, and components. |
| [`debugging-streamlit`](https://github.com/streamlit/streamlit/blob/8c5983bac5f8abcad21b15aa61025ab106bbd7ec/.claude/skills/debugging-streamlit/SKILL.md) | **Do not adopt** | It assumes the Streamlit framework monorepo: `make debug`, React/Vite hot reload, `work-tmp/debug`, and upstream `e2e_playwright` helpers. These commands and paths do not exist in ARIA-NBV. |
| [`understanding-streamlit-architecture`](https://github.com/streamlit/streamlit/blob/8c5983bac5f8abcad21b15aa61025ab106bbd7ec/.claude/skills/understanding-streamlit-architecture/SKILL.md) | **Link only for escalation** | Its rerun/session mental model is useful, but most navigation points are Streamlit's Python/React/protobuf internals. Load it only when public API documentation cannot explain a framework-level issue. |
| Archived [`streamlit/agent-skills`](https://github.com/streamlit/agent-skills) repository | **Do not vendor or treat as current owner** | Upstream archived it and moved canonical skill ownership into the main Streamlit package/repository. It remains historical provenance, not the update source. |
| Official [`AppTest`](https://docs.streamlit.io/develop/concepts/app-testing/get-started) guidance | **Link from the local app guide** | It is already used in ARIA-NBV and is the correct server-side widget/output test surface. It does not replace browser visual or Rerun evidence. |
| Generic third-party Streamlit, dashboard, Plotly, or Playwright skills | **Do not adopt now** | No additional skill closed a demonstrated gap better than the official bundled skill plus existing ARIA skills. Add one only after a concrete repeated workflow cannot be expressed by the local guide and current verification surfaces. |

Streamlit is Apache-2.0 licensed
([license](https://github.com/streamlit/streamlit/blob/8c5983bac5f8abcad21b15aa61025ab106bbd7ec/LICENSE)),
so copying is legally possible, but vendoring would create needless drift and
attribution maintenance.

## Version and installation constraint

The current project declares `streamlit>=1.52.2` and the resolved worktree
environment is Streamlit `1.57.0`. That installation already contains the full
`developing-with-streamlit` skill and topic references under its package, but
it does not yet expose the `streamlit skills` CLI:

```text
$ uv run streamlit --version
Streamlit, version 1.57.0

$ uv run streamlit skills --help
Error: No such command 'skills'.
```

The official [`streamlit skills`](https://docs.streamlit.io/develop/api-reference/cli/skills)
installer arrived in 1.58. Therefore:

- do not create a committed symlink into a worktree-local or shared virtual
  environment;
- do not raise the runtime dependency solely to install agent guidance;
- when a separately verified Streamlit upgrade reaches 1.58 or later, prefer
  `uv run streamlit skills --global --yes` on this multi-worktree workstation;
  the global meta-skill resolves each project's installed, version-matched
  package skill without committing environment-specific symlinks;
- use project-scoped `uv run streamlit skills --yes` only if deterministic
  repository-local discovery is later required and the generated symlink policy
  has been reviewed;
- until then, agents can consult the already bundled 1.57 skill through the
  resolved environment, while the local app guide links its official source
  and the public Streamlit documentation.

This avoids coupling a guidance change to an untested framework upgrade.

## Durable local ownership

### `aria_nbv/aria_nbv/app/AGENTS.md`

Keep this short and enforceable. It should own:

1. **Routing**
   - On the current Streamlit 1.57 environment, consult the package-bundled
     `developing-with-streamlit` source for generic Streamlit behavior; it is
     not yet registered as an invokable Codex skill.
   - After a separately verified upgrade to Streamlit 1.58 or later, use the
     globally installed `developing-with-streamlit` meta-skill.
   - Use `rerun-nbv-inspector` for Rerun entities, blueprints, `.rrd`, camera,
     depth, and post-hoc visual evidence.
   - Use the nearest semantic owner for scientific metrics and persisted data.

2. **Architecture seams**
   - `streamlit_app.py` remains import-light.
   - `app.py` owns navigation and lazy page imports.
   - `state_types.py` stays Streamlit-free; `state.py` adapts session state.
   - `controller.py` owns single-step compute orchestration.
   - Page modules render typed projections; they do not decode Zarr, recreate
     rollout schemas, or duplicate scientific reducers.
   - Stable public panel facades stay thin; private modules own concerns
     directly, without compatibility alias carpets.

3. **Rerun, state, and cache rules**
   - Assume top-to-bottom reruns.
   - Namespace widget and session keys by page/store identity.
   - Bounded primary diagnostics may be visible by default. Expensive full-
     store aggregates, deep Q_H reads, and unbounded evidence require an
     explicit action and a stable input identity.
   - Use `st.cache_data` for serializable data and `st.cache_resource` only for
     deliberately shared, thread-safe resources.
   - Store-backed cache keys must detect same-path atomic replacement and bind
     validation/promotion evidence; refresh must clear every dependent cache.

4. **ARIA presentation rules**
   - Lead with a small answer/readiness/quality summary and the primary plot.
   - Put exact tables and exports collapsed directly beneath their plot or
     metric panel.
   - Separate reward/reconstruction from admission/feasibility evidence.
   - Aggregate compatible shards by factual contract; keep incompatible or
     invalid stores explicit and unpooled.
   - Bound display rows deterministically; compute scientific aggregates over
     the intended complete population.
   - Use human-readable storage units and one-based acquisition numbering.
   - Scientific explanations reference canonical Typst/notation/glossary
     owners; operational counts and provenance remain narrative when an
     equation would add no value.

5. **Verification**
   - Test lazy imports and grouped navigation.
   - Use `AppTest` for actual rerun/widget/output behavior.
   - Use narrow unit fakes only for presentation helpers.
   - Prove expensive projections are absent before explicit dispatch and occur
     exactly once afterward.
   - Test cache invalidation on same-path store replacement.
   - Treat browser rendering and Rerun visual behavior as separate evidence,
     not something `AppTest` proves.

The guide should point to existing focused tests rather than copy long command
transcripts.

### `aria_nbv/aria_nbv/app/README.md`

Keep this operator-facing. It should explain:

- how to launch the current worktree with `uv run nbv-st`;
- the five navigation groups and the purpose of each page;
- which pages read immutable stores, which can launch bounded generation, and
  which are post-hoc inspection only;
- the disabled-by-default file watcher and how to override it;
- how to distinguish a stale Streamlit session, a stale store cache, a missing
  data/config root, and a Rerun-launch failure;
- the smallest focused test and AppTest commands;
- how to add a page without violating lazy-import and state ownership.

Do not put scientific definitions, internal cache-key values, or agent workflow
policy in the README.

## Recovered user requirements

The exact source session
`01a01ac6-8892-7800-b3c3-985a4738b347` and project debriefs consistently add
the following local constraints:

- Both Training Dataset and Rollout Supervision had become overwhelming; the
  desired direction is fewer layers, essential summaries first, and removal of
  non-essential clutter.
- Default presentation should be plot-first. Raw tables remain available but
  collapsed beneath their corresponding plot or metric panel.
- Corpus summaries must aggregate compatible selected shards, while a separate
  active store exists only for drill-down.
- Reward/reconstruction evidence and admission/clearance/intersection evidence
  belong on different tabs.
- Use metrics and human-readable KiB/MiB units rather than raw-byte tables for
  headline storage information.
- Bounded primary candidate geometry may be visible by default. Full-store
  candidate aggregates, deep Q_H reads, and unbounded evidence remain explicit;
  lightweight validation/metadata may load first.
- Display samples may be bounded and deterministic, but aggregate statistics
  must use the complete intended population.
- Streamlit presentation consumes typed read models; it must not reimplement
  Zarr schemas, campaign semantics, or scientific aggregation.
- Scientific explanations should be concise, narrative, and backed by
  canonical equations/symbols/glossary terms where relevant, without runtime
  Typst parsing or duplicated formulas.
- Compatibility aliases that only preserve obsolete private callers are not a
  desired architecture.

These are project policy, not generic Streamlit facts, so the nearest app guide
is the correct durable owner. Historical debriefs remain evidence and should
not become a second live checklist.

Evidence pointers:

- source session line 39792 records the direct request to aggregate across
  shards and reduce Training Dataset / Rollout Supervision clutter;
- source session lines 41849, 41930, 42002, 42045, 42510, and 44442 record,
  respectively, removal of private compatibility aliases, metric cards and
  readable units, table overload, plot-first disclosure, excessive layering,
  and canonical scientific explanations;
- `rollout_summaries/2026-08-17T14-28-20-mkXc-lazy_streamlit_wp5_presentation.md:14-18,38-43`
  records the frozen-reader, explicit-laziness, bounded-display, and metadata-
  first Q_H requirements;
- `rollout_summaries/2026-08-20T13-28-39-M6Fa-aria_nbv_rollout_salvage_and_default_3d_candidate_geometry.md:49-78`
  records default-visible bounded geometry and scientific coordinate context;
- `.agents/memory/history/2026/03/streamlit_counterfactual_panel_2026-03-30.md:14-28`
  records explicit execution and stable cache identity to avoid rerun work;
- `.agents/memory/history/2026/03/rl_streamlit_inspector_2026-03-30.md:18-32`
  records evaluation-first behavior and session cache inputs.

## Current verification surfaces

ARIA-NBV already exercises stronger Streamlit behavior than a new generic skill
would provide:

- [`test_app_router.py`](../../../aria_nbv/tests/app/test_app_router.py) locks
  grouped navigation, lazy imports, sibling page relationships, and headings;
- [`test_streamlit_entry.py`](../../../aria_nbv/tests/test_streamlit_entry.py)
  locks the import-light entrypoint and watcher behavior;
- [`test_training_dataset_panel.py`](../../../aria_nbv/tests/app/panels/test_training_dataset_panel.py)
  and [`test_counterfactual_rollouts_panel.py`](../../../aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py)
  already use `streamlit.testing.v1.AppTest`;
- [`test_stored_rollouts_projection_laziness.py`](../../../aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py)
  protects explicit dispatch, ordered cache identity, same-path replacement,
  and refresh invalidation.

The missing artifact is not another framework tutorial. It is a concise local
map telling agents when these existing owners and tests apply.

The upstream router is intentionally broad, so context loading must remain
bounded: load the router plus only the task-relevant reference files. Load the
framework-internals architecture skill only when public app-development
guidance cannot answer a reproduced cross-layer problem.

## Recommended adoption sequence

1. Add the scoped app `AGENTS.md` with the rules above and verify it with
   `make check-agent-memory` plus the app router/laziness test seams.
2. Add the app README with launch/navigation/troubleshooting information and
   verify every documented command against the worktree environment.
3. In a separate dependency-maintenance change, evaluate upgrading Streamlit
   from the resolved 1.57 environment to a current supported release. Run the
   full app-focused tests and one browser smoke before accepting it.
4. After the verified upgrade exposes `streamlit skills`, install the official
   global meta-skill through that CLI. Do not commit copied upstream reference
   files or virtual-environment symlinks; record only the discovery mechanism
   and precedence in the app guide.
5. Reassess after two or three real UI tasks. Create an ARIA-specific Streamlit
   workflow skill only if the same multi-step procedure is repeatedly missing
   from `agent-behavior`, the official skill, the app guide, and existing test
   commands.

## Explicit non-goals

- No current Streamlit page or behavior refactor.
- No dependency update as part of guidance adoption.
- No vendored upstream skill snapshot.
- No new dashboard/control-plane abstraction.
- No duplicated scientific definitions.
- No replacement of `rerun-nbv-inspector`, `aria-grill`, `codebase-design`, or
  `python-standards`.

## Provenance and limitations

- Repository architecture was navigated with the existing Graphify projection
  and verified against exact source/tests.
- External findings use official Streamlit repository, CLI documentation,
  public architecture/testing documentation, release history, and license.
- Historical requirements were separated from current code truth and checked
  against the exact local source session plus repository debriefs.
- The shared worktree advanced and acquired concurrent, unrelated scientific-
  explanation edits during this read-only research. This report did not edit or
  stage any app source or test file and does not claim those concurrent changes.
