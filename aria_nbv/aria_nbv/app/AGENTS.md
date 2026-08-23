---
scope: package
applies_to: aria_nbv/aria_nbv/app/**
summary: Streamlit ownership, progressive disclosure, lazy execution, and focused verification.
---

# Streamlit App Guidance

Use the globally installed `developing-with-streamlit` skill for every
Streamlit task. Its discovery script resolves the reference material bundled
with this project's installed Streamlit version. Load only the references that
match the task. Use `rerun-nbv-inspector` for Rerun entities, recordings,
blueprints, camera/depth evidence, and viewer behavior.

## Owners

- `streamlit_app.py` is the import-light CLI entrypoint and file-watcher owner.
- `app.py` owns grouped navigation, exception containment, and lazy page
  imports.
- `state_types.py` owns Streamlit-free state types; `state.py` adapts them to
  session state.
- `controller.py` owns single-step orchestration and compute caching.
- Page modules render typed projections. Persisted semantics, Zarr decoding,
  scientific reducers, and campaign behavior stay in their package owners.
- Stable panel facades stay thin. Private concern modules own their behavior
  directly; do not add compatibility-alias carpets between them.

## Interaction Contract

- Lead with the answer or readiness verdict and one sentence interpreting the
  decisive evidence, then show essential metrics and the primary plot.
- Before explaining a scientific metric beyond that sentence, read and apply
  the conditional
  [scientific interpretation rubric](references/scientific-interpretation.md).
- Keep raw/exact tables and exports subordinate to the interpretation and
  collapsed directly beneath it.
- Keep operational counts and provenance on the lightweight path as concise
  narrative; do not load the scientific rubric or invent equations for them.
- Separate reward/reconstruction evidence from admission/feasibility evidence.
- Aggregate compatible shards by their persisted contract. Keep invalid or
  incompatible stores visible and unpooled.
- Bounded primary diagnostics may render by default. Full-store aggregation,
  deep Q_H reads, and unbounded evidence require explicit user dispatch.
- A collapsed expander or inactive tab is not a computation boundary. Guard
  expensive work with explicit state or a dynamic container before computing.
- Display samples may be bounded and deterministic; scientific aggregates use
  the complete intended population.
- Use human-readable storage units and one-based acquisition numbering in the
  presentation layer.

## State And Cache Contract

- Treat every interaction as a top-to-bottom rerun.
- Namespace widget and session keys by page and selected-store identity.
- Use `st.cache_data` for serializable projections and `st.cache_resource` only
  for deliberately shared, thread-safe resources.
- Bind store-backed caches to validated content/promotion identity and detect
  same-path atomic replacement. Refresh actions clear every dependent cache.
- Prefer forms or explicit action controls when several inputs feed expensive
  work. Keep the initial page render metadata-first.

## Verification

- Router or entrypoint changes: run `tests/app/test_app_router.py` and
  `tests/test_streamlit_entry.py`.
- Page behavior: use `streamlit.testing.v1.AppTest`; unit fakes are appropriate
  only for isolated presentation helpers.
- Expensive projections: prove they are absent before dispatch, occur once
  after dispatch, and invalidate when a selected store is atomically replaced.
- Rerun and browser rendering need their own smoke or visual evidence; AppTest
  does not prove native/web viewer behavior or pixel layout.
- Run Ruff format/check and the narrowest affected Pytest targets before a
  completion claim.
