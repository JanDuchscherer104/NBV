# Architect Review: Local Scientific Agent Skill Adapters

Verdict: APPROVE

## Strongest Antithesis
The strongest counterargument is that adding six new adapter skills and an external-skill audit tool increases scaffold surface area. A smaller change could merge selected guidance into existing owners and avoid submodule/update-tool overhead.

## Tradeoff Tension
Pinned external plus adapters gives provenance and safe activation, but it adds files, update policy, and fixture work. Minimal merging has lower operational cost but weaker provenance and higher adjacent-owner overload.

## Required Improvements Applied
- Phase 4 is conditional on fixture or dry-exercise wins before merging slide, Mermaid, or `plan-grill` guidance.
- The plan now names pinned git submodule as the concrete storage mechanism.
- The test spec includes nearest-neighbor collision fixtures for `scientific-writing` versus `typst-authoring` and `scientific-visualization` versus `aria-nbv-mermaid`.

## Architectural Status
CLEAR
