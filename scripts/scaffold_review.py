#!/usr/bin/env python3
"""Build a private, self-contained review board for scaffold decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / ".artifacts" / "scaffold-review"
THEME_LABELS = {
    "core": "Core principles",
    "guidance_routing": "Context and routing",
    "skills_workflows": "Skills and external reuse",
    "discovery_upstream": "Graphify and discovery",
    "memory_backlog_debrief": "Memory and Agents DB",
    "omx_artifacts": "OMX lifecycle",
    "docs_crosslink_ownership": "Documentation and linkage",
    "privacy_provenance": "Privacy and provenance",
    "scaffold_evaluation": "Evaluation and reviewability",
    "agents_db": "Agents DB",
    "pr30": "PR #30",
    "scaffold_map": "Scaffold map",
}
THEME_ORDER = (
    "scaffold_map",
    "core",
    "guidance_routing",
    "skills_workflows",
    "discovery_upstream",
    "memory_backlog_debrief",
    "omx_artifacts",
    "docs_crosslink_ownership",
    "privacy_provenance",
    "scaffold_evaluation",
    "pr30",
    "agents_db",
)


@dataclass(frozen=True)
class ReviewItem:
    """One independently reviewable statement and its provenance."""

    id: str
    kind: str
    theme: str
    title: str
    statement: str
    sources: tuple[str, ...]
    details: tuple[str, ...] = ()


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _validate_item(item: ReviewItem) -> None:
    if item.theme not in THEME_LABELS:
        raise ValueError(f"unknown review theme: {item.theme!r}")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", item.kind):
        raise ValueError(f"invalid review item kind: {item.kind!r}")
    if not item.id or not item.statement.strip():
        raise ValueError("review items require a non-empty id and statement")


def load_corpus(path: Path) -> list[ReviewItem]:
    """Load reconciled intent clusters without copying raw transcript text."""

    corpus_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    items: list[ReviewItem] = []
    for row in _read_jsonl(path):
        themes = row.get("themes") or ["core"]
        statement = str(row["canonical_statement"]).strip()
        items.append(
            ReviewItem(
                id=f"intent:{row.get('cluster_id') or _stable_id('intent', statement)}",
                kind="intent",
                theme=str(themes[0]),
                title="Proposed scaffold intent",
                statement=statement,
                sources=(
                    f"private:corpus:{corpus_digest}#{row.get('cluster_id', 'cluster')}",
                ),
                details=tuple(
                    f"Theme: {THEME_LABELS.get(str(theme), str(theme))}"
                    for theme in themes
                ),
            )
        )
    return items


def load_agents_db(repo_root: Path) -> list[ReviewItem]:
    """Load active Agents DB records through their existing TOML interface."""

    items: list[ReviewItem] = []
    for kind in ("issue", "todo", "refactor"):
        path = repo_root / ".agents" / f"{kind}s.toml"
        if not path.is_file():
            continue
        rows = tomllib.loads(path.read_text(encoding="utf-8")).get(kind, [])
        for row in rows:
            record_id = str(row["id"])
            context = tuple(str(value) for value in row.get("context", [])[:3])
            references = tuple(str(value) for value in row.get("references", [])[:8])
            items.append(
                ReviewItem(
                    id=f"agents-db:{kind}:{record_id}",
                    kind=kind,
                    theme="agents_db",
                    title=f"{record_id}: {row['title']}",
                    statement=str(row["description"]),
                    sources=(f"repo:.agents/{kind}s.toml#{record_id}", *references),
                    details=(
                        f"Priority: {row.get('priority', '?')} | Status: {row.get('status', '?')}",
                        *context,
                    ),
                )
            )
    return items


def load_omx(paths: Iterable[Path]) -> list[ReviewItem]:
    """Extract concise goal and target-state bullets from selected OMX Markdown."""

    items: list[ReviewItem] = []
    wanted = re.compile(
        r"outcome|principles?|resolved direction|target|goals?|decision$", re.I
    )
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        heading = ""
        accepted = 0
        for raw in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^#{1,3}\s+(.+?)\s*$", raw)
            if match:
                heading = match.group(1)
                continue
            bullet = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$", raw)
            if not bullet or not wanted.search(heading):
                continue
            statement = re.sub(r"\s+", " ", bullet.group(1)).strip()
            if not 15 <= len(statement) <= 500:
                continue
            source = path.name
            items.append(
                ReviewItem(
                    id=_stable_id("omx", f"{source}\0{heading}\0{statement}"),
                    kind="goal",
                    theme="omx_artifacts",
                    title=f"{path.stem}: {heading}",
                    statement=statement,
                    sources=(f"local-omx:{source}#{heading}",),
                )
            )
            accepted += 1
            if accepted == 24:
                break
    return items


def load_review_items(paths: Iterable[Path]) -> list[ReviewItem]:
    """Load explicit owner-authored findings from JSONL files."""

    items: list[ReviewItem] = []
    for path in paths:
        for row in _read_jsonl(path):
            item = ReviewItem(
                id=f"review:{row['id']}",
                kind=str(row.get("kind", "finding")),
                theme=str(row.get("theme", "core")),
                title=str(row["title"]),
                statement=str(row["statement"]),
                sources=tuple(str(value) for value in row.get("sources", [])),
                details=tuple(str(value) for value in row.get("details", [])),
            )
            _validate_item(item)
            items.append(item)
    return items


def load_pr(repo: str, number: int) -> list[ReviewItem]:
    """Load live PR scope and health through the GitHub CLI."""

    fields = (
        "number,title,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,"
        "mergeStateStatus,additions,deletions,changedFiles,statusCheckRollup,url"
    )
    result = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", repo, "--json", fields],
        check=True,
        capture_output=True,
        text=True,
    )
    pr = json.loads(result.stdout)
    checks = pr.get("statusCheckRollup") or []
    failed = [
        check.get("name", "check")
        for check in checks
        if check.get("conclusion") == "FAILURE"
    ]
    source = f"url:{pr['url']}"
    facts = [
        (
            "PR scope",
            f"PR #{number} changes {pr['changedFiles']} files with +{pr['additions']} / -{pr['deletions']} lines.",
            (f"Head: {pr['headRefName']} @ {pr['headRefOid'][:12]}",),
        ),
        (
            "PR health",
            f"PR #{number} is {pr['state'].lower()}, {'draft' if pr['isDraft'] else 'ready'}, mergeable={pr['mergeable']}, merge-state={pr['mergeStateStatus']}.",
            (f"Failing checks: {', '.join(failed) if failed else 'none'}",),
        ),
        (
            "PR identity",
            f"PR #{number} is titled “{pr['title']}” and targets {pr['baseRefName']} from {pr['headRefName']}.",
            (),
        ),
    ]
    return [
        ReviewItem(
            id=_stable_id("pr", f"{number}\0{title}"),
            kind="finding",
            theme="pr30",
            title=title,
            statement=statement,
            sources=(source,),
            details=details,
        )
        for title, statement, details in facts
    ]


def load_scaffold_map(repo_root: Path) -> list[ReviewItem]:
    """Expose the scaffold's major owned surfaces without indexing every file."""

    specs = (
        ("Guidance", ("AGENTS.md", ".agents/references")),
        ("Skills", (".agents/skills", ".codex/skills")),
        (
            "Backlog",
            (".agents/issues.toml", ".agents/todos.toml", ".agents/refactors.toml"),
        ),
        ("Memory", (".agents/memory",)),
        (
            "Graphify",
            (".graphifyignore", "graphify-out", "scripts/graphify_adapter.py"),
        ),
        ("Literature tools", (".agents/external/litkg-rs", ".configs/litkg.toml")),
        ("Documentation", ("docs/contents", "docs/typst")),
        ("OMX", (".omx",)),
    )
    items: list[ReviewItem] = []
    for title, relatives in specs:
        present = [
            relative for relative in relatives if (repo_root / relative).exists()
        ]
        absent = [relative for relative in relatives if relative not in present]
        statement = f"Review the {title.lower()} surface as one ownership area: {', '.join(present) or 'not present on this branch'}."
        details: list[str] = []
        for relative in present:
            path = repo_root / relative
            if path.is_dir():
                files = [child for child in path.rglob("*") if child.is_file()]
                children = sorted(child.name for child in path.iterdir())[:12]
                details.append(
                    f"{relative}: {len(files)} files; top level: {', '.join(children)}"
                )
            else:
                details.append(f"{relative}: file")
        details.extend(f"Absent: {value}" for value in absent)
        items.append(
            ReviewItem(
                id=_stable_id("surface", title),
                kind="surface",
                theme="scaffold_map",
                title=title,
                statement=statement,
                sources=tuple(f"repo:{relative}" for relative in present),
                details=tuple(details),
            )
        )
    return items


def _deduplicate(items: Iterable[ReviewItem]) -> list[ReviewItem]:
    seen_ids: set[str] = set()
    seen_statements: set[str] = set()
    result: list[ReviewItem] = []
    for item in items:
        _validate_item(item)
        if item.id in seen_ids:
            raise ValueError(f"duplicate review item id: {item.id}")
        seen_ids.add(item.id)
        key = re.sub(r"\W+", " ", item.statement.casefold()).strip()
        if key in seen_statements:
            continue
        seen_statements.add(key)
        result.append(item)
    rank = {theme: index for index, theme in enumerate(THEME_ORDER)}
    return sorted(
        result,
        key=lambda item: (rank.get(item.theme, len(rank)), item.kind, item.id),
    )


def _render_html(items: list[ReviewItem]) -> str:
    payload = [asdict(item) for item in items]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    labels = json.dumps(THEME_LABELS, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARIA-NBV scaffold review</title>
<style>
:root{{--ink:#17201d;--muted:#63706b;--paper:#f5f7f5;--panel:#fff;--line:#d9dfdc;--yes:#16794b;--no:#a43d3d;--accent:#2458a6;--gold:#9a6b12}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 ui-sans-serif,system-ui,sans-serif;letter-spacing:0}}
header{{padding:24px clamp(18px,4vw,56px);background:#16231e;color:white}} h1{{font-size:clamp(24px,4vw,38px);margin:0 0 6px}} header p{{margin:0;color:#cbd7d1}}
.layout{{display:grid;grid-template-columns:minmax(210px,280px) minmax(0,1fr);min-height:calc(100vh - 112px)}}
aside{{border-right:1px solid var(--line);padding:20px;position:sticky;top:0;height:100vh;overflow:auto;background:#edf1ef}}
main{{padding:clamp(20px,4vw,52px);max-width:1100px;width:100%;margin:auto}}
.progress{{height:8px;background:#dfe5e2;margin:16px 0 8px}} .progress span{{display:block;height:100%;background:var(--accent);transition:width .2s}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}} .stat{{background:white;border:1px solid var(--line);padding:10px}} .stat b{{display:block;font-size:20px}}
button,select,input{{font:inherit}} button{{border:1px solid var(--line);background:white;padding:10px 14px;cursor:pointer}} button:hover{{border-color:#7d8b84}}
.theme{{display:block;width:100%;text-align:left;margin:5px 0;padding:8px}} .theme.active{{border-color:var(--accent);color:var(--accent);font-weight:700}}
.card{{background:var(--panel);border:1px solid var(--line);padding:clamp(20px,4vw,42px);min-height:390px;box-shadow:0 12px 32px rgba(20,35,29,.06)}}
.eyebrow{{color:var(--accent);font-weight:700;text-transform:uppercase;font-size:12px}} h2{{font-size:clamp(22px,3vw,34px);margin:8px 0 18px}} .statement{{font-size:clamp(18px,2.2vw,25px);line-height:1.35}}
details{{margin-top:24px;border-top:1px solid var(--line);padding-top:14px}} code{{font-size:12px;overflow-wrap:anywhere}}
.actions{{display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:10px;margin-top:22px}} .yes{{color:var(--yes);border-color:var(--yes)}} .no{{color:var(--no);border-color:var(--no)}} .custom{{color:var(--gold);border-color:var(--gold)}} .actions button.selected{{color:white}} .yes.selected{{background:var(--yes)}} .no.selected{{background:var(--no)}} .custom.selected{{background:var(--gold)}}
.custom-box{{display:none;gap:8px;margin-top:10px}} .custom-box.open{{display:flex}} .custom-box input{{flex:1;padding:10px;border:1px solid var(--line)}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}} .current{{margin-left:auto;color:var(--muted)}} .empty{{padding:60px 0;text-align:center;color:var(--muted)}}
@media(max-width:760px){{.layout{{display:block}}aside{{position:static;height:320px;border-right:0;border-bottom:1px solid var(--line)}}main{{padding:18px}}.actions{{grid-template-columns:1fr}}.current{{width:100%;margin:0}}}}
</style></head><body>
<header><h1>Scaffold decision review</h1><p>One fact at a time. Press Y, N, or C. Decisions stay in this browser until exported.</p></header>
<div class="layout"><aside>
<strong>Progress</strong><div class="progress"><span id="bar"></span></div><div id="progressText"></div>
<div class="stats"><div class="stat"><b id="yesCount">0</b>Yes</div><div class="stat"><b id="noCount">0</b>No</div><div class="stat"><b id="customCount">0</b>Custom</div></div>
<button class="theme active" data-theme="all">All items</button><div id="themes"></div>
<hr><button id="export">Export decisions</button> <button id="reset">Reset</button>
</aside><main><div class="toolbar"><button id="prev">← Previous</button><button id="next">Next →</button><span class="current" id="position"></span></div><div id="app"></div></main></div>
<script>
const ITEMS={data}; const LABELS={labels}; const DIGEST='{digest}'; const KEY='aria-scaffold-review-'+DIGEST;
const el=Object.fromEntries(['app','bar','progressText','yesCount','noCount','customCount','themes','position','prev','next','export','reset'].map(id=>[id,document.getElementById(id)]));
let decisions=JSON.parse(localStorage.getItem(KEY)||'{{}}'), theme='all', index=0;
const save=()=>localStorage.setItem(KEY,JSON.stringify(decisions));
const visible=()=>ITEMS.filter(x=>theme==='all'||x.theme===theme);
function counts(){{const v=Object.values(decisions);el.yesCount.textContent=v.filter(x=>x.answer==='yes').length;el.noCount.textContent=v.filter(x=>x.answer==='no').length;el.customCount.textContent=v.filter(x=>x.answer==='custom').length;el.bar.style.width=(100*v.length/ITEMS.length)+'%';el.progressText.textContent=`${{v.length}} of ${{ITEMS.length}} reviewed`;}}
function decide(answer,note=''){{const item=visible()[index];if(!item)return;decisions[item.id]={{answer,note,reviewed_at:new Date().toISOString()}};save();counts();if(index<visible().length-1)index++;render();}}
function render(){{const list=visible();if(!list.length){{el.app.innerHTML='<div class="empty">No items in this view.</div>';return}}index=Math.min(index,list.length-1);const x=list[index],d=decisions[x.id],recorded=d?` · ${{d.answer}}${{d.note?`: ${{d.note}}`:''}}`:'';el.position.textContent=`${{index+1}} / ${{list.length}}${{recorded}}`;const pressed=a=>d?.answer===a;el.app.innerHTML=`<article class="card"><div class="eyebrow">${{escapeHtml(LABELS[x.theme]||x.theme)}} · ${{escapeHtml(x.kind)}}</div><h2>${{escapeHtml(x.title)}}</h2><p class="statement">${{escapeHtml(x.statement)}}</p>${{x.details.length?`<details><summary>Context</summary><ul>${{x.details.map(v=>`<li>${{escapeHtml(v)}}</li>`).join('')}}</ul></details>`:''}}<details><summary>Sources</summary>${{x.sources.map(v=>`<div><code>${{escapeHtml(v)}}</code></div>`).join('')}}</details><div class="actions"><button class="yes ${{pressed('yes')?'selected':''}}" aria-pressed="${{pressed('yes')}}" onclick="decide('yes')">Y · Accept</button><button class="no ${{pressed('no')?'selected':''}}" aria-pressed="${{pressed('no')}}" onclick="decide('no')">N · Reject</button><button class="custom ${{pressed('custom')?'selected':''}}" aria-pressed="${{pressed('custom')}}" id="customBtn">C · Revise</button></div><div class="custom-box" id="customBox"><input id="customInput" placeholder="Write the corrected statement" value="${{d?.answer==='custom'?escapeAttr(d.note):''}}"><button id="customSave">Save</button></div></article>`;const customBtn=document.getElementById('customBtn'),customBox=document.getElementById('customBox'),customInput=document.getElementById('customInput'),customSave=document.getElementById('customSave');customBtn.onclick=()=>customBox.classList.toggle('open');customSave.onclick=()=>customInput.value.trim()&&decide('custom',customInput.value.trim());}}
function escapeHtml(s){{return String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}} function escapeAttr(s){{return escapeHtml(s)}}
[...new Set(ITEMS.map(x=>x.theme))].forEach(t=>{{const b=document.createElement('button');b.className='theme';b.dataset.theme=t;b.textContent=`${{LABELS[t]||t}} (${{ITEMS.filter(x=>x.theme===t).length}})`;el.themes.appendChild(b)}});
document.querySelectorAll('.theme').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.theme').forEach(x=>x.classList.remove('active'));b.classList.add('active');theme=b.dataset.theme;index=0;render()}});
el.prev.onclick=()=>{{index=Math.max(0,index-1);render()}};el.next.onclick=()=>{{index=Math.min(visible().length-1,index+1);render()}};
function exportPayload(){{const rows=ITEMS.filter(x=>decisions[x.id]).map(x=>({{item_id:x.id,statement:x.statement,sources:x.sources,...decisions[x.id]}}));return {{schema_version:2,dataset_digest:DIGEST,exported_at:new Date().toISOString(),decisions:rows}}}}
el.export.onclick=()=>{{const payload=exportPayload();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{{type:'application/json'}}));a.download=`scaffold-decisions-${{DIGEST}}.json`;a.click();URL.revokeObjectURL(a.href)}};
el.reset.onclick=()=>{{if(confirm('Clear all local decisions for this dataset?')){{decisions={{}};save();counts();render()}}}};
document.addEventListener('keydown',e=>{{if(e.target.tagName==='INPUT')return;if(e.key.toLowerCase()==='y')decide('yes');if(e.key.toLowerCase()==='n')decide('no');if(e.key.toLowerCase()==='c')document.getElementById('customBtn')?.click();if(e.key==='ArrowLeft')el.prev.click();if(e.key==='ArrowRight')el.next.click()}});counts();render();
</script></body></html>"""


def _render_qmd(item_count: int) -> str:
    return f"""---
title: "Scaffold decision review"
format: html
toc: false
---

This private review bundle contains {item_count} scaffold facts, goals, findings,
and backlog records. Review them in the embedded board.

<iframe src="index.html" style="width:100%;height:82vh;border:1px solid #d9dfdc"></iframe>
"""


def build(args: argparse.Namespace) -> int:
    items: list[ReviewItem] = []
    if args.corpus:
        items.extend(load_corpus(args.corpus))
    items.extend(load_agents_db(args.repo_root))
    items.extend(load_omx(args.omx))
    items.extend(load_review_items(args.items))
    items.extend(load_scaffold_map(args.repo_root))
    if not args.no_pr:
        items.extend(load_pr(args.github_repo, args.pr))
    items = _deduplicate(items)
    repo_root = args.repo_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(repo_root) and not output.is_relative_to(
        repo_root / ".artifacts"
    ):
        raise ValueError("repo-local review output must remain under .artifacts/")
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(_render_html(items), encoding="utf-8")
    (output / "review.qmd").write_text(_render_qmd(len(items)), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "item_count": len(items),
        "themes": {
            theme: sum(item.theme == theme for item in items)
            for theme in sorted({item.theme for item in items})
        },
        "sources": {
            "corpus": (
                {
                    "file": args.corpus.name,
                    "sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
                }
                if args.corpus
                else None
            ),
            "omx": [path.name for path in args.omx],
            "review_items": [path.name for path in args.items],
            "agents_db": ".agents/{issues,todos,refactors}.toml",
            "pull_request": None if args.no_pr else f"{args.github_repo}#{args.pr}",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(items)} review items to {output / 'index.html'}")
    return 0


def summarize(args: argparse.Namespace) -> int:
    payload = json.loads(args.decisions.read_text(encoding="utf-8"))
    decisions = payload.get("decisions", [])
    for answer in ("yes", "no", "custom"):
        rows = [row for row in decisions if row.get("answer") == answer]
        print(f"\n## {answer.title()} ({len(rows)})")
        for row in sorted(rows, key=lambda value: value["item_id"]):
            note = f": {row.get('note')}" if row.get("note") else ""
            print(f"- {row['item_id']}: {row['statement']}{note}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Build the private review board")
    build_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    build_parser.add_argument("--corpus", type=Path, help="Reconciled clusters JSONL")
    build_parser.add_argument(
        "--omx",
        type=Path,
        action="append",
        default=[],
        help="Selected OMX Markdown (repeatable)",
    )
    build_parser.add_argument(
        "--items",
        type=Path,
        action="append",
        default=[],
        help="Explicit owner-authored review-item JSONL (repeatable)",
    )
    build_parser.add_argument("--github-repo", default="JanDuchscherer104/ARIA-NBV")
    build_parser.add_argument("--pr", type=int, default=30)
    build_parser.add_argument("--no-pr", action="store_true")
    build_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build_parser.set_defaults(func=build)
    summary_parser = commands.add_parser(
        "summarize", help="Summarize an exported decisions JSON"
    )
    summary_parser.add_argument("decisions", type=Path)
    summary_parser.set_defaults(func=summarize)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
