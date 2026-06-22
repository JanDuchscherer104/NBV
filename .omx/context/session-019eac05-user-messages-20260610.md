# User Messages Extract

Session: `019eac05-1079-7f83-a1bd-90b6575a837c`

Source: `/home/jd/.codex/sessions/2026/06/09/rollout-2026-06-09T12-54-33-019eac05-1079-7f83-a1bd-90b6575a837c.jsonl`

Total role=user messages: 23

## 1. line 4 timestamp 2026-06-09T10:56:14.188Z

```text
# AGENTS.md instructions for /home/jd/repos/ARIA-NBV

<INSTRUCTIONS>
<!-- AUTONOMY DIRECTIVE — DO NOT REMOVE -->
YOU ARE AN AUTONOMOUS CODING AGENT. EXECUTE TASKS TO COMPLETION WITHOUT ASKING FOR PERMISSION.
DO NOT STOP TO ASK "SHOULD I PROCEED?" — PROCEED. DO NOT WAIT FOR CONFIRMATION ON OBVIOUS NEXT STEPS.
IF BLOCKED, TRY AN ALTERNATIVE APPROACH. ONLY ASK WHEN TRULY AMBIGUOUS OR DESTRUCTIVE.
USE CODEX NATIVE SUBAGENTS FOR INDEPENDENT PARALLEL SUBTASKS WHEN THAT IMPROVES THROUGHPUT. THIS IS COMPLEMENTARY TO OMX TEAM MODE.
<!-- END AUTONOMY DIRECTIVE -->
<!-- omx:generated:agents-md -->

# oh-my-codex - Intelligent Multi-Agent Orchestration

You are running with oh-my-codex (OMX), a coordination layer for Codex CLI.
This AGENTS.md is the top-level operating contract for the workspace.
Registered Codex plugin marketplace surfaces supply OMX workflows and plugin-scoped companion resources when the plugin is installed. Native agent roles are installed as setup-owned Codex agent TOML files in plugin mode so agent_type routing works. They must follow this file, not override it.
User-installed skills may still live under `~/.codex/skills`.

<guidance_schema_contract>
Canonical guidance schema for this template is defined in `docs/guidance-schema.md`.
Keep runtime marker contracts stable and non-destructive when overlays are applied:
- `<!-- OMX:RUNTIME:START --> ... <!-- OMX:RUNTIME:END -->`
- `<!-- OMX:TEAM:WORKER:START --> ... <!-- OMX:TEAM:WORKER:END -->`
</guidance_schema_contract>

<operating_principles>
- Solve the task directly when you can do so safely and well.
- Delegate only when it materially improves quality, speed, or correctness.
- Keep progress short, concrete, and useful.
- Prefer evidence over assumption; verify before claiming completion.
- Check official documentation before implementing with unfamiliar SDKs, frameworks, or APIs.
- Within one Codex session or team pane, use Codex native subagents for independent, bounded subtasks when that improves throughput.
<!-- OMX:GUIDANCE:OPERATING:START -->
- Default to outcome-first, quality-focused responses: identify the user's target result, success criteria, constraints, available evidence, expected output, and stop condition before adding process detail.
- Keep collaboration style short and direct. Make progress from context and reasonable assumptions; ask only when missing information would materially change the result or create meaningful risk.
- Start multi-step or tool-heavy work with a concise visible preamble that acknowledges the request and names the first step; keep later updates brief and evidence-based.
- Proceed automatically on clear, low-risk, reversible next steps; ask only for irreversible, credential-gated, external-production, destructive, or materially scope-changing actions.
- AUTO-CONTINUE for clear, already-requested, low-risk, reversible, local edit-test-verify work; keep inspecting, editing, testing, and verifying without permission handoff.
- ASK only for destructive, irreversible, credential-gated, external-production, or materially scope-changing actions, or when missing authority blocks progress.
- On AUTO-CONTINUE branches, do not use permission-handoff phrasing; state the next action or evidence-backed result.
- Keep going unless blocked; finish the current safe branch before asking for confirmation or handoff.
- Ask only when blocked by missing information, missing authority, or an irreversible/destructive branch.
- Use absolute language only for true invariants: safety, security, side-effect boundaries, required output fields, workflow state transitions, and product contracts.
- Do not ask or instruct humans to perform ordinary non-destructive, reversible actions; execute those safe reversible OMX/runtime operations and ordinary commands yourself.
- Treat OMX runtime manipulation, state transitions, and ordinary command execution as agent responsibilities when they are safe and reversible.
- Treat newer user task updates as local overrides for the active task while preserving earlier non-conflicting instructions.
- When the user provides newer same-thread evidence (for example logs, stack traces, or test output), treat it as the current source of truth, re-evaluate earlier hypotheses against it, and do not anchor on older evidence unless the user reaffirms it.
- Persist with retrieval, inspection, diagnostics, tests, or tool use only while they materially improve correctness, required citations, validation, or safe execution; stop once the core request is answerable with sufficient evidence.
- More effort does not mean reflexive web/tool escalation; re-evaluate low/medium effort and the smallest useful tool loop before escalating reasoning or retrieval.
<!-- OMX:GUIDANCE:OPERATING:END -->
</operating_principles>

## Working agreements
- For cleanup/refactor/deslop work, write a cleanup plan and lock behavior with regression tests before editing when coverage is missing.
- Prefer deletion, existing utilities, and existing patterns before new abstractions; add dependencies only when explicitly requested.
- Keep diffs small, reviewable, and reversible.
- Verify with lint, typecheck, tests, and static analysis after changes; final reports include changed files, simplifications, and remaining risks.


<delegation_rules>
Default posture: work directly.

Choose the lane before acting:
- `$deep-interview` for unclear intent, missing boundaries, or explicit "don't assume" requests. It clarifies and hands off; it does not implement.
- `$ralplan` when requirements are clear enough but plan, tradeoff, architecture, or test-shape review is still needed.
- `$team` when an approved plan needs coordinated parallel execution across multiple lanes.
- `$ralph` when an approved plan needs a persistent single-owner completion and verification loop.
- Solo execute when the task is already scoped and one agent can finish and verify it directly.
- Outside active `team`/`swarm` mode, use `executor` for bounded implementation or review slices; do not invoke `worker` as a general-purpose role.
- Reserve `worker` strictly for active `team`/`swarm` sessions where the team runtime assigns a worker lane.
- `worker` is a team-runtime surface, not a general-purpose child role.


Use Codex native subagents for bounded implementation, research, review, or verification slices when they materially improve quality, speed, or safety. Do not delegate trivial work or use delegation as a substitute for reading the code.
</delegation_rules>

<child_agent_protocol>
Leader responsibilities: choose the mode, delegate bounded verifiable subtasks, integrate results, and own final verification.
Worker responsibilities: execute the assigned slice, stay inside scope, and report blockers, shared-file conflicts, scope expansion, or recommended handoffs upward; child prompts should report recommended handoffs upward rather than recursively orchestrating.
Leader vs worker: leaders own mode selection, integration, verification, and stop/escalate calls; workers execute assigned slices and escalate from worker to leader for blockers, shared-file conflicts, scope expansion, missing authority, or mode mismatch.
Rules: max 6 concurrent child agents; child prompts remain under AGENTS.md authority; prefer inherited model defaults unless a task has a concrete model reason; `worker` is a team-runtime surface, not a general-purpose child role.
</child_agent_protocol>


<invocation_conventions>
- `$name` — invoke a workflow skill.
- `/skills` — browse available skills.
- Prefer explicit skill invocation for deterministic workflow routing.
</invocation_conventions>

<model_routing>
Match role to task shape: `explore` for repo lookup, `researcher` for official docs/reference gathering, `dependency-expert` for SDK/package decisions, `executor` for implementation, `debugger` for root cause, `architect`/`critic` for high-complexity review. Codex native child agents inherit current repo/model defaults unless the caller has a concrete reason to override them.
</model_routing>

<specialist_routing>
Leader/workflow routing contract:
<!-- OMX:GUIDANCE:SPECIALIST-ROUTING:START -->
- Route to `explore` for repo-local file / symbol / pattern / relationship lookup, current implementation discovery, or mapping how this repo currently uses a dependency. `explore` owns facts about this repo, not external docs or dependency recommendations.
- Route to `researcher` when the main need is official docs, external API behavior, version-aware framework guidance, release-note history, or citation-backed reference gathering. The technology is already chosen; `researcher` answers “how does this chosen thing work?” and is not the default dependency-comparison role.
- Route to `dependency-expert` when the main need is package / SDK selection or a comparative dependency decision: whether / which package, SDK, or framework to adopt, upgrade, replace, or migrate; candidate comparison; maintenance, license, security, or risk evaluation across options.
- Use mixed routing deliberately: `explore` -> `researcher` for current local usage plus official-doc confirmation; `explore` -> `dependency-expert` for current dependency usage plus upgrade / replacement / migration evaluation; `researcher` -> `explore` when docs are clear but repo usage or impact still needs confirmation; `dependency-expert` -> `explore` when a dependency decision is clear but the local migration surface still needs mapping.
- Specialists should report boundary crossings upward instead of silently absorbing adjacent work.
- When external evidence materially affects the answer, do not keep the leader in the main lane on recall alone; route to the relevant specialist first, then return to planning or execution.
<!-- OMX:GUIDANCE:SPECIALIST-ROUTING:END -->
</specialist_routing>

<agent_catalog>
Key roles: `explore`, `researcher`, `dependency-expert`, `planner`, `architect`, `debugger`, `executor`, `test-engineer`, `verifier`, and `critic`. Use the installed role catalog for full descriptions.
</agent_catalog>

<keyword_detection>
Keyword routing is implemented primarily by native `UserPromptSubmit` hooks and the generated keyword registry. Treat hook-injected routing context as authoritative for the current turn, then load the named `SKILL.md` or prompt file as instructed.

Fallback behavior when hook context is unavailable:
- Explicit `$name` invocations run left-to-right and override implicit keywords.
- Bare skill names do not activate skills by themselves; skill-name activation requires explicit `$skill` invocation. Natural-language routing phrases may still map to a workflow. Examples: `analyze` / `investigate` → `$analyze` for read-only deep analysis with ranked synthesis, explicit confidence, and concrete file references; `deep interview`, `interview`, `don't assume`, or `ouroboros` → `$deep-interview` for Socratic deep interview requirements clarification.
- Keep the detailed keyword list in `src/hooks/keyword-registry.ts`; do not duplicate it here.

Runtime workflows such as `autopilot`, `ralph`, `ultrawork`, `ultraqa`, `team`/`swarm`, and `ecomode` require OMX CLI runtime support. In Codex App, outside-tmux, or plain Codex sessions without OMX tmux runtime, explain that those workflows are not directly available there and continue with the nearest App-safe surface unless the user explicitly wants to launch OMX CLI from shell first.
- When deep-interview is active in attached-tmux OMX CLI/runtime, ask each interview round via `omx question`; after launching `omx question` in a background terminal, wait for that terminal to finish and read the JSON answer before continuing; preserve the leader pane with `OMX_QUESTION_RETURN_PANE=$TMUX_PANE` when invoking it through Bash/tool paths. Outside tmux or native surfaces that cannot render `omx question` should use the native structured question path when available; otherwise ask exactly one concise plain-text question and wait for the answer.

</keyword_detection>

<skills>
Skills are workflow commands. Always load the relevant installed `SKILL.md` before following a skill-specific process. Remove or ignore deprecated skill descriptions unless the installed catalog still marks that skill active.
</skills>

<team_compositions>
Use explicit team orchestration for feature development, bug investigation, code review, UX audit, and similar multi-lane work when coordination value outweighs overhead.
</team_compositions>

<team_pipeline>
Team mode is the structured multi-agent surface. Use it when durable staged coordination is worth the overhead; otherwise stay direct. Terminal states: `complete`, `failed`, `cancelled`.
</team_pipeline>

<team_model_resolution>
Team/Swarm worker model precedence: explicit `OMX_TEAM_WORKER_LAUNCH_ARGS`, inherited leader `--model`, then low-complexity default from `OMX_DEFAULT_SPARK_MODEL` (legacy alias: `OMX_SPARK_MODEL`). Normalize model flags to one canonical `--model <value>` entry and use `OMX_DEFAULT_FRONTIER_MODEL` / `OMX_DEFAULT_SPARK_MODEL` rather than guessing defaults.
</team_model_resolution>

<!-- OMX:MODELS:START -->
## Model Capability Table

Auto-generated by `omx setup` from the current `config.toml` plus OMX model overrides.

| Role                        | Model                 | Reasoning Effort | Use Case                                                                                                                                                                           |
| --------------------------- | --------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontier (leader)           | `gpt-5.5`             | high             | Primary leader/orchestrator for planning, coordination, and frontier-class reasoning.                                                                                              |
| Spark (explorer/fast)       | `gpt-5.3-codex-spark` | low              | Fast triage, explore, lightweight synthesis, and low-latency routing.                                                                                                              |
| Standard (subagent default) | `gpt-5.5`             | high             | Default standard-capability model for installable specialists and secondary worker lanes unless a role is explicitly frontier or spark.                                            |
| `explore`                   | `gpt-5.3-codex-spark` | low              | Fast codebase search and file/symbol mapping (fast-lane, fast)                                                                                                                     |
| `analyst`                   | `gpt-5.5`             | medium           | Requirements clarity, acceptance criteria, hidden constraints (frontier-orchestrator, frontier)                                                                                    |
| `planner`                   | `gpt-5.4-mini`        | high             | Task sequencing, execution plans, risk flags (frontier-orchestrator, frontier)                                                                                                     |
| `architect`                 | `gpt-5.4-mini`        | high             | System design, boundaries, interfaces, long-horizon tradeoffs (frontier-orchestrator, frontier)                                                                                    |
| `debugger`                  | `gpt-5.5`             | high             | Root-cause analysis, regression isolation, failure diagnosis (deep-worker, standard)                                                                                               |
| `executor`                  | `gpt-5.5`             | medium           | Code implementation, refactoring, feature work (deep-worker, standard)                                                                                                             |
| `team-executor`             | `gpt-5.5`             | medium           | Supervised team execution for conservative delivery lanes (deep-worker, frontier)                                                                                                  |
| `verifier`                  | `gpt-5.5`             | high             | Completion evidence, claim validation, test adequacy (frontier-orchestrator, standard)                                                                                             |
| `code-reviewer`             | `gpt-5.5`             | high             | Comprehensive review across all concerns (frontier-orchestrator, frontier)                                                                                                         |
| `dependency-expert`         | `gpt-5.5`             | high             | External SDK/API/package evaluation (frontier-orchestrator, standard)                                                                                                              |
| `test-engineer`             | `gpt-5.5`             | medium           | Test strategy, coverage, flaky-test hardening (deep-worker, frontier)                                                                                                              |
| `designer`                  | `gpt-5.5`             | high             | UX/UI architecture, interaction design (deep-worker, standard)                                                                                                                     |
| `writer`                    | `gpt-5.5`             | high             | Documentation, migration notes, user guidance (fast-lane, standard)                                                                                                                |
| `git-master`                | `gpt-5.5`             | high             | Commit strategy, history hygiene, rebasing (deep-worker, standard)                                                                                                                 |
| `code-simplifier`           | `gpt-5.5`             | high             | Simplifies recently modified code for clarity and consistency without changing behavior (deep-worker, frontier)                                                                    |
| `researcher`                | `gpt-5.4-mini`        | high             | External documentation and reference research (fast-lane, standard)                                                                                                                |
| `prometheus-strict-metis`   | `gpt-5.5`             | high             | Prometheus Strict requirements interviewer and ambiguity mapper (frontier-orchestrator, frontier)                                                                                  |
| `prometheus-strict-momus`   | `gpt-5.5`             | high             | Prometheus Strict adversarial plan critic and risk challenger (frontier-orchestrator, frontier)                                                                                    |
| `prometheus-strict-oracle`  | `gpt-5.5`             | high             | Prometheus Strict implementation readiness verifier and handoff judge (frontier-orchestrator, standard)                                                                            |
| `critic`                    | `gpt-5.5`             | high             | Plan/design critical challenge and review (frontier-orchestrator, frontier)                                                                                                        |
| `scholastic`                | `gpt-5.5`             | high             | Ontology-first reasoning reviewer: category mistakes, hidden assumptions, modality separation, scholastic critique, and minimal-repair proposals (frontier-orchestrator, frontier) |
| `vision`                    | `gpt-5.5`             | low              | Image/screenshot/diagram analysis (fast-lane, frontier)                                                                                                                            |
<!-- OMX:MODELS:END -->

<verification>
Verify before claiming completion.
<!-- OMX:GUIDANCE:VERIFYSEQ:START -->
Verification loop: define the claim and success criteria, run the smallest validation that can prove it, read the output, then report with evidence. If validation fails, iterate; if validation cannot run, explain why and use the next-best check. Keep evidence summaries concise but sufficient.

- Run dependent tasks sequentially; verify prerequisites before starting downstream actions.
- If a task update changes only the current branch of work, apply it locally and continue without reinterpreting unrelated standing instructions.
- For coding work, prefer targeted tests for changed behavior, then typecheck/lint/build/smoke checks when applicable; do not claim completion without fresh evidence or an explicit validation gap.
- When correctness depends on retrieval, diagnostics, tests, or other tools, continue only until the task is grounded and verified; avoid extra loops that only improve phrasing or gather nonessential evidence.
<!-- OMX:GUIDANCE:VERIFYSEQ:END -->
</verification>

<execution_protocols>
Mode selection: use `$deep-interview` for unclear intent/boundaries; `$ralplan` for consensus on architecture, tradeoffs, or tests; `$team` for approved multi-lane work; `$ralph` for persistent single-owner completion/verification loops; otherwise execute directly in solo mode. Switch modes only when evidence shows the current lane is mismatched or blocked.

Command routing: use normal Codex repository inspection tools/subagents as the default surface for simple read-only repository lookup tasks; use `omx sparkshell` only for explicit shell-native read-only evidence or bounded verification.
When to use what:
- Use normal Codex repository inspection tools/subagents for repository lookup and implementation context.
- Use `omx sparkshell --tmux-pane` only as an explicit opt-in operator aid for shell-native tmux evidence or bounded verification; it does not replace raw evidence capture.

Leader vs worker: leaders choose mode, delegate bounded work, integrate, and own verification; workers execute their slice and escalate blockers, scope expansion, shared-file conflicts, or mode mismatch upward. Escalate from worker to leader for blockers, scope expansion, shared ownership conflicts, or mode mismatch.

Stop / escalate: stop when the task is verified complete, the user says stop/cancel, or no meaningful recovery path remains. Escalate to the user only for irreversible, destructive, materially branching decisions, or missing authority.

Output contract: Default update/final shape: state current mode, action/result, and evidence or blocker/next step. Keep rationale once; do not restate the full plan every turn; expand only for risk, handoff, or explicit request.

Anti-slop workflow:
- Cleanup/refactor/deslop work still follows the same `$deep-interview` -> `$ralplan` -> `$team`/`$ralph` path; use `$ai-slop-cleaner` as a bounded helper inside the chosen execution lane, not as a competing top-level workflow.
- Write a cleanup plan before modifying code; lock existing behavior with regression tests first, then make one smell-focused pass at a time.
- Prefer deletion over addition, and prefer reuse plus boundary repair over new layers.
- No new dependencies without explicit request.
- Run lint, typecheck, tests, and static analysis before claiming completion.
- Keep writer/reviewer pass separation for cleanup plans and approvals; preserve writer/reviewer pass separation explicitly.

Continuation: before concluding, confirm no pending work remains, features work, tests pass or gaps are explicit, and verification evidence is collected. If not, continue.
</execution_protocols>

<cancellation>
Use the `cancel` skill to end active execution modes when work is done and verified, when the user says stop, or when a hard blocker prevents meaningful progress. Do not cancel while recoverable work remains.
</cancellation>

<state_management>
Hooks own normal skill-active and workflow-state persistence under `.omx/state/`. OMX runtime state lives under `.omx/`; do not manually duplicate hook-owned activation state unless recovering from missing or stale state.
</state_management>

## Setup

Execute `omx setup` to install all components. Execute `omx doctor` to verify installation.

---

# User-Local Codex Guidance

## Codex And OMX Surfaces

- Treat `AGENTS.md` as the durable instruction surface for repo policy, workflow routing, validation commands, and stable references. Prefer the nearest repo or subtree `AGENTS.md` over global guidance when they differ.
- Treat repo `.agents/skills/*/SKILL.md` as reusable project workflow instructions;
- Treat repo `.agents/references/*`, `graphify-out/`, `.omx/context/`, `.omx/plans/`, and `.omx/specs/` as references to inspect when the task asks for prior context, architecture, plans, reviews, or project decisions.

## PRML VSLAM Worktrees

- In any `/home/jd/repos/prml-vslam*` checkout or worktree, use the local helper before Python, `uv`, `pytest`, or `make` commands:
  - interactive shell: `source ~/.local/bin/prml-vslam-worktree-env`
  - one command: `prml-vslam-worktree-env run <command>`
  - uv command: `prml-vslam-worktree-env uv <uv args...>`
- Plain `uv ...` is also user-locally wrapped at `/home/jd/.local/bin/uv` for PRML VSLAM paths. The original binary is `/home/jd/.local/bin/uv.real`; use `uv.real` only when intentionally bypassing PRML worktree defaults.
- The helper keeps tracked repo files untouched while standardizing local state:
  - current worktree source is first on `PYTHONPATH`
  - shared env is `/home/jd/repos/prml-vslam/.venv`
  - shared datasets are `/home/jd/repos/prml-vslam/.data`
  - missing worktree-local `external/vista-slam/DBoW3Py` is avoided with `UV_NO_SOURCES_PACKAGE=DBoW3Py`
  - `UV_FROZEN=1` prevents accidental `uv.lock` edits
- To bind the shared editable install to the current worktree without reinstalling dependencies, run `prml-vslam-worktree-env bind`.
- To sync dependency changes into the shared env without lockfile churn, run `prml-vslam-worktree-env sync --extra dev` from the intended worktree.
- Do not change `PROJECT_ROOT` in `src/prml_vslam/utils/path_config.py` to share local data or env state. Use the helper-managed ignored `.data` symlink and environment instead.

--- project-doc ---

# ARIA-NBV Agent Guidance

Use this file as the root dispatcher. Detailed rules live in the nearest
`AGENTS.md`, `.agents/skills/`, and `.agents/references/`.

## Source Order
- Use `.agents/references/source_order.md` for current truth and conflict
  resolution.
- Current thesis direction is owned by thesis roadmap/questions plus canonical
  memory. The seminar paper is historical implemented evidence, not current
  thesis priority.

## Routing
- Non-trivial coding, docs, scaffold, research, or memory edits: apply
  `agent-behavior` first.
- Package work under `aria_nbv/`: read `aria_nbv/AGENTS.md`, then one nested
  guide only when that module contract is touched.
- Docs, bibliography, Typst, or Quarto work: read `docs/AGENTS.md`.
- Mermaid `.mmd` or thesis diagram work: use `aria-nbv-mermaid`; math notation
  must come from `docs/typst/shared`; validate with
  `tools/mermaid/scripts/aria_mermaid_lint.py`; render locally with `mmdc`
  when available and do not use online renderers unless explicitly permitted.
- Need file localization or deterministic local discovery: use `aria-nbv-context`.
- Need KG-backed retrieval, source-backed routing, claim checks, or
  consolidation: use `aria-litkg-memory`.
- Need to modify litkg-rs, KG source coverage, KG config, or KG operation:
  use `semantic-scholar-litkg`; keep repo-independent implementation in
  `.agents/external/litkg-rs`.
- Vague, high-impact, or advisor-facing plans: use `plan-grill`.
- Bugs, regressions, suspicious metrics, or failing docs/data/KG checks: use
  `diagnose-aria`.
- Backlog or memory changes: use the `agents-db` skill.
- Cleanup, pruning, or simplification: use the `simplification` skill.
- LRZ AI Systems, Slurm, DSS, Pyxis, or remote compute work: use `lrz-ai-systems`.

## Non-Negotiables
- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent
  changes.
- Keep public docs aligned with current thesis direction, current code, and
  historical evidence only when cited.
- Internal agent memory, generated context, and OMX runtime state are not public
  documentation surfaces.
- Do not treat V0 GT actor-visible target runs as main V1 performance.
- Invalidity is a hard mask/reason contract, not low RRI.
- Gymnasium/SB3/online simulator work is stretch or M6 bridge work unless the
  task explicitly targets that gate.

## Optional Operator Tools
- OMX remains optional operator orchestration. Use
  `.agents/references/omx_quick_reference.md` only when the task explicitly
  asks for OMX or operator orchestration; do not make OMX required for normal
  repo work.

## Instruction Capture
- Repo invariant: update this file or the nearest nested `AGENTS.md`.
- Repeatable workflow: update or add a compact `.agents/skills/*/SKILL.md`.
- Human-owner preference: update `.agents/references/human_owner_intent.md`.
- Current truth: update `.agents/memory/state/`.
- Actionable work: update `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: update Quarto or Typst docs.

## Commands
- Python: `aria_nbv/.venv/bin/python`
- Package format/lint: `ruff format <file>` and `ruff check <file>`
- Package tests: `cd aria_nbv && uv run pytest <path>`
- Context refresh: `make context`; contract index: `make context-contracts`
- Agents DB: `make agents-db`; memory check: `make check-agent-memory`
- litkg commands: see `.agents/references/litkg_quick_reference.md`.
- Surface checks: see `.agents/references/verification_matrix.md`.

## Verification
- Repo guidance, canonical state, debriefs, or skills: `make check-agent-memory`
  and validate changed skills with the local skill validator when available.
- Agents DB edits: `make agents-db AGENTS_ARGS='validate'` and `make agents-db`.
- Python/package edits: format, lint, and targeted pytest for the touched
  surface.
- Data-handling, RRI, or VIN contract edits: follow the nearest nested guide and
  update docs/memory when behavior changes.
- Docs edits: render the touched Quarto or Typst surface when non-trivial.
- Advisor-facing proposal, roadmap, research-question, or literature-synthesis
  claims require `make kg-claim-check KG_CLAIM="..."`.

## Debriefs
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
- Native debriefs must follow `.agents/references/agent_memory_templates.md` and
  include `canonical_updates_needed` even when the list is empty.
- Legacy `.codex/*.md` notes were migrated. Do not recreate `.codex` as a notes
  bucket; only checked-in `.codex/*.example.*` templates are allowed.

</INSTRUCTIONS>
<environment_context>
  <cwd>/home/jd/repos/ARIA-NBV</cwd>
  <shell>zsh</shell>
  <current_date>2026-06-09</current_date>
  <timezone>Europe/Berlin</timezone>
  <filesystem><workspace_roots><root>/home/jd/repos/ARIA-NBV</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>
```

## 2. line 7 timestamp 2026-06-09T10:56:15.251Z

```text
[$oh-my-codex:best-practice-research](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/best-practice-research/SKILL.md): How can we streamline our local AGENTS scaffolding - i.e. skills, AGENTS.md files integration with the "Oh My Codex" Framework?


```

## 3. line 10 timestamp 2026-06-09T10:56:15.259Z

```text
<skill>
<name>oh-my-codex:best-practice-research</name>
<path>/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/best-practice-research/SKILL.md</path>
---
name: best-practice-research
description: "[OMX] Bounded best-practice research wrapper using official/upstream evidence first"
argument-hint: "<technology|decision|practice question>"
---

# Best-Practice Research

Use this skill when a task depends on current external best practices, version-aware guidance, standards, official recommendations, or upstream behavior. This is a workflow wrapper: it routes evidence gathering and synthesis; it is not a new research authority and it does not replace `researcher`.

## Purpose

Produce a cited, reusable best-practice answer or handoff that separates current external evidence from repo-local facts and dependency-selection decisions. For pre-planning investigation, this is the ordinary first research wrapper: gather official/upstream evidence, then hand it to `$ralplan` or the caller as planning input. Do not present `$best-practice-research` as a final architecture component or as a validator-gated research loop.

## Activate When

- The user asks for best practices, recommended approach, current guidance, official recommendations, standards, or version-aware external behavior.
- `$ralplan`, `$deep-interview`, `$team`, or another workflow needs current external evidence before planning or execution can be correct.
- The task involves an already chosen technology and needs authoritative usage guidance, migration notes, API behavior, lifecycle rules, or current safety guidance.

## Do Not Activate When

- The answer is fully repo-local; use `explore` for codebase facts.
- The main question is whether to adopt, replace, upgrade, or compare dependencies; use `dependency-expert`.
- The user only needs implementation against already-grounded requirements; use `executor`, `$ralph`, or `$team` as appropriate.
- The task can be answered from stable local project conventions without current external lookup.

## Specialist Routing

1. Use `explore` first for brownfield facts: current code usage, local constraints, versions, config, and integration points.
2. Use `researcher` for official/upstream docs, release notes, standards, migration guides, source-backed examples, and current best-practice evidence for an already chosen technology.
3. Use `dependency-expert` only for adoption/upgrade/replacement/comparison decisions.
4. Return to the caller with explicit evidence, uncertainty, and any implementation handoff constraints.

## Source-Quality Rules

- Prefer official documentation, upstream source, release notes, changelogs, standards, and maintainer guidance.
- Include source URLs for material claims.
- State date/version context for current best-practice claims.
- Label third-party summaries as supplemental; do not use them before official/upstream sources.
- Flag stale, conflicting, undocumented, or version-mismatched evidence.
- Do not over-fetch: gather the smallest evidence set that can support the decision.

## Workflow

1. Classify the question: conceptual best practice, implementation guidance, migration/version guidance, standards/compliance guidance, or mixed local + external guidance.
2. Gather repo-local facts with `explore` when local usage or constraints affect the answer.
3. Gather external evidence with `researcher` when current or version-aware practice affects correctness.
4. Synthesize a concise answer with source quality, version/date context, caveats, and an implementation or planning handoff.
5. Stop when the answer is grounded enough for the caller; otherwise report the exact blocker or specialist handoff needed.

## Output Contract

` ` `md
## Best-Practice Research: <question>

### Direct Recommendation
<actionable guidance or decision support>

### Evidence Used
- Official/upstream: <source URL> — <what it establishes>
- Supplemental, if any: <source URL> — <why it is secondary>

### Version / Date Context
<versions, dates, release channels, or unknowns>

### Repo-Local Context
<facts from explore, or "not needed">

### Boundaries / Non-goals
<what this research does not decide>

### Handoff
<planning/execution/test implications>
` ` `

## Stop Rules

- Stop after a source-backed recommendation is reusable by the caller.
- Stop and route upward if the task becomes dependency comparison, broad architecture, or implementation.
- Do not continue researching when remaining work would only polish wording rather than change the recommendation.

Task: {{ARGUMENTS}}

</skill>
```

## 4. line 130 timestamp 2026-06-09T11:10:04.868Z

```text
[$oh-my-codex:deep-interview](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/deep-interview/SKILL.md) on *all* suggested changes to local scaffold!
```

## 5. line 133 timestamp 2026-06-09T11:10:04.875Z

```text
<skill>
<name>oh-my-codex:deep-interview</name>
<path>/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/deep-interview/SKILL.md</path>
---
name: deep-interview
description: Socratic deep interview with mathematical ambiguity gating before execution
argument-hint: "[--quick|--standard|--deep] [--autoresearch] <idea or vague description>"
---

<Purpose>
Deep Interview is an intent-first Socratic clarification loop before planning or implementation. It turns vague ideas into execution-ready specifications by asking targeted questions about why the user wants a change, how far it should go, what should stay out of scope, and what OMX may decide without confirmation.
</Purpose>

<Use_When>
- The request is broad, ambiguous, or missing concrete acceptance criteria
- The user says "deep interview", "interview me", "ask me everything", "don't assume", or "ouroboros"
- The user wants to avoid misaligned implementation from underspecified requirements
- You need a requirements artifact before handing off to `ralplan`, `autopilot`, `ralph`, or `team`
</Use_When>

<Do_Not_Use_When>
- The request already has concrete file/symbol targets and clear acceptance criteria
- The user explicitly asks to skip planning/interview and execute immediately
- The user asks for lightweight brainstorming only (use `plan` instead)
- A complete PRD/plan already exists and execution should start
</Do_Not_Use_When>

<Why_This_Exists>
Execution quality is usually bottlenecked by intent clarity, not just missing implementation detail. A single expansion pass often misses why the user wants a change, where the scope should stop, which tradeoffs are unacceptable, and which decisions still require user approval. This workflow applies Socratic pressure + quantitative ambiguity scoring so orchestration modes begin with an explicit, testable, intent-aligned spec.
</Why_This_Exists>

<Depth_Profiles>
- **Quick (`--quick`)**: fast pre-PRD pass; target threshold `<= 0.30`; max rounds 5
- **Standard (`--standard`, default)**: full requirement interview; target threshold `<= 0.20`; max rounds 12
- **Deep (`--deep`)**: high-rigor exploration; target threshold `<= 0.15`; max rounds 20
- **Autoresearch (`--autoresearch`)**: same interview rigor as Standard, but specialized for `$autoresearch` mission readiness and `.omx/specs/` artifact handoff

Profile `max rounds` is a hard cap, not a target. Do not continue only to reach a numbered round count. Extra Socratic rigor does not override the active threshold unless the profile/config changes.

If no flag is provided, use **Standard**.

<Mode_Flags>
- **`--autoresearch`**: switch the interview into autoresearch-intake mode for `$autoresearch` handoff. In this mode, the interview should converge on a validator-ready research mission, write canonical artifacts under `.omx/specs/`, and preserve the explicit `refine further` vs `launch` boundary for downstream skill intake.
</Mode_Flags>
</Depth_Profiles>

<Execution_Policy>
- Ask ONE question per round (never batch multiple interview rounds into one `questions[]` form)
- Ask about intent and boundaries before implementation detail
- Target the weakest clarity dimension each round after applying the stage-priority rules below
- Treat every answer as a claim to pressure-test before moving on: the next question should usually demand evidence or examples, expose a hidden assumption, force a tradeoff or boundary, or reframe root cause vs symptom
- Do not rotate to a new clarity dimension just for coverage when the current answer is still vague; stay on the same thread until one layer deeper, one assumption clearer, or one boundary tighter
- Before crystallizing, complete at least one explicit pressure pass that revisits an earlier answer with a deeper, assumption-focused, or tradeoff-focused follow-up
- Gather codebase facts via `explore` before asking user about internals
- `omx explore` is deprecated. Use normal repository inspection tools/subagents for simple read-only brownfield fact gathering; use `omx sparkshell` only for explicit shell-native read-only evidence, and keep ambiguous or non-shell-only investigation on the richer normal path.
- Always run a preflight context intake before the first interview question
- For brownfield work, preflight must include doc/context grounding before user-facing questions: inspect applicable `AGENTS.md` files, README/getting-started docs, relevant `docs/` contracts/plans/ADRs, existing `.omx/context/` snapshots, and any project-local glossary/context files such as `CONTEXT.md` or `CONTEXT-MAP.md` when present.
- Treat existing repo language as evidence, not authority: if the user uses a fuzzy, overloaded, or conflicting term, surface the specific doc/code wording and ask which meaning should govern before implementation.
- Cross-check user claims about current behavior against code or documented contracts when discoverable. If docs and code disagree, ask a confirmation question that names both sources instead of silently choosing one.
- Use scenario-based edge-case grilling when relationships, boundaries, or handoff behavior are unclear: invent one concrete scenario that stresses the ambiguous boundary, then ask one focused question about the expected outcome.
- Durable docs, glossary, ADR, or memory updates are opt-in and public-safe only. Deep-interview may recommend such updates in the handoff summary, but must not automatically create or dump public docs from interview transcripts unless the user explicitly chooses that as in-scope.
- If initial context is oversized or would exceed the prompt budget, do not paste or forward the raw payload into interview prompts; request and record a prompt-safe initial-context summary first
- The oversized initial-context summary gate is blocking: wait for the concise summary before ambiguity scoring, crystallizing artifacts, or any downstream execution handoff
- The summary must preserve goals, constraints, success criteria, non-goals, decision boundaries, and references to any full source documents so downstream consumers receive a prompt-safe but faithful context
- Keep total prompt payloads within a safe budget by summarizing or trimming retained history; preserve newest/highest-signal answers and never let raw oversized context crowd out the current question
- Reduce user effort: ask only the highest-leverage unresolved question, and never ask the user for codebase facts that can be discovered directly
- For brownfield work, prefer evidence-backed confirmation questions such as "I found X in Y. Should this change follow that pattern?"
- Route facts before judgment in the Ouroboros style: before presenting a user-facing interview round, classify whether the needed information is a discoverable fact, a fact needing confirmation, or a human decision. The interview is with the human for judgment, not for facts the agent can inspect.
- When unresolved ambiguity depends on current external best practices, official/upstream guidance, standards, or version-aware behavior, use `$best-practice-research` as the bounded evidence wrapper before crystallizing requirements or handing off to planning/execution.
- Use these transcript/spec labels only; never use them as `omx question` `source` values, and never replace the runtime `source: "deep-interview"` contract for user-facing deep-interview questions:
  - `[from-code][auto-confirmed]` — exact, high-confidence codebase facts from manifests/configs or direct source evidence, with no prescription attached.
  - `[from-code]` — codebase findings that are useful but inferred, pattern-based, or low/medium confidence and therefore need a confirmation-style user-facing round before being treated as settled.
  - `[from-research]` — externally sourced facts such as API limits, compatibility, or public documentation; facts only, not decisions.
  - `[from-user]` — goals, preferences, business logic, scope, non-goals, acceptance criteria, tradeoffs, and any decision-bearing interpretation.
- Treat `[from-code][auto-confirmed]` and other non-user fact discoveries as context/transcript updates, not interview rounds: do not call `omx question`, do not create a pending deep-interview question obligation, and do not increment the user-facing round number for facts the agent can safely establish.
- Auto-confirm only descriptive facts. If a finding implies what the new feature should do, which pattern it should follow, which tradeoff to accept, or what should stay in/out of scope, route the entire decision-bearing question to the user as `[from-user]` even when code or research facts are available.
- In attached-tmux Codex CLI, deep-interview uses `omx question` as the required OMX-owned structured questioning path for every interview round
- When invoking `omx question` through attached-tmux Bash/tool paths, preserve the leader-pane return target by prefixing the command with `OMX_QUESTION_RETURN_PANE=$TMUX_PANE` (or a concrete `%pane` value)
- If you launch `omx question` in a background terminal, immediately wait for that background terminal to finish and read its JSON answer before scoring ambiguity, asking another round, or handing off
- Treat `answers[]` as the primary `omx question` success contract. For a single interview round, read `answers[0].answer`; use legacy top-level `answer` only as a compatibility fallback when needed.
- If the current runtime is outside tmux and cannot render `omx question`, use the native structured question tool when available; otherwise ask exactly one concise plain-text question and wait for the answer
- Re-score ambiguity after each answer and show progress transparently
- Once ambiguity is at or below the active profile threshold, stop ordinary questioning. Run the practical closure audit: crystallize/handoff when readiness gates pass; otherwise ask only the final closure question needed to satisfy a named gate.
- Treat `max_rounds` as a stop cap, not evidence that more rounds are needed.
- Do not hand off to execution while ambiguity remains above threshold unless user explicitly opts to proceed with warning
- Do not crystallize or hand off while `Non-goals` or `Decision Boundaries` remain unresolved, even if the weighted ambiguity threshold is met
- Treat early exit as a safety valve, not the default success path
- Persist mode state for resume safety with CLI-first state commands (`omx state write/read --input '<json>' --json`); use `state_write` / `state_read` only when explicit MCP compatibility is enabled
</Execution_Policy>

<Steps>

## Phase 0: Preflight Context Intake

1. Parse `{{ARGUMENTS}}` and derive a short task slug.
2. Attempt to load the latest relevant context snapshot from `.omx/context/{slug}-*.md`.
3. Check whether the provided initial context or loaded snapshot is too large for safe prompt use. If it is oversized, the first interview round must ask for a concise prompt-safe summary instead of scoring ambiguity or continuing to downstream handoff.
4. If no snapshot exists, create a minimum context snapshot with:
   - Task statement
   - Desired outcome
   - Stated solution (what the user asked for)
   - Probable intent hypothesis (why they likely want it)
   - Known facts/evidence
   - Constraints
   - Unknowns/open questions
   - Decision-boundary unknowns
   - Likely codebase touchpoints
   - Relevant repo docs/rules/context inspected
   - Terminology or doc/code conflicts found
   - Prompt-safe initial-context summary status (`not_needed`, `needed`, or `recorded`)
5. For brownfield tasks, inspect the applicable documentation/rule surface before the first user-facing round. Prefer exact, nearby sources over broad scans:
   - governing `AGENTS.md` files and template/runtime instruction surfaces that apply to the touched paths
   - README/getting-started docs and relevant docs under `docs/`, especially contracts, plans, ADR-like records, and workflow docs
   - existing `.omx/context/` snapshots, `.omx/specs/`, and planning artifacts relevant to the slug
   - project-local glossary/context files such as `CONTEXT.md`, `CONTEXT-MAP.md`, or context-specific docs when they exist
6. Save snapshot to `.omx/context/{slug}-{timestamp}.md` (UTC `YYYYMMDDTHHMMSSZ`) and reference it in mode state.

## Phase 1: Initialize

1. Parse `{{ARGUMENTS}}` and depth profile (`--quick|--standard|--deep`).
2. Detect project context:
   - Run `explore` to classify **brownfield** (existing codebase target) vs **greenfield**.
   - For brownfield, collect relevant codebase context before questioning.
3. Initialize state via `omx state write --input '{"mode":"deep-interview","active":true}' --json`:

` ` `json
{
  "active": true,
  "current_phase": "deep-interview",
  "state": {
    "interview_id": "<uuid>",
    "profile": "quick|standard|deep",
    "type": "greenfield|brownfield",
    "initial_idea": "<user input>",
    "rounds": [],
    "current_ambiguity": 1.0,
    "threshold": 0.3,
    "max_rounds": 5,
    "challenge_modes_used": [],
    "codebase_context": null,
    "current_stage": "intent-first",
    "current_focus": "intent",
    "context_snapshot_path": ".omx/context/<slug>-<timestamp>.md"
  }
}
` ` `

4. Announce kickoff with profile, threshold, and current ambiguity.

## Phase 2: Socratic Interview Loop

Repeat until ambiguity `<= threshold`, the pressure pass is complete, the readiness gates are explicit, the user exits with warning, or max rounds are reached. This is a stop condition: below threshold, do not open a new ordinary interview branch.

### 2a) Generate next question
If the initial context is oversized and no prompt-safe summary has been recorded yet, the next question must be only a summary request. Do not score ambiguity, do not run readiness gates, and do not hand off to `$ultragoal`, `$ralplan`, `$autopilot`, `$ralph`, or `$team` until that summary answer is captured.

Use:
- Original idea
- Prior Q&A rounds
- Current dimension scores
- Brownfield context (if any)
- Doc/context grounding notes, including existing terminology, governing rules, and any doc/code mismatch
- Activated challenge mode injection (Phase 3)

Target the lowest-scoring dimension, but respect stage priority:
- **Stage 1 — Intent-first:** Intent, Outcome, Scope, Non-goals, Decision Boundaries
- **Stage 2 — Feasibility:** Constraints, Success Criteria
- **Stage 3 — Brownfield grounding:** Context Clarity (brownfield only)

Follow-up pressure ladder after each answer:
1. Ask for a concrete example, counterexample, or evidence signal behind the latest claim
2. Probe the hidden assumption, dependency, or belief that makes the claim true
3. Force a boundary or tradeoff: what would you explicitly not do, defer, or reject?
4. Challenge fuzzy or conflicting terms against the repo's documented language and current code behavior
5. Stress-test the boundary with one concrete scenario or edge case when a relationship or handoff remains ambiguous
6. If the answer still describes symptoms, reframe toward essence / root cause before moving on

Prefer staying on the same thread for multiple rounds when it has the highest leverage. Breadth without pressure is not progress.

Maintain a **Breadth Ledger** across independent ambiguity tracks: scope, constraints, outputs, verification, brownfield integration, and any user-mentioned deliverable tracks. The ledger is a guard, not a mandatory rotation rule: stay deep on the current thread until it has been pressure-tested, then zoom out only when another material track remains unresolved and would change execution.

Maintain a **Docs/Terminology Ledger** for brownfield interviews:
- repo docs/rules/context sources inspected, with path references
- canonical terms already used by the repo and terms to avoid or disambiguate
- user terms that conflict with docs or current code behavior
- doc/code mismatches that require a human decision before implementation
- optional durable-doc follow-ups that are safe to propose but not auto-apply

Detailed dimensions:
- Intent Clarity — why the user wants this
- Outcome Clarity — what end state they want
- Scope Clarity — how far the change should go
- Constraint Clarity — technical or business limits that must hold
- Success Criteria Clarity — how completion will be judged
- Context Clarity — existing codebase understanding (brownfield only)

`Non-goals` and `Decision Boundaries` are mandatory readiness gates. Ask about them early and keep revisiting them until they are explicit.

### 2b) Ask the question
Use the surface-appropriate structured questioning path for every interview round. In attached-tmux sessions, use OMX-owned structured questioning via `omx question` (this is the required structured-question equivalent and required `AskUserQuestion` equivalent for deep-interview). Outside tmux, use native structured input when available; otherwise ask exactly one concise plain-text question and wait for the answer. Present:

` ` `
Round {n} | Target: {weakest_dimension} | Ambiguity: {score}%

{question}
` ` `

`omx question` payload guidance for interview rounds:
- Deep-interview is Socratic: ask one focused round at a time. Do not use batch `questions[]` to combine multiple interview rounds, even though `omx question` supports batch forms for other workflows.
- Use canonical `type` values instead of authoring raw `multi_select` flags by hand. `type: "single-answerable"` is the default for one-path decisions; `type: "multi-answerable"` is the canonical shape for bounded multi-select rounds. The runtime will keep `multi_select` aligned with `type`.
- Use `single-answerable` when exactly one answer should drive the next branch, the options are mutually exclusive, or selecting more than one answer would blur the decision boundary. Typical cases: handoff lane selection, choosing the primary failure mode, or confirming which of several competing interpretations is correct.
- Use `multi-answerable` when multiple options may all be true at once and you need to capture a bounded set of coexisting constraints, non-goals, risks, or acceptance checks in one round. Typical cases: selecting all out-of-scope items, all success metrics that must hold, or all deployment constraints that apply together.
- If one selected option would immediately require a follow-up question to disambiguate the others, prefer a `single-answerable` round now and ask the follow-up next. Do not hide a branching interview tree inside one overloaded multi-select prompt.
- Keep interview options bounded and concrete. If the valid answers are already known, set `allow_other: false`; only leave `allow_other: true` when the interview genuinely needs one user-supplied option that cannot be enumerated in advance.
- Read answers structurally from the primary `answers[]` array. For a normal single-round interview response, use `answers[0].answer` as the source of truth; the top-level `answer` field is a legacy single-question projection/fallback only.
- For `single-answerable`, expect one decisive selection in the `value` field of `answers[0].answer` plus its selected-values metadata. For `multi-answerable`, treat the selected-values field inside `answers[0].answer` as the source of truth for all chosen constraints/non-goals and preserve the full set in the transcript/spec. In legacy single-question projections, this is equivalent to: For `multi-answerable`, treat `answer.selected_values` as the source of truth.

Canonical bounded single-choice payload:

` ` `json
{
  "question": "Which execution lane should own this once the interview is complete?",
  "type": "single-answerable",
  "options": [
    {
      "label": "Plan first",
      "value": "ralplan",
      "description": "Need architecture and test-shape review before execution"
    },
    {
      "label": "Execute directly",
      "value": "autopilot",
      "description": "Requirements are already explicit enough for planning plus execution"
    },
    {
      "label": "Refine further",
      "value": "refine",
      "description": "Clarification is still needed before any handoff"
    }
  ],
  "allow_other": false,
  "other_label": "Other",
  "source": "deep-interview"
}
` ` `

Canonical bounded multi-select payload:

` ` `json
{
  "question": "Which non-goals must stay out of scope for the first pass?",
  "type": "multi-answerable",
  "options": [
    {
      "label": "No UI redesign",
      "value": "no-ui-redesign",
      "description": "Keep layout and styling unchanged"
    },
    {
      "label": "No new dependencies",
      "value": "no-new-dependencies",
      "description": "Work within the existing toolchain"
    },
    {
      "label": "No API contract changes",
      "value": "no-api-contract-changes",
      "description": "Preserve external request and response shapes"
    }
  ],
  "allow_other": false,
  "other_label": "Other",
  "source": "deep-interview"
}
` ` `

Canonical answer-shape reminders:

` ` `json
{
  "answer": {
    "kind": "option",
    "value": "ralplan",
    "selected_labels": ["Plan first"],
    "selected_values": ["ralplan"]
  }
}
` ` `

` ` `json
{
  "answer": {
    "kind": "multi",
    "value": ["no-new-dependencies", "no-api-contract-changes"],
    "selected_labels": ["No new dependencies", "No API contract changes"],
    "selected_values": ["no-new-dependencies", "no-api-contract-changes"]
  }
}
` ` `

### 2c) Score ambiguity
Score each weighted dimension in `[0.0, 1.0]` with justification + gap.

Greenfield: `ambiguity = 1 - (intent × 0.30 + outcome × 0.25 + scope × 0.20 + constraints × 0.15 + success × 0.10)`

Brownfield: `ambiguity = 1 - (intent × 0.25 + outcome × 0.20 + scope × 0.20 + constraints × 0.15 + success × 0.10 + context × 0.10)`

Readiness gate:
- `Non-goals` must be explicit
- `Decision Boundaries` must be explicit
- A pressure pass must be complete: at least one earlier answer has been revisited with an evidence, assumption, or tradeoff follow-up
- A practical closure audit must pass: another question would change execution materially, not merely polish wording or chase a narrow edge case
- If either gate is unresolved, or the pressure pass is incomplete, continue below threshold only with a final closure question that names the unresolved gate and would materially change execution.
- Treat a low ambiguity score as permission to audit closure, not permission to keep drilling indefinitely. If remaining uncertainty would not change implementation, crystallize the spec instead of opening a new branch.
- If ambiguity is `<= 0.10`, another user-facing question is allowed only as that final closure question; otherwise crystallize immediately.

### 2d) Report progress
Show weighted breakdown table, readiness-gate status (`Non-goals`, `Decision Boundaries`), and the next focus dimension.

### 2e) Persist state
Append round result and updated scores via `omx state write --input '<json>' --json`; use `state_write` only when explicit MCP compatibility is enabled.

### 2f) Round controls
- Do not offer early exit before the first explicit assumption probe and one persistent follow-up have happened
- Apply a **Dialectic Rhythm Guard**: track consecutive non-user fact discoveries and confirmation-style answers (`[from-code][auto-confirmed]`, `[from-code]`, or `[from-research]`). After 3 consecutive non-user or confirmation answers, the next material user-facing round must solicit direct human judgment (`[from-user]`) unless the closure audit says the interview is ready to crystallize.
- Round 4+: allow explicit early exit with risk warning
- Soft warning at profile midpoint (e.g., round 3/6/10 depending on profile)
- Hard cap at profile `max_rounds`; never treat this cap as a desired interview length or quota

## Phase 3: Challenge Modes (assumption stress tests)

Use each mode once when applicable. These are normal escalation tools, not rare rescue moves:

- **Contrarian** (round 2+ or immediately when an answer rests on an untested assumption): challenge core assumptions
- **Terminologist** (brownfield, whenever a key term is fuzzy, overloaded, or conflicts with repo docs/code): force a canonical meaning against existing project language before implementation
- **Simplifier** (round 4+ or when scope expands faster than outcome clarity): probe minimal viable scope
- **Ontologist** (round 5+ and ambiguity > 0.25, or when the user keeps describing symptoms): ask for essence-level reframing

Track used modes in state to prevent repetition.

## Phase 4: Crystallize Artifacts

When threshold is met (or user exits with warning / hard cap):

1. Write interview transcript summary to:
   - `.omx/interviews/{slug}-{timestamp}.md`  
     (kept for ralph PRD compatibility)
2. Write execution-ready spec to:
   - `.omx/specs/deep-interview-{slug}.md`

Spec should include:
- Metadata (profile, rounds, final ambiguity, threshold, context type)
- Context snapshot reference/path (for ralplan/team reuse)
- Prompt-safe initial-context summary when oversized context was provided, plus references to any full source documents
- Clarity breakdown table
- Intent (why the user wants this)
- Desired Outcome
- In-Scope
- Out-of-Scope / Non-goals
- Decision Boundaries (what OMX may decide without confirmation)
- Constraints
- Testable acceptance criteria
- Assumptions exposed + resolutions
- Pressure-pass findings (which answer was revisited, and what changed)
- Brownfield evidence vs inference notes for any repository-grounded confirmation questions
- Docs/Terminology Ledger with inspected repo docs/rules/context, term conflicts, and any doc/code mismatch decisions
- Scenario/edge-case pressure findings that materially shaped scope or acceptance criteria
- Optional durable documentation recommendations, explicitly marked opt-in and public-safe; do not include raw private transcript dumps
- Technical context findings
- Full or condensed transcript

### Autoresearch specialization

When the clarified task is specifically about `$autoresearch`, or the skill is invoked with `--autoresearch`, keep the interview domain-specific and emit skill-consumable artifacts without skipping clarification.

- **Accepted seed inputs:** `topic`, `evaluator`, `keep-policy`, `slug`, existing mission draft text, and prior evaluator examples/templates
- **Required interview focus:** mission clarity, evaluator readiness, keep policy, slug/session naming, and whether the draft is ready to launch now or should refine further
- **Canonical artifact path:** `.omx/specs/deep-interview-autoresearch-{slug}.md`
- **Launch artifact bundle:** `.omx/specs/autoresearch-{slug}/mission.md`, `.omx/specs/autoresearch-{slug}/sandbox.md`, and `.omx/specs/autoresearch-{slug}/result.json`
- **Launch artifact directory:** `.omx/specs/autoresearch-{slug}/`
- **Required artifact sections:**
  - `Mission Draft`
  - `Evaluator Draft`
  - `Launch Readiness`
  - `Seed Inputs`
  - `Confirmation Bridge`
- **Required launch artifacts under `.omx/specs/autoresearch-{slug}/`:**
  - `mission.md`
  - `sandbox.md`
  - `result.json`
- **Launch-readiness rule:** mark the draft as **not launch-ready** while the evaluator command still contains placeholder markers such as `<...>`, `TODO`, `TBD`, `REPLACE_ME`, `CHANGEME`, or `your-command-here`
- **Structured result contract:** `result.json` should point to the draft + mission/sandbox artifacts and carry the finalized `topic`, `evaluatorCommand`, `keepPolicy`, `slug`, `launchReady`, and `blockedReasons` fields so `$autoresearch` can consume it directly
- **Confirmation bridge:** after artifact generation, offer at least `refine further` and `launch`; do not run direct CLI launch or detached/split tmux launch, and only hand off to `$autoresearch` after explicit confirmation
- **Handoff rule:** downstream execution must preserve the clarified mission intent, evaluator expectations, decision boundaries, and launch-readiness status from this artifact rather than bypassing the draft review step

## Phase 5: Execution Bridge

Present execution options after artifact generation using explicit handoff contracts. Treat the deep-interview spec as the current requirements source of truth and preserve intent, non-goals, decision boundaries, acceptance criteria, docs/terminology grounding, and any residual-risk warnings across the handoff.

### Optional execution contract foundation

When an Autopilot/deep-interview handoff explicitly requires a stride contract, emit it as structured data rather than prose. This is a validation foundation, not a broadness-inference feature: do not infer stride from task length, phase labels, snapshots, or freeform wording.

Canonical location under Autopilot state:

` ` `json
{
  "handoff_artifacts": {
    "deep_interview": {
      "execution_contract_required": true,
      "execution_contract": {
        "version": 1,
        "execution_stride": "task",
        "source": "deep-interview",
        "selected_by": "user",
        "allow_task_shrink": true,
        "completion_unit": "One focused task",
        "stop_condition": "Stop after that task is implemented and verified",
        "acceptance_coverage_scope": "task",
        "shrink_policy": "allowed"
      }
    }
  }
}
` ` `

Stride meanings:
- `task`: conservative, small-step execution; `allow_task_shrink:true`, `acceptance_coverage_scope:"task"`, `shrink_policy:"allowed"`.
- `deliverable`: finish the named deliverable before stopping; `allow_task_shrink:false`, `acceptance_coverage_scope:"deliverable"`, `shrink_policy:"ask_before_shrink"`.
- `milestone`: finish the larger approved milestone unless blocked; `allow_task_shrink:false`, `acceptance_coverage_scope:"milestone"`, `shrink_policy:"deny_unless_blocked"`.

Only set `execution_contract_required:true` when the selected downstream workflow needs this explicit stride/stop-condition guard. New artifacts must write the canonical snake_case schema shown above under `handoff_artifacts.deep_interview`; runtime readers may accept legacy camelCase field/marker aliases and direct/nested `execution_contract` locations only as compatibility input. If `execution_contract_required` is absent or false, downstream Autopilot compatibility behavior is unchanged.

### Goal-mode follow-ups

Include these product-facing suggestions when they fit the clarified spec, without removing the existing `$ultragoal`, `$ralplan`, `$autopilot`, `$ralph`, and `$team` handoff options:

- **`$ultragoal`** — default goal-mode follow-up for implementation or general goal-oriented follow-up specs that should be converted into durable Codex/OMX goals with sequential completion tracking.
- **`$autoresearch-goal`** — use when the clarified context is a research project: a research question, reference/literature gathering, evaluator-backed analysis, or professor/critic-style deliverable.
- **`$performance-goal`** — use when the clarified context is an optimization or performance project with measurable speed, latency, throughput, memory, benchmark, or evaluator criteria.

Recommend `$ultragoal` as the default durable goal-mode follow-up because it supersedes Ralph for goal tracking. Preserve `$team` for coordinated parallel implementation and keep `$ralph` only as an explicit fallback for persistent single-owner execution/verification when the user specifically selects it.

### 1. **`$ultragoal` (Default durable execution follow-up)**
- **Input Artifact:** `.omx/specs/deep-interview-{slug}.md` (optionally accompanied by the transcript/context snapshot for traceability)
- **Invocation:** `$ultragoal create-goals --brief-file <spec-path>` followed by `$ultragoal complete-goals` in the active execution lane
- **Consumer Behavior:** Convert the clarified spec into durable goal-mode work. Preserve intent, non-goals, decision boundaries, acceptance criteria, docs/terminology grounding, scenario-pressure findings, and residual-risk warnings as binding story constraints.
- **Skipped / Already-Satisfied Stages:** Requirement interview, ambiguity clarification, doc/context preflight, and early intent-boundary elicitation
- **Expected Output:** `.omx/ultragoal/brief.md`, `.omx/ultragoal/goals.json`, `.omx/ultragoal/ledger.jsonl`, implementation evidence, verification evidence, and final cleanup/review-gate evidence
- **Best When:** The clarified spec is execution-ready or the user explicitly wants durable goal tracking as the next step
- **Next Recommended Step:** Run the Ultragoal completion loop; launch `$team` only inside an active Ultragoal story when parallel lanes are warranted, and use `$ralph` only as an explicit fallback when the user asks for that legacy persistence mode

### 2. **`$ralplan` (Recommended when architecture/test-shape review is still needed)**
- **Input Artifact:** `.omx/specs/deep-interview-{slug}.md` (optionally accompanied by the transcript/context snapshot for traceability)
- **Invocation:** `$plan --consensus --direct <spec-path>`
- **Consumer Behavior:** Treat the deep-interview spec as the requirements source of truth. Do not repeat the interview by default; refine architecture/feasibility around the clarified intent and boundaries instead.
- **Skipped / Already-Satisfied Stages:** Requirements discovery, ambiguity clarification, and early intent-boundary elicitation
- **Expected Output:** Canonical planning artifacts under `.omx/plans/`, especially `prd-*.md` and `test-spec-*.md`
- **Best When:** Requirements are clear enough to stop interviewing, but architectural validation / consensus planning is still desirable
- **Next Recommended Step:** Use the approved planning artifacts with `$ultragoal` as the default durable goal-mode follow-up (optionally with `$team` for parallel lanes); choose `$autoresearch-goal` for research validation or `$performance-goal` for measurable optimization, and use `$ralph` only as an explicit fallback when a narrow single-owner persistence loop is requested

### 3. **`$autopilot`**
- **Input Artifact:** `.omx/specs/deep-interview-{slug}.md`
- **Invocation:** `$autopilot <spec-path>`
- **Consumer Behavior:** Use the deep-interview spec as the clarified execution brief. Preserve intent, non-goals, decision boundaries, and acceptance criteria as binding context for planning/execution.
- **Skipped / Already-Satisfied Stages:** Initial requirement discovery and ambiguity reduction
- **Expected Output:** Planning/execution progress, QA evidence, and validation artifacts produced by autopilot
- **Best When:** The clarified spec is already strong enough for direct planning + execution without an additional consensus gate
- **Next Recommended Step:** Continue through autopilot's execution/QA/validation flow; if coordination-heavy execution emerges, prefer `$team` under a leader-owned `$ultragoal` ledger, using `$ralph` only as an explicit fallback when a narrow single-owner persistence loop is requested

### 4. **`$ralph` (Explicit fallback only)**
- **Input Artifact:** `.omx/specs/deep-interview-{slug}.md`
- **Invocation:** `$ralph <spec-path>`
- **Consumer Behavior:** Use the spec's acceptance criteria and boundary constraints as the persistence target. Do not reopen requirements discovery unless the user explicitly asks to refine further.
- **Skipped / Already-Satisfied Stages:** Requirement interview, ambiguity clarification, and initial scope-definition work
- **Expected Output:** Iterative execution progress and verification evidence tracked against the clarified criteria
- **Best When:** The user explicitly asks for Ralph's persistent sequential completion pressure; otherwise use `$ultragoal` for durable goal tracking and completion checkpoints
- **Next Recommended Step:** If this explicit fallback is selected, continue Ralph's persistence loop; if work expands into coordination-heavy lanes, hand off to `$team` under `$ultragoal` checkpointing rather than promoting Ralph as the next default

### 5. **`$team`**
- **Input Artifact:** `.omx/specs/deep-interview-{slug}.md`
- **Invocation:** `$team <spec-path>`
- **Consumer Behavior:** Treat the spec as shared execution context for coordinated parallel work. Preserve the clarified intent, non-goals, decision boundaries, and acceptance criteria as common lane constraints.
- **Skipped / Already-Satisfied Stages:** Requirement clarification and early ambiguity reduction
- **Expected Output:** Coordinated multi-agent execution against the shared spec, with evidence that can later feed Ultragoal checkpoints by default, or an explicit Ralph verification pass only when requested
- **Best When:** The task is large, multi-lane, or blocker-sensitive enough to justify coordinated parallel execution instead of a single persistent loop
- **Next Recommended Step:** Follow the team verification path when the coordinated execution phase finishes; checkpoint completion through `$ultragoal` by default, escalating to a separate Ralph loop only when the user explicitly asks for that persistent verification/fix owner

### 6. **Refine further**
- **Input Artifact:** Existing transcript, context snapshot, and current spec draft
- **Invocation:** Continue the interview loop
- **Consumer Behavior:** Re-enter questioning to resolve the highest-leverage remaining uncertainty
- **Skipped / Already-Satisfied Stages:** None beyond already-captured context
- **Expected Output:** A lower-ambiguity spec with tighter boundaries and fewer unresolved assumptions
- **Best When:** Residual ambiguity is still too high, the user wants stronger clarity, or the above-threshold / early-exit warning indicates too much risk to proceed cleanly
- **Next Recommended Step:** Return to one of the execution handoff contracts above once the spec is sufficiently clarified

**Residual-Risk Rule:** If the interview ended via early exit, hard-cap completion, or above-threshold proceed-with-warning, explicitly preserve that residual-risk state in the handoff so the downstream skill knows it inherited a partially clarified brief.

**IMPORTANT:** Deep-interview is a requirements mode. On handoff, invoke the selected skill using the contract above. **Do NOT implement directly** inside deep-interview.

</Steps>

<Tool_Usage>
- Use `explore` for codebase fact gathering
- Use `omx question` as the OMX-native structured user-input tool for each interview round when an attached tmux renderer is available
- From attached-tmux Bash/tool paths, call it as `OMX_QUESTION_RETURN_PANE=$TMUX_PANE omx question ...` unless an explicit `%pane` return target is already known
- If the current runtime is outside tmux and cannot render `omx question`, use native structured input when available; otherwise ask exactly one concise plain-text question and wait for the answer
- After `omx question` returns JSON, prefer `answers[0].answer` / `answers[]`; use legacy `answer` only as a fallback for older records
- Use `omx state write/read --input '<json>' --json` for resumable mode state; `state_write` / `state_read` are explicit MCP compatibility fallbacks only
- If the interview cannot ask a required `omx question` round, persist the blocker as terminal state with `active: false` and `current_phase: "blocked"`; do not write a terminal blocked phase with `active: true`
- Read/write context snapshots under `.omx/context/`
- Read applicable repo docs/rules/context during preflight; write durable docs, glossary, ADR, or memory updates only when the user explicitly opts in and the content is public-safe
- Record whether the oversized-context summary gate is not needed, pending, or satisfied before any scoring or handoff step
- Save transcript/spec artifacts under `.omx/interviews/` and `.omx/specs/`
</Tool_Usage>

<Escalation_And_Stop_Conditions>
- User says stop/cancel/abort -> persist state and stop
- Ambiguity stalls for 3 rounds (+/- 0.05) -> force Ontologist mode once
- Max rounds reached -> proceed with explicit residual-risk warning
- All dimensions >= 0.9 -> allow early crystallization even before max rounds
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Preflight context snapshot exists under `.omx/context/{slug}-{timestamp}.md`
- [ ] Oversized initial context, if present, has a prompt-safe summary recorded before ambiguity scoring or downstream handoff
- [ ] Ambiguity score shown each round
- [ ] Intent-first stage priority used before implementation detail
- [ ] Weakest-dimension targeting used within the active stage
- [ ] At least one explicit assumption probe happened before crystallization
- [ ] At least one persistent follow-up / pressure pass deepened a prior answer
- [ ] Challenge modes triggered at thresholds (when applicable)
- [ ] Transcript written to `.omx/interviews/{slug}-{timestamp}.md`
- [ ] Spec written to `.omx/specs/deep-interview-{slug}.md`
- [ ] Brownfield questions use evidence-backed confirmation when applicable
- [ ] Brownfield preflight inspected applicable repo docs/rules/context before user-facing questions
- [ ] Fuzzy or conflicting terminology was challenged against repo language/current code behavior when applicable
- [ ] Scenario-based edge-case grilling was used when boundary ambiguity would materially affect implementation
- [ ] Durable docs/ADR/memory updates, if any, were explicitly opted into and public-safe
- [ ] Handoff options provided (`$ultragoal`, `$ralplan`, `$autopilot`, `$ralph`, `$team`) plus context-sensitive goal-mode suggestions (`$autoresearch-goal`, `$performance-goal`) when applicable
- [ ] No direct implementation performed in this mode
</Final_Checklist>

<Advanced>
## Suggested Config (optional)

Deep-interview reads runtime defaults from the first existing config source in this order:

1. Repository-local `.omx/config.toml`
2. Repository-root `omx.toml`
3. User-global `~/.omx/config.toml`

This section is currently a deep-interview-specific runtime override surface, not a general replacement for Codex `config.toml` or `.omx-config.json` model/env routing.
Malformed config files are ignored fail-soft so `$deep-interview` activation can continue with built-in defaults.
Explicit `--quick`, `--standard`, or `--deep` invocation flags override `defaultProfile`.

` ` `toml
[omx.deepInterview]
defaultProfile = "standard"
quickThreshold = 0.30
standardThreshold = 0.20
deepThreshold = 0.15
quickMaxRounds = 5
standardMaxRounds = 12
deepMaxRounds = 20
enableChallengeModes = true
` ` `

## Resume

If interrupted, rerun `$deep-interview`. Resume from persisted mode state via `omx state read --input '{"mode":"deep-interview"}' --json`.

## Recommended 3-Stage Pipeline

` ` `
deep-interview -> ralplan -> autopilot
` ` `

- Stage 1 (deep-interview): clarity gate
- Stage 2 (ralplan): feasibility + architecture gate
- Stage 3 (autopilot): execution + QA + validation gate
</Advanced>

</skill>
```

## 6. line 184 timestamp 2026-06-09T19:13:45.614Z

```text
Operator onboarding - so adapt ~./codex/AGENTS.md to better fit aria_nbv and integrate omx optimally with our local agents scaffold, code, docs, literature, cli and streamlit verification looops with visual interpretation of results via omx automation gates to allow for iterative auto research, auto ml a la [karpathy/autoresearch](https://github.com/karpathy/autoresearch). so dispatch some research agent to find a good maintained autoresearch version that we could enmploy as external tools.
all integration with external harness elements like omx must be maintained in a way that makes it easy to update or replace these external scaffolds.
```

## 7. line 200 timestamp 2026-06-09T19:19:05.544Z

```text

# Files mentioned by the user:

## Pasted text.txt: /home/jd/.codex/attachments/bc770d90-44e4-422c-8b28-439702d9dde4/pasted-text.txt

## My request for Codex:
The following might also contain some high value conditioning to improve our alignment 


```

## 8. line 268 timestamp 2026-06-09T19:34:08.396Z

```text
<subagent_notification>
{"agent_path":"019eadd3-5975-75b2-b781-f201b4295b78","status":{"completed":"## Research: autoresearch-style agent layer for ARIA-NBV + OMX\n\n### Request Type\nCurrent best-practice research / comparative evaluation\n\n### Direct Recommendation\nAs of **2026-06-09**, I would start with **LangGraph + Open Deep Research**, keep **LlamaIndex Workflows / LlamaAgents** as the best document-centric alternative, and use **smolagents** only if you want the thinnest code-first harness. **CrewAI** is the strongest runner-up if you want a fuller product surface. I would **not** base a new integration on **AutoGen**, and I would treat **karpathy/autoresearch** as inspiration only, not a dependency base.\n\n### Top 3 Candidates\n\n1. **LangGraph + Open Deep Research**\n- Maintenance signal: `langgraph` latest release is **1.2.4** on **2026-06-02**; the repo is MIT and the docs frame it as a low-level orchestration runtime with persistence, interrupts, subgraphs, and durable state ([LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [LangGraph releases](https://github.com/langchain-ai/langgraph/releases), [LangGraph repo](https://github.com/langchain-ai/langgraph)).\n- Open Deep Research is also MIT, has **213 commits**, recent upstream updates in **Aug 2025**, and explicitly says **no releases published** ([Open Deep Research repo](https://github.com/langchain-ai/open_deep_research)).\n- Why for ARIA-NBV: best fit for a replaceable research loop because the harness can be kept thin and the actual research steps can be modeled as nodes/subgraphs with persistent state.\n- Why not: it is a lower-level runtime, so you will write more orchestration code than with turnkey frameworks.\n\n2. **LlamaIndex Workflows / LlamaAgents**\n- Maintenance signal: `run-llama/llama-agents` is MIT, shows **592 commits**, **180 releases**, and the latest release line is **llamactl@0.10.2** on **2026-05-14**; the repo page was published **last week** in GitHub’s activity view ([repo](https://github.com/run-llama/llama-agents), [LlamaIndex agent/workflow docs](https://developers.llamaindex.ai/python/framework/), [multi-agent docs](https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/)).\n- The docs describe workflows as event-driven, step-based orchestration with state, human-in-the-loop support, and deployment as microservices.\n- Why for ARIA-NBV: strongest if the loop is document-heavy, needs structured extraction/review, or should be deployable as a service without forcing a monolithic harness.\n- Why not: it is more document/workflow oriented than pure research-loop oriented, so it is not as immediately “autoresearch-like” as LangGraph.\n\n3. **smolagents**\n- Maintenance signal: Apache-2.0, **1,047 commits**, and latest release **v1.26.0** on **2026-05-29** ([repo](https://github.com/huggingface/smolagents), [releases](https://github.com/huggingface/smolagents/releases), [docs](https://huggingface.co/docs/smolagents/index)).\n- The docs emphasize a very small, code-first abstraction surface, plus MCP support and sandboxed execution.\n- Why for ARIA-NBV: best “thin harness” option if you want to own most of the logic yourself and swap the agent backend later.\n- Why not: the docs explicitly call the API **experimental**, so I would not make it the only long-lived core unless you are comfortable with some churn.\n\n### Strong Runner-Up\n\n- **CrewAI** is active and MIT, with latest stable release **1.14.5** on **2026-05-18** and a **1.14.6a1** pre-release on the same releases page; docs position it as production-ready with flows, crews, memory, knowledge, observability, and MCP support ([docs](https://docs.crewai.com/), [releases](https://github.com/crewAIInc/crewAI/releases), [repo](https://github.com/crewAIInc/crewAI)).\n- I did **not** put it in the top 3 because it is more opinionated and role/crew-centric than I’d want for a replaceable ARIA-NBV research harness, but it is a viable alternative if you want more framework packaging.\n\n### Exclusions / Cautions\n\n- **AutoGen**: official repo now says **maintenance mode**, with no new features/enhancements and a recommendation to start with Microsoft Agent Framework instead ([repo](https://github.com/microsoft/autogen)). It is MIT for code, but I would not start a new ARIA-NBV integration there.\n- **karpathy/autoresearch**: the repo is a great pattern reference, but it still has no clearly present top-level LICENSE file in the repo discussion trail, and 2026 issues explicitly ask for one ([repo](https://github.com/karpathy/autoresearch), [license issue](https://github.com/karpathy/autoresearch/issues/523), [license-file issue](https://github.com/karpathy/autoresearch/issues/210)). I would not treat it as a safe base dependency.\n- **OpenHands**: MIT and actively maintained, but the SDK/docs are explicitly oriented toward software engineering, code editing, bash, web, and sandboxed execution ([docs](https://docs.openhands.dev/sdk), [repo](https://github.com/All-Hands-AI/OpenHands)). Use it only if your “research” loop is actually code-execution-heavy.\n\n### Integration Boundary Advice\n- Keep **ARIA-NBV/OMX-owned state, artifacts, and scheduling** outside the agent framework.\n- Make the framework own only the **inner loop**: plan, search, extract, synthesize, verify.\n- Expose tools through a **small stable adapter** or **MCP**, not framework-specific prompts everywhere.\n- Treat the framework as **replaceable orchestration**, not as the source of truth.\n- If you choose LangGraph, make the seam the **node/subgraph boundary**.\n- If you choose LlamaIndex, make the seam the **Workflow/Context boundary**.\n- If you choose smolagents, wrap the runner behind a single `ResearchRunner` interface and keep tool/state wiring outside it.\n\n### Reusable Takeaway\nFor a maintainable ARIA-NBV autoresearch layer, **LangGraph is the best core**, **LlamaIndex is the best document/workflow alternative**, and **smolagents is the best thin harness fallback**. Keep the framework replaceable by constraining it to orchestration only, while OMX and ARIA-NBV own state, artifacts, and execution policy."}}
</subagent_notification>
```

## 9. line 284 timestamp 2026-06-09T20:19:28.361Z

```text
also omx:review the actual utility of litkg and potential external replacements - i.e. what create external mcp servers, skills, etc exist in some open source well-maintained GH repos
```

## 10. line 395 timestamp 2026-06-09T20:27:56.224Z

```text
also: having tools to maintain alignment and ensuring strict single sources of definition / responsibility - to avoid redundancies...

graphify? graphity? mempalace? what do we really need and how to integrate it optimally with omx?
 
```

## 11. line 421 timestamp 2026-06-09T20:46:46.848Z

```text
[$oh-my-codex:autopilot](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/autopilot/SKILL.md) from all your context do clean up and improvement to our agent scaffold!
```

## 12. line 424 timestamp 2026-06-09T20:46:46.852Z

```text
<skill>
<name>oh-my-codex:autopilot</name>
<path>/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/autopilot/SKILL.md</path>
---
name: autopilot
description: "[OMX] Strict autonomous loop: $deep-interview -> $ralplan -> $ultragoal (+ $team if needed) -> $code-review -> $ultraqa"
---

<Purpose>
Autopilot is the strict autonomous delivery loop for non-trivial work. Its recommended/default contract is exactly:

` ` `text
$deep-interview -> $ralplan -> $ultragoal (+ $team if needed) -> $code-review -> $ultraqa
` ` `

If `$code-review` or `$ultraqa` is not clean, Autopilot returns to `$ralplan` with the findings as the next planning input, then continues again through `$ultragoal`, `$code-review`, and `$ultraqa` until the gates are clean or a hard blocker is reported. Ralph is a legacy/explicit alternate execution loop only; do not advertise Ralph as the default Autopilot path.
</Purpose>

<Use_When>
- User wants hands-off execution from a concrete idea, issue, PRD, or requirements artifact to reviewed and QA-checked code
- User says `$autopilot`, "autopilot", "auto pilot", "autonomous", "build me", "create me", "make me", "full auto", "handle it all", or "I want a/an..."
- Task needs clarification, planning, durable execution, verification, code review, and QA with automatic follow-up when gates are not clean
</Use_When>

<Do_Not_Use_When>
- User wants to explore options or brainstorm -- use `$plan` / `$ralplan`
- User says "just explain", "draft only", or "what would you suggest" -- respond conversationally
- User wants a single focused code change -- use `$ultragoal`, `$ralph` only when explicitly requested, or direct executor work
- User wants only review/critique of existing code -- use `$code-review`
</Do_Not_Use_When>

<Strict_Loop_Contract>
Autopilot must not run a separate broad expansion/planning/execution/QA/validation lifecycle as its primary behavior. It delegates those concerns to the canonical workflow phases below:

1. **Phase `deep-interview`** — Socratic requirements clarification gate
   - Run or resume `$deep-interview` to clarify intent, scope, non-goals, constraints, and decision boundaries.
   - Deep-interview is a structured question chain, not a one-question gate; `max_rounds` is a cap, not a target.
   - After a user answers an `omx question`, re-score ambiguity against the active profile threshold. Ask another question only when a readiness gate is still unresolved and the answer would materially change execution; otherwise crystallize the spec and hand off.
   - Required handoff artifact: a clarified spec or concise requirements summary suitable for `$ralplan`, including an explicit interview-complete rationale when leaving deep-interview.

2. **Phase `ralplan`** — consensus planning gate
   - Ground the task with pre-context intake and the deep-interview artifact.
   - Run or resume `$ralplan` to produce/update PRD and test-spec artifacts.
   - PRD/test-spec files alone are not completion evidence. Ralplan may hand off only after durable consensus evidence records a subsequent `Architect` approval first and a subsequent `Critic` approval second.
   - When returning from a non-clean review or QA pass, include `return_to_ralplan_reason` and the findings as first-class planning input.
   - If either review is missing, blocked, out of order, or non-approving, remain in `ralplan` or report an explicit blocker/max-iteration outcome; do not progress to `$ultragoal`, `$team`, `$ralph`, or implementation.
   - Required handoff artifact: an approved plan/test spec plus `ralplan_consensus_gate` evidence suitable for `$ultragoal`.

3. **Phase `ultragoal`** — durable implementation + verification loop
   - Run `$ultragoal` from the approved ralplan artifacts.
   - Ultragoal owns durable Codex goal handoffs, `.omx/ultragoal` ledger checkpoints, implementation, tests, build/lint/typecheck evidence, cleanup, and final review gate discipline.
   - Use `$team` only inside an active Ultragoal story when the story clearly benefits from coordinated parallel execution (for example independent file/module lanes, broad test matrix work, or multi-domain implementation). Team remains explicit and leader-owned; Ultragoal keeps the goal/ledger state.
   - Required handoff artifact: implementation evidence, changed-file summary, verification evidence, and Ultragoal ledger/checkpoint references suitable for `$code-review`.

4. **Phase `code-review`** — merge-readiness gate
   - Run `$code-review` on the diff/artifacts produced by `$ultragoal`.
   - A clean review means final recommendation `APPROVE` with architectural status `CLEAR`.
   - `COMMENT`, `REQUEST CHANGES`, any architectural `WATCH`/`BLOCK`, or any unresolved finding is not clean.
   - If not clean, increment the review cycle, persist `review_verdict`, set `return_to_ralplan_reason`, and transition back to Phase `ralplan`.

5. **Phase `ultraqa`** — adversarial QA gate
   - Run `$ultraqa` after a clean code review when user-facing behavior, workflows, CLI/runtime behavior, integration surfaces, or regression risk warrant adversarial QA.
   - For docs-only or trivially non-runtime changes, record `ultraqa` as skipped with an explicit condition and evidence.
   - If UltraQA finds issues, persist the QA verdict/evidence, set `return_to_ralplan_reason`, and transition back to Phase `ralplan`.

The only normal terminal state is `complete` after clean code review and a passed or explicitly skipped UltraQA gate. Cancellation, blocked credentials, unrecoverable repeated failures, or explicit user stop may terminate earlier with preserved state.
</Strict_Loop_Contract>

<Pre-context Intake>
Before Phase `deep-interview` or `ralplan` starts or resumes:
1. Derive a task slug from the request.
2. Reuse the latest relevant `.omx/context/{slug}-*.md` snapshot when available.
3. If none exists, create `.omx/context/{slug}-{timestamp}.md` (UTC `YYYYMMDDTHHMMSSZ`) with:
   - activation prompt / task seed
   - original task status (`activation-prompt`, `legacy-unverified`, or `unavailable`)
   - desired outcome
   - known facts/evidence
   - constraints
   - unknowns/open questions
   - likely codebase touchpoints
   - a scope note that the seed is the Autopilot activation prompt, not guaranteed prior conversation context
4. If brownfield facts are missing, run `explore` first before or during `$deep-interview` (`$deep-interview --quick <task>` remains acceptable for bounded low-ambiguity intake); do not skip the clarification gate merely because the task sounds actionable.
5. Carry the snapshot path in Autopilot state and all handoff artifacts.
</Pre-context Intake>

<Execution_Policy>
- Always execute the recommended phases in order: `deep-interview`, then `ralplan`, then `ultragoal`, then `code-review`, then `ultraqa`.
- `$team` is conditional and explicit: use it only within an Ultragoal story when parallel execution materially improves throughput, quality, or safety.
- Never skip directly from vague/freeform expansion to implementation; unclear input must be clarified and planned through `$deep-interview` and `$ralplan`.
- A non-clean `$code-review` or failed `$ultraqa` always returns to `$ralplan`; do not patch findings ad hoc outside the loop.
- Each phase must write/update Autopilot state before handing off.
- Use existing hooks, `.omx/state`, `$deep-interview`, `$ralplan`, `$ultragoal`, optional `$team`, `$code-review`, `$ultraqa`, and pipeline primitives; do not invent a separate execution framework.
- Preserve legacy compatibility: if a user explicitly requests the old Ralph execution lane, use `$ralph` as an intentional alternate execution phase, but do not present it as Autopilot's default recommended loop.
- Continue automatically through safe reversible phase transitions. Ask only for destructive, credential-gated, or materially preference-dependent branches.
- Apply the shared workflow guidance pattern: outcome-first framing, concise visible updates for multi-step execution, local overrides for the active workflow branch, validation proportional to risk, explicit stop rules, and automatic continuation for safe reversible steps. Ask only for material, destructive, credentialed, external-production, or preference-dependent branches.
</Execution_Policy>

<State_Management>
Use the CLI-first state surface (`omx state ... --json`) for Autopilot lifecycle state. State must be session-aware when a session id exists. If the explicit MCP compatibility surface is already available, equivalent `omx_state` tool calls remain acceptable but are not required.

Inside active Autopilot, named child phases such as `$ralplan` are supervised phases, not peer workflow activations: keep `mode:"autopilot"` active and update `current_phase:"ralplan"` rather than starting standalone `mode:"ralplan"` over Autopilot.

Required fields:

` ` `json
{
  "mode": "autopilot",
  "active": true,
  "current_phase": "deep-interview",
  "iteration": 1,
  "review_cycle": 0,
  "max_iterations": 10,
  "phase_cycle": ["deep-interview", "ralplan", "ultragoal", "code-review", "ultraqa"],
  "handoff_artifacts": {
    "context_snapshot_path": ".omx/context/<slug>-<timestamp>.md",
    "deep_interview": null,
    "ralplan": null,
    "ralplan_consensus_gate": {
      "required": true,
      "sequence": ["architect-review", "critic-review"],
      "planning_artifacts_are_not_consensus": true,
      "required_review_roles": ["architect", "critic"],
      "ralplan_architect_review": null,
      "ralplan_critic_review": null,
      "complete": false
    },
    "ultragoal": null,
    "code_review": null,
    "ultraqa": null
  },
  "review_verdict": null,
  "qa_verdict": null,
  "return_to_ralplan_reason": null
}
` ` `

- **On start**: `omx state write --input '{"mode":"autopilot","active":true,"current_phase":"deep-interview","iteration":1,"review_cycle":0,"state":{"phase_cycle":["deep-interview","ralplan","ultragoal","code-review","ultraqa"],"handoff_artifacts":{"context_snapshot_path":"<snapshot-path>","deep_interview":null,"ralplan":null,"ralplan_consensus_gate":{"required":true,"sequence":["architect-review","critic-review"],"planning_artifacts_are_not_consensus":true,"required_review_roles":["architect","critic"],"ralplan_architect_review":null,"ralplan_critic_review":null,"complete":false},"ultragoal":null,"code_review":null,"ultraqa":null},"review_verdict":null,"qa_verdict":null,"return_to_ralplan_reason":null}}' --json`
- **On deep-interview -> ralplan**: only after a separate gate proves the interview chain is explicitly complete or the user explicitly authorized a skip. For completion, persist `deep_interview_gate:{"status":"complete","rationale":"<why requirements are complete>","handoff_summary":"<summary>"}` (or equivalent non-empty rationale/summary) plus the clarified spec/requirements under `handoff_artifacts.deep_interview`; if a final `omx question` was involved, keep its same-session answered record linked by `question_id`/`satisfied_at`. For skip, persist `deep_interview_gate:{"status":"skipped","skip_authorized_by_user":true,"skip_reason":"<user-authorized reason>","skipped_at":"<timestamp>","source":"user","session_id":"<session>"}`. Do not leave deep-interview merely because the first `omx question` was answered or cleared.
  - **Optional execution contract foundation**: when a downstream handoff explicitly sets `execution_contract_required:true`, persist a complete structured `execution_contract` under `handoff_artifacts.deep_interview` before leaving deep-interview. The canonical schema is `version:1`, `execution_stride:"task"|"deliverable"|"milestone"`, `source:"deep-interview"`, `selected_by:"user"|"default"`, `allow_task_shrink:<boolean>`, non-empty `completion_unit`, non-empty `stop_condition`, `acceptance_coverage_scope:"task"|"deliverable"|"milestone"`, and `shrink_policy:"allowed"|"ask_before_shrink"|"deny_unless_blocked"`.
  - Stride semantics are binding only when `execution_contract_required:true`: `task` means `allow_task_shrink:true`, `acceptance_coverage_scope:"task"`, `shrink_policy:"allowed"`; `deliverable` means `allow_task_shrink:false`, `acceptance_coverage_scope:"deliverable"`, `shrink_policy:"ask_before_shrink"`; `milestone` means `allow_task_shrink:false`, `acceptance_coverage_scope:"milestone"`, `shrink_policy:"deny_unless_blocked"`.
  - Preserve legacy behavior when `execution_contract_required` is absent or false. Do not infer stride from prose, broadness, phase names, snapshots, or task size; this foundation only validates an explicit structured contract and deliberately uses `milestone` rather than `phase`. New artifacts must write canonical snake_case keys under `handoff_artifacts.deep_interview`; the runtime may read legacy camelCase field/marker aliases and direct/nested `execution_contract` locations only as compatibility input.
- **On ralplan -> ultragoal**: only after `ralplan_consensus_gate.complete:true`, with tracker-backed native-subagent `ralplan_architect_review.agent_role:"architect"` and `ralplan_architect_review.verdict:"approve"` recorded before tracker-backed native-subagent `ralplan_critic_review.agent_role:"critic"` and `ralplan_critic_review.verdict:"approve"`; `codex_exec` or artifact-only approvals are trace evidence but not native lane proof. Set `current_phase:"ultragoal"` and persist the plan/test-spec paths under `handoff_artifacts.ralplan`.
- **On missing ralplan consensus evidence**: keep `current_phase:"ralplan"`, persist `ralplan_consensus_gate.complete:false` with `blocked_reason`, and report an explicit blocker or max-iteration outcome instead of handing off to execution.
- **On ultragoal -> code-review**: set `current_phase:"code-review"`, persist implementation/test/ledger evidence under `handoff_artifacts.ultragoal`.
- **On code-review -> ultraqa**: set `current_phase:"ultraqa"` only after a real `$code-review` stage/subagent has produced durable evidence; persist the clean review under `handoff_artifacts.code_review` with its source thread/tool/stage reference. Do not author `review_verdict:{clean:true}` from the leader's own summary.
- **On clean review + passed/skipped QA**: set `active:false`, `current_phase:"complete"`, persist `review_verdict:{recommendation:"APPROVE", architectural_status:"CLEAR", clean:true}`, `qa_verdict:{clean:true, skipped:<boolean>, reason:<string|null>}`, and `completed_at` only when both gates have durable source evidence. Required evidence is either (a) actual `$code-review`/`$ultraqa` stage or native-subagent/thread/tool records, or (b) for QA only, an explicit persisted skip reason for a documented docs-only/trivially non-runtime condition. If that evidence is missing, keep the active phase at `code-review` or `ultraqa` and record a blocker instead of self-attesting a clean gate.
- **On non-clean review or failed QA**: increment `iteration` and `review_cycle`, set `current_phase:"ralplan"`, persist `review_verdict` or `qa_verdict`, persist the phase handoff, and set `return_to_ralplan_reason` to a concise findings-driven reason.
- **Legacy Ralph state**: if a user explicitly selected the legacy Ralph execution lane, phase names and handoff keys may include `ralph`; preserve and resume them rather than rewriting history to Ultragoal.
- **On cancellation**: run `$cancel`; preserve progress for resume rather than deleting handoff artifacts.
</State_Management>

<Continuation_And_Resume>
When the user says `continue`, `resume`, or `keep going` while Autopilot is active, read `autopilot-state.json` and continue from `current_phase`:
- `deep-interview`: clarify requirements and record the handoff artifact.
- `ralplan`: run/update consensus planning from current handoffs and any `return_to_ralplan_reason`.
- `ultragoal`: execute the approved plan durably and record verification/ledger evidence.
- `team`: continue explicit team work only when it is nested under the active Ultragoal story and report evidence back to the leader.
- `code-review`: review the current diff and decide clean vs return-to-ralplan.
- `ultraqa`: run or explicitly skip adversarial QA based on the documented condition, then finish if clean or transition to `ralplan` with findings if not clean.
- `ralph`: resume only for explicit legacy Ralph-path Autopilot state.
- `complete`: report completion evidence; do not restart.

Do not restart discovery or discard handoff artifacts on continuation.
</Continuation_And_Resume>

<Pipeline_Orchestrator>
Autopilot may be represented by the configurable pipeline orchestrator (`src/pipeline/`) when useful. The default Autopilot pipeline contract is:

` ` `text
deep-interview -> ralplan -> ultragoal -> code-review -> ultraqa
` ` `

Pipeline state should use `current_phase` values that match the same phase names (`deep-interview`, `ralplan`, `ultragoal`, `code-review`, `ultraqa`, `complete`, `failed`) and should carry `iteration`, `review_cycle`, `handoff_artifacts`, `review_verdict`, `qa_verdict`, and `return_to_ralplan_reason` alongside stage results. `$team` is not a default pipeline stage; it is an explicit conditional execution engine inside an Ultragoal story.
</Pipeline_Orchestrator>

<Escalation_And_Stop_Conditions>
- Stop and report a blocker when required credentials/authority are missing.
- Stop and report when the same review or QA failure recurs across 3 review cycles with no meaningful new plan.
- Stop when the user says "stop", "cancel", or "abort" and run `$cancel`.
- Otherwise, continue the loop until `$code-review` is clean and `$ultraqa` has passed or been explicitly skipped with evidence.
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Phase `deep-interview` produced/updated clarified requirements or a concise spec
- [ ] Phase `ralplan` produced/updated approved planning artifacts and durable sequential evidence from a subsequent `Architect` approval followed by a subsequent `Critic` approval
- [ ] Phase `ultragoal` implemented and verified the plan with fresh evidence and durable ledger/checkpoint references
- [ ] `$team` was used only if the active Ultragoal story needed coordinated parallel work, or explicitly recorded as not needed
- [ ] Phase `code-review` returned a clean verdict (`APPROVE` + `CLEAR`)
- [ ] Phase `ultraqa` passed, or was explicitly skipped because the change was docs-only/trivially non-runtime with evidence
- [ ] Clean `review_verdict` cites durable source evidence from a real `$code-review` stage/subagent/thread/tool record; `qa_verdict` cites durable `$ultraqa` evidence or an explicit persisted low-risk skip reason; leader-authored summaries alone are not gate evidence
- [ ] `review_verdict.clean` is true, `qa_verdict.clean` is true, and `return_to_ralplan_reason` is null
- [ ] Tests/build/lint/typecheck evidence from Ultragoal is available in handoff artifacts
- [ ] Autopilot state is marked `complete` or cancellation state is preserved coherently
- [ ] User receives a concise summary with clarification, plan, implementation, verification, review, and QA evidence
</Final_Checklist>

<Examples>
<Good>
User: `$autopilot implement GitHub issue #42`
Flow: create/load context snapshot -> `$deep-interview` requirements check -> `$ralplan` issue plan -> `$ultragoal` durable implementation + tests (launch `$team` only if a story needs parallel lanes) -> `$code-review` -> `$ultraqa`; if review or QA requests changes, return to `$ralplan` with findings.
</Good>

<Good>
User: `continue`
Context: Autopilot state says `current_phase:"code-review"`.
Flow: run `$code-review` on current diff, persist verdict, transition to `ultraqa` if clean or to `ralplan` with findings if not clean.
</Good>

<Good>
User: `$autopilot --legacy-ralph finish the migration`
Flow: preserve the explicit legacy Ralph execution choice and run the old Ralph execution lane as an alternate, without changing the documented default Autopilot recommendation.
</Good>

<Bad>
Autopilot invents independent "Expansion", "QA", and "Validation" phases and treats them as the primary lifecycle.
Why bad: this bypasses the strict `$deep-interview -> $ralplan -> $ultragoal -> $code-review -> $ultraqa` contract.
</Bad>
</Examples>

</skill>
```

## 13. line 548 timestamp 2026-06-09T21:17:02.569Z

```text
<subagent_notification>
{"agent_path":"019eae34-4b58-7163-bbf7-61d48eb99a72","status":{"completed":"Verdict: ITERATE  \nArchitectural status: WATCH\n\n**Summary**\nThe direction is sound: it keeps OMX, litkg, Graphiti, and MemPalace optional and tries to route truth back to repo-owned surfaces. The architectural risk is that the proposed `alignment_tools_contract.md` plus a broader `check-agent-memory` can become a second policy layer on top of existing owner docs, which this repo already tries to avoid.\n\n**Analysis**\n- Boundary ownership already exists. `[AGENTS.md](/home/jd/repos/ARIA-NBV/AGENTS.md#L50)` keeps OMX optional, `[.agents/kg/README.md](/home/jd/repos/ARIA-NBV/.agents/kg/README.md#L19)` already owns the litkg role split, `[.agents/kg/README.md](/home/jd/repos/ARIA-NBV/.agents/kg/README.md#L22)` and `[.agents/kg/README.md](/home/jd/repos/ARIA-NBV/.agents/kg/README.md#L23)` already mark Graphiti and MemPalace as optional/separate, `[.agents/references/human_owner_intent.md](/home/jd/repos/ARIA-NBV/.agents/references/human_owner_intent.md#L30)` says to preserve the smallest correct surface, and `[.agents/skills/semantic-scholar-litkg/SKILL.md](/home/jd/repos/ARIA-NBV/.agents/skills/semantic-scholar-litkg/SKILL.md#L60)` treats graphify/Neo4j/Graphiti/MemPalace as optional or separate.\n- That means the new contract is only safe if it is a thin adapter/boundary reference. If it repeats the existing operational table, it conflicts with the repo’s own smallest-surface rule and creates a duplicate authority surface.\n- The validator piece needs tighter scope. `[scripts/validate_agent_memory.py](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L4)` is explicitly narrow today, and `check-agent-memory` runs in the session-start hook `[.codex/hooks.json](/home/jd/repos/ARIA-NBV/.codex/hooks.json#L3)` and in root CI `[Makefile](/home/jd/repos/ARIA-NBV/Makefile#L848)`, so semantic “duplicate ownership language” checks would be noisy and brittle there.\n- A short `/home/jd/.codex/AGENTS.md` pointer is acceptable. The repo already uses thin local entrypoints into canonical guidance in `[CLAUDE.md](/home/jd/repos/ARIA-NBV/CLAUDE.md#L8)` and `[CLAUDE.md](/home/jd/repos/ARIA-NBV/CLAUDE.md#L12)`, so that file should stay pointer-only and not become a second ARIA policy surface.\n\n**Root Cause**\nThe plan is trying to collapse real scaffold drift, but it risks doing so by adding another canonical layer. That helps only if it stays thinner than the docs it points at. If it absorbs role tables or fuzzy validation, it increases entropy instead of reducing it.\n\n**Recommendations**\n1. Keep `alignment_tools_contract.md` thin and cross-surface only. It should describe adapter replaceability, optionality, and boundary rules, but not duplicate the operational role table already present in `.agents/kg/README.md`.\n2. Update `[AGENTS.md](/home/jd/repos/ARIA-NBV/AGENTS.md)` and `[.agents/references/source_order.md](/home/jd/repos/ARIA-NBV/.agents/references/source_order.md)` so they point to the new contract, but do not make the new contract a second owner for KG/operator policy. One doc should own the operational table; the other should defer.\n3. Restrict `[scripts/validate_agent_memory.py](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py)` to deterministic invariants: required references and forbidden runtime leaks. Do not add semantic duplicate-ownership heuristics to `check-agent-memory`, because it is invoked on session start and in root CI.\n4. Keep `/home/jd/.codex/AGENTS.md` as a pointer only. No detailed ARIA policy there.\n\n**Trade-offs**\n| Option | Pros | Cons |\n|--------|------|------|\n| Centralize hard in a new contract and broaden the validator | Fewer places to look | Creates duplicate authority and brittle hooks |\n| Keep the contract thin and the validator deterministic | Preserves source-of-truth boundaries and low-noise checks | Slightly less centralized, one extra file to read |\n\n**Synthesis**\nCentralize only the adapter rules; leave operational ownership with the existing owner docs. That gives you less slop without inventing a new policy layer."}}
</subagent_notification>
```

## 14. line 569 timestamp 2026-06-09T21:19:48.600Z

```text
<subagent_notification>
{"agent_path":"019eae3f-74d7-7ed1-8820-2197fbe782d8","status":{"completed":"**Verdict: APPROVE**\n\n**Architectural/quality status: WATCH**\n\n**Blocking changes:** None.\n\n**Rationale:** The revised PRD is actionable and incorporates the Architect’s required adjustment. It keeps the new surface thin: `.agents/references/alignment_tools_contract.md` owns only cross-surface adapter boundaries, while `AGENTS.md`, `source_order.md`, `verification_matrix.md`, `.configs/litkg.toml`, and litkg/OMX references keep their existing responsibilities. The current repo structure supports this: root `AGENTS.md` is already a dispatcher, `.configs/litkg.toml` already owns KG runtime roles, and `make check-agent-memory` / `make agents-db AGENTS_ARGS='validate'` both pass now.\n\n**Verification improvements before execution completes:**\n- Make `validate_agent_memory.py` check only exact deterministic invariants: contract file exists, root/source-order links exist, and `git ls-files` does not include `.omx/*`, `.codex/config.toml`, or `.codex/hooks.json`.\n- Keep `/home/jd/.codex/AGENTS.md` to a pointer only, ideally one short ARIA-NBV note routing to repo `AGENTS.md` and `.agents/references/source_order.md`.\n- In final QA, include `git status --short --untracked-files=all` evidence that the pre-existing thesis/advisor files were untouched.\n\n**Short gate summary:**\n- Clarity: Good. The plan names files and limits each owner’s role.\n- Verifiability: Good with the deterministic-check tightening above.\n- Completeness: Sufficient for first cleanup pass.\n- Big Picture: Fits the user’s “optional harness, single source of responsibility” intent.\n- Ralplan consistency: Pass, with WATCH status to prevent contract bloat during implementation.\n\n"}}
</subagent_notification>
```

## 15. line 590 timestamp 2026-06-09T21:21:26.368Z

```text
<subagent_notification>
{"agent_path":"019eae41-f933-74b2-86c9-be85999213e3","status":{"completed":"Verdict: ITERATE  \nArchitectural status: WATCH\n\nRemaining required changes:\n- Tighten the `/home/jd/.codex/AGENTS.md` requirement from “add a short ARIA pointer” to an explicit replace/trim instruction that makes the file pointer-only and removes duplicated ARIA policy text. The current PRD wording at [.omx/plans/agent-scaffold-cleanup-prd-20260609.md:30-31](.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L30-L31) is additive, not exclusive, while the test spec already expects the file to “only route” and not duplicate policy at [.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md:22-23](.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md#L22-L23).\n- Add a concrete acceptance check or negative grep for duplicated ARIA policy text in `/home/jd/.codex/AGENTS.md`, so the pointer-only requirement is mechanically enforceable rather than implied.\n\nShort synthesis:\n- The revision does fix the main prior issues: the new contract stays thin and cross-surface at [.omx/plans/agent-scaffold-cleanup-prd-20260609.md:22-29](.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L22-L29), KG operational detail is explicitly kept in existing owner docs at [.omx/plans/agent-scaffold-cleanup-prd-20260609.md:27-31](.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L27-L31), and `validate_agent_memory.py` is still scoped to deterministic invariants at [.omx/plans/agent-scaffold-cleanup-prd-20260609.md:58-62](.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L58-L62). The only remaining architectural gap is the user-local ARIA guidance file, where the PRD still reads as an addition rather than a forced reduction to pointer-only."}}
</subagent_notification>
```

## 16. line 611 timestamp 2026-06-09T21:24:25.270Z

```text
<subagent_notification>
{"agent_path":"019eae44-0fda-7941-bd19-0e4121ee4a67","status":{"completed":"Verdict: ITERATE\n\nArchitectural status: WATCH\n\nRemaining required changes:\n- Tighten the `/home/jd/.codex/AGENTS.md` check so it proves an exact pointer-only ARIA-NBV section or file, not just the absence of a few blacklisted phrases; the current test spec uses a negative `rg` blacklist plus a generic routing check ([`.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md`]( /home/jd/repos/ARIA-NBV/.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md#L15)) ([`.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md`]( /home/jd/repos/ARIA-NBV/.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md#L23)) while the PRD says the rule must be “exclusive and mechanically checkable” and that the file should “contain only a pointer” ([`.omx/plans/agent-scaffold-cleanup-prd-20260609.md`]( /home/jd/repos/ARIA-NBV/.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L77)) ([`.omx/plans/agent-scaffold-cleanup-prd-20260609.md`]( /home/jd/repos/ARIA-NBV/.omx/plans/agent-scaffold-cleanup-prd-20260609.md#L87)).\n\nShort synthesis: The revised PRD now states the exclusive pointer-only intent clearly, but the verification is still phrase-blacklist based rather than exact, so it does not yet mechanically rule out additional ARIA policy drift."}}
</subagent_notification>
```

## 17. line 633 timestamp 2026-06-09T21:38:46.661Z

```text
<subagent_notification>
{"agent_path":"019eae46-b111-7030-80dd-0b94cf85fb2a","status":{"completed":"Verdict: APPROVE\n\nArchitectural status: WATCH\n\nRemaining required changes, if any:\n- Apply the amendment to the checked-in spec; the current test spec still uses the older negative `rg` gate at [`.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md`](./.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md):15 and prose-only review wording at [same file](./.omx/specs/agent-scaffold-cleanup-test-spec-20260609.md):23.\n- The final QA rule should be the exact-block check described in the amendment, not just phrase exclusion.\n\nShort synthesis:\nThe amendment resolves the prior architectural gap by allowing generic user-local guidance while constraining ARIA-specific content to one exact marker-delimited block. That makes the `/home/jd/.codex/AGENTS.md` contract mechanically checkable and keeps repo-owned ARIA policy out of the global file."}}
</subagent_notification>
```

## 18. line 658 timestamp 2026-06-09T21:42:07.298Z

```text
<subagent_notification>
{"agent_path":"019eae53-5bda-7583-9204-ca05df87bfa4","status":{"completed":"Verdict: APPROVE  \nQuality status: WATCH\n\nBlocking changes: none before implementation.\n\nShort rationale: the plan is safe to execute despite WATCH. The PRD is narrow and owner-preserving: one new boundary reference, small routing updates, deterministic validator extensions, and no semantic duplicate-policy sweep. Current repo evidence supports that path: `AGENTS.md` already keeps OMX/runtime state non-public, `source_order.md` owns truth/capture routing, `verification_matrix.md` owns scaffold checks, and `validate_agent_memory.py` is currently narrow enough to extend without optional backend dependencies. Current `make check-agent-memory`, `make agents-db AGENTS_ARGS='validate'`, and `git check-ignore -v .omx .codex/config.toml .codex/hooks.json` pass.\n\nWATCH condition: the test spec’s negative grep for `/home/jd/.codex/AGENTS.md` is not sufficient by itself. Execution must include the Architect amendment as an exact-block final QA check, and repo validation must not read or depend on `/home/jd/.codex/AGENTS.md`.\n\nVerification requirements for execution:\n- Run `make check-agent-memory` and `make agents-db AGENTS_ARGS='validate'`.\n- Confirm `.omx`, `.codex/config.toml`, and `.codex/hooks.json` are ignored and not tracked.\n- Capture pre/post `git status --short` and leave existing dirty thesis/advisor files untouched.\n- Verify the new contract is linked from `AGENTS.md`, `source_order.md`, and `verification_matrix.md`.\n- Run an exact-block Python check for `/home/jd/.codex/AGENTS.md` using the required pointer text, including “exactly one start marker”, “exactly one end marker”, “block equals expected”, and no `ARIA-NBV` text outside the block.\n\nRequired final QA command shape:\n\n` ` `bash\npython3 - <<'PY'\nfrom pathlib import Path\n\npath = Path(\"/home/jd/.codex/AGENTS.md\")\ntext = path.read_text(encoding=\"utf-8\")\nexpected = \"\"\"<!-- ARIA-NBV:POINTER:START -->\n## ARIA-NBV Operator Pointer\n\n- For `/home/jd/repos/ARIA-NBV`, repo `AGENTS.md` owns ARIA policy and routing.\n- Use `.agents/references/source_order.md` for current truth and capture rules.\n- Use `.agents/references/alignment_tools_contract.md` for optional OMX, MCP,\n  KG, memory, graph, and autoresearch adapter boundaries.\n<!-- ARIA-NBV:POINTER:END -->\"\"\"\n\nstart_marker = \"<!-- ARIA-NBV:POINTER:START -->\"\nend_marker = \"<!-- ARIA-NBV:POINTER:END -->\"\nassert text.count(start_marker) == 1\nassert text.count(end_marker) == 1\nstart = text.index(start_marker)\nend = text.index(end_marker) + len(end_marker)\nassert text[start:end] == expected\noutside = text[:start] + text[end:]\nassert \"ARIA-NBV\" not in outside\nprint(\"global ARIA pointer block exact\")\nPY\n` ` `\n\n"}}
</subagent_notification>
```

## 19. line 958 timestamp 2026-06-09T21:58:16.709Z

```text
<subagent_notification>
{"agent_path":"019eae61-d444-76f3-8eed-cee695e9ff47","status":{"completed":"## Code Review Summary\n\n**Recommendation:** APPROVE  \n**Files reviewed:** 7 intended repo files + `/home/jd/.codex/AGENTS.md` pointer block  \n**Total issues:** 0\n\n### Findings\n\nNo findings identified.\n\nThe scaffold change matches the stated intent: `AGENTS.md` points boundary-crossing work to the new contract without making OMX required; `alignment_tools_contract.md` keeps OMX/litkg/graph/memory/MCP/autoresearch as optional evidence or adapter producers; `source_order.md` keeps repo AGENTS/source_order/memory as owners; and the user-local pointer block only redirects back to repo-owned guidance.\n\nThe validator change is narrow and deterministic: it checks the alignment contract exists, verifies required repo references, and rejects tracked `.omx/`, `.codex/config.toml`, or `.codex/hooks.json` runtime state.\n\n### Verification\n\nPassed locally:\n- `make check-agent-memory`\n- `make agents-db AGENTS_ARGS='validate'`\n- `make agents-db`\n- `aria_nbv/.venv/bin/ruff check scripts/validate_agent_memory.py`\n- `PYTHONDONTWRITEBYTECODE=1 aria_nbv/.venv/bin/python -m py_compile scripts/validate_agent_memory.py`\n- `git check-ignore -v .omx .codex/config.toml .codex/hooks.json`\n- exact marker-block read of `/home/jd/.codex/AGENTS.md`\n- `git diff --check` on tracked intended files\n\n### Verification Gaps\n\n`pyright`/`basedpyright`, `ast-grep`, and an explicit `lsp_diagnostics` tool were not available in this environment, so I used Ruff, Python compile, regex pattern scan, and the available Python analysis fallback. I also did not add or run negative regression tests that intentionally remove the alignment link or track forbidden runtime files; the current positive validation path and code inspection cover the scaffold gate, but those failure cases remain unexercised by tests.\n\n"}}
</subagent_notification>
```

## 20. line 965 timestamp 2026-06-09T21:58:41.009Z

```text
<subagent_notification>
{"agent_path":"019eae61-f564-72e0-bc06-326eb73cf337","status":{"completed":"**Summary**\nThe scaffold wiring is directionally correct: the repo-level dispatcher, source-order, verification matrix, and the user-local pointer block all point at the new boundary contract without making `OMX` or the external harnesses a new source of truth. The problem is in the new validator: it checks for presence by substring/prefix, not by exact structure, so the gate is still porous. That makes this `WATCH`, not `CLEAR`.\n\n**Analysis**\n- The ownership split is consistent with the stated intent. [`AGENTS.md`](/home/jd/repos/ARIA-NBV/AGENTS.md#L54) points optional-tool work at the new contract, [`source_order.md`](/home/jd/repos/ARIA-NBV/.agents/references/source_order.md#L26) makes it a boundary reference, [`verification_matrix.md`](/home/jd/repos/ARIA-NBV/.agents/references/verification_matrix.md#L12) documents the new memory check, and the user-local pointer block keeps repo `AGENTS.md` as the owner surface rather than a local policy source. [`/home/jd/.codex/AGENTS.md`](/home/jd/.codex/AGENTS.md#L224)\n- Finding 1, medium: [`scripts/validate_agent_memory.py`](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L164) only checks whether each target file contains the substring `alignment_tools_contract.md`. That can pass on an incidental mention and does not actually prove the intended link/pointer relationship exists in the right place. The new “deterministic scaffold validation” therefore does not fully enforce the ownership boundary it is supposed to protect. [`scripts/validate_agent_memory.py`](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L170)\n- Finding 2, medium: [`scripts/validate_agent_memory.py`](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L26) only forbids tracked runtime paths that start with `.omx/`. The repo guidance treats `.omx/` as operator-local runtime state, but a tracked file literally named `.omx` would bypass this guard. That leaves a small but real loophole in the “forbidden tracked runtime state” check. [`omx_quick_reference.md`](/home/jd/repos/ARIA-NBV/.agents/references/omx_quick_reference.md#L44) [`scripts/validate_agent_memory.py`](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L187)\n\n**Root Cause**\nThe new scaffold encodes ownership rules as broad string/prefix checks instead of exact structural assertions. That is enough to document the boundary, but not enough to guarantee it.\n\n**Recommendations**\n1. Tighten `check_scaffold_alignment()` to validate the exact markdown link or marker block, not just the filename token. High impact, small change.\n2. Expand the forbidden runtime-state predicate to cover the exact `.omx` path as well as `.omx/` descendants. High impact, trivial change.\n\n**Architectural Status**\n`WATCH`\n\n**Trade-offs**\n| Option | Pros | Cons |\n|--------|------|------|\n| Keep substring/prefix checks | Simple and low-maintenance | False positives/negatives can let the scaffold drift silently |\n| Use exact link/path assertions | Preserves the ownership boundary and makes the gate meaningful | Slightly more code and a bit more validation logic |\n\n**References**\n- [`AGENTS.md`](/home/jd/repos/ARIA-NBV/AGENTS.md#L54) - root dispatcher now points optional-tool work at the boundary contract.\n- [`.agents/references/alignment_tools_contract.md`](/home/jd/repos/ARIA-NBV/.agents/references/alignment_tools_contract.md#L3) - thin ownership contract for optional tools and external harnesses.\n- [`.agents/references/source_order.md`](/home/jd/repos/ARIA-NBV/.agents/references/source_order.md#L26) - source-order reference to the boundary contract.\n- [`.agents/references/verification_matrix.md`](/home/jd/repos/ARIA-NBV/.agents/references/verification_matrix.md#L10) - verification matrix entry for the new scaffold check.\n- [`scripts/validate_agent_memory.py`](/home/jd/repos/ARIA-NBV/scripts/validate_agent_memory.py#L155) - new scaffold validation logic and its two gaps.\n- [`/home/jd/.codex/AGENTS.md`](/home/jd/.codex/AGENTS.md#L224) - user-local pointer block that keeps repo policy ownership in the repo."}}
</subagent_notification>
```

## 21. line 1066 timestamp 2026-06-10T06:52:57.471Z

```text
<environment_context>
  <current_date>2026-06-10</current_date>
  <timezone>Europe/Berlin</timezone>
  <filesystem><workspace_roots><root>/home/jd/repos/ARIA-NBV</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>
```

## 22. line 1070 timestamp 2026-06-10T06:52:58.365Z

```text
[$oh-my-codex:code-review](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/code-review/SKILL.md) extract all user messages from "019eac05-1079-7f83-a1bd-90b6575a837c". I'm pretty sure that I requested more features than what you have implemented!
```

## 23. line 1073 timestamp 2026-06-10T06:52:58.368Z

```text
<skill>
<name>oh-my-codex:code-review</name>
<path>/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.11/skills/code-review/SKILL.md</path>
---
name: code-review
description: Run a comprehensive code review
---

# Code Review Skill

Conduct a thorough code review for quality, security, and maintainability with severity-rated feedback.

## When to Use

This skill activates when:
- User requests "review this code", "code review"
- Before merging a pull request
- After implementing a major feature
- User wants quality assessment

## GPT-5.5 Guidance Alignment

- Default to outcome-first progress and completion reporting: state the target result, evidence, validation status, and stop condition before adding process detail.
- Treat newer user task updates as local overrides for the active workflow branch while preserving earlier non-conflicting constraints.
- If correctness depends on additional inspection, retrieval, execution, or verification, keep using the relevant tools until the review is grounded; stop once enough evidence exists.
- Continue through clear, low-risk, reversible next steps automatically; ask only when the next step is materially branching, destructive, credentialed, external-production, or preference-dependent.

Delegates to the `code-reviewer` and `architect` agents in parallel for a two-lane review:

1. **Identify Changes**
   - Run `git diff` to find changed files
   - Determine scope of review (specific files or entire PR)

2. **Launch Parallel Review Lanes**
   - **`code-reviewer` lane** - owns spec compliance, security, code quality, performance, and maintainability findings
   - **`architect` lane** - owns the devil's-advocate / design-tradeoff perspective
   - Both lanes run in parallel on a clean context with explicit scope and artifacts, and produce distinct outputs before final synthesis
   - If either lane cannot be launched or does not return evidence, report `independent review unavailable`; do **not** substitute the current/authoring lane, and do **not** approve or mark the review merge-ready.

3. **Review Categories**
   - **Security** - Hardcoded secrets, injection risks, XSS, CSRF
   - **Code Quality** - Function size, complexity, nesting depth
   - **Performance** - Algorithm efficiency, N+1 queries, caching
   - **Best Practices** - Naming, documentation, error handling
   - **Maintainability** - Duplication, coupling, testability

4. **Severity Rating**
   - **CRITICAL** - Security vulnerability (must fix before merge)
   - **HIGH** - Bug or major code smell (should fix before merge)
   - **MEDIUM** - Minor issue (fix when possible)
   - **LOW** - Style/suggestion (consider fixing)

5. **Architectural Status Contract**
   - **CLEAR** - No unresolved architectural blocker was found
   - **WATCH** - Non-blocking design/tradeoff concern that must appear in the final synthesis
   - **BLOCK** - Unresolved design concern that prevents a merge-ready verdict

6. **Specific Recommendations**
   - File:line locations for each issue
   - Concrete fix suggestions
   - Code examples where applicable

7. **Final Synthesis**
   - Combine the `code-reviewer` recommendation and the architect status into one final verdict
   - Approval requires explicit evidence from both independent lanes; missing or failed delegation is a blocking unavailable-review state, not an approval fallback
   - Deterministic merge gating rules:
     - If architect status is **BLOCK**, final recommendation is **REQUEST CHANGES**
     - Else if `code-reviewer` recommendation is **REQUEST CHANGES**, final recommendation is **REQUEST CHANGES**
     - Else if architect status is **WATCH**, final recommendation is **COMMENT**
     - Else final recommendation follows the `code-reviewer` lane
   - The final report must make architect blockers impossible to miss

## Agent Delegation

Do not self-review as a fallback. If the `code-reviewer` or `architect` agent path is missing, unavailable, skipped, or fails, emit a clear unavailable-review result and block approval until the independent lane evidence exists.

Respect the user's current model and reasoning/effort selection when launching review lanes. Do not pass `model` or `reasoning_effort` overrides in the review-lane task calls unless the user explicitly asks for review-specific overrides; omitting them lets native subagents inherit the active session settings.

` ` `
task(
  agent_type="code-reviewer",
  prompt="CODE REVIEW TASK

Review code changes for quality, security, and maintainability.

This is the code/spec/security lane. Do not absorb architectural ownership.

Scope: [git diff or specific files]

Review Checklist:
- Security vulnerabilities (OWASP Top 10)
- Code quality (complexity, duplication)
- Performance issues (N+1, inefficient algorithms)
- Best practices (naming, documentation, error handling)
- Maintainability (coupling, testability)

Output: Code review report with:
- Files reviewed count
- Issues by severity (CRITICAL, HIGH, MEDIUM, LOW)
- Specific file:line locations
- Fix recommendations
- Approval recommendation (APPROVE / REQUEST CHANGES / COMMENT)"
)

task(
  agent_type="architect",
  prompt="ARCHITECTURE / DEVIL'S-ADVOCATE REVIEW TASK

Review the same code changes from the architecture/tradeoff perspective.

Scope: [git diff or specific files]

Focus:
- System boundaries and interfaces
- Hidden coupling or long-term maintainability risks
- Tradeoff tension the main reviewer might miss
- Strongest counterargument against approving as-is

Output:
- Architectural Status: CLEAR / WATCH / BLOCK
- File:line evidence for each concern
- Concrete tradeoff or design recommendation"
)

Run both lanes in parallel, then synthesize them with the deterministic rules above.
` ` `

## External Model Consultation (Preferred)

The code-reviewer agent SHOULD consult Codex for cross-validation.

### Protocol
1. **Form your OWN review FIRST** - Complete the review independently
2. **Consult for validation** - Cross-check findings with Codex
3. **Critically evaluate** - Never blindly adopt external findings
4. **Graceful optional consultation fallback** - Never block because optional external consultation tools are unavailable; this does not waive the required independent `code-reviewer` and `architect` lanes

### When to Consult
- Security-sensitive code changes
- Complex architectural patterns
- Unfamiliar codebases or languages
- High-stakes production code

### When to Skip
- Simple refactoring
- Well-understood patterns
- Time-critical reviews
- Small, isolated changes

### Tool Usage
Prefer native `code-reviewer` agent consultation or CLI-backed `ask_codex` surfaces when available. Optional MCP compatibility ask tools may be used only when already enabled. If optional external consultation tools are unavailable, continue with the required independent `code-reviewer` and `architect` lanes; do not replace those lanes with self-review.

**Note:** Codex calls can take up to 1 hour. Consider the review timeline before consulting.

## Output Format

` ` `
CODE REVIEW REPORT
==================

Files Reviewed: 8
Total Issues: 12
Architectural Status: WATCH

CRITICAL (0)
-----------
(none)

HIGH (0)
--------
(none)

MEDIUM (7)
----------
1. src/api/auth.ts:42
   Issue: Email normalization logic is duplicated instead of reusing the shared helper
   Risk: Validation rules can drift between authentication paths
   Fix: Route both paths through the shared normalization helper

2. src/components/UserProfile.tsx:89
   Issue: Derived permissions are recalculated on every render
   Risk: Avoidable work during profile refreshes
   Fix: Memoize the derived permissions list or compute it upstream

3. src/utils/validation.ts:15
   Issue: Form-layer and server-layer validation messages are defined separately
   Risk: User-facing validation guidance can become inconsistent
   Fix: Share one validation message helper across both call sites

LOW (5)
-------
...

ARCHITECTURE WATCHLIST
----------------------
- src/review/orchestrator.ts:88
  Concern: Review result synthesis relies on implicit ordering rather than an explicit blocker contract
  Status: WATCH
  Recommendation: Define deterministic merge gating before expanding reviewers

SYNTHESIS
---------
- code-reviewer recommendation: COMMENT
- architect status: WATCH
- final recommendation: COMMENT

RECOMMENDATION: COMMENT

Address any WATCH concerns before treating the change as merge-ready.
` ` `

## Review Checklist

The `code-reviewer` lane checks:

### Security
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs sanitized
- [ ] SQL/NoSQL injection prevention
- [ ] XSS prevention (escaped outputs)
- [ ] CSRF protection on state-changing operations
- [ ] Authentication/authorization properly enforced

### Code Quality
- [ ] Functions < 50 lines (guideline)
- [ ] Cyclomatic complexity < 10
- [ ] No deeply nested code (> 4 levels)
- [ ] No duplicate logic (DRY principle)
- [ ] Clear, descriptive naming

### Performance
- [ ] No N+1 query patterns
- [ ] Appropriate caching where applicable
- [ ] Efficient algorithms (avoid O(n²) when O(n) possible)
- [ ] No unnecessary re-renders (React/Vue)

### Best Practices
- [ ] Error handling present and appropriate
- [ ] Logging at appropriate levels
- [ ] Documentation for public APIs
- [ ] Tests for critical paths
- [ ] No commented-out code

## Architect Lane Checklist

The `architect` lane checks:

- [ ] Boundary or interface changes are explicit
- [ ] New coupling/tradeoff risks are surfaced
- [ ] Long-horizon maintainability concerns are evidence-backed
- [ ] Architectural status is one of `CLEAR`, `WATCH`, or `BLOCK`
- [ ] Any `BLOCK` concern cites the reason merge-ready status should be withheld

## Approval Criteria

**APPROVE** - `code-reviewer` returns APPROVE, architect status is `CLEAR`, and both independent lanes returned evidence
**REQUEST CHANGES** - `code-reviewer` returns REQUEST CHANGES, architect status is `BLOCK`, or required independent review delegation is unavailable/skipped/failed
**COMMENT** - `code-reviewer` returns COMMENT with architect status `CLEAR`, architect status is `WATCH`, or only LOW/MEDIUM improvements remain


## Scenario Examples

**Good:** The user says `continue` after the workflow already has a clear next step. Continue the current branch of work instead of restarting or re-asking the same question.

**Good:** The user changes only the output shape or downstream delivery step (for example `make a PR`). Preserve earlier non-conflicting workflow constraints and apply the update locally.

**Bad:** The user says `continue`, and the workflow restarts discovery or stops before the missing verification/evidence is gathered.

## Use with Other Skills

**With Team:**
` ` `
/team "review recent auth changes and report findings"
` ` `
Includes coordinated review execution across specialized agents.

**With Ralph:**
` ` `
/ralph code-review then fix all issues
` ` `
On the explicit Ralph path, review findings should flow into automatic fix follow-up without another permission prompt. Plain `code-review` itself remains read-only and does **not** promise auto-fix.

**With Ultrawork:**
` ` `
/ultrawork review all files in src/
` ` `
Parallel code review across multiple files.

## Best Practices

- **Review early** - Catch issues before they compound
- **Review often** - Small, frequent reviews better than huge ones
- **Address CRITICAL/HIGH first** - Fix security and bugs immediately
- **Consider context** - Some "issues" may be intentional trade-offs
- **Learn from reviews** - Use feedback to improve coding practices

</skill>
```

