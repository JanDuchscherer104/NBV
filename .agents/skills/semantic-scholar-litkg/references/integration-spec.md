# Semantic Scholar litkg Integration Spec

Use this reference when implementing ARIA-NBV knowledge graph ingestion in `.agents/external/litkg-rs`.

## Architecture

- Keep `litkg-core` repo-independent. ARIA-NBV paths, globs, relevance tags, and backend defaults belong in TOML configs or examples.
- Add new behavior as small pipeline stages over existing normalized records whenever possible: sync, download/enrich, Semantic Scholar enrichment, parse, materialize, export.
- Keep graph adapters independent: graphify writes deterministic file corpora; Neo4j writes import bundles; Graphiti/code-index provide local runtime enrichment; mempalace is optional temporal memory/KG integration.
- Prefer external implementations over bespoke parsers: the native litkg-rs Semantic Scholar REST client for paper metadata/search/recommendations, Context7 for library documentation lookup, MarkItDown for optional HTTPS-to-Markdown conversion, CodeGraphContext/code-index for code graph extraction, and Rust/Python AST libraries only for gaps.
- Verify dependency freshness at implementation time. As of 2026-04-29, `cargo info mempalace-rs` reports `mempalace-rs = 0.4.2`.

## Source Coverage

Required sources for ARIA-NBV:

- Repo guidance and current owners: root/nested `AGENTS.md`,
  `.agents/AGENTS_INTERNAL_DB.md`, active `.agents/*.toml` backlog files, thesis
  roadmap/questions, and exact package sources.
- Python package source: symbols from `aria_nbv/aria_nbv/**/*.py`, including qualified name, kind, signature, docstring summary, file/line span, config fields, imports, and call/reference edges when available.
- Quarto docs: `docs/**/*.qmd`, with headings, links, code blocks, and cross-links to source symbols where resolvable.
- Typst docs: `docs/typst/**/*.typ`, including the paper include graph and section headings.
- Literature: local BibTeX, arXiv/TeX/PDF assets, and Semantic Scholar paper/citation metadata.
- External library docs: Context7-resolved library ids plus linked provenance for APIs used in the repo.
- Optional HTTPS pages: only when enabled in TOML; convert with MarkItDown and store URL, fetch timestamp, title, and conversion diagnostics.

## TOML Contract

Use one repo-level TOML config as the operator entrypoint. Keep names stable and explicit:

```toml
[repo]
id = "aria-nbv"
root = "."

[literature]
bib_path = "docs/references.bib"
tex_root = "docs/literature/tex-src"
pdf_root = "docs/literature/pdf"

[sources.agent_memory]
include = ["AGENTS.md", "**/AGENTS.md", ".agents/AGENTS_INTERNAL_DB.md", ".agents/*.toml", "docs/contents/thesis/*.qmd"]
required = true

[sources.python]
include = ["aria_nbv/aria_nbv/**/*.py"]
exclude = ["**/.venv/**", "**/__pycache__/**"]
symbols = true
edges = "best-effort"

[sources.docs]
quarto = ["docs/**/*.qmd"]
typst = ["docs/typst/**/*.typ"]

[sources.external_docs]
# Values are exact IDs from .agents/references/context7_library_ids.md.
context7_libraries = ["/pytorch/pytorch", "/pydantic/pydantic", "/isl-org/open3d", "/lightning-ai/pytorch-lightning"]
snapshot_content = false

[sources.web]
enabled = false
markitdown = true
urls = []

[semantic_scholar]
enabled = true
api_key_env = "SEMANTIC_SCHOLAR_API_KEY"
min_interval_s = 1.05
max_retries = 4
batch_size = 100
fields = ["title", "abstract", "authors", "year", "venue", "citationCount", "referenceCount", "influentialCitationCount", "externalIds"]
link_by = ["doi", "arxiv", "title"]

[backends]
graphify = true
neo4j_export = true
graphiti = false
code_index = true
mempalace = false

[storage]
generated_root = ".agents/kg/generated"
db_root = ".agents/kg/db"
lfs = true
```

## Backend Selection

- Use graphify for deterministic, reviewable Markdown/JSON output and default commit-friendly artifacts.
- Use Neo4j export when graph traversal, Cypher import, or MCP graph tooling is needed.
- Use Graphiti when temporal/event-style doc and memory ingestion adds value; keep it optional because it requires local services and model dependencies.
- Use code-index/CodeGraphContext for local code graph extraction before writing a bespoke Python parser.
- Use mempalace only when the task needs durable agent memory, AAAK-style protocol behavior, temporal KG features, or MCP integration that fits its current API cleanly.

## litkg-rs Commands

- `cargo run -p litkg-cli -- enrich-semantic-scholar --config <config>` enriches the local registry by DOI/arXiv/S2 id and writes it back.
- `cargo run -p litkg-cli -- semantic-scholar-search --query '<query>' --limit 20` runs official bulk paper search.
- `cargo run -p litkg-cli -- semantic-scholar-paper --paper ARXIV:<id> --format json` resolves a known paper id.
- `cargo run -p litkg-cli -- semantic-scholar-recommend --positive <paperId>` returns recommendation results from seed papers.
- The Rust client also exposes `get_citations` and `get_references` for citation/reference tracing; add CLI wrappers only when an operator workflow needs them.

## Storage and LFS

- Commit only deterministic configs, schemas, small generated manifests, and intentionally versioned KG bundles.
- Keep local runtime caches such as Neo4j data directories, virtualenvs, downloaded service repos, and temporary MarkItDown outputs ignored.
- Track large database-like artifacts through Git LFS, especially `*.db`, `*.sqlite*`, `*.duckdb`, `*.parquet`, `*.arrow`, and large KG bundle files under `.agents/kg/`.

## Acceptance Criteria

- A fresh agent can discover the skill from `.agents/skills/semantic-scholar-litkg/SKILL.md`.
- litkg-rs remains repo-independent; ARIA-NBV-specific paths live in TOML/config docs.
- Agent memory and root/nested `AGENTS.md` are indexed as required sources.
- Semantic Scholar enrichment is keyed by durable identifiers first, then normalized title fallback.
- Optional external web ingestion cannot run unless TOML enables it.
- Backend outputs are deterministic enough to diff, and large DB artifacts match LFS patterns before staging.
