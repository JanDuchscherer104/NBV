// Shared macros and symbols for NBV project
// This file can be imported in both presentations and papers

// ============================================================================
// Text Styling Macros
// ============================================================================

/// Emphasize text in primary color (similar to current emph but explicit)
#let emph-color(body) = text(fill: rgb("fc5555"), body)

/// Italic text
#let textit(body) = text(style: "italic", body)

/// Bold italic text
#let textbf-it(body) = text(weight: "bold", style: "italic", body)

/// Bold text (for completeness)
#let textbf(body) = text(weight: "bold", body)

/// Colored bold text
#let emph-bold(body) = text(fill: rgb("fc5555"), weight: "bold", body)

/// Colored italic text
#let emph-it(body) = text(fill: rgb("fc5555"), style: "italic", body)

/// Monospace/code inline
#let code-inline(body) = text(font: "DejaVu Sans Mono", size: 0.9em, body)

// ============================================================================
// Mathematical Symbols & Notation
// ============================================================================

/// Relative Reconstruction Improvement
#let RRI = "RRI"

/// Coverage Ratio
#let CR = "CR"

/// Chamfer Distance
#let CD = "CD"

/// Next-Best-View
#let NBV = "NBV"

/// Ground Truth
#let GT = "GT"

/// Degrees of Freedom
#let DoF = "DoF"

/// 6 Degrees of Freedom
#let SixDoF = "6DoF"

/// 5 Degrees of Freedom
#let FiveDoF = "5DoF"

/// Area Under Curve
#let AUC = "AUC"

/// Point Cloud
#let PC = "PC"

/// Multi-view Stereo
#let MVS = "MVS"

/// Simultaneous Localization and Mapping
#let SLAM = "SLAM"

/// Occupancy Grid
#let OccGrid = "Occupancy Grid"

// ============================================================================
// Dataset & Model Abbreviations
// ============================================================================
//  TODO: define both short and long names for every acronym or abbreviation - use a suitable package!

/// Aria Synthetic Environments
#let ASE = "ASE"

/// Egocentric Foundation Model 3D
#let EFM3D = "EFM3D"

/// Egocentric Voxel Lifting
#let EVL = "EVL"

/// Aria Digital Twin
#let ADT = "ADT"

/// Aria Everyday Objects
#let AEO = "AEO"

/// Scene Script Structured Language
#let SSL = "SSL"

// ============================================================================
// Common Math Expressions
// ============================================================================

/// RRI formula in display math
#let rri-formula = $
  "RRI"(q) = (CD(cal(R)_"base", cal(R)_"GT") - CD(cal(R)_("base" union q), cal(R)_"GT")) / (CD(cal(R)_"base", cal(R)_"GT"))
$

/// Coverage ratio formula
#let coverage-ratio-formula = $
  "CR"_t = (tilde(N)_t) / (N^*) dot 100%
$

/// Action space definition
#let action-space = $
  cal(A) = bb(R)^3 times S O(2)
$

// ============================================================================
// Utility Functions
// ============================================================================

/// Create a highlighted inline term
#let term(body) = text(weight: "semibold", body)

/// Create a filename/path reference
#let filepath(body) = raw(body, lang: none)

/// Create a citation-style reference
#let paperref(title, authors) = [
  #emph[#title] by #authors
]
