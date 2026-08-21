# Fletcher Manual

## Table of Contents

- [Usage examples](#usage-examples)
- [Diagrams](#diagrams)
- [Elastic coordinates](#elastic-coordinates)
- [Absolute coordinates](#absolute-coordinates)
- [Coordinate expressions](#coordinate-expressions)
- [Nodes](#nodes)
- [Node shapes](#node-shapes)
- [Node groups](#node-groups)
- [Node anchors](#node-anchors)
- [Edges](#edges)
- [Specifying edge vertices](#specifying-edge-vertices)
  - [Use `auto` for the previous or next node](#use-auto-for-the-previous-or-next-node)
  - [Relative coordinate shorthands](#relative-coordinate-shorthands)
  - [Node anchors](#node-anchors-1)
- [Edge types](#edge-types)
- [Ways to adjust edge connection points](#ways-to-adjust-edge-connection-points)
- [Marks and arrows](#marks-and-arrows)
- [Custom marks](#custom-marks)
  - [Mark objects](#mark-objects)
  - [Special mark properties](#special-mark-properties)
  - [Detailed example](#detailed-example)
- [Defining mark shorthands](#defining-mark-shorthands)
- [CeTZ integration](#cetz-integration)
- [Bézier edges](#bezier-edges)
- [Touying integration](#touying-integration)
- [Main functions](#main-functions)
- [Behind the scenes](#behind-the-scenes)
- [`marks.typ`](#markstyp)
- [`shapes.typ`](#shapestyp)
- [`coords.typ`](#coordstyp)
- [`diagram.typ`](#diagramtyp)
- [`node.typ`](#nodetyp)
- [`edge.typ`](#edgetyp)
- [`draw.typ`](#drawtyp)
- [`utils.typ`](#utilstyp)


# Usage examples

Avoid importing everything with `*` as many internal functions are also exported.

```typ
  // You can specify nodes in math-mode, separated by `&`:
  #diagram($
   G edge(f, ->) edge("d", pi, ->>) & im(f) \
   G slash ker(f) edge("ur", tilde(f), "hook-->")
  $)
```

```typ
  // Or you can use code-mode, with variables, loops, etc:
  #diagram(spacing: 2cm, {
   let (A, B) = ((0,0), (1,0))
   node(A, $cal(A)$)
   node(B, $cal(B)$)
   edge(A, B, $F$, "->", bend: +35deg)
   edge(A, B, $G$, "->", bend: -35deg)
   let h = 0.2
   edge((.5,-h), (.5,+h), $alpha$, "=>")
  })
```

```typ
  #diagram(
   spacing: (10mm, 5mm), // wide columns, narrow rows
   node-stroke: 1pt,     // outline node shapes
   edge-stroke: 1pt,     // make lines thicker
   mark-scale: 60%,      // make arrowheads smaller
   edge((-2,0), "r,u,r", "-|>", $f$, label-side: left),
   edge((-2,0), "r,d,r", "..|>", $g$),
   node((0,-1), $F(s)$),
   node((0,+1), $G(s)$),
   node(enclose: ((0,-1), (0,+1)), stroke: teal, inset: 10pt,
        snap: false), // prevent edges snapping to this node
   edge((0,+1), (1,0), "..|>", corner: left),
   edge((0,-1), (1,0), "-|>", corner: right),
   node((1,0), text(white, $ plus.circle $), inset: 2pt, fill: black),
   edge("-|>"),
  )
```

```typ
  An equation $f: A -> B$ and \
  an inline diagram #diagram($A edge(->, text(#0.8em, f)) & B$).
```

```typ
  #import fletcher.shapes: diamond, brace
  #diagram(
   debug: 3,
   node-stroke: black + 0.5pt,
   node-fill: gradient.radial(white, blue, center: (40%, 20%),
                              radius: 150%),
   spacing: (10mm, 5mm),
   node((0,0), [1], name: <1>, extrude: (0, -4)), // double stroke
   edge("=>"),
   node((1,0), [2], name: <2>, shape: diamond),
   node((2,-1), [3a], name: <3a>),
   node((2,+1), [3b], name: <3b>),
   node(enclose: (<1>, <2>), shape: brace.with(dir: top, label: [12])),
   edge(<2.east>, "->", <3a>, bend: -15deg),
   edge(<2.east>, "->", <3b>, bend: +15deg),
   edge(<3b>, "~>", <3b>, bend: -130deg, loop-angle: 120deg)[loop!],
  )
```

# Diagrams

Diagrams are collections of _nodes_ and _edges_ rendered on a CeTZ canvas with `diagram()`.

## Elastic coordinates

Diagrams are laid out on a _flexible coordinate grid_, visible when #the-param[diagram][debug] is on.

When a node is placed, the rows and columns grow to accommodate the node's size, like a table.

By default, coordinates $(u, v)$ have $u$ going $arrow.r$ and $v$ going $arrow.b$.

This can be changed with #the-param[diagram][axes].

The #param[diagram][cell-size] option is the minimum row and column width, and #param[diagram][spacing] is the gutter between rows and columns.

```typ
#let c = (orange, red, green, blue).map(x => x.lighten(50%))
#diagram(
 debug: 1,
 spacing: 10pt,
 node-corner-radius: 3pt,
 node((0,0), [a], fill: c.at(0), width: 10mm, height: 10mm),
 node((1,0), [b], fill: c.at(1), width:  5mm, height:  5mm),
 node((1,1), [c], fill: c.at(2), width: 20mm, height:  5mm),
 node((0,2), [d], fill: c.at(3), width:  5mm, height: 10mm),
)
```

So far, this is just like a table --- however, elastic coordinates can be _fractional_.

Notice how the column sizes change as the green node is gradually moved between columns:

## Absolute coordinates

As well as _elastic_ or $u v$ coordinates, which are row/column numbers, you can also use _absolute_ or $x y$ coordinates, which are physical lengths.

Absolute coordinates let you position nodes _exactly_, whereas elastic coordinates are useful for table-like layouts.

Absolutely positioned nodes never affect the positions of other nodes --- the row and column sizes of a diagram depend only on the positions and sizes of nodes at elastic coordinates.

## Coordinate expressions

You can use CeTZ-style coordinate expressions such as _relative_ `(rel: (1, 2))`, _polar_ `(45deg, 1cm)`, _interpolating_ `(<P>, 80%, <Q>)`, _perpendicular_ `(<X>, "|-", <Y>)`, and so on.

```typ
#diagram(
 node((1, 0), name: <origin>), // elastic coordinate
 for θ in range(16).map(i => i/16*360deg) {
  node((rel: (θ, 10mm), to: <origin>), $ * $, inset: 1pt) // absolute offset
  edge(<origin>)
 }
)
```

# Nodes

Nodes are content centered at a particular coordinate.

Nodes automatically fit to the size of their label (with an #param[node][inset]), but can also be given an exact `width`, `height`, or `radius`, as well as a #param[node][stroke] and #param[node][fill]. For example:

```typ
#diagram(
 debug: true, // show a coordinate grid
 spacing: (5pt, 4em), // small column gaps, large row spacing
 node((0,0), $f$),
 node((1,0), $f$, stroke: 1pt),
 node((2,0), $f$, stroke: blue, shape: rect),
 node((3,0), $f$, stroke: 1pt, radius: 6mm, extrude: (0, 3)),
 {
  let b = blue.lighten(70%)
  node((0,1), `xyz`, fill: b, )
  let dash = (paint: blue, dash: "dashed")
  node((1,1), `xyz`, stroke: dash, inset: 1em)
  node((2,1), `xyz`, fill: b, stroke: blue, extrude: (0, -2))
  node((3,1), `xyz`, fill: b, height: 5em, corner-radius: 5pt)
 }
)
```

## Node shapes

By default, nodes are circular or rectangular depending on the aspect ratio of their label.

The #param[node][shape] option accepts `rect`, `circle`, various shapes provided in the #link(<shapes>, `fletcher.shapes`) submodule, or a function.

```typ
#import fletcher.shapes: pill, parallelogram, diamond, hexagon, brace
#diagram(
 node-fill: gradient.radial(white, blue, radius: 200%),
 node-stroke: blue,
 (
  node((0,0), [Blue Pill], shape: pill),
  node((1,0), [_Slant_], shape: parallelogram.with(angle: 20deg)),
  node((0,1), [Choice], shape: diamond),
  node((1,1), [Stop], shape: hexagon, extrude: (-3, 0), inset: 10pt),
 ).intersperse(edge("o--|>")).join(),
 node(enclose: ((0,0), (1,1)), shape: brace.with(label: [Group]))
)
```

The predefined shapes, many of which are configurable, are:

Shapes respect the #param[node][stroke], #param[node][fill], #param[node][width], #param[node][height], and #param[node][extrude] options of `node()`.

There are also node "shapes" for placing a `stretched-glyph()` along the edge of a nodes, especially useful with #param[node][enclose].

Custom node shapes may be implemented with CeTZ via #the-param[node][shape], but it is up to the user to support outline extrusion for custom shapes.

## Node groups

Nodes are usually centered at a particular coordinate, but they can also #param[node][enclose] multiple centers.

When #the-param[node][enclose] is given, the node automatically resizes.

```typ
#diagram(
 node-stroke: 0.6pt,
 node($Sigma$, enclose: ((1,1), (1,2)), // a node spanning multiple centers
     inset: 10pt, stroke: teal, fill: teal.lighten(90%), name: <bar>),
 node((2,1), [X]),
 node((2,2), [Y]),
 edge((1,1), "r", "->", snap-to: (<bar>, auto)),
 edge((1,2), "r", "->", snap-to: (<bar>, auto)),
)
```

You can also #param[node][enclose] other nodes by coordinate or #param[node][name] to create node groups:

```typ
#diagram(
 node-stroke: 0.6pt,
 node-fill: white,
 node((0,1), [X]),
 edge("->-", bend: 40deg),
 node((1,0), [Y], name: <y>),
 node($Sigma$, enclose: ((0,1), <y>),
      stroke: teal, fill: teal.lighten(90%),
      snap: -1, // prioritise other nodes when auto-snapping
      name: <group>),
 edge(<group>, <z>, "->"),
 node((2.5,0.5), [Z], name: <z>),
)
```

## Node anchors

You can reference anchor points on node shapes like in CeTZ, provided the node has a #param[node][name].

For example, `<A.north>` and `(name: "A", anchor: "north")` are equivalent coordinate expressions that can be referenced in other nodes or edges.

```typ
#diagram(
 node-shape: rect,
 node(circle(stroke: white, text(white, $Delta$)), name: <A>, fill: navy),
 node(<A.north-east>, circle(fill: white, radius: 6pt, $ plus.circle $)),
 edge((<A.north-west>, 25%, <A.south-west>), "l,u", "-O"),
 edge((<A.north-west>, 50%, <A.south-west>), "l,l", "-@"),
 edge((<A.north-west>, 75%, <A.south-west>), "l,d", "-O"),
)
```

Node anchors count as _absolute_ coordinates, meaning that nodes positioned with anchors are _floating_ and never affect row and column sizes.

# Edges

An edge connects two coordinates.

By default, edges _snap_ to nodes' bounding shapes (after applying the node's #param[node][outset]).

This can be adjusted with #the-param[edge][snap-to].

An edge can have a #param[edge][label], can #param[edge][bend] into an arc, and can have various arrow #param[edge][marks].

```typ
#diagram(spacing: (12mm, 6mm), {
 let (a, b, c, abc) = ((-1,0), (0,1), (1,0), (0,-1))
 node(abc, $A times B times C$)
 node(a, $A$)
 node(b, $B$)
 node(c, $C$)

 edge(a, b, bend: -18deg, "dashed")
 edge(c, b, bend: +18deg, "<-<<")
 edge(a, abc, $a$)
 edge(b, abc, "<=>")
 edge(c, abc, $c$)

 node((.6,3), [_just a thought..._])
 edge(b, "..|>", corner: right)
})
```

## Specifying edge vertices

The first few arguments given to `edge()` specify its #param[edge][vertices], of which there can be two or more.

Like node positions, vertices may be CeTZ-style coordinate expressions, combining elastic and physical coordinates, and node anchors.

Here is a more advanced example using coordinate expressions and `()`, the edge's previous vertex.

```typ
#diagram(edge-stroke: 1pt, node-stroke: 1pt, {
 node((0,0), name: <x>)[Input, $arrow(x)$]
 node((0,1), name: <y>)[Ground truth, $arrow(y)$]
 node((1,0.5), name: <out>)[MSE]
 let verts = ( // () means the previous vertex
  ((), "-|", (<y.east>, 50%, <out.west>)),
  ((), "|-", <out>), <out>)
 edge(<x>, ..verts, "->") // () == <x>
 edge(<y>, ..verts)  // () == <y>
})
```

### Use `auto` for the previous or next node

If an edge's first or last vertex is `auto`, the previous or next node is used, according to the order that nodes and edges are passed to `diagram()`.

A single vertex, such as `edge(to)`, is interpreted as `edge(auto, to)`.

Given no vertices, an edge connects the nearest nodes on either side.

```typ
#diagram(
 node((0,0), [London]),
 edge("..|>", bend: 20deg),
 edge("<|--", bend: -20deg),
 node((1,1), [Paris]),
)
```

Implicit coordinates can be handy for diagrams in math-mode:

```typ
#diagram($ L edge("->", bend: #30deg) & P $)
```

```typ
// #diagram(node-fill: blue, {
//  let (dep, arv) = ((0,0), (1,1))
//  node(dep, text(white)[London])
//  node(arv, text(white)[Paris])
//  edge(dep, arv, "==>", bend: 40deg)
// })
//
```

### Relative coordinate shorthands

You may use strings such as `"u"` for up or `"sw"` for south west as shorthands for relative vertex coordinates of the form `(rel: (du, dv))`. Any combination of

are allowed. Together with implicit coordinates, this allows you to do things like:

```typ
#diagram($ A edge("rr", ->, #[jump!], bend: #30deg) & B & C $)
```

### Node anchors

Nodes can be given a #param[node][name], which is a label (not a string) identifying that node.

A label as an edge vertex is interpreted as the position of the node with that label.

```typ
#diagram(
 node((0,0), $frak(A)$, name: <A>),
 node((1,0.5), $frak(B)$, name: <B>),
 edge(<A>, <B>, "-->")
)
```

## Edge types

There are three types of edges: `"line"`, `"arc"`, and `"poly"`.

All edges have at least two `vertices`, but `"poly"` edges can have more.

If unspecified, #param[edge][kind] is chosen based on #param[edge][bend] and the number of #param[edge][vertices].

```typ
#diagram(
 edge((0,0), (1,1), "->", `line`),
 edge((2,0), (3,1), "->", bend: -30deg, `arc`),
 edge((4,0), (4,1), (5,1), (6,0), "->", `poly`),
)
```

All vertices except the first can be relative coordinate shorthands (see above), so that in the example above, the `"poly"` edge could also be written in these equivalent ways:

```typ
c
edge((4,0), (rel: (0,1)), (rel: (1,0)), (rel: (1,-1)), "->", `poly`)
edge((4,0), "d", "r", "ur", "->", `poly`) // using relative coordinate names
edge((4,0), "d,r,ur", "->", `poly`) // shorthand
```

Only the first and last #param[edge][vertices] of an edge automatically snap to nodes.

## Ways to adjust edge connection points

A node's #param[node][outset] controls how _close_ edges connect to the node's boundary.

To adjust _where_ along the boundary the edge connects, you can adjust the edge's end coordinates by a fractional amount.

```typ
#diagram(
 node-stroke: (thickness: .5pt, dash: "dashed"),
 node((0,0), [no outset], outset: 0pt),
 node((0,1), [big outset], outset: 10pt),
 edge((0,0), (0,1)),
 edge((-0.1,0), (-0.4,1), "-o", "wave"), // shifted with fractional coordinates
 edge((0,0), (0,1), "=>", shift: 15pt),  // shifted by a length
)
```

Alternatively, #the-param[edge][shift] lets you shift edges sideways by an absolute length:

```typ
#diagram($A edge(->, shift: #3pt) edge(<-, shift: #(-3pt)) & B$)
```

By default, edges which are incident at an angle are automatically adjusted slightly, especially if the node is wide or tall.

Aesthetically, things can look more comfortable if edges don't all connect to the node's exact center, but instead spread out a bit.

Notice the (subtle) difference the figures below.

The strength of this adjustment is controlled by #the-param[node][defocus] or #the-param[diagram][node-defocus].

# Marks and arrows

Arrow marks can be specified like  `edge(a, b, "-->")` or with #the-param[edge][marks].

Some mathematical arrow heads are supported, which match $arrow$, $arrow.double$, $arrow.triple$, $arrow.bar$, $arrow.twohead$, and $arrow.hook$ in the default font.

A few other marks are provided, and all marks can be placed anywhere along the edge.

All the built-in marks (see @all-marks) are defined in the state variable `fletcher.MARKS`, which you may access with `context fletcher.MARKS.get()`.

You add or tweak mark styles by modifying `fletcher.MARKS`, as described in @mark-objects.

) <all-marks>]

Marks can be flipped by appending `'` to the name.

```typ
#diagram(edge("harpoon'-hook", stroke: 1pt))
#diagram(edge("hook'-harpoon", stroke: 1pt))
```

If there is a common mark style that you believe should be included with `fletcher` by default, please #link("<https://github.com/Jollywatt/typst-fletcher")[open> an issue]!

## Custom marks

While shorthands like `"|=>"` exist for specifying marks and stroke styles, finer control is possible.

Marks can be specified by passing an array of _mark objects_ to #the-param[edge][marks].

For example:

```typ
#diagram(
 edge-stroke: 1.5pt,
 spacing: 28mm,
 edge((0,1), (-0.1,0), bend: -8deg, marks: (
  (inherit: ">>", size: 6, delta: 70deg, sharpness: 65deg),
  (inherit: "head", rev: true, pos: 0.8, sharpness: 0deg, size: 17),
  (inherit: "bar", size: 1, pos: 0.3),
  (inherit: "solid", size: 12, rev: true, stealth: 0.1, fill: red.mix(purple)),
 ), stroke: green.darken(50%)),
)
```

In fact, shorthands like `"|=>"` are expanded with `interpret-marks-arg()` into a form more like the example above.

More precisely, `edge(from, to, "|=>")` is equivalent to:

```typ
c
context edge(from, to, ..fletcher.interpret-marks-arg("|=>"))
```

If you want to explore the internals of mark objects, you might find it handy to inspect the output of `context fletcher.interpret-marks-arg(..)` with various mark shorthands as input.

### Mark objects

A _mark object_ is a dictionary with, at the very least, a `draw` entry containing the CeTZ objects to be drawn.

These CeTZ objects are translated and scaled to fit the edge; the mark should be centered at `(0, 0)`, and the stroke's thickness is defined as the unit length.

For example, here is a basic circle mark:

```typ
#import cetz.draw
#let my-mark = (
 draw: draw.circle((0,0), radius: 2, fill: none)
)
#diagram(
 edge((0,0), (1,0), stroke: 1pt, marks: (my-mark, my-mark), bend: 30deg),
 edge((0,1), (1,1), stroke: 3pt + orange, marks: (none, my-mark)),
)
```

A mark object can contain arbitrary parameters.

Parameters can be functions `mark => (..)` referencing other `mark` parameters defined earlier.

For example, the mark above could also be written as:

```typ
#let my-mark = (
 size: 2,
 draw: mark => draw.circle((0,0), radius: mark.size, fill: none)
)
```

This form makes it easier to change the size without modifying the `draw` function, for example:

```typ
#import cetz.draw
#let my-mark = (
 size: 2,
 draw: mark => draw.circle((0,0), radius: mark.size, fill: none)
) // setup
#diagram(edge(stroke: 3pt, marks: (my-mark + (size: 4), my-mark)))
```

Lastly, mark objects may _inherit_ properties from other marks in `fletcher.MARKS` by containing an `inherit` entry, for example:

```typ
#let my-mark = (
 inherit: "stealth", // base mark on `fletcher.MARKS.stealth`
 fill: red,
 stroke: none,
 extrude: (0, -3),
)
#diagram(edge("rr", stroke: 2pt, marks: (my-mark, my-mark + (fill: blue))))
```

Internally, marks are passed to `resolve-mark()`, which resolves all entries to their final values.

### Special mark properties

A mark object may contain any properties, but some have special functions.

The last few properties control the fine behaviours of how marks connect to the target point and to the edge's stroke.

Briefly, a mark has four possibly-distinct center points.

It is easier to show than to tell:

See `mark-debug()` and `cap-offset()` for details.

### Detailed example

As a complete example, here is the implementation of a straight arrowhead in ```plain src/default-marks.typ```:

```typ
#import cetz.draw
#let straight = (
 size: 8,
 sharpness: 20deg,
 tip-origin: mark => 0.5/calc.sin(mark.sharpness),
 tail-origin: mark => -mark.size*calc.cos(mark.sharpness),
 fill: none,
 draw: mark => {
  draw.line(
   (180deg + mark.sharpness, mark.size), // polar cetz coordinate
   (0, 0),
   (180deg - mark.sharpness, mark.size),
  )
 },
 cap-offset: (mark, y) => calc.tan(mark.sharpness + 90deg)*calc.abs(y),
)

#set align(center)
#fletcher.mark-debug(straight)
#fletcher.mark-demo(straight)
```

## Defining mark shorthands

While you can pass custom mark objects directly to #the-param[edge][marks], this can get annoying if you use the same mark often.

In these cases, you can define your own mark shorthands.

Mark shorthands such as `"hook->"` search the state variable `fletcher.MARKS` for defined mark names.

```typ
#context fletcher.MARKS.get().at(">")
```

With a bit of care, you can modify the `MARKS` state like so:

```typ
Original marks:
#diagram(spacing: 2cm, edge("<->", stroke: 1pt))

#fletcher.MARKS.update(m => m + (
 "<": (inherit: "stealth", rev: true),
 ">": (inherit: "stealth", rev: false),
 "multi": (
  inherit: "straight",
  draw: mark => fletcher.cetz.draw.line(
   (0, +mark.size*calc.sin(mark.sharpness)),
   (-mark.size*calc.cos(mark.sharpness), 0),
   (0, -mark.size*calc.sin(mark.sharpness)),
  ),
 ),
))

Updated marks:
#diagram(spacing: 2cm, edge("multi->-multi", stroke: 1pt + eastern))
```

Here, we redefined which mark style the `"<"` and `">"` shorthands refer to, and added an entirely new mark style with the shorthand `"multi"`.

Finally, I will restore the default state so as not to affect the rest of this manual:

```typ
#fletcher.MARKS.update(fletcher.DEFAULT_MARKS) // restore to built-in mark styles
```

# CeTZ integration

Fletcher's drawing capabilities are deliberately restricted to a few simple building blocks.

However, an escape hatch is provided with #the-param[diagram][render] so you can intercept diagram data and draw things using CeTZ directly.

## Bézier edges

Here is an example of how you might hack together a Bézier edge using the same functions that `fletcher` uses internally to anchor edges to nodes:

```typ
#diagram(
 node((0,1), $A$, stroke: 1pt),
 node((2,0), [Bézier], stroke: 1pt, shape: fletcher.shapes.diamond),
 render: (grid, nodes, edges, options) => {
  fletcher.cetz.canvas({
   fletcher.draw-diagram(grid, nodes, edges, debug: options.debug)

   let n1 = fletcher.find-node-at(nodes, (0,1))
   let n2 = fletcher.find-node-at(nodes, (2,0))

   let θ1 = 0deg
   let θ2 = -90deg

   let p1 = fletcher.get-node-anchor(n1, θ1)
   let p2 = fletcher.get-node-anchor(n2, θ2)

   let c1 = (rel: (θ1, 30pt), to: p1)
   let c2 = (rel: (θ2, 70pt), to: p2)

   fletcher.cetz.draw.bezier(p1, p2, c1, c2)
   fletcher.draw-mark("head", origin: p1, angle: 180deg, stroke: 1pt)
  })
 }
)
```

# Touying integration

You can create incrementally-revealed diagrams with Touying presentation slides by defining a `touying-reducer`.

You must redefine `diagram` to use this reducer so that Touying primitives like `pause`, `uncover`, `only`, and so on are understood.

For example, here is a simple animated diagram:

```typ
#import "@preview/touying:0.5.5": *
#show: themes.simple.simple-theme.with(aspect-ratio: "16-9")
#let diagram = touying-reducer.with(
 reduce: fletcher.diagram, cover: fletcher.hide)

#slide(repeat: 6, self => {
 let (uncover, only, alternatives) = utils.methods(self)
 diagram(
  node((0, 0), name: <A>)[$A$],
  pause,
  edge("->"),
  node((1, 0), name: <B>)[$B$],
  pause,
  edge("->"),
  node((2, 0), name: <C>)[$C$],
  only("4,6", edge(<A>, "~", <B>, bend: 40deg, stroke: red)),
  only("5,6", edge(<B>, "~", <C>, bend: 40deg, stroke: green)),
  only("6", edge(<C>, "~", <A>, bend: 40deg, stroke: blue)),
 )
})
```

# Main functions

# Behind the scenes

## `marks.typ`

The default marks are defined in the `fletcher.MARKS` dictionary with keys:

## `shapes.typ`

To use built-in shapes in a diagram, import them with:

```typ
#import fletcher: shapes
#diagram(node([Hello], stroke: 1pt, shape: shapes.hexagon))
```

or:

```typ
#import fletcher.shapes: hexagon
#diagram(node([Hello], stroke: 1pt, shape: hexagon))
```

To set a shape parameter, use `shape.with(..)`, for example `hexagon.with(angle: 45deg)`.

Shapes respect the #param[node][stroke], #param[node][fill], #param[node][width], #param[node][height], and #param[node][extrude] options of `edge()`.

## `coords.typ`

## `diagram.typ`

## `node.typ`

## `edge.typ`

## `draw.typ`

## `utils.typ`
