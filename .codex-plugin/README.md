# ARIA-NBV Codex Plugin

This repo-local plugin exposes the ARIA-NBV MemPalace MCP server and safe Codex
hooks. It is independent of Oh My Codex (OMX): normal repo work must continue to
function with plain Codex plus `AGENTS.md` and `.agents/skills/`.

## OMX Relationship

OMX is an optional Codex CLI workflow layer. Use it for planning, audits, and
coordinated team execution after the repo guidance is clean. Do not require it
for tests, docs builds, or package workflows.

Operator-local runtime files stay out of Git:

- `.omx/`
- `.codex/config.toml`
- `.codex/hooks.json`

Checked-in templates are allowed:

- `.codex/config.example.toml`
- `.codex/hooks.example.json`

Use the installed OMX help for operator commands; the repository does not
maintain a duplicate command guide.

## Hook Policy

The plugin hooks are non-blocking. If MemPalace is unavailable, the hook logs a
message and exits successfully so Codex sessions are not blocked by optional
memory tooling.
