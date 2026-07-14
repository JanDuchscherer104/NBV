#import "../../shared/macros.typ": *
#import "../../shared/symbols.typ": symb
#import "../draft_markers.typ": *

= Discussion <sec:thesis-discussion>

The discussion will interpret failures and gains only after the prerequisite support checks are available. If oracle lookahead has little headroom, the correct conclusion is about the evaluated target set, candidate distribution, horizon, and support regime, not about neural planning capacity in general. If headroom exists but #symb.rl.qh fails to recover it, the diagnosis should separate target identity, candidate validity, scene-representation support, replay coverage, mask handling, calibration, and model capacity.

Representation conclusions should preserve the actor/oracle boundary. EFM3D/EVL can be credited as Aria-native local target and support evidence; sparse ray-aware memory, semidense support, and logged DINO-on-point descriptors should be discussed as actor-visible representation ablations. CubeRCNN-style ROI features remain detector/appearance baselines unless an ARIA/ASE target-evidence contract comparable to EFM3D is demonstrated.

Sequence models, recurrent refinement, continuous control, 3D Gaussian Splatting, semantic planners, point or sparse backbones, spherical harmonics, residual heads, and attention ladders are bridge hypotheses. They may explain a measured bottleneck or define future experiments, but they are not consequences of the formal problem statement and cannot be presented as validated architecture choices without comparative evidence.

#research_todo(
  [After final experiments, move only evidence-backed limitations and future-work claims here; keep implementation recipes in Quarto implementation notes.],
  source: [thesis migration plan],
  gate: [final results pass],
)
