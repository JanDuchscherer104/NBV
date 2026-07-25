// Thesis-local semantic override for Q_H while the canonical glossary is regenerated.
// All other entries are imported unchanged from the canonical glossary source.
#import "@preview/glossarium:0.5.10": make-glossary, print-glossary, register-glossary
#import "../shared/glossary.typ": aria-glossary-entries as canonical-entries

#let qh-entry = (
  key: "finite-horizon-q-function",
  short: "Q_H",
  long: "Finite-Horizon Q Function",
  description: "Target-conditioned finite-candidate value family Q_theta(s,e,a,h) that scores each valid candidate for an explicit requested residual horizon h up to a configured maximum H. The thesis-core architecture is one shared horizon-conditioned scorer; dense Q_1 and exact Q_2 targets establish the recursion, horizon-indexed fitted Q supplies longer-horizon targets, and Double Q remains an optional correction for a noisy learned successor maximum.",
  group: "Model",
  custom: (
    anchor: "term-finite-horizon-q-function",
    aliases: (
      "Q_H",
      "variable-horizon Q scorer",
      "horizon-conditioned Q",
      "finite-candidate Q",
      "bounded Q function",
    ),
    category: "model.value",
    parent: "target-conditioned-nbv-mdp",
    definition_short: "Horizon-conditioned candidate-value family for target-conditioned ARIA-NBV.",
    definition_long: "The minimal learned method is one shared scorer Q_theta(s_t,e,i,h) that conditions on the actor state, target, candidate row, and requested residual horizon. H is the maximum supported horizon, h is the query, and h must not exceed the remaining budget. Offline fitted Q learning does not require online interaction. Q_1 is densely supervised, exact Q_2 is a base-case control when successor one-step labels exist, and Q_h for h>1 bootstraps only from a lower-horizon value Q_{h-1}. Double Q may separate successor selection from evaluation to reduce maximization bias, but it does not define the architecture or solve offline-support and state-aliasing failures. Optimality is bounded to the finite candidate, validity, state, and replay-support contract.",
    internal_links: (
      "docs/contents/thesis/questions.qmd#rq4-planning",
      "docs/contents/thesis/roadmap.qmd#roadmap-m5",
      "docs/contents/theory/rl_planning.qmd#q-h-training-contract",
      "docs/contents/literature/rl_planning.qmd#q-h-and-dqn",
    ),
    citations: (
      "FittedQIteration-ernst2005",
      "FixedHorizonTD-deAsis2020",
      "UVFA-schaul2015",
      "DoubleDQN-vanHasselt2015",
    ),
    related: (
      "finite-horizon-return",
      "minimal-counterfactual-state",
      "predicted-target-q",
      "validity-mask",
    ),
    kg_tags: (
      "model",
      "q-learning",
      "variable-horizon",
      "thesis-core",
    ),
    tier: "core",
    lookup_rank: 190,
    symbol_refs: (
      "rl.qh",
      "rl.return_h",
      "rl.s_cf0",
      "rl.a",
    ),
    equation_refs: (
      "rl.q_h",
      "rl.q_backup",
    ),
    typst_macro: none,
    notation: (
      typst: "$Q_H$",
    ),
    formula: (
      label: "Variable-horizon candidate value",
      tex: "Q_\\theta(s_t,e,a,h)=\\mathbb{E}[G_t^{(h)}\\mid s_t,e,a_t=a]",
    ),
    formulae: (
      (
        label: "Lower-horizon fitted target",
        tex: "y_t^{(h)}=r_t^e+\\gamma(1-d_t)\\max_{j:m_{t+1,j}=1}Q_{\\bar\\theta}(s_{t+1},e,j,h-1)",
      ),
      (
        label: "Optional Double-Q selector",
        tex: "j^*=\\arg\\max_{j:m_{t+1,j}=1}Q_\\theta(s_{t+1},e,j,h-1)",
      ),
    ),
  ),
)

#let aria-glossary-entries = canonical-entries.map(
  entry => if entry.key == "finite-horizon-q-function" { qh-entry } else { entry },
)

#let register-aria-glossary() = register-glossary(aria-glossary-entries)
#let print-aria-glossary(..args) = print-glossary(aria-glossary-entries, ..args)
