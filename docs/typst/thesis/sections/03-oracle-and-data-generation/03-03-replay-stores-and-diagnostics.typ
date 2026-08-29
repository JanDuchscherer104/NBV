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
  caption: [Normalized lineage of the replay evidence. An immutable source row may define several target tasks; each target may produce several retained policy chains; each chain contains ordered steps; and each step owns one full candidate shell. Selected-action successor and finite-horizon training fields are derived from those factual relations rather than treated as an independent counterfactual transition table.],
) <fig:offline-rollout-store-relation>

#figure(
  publication-table(
    columns: (0.8fr, 1.35fr),
    header: ([*Evidence family*], [*Interpretation contract*]),
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
  caption: [Interpretation contract for rollout-store audits. Numeric values are rendered from the resolved report bundle in the experiment and reproducibility sections.],
) <tab:current-rollout-store-audit>

Selected-depth persistence stores only the depth raster and calibration for the
chosen action at each retained step. It can reconstruct the selected-observation
prefix without duplicating dense all-candidate renders, but persistence does not
make the source actor-visible. A privileged reader may consume selected
mesh-rendered depth; an actor-visible reader must consume an admitted sensor-like
or observed source. Unselected candidate renders remain oracle-only, and selected
depth is not an independently scored endpoint artifact.

Likewise, rollout rows summarize final cumulative selected-chain metrics; they do not preserve every rejected branch or a policy-neutral endpoint reconstruction. These limitations must be resolved by matched endpoint re-evaluation before confirmatory policy comparison.

The evidence contract is complete only when missingness remains explicit.
Reporting therefore retains target-task coverage, candidate validity and failure
reasons, family survival and selection, selected-history sanity, gain
distributions, source-role counts, and runtime or storage exclusions. Exact
schema columns, joins, compression, chunking, hashes, and execution commands
belong to the reproducibility record and resolved manifests. Development
bandwidth pilots may size later jobs but cannot support held-out reconstruction
or policy claims.
