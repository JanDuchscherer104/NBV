# SENPAI Adoption Updates

Pinned: [W&B SENPAI](https://github.com/wandb/senpai/tree/772acc597f29065ccad012c749334a287d89badd)
`772acc597f29065ccad012c749334a287d89badd`.

Review the adopted contracts at that revision:

- [research-program bootstrap](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/.agents/skills/bootstrap-target/SKILL.md)
- [research grilling](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/.agents/skills/grilling-autoresearch/SKILL.md)
- [experiment assignment](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/plugins/senpai/skills/assign-experiment/SKILL.md)
- [result review and revision](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/plugins/senpai/skills/review-experiment/SKILL.md)
- [research-state maintenance](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/plugins/senpai/skills/maintain-research-state/SKILL.md)
- [W&B evidence](https://github.com/wandb/senpai/blob/772acc597f29065ccad012c749334a287d89badd/plugins/senpai/skills/wandb-primary/SKILL.md)
- [Karpathy keep/discard loop](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md)

```bash
git ls-remote https://github.com/wandb/senpai.git HEAD
```

If changed, review:

```text
https://github.com/wandb/senpai/compare/772acc597f29065ccad012c749334a287d89badd...<new-oid>
```

Update the pin, links, and locally adopted behavior together. Keep Kubernetes,
OpenHands, GitHub-writing control planes, and upstream credentials external.
Validate changed owners and run `make check-agent-memory`.
