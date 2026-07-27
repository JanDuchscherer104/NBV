// Thesis-local, human-approved review registry. Canonical glossary and notation
// owners remain unchanged; the audit script supplies the occurrence evidence.
#let prune_target_registry = (
  (kind: "glossary", key: "aria-digital-twin", label: "ADT", reason: "trivial common terminology"),
  (kind: "glossary", key: "aria-everyday-objects", label: "AEO", reason: "only needed by another document"),
  (kind: "glossary", key: "area-under-curve", label: "AUC", reason: "trivial common terminology"),
  (kind: "glossary", key: "central-pupil-frame", label: "CPF", reason: "unreferenced implementation detail"),
  (kind: "glossary", key: "degrees-of-freedom", label: "DoF", reason: "trivial common terminology"),
  (kind: "glossary", key: "five-degrees-of-freedom", label: "5DoF", reason: "duplicate/alias"),
  (kind: "glossary", key: "six-degrees-of-freedom", label: "6DoF", reason: "duplicate/alias"),
  (kind: "glossary", key: "left-up-forward", label: "LUF", reason: "unreferenced implementation detail"),
  (kind: "glossary", key: "machine-perception-services", label: "MPS", reason: "only needed by another document"),
  (kind: "glossary", key: "motion-trajectory-data", label: "MTD", reason: "only needed by another document"),
  (kind: "glossary", key: "multi-frame-camera-data", label: "MFCD", reason: "only needed by another document"),
  (kind: "glossary", key: "multi-semi-dense-point-data", label: "MSDPD", reason: "only needed by another document"),
  (kind: "glossary", key: "multi-view-stereo", label: "MVS", reason: "trivial common terminology"),
  (kind: "glossary", key: "scene-script-language", label: "SSL", reason: "only needed by another document"),
  (kind: "glossary", key: "simultaneous-localization-and-mapping", label: "SLAM", reason: "trivial common terminology"),
  (kind: "glossary", key: "three-dimensional-gaussian-splatting", label: "3DGS", reason: "only needed by another document"),
  (kind: "glossary", key: "virtual-reality-standard", label: "VRS", reason: "only needed by another document"),
  (kind: "glossary", key: "visual-inertial-odometry", label: "VIO", reason: "trivial common terminology"),
)
