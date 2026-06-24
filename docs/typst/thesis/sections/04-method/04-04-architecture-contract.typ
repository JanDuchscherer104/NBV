#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Architecture Contract and Geometric Acceptance Tests <sec:thesis-method-geometry-contract>

// source: docs/contents/theory/candidate_view_dependence.qmd:83-89 and docs/contents/theory/candidate_view_dependence.qmd:384-421 define the candidate-set architecture ladder.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:2502-2603 defines the derived q_h training view, masks, rewards, and TD links.
The geometric-learning rationale in @sec:thesis-geometric-learning-theory becomes replay-field acceptance tests. Each module must answer a symmetry or provenance requirement: candidate rows need row-level permutation equivariance; invalid and padded rows need mask isolation; candidate, target, and history geometry need local frames; and actor/oracle fields need separate provenance. The task is gravity aligned and egocentric, so exact global $op("SO")(3)$ or $op("SE")(3)$ equivariance is an ablation claim, not the default system claim.

#figure(
  align(center, image(
    "../../figures/qh_symmetry_contract.pdf",
    width: 100%,
  )),
  caption: [Minimum symmetry and provenance contract for the finite-candidate #symb.rl.qh model. The contract requires row-level equivariance, mask isolation, local-frame geometry, target-local directional memory, and oracle/actor provenance gates; it does not claim exact global $op("SE")(3)$ equivariance.],
) <fig:qh-symmetry-contract>

The first model family should therefore use scalar invariant and local-frame relative features before heavier equivariant tensor machinery. Relative transforms such as $xi_(r_t,i)^"rel"$ and candidate-local target vectors such as $bold(R)_(t,i)^top (bold(c)_e - bold(c)_(t,i))$ are deliberate gauge choices: they remove irrelevant global-coordinate dependence while preserving yaw, elevation, distance, gravity/up, frustum, and approach-direction signals needed for visibility. Directional history is a separate object. A selected view direction belongs on $bb(S)^2$ and should be stored as a target-local histogram, second-moment matrix, or low-order spherical-harmonic memory rather than being merged into generic pose features. This separation follows the geometric-learning distinction between physical symmetries and useful task structure, and it protects the interpretation of each ablation: a QCNet-style relative positional bias tests candidate-candidate geometry, while directional memory tests whether the target has already been observed from similar directions @GeometricDeepLearning-bronstein2021 @zhou2023query @e3nn-SphericalHarmonics-2025.

The architecture acceptance tests are as important as validation loss. Row-shuffle tests must satisfy $f_theta (Pi X_t, m_t)=Pi f_theta (X_t, m_t)$ up to numerical tolerance for every per-candidate output used by selection. Mask tests must show that invalid rows cannot alter valid scores except through explicit valid-count or support features. Valid-count and duplicate-row stress tests check whether attention normalization has corrupted absolute target-specific @relative-reconstruction-improvement:short calibration. Only after the independent scorer and candidate-to-state query controls pass these tests should DeepSets context, masked Set Transformer interaction, Fisher/SCONE overlap bias, QCNet-style local relative positional encoding, or EGNN-style candidate graphs be credited as architectural gains @DeepSets-zaheer2017 @SetTransformer-lee2019 @FisherRF-jiang2024 @SCONE-guedon2022 @EGNN-satorras2021.

The token design follows the same separation of concerns. State tokens summarize known actor-visible evidence before the next view; candidate tokens describe one finite action and its mask/reason code; relation tokens describe target/candidate/history geometry; label tokens store GT target crops, target gains, endpoint metrics, and TD targets outside the actor graph. The first model should therefore start with a per-candidate scorer and candidate-to-state cross-attention; pooled set context or masked candidate-candidate attention is an ablation only when interaction is needed.

#research_todo(
  [Treat Fisher/SCONE overlap attention and QCNet-style relative encodings as ablation hypotheses until row-shuffle, mask-isolation, and paired oracle policy evidence show they improve target-specific endpoint gain over simpler controls.],
  source: [autoresearch thesis-lit-review report; docs/contents/theory/candidate_view_dependence.qmd],
  gate: [A2/A3/A4 architecture ablation tables],
)
