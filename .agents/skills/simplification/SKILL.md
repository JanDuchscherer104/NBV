---
name: simplification
description: Use for ARIA-NBV behavior-preserving pruning of redundancy, dead code, stale compatibility, unused config, or excess LOC.
---

# Simplification

Use this skill for behavior-preserving pruning of the current intended surface.

## Modes

- Default simplification: reduce redundancy, stale surface, and unnecessary
  indirection while preserving intended behavior.
- Ruthless simplification: only when explicitly requested. Read
  [`references/ruthless.md`](references/ruthless.md) before planning or editing.

## Workflow

1. Establish the current contract and baseline verification.
2. Use focused `rg`, narrow reads, and
   [redundancy discovery](./references/redundancy-discovery.md) to find actual
   overlap or dead surface.
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
- For optional upstream architecture cleanup prompts, read
  [`references/upstream-mattpocock.md`](references/upstream-mattpocock.md); use
  them as questions, not authority.

## Tooling

- Use `rg` first for local checks.
- Use indexed search or analyzers only after the candidate surface is broader
  than a quick local search; choose the smallest available operation described
  in [the tool decision tree](./references/tool-decision-tree.md).
- For current external dependency API or version uncertainty, route through
  [`aria-nbv-context`](../aria-nbv-context/SKILL.md) and its
  [`Context7 registry`](../aria-nbv-context/references/context7_library_ids.md)
  before treating upstream behavior as a cleanup target.

## Verification

- Focused tests for the changed surface.
- `ruff format <file>` and `ruff check <file>` for Python changes.
- `make loc` before and after when LOC reduction is part of the decision.
- `make ci` before commit when the change is broad.
