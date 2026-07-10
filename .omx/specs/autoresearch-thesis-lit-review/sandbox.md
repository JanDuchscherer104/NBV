# Sandbox Notes

- Worktree was already dirty before this mission. Existing unrelated changes
  were preserved.
- Subagents used for bounded read-only slices:
  - Rawls `019ed62e-9531-7b93-ae15-b4f2295a3f72`: `.agents/work` source and
    implementation-risk extraction.
  - Pasteur `019ed633-5d1f-70a1-81c2-5da830cad17b`: `docs/contents/theory` and
    thesis-claim audit.
  - Boole `019ed633-6e8e-74e2-bc5d-41746f1f92a6`: literature manifest and TeX
    relevance extraction.
- litkg commands used:
  - `make kg-status`
  - `make kg-route KG_TASK='thesis literature review and implementation aims for ARIA-NBV finite-candidate target-conditioned NBV' KG_FORMAT=json`
  - `make kg-show-paper KG_PAPER='EFM3D-straub2024' KG_FORMAT=json`
  - `make kg-show-paper KG_PAPER='e3nn-SphericalHarmonics-2025' KG_FORMAT=json`
  - `./scripts/kg/ingest_papers.sh sync`
  - `./scripts/kg/ingest_papers.sh parse`
  - `./scripts/kg/ingest_papers.sh materialize`
  - `./scripts/kg/ingest_papers.sh export-neo4j`
