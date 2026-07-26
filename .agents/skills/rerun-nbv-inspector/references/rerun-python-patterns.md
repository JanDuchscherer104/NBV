# Rerun SDK Evidence And Smoke

Use this branch when implementation depends on Rerun SDK behavior.

1. Check the installed `rerun-sdk` version in the package environment.
2. Consult the matching official Python API documentation and examples at
   <https://rerun.io/docs/reference/types/archetypes> and
   <https://rerun.io/docs/getting-started/data-in/python>.
3. Confirm constructor arguments, transform relations, recording sinks, and
   blueprint behavior in the installed SDK or a focused test. Do not maintain
   a static SDK symbol inventory in this skill.
4. Keep entity paths stable and low-cardinality, initialize one recording, and
   establish the save/spawn/connect sink before logging.
5. Use package owners for coordinate frames, camera conventions, depth units,
   candidate ordering, validity, labels, and storage. Inspector code may only
   adapt those values for display without mutating source samples.
6. Run focused fake-SDK/unit tests, then save a deterministic one-sample `.rrd`
   when compatible data is available. Record the command, SDK version, output
   path, and any exact blocker.

Official SDK evidence owns Rerun behavior; package code and tests own the
inspector implementation and ARIA-NBV contracts.
