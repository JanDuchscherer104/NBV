# PRD: ARIA-NBV Agent Scaffold Cleanup

## Decision

Tighten ARIA-NBV's agent scaffold by enforcing one owner per durable
responsibility, without creating a new broad policy layer. Add only a thin
adapter/boundary reference for replaceable operator tools; leave existing owner
docs in charge of their operational details.

## Drivers

- Avoid duplicated guidance across `AGENTS.md`, skills, references, memory, KG
  docs, and runtime tool docs.
- Preserve plain Codex + repo `AGENTS.md` as sufficient for normal repo work.
- Keep OMX, litkg, graph outputs, memory backends, and external autoresearch
  frameworks optional and replaceable.
- Add deterministic scaffold checks for objective drift; avoid semantic or fuzzy
  duplicate-policy checks in hot validation paths.

## Scope

- Add a compact `.agents/references/alignment_tools_contract.md` that owns only
  cross-surface adapter boundaries: tools produce evidence, repo owner surfaces
  decide truth, and external harnesses stay replaceable.
- Route root `AGENTS.md` and source-order guidance to that contract without
  copying long policy.
- Keep operational KG/backend details in the existing KG/litkg owner docs.
- Extend `scripts/validate_agent_memory.py` only for deterministic invariants:
  required scaffold links and forbidden committed runtime leaks.
- Replace or trim any ARIA-specific text in `/home/jd/.codex/AGENTS.md` to a
  pointer-only note. User-local guidance must route to repo-owned ARIA sources
  and must not duplicate ARIA policy.

## Non-Goals

- Do not introduce LangGraph, Graphiti, MemPalace, Graphity, Graphify, or any
  autoresearch framework as a required dependency.
- Do not rewrite all skills.
- Do not make `.omx/` or user-local `.codex` runtime files public docs.
- Do not duplicate the KG operational role table already owned by KG/litkg docs.
- Do not rely on litkg claim-check as a hard automation gate until verdict false
  positives are fixed.

## Implementation Shape

- New `.agents/references/alignment_tools_contract.md`:
  - thin boundary rules;
  - source-of-truth rule: tools never own truth;
  - adapter replaceability rule for OMX/autoresearch/MCP/KG backends;
  - pointers to existing KG/litkg and verification owners for details.
- Root `AGENTS.md`:
  - add a short route under Optional Operator Tools pointing to the new contract.
- `.agents/references/source_order.md`:
  - add the new reference as the owner for cross-surface tool/adapter boundary
    rules only.
- `.agents/references/verification_matrix.md`:
  - make `make check-agent-memory` explicitly cover deterministic scaffold
    alignment checks.
- `scripts/validate_agent_memory.py`:
  - keep debrief checks unchanged;
  - add deterministic checks for required reference links and forbidden runtime
    leaks;
  - no heuristic duplicate-language or semantic policy checks.
- `/home/jd/.codex/AGENTS.md`:
  - replace/trim ARIA-specific guidance to one pointer-only note;
  - remove duplicated ARIA policy text if present.

## Acceptance Criteria

- A new agent can identify where adapter-boundary rules live and where each
  underlying policy remains owned.
- External graph/memory/autoresearch tools are documented as replaceable
  evidence producers, never source-of-truth owners.
- `make check-agent-memory` passes and exercises deterministic scaffold checks.
- `make agents-db AGENTS_ARGS='validate'` passes.
- Unrelated dirty thesis/advisor files are untouched.
- `/home/jd/.codex/AGENTS.md` contains only a pointer for ARIA-NBV and does not
  duplicate ARIA policy phrases such as `Invalidity is a hard mask/reason`,
  `Do not treat V0 GT`, `Gymnasium/SB3/online simulator`, or ARIA-specific
  verification command lists.

## Architect Review Incorporated

Architect verdict was `ITERATE` / `WATCH`. The plan was revised so the new
contract is thin, operational KG roles stay in existing KG/litkg docs, and the
validator avoids semantic duplicate-ownership heuristics. A second Architect
re-review required making the `/home/jd/.codex/AGENTS.md` pointer-only rule
exclusive and mechanically checkable; this revision incorporates that.
