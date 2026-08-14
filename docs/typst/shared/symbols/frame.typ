// Short labels used as coordinate-frame arguments in transforms and poses.
#let frame = (
    // World-frame label; plain w also denotes weights elsewhere, so qualify mixed equations.
    w: $w$,
    // Rig-frame label; plain r also denotes reward/RRI elsewhere, so qualify mixed equations.
    r: $r$,
    // Camera-frame label; plain c also denotes coverage elsewhere, so qualify mixed equations.
    c: $c$,
    // Candidate camera frame label.
    cq: $c_q$,
    // Voxel-frame label; plain v also denotes validity elsewhere, so qualify mixed equations.
    v: $v$,
    // Sampling frame label (gravity-aligned shell).
    s: $s$,
  )
