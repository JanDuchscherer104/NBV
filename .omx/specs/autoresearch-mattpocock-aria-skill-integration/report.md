# Matt Pocock Skills And ARIA-NBV Integration Report

## Executive Recommendation

Do not install the full `mattpocock/skills` set as active global skills for
ARIA-NBV. Install only a small set of generic engineering skills that either
have low collision risk or are explicitly user-invoked. Treat the rest as
upstream guidance referenced from ARIA-local skills.

The boundary should be:

- OMX owns orchestration: goals, phase transitions, teams, Ralph/Ralplan,
  autoresearch, validation gates, and state.
- Matt skills own generic engineering discipline: codebase design vocabulary,
  red-green-refactor, prototype discipline, and skill-writing craft.
- ARIA local skills own domain knowledge: ASE, RRI, NBV geometry, litkg, thesis
  source order, Typst/Quarto routing, dataset/cache/Rerun/LRZ contracts, and
  ARIA-specific verification.

This matches the Matt repo's own split between user-invoked orchestrators and
model-invoked reusable discipline, while preserving ARIA's source-order rule
that `.agents/skills/*/SKILL.md` are sidecars for activation, evidence, and
verification rather than durable thesis truth.

## Install / Activate Now

| Matt skill | Invocation posture | Why |
|---|---|---|
| `codebase-design` | Install as model-invoked generic discipline | This is the cleanest reusable Matt contribution for ARIA. It supplies shared vocabulary for modules, interfaces, depth, seams, adapters, leverage, and locality. ARIA skills should refer to it instead of carrying generic architecture prose. |
| `improve-codebase-architecture` | Install, but explicit/user-invoked only | Useful as an operator command for architecture scans. It should not replace ARIA `simplification`, `plan-grill`, or `code-review-aria-nbv`; it can feed candidates into those local owners. |
| `tdd` | Install as model-invoked when test-first is requested | Low collision risk. ARIA still owns which package tests and verification commands apply. |
| `prototype` | Install as model-invoked for throwaway design probes | Useful for state-model or UI sanity checks. Keep it explicitly throwaway; durable implementation still routes through ARIA owners. |
| `writing-great-skills` | Install as explicit/reference skill | Use it to maintain ARIA skills and prune duplicated skill prose. It should inform `.agents/references/skill_style_guide.md`, not replace it. |

## Optional Explicit-Only Installs

These are useful only if the operator wants those exact commands available.
They should not become automatic ARIA routing.

| Matt skill | Recommendation |
|---|---|
| `to-prd` | Optional explicit-only. ARIA usually has roadmap/questions/issues already; output should route into `agents-db` or existing `.omx/plans`, not create a parallel PRD owner. |
| `to-issues` | Optional explicit-only. If used, final actionable work must be entered through `agents-db` into `.agents/issues.toml`, `.agents/todos.toml`, or `.agents/refactors.toml`. |
| `teach` | Optional explicit-only. No ARIA integration needed. |
| `handoff` | Optional explicit-only. Codex/OMX already has handoff and state surfaces; use only when the operator wants Matt's compact handoff behavior. |
| `resolving-merge-conflicts` | Optional explicit-only or model-invoked for actual merge/rebase conflicts. It does not collide with ARIA thesis/domain routing. |
| `wizard` | Optional explicit-only for manual third-party setup. Do not use for normal ARIA verification. |

## Reference-Only, Do Not Activate By Default

These overlap with existing ARIA owners. Use them as upstream guidance for
trimming local skills, not as active default skills.

| Matt skill | ARIA owner to keep | Integration |
|---|---|---|
| `code-review` | `code-review-aria-nbv` | Keep ARIA review active for PR/worktree diffs. Borrow Matt's two-axis Standards/Spec split and smell baseline as reference prose. |
| `diagnosing-bugs` | `diagnose-aria` | Keep ARIA diagnosis active because failures often depend on Streamlit, Rerun, KG, docs, package, ASE, and data caches. Borrow reproduce/minimize/hypothesize/instrument/fix/regression-test structure. |
| `research` | `aria-litkg-memory`, `semantic-scholar-litkg`, `docs-curator` | Keep ARIA retrieval and claim checks active. Borrow primary-source capture discipline only. |
| `domain-modeling` | `plan-grill`, `docs-curator`, glossary owner | Use as guidance for terminology hardening, but ARIA terms live in `docs/typst/shared/glossary.typ` and `.agents/memory/state/DECISIONS.md`, not `CONTEXT.md`. |
| `grill-me`, `grill-with-docs`, `grilling` | `plan-grill` | Do not activate globally. Fold one-question-at-a-time, recommendation-with-question, and codebase-facts-before-questions behavior into `plan-grill` references. |
| `edit-article`, `writing-shape`, `writing-beats`, `writing-fragments` | `docs-curator`, `typst-authoring` | Use as prose-process inspiration only. ARIA thesis/docs routing stays local. |
| `triage`, `qa`, `request-refactor-plan` | `agents-db`, `plan-grill`, `diagnose-aria` | Do not activate. ARIA backlog and bug triage live in TOML and repo-specific diagnostics. |
| `implement` | OMX plus `agent-behavior` | Do not activate. Implementation mode selection is OMX/ARIA-owned. |
| `ask-matt`, `setup-matt-pocock-skills` | ARIA root `AGENTS.md` and OMX routing | Do not activate for ARIA. They would create a competing router/setup surface. |
| `design-an-interface` | `codebase-design` plus explicit subagent patterns | Do not activate by default. It lives under upstream `deprecated/`; use `codebase-design` and its design-it-twice reference instead. |

## Skip

Do not install for ARIA-NBV unless a future task explicitly asks for them:

- `claude-handoff`
- `git-guardrails-claude-code`
- `loop-me`
- `migrate-to-shoehorn`
- `obsidian-vault`
- `scaffold-exercises`
- `setup-pre-commit`
- `ubiquitous-language`
- `wayfinder`

## ARIA Skill Integration Matrix

| ARIA local skill | Keep? | Matt reference |
|---|---:|---|
| `agent-behavior` | Keep | No direct Matt owner. It remains the ARIA preflight/router. Mention `codebase-design`, `tdd`, and `prototype` only as optional generic sidecars. |
| `agents-db` | Keep | Reference `to-issues`, `triage`, and `to-prd` as optional upstream issue-workflow inspiration, but keep TOML ownership local. |
| `aria-litkg-memory` | Keep | Reference `research` as primary-source capture inspiration only. ARIA KG/retrieval remains local. |
| `aria-nbv-context` | Keep | No replacement. |
| `aria-nbv-mermaid` | Keep | No direct Matt replacement. |
| `code-review-aria-nbv` | Keep and slim | Reference `code-review` for Standards/Spec split; keep ARIA severity, domain, PR/worktree, and evidence rules local. |
| `counterfactual-rollout-planner` | Keep | No replacement. |
| `dataset-cache-ops` | Keep | No replacement. |
| `diagnose-aria` | Keep and slim | Reference `diagnosing-bugs` for generic diagnosis loop; keep local toolbelt and domain failure taxonomy. |
| `docs-curator` | Keep | Reference `edit-article` / writing skills only as prose-process inspiration. |
| `entity-aware-rri` | Keep | No replacement. |
| `lrz-ai-systems` | Keep | No replacement. |
| `nbv-geometry-contracts` | Keep | No replacement. |
| `plan-grill` | Keep and slim | Reference `grilling`, `grill-me`, `grill-with-docs`, and `domain-modeling`; keep ARIA thesis source ladder, claim checks, glossary, and public/internal boundaries. |
| `python-docstrings` | Keep | No Matt replacement. |
| `rerun-nbv-inspector` | Keep | No replacement. |
| `semantic-scholar-litkg` | Keep | No replacement. |
| `simplification` | Keep and slim | Reference `codebase-design`, `improve-codebase-architecture`, and `code-review` smell baseline. Keep ARIA behavior-preserving cleanup rules local. |
| `typst-authoring` | Keep | Reference writing skills only for prose shaping if useful. Typst/Quarto rendering and thesis notation stay local. |
| `zarr-python` | Keep | No replacement. |

## Where To Point To Matt Skills

Use three layers, in this order:

1. `.configs/external_skills.toml`

   Record the Matt source as an external skill source:

   - `source = "mattpocock/skills"`
   - `url = "https://github.com/mattpocock/skills.git"`
   - `reviewed_ref = "896f14d9c25659f03b24e08e4efc3ee69bbade08"`
   - `license = "MIT"`
   - `default_policy = "disabled_unless_selected"`
   - per-skill rows with `integration = "install" | "explicit" | "reference" | "skip"`

   This is the right machine-readable owner for update/audit policy.

2. `.agents/references/external_skill_sources.md` or a narrower
   `.agents/references/mattpocock_skills.md`

   Use this as the human-readable index that explains the boundary: Matt is
   upstream generic engineering discipline; ARIA is local domain evidence. This
   file should point to the pinned commit and selected upstream skill paths.

3. Per-skill reference files under ARIA skills only when the relationship is
   strong.

   Examples:

   - `.agents/skills/plan-grill/references/upstream-mattpocock.md`
   - `.agents/skills/simplification/references/upstream-mattpocock.md`
   - `.agents/skills/code-review-aria-nbv/references/upstream-mattpocock.md`
   - `.agents/skills/diagnose-aria/references/upstream-mattpocock.md`

   Keep `SKILL.md` bodies compact. They should say "use the upstream reference
   for generic process; keep ARIA evidence and verification local."

Do not put Matt paths in `metadata.canonical_sources`; ARIA canonical sources
must stay repo-local and truth-owning. Do not put `mattpocock:*` names into
machine-facing `handoff_to`; use prose references or local handoff targets.

## What To Cut From ARIA Skills

Cut generic workflow prose when an upstream Matt skill owns it better:

- `plan-grill`: remove duplicated generic grilling/domain-modeling theory; keep
  ARIA source ladder, claim-check requirements, thesis boundary, and glossary
  capture.
- `simplification`: remove broad architecture philosophy; point to
  `codebase-design` and keep ARIA cleanup safeguards, behavior-preservation,
  and verification.
- `diagnose-aria`: remove generic debugging-loop teaching; point to
  `diagnosing-bugs` and keep ARIA toolbelt/failure surfaces.
- `code-review-aria-nbv`: remove generic review-method exposition; point to
  `code-review` and keep ARIA severity, evidence, and domain-specific review
  rules.
- `agents-db`: avoid becoming a full issue-tracker guide; point optional
  `to-issues`/`triage` behavior into TOML-backed ARIA backlog surfaces.

Do not cut domain skills merely because Matt has a broadly similar verb. A skill
is removable only when its ARIA-specific read-first sources, evidence
requirements, and verification commands can move into another ARIA owner without
losing routing clarity.

## Recommended Installer Selections

If the installer is asking which Matt skills to install now, choose:

- `codebase-design`
- `improve-codebase-architecture`
- `prototype`
- `tdd`
- `writing-great-skills`

Optionally choose, only if you want the explicit commands:

- `to-prd`
- `to-issues`
- `teach`
- `handoff`
- `resolving-merge-conflicts`

Do not select by default:

- `ask-matt`
- `setup-matt-pocock-skills`
- `implement`
- `code-review`
- `diagnosing-bugs`
- `research`
- `domain-modeling`
- `grill-me`
- `grill-with-docs`
- `grilling`
- `design-an-interface`
- `triage`
- the deprecated, personal, in-progress, TypeScript-specific, or setup skills
  not listed above.

## Verification For A Follow-Up Patch

When implementing this recommendation:

```bash
make scaffold-audit
make scaffold-audit-self-test
make check-agent-memory
make claude-skills
```

Also add fixtures that prove:

- "review this ARIA PR" routes to `code-review-aria-nbv`, not Matt `code-review`.
- "diagnose this Streamlit/Rerun/KG failure" routes to `diagnose-aria`, not Matt
  `diagnosing-bugs`.
- "stress-test this thesis scope decision" routes to `plan-grill`, not
  `grilling`.
- "find a deep module seam" can use `codebase-design`.
- "run an architecture scan" is explicit `improve-codebase-architecture`.

## Conclusion

Use Matt skills to shrink and sharpen generic engineering process inside ARIA,
not to replace ARIA's domain routers. The smallest safe active set is
`codebase-design`, `improve-codebase-architecture`, `prototype`, `tdd`, and
`writing-great-skills`, with a few optional explicit commands. Everything else
should be reference-only or skipped until a concrete workflow needs it.

