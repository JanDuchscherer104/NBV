# Agents DB Provenance

Every active issue and todo needs enough context for a future agent to verify
why it exists without chat history.

## Reference Prefixes

- `repo:<path>#<anchor-or-section>` for repo files, docs, code, tests, or skills.
- `bib:<citation-key>` for papers in `docs/references.bib`.
- `arxiv:<id>`, `doi:<doi>`, or `s2:<paperId>` for durable paper identifiers.
- `url:<https-url>` for external API or tool documentation.
- `context7:<library-id>` for Context7-resolved external library docs.
For broad or literature-backed DB additions, inspect the exact source owners
and copy only stable source pointers into `references`.

Backlog records should remain compact but auditable. If a context pack omits
active backlog rows or references, amend `issue-023` or `issue-025` rather than
inventing a parallel tracker.
