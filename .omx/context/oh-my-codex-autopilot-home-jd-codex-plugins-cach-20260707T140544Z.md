# Autopilot task seed: oh-my-codex-autopilot-home-jd-codex-plugins-cach

- activation prompt / task seed: [$oh-my-codex:autopilot](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.16/skills/autopilot/SKILL.md) 

Deprecate any usage of litkg-rs. Instead employ [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) and initialize it full using codex agents omx orchestration.
- original task status: activation-prompt
- scope note: this seed captures the Autopilot activation prompt and is not guaranteed to include prior conversation context.
- desired outcome: complete the requested Autopilot workflow correctly with durable gate evidence.
- known facts/evidence: Autopilot was activated from a UserPromptSubmit keyword.
- constraints: follow deep-interview -> ralplan -> ultragoal -> code-review -> ultraqa; do not skip gates without persisted evidence.
- unknowns/open questions: to be resolved by the deep-interview gate.
- likely codebase touchpoints: to be discovered during pre-context intake and planning.
