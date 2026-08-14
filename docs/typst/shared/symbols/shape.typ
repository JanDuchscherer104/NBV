// Dimension symbols used to document tensor and collection shapes.
#let shape = (
    // Batch size.
    B: $B$,
    // Generic count.
    N: $N$,
    // Number of candidates.
    Nq: $N_q$,
    // Trajectory length / time steps.
    Tlen: $T$,
    // Point count.
    P: $P$,
    // Max points after subsampling.
    Pmax: $P_"max"$,
    // Projected points.
    Pproj: $P_"proj"$,
    // Frustum points.
    Pfr: $P_"fr"$,
    // Feature dimension (generic).
    D: $D$,
    // Height.
    H: $H$,
    // Width.
    Wdim: $W$,
    // Image height/width (pixel space).
    Himg: $H_"img"$,
    // Image width in pixels.
    Wimg: $W_"img"$,
    // Voxel grid size.
    Vvox: $V$,
    // Global pooling dim.
    Gpool: $G_"pool"$,
    // Global projection dim.
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
    // Positional-encoding feature dimension.
    Fpe: $F_"pe"$,
    // Candidate-feature dimension.
    Fq: $F_q$,
    // Global-context feature dimension.
    Fg: $F_g$,
    // Trajectory-context feature dimension.
    Ftau: $F_tau$,
    // Projection-layer output dimension.
    Fproj: $F_"proj"$,
    // Convolutional feature dimension.
    Fcnn: $F_"cnn"$,
    // Token embedding dimension.
    Ftok: $F_"tok"$,
    // Frustum feature dimension.
    Ffr: $F_"fr"$,
    // Point feature dimension.
    Fpt: $F_"pt"$,
    // Auxiliary-head feature dimension.
    Faux: $F_"aux"$,
    // Prediction-head feature dimension.
    Fhead: $F_"head"$,
    // Hidden-layer feature dimension.
    Fhid: $F_"hid"$,
  )
