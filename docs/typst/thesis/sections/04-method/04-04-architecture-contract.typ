#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

== Geometric and Mask Acceptance Tests <sec:thesis-method-geometry-contract>

=== Acceptance boundary

The implemented acceptance boundary is the DTO, replay, and fitted-Q adapter contract. It is not a scorer-level architecture or invariance result. A production scorer must be admitted only after it preserves the row, source, frame, and mask contracts.

// evidence:
// - aria_nbv/aria_nbv/data_handling/qh_data/batching.py:62-136 -> selected training, successor, and no-bootstrap masks.
// - aria_nbv/tests/data_handling/test_qh.py:371-393 -> distinct successor masks and explicit all-invalid/no-bootstrap behavior.
// - aria_nbv/tests/lightning/test_qh_module.py:146-210,327-374 -> named profile privilege, geometry-hash, and contract-admission checks.

The required tests are literal. Permuting candidate rows must permute row-aligned outputs; changing invalid-row contents must not change valid-row values; padding must not become an action; `q_train_mask` must not widen valid action support; and an all-invalid successor must not be bootstrapped. Frame-transform tests apply to the DTO/adapter representation. They do not authorize a claim of exact $op("SE")(3)$ scorer invariance.

Actor/oracle tests must also reject GT target gains, GT associations, mesh distances, candidate renders, and target crops in actor inputs. A selected-depth source is accepted only under the explicit privileged CF+ profile and matching geometry contract. `qh_cf0_v1` and `qh_cfplus_gt_depth_v1` are separate experimental cohorts, not interchangeable checkpoints.

#development_only(() => [
  === Primary architecture direction

  The planned scorer is a bounded fixed-H candidate-value model. It reads actor-admitted root/context features, target context, factual history, remaining budget, and a finite candidate table, then emits one continuous value per candidate row. Masked selection uses only valid candidate rows. The current substrate provides the injected-scorer seam and owns transition validation, loss, target synchronization, and contract checks; scorer construction and policy evaluation remain a future deliverable.

  #figure(
    text(size: 8.2pt, table(
      columns: (0.9fr, 1.55fr),
      toprule(),
      table.header([*Primary component*], [*Contract*]),
      midrule(),
      [fixed-H candidate-value scorer], [one continuous value per finite candidate row, remaining budget in state, valid-action masked selection],
      [injected-scorer adapter], [selected-transition loss, target synchronization, profile and contract validation],
      bottomrule(),
    )),
    caption: [Primary geometric-learning contract.]
  ) <tab:geometric-learning-ladder>

  The fixed-H boundary keeps candidate interaction and representation choices subordinate to the information and support contracts. It does not require candidate-to-candidate attention, recurrent memory, or exact equivariant layers. Those choices may be evaluated only after a baseline scorer passes row, mask, source, frame, and support tests.

  The development ladder is A0 independent row scorer, A1 candidate-to-state query, A2 set context, A3 masked candidate interaction, and later temporal or equivariant variants. Requested-horizon conditioning is an alternative time-query design, not a primary architecture. A level advances only on a diagnosed failure and matched held-out evidence under the same actor protocol.
])
