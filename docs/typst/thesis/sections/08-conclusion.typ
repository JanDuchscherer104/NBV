#import "../draft_markers.typ": validation_todo

= Conclusion <sec:thesis-conclusion>

#validation_todo(
  [Rewrite the conclusion as direct, evidence-calibrated answers to RQ1--RQ4. The current conditional outcome tree is useful development guidance but is not a final scientific conclusion.],
  source: [@sec:thesis-results; @sec:thesis-discussion],
  gate: [confirmatory results and discussion support one concise answer per research question],
)

This thesis defines a leakage-auditable experiment for target-conditioned finite-candidate next-best-view planning. Its present contribution is the separation of actor-visible state from oracle supervision, the target-specific reconstruction objective, hard validity and replay contracts, and an artifact-driven reporting seam that keeps provenance and missingness attached to later results.

The available evidence does not answer whether bounded oracle lookahead improves fixed-budget target reconstruction over oracle-greedy or whether a learned finite-horizon policy closes the separate endpoint gap from an actor-visible learned-myopic control to oracle lookahead. The current training-source rollout attempts establish pipeline reachability and reveal a renderer resource gate; the development report fixture establishes the data contract only. Neither supports a held-out policy claim, a population-level effect, or a scale estimate.

The final scientific conclusion is therefore conditional on evidence that is not yet available. A stable oracle metric and positive paired lookahead effect would define measurable headroom for the evaluated finite support. Negligible headroom would be a setup-specific negative result. Unstable oracle evaluation would block planning claims, and stable headroom without the prescribed learned-control gap closure would remain a learned-control failure with several unresolved mechanisms. These outcomes delimit the thesis without extending it to continuous control, online reinforcement learning, or real-device deployment.
