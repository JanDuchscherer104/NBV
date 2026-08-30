#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/tables.typ": publication-table

== Evidence and Reproducibility

The experiment preserves two evidence roles. An immutable source store owns the
logged actor substrate and one-step oracle products; a replay store references
those rows and owns target tasks, retained chains, per-step candidate shells,
hard masks, reason codes, and selected-action successor evidence. This boundary
prevents counterfactual experiments from mutating their source and prevents
dense one-step labels from being mistaken for factual multi-step transitions.

Lineage follows the scientific units. One source may define several target
tasks; one task may produce several recipe-specific retained chains; one chain
contains ordered selected steps; and each step owns a full finite candidate
shell. The store therefore represents selected or beam-retained evidence rather
than an exhaustive counterfactual tree. Derived padded training arrays remain
caches over these factual relations. Invalid rows stay auditable while action,
training, and bootstrap masks exclude them from their respective decisions.

#figure(
  align(center, image(
    "../../figures/replay_lineage_relations.pdf",
    width: 100%,
  )),
  alt: "An immutable VIN source row and a replay target-task row each point to one or more retained rollout chains through the source_row_id and target_row_id stored on each rollout row. Inside a dashed factual-replay boundary, each chain points to ordered steps and each step to a full candidate shell containing exactly one selected row. One downward materialization arrow leads from the factual tables to a derived Q_H cache of padded identifiers, copied masks, rewards, and selected-action successor fields. The cache is validated against its factual rows and is not an independent transition table or exhaustive counterfactual tree.",
  caption: [Persisted replay lineage and repository-validated $Q_H$ materialization. Solid links are persisted row references or ownership relations; the selected marker identifies one member of each full candidate shell.],
) <fig:offline-rollout-store-relation>

#figure(
  publication-table(
    columns: (0.8fr, 1.35fr),
    header: ([*Evidence family*], [*Scientific interpretation*]),
    rows: (
      [Sources and targets],
      [Manifest-backed task coverage; not proof of actor-visible target discovery.],
      [Candidates and invalidity],
      [Full-shell support with separate hard-action, training, padding, and future deployable-feasibility roles.],
      [Retained chains and steps],
      [Recipe-selected evidence; not a persisted exhaustive search tree.],
      [Selected depth],
      [Chosen-action successor observation with calibration and source role; actor input only under an explicitly admitted later-state protocol.],
      [Finite-horizon training view],
      [Derived training cache whose rewards and masks must agree with factual rows; not a scene-memory representation.],
      [Candidate-support metrics],
      [Attempted-row actor-valid fraction, per-state valid support, configured-family zero rate, attempted target-conditioned side balance and circular span, calibrated target-centre projection fraction, finite-support oracle opportunity, and bounded-jitter compliance.],
      [Metric populations],
      [State metrics aggregate state then scene then cohort; failed roots and zero-valid configured family/state pairs remain in denominators. Projection is framing, oracle opportunity is headroom, and jitter is QC—not visibility or policy performance.],
    ),
  ),
  caption: [Scientific interpretation of replay evidence. Numeric values are rendered from the resolved report bundle in the experiment and reproducibility sections.],
) <tab:current-rollout-store-audit>

Selected-depth persistence stores only the depth raster and calibration for the
chosen action at each retained step. It can reconstruct the selected-observation
prefix without duplicating dense all-candidate renders, but persistence does not
make the source actor-visible. A privileged reader may consume selected
mesh-rendered depth; an actor-visible reader must consume an admitted sensor-like
or observed source. Unselected candidate renders remain oracle-only, and selected
depth is not an independently scored endpoint artifact.

Likewise, rollout rows summarize final cumulative selected-chain metrics; they do not preserve every rejected branch or a policy-neutral endpoint reconstruction. These limitations must be resolved by matched endpoint re-evaluation before confirmatory policy comparison.

Missingness is part of the evidence rather than an ordinary zero. Reporting
therefore retains target-task coverage, candidate validity and failure
reasons, family survival and selection, selected-history sanity, gain
distributions, source-role counts, and runtime or storage exclusions. Exact
schema columns, joins, compression, chunking, hashes, and execution commands
belong to the reproducibility record and resolved manifests. Development
bandwidth pilots may size later jobs but cannot support held-out reconstruction
or policy claims.
