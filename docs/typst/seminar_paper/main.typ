#import "charged_ieee_local.typ": ieee
#import "../shared/macros.typ": *

#let figures_path = "/figures/"

#show: ieee.with(
  title: [Aria-NBV: Quality-Driven Next-Best-View Planning with Egocentric Foundation Models],
  abstract: [
    Next-Best-View (NBV) planning addresses the fundamental challenge of autonomous viewpoint selection in active 3D reconstruction, aiming to maximize acquisition quality under a limited capture budget. Classical NBV methods rely on hand-crafted criteria, limited action spaces, or per-scene optimized representations. Learning-based NBV methods improve generalization but still optimize geometric coverage as a proxy for reconstruction quality, which can fail in cluttered scenes with occlusions and fine details. Diretly optimizing reconstruction quality, as pioneered by VIN-NBV @VIN-NBV-frahm2025, improves candidate ranking via Relative Reconstruction Improvement (RRI) but remains limited to object-centric scenarios without pre-trained foundation-model priors.

    We introduce Aria-VIN-NBV, an oracle labeling pipeline for quality-driven RRI based NBV on egocentric indoor trajectories in Aria Synthetic Environments (ASE). We compute oracle RRI labels by rendering candidate depths from ASE ground-truth meshes and scoring their RRI relative to a previously captured SLAM point clud. Utilizing these labels we train an RRI prediction model leveraging an egocentric foundation model (EFM3D) backbone to capture rich priors from large-scale pre-training.
  ],
  authors: (
    (
      name: "Jan Duchscherer",
      department: [Department of Computer Science & Mathematics],
      organization: [Munich University of Applied Sciences],
      location: [Munich, Germany],
      email: "j.duchscherer@hm.edu",
    ),
  ),
  index-terms: (
    "next-best-view",
    "relative reconstruction improvement",
    "egocentric foundation models",
    "EFM3D",
    "Aria Synthetic Environments",
    "ordinal regression",
  ),
  bibliography: bibliography("/references.bib"),
  figure-supplement: [Fig.],
  paper-size: "a4",
)

// #set text(font: "DejaVu Serif")
#set text(font: "New Computer Modern")



#include "sections/01-introduction.typ"
#include "sections/02-related-work.typ"
#include "sections/03-problem-formulation.typ"
#include "sections/04-dataset.typ"
#include "sections/05-coordinate-conventions.typ"
#include "sections/05-oracle-rri.typ"
#include "sections/06-architecture.typ"
#include "sections/07-training-objective.typ"
#include "sections/09a-evaluation.typ"
#include "sections/09c-wandb.typ"
#include "sections/09b-ablation.typ"
#include "sections/10-discussion.typ"
#include "sections/10a-extensions.typ"
#include "sections/11-conclusion.typ"
#include "sections/12c-appendix-oracle-rri-labeler.typ"
#include "sections/12f-appendix-pose-frames.typ"
#include "sections/12h-appendix-offline-cache.typ"
#include "sections/12b-appendix-extra.typ"
