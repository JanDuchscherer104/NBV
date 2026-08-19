---
id: 2026-08-14_cuda_campaign_generation_page
date: 2026-08-14
title: "CUDA Campaign Generation Page"
status: done
topics: [streamlit, campaign, cuda, rollout, verification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/app.py
  - aria_nbv/aria_nbv/app/panels/__init__.py
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
  - aria_nbv/tests/app/test_app_router.py
  - aria_nbv/tests/app/panels/test_campaign_generation_panel.py
  - aria_nbv/tests/test_panels_dispatcher.py
artifacts:
  - ".omx/plans/prd-cuda-rollout-campaign-generation.md"
---

## Task

Add the rich Streamlit Campaign Generation page as a separate G003 story. Keep
campaign semantics in the canonical rollout CLI and provide bounded controls
and focused verification without launching the broad rollout campaign.

## Method And Findings

Added a lazy `Campaign Generation` route under the Generation navigation group.
The page imports and renders its dedicated panel only when selected, and the
panel facade keeps the Streamlit implementation out of eager app imports.
Scientific campaign details are presented read-only from the reviewed CUDA
configuration: profiles, candidate/beam settings, strict-IoU policy, root
support gate, watchdogs, and the ordered recipe suite are not editable page
state.

All actions delegate to the canonical `nbv-rollout-campaign` CLI. The panel
builds explicit argv for preflight, plan, smoke, run, resume, and JSON status;
it does not duplicate campaign execution logic. Run and resume are gated on a
current passing one-target smoke, an available `tmux`, a safe named session,
and an absent campaign claim. Detached launches use shell-free argv, verify
the named session, and expose only bounded output. Existing claims and stale
or failed smoke evidence block launch. Status is read only after an explicit
refresh; cached summaries, events, and bounded tmux output are invalidated
when the selected plan changes.

The page keeps completed-artifact science in the existing Rollout Supervision
inspection surface. It does not add rich rollout inspection, a second campaign
engine, broad rollout execution, Rerun monitoring, schema changes, or external
GitHub writes.

## Verification

- Combined verification passed: 151 tests.
- Focused G003 verification passed: 38 tests covering lazy routing and
  dispatcher loading, canonical CLI delegation, shell-free tmux launch and
  claim/smoke gates, explicit status refresh, cache invalidation, read-only
  scientific summaries, and bounded action/log output.
- Ruff format, Ruff lint, and path-scoped diff checks were green.
- Independent verifier marked the result `VERIFIED`; independent code review
  marked it `APPROVE`.
- No broad rollout campaign was launched, and no push, pull request, issue, or
  other external GitHub write was performed.

## Canonical-State Impact

The six package and test paths above remain the canonical app routing, panel,
and verification owners. This story adds no durable current-truth update;
`canonical_updates_needed` is therefore empty. Rich completed-rollout
inspection remains owned by Rollout Supervision, while campaign generation
semantics remain owned by the rollout CLI and campaign core.
