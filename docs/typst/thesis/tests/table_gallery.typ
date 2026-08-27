// Synthetic table-style gallery. This is a visual contract, not evidence.
#import "../../shared/tables.typ": *

#set page(margin: 1.4cm)
#set text(font: "New Computer Modern", size: 9pt)

= Table style gallery

The examples below exercise the shared table vocabulary with synthetic values.
They demonstrate grouped rows, grouped columns, and two-dimensional indices.

== Paired-policy scorecard

#figure(
  publication-table(
    columns: (0.62fr, 0.68fr, 0.72fr, 0.58fr, 0.58fr, 0.5fr, 0.5fr, 0.55fr),
    header-rows: 2,
    header: (
      table.cell(rowspan: 2)[*Profile*],
      table.cell(rowspan: 2)[*Target*],
      table.cell(rowspan: 2)[*Policy*],
      table.cell(colspan: 2)[*Endpoint*],
      table.cell(colspan: 2)[*Support*],
      table.cell(colspan: 1)[*Systems*],
      [*Gain*], [*Recovered*], [*$n$*], [*Valid*], [*ms*],
    ),
    rows: (
      group-header([Core], rowspan: 4),
      index-cell([Near], rowspan: 2), index-cell([Greedy]), [0.42], [--], [48], [0.96], [12.4],
      index-cell([Lookahead]), [0.51], [1.00], [48], [0.94], [18.7],
      index-cell([Far], rowspan: 2), index-cell([Greedy]), [0.31], [--], [36], [0.89], [11.8],
      index-cell([Learned]), [0.39], [0.64], [36], [0.87], [13.1],
    ),
    align: (left, left, left, right, right, right, right, right),
    text-size: 7.6pt,
  ),
  caption: [Synthetic scorecard with profile, target-stratum, and policy row indices plus grouped endpoint, support, and systems columns.],
) <tab:gallery-scorecard>

== Profile-by-metric matrix

#figure(
  publication-table(
    columns: (0.85fr, 1fr, 0.72fr, 0.72fr, 0.72fr, 0.72fr),
    header-rows: 2,
    header: (
      table.cell(rowspan: 2)[*Family*],
      table.cell(rowspan: 2)[*Measure*],
      table.cell(colspan: 2)[*Compact profile*],
      table.cell(colspan: 2)[*Detailed profile*],
      [*Estimate*], [*Denom.*], [*Estimate*], [*Denom.*],
    ),
    rows: (
      group-header([Quality], rowspan: 2), index-cell([Endpoint gain]), [0.42], [48], [0.51], [48],
      index-cell([Coverage]), [0.74], [48], [0.79], [48],
      group-header([Cost], rowspan: 2), index-cell([Latency (ms)]), [12.4], [96], [18.1], [96],
      index-cell([Memory (GB)]), [2.8], [8], [4.1], [8],
    ),
    align: (left, left, right, right, right, right),
  ),
  caption: [Synthetic metric-family matrix with profile-specific estimate and denominator column indices.],
) <tab:gallery-profile-matrix>

== Evidence ledger

#figure(
  development-table(
    columns: (0.9fr, 1.15fr, 1.1fr, 1.45fr),
    header: ([*Domain*], [*Indexed check*], [*Readout*], [*Inference boundary*]),
    rows: (
      group-header([Population], rowspan: 2), index-cell([Scene split]), [stable], [Held-out scenes only],
      index-cell([Target support]), [42 / 48], [Admitted targets only],
      group-header([Policy], rowspan: 2), index-cell([Paired budget]), [matched], [Same candidates and horizon],
      index-cell([Uncertainty]), [pending], [No confirmatory claim],
    ),
  ),
  caption: [Synthetic development ledger showing the development-only palette.],
) <tab:gallery-ledger>

== Parameter decision matrix

#figure(
  publication-table(
    columns: (0.7fr, 0.82fr, 1fr, 0.9fr, 0.62fr, 1.2fr),
    align: (left, left, left, right, left, left),
    header: ([*Profile*], [*Family*], [*Key*], [*Typed value*], [*Unit*], [*Decision use*]),
    rows: (
      group-header([Core], rowspan: 4),
      index-cell([Acquisition], rowspan: 2), index-cell([candidate-count]), [`16`], [views], [Fix comparison support],
      index-cell([horizon]), [`2`], [steps], [Fix endpoint budget],
      index-cell([Representation], rowspan: 2), index-cell([voxel-size]), [`0.08`], [m], [Control spatial resolution],
      index-cell([feature-width]), [`64`], [channels], [Control model capacity],
    ),
    text-size: 7.8pt,
  ),
  caption: [Synthetic profile, parameter-family, and key index with typed values, units, and decision use.],
) <tab:gallery-parameter-matrix>
