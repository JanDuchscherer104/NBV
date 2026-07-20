# Maquette 0.1.1

Use Maquette when a figure must render a local PLY, OBJ, or STL body directly
from Typst. Prefer orthographic projection and restrained diffuse or Gooch
shading for technical shape communication. Record the input checksum, units,
up axis, camera, projection, decimation, palette, and output mode.

Project fixture:
`../../assets/fixtures/maquette-smoke.typ`, with the closed test mesh
`../../assets/fixtures/maquette-octahedron.obj`. Compile from the repository
root:

```sh
typst compile \
  .agents/skills/typst-authoring/assets/fixtures/maquette-smoke.typ \
  /tmp/maquette-smoke.pdf --root .
```

The SVG fixture passed with Typst 0.14.2 on 2026-07-19. SVG uses a painter's
algorithm and is appropriate only for low- or medium-poly meshes whose ordering
has been inspected. Dense, concave, or strongly intersecting meshes use the
z-buffered PNG output, with Typst/CeTZ retaining vector axes, labels, frusta,
and callouts. Avoid decorative effects such as bloom, glow, glossy highlights,
or x-ray transparency unless they encode a stated scientific property.

Primary sources: [Typst Universe](https://typst.app/universe/package/maquette/)
and [upstream repository](https://github.com/bernsteining/maquette).
