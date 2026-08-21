---
id: 2026-08-21_streamlit_app_guidance_install
date: 2026-08-21
title: "Install global Streamlit skill and add app guidance"
status: done
topics: [streamlit, agent-guidance, app-architecture, progressive-disclosure]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/app/AGENTS.md
  - aria_nbv/aria_nbv/app/README.md
artifacts:
  - .omx/specs/autoresearch-streamlit-guidance/report.md
---

## Outcome

- Installed Streamlit's official global `developing-with-streamlit` meta-skill
  through the 1.58 CLI without changing ARIA-NBV's Streamlit dependency.
- Added the nearest app guidance owner for architecture, cache/laziness,
  progressive disclosure, scientific presentation, and verification rules.
- Added a human README for launch, navigation, troubleshooting, tests, and page
  extension.

## Verification

- The global discovery script resolved the Streamlit 1.57 skill bundled in the
  ARIA-NBV environment.
- The project still resolves Streamlit 1.57.0 and imports `aria_nbv` from the
  active split-repair worktree.
- `make check-agent-memory` validates both new guidance owners and this debrief.

## Scope

No Python, dependency, schema, generation, or persisted-data behavior changed.
The guidance points to existing owners instead of duplicating their contracts.
