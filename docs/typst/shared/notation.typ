// Thesis-facing notation lists backed by generated notation metadata.

#import "notation.generated.typ": notation-symbols-list

#let thesis-symbol-entries() = notation-symbols-list.filter(entry => entry.thesis_list)

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
        ..entries
          .map(entry => (
            [#entry.body],
            [#entry.description],
            text(size: 7.6pt, raw(entry.key)),
          ))
          .flatten(),
      )
    ]
  }
}
