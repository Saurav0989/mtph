"""The reader UI — a viewer experience for ``.mtph`` files (used by ``mtph view``).

Builds three kinds of page on top of the core HTML renderer:

* :func:`render_reader` — a single problem with a toolbar (reveal answer, source, print) and
  live-reload, so the view feels like a dedicated reader rather than a static file.
* :func:`render_gallery` — a searchable card grid for a folder of problems (the library).
* :func:`render_error` — a friendly error page (shown in-place when an edited file is invalid).
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional

from ..model import Document
from .html import (
    _PAGE_CSS,
    _katex_head,
    _render_blocks,
    _render_header,
    _resolve_mode,
    answer_solution_parts,
)
from .md import md_to_html

_READER_CSS = """
/* The reader is a deliberately light reading surface (white panels, light toolbar). Re-pin the
   theme variables here so the shared dark-mode media query can't flip the ink light and make
   figures/math vanish on the reader's white panels. */
body.reader { --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; --paper:#fff;
  --chip-bg:#eef0f3; --chip-ink:#445; --code-bg:#f0f0f2; background:#eef0f3; color:#1a1a1a; }
.toolbar { position:sticky; top:0; z-index:30; display:flex; justify-content:space-between;
  align-items:center; gap:16px; padding:10px 18px; background:rgba(255,255,255,.86);
  backdrop-filter:blur(10px); border-bottom:1px solid var(--line);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
.toolbar .left { font-weight:600; display:flex; gap:14px; align-items:center; min-width:0; }
.toolbar .title { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.toolbar a.back { text-decoration:none; color:#5566aa; font-weight:600; }
.toolbar .right { display:flex; gap:8px; flex:none; }
.btn { font:inherit; font-size:.84rem; border:1px solid var(--line); background:#fff;
  border-radius:8px; padding:5px 12px; cursor:pointer; color:#334; }
.btn:hover { background:#f1f2f4; }
.btn.active { background:#1a1a1a; color:#fff; border-color:#1a1a1a; }
main { margin-top:26px; }
.answer-panel { max-width:760px; margin:0 auto 48px; background:#fff; border:1px solid var(--line);
  border-radius:10px; padding:8px 48px 28px; }
.answer-panel h3 { font-size:.95rem; text-transform:uppercase; letter-spacing:.04em;
  color:#666; margin:1.2rem 0 .3rem; }
.answer-panel[hidden]{ display:none; }
.source-drawer { position:fixed; top:0; right:0; height:100vh; width:min(580px,94vw);
  background:#0d1117; color:#e6edf3; overflow:auto; box-shadow:-10px 0 40px rgba(0,0,0,.3);
  z-index:40; padding:16px 20px 40px; }
.source-drawer[hidden]{ display:none; }
.source-drawer .dh { display:flex; justify-content:space-between; align-items:center;
  font-family:system-ui; margin-bottom:12px; position:sticky; top:0; background:#0d1117; padding-top:4px; }
.source-drawer pre { white-space:pre-wrap; word-break:break-word;
  font:13px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace; margin:0; }
.source-drawer .x { cursor:pointer; color:#9aa4b2; font-size:1.3rem; line-height:1; }
@media print { .toolbar,.source-drawer{ display:none !important; } .answer-panel[hidden]{ display:block !important; } body.reader{ background:#fff; } }
/* gallery */
.gallery { max-width:1120px; margin:32px auto; padding:0 24px; }
.gallery h1 { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; margin:0 0 4px; }
.gallery .sub { color:#667; margin-bottom:20px; }
.search { width:100%; max-width:380px; padding:9px 13px; border:1px solid var(--line);
  border-radius:9px; font:inherit; margin-bottom:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:16px; }
.card { display:block; text-decoration:none; color:inherit; background:#fff;
  border:1px solid var(--line); border-radius:12px; padding:18px 18px 16px; transition:.15s; }
.card:hover { box-shadow:0 8px 24px rgba(0,0,0,.09); transform:translateY(-2px); }
.card .t { font-weight:700; font-size:1.06rem; margin-bottom:8px; line-height:1.3; }
.card .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.card .chip { font-size:.72rem; background:#eef0f3; color:#445; padding:2px 9px; border-radius:20px; }
.card .stars { color:#f5a623; letter-spacing:1px; font-size:.85rem; }
.card .tags { color:#889; font-size:.74rem; margin-top:8px; }
.empty { color:#889; padding:40px 0; }
"""

_LIVE_RELOAD = """
<script>
(function(){
  var path = %PATH%, mtime = %MTIME%;
  if(!path) return;
  setInterval(async function(){
    try {
      var r = await fetch('/__mtph__/status?path=' + encodeURIComponent(path));
      if(!r.ok) return;
      var j = await r.json();
      if(j.mtime && mtime && j.mtime !== mtime) location.reload();
    } catch(e){}
  }, 1000);
})();
</script>
"""

_TOGGLES = """
<script>
function _mtphToggle(id, btn){
  var el = document.getElementById(id);
  if(!el) return;
  var show = el.hasAttribute('hidden');
  if(show){ el.removeAttribute('hidden'); } else { el.setAttribute('hidden',''); }
  if(btn) btn.classList.toggle('active', show);
}
</script>
"""


def _page(title: str, body: str, *, mode: str, body_class: str = "reader") -> str:
    return (
        "<!doctype html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_PAGE_CSS}{_READER_CSS}</style>\n{_katex_head(mode)}\n</head>\n"
        f"<body class='{body_class}'>\n{body}\n</body>\n</html>\n"
    )


def _answer_panel(doc: Document) -> str:
    parts = answer_solution_parts(doc)
    if not parts:
        return ""
    return f'<section id="answerPanel" class="answer-panel" hidden>{"".join(parts)}</section>'


def render_reader(
    doc: Document,
    *,
    source_text: str,
    title: str,
    katex: str = "auto",
    file_path: Optional[str] = None,
    mtime: Optional[float] = None,
    gallery_href: Optional[str] = None,
) -> str:
    mode = _resolve_mode(katex)
    has_answer = bool(answer_solution_parts(doc))

    back = f'<a class="back" href="{html.escape(gallery_href)}">&larr; Library</a>' if gallery_href else ""
    reveal = (
        '<button class="btn" onclick="_mtphToggle(\'answerPanel\', this)">Reveal answer</button>'
        if has_answer else ""
    )
    toolbar = (
        '<header class="toolbar">'
        f'<div class="left">{back}<span class="title">{html.escape(title)}</span></div>'
        '<div class="right">'
        f"{reveal}"
        '<button class="btn" onclick="_mtphToggle(\'sourceDrawer\', this)">Source</button>'
        '<button class="btn" onclick="window.print()">Print</button>'
        "</div></header>"
    )

    main = f"<main>{_render_header(doc.meta)}\n{_render_blocks(doc)}</main>"
    panel = _answer_panel(doc)
    drawer = (
        '<aside id="sourceDrawer" class="source-drawer" hidden>'
        '<div class="dh"><strong>Source &middot; .mtph</strong>'
        '<span class="x" onclick="_mtphToggle(\'sourceDrawer\')">&times;</span></div>'
        f"<pre>{html.escape(source_text)}</pre></aside>"
    )

    live = ""
    if file_path is not None:
        import json

        live = _LIVE_RELOAD.replace("%PATH%", json.dumps(file_path)).replace(
            "%MTIME%", json.dumps(mtime)
        )

    body = toolbar + main + panel + drawer + _TOGGLES + live
    return _page(title, body, mode=mode)


def _stars(d: Optional[int]) -> str:
    if not d:
        return ""
    d = max(0, min(5, int(d)))
    return f'<span class="stars">{"★" * d}{"☆" * (5 - d)}</span>'


def render_gallery(items: List[Dict], *, title: str = "Problems", katex: str = "auto") -> str:
    """items: list of {href, title, subject, topic, difficulty, tags, error}."""
    mode = _resolve_mode(katex)
    cards = []
    for it in items:
        chips = []
        if it.get("subject"):
            chips.append(f'<span class="chip">{html.escape(it["subject"])}</span>')
        if it.get("difficulty"):
            chips.append(_stars(it["difficulty"]))
        tags = " ".join(f"#{html.escape(str(t))}" for t in (it.get("tags") or []))
        search_blob = html.escape(
            " ".join(
                str(x) for x in [it.get("title", ""), it.get("subject", ""),
                                 it.get("topic", ""), tags]
            ).lower()
        )
        err = ' style="border-color:#e3a"' if it.get("error") else ""
        cards.append(
            f'<a class="card" href="{html.escape(it["href"])}" data-search="{search_blob}"{err}>'
            f'<div class="t">{html.escape(it.get("title","Untitled"))}</div>'
            f'<div class="row">{"".join(chips)}</div>'
            + (f'<div class="tags">{tags}</div>' if tags else "")
            + "</a>"
        )
    grid = "".join(cards) if cards else '<div class="empty">No .mtph files found here.</div>'
    body = (
        '<div class="gallery">'
        f"<h1>{html.escape(title)}</h1>"
        f'<div class="sub">{len(items)} problem(s)</div>'
        '<input class="search" placeholder="Search title, subject, tag…" '
        'oninput="(function(q){q=q.toLowerCase();document.querySelectorAll(\'.card\').forEach('
        'c=>{c.style.display=c.dataset.search.indexOf(q)>=0?\'\':\'none\';});})(this.value)">'
        f'<div class="grid">{grid}</div></div>'
    )
    return _page(title, body, mode=mode, body_class="gallery-body")


def render_error(message: str, *, title: str, source_text: str = "", katex: str = "auto",
                 file_path: Optional[str] = None, mtime: Optional[float] = None) -> str:
    mode = _resolve_mode(katex)
    live = ""
    if file_path is not None:
        import json

        live = _LIVE_RELOAD.replace("%PATH%", json.dumps(file_path)).replace(
            "%MTIME%", json.dumps(mtime)
        )
    src = f"<aside class='source-drawer' style='position:static;width:auto;border-radius:10px;margin-top:18px'><pre>{html.escape(source_text)}</pre></aside>" if source_text else ""
    body = (
        "<main><h1>Couldn't render this .mtph file</h1>"
        f'<p style="color:#c0392b;white-space:pre-wrap"><strong>{html.escape(message)}</strong></p>'
        "<p style='color:#667'>Fix the file and save — this view refreshes automatically.</p>"
        f"{src}</main>{_TOGGLES}{live}"
    )
    return _page(title, body, mode=mode)
