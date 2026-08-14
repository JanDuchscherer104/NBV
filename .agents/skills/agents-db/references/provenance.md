# Agents DB Provenance

Every active issue and todo needs enough context for a future agent to verify
why it exists without chat history.

## Reference Prefixes

- `repo:<path>#<anchor-or-section>` for repo files, docs, code, tests, skills,
  or generated context.
- `bib:<citation-key>` for papers in `docs/references.bib`.
- `arxiv:<id>`, `doi:<doi>`, or `s2:<paperId>` for durable paper identifiers.
- `url:<https-url>` for external API or tool documentation.
- `context7:<library-id>` for Context7-resolved external library docs.
For broad or literature-backed DB additions, inspect the cited primary source
and record only stable source pointers in `references`.

Backlog records should remain compact but auditable. If a context pack omits
active backlog rows or references, amend `issue-023` or `issue-025` rather than
inventing a parallel tracker.

For a Context7-backed external-library record, include the exact resolved
`context7:<library-id>`, current-doc version context, and paired `repo:` anchors
to the installed source and focused test. Context7 is current documentation
evidence; the installed source/test pair and exact repository owner remain the
behavioral authority.
