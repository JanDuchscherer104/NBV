# Sandbox Notes

## Local Inputs

- ARIA root guidance: `AGENTS.md`
- ARIA source-order owner: `.agents/references/source_order.md`
- ARIA skill style owner: `.agents/references/skill_style_guide.md`
- ARIA local skills: `.agents/skills/*/SKILL.md`
- Prior local skill integration plan:
  `.omx/plans/local-agent-skill-recommendations-prd-20260622.md`
- Prior local skill routing test spec:
  `.omx/specs/local-agent-skill-recommendations-test-spec-20260622.md`
- Current user screenshot / installer list, cross-checked against upstream.

## Upstream Inputs

- Repository: `https://github.com/mattpocock/skills.git`
- Checked commit: `896f14d9c25659f03b24e08e4efc3ee69bbade08`
- Local temporary checkout: `/tmp/mattpocock-skills-current`
- Upstream skill count at checked commit: 38 `SKILL.md` files.
- License: MIT.

## Commands

```bash
git ls-remote https://github.com/mattpocock/skills.git HEAD 'refs/heads/*'
rm -rf /tmp/mattpocock-skills-current
git clone --depth 1 https://github.com/mattpocock/skills.git /tmp/mattpocock-skills-current
git -C /tmp/mattpocock-skills-current rev-parse HEAD
find /tmp/mattpocock-skills-current/skills -name SKILL.md -print | sort
rg -n "^(name|description|disable-model-invocation):" /tmp/mattpocock-skills-current/skills/*/*/SKILL.md
rg -n "^(name|description):" .agents/skills/*/SKILL.md
```

## Current Local Observation

`/home/jd/.agents/skills` currently contains no `SKILL.md` files. The
installer screenshot therefore represents available install candidates, not an
already active global Matt skill set.

