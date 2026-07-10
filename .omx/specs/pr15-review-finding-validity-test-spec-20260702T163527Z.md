# Test Spec: PR15 Review Finding Implementation

Scope: Verification expected if the accepted PR15 review findings are implemented on the actual PR15 branch/head.

Preconditions:
- Work from a clean PR15 worktree whose `HEAD` equals the current GitHub PR #15 head or a deliberate descendant.
- Preserve unrelated local work in `/home/jd/repos/ARIA-NBV`.
- Capture baseline `git rev-parse HEAD`, `git status --short`, and `gh pr view 15 --json headRefOid,statusCheckRollup`.

Required regression tests:
- Diagnostics checkpoint loading:
  - checkpoint with sentinel parameter is loaded by `render_vin_diagnostics_page()` composition path or its testable helper;
  - missing/corrupt checkpoint stops diagnostics instead of warning and continuing with random weights.
- Inference binner lifecycle:
  - embedded checkpoint binner wins;
  - missing configured binner path can fall back to provided fallback path;
  - corrupt configured binner raises an actionable corruption error;
  - repeated `prepare_for_inference()` does not overwrite trained CORAL bin values or biases;
  - chosen legacy-checkpoint policy is covered.
- Table metric aggregation:
  - two batches with unequal candidate counts but one table each contribute equal table weight;
  - top-k comparable and selected-action non-comparable masks are counted independently;
  - selected-action comparable and top-k non-comparable masks are counted independently;
  - valid-table rate is `valid_tables / all_tables`;
  - empty comparability yields NaN value metrics without corrupting subsequent updates.
- Forward graph/device stability:
  - parameter names/ids are unchanged before and after first forward;
  - optimizer parameter ids cover every trainable parameter;
  - forward path never calls `nn.Module.to`;
  - cached and online evidence paths use the same normalized scorer input contract or online path is explicitly prepared outside the scorer.
- Public API contraction:
  - `aria_nbv.vin`, `aria_nbv.vin.models`, and `aria_nbv.vin.types` expose only supported runtime contracts;
  - no public scorer/config constructor deliberately raises `NotImplementedError`;
  - the zero-descriptor myopic wrapper, if removed, has a tested replacement preset or compatibility alias for existing TOML/checkpoint expectations;
  - config unions no longer parse unsupported runtime scaffolds unless intentionally moved to non-runtime proposal/docs surfaces.
- Diagnostics correlations:
  - Pearson/Spearman require matching flattened shapes;
  - finite mask is joint (`isfinite(x) & isfinite(y)`);
  - NaNs at different indices do not pair unrelated values;
  - tie behavior is either tie-aware or explicitly documented and tested.
- Scene-field semantics:
  - exactly one canonical builder/mode owns V3 scene-field evidence semantics;
  - parity test proves the active soft-count semantics are unchanged.
- Semidense aliases:
  - one canonical semidense visibility field/key remains;
  - legacy payload conversion, if needed, happens at a serialization boundary and is tested.
- CI/config/docs:
  - Root Verification passes;
  - the observed agent-memory scaffold failure is fixed in the repo-contract lane;
  - required workflow visibly runs new VIN, checkpoint, diagnostics, and rollout metric test surfaces;
  - smoke rollout config name reflects one-sample smoke status;
  - PR body names current files, verification, limitations, and actual implemented scope.

Targeted command families:
- `make ci PYTHON_INTERPRETER=python`.
- `cd aria_nbv && uv run ruff format --check <touched files>`.
- `cd aria_nbv && uv run ruff check <touched files>`.
- `cd aria_nbv && uv run pytest tests/vin tests/lightning tests/rri_metrics tests/rollouts -q` narrowed to touched tests during iteration.
- Offline binner and two-epoch smoke after correctness fixes.
- `make loc` before/after if cleanup still claims LOC reduction.

Acceptance:
- No accepted P0/P1 correctness finding remains reproducible.
- Deferred P2/P1 architecture cleanup is explicitly listed as follow-up, not silently ignored.
- Final PR head is aligned between local and GitHub and Root Verification is green.
