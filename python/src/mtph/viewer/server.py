"""A tiny stdlib HTTP server that renders ``.mtph`` files into the reader UI.

* a single file  → opens straight into the reader,
* a folder       → opens a searchable gallery; cards link to ``/view?path=<rel>``.

A ``/__mtph__/status`` endpoint reports file mtimes so the reader can live-reload on save.
Only files beneath the served root are accessible (path-traversal guard).
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

from ..diagram.dsl import DiagramSyntaxError
from ..diagram.plot import PlotError
from ..parser import MtphSyntaxError, load
from ..render.reader import render_error, render_gallery, render_reader
from ..validate import validate


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    @property
    def cfg(self):
        return self.server.cfg  # type: ignore[attr-defined]

    # -- helpers --------------------------------------------------------------
    def _send(self, body: str, status: int = 200, ctype: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _safe(self, rel: str) -> Optional[Path]:
        root = self.cfg["root"]
        try:
            p = (root / rel).resolve()
        except (OSError, ValueError):
            return None
        if p != root and root not in p.parents:
            return None
        return p

    def _render_file(self, path: Path, gallery_href: Optional[str]) -> str:
        katex = self.cfg["katex"]
        try:
            text = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
        except OSError as e:
            return render_error(str(e), title=path.name, katex=katex)
        try:
            doc = load(path)
            errors = validate(doc)
            if errors:
                msg = "Validation errors:\n  - " + "\n  - ".join(errors)
                return render_error(msg, title=path.name, source_text=text,
                                    katex=katex, file_path=str(path), mtime=mtime)
            return render_reader(
                doc, source_text=text, title=doc.title, katex=katex,
                file_path=str(path), mtime=mtime, gallery_href=gallery_href,
            )
        except (MtphSyntaxError, DiagramSyntaxError, PlotError) as e:
            return render_error(str(e), title=path.name, source_text=text,
                                katex=katex, file_path=str(path), mtime=mtime)
        except Exception as e:  # keep the server responsive on any render error
            return render_error(f"Unexpected error: {e}", title=path.name, source_text=text,
                                katex=katex, file_path=str(path), mtime=mtime)

    def _gallery(self) -> str:
        root = self.cfg["root"]
        items: List[dict] = []
        for f in sorted(root.glob("*.mtph")):
            rel = f.relative_to(root).as_posix()
            href = "/view?path=" + quote(rel)
            try:
                doc = load(f)
                m = doc.meta
                items.append({
                    "href": href, "title": m.get("title", f.stem),
                    "subject": m.get("subject"), "topic": m.get("topic"),
                    "difficulty": m.get("difficulty"), "tags": m.get("tags"),
                })
            except Exception:
                items.append({"href": href, "title": f.name, "error": True})
        return render_gallery(items, title=root.name or "Problems", katex=self.cfg["katex"])

    # -- routing --------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/__mtph__/status":
            root = self.cfg["root"]
            try:
                p = Path(q.get("path", [""])[0]).resolve()
            except (OSError, ValueError):
                p = None
            if p is None or (p != self.cfg["target"] and p != root and root not in p.parents):
                self._send(json.dumps({"mtime": None}), status=403, ctype="application/json")
                return
            try:
                self._send(json.dumps({"mtime": p.stat().st_mtime}), ctype="application/json")
            except OSError:
                self._send(json.dumps({"mtime": None}), status=404, ctype="application/json")
            return

        if u.path == "/":
            if self.cfg["is_dir"]:
                self._send(self._gallery())
            else:
                self._send(self._render_file(self.cfg["target"], None))
            return

        if u.path == "/view":
            rel = q.get("path", [""])[0]
            p = self._safe(rel)
            if p is None or not p.is_file():
                self._send("<h1>404 — not found</h1>", status=404)
                return
            back = "/" if self.cfg["is_dir"] else None
            self._send(self._render_file(p, back))
            return

        self._send("<h1>404</h1>", status=404)


def make_server(
    target: os.PathLike | str, *, katex: str = "auto", port: int = 0
) -> Tuple[ThreadingHTTPServer, str]:
    """Create (but do not start) a viewer server for a file or folder. Returns (server, url)."""
    target = Path(target).resolve()
    is_dir = target.is_dir()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    httpd.cfg = {  # type: ignore[attr-defined]
        "target": target,
        "is_dir": is_dir,
        "root": target if is_dir else target.parent,
        "katex": katex,
    }
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    return httpd, url
