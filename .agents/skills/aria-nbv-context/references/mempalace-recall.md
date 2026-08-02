# MemPalace Recall

Read this only when prior decisions, failed approaches, unknown ownership, or
cross-surface relationships materially improve discovery.

## Eligibility

- Known files, symbols, implementation, tests, and active configuration use
  direct `rg`, code-index, and exact-source reads. Code is outside the reviewed
  corpus.
- Use a prompt-visible MCP search surface verified by upstream `--read-only`
  plus Codex's fail-closed `enabled_tools` allowlist. Mutating MCP tools remain
  hidden and refused; Chroma may still update internal bookkeeping during search.
- If that surface is unavailable or unverified, continue deterministically.

## Scope And Evidence

- Choose one smallest wing: `aria-thesis`; `aria-literature-reviews`, followed
  by the matching `aria-papers` room for primary evidence; `aria-project-docs`;
  `aria-debriefs`; or `aria-codex-history` for explicit raw-history requests.
- Treat results as candidate evidence. Record source and authored date, open the
  exact current-worktree source, and apply source order.
- Chronology alone never implies supersession; ingestion-only dates stay
  unknown.
