---
kind: spec
status: current
---

# Trusted External Practices for the ARIA-NBV Agent Scaffold

## Executive Conclusion

The strongest external guidance supports a much smaller intervention than
PR #30:

1. Keep always-loaded repository instructions short, scoped, and navigational.
2. Put durable facts in their owning source; use skills for recurring procedures.
3. Add retrieval, hooks, memory, orchestration, and custom adapters only after a
   realistic task evaluation demonstrates value over the simpler baseline.
4. Evaluate end-state task outcomes, regressions, context/cost, and human review
   burden rather than lexical routing or generated-artifact counts.
5. Land one self-contained concern with its tests and evidence per pull request.

No trusted source reviewed here recommends a fixed repository skill count, a
tracked generated graph or wiki, source/graph commit pairs, transcript-derived
automatic truth, or a custom artifact-lifecycle engine as a default. Those were
ARIA implementation hypotheses, and PR #30 did not establish their value.

## Research Question And Method

This report asks which externally supported practices should constrain the next
ARIA-NBV scaffold attempt after the oversized PR #30 experiment.

Evidence was retrieved on 2026-07-30. Sources were ranked as follows:

- **Normative or protocol evidence:** published specifications and documented
  client behavior. These establish supported formats or security requirements.
- **Maintainer practice evidence:** official guidance from organizations that
  build coding agents. These are credible experience reports, not universal laws.
- **Peer-reviewed empirical evidence:** experiments that isolate an agent
  interface or evaluation effect. Results may not transfer to current models.
- **Upstream vendor evidence:** authoritative for a tool's native behavior, but
  comparative performance claims require independent validation.

ARIA owner preferences and local PR evidence remain separate from these source
classes. External agreement can support a local decision; it cannot silently
promote one.

## High-Confidence Findings

### 1. Root instructions should be a scoped map

The [AGENTS.md open format](https://agents.md/) and Codex's
[documented instruction behavior](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/prompts/base_instructions/default.md)
both use directory-tree scope with the closest applicable file taking
precedence. OpenAI's
[Harness Engineering](https://openai.com/index/harness-engineering/) reports that
one large instruction manual crowded out task context, became stale, and was
hard to verify; the replacement was a short map into structured owners.

**ARIA implication:** keep root `AGENTS.md` to universal safety, authority,
routing, and verification. Put package hazards and commands in the nearest
guide. Do not move the whole project model into `aria-nbv-context` or a root file.

**Limit:** OpenAI's harness article is a greenfield internal case study. Its
roughly 100-line example is not an ARIA budget or a specification requirement.

### 2. Context is a finite resource, not an archive

Anthropic's
[context-engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
recommends the smallest high-signal token set that supports the desired outcome.
Agent Skills guidance similarly warns that overly comprehensive skills introduce
irrelevant branches and recommends progressive disclosure with precise pointers.

**ARIA implication:** measure actual startup metadata, activated skill bodies,
and references read. Do not use aggregate repository file sizes as a proxy for
runtime context, and do not preload plans, debriefs, graph reports, or transcripts.

### 3. Skills should encode coherent, demonstrated procedures

The [Agent Skills specification](https://agentskills.io/specification) defines a
small required surface: `SKILL.md` metadata and instructions, with optional
scripts, references, and assets. Its
[best-practice guidance](https://agentskills.io/skill-creation/best-practices)
recommends grounding skills in real tasks and failures, choosing a coherent unit
of work, providing a default rather than a menu, and moving branch-specific
detail behind explicit context pointers.

The specification does not standardize ARIA's exact invocation policy,
`disable-model-invocation`, a fixed count, or a mandatory router. Those behaviors
must be checked in the actual Codex client.

**ARIA implication:** retain a skill only when it has independent procedural
value, a clear trigger, a default path, and evidence that the agent performs the
task better or more predictably with it. A skill is not a package encyclopedia.

### 4. Scaffold changes need outcome-based evaluations

Agent Skills'
[evaluation guide](https://agentskills.io/skill-creation/evaluating-skills)
recommends realistic prompts, a with-skill versus no-skill or previous-version
baseline, observable assertions, timing data, aggregation, and human review.
Anthropic's
[agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
distinguishes capability from regression suites and combines code-based,
model-based, and human graders. For coding agents, executable end-state tests are
primary; transcript inspection explains failures and costs.

**ARIA implication:** routing-string fixtures and self-consistency checks are
insufficient. Each scaffold capability needs realistic owner-localization or
task-completion trials, adjacent negative prompts, a baseline, multiple trials
where stochasticity matters, and a regression set for capabilities already kept.

### 5. Prefer simple, legible interfaces before orchestration

Anthropic's
[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
recommends simple composable patterns and adding complexity only when evaluation
shows improved outcomes. It also emphasizes transparent plans and carefully
documented, tested tools. The peer-reviewed
[SWE-agent paper](https://papers.nips.cc/paper_files/paper/2024/hash/5a7c947568c1b1328ccc5230172e1e7c-Abstract-Conference.html)
demonstrates that an agent-computer interface can materially affect repository
navigation, editing, and test execution.

**ARIA implication:** exact search, direct source reads, tests, and a small set of
well-documented commands are the baseline. Add Graphify, MCP, MemPalace, or custom
scripts where they close a measured interface gap, not because more modalities
appear more capable.

**Limit:** SWE-agent's benchmark numbers are tied to its 2024 models and tasks.
The transferable result is that interface design matters, not its pass rate.

### 6. Enforce stable invariants, not speculative policy

OpenAI's harness experience supports mechanical checks for stable architecture,
freshness, and cross-link invariants. It does not imply that every preference
needs a hook. Agent Skills advises matching prescriptiveness to fragility, while
Anthropic advises adding complexity only after measured benefit.

**ARIA implication:** a permanent validator must protect a recurring objective
failure mode, have positive and negative fixtures, give useful remediation, and
remain smaller than the policy surface it replaces. Taste, unresolved design,
and historical intent remain review concerns rather than executable policy.

### 7. One self-contained concern is the review unit

Google's
[small-change guidance](https://google.github.io/eng-practices/review/developer/small-cls.html)
states that small, self-contained changes are reviewed more thoroughly, are
easier to reason about and roll back, and should keep related tests with the
change. It specifically recommends separating refactors from behavior changes.

**ARIA implication:** the next series must not combine skills, Graphify, memory,
OMX lifecycle, LitKG retirement, thesis migration, and generated documents.
"Small" means one understandable concern with a green repository, not an
arbitrary line limit.

### 8. Tool capability should be explicit and least-privileged

GitHub's
[customization-surface guidance](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/comparing-cli-features)
separates persistent instructions, task-specific skills, tools, MCP servers,
hooks, subagents, custom agents, and plugins by responsibility. The MCP
[security guidance](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
recommends restricted filesystem/process access, authorization for dangerous
commands, and progressive least-privilege scopes.

**ARIA implication:** do not expose every installed skill, tool, or MCP route by
default. Classify the actual runtime surface and grant capabilities according to
the task. Optional navigation tools must not become hidden mandatory dependencies.

### 9. Graph provenance is useful; Graph authority is not established

Graphify's [current concepts documentation](https://graphify.com/concepts)
defines `EXTRACTED`, `INFERRED`, and `AMBIGUOUS` edges and native `query`, `path`,
and `explain` interfaces. It also documents native outputs `graph.html`,
`GRAPH_REPORT.md`, and `graph.json`. As of this research, upstream releases have
advanced from the previously planned `0.9.22` pin to
[0.9.26](https://github.com/Graphify-Labs/graphify/releases).

These are authoritative descriptions of Graphify behavior. Claims that graph
traversal generally beats grep or embeddings are vendor claims and do not prove
usefulness on ARIA-NBV's mixture of Python, Typst, papers, and scaffold sources.

**ARIA implication:** benchmark unmodified upstream Graphify first. Require
exact-source verification for consequential inferred links. Do not track outputs,
install hooks, pin an older version, or add adapters until the evaluator shows a
specific benefit and acceptable freshness, privacy, runtime, and maintenance cost.

### 10. Stable domain language should precede scaffold automation

The local `domain-modeling` reference recommends challenging overloaded terms,
testing boundaries with concrete scenarios, checking stated behavior against
code, capturing resolved language promptly, and recording only consequential
trade-offs. ARIA should adopt this discipline without copying the generic
`CONTEXT.md` and `docs/adr/` layout. Terms such as "context", "memory", "truth",
"owner", and "artifact" currently carry multiple meanings and can blur the
boundary between authority and evidence.

**ARIA implication:** define a compact authority vocabulary in the existing
source-order owner; challenge conflicting uses during design; test boundaries
through concrete scenarios; and compare declared ownership with hooks, imports,
consumers, and runtime behavior. Existing accepted OMX decision records remain
the place for the few durable trade-offs worth preserving.

## Adopted Principles, Goals, Invariants, And Non-Goals

The next scaffold attempt should adopt the following constraints. They combine
the external evidence above with the domain-modeling discipline while preserving
ARIA's existing source owners.

### Principles

- Use one precise term and one definition owner for each scaffold concept.
- Surface conflicting terminology before designing around it.
- Test ownership boundaries with concrete failure scenarios and implementation
  evidence, not only prose or lexical routing.
- Capture resolved language in its existing owner; create new owner surfaces
  only when real content requires them.
- Record a durable decision only when it is expensive to reverse, surprising
  without rationale, and the result of a genuine trade-off.

### Goals

- Establish a compact ubiquitous language for scaffold governance. At minimum,
  distinguish owner, authority, evidence, derived view, router, runtime state,
  human intent, decision record, plan, capability, and supersession.
- Route through concepts and responsibilities rather than generated catalogs.
- Expose contradictions between intended ownership and actual repository
  behavior before migration or deletion.
- Evaluate the scaffold using scenarios such as stale graph versus current
  source, global versus nearest guidance, skill versus package invariant,
  accepted plan versus newer owner intent, and optional tool unavailable.
- Keep scientific language in the thesis glossary, code, and papers while the
  scaffold vocabulary covers only guidance, evidence, lifecycle, and authority.

### Invariants

- Exact owner sources settle claims; plans, graphs, retrieval, transcripts,
  debriefs, and generated reports provide evidence only.
- A router points to an owner and may explain how to reach it, but does not copy
  the owner's durable facts.
- A derived view remains reproducible, provenance-bearing, and non-authoritative.
- A decision record preserves rationale; it is not a task queue, current-state
  mirror, implementation specification, or proof of implementation.
- Vocabulary definitions describe what a concept is and how it differs from
  adjacent concepts; implementation mechanics remain with code, tests, or the
  owning operational workflow.
- Capability retirement requires a concrete owner, consumer, replacement, and
  scenario-based verification; deleting a named skill or file is not evidence
  that its capability is preserved.

### Non-Goals

- Do not add a root `CONTEXT.md`, `CONTEXT-MAP.md`, or parallel scaffold
  glossary while `.agents/references/source_order.md` can own the compact
  authority vocabulary.
- Do not create `docs/adr/` or an ADR for every file move, skill edit, routing
  adjustment, or reversible implementation choice. Existing accepted OMX
  decision records remain the durable trade-off surface.
- Do not build a generated ontology, transcript-derived vocabulary, or
  natural-language conflict resolver; retrieval tools cannot define terms.
- Do not place general programming terminology or scientific/domain facts in
  the scaffold vocabulary merely because the scaffold references them.
- Do not turn terminology discipline into a mandatory semantic validator.
- Do not duplicate a definition across root guidance, skills, package guides,
  generated reports, and decision records for convenience.

## Where External Sources Agree

Across OpenAI, Anthropic, Agent Skills, GitHub, Google, AGENTS.md, and SWE-agent,
the stable overlap is:

- make repository behavior and success criteria legible to the agent;
- scope durable instructions and disclose detail on demand;
- use simple, documented interfaces with clear defaults;
- ground procedures in real repository work and observed failures;
- verify executable outcomes and preserve human review;
- add complexity only when it improves measured performance; and
- keep changes small enough to understand and reverse.

This overlap supports ARIA's principles of context hygiene, progressive
disclosure, evidence before assertion, minimal custom implementation, and
reviewability.

## Tensions And Non-Transferable Advice

- **Repository knowledge versus single ownership:** OpenAI advocates a rich
  repository knowledge base, while ARIA requires one owner per meaning. These
  are compatible only when indexes point to owners rather than restating them.
- **Domain knowledge in skills:** Agent Skills encourages project-specific
  expertise in skills. ARIA should interpret this as operational knowledge and
  owner pointers, not duplicate scientific facts or formulas.
- **Mechanical enforcement:** OpenAI reports extensive custom linters in a
  million-line agent-built system. ARIA's smaller research repository should not
  infer that more validators are automatically better.
- **Upstream first:** maintained upstream behavior is the default, but OpenAI's
  harness report also describes a justified small local implementation when it
  was more inspectable and testable. Upstream preference is a decision rule, not
  an absolute prohibition.
- **Generated architecture artifacts:** Graphify generates HTML, Markdown, and
  JSON by default. Native generation does not imply that these files should be
  tracked, loaded at startup, or treated as source truth.
- **Plans and memory:** official experience supports durable plans and compacted
  context, but none of the reviewed sources establishes ARIA's proposed OMX
  registry, immutable-bundle layout, debrief trigger, transcript corpus, or
  MemPalace integration as a best practice.

## PR #30 Through The External Lens

The local [PR #30 audit](../../../.agents/references/scaffold_rework/evidence/pr30-reviewability-20260728.html)
recorded 383 changed files and unrelated changes to routing, skills, Graphify,
LitKG, OMX, memory, thesis, and generated artifacts. External guidance predicts
the observed review failure:

- it violated the one-self-contained-change review model;
- it added several layers before comparative task evaluations existed;
- it measured lexical routing and partial prompt surfaces rather than end-state
  capability;
- it mixed refactors, behavior changes, deletion, and generated output; and
- it made source-of-truth claims while some replacement capabilities and
  scientific links were unresolved.

PR #30 nevertheless produced useful experiment candidates: progressive skill
disclosure, measured-autoresearch tests, Graphify provenance and hierarchy,
Typst notation/equation checks, and source links. Each candidate must be isolated
and re-evaluated; the branch is not a migration template.

## Recommended Evidence-Led Series

### Experiment 1: Runtime context and skill baseline

Inventory what the actual Codex client exposes at startup and after activation.
Run realistic positive, near-miss, and no-skill tasks. This is measurement only;
do not delete or rewrite skills in the same change.

Acceptance evidence:

- complete discovered-surface inventory, including uncontrollable system skills;
- activation precision/recall on representative prompts;
- end-state assertions, tokens, duration, and references read; and
- a human review of traces and false activations.

### PR 2: One additive skill/router improvement

Choose the single clearest failure from Experiment 1. Repair one skill or one
router without retiring its predecessor until outcome parity is shown.

### Experiment 3: Native Graphify versus exact source

Compare exact search, unmodified current Graphify, the existing main integration,
and the PR #30 adapter on fixed code, thesis, paper, and scaffold questions.

Acceptance evidence:

- owner-at-k and exact locator/path correctness;
- extracted versus inferred false-link rate;
- stale-graph behavior and source-verification rate;
- task tokens, runtime, generated size, and custom LOC; and
- no hidden network or mandatory-hook requirement.

### PR 4+: One capability disposition at a time

Retire or retain one context generator, state surface, LitKG route, Graphify
adapter, or skill per independently green PR. Preserve the old route until its
replacement is non-inferior on the declared capability.

### Separate thesis and OMX work

Typst equation/notation ownership, Quarto consolidation, and source-link changes
belong in thesis PRs. Artifact supersession and accepted-plan retention need a
separate minimal OMX design experiment. Neither should be bundled with runtime
skill or Graphify changes.

## Claims Not Justified By This Research

This evidence does not justify:

- an exact number of ARIA skills or a universal line/token budget;
- deleting `agents-db`, LitKG, handwritten state, or debriefs without capability
  evidence;
- treating Graphify, MemPalace, or transcripts as current truth;
- tracking a graph, wiki, or generated context in Git;
- mandatory post-commit graph refresh or source/graph commit pairs;
- a custom natural-language intent extraction or conflict-resolution engine;
- a broad external-skill allowlist or recursive closure validator; or
- replaying any implementation slice merely because it existed in PR #30.

## Final Recommendation

Adopt the externally supported process, not an externally inspired architecture:
small scoped instructions, focused skills, simple interfaces, realistic outcome
evals, least privilege, exact-source verification, and self-contained changes.
Everything else remains an ARIA hypothesis that must earn its maintenance cost
through a frozen comparative evaluator.
