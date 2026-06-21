# Typst Data Structures (Array + Dictionary)

## Array
Arrays are ordered sequences indexed by integers.

Common methods (see Context7 `foundations/array`):
- `map`, `filter`, `slice`, `join`, `reduce`
- `to-dict` (convert array of key-value pairs into a dictionary)

Example: transform rows
```typst
#let rows = (("run", 0.95), ("loss", 0.12))
#let pretty = rows.map(r => (r.at(0), str(r.at(1))))
```

Example: array of pairs to dict
```typst
#(
  ("apples", 2),
  ("peaches", 3),
  ("apples", 5),
).to-dict()  // {"apples": 5, "peaches": 3}
```

## Dictionary
Dictionaries map string keys to values.

Construction:
```typst
#let d = (title: "Report", version: 1)
```

Access:
- Static key: `d.title`
- Dynamic key: `d.at("title")`
- Membership: `"title" in d`

Notes:
- Dictionaries preserve insertion order in iteration.
- Adding dictionaries with `+` merges keys (later wins).

## Table pattern (array to flat cells)
```typst
#import "@preview/booktabs:0.0.4": *

#let rows = (
  (run: "alexnet", acc: 0.99),
  (run: "resnet", acc: 0.96),
)

#table(
  columns: 2,
  toprule(),
  table.header[*Run*][*Acc*],
  midrule(),
  ..rows.map(r => (r.run, r.acc)).flatten(),
  bottomrule(),
)
```
