## Prometheus Strict Plan

### Target Result
- Produce a ranked, execution-ready cleanup plan for ARIA-NBV agent-scaffold
  debt found in the 2026-06-19 reviews, prioritizing validation, safety, and
  identity/routing correctness before broad simplification.

### Clarified Requirements (Metis)
- Planning-only output; no package behavior, public thesis implementation,
  GitHub remote writes, or pandas/Plotly implementation in the first pass.
- Treat external reviews as advisory. Every execution item must be grounded in
  checked-in repo evidence before editing.
- Preserve dirty user or agent work. Execution should use either an isolated
  worktree from a known base or a current-worktree preflight ownership map
  before touching scaffold-adjacent dirty files.
- Keep `refactor-016` as the main scaffold consolidation owner unless
  `agents-db` explicitly updates ownership.
- Existing validators are necessary but insufficient: `make agents-db
  AGENTS_ARGS='validate'` and `make check-agent-memory` currently pass, while
  known skill metadata, handoff, and runtime-safety gaps remain.

### Critique Resolved (Momus)
- Missing validation substrate -> add PR0/PR1 scaffold-audit bootstrap before
  broad cleanup.
- Runtime safety was too late -> move Gemini `auto_edit` and MemPalace `Write`
  handling into PR1.
- Review identity cleanup was too late -> fix machine-facing `code-review`
  name/handoff issues in PR1 before using review as a gate.
- PR2 was overloaded -> split metadata normalization, `agent-behavior`
  reduction, and context/litkg boundary tuning.
- Broad domain cleanup was unsafe -> make later slices record-specific and
  owner-specific.
- Post-plan gap: PR1 audit must distinguish hard failures from report-only
  findings until PR2 resolves intentional carry-forward drift.
- Post-plan gap: `agent-behavior` must not be slimmed or removed until its
  lane-selection, request-traceability, dirty-worktree, and verification
  invariants have an explicit replacement owner.

### ROI + Urgency Ranking
| Rank | Work package | ROI | Urgency | Reason |
| --- | --- | --- | --- | --- |
| 1 | PR0 scaffold audit spec/inventory | Very high | Immediate | Locks current facts and dirty-worktree ownership before edits. |
| 2 | PR1 `make scaffold-audit` bootstrap | Very high | Immediate | Turns review findings into repeatable gates. |
| 3 | PR1 safety hardening | High | Immediate | `auto_edit` and plugin `Write` are write-authority risks. |
| 4 | PR1 identity/handoff cleanup | High | High | Prevents stale or non-native skill routing before review gates depend on it. |
| 5 | PR2a metadata/routing normalization | High | High | Fixes `mode=scaffold`, missing `metadata.mode`, and required-field drift without behavior shrink. |
| 6 | PR2b `agent-behavior` slimming | Medium-high | Medium | Valuable only after validation and replacement ownership prove equivalent routing. |
| 7 | PR2c context/litkg boundary tuning | Medium-high | Medium | Preserve useful separation; do not merge local discovery and KG retrieval prematurely. |
| 8 | Record-tied domain slices | Medium | Medium | Reduce root/skill sprawl only with owner, acceptance, and tests per slice. |
| 9 | pandas/Plotly/tooling polish | Low now | Later | Useful, but not a scaffold safety blocker. |

### Oracle Execution Plan
1. **PR0, scaffold lead: audit-only inventory.**
   - Record current dirty scaffold-adjacent files and choose one execution
     isolation mode: isolated worktree from known base, or current-worktree
     preflight ownership map.
   - Enumerate the intended skill metadata contract, skill directory/name
     policy, handoff label policy, plugin/hook permission policy, and
     `scaffold-audit` report shape.
   - No cleanup edits.

2. **PR1, tooling executor: scaffold-audit bootstrap.**
   - Add `make scaffold-audit` and a repo-scoped audit script.
   - PR1 hard failures: audit command import/runtime errors, missing skills
     directory, unreadable frontmatter, directory/frontmatter name mismatch for
     machine-facing skills, unsafe write defaults without allowlist,
     unsupported handoff namespace without allowlist.
   - PR1 report-only findings carried to PR2: missing `metadata.mode`,
     `agent-behavior` using `mode: scaffold`, hot-path length warnings,
     overlapping triggers, and broad `applies_to: "**"` warnings.
   - Acceptance: audit fails on at least one known hard issue before fixes, then
     passes hard gates after PR1 while still reporting PR2 carry-forward items.

3. **PR1, safety executor: runtime authority hardening.**
   - Remove or narrow checked-in Gemini `defaultApprovalMode: auto_edit`.
   - Remove, narrow, or explicitly allowlist MemPalace `Write` capability in
     `.codex-plugin/plugin.json`.
   - Keep optional tools evidence/proposal-only unless an owner surface promotes
     a specific capability.

4. **PR1, routing executor: identity and handoff cleanup.**
   - Normalize `code-review` directory/frontmatter identity.
   - Replace `diagnose-aria` `omx:analyze` and `code-review`
     `github:gh-address-comments` handoff labels with installed/native skill
     names, declared capabilities, or documented optional plugin workflows.

5. **PR2a, scaffold executor: metadata normalization without behavior shrink.**
   - Update `.agents/references/skill_style_guide.md` to match the accepted
     mode vocabulary and validator behavior.
   - Normalize all `.agents/skills/*/SKILL.md` metadata fields.
   - Keep `agent-behavior` active except for schema-compatible corrections.

6. **PR2b, scaffold simplifier: `agent-behavior` slimming.**
   - Proceed only after PR1 and PR2a gates pass.
   - Before slimming/removal, move or explicitly assign these invariants to
     root `AGENTS.md` or another owner: lane selection, assumption naming,
     request-traceable diffs, dirty-worktree preservation, and verification
     before completion.
   - Acceptance: routing fixtures for scaffold/docs/package/memory examples
     make the same owner decisions before and after.

7. **PR2c, KG/context owner: context/litkg boundary tuning.**
   - Clarify local deterministic discovery versus KG-backed retrieval and claim
     checks.
   - Do not merge `aria-nbv-context` and `aria-litkg-memory` unless audit
     scenarios prove duplicated responsibilities and preserve deterministic
     local fallback plus source-backed KG escalation.

8. **PR3+, record-specific executors: domain and prose slices.**
   - Execute separate slices tied to concrete records such as `issue-012`,
     `refactor-016`, `issue-023`, `issue-025`, `todo-003`, or `todo-004`.
   - Each slice owns one area: root guardrail trimming,
     docs/code-review/simplification hot-path slimming, agents-db record style,
     alignment-tool boundary, RRI contract skill, rollout/Q_H contract skill, or
     VIN training/eval skill.

9. **Deferred lane: data-analysis/visualization skills.**
   - Revisit pandas/Plotly only after scaffold-audit, safety, and routing gates
     are green.

### Verification Matrix
| Claim | Required evidence | Owner/lane |
| --- | --- | --- |
| Execution will not overwrite unrelated dirty work | isolated worktree path or current-worktree preflight ownership map; `git status --short` captured before edits | PR0 scaffold |
| Scaffold audit is repo-scoped and portable | `make scaffold-audit`; no dependency on `/home/jd/.codex/AGENTS.md`; `make check-agent-memory` | PR1 tooling |
| PR1 hard/report split is honored | audit output distinguishes hard failures from PR2 carry-forward warnings | PR1 tooling |
| Unsafe automation defaults are resolved | `rg -n "defaultApprovalMode|auto_edit|\"Write\"" .gemini .codex-plugin .codex` plus allowlist if retained | PR1 safety |
| Handoff labels resolve to installed/native workflows or declared capabilities | `make scaffold-audit`; targeted `rg` for `omx:analyze` and `github:gh-address-comments` | PR1 routing |
| Skill metadata contract matches live skills | `make scaffold-audit`; `rg -n "^  mode:" .agents/skills/*/SKILL.md`; local skill validator output | PR2a scaffold |
| `agent-behavior` reduction preserves behavior | before/after routing fixture doc or script for scaffold/docs/package/memory scenarios | PR2b simplifier |
| Context and litkg remain correctly separated | scenario checks for local file lookup versus KG-backed claim/routing tasks | PR2c KG/context |
| Agents DB remains valid | `make agents-db AGENTS_ARGS='validate'` and `make agents-db` | every PR |
| Memory/guidance hygiene remains valid | `make check-agent-memory` | every PR |
| No package/public thesis behavior changed | `git diff --stat`; no changes under `aria_nbv/` or public thesis docs unless explicitly scoped | every PR |

### Rollback And Escalation
- Roll back PR1 if the audit expands beyond repo-scoped scaffold surfaces,
  breaks `make check-agent-memory` / `make agents-db AGENTS_ARGS='validate'`
  without a local fix, or turns report-only drift into blocking failure before
  the owning PR.
- Roll back PR2 if routing coverage shrinks without an explicit replacement
  owner and fixture evidence.
- Escalate to the user before retaining MemPalace `Write`, keeping Gemini
  `auto_edit`, changing GitHub remote behavior, or authorizing any
  external-production action.

### Artifact
- Durable plan path: `.omx/plans/prometheus-strict/agent-scaffold-roi-2026-06-19.md`

### Handoff
- Recommended next workflow:
  `$ultragoal "ARIA-NBV scaffold ROI cleanup: execute PR0 validation inventory, PR1 scaffold-audit/safety/handoff hardening, PR2 metadata/routing cleanup, then record-tied domain slices; keep package behavior, public thesis implementation, GitHub writes, and pandas/plotly work out of scope."`
- Use `$team` only after PR1 is green, and only for independent PR2a/PR2c or
  record-specific slices with no shared-file conflicts.
- Stop condition: all planned packages have passing verification evidence, or
  the next package is blocked by an unresolved owner/safety decision.

### Clean-Room Credit
Inspired by OMO Prometheus (`code-yeongyu/oh-my-openagent`), reimplemented from
concept under MIT.
