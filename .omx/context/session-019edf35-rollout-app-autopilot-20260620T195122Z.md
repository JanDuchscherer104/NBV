# Autopilot Context: Session 019edf35 Rollout App Alignment

## Activation Prompt / Task Seed

User invoked `$oh-my-codex:autopilot` and asked to continue from the latest
repo transcripts under `.agents/memory/transcripts` plus all goals agreed in
Codex session `019edf35-6ede-7ab1-907a-44fb067d5221`.

## Original Task Status

activation-prompt

The checked-in transcript export currently stops at 2026-06-18. The active
session source for this task is:

`/home/jd/.codex/sessions/2026/06/19/rollout-2026-06-19T11-28-01-019edf35-6ede-7ab1-907a-44fb067d5221.jsonl`

The transcript export is background evidence, not the current source of truth
for the 2026-06-20 rollout-app goals.

## Desired Outcome

Deliver a reviewed, QA-checked implementation that makes iterative
counterfactual rollout generation and stored rollout-Zarr inspection first
class in the ARIA-NBV Streamlit/Rerun workflow.

The implementation must:

- make the existing counterfactual rollout page the central live configuration,
  generation, and inspection surface;
- add or wire a first-class stored rollout-Zarr inspection page in the app;
- expose qualitative and quantitative verification plots for generated/stored
  rollouts using the repo's Plotly/builder patterns;
- expose Rerun commands for selected rollout rows/samples;
- remove the untracked external `aria_nbv/scripts/plot_rollout_validation.py`
  detour;
- avoid Matplotlib for this rollout validation/app path.

## Known Facts / Evidence

- `.agents/memory/transcripts` latest checked-in exports are 2026-06-18 files.
- Current session log contains the active user goals:
  - build one rollout sample at a time, inspect schema validity, geometry,
    target selection, reward/invalidity metadata, and Rerun inspectability;
  - improve bad validation plots with more candidates, projected GT/pred OBBs,
    objective curves, branching, and sampling-rule visualization;
  - make `_page_counterfactual_rollouts` first class for live configuration,
    multi-step generation, and on-the-fly inspection;
  - add a detailed rollout-Zarr dataset inspection page;
  - use no Matplotlib and stick to `aria_nbv` plotting utilities, Plotly, and
    builder patterns.
- Best-practice research in the same session concluded:
  - use Streamlit `st.plotly_chart`, Plotly figures, existing
    `aria_nbv.pose_generation.plotting` builders, and Rerun;
  - do not build an external one-off plotting script;
  - Rerun is the dense 3D/time-series inspector, not a replacement for
    app-native dataset QA.
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py` already exists and renders
  persisted rollout-Zarr validation, summaries, Plotly QA dashboards, candidate
  audit rows, and Rerun launch commands.
- `aria_nbv/aria_nbv/app/app.py` currently has a Counterfactual Rollouts page
  but does not include a Stored Rollout Zarr page.
- `aria_nbv/aria_nbv/app/panels/__init__.py` currently exports
  `render_stored_rollouts_panel`; the compatibility dispatcher
  `aria_nbv/aria_nbv/app/panels.py` does not.
- `aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py` already logs rollout
  scalar series, branch series, selected candidate probability, target/scene
  RRI, invalid fraction, candidate metadata, and matched GT target OBBs.
- The worktree is already heavily dirty. Preserve unrelated user/agent changes.

## Constraints

- Follow Autopilot phase order:
  `deep-interview -> ralplan -> ultragoal -> code-review -> ultraqa`.
- Do not self-attest consensus, review, or QA gates; use durable artifacts and
  native subagent evidence where required.
- Keep changes narrow and request-traceable.
- No Matplotlib in the rollout validation/app inspection path.
- Reuse existing `aria_nbv` Plotly/builder and Rerun surfaces before adding new
  helpers.
- Do not train `Q_H` as part of this app/inspection alignment pass.
- Do not make thesis/scaffold restructuring part of this delivery unless a
  small docs update is required by changed behavior.

## Unknowns / Open Questions

- Whether existing fixture stores contain all fields needed for objective
  curves and branching plots; the implementation should degrade with clear
  warnings when older stores lack fields.
- Whether projected predicted OBB overlays are already persisted in stored
  rollout stores; if not, this pass should expose what is available and keep
  deeper persistence changes as a follow-up.
- Whether full app screenshot QA can run locally after the implementation;
  if not, use import tests plus targeted panel/helper tests.

## Likely Codebase Touchpoints

- `aria_nbv/aria_nbv/app/app.py`
- `aria_nbv/aria_nbv/app/panels/__init__.py`
- `aria_nbv/aria_nbv/app/panels.py`
- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/aria_nbv/pose_generation/plotting.py`
- `aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py`
- `aria_nbv/tests/app/**`
- `aria_nbv/tests/rollouts/test_inspection.py`
- `aria_nbv/tests/rerun_inspector/test_rollout_zarr_logger.py`

## Scope Note

This snapshot is the Autopilot activation context. It distills the latest
session goals and local evidence; it is not a guarantee that every prior
conversation artifact has been revalidated.
