# Thesis Code Link Convention

Use this convention when connecting ARIA-NBV thesis prose, Typst figures, or
agent-facing notes to source code.

## Link Tiers

- `#gh(path, body: none, ref: none, line: none, end: none)` is for
  final-worthy implementation anchors. It remains a hyperlink when draft-only
  links are disabled. Final builds should pass a commit SHA or release tag with
  `--input aria-code-ref=<sha-or-tag>`.
- `#gh-wip(path, body: none, ref: "main", line: none, end: none)` is for
  draft/editor navigation. It links to a file or line while writing, but
  compiles to plain visible text when `--input aria-wip-links=false`.
- `#gh-symbol(symbol, body: none, language: "python")` is for draft/editor
  navigation to GitHub Code Search symbol results. It also compiles to plain
  visible text when `--input aria-wip-links=false`.

## Policy

- Exact `repo:.agents/{issues,todos,refactors}.toml#<record-id>` values in a
  draft marker's existing `source` field are navigation only. The agents DB
  remains authoritative for the record's status, scope, acceptance criteria,
  and verification; this reference defines no domain truth.
- Implementation links are navigational aids, not substitutes for citations,
  equations, source-backed prose, or experiment manifests.
- Use final-visible `#gh` sparingly in the thesis body and appendix for code
  anchors that clarify reproducibility or a central implementation contract.
- Use `#gh-wip` and `#gh-symbol` liberally during drafting when they help agents
  or humans follow thesis-to-code relationships, then compile final review PDFs
  with draft links disabled.
- Pin final links to a thesis release tag or commit SHA. Prefer a repository
  release, DOI, or archived software citation in the bibliography or
  reproducibility appendix for the scholarly record.
- Treat GitHub symbol search as dynamic and search-index-dependent. It is useful
  for grounding during work, but not an archival symbol permalink.

## Compile Modes

Draft/default:

```bash
cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-draft.pdf --root .
```

Final-link review:

```bash
cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-final.pdf --root . \
  --input aria-wip-links=false \
  --input aria-code-ref=<sha-or-tag>
```

Check that final output has no WIP symbol-search links:

```bash
pdftotext /tmp/aria-thesis-final.pdf - | rg "github.com/search|symbol%3A|symbol:"
```
