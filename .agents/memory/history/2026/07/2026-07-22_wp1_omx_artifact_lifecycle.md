---
id: 2026-07-22_wp1_omx_artifact_lifecycle
date: 2026-07-22
title: "WP1 OMX Artifact Lifecycle"
status: done
topics: [scaffold, omx, lifecycle, provenance]
confidence: high
canonical_updates_needed: []
---

WP1 introduced the registry-backed OMX planning-evidence lifecycle. The approved
successor remains at its six native role paths; the accepted July 14 predecessor
is preserved byte-identically under the reserved accepted-bundle archive and is
linked as superseded. Two baseline standalone plans were removed only after
their approved SHA-256 and Git blob identities were verified and recorded as
tombstones.

Verification is owned by `make omx-artifacts-check` and is also included in
`make check-agent-memory` and root CI. Lifecycle fixtures cover promotion,
supersession, native/archive placement, redaction, history, collision safety,
and rollback.
