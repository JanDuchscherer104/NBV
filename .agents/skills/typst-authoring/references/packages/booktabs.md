# booktabs (Typst package)

Table styling inspired by LaTeX Booktabs, distributed via Typst Universe.
This is the default table style for ARIA-NBV thesis/proposal Typst sources.

## Package metadata

- **Package:** `booktabs`
- **Version:** `0.0.4`
- **Min Typst:** `0.13.1`
- **Author:** Budo Zindovic
- **License:** LGPL-3.0-or-later
- **Last updated:** 2025-08-12

## Quick use

```
#import "@preview/booktabs:0.0.4": *
#show: booktabs-default-table-style
```

Add rules with:

- `toprule()`
- `midrule()`
- `cmidrule(start: <col>, end: <col>)`
- `bottomrule()`

## Notes

- The default style is enabled with `#show: booktabs-default-table-style`.
- Publication-facing thesis/proposal tables should include `toprule()`,
  `midrule()` after `table.header`, and `bottomrule()`.
- Use `#sym.degree` and other `#sym.*` symbols in headers instead of Unicode glyphs.

## Examples

- `references/packages/booktabs-01-basic.typ`
- `references/packages/booktabs-02-grouped.typ`

## Links

- Package page: `https://typst.app/universe/package/booktabs`
- Manual: `https://bzindovic.github.io/booktabs/`
