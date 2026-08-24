# SENPAI Adoption Updates

The selective adoption is pinned to [W&B SENPAI](https://github.com/wandb/senpai)
commit `772acc597f29065ccad012c749334a287d89badd` from 2026-08-24.

Run:

```bash
git ls-remote https://github.com/wandb/senpai.git HEAD
```

If it differs, review:

```text
https://github.com/wandb/senpai/compare/772acc597f29065ccad012c749334a287d89badd...<new-oid>
```

Then update this pin and only the adopted mechanics in `senpai-performance.md`.
Preserve its excluded-runtime boundary; validate every changed ARIA owner and
run `make check-agent-memory`. An upstream revision never changes ARIA behavior
without scoped review and proof.
