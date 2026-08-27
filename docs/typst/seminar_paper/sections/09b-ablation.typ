#import "../../shared/macros.typ": *
#import "../../shared/tables.typ": publication-table

= Ablation Plan and Open Experiments <sec:ablation-plan>

We tested various archtectural features, but could not establsih significant results due to the lack time and computational ressources as well as too many DoFs in our previous Optuna sweeps. Hence, we refer to these potential ablations as planned experiments with hypotheses about their impact; the
expected outcomes are summarized in @tab:ablations.


#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Planned ablations and hypotheses.],
  [
    #publication-table(
      columns: (9em, 8em, auto),
      header: ([Ablation], [Change], [Hypothesis]),
      align: (left, left, left),
      rows: ([Semi-dense point encoder], [on/off (PointNeXt)],
      [Does a global semi-dense embedding help beyond view-conditioned cues?], [Semi-dense frustum MHCA], [on/off],
      [Does token-level candidate conditioning improve ranking vs. projection stats alone?],
      [Visibility token embedding],
      [on/off],

      [Token-type embedding should help keep invalid points informative without masking.],
      [Mask invalid tokens],
      [on/off],

      [Masking may stabilize attention but can erase evidence about *missing* visibility.],
      [Observation counts],
      [on/off + normalization choice],

      [Track-length features should correlate with point reliability and improve frustum aggregation.],
      [Trajectory context],
      [on/off],

      [History-aware features should reduce ambiguity between candidates with similar geometry.],
      [Voxel reliability gating],
      [on/off],

      [Gating should reduce noise when candidates fall outside EVL voxel extent.],
      [Voxel reliability feature],
      [on/off],

      [Explicitly conditioning the head on evidence quality should improve calibration.],
      [Global pool resolution],
      [grid size $G$ in {$4, 5, 6, 7, 8$}],

      [Higher resolution may help in clutter but risks overfitting / compute overhead.],
      [CORAL imbalance handling],
      [loss variant: CORAL vs. balanced vs. focal],

      [Better gradients for rare thresholds; less median-bin collapse.],
      [Coverage-weight curriculum],
      [on/off (annealed weighting)],

      [Early emphasis on high-evidence candidates should prevent collapse while still learning all candidates.],
      ),
    )
  ],
) <tab:ablations>

// <rm>
// Planned-results scaffolding (no numbers yet). Either add the actual ablation results
// (table + variance) or move this plan to a TODO list / appendix.
We will report per-epoch Spearman correlation, confusion matrices, and
calibration curves for each ablation, and use these results to guide the
transition to entity-aware NBV.
// </rm>

== Current Evidence: Two Baselines

The current top-2 training runs runs provide an *uncontrolled* comparison of trajectory
conditioning:
- `hq1how1j` (`R2026-01-27_13-08-02`): trajectory encoder disabled, ReduceLROnPlateau, no auxiliary regression loss, batch size of 16 instead of 8. Trained for 22 epochs (early stopped at 21).
- `rtjvfyyp` (`v03-best`): trajectory encoder enabled, OneCycleLR. Trained for 35 epochs (early stopped at 22)

`rtjvfyyp` achieves better validation metrics, but the evidence is inconclusive:
the two runs differ in more than the trajectory encoder and require a controlled
ablation to attribute gains to trajectory features.

#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Final validation metrics for the current top-2 runs (last logged points).],
  [
    #publication-table(
      columns: (auto, auto, auto, auto),
      header: ([Run], [$#(symb.vin.loss) _("rel")$], [$rho$], [$"TopKAcc"(3)$]),
      align: (left, left, left, left),
      rows: ([`hq1how1j`], [0.677], [0.469],
      [0.314], [`rtjvfyyp`], [0.666], [0.501],
      [0.329]),
    )
  ],
) <tab:wandb-top2-final>

#figure(
  grid(
    columns: (1fr, 1fr),
    rows: (auto, auto),
    gutter: 10pt,
    align(center)[text(weight: "bold")[`hq1how1j` (start)]], align(center)[text(weight: "bold")[`hq1how1j` (finish)]],
    image("/figures/wandb/hq1how1j/val-figures/confusion_start.png", width: 100%),
    image("/figures/wandb/hq1how1j/val-figures/confusion_end.png", width: 100%),
  ),
  caption: [Validation confusion matrices for `hq1how1j` (first and last logged). The corresponding matrices for `rtjvfyyp` are shown in @fig:wandb-rtjvfyyp-conf.],
) <fig:wandb-hq1how1j-conf>

*Status.* The current VINv3 baseline (Jan 2026 run) already realizes several
ablations by design: PointNeXt is off, frustum MHCA is off, and trajectory
context is disabled. The delta to `rtjvfyyp` confirms that trajectory features are neither harmful nor informative, that the choice of LR schedule doesn't matter significantly, and that auxiliary regression loss is not essential to training performance. It shoudl be noted that the confusion matrix of the ablation run looks somewhat better calibrated than the baseline. Futhermore, both runs use coverage-weight curriculum, balanced CORAL loss, and voxel reliability gating and features which should be ablated in future controlled experiments.
