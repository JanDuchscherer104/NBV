---
name: plan-grill
description: Stress-test high-impact or advisor-facing ARIA-NBV plans.
metadata:
  mode: router
  not_when:
    - "a concrete failure or localized low-impact edit owns the task"
    - "the user asks for review of an existing concrete diff"
  handoff_to:
    - "aria-nbv-context when the affected source owner is unknown"
    - "aria-docs for direct-source claim review"
    - "aria-docs for public narrative after the decision"
    - "specialized diagnostic or review capability for concrete evidence"
  evidence_required:
    - "source-order owner and current implementation boundary"
    - "success criteria, in/out of scope, assumptions, and deferred decisions"
    - "claim strength and source evidence for research-facing choices"
  applies_to:
    - "**"
  triggers:
    - "advisor-facing or thesis-scope decision"
    - "high-impact scaffold or architecture plan"
    - "theory-rich or conceptual option analysis"
  must_read:
    - ".agents/references/source_order.md"
    - ".agents/skills/plan-grill/references/plan-mode-theory-patterns.md when theory-rich"
  canonical_sources:
    - ".agents/references/source_order.md#role-split"
    - "docs/contents/thesis/roadmap.qmd"
    - "docs/contents/thesis/questions.qmd"
    - "docs/typst/thesis/main.typ"
    - ".agents/skills/plan-grill/references/plan-mode-theory-patterns.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/facebookresearch/pytorch3d"
    - "/websites/typst_app"
    - "/websites/quarto"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "DoubleDQN-vanHasselt2015"
    - "VIN-NBV-frahm2025"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
  verification:
    - "decision-complete plan with owners, tests, risks, and deferred choices"
---

# Plan Grill

Resolve discoverable facts before asking questions. Start from the source-order
owner, nearest package/docs guidance, current implementation, and active tests.

For each material ambiguity:

1. State the decision and recommended default.
2. Explain the practical tradeoff and failure mode.
3. Test one normal case, one boundary case, and one failure case.
4. Separate current, planned, scratch, and historical evidence.

For theory-rich work, read `references/plan-mode-theory-patterns.md`, name the
source ladder and claim strength, and use external API or literature evidence
only where it changes the decision. Durable outcomes go directly to the owner
named by root guidance, never to a parallel context or decision file.

Complete with a decision-ready plan naming goal, interfaces, owners, sequence,
verification, assumptions, rollback point, and deferred decisions.
