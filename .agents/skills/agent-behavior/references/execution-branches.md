# Execution Branches

Load only the branch selected by `agent-behavior`.

## Failure-First Diagnosis

Use for a bug, regression, suspicious metric, or failing check.

1. Establish the smallest red reproducer before editing.
2. Inspect the exact semantic owner and focused tests.
3. Map the proposed change to the verified cause.
4. Run the same proof after the fix.

Complete the branch when the proof is green or its remaining gap is explicit.

## Reversible Learning

Use when uncertainty blocks the selected lane.

1. Choose a production-quality tracer slice that can be retained or a disposable
   prototype that answers one question.
2. Treat prototype output as evidence until an authoritative owner adopts the
   conclusion.
3. Record whether the artifact is retained, promoted, discarded, or deferred.

Complete the branch when the uncertainty is answered and the artifact has an
explicit disposition.
