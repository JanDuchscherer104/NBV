#import "@preview/maquette:0.1.1": render-obj

#set page(width: auto, height: auto, margin: 4mm)

#let mesh = read("maquette-octahedron.obj", encoding: none)

#render-obj(
  mesh,
  (
    projection: "orthographic",
    azimuth: 35,
    elevation: 24,
    up: (0, 0, 1),
    background: "none",
    color: "#94a3b8",
    shading: "gooch",
    gooch-cool: "#5077a8",
    gooch-warm: "#d6a04f",
    specular: 0.0,
    fresnel: 0.0,
    outline: (color: "#334155", width: 1.2),
  ),
  width: 55mm,
  height: 42mm,
  format: "svg",
)
