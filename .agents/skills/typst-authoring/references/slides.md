# Slides (Typst + definitely-not-isec-slides)

Use this reference when authoring slide decks with our custom template built on:
`@preview/definitely-not-isec-slides:1.0.1`.

## Package metadata (Typst Universe)

- **Template:** `definitely-not-isec-slides`
- **Version:** `1.0.1`
- **Author:** Ernesto Martinez Garcia
- **License:** MIT
- **Minimum Typst:** `0.13.1`
- **Init:** `typst init @preview/definitely-not-isec-slides:1.0.1`

## Core functionality (from the package)

Slide types and layout:

- `#slide(...)` (main slide with header/footer, optional title)
- `#title-slide(...)` (title page)
- `#section-slide(...)` (section divider)
- `#standout-slide(...)` (big centered text)
- `#blank-slide[...]` (full-bleed custom content)

Theme configuration:

- `#show: definitely-not-isec-theme.with(...)`
- `config-info(...)`: title, subtitle, authors, footer, QR
- `config-common(...)`: handout mode, slide wrapper
- `config-colors(...)`: palette and accents
- Slide counter + optional progress bar in footer

Built-in helpers:

- `#note(...)`: speaker notes (pdfpc)
- `#quote-block[...]`: left-accent block
- `#color-block(title: ...)[...]`: boxed block with title and optional icon
- `#showcase-colors`: palette overview

Ecosystem integrations:

- `touying` for slide composition
- `codly` for code blocks
- `fletcher` / `cetz` for diagrams
- `tiaoma` for QR codes
- `showybox` + `tableau-icons` for block styling

## Touying essentials

For current Touying behavior, use the
[`aria-nbv-context` Context7 registry](../../aria-nbv-context/references/context7_library_ids.md)
and verify the installed package before relying on these notes.

Key Touying capabilities to use inside our theme:

- **Slides + themes:** `#show: <theme>.with(...)`, then `#slide[...]` sections.
- **Reveal control:** `#pause` (step), `#meanwhile` (parallel), `#uncover("2-")` (reserve space), `#only("2-")` (no reserve), `#alternatives[...]`.
- **Repeat/step logic:** `#slide(repeat: n, self => [...])` with `self.subslide`.
- **Speaker notes:** `#speaker-note[...]` (can be shown on second screen via `config-common`).
- **Multi-column layout:** `#slide(composer: (1fr, 1fr))[...][...]`.
- **Appendix sections:** `#show: appendix` to mark appendix blocks.
- **Animation in math/diagrams:** `#pause` in math; Touying reducers for `cetz` and `fletcher`.

Recommended usage here:

- Keep `#show: definitely-not-isec-theme.with(...)` as the outer wrapper.
- Use Touying animation/reveal helpers only inside slide bodies.

## Our custom template (local)

We use a lightly adapted version of the template with two local modules:

- `template.typ` (theme + extra macros)
- `notes.typ` (speaker notes helpers)

These are not part of the upstream template. They must live next to your slide
entrypoint and are referenced by:

```
#import "template.typ": *
#import "notes.typ": *
```

## Custom macros used in our slides

From our local template:

- `#good-note(...)` (compact highlight callout)
- Customized `#show figure.caption` for smaller captions
- Global sizing + list spacing presets

Use these alongside package macros like `#color-block` and `#quote-block`.

## Core pattern (entrypoint)

```
#import "template.typ": *
#import "notes.typ": *

#show: definitely-not-isec-theme.with(
  aspect-ratio: "16-9",
  slide-alignment: top,
  progress-bar: true,
  institute: [Your Institute],
  logo: [#image("figures/logo.svg", width: 2cm)],
  config-info(
    title: [Talk Title],
    subtitle: [Subtitle],
    authors: [A. Author, B. Author],
    extra: [Course or Event],
    footer: [
      #grid(
        columns: (1fr, auto, 1fr),
        align: bottom,
        align(left)[First #sym.dot Second],
        align(center)[Event],
        align(right)[#datetime(year: 2026, month: 1, day: 20).display("[day padding:none]. [month repr:short] [year]")],
      )
    ],
    download-qr: "",
  ),
  config-common(handout: false),
  config-colors(primary: rgb("fc5555"), lite: rgb("f4f6fb")),
)

#set text(size: 18pt)
```

## Positive examples (use as templates)

```
#slide(title: [KAN Layer])[
  #block(height: 100%)[
    #grid(
      columns: (1.25fr, 1fr),
      gutter: 0.8cm,
      [
        #color-block(title: [Layer = matrix of 1D functions], spacing: 0.5em)[
          - Each edge learns a univariate mapping
          $ phi_(l,j,i): RR -> RR. $

          - Activation of the $j$-th neuron in layer $l+1$: 

          $
            x_(l+1,j) = sum_(i=1)^(n_l) phi_(l,j,i)(x_(l,i))
          $

          - A single KAN layer can be written in *matrix form*:

          #text(size: 16pt)[
            $
              bold(x)_(l+1) =
              underbrace(
                mat(
                  phi_(l,1,1)(dot.c), phi_(l,1,2)(dot.c), dots, phi_(l,1,n_l)(dot.c);
                  phi_(l,2,1)(dot.c), phi_(l,2,2)(dot.c), dots, phi_(l,2,n_l)(dot.c);
                  dots.v, dots.v, , dots.v;
                  phi_(l,n_(l+1),1)(dot.c), phi_(l,n_(l+1),2)(dot.c), dots, phi_(l,n_(l+1),n_l)(dot.c)
                ),
                #v(0.5cm) #text(size: 26pt)[$bold(Phi)_l in (RR -> RR)^(n_(l+1) times n_l)$]
              )
              bold(x)_l
              \
            $
          ]
        ]
      ],
      [
        #block(height: 100%)[
          #grid(
            columns: 1,
            rows: (1fr, auto),
            gutter: 0.55cm,
            [
              #align(center + horizon)[
                #figure(
                  image(fig_path + "spline_notation_kan_only.png", height: 55%),
                  caption: text(size: 11pt, fill: gray)[B-spline parametrization and grid refinement. @liu_kan_2025],
                )
                #align(center + horizon)[
                  #figure(
                    image(fig_path + "kan_function_matrix.svg", width: 65%),
                    caption: text(size: 11pt, fill: gray)[KAN layer in matrix form],
                  )
                ]
              ]
            ],
            [
              #color-block(title: [General KAN with $L$ layers], spacing: 0.45em)[
                #text(size: 16pt)[
                  $
                    "KAN"(bold(x)) =
                    (bold(Phi)_(L-1) compose bold(Phi)_(L-2) compose dots compose bold(Phi)_0)(bold(x))\
                  $
                  KART #sym.image KAN of shape $[n arrow.r 2n+1 arrow.r 1]$
                ]
              ]
            ],
          )
        ]
      ],
    )
  ]
]
```

```
#slide(title: [Edge Functions - Residual Splines])[
  #grid(
    columns: (1.05fr, 0.95fr),
    gutter: 0.8cm,
    [
      #color-block(title: [Edge - Residual Spline], spacing: 0.55em)[
        $
          phi(x) = #text(fill: green)[$w_b$] b(x) + #text(fill: green)[$w_s$] sum_i #text(fill: green)[$c_i$] #text(fill: red)[$B_(i)(x)$]
        $

        - Trainable (per edge, backprop): #text(fill: green)[$c_i$], #text(fill: green)[$w_b$], #text(fill: green)[$w_s$]
        - #text(fill: red)[$B_(i)(x)$]: B-spline basis functions, fixed given the current grid.
        - $b(x)$: fixed *global* non-linearity (i.e. SiLU).
          #v(0.1em)
          #text(size: 15pt)[
            1. Ensure $phi$ is well-defined on $RR$
            2. Residual path eases optimization -- learn deviation from $b(x)$ rather than full function
          ]
      ]
      #figure(
        image(fig_path + "silu_minimal.svg", width: 50%),
      )
    ],
    [
      #figure(
        image(fig_path + "kan_residual_spline.svg", width: 100%),
        caption: text(
          size: 11pt,
          fill: gray,
        )[Residual spline edge function: local basis #sym.arrow.r spline #sym.arrow.r $phi(x)$.],
      )
      #text(size: 15pt)[
        #color-block(title: [Why B-Splines?])[
          - *local*, *translation-invariant* basis \
            #text(size: 14pt)[
              - local capacity allocation \
              - continual learning #sym.arrow.t, catastrophic forgetting #sym.arrow.b
            ]
          - Allows for other orthogonal bases (Fourier, Chebyshev).
          - Locality #sym.arrow.l.r global efficiency.
        ]
      ]
    ],
  )
]
```

```
#slide(title: [Grid Update - Knot Relocation])[
  #set text(size: 17pt)

  #grid(
    columns: (1.3fr, 1.3fr),
    [
      #color-block(title: [Keep knots where the data lives], spacing: 0.55em)[
        - _Non-stationary_ activations in training, but splines live on bounded grid
        - #strong[Grid update:] periodically estimate activation distributions; _move knots_ to maintain coverage.
        - _non-differentiable_ reparameterization
      ]
      #figure(
        image(fig_path + "two_gaussians_drift_minimal.svg", width: 92%),
        caption: text(size: 12pt)[Non-stationarity motivates knot relocation.],
      )
    ],
    [
      #figure(
        image(fig_path + "spline_notation_grid_extension.jpg", width: 80%),
        caption: [@liu_kan_2025],
      )
      #quote-block[
        _Grid updates_ reallocate representational capacity at *fixed number of knots* (contrast: grid extension adds knots).
      ]
    ],
  )
]
```

```
#slide(title: [Grid Extension: Accuracy Scaling])[
  #grid(
    columns: (1fr, 0.8fr),
    gutter: 0.8cm,
    [
      #color-block(title: [Key idea], spacing: 0.55em)[
        - *Grid extension*: add knots ($G$ #sym.arrow.r $G'$) #sym.arrow.r higher spline resolution.
        - Curriculum-style schedule:
          1. Start with coarse spatial resolution -- fewer knots, global structure, simpler optimization.
          2. Gradually increase resolution, initialize finer splines via least-squares fit to coarse spline.

        - Monitor validation error to stop grid extension once improvement ceases.
        - $"RMSE" prop G^(-4)$ #text(size: 12pt)[(on test split)]
      ]

    ],
    [
      #figure(
        image(fig_path + "extend_grid_left.png", width: 100%),
        caption: text(size: 10pt)[Staircase-like loss drops after each grid refinement. @liu_kan_2025],
      )
      #v(0.4em)
      #figure(
        image(fig_path + "kan_external_vs_internal_dof.svg", width: 40%),
      )
      #v(0.4em)
      #text(size: 14pt)[
        $
          {c'_j} =
          op("argmin", limits: #true)_(\{c'_j\})
          bb(E)_(x ~ p(x))
          (sum_(j=0)^(G_2+k-1) c'_j B'_(j)(x) - sum_(i=0)^(G_1+k-1) c_i B_(i)(x))^2
        $
      ]
    ],
  )
]
```

## Visual inspection loop (required)

For tables, equations, and diagrams, always isolate and render to PNG first:

- Use `.agents/skills/typst-authoring/scripts/render_png.sh`
- Iterate until the PNG is clean, then integrate into the main deck

## Notes

- Avoid Unicode symbols in slides; use `#sym.*` or math shorthands.
- Keep caption sizes compact for slides (`#show figure.caption: ...`).
- Use `#set grid(gutter: ...)` and consistent padding for multi-column layouts.
