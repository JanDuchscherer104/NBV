# Matt Pocock Skills Contract

ARIA uses a pinned external Matt skill collection for generic engineering
discipline without vendoring it or giving it ownership of project truth.

## Pin And Activation

- Upstream commit: `ed37663cc5fbef691ddfecd080dff42f7e7e350d`.
- Installer: `skills@1.5.20` at the npm integrity recorded in
  `mattpocock_skills_manifest.toml`; `latest` is forbidden.
- The project allowlist is exactly the twelve manifest entries. Every other
  skill discovered in that pinned checkout is disabled for this project.
- Matt skill bodies remain operator-local under the global Codex skill root.
  Do not copy them into `.agents/skills`, `.codex/skills`, or another tracked
  repository path.
- `.codex/config.toml` is ignored operator-local state. Generate its managed
  Matt block with `matt_skills_policy.py render-config`; do not commit trust
  settings, absolute operator paths, or runtime state.

ARIA, plugin, system, and unrelated user skills are outside Matt isolation.
Path-specific `[[skills.config]]` entries affect only the validated Matt paths.
Duplicate IDs, duplicate paths, symlink escapes, or an existing target path
collision fail closed instead of relying on discovery precedence.

## Closure And Prompt Budget

For each selected skill, start from its `SKILL.md`, recursively follow
repository-relative Markdown links outside fenced examples, sort the resulting
repo-relative paths, and hash concatenated `path + NUL + raw bytes` records with
SHA-256. Invocation metadata is pinned separately. Missing, escaping,
ambiguous, added, removed, or changed closure members invalidate the install.

Only six selected Matt skills permit model invocation at the pinned commit.
Their descriptions total 1008 bytes. The ten model-visible ARIA skills total
380 bytes (343 retained bytes plus the 37-byte `agent-behavior` description).
In one clean-home integrated `codex debug prompt-input` run, those six must
appear together with all ten ARIA skills: exactly sixteen unique, complete
entries totaling 1388 bytes, below the WP0-derived ceiling of 1511 bytes. Missing, duplicate,
colliding, truncated, or path-mismatched entries fail closed. Frontmatter
arithmetic (380 ARIA bytes plus 1008 Matt bytes) is only a cross-check of the
CLI-rendered prompt evidence; explicit-only Matt skills consume no
model-visible description budget.

## ARIA Overrides

Repository owners and invariants override external conventions:

- no Matt-created root `CONTEXT.md`, `CONTEXT-MAP.md`, or generic `docs/adr/`;
- no unapproved issue, ticket, PRD, or scratch hierarchy;
- teaching output only in a user-selected teaching workspace;
- dirty worktrees are preserved, and merge/rebase conflicts may be aborted or
  escalated when safe resolution is not established;
- no hidden writes to `.omx`, Codex runtime state, or operator configuration;
- durable plans and handoffs use accepted OMX owners.

The executable conflict fixtures in `scripts/tests/fixtures/matt_policy/`
define these cases. Rollback removes only the managed project activation block;
it does not delete the global Matt installation or alter other configuration.

## Commands

```bash
python3 scripts/scaffold/bootstrap_matt_skills.py
python3 scripts/scaffold/matt_skills_policy.py validate \
  --source-checkout /path/to/pinned/mattpocock-skills \
  --skills-root "$HOME/.agents/skills" \
  --project-config .codex/config.toml
python3 scripts/scaffold/matt_skills_policy.py rollback
```
