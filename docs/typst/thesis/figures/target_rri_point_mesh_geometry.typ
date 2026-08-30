#import "@preview/cetz:0.5.2"

#set page(width: 160mm, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#18212b"))

#let data = json("data/point_mesh_metric_fixture.json")
#let ink = rgb("#18212b")
#let muted = rgb("#5d6977")
#let mesh-fill = rgb("#e4e8ec")
#let mesh-edge = rgb("#718096")
#let point-color = rgb("#2867a7")
#let accuracy-color = rgb("#7451a6")
#let completeness-color = rgb("#c4515b")
#let warning-color = rgb("#a85b16")
#let rule = rgb("#c7d0d9")

#let v2(raw, scale: (1, 1), offset: (0, 0)) = (
  offset.at(0) + raw.at(0) * scale.at(0),
  offset.at(1) + raw.at(1) * scale.at(1),
)

#let panel(title, subtitle, body) = block(
  width: 100%,
  inset: (top: 2.2mm, left: 2.4mm, right: 2.4mm, bottom: 2.2mm),
  stroke: (top: .7pt + ink, bottom: .45pt + rule),
  [
    #text(size: 10pt, weight: "bold", title)
    #linebreak()
    #text(size: 8pt, fill: muted, subtitle)
    #v(1.4mm)
    #body
  ],
)

#let primitive = data.at("primitive")
#let primitive-view = cetz.canvas(length: 10.8mm, padding: .15, {
  import cetz.draw: *
  let tri = primitive.at("triangle").map(point => v2(point, scale: (2.25, 2.25), offset: (.35, .42)))
  let p = v2(primitive.at("point"), scale: (2.25, 2.25), offset: (.35, .42))
  let q = v2(primitive.at("closest"), scale: (2.25, 2.25), offset: (.35, .42))

  line(..tri, close: true, fill: mesh-fill, stroke: .75pt + mesh-edge)
  line(p, q, stroke: 1.25pt + accuracy-color)
  circle(p, radius: .075, fill: point-color, stroke: .45pt + white)
  circle(q, radius: .065, fill: white, stroke: 1pt + accuracy-color)
  for (index, name) in ("a", "b", "c").enumerate() {
    content(tri.at(index), text(size: 7.6pt, weight: "bold", [$#name$]), anchor: "south")
  }
  content((p.at(0) + .16, p.at(1) + .06), text(size: 7.8pt, [$bold(p)$]), anchor: "west")
  content((q.at(0) + .14, q.at(1) - .05), text(size: 7.8pt, [$bold(q)$]), anchor: "west")
  content((2.45, 2.2), text(size: 7.6pt, fill: accuracy-color,
    [$d^2(bold(p), bold(f)) = norm(bold(p)-bold(q))^2$]), anchor: "west")
})

#let coarse = data.at("coarse")
#let reduction-view = cetz.canvas(length: 13.2mm, padding: .12, {
  import cetz.draw: *
  let scale = (1.65, 3.15)
  let offset = (.2, .55)
  let verts = coarse.at("vertices").map(point => v2(point, scale: scale, offset: offset))
  for face in coarse.at("faces") {
    let corners = face.map(index => verts.at(index))
    line(..corners, close: true, fill: mesh-fill, stroke: .55pt + mesh-edge)
  }

  // One exact representative per direction makes the asymmetric reductions
  // readable; the JSON retains every Trimesh witness used for verification.
  let accuracy-witness = coarse.at("point_to_face_witnesses").at(0)
  line(
    v2(accuracy-witness.at("point"), scale: scale, offset: offset),
    v2(accuracy-witness.at("closest"), scale: scale, offset: offset),
    stroke: 1.35pt + accuracy-color,
    mark: (end: ">", scale: .52),
  )
  let completeness-witness = coarse.at("face_to_point_witnesses").at(2)
  line(
    v2(completeness-witness.at("closest"), scale: scale, offset: offset),
    v2(completeness-witness.at("point"), scale: scale, offset: offset),
    stroke: (paint: completeness-color, thickness: 1.25pt, dash: "dashed"),
    mark: (end: ">", scale: .52),
  )
  for point in coarse.at("points") {
    circle(v2(point, scale: scale, offset: offset), radius: .065,
      fill: point-color, stroke: .35pt + white)
  }
  content((.18, 2.96), text(size: 7.6pt, fill: accuracy-color, [solid: $bold(p) arrow$ nearest triangle]), anchor: "west")
  content((.18, 2.62), text(size: 7.6pt, fill: completeness-color, [dashed: triangle $arrow$ nearest $bold(p)$]), anchor: "west")
})

#let tessellation-view(mesh, x-offset: 0, highlight-left: false) = {
  let scale = (1.0, 2.15)
  let offset = (x-offset, .6)
  let verts = mesh.at("vertices").map(point => v2(point, scale: scale, offset: offset))
  if highlight-left {
    let weighted-region = mesh.at("left_region_outline").map(
      point => v2(point, scale: scale, offset: offset),
    )
    cetz.draw.line(
      ..weighted-region,
      close: true,
      fill: warning-color.lighten(88%),
      stroke: (paint: warning-color, thickness: .55pt, dash: "dashed"),
    )
  }
  for face in mesh.at("faces") {
    let corners = face.map(index => verts.at(index))
    cetz.draw.line(..corners, close: true, fill: mesh-fill, stroke: .38pt + mesh-edge)
  }
  if highlight-left {
    let weighted-region = mesh.at("left_region_outline").map(
      point => v2(point, scale: scale, offset: offset),
    )
    cetz.draw.line(
      ..weighted-region,
      close: true,
      stroke: (paint: warning-color, thickness: .65pt, dash: "dashed"),
    )
  }
  for point in mesh.at("points") {
    cetz.draw.circle(v2(point, scale: scale, offset: offset), radius: .045,
      fill: point-color, stroke: .25pt + white)
  }
}

#let comparison-view = cetz.canvas(length: 10.8mm, padding: .12, {
  import cetz.draw: *
  tessellation-view(coarse, x-offset: .15)
  tessellation-view(data.at("refined"), x-offset: 3.10, highlight-left: true)
  content((1.25, 3.08), text(size: 7.5pt, weight: "bold", [4 equal-area]), anchor: "center")
  content((4.25, 3.08), text(size: 7.5pt, weight: "bold", [40 non-uniform]), anchor: "center")
  content((3.60, 2.73), text(size: 6.9pt, fill: warning-color,
    [left region: #data.at("refined").at("left_region_face_count")/#data.at("refined").at("face_count") equal-weight faces]), anchor: "center")
  content((1.25, .24), text(size: 7.2pt,
    [$D_(M arrow P) = $#coarse.at("completeness_display") $ "m"^2$]), anchor: "center")
  content((4.25, .24), text(size: 7.2pt, fill: warning-color,
    [$D_(M arrow P) = $#data.at("refined").at("completeness_display") $ "m"^2$]), anchor: "center")
})

#grid(
  columns: (1fr, 1fr, 1.16fr),
  gutter: 3.2mm,
  panel(
    [A. Exact point--triangle primitive],
    [the closest point may lie on the face, an edge, or a vertex],
    [
      #align(center, primitive-view)
      #text(size: 7.7pt)[The backend evaluates squared Euclidean distance to the triangle itself, not distance to its supporting plane or centroid.]
    ],
  ),
  panel(
    [B. Two directional reductions],
    [the arrows reverse which population contributes summands],
    [
      #align(center, reduction-view)
      #text(size: 7.7pt)[One exact witness is shown per direction; the implementation reduces over every point or every face.]
    ],
  ),
  panel(
    [C. Controlled tessellation check],
    [same planar surface + same points; only tessellation changes],
    [
      #align(center, comparison-view)
      #text(size: 7.7pt)[The left region contributes #data.at("refined").at("left_region_face_count") of #data.at("refined").at("face_count") equally weighted face summands.]
    ],
  ),
)

#v(1.8mm)
#block(
  width: 100%,
  inset: (x: 2.4mm, y: 1.5mm),
  fill: rgb("#f5f7f9"),
  stroke: (left: 1.3pt + warning-color),
  [
    #text(size: 8pt, weight: "bold")[Controlled conclusion.]
    #h(1mm)
    #text(size: 7.8pt)[$D_(P arrow M) = $#coarse.at("accuracy_display") $ "m"^2$ in both; $D_(M arrow P)$: #coarse.at("completeness_display") $arrow.r$ #data.at("refined").at("completeness_display") $ "m"^2$ after retessellation.]
  ],
)
