# OMX Artifact Retention

OMX runtime state is local by default. Git history is the archive for completed
or superseded durable records, while logs, goals, sessions, caches, and other
machine runtime state remain untracked.

Tracked `.omx` records must be durable, human-reviewable artifacts under
`.omx/context/`, `.omx/interviews/`, `.omx/plans/`, or `.omx/specs/`. Markdown,
JSON, and HTML are supported when the format is appropriate to the record.
Human-facing Markdown plans and specifications should use lifecycle
frontmatter, for example:

```yaml
---
kind: plan # or spec
status: current # or accepted
---
```

`make check-agent-memory` rejects paths outside those durable roots, unsupported
formats, the generated `ownership-branch-consolidation-inventory.*` artifacts,
and known runtime, cache, log, state, goal, temporary, and transient paths. It
does not impose a blanket Markdown-only or frontmatter rule on durable JSON or
HTML. Add a durable record intentionally; leave generated workflow output and
user-local runtime state ignored.
