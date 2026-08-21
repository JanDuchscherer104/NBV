# Typst Scripting (Reference)

Use Typst scripting for data shaping, reusable components, and conditional rendering.
Keep scripts small and declarative; push heavy computation outside Typst.

## Code vs Markup

- In markup, prefix expressions with `#`.
- In code blocks, `#` is not required and multiple expressions can appear.

```
#let x = 2
Value: #x

#let y = { 1 + 2 }
```

## Bindings and Functions

- Bind values and functions with `let`.
- Functions can return numbers, strings, or content blocks.

```
#let name = "Typst"
#let add(x, y) = x + y
#let badge(label) = [*#label*]
```

## Blocks

- **Code block:** `{ ... }` for multiple expressions.
- **Content block:** `[ ... ]` for programmatic markup.

```
#let emphasize(text) = [*#text*]
#let sum = { let a = 1; let b = 2; a + b }
```

Content blocks can be passed as trailing arguments:

```
list([A], [B]) == list[A][B]
```

## Control Flow

- `if ... { ... } else { ... }` for conditional output.
- `for` and `while` loops return joined values.
- `break`, `continue`, `return` are available in code mode.

```
#if score >= 0.9 [Excellent] else [Ok]

#for item in items [
  - #item
]

#let n = 2
#while n < 10 { n = (n * 2) - 1; (n,) }
```

## Destructuring

- Destructure arrays and dictionaries in `let` bindings.
- Use `..` to capture the remainder.
- Use `_` to ignore elements.

```
#let (first, second, ..rest) = (1, 2, 3, 4)
#let (name: n, ..rest) = (name: "A", age: 2)
```

## Types and Methods

- `type(x) == int` for type checks.
- Methods are sugar for scoped functions: `str.len(s)` == `s.len()`.

```
#if type(x) == int { ... }
#let size = "hello".len()
```

## Modules: include vs import

- `include` inserts another file directly.
- `import` gives names from a module (with aliasing).

```
#include "shared.typ"
#import "shared.typ": card, grid
#import "shared.typ" as shared
```

## Styling Hooks

- `set` applies defaults (e.g., text, figure, page).
- `show` rules transform matching content.

```
#set text(size: 10pt)
#show heading: it => [*#it*]
```

## Context and Measurement

- Use `context` to access container or page-specific information.
- Use `layout` and `measure` when sizing content programmatically.

See `references/layout.md` for layout-specific patterns.

## Data and Symbols

- For data-driven content, use `csv()` / `json()` / `toml()` and map/flatten.
- For symbols, avoid Unicode and use `#sym.*` or math shorthands.

See `references/data-loading.md` and `references/typst-symbols.md`.

## Context7 Queries (Scripting)

Use official Typst documentation; for current library selection, use the
[`aria-nbv-context` Context7 registry](../../aria-nbv-context/references/context7_library_ids.md):

- `scripting let bindings destructuring blocks content`
- `if for while break continue return`
- `include import module`
- `set show context`
