# OMX Quick Reference

Use this reference for optional Oh My Codex (OMX) orchestration around
ARIA-NBV. OMX is not required for normal repo work; the canonical repo surfaces
remain `AGENTS.md`, `.agents/skills/`, `.agents/memory/state/`, and
`make agents-db`.

## Requirements

- Node.js 20+
- Codex CLI installed and authenticated in the same shell profile used by OMX
- macOS or Linux for the recommended OMX path
- `tmux` when using durable team runtime

Native Windows and Codex App are not OMX's recommended default path. From a
desktop or Codex-App-adjacent workflow, prefer direct launch or treat OMX as a
separate terminal operator tool.

## Install And Smoke

```bash
npm install -g @openai/codex oh-my-codex
omx setup
omx doctor
codex login status
omx exec --skip-git-repo-check -C . "Reply with exactly OMX-EXEC-OK"
```

If `omx doctor` passes but execution fails, check that the shell running OMX
sees the same `CODEX_HOME`, auth profile, and environment as normal Codex CLI.

## Launch

```bash
omx --madmax --high
```

For a one-off launch without OMX tmux/HUD management:

```bash
omx --direct --yolo
```

Keep `.omx/`, `.codex/config.toml`, and `.codex/hooks.json` operator-local.
Only commit `.codex/*.example.*` templates, plus the deliberately vendored
`.codex/skills/graphify/**` project skill.

## Recommended Workflows

- `$deep-interview "..."` for vague scope, advisor decisions, or ambiguous
  thesis boundaries.
- `$ralplan "..."` for approving an implementation plan before broad edits.
- `$prometheus-strict "..."` for durable multi-surface planning where goals
  must be persisted before execution.
- `$team 3:executor "..."` for independent audits or clearly split work.
- `$ralph "..."` for a persistent single-owner completion loop after the plan
  is approved.

Avoid team execution for geometry/RRI code changes until the relevant targeted
tests are reliable and the work has a decision-complete plan.

## Scaffold Goal Persistence

For ARIA-NBV scaffold rework, keep the narrative plan under
`.omx/plans/prometheus-strict/` and the actionable follow-up under
`make agents-db`. `.omx/` remains operator-local runtime/planning state, so
checked-in owner surfaces should link the plan only when the path is needed for
traceability.

Autoresearch and visual interpretation loops integrate through
`.agents/references/alignment_tools_contract.md`: OMX may orchestrate the loop,
but the repo owns only the typed adapter boundary, evidence artifacts, and
verification gates.

## Hook Interplay

ARIA-NBV already has a repo-local `.codex-plugin` for MemPalace. OMX setup may
create native `.codex/hooks.json`; keep that runtime file local and merge
operator hooks deliberately from `.codex/hooks.example.json` if needed. The
repo plugin must continue to work without OMX.

## Accepted Planning Evidence

OMX runtime state stays local. Accepted planning bundles are governed by
`.agents/omx_artifacts.toml`: current artifacts remain in native OMX role paths,
and superseded bundles live only under
`.omx/archive/accepted-bundles/<bundle-id>/`. Run `make omx-artifacts-check`
after changing registry members or lifecycle policy.

## Safety Checks

Before committing scaffold work:

```bash
git status --short --untracked-files=all
rg -n "api_key|/home/|/Users/|C:\\\\|\\.omx" .codex .codex-plugin .agents .gitignore || true
make check-agent-memory
```
