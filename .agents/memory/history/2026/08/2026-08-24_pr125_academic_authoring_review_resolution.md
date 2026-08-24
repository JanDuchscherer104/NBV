---
id: 2026-08-24_pr125_academic_authoring_review_resolution
date: 2026-08-24
title: "PR 125 academic authoring review resolution"
status: done
topics: [scaffold, academic-writing, scientific-review, typst, routing]
confidence: high
canonical_updates_needed:
  - .agents/skills/README.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/ci_impact.py
  - scripts/scaffold_audit.py
  - .agents/skills/scientific-review/references/review-protocol.md
touched_owner_paths:
  - .agents/skills/README.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/source-grounded-workflow.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/scientific-review/references/review-protocol.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/scaffold/run_routing_trials.py
  - scripts/scaffold_audit.py
  - scripts/ci_impact.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_routing_trials.py
repo_object_format: sha1
repo_head: 348ccd1271d902ea2c409de63bb0d4bb53175c2b
repo_branch: "codex/pr109-academic-scaffold-salvage"
worktree_kind: linked
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
---

## Task

Resolve the remaining valid review findings for the academic-authoring skill
split while retaining separate authoring, review, and Typst realization owners.

## Decision

Keep `scientific-review` as a broad advisory review skill, but route each
review kind to existing claim, section, notation, empirical, and active-thesis
owners. Keep the shared phase transition in the skills style guide rather than
duplicating it in all three skills.

## Findings

- Independent review requires a fresh candidate-bound context; otherwise its
  result is advisory.
- A repository-edit request can compose authoring, optional review, and Typst
  realization, but scientific release remains a separate human/evidence gate.
- The focused routing suite now uses natural synthesis, mechanical-repair,
  frozen-review, claim-revision, empirical-revision, and non-writing cases.
- Workspace-write routing cases must produce the required active-Thesis diff
  and compile/render receipt; their disposable subject checkout excludes both
  evaluator fixtures and the candidate repository history.
- Empirical-result candidates need a candidate-bound review without a blocking
  finding before they are ready for Typst realization.
- Authoring-owner changes trigger both documentation and scaffold CI gates.
- Routing subjects exclude evaluator fixtures, tests, debriefs, and OMX state;
  their fresh Git baseline detects untracked and committed writes, and
  workspace-write trials accept only the required Typst roots plus a full-page
  render receipt.
- Empirical readiness requires an independent review receipt separately from
  its blocking, advisory, or clear finding gate.
- Subject cleanup removes only the exact linked-worktree registry entry; a
  sibling-worktree regression proves unrelated registrations survive.
- Baseline evidence includes ignored files, and proof compares every rendered
  PNG page identity with Poppler's bounded PDF page count.
- Bubblewrap mounts only the sanitized subject, a separate receipt directory,
  the required system runtime files, and an empty Codex home; it never mounts
  host authentication, and its regression proves the evaluator's absolute
  fixture path cannot be read.
- Bubblewrap execution probes are conditional on a host Bubblewrap binary;
  every environment still checks the immutable-schema sandbox command shape.
- The portable sandbox command-shape test uses a mounted system command rather
  than requiring Codex on every CI runner; the separate Bubblewrap integration
  test exercises the resolved Codex runtime whenever both binaries are present.
- Routing subjects and model-based verifiers now require an explicit local
  Responses-compatible broker, use a credential-free custom provider inside
  Bubblewrap, and never mount host `auth.json`. The current machine has no
  configured broker or API key, so a live current-head academic routing receipt
  remains unavailable rather than falling back to host credentials.
- The trial report schema is mounted read-only outside the model-writable
  receipt, trial receipts are checked against that canonical schema before
  adjudication, and verifier stdout/stderr now have the same bounded capture
  and fail-closed overflow behavior as subject execution.
- Host-captured streams, final reports, and verifier output now remain outside
  the model-writable subject receipt. Both schemas are frozen evaluator inputs
  and removed from the subject checkout; a process-group termination escalation
  bounds timeout cleanup, and Bubblewrap mounts the exact resolved Codex
  runtime rather than relying on its ambient PATH.
- Trial and verifier receipts are opened with `O_NOFOLLOW`, verified regular,
  and read under their byte bounds, so a sandbox-created symlink cannot turn a
  report read into a host-file read.
- Typst compilation and page rendering run inside a separate network-isolated
  Bubblewrap namespace. The exact Typst executable and, when locally available,
  its read-only package cache are mounted explicitly; rendering is skipped after
  compilation failure. The trusted renderer is an attested evaluator fixture,
  so `--head` cannot combine tested thesis sources with a different renderer.
- Workspace-write layout-repair trials now require the same active-source diff
  and Typst receipt as claim and empirical revisions. Trial and verifier final
  messages are derived from bounded host-captured JSONL, and the verifier runs
  in an empty evaluator-owned checkout rather than the modified subject.
- The controller relays only the configured host-loopback Responses broker over
  a private Unix socket. Trial and verifier Bubblewrap namespaces are network
  unshared and reach only an in-namespace TCP-to-socket relay; they cannot
  probe other host-loopback services.
- Routing receipts accept a final model response only when it is a completed
  item and no nonblank event follows it before `turn.completed`; this fails
  closed for unfinished messages and all late tool, search, file-change,
  reasoning, todo, error, and turn activity.
- The verifier's declared report byte bound is enforced on UTF-8 encoded text,
  not Python character count, so multi-byte output cannot exceed the contract.
- A receipt response is trusted only from an `item.completed` agent-message
  event; an unfinished `item.started` message cannot become terminal evidence.
- Bubblewrap binds the resolved Codex executable itself, never its parent
  runtime directory, so a user-level `~/bin/codex` cannot expose the home
  directory to the sandboxed model.
- The submission proof uses the bounded-process supervisor and passes only
  when the intended missing-evidence diagnostic is observed from an executed
  nonzero submission compile; unrelated errors, timeouts, launch failures, and
  overflow cannot satisfy the gate.
- Malformed JSONL whose decoded agent message contains an unencodable UTF-8
  surrogate fails verifier receipt validation rather than raising an exception.
- PR #104 had no unresolved review threads at its exact live head, so it needed
  no retrospective patch.

## Commits

- [6c1669ac1d4c7367148a481fcbf88b625135d903](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6c1669ac1d4c7367148a481fcbf88b625135d903) — implementation: compose academic authoring phases
- [6f7d170b9b88607a333a4de00bccb58c3abb06d1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6f7d170b9b88607a333a4de00bccb58c3abb06d1) — implementation: enforce authoring routing evidence
- [a76cef4590579f46dff29e59c398529ab9443765](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a76cef4590579f46dff29e59c398529ab9443765) — implementation: close routing review gaps
- [8f74f1183dbb09b00900cf66bd6225dba6039959](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8f74f1183dbb09b00900cf66bd6225dba6039959) — implementation: preserve sibling worktree registrations
- [3e61fb34c2c17083a58c3c44d68d2d53ab0fd790](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3e61fb34c2c17083a58c3c44d68d2d53ab0fd790) — implementation: close routing evidence escapes
- [e2348b3091932c882e7d8c55b447e86c5db78388](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e2348b3091932c882e7d8c55b447e86c5db78388) — implementation: isolate routing trial subjects
- [6393da2cae8f4e911f8f86bf5a2d851b67d0bf25](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6393da2cae8f4e911f8f86bf5a2d851b67d0bf25) — test: make routing isolation portable
- [9f08d5586d8455642dfdc51bfdf8445203e533cb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9f08d5586d8455642dfdc51bfdf8445203e533cb) — implementation: bound and validate routing receipts
- [b36b376487cfb5704c5e15fb626ebb404a25a93a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b36b376487cfb5704c5e15fb626ebb404a25a93a) — implementation: isolate evaluator receipts and runtime
- [e9e04fc26c78dcf4eae223f83bc71a9b9d6a43df](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e9e04fc26c78dcf4eae223f83bc71a9b9d6a43df) — test: keep the sandbox command contract portable
- [f25dacd8a65e2d01b13335a431eabd0c7f88a486](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f25dacd8a65e2d01b13335a431eabd0c7f88a486) — implementation: isolate routing trials from Codex auth
- [679aa2f202bba9de04195de1088eeefbb3cbb983](https://github.com/JanDuchscherer104/ARIA-NBV/commit/679aa2f202bba9de04195de1088eeefbb3cbb983) — test: keep verifier sandbox tests portable
- [804930a42c748ad1b0f08dff9a4769455975c5b1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/804930a42c748ad1b0f08dff9a4769455975c5b1) — implementation: harden routing trial receipts and proof
- [f54e641926793c08e7a410a38392069867bde7b8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f54e641926793c08e7a410a38392069867bde7b8) — implementation: isolate Typst proof execution
- [5bfe12c81132156c097cd99fb2a4185751dde6f5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/5bfe12c81132156c097cd99fb2a4185751dde6f5) — implementation: isolate routing adjudication evidence
- [335935f6287f64ce9131bef79bf369dc28649e69](https://github.com/JanDuchscherer104/ARIA-NBV/commit/335935f6287f64ce9131bef79bf369dc28649e69) — implementation: confine routing broker network
- [6830720bbe15385826c51e22067eb0ba28f69c3e](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6830720bbe15385826c51e22067eb0ba28f69c3e) — test: keep broker isolation checks portable
- [bdfcea0dccb229daf0ad682b1cc00ba15b23ab42](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bdfcea0dccb229daf0ad682b1cc00ba15b23ab42) — implementation: make routing receipts terminal
- [39b828b5a6a5f442ca803fd1a84049c5e62b1c4b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/39b828b5a6a5f442ca803fd1a84049c5e62b1c4b) — implementation: validate exact routing write paths
- [8ca4b57d129ae3da376e5ed4d5e7df75683762f3](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8ca4b57d129ae3da376e5ed4d5e7df75683762f3) — implementation: reject all late routing activity
- [996223bfe01d4a991aca72ca540a0135d9a8bfba](https://github.com/JanDuchscherer104/ARIA-NBV/commit/996223bfe01d4a991aca72ca540a0135d9a8bfba) — implementation: fail closed on terminal receipts
- [3126875ea0bb46cda63c37e25db3b08ff3db8f2d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3126875ea0bb46cda63c37e25db3b08ff3db8f2d) — implementation: seal routing runtime boundary
- [348ccd1271d902ea2c409de63bb0d4bb53175c2b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/348ccd1271d902ea2c409de63bb0d4bb53175c2b) — implementation: prove routing gates explicitly

## Verification

- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_agent_governance_g002.py scripts/tests/test_routing_trials.py scripts/tests/test_scientific_review_trials.py` — 68 passed.
- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py scripts/tests/test_agent_governance_g002.py scripts/tests/test_scientific_review_trials.py scripts/tests/test_debrief_index.py` — 124 passed, 50 subtests passed.
- `make scaffold-audit scaffold-audit-self-test ci-impact-self-test check-agent-memory PYTHON_INTERPRETER=python3` — passed.
- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py scripts/tests/test_agent_governance_g002.py scripts/tests/test_scientific_review_trials.py` — 90 passed, 51 subtests passed.
- The three modified skills passed the skill validator.
- `git diff --check` and routing fixture JSON/JSONL parsing passed.
- `uv run --no-project --with pytest pytest -q scripts/tests/test_routing_trials.py` — 47 passed, including real local Bubblewrap probes.
- CI-equivalent scaffold verification with pytest supplied by `uv` — 92 passed; agent-status, governance, Graphify, and worktree setup checks passed.
- `uv run --no-project --with pytest pytest -q scripts/tests/test_routing_trials.py` — 49 passed, including process-group timeout escalation and exact Codex-runtime Bubblewrap proof.
- CI-equivalent scaffold verification with pytest supplied by `uv` — 94 passed; agent-status, governance, Graphify, and worktree setup checks passed.
- `uv run --no-project --with pytest pytest -q scripts/tests/test_routing_trials.py` — 49 passed; Ruff and `git diff --check` passed.
- `uv run --no-project --with pytest pytest -q scripts/tests/test_routing_trials.py` — 57 passed, including Bubblewrap proof that the subject cannot access `/codex-home/auth.json`; routing listing remains available without a broker and live execution fails closed when one is absent.
- `uv run --no-project --with pytest --with ruff pytest -q scripts/tests/test_routing_trials.py` — 64 passed, including a real isolated compile and render of the active thesis; Ruff and `git diff --check` passed.
- `uv run --no-project --with pytest pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py` — 83 passed, 51 subtests passed; receipt-terminal and UTF-8 byte-bound regressions passed.
- `uv run --no-project --with pytest --with ruff pytest -q scripts/tests/test_routing_trials.py` — 71 passed, including unfinished-message and home-level-runtime mount regressions; Ruff and `git diff --check` passed.
- `uv run --no-project --with pytest --with ruff pytest -q scripts/tests/test_routing_trials.py` — 75 passed, including late top-level events, UTF-8 surrogates, and submission timeout/wrong-diagnostic regressions; Ruff, scaffold audit, CI-impact self-test, G002 governance, and `git diff --check` passed.

## Canonical Owner Impact

The skills style guide owns cross-skill phase states. Individual skills retain
only their own workflow branches, and routing fixtures remain the tested
navigation contract rather than a source of scientific truth.
