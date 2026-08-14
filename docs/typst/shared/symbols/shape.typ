// Dimension symbols used to document tensor and collection shapes.
#let shape = (
    // Batch size.
    B: $B$,
    // Generic count.
    N: $N$,
    // Number of candidates.
    Nq: $N_q$,
    // Trajectory length; glyph T can collide with `rl.transition` and bold transforms.
    Tlen: $T$,
    // Point count.
    P: $P$,
    // Max points after subsampling.
    Pmax: $P_"max"$,
    // Projected points.
    Pproj: $P_"proj"$,
    // Frustum points.
    Pfr: $P_"fr"$,
    // Generic feature dimension; glyph D can collide with `oracle.err`.
    D: $D$,
    // Image/tensor height; glyph H can collide with `rl.H` horizon.
    H: $H$,
    // Width.
    Wdim: $W$,
    // Reserved explicit image height; no direct authored use in the 2026-08-14 audit.
    Himg: $H_"img"$,
    // Reserved explicit image width; no direct authored use in the 2026-08-14 audit.
    Wimg: $W_"img"$,
    // Voxel grid size.
    Vvox: $V$,
    // Global pooling dim.
    Gpool: $G_"pool"$,
    // Reserved global-projection dimension; no direct authored use in the 2026-08-14 audit.
    Gproj: $G_"proj"$,
    // Semidense projection grid size.
    Gsem: $G_"sem"$,
    // Mesh vertex count.
    M: $M$,
    // Ordinal bins.
    K: $K$,
    // Per-point semidense feature dimension (e.g., XYZ + extras).
    Csem: $C_"sem"$,
    // Input feature-channel dimension.
    Fin: $F_"in"$,
    // Scene-field channel dimension.
    Ffield: $F_"field"$,
    // Pose-feature dimension.
    Fpose: $F_"pose"$,
    // Reserved positional-encoding dimension; no direct authored use in the 2026-08-14 audit.
    Fpe: $F_"pe"$,
    // Reserved candidate-feature dimension; no direct authored use in the 2026-08-14 audit.
    Fq: $F_q$,
    // Global-context feature dimension.
    Fg: $F_g$,
    // Reserved trajectory-context dimension; no direct authored use in the 2026-08-14 audit.
    Ftau: $F_tau$,
    // Reserved projection output dimension; no direct authored use in the 2026-08-14 audit.
    Fproj: $F_"proj"$,
    // Reserved convolutional dimension; no direct authored use in the 2026-08-14 audit.
    Fcnn: $F_"cnn"$,
    // Reserved token dimension; no direct authored use in the 2026-08-14 audit.
    Ftok: $F_"tok"$,
    // Reserved frustum-feature dimension; no direct authored use in the 2026-08-14 audit.
    Ffr: $F_"fr"$,
    // Reserved point-feature dimension; no direct authored use in the 2026-08-14 audit.
    Fpt: $F_"pt"$,
    // Reserved auxiliary dimension; no direct authored use in the 2026-08-14 audit.
    Faux: $F_"aux"$,
    // Prediction-head feature dimension.
    Fhead: $F_"head"$,
    // Hidden-layer feature dimension.
    Fhid: $F_"hid"$,
  )
