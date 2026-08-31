// Shared table vocabulary for authored thesis, paper, and presentation tables.
//
// Keep data selection, captions, and labels at the call site. These helpers
// own only the visual grammar: booktabs rules, compact spacing, and restrained
// index/group cells.
#import "@preview/booktabs:0.0.4": bottomrule, midrule, toprule

#let _header-fill = rgb("e9eef2")
#let _development-header-fill = rgb("f1ede5")
#let _index-fill = rgb("f5f7f8")
#let _rule-color = rgb("53616b")

#let _table(
  columns,
  header,
  rows,
  header-fill,
  header-rows: 1,
  align: auto,
  text-size: 8.5pt,
  inset: (x: 5pt, y: 4pt),
  column-gutter: auto,
  row-gutter: auto,
) = {
  set par(justify: false)
  assert(header.len() > 0, message: "shared table requires a semantic header")
  // Author rows as nested tuples so the source grid mirrors the rendered grid.
  // Flat legacy rows remain accepted while existing tables migrate.
  let flat-rows = rows.fold((), (cells, row) => {
    if type(row) == array { cells + row } else { cells + (row,) }
  })
  let styled = table(
    columns: columns,
    align: align,
    stroke: none,
    fill: (x, y) => if y < header-rows { header-fill } else { none },
    inset: inset,
    column-gutter: column-gutter,
    row-gutter: row-gutter,
    toprule(stroke: 0.09em + _rule-color),
    table.header(..header),
    midrule(stroke: 0.045em + _rule-color),
    ..flat-rows,
    bottomrule(stroke: 0.09em + _rule-color),
  )
  text(size: text-size, styled)
}

/// A compact publication table with a semantic, repeated header.
#let publication-table(
  columns: auto,
  header: (),
  rows: (),
  header-rows: 1,
  align: auto,
  text-size: 8.5pt,
  column-gutter: auto,
  row-gutter: auto,
) = {
  _table(
    columns,
    header,
    rows,
    _header-fill,
    header-rows: header-rows,
    align: align,
    text-size: text-size,
    column-gutter: column-gutter,
    row-gutter: row-gutter,
  )
}

/// A visually distinct table for development-only reports.
#let development-table(
  columns: auto,
  header: (),
  rows: (),
  header-rows: 1,
  align: auto,
  text-size: 8.5pt,
) = {
  _table(
    columns,
    header,
    rows,
    _development-header-fill,
    header-rows: header-rows,
    align: align,
    text-size: text-size,
  )
}

/// A slide-sized table using the same scientific-table visual grammar.
#let presentation-table(
  columns: auto,
  header: (),
  rows: (),
  header-rows: 1,
  align: auto,
  text-size: 13pt,
) = {
  _table(
    columns,
    header,
    rows,
    _header-fill,
    header-rows: header-rows,
    align: align,
    text-size: text-size,
    inset: (x: 4pt, y: 3pt),
  )
}

/// A spanning section label inside a table body.
#let group-header(body, rowspan: 1, colspan: 1, fill: _index-fill) = table.cell(
  rowspan: rowspan,
  colspan: colspan,
  fill: fill,
  inset: (x: 5pt, y: 3pt),
)[#strong(body)]

/// A consistently shaded row/column index cell.
#let index-cell(body, rowspan: 1, colspan: 1, fill: _index-fill) = table.cell(
  rowspan: rowspan,
  colspan: colspan,
  fill: fill,
  inset: (x: 5pt, y: 4pt),
)[#strong(body)]
