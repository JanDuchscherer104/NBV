#import "@preview/cetz:0.5.2"
#import "@preview/scenery:0.1.0": build-scene, uv-sphere, sphere, edge, arrow, camera, render-scene

#set page(width: 160mm, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#17202a"))

#let data = json("data/directional_memory_81286_000024_inst128.json")
#let ink = rgb("#17202a")
#let muted = rgb("#5f6b78")
#let rule = rgb("#c9d2dc")
#let pale = rgb("#f5f7f9")
#let history-color = rgb("#3269a8")
#let query-color = rgb("#b56a19")
#let sphere-color = rgb("#d7dee6")
#let x-color = rgb("#b23a48")
#let y-color = rgb("#23856d")
#let z-color = rgb("#5c4fa3")

#let v2(a) = (a.at(0), a.at(1))
#let v3(a) = (a.at(0), a.at(1), a.at(2))
#let history = data.at("history_directions").map(v3)
#let query = v3(data.at("query_direction"))

#let sphere-scene = build-scene(
  uv-sphere(
    (0, 0, 0),
    1,
    segments: 18,
    rings: 9,
    color: sphere-color,
    // Scenery interprets fill-opacity as a transparentize amount.
    fill-opacity: 100%,
    stroke: (paint: rgb("#8d9baa"), thickness: .3pt),
    hidden-stroke: (paint: rgb("#c7d0da"), thickness: .16pt),
    cull: none,
  ),
  ..history.map(direction => edge(
    (0, 0, 0),
    direction,
    color: history-color,
    width: .65pt,
  )),
  ..history.map(direction => sphere(direction, .045, color: history-color, specular: false)),
  edge((0, 0, 0), query, color: query-color, width: 1.1pt),
  sphere(query, .065, color: query-color, specular: false),
  arrow((0, 0, 0), (1.14, 0, 0), color: x-color, w: .016),
  arrow((0, 0, 0), (0, 1.14, 0), color: y-color, w: .016),
  arrow((0, 0, 0), (0, 0, 1.14), color: z-color, w: .016),
)

#let panel(title, subtitle, body) = block(
  width: 100%,
  inset: (top: 2.2mm, left: 2.5mm, right: 2.5mm, bottom: 2.2mm),
  stroke: (top: .7pt + ink, bottom: .45pt + rule),
  [
    #text(size: 10.2pt, weight: "bold", title)
    #linebreak()
    #text(size: 8pt, fill: muted, subtitle)
    #v(1.4mm)
    #body
  ],
)

#let mollweide-map = cetz.canvas(length: 10.8mm, padding: .12, {
  import cetz.draw: *
  let outline = data.at("mollweide_outline").map(v2)
  let grid-color = rgb("#aeb8c3")
  line(..outline, close: true, fill: white, stroke: .7pt + rgb("#657383"))
  for curve in data.at("mollweide_graticule").at("latitudes") {
    line(..curve.map(v2), stroke: .35pt + grid-color)
  }
  for curve in data.at("mollweide_graticule").at("longitudes") {
    line(..curve.map(v2), stroke: .35pt + grid-color)
  }
  for point in data.at("history_mollweide") {
    circle(v2(point), radius: .055, fill: history-color, stroke: none)
  }
  let q = v2(data.at("query_mollweide"))
  circle(q, radius: .09, fill: white, stroke: 1pt + query-color)
  line((q.at(0) - .055, q.at(1)), (q.at(0) + .055, q.at(1)), stroke: .8pt + query-color)
  line((q.at(0), q.at(1) - .055), (q.at(0), q.at(1) + .055), stroke: .8pt + query-color)
})

#grid(
  columns: (1.05fr, 1.18fr),
  gutter: 4mm,
  panel(
    [A. Target-centred directions on $bb(S)^2$],
    [actual logged camera centres, expressed in the target-object frame],
    align(center, [
      #render-scene(
        sphere-scene,
        camera(azimuth: -38deg, elevation: 19deg),
        width: 69mm,
      )
      #text(size: 7.5pt)[
        #text(fill: history-color)[● logged history direction] #h(2.5mm)
        #text(fill: query-color)[⊕ example query]
      ]
      #linebreak()
      #text(size: 7.3pt, fill: muted)[
        Scene #data.at("scene_id"), sample #data.at("snippet_id"), target instance
        #data.at("target_instance_id"); frames
        #data.at("history_frames").map(str).join([, ]) and query frame
        #data.at("query_frame").
      ]
    ]),
  ),
  panel(
    [B. Complete-domain view and prospective compression],
    [Mollweide is equal-area; no smooth field or SH lobe is implied],
    [
      #align(center, mollweide-map)
      #align(center, text(size: 7.4pt, fill: muted)[
        $+x_e$ at map centre · $+z_e$ north · wrap seam at $plus.minus 180 degree$
      ])
      #v(2.5mm)
      #align(center, $bold(M)_"dir"(v) = sum_(k<t) w_k(v) bold(d)_k(v) bold(d)_k(v)^top$)
      #v(1.8mm)
      #align(center, $nu_i(v) = 1 - frac(bold(d)_i^top bold(M)_"dir" bold(d)_i, op("tr") bold(M)_"dir" + epsilon)$)
      #v(2.5mm)
      #text(size: 7.8pt)[
        This fixture uses uniform weights and a logged future pose only to make
        the second-moment query inspectable. It does not claim that the learner
        currently stores $bold(M)_"dir"$ or that this novelty predicts target
        RRI.
      ]
      #v(2.5mm)
      #block(
        inset: 2mm,
        radius: 1mm,
        fill: none,
        stroke: (left: 1.1pt + query-color),
        text(size: 7.5pt, fill: ink)[
          HYPOTHESIS / ABLATION MATERIAL. Keep outside submission claims until
          the representation exists and paired evaluation tests whether it adds
          information beyond pose distance and overlap.
        ],
      )
    ],
  ),
)
