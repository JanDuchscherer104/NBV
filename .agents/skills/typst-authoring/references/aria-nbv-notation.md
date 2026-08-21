# ARIA-NBV Notation Policy

## Source Of Truth

Use the shared Typst library in `docs/typst/shared`:

```text
docs/typst/shared/
  symbols.typ       # facade: symb.frame, symb.vin, symb.oracle, ...
  equations.typ     # facade: eqs.rri, eqs.vin, eqs.entity, ...
  math.typ          # helpers such as T(A, B)
  terms.typ         # legacy generated acronym facade, not new prose API
  glossary.typ      # glossary source
  macros.typ        # reusable document macros
```

Import relative to the file being edited. From an active thesis section under
`docs/typst/thesis/sections/`, the shared library is reached through
`../../shared/...`; fixtures under `.agents/skills` can use root-relative
imports with `--root .`.

## Shared Modules

Use these facades before writing raw notation:

```typst
#symb.frame.w
#symb.frame.r
#symb.frame.cq
#symb.vin.pose_emb
#symb.vin.sem_proj
#symb.vin.field_v
#symb.oracle.candidates
#symb.oracle.rri
#symb.entity.rri_total
#eqs.rri.rri
#eqs.entity.objective
#T(symb.frame.w, symb.frame.r)
```

Current shared symbol modules:

| Module | Scope |
| --- | --- |
| `symb.ase` | ASE dataset, snippets, and mesh-supervised substrate. |
| `symb.entity` | Targets, entities, OBBs, target descriptors, and target RRI. |
| `symb.frame` | Coordinate frames, rig/camera frames, poses, and transforms. |
| `symb.obs` | Observations, semi-dense points, images, depth, and masks. |
| `symb.oracle` | Candidate sets, oracle labels, RRI, and privileged assets. |
| `symb.rl` | Rollout, policy, value, action, mask, and horizon notation. |
| `symb.shape` | Meshes, points, surfaces, and reconstruction geometry. |
| `symb.vin` | VIN/EVL feature fields, embeddings, voxel tensors, and scorer inputs. |

Current shared equation modules:

| Module | Scope |
| --- | --- |
| `eqs.action` | Candidate action and validity definitions. |
| `eqs.binning` | Ordinal bins and discretization contracts. |
| `eqs.coral` | CORAL ordinal regression equations. |
| `eqs.coverage` | Coverage and visibility utility definitions. |
| `eqs.entity` | Target-specific objectives and entity-aware metrics. |
| `eqs.features` | Feature projection and representation equations. |
| `eqs.metrics` | Evaluation metrics and reporting helpers. |
| `eqs.rl` | Rollout return, value, and finite-horizon learning equations. |
| `eqs.rri` | Scene-level RRI and reconstruction-error equations. |
| `eqs.vin` | VIN-style one-step scorer equations. |

## Typed Convention

Use a typed convention, not blanket bolding:

- Use `cal(...)` for abstract sets, spaces, point sets, candidate sets, meshes,
  face sets, and geometric collections: `cal(P)_t`, `cal(Q)_t`,
  `cal(M)^"GT"`, `cal(M)_e^"GT"`, `cal(F)^"GT"`.
- Use `bold(...)` for coordinate vectors, matrices, tensors, feature fields,
  embeddings, image/depth tensors, voxel tensors, and implementation arrays:
  `bold(x)_q`, `bold(F)_v`, `bold(X)_t^"cand"`, `bold(u)_(t,i)`.
- Use `bb(...)` for number/probability spaces and expectations:
  `bb(R)^3`, `bb(E)`, `bb(P)`, `bb(1)`.
- Use `op("...")` for named mathematical operators and manifolds:
  `op("argmax", limits: #true)`, `op("RRI")`, `op("SO")(2)`.
- Use quoted strings for semantic tags: `s_t^"obs"`,
  `bold(F)_t^"EVL"`, `bold(V)_"occ"^"pr"`.

Examples:

```typst
$ cal(P)_t, cal(Q)_t, cal(M)_e^"GT", q_(t,i) $
$ bold(x)_q, bold(F)_v, bold(X)_t^"cand", bold(u)_(t,i) $
$ op("argmax", limits: #true)_(q in cal(Q)) op("RRI") (q) $
```

Negative examples that must not appear in advisor-facing thesis math:

```typst
$ bold(cal(P)), bold(cal(Q)), bold(cal(M))_"GT" $
$ bold(Q)_t, bold(s)_t^"obs", S O(2) $
```

## ARIA-NBV Core Objects

Use these canonical meanings:

| Object | Shared form | Meaning |
| --- | --- | --- |
| Accumulated point set | `#symb.obs.points_t` / `cal(P)_t` | Abstract actor-visible geometry. |
| Candidate set | `#symb.rl.candidate_table` / `cal(Q)_t` | Finite unordered candidate rows. |
| Candidate pose | `#symb.rl.candidate_qti` / `q_(t,i)` | Candidate action row, not a tensor. |
| Candidate features | `#symb.rl.candidate_features` / `bold(X)_t^"cand"` | Tensor/table passed to a model. |
| Abstract states | `#symb.rl.s_obs`, `#symb.rl.s_cf0`, `#symb.rl.s_oracle` | Plain `s`, never bold. |
| Learned embeddings | `bold(h)_t`, `#symb.rl.candidate_token` | Data-bearing model states/tokens. |
| Scene GT mesh | `#symb.ase.mesh` / `cal(M)^"GT"` | Oracle/evaluation surface. |
| Target GT crop | `#symb.ase.mesh_target` / `cal(M)_e^"GT"` | Target-only oracle/evaluation surface. |

For thesis-core reconstruction quality, use point-mesh error `D` and
directional components:

```typst
$ D_(P -> M), D_(M -> P), Delta_t^e $
```

Do not describe the implemented ARIA-NBV target objective as generic
point-cloud Chamfer distance. Historical seminar text may still use `CD`; new
proposal/thesis math should use `D` and the shared equations.

## Adding Missing Notation

The authoring contract is intentionally scope-aware. A symbol belongs in a
shared facade when it recurs as domain notation across thesis consumers; an
equation-local binder, summation index, set member, or table index does not.
Use `make typst-authoring-contract` after notation edits. Its fixtures include
both a recurring raw symbol that must be promoted and local binders that must
remain legal.

ARIA-NBV has three coupled notation stores:

- `symbols.typ` / `equations.typ` provide autocomplete-friendly Typst APIs
  (`#symb...`, `#eqs...`) for math in thesis text, slides, and diagrams.
- `glossary.typ` uses Glossarium as the prose term source; write
  Glossarium-native `@term` or `@term:short` references instead of new `#gls`
  wrappers.
- `symbols.typ` and `equations.typ` carry the stable key, TeX, description, and
  thesis-list metadata beside their shared Typst APIs. The generated
  `docs/notation.yml` drives Quarto lookup tables, Lua helpers, and agent context.

When a new symbol is needed:

1. Pick the domain module: `symbols/vin.typ`, `symbols/oracle.typ`,
   `symbols/entity.typ`, and so on.
2. Add a comment describing semantics and usage.
3. Export through `symbols.typ` if a new module is added.
4. Add reusable formulae under `equations/*.typ` and export through
   `equations.typ`.
5. Add or update the matching metadata record in the shared facade and connect
   glossary records through `symbol_refs` or `equation_refs` when a term owns the symbol.
6. Use the shared symbol/equation in the document.
7. Run `make glossary` so generated Quarto, Typst, Lua, JSONL, and notation
   artifacts stay synchronized.
8. Compile a fixture or the affected document.
9. If the new term needs a glossary entry, edit
   `docs/typst/shared/glossary.typ`, use native Glossarium references in prose,
   and verify generated Typst/Quarto glossary artifacts changed as expected.

Do not create a local one-off alias in a thesis section if the symbol will
recur.

## Compatibility Aliases

Some shared keys retain older names for compatibility, for example
`symb.oracle.acc`, `symb.oracle.comp`, and `eqs.rri.cd`. Their rendered
notation now follows the thesis convention (`D_(P -> M)`, `D_(M -> P)`, and
aggregate `D`). Do not infer old `cal(A)` / `cal(C)` or `CD(...)` semantics
from compatibility key names.

## ARIA-NBV Prose Convention

Use project terms consistently:

- ARIA-NBV, not ARIA NBV.
- Next-best view (NBV) on first definition, NBV afterwards.
- Relative Reconstruction Improvement (RRI) on first definition, RRI
  afterwards.
- Semi-dense point cloud, candidate view, candidate pose, target-specific RRI,
  VIN proxy, oracle labeler.

Avoid uncontrolled synonyms in thesis prose.
