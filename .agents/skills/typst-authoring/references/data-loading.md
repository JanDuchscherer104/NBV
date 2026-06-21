# Data Loading (Typst)

Use this when a document needs external data (tables, metrics, metadata).
Prefer stable, small files and keep parsing minimal.

## Context7 queries
- **Index:** `data-loading csv toml read json cbor yaml xml`
- **CSV:** `csv data-loading row-type dictionary`
- **TOML:** `toml data-loading`
- **JSON:** `json data-loading`

## Formats & functions (from Typst data-loading)
- `csv` — reads CSV into a 2D array (or dictionaries with `row-type: dictionary`).
- `toml` — reads TOML into a dictionary (root table required).
- `json` — reads JSON into a dictionary/array.
- `read` — reads plain text or bytes.
- `yaml`, `xml`, `cbor` — other structured data formats.

## CSV (table-ready)
```typst
#import "@preview/booktabs:0.0.4": *

#let rows = csv("results.csv", row-type: dictionary)

#table(
  columns: 3,
  toprule(),
  table.header[*Run*][*Acc*][*Loss*],
  midrule(),
  ..rows.map(r => (r.run, r.acc, r.loss)).flatten(),
  bottomrule(),
)
```
Notes:
- Header row is not stripped; `row-type: dictionary` maps keys to strings.
- Use `map`/`flatten` to build table cells.
- For full documents, import `booktabs` once near the root and enable
  `#show: booktabs-default-table-style`.

## TOML (metadata/config)
```typst
#let details = toml("details.toml")

Title: #details.title \
Version: #details.version \
Authors: #(details.authors.join(", ", last: " and "))
```
Notes:
- TOML root must be a table.
- Values become Typst strings, numbers, arrays, or dictionaries.

## JSON (structured data)
```typst
#let data = json("metrics.json")
Accuracy: #data.val_accuracy
```

## Encoding caveat
Data formats have native types. Conversions can be lossy for non-primitive Typst values; `repr` is for debugging only.
