---
id: 2026-05-21_advisor_meeting_slide_deck
date: 2026-05-21
title: "Advisor Meeting Slide Deck"
status: done
topics: [thesis, typst, slides, advisor, qh, rri]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/advisor_meeting_2026_05_22.typ
  - docs/typst/thesis/advisor_meeting_2026_05_22.pdf
  - docs/contents/thesis/advisor_meeting_2026_05_22_questions.md
---

## Task

Prepared and iteratively refined a Typst advisor deck for the 2026-05-22 ARIA-NBV meeting, using the main seminar slide style while updating the narrative to the current target-conditioned rollout/RRI/Q_H thesis contract.

## Method

Spawned read-only sub-agents for thesis synthesis, research-question mining, slide-style extraction, diagram selection, math/formulation checks, and implementation status. Built the deck from current thesis roadmap/questions, advisor distillation, canonical memory, rollout readiness notes, PR #14 summary, shared equations/symbols, and existing Typst/diagram assets.

Performed a second refinement pass on 2026-05-21 against the local literature/theory pages for EFM3D scene embeddings, SCONE/FisherRF, candidate-view dependence, and the advisor distillation. The pass made the literature transfer explicit while preserving the same 15-slide meeting structure.

Performed a 2026-05-22 visual fix for the Zarr dataset-contract slide after the tdtr tree proved too dense for the slide column.

Resolved inline slide TODO comments on 2026-05-22 by removing the PR/changelog framing, keeping the deck RQ-aligned, dropping the "non-claims" wording in favor of scope boundaries, and replacing the evaluation policy table with a compact matched-policy ladder.

Performed a final 2026-05-22 RQ-first pass after advisor-facing feedback that the research questions needed to dominate the deck. The deck now opens title -> central research question -> RQ dependency chain -> pass/fail RQ gates -> evidence ledger, and nearly every technical slide is titled by the RQ(s) it supports. The companion meeting-question note was regrouped by RQ1--RQ6.

Added a 2026-05-22 architecture-considerations pass with two slides after the target protocol: one for scene/target/candidate tokenization and one for the conservative candidate-set architecture ladder. The slides use shared Typst equations for scene memory, point-DINO tokens, candidate-query pools, candidate row features, and the masked set encoder.

Added a 2026-05-22 feature-budget pass with a third architecture slide between scene tokenization and the candidate-set ladder. The slide separates target descriptors, view/candidate features, history/directional features, and validity/provenance diagnostics, while restating the V1 actor-visible boundary for GT and oracle assets.

Performed a 2026-05-22 RQ realignment pass after feedback that the slide RQs still missed the representation and escalation structure. The central thesis question was left unchanged; RQ2 now owns actor-visible scene/target/history/visibility/candidate-view representations, RQ5 is gated discrete online training over the same finite-candidate contract after stable offline Q_H evidence, and RQ6 is gated continuous target-then-pose headroom after discrete evidence. Scale, splits, LRZ/Zarr, leakage, invalidity, and coverage were moved into a shared evidence protocol rather than treated as RQs.

Performed a 2026-05-22 deck-only RQ/TODO/citation cleanup after further advisor-facing grilling. The compact deck now uses pitch-order RQs: RQ1 objective/method contract, RQ2 offline masked finite-candidate Q_H headroom recovery, RQ3 actor-visible representations, RQ4 support plus scale, RQ5 online discrete, and RQ6 continuous/hierarchical headroom. All live deck TODOs were resolved, Gumbel-Top-k was moved out of the main policy ladder, and the `@GumbelTopK-kool2019` Typst citation error was removed without editing `docs/references.bib`.

Applied a 2026-05-22 endpoint-objective clarification on the central research-question slide: \(J_e^{(H)}(\tau)\) now explicitly compares the root target error \(\Delta_0^e\) to \(\Delta_H^e\), where \(\Delta_H^e\) is evaluated after accumulating \(C_e(\mathcal{P}_0 \cup \mathcal{P}_1 \cup \cdots \cup \mathcal{P}_H)\) against the target ground-truth mesh.

## Outputs

- Added `docs/typst/thesis/advisor_meeting_2026_05_22.typ`.
- Rendered `docs/typst/thesis/advisor_meeting_2026_05_22.pdf`.
- Added `docs/contents/thesis/advisor_meeting_2026_05_22_questions.md` with slide-visible and off-slide advisor questions.
- Kept the deck explicit about implemented, partial, planned, and escalation work: multi-step rollout and rollout Zarr/Q_H persistence exist, but broad LRZ rollout generation is still blocked by preflight, sharding, chunking, invalidity-consistency, and target-sampling readiness.
- Refined the deck with an evidence-ledger slide that names what VIN-NBV, Project Aria/ASE/EFM3D, SCONE/FisherRF, DeepSets/Set Transformer/Double-Q, and GenNBV/Hestia/object-centric NBV contribute and what they do not replace.
- Replaced the tiny Q_H replay figure with native Typst flow blocks plus a compact residual-dueling and masked Double-Q formulation.
- Replaced the dense tdtr Zarr relation tree with a native compact relation map so node text no longer overlaps or clips.
- Removed inline TODO/NOTE comments from the advisor deck source and resolved their requested content changes.
- Added companion-note literature talking points for the advisor meeting.
- Reordered the opening deck narrative so RQ gates precede implementation evidence.
- Grouped slide-visible and off-slide advisor questions by RQ1--RQ6.
- Added `Architecture I: Scene / Target / Candidate Tokens` and `Architecture II: Conservative Candidate-Set Ladder`; the deck now renders as 17 slides.
- Added `Architecture II: Target / View / History Feature Budget` and renamed the ladder to `Architecture III: Conservative Candidate-Set Ladder`; the deck now renders as 18 slides.
- Realigned the deck RQs: RQ2 now covers actor-visible representations, RQ5 covers gated discrete online training, and RQ6 covers gated continuous hierarchical headroom; the companion question note now follows the same structure.
- The earlier RQ realignment render was 19 PDF pages including the title slide.
- Refined the deck to the compact 10-page pitch-order version: RQ2 is offline Q_H, RQ3 is representations, RQ4 is support/scale, RQ5/RQ6 are gated extension questions, and the policy ladder no longer contains unresolved Gumbel/continuous-control TODOs.
- Updated the central slide objective math so the endpoint gain definition uses accumulated selected-view point evidence through horizon \(H\), not an implicit generic \(\Delta_t^e\).

## Verification

- `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .`
- `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ /tmp/advisor_meeting_2026_05_22.pdf --root .`
- Rendered PDF pages with `pdftoppm -png -r 120` and inspected contact sheets across multiple iterations until the deck had 15 pages with no continuation overflows.
- `make qmd-frontmatter-check`
- `make kg-claim-check KG_CLAIM="ARIA-NBV's thesis core is a leakage-safe target-conditioned finite-candidate RRI decision process on ASE/EVL: measure oracle-lookahead headroom under matched budgets, then train a finite-candidate Q_H value model to recover that headroom from actor-visible target, scene, history, candidate, mask, and reason-code inputs; continuous actor-critic remains a later escalation."` returned supported with confidence 1.0.
- Second-pass compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 15-page PDF.
- Zarr-slide fix compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 15-page PDF; slide 8 was rendered with `pdftoppm -f 8 -l 8 -singlefile -png -r 180` and inspected.
- TODO-resolution compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 15-page PDF; `rg -n "TODO|todo|FIXME|XXX|NOTE" docs/typst/thesis/advisor_meeting_2026_05_22.typ` returned no matches; affected pages were rendered with `pdftocairo`.
- RQ-first compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 15-page PDF.
- RQ-first visual QA: rendered all pages with `pdftoppm -png -r 120 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/advisor_rq_pages/page` and inspected `/tmp/advisor_rq_contact_sheet.png`; no obvious overflow, Zarr clipping, or math regression was visible.
- `make kg-claim-check KG_CLAIM="ARIA-NBV's advisor deck should treat RQ1 through RQ6 as the thesis spine: objective and metrics, actor-visible target protocol, candidate and rollout support, finite-candidate Q_H headroom recovery, scale under target-RRI supervision, and online or continuous escalation only after finite-candidate evidence."` returned supported with confidence 1.0.
- `make check-agent-memory` passed.
- Architecture-slide compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 17-page PDF.
- Architecture-slide visual QA: rendered all pages with `pdftoppm -png -r 120 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/advisor_arch_pages/page`, inspected `/tmp/advisor_arch_contact_sheet.png`, and zoom-ins for pages 10--11 at 180 DPI.
- `make kg-claim-check KG_CLAIM="ARIA-NBV's architecture plan should use EVL as actor-visible local evidence and target support, semidense or fused point evidence with optional compressed DINO features as broader scene memory, and a staged finite-candidate model ladder from independent scoring through DeepSets, masked Set Transformer, relative-bias interaction, overlap-bias diagnostics, and residual dueling Q_H."` returned supported with confidence 1.0.
- Feature-budget compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced an 18-page PDF.
- Feature-budget visual QA: rendered all pages with `pdftoppm -png -r 120 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/advisor_feature_pages/page`, inspected `/tmp/advisor_feature_contact_sheet.png`, and zoomed pages 10--12 at 180 DPI.
- `make kg-claim-check KG_CLAIM="ARIA-NBV's advisor architecture slide should separate target descriptors, view and candidate pose/frustum features, selected-history and directional-memory features, and validity/provenance diagnostics while keeping GT crops, GT meshes, oracle RRI, and all-candidate GT renders out of V1 actor-visible inputs."` returned supported with confidence 1.0.
- RQ realignment compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 19-page PDF.
- RQ realignment visual QA: rendered pages 2--19 with `pdftocairo -png -f 2 -l 20 -r 125 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/aria_nbv_rq_realign/page` and inspected the central RQ, dependency, pass/fail, evidence-ledger, shared-evidence, RQ2 representation, Q_H, RQ5/RQ6, advisor-decision, roadmap, and feedback slides.
- `rg -n "TODO|FIXME|diffuse|non-claims|Scale boundary|Escalation boundary|Leakage-Safe Target Protocol|scope the evidence" docs/typst/thesis/advisor_meeting_2026_05_22.typ docs/contents/thesis/advisor_meeting_2026_05_22_questions.md` returned no matches.
- `make qmd-frontmatter-check` passed.
- `make kg-claim-check KG_CLAIM="ARIA-NBV's advisor deck frames RQ2 as the actor-visible representation question over scene, target, history, visibility, and candidate-view features; RQ5 as gated discrete online training over the same finite-candidate contract after stable offline Q_H evidence; and RQ6 as gated continuous target-then-pose headroom after discrete evidence, while scale, leakage, invalidity, and LRZ/Zarr readiness remain shared evidence protocol."` returned unverifiable because the literature KG lacks source paths for that deck-structure claim.
- RQ/TODO/citation cleanup compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` produced a 10-page PDF.
- RQ/TODO/citation cleanup visual QA: rendered all pages with `pdftocairo -png -r 125 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/advisor_rq_refined/page` and inspected the first RQ slide, RQ3 representation slides, RQ4 support/scale slide, RQ2 Q_H slides, RQ5/RQ6 slide, and final feedback slide.
- `rg -n -i "TODO|FIXME|XXX|TBD|placeholder|find better|cite gumbel|include continuous|What target objective\\?|Other ways to scale|rescue path|@Gumbel" docs/typst/thesis/advisor_meeting_2026_05_22.typ` returned no matches.
- `make kg-claim-check KG_CLAIM="The advisor deck frames the thesis as a target-conditioned finite-candidate RRI test: offline masked finite-candidate Q_H is evaluated only after oracle-lookahead headroom is measured; actor-visible representations and rollout support are prerequisite ablations; online discrete and continuous hierarchical control are gated extension questions."` returned supported with confidence 1.0.
- Endpoint-objective clarification compile: `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ typst/thesis/advisor_meeting_2026_05_22.pdf --root .` passed.
- Endpoint-objective visual QA: rendered the affected opening RQ slide with `pdftocairo -png -f 2 -l 2 -r 150 docs/typst/thesis/advisor_meeting_2026_05_22.pdf /tmp/advisor_delta_fix/page` and inspected `/tmp/advisor_delta_fix/page-02.png`; the accumulated-point equation fits without overflow.
- Endpoint-objective hygiene: `rg -n -i "TODO|FIXME|XXX|TBD|placeholder|find better|cite gumbel|include continuous|What target objective\\?|Other ways to scale" docs/typst/thesis/advisor_meeting_2026_05_22.typ` returned no matches.
- `make kg-claim-check KG_CLAIM="The advisor deck defines endpoint target gain J_e^(H)(tau) by comparing the root target error Delta_0^e against Delta_H^e, where Delta_H^e is computed after accumulating root and selected-view point evidence through horizon H against the target ground-truth mesh."` returned unverifiable because literature KG paper nodes lack source paths for this local deck-definition claim.
- `make check-agent-memory` passed.

## Canonical State Impact

No canonical memory update is needed. The deck and meeting note are public/advisor narrative artifacts derived from existing roadmap, questions, advisor distillation, and canonical state.
