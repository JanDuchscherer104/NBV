# Ralplan architect review 1

- Reviewer role: architect
- Verdict: REVISE
- Date: 2026-07-13

Required revisions:

1. Treat the existing Autoresearch goal as authoritative; use only an App-safe Ultragoal artifact ledger while it is active.
2. Add a trivial C-ABI build/link/wheel/clean-runtime gate before real kernels.
3. Co-locate each Mojo source with its PyTorch3D CPU/CUDA operator.
4. Make Torch build matching and the Darwin/Clang-26 compatibility flag deterministic.
5. Specify the exact ARIA raster contract and a near-plane-clipped-neighbor parity case.
6. Define eligibility and per-operator provenance; real-data evidence remains required; add numeric performance thresholds.

Disposition: all six requirements incorporated into the PRD and test plan before re-review.
