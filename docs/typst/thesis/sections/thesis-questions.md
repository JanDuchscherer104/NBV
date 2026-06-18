# Questions w.r.t. the thesis (structure)

- Where should we introduce the problem statement and research questions?
- Where should we elaborate on geometric isomorphisms (that exist for the problem) and their relevance to designing a next-best-view prediction system that leverages geometric priors and inductive biases? Also, where to map from these isomorphisms to concrete architectural choices and design decisions?
  - 02-0X-theory-background.typ?
-
- Where should we elaborate on the employed dataset(s)?

## 2026-06-18 structure decision

- Keep `03-method.typ` as the Method chapter entrypoint.
- Use `03-01-formal-state.typ` for the formal state / oracle boundary.
- Use `03-02-data-generation.typ` for oracle target-task sampling, target-specific RRI labels, rollout supervision, and headroom diagnostics.
- Do not make deployable automatic target discovery the target-selection claim. In the current thesis seed, target selection belongs to oracle data generation; the learned model is target-conditioned view selection.
