#import "@preview/definitely-not-isec-slides:1.0.1": *
#import "@preview/tableau-icons:0.331.0": *
#import "@preview/muchpdf:0.1.1": muchpdf
#import "@preview/codly:1.3.0": *
#import "@preview/tdtr:0.5.0": *
// Shared math symbols (also imported by slides; safe to import here for helpers).
#import "macros.typ": *

#let theme_color_primary_hm = rgb("fc5555")
#let theme_color_block = rgb("f4f6fb")
#let theme_color_footer = rgb("808080")

// ---------------------------------------------------------------------------
// Note helpers
// ---------------------------------------------------------------------------

#let note_inset = 1em
#let note_border_radius = 0.5em

#let note_info_border_color = black
#let note_info_background_color = gray.lighten(80%)
#let note_warning_border_color = red
#let note_warning_background_color = orange.lighten(80%)
#let note_good_border_color = green
#let note_good_background_color = lime.lighten(80%)

#let note-box(
  content,
  width: auto,
  background: note_info_background_color,
  border: note_info_border_color,
  bold: true,
) = {
  let weight = "light"
  if bold {
    weight = "semibold"
  }

  block(
    stroke: 1pt + border,
    fill: background,
    inset: note_inset,
    radius: note_border_radius,
    width: width,
  )[
    #set text(fill: black, weight: weight)
    #content
  ]
}

#let note(content, width: auto, background: note_info_background_color, border: note_info_border_color, bold: true) = {
  note-box(content, width: width, background: background, border: border, bold: bold)
}

#let warning-note(content, width: auto) = {
  note-box(
    content,
    width: width,
    background: note_warning_background_color,
    border: note_warning_border_color,
    bold: true,
  )
}

#let good-note(content, width: auto) = {
  note-box(
    content,
    width: width,
    background: note_good_background_color,
    border: note_good_border_color,
    bold: true,
  )
}

#let todo() = {
  set text(black)
  text(size: 120pt)[#emoji.chicken.baby #text(fill: gradient.linear(..color.map.rainbow))[TUDÜ]]
}

// ---------------------------------------------------------------------------
// Code blocks (minimal raw styling)
// ---------------------------------------------------------------------------

/// Render a minimal code block (raw) for slides.
#let code-block(
  body,
  size: 13pt,
  fill: theme_color_block,
  stroke: 0.75pt + theme_color_block.darken(12%),
  radius: 8pt,
  inset: (x: 0.6em, y: 0.45em),
) = [
  #show raw.where(block: true): set text(font: "DejaVu Sans Mono", size: size)
  #show raw.where(block: true): block.with(
    fill: fill,
    stroke: stroke,
    radius: radius,
    inset: inset,
  )
  #body
]

/// Code block wrapped as a captioned figure (for slides).
#let code-figure(
  caption: none,
  size: 13pt,
  body,
) = figure(
  caption: caption,
  code-block(size: size)[body],
)

// Redefine the slide function to use custom logo in header (no institute name)
#let slide(
  title: auto,
  alignment: none,
  outlined: true,
  ..args,
) = touying-slide-wrapper(self => {
  let info = self.info + args.named()

  // Custom Header with logo only (no institute name)
  let header(self) = {
    let hdr = if title != auto { title } else { self.store.header }
    show heading: set text(size: 24pt, weight: "semibold")

    grid(
      columns: (self.page.margin.left, 1fr, auto, 0.5cm),
      block(), heading(level: 1, outlined: outlined, hdr), move(dy: -0.31cm, self.store.logo), block(),
    )
  }

  // Footer with page numbers and date
  let footer(self) = context {
    set block(height: 100%, width: 100%)
    set text(size: 15pt, fill: self.colors.footer)

    grid(
      columns: (self.page.margin.bottom - 1.68%, 1.3%, auto, 1cm),
      block(fill: self.colors.primary)[
        #set align(center + horizon)
        #set text(fill: white, size: 14pt)
        #utils.slide-counter.display()
      ],
      block(),
      block[
        #set align(left + horizon)
        #set text(size: 14pt)
        #info.at("footer", default: "")
      ],
      block(),
    )

    if self.store.progress-bar {
      place(bottom + left, float: true, move(dy: 1.05cm, components.progress-bar(
        height: 3pt,
        self.colors.primary,
        white,
      )))
    }
  }

  let self = utils.merge-dicts(self, config-page(
    header: header,
    footer: footer,
  ))

  set align(
    if alignment == none {
      self.store.default-alignment
    } else {
      alignment
    },
  )

  touying-slide(self: self, ..args)
})

// Default figure caption (title) styling for slides.
#show figure.caption: set text(size: 14pt)

// Override color-block to have rounded corners
#let color-block(
  title: [],
  icon: none,
  spacing: 0.78em,
  color: none,
  color-body: none,
  body,
) = [
  #touying-fn-wrapper((self: none) => [
    #show emph: it => {
      text(weight: "medium", fill: self.colors.primary, it.body)
    }

    #showybox(
      title-style: (
        color: white,
        sep-thickness: 0pt,
      ),
      frame: (
        radius: 8pt, // Rounded corners!
        thickness: 0pt,
        border-color: if color == none { self.colors.primary } else { color },
        title-color: if color == none { self.colors.primary } else { color },
        body-color: if color-body == none { self.colors.lite } else { color-body },
        inset: (x: 0.55em, y: 0.65em),
      ),
      above: spacing,
      below: spacing,
      title: if icon == none {
        align(horizon)[#strong(title)]
      } else {
        align(horizon)[
          #draw-icon(icon, height: 1.2em, baseline: 20%, fill: white) #h(0.2cm) #strong[#title]
        ]
      },
      body,
    )
  ])
]

#let io-formulation(input-items, output-items) = [
  #grid(
    gutter: 0.4cm,
    color-block(title: [Input], color-body: rgb("#d5e8d4"))[
      #input-items
    ],
    color-block(title: [Output], color-body: rgb("#f8cecc"))[
      #output-items
    ],
  )
]

// ---------------------------------------------------------------------------
// tdtr helpers (tidy trees)
// ---------------------------------------------------------------------------

/// Compact tdtr tree visualization for EVL backbone output dictionaries.
///
/// This is intended to replace screenshot-style "rich_summary(...)" outputs in
/// slides with a structured view grouped by namespace (voxel/neck/obbs/rgb).
///
/// Note: Leaf labels are schematic (symbolic shapes), so the diagram stays
/// stable across runs and configs.
#let evl-backbone-tree(
  compact: true,
  text-size: 9pt,
  node-width: 15em,
  spacing: (10pt, 16pt),
) = {
  let group = metadata("group")
  let leaf = metadata("leaf")

  let tree = tidy-tree-graph.with(
    compact: compact,
    text-size: text-size,
    node-width: node-width,
    node-inset: 3pt,
    spacing: spacing,
    draw-edge: tidy-tree-draws.horizontal-vertical-draw-edge,
    draw-node: (
      tidy-tree-draws.metadata-match-draw-node.with(
        matches: (
          group: (fill: theme_color_primary_hm.lighten(75%), stroke: 0.6pt + theme_color_primary_hm),
          leaf: (fill: theme_color_block, stroke: 0.5pt + theme_color_block.darken(18%)),
        ),
        default: (fill: theme_color_block, stroke: 0.5pt + theme_color_block.darken(18%)),
      ),
    ),
  )

  tree[
    - EVL backbone outputs (EvlBackboneOutput) #group
      - Grid contract (geometry + frame) #group
        - Anchor + pose #group
          - [#symb.frame.v voxel grid anchored at #symb.ase.traj_final] #leaf
          - [t_world_voxel: PoseTW(#symb.shape.B, 12) = #T(symb.frame.w, symb.frame.v)] #leaf
          - [voxel_select_t: Tensor(#symb.shape.B, 1) int64 (optional)] #leaf
        - Metric extent #group
          - [voxel_extent: Tensor(#symb.shape.B, 6) in meters (voxel frame)] #leaf
        - Voxel centers (optional) #group
          - [pts_world: Tensor(#symb.shape.B, #symb.shape.Vvox, 3) (world)] #leaf
      - Input/evidence features (voxel/(...)) #group
        - Occupied evidence #group
          - [#symb.vin.occ_in : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - Free-space evidence (optional) #group
          - [#symb.vin.free_in : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - Coverage / visibility counts #group
          - [#symb.vin.counts : Tensor(#symb.shape.B, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) int64] #leaf
          - [counts_m: Tensor(#symb.shape.B, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) (debug)] #leaf
      - Internal voxel features (voxel/feat, neck/(...)) #group
        - Raw lifted voxel features (optional) #group
          - [voxel_feat: Tensor(#symb.shape.B, #symb.shape.Fin, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - Neck features (optional) #group
          - [occ_feat: Tensor(#symb.shape.B, #symb.shape.Fhead, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
          - [obb_feat: Tensor(#symb.shape.B, #symb.shape.Fhead, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
      - Head features (dense voxel heads) #group
        - Surface reconstruction #group
          - [#symb.vin.occ_pr : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - OBB detection #group
          - Centerness (anchor for NMS) #group
            - [#symb.vin.cent_pr : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
          - Regression heads (optional) #group
            - [bbox_pr: Tensor(#symb.shape.B, 7, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
            - [clas_pr: Tensor(#symb.shape.B, #symb.shape.K, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
      - Post-processing (obbs/(...)) #group
        - Post-NMS boxes (optional) #group
          - [obbs_pr_nms: ObbTW(#symb.shape.B, #symb.shape.M, 34)] #leaf
        - Snippet-frame boxes (optional) #group
          - [obb_pred: ObbTW(#symb.shape.B, #symb.shape.M, 34)] #leaf
        - Taxonomy + probabilities (optional) #group
          - [sem_id_to_name: dict(int, str)] #leaf
      - RGB debug features (rgb/(...)) #group
        - 2D features (optional) #group
          - [feat2d_upsampled: Tensor(#symb.shape.B, #symb.shape.Tlen, C, Hp, Wp)] #leaf
        - Tokens (optional) #group
          - [token2d: Tensor or list(Tensor)] #leaf
  ]
}

/// Multi-panel EVL backbone output visualization (split by semantic group).
///
/// Rationale: `EvlBackboneOutput` is wide; splitting into multiple trees keeps
/// each view narrow and makes it easier to compare occ vs OBB heads.
// Shared style wrapper for the EVL trees.
#let _evl-tree-style(compact, text-size, node-width, spacing) = tidy-tree-graph.with(
  compact: compact,
  text-size: text-size,
  node-width: node-width,
  node-inset: 3pt,
  spacing: spacing,
  draw-edge: tidy-tree-draws.horizontal-vertical-draw-edge,
  draw-node: (
    tidy-tree-draws.metadata-match-draw-node.with(
      matches: (
        group: (fill: theme_color_primary_hm.lighten(75%), stroke: 0.6pt + theme_color_primary_hm),
        leaf: (fill: theme_color_block, stroke: 0.5pt + theme_color_block.darken(18%)),
      ),
      default: (fill: theme_color_block, stroke: 0.5pt + theme_color_block.darken(18%)),
    ),
  ),
)

/// EVL tree: grid contract (pose + extent + optional voxel centers).
#let evl-backbone-tree-grid(
  compact: true,
  text-size: 9pt,
  node-width: 16em,
  spacing: (10pt, 16pt),
) = {
  let group = metadata("group")
  let leaf = metadata("leaf")
  let tree = _evl-tree-style(compact, text-size, node-width, spacing)
  tree[
    - Grid contract #group
      - [#symb.frame.v voxel grid anchored at #symb.ase.traj_final] #leaf
      - [t_world_voxel: PoseTW(#symb.shape.B, 12) = #T(symb.frame.w, symb.frame.v)] #leaf
      - [voxel_extent: Tensor(#symb.shape.B, 6) in meters (voxel frame)] #leaf
      - [pts_world: Tensor(#symb.shape.B, #symb.shape.Vvox, 3) (optional)] #leaf
  ]
}

/// EVL tree: evidence + internal features (voxel evidence, neck, rgb debug).
#let evl-backbone-tree-evidence(
  compact: true,
  text-size: 9pt,
  node-width: 16em,
  spacing: (10pt, 16pt),
) = {
  let group = metadata("group")
  let leaf = metadata("leaf")
  let tree = _evl-tree-style(compact, text-size, node-width, spacing)
  tree[
    - Evidence + internal features #group
      - Evidence (voxel/(...)) #group
        - [#symb.vin.occ_in : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - [#symb.vin.free_in : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) (optional)] #leaf
        - [#symb.vin.counts : Tensor(#symb.shape.B, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) int64] #leaf
        - [counts_m: Tensor(#symb.shape.B, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) (debug)] #leaf
      - Internal (optional) #group
        - [voxel_feat: Tensor(#symb.shape.B, #symb.shape.Fin, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - [occ_feat: Tensor(#symb.shape.B, #symb.shape.Fhead, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - [obb_feat: Tensor(#symb.shape.B, #symb.shape.Fhead, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
      - RGB debug (optional) #group
        - [feat2d_upsampled: Tensor(#symb.shape.B, #symb.shape.Tlen, C, Hp, Wp)] #leaf
        - [token2d: Tensor or list(Tensor)] #leaf
  ]
}

/// EVL tree: head voxel fields, split into occ vs obb (+ post-processing).
#let evl-backbone-tree-heads(
  compact: true,
  text-size: 9pt,
  node-width: 16em,
  spacing: (10pt, 16pt),
) = {
  let group = metadata("group")
  let leaf = metadata("leaf")
  let tree = _evl-tree-style(compact, text-size, node-width, spacing)
  tree[
    - Head voxel fields #group
      - Surface reconstruction (occ) #group
        - [#symb.vin.occ_pr : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
      - OBB detection (obb) #group
        - [#symb.vin.cent_pr : Tensor(#symb.shape.B, 1, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim)] #leaf
        - [bbox_pr: Tensor(#symb.shape.B, 7, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) (optional)] #leaf
        - [clas_pr: Tensor(#symb.shape.B, #symb.shape.K, #symb.shape.D, #symb.shape.H, #symb.shape.Wdim) (optional)] #leaf
      - Post-processing (obbs/(...)) #group
        - [obbs_pr_nms: ObbTW(#symb.shape.B, #symb.shape.M, 34) (optional)] #leaf
        - [obb_pred: ObbTW(#symb.shape.B, #symb.shape.M, 34) (optional)] #leaf
        - [sem_id_to_name: dict(int, str) (optional)] #leaf
  ]
}

/// Multi-panel EVL backbone output visualization (split by semantic group).
#let evl-backbone-trees(
  compact: true,
  text-size: 9pt,
  node-width: 16em,
  spacing: (10pt, 16pt),
  gutter: 0.35cm,
) = grid(
  columns: (1fr, 1fr, 1fr),
  gutter: gutter,
  evl-backbone-tree-grid(compact: compact, text-size: text-size, node-width: node-width, spacing: spacing),
  evl-backbone-tree-evidence(compact: compact, text-size: text-size, node-width: node-width, spacing: spacing),
  evl-backbone-tree-heads(compact: compact, text-size: text-size, node-width: node-width, spacing: spacing),
)

// Parse the training step from filenames shaped like:
// `confusion_matrix_<step>_<hash>.png`.
#let conf-matrix-step(file) = {
  let base = file.split("/").last()
  let stem = base.replace(".png", "")
  let parts = stem.split("_")
  int(parts.at(2))
}

// Build ordered confusion-matrix frames from a directory manifest.
// `manifest` should be a JSON array of filenames (or a dict with `files`).
#let conf-matrix-frames-from-dir(dir, manifest: "frames.json") = {
  let raw = json(dir + "/" + manifest)
  let files = if type(raw) == dictionary { raw.at("files", default: ()) } else { raw }
  files.map(file => (step: conf-matrix-step(file), file: file)).sorted(key: it => it.step)
}

// Animated slide sequence for confusion matrices (Touying subslides).
// - `dir` is the directory containing the images (no trailing slash).
#let conf-matrix-sequence(
  dir,
  manifest: "frames.json",
  title: auto,
  alignment: none,
  outlined: true,
  width: 85%,
  caption: none,
  caption-style: (size: 14pt, weight: "medium"),
  show-step: true,
  step-prefix: [Step],
  step-style: (size: 12pt, fill: gray),
  ..args,
) = {
  let frames = conf-matrix-frames-from-dir(dir, manifest: manifest)
  slide(
    title: title,
    alignment: alignment,
    outlined: outlined,
    repeat: frames.len(),
    self => [
      #let frame = frames.at(self.subslide - 1)
      #align(center + horizon)[
        #figure(
          image(dir + "/" + frame.file, width: width),
          caption: if caption == none {
            none
          } else if show-step {
            [
              #text(
                ..caption-style,
              )[
                #caption #h(0.4em) #text(..step-style)[#step-prefix #frame.step]
              ]
            ]
          } else {
            caption
          },
        )
      ]
    ],
    ..args,
  )
}
