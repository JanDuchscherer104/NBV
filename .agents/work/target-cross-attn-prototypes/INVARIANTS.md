# Prototype invariants

The tests preserve the properties that should survive any production rewrite:

- actor-visible inputs and oracle supervision are separate values;
- a shared global SE(3) transformation does not change scores;
- joint candidate or target permutation only permutes corresponding outputs;
- removing unrelated targets or candidates does not change retained outputs;
- target-candidate queries never exchange information with other query pairs;
- scene or field memory is encoded once and reused across queries;
- future field tokens are masked at each candidate query time;
- timestamp origin and padded or reordered field history do not change outputs;
- hard actor validity and oracle-label availability are intersected by losses;
- loss reduction is hierarchical across candidates, targets, then scenes;
- repeated refinement reuses one parameter set.

These are architectural invariants, not evidence that the present feature
choices, ordinal head, or one-step objective are scientifically optimal.
