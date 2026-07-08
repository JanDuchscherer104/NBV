# Upstream Matt Pocock Guidance For Simplification

Use this as reference-only inspiration from Matt `codebase-design`,
`improve-codebase-architecture`, and `writing-great-skills`.

Borrow:

- use module, interface, depth, seam, adapter, leverage, and locality vocabulary;
- apply the deletion test before adding abstractions;
- prefer deep modules over shallow forwarding layers;
- prune duplicated skill prose, no-ops, and sediment;
- use architecture scans as candidate generators, not as automatic refactor
  authority.

ARIA differences:

- `simplification` owns behavior-preserving pruning under ARIA source order.
- Durable thesis claims, formulas, package contracts, and future plans must move
  to canonical owners instead of staying in hot-path skills.
- ARIA verification decides whether a cut is safe.
