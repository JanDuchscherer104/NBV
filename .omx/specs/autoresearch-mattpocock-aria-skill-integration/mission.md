# Autoresearch Mission: Matt Pocock Skills And ARIA-NBV Integration

## Mission

Recommend which current `mattpocock/skills` entries to install or activate for
ARIA-NBV, how they should integrate with the repo-local ARIA skills, and where
the repo should record references to upstream Matt skills.

## Validation Mode

`mission-validator-script`

## Success Criteria

- The recommendation is grounded in the current upstream `mattpocock/skills`
  tree and current ARIA-NBV skill/source-order policy.
- Every Matt skill family is classified as install/activate, explicit-only,
  upstream-reference-only, or skip.
- Every ARIA-NBV local skill is preserved, slimmed, or explicitly marked as a
  possible merge/deletion candidate.
- The recommendation preserves OMX as orchestration, Matt skills as generic
  engineering discipline, and ARIA skills as local domain/evidence sidecars.
- The report names concrete repository surfaces for recording upstream
  references without making upstream skills canonical ARIA truth.

## Non-Goals

- Do not install or delete skills in this pass.
- Do not rewrite `.agents/skills/*` in this pass.
- Do not make Matt skills public thesis truth or ARIA domain owners.
- Do not replace OMX workflow state, goals, phase transitions, or validation
  with Matt workflow skills.

