// Custom template that extends definitely-not-isec-slides
// with our custom styling and modifications

#import "@preview/definitely-not-isec-slides:1.0.1": *

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
      block(),
      heading(level: 1, outlined: outlined, hdr),
      move(dy: -0.31cm, self.store.logo),
      block(),
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
        #set text(fill: white, size: 12pt)
        #utils.slide-counter.display()
      ],
      block(),
      block[
        #set align(left + horizon)
        #set text(size: 13pt)
        #info.at("footer", default: "")
      ],
      block(),
    )

    if self.store.progress-bar {
      place(bottom + left, float: true,
        move(dy: 1.05cm,
          components.progress-bar(
            height: 3pt,
            self.colors.primary,
            white,
          )
        )
      )
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
    }
  )

  touying-slide(self: self, ..args)
})

// Override color-block to have rounded corners
#let color-block(
  title: [],
  icon: none,
  spacing: 0.78em,
  color: none,
  color-body: none,
  body
) = [
  #import "@preview/tableau-icons:0.331.0": *
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
        radius: 8pt,  // Rounded corners!
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
