#import "../draft_markers.typ": *

#impl_todo(
  [Add supplementary derivations, camera-convention details, full seminar-substrate adaptation notes, generated manifest tables, and implementation-flow figures.],
  source: [thesis peer-review pass; seminar paper oracle/CORAL/offline-cache sections],
  gate: [final appendix pass],
)

#validation_todo(
  [Resolve the final document order in `template/layout/thesis_template.typ`: lists of figures and tables currently follow the body, the bibliography follows the appendix, and an unnumbered “Appendix A” heading contains a normally numbered chapter. Adopt institution-compliant front-matter, bibliography, and true appendix-numbering behavior before submission.],
  source: [thesis template lines 138--164; independent peer-review critic],
  gate: [submission template freeze],
)

#prune_todo(
  [Remove the entire Draft Intake and Open Work chapter from the submission build. It is an integrated research-and-development diary surface, not a final thesis appendix; promote only evidence-bearing derivations, manifest tables, or reproducibility material.],
  source: [thesis peer review; development-diary allowance],
  gate: [submission build],
)

#include "../sections/06-draft-open-work.typ"
