# Fletcher (diagram package)

Use Fletcher for flow charts and architecture diagrams with arrows. The
package index routes directly to the cleaned manual when its details are
needed.

## Import pattern

```typ
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
```

## Templates

- `references/packages/fletcher-01-ml-architecture.typ`: Attention-style block (multi-head attention + add + FFN) - this is *by far* the prettiest diagram.
- `references/packages/fletcher-02-residual-block.typ`: Residual block with skip connection.
- `references/packages/fletcher-03-unet.typ`: U-Net style encoder/decoder with skip connections.

## Editing tips

- Prefer explicit node names and connect with `edge(<from>, <to>, "-|>")` for clarity.
- Avoid Unicode arrows in labels; use plain text or `#sym.*` if a glyph is required.
- Keep a `block(...)` helper per template to centralize color + sizing.
- Use `spacing` and `cell-size` to compact or expand layouts.

## Manual sections worth scanning

- Diagrams and elastic coordinates (layout + spacing options).
- Nodes (shapes, enclose, anchors).
- Edges (marks, bends, dash styles, snap-to).
