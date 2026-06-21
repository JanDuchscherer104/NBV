# Typst Math Attachments And Operator Calls

This reference targets the failure modes observed in ARIA-NBV proposal
equations.

## Core Rule

After an attachment (`_` or `^`), do not place a non-subscript argument list
directly adjacent unless the rendered result has been checked. Insert a space
before arguments that should belong to the operator/function call rather than
to the attachment.

Bad:

```typst
$ op("IoU")_"3D"(hat(bold(B))_(hat(e)), bold(B)_e^"GT") $
```

Good:

```typst
$ op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e^"GT") $
```

## Output Indexing

If a subscript denotes an output component, group the whole call first.

Bad:

```typst
$ op("MLP")_theta (bold(x)_q)_i $
```

Good:

```typst
$ (op("MLP")_theta (bold(x)_q))_i $
```

## Transformer / Network Notation

Prefer this pattern for learned modules:

```typst
$ bold(h)_i = (op("Transformer")_theta (bold(X)_t))_i $
$ hat(r)_q = op("MLP")_phi (bold(h)_q) $
```

If the network is important enough to appear more than once, define a shared
equation or macro.

## Quoted Roman Labels

Use quoted labels for domain-specific roman subscripts/superscripts:

```typst
$ bold(V)_"occ"^"pr" $
$ bold(V)_"count"^"norm" $
$ bold(s)_"proj" $
```

## Anti-Patterns

Avoid:

```typst
$ bold(bold(X)) $
$ op("IoU")_3D(...) $
$ \mathbf{x} $
$ \mathcal{Q} $
```

Prefer:

```typst
$ bold(X) $
$ op("IoU")_"3D" (...) $
$ bold(x) $
$ cal(Q) $
```

## QA Requirement

Every new or changed displayed equation must be checked by at least one compile
and rendered-page inspection pass:

```bash
cd docs && typst compile typst/thesis/main.typ /tmp/check.pdf --root .
.agents/skills/typst-authoring/scripts/render_png.sh -i path/to/file.typ -o /tmp/renders --root docs --pages <page>
```
