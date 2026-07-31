# MemPalace ARIA-NBV

This optional MCP-only plugin uses its inline MCP command to resolve the active
Git repository and start the globally installed `mempalace-mcp` executable
with its absolute `.artifacts/mempalace/palace` path. Set
`MEMPALACE_PALACE_PATH` to override the palace explicitly. Resolution fails
closed outside a Git repository. The plugin contains no skills, hooks, or
apps; Codex discovers ARIA skills directly from `.agents/skills/`.

Install the repository marketplace, then add `mempalace-aria-nbv`. The plugin
remains optional and never owns repository truth.
