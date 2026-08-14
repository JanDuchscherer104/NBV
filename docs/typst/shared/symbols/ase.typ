// Symbols for the ASE dataset, trajectories, and mesh-supervised substrate.
#let ase = (
    // GT mesh / surface.
    mesh: $cal(M)^"GT"$,
    // Target-specific GT surface / mesh crop.
    mesh_target: $cal(M)_e^"GT"$,
    // GT mesh faces / triangles.
    faces: $cal(F)^"GT"$,
    // Time-indexed world-from-rig trajectory pose.
    traj: $bold(T)_"rig"^"w" (t)$,
    // Final world-from-rig trajectory pose at step T.
    traj_final: $bold(T)_"rig"^"w" (T)$,
    // Canonical ASE time-indexed semi-dense set; `obs.points_semi_t` is unused duplicate notation.
    points_semi: $cal(P)_t^"semi"$,
  )
