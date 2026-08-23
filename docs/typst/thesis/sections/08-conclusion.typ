#import "../draft_markers.typ": validation_todo

= Conclusion <sec:thesis-conclusion>

#validation_todo(
  [Rewrite the conclusion as direct, evidence-calibrated answers to RQ1--RQ4. The current conditional outcome tree is useful development guidance but is not a final scientific conclusion.],
  source: [@sec:thesis-results; @sec:thesis-discussion],
  gate: [confirmatory results and discussion support one concise answer per research question],
)

This thesis defines a leakage-auditable experiment for target-conditioned finite-candidate next-best-view planning. Its present contribution is the separation of actor-visible state from oracle supervision, the target-specific reconstruction objective, hard validity and replay contracts, and an artifact-driven reporting seam that keeps provenance and missingness attached to later results.

// - repo:docs/typst/thesis/sections/08-conclusion.typ:11-11
// evidence:
// claims: pc-c1-auditable-experiment-contract

The available evidence does not answer whether bounded oracle lookahead improves fixed-budget target reconstruction or whether a learned finite-horizon policy recovers such headroom. The current training-source rollout attempts establish pipeline reachability and reveal a renderer resource gate; the development report fixture establishes the data contract only. Neither supports a held-out policy claim, a population-level effect, or a scale estimate.

// - repo:docs/typst/thesis/sections/08-conclusion.typ:17-17
// evidence:
// claims: pc-r0-no-confirmatory-policy-result

The final scientific conclusion is therefore conditional on evidence that is not yet available. A stable oracle metric and positive paired lookahead effect would define measurable headroom for the evaluated finite support. Negligible headroom would be a setup-specific negative result. Unstable oracle evaluation would block planning claims, and stable headroom without learned recovery would remain a learned-control failure with several unresolved mechanisms. These outcomes delimit the thesis without extending it to continuous control, online reinforcement learning, or real-device deployment.
