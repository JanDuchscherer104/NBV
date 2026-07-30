# Theory-Rich Docstrings

Use theory-rich docstrings when an API is easy to misuse without the underlying
math, coordinate convention, or domain model.

## When Richness Is Required

- module docstrings for RRI, geometry, rendering, rollout, VIN, and dataset
  contract modules
- important classes that represent policies, metrics, typed samples, datasets,
  model heads, candidates, or oracle outputs
- functions whose behavior is defined by equations, coordinate transforms,
  metric normalization, masking, stochastic branching, or learning objectives

Small helpers can stay concise. Do not add theory blocks where the signature and
name fully determine behavior.

## Equation Rules

- Include the most important equation when it defines the callable's contract.
- Use `Theory:` for core equations and `Notes:` for caveats, approximations, or
  implementation details.
- Use raw docstrings (`r"""..."""`) when LaTeX contains backslashes.
- State frames, units, domains, and normalization terms near the equation.
- Link to stable internal theory pages or external papers when the equation is
  not self-contained.

Example:

```python
def score_candidate(...):
    r"""Score a candidate view by target-relative reconstruction gain.

    Theory:
        The root-normalized gain compares target reconstruction error before
        and after adding candidate evidence:

        $$
        \mathrm{RRI}(q)=
        \frac{D(P_t, M)-D(P_t \cup P_q, M)}
             {\max(D(P_t, M), \epsilon)}.
        $$

        `P_t` and `P_q` are target-frame point sets and `M` is the ground-truth
        target surface. Invalid candidates are masked before this value is used
        as a learning target.
    """
```

Prefer one decisive equation plus precise prose over a long derivation. Put
full derivations in Quarto theory pages and link them from the docstring.
