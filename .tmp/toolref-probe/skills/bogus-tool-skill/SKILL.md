---
name: bogus-tool-skill
description: Test-only skill fixture.
metadata:
  mode: router
  not_when:
    - "test-only adjacent owner"
  handoff_to:
    - "external test capability"
  evidence_required:
    - "test evidence"
  applies_to:
    - ".tmp/**"
  triggers:
    - "test"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - ".agents/references/source_order.md#role-split"
  tool_refs:
    - "mcp__Bogus.fake"
  verification:
    - "test verification"
---

# Test Skill

Use this test body for tool ref validation.
