# Known gaps

- No finite-horizon target or executable `Q_H(s, a)` learner.
- No horizon or candidate-time-step token.
- No selected-action history or evolving candidate-shell representation.
- No bootstrap, Double-Q, target-network, or sequence-return implementation.
- No production Lightning/DataModule integration.
- No benchmark against the existing myopic scorer.
- No parameter-count or data-scaling study.
- No real-data training result is claimed by this preservation branch.
- The originating worktree's tests were blocked before collection by an
  incompatible PyTorch3D/LibTorch binary (`getGlobalPyInterpreter` missing).
- Platform acceleration is explicitly out of scope; no Mojo or Apple-Silicon
  code has been copied into this branch.
