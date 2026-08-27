#import "../../shared/macros.typ": *
#import "../../shared/tables.typ": publication-table

= Training Dynamics <sec:wandb-analysis>

// <rm>
// This section is currently run-specific (W&B ids, “start→finish” plots) and reads like a
// lab notebook. Prefer moving it to an appendix or to external artifacts, and keep the main
// paper focused on (i) the oracle pipeline + dataset + metric contract and (ii) NBV-relevant
// evaluation (e.g., greedy one-step rollouts vs baselines).
// </rm>

// <rm>
This section summarizes training dynamics of the current best run and
visualizes how validation ordinal performance evolves over training.

The run shown here is `rtjvfyyp` (`v03-best`).

We focus on the *within-run* improvement (start #sym.arrow finish) rather than
attributing changes to specific architectural or optimization choices. A
comparison against another near-identical run is discussed in
@sec:ablation-plan.

In particular, `rtjvfyyp` improves from validation relative CORAL loss
$#(symb.vin.loss) _("rel") = 0.743$ to $0.666$ and from Spearman
$rho = 0.254$ to $0.501$ over training.

// TODO Include this figure in slides_4.typ
#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Start #sym.arrow finish improvements for `rtjvfyyp` (first and last logged points).],
  [
    #publication-table(
      columns: (auto, auto),
      header: ([Metric], [Start #sym.arrow finish (delta)]),
      align: (left, left),
      rows: ([$#(symb.vin.loss) _("rel")^"train"$],
      [0.777 #sym.arrow 0.659 (-15.2%)], [$#(symb.vin.loss) _("rel")^"val"$],
      [0.743 #sym.arrow 0.666 (-10.4%)], [$rho(r, hat(r))$],
      [0.254 #sym.arrow 0.501 (+96.9%)], [$"Acc"@3$ (val)],
      [0.248 #sym.arrow 0.329 (+32.8%)]),
    )
  ],
) <tab:wandb-rtjvfyyp-improvement>

#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/wandb/train-coral-rel-epoch.png", width: 100%),
    image("/figures/wandb/train-corlal-rel-step.png", width: 100%),

    image("/figures/wandb/val-coral-rel.png", width: 100%), image("/figures/wandb/val-top3-acc.png", width: 100%),
  ),
  caption: [CORAL loss (relative-to-random) and validation top-3 bin accuracy (shown for `rtjvfyyp`).],
) <fig:wandb-coral>

// TODO: move to 12b-appendix-extra
#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/wandb/train-aux-reg.png", width: 100%), image("/figures/wandb/train-aux-weight.png", width: 100%),
  ),
  caption: [Auxiliary regression loss and weight schedule (shown for `rtjvfyyp`).],
) <fig:wandb-aux>

#figure(
  grid(
    columns: (1fr, 1fr),
    rows: (auto, auto),
    gutter: 10pt,
    align(center)[text(weight: "bold")[`rtjvfyyp` (start)]], align(center)[text(weight: "bold")[`rtjvfyyp` (finish)]],
    image("/figures/wandb/rtjvfyyp/val-figures/confusion_start.png", width: 100%),
    image("/figures/wandb/rtjvfyyp/val-figures/confusion_end.png", width: 100%),
  ),
  caption: [Validation confusion matrices for `rtjvfyyp` (first and last logged).],
) <fig:wandb-rtjvfyyp-conf>

== Observations

- The run improves validation ordinal performance substantially over training
  (Spearman and top-3 accuracy increase, and `val/coral_loss_rel_random`
  decreases).
- The *early* validation confusion matrices are highly collapsed (nearly
  constant predictions), while the *final* matrices show a much richer
  structure with fewer massed columns.
// </rm>
