---
id: 2026-08-24_candidate_jitter_mvp_and_sampling_visualization
date: 2026-08-24
title: "Candidate jitter MVP and sampling visualization"
status: done
topics: [candidate-generation, view-jitter, streamlit, rollouts]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/candidate_generation.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - aria_nbv/aria_nbv/app/panels/candidates.py
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - .configs/build_rollouts_v1_realistic.toml
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: fff3416b1a618cf15c35f6e9f6931e515ff34bf7
repo_branch: "codex/candidate-mvp-01-jitter-vis"
worktree_kind: linked
---

## Task
Adopt the final seminar view-jitter support for production candidate mixtures and make the sampled support directly auditable in Streamlit.

## Method
Traced the mixture, orientation, rollout-config, live-app, visualization, test, and thesis owners. Replaced zero production mixture overrides with the existing symmetric 60-degree yaw and 30-degree pitch caps, rejected zero resolved mixture caps, retained per-row jitter provenance, and added a full-shell yaw--pitch support plot.

## Findings
The single-family generator already defaulted to the seminar caps, but mixture presets, rollout configurations, and the live target-aware rollout builder overrode them to zero. The mixture validator now makes that production failure explicit. `candidate_generation.py` retains sampled yaw/pitch, resolved caps, and a per-candidate bounded-support flag even when general debug collection is disabled, so `plotting.py` and the Candidates page can distinguish proposal support from downstream hard-rule rejection. Legacy zero-cap spherical samplers are marked uncapped and plotted on fixed spherical axes without a misleading zero-area box.

## Commits
- [1c4ecd9751bb0371098f7e9be8c29cbc61550336](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1c4ecd9751bb0371098f7e9be8c29cbc61550336)
- [6cde7ef77912fecde4c4277d31ce2cffee680721](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6cde7ef77912fecde4c4277d31ce2cffee680721)

## Candidate Owner Intent
<!-- Omit this section unless the agent-behavior candidate-intent branch applies. -->
- Statement: Production candidate mixtures must never resolve yaw or pitch view jitter to zero and must use the final seminar values.
- Evidence: Direct user instruction in the originating Codex thread on 2026-08-24.
- Scope and target owner: Production mixture validation and presets in `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py`, with rollout configurations and thesis method text synchronized.
- Status: proposed for current-user review

## Verification
- Ruff passed for all changed Python owners and tests.
- 23 focused pose-generation, plotting, and Candidates-panel tests passed.
- 93 counterfactual rollout and live-panel tests passed.
- 12 rollout-profile configuration tests passed; the attempted full campaign module was not a valid dirty-worktree check because campaign revision tests intentionally require a clean checkout.
- `typst compile typst/thesis/main.typ` and `make typst-authoring-contract` passed.
- The review regression suite passed 28 focused pose-generation, plotting, mixture, and Candidates-panel tests; it proves nonzero zero-cap spherical residuals remain visible on fixed yaw `[-180, 180]` and pitch `[-90, 90]` axes with no envelope rectangle.

## Canonical Owner Impact
Updated the exact candidate-mixture/generation owners, active rollout configs, live candidate-generation UI, plotting helper, contract tests, and active thesis method section. No further canonical updates are pending for this slice.
