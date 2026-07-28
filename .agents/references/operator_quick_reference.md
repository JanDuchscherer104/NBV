# Operator Quick Reference

Use this file for practical operator aids that do not belong in canonical project state.

## Environment Recovery
- Preferred interpreter: `aria_nbv/.venv/bin/python`
- If the venv is missing or stale, rebuild it from `aria_nbv/` with:

```bash
cd aria_nbv
uv sync --all-extras
```

- If `uv` does not resolve Python 3.11 automatically on this machine, rerun with an explicit local interpreter path:

```bash
cd aria_nbv
UV_PYTHON=/path/to/python3.11 uv sync --all-extras
```

- Replace `/path/to/python3.11` with a machine-local interpreter path. Keep host-specific paths here or in user-local notes, not in shared repo guidance.

- Verify the interpreter before diagnosing dependency issues:

```bash
aria_nbv/.venv/bin/python --version
uv run python --version
```

## litkg Health Probe
Run `make kg-status` first when KG output looks degraded or empty. It is a
fast 0/1 probe (checks `.configs/litkg.toml`, the litkg-rs submodule, and
`cargo` on PATH). Exit 0 = healthy, exit 1 = degraded with a one-line reason
on stderr; never blocks. If degraded, fall back to `aria-nbv-context` plus
targeted reads instead of waiting for the heavier `make kg-*` commands.

## Automatic KG refresh on session Stop
`scripts/kg/auto_refresh.sh` runs on every Claude/Codex Stop hook (see
`.claude/settings.json` and `.codex/hooks.example.json`). It silently skips
when:
- the ollama tunnel at `127.0.0.1:11434` is unreachable
  (`ssh -N -R 11434:127.0.0.1:11434 ubuntu` not running);
- no tracked source under `docs/`, `aria_nbv/aria_nbv/`,
  `.agents/references/`, or `.agents/*.toml` changed since the last
  refresh;
- another refresh is in flight (`.agents/kg/.refresh.lock` present).

Otherwise it spawns `make kg-refresh-light` detached; status lands in
`.agents/kg/.refresh.log`. Force a refresh with
`KG_FORCE=1 scripts/kg/auto_refresh.sh`. If a stale lock blocks future
refreshes, remove it manually: `rm .agents/kg/.refresh.lock`.

## Mac-Offloaded litkg Ollama
Use the Mac as the Ollama model host while keeping ARIA-NBV sources, Neo4j,
Graphiti, and generated KG artifacts on the Ubuntu workstation.

On the Mac:

```bash
ollama serve
ollama pull qwen3-embedding:4b
ollama pull gemma4:26b
ssh -R 11434:127.0.0.1:11434 jd@ubuntu-workstation
```

On Ubuntu, the ARIA-NBV Makefile reads the Ollama model settings from
`.configs/litkg.toml`:

```bash
make kg-ollama-check
make kg-up
make kg-ingest-docs KG_SMOKE=1
```

Run `make kg-ollama-check` before `make kg-ingest-docs` or embedding
enrichment when the tunnel might have expired. Override values with environment
variables only for one-off experiments; the default ARIA-NBV contract lives in
`[runtime.ollama]`.

## Repo Hygiene
Run these before staging or when the worktree looks noisy:

```bash
git status -sb
git diff --stat
git diff --name-only
```

Workflow:
- Classify untracked files as keep, ignore, or delete before staging.
- Add ignores for logs, renders, caches, and other generated artifacts instead of committing them.
- Stage by intent so code, docs, and assets remain reviewable as separate changes.
- Do not revert unrelated worktree changes unless the user explicitly asks.

## Frame and Key Conventions
- Frame hierarchy: world -> rig/device -> camera; use `PoseTW` for poses and `CameraTW` for cameras.
- Transform notation: `T_A_B` means “transform from frame B to frame A.”
- ATEK key prefixes:
  - `mtd`: motion trajectory data
  - `mfcd`: multi-frame camera data
  - `msdpd`: multi-semidense-point data

## EFM Snippet View Quick Reference
- `camera_rgb`, `camera_slam_left`, `camera_slam_right` -> `EfmCameraView`
- `trajectory` -> `EfmTrajectoryView`
- `semidense` -> `EfmPointsView`
- `obbs` -> `EfmObbView` or `None`
- `gt` -> `EfmGTView`
- `mesh` / `has_mesh` -> optional ground-truth mesh
- Use `.to(...)` on the snippet or its sub-views to move tensors without cloning when possible.
