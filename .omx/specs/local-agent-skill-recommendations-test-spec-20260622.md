# Test Spec: Local Scientific Agent Skill Adapters

## Claims To Prove
1. The upstream K-Dense collection is pinned outside the activated local skill path.
2. Only ARIA-owned adapter skills are discoverable under `.agents/skills/`.
3. The six adapters route work to the right owners and do not collide with adjacent skills.
4. External skill updates are auditable and never rewrite local adapters automatically.
5. Adapter bodies stay compact, source-order-compliant, and free of durable thesis truth leakage.

## Static Checks
- `make scaffold-audit`: required metadata, directory/frontmatter name match, local handoffs, canonical sources, hot-path line budget, routing fixtures.
- `make scaffold-audit-self-test`: bad anchors, invalid handoffs, semantic drift, unknown tool refs, and fixture mistakes are caught.
- `make check-agent-memory`: guidance/debrief hygiene after scaffold changes.
- `make claude-skills`: only direct `.agents/skills/*/SKILL.md` local skills are exposed.

## External Source Checks
- `python3 scripts/external_skills.py status`: report source path, URL, pinned ref, selected paths, local adapters, license, and cleanliness.
- `python3 scripts/external_skills.py diff --source kdense`: report diffs only for selected upstream skills and highlight descriptions, commands, allowed tools, env vars, network endpoints, scripts, references, and license.
- `python3 scripts/external_skills.py audit --source kdense`: fail on missing selected paths, missing adapters, dirty submodule, executable upstream scripts without approval, missing provenance, new credential/network requirements, or scaffold-audit failure.
- `python3 scripts/external_skills.py update --source kdense --ref <sha-or-tag>`: fetch/checkout requested ref, write selected-skill diff report, update lock, and do not rewrite adapter bodies.
- Mocked or `--dry-run` update smoke: prove update planning/diff generation can run without rewriting adapter bodies.

## Routing Fixtures
Positive fixtures:
- `scientific-writing-thesis-prose`: "Rewrite the thesis introduction from a verified claim outline" -> `scientific-writing`
- `literature-review-object-aware-nbv`: "Run a scoped literature synthesis for object-aware NBV" -> `literature-review`
- `scientific-review-methods-validity`: "Review the thesis methods chapter for scientific validity" -> `scientific-review`
- `experiment-design-target-rri`: "Design an experiment comparing target-RRI rollout policies" -> `experiment-design`
- `scientific-visualization-validity-figure`: "Check candidate-family validity figure semantics and provenance" -> `scientific-visualization`
- `citation-management-bibtex-metadata`: "Validate duplicate BibTeX keys and missing DOI metadata" -> `citation-management`

Negative fixtures:
- `code-review-pr-diff`: "Review this PR diff" -> `code-review-aria-nbv`
- `typst-equation-layout`: "Fix this Typst equation or page layout" -> `typst-authoring`
- `context-local-vin-methods`: "Find the source family for a local VIN-NBV methods claim" -> `aria-nbv-context`
- `kg-literature-claim-check`: "Check an advisor-facing literature claim against source-backed evidence" -> `aria-litkg-memory`
- `rerun-rollout-inspection`: "Inspect this rollout in Rerun" -> `rerun-nbv-inspector`
- `docs-quarto-navigation`: "Plan a Quarto navigation cleanup" -> `docs-curator`
- `scientific-writing-not-typst`: "Turn a verified claim outline into thesis prose without touching Typst layout" -> `scientific-writing`, not `typst-authoring`
- `typst-not-scientific-writing`: "Fix a Typst citation, equation, page break, or rendered layout issue" -> `typst-authoring`, not `scientific-writing`
- `scientific-visualization-not-mermaid`: "Review a data figure plan for uncertainty, units, aggregation, and provenance" -> `scientific-visualization`, not `aria-nbv-mermaid`
- `mermaid-not-scientific-visualization`: "Create, edit, lint, or render a Mermaid `.mmd` thesis diagram" -> `aria-nbv-mermaid`, not `scientific-visualization`

## Adapter Dry Exercises
- `scientific-writing`: produce a section outline from a verified claim ledger.
- `literature-review`: create a query/screening/synthesis ledger for one bounded NBV topic using existing source policy.
- `citation-management`: report missing/duplicate/unused citation issues without changing `docs/references.bib`.
- `scientific-review`: review one thesis or method section for claim strength, leakage, V0/V1 status, and evidence support.
- `experiment-design`: specify experimental unit, paired roots, scene splits, uncertainty method, and budget parity for one comparison.
- `scientific-visualization`: review one figure/table plan for units, aggregation level, sample counts, uncertainty, provenance, and accessibility.

## Content Guards
- No adapter `SKILL.md` contains broad upstream tool requirements such as OpenRouter, Nano Banana, PubMed defaults, Google Scholar scraping, mandatory generated schematics, blanket PRISMA/PICO defaults, or citation-count thresholds.
- No adapter mutates `docs/references.bib` without an explicit diff path.
- No adapter promotes planned thesis work to implemented evidence.
- No adapter uses `.omx/`, `.codex/`, or upstream K-Dense files as canonical thesis truth.

## Review Checks
- External source is pristine and pinned.
- `.configs/external_skills.toml` default policy disables unlisted upstream skills.
- Every adapter has an upstream adaptation note with adopted/rejected decisions.
- Root and docs guidance route without duplicating long policy.
- Public docs are not updated with internal agent scaffold content.

## Completion Criteria
All static checks pass; external source checks pass or exact blockers are recorded; routing fixtures pass; dry exercises show each adapter improves a real ARIA-NBV workflow or it is removed/deferred.
