#import "../symbols.typ": symb

#let rri = (
    error: $
      #symb.oracle.err (#symb.oracle.points, #symb.ase.mesh) =
      #symb.oracle.dist_pm (#symb.oracle.points, #symb.ase.mesh)
      +
      #symb.oracle.dist_mp (#symb.oracle.points, #symb.ase.mesh)
    $,
    // Compatibility key for older notation lookups; ARIA-NBV uses point-mesh error D.
    cd: $
      #symb.oracle.err (#symb.oracle.points, #symb.ase.mesh) =
      #symb.oracle.dist_pm (#symb.oracle.points, #symb.ase.mesh)
      +
      #symb.oracle.dist_mp (#symb.oracle.points, #symb.ase.mesh)
    $,
    dist_pm: $
      #symb.oracle.dist_pm (#symb.oracle.points, #symb.ase.mesh) =
      (1)/(||#symb.oracle.points||)
      sum_(bold(p) in #symb.oracle.points)
      min_(bold(f) in #symb.ase.faces) d(bold(p), bold(f))^2
    $,
    dist_mp: $
      #symb.oracle.dist_mp (#symb.oracle.points, #symb.ase.mesh) =
      (1)/(||#symb.ase.faces||)
      sum_(bold(f) in #symb.ase.faces)
      min_(bold(p) in #symb.oracle.points) d(bold(p), bold(f))^2
    $,
    acc: $
      #symb.oracle.dist_pm (#symb.oracle.points, #symb.ase.mesh) =
      (1)/(||#symb.oracle.points||)
      sum_(bold(p) in #symb.oracle.points)
      min_(bold(f) in #symb.ase.faces) d(bold(p), bold(f))^2
    $,
    comp: $
      #symb.oracle.dist_mp (#symb.oracle.points, #symb.ase.mesh) =
      (1)/(||#symb.ase.faces||)
      sum_(bold(f) in #symb.ase.faces)
      min_(bold(p) in #symb.oracle.points) d(bold(p), bold(f))^2
    $,
    // Conventional bidirectional Chamfer distance between two point samples.
    // This is an alternative to ARIA-NBV's fixed ASE mesh point-to-face error;
    // the point sets' sampling densities therefore remain part of its meaning.
    point_sampled_chamfer: $
      D_"PS-Chamfer"(cal(P), cal(Q))
      =
      (1)/(||cal(P)||) sum_(bold(p) in cal(P))
        min_(bold(q) in cal(Q)) ||bold(p) - bold(q)||_2^2
      +
      (1)/(||cal(Q)||) sum_(bold(q) in cal(Q))
        min_(bold(p) in cal(P)) ||bold(q) - bold(p)||_2^2
    $,
    union: $
      #(symb.oracle.points) _(t union q) = #(symb.oracle.points) _t union #symb.oracle.points_q
    $,
    rri: $
      op("RRI") (q) =
      (
        #symb.oracle.err (#(symb.oracle.points)_t, #symb.ase.mesh)
        -
        #symb.oracle.err (#(symb.oracle.points)_t union #symb.oracle.points_q, #symb.ase.mesh)
      )
      /
      (#symb.oracle.err (#(symb.oracle.points)_t, #symb.ase.mesh) + epsilon)
    $,
    target_rri: $
      op("RRI")_e (q) =
      (
        #symb.oracle.err (#(symb.oracle.points)_t^e, #symb.ase.mesh_target)
        -
        #symb.oracle.err (#(symb.oracle.points)_t^e union #(symb.oracle.points)_q^e, #symb.ase.mesh_target)
      )
      /
      (#symb.oracle.err (#(symb.oracle.points)_t^e, #symb.ase.mesh_target) + epsilon)
    $,
    greedy: $ q_star = op("argmax", limits: #true)_(q in #symb.oracle.candidates) op("RRI") (q) $,
  )
