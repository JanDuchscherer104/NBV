---
name: diagnose-aria
description: Use to diagnose ARIA-NBV bugs, regressions, failing metrics, Streamlit issues, docs builds, KG failures, or suspicious outputs.
metadata:
  mode: diagnostic
  not_when:
    - "broad planning without a concrete symptom"
    - "pure source localization with no failure"
    - "reviewing concrete diffs rather than reproducing a symptom"
  handoff_to:
    - "external analysis workflow capability for domain-agnostic read-only causal ranking before mutation"
    - "plan-grill for broad planning without a concrete symptom"
    - "aria-nbv-context for localizing an unknown failure surface"
    - "code-review-aria-nbv for diff review"
    - "specialized contract skills after the failing surface is known"
  evidence_required:
    - "smallest reproducible failing loop or explicit reason none exists"
    - "exact command, traceback, metric, or bad output"
    - "passing loop after the fix"
  applies_to:
    - "**"
  triggers:
    - "bug"
    - "regression"
    - "failing test"
    - "suspicious metric"
  must_read:
    - "AGENTS.md"
    - ".agents/memory/state/GOTCHAS.md"
    - "nearest package AGENTS.md or diagnostic skill"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - "nearest package AGENTS.md or diagnostic skill"
    - ".agents/memory/state/GOTCHAS.md"
  context7_refs:
    - "/websites/streamlit_io"
    - "/pytorch/pytorch"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.browser_run_code"
    - "mcp__MCP_DOCKER.analyze_python_file"
    - "mcp__MCP_DOCKER.get_package_metrics"
  verification:
    - "the narrowest reproducer for the failing surface"
    - "focused regression test after fixes"
---

# Diagnose ARIA

## Role Split With OMX

OMX owns orchestration, autonomy, goals, loops, and handoffs. Use external
read-only causal ranking only when no concrete command, artifact, metric, or
runtime symptom is known yet.

`diagnose-aria` is the ARIA-NBV sidecar for existing symptoms: it picks the
local reproducer, inspection command, domain verification loop, expected signal,
and passing loop. Use `references/upstream-mattpocock.md` only as optional
generic debugging inspiration; ARIA repro and verification loops remain
authoritative.

## When To Use

Use this skill for hard bugs or regressions in:

- geometry, `PoseTW` / `CameraTW`, rendering, RRI, VIN, or rollout behavior
- immutable VIN offline stores, manifests, split files, or data smoke checks
- Streamlit panels, Quarto / Typst renders, KG ingestion, or CLI failures
- metric drift, calibration collapse, performance regressions, or flaky tests

## Local Command Toolbelt

Use the smallest tool that can reproduce or inspect the symptom.

- Streamlit entrypoint:
  `cd aria_nbv && uv run nbv-st --server.port <port>`
  The wrapper disables Streamlit file watching by default; pass
  `--server.fileWatcherType=<mode>` before `--` only when watcher behavior is
  the suspected issue.
- Streamlit smoke and panel tests:
  `cd aria_nbv && uv run pytest tests/test_streamlit_entry.py tests/app`
  Start with entrypoint or panel-specific tests before live UI inspection.
- Offline VIN store: `make offline-info`, `make offline-tree`,
  `make offline-samples`, and `make offline-sample-rerun-random`.
- Rollout store: `make rollouts-info`, `make rollouts-stats`, and
  `make rollouts-rerun-random`.
- Rerun inspector:
  `cd aria_nbv && uv run nbv-rerun-inspect ...`.
  Hand off to `rerun-nbv-inspector` for visual, frame-coordinate, depth/RGB,
  OBB, frustum, or `.rrd` entity-tree issues.
- Docs failures: `make qmd-frontmatter-check` and focused Quarto or Typst
  renders for the touched page.
- Package behavior:
  `cd aria_nbv && uv run pytest <focused-test>`, then targeted
  `cd aria_nbv && uv run ruff check <path>` only for touched Python surfaces.

## Feedback Loop First

Build the smallest deterministic loop that reproduces the user-visible symptom:

- package behavior: `cd aria_nbv && uv run pytest <focused-test>`
- CLI/data path: `cd aria_nbv && uv run nbv-summary --config-path <config>`
- immutable store: manifest/sample-index read plus
  `tests/data_handling/test_vin_offline_store.py`
- Streamlit panel: entrypoint or panel test before manual UI inspection
- docs: `cd docs && quarto render <page>` or
  `typst compile typst/seminar_slides/<file>.typ --root .`
- performance: a timing harness or profiler before changing code

Do not proceed on code guesses until the loop fails in the same way the user
reported, or until you can state exactly why a loop cannot be built.

If no reproducible loop can be built, do not patch by guesswork. State the
missing artifact, access, fixture, command, or metric needed next. If the
blocker is durable repo debt, record a blocked issue in `.agents/issues.toml`
through `agents-db`.

## Workflow

1. Reproduce the symptom and capture the exact command, traceback, metric, or
   bad output.
2. Minimize the loop until it is fast enough to run repeatedly.
3. Write 3 to 5 ranked falsifiable hypotheses.
4. Probe one variable at a time. Temporary logs must use a unique
   `[DEBUG-...]` prefix.
5. Turn the minimized repro into a regression test when the seam is real.
6. Fix the cause, rerun the minimized loop and original loop, then remove all
   debug instrumentation.

If no good test seam exists, record that as architecture debt in
`.agents/issues.toml` or `.agents/refactors.toml` through `agents-db`.

## Specialized Evidence

After the failing surface is known, include the relevant contract skill named
by root routing or nested package guidance in the repro and verification loop.

## Completion

Report:

- failing loop and passing loop
- confirmed cause, not only the patch
- regression test or reason no correct seam exists
- removed debug probes
- any DB or memory updates needed
