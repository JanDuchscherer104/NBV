# Source-Of-Truth Conflict Autoresearch Report

Verified against the local repository at `/home/jd/repos/ARIA-NBV` on
2026-06-16. The source ledger contains C1-C16 and R1-R4; all are covered below.

## Owner Baseline

Current owner hierarchy is explicit and should be treated as the repair rule:

- Current thesis direction: `docs/contents/thesis/roadmap.qmd`,
  `docs/contents/thesis/questions.qmd`, and `.agents/memory/state/`
  (`.agents/references/source_order.md:7`, `.agents/references/source_order.md:8`,
  `AGENTS.md:9`, `AGENTS.md:10`, `docs/AGENTS.md:7`, `docs/AGENTS.md:8`).
- Proposal wording: `docs/typst/thesis/proposal.typ` and included sections
  (`.agents/references/source_order.md:15`, `.agents/references/source_order.md:16`,
  `docs/AGENTS.md:12`).
- Seminar paper/slides: historical implemented evidence, not current thesis
  direction (`.agents/references/source_order.md:17`, `.agents/references/source_order.md:18`,
  `.agents/references/source_order.md:32`, `.agents/references/source_order.md:33`,
  `docs/AGENTS.md:13`).
- Durable tool/autoresearch outputs are evidence/proposals, not owner surfaces
  (`.agents/references/alignment_tools_contract.md:6`, `.agents/references/alignment_tools_contract.md:12`).

## Critical Conflicts

### C1 - Public docs still claim the seminar paper is highest-level truth

Status: confirmed.

Conflicting sources:

- `docs/index.qmd:47` says `docs/typst/seminar_paper/main.typ` is the
  highest-level project ground truth.
- `AGENTS.md:9` and `AGENTS.md:10` say current thesis direction is owned by
  roadmap/questions/canonical memory, and the seminar paper is historical
  evidence.
- `docs/AGENTS.md:7`, `docs/AGENTS.md:8`, and `docs/AGENTS.md:13` repeat that
  split.
- `.agents/references/source_order.md:7`, `.agents/references/source_order.md:8`,
  `.agents/references/source_order.md:17`, and `.agents/references/source_order.md:18`
  define the same owner split.

Recommended owner/fix:

- Owner: public narrative in `docs/index.qmd`, constrained by
  `.agents/references/source_order.md`.
- Patch `docs/index.qmd` to say roadmap/questions/canonical memory own current
  thesis direction; seminar paper is historical implemented evidence.

### C2 - Research-question numbering differs across canonical docs, deck, and meeting note

Status: confirmed.

Conflicting sources:

- Canonical questions define RQ1 objective, RQ2 actor-visible target
  representation, RQ3 candidate/rollout support, RQ4 finite-candidate Q_H,
  RQ5 scale, RQ6 online/continuous escalation
  (`docs/contents/thesis/questions.qmd:119`, `docs/contents/thesis/questions.qmd:215`,
  `docs/contents/thesis/questions.qmd:297`, `docs/contents/thesis/questions.qmd:347`,
  `docs/contents/thesis/questions.qmd:455`, `docs/contents/thesis/questions.qmd:496`).
- Advisor deck uses pitch-order labels: RQ1 Method, RQ2 Offline, RQ3 Repr.,
  RQ4 Support, RQ5 Online, RQ6 Cont.
  (`docs/typst/thesis/advisor_meeting_2026_05_22.typ:142`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:146`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:150`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:153`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:156`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:159`).
- Meeting questions use the canonical-style RQ2/RQ3/RQ4 mapping, not the deck's
  pitch-order RQ2/RQ3/RQ4
  (`docs/contents/thesis/advisor_meeting_2026_05_22_questions.md:18`,
  `docs/contents/thesis/advisor_meeting_2026_05_22_questions.md:20`,
  `docs/contents/thesis/advisor_meeting_2026_05_22_questions.md:21`).
- The debrief records both a realignment pass and a later compact pitch-order
  pass while still claiming no canonical update is needed
  (`.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:8`,
  `.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:35`,
  `.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:37`,
  `.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:98`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/questions.qmd` owns RQ numbering; roadmap mirrors
  it. Advisor decks may own slide grouping only.
- Rename deck labels to "Slide group" or align them to canonical RQ numbering.
  Do not let `advisor_meeting_2026_05_22.typ` redefine RQ numbers.

### C3 - Reward normalization mixes root-normalized and state-relative RRI

Status: confirmed, with an additional shared-equation owner issue.

Conflicting sources:

- Canonical questions state root-normalized additive target gain is the default
  rollout/Q_H reward, and state-relative target RRI is a one-step diagnostic
  (`docs/contents/thesis/questions.qmd:128`, `docs/contents/thesis/questions.qmd:129`,
  `docs/contents/thesis/questions.qmd:172`, `docs/contents/thesis/questions.qmd:176`,
  `docs/contents/thesis/questions.qmd:186`, `docs/contents/thesis/questions.qmd:188`).
- Canonical memory agrees (`.agents/memory/state/PROJECT_STATE.md:18`,
  `.agents/memory/state/PROJECT_STATE.md:47`,
  `.agents/memory/state/DECISIONS.md:204`,
  `.agents/memory/state/DECISIONS.md:205`,
  `.agents/memory/state/DECISIONS.md:294`).
- Advisor distillation first says rollout/Q_H use root-normalized target gain,
  then says each immediate RRI term is normalized by current target error
  (`docs/typst/thesis/advisor_distillation.typ:260`,
  `docs/typst/thesis/advisor_distillation.typ:282`).
- Proposal method uses the current-error denominator for
  `target_reward`
  (`docs/typst/thesis/sections/proposal/04-method.typ:95`,
  `docs/typst/thesis/sections/proposal/04-method.typ:98`).
- Shared Typst equation `eqs.entity.target_rri_reward` also encodes
  current-error normalization
  (`docs/typst/shared/equations/entity.typ:64`,
  `docs/typst/shared/equations/entity.typ:69`), while the shared glossary says
  the target reward is root-normalized
  (`docs/typst/shared/glossary.typ:996`,
  `docs/typst/shared/glossary.typ:1007`,
  `docs/typst/shared/glossary.typ:1008`).

Recommended owner/fix:

- Owners: `docs/contents/thesis/questions.qmd` owns thesis semantics;
  `docs/typst/shared/glossary.typ` and `docs/typst/shared/equations/*.typ`
  own reusable symbols/equations; proposal/advisor docs render the owner.
- Split names everywhere: `endpoint_gain`, `target_root_gain` or
  `root_step_gain`, and `state_relative_rri`. Fix the shared equation first,
  then update advisor/proposal prose to use the exact names.

### C4 - Gamma is fixed in old slides but open in canonical docs

Status: confirmed.

Conflicting sources:

- Old thesis outlook slides set `gamma = 0.1` and describe low-discount
  behavior (`docs/typst/thesis_slides/slides_thesis_outlook.typ:269`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:283`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:319`).
- Canonical questions leave exact gamma, epsilon, clipping, and near-solved
  policy open (`docs/contents/thesis/questions.qmd:205`,
  `docs/contents/thesis/questions.qmd:206`).
- Open questions explicitly ask for discount/default gamma
  (`.agents/memory/state/OPEN_QUESTIONS.md:23`).
- Meeting questions ask to confirm gamma/clipping/near-solved policy
  (`docs/contents/thesis/advisor_meeting_2026_05_22_questions.md:17`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/questions.qmd` and
  `.agents/memory/state/OPEN_QUESTIONS.md`.
- Mark `slides_thesis_outlook.typ` historical or replace fixed-gamma language
  with "gamma symbolic; gamma=1 endpoint-aligned default candidate; gamma<1
  ablation".

### C5 - Rollout storage conflicts: `vin_offline.counterfactuals` vs `rollouts.zarr`

Status: confirmed.

Conflicting sources:

- Old outlook slides recommend persisting top-k chains into
  `vin_offline.counterfactuals`
  (`docs/typst/thesis_slides/slides_thesis_outlook.typ:256`).
- Canonical decisions say first implemented replay path is standalone
  `rollouts.zarr` and not embedded VIN counterfactual blocks
  (`.agents/memory/state/DECISIONS.md:140`,
  `.agents/memory/state/DECISIONS.md:141`,
  `.agents/memory/state/DECISIONS.md:162`,
  `.agents/memory/state/DECISIONS.md:163`).
- Project state says immutable VIN offline stores do not advertise no-op
  counterfactual blocks; multi-step replay lives in standalone rollout artifacts
  (`.agents/memory/state/PROJECT_STATE.md:53`).
- Tests enforce no counterfactual hooks in the VIN offline public contract
  (`aria_nbv/tests/data_handling/test_public_api_contract.py:95`,
  `aria_nbv/tests/data_handling/test_public_api_contract.py:96`,
  `aria_nbv/tests/data_handling/test_vin_offline_store.py:1083`,
  `aria_nbv/tests/data_handling/test_vin_offline_store.py:1084`).

Recommended owner/fix:

- Owner: `.agents/memory/state/DECISIONS.md` plus rollout code/tests;
  old slides are historical.
- Replace or annotate the slide reference so it cannot guide implementation.

### C6 - Online RL/Gymnasium status conflicts with gate policy

Status: confirmed as narrative emphasis conflict, not necessarily false code.

Conflicting sources:

- Root guidance gates Gymnasium/SB3/online simulator work as stretch or M6
  bridge (`AGENTS.md:46`).
- Canonical questions and roadmap defer continuous/simulator-backed work until
  after finite-candidate evidence
  (`docs/contents/thesis/questions.qmd:94`,
  `docs/contents/thesis/questions.qmd:112`,
  `docs/contents/thesis/questions.qmd:512`,
  `docs/contents/thesis/roadmap.qmd:349`,
  `docs/contents/thesis/roadmap.qmd:559`).
- Canonical memory says full continuous control, online RL, and real-device
  deployment remain bridge/future work
  (`.agents/memory/state/PROJECT_STATE.md:19`,
  `.agents/memory/state/DECISIONS.md:272`,
  `.agents/memory/state/DECISIONS.md:302`).
- Old slides say Gymnasium env and SB3 PPO smoke coverage already exist and
  that greedy immediate reward beats random
  (`docs/typst/thesis_slides/slides_thesis_outlook.typ:384`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:387`).
- The code does contain Gymnasium/SB3/PPO-ready surfaces
  (`aria_nbv/aria_nbv/rl/counterfactual_env.py:1`,
  `aria_nbv/aria_nbv/rl/counterfactual_env.py:14`,
  `aria_nbv/aria_nbv/rl/counterfactual_env.py:487`,
  `aria_nbv/aria_nbv/rl/counterfactual_env.py:529`).

Recommended owner/fix:

- Owner: roadmap/questions/memory own thesis priority; `aria_nbv/aria_nbv/rl`
  owns implementation existence.
- Mark old RL slides as historical/diagnostic surface only; keep code docs clear
  that RL readiness is not thesis-core priority before M6 gates.

### C7 - Implemented-state claims in old slides overstate trusted evidence

Status: confirmed.

Conflicting sources:

- Old slides state rollout/RL surfaces already instantiate the contract, hard
  masks handle constraints, candidate rules reject invalid actions, PPO
  diagnostics exist, and rollout scaffold exists
  (`docs/typst/thesis_slides/slides_thesis_outlook.typ:241`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:282`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:297`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:298`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:299`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:363`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:384`).
- Rollout readiness/backlog says broad generation is blocked by invalidity
  consistency, forward-local collapse, stale stores, and low target-root-gain
  signal (`.agents/issues.toml:221`,
  `.agents/memory/history/2026/05/2026-05-20_rollout_probe_agents_db.md:30`,
  `.agents/memory/history/2026/05/2026-05-20_rollout_probe_agents_db.md:31`,
  `.agents/memory/history/2026/05/2026-05-20_rollout_probe_agents_db.md:32`,
  `.agents/memory/history/2026/05/2026-05-20_rollout_probe_agents_db.md:33`,
  `.agents/todos.toml:1128`,
  `.agents/todos.toml:1174`,
  `.agents/todos.toml:1198`).

Recommended owner/fix:

- Owner: current evidence status belongs in `.agents/memory/state/` and
  `.agents/*.toml`; old slides may only claim historical implementation.
- Introduce/propagate three labels: implemented surface, trusted evidence,
  thesis-scale evidence.

### C8 - README current focus lags the thesis spine

Status: confirmed as incomplete public entry-point framing.

Conflicting sources:

- README current focus stops at VIN/offline-store/one-step baseline before
  target-conditioned RRI and rollouts
  (`README.md:11`, `README.md:13`, `README.md:16`).
- Current state says the thesis plan has a hard gated core beyond one-step
  scoring and a mandatory candidate-query Transformer Q_H
  (`.agents/memory/state/PROJECT_STATE.md:17`,
  `.agents/memory/state/PROJECT_STATE.md:25`).
- Decisions say Q_H is not optional and define the candidate-query Transformer
  result (`.agents/memory/state/DECISIONS.md:99`,
  `.agents/memory/state/DECISIONS.md:100`,
  `.agents/memory/state/DECISIONS.md:295`).
- Questions/roadmap make Q_H hard thesis core
  (`docs/contents/thesis/questions.qmd:92`,
  `docs/contents/thesis/questions.qmd:106`,
  `docs/contents/thesis/roadmap.qmd:60`,
  `docs/contents/thesis/roadmap.qmd:348`).

Recommended owner/fix:

- Owner: `README.md` is public entry-point summary; roadmap/questions own detail.
- Update README to state immediate M1 gate plus thesis spine:
  target-specific RRI -> target-conditioned one-step scorer -> rollout headroom
  -> Q_H. Keep VIN as myopic control.

### C9 - Quarto nav exposes old thesis outlook slides without warning

Status: confirmed.

Conflicting sources:

- Public nav exposes "MSc Slides 01 (outlook)"
  (`docs/_quarto.yml:141`, `docs/_quarto.yml:149`, `docs/_quarto.yml:150`).
- The same deck contains stale gamma/storage/RL claims cited in C4-C7
  (`docs/typst/thesis_slides/slides_thesis_outlook.typ:256`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:269`,
  `docs/typst/thesis_slides/slides_thesis_outlook.typ:384`).
- Current advisor deck exists but is not linked by this nav entry
  (`docs/typst/thesis/advisor_meeting_2026_05_22.typ:15`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:27`).

Recommended owner/fix:

- Owner: `docs/_quarto.yml` public navigation, constrained by docs source order.
- Remove the old deck from current nav or relabel it
  "historical outlook, superseded". Link the current advisor deck only if it is
  intended to be public.

### C10 - Advisor distillation and proposal duplicate canonical content

Status: confirmed.

Conflicting sources:

- Advisor distillation contains a full thesis contract, model, RQs, reward,
  architecture, policy comparison, literature ledger, and schedule
  (`docs/typst/thesis/advisor_distillation.typ:132`,
  `docs/typst/thesis/advisor_distillation.typ:147`,
  `docs/typst/thesis/advisor_distillation.typ:282`,
  `docs/typst/thesis/advisor_distillation.typ:311`,
  `docs/typst/thesis/advisor_distillation.typ:635`).
- Proposal sections duplicate objective, method, policy comparison, and schedule
  (`docs/typst/thesis/sections/proposal/03-objectives.typ:6`,
  `docs/typst/thesis/sections/proposal/04-method.typ:81`,
  `docs/typst/thesis/sections/proposal/04-method.typ:164`,
  `docs/typst/thesis/sections/proposal/05-schedule.typ:7`).
- Canonical owners are questions/roadmap/memory per source order
  (`.agents/references/source_order.md:7`, `.agents/references/source_order.md:8`).

Recommended owner/fix:

- Owners: questions own RQs/reward semantics; roadmap owns milestones; proposal
  owns proposal wording; advisor distillation is derivative advisor synthesis.
- Add explicit derivative headers to advisor distillation and proposal, and
  reduce duplicated definitions where possible.

## Medium-Severity Inconsistencies

### C11 - Source order excludes advisor distillation

Status: confirmed.

Conflicting sources:

- `source_order.md` lists roadmap/questions/memory, glossary, ideas, proposal,
  seminar evidence, backlog, generated artifacts, references, and optional tool
  boundaries (`.agents/references/source_order.md:7`,
  `.agents/references/source_order.md:15`,
  `.agents/references/source_order.md:17`).
- It does not name `docs/typst/thesis/advisor_distillation.typ`, even though
  that file carries extensive current advisor-facing synthesis
  (`docs/typst/thesis/advisor_distillation.typ:132`,
  `docs/typst/thesis/advisor_distillation.typ:147`).

Recommended owner/fix:

- Owner: `.agents/references/source_order.md`.
- Add advisor distillation as derivative advisor-facing synthesis that must not
  override roadmap/questions/canonical memory.

### C12 - Docs slide command points only to seminar slides

Status: confirmed.

Conflicting sources:

- `docs/AGENTS.md:46` says Typst slides compile from
  `typst/seminar_slides/<file>.typ`.
- Current thesis/advisor slide sources live under `docs/typst/thesis_slides/`
  and `docs/typst/thesis/`
  (`docs/typst/thesis_slides/slides_thesis_outlook.typ:25`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:15`).

Recommended owner/fix:

- Owner: `docs/AGENTS.md` command index.
- Split commands for seminar slides, thesis slides, and advisor decks.

### C13 - M1 report is now present, but its status/version evidence conflicts

Status: ledger claim partially stale; live conflict confirmed.

Current local state:

- The file exists and is linked in nav (`docs/contents/thesis/m1_contract_report.qmd:1`,
  `docs/_quarto.yml:69`, `docs/_quarto.yml:120`), so the original "referenced
  as if it exists but M1 is TODO" claim is stale as a missing-file claim.
- The report is `status: current` (`docs/contents/thesis/m1_contract_report.qmd:5`)
  but contains blocked M1 exit rows
  (`docs/contents/thesis/m1_contract_report.qmd:29`,
  `docs/contents/thesis/m1_contract_report.qmd:30`,
  `docs/contents/thesis/m1_contract_report.qmd:31`,
  `docs/contents/thesis/m1_contract_report.qmd:32`).
- `todo-007` remains open and says no target-RRI/rollout/stochastic/Q_H scale-up
  before the report is passable (`.agents/todos.toml:99`,
  `.agents/todos.toml:102`).
- New verified contradiction: the M1 report says "manifest v7" in the status row
  but "version = 6" in the evidence row, while code expects version 7
  (`docs/contents/thesis/m1_contract_report.qmd:29`,
  `docs/contents/thesis/m1_contract_report.qmd:43`,
  `aria_nbv/aria_nbv/data_handling/_offline_store.py:33`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/m1_contract_report.qmd` owns M1 evidence status;
  `.agents/todos.toml` owns open work until agents-db closes it.
- Keep the report in nav, but make status explicit as "current blocked report"
  or equivalent. Fix the manifest version inconsistency before using it as M1
  evidence.

### C14 - Scale is both RQ5 and shared protocol

Status: confirmed.

Conflicting sources:

- Canonical questions define RQ5 as scaling beyond small trusted subsets
  (`docs/contents/thesis/questions.qmd:455`), while also saying coverage
  reporting remains cross-cutting protocol
  (`docs/contents/thesis/questions.qmd:531`).
- Advisor deck treats RQ4 as "Support + Scale Controls"
  (`docs/typst/thesis/advisor_meeting_2026_05_22.typ:153`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:277`).
- Debrief says scale was moved into shared evidence protocol and later into
  compact RQ4 support/scale
  (`.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:35`,
  `.agents/memory/history/2026/05/2026-05-21_advisor_meeting_slide_deck.md:37`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/questions.qmd`.
- Keep scale as RQ5 and state that scale reporting is also cross-cutting
  evidence protocol. Decks may compress visual groups but not renumber RQs.

## Implementation-Vs-Document Wording

### C15 - Q_H not implemented vs detailed architectural claims

Status: confirmed as wording-risk, not a direct factual contradiction when read
carefully.

Conflicting sources:

- Canonical state says Q_H is not implemented yet and rollout data/storage are
  prerequisites (`.agents/memory/state/PROJECT_STATE.md:25`).
- Questions/roadmap say Q_H is first implemented as candidate-query Transformer
  and is mandatory thesis core (`docs/contents/thesis/questions.qmd:47`,
  `docs/contents/thesis/questions.qmd:382`,
  `docs/contents/thesis/roadmap.qmd:60`,
  `docs/contents/thesis/roadmap.qmd:523`).
- Advisor distillation uses design language around residual/dueling Q_H and set
  interactions (`docs/typst/thesis/advisor_distillation.typ:406`,
  `docs/typst/thesis/advisor_distillation.typ:523`,
  `docs/typst/thesis/advisor_distillation.typ:551`).

Recommended owner/fix:

- Owner: `.agents/memory/state/PROJECT_STATE.md` owns implementation status;
  questions/roadmap own planned thesis contract; advisor distillation is
  derivative.
- Add labels in derivative docs: implemented, planned first implementation,
  candidate ablation.

### C16 - Candidate family vocabulary differs

Status: confirmed.

Conflicting sources:

- Canonical questions list `TARGET_POINT`, `RADIAL_AWAY`, `RADIAL_TOWARDS`,
  `FORWARD_RIG`, plus `UNIFORM_SPHERE` and `FORWARD_POWERSPHERICAL`
  (`docs/contents/thesis/questions.qmd:316`,
  `docs/contents/thesis/questions.qmd:318`,
  `docs/contents/thesis/questions.qmd:320`,
  `docs/contents/thesis/questions.qmd:321`).
- Code owns enums for view modes, sampling strategies, and position modes
  (`aria_nbv/aria_nbv/pose_generation/types.py:33`,
  `aria_nbv/aria_nbv/pose_generation/types.py:55`,
  `aria_nbv/aria_nbv/pose_generation/types.py:63`,
  `aria_nbv/aria_nbv/pose_generation/types.py:66`,
  `aria_nbv/aria_nbv/pose_generation/types.py:69`,
  `aria_nbv/aria_nbv/pose_generation/types.py:78`,
  `aria_nbv/aria_nbv/pose_generation/types.py:80`).
- Current mixture code and backlog use production component names
  `forward_local`, `target_bearing_local`, `lateral_target_bypass`
  (`aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:18`,
  `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:153`,
  `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:161`,
  `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:169`,
  `.agents/todos.toml:253`,
  `.agents/todos.toml:1007`).
- Readiness evidence says one probe collapsed to `forward_local`
  (`.agents/todos.toml:1128`, `.agents/todos.toml:1198`).

Recommended owner/fix:

- Owner: code enums/configs own machine vocabulary; a generated or manually
  maintained candidate-family registry should map aliases for docs.
- Add a registry table that distinguishes view-direction modes, position modes,
  mixture component names, and production/ablation profiles.

## Redundancy Hotspots

### R1 - Thesis spine duplicated across many surfaces

Status: confirmed.

Sources:

- Canonical spine in questions/roadmap/memory
  (`docs/contents/thesis/questions.qmd:15`,
  `docs/contents/thesis/questions.qmd:92`,
  `docs/contents/thesis/roadmap.qmd:18`,
  `.agents/memory/state/PROJECT_STATE.md:17`,
  `.agents/memory/state/DECISIONS.md:269`).
- Duplicated in advisor distillation, proposal, and advisor deck
  (`docs/typst/thesis/advisor_distillation.typ:132`,
  `docs/typst/thesis/advisor_distillation.typ:138`,
  `docs/typst/thesis/sections/proposal/03-objectives.typ:8`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:109`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/questions.qmd` for compact thesis contract,
  `docs/contents/thesis/roadmap.qmd` for timeline, memory for current state.
- Make derivative docs explicitly render/summarize those owners.

### R2 - Milestone schedule duplicated

Status: confirmed, partly already mitigated in proposal.

Sources:

- Roadmap owns milestone timeline (`docs/contents/thesis/roadmap.qmd:339`).
- Proposal schedule says roadmap owns the detailed Gantt chart
  (`docs/typst/thesis/sections/proposal/05-schedule.typ:7`), but still carries
  milestone exits.
- Advisor distillation also carries schedule/timeline content
  (`docs/typst/thesis/advisor_distillation.typ:725`,
  `docs/typst/thesis/advisor_distillation.typ:735`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/roadmap.qmd`.
- Keep proposal/advisor schedule as short derivative summaries only.

### R3 - Policy ladder duplicated

Status: confirmed.

Sources:

- Advisor deck has matched policy ladder
  (`docs/typst/thesis/advisor_meeting_2026_05_22.typ:414`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:423`).
- Advisor distillation has policy comparison
  (`docs/typst/thesis/advisor_distillation.typ:635`,
  `docs/typst/thesis/advisor_distillation.typ:647`).
- Proposal method has a canonical comparison table
  (`docs/typst/thesis/sections/proposal/04-method.typ:164`,
  `docs/typst/thesis/sections/proposal/04-method.typ:196`).

Recommended owner/fix:

- Owner: a shared Typst snippet or canonical theory QMD should define the policy
  ladder; proposal/deck/handout should import or summarize it.

### R4 - Target leakage boundary duplicated

Status: confirmed, but mostly consistent.

Sources:

- Canonical questions define V0/V1 target contract
  (`docs/contents/thesis/questions.qmd:104`,
  `docs/contents/thesis/questions.qmd:230`,
  `docs/contents/thesis/questions.qmd:248`,
  `docs/contents/thesis/questions.qmd:249`,
  `docs/contents/thesis/questions.qmd:330`,
  `docs/contents/thesis/questions.qmd:331`).
- Roadmap repeats V0/V1
  (`docs/contents/thesis/roadmap.qmd:52`,
  `docs/contents/thesis/roadmap.qmd:454`,
  `docs/contents/thesis/roadmap.qmd:456`,
  `docs/contents/thesis/roadmap.qmd:607`).
- Advisor/proposal/deck repeat the same boundary
  (`docs/typst/thesis/advisor_distillation.typ:224`,
  `docs/typst/thesis/sections/proposal/02-problem.typ:59`,
  `docs/typst/thesis/sections/proposal/03-objectives.typ:16`,
  `docs/typst/thesis/advisor_meeting_2026_05_22.typ:266`).

Recommended owner/fix:

- Owner: `docs/contents/thesis/questions.qmd` currently owns target/RQ
  semantics. If duplication continues, create `docs/contents/thesis/target_contract.qmd`
  as a canonical target-contract page and make the other docs summarize it.

## Recommended Cleanup Order

1. Fix hard current-truth contradictions: C1, C2, C3, C5, C9.
2. Mark old thesis outlook slides historical or remove them from current nav:
   C4, C6, C7, C9.
3. Fix M1 report evidence/status: C13, including the manifest version conflict.
4. Add role headers/source-order entries for derivative documents: C10, C11.
5. Add shared registry/snippets to prevent recurrent drift: C16, R1-R4.

## Validator Notes

The original C13 claim was stale in one respect: `m1_contract_report.qmd` now
exists and is linked. The verified current issue is that it is a current,
blocked report with an internal manifest-version contradiction and an open
agents-db TODO.
