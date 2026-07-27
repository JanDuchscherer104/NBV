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
// Utility Functions
// ============================================================================

/// Create a highlighted inline term
#let term(body) = text(weight: "semibold", body)

/// Create a filename/path reference
#let filepath(body) = raw(body, lang: none)

// ============================================================================
// Thesis/Source Code Link Macros
// ============================================================================

#let aria-github-repo = "JanDuchscherer104/ARIA-NBV"
#let aria-github-base = "https://github.com/" + aria-github-repo

#let _aria-code-ref() = sys.inputs.at("aria-code-ref", default: "main")
#let _aria-wip-links-enabled() = (
  sys.inputs.at("aria-thesis-mode", default: "development") != "submission"
  and sys.inputs.at("aria-wip-links", default: "true") != "false"
)

#let _gh-label(path, body: none) = if body == none {
  code-inline(path.split("/").last())
} else {
  body
}

#let _gh-link-label(body) = text(fill: rgb("#096eda"))[body]

#let _gh-line-anchor(line: none, end: none) = if line == none {
  ""
} else if end == none {
  "#L" + str(line)
} else {
  "#L" + str(line) + "-L" + str(end)
}

#let _github-file-url(path, ref: none, line: none, end: none) = {
  let resolved-ref = if ref == none { _aria-code-ref() } else { ref }
  aria-github-base + "/blob/" + resolved-ref + "/" + path + _gh-line-anchor(line: line, end: end)
}

#let _github-symbol-search-url(symbol, language: "python") = {
  (
    "https://github.com/search?q=repo%3A"
      + aria-github-repo
      + "+language%3A"
      + language
      + "+symbol%3A"
      + symbol
      + "&type=code"
  )
}

/// Link to a file or line in the GitHub repo. Use for final-worthy implementation anchors.
#let gh(path, body: none, ref: none, line: none, end: none) = {
  link(_github-file-url(path, ref: ref, line: line, end: end))[
    #_gh-link-label(_gh-label(path, body: body))
  ]
}

/// Draft-only GitHub file/line link. By default it inherits `aria-code-ref`.
/// Compiles to plain text with `--input aria-wip-links=false`.
#let gh-wip(path, body: none, ref: none, line: none, end: none) = {
  let label = _gh-label(path, body: body)
  if _aria-wip-links-enabled() {
    link(_github-file-url(path, ref: ref, line: line, end: end))[
      #_gh-link-label(label)
    ]
  } else {
    label
  }
}

/// Link a known source symbol to its branch- or SHA-resolved GitHub file anchor.
#let gh-symbol(path, symbol, body: none, ref: none, line: none, end: none) = {
  let label = if body == none { code-inline(symbol) } else { body }
  link(_github-file-url(path, ref: ref, line: line, end: end))[
    #_gh-link-label(label)
  ]
}

/// Draft-only, unpinned GitHub Code Search navigation; never use as a source anchor.
/// Compiles to plain text with `--input aria-wip-links=false`.
#let gh-symbol-search(symbol, body: none, language: "python") = {
  let label = if body == none { code-inline(symbol) } else { body }
  if _aria-wip-links-enabled() {
    link(_github-symbol-search-url(symbol, language: language))[
      #_gh-link-label(label)
    ]
  } else {
    label
  }
}

/// Create a citation-style reference
#let paperref(title, authors) = [
  #emph[#title] by #authors
]
