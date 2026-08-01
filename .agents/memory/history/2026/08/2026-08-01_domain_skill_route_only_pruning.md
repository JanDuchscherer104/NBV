---
id: 2026-08-01_domain_skill_route_only_pruning
date: 2026-08-01
title: "Domain Skill Route-Only Pruning"
status: done
topics: [scaffold, skills, progressive-disclosure, ownership]
confidence: high
canonical_updates_needed:
  - .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
files_touched:
  - .agents/skills/
  - .agents/references/source_order.md
  - AGENTS.md
  - scripts/scaffold_audit.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
---

# Task

Apply the human-owner follow-up to the domain-skill distillation: remove the
nine retained route-only domain skills after review showed they no longer
earned independent procedural ownership.

# Method

- Rechecked every skill consumer and each nearest package or documentation
  owner before deletion.
- Confirmed that data handling, rollouts, RRI, Rerun, geometry, and docs already
  own their commands, contracts, and focused verification.
- Removed the temporary dual-schema audit branch that existed only for these
  nine skills and changed routing fixtures to require owner-first routing.
- Updated live Agents DB references and peer-skill handoffs to target nearest
  owners instead of deleted routers.
- Graphify freshness returned exit 1, so all ownership decisions used exact
  repository sources rather than stale graph evidence.

# Findings

The nine skills had useful activation labels but no remaining unique workflow,
state machine, or tool integration. Keeping them added another prose layer
between a task and its authoritative owner. Repository structure plus
`agent-behavior`, `aria-nbv-context`, root or nested `AGENTS.md`, module README
files, docstrings, CLI help, and tests preserve the required routing and
completion evidence without a domain-skill registry.

# Verification

- `make scaffold-audit` passed with 11 remaining skills and no errors;
  `make scaffold-audit-self-test` passed 15 negative probes and all 5 G002
  governance tests.
- `make check-agent-memory`, Agents DB validation, glossary generation, and
  `git diff --check` passed.
- Three read-only Codex route probes covered all nine retired lanes and reached
  exact package/docs owners with `missing_capability: false`.
- `make ci` passed, including 266 package smoke tests, 112 focused package
  tests, 42 Graphify projection tests, and the 33-page core docs render.
- Independent uncommitted-diff review reported no routing or ownership
  regression; its sandbox-only pytest attempt lacked a writable temporary
  directory, while the same tests passed in the main verification run.

# Canonical-State Impact

The accepted target-state specification records the explicit route-only
supersession. No scientific or implementation truth moved into agent memory.
