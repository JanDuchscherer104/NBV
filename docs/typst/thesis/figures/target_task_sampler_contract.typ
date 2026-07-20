#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.5pt)

#let ink = rgb("#17202a")
#let muted = rgb("#5f6b78")
#let rule = rgb("#c9d2dc")
#let blue = rgb("#3269a8")
#let green = rgb("#23856d")
#let orange = rgb("#b56a19")
#let red = rgb("#b23a48")
#let pale = rgb("#f5f7f9")

#cetz.canvas(length: 8mm, padding: .24, {
  import cetz.draw: *

  let arrow = (end: ">", scale: .72)
  let small(body, fill: ink) = text(size: 7.15pt, fill: fill, body)
  let tiny(body, fill: muted) = text(size: 6.55pt, fill: fill, body)

  let heading(x, number, title, subtitle, color) = {
    circle((x, 5.32), radius: .25, fill: color, stroke: none)
    content((x, 5.32), text(size: 7.1pt, fill: white, weight: "bold", number))
    content((x + .42, 5.47), text(size: 8.0pt, weight: "bold", title), anchor: "west")
    content((x + .42, 5.08), tiny(subtitle), anchor: "west")
  }

  let status-mark(x, y, ok: true) = {
    if ok {
      circle((x, y), radius: .13, fill: green, stroke: none)
      line((x - .06, y), (x - .01, y - .055), (x + .075, y + .065),
        stroke: .7pt + white)
    } else {
      circle((x, y), radius: .13, fill: white, stroke: .7pt + red)
      line((x - .055, y - .055), (x + .055, y + .055), stroke: .7pt + red)
      line((x - .055, y + .055), (x + .055, y - .055), stroke: .7pt + red)
    }
  }

  let row(y, id, geometry, ok: true) = {
    rect((.72, y - .24), (5.22, y + .24),
      radius: .045,
      fill: if ok { white } else { pale },
      stroke: .5pt + rule)
    status-mark(1.02, y, ok: ok)
    content((1.30, y), small(id, fill: if ok { ink } else { muted }), anchor: "west")
    content((2.38, y), tiny(geometry), anchor: "west")
  }

  let task-chip(x, y, id, selected: true) = {
    rect((x, y), (x + 1.18, y + .55),
      radius: .08,
      fill: if selected { green.lighten(86%) } else { pale },
      stroke: if selected { .7pt + green } else { (paint: muted, thickness: .55pt, dash: "dashed") })
    content((x + .59, y + .30), small(id, fill: if selected { ink } else { muted }))
    content((x + .59, y + .10), tiny(if selected { [kept] } else { [not drawn] }))
  }

  rect((0, 0), (18.8, 6.15), radius: .1, fill: white, stroke: .5pt + rule)
  content((.45, 5.82), text(size: 9.1pt, weight: "bold", [Implemented oracle target-task sampling]), anchor: "west")
  content((18.35, 5.82), tiny([admission is independent of headroom and expected gain]), anchor: "east")

  // 1: actual source rows and geometry-only admission.
  heading(.72, [1], [Enumerate GT OBB rows], [stored rows from one snippet], blue)
  content((.76, 4.63), tiny([row]), anchor: "west")
  content((2.38, 4.63), tiny([stored geometry]), anchor: "west")
  row(4.24, [$e_0$], [finite pose · positive extent], ok: true)
  row(3.66, [$e_1$], [padding row], ok: false)
  row(3.08, [$e_2$], [finite pose · zero extent], ok: false)
  row(2.50, [$e_3$], [finite pose · positive extent], ok: true)

  // 2: deterministic seeded cap from the valid pool.
  heading(6.10, [2], [Form the task pool], [finite, non-padding, positive geometry], green)
  rect((6.10, 3.24), (10.72, 4.63), radius: .08, fill: green.lighten(92%), stroke: .65pt + green)
  content((6.38, 4.29), small([$cal(E)_"valid" = {e_0, e_3, dots}$]), anchor: "west")
  content((6.38, 3.86), tiny([seeded uniform · no replacement]), anchor: "west")
  content((6.38, 3.49), tiny([cap $K$ from the run manifest]), anchor: "west")
  task-chip(6.20, 2.39, [$e_0$])
  task-chip(7.62, 2.39, [$e_3$])
  task-chip(9.04, 2.39, [$e_7$], selected: false)

  // 3: task creation and a later, distinct evaluability decision.
  heading(11.62, [3], [Create oracle task rows], [GT identity; no proposal match], orange)
  rect((11.62, 3.24), (14.87, 4.63), radius: .08, fill: orange.lighten(91%), stroke: .65pt + orange)
  content((13.245, 4.28), align(center, small([$e, bold(phi)_e$])))
  content((13.245, 3.96), align(center, tiny([identity · class])))
  content((13.245, 3.66), align(center, tiny([pose · extent])))
  content((13.245, 3.38), align(center, text(size: 6.1pt, fill: muted, [reference-relative geometry])))

  line((15.38, 2.03), (15.38, 4.88), stroke: (paint: rule, thickness: .65pt, dash: "dashed"))
  rect((15.92, 3.24), (18.25, 4.63), radius: .08, fill: pale, stroke: .65pt + muted)
  content((17.085, 4.28), align(center, small([Oracle evaluability])))
  content((17.085, 3.88), align(center, tiny([mesh crop + support])))
  content((17.085, 3.54), align(center, tiny([rendered evidence])))

  line((5.23, 3.86), (6.06, 3.86), stroke: .8pt + green, mark: arrow)
  line((10.73, 3.86), (11.58, 3.86), stroke: .8pt + orange, mark: arrow)
  line((14.88, 3.86), (15.88, 3.86), stroke: .8pt + muted, mark: arrow)

  // Explicitly separate absent proposal-quality gates from the implemented rule.
  rect((.72, .34), (18.25, 1.58), radius: .07, fill: red.lighten(95%), stroke: (paint: red, thickness: .58pt, dash: "dashed"))
  content((1.02, 1.27), text(size: 7.35pt, weight: "bold", fill: red, [Not used for target admission]), anchor: "west")
  content((1.02, .86), small([actor proposal  ·  proposal–GT IoU  ·  ambiguity gap  ·  visibility/support threshold  ·  headroom threshold]), anchor: "west")
  content((1.02, .51), tiny([These belong to a future actor-visible protocol or to later oracle diagnostics.]), anchor: "west")
})
