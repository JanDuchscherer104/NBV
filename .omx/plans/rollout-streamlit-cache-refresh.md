# Rollout Streamlit cache refresh

## Goal

Speed repeat interaction with rollout pages using the existing native Streamlit
cache decorators, while preserving replacement/tamper-sensitive artifact keys.

## Scope

1. Keep the current per-store identity as the cache invalidation key; do not
   introduce a fast identity that can accept changed artifact content.
2. Complete the Rollout Supervision clear path, including candidate-population
   projections and the session-local corpus result.
3. Give Training Dataset an explicit cache-refresh action that clears its four
   cached read models and its session-local results.
4. Make the two page controls a single user-facing contract: **Refresh rollout
   caches** clears both page families and reruns.

## Acceptance criteria

- Each heavy cached function is cleared by the unified control.
- A selected store's cache remains keyed by its existing replacement-sensitive
  identity.
- Refresh removes stale training-page readiness/preview/deep results.
- Focused panel tests prove clearing and preserve lazy initial loads.
- Ruff, compileall, focused panel tests, and `git diff --check` pass.

## Stop condition

No new cache backend, persistence layer, dependency, schema, or generation
change is added.
