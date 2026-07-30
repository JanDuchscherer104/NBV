---
name: simplification
description: Use for ARIA-NBV behavior-preserving pruning of redundancy, dead code, stale compatibility, unused config, or excess LOC.
metadata:
  mode: implementation
  not_when:
    - "behavior is intended to change"
    - "ownership is unclear and needs a high-impact decision first"
    - "the task is only general surgical-edit discipline"
  handoff_to:
    - "plan-grill for unclear ownership or high-impact cleanup choices"
    - "agent-behavior for general surgical-edit discipline"
    - "agents-db when cleanup materially changes active debt"
  evidence_required:
    - "current contract and baseline verification for touched surface"
    - "usage or redundancy evidence before pruning"
    - "focused verification after the cut"
  applies_to:
    - "aria_nbv/**"
    - ".agents/**"
    - "docs/**"
  triggers:
    - "simplify"
    - "prune"
    - "dead code"
    - "ruthless simplification"
  must_read:
    - "AGENTS.md"
    - ".agents/skills/agent-behavior/SKILL.md"
    - ".agents/skills/simplification/references/redundancy-discovery.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#capture-rule"
    - ".agents/skills/README.md#style-rules"
    - ".agents/skills/simplification/references/redundancy-discovery.md"
    - ".agents/skills/simplification/references/tool-decision-tree.md"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.analyze_python_file"
    - "mcp__MCP_DOCKER.get_package_metrics"
    - "mcp__MCP_DOCKER.get_extraction_guidance"
  verification:
    - "focused tests for the changed surface"
    - "ruff format <file> and ruff check <file> for Python changes"
    - "make loc when LOC reduction is part of the goal"
---

# Simplification

Use this skill for behavior-preserving pruning of the current intended surface.

## Modes

- Default simplification: reduce redundancy, stale surface, and unnecessary
  indirection while preserving intended behavior.
- Ruthless simplification: only when explicitly requested. Read
  `references/ruthless.md` before planning or editing.

## Workflow

1. Establish the current contract and baseline verification.
2. Use focused `rg`, narrow reads, and `references/redundancy-discovery.md` to
   find actual overlap or dead surface.
3. Choose the smallest behavior-preserving cut.
4. Prefer deleting, merging, or inlining over adding new abstraction.
5. Validate with focused tests and formatting/lint checks for the touched
   surface.
6. Record durable debt only when the cleanup materially changes active debt.

## Rules

- Prefer deletion over abstraction.
- Prefer inlining over helper extraction for single-use or forwarding helpers.
- Keep one canonical owner per semantic concept.
- Do not widen APIs or add compatibility scaffolding unless explicitly asked.
- Do not preserve stale wrappers, deprecated import paths, or no-op config
  flags unless they are active public contracts named by the task.
- Move genuinely shared behavior to the canonical shared owner instead of
  leaving quasi-shared helpers in leaf modules.
- Treat analyzer output as advisory; repo ownership and tests decide.
- For optional upstream architecture cleanup prompts, see
  `references/upstream-mattpocock.md`; use them as questions, not authority.

## Tooling

- Use `rg` first for local checks.
- Use code-index or analyzer tools only after the candidate surface is broader
  than a quick local search.
- See `references/tool-decision-tree.md` for the optional analyzer workflow.

## Verification

- Focused tests for the changed surface.
- `ruff format <file>` and `ruff check <file>` for Python changes.
- `make loc` before and after when LOC reduction is part of the decision.
- `make ci` before commit when the change is broad.
