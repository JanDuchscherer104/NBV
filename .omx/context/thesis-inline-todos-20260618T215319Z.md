# Thesis Inline TODO Extraction - 2026-06-18

## Scope

Active thesis Typst sections contain two TODO classes:

- Plain `// TODO` comments inside active prose, equations, and figure includes.
  These are immediate cleanup items for this run.
- Explicit `#validation_todo`, `#decision_todo`, `#research_todo`, and
  related draft-marker macros. These are thesis evidence gates and remain in
  place unless their local prose also has a plain TODO.

## Immediate Plain TODOs

1. `docs/typst/thesis/sections/03-01-formal-state.typ`
   - `qh_actor_oracle_contract.pdf` include comment: actor-visible inputs and
     oracle-only assets should read horizontally; actor-visible modalities
     should be compact/grid-like, with target descriptor allowed its own line.
2. `docs/typst/thesis/sections/03-01-formal-state.typ`
   - `cal(S)^hist`, `cal(S)^cf0`, and `cal(S)^oracle` are used in the NBV
     tuple before they are defined. Add definitions near the tuple and use the
     shared symbol/equation surfaces.
3. `docs/typst/thesis/sections/02-02-geometric-learning.typ`
   - The section needs compact equations for candidate-row equivariance,
     masking, and local-frame/gauge structure, grounded in Bronstein-style
     geometric learning, Set Transformer, and QCNet-style relative encodings.
4. `docs/typst/thesis/sections/02-02-geometric-learning.typ`
   - Architecture ladder omits levels such as online learning and continuous
     policies. Expand the ladder without promoting bridge work into thesis-core
     claims.
5. `docs/typst/thesis/sections/03-02-data-generation.typ`
   - Target-RRI reward, finite-horizon return, endpoint gain, and log gain are
     stacked without conceptual explanation. Introduce each equation separately
     and cite/source adaptations.
6. `docs/typst/thesis/sections/03-method.typ`
   - Backbone/representation ladder material may be too table-heavy; rewrite or
     mark it so roadmap/internal-design material is explicitly visible as
     thesis design scaffolding rather than final empirical result.
7. `docs/typst/thesis/sections/03-method.typ`
   - Descriptor core and encoder escalation plan tables use raw
     `TODO(^mark-wip-internal)` comments; convert them to explicit marker prose
     or approved draft-marker surfaces.
8. `docs/typst/thesis/sections/03-method.typ`
   - Descriptor block table is too wordy and lacks symbols/equations. Replace
     table-heavy wording with compact symbolic descriptors or equation-backed
     prose.
9. `docs/typst/thesis/sections/03-method.typ`
   - Directional-memory equations need domains, shapes, operator semantics,
     conceptual explanation, and citations; the existing figure may serve the
     diagram role.
10. `docs/typst/thesis/sections/03-method.typ`
   - CORAL section needs equations and prose for ARIA-NBV-specific
     modifications from the seminar/code path: quantile bins, CORAL threshold
     levels, class probabilities, expected ordinal score, and optional
     monotone bin representatives.
11. `docs/typst/thesis/sections/03-method.typ`
   - `qh_vin_gnn_architecture.pdf` include comment: diagram labels need larger
     fonts, bold title-case node names, shorter text, and stronger symbolic
     naming for legibility.

Exact extraction command and current hit set:

```sh
rg -n "//\\s*TODO" docs/typst/thesis/sections docs/typst/thesis/main.typ
```

- `docs/typst/thesis/sections/02-02-geometric-learning.typ:9`
- `docs/typst/thesis/sections/02-02-geometric-learning.typ:54`
- `docs/typst/thesis/sections/03-01-formal-state.typ:11`
- `docs/typst/thesis/sections/03-01-formal-state.typ:19`
- `docs/typst/thesis/sections/03-02-data-generation.typ:107`
- `docs/typst/thesis/sections/03-method.typ:55`
- `docs/typst/thesis/sections/03-method.typ:56`
- `docs/typst/thesis/sections/03-method.typ:100`
- `docs/typst/thesis/sections/03-method.typ:125`
- `docs/typst/thesis/sections/03-method.typ:154`
- `docs/typst/thesis/sections/03-method.typ:216`
- `docs/typst/thesis/sections/03-method.typ:307`
- `docs/typst/thesis/sections/03-method.typ:336`

## Future Evidence Gates Left Intact

Marker macros in `docs/typst/thesis/main.typ`,
`docs/typst/thesis/sections/01-introduction.typ`,
`docs/typst/thesis/sections/02-background.typ`,
`docs/typst/thesis/sections/03-method.typ`,
`docs/typst/thesis/sections/03-02-data-generation.typ`,
`docs/typst/thesis/sections/04-evaluation.typ`,
`docs/typst/thesis/sections/05-conclusion.typ`, and
`docs/typst/thesis/sections/06-draft-open-work.typ` remain explicit thesis
gates for missing evidence, final experiments, final public narrative, or
advisor-facing decisions.

## Verification Target

- Add a narrow agents-db TODO for the immediate plain TODO set.
- Resolve every plain TODO comment returned by the extraction command above.
- Verify with agents-db validation, Mermaid lint/render, a focused Typst
  compile, and a final plain TODO grep over active thesis sections.
