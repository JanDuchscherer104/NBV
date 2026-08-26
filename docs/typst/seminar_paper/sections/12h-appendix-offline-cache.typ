#import "../../shared/tables.typ": publication-table

= VIN offline store and batching

#let cache = json("/typst/shared/data/vin_offline_store_stats.json").vin_offline_store
#let s = cache.sample_sizes_mb

This appendix summarizes why we materialize oracle outputs, what is stored, and the
approximate storage footprint per snippet and for the full ASE mesh subset.

== Motivation

// <rm>
// Qualitative/unstated runtime + memory claims. Replace with measured numbers (sec/candidate,
// sec/snippet, GPU mem) and a cache-throughput table in main text + appendix.
The oracle pipeline combines candidate sampling, depth rendering, backprojection,
and point-to-mesh scoring. Each step is GPU-heavy and hard to parallelize inside
PyTorch. In practice, this results in per-snippet runtimes on the order of tens
of seconds, while the EVL backbone alone can consume multiple GB of GPU memory
per forward pass and hence limits us to batch sizes of one. The immutable VIN offline store makes training a standard supervised learning problem
and enables larger batch sizes for noisy ordinal supervision.
// </rm>


== Storage footprint

Let $S_"cur"$ denote the size of the cached subset and $f_"cover"$ the
scene coverage fraction. We estimate the full-coverage size as:

$ S_"full" approx S_"cur" / f_"cover" $.

For the current materialized subset we observe:

- $S_"cur" = #cache.samples_size_gb$ GB for materialized oracle/backbone payloads.
- $S_"vin" = #cache.vin_snippet_cache_gb$ GB for minimal VIN snippet tensors.
- $S_"full" approx #cache.full_coverage_total_gb$ GB for 100 mesh scenes.

#figure(
  kind: "table",
  supplement: [Table],
  caption: [Representative per-snippet tensor footprint (CPU, float32).],
  [
    #let rows = (
      ([backbone_out], [#s.backbone MB]),
      ([candidate_pcs], [#s.candidate_pcs MB]),
      ([depths], [#s.depths MB]),
      ([candidates], [#s.candidates MB]),
      ([rri], [#s.rri MB]),
      ([vin_snippet], [#s.vin_snippet MB]),
      ([total + backbone], [#s.total_with_backbone MB]),
      ([min train payload], [#s.total_min_train MB]),
    )
    #publication-table(
      columns: (16em, auto),
      header: ([Field], [MB]),
      align: (left, left),
      rows: rows.flatten(),
    )
  ],
)

== Minimal training payload

The bare minimum for VIN training (with cached candidates) is:

- Candidate poses and PyTorch3D camera parameters.
- Oracle targets (RRI + point-to-mesh components).
- `VinSnippetView` (semi-dense points, lengths, trajectory).

This minimal payload is approximately #s.total_min_train MB per snippet in the
current configuration. Caching the full EVL backbone output adds ~#s.backbone MB
per snippet, dominating storage when enabled.
