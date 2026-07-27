# Thesis Code Link Convention

Use this convention when connecting ARIA-NBV thesis prose, Typst figures, or
agent-facing notes to source code.

## Link Tiers

- `#gh(path, body: none, ref: none, line: none, end: none)` is for
  final-worthy implementation anchors. It remains a hyperlink when draft-only
  links are disabled. Final builds should pass a commit SHA or release tag with
  `--input aria-code-ref=<sha-or-tag>`.
- `#gh-wip(path, body: none, ref: none, line: none, end: none)` is for
  draft/editor navigation. It links to a file or line while writing, but
  compiles to plain visible text when `--input aria-wip-links=false`. With no
  explicit `ref`, it inherits `aria-code-ref`, so it follows the active
  worktree branch supplied by `make thesis-pdf`.
- `#gh-symbol(path, symbol, body: none, ref: none, line: none, end: none)`
  links a known source symbol through the branch- or SHA-resolved GitHub blob
  URL. Use it whenever a thesis source reference names both a file and symbol.
- `#gh-symbol-search(symbol, body: none, language: "python")` is unpinned,
  draft/editor-only GitHub Code Search navigation. It compiles to plain text
  when `--input aria-wip-links=false`; do not use it as a reader-visible or
  final source-symbol anchor.

## Policy

- When a draft marker names an agents-DB file, use
  `#gh(".agents/todos.toml", body: [todo-<id>])` (or the matching issues or
  refactors file) so the reader-visible source is a GitHub link. The agents DB
  remains authoritative for the record's status, scope, acceptance criteria,
  and verification; this reference defines no domain truth.
- Implementation links are navigational aids, not substitutes for citations,
  equations, source-backed prose, or experiment manifests.
- Use final-visible `#gh` sparingly in the thesis body and appendix for code
  anchors that clarify reproducibility or a central implementation contract.
- Use `#gh-wip` and `#gh-symbol-search` only as drafting aids. Use `#gh` or
  path-bearing `#gh-symbol` for reader-visible source anchors, then compile
  final review PDFs with draft links disabled.
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

`make thesis-pdf` automatically supplies `aria-code-ref` from the checked-out
worktree branch. To make a different branch, release tag, or commit SHA the
source-link target, set `THESIS_CODE_REF=<ref>` on that command.

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
