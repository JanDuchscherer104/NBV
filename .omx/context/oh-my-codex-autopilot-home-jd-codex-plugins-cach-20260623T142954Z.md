# Autopilot task seed: oh-my-codex-autopilot-home-jd-codex-plugins-cach

- activation prompt / task seed: [$oh-my-codex:autopilot](/home/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.18.14/skills/autopilot/SKILL.md) The current vin module is still a mess. There are many free helper functions that are defined in leaf nodes that hence introduce redundancies and also motivate a further refactoring to allow us maintaining and expanding the module with functionality as necessary for our planned architecture more easily. And also now remove the backward dependencies in the form of the current compatibility facades. and generally try to improve the structure of this module as best as possible. So in the autopilot mode, start by doing some best practices research to see how we can optimally modularize this module and make it more maintainable. And also, as I said, ensure to move all of these three helper functions into shared modules if they can be used elsewhere. I assume that should be the case with some of them otherwise there are probably quite a few candidate functions that could be inlined. Make use of code index and the make context helpers to    Get an overview of all symbols and definitions in the vin module.

Also respect our internal python standards (i.e. making use of the config-as-Factory pattern for all PyTorch modules) and improve the doc-strings wherever possible.
I'm generally a fan of having only one class per source file and maintaining helper functions in a side car file.

We want to maintain the previous third version of our first model that we developed in the main seminar, which was a full scene view introspection network slash RRI scorer. So this model should be kept as is, but also start implementing the facade and scaffold for the planned target-conditioned myopic and multi-step models. 

So this means that we will have at least three final architectures, so the top-level model definitions should then also be in a dedicated module, i.e. aria_nbv/vin/models
- original task status: activation-prompt
- scope note: this seed captures the Autopilot activation prompt and is not guaranteed to include prior conversation context.
- desired outcome: complete the requested Autopilot workflow correctly with durable gate evidence.
- known facts/evidence: Autopilot was activated from a UserPromptSubmit keyword.
- constraints: follow deep-interview -> ralplan -> ultragoal -> code-review -> ultraqa; do not skip gates without persisted evidence.
- unknowns/open questions: to be resolved by the deep-interview gate.
- likely codebase touchpoints: to be discovered during pre-context intake and planning.
