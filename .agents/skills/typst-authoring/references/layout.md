# Layout Handling (Typst)

Use this when arranging content, controlling flow, or building complex layouts.
Refer to Context7 queries in this file before editing.

## Context7 queries (Layout docs)
- `layout align block box columns grid stack place pad page pagebreak measure`
- `layout h v move rotate scale skew`
- `layout relative fraction ratio length`

## Core layout building blocks (by name)
- **align**: Align content horizontally/vertically inside a container.
- **block**: Block-level container (starts a new block).
- **box**: Inline container that sizes content.
- **columns**: Split a region/page into multiple columns.
- **grid**: Arrange content in a grid (row/column).
- **stack**: Arrange content horizontally or vertically with spacing.
- **h / v**: Insert horizontal/vertical space in flow.
- **pad**: Add spacing around content.
- **place**: Place content relative to a parent container.
- **page / pagebreak / colbreak**: Control pagination and column breaks.
- **layout**: Access container/page size (width/height) inside a callback.
- **measure**: Measure layouted size of content (use with `layout`).

## Geometry & transforms
- **move**: Move content without affecting layout.
- **rotate / scale / skew**: Transform content without affecting layout.
- **angle / direction**: Angles and directions for transforms/layout.

## Size & distribution
- **length / relative**: Specify sizes (absolute or relative).
- **fraction / ratio**: Allocate remaining space in layouts.

## Practical patterns
- **Two-column page**: `#set page(columns: 2, ...)`
- **Figure grids**: `#grid(columns: (1fr, 1fr), gutter: 12pt, ...)`
- **Measured layout**: `#layout(size => [ ... #measure(width: size.width, ...) ... ])`

## Rendered Column Contract

The thesis body has 30 mm left/right margins. `make thesis-pdf` verifies the
compiled PDF with `scripts/check_typst_pdf_column_bounds.py`; do not treat a
successful Typst compile as proof that a display fits. When the checker reports
`typst-column-overflow`, prefer one of these semantic repairs:

- split a compound display into independently readable shared equations;
- move definitions into a short preceding display and retain only the needed
  relation at the point of use;
- use a vertical `cases` or `mat` layout for conditional clauses;
- give a table an explicit column allocation and shorten/restructure cells.

Scaling, negative horizontal spacing, `move`, or clipping can hide a warning
while making the printed document harder to read, so they are not repairs.
The default Make target reports the current manuscript baseline in warning-only
mode; `THESIS_COLUMN_CHECK_ARGS=` promotes it to a strict rendered-layout gate.
