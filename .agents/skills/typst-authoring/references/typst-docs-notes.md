# Typst Docs Notes (Context7 distilled)

Use these notes to align patterns with official docs. Each item includes a Context7 query and the relevant doc section.

## Figures & captions
- **Query:** `figure caption label`
- **Docs:** *Reference → model/figure*; *Tutorial → Writing in Typst*
- **Pattern:** `#figure(image(...), caption: [...]) <label>` then reference with `@label`.

## Tables + headers
- **Query:** `table table.header align stroke inset`
- **Docs:** *Reference → model/table*; *Guides → Tables*
- **Pattern:** import `@preview/booktabs:0.0.4`, enable `#show: booktabs-default-table-style`, then use `#table(..., toprule(), table.header[...], midrule(), ..., bottomrule())` and wrap in `#figure(..., caption: [...]) <label>` for caption+reference.
- **Note:** Use `table.header` for accessibility and booktabs rules for thesis/proposal tables.

## Layout grids
- **Query:** `grid stack wrap-content`
- **Docs:** *Reference → layout/grid*
- **Pattern:** use `#grid(...)` for multi-panel figures; keep consistent gutters.

## Layout fundamentals
- **Query:** `layout align block box columns grid stack place pad page pagebreak measure`
- **Docs:** *Reference → layout/*
- **Pattern:** use `align`, `block`, `box`, `pad`, `place` for positioning; use `layout` + `measure` for size-aware logic.

## Symbols & math shorthands
- **Query:** `math symbols sym`
- **Docs:** *Reference → math*; *Reference → foundations/symbol*
- **Pattern:** `$...$` for math mode; `#sym.arrow.r`, `#sym.tilde`, or shorthands like `=>`.
- **Rule:** avoid raw Unicode glyphs; prefer `#sym.*` or math shorthands.

## Data loading
- **Query:** `csv data-loading row-type dictionary`
- **Docs:** *Reference → data-loading/csv*
- **Pattern:** `#let data = csv("file.csv", row-type: dictionary)` and map/flatten for tables.
- **Query:** `json data-loading`
- **Docs:** *Reference → data-loading/json*
- **Pattern:** `#let data = json("file.json")`, access via `data.key`.
- **Query:** `toml data-loading`
- **Docs:** *Reference → data-loading/toml*
- **Pattern:** `#let data = toml("file.toml")`, access via `data.key`.

## Scripting fundamentals
- **Query:** `scripting let blocks content destructuring`
- **Docs:** *Reference → scripting*
- **Pattern:** `#let f(x) = x + 1` and `#let (a, ..rest) = (1, 2, 3)`.
- **Note:** Use code blocks `{ ... }` for multi-step logic, content blocks `[ ... ]` for markup-as-values.

## Control flow + modules
- **Query:** `if for while break continue return`
- **Docs:** *Reference → scripting*
- **Pattern:** `#for item in items [ ... ]` or `#if cond [..] else [..]`.
- **Query:** `include import module`
- **Docs:** *Reference → scripting*
- **Pattern:** `#import "mod.typ": a, b` or `#include "shared.typ"`.

## Simple scripting helpers
- **Query:** `calc round map slice filter`
- **Docs:** *Reference → foundations/calc*
- **Pattern:** `calc.round(value, digits: 2)` for table-ready numbers.

## Export to PNG
- **Query:** `export png ppi pages`
- **Docs:** *Reference → export* (PNG section)
- **Pattern:** `typst compile input.typ output.png --format png --ppi 300 --pages 1`
- **Note:** For multi-page export, use a template like `'out/{0p}.png'`; set `#set page(fill: none)` for transparency.
