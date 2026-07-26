---
name: rerun-nbv-inspector
description: Build and smoke-test the read-only Rerun inspector.
metadata:
  mode: implementation
  not_when:
    - "the input store is invalid before inspection"
    - "package geometry, candidate, label, or storage semantics are changing"
  handoff_to:
    - "dataset-cache-ops for invalid or incompatible input stores"
    - "nearest package owner for geometry, candidate, label, or storage changes"
    - "specialized diagnostic capability for launch failures or suspicious output"
  evidence_required:
    - "inspector implementation and focused tests"
    - "official Rerun SDK evidence for changed SDK behavior"
    - "saved .rrd smoke artifact or exact input blocker"
  applies_to:
    - "aria_nbv/aria_nbv/rerun_inspector/**"
    - "aria_nbv/tests/rerun_inspector/**"
  triggers:
    - "change the Rerun inspector or its logging"
    - "produce or inspect an .rrd smoke artifact"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/rerun-nbv-inspector/references/rerun-python-patterns.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#geometry-contracts"
    - "aria_nbv/aria_nbv/rerun_inspector"
    - "aria_nbv/tests/rerun_inspector"
  verification:
    - "focused inspector tests followed by a one-sample saved .rrd smoke"
---

# Rerun Inspector

Keep the inspector read-only. Localize the logging path in package code and
read the nearest owners for every data, geometry, frame, candidate, validity,
label, and storage contract it displays. Do not restate or reinterpret those
contracts in inspector guidance.

For SDK calls, follow the progressive-disclosure reference and verify changed
behavior against the official Rerun Python documentation for the installed
version. Keep display transforms, styling, thinning, and blueprints isolated
from source samples.

Run focused inspector tests, then prefer a deterministic one-sample saved
`.rrd` smoke. If input validation fails, report the exact owner-backed error;
do not weaken readers or mutate stored samples.
