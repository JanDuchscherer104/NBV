# Autoresearch Report: May 22 Advisor Deck As ARIA-NBV Thesis Source Of Truth

Date: 2026-06-17  
Target: `docs/typst/thesis/advisor_meeting_2026_05_22.typ`  
Mode: research artifact only; no deck rewrite in this phase.

## Executive Synthesis

`docs/typst/thesis/advisor_meeting_2026_05_22.typ` is already the strongest compact advisor-facing contract in the repo: it states the central target-conditioned finite-candidate `Q_H` thesis question, the RQ1-RQ6 order, actor-visible target/representation boundaries, support gates, finite-candidate value-learning ladder, and RQ5/RQ6 escalation posture. It should become the highest source of truth only after a consolidation pass adds source-governance, citations/links, a state matrix, explicit todo flavors, and a prune pass for stale or over-operational slide text.

The clean owner split after consolidation should be:

| Surface | New role |
|---|---|
| `docs/typst/thesis/advisor_meeting_2026_05_22.typ` | Highest advisor-facing thesis contract and current decision deck. |
| `docs/contents/thesis/questions.qmd` | Rendered public mirror for RQ definitions and stable anchors; should be updated from the deck after deck promotion. |
| `docs/contents/thesis/roadmap.qmd` | Rendered public mirror for dated milestones, evidence contract, and risk register; should be updated from the deck after deck promotion. |
| `.agents/memory/state/*.md` | Internal canonical memory: decisions, open questions, gotchas, and project state. It should cite or summarize deck deltas but not compete with it. |
| `docs/typst/thesis/advisor_distillation.typ` | Long-form advisor/proposal distillation; preserve as detail source, but route conflicts to the deck once promoted. |
| `docs/typst/thesis_slides/slides_thesis_outlook.typ` | Historical outlook/advisor-history input only. Do not let it override the promoted deck. |
| `docs/typst/seminar_paper/**` | Historical implemented evidence: oracle RRI, VINv3, offline store, diagnostics, run history. Not current thesis priority. |

## Verification Inputs

Local guidance and skills read:

- `AGENTS.md` from the prompt, `docs/AGENTS.md`.
- `.agents/skills/agent-behavior/SKILL.md`, `docs-curator/SKILL.md`, `typst-authoring/SKILL.md`, `aria-litkg-memory/SKILL.md`.
- `.agents/references/source_order.md`, `.agents/references/verification_matrix.md`, `.agents/references/litkg_quick_reference.md`.
- Typst-authoring references for slides, shared notation, and claim/citation discipline.

Local discovery and KG checks:

- `make kg-status` returned `kg-status: ok`.
- `make kg-route KG_TASK="distill ARIA-NBV thesis source truth into advisor_meeting_2026_05_22 deck with citations todos and prune historical conflicts" KG_FORMAT=json` ranked `.agents/memory/state/DECISIONS.md`, `docs/contents/thesis/questions.qmd`, `docs/typst/thesis/advisor_distillation.typ`, active backlog, rollout code, `docs/typst/thesis/proposal.typ`, and `docs/contents/thesis/roadmap.qmd` as the relevant source families.
- `make kg-search KG_QUERY="advisor meeting Q_H target RRI roadmap questions rollouts zarr" KG_FORMAT=json KG_LIMIT=12` surfaced `OPEN_QUESTIONS.md:33`, historical advisor deck memory, RRI metric docs, rollout docs, and historical rollout notes.
- `make kg-search KG_QUERY="Hestia GenNBV SceneScript VIN-NBV Project Aria ASE EFM3D EVL target RRI" KG_FORMAT=json KG_LIMIT=12` surfaced VIN/RRI implementation references and canonical `docs/contents/literature/vin_nbv.qmd`.
- `make kg-claim-check KG_CLAIM="ARIA-NBV treats Hestia-style hierarchy, GenNBV-style continuous control, and SceneScript-style semantic memory as design references, not thesis-core claims."` returned `supported (confidence=1.0)`.
- `make kg-claim-check KG_CLAIM="ARIA-NBV's thesis core is a target-conditioned finite-candidate Q_H value model trained from ASE oracle rollout traces and evaluated by oracle re-evaluation under equal budgets."` returned `supported (confidence=1.0)`.

Known KG nuance: strict invalidity-as-constraint is locally canonical in `questions.qmd`, `DECISIONS.md`, and `glossary.typ`, but one subagent observed an `unverifiable` KG verdict for that exact shape. Treat it as a KG classifier limitation for local design-contract claims, not as a contradiction.

## Proposed State Categories

Use these categories consistently in the deck.

| Category | Meaning | Primary owner after deck promotion |
|---|---|---|
| Implemented substrate | Code, data paths, diagnostics, or historical results that already exist. | Deck summary plus links to API docs, seminar paper, generated references. |
| Current thesis core | Required claim path for thesis success. | Deck. |
| WIP necessary | Work that must be completed before thesis-grade claims. | Deck plus roadmap/backlog mirrors. |
| Optional ablation | Useful if schedule allows, but not a core success condition. | Deck appendix or roadmap mirror. |
| Open decision | Advisor-facing unresolved choice. | Deck `#todo` marker plus `OPEN_QUESTIONS.md` mirror. |
| Conflict/historical | Older source or claim that contradicts current contract unless demoted. | Deck `#todo` marker or historical appendix, then source cleanup. |
| Prune candidate | Detail that belongs in backlog, logs, or historical notes, not the top contract. | Remove from main deck or move to appendix with marker. |

## Current Deck Content To Preserve

| Deck span | Keep | Reason |
|---|---|---|
| `advisor_meeting_2026_05_22.typ:110-167` | Central research question and RQ1-RQ6 table. | Matches `questions.qmd:12-30` and `roadmap.qmd:12-34`; it is the compact contract. |
| `advisor_meeting_2026_05_22.typ:169-276` | RQ3 scene/target/candidate boundary and actor-visible GT exclusion. | Matches `questions.qmd:325-407`, `roadmap.qmd:170-182`, and `DECISIONS.md:279-282`. |
| `advisor_meeting_2026_05_22.typ:278-328` | Support/scale controls and invalidity as mask/reason. | Matches `questions.qmd:409-477` and `questions.qmd:570-612`. |
| `advisor_meeting_2026_05_22.typ:330-450` | Offline `Q_H`, policy ladder, headroom/recovery, reported quantities. | Matches `questions.qmd:217-323`, `roadmap.qmd:497-539`, and shared equations. |
| `advisor_meeting_2026_05_22.typ:452-490` | RQ5/RQ6 gating. | Matches `questions.qmd:520-568` and KG-supported design-reference claim. |
| `advisor_meeting_2026_05_22.typ:492-562` | Milestone table and advisor feedback prompts. | Keep, but update with the broader state matrix and open-decision taxonomy. |

## What To Add To The Deck

| Priority | Addition | Evidence |
|---|---|---|
| P0 | A first-content “Source Governance / Highest Truth” slide. It should state that this May 22 deck owns current advisor-facing thesis direction; roadmap/questions/memory mirror it after promotion; seminar/outlook slides are historical evidence. | `source_order.md:7-10`, `source_order.md:32-34`, `DECISIONS.md:35-36`, `roadmap.qmd:43-45`, `docs/index.qmd:47-50`. |
| P0 | A “State Matrix” slide/table using the proposed categories above. | `questions.qmd:88-96`, `PROJECT_STATE.md:15-20`, `DECISIONS.md:270-320`. |
| P0 | A concise “Implemented Substrate” slide. | `PROJECT_STATE.md:15-20`, `questions.qmd:88-92`, seminar paper `main.typ:9-15`, seminar sections for oracle/VIN/offline store, generated API pages. |
| P0 | A “WIP Necessary Before Claims” slide: M1/M2/M3/M4/M5 gates, LRZ/Zarr, V1 target selector, rollout support, one-step scorer evidence, `Q_H`. | `roadmap.qmd:346-358`, `roadmap.qmd:401-539`, `questions.qmd:98-118`, `DECISIONS.md:274-278`. |
| P0 | A “Todo/Open Decision Legend” slide and local Typst helper macros derived from `#todo[...]`. | Deck already imports `@preview/dashy-todo:0.1.3` at `advisor_meeting_2026_05_22.typ:7`; one unresolved generic `#todo` exists at line 259. |
| P1 | Literature/citation anchors on the first appearance of VIN-NBV, Project Aria/ASE, EFM3D/EVL, GenNBV, Hestia, SceneScript, and offline-RL references. | `roadmap.qmd:114-122`, `questions.qmd:21-30`, `docs/contents/literature/*.qmd`, `docs/references.bib`. |
| P1 | Internal source links for roadmap/questions/theory/API pages. | `questions.qmd:21-30`, `roadmap.qmd:35-45`, `roadmap.qmd:690-705`. |
| P1 | A “No-Headroom Is A Valid Result” clause. | `questions.qmd:241-250`, `questions.qmd:320-323`, `roadmap.qmd:73-88`, `roadmap.qmd:687-688`. |
| P1 | A “Shared Evidence Contract” slide: coverage tuple, equal-budget protocol, split leakage boundary, invalidity and masks, storage/scale protocol. | `questions.qmd:570-621`, `roadmap.qmd:625-676`. |
| P1 | A compact appendix mapping literature families to adopt/reject decisions. | `roadmap.qmd:114-122`, `advisor_distillation.typ:652-693`. |

## What To Prune Or Move From The Current Deck

| Deck span | Recommendation | Why |
|---|---|---|
| `advisor_meeting_2026_05_22.typ:259` | Replace generic `#todo[...]` with a typed open-decision marker, fix typo `decsriptor`, and cite the conflicting/owning sources. | It is currently a raw unresolved note in a math block. If the deck becomes highest truth, TODOs need typed semantics. |
| `advisor_meeting_2026_05_22.typ:121-133` | Replace or supplement local endpoint-gain equation with shared `#eqs.entity.endpoint_gain` or a small local expansion explicitly declared as the rendered definition. | Shared notation exists in `docs/typst/shared/equations/entity.typ:83-120`; avoid duplicated drift. |
| `advisor_meeting_2026_05_22.typ:349-359` | Replace local residual dueling formula with `#eqs.rl.qh_dueling_residual` and shared action-set notation. | Current formula uses `cal(A)_t`; shared policy reserves `cal(Q)_t` for candidates and `Q_H` for value functions. |
| `advisor_meeting_2026_05_22.typ:386-398` | Replace with `#eqs.rl.qh_doubleq_index` and `#eqs.rl.qh_doubleq_target` or ensure exact notation matches those shared equations. | Shared definitions exist in `docs/typst/shared/equations/rl.typ:148-162`. |
| `advisor_meeting_2026_05_22.typ:519-527` | Move “Immediate next edits before scale” out of main flow or convert to WIP necessary TODOs with backlog links. | These are operational next edits, not stable highest-truth thesis claims. |
| `advisor_meeting_2026_05_22.typ:533-562` | Rename from “What I Need Feedback On” to “Advisor Locks / Open Decisions” and add typed todos. | As highest truth, the deck should not read like a one-off meeting note. |
| Any uncited first-use literature mention | Add citations/links. | Advisor-facing literature and thesis claims require citation/claim checks. |
| Any mention inherited from `slides_thesis_outlook.typ` that frames storage/gamma/RL priority as current truth without current-source support | Prune or mark historical/conflict. | Outlook deck self-labels as historical at `slides_thesis_outlook.typ:57-63`. |

## Historical Sources To Demote Or Archive

| Source | Recommendation |
|---|---|
| `docs/typst/thesis_slides/slides_thesis_outlook.typ:57-63` | Keep historical trust-boundary text or archive the deck; do not treat it as current truth after promotion. |
| `docs/typst/thesis_slides/slides_thesis_outlook.typ:65-179` | Prune from current control flow; extract only decisions already aligned with May 22. |
| `docs/typst/thesis_slides/slides_thesis_outlook.typ:367-408` | Keep rollout/RL inspector figures as diagnostic scaffold evidence only, not thesis-grade result claims. |
| `docs/typst/seminar_paper/main.typ:9-15` and seminar introduction | Preserve as implemented evidence for older Aria-VIN-NBV/VINv3 one-step substrate. |
| Seminar W&B/run appendices | Do not use as top-level truth; retain as reproducibility appendix or historical log evidence only. |

## Shared Typst Collection Usage

Use existing shared modules before adding local math:

- `docs/typst/shared/equations/entity.typ:13-120`: target descriptor, match score, target error, root-normalized target reward, state-relative RRI, finite-horizon return, endpoint gain, lookahead headroom, `Q_H` recovery.
- `docs/typst/shared/equations/rl.typ:80-174`: finite action set, counterfactual transition, `Q_H`, residual/dueling/candidate-token definitions, masked argmax, Double-Q target, loss.
- `docs/typst/shared/equations/features.typ`: scene memory, candidate query pools, candidate pose features.
- `docs/typst/shared/glossary.typ:884-900`: finite candidate action set definition, including invalidity-as-constraint.
- `docs/typst/shared/glossary.typ:1181-1196`: validity mask definition.

Do not add a local symbol for a concept that already exists in `symb.*` or `eqs.*`. If a new todo taxonomy becomes reusable across thesis decks, prefer a small shared helper file such as `docs/typst/shared/todos.typ`; otherwise keep it deck-local.

## Dashy Todo Flavor Design

The deck already imports `@preview/dashy-todo:0.1.3`. Add thin wrappers derived from `#todo[...]`, not a new dependency. Exact package styling can be tuned during Typst compilation; the semantic API should be stable:

```typst
#let conflict-todo(body, sources: none) = todo[
  *Conflict:* #body
  #if sources != none [\ #text(size: 9pt)[Sources: #sources]]
]

#let decision-todo(body, owner: [advisor], sources: none) = todo[
  *Open decision (#owner):* #body
  #if sources != none [\ #text(size: 9pt)[Sources: #sources]]
]

#let necessary-todo(body, gate: none, sources: none) = todo[
  *WIP necessary:* #body
  #if gate != none [\ #text(size: 9pt)[Gate: #gate]]
  #if sources != none [\ #text(size: 9pt)[Sources: #sources]]
]

#let optional-todo(body, sources: none) = todo[
  *Optional ablation:* #body
  #if sources != none [\ #text(size: 9pt)[Sources: #sources]]
]

#let prune-todo(body, sources: none) = todo[
  *Prune candidate:* #body
  #if sources != none [\ #text(size: 9pt)[Sources: #sources]]
]
```

First markers to add:

| Marker | Target |
|---|---|
| `decision-todo` | Candidate pose descriptor choice at `advisor_meeting_2026_05_22.typ:259`; sources: shared features equation TODOs and RQ3 representation text. |
| `decision-todo` | Exact `Q_H` effect-size threshold; sources: `questions.qmd:320-323`, `OPEN_QUESTIONS.md:13-16`. |
| `decision-todo` | Horizon/gamma/clipping/near-solved-target policy; sources: `questions.qmd:205-209`, `OPEN_QUESTIONS.md:22-27`. |
| `decision-todo` | V1 target matching thresholds and ambiguity policy; sources: `questions.qmd:377-401`, `OPEN_QUESTIONS.md:17-20`. |
| `necessary-todo` | LRZ/Zarr preflight before scale; sources: `roadmap.qmd:672-676`, `DECISIONS.md:278`. |
| `necessary-todo` | Scene-level split and coverage reporting before final claims; sources: `questions.qmd:592-605`, `roadmap.qmd:625-670`. |
| `conflict-todo` | Any reused outlook-deck claim that still says `.omx`/historical/gamma/storage/RL priority differently from current sources. |
| `prune-todo` | Main-flow operational next edits if retained in the deck. |

## Citation And Link Plan

Add citations on first use where the deck makes advisor-facing literature claims:

| Claim family | Citation or internal link |
|---|---|
| Project Aria / ASE substrate | `@projectaria-engel2023`, `@ProjectAria-ASE-2025`; internal `docs/contents/literature/project_aria.qmd`, `docs/contents/ase_dataset.qmd`. |
| EFM3D / EVL local evidence and OBB support | `@EFM3D-straub2024`, `@EVL-Doc-2025`; internal `docs/contents/literature/efm3d.qmd`. |
| VIN-NBV quality/RRI precedent | `@VIN-NBV-frahm2025`; internal `docs/contents/literature/vin_nbv.qmd`. |
| GenNBV and Hestia as bridge references | `@GenNBV-chen2024`, `@Hestia-lu2026`; internal literature pages. |
| SceneScript semantic/global future-work bridge | `@SceneScript-avetisyan2024`; internal literature page. |
| Offline RL / masked value-learning references | DQN, Double-DQN, IQL, CQL, BCQ, Decision Transformer, Trajectory Transformer, Gumbel-Top-k as appropriate; keep them as reference families, not claimed implemented algorithms. |
| Internal current truth | Link to `questions.qmd`, `roadmap.qmd`, `rri_theory.qmd`, `rl_planning.qmd`, generated API references, and canonical memory only when the slide needs traceability. |

## Implementation Order For The Later Deck Patch

1. Add source-governance and state-matrix slides near the start.
2. Add the todo flavor helpers immediately after existing helper macros.
3. Replace the generic line-259 todo with a typed open decision.
4. Convert local duplicated equations to shared `#eqs.*` where available.
5. Add citations and internal links on first-use literature/source claims.
6. Move main-flow operational next edits into a WIP/appendix or typed TODO block.
7. Add appendix tables for implemented substrate, necessary WIP, optional ablations, open decisions, and prune/historical sources.
8. Compile and visually inspect the deck.
9. After deck promotion, update roadmap/questions/memory to state that the May 22 deck is the highest current advisor source.

## Proposed Verification For The Later Deck Patch

```sh
cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ --root . /tmp/advisor_meeting_2026_05_22.pdf
rg -n "#todo\\[|conflict-todo|decision-todo|necessary-todo|optional-todo|prune-todo" docs/typst/thesis/advisor_meeting_2026_05_22.typ
rg -n "gamma = 0\\.1|vin_offline\\.counterfactuals|online RL.*stretch|highest-level project ground truth" docs/typst/thesis/advisor_meeting_2026_05_22.typ
make kg-claim-check KG_CLAIM="ARIA-NBV treats Hestia-style hierarchy, GenNBV-style continuous control, and SceneScript-style semantic memory as design references, not thesis-core claims."
make kg-claim-check KG_CLAIM="ARIA-NBV's thesis core is a target-conditioned finite-candidate Q_H value model trained from ASE oracle rollout traces and evaluated by oracle re-evaluation under equal budgets."
git diff --check
```

If the deck promotion also edits canonical memory or source-order references:

```sh
make check-agent-memory
make qmd-frontmatter-check
```

## Open Risks

- The deck can become too dense if every current-truth detail is moved into main flow. Keep the main flow decision-oriented; move implementation details and historical extraction to appendix.
- `dashy-todo` wrappers may need small syntax/style adjustment after a compile check; the semantic wrapper names should remain stable.
- Once the May 22 deck is promoted, source-order docs must be updated or agents will continue to prefer roadmap/questions/memory during conflicts.
- The current worktree has unrelated dirty files from earlier tasks; keep later deck changes scoped and do not stage unrelated drift.
