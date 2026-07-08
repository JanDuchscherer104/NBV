# Deprecated VIN Experimental Models

This directory preserves historical VIN model iterations that are no longer
importable from `aria_nbv.vin.experimental`. They are retained as development
evidence for the seminar-era architecture search, while canonical package code
continues under `aria_nbv.vin.model_v3`, `aria_nbv.vin.models`, and the
domain-specific `aria_nbv.vin.{encoders,geometry,modules,diagnostics,types}`
packages.

Archived modules:

- `model.py`: early experimental VIN scorer with mixed utility ownership.
- `model_v1_SH.py`: first spherical-harmonics shell-pose scorer.

Do not add compatibility facades for these modules. New work should either use
the maintained V3 scorer or introduce a canonical model under
`aria_nbv.vin.models`.
