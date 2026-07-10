# Architect Review: Archive RL and Interpretability

VERDICT: APPROVE

Architectural Status: CLEAR

Summary:
- The revised plan is architecturally sound for Critic review.
- It covers the real active surfaces that must be removed or retargeted before `aria_nbv/aria_nbv/rl` and `aria_nbv/aria_nbv/interpretability` can be archived.
- The `scripts/quartodoc_expand_config.py` exclusions are correctly treated as deferred docs metadata rather than a blocking runtime edge.

Key findings:
- The active Streamlit surface is fully accounted for: `app/config.py`, `app/app.py`, `app/panels.py`, `app/panels/__init__.py`, `app/panels/rl.py`, and `app/panels/testing_attribution.py`.
- The test surface is fully accounted for: `test_config_field_constraints.py`, `test_counterfactual_rollouts_panel.py`, `test_panels_dispatcher.py`, module-specific RL and interpretability tests, and `test_rl_panel.py`.
- `streamlit_app.py` is not an additional blocking edge because it only forwards to `NbvStreamlitAppConfig` and the app launcher.
- `scripts/quartodoc_expand_config.py` becomes stale after archival, but it is docs-generator metadata, not an active import edge.

Antithesis:
- The Quartodoc exclusions could be removed in the same slice to avoid stale metadata.

Tradeoff:
- Keeping the archive plan narrow reduces churn and avoids mixing low-risk docs-generator cleanup into the critical active-surface removal path.

Synthesis:
- Proceed with the archive plan as written.
- Treat `scripts/quartodoc_expand_config.py` as a deferred follow-up unless the execution lane is already doing API-doc generator cleanup.

Agent:
- `019f4668-0037-7ee2-8f08-8b23cb691529`
