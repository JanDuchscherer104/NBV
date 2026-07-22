---
id: 2026-07-22_wp3_codex_matt_policy
date: 2026-07-22
title: "WP3 Codex And Matt Policy"
status: done
topics: [codex, matt-skills, scaffold]
confidence: high
canonical_updates_needed: []
---

Implemented the approved twelve-skill Matt allowlist at commit
`ed37663cc5fbef691ddfecd080dff42f7e7e350d` without vendoring skill bodies.
The policy pins `skills@1.5.20` and npm integrity, recursively hashes sorted
`path + NUL + raw bytes` Markdown closures, validates invocation metadata,
isolates unlisted Matt paths, and preserves unrelated skill families.

Focused fixtures cover routing, ARIA owner conflicts, wrong pins, closure
drift, missing and duplicate paths, symlink escape, unlisted enablement,
collision rollback, and project-config rollback. `codex debug prompt-input`
against the generated managed block exposes the six implicitly invokable Matt
skills at 1008 description bytes, below the 1511-byte WP0-derived limit. Codex
0.144.4 did not apply `skills.config` from project config during the temporary
prompt-input probe, so the probe loaded the identical managed block through a
clean temporary user config; the tracked project renderer and validator remain
the portable policy surface.
