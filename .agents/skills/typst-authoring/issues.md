# Known ARIA-NBV Typst Authoring Failures

Use this regression checklist before editing equations, notation, figures,
captions, or shared Typst modules.

## 1. Attachment Over-Capture After `_` / `^`

Typst attachments are easy to misread when an attached expression is followed
immediately by a parenthesized argument list.

Bad:

```typst
$ op("IoU")_"3D"(hat(bold(B))_(hat(e)), bold(B)_e^"GT") $
```

Good:

```typst
$ op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e^"GT") $
```

Rule: if the argument list is not part of the attachment, insert a space after
the attached operator.

## 2. Output Indexing vs. Argument Indexing

Bad:

```typst
$ op("Transformer")_theta (bold(X)_t)_i $
```

This reads as indexing the input argument. If the index belongs to the network
output, group the whole call.

Good:

```typst
$ (op("Transformer")_theta (bold(X)_t))_i $
```

## 3. Bolding Policy For Data-Bearing Objects

Bad:

```typst
$ x_q, F_v, V_"occ"^"pr", s_"proj" $
$ bold(cal(P)), bold(cal(Q)), bold(s)_t^"obs" $
```

Good for data vectors, feature fields, voxel tensors, and learned embeddings:

```typst
$ bold(x)_q, bold(F)_v, bold(V)_"occ"^"pr", bold(s)_"proj" $
$ bold(X)_t^"cand", bold(u)_(t,i), bold(h)_t $
```

Do not bold abstract sets, meshes, candidate sets, candidate poses, states, or
operators:

```typst
$ cal(P)_t, cal(Q)_t, cal(M)_e^"GT", q_(t,i), s_t^"obs" $
$ cal(E), cal(A)(s_t), op("argmax", limits: #true)_(q in cal(Q)) $
```

## 3b. ARIA-NBV RRI Component Notation

Bad:

```typst
$ CD(cal(P)_t, cal(M)^"GT") $
$ Delta_t^e = cal(A)_t^e + cal(C)_t^e $
```

Good:

```typst
$ D(cal(P)_t, cal(M)^"GT") $
$ Delta_t^e = D_(P -> M,t)^e + D_(M -> P,t)^e $
```

Rule: thesis-core ARIA-NBV equations use point-mesh error `D`; `CD` remains
historical/background wording only.

## 4. Duplicate Or Ad-Hoc Symbols

Bad:

```typst
$ bold(P)_"semi" $
$ RRI_total(q) $
```

Good:

```typst
#import "../shared/symbols.typ": symb
#import "../shared/equations.typ": eqs

#symb.obs.points_semi
#symb.entity.rri_total
#eqs.entity.objective
```

If a symbol appears in more than one thesis/proposal section, put it in
`docs/typst/shared`.

## 5. Raw Unicode And LaTeX Leakage

Bad:

```typst
$ <raw Unicode alpha> <raw Unicode arrow> <raw Unicode beta> $
$ \mathcal{E} $
```

Good:

```typst
$ alpha -> beta $
$ cal(E) $
```

In markup, use `#sym.*` names. In math, use Typst math names/shorthands and
ARIA-NBV shared macros.

## 6. Figure Inclusion Without Scale And Visual QA

Bad:

```typst
#image("figures/vin_pipeline.png")
```

Good:

```typst
#figure(
  image("figures/vin_pipeline.png", width: 92%),
  caption: [VIN offline-store training pipeline. Logged observations define historical context, counterfactual candidate rendering provides alternative views, and oracle RRI labels supervise candidate scoring.],
) <fig:vin-offline-store>
```

Then compile and inspect the affected page.

## 7. Mermaid-To-Typst Figure Rules

- Keep `.mmd` as the version-controlled source.
- Render locally with Mermaid CLI, the ARIA-NBV Mermaid workflow, or
  `scripts/render_mermaid.sh`.
- Include PNG/SVG/PDF with explicit Typst width.
- Inspect the final Typst page, not only the standalone diagram.
- Captions should state the scientific point, not just list components.

## 8. Fluent But Empty Scientific Prose

Bad:

> This work highlights the crucial role of semantic relevance in the rapidly evolving landscape of AR-based reconstruction.

Good:

> ARIA-NBV uses entity relevance to prioritize candidate views whose expected reconstruction gain concerns the selected target rather than only the scene-level surface.

Rule: replace importance claims with mechanisms, conditions, comparisons, or
measured effects.

## 9. Claim Strength Drift

Bad:

```text
ARIA-NBV solves interactive semantic reconstruction.
```

Good:

```text
ARIA-NBV evaluates whether target-conditioned candidate scoring improves
reconstruction utility under fixed view budgets in an offline ARIA-derived
setting.
```

Rule: planned work, bridge work, and future work must not read like completed
empirical evidence.

## 10. Strict Hygiene Is For Real Documents

Run:

```bash
.agents/skills/typst-authoring/scripts/hygiene_checks.sh --strict docs/typst/thesis/sections
```

Use `--examples` only when intentionally reviewing the bad/good examples in
this skill. Do not normalize fixture warnings as acceptable proposal output.
