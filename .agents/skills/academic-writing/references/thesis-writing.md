# ARIA-NBV Thesis Writing Guide

This guide calibrates the reader-facing argument for a computer-science
master's thesis on target-conditioned next-best-view planning. The educational
goal is not to expose every verified contract. It is to teach a technically
competent reader how geometry, time, hierarchy, representation, and data shape
the scientific problem, then let that reader assess the evidence.

## Narrative spine

The default thesis spine is:

1. a limited view budget makes observation choice consequential;
2. target conditioning defines whose reconstruction should improve;
3. the locally strongest view may be a poor first step of a useful sequence;
4. an offline oracle tests whether bounded non-myopic opportunity exists;
5. an actor-visible model tests whether that opportunity can be recovered
   without privileged information;
6. representation, candidate support, and data quality explain when those tests
   succeed or fail.

Secondary representation or simulator questions support this spine. They do
not become co-equal thesis narratives merely because the implementation
contains them.

## ARIA theory lenses

Use these lenses when they clarify a chapter's reader question. They are
questions to teach and test, not conclusions to assert without evidence.

### Geometry and symmetry

- Which geometric objects are represented: poses, rays, points, voxels,
  surfaces, targets, candidate sets, or relations?
- Which group action changes only coordinates, and which output should remain
  invariant or transform equivariantly?
- Can candidate-target or candidate-history relations remove arbitrary global
  frames while preserving decision-relevant geometry?
- Is an apparent isomorphism exact, approximate, or only an architectural
  analogy?

Introduce the physical transformation and desired behavior before terms such
as invariance, equivariance, or SE(3).

### Spatio-temporal state

- What information is available before the current action?
- Which temporal dependence is already captured by explicit poses, observations,
  and budget, and which requires learned memory?
- Does a sequence model address a diagnosed missing dependency, or merely mirror
  the dataset's time axis?
- How do factual successors differ from counterfactual one-step outcomes?

Teach causal prefixes and delayed consequences through a short rollout before
formal return notation.

### Hierarchy

Distinguish scene, requested target, current state, candidate set, selected
action, rollout, and experiment population. Explain how information moves
between levels and which operations should be shared, pooled, masked, or
conditioned. A flat tensor layout is not itself a scientific hierarchy.

### Scene and target representations

Compare representations by the information and symmetries they preserve:
local EVL voxel fields, occupancy or observed/free/unknown state, semidense
points, sparse geometric tokens, target-centred crops, relational graphs,
renderable fields, and combinations thereof. For a discrete field, teach
resolution, sparsity, locality, boundary effects, interpolation, unknown space,
and target alignment before discussing an encoder. Derived representations are
motivated by a specific lost distinction, not by architectural novelty.

### Data and simulation

Separate independent scenes, overlapping snippets, factual transitions,
counterfactual labels, augmentations, and simulator-generated trajectories.
Changing ATEK stride may produce more factual windows and state coverage, but
does not create new independent environments. Synthetic data is useful only
when action, observation, target, modality, noise, and provenance interfaces
match the question being tested. Explicitly expose factual-counterfactual
modality asymmetry and ground-truth leakage.

## Chapter jobs

- **Introduction:** motivate one central planning tension through a concrete
  target example; state the principal questions and subordinate validity
  conditions.
- **Foundations and Related Work:** teach the objective, support, temporal, and
  representation machinery through conceptual tensions. Synthesize sources
  around those tensions rather than attaching a criticism to every paper.
- **Oracle and Data Generation:** use a running state-and-candidate example to
  separate actor information, privileged evaluation, selected factual
  successors, and replay.
- **Method:** begin with one conceptual input-output account and one selected
  method. Formalize components only after their roles are understood; place
  code mappings and design-space ladders later.
- **Experimental Design:** align comparisons with the research questions and
  distinguish scene-level evidence from additional correlated windows or
  labels.
- **Results:** report in research-question order using ordinary metric names,
  denominators, uncertainty, and first-failure attribution.
- **Discussion:** move from observation to mechanism, competing explanation,
  discriminating test, and bounded implication.
- **Conclusion:** answer each principal question directly and introduce no new
  machinery.

## Prose and notation

Prefer positive, concrete definitions. Conceptual prose uses scientific terms;
formal relations use the shared notation owners; implementation identifiers
appear only in an explicit correspondence surface. Introduce an alternative
after the selected idea is understood. Avoid turning development status,
admission rules, manifests, hashes, DTOs, masks, and report keys into the
narrative subject.

Good:

> ARIA-NBV evaluates how much a candidate view improves the requested object's
> reconstruction. Scene-wide coverage remains a separate diagnostic.

Use active voice when it is clearer. Reserve “significant” for statistical
significance and choose one calibrated hedge when evidence is limited. Prefer
mechanisms, examples, measurements, and consequences over generic academic
phrasing.

## Writing modes

- **Fragment capture:** collect claims, examples, objections, and evidence gaps;
  do not promote fragments directly.
- **Shape pass:** satisfy the teaching-first section contract and chapter ledger.
- **Beat pass:** improve paragraph inheritance and chapter transitions without
  changing evidence or notation contracts.

Review in this order: reader journey and conceptual dependency, scientific
correctness, evidence calibration, formal exposition, then sentence style. A
late style pass cannot repair a specification-shaped argument.
