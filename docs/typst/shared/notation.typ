// Thesis-facing notation lists backed by generated notation metadata.

#import "notation.generated.typ": notation-symbols-list

#let thesis-symbol-entries() = notation-symbols-list.filter(entry => entry.thesis_list)
#let thesis-symbol-domain(key) = key.split(".").first()
#let thesis-symbol-domain-title(domain) = (
  oracle: "Oracle and Reconstruction",
  rri: "RRI Metrics",
  ase: "ASE Assets",
  obs: "Observation and Actor State",
  vin: "VIN Scorer",
  entity: "Entity and Target",
  rl: "Planning and Rollout",
  shape: "Shape and Size",
).at(domain, default: domain)

#let thesis-symbol-table-cells(entries) = {
  let cells = ()
  let current-domain = none
  for entry in entries {
    let domain = thesis-symbol-domain(entry.key)
    if domain != current-domain {
      current-domain = domain
      cells.push(table.cell(colspan: 3, fill: rgb("#f0f0f0"))[
        #text(weight: 700, thesis-symbol-domain-title(domain))
      ])
    }
    cells.push([#entry.body])
    cells.push([#entry.description])
    cells.push(text(size: 7.6pt, raw(entry.key)))
  }
  cells
}

#let print-thesis-symbols() = {
  let entries = thesis-symbol-entries()
  if entries.len() == 0 {
    [No thesis symbols have been marked for the printed notation list.]
  } else {
    text(size: 9pt)[
      #table(
        columns: (1.15fr, 4.6fr, 2fr),
        column-gutter: 8pt,
        row-gutter: 5pt,
        inset: (x: 0pt, y: 3pt),
        align: (center + horizon, left, left + horizon),
        table.header([*Symbol*], [*Meaning*], [*Key*]),
        ..thesis-symbol-table-cells(entries),
      )
    ]
  }
}
