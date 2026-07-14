# OMX Artifact Retention

OMX runtime state is local by default. Git history is the archive for completed
or superseded plans, reviews, logs, goals, sessions, generated reports, and
machine-readable runtime output.

The only tracked `.omx` records are current or accepted human-facing plans and
specifications. They must be Markdown files under `.omx/plans/` or
`.omx/specs/` with YAML frontmatter:

```yaml
---
kind: plan # or spec
status: current # or accepted
---
```

`make check-agent-memory` rejects every other tracked `.omx` path and records
without this metadata. Add a record only after it becomes current or accepted;
force-add that validated record intentionally, and leave drafts and generated
workflow output ignored locally.
