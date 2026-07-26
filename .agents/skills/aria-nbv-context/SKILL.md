---
name: aria-nbv-context
description: Localize ARIA-NBV sources and owners.
metadata:
  mode: router
  not_when:
    - "the exact owner and target are already known"
  handoff_to:
    - "aria-docs for documentation authoring after localization"
    - "plan-grill for high-impact decisions after localization"
  evidence_required:
    - "owning path plus Graphify or exact-source localization evidence"
  applies_to:
    - "**"
  triggers:
    - "locate an ARIA-NBV file, symbol, owner, or source family"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - "AGENTS.md#graphify"
    - ".agents/references/graphify_contract.md"
  verification:
    - "the localized owner is confirmed in exact source"
---

# ARIA-NBV Context

1. Run `make graphify-freshness`. When fresh, choose the native command by task:
   `tree --root .` for hierarchy, `explain` for a known symbol, `affected` for
   callers and impact, `path` for two known entities, and `query` for broad
   discovery.
2. Confirm the result in exact tracked source. If Graphify is stale or
   insufficient, use targeted `rg` and narrow reads directly.
3. Open the nearest `AGENTS.md` only after the surface is localized.
4. Hand off with the owning path, why it owns the task, the relevant caller or
   consumer, the narrow verification command, and any unresolved evidence.

Stop once the smallest sufficient source set and owner are confirmed. Graphify
is navigation evidence; exact source owns the result.
