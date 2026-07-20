#import "@preview/cetz:0.5.2"
#import "candidate_scene_primitives.typ": panel-point, wire-segments, candidate-marker

#set page(width: 160mm, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#17202a"))

#let data = json("data/candidate_scene_81286_000035.json")
#let ink = rgb("#17202a")
#let muted = rgb("#5f6b78")
#let rule = rgb("#c9d2dc")
#let pale = rgb("#f5f7f9")
#let history-color = rgb("#6b7280")
#let root-color = rgb("#315f93")
#let target-color = rgb("#b26a16")
#let valid-color = rgb("#23856d")
#let invalid-color = rgb("#b23a48")
#let selected-color = rgb("#f2c14e")
#let palette = (
  ink: ink,
  valid: valid-color,
  invalid: invalid-color,
  selected: selected-color,
)

#let panel(title, subtitle, body, footer) = block(
  width: 100%,
  inset: 2.6mm,
  radius: 1.2mm,
  stroke: .55pt + rule,
  fill: pale,
  [
    #text(size: 10.2pt, weight: "bold", title)
    #linebreak()
    #text(size: 8pt, fill: muted, subtitle)
    #v(1.3mm)
    #align(center, body)
    #v(1.2mm)
    #footer
  ],
)

#let scene-canvas(panel-data, mode: "oblique") = {
  let width = 7.25
  let height = 4.45
  cetz.canvas(length: 9.6mm, padding: .05, {
    import cetz.draw: *

    content(
      (0, 0),
      (width, height),
      image(
        "data/" + panel-data.at("background"),
        width: 100%,
        height: 100%,
        fit: "stretch",
      ),
    )

    wire-segments(
      panel-data.at("target_obb_segments"),
      width,
      height,
      1.1pt + target-color,
    )

    if mode == "oblique" {
      line(
        ..panel-data.at("history_path").map(point => panel-point(point, width, height)),
        stroke: (paint: history-color, thickness: .65pt, dash: "dashed"),
      )
      for frustum in panel-data.at("history_frusta") {
        wire-segments(frustum, width, height, .42pt + history-color)
      }
      for frustum in panel-data.at("valid_frusta") {
        wire-segments(frustum.at("segments"), width, height, .55pt + valid-color)
      }
      for frustum in panel-data.at("invalid_frusta") {
        wire-segments(
          frustum.at("segments"),
          width,
          height,
          (paint: invalid-color, thickness: .5pt, dash: "dashed"),
        )
      }
    } else {
      for candidate in panel-data.at("candidates") {
        candidate-marker(
          candidate.at("center"),
          width,
          height,
          valid: candidate.at("valid"),
          selected: candidate.at("selected"),
          colors: palette,
        )
      }
      line(
        ..panel-data.at("scale_bar").map(point => panel-point(point, width, height)),
        stroke: 1.15pt + ink,
      )
      let scale-mid = panel-point(panel-data.at("scale_bar").at(0), width, height)
      content(
        (scale-mid.at(0) + .57, scale-mid.at(1) + .08),
        anchor: "south",
        text(size: 6.8pt, fill: ink, [1 m]),
      )
    }

    line(
      ..panel-data.at("selected_path").map(point => panel-point(point, width, height)),
      stroke: 1.2pt + selected-color,
      mark: (end: ">", scale: .7),
    )
    wire-segments(
      panel-data.at("root_frustum"),
      width,
      height,
      1.0pt + root-color,
    )
    wire-segments(
      panel-data.at("selected_frustum"),
      width,
      height,
      1.0pt + ink,
    )

    let target-label = panel-point(panel-data.at("target_center"), width, height)
    content(
      (target-label.at(0), target-label.at(1) + .10),
      anchor: "south",
      text(size: 7.2pt, weight: "bold", fill: target-color, [$e=133$]),
    )
    let root-label = panel-point(panel-data.at("root_center"), width, height)
    content(
      (root-label.at(0), root-label.at(1) - .10),
      anchor: "north",
      text(size: 7.2pt, weight: "bold", fill: root-color, [$r_t$]),
    )
  })
}

#let counts = data.at("counts")
#let provenance = data.at("provenance")
#let selected = data.at("selected")

#grid(
  columns: (1fr, 1fr),
  gutter: 3.2mm,
  panel(
    [A. One decision state in its ASE scene],
    [logged RGB-camera history, oracle target OBB, and a thinned candidate overlay],
    scene-canvas(data.at("oblique"), mode: "oblique"),
    [
      #text(size: 7.2pt, fill: muted)[
        Dashed grey: logged history · green: valid examples · dashed red:
        clearance-rule rejections · black/gold: selected shell #selected.at("shell").
      ]
    ],
  ),
  panel(
    [B. Full finite action set in bird's-eye view],
    [all candidate centres retain shell identity; invalid rows lie outside the admissible set],
    scene-canvas(data.at("top"), mode: "top"),
    [
      #grid(
        columns: (auto, auto, auto),
        column-gutter: 2.2mm,
        align: (left, left, left),
        text(size: 7.2pt, fill: valid-color)[● #counts.at("valid") valid],
        text(size: 7.2pt, fill: invalid-color)[× #counts.at("invalid_clearance") clearance-invalid],
        text(size: 7.2pt, fill: ink)[◆ shell #selected.at("shell") selected],
      )
    ],
  ),
)

#v(1.4mm)
#align(center, text(size: 7.2pt, fill: muted)[
  Scene #provenance.at("scene_id"), sample `ASE_81286_Atek_000035`, rollout row
  #provenance.at("rollout_row"), step row #provenance.at("step_row");
  #counts.at("forward_local") forward-local + #counts.at("target_bearing_local") target-bearing
  + #counts.at("lateral_target_bypass") lateral-bypass candidates. Dense mesh layers are
  z-buffered raster; OBBs, paths, centres, and wire frusta remain vector geometry.
])
