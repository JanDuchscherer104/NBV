#import "@preview/scenery:0.1.0": build-scene, edge, face, camera, render-scene

#set page(width: auto, height: auto, margin: 4mm)
#set text(size: 8pt)

#let blue = rgb("#3269a8")
#let orange = rgb("#b56a19")
#let corners = (
  (-1.2, -0.75, 2.2),
  ( 1.2, -0.75, 2.2),
  ( 1.2,  0.75, 2.2),
  (-1.2,  0.75, 2.2),
)

#let scene = build-scene(
  face(corners, fill: blue.lighten(82%), stroke: .6pt + blue),
  ..corners.map(p => edge((0, 0, 0), p, stroke: .7pt + orange)),
  edge(corners.at(0), corners.at(1), stroke: .7pt + blue),
  edge(corners.at(1), corners.at(2), stroke: .7pt + blue),
  edge(corners.at(2), corners.at(3), stroke: .7pt + blue),
  edge(corners.at(3), corners.at(0), stroke: .7pt + blue),
)

#render-scene(
  scene,
  camera(azimuth: 32deg, elevation: 22deg),
  width: 55mm,
)
