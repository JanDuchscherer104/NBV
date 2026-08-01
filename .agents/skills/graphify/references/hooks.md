# graphify reference: optional Git hook

Load this only when the user asks to install the optional upstream Git hook.

## ARIA-NBV boundary

The upstream hook is a local accelerator for incremental code refresh and
semantic invalidation. It is not a freshness authority: its absence or failure
cannot make a graph fresh, remove `graphify-out/needs_update`, or change
`scripts/check_graphify_freshness.py` output. Only a successful freshness check
authorizes graph-backed claims.

If the hook is useful locally, use the upstream Git hook command:

```bash
graphify hook install    # install
graphify hook uninstall  # remove
graphify hook status     # check
```

Do not run `graphify install --project --platform codex`, `graphify agents
install`, or any installer that rewrites root `AGENTS.md`. Do not install the
upstream Codex hook: its pre-tool hook is a no-op, while ARIA-NBV routing is
already owned by `.agents/skills/graphify/`.

Code-only staleness may use upstream incremental AST update. Projection,
documentation, paper, citation, or diagram staleness requires an explicit
Graphify workflow: rebuild `graphify-input/` at current `HEAD`, run isolated
Codex semantic extraction, complete the upstream graph update, then pass
`python3 scripts/check_graphify_freshness.py --quiet`. Ordinary questions use
exact sources while that work is pending.

Clearing either shared semantic-cache link affects every linked worktree and
increases future extraction cost. It cannot make a stale graph current.
