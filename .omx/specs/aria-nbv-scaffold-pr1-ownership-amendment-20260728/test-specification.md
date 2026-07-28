# PR1 Ownership Amendment Test Specification

## Required Gates

```sh
OMX_ARTIFACT_PREVIOUS_REF=b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c make check-agent-memory
python scripts/tests/test_validate_omx_artifacts.py
cd aria_nbv && uv run pytest tests/agent_memory/test_validate_agent_memory.py tests/agent_memory/test_codex_transcript_extract.py
make scaffold-audit
make scaffold-audit-self-test
CUDA_VISIBLE_DEVICES='' OMX_ARTIFACT_PREVIOUS_REF=b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c make ci PYTEST_ARGS=
```

## Ownership Cases

- Reject direct writes to legacy paths, aliases, and bare journal names.
- Reject capitalized owner anaphors across Markdown, TOML, and Typst.
- Accept an explicit different active owner in the same logical record.
- Join TOML table and array-table fields without crossing table boundaries.
- Keep Typst brackets balanced when prose contains apostrophes.
- Accept unrelated writes before and after a legacy migration statement.
- Reject direct alias writes and clause-initial `Update it` with a prior legacy
  antecedent.
- Accept writes to explicit non-legacy benchmark, report, and figure objects.

## Lifecycle Cases

- Validate every first-parent snapshot from the merge base through the PR head.
- Reject mixed, omitted, reordered, non-identical, or pointer-only supersession.
- Preserve archived predecessor bytes and verify content and chain receipts.
- Reject runtime, transcript, private-path, machine-locator, and secret payloads.
