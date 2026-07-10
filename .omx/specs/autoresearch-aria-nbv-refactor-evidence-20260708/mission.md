# Mission

Gather current evidence and grounded refactor suggestions for ARIA-NBV module
architecture work, with recency-weighted use of persisted `.agents/work/**/*.md`
and `.omx` planning artifacts.

Focus areas:

- `data_handling` restructuring, especially target-selection ownership.
- Oracle RRI pipeline unification, with pipeline orchestration owned by
  `aria_nbv/aria_nbv/pipelines` rather than scattered across package roots.
- Quarantine or archive of the current `aria_nbv/aria_nbv/rl` surface if it is
  not part of the immediate thesis core.

Validation mode: `prompt-architect-artifact`.

Validator prompt: Review whether the report grounds recommendations in recent
persisted plans and live code evidence, covers data-handling restructuring,
Oracle RRI pipeline unification under `aria_nbv.pipelines`, and `rl/` archive
guidance, and separates now/next/later refactors with scope risks.
