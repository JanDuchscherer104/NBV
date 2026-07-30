---
id: 2026-07-30_mermaid_skill_local_tool_seam
date: 2026-07-30
title: "Mermaid skill local-tool seam"
status: done
topics: [skills, mermaid, tooling, documentation]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/aria-nbv-mermaid/SKILL.md
  - .agents/skills/typst-authoring/references/figures-tables.md
  - .agents/skills/typst-authoring/issues.md
  - tools/mermaid/scripts
---

## Task

Tighten the ARIA-NBV Mermaid skill around the repository-local tool seam.

## Method

Reviewed skill guidance, the local Mermaid lint/render scripts, templates, and
Typst-authoring guidance; then removed the duplicate renderer wrapper.

## Findings

- `aria-nbv-mermaid` now owns only the versioned source-to-local-tool seam and
  hands notation, inclusion, and diagnosed failures to their established skills.
- `tools/mermaid/scripts/render_mermaid.sh` is the sole repository Mermaid CLI
  wrapper; it resolves a repository-local CLI before explicit environment or
  `PATH` installations, and the duplicated Typst-authoring helper was removed.
- `make mmdc-render` and the linter's `--render` mode both delegate to that
  wrapper, retaining the batch target's scale option.
- Typst figure guidance now invokes that canonical local wrapper.

## Verification

- `python tools/mermaid/scripts/aria_mermaid_lint.py` passed for both local
  templates before the guidance change.
- The local skill validator, `python3 scripts/scaffold_audit.py`,
  `make check-agent-memory`, and `git diff --check` passed.
- Rendering was intentionally skipped: the canonical wrapper returned `127`
  because no repository-local, environment-selected, or `PATH` `mmdc` exists
  on this machine. Its resolution order was independently smoke-tested.

## Canonical State Impact

No `.agents/memory/state` update is needed. The durable workflow owner is the
Mermaid skill and its existing `tools/mermaid` seam.
