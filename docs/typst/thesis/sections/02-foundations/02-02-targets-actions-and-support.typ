#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "@preview/booktabs:0.0.4": *

== Targets, Actions, and Factual Support <sec:thesis-targets-actions-support>

A target-conditioned NBV task requires five distinct contracts: how the target
is specified, whether it is discovered from actor observations, how its
identity is associated over time, how the value function is conditioned on it,
and how endpoint quality is evaluated. EFM3D provides calibrated object boxes,
visibility, occlusion, and meshes, while object-centric 3DGS view planning
provides object features and a requested-object gate @EFM3D-straub2024
@ObjectCentricNBV-jeong2026. These sources support target definition and
supervision; a supplied box, mask, or identifier does not by itself establish
actor-visible target discovery or temporal association.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (OBB visibility, occlusion, observability, and ground-truth meshes)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object-feature supervision and requested-object confidence gate)

The evaluated action is likewise defined by more than a pose parameterization.
PB-NBV materializes a finite candidate set before scoring @PB-NBV-jia2025. At
step $t$, the candidate-row mask records which table rows exist, whereas the
action mask defines the state-dependent set from which selection is permitted.
The resulting policy is the hard-masked raw-value maximizer
$
  #eqs.rl.masked_candidate_selection
$
Invalid-action masking has a formal policy-gradient interpretation, but that
result does not establish a fitted-Q theorem for this setting
@InvalidActionMasking-huang2022. Here the equation is therefore a decision
contract: invalidity excludes an action; it is not a low or zero return.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (finite candidate proposal and score-based selection)
// - @InvalidActionMasking-huang2022 -> docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:52-56, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:66-71, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:150-174 (state-dependent valid actions and policy-gradient scope)

The following taxonomy separates the support roles implied by finite
candidate selection, state-dependent action masking, and fixed-batch learning
@PB-NBV-jia2025 @InvalidActionMasking-huang2022 @BCQ-fujimoto2019.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24 (candidate proposal and selection stages)
// - @InvalidActionMasking-huang2022 -> docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:66-71, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:88-91 (state-dependent valid-action sets and formal scope)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (fixed-batch support and extrapolation error)

#figure(
  text(size: 8.2pt, table(
    columns: (0.72fr, 1.1fr, 2.25fr),
    toprule(),
    table.header([*Symbol*], [*Support role*], [*Scientific meaning*]),
    midrule(),
    [$#symb.rl.candidate_row_mask$], [candidate row], [A materialized, non-padding row; it may still be invalid or unlabeled.],
    [$#symb.rl.action_mask$], [action], [Authoritative geometric and operational support for selection.],
    [$#symb.rl.q_label_mask$], [Q label], [A finite factual value target exists for the row at requested horizon $h$.],
    [$#symb.rl.feasibility_label_mask$], [feasibility label], [A trustworthy validity target exists; this need not coincide with value support.],
    [$#symb.rl.successor_mask$], [successor], [A selected transition has a factual successor or explicit terminal outcome.],
    [$#symb.rl.source_role$], [provenance], [Evidence is typed as actor-visible, supervision-only, or oracle evaluation.],
    bottomrule(),
  )),
  caption: [Support-role taxonomy for finite-candidate value learning. The separation follows finite candidate selection, state-dependent action masking, and fixed-batch support concerns.],
) <tab:thesis-mask-taxonomy>

These roles must remain separate in both training and evaluation. In particular,
multiplying a signed conditional value by a predicted validity probability can
reverse the ordering among valid negative-valued actions and silently replace
hard support with a different expected-utility objective. Learned feasibility
may be evaluated as an explicitly versioned alternative, but the authoritative
policy first restricts selection by the hard action mask and then compares raw
conditional values @InvalidActionMasking-huang2022 @BCQ-fujimoto2019.

// evidence:
// - @InvalidActionMasking-huang2022 -> docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:66-71, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:150-174 (invalid actions are excluded from the state-dependent policy support)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163 (unsupported-action extrapolation and constrained selection)
