---
id: 2026-08-30_candidate_family_preflight_wp02
date: 2026-08-30
title: "WP02 Candidate-Family Preflight and Phase-A Gate"
status: done
topics: [candidate-generation, rollouts, preflight, phase-a, evidence]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/candidate_benchmark.py
  - aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py
  - aria_nbv/aria_nbv/rollouts/info_cli.py
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/pipelines/cli.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
  - docs/contents/evidence/candidate_family_phase_a_wp02.json
codex_thread: codex://threads/01a05281-f9f7-7f80-967e-4000d77aca81
repo_object_format: sha1
repo_head: fcecdf5f2da0afd9aa25dae717f4ec52fefe0c6e
repo_branch: "codex/candidate-family-preflight"
worktree_kind: linked
---

# WP02 candidate-family preflight and Phase-A gate

## Task and method

WP02 froze one presentation-free candidate-family reducer for rollout-store
preflight, campaign admission, plotting, and Streamlit. It separates the
resolved root floor from the versioned family floor and treats Phase A as
incapable of establishing flat target-root gain without reward labels. The
existing campaign preflight command was extended to generate candidate shells
directly from the reviewed 100-scene source manifest without constructing a
scorer, renderer, replay policy, or reward label. This is a no-render,
no-reward-label proposal-support audit with privileged GT target instruction
and mesh validity, not an oracle-free path.

## Findings

The exact-head run used the reviewed source store
`vin_offline_rollout_campaign100_v10_rebuilt` and covered 100 source rows, 100
scenes, and 100 target states without exclusions. It attempted 6,000 candidates
and admitted 3,146 rows to compact valid shells. The result is a no-go with 76
typed blockers: 44 applicable-family collapses, 24 low non-forward
target-family-support failures, and 8 low-root-support failures. `flat_gain` is
unavailable with denominator zero. Broad rollout generation remains blocked
both by this failed gate and by the independent WP18 requirement. The fail-closed
mechanism and bounded evidence checklist requested by issue #54 are complete;
sampler remediation remains a separate later work package.

The compact canonical JSON has artifact SHA-256
`6d33e9e3d68737c8a6a5589ae5117c1e4d7fcaa89056fcfcaec1d315e4509c83`
and file SHA-256
`843d1e6c41df7746db1187a92eb7b29f9f18263bb33cbb5e3b4efc9f1acea017`.
It records execution revision
`2baf7cf6b276b81c50d01d45b152016d7cf68033`, generation revision
`a2ae86b7463930c9`, source-manifest file SHA-256
`d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56`,
native source-store manifest identity `605453ba11869e40`, writer configuration
SHA-256 `4ae05a1e4066756a47f9ba00d914b8f4337321ae8dcd161a62228d02f71d0587`,
and the Python 3.11.15, PyTorch 2.4.1/CUDA 12.1, PyTorch3D 0.7.9,
RTX 3080 Ti runtime identity.

The first compact serialization exposed that source-sample decoding mutates
the process-global path singleton. The writer-config identity is therefore
captured before source setup and iteration. The evidence above preserves the
unchanged 100 generated candidate shells while replacing only that provenance
field and its enclosing content hash with the independently reproducible,
path-independent scientific writer identity. Artifact correction revision
`phase-a-path-independent-config-reseal-v1` records this authenticated reseal;
no candidate generation, rendering, scoring, or GPU population was rerun.
The v4 evidence envelope names assembly revision
`phase-a-evidence-assembly-v1`, transformation
`authenticated_metadata_reseal_no_candidate_rerun`, and predecessor artifact
`6c7fa8cb249687b80867261db1d1c7d1906e6b01f54d3cca3db4bfcbfa7bc670`.
The exact 100-record payload retained SHA-256
`637f9747d3125a8e746866d18843f2ca6aa84e50bcc2c75b5532a49b15690f6f`.

Final PR review found that those candidate centres, target-relative vectors,
and view directions were still serialized in rig/reference axes despite their
target-forward and target-lateral labels. The canonical source reader joined
the same 100 authenticated records to their factual final rig rotations and
rotated only those vectors into the existing target-aligned world-Z-up basis.
Transformation `authenticated_target_frame_correction_no_candidate_rerun`,
geometry revision `phase-a-target-aligned-z-up-v1`, and predecessor artifact
`60b271db515a5e665fcb7bbeeecb87e6acb4bac2ff8e28b26b7308911328759c`
record the correction. No candidate generation or GPU population was rerun;
the preflight payload, 76 blockers, support counts, and no-go verdict remain
byte-identical. The corrected 100-record payload SHA-256 is
`43a4fbba2e412c6a7d4b9a0c2a8b6f3d064dde4d9387566ea29f077365447c89`.

The same review found that paired-view rows retained `gaze_variant_id` in the
canonical rollout store but the reader decoded only the base mixture ID. The
reader now combines manifest-owned component configuration with persisted gaze
variant provenance, preserving base and `__paired_<mode>` family identities;
legacy ambiguity fails closed.

Final review repair also made the campaign worker leaf admit the immutable plan
and explicit purpose before any runner or path effect, recomputes generation
revision identity from its constituents, rejects unconfigured families before
root-support aggregation, streams complete preflight without geometry, and
keeps Plotly event decoding in the app adapter. A heatmap selection explicitly
loads only the selected identity-bound shell and caches it across ordinary
reruns; the default interactive funnel is limited to one factual state per
persisted audit stratum while the complete evidence figures remain available.

## Issue #54 acceptance

- Threshold formula, persistence, state/family applicability matrix, typed
  family failures, state-conditional no-reward-label flat-gain semantics, and focused tests are
  evidenced.
- The required all-100-scene Phase-A run is evidenced and fails closed with an
  exact blocker taxonomy.
- These two points complete issue #54's mechanism and bounded evidence
  checklist. The sampler-pass criterion is not met; remediation and a passing
  rerun remain `todo-088`, not a reason to keep the completed mechanism open.
- No external issue state was changed in this lane. The publishing owner may
  use `Closes #54` only after the final PR-level verification.

## Verification

- Broad campaign/family/info/panel/cache/source-adapter suite: 370 passed.
- Reporting and Zarr integration suite: 68 passed.
- CLI dispatch suite: 21 passed; 2 unrelated config-resolution tests were
  deselected because this linked worktree does not contain `.data/ase_efm`.
- Strict focused mypy: five changed Python owners passed.
- Ruff check/format, Agents-DB validation, agent-memory validation, thesis
  compilation, and `git diff --check` passed.
- Exact 100-scene command exited 2 after atomically writing the complete no-go
  artifact. The full heatmap and audit-stratum funnel views were reconstructed
  through the dedicated reader and plotting helper; their SVG SHA-256 values are
  `8fe696aa01ac79da23ed2bd032e310153b5b58dff747708b00f1da1b2c5f3cb7`
  and `dd9cf0a27a5fe1d63ed450d7b320f724e2d74cd07e99aadf76cc1737f749d0f0`.
  The legible one-scene-per-stratum thesis projection has SVG SHA-256
  `e53e84969bdf58ccc19c0c46f3b6e447ad1bdb27df2b84f5b83e2789a6e97f99`.

## Canonical impact

The preflight interface, typed blocker taxonomy, Phase-A adapter, and thin UI
consumer are current implementation owners. The empirical artifact records a
failed unchanged control and must not be cited as a passing support gate, an
RRI result, or permission for broad generation.

## Commits

- [Fail-closed family admission repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/cf9e44d468fb9688872f772544b7bd4aeb7d8fdb)
- [Frozen campaign execution head](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2baf7cf6b276b81c50d01d45b152016d7cf68033)
- [Canonical reader order repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/801dbae07f)
- [Pre-read writer-config identity repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/59a5d72413cc7d39744be08e05baec4ba6491afa)
- [Final trust-boundary repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d138fe72cc)
- [Path-independent evidence reseal](https://github.com/JanDuchscherer104/ARIA-NBV/commit/18e1970d84)
- Final admission and evidence seam repair: `c0f7a1abea17e87d8a1a2c610db3dad0328c86c4`.
- Self-describing v4 metadata reseal: `103c44a5299734df11a2f0a772a060972bb54a50`.
- Presentation-free streaming preflight: `fcecdf5f2da0afd9aa25dae717f4ec52fefe0c6e`.
